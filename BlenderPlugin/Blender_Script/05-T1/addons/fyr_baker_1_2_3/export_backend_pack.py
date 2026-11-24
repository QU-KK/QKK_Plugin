"""Backend texture-export packer (Phase 4 / D6).

Writes float32 RGBA source planes + a ``master_baker.texture_pack.v1`` JSON job,
then invokes ``fyr_baker_backend pack --job``. Falls back to the numpy/Blender
path when the backend does not advertise ``texture_export_pack``.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from . import constants, export_pack, runtime


PACK_SCHEMA = "master_baker.texture_pack.v1"


def last_json_object(stdout: str | None) -> dict | None:
    """The LAST stdout line that parses as a JSON object, or ``None``.

    The backend prints its result as one JSON line, but it is not guaranteed to
    be the final thing on stdout: a driver warning, a flushed progress line or a
    trailing blank can land after it. Reading only ``splitlines()[-1]`` then
    threw away a perfectly good summary, and the caller saw ``written = 0`` for
    an export that had just written every file to disk. Scanning backwards keeps
    the "last one wins" rule while ignoring anything that is not a JSON object.
    """
    if not stdout:
        return None
    for line in reversed(str(stdout).splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


#: Slack on the "written during this run" mtime test. The start time comes from
#: time.time() while mtimes come from the filesystem, and the two clocks are not
#: the same one on a network share, so a couple of seconds keeps a file the run
#: really did write from being dismissed as stale.
_WRITTEN_MTIME_SLACK_SECONDS = 2.0


def _written_from_disk(destinations, started_at: float | None = None) -> int:
    """How many of the pack's destination files this run actually wrote.

    Used only when the backend exited cleanly but printed no usable summary.
    Reporting 0 there tells the artist "nothing was exported" while the files
    sit on disk, which is worse than counting them. But counting every file that
    merely *exists* is how a pack that silently produced nothing reported a full
    export: the destinations are stable paths, so last week's files are sitting
    right there. With ``started_at`` only files modified since the run began are
    counted, which is the difference between "exported" and "was already here".
    """
    total = 0
    cutoff = None if started_at is None else float(started_at) - _WRITTEN_MTIME_SLACK_SECONDS
    for destination in destinations:
        try:
            path = Path(destination)
            if not path.is_file():
                continue
            if cutoff is not None and path.stat().st_mtime < cutoff:
                continue
            total += 1
        except (OSError, TypeError, ValueError):
            continue
    return total


def pack_result(
    stdout: str | None,
    returncode: int,
    destinations,
    started_at: float | None = None,
) -> tuple[int, list[str]]:
    """``(written, warnings)`` for a finished ``fyr_baker_backend pack`` run."""
    warnings: list[str] = []
    payload = last_json_object(stdout)
    if payload is None or "written" not in payload:
        # No summary to trust. A clean exit means the pack ran, so believe the
        # files it touched rather than a missing line of stdout.
        return (_written_from_disk(destinations, started_at) if returncode == 0 else 0), warnings
    try:
        written = int(payload.get("written") or 0)
    except (TypeError, ValueError):
        written = 0
    for warning in payload.get("warnings") or ():
        warnings.append(str(warning))
    if payload.get("error"):
        warnings.append(str(payload["error"]))
    return written, warnings


def backend_pack_available() -> bool:
    """True when the resolved backend advertises ``texture_export_pack``."""
    try:
        backend_path = runtime.resolve_backend_executable()
    except Exception:
        return False
    if not backend_path:
        return False
    try:
        completed = subprocess.run(
            [str(backend_path), "capabilities", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        return False
    if completed.returncode != 0 or not completed.stdout:
        return False
    payload = last_json_object(completed.stdout)
    if payload is None:
        return False
    return bool(payload.get("texture_export_pack"))


def _write_rgba32f(path: Path, array: np.ndarray) -> tuple[int, int]:
    """Write a float32 HxWx4 (or HxWx3, padded) array as raw RGBA **top-down**.

    ``export_pack`` / Blender ``Image.pixels`` are bottom-up (row 0 = bottom).
    Pack planes use the bake/DirectX/PNG convention (row 0 = top), so this flips
    once on the way out. The backend loads that order into ``OverlayImageBuffer``
    with ``y == 0`` at the top — matching ``write_image_file`` / DDS encode.
    """
    arr = np.asarray(array, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise export_pack.ExportPackError(
            f"Source array must be HxWx3/4, got shape {getattr(arr, 'shape', None)}"
        )
    height, width, channels = int(arr.shape[0]), int(arr.shape[1]), int(arr.shape[2])
    if channels == 3:
        rgba = np.ones((height, width, 4), dtype=np.float32)
        rgba[:, :, :3] = arr
    else:
        rgba = arr
    # Bottom-up (Blender) -> top-down (pack / bake ImageBuffer / DirectX).
    rgba = np.ascontiguousarray(np.flipud(rgba), dtype=np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba.tofile(str(path))
    return width, height


def _slot_payload(slot_def) -> dict | None:
    """Convert an already-normalized export slot to the backend channel schema."""
    if slot_def is None:
        return None
    source = str(slot_def.get("source") or "").strip()
    if source.upper() == "CONSTANT" or slot_def.get("constant") is not None:
        return {
            "source": "CONSTANT",
            "channel": str(slot_def.get("channel") or "GRAY"),
            "invert": bool(slot_def.get("invert", False)),
            "constant": float(slot_def.get("constant") or 0.0),
        }
    return {
        "source": source,
        "channel": str(slot_def.get("channel") or "GRAY"),
        "invert": bool(slot_def.get("invert", False)),
    }


def build_pack_job(
    *,
    source_planes: dict[str, dict],
    outputs: list[dict],
) -> dict:
    """Pure: assemble the pack-job dict the backend parses."""
    return {
        "schema": PACK_SCHEMA,
        "sources": source_planes,
        "outputs": outputs,
    }


def _coverage_plane_for_row(
    row,
    spec,
    row_sources: dict[str, str],
    source_planes: dict[str, dict],
    coverage_source,
    workspace: Path,
    cache: dict,
) -> tuple[str, str]:
    """``(coverage_path, warning)`` for a row that asked for extra padding.

    The backend dilates ``composed`` AFTER the resize, so the mask has to be
    rasterized at the output size: the row's own Size when set, else the size of
    the first map-backed source plane (which is what the output keeps). One mask
    per (set, tile, size) is written; every output of that set shares it.

    Padding was silently a no-op before this: the job never carried
    ``coverage_path``, the backend answered "padding requested but no
    coverage_path; left as baked", and that warning was buried under the skip
    messages the dialog reports first. When coverage cannot be produced now, the
    warning says so in the row's own name.
    """
    if coverage_source is None:
        return "", f"{row.filename}: padding skipped: no UV coverage source was supplied; left as baked"
    width, height = int(getattr(row, "width", 0) or 0), int(getattr(row, "height", 0) or 0)
    if width <= 0 or height <= 0:
        for plane_key in row_sources.values():
            plane = source_planes.get(plane_key)
            if plane:
                width, height = int(plane["width"]), int(plane["height"])
                break
    if width <= 0 or height <= 0:
        return "", f"{row.filename}: padding skipped: no map-backed source to size the UV coverage from; left as baked"
    key = (str(getattr(row, "set_key", "")), str(getattr(row, "tile", "")), width, height)
    if key not in cache:
        reason = ""
        mask = None
        try:
            mask = coverage_source(spec, getattr(row, "tile", ""), width, height)
        except Exception as error:
            reason = str(error)
        if mask is not None and tuple(getattr(mask, "shape", ())) != (height, width):
            reason = f"coverage is {getattr(mask, 'shape', None)}, output is {width}x{height}"
            mask = None
        if mask is None:
            cache[key] = ("", reason)
        else:
            path = workspace / f"coverage_{len(cache)}.u8"
            path.write_bytes(export_pack.coverage_mask_to_backend_u8(mask))
            cache[key] = (str(path).replace("\\", "/"), "")
    path, reason = cache[key]
    if not path:
        detail = f" ({reason})" if reason else ""
        return "", (
            f"{row.filename}: padding skipped: no UV coverage could be rasterized for this "
            f"texture set{detail}; left as baked"
        )
    return path, ""


def pack_rows_with_backend(
    pending_rows,
    *,
    outputs: list,
    specs: dict,
    load_source,
    coverage_source=None,
) -> tuple[int, list[str]]:
    """Pack every pending export row through the backend.

    ``load_source(path, map_type) -> np.ndarray`` is injected so the dialog's
    colorspace-aware loader stays the single place that reads bake files.
    ``coverage_source(spec, tile, width, height) -> HxW bool mask | None`` (bottom-up,
    like the loaded planes) supplies the UV coverage the Dilation Infinite / Distance
    padding modes dilate from; without it those modes cannot run and say so.
    Per-row Size/Padding/filter/DDS come from the ``ExportRow`` fields resolved
    by the dialog. Returns ``(written_count, warnings)``.
    """
    backend_path = runtime.resolve_backend_executable()
    if not backend_path:
        raise export_pack.ExportPackError("No backend executable for pack")

    warnings: list[str] = []
    written = 0

    with tempfile.TemporaryDirectory(prefix="fyr_export_pack_") as tmp:
        workspace = Path(tmp)
        plane_cache: dict[tuple[str, str], str] = {}
        source_planes: dict[str, dict] = {}
        coverage_cache: dict = {}
        pack_outputs: list[dict] = []

        for row in pending_rows:
            spec = specs.get(row.set_key)
            if spec is None:
                continue
            missing = tuple(getattr(row, "missing", ()) or ())
            try:
                # Same substitution the numpy path makes: an unbaked channel of a
                # partly-baked output becomes a normal CONSTANT slot carrying that
                # map's neutral, so the backend needs no notion of "missing".
                output_def, _fills = export_pack.substitute_missing_sources(
                    outputs[row.output_index], missing
                )
                slots = export_pack._slot_definitions(dict(output_def, format=row.format_id))
            except Exception as error:
                warnings.append(f"{row.filename}: {error}")
                continue

            row_sources: dict[str, str] = {}
            try:
                for source in row.sources:
                    if source in missing:
                        continue
                    path = (spec.sources.get(source) or {}).get(row.tile, "")
                    map_type, _variant = export_pack.parse_source_key(source)
                    key = (source, path)
                    if key not in plane_cache:
                        array = load_source(path, map_type)
                        # A map/variant name is local to its set and tile. Job keys
                        # and files must identify the actual source image instead.
                        plane_key = f"source_{len(plane_cache)}"
                        plane_path = workspace / f"{plane_key}.rgba32f"
                        width, height = _write_rgba32f(plane_path, array)
                        plane_cache[key] = plane_key
                        source_planes[plane_key] = {
                            "path": str(plane_path).replace("\\", "/"),
                            "width": width,
                            "height": height,
                        }
                    row_sources[source] = plane_cache[key]

                channels = {letter: _slot_payload(slots.get(letter)) for letter in ("R", "G", "B", "A")}
                for entry in channels.values():
                    if entry is None:
                        continue
                    src = entry["source"]
                    if src and src != "CONSTANT":
                        if src not in row_sources:
                            raise export_pack.ExportPackError(f"Missing baked source '{src}' for this output")
                        entry["source"] = row_sources[src]
            except Exception as error:
                warnings.append(f"{row.filename}: {error}")
                continue

            coverage_path = ""
            padding_mode = str(getattr(row, "padding_mode", None) or constants.EXPORT_PADDING_NONE)
            if padding_mode != constants.EXPORT_PADDING_NONE:
                coverage_path, coverage_warning = _coverage_plane_for_row(
                    row, spec, row_sources, source_planes, coverage_source, workspace, coverage_cache
                )
                if coverage_warning:
                    warnings.append(coverage_warning)

            pack_outputs.append(
                {
                    "path": str(Path(row.path)).replace("\\", "/"),
                    "coverage_path": coverage_path,
                    "format": str(row.format_id),
                    "bit_depth": int(row.bit_depth),
                    "color_space": str(row.color_space or "LINEAR"),
                    "width": int(row.width) if int(row.width) > 0 else 0,
                    "height": int(row.height) if int(row.height) > 0 else 0,
                    "resize_filter": str(getattr(row, "resize_filter", None) or "TRIANGLE"),
                    "padding_mode": str(getattr(row, "padding_mode", None) or "NONE"),
                    "padding_size": int(getattr(row, "padding_size", 0) or 0),
                    "dds_compression": str(getattr(row, "dds_compression", None) or "BC7"),
                    # The packer only honours this for DDS; keep it off other formats so
                    # the job says what will actually happen.
                    "generate_mips": bool(getattr(row, "dds_generate_mips", False))
                    and str(row.format_id).upper() == constants.IMAGE_FORMAT_DDS,
                    "channels": channels,
                }
            )

        if not pack_outputs:
            return 0, warnings

        job = build_pack_job(source_planes=source_planes, outputs=pack_outputs)
        job_path = workspace / "pack.json"
        job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")

        pack_started_at = time.time()
        try:
            completed = subprocess.run(
                [str(backend_path), "pack", "--job", str(job_path)],
                capture_output=True,
                text=True,
                timeout=None,
                check=False,
            )
        except Exception as error:
            raise export_pack.ExportPackError(f"Backend pack failed to launch: {error}") from error

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise export_pack.ExportPackError(
                f"Backend pack failed (exit {completed.returncode}): {detail or 'no detail'}"
            )

        written, pack_warnings = pack_result(
            completed.stdout,
            completed.returncode,
            [entry["path"] for entry in pack_outputs],
            pack_started_at,
        )
        warnings.extend(pack_warnings)
        return written, warnings
