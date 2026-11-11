from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

# Path.resolve() walks the filesystem (GetFinalPathNameByHandle per component on Windows).
# One output refresh normalised the same few hundred paths ~24,000 times: 4 of the 6.3 s a
# 66-group Ubrion refresh took on Blender's main thread, five refreshes per bake
# (2026-09-29). Inside normalized_path_cache() each distinct path resolves once; outside it
# nothing is cached, so a path that changes meaning between refreshes is never stale.
_NORMALIZED_PATH_CACHE: dict | None = None


@contextmanager
def normalized_path_cache():
    """Memoise path normalisation for the duration of one refresh (re-entrant)."""
    global _NORMALIZED_PATH_CACHE
    outermost = _NORMALIZED_PATH_CACHE is None
    if outermost:
        _NORMALIZED_PATH_CACHE = {}
    try:
        yield
    finally:
        if outermost:
            _NORMALIZED_PATH_CACHE = None


def cached_normalized_path(kind: str, text: str, compute):
    """`compute()` once per (kind, text) while a normalized_path_cache() scope is open."""
    cache = _NORMALIZED_PATH_CACHE
    if cache is None:
        return compute()
    key = (kind, text)
    hit = cache.get(key)
    if hit is None:
        hit = compute()
        cache[key] = hit
    return hit


def normalize_image_path(file_path: str | Path | None, *, os_module) -> str:
    raw_path = str(file_path or "").strip()
    if not raw_path:
        return ""

    def compute() -> str:
        try:
            normalized = Path(raw_path).expanduser().resolve(strict=False)
        except Exception:
            normalized = Path(raw_path).expanduser()
        return os_module.path.normcase(str(normalized))

    return cached_normalized_path(f"image:{id(os_module)}", raw_path, compute)


def image_file_mtime_ns(file_path: str | Path | None) -> int:
    raw_path = str(file_path or "").strip()
    if not raw_path:
        return 0
    try:
        return int(Path(raw_path).expanduser().stat().st_mtime_ns)
    except OSError:
        return 0


