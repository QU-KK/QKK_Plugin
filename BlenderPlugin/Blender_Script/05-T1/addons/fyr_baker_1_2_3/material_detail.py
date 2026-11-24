"""Post-project high-material detail layers into final Normal and AO outputs."""

from __future__ import annotations

from array import array
import json
import math
from pathlib import Path

from . import image_cleanup


def _image_format_for_path(path: Path) -> str:
    return {
        ".tga": "TARGA_RAW",
        ".png": "PNG",
        ".exr": "OPEN_EXR",
        ".tif": "TIFF",
        ".tiff": "TIFF",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
    }.get(path.suffix.lower(), "OPEN_EXR")


def _load_pixels(bpy, path: Path):
    image = bpy.data.images.load(str(path), check_existing=False)
    # Own the datablock until it is handed back. The caller binds it only from the
    # returned tuple, so a raise below used to put it beyond the reach of its finally:
    # a truncated output (worker killed by the bake cap, or a full disk) loads lazily,
    # reports size (0, 0) and raises in foreach_get, leaving one orphan Image per
    # failed entry per retry, saved into the .blend.
    try:
        # Read the stored values, not a display-linearised copy. Blender loads a
        # 16-bit PNG/TIFF into a float buffer and converts it from the default sRGB
        # space at first access, so a Normal or AO output read here came back with
        # 0.5 decoded to 0.21; the blend then ran on those values and the result was
        # written back raw (dark AO, tilted normals). 8-bit files were unaffected,
        # which is why the default PNG path hid it. Setting the colorspace before the
        # first pixel read makes Blender load the buffer untouched.
        image.colorspace_settings.name = "Non-Color"
        width, height = int(image.size[0]), int(image.size[1])
        if width <= 0 or height <= 0:
            raise ValueError(f"{path.name} has no pixels (truncated or unreadable)")
        pixels = array("f", [0.0]) * (width * height * 4)
        image.pixels.foreach_get(pixels)
    except BaseException:
        try:
            image_cleanup.remove_image_when_safe(image, reason="material detail load failure")
        except Exception:
            pass
        raise
    return image, width, height, pixels


def apply_workspace_material_detail(workspace_path: str | Path) -> list[str]:
    """Apply a prepared job's material-detail manifest once.

    Returns warnings rather than raising so a correct geometry bake remains
    available if Blender cannot read or write a detail layer.
    """
    import bpy

    workspace = Path(workspace_path)
    manifest_path = workspace / "material_detail_manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Material detail manifest could not be read: {exc}"]

    # Export-time diagnostics (e.g. partial material-detail coverage) ride in the
    # manifest so they reach the finished bake's warning summary on every
    # completion path, not just the prepare-time operator report.
    warnings: list[str] = [
        str(note).strip()
        for note in (payload.get("warnings", []) or [])
        if str(note).strip()
    ]
    all_applied = True
    for entry in payload.get("entries", []):
        action = str(entry.get("action", "") or "").strip().upper()
        detail_path = Path(str(entry.get("detail_path", "") or ""))
        final_path = Path(str(entry.get("final_path", "") or ""))
        if action not in {"REPLACE_NORMAL", "COMBINE_NORMAL", "MULTIPLY_AO"}:
            continue
        if not detail_path.is_file() or not final_path.is_file():
            warnings.append(
                f"Material detail skipped for '{entry.get('group_name', '')}': required image is missing"
            )
            all_applied = False
            continue

        detail_image = final_image = None
        try:
            detail_image, detail_w, detail_h, detail_pixels = _load_pixels(bpy, detail_path)
            final_image, final_w, final_h, final_pixels = _load_pixels(bpy, final_path)
            if (detail_w, detail_h) != (final_w, final_h):
                raise RuntimeError(
                    f"resolution mismatch ({detail_w}x{detail_h} vs {final_w}x{final_h})"
                )

            if action in {"REPLACE_NORMAL", "COMBINE_NORMAL"}:
                output_pixels = final_pixels
                flip_green = bool(entry.get("flip_green", False))
                for index in range(0, len(output_pixels), 4):
                    coverage = max(0.0, min(1.0, float(detail_pixels[index + 3])))
                    if coverage <= 0.0:
                        continue
                    detail_green = (
                        1.0 - detail_pixels[index + 1]
                        if flip_green
                        else detail_pixels[index + 1]
                    )
                    if action == "REPLACE_NORMAL":
                        combined = (
                            detail_pixels[index],
                            detail_green,
                            detail_pixels[index + 2],
                        )
                    else:
                        base = (
                            output_pixels[index] * 2.0 - 1.0,
                            output_pixels[index + 1] * 2.0 - 1.0,
                            output_pixels[index + 2] * 2.0 - 1.0,
                        )
                        detail = (
                            detail_pixels[index] * 2.0 - 1.0,
                            detail_green * 2.0 - 1.0,
                            detail_pixels[index + 2] * 2.0 - 1.0,
                        )
                        # Reoriented Normal Mapping (RNM): retain the base
                        # geometric orientation while adding material detail.
                        t = (base[0], base[1], base[2] + 1.0)
                        u = (-detail[0], -detail[1], detail[2])
                        dot_tu = t[0] * u[0] + t[1] * u[1] + t[2] * u[2]
                        result = (
                            t[0] * dot_tu - u[0] * t[2],
                            t[1] * dot_tu - u[1] * t[2],
                            t[2] * dot_tu - u[2] * t[2],
                        )
                        length = math.sqrt(
                            result[0] * result[0]
                            + result[1] * result[1]
                            + result[2] * result[2]
                        )
                        if length <= 1.0e-12:
                            combined = (
                                output_pixels[index],
                                output_pixels[index + 1],
                                output_pixels[index + 2],
                            )
                        else:
                            combined = (
                                result[0] / length * 0.5 + 0.5,
                                result[1] / length * 0.5 + 0.5,
                                result[2] / length * 0.5 + 0.5,
                            )
                    output_pixels[index] = (
                        output_pixels[index] * (1.0 - coverage)
                        + combined[0] * coverage
                    )
                    output_pixels[index + 1] = (
                        output_pixels[index + 1] * (1.0 - coverage)
                        + combined[1] * coverage
                    )
                    output_pixels[index + 2] = (
                        output_pixels[index + 2] * (1.0 - coverage)
                        + combined[2] * coverage
                    )
            else:
                output_pixels = final_pixels
                for index in range(0, len(output_pixels), 4):
                    coverage = max(0.0, min(1.0, float(detail_pixels[index + 3])))
                    sampled_ao = max(0.0, min(1.0, float(detail_pixels[index])))
                    material_ao = 1.0 + (sampled_ao - 1.0) * coverage
                    output_pixels[index] *= material_ao
                    output_pixels[index + 1] *= material_ao
                    output_pixels[index + 2] *= material_ao

            final_image.pixels.foreach_set(output_pixels)
            final_image.filepath_raw = str(final_path)
            final_image.file_format = _image_format_for_path(final_path)
            final_image.save()
        except Exception as exc:
            warnings.append(
                f"Material detail could not be applied for '{entry.get('group_name', '')}': {exc}"
            )
            all_applied = False
        finally:
            for image in (detail_image, final_image):
                if image is not None:
                    try:
                        image_cleanup.remove_image_when_safe(image, reason="material detail")
                    except Exception:
                        pass

    if all_applied:
        try:
            manifest_path.unlink()
        except Exception:
            pass
    return warnings
