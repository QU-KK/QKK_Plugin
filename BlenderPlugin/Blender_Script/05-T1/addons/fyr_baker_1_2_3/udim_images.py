"""Native Blender ``TILED`` image datablocks for Fyr's UDIM outputs, and stale-tile cleanup.

One logical texture-set/map result is one Blender Image, never N. Its ``filepath`` carries
``constants.UDIM_PATH_TOKEN`` and its ``tiles`` collection holds the concrete tiles Fyr wrote
(GDD-equivalent: plan §1.5). The alternative -- a datablock per file -- is what turns a
40-tile character into 40 output rows and 40 image users, and it is exactly what §9.1 forbids.

Two verified Blender behaviours drive the shape of this module (plan §5.6, Blender 5.1.1):

* ``image.tiles.remove()`` works on the default 1001 tile, so a set that does not include
  1001 is expressible -- but the collection must never be emptied, so removal happens only
  after the replacement tiles are in;
* **a tile with no file on disk does not survive ``reload()``** -- Blender prunes it. A tile
  is therefore only ever added once its file actually exists, which also makes incremental
  completion safe: a not-yet-written tile is skipped now and picked up on a later refresh
  rather than added and silently pruned.

The header probing at the bottom is deliberately stdlib-only. Tile dimensions are required by
the handoff manifest (§9.3) and tiles may legitimately differ in resolution, so the file on
disk is the only honest source -- not the project settings, which the artist may have changed
since the bake.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct

from . import udim


# Mirrors runtime.py's managed-image markers; a tiled output is still a managed output.
MANAGED_OUTPUT_PATH_KEY = "_master_baker_output_path"
# Per-tile mtimes, joined. Blender exposes no per-tile reload, so this is what makes
# "reload only when something changed" possible instead of reloading on every refresh.
TILE_SIGNATURE_KEY = "_master_baker_udim_tile_signature"


class UdimImageError(RuntimeError):
    """A tiled datablock could not be built or refreshed."""


def _normalized(path) -> str:
    text = str(path or "").strip()
    if not text:
        return ""

    def compute() -> str:
        try:
            resolved = Path(text).expanduser().resolve(strict=False)
        except Exception:
            resolved = Path(text).expanduser()
        return os.path.normcase(str(resolved))

    # Memoised inside runtime_output_images.normalized_path_cache() (one output refresh).
    from . import runtime_output_images

    return runtime_output_images.cached_normalized_path("udim", text, compute)


def _mtime_ns(path) -> int:
    text = str(path or "").strip()
    if not text:
        return 0
    try:
        return int(Path(text).stat().st_mtime_ns)
    except OSError:
        return 0


def _exists(path) -> bool:
    text = str(path or "").strip()
    if not text:
        return False
    try:
        return Path(text).is_file()
    except OSError:
        return False


def tile_signature(tiles) -> str:
    """Stable ``tile:mtime`` digest of a tile set, used to skip no-op reloads."""
    parts = [
        f"{int(tile_number)}:{_mtime_ns(path)}"
        for tile_number, path in sorted(tiles, key=lambda item: int(item[0]))
    ]
    return ",".join(parts)


def existing_tiles_on_disk(tiles) -> list[tuple[int, str]]:
    """Filter a desired tile set down to the tiles that actually have a file.

    Adding a tile whose file is missing is not merely useless -- Blender prunes it on the
    next ``reload()``, which would make incremental completion look like tiles randomly
    disappearing.
    """
    return sorted(
        ((int(tile_number), str(path)) for tile_number, path in tiles if _exists(path)),
        key=lambda item: item[0],
    )


def _image_matches_logical_path(image, normalized_logical: str) -> bool:
    if not normalized_logical:
        return False
    try:
        marked = image.get(MANAGED_OUTPUT_PATH_KEY, "")
    except Exception:
        marked = ""
    if str(marked or "") == normalized_logical:
        return True
    for attribute in ("filepath_raw", "filepath"):
        value = str(getattr(image, attribute, "") or "")
        if value and _normalized(value) == normalized_logical:
            return True
    return False


def find_tiled_image(images, logical_path):
    normalized_logical = _normalized(logical_path)
    if not normalized_logical or images is None:
        return None
    for image in images:
        if _image_matches_logical_path(image, normalized_logical):
            return image
    return None


def _tile_numbers(image) -> list[int]:
    numbers: list[int] = []
    for tile in getattr(image, "tiles", []) or ():
        try:
            numbers.append(int(getattr(tile, "number", 0) or 0))
        except (TypeError, ValueError):
            continue
    return sorted(numbers)


def _active_tile_number(image) -> int:
    tiles = getattr(image, "tiles", None)
    if tiles is None:
        return 0
    active = getattr(tiles, "active", None)
    if active is not None:
        try:
            return int(getattr(active, "number", 0) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _restore_active_tile(image, wanted_number: int) -> None:
    """Put the active tile back where the artist left it, if that tile still exists."""
    if not wanted_number:
        return
    tiles = getattr(image, "tiles", None)
    if tiles is None:
        return
    for index, tile in enumerate(tiles):
        try:
            if int(getattr(tile, "number", 0) or 0) != int(wanted_number):
                continue
        except (TypeError, ValueError):
            continue
        try:
            tiles.active_index = index
        except Exception:
            try:
                tiles.active = tile
            except Exception:
                pass
        return


def _reconcile_tiles(image, wanted: list[int]) -> bool:
    """Make ``image.tiles`` hold exactly ``wanted``. Returns True if anything changed.

    Additions run before removals so the collection is never momentarily empty -- which is
    the whole reason a non-1001-anchored set needs care at all.
    """
    if not wanted:
        return False
    changed = False
    current = set(_tile_numbers(image))
    for tile_number in wanted:
        if tile_number in current:
            continue
        try:
            image.tiles.new(tile_number=int(tile_number))
        except Exception as exc:  # pragma: no cover - Blender-only failure path
            raise UdimImageError(f"could not add UDIM tile {tile_number}: {exc}") from exc
        changed = True
    wanted_set = set(wanted)
    for tile in [tile for tile in list(getattr(image, "tiles", []) or ())]:
        try:
            number = int(getattr(tile, "number", 0) or 0)
        except (TypeError, ValueError):
            continue
        if number in wanted_set:
            continue
        try:
            image.tiles.remove(tile)
            changed = True
        except Exception:
            # Leaving a spare tile in place is strictly better than aborting the refresh;
            # the tile simply resolves to nothing.
            continue
    return changed


def sync_tiled_image(
    logical_path,
    tiles,
    *,
    images,
    name: str = "",
):
    """Create or refresh the one ``TILED`` datablock for a logical output.

    ``tiles`` is an iterable of ``(udim_tile, concrete_path)``. Tiles without a file on disk
    are skipped, so this is safe to call repeatedly while a bake is still completing.

    Returns the image, or ``None`` when no tile has been written yet.
    """
    if images is None:
        raise UdimImageError("Blender image datablocks are not available")
    logical_text = str(logical_path or "").strip()
    if not logical_text or not udim.is_logical_udim_path(logical_text):
        raise UdimImageError(f"not a logical <UDIM> path: {logical_path!r}")

    live = existing_tiles_on_disk(tiles)
    if not live:
        return None

    signature = tile_signature(live)
    image = find_tiled_image(images, logical_text)
    created = False
    if image is None:
        first_width, first_height = read_image_size(live[0][1])
        image = images.new(
            name or Path(logical_text).stem,
            width=max(1, first_width),
            height=max(1, first_height),
            tiled=True,
        )
        created = True

    try:
        image.filepath = logical_text
    except Exception:
        pass
    try:
        image.filepath_raw = logical_text
    except Exception:
        pass
    try:
        image.source = "TILED"
    except Exception:
        pass

    active_before = _active_tile_number(image)
    changed = _reconcile_tiles(image, [tile_number for tile_number, _path in live])

    try:
        previous_signature = str(image.get(TILE_SIGNATURE_KEY, "") or "")
    except Exception:
        previous_signature = ""
    # Blender has no per-tile reload; the signature is what keeps a refresh from re-decoding
    # every tile of a 40-tile set when a single tile's file moved on.
    if created or changed or signature != previous_signature:
        try:
            image.reload()
        except Exception:
            pass

    _restore_active_tile(image, active_before)

    for key, value in ((MANAGED_OUTPUT_PATH_KEY, _normalized(logical_text)), (TILE_SIGNATURE_KEY, signature)):
        try:
            image[key] = value
        except Exception:
            pass
    return image


def sync_project_output_images(project, *, images):
    """Refresh a tiled datablock for every tiled entry in ``project.latest_outputs``.

    Untiled outputs are left entirely alone -- they keep going through the existing
    single-image path in ``runtime``, unchanged.
    """
    synced = []
    # A texture set's composite is one logical output shared by every member group's entry
    # (Ubrion: 594 entries, a few dozen logical paths), and each sync_tiled_image call writes
    # several datablock properties. A repeat with the same path AND the same tiles cannot
    # change anything the first call left, so it is skipped (2026-09-29).
    seen: set[tuple[str, tuple[tuple[int, str], ...]]] = set()
    for output in getattr(project, "latest_outputs", []) or ():
        logical_path = str(getattr(output, "udim_logical_path", "") or "").strip()
        if not logical_path:
            continue
        tiles = [
            (int(getattr(tile, "udim_tile", 0) or 0), str(getattr(tile, "file_path", "") or ""))
            for tile in getattr(output, "udim_tiles", []) or ()
            if not bool(getattr(tile, "stale", False)) and int(getattr(tile, "udim_tile", 0) or 0)
        ]
        if not tiles:
            continue
        identity = (logical_path, tuple(tiles))
        if identity in seen:
            continue
        seen.add(identity)
        try:
            image = sync_tiled_image(
                logical_path,
                tiles,
                images=images,
                name=str(getattr(output, "display_name", "") or "") or Path(logical_path).stem,
            )
        except UdimImageError:
            continue
        if image is not None:
            synced.append(image)
    return synced


# --------------------------------------------------------------------------------------
# Stale tiles
#
# A tile that stops being occupied leaves its file behind. §1.4 is explicit that this file is
# never removed silently -- silent deletion of a texture the artist may have hand-edited or
# referenced downstream is unrecoverable, and the cost of leaving it is a stale row in a list.
# So: report always, delete only when the artist asks.
# --------------------------------------------------------------------------------------


def find_stale_tile_files(logical_path, live_tiles, *, directory_names=None) -> list[tuple[int, str]]:
    """Concrete tile files on disk that the current tile set no longer claims."""
    logical_text = str(logical_path or "").strip()
    if not logical_text or not udim.is_logical_udim_path(logical_text):
        return []
    live_numbers = {int(tile_number) for tile_number in live_tiles or ()}
    return [
        (tile_number, path)
        for tile_number, path in udim.sibling_tile_paths(logical_text, directory_names=directory_names)
        if tile_number not in live_numbers
    ]


def delete_stale_tile_files(paths) -> tuple[list[str], list[str]]:
    """Delete the named files. Returns ``(deleted, failures)``.

    Takes an explicit path list rather than a project so that nothing can widen the blast
    radius between what the artist was shown and what is removed.
    """
    deleted: list[str] = []
    failures: list[str] = []
    for raw_path in paths or ():
        text = str(raw_path or "").strip()
        if not text:
            continue
        # A path with no tile segment is by definition not a stale tile file; refusing it
        # keeps a bad caller from deleting a project's only untiled output.
        if not udim.tile_from_path(text):
            failures.append(f"{text}: not a UDIM tile file")
            continue
        try:
            Path(text).unlink()
            deleted.append(text)
        except FileNotFoundError:
            deleted.append(text)
        except OSError as exc:
            failures.append(f"{text}: {exc}")
    return deleted, failures


# NOTE: this operator's eventual home is `addon/operators.py`, alongside every other
# `master_baker.*` operator; it lives here only because operators.py was being edited
# concurrently when UDIM handoff landed. Moving it is a cut-and-paste plus adding the class
# to operators.py's registration tuple -- no logic changes.
def _active_project_stale_tiles(context) -> list[str]:
    """Stale tile files of the ACTIVE project, or an empty list.

    The old lookup read ``scene.master_baker_project``, a property this addon never
    registers (the real root is ``scene.fyr_baker_settings``), so poll() was always
    False: the operator was permanently greyed out and stale tile files accumulated
    with no way to remove them.
    """
    from . import properties

    scene = getattr(context, "scene", None) if context is not None else None
    project = properties.get_active_project(scene) if scene is not None else None
    if project is None:
        return []
    try:
        return list(properties.project_stale_tile_paths(project) or [])
    except Exception:
        return []


try:  # pragma: no cover - Blender-only
    import bpy

    class MASTER_BAKER_OT_cleanup_stale_udim_tiles(bpy.types.Operator):
        """Delete output files for UDIM tiles that are no longer occupied. Fyr never removes these on its own"""

        bl_idname = "master_baker.cleanup_stale_udim_tiles"
        bl_label = "Clean Up Stale UDIM Tiles"
        # No UNDO: it removes rows from a CollectionProperty, and every structural
        # operator in this addon drops it for the memfile-undo realloc crash (T74067).
        bl_options = {"REGISTER"}

        @classmethod
        def poll(cls, context):
            return bool(_active_project_stale_tiles(context))

        def execute(self, context):
            from . import properties

            project = properties.get_active_project(getattr(context, "scene", None))
            paths = properties.project_stale_tile_paths(project) if project is not None else []
            if not paths:
                self.report({"INFO"}, "No stale UDIM tile files")
                return {"CANCELLED"}
            deleted, failures = delete_stale_tile_files(paths)
            for output in getattr(project, "latest_outputs", []) or ():
                for index in reversed(range(len(getattr(output, "udim_tiles", [])))):
                    tile = output.udim_tiles[index]
                    if bool(getattr(tile, "stale", False)) and str(getattr(tile, "file_path", "")) in deleted:
                        output.udim_tiles.remove(index)
            if failures:
                self.report({"WARNING"}, f"Removed {len(deleted)} stale tile files, {len(failures)} failed")
            else:
                self.report({"INFO"}, f"Removed {len(deleted)} stale tile files")
            return {"FINISHED"}

    _CLASSES = (MASTER_BAKER_OT_cleanup_stale_udim_tiles,)

except Exception:  # pragma: no cover - importing outside Blender
    bpy = None
    # Outside Blender (unit tests) there is nothing to register; register()/unregister()
    # become no-ops rather than import errors.
    _CLASSES = ()


# --------------------------------------------------------------------------------------
# Image dimension probing
# --------------------------------------------------------------------------------------


def _png_size(handle) -> tuple[int, int] | None:
    header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def _tga_size(handle) -> tuple[int, int] | None:
    # TGA has no magic number, so this is only ever reached by extension.
    header = handle.read(18)
    if len(header) < 18:
        return None
    width, height = struct.unpack("<HH", header[12:16])
    return int(width), int(height)


def _tiff_size(handle) -> tuple[int, int] | None:
    header = handle.read(8)
    if len(header) < 8:
        return None
    if header[:4] == b"II\x2a\x00":
        endian = "<"
    elif header[:4] == b"MM\x00\x2a":
        endian = ">"
    else:
        return None
    (offset,) = struct.unpack(endian + "I", header[4:8])
    handle.seek(offset)
    count_bytes = handle.read(2)
    if len(count_bytes) < 2:
        return None
    (entry_count,) = struct.unpack(endian + "H", count_bytes)
    width = height = 0
    for _index in range(entry_count):
        entry = handle.read(12)
        if len(entry) < 12:
            break
        tag, field_type = struct.unpack(endian + "HH", entry[:4])
        if tag not in (256, 257):
            continue
        if field_type == 3:  # SHORT, stored left-justified in the 4-byte value field
            (value,) = struct.unpack(endian + "H", entry[8:10])
        elif field_type == 4:  # LONG
            (value,) = struct.unpack(endian + "I", entry[8:12])
        else:
            continue
        if tag == 256:
            width = int(value)
        else:
            height = int(value)
    return (width, height) if width and height else None


def _exr_size(handle) -> tuple[int, int] | None:
    header = handle.read(8)
    if len(header) < 8 or header[:4] != b"\x76\x2f\x31\x01":
        return None
    # Attribute list: name\0 type\0 size(int32) value...  Stop at the terminating null name.
    for _guard in range(512):
        name = _read_null_terminated(handle)
        if name is None or name == b"":
            return None
        attribute_type = _read_null_terminated(handle)
        if attribute_type is None:
            return None
        size_bytes = handle.read(4)
        if len(size_bytes) < 4:
            return None
        (size,) = struct.unpack("<i", size_bytes)
        payload = handle.read(size)
        if len(payload) < size:
            return None
        if name == b"dataWindow" and attribute_type == b"box2i" and size >= 16:
            x_min, y_min, x_max, y_max = struct.unpack("<iiii", payload[:16])
            return int(x_max - x_min + 1), int(y_max - y_min + 1)
    return None


def _read_null_terminated(handle) -> bytes | None:
    collected = bytearray()
    while True:
        byte = handle.read(1)
        if not byte:
            return None
        if byte == b"\x00":
            return bytes(collected)
        collected.extend(byte)
        if len(collected) > 255:
            return None


_SIZE_READERS = {
    ".png": _png_size,
    ".tga": _tga_size,
    ".tif": _tiff_size,
    ".tiff": _tiff_size,
    ".exr": _exr_size,
}


def read_image_size(file_path) -> tuple[int, int]:
    """``(width, height)`` from the file header, or ``(0, 0)`` when it cannot be read.

    Header-only on purpose: the handoff manifest needs the dimensions of potentially dozens of
    tiles, and decoding them would cost seconds for information that sits in the first 24
    bytes. Never raises -- a manifest with a zero size is far better than a failed handoff.
    """
    text = str(file_path or "").strip()
    if not text:
        return (0, 0)
    path = Path(text)
    reader = _SIZE_READERS.get(path.suffix.lower())
    if reader is None:
        return (0, 0)

    def compute() -> tuple[int, int]:
        try:
            with path.open("rb") as handle:
                size = reader(handle)
        except (OSError, struct.error, ValueError):
            return (0, 0)
        if not size:
            return (0, 0)
        width, height = size
        return (int(width) if width > 0 else 0, int(height) if height > 0 else 0)

    # One progress update read every tile header twice (Ubrion: 2,340 opens); inside
    # runtime_output_images.normalized_path_cache() each file is read once.
    from . import runtime_output_images

    return runtime_output_images.cached_normalized_path("imagesize", text, compute)


def register():
    """Register the stale-tile cleanup operator.

    Defined here rather than in operators.py only because that file was being edited
    concurrently; the class carries a note about its eventual home. Without this the operator
    existed but was never registered, so invoking it would have failed.
    """
    if _CLASSES:
        from .registration import safe_register_class

        for cls in _CLASSES:
            safe_register_class(cls)


def unregister():
    if _CLASSES:
        from .registration import safe_unregister_class

        for cls in reversed(_CLASSES):
            safe_unregister_class(cls)


__all__ = [
    "MANAGED_OUTPUT_PATH_KEY",
    "TILE_SIGNATURE_KEY",
    "UdimImageError",
    "delete_stale_tile_files",
    "existing_tiles_on_disk",
    "find_stale_tile_files",
    "find_tiled_image",
    "read_image_size",
    "sync_project_output_images",
    "sync_tiled_image",
    "tile_signature",
]