def image_metadata_get(image, key: str, default=None):
    if image is None:
        return default
    getter = getattr(image, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except Exception:
            pass
    return getattr(image, key, default)


def image_metadata_set(image, key: str, value) -> None:
    if image is None:
        return
    if isinstance(value, int) and not isinstance(value, bool) and not (-2**31 <= value < 2**31):
        # ID properties hold 32-bit ints; a file mtime in nanoseconds does not fit
        # and the assignment raised OverflowError. That left the recorded mtime empty
        # forever, so every managed load reloaded the texture from disk. Store it
        # as text; readers already coerce with int().
        value = str(value)
    try:
        image[key] = value
        return
    except Exception:
        pass
    try:
        setattr(image, key, value)
    except Exception:
        pass


def image_filepath(image) -> str:
    if image is None:
        return ""
    for attr_name in ("filepath_raw", "filepath"):
        value = getattr(image, attr_name, "")
        if str(value or "").strip():
            return str(value)
    return ""


def mark_managed_output_image(
    image,
    file_path: str | Path,
    *,
    managed_output_path_key: str,
    managed_output_mtime_key: str,
    image_metadata_set_fn,
    normalize_image_path_fn,
    image_file_mtime_ns_fn,
) -> None:
    image_metadata_set_fn(image, managed_output_path_key, normalize_image_path_fn(file_path))
    image_metadata_set_fn(image, managed_output_mtime_key, image_file_mtime_ns_fn(file_path))


def image_matches_output_path(
    image,
    normalized_file_path: str,
    *,
    managed_output_path_key: str,
    image_metadata_get_fn,
    normalize_image_path_fn,
    image_filepath_fn,
) -> bool:
    if not normalized_file_path:
        return False
    managed_path = str(image_metadata_get_fn(image, managed_output_path_key, "") or "")
    if managed_path and managed_path == normalized_file_path:
        return True
    return normalize_image_path_fn(image_filepath_fn(image)) == normalized_file_path


def find_existing_image_for_path(images, normalized_file_path: str, *, image_matches_output_path_fn):
    if not normalized_file_path:
        return None
    for image in images:
        if image_matches_output_path_fn(image, normalized_file_path):
            return image
    return None


def load_managed_output_image(
    file_path: str | Path,
    *,
    images,
    managed_output_mtime_key: str,
    normalize_image_path_fn,
    find_existing_image_for_path_fn,
    image_metadata_get_fn,
    image_file_mtime_ns_fn,
    mark_managed_output_image_fn,
):
    if images is None or not hasattr(images, "load"):
        raise RuntimeError("Blender image datablocks are not available")

    normalized_file_path = normalize_image_path_fn(file_path)
    existing_image = find_existing_image_for_path_fn(images, normalized_file_path)
    image = images.load(str(file_path), check_existing=True)
    previous_mtime = int(image_metadata_get_fn(image, managed_output_mtime_key, 0) or 0)
    current_mtime = image_file_mtime_ns_fn(file_path)
    if existing_image is not None and current_mtime > 0 and current_mtime != previous_mtime and hasattr(image, "reload"):
        try:
            image.reload()
        except Exception:
            pass
    mark_managed_output_image_fn(image, file_path)
    return image


def invalidate_output_image_cache(
    file_paths: list[str] | tuple[str, ...],
    *,
    images,
    normalize_image_path_fn,
    image_matches_output_path_fn,
    image_filepath_fn,
    image_file_mtime_ns_fn,
    image_metadata_get_fn,
    managed_output_mtime_key: str,
    mark_managed_output_image_fn,
) -> int:
    normalized_paths = {
        normalize_image_path_fn(file_path)
        for file_path in file_paths
        if str(file_path or "").strip()
    }
    if not normalized_paths:
        return 0
    if images is None:
        return 0

    reloaded_count = 0
    for image in images:
        matched_path = next((path for path in normalized_paths if image_matches_output_path_fn(image, path)), "")
        if not matched_path:
            continue
        current_path = image_filepath_fn(image)
        current_mtime = image_file_mtime_ns_fn(current_path)
        previous_mtime = int(image_metadata_get_fn(image, managed_output_mtime_key, 0) or 0)
        if current_mtime > 0 and current_mtime != previous_mtime and hasattr(image, "reload"):
            try:
                image.reload()
                reloaded_count += 1
            except Exception:
                # Leave the old mtime in place so the next pass retries: stamping
                # the new one here recorded a reload that never happened and the
                # image kept its stale pixels for good.
                continue
        mark_managed_output_image_fn(image, current_path)
    return reloaded_count


def refresh_project_output_images(project, *, invalidate_output_image_cache_fn) -> int:
    file_paths = [getattr(item, "file_path", "") for item in getattr(project, "latest_outputs", [])]
    return invalidate_output_image_cache_fn(file_paths)


def apply_output_image_colorspaces(
    project,
    *,
    find_existing_image_for_path_fn,
    colorspace_name_fn,
) -> int:
    """Tag every tracked output image with the encoding its file was written in.

    Blender guesses a colorspace from the file extension when an image datablock is
    created, and for TGA/PNG that guess is sRGB. Data maps are written LINEAR, so the
    guess silently linearises them again on read: a 0.35 roughness arrives at the
    shader as ~0.10 (much glossier) and a normal map's XY are distorted. Every
    consumer of these datablocks -- the preview materials, the Image Editor, and any
    material the user wires up from them -- inherits that error, so it is fixed once,
    here, on the datablock itself.

    Returns the number of images retagged.
    """
    retagged = 0
    for item in getattr(project, "latest_outputs", []) or []:
        file_path = str(getattr(item, "file_path", "") or "")
        if not file_path:
            continue
        image = find_existing_image_for_path_fn(file_path)
        if image is None:
            continue
        # Prefer effective_map_type: material rows store stack type MATERIAL in
        # map_type, which would mis-tag Albedo as Non-Color and leave Roughness /
        # Normal guessing from the PNG extension (sRGB) when retagging.
        map_type = str(
            getattr(item, "effective_map_type", "")
            or getattr(item, "map_type", "")
            or ""
        )
        expected = colorspace_name_fn(map_type)
        settings = getattr(image, "colorspace_settings", None)
        if settings is None:
            continue
        try:
            if str(getattr(settings, "name", "") or "") == expected:
                continue
            settings.name = expected
            retagged += 1
        except Exception:
            continue
    return retagged
