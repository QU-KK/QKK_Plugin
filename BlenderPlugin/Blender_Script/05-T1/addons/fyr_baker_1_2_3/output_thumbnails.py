from __future__ import annotations

import time
from pathlib import Path

import bpy

_PREVIEW_COLLECTION = None
_PREVIEW_MTIMES: dict[str, int] = {}
_PREVIEW_ICON_IDS: dict[str, int] = {}
#: raw path text -> resolved path text. ``Path.resolve()`` walks the filesystem on
#: Windows, and this is called once per output row on every redraw. The mapping from
#: a raw path to its resolved form does not change while Blender is running, so it is
#: memoised for the session rather than on a timer.
_RESOLVED_PATHS: dict[str, str] = {}
#: resolved path -> (monotonic timestamp, mtime_ns). Bounds the re-stat rate of any one
#: output file; a re-bake is still picked up within _MTIME_TTL_S.
_MTIME_CACHE: dict[str, tuple[float, int]] = {}
#: Seconds an output file's mtime is trusted before it is stat'd again.
_MTIME_TTL_S = 0.5
#: Entries kept before stale ones are swept, well above the row count of one draw.
_PATH_CACHE_MAX_ENTRIES = 512
#: Superseded preview keys awaiting release. get_output_icon_value runs from UI DRAW
#: callbacks, and freeing a preview there can pull an icon out from under the frame
#: that is still being drawn with it. Collect the keys during the draw and release
#: them from a timer, once no draw is in progress.
_PENDING_DISCARDS: set[str] = set()
_DISCARD_TIMER_REGISTERED = False


def _preview_api():
    """``bpy.utils.previews``, or ``None`` when tests stub ``bpy`` without it.

    See ``sidebar_icons._preview_api``: the submodule is not bound until imported.
    """
    utils = getattr(bpy, "utils", None)
    if utils is None:
        return None
    previews = getattr(utils, "previews", None)
    if previews is not None:
        return previews
    try:
        import importlib
        return importlib.import_module("bpy.utils.previews")
    except Exception:
        return None


def _normalize_output_path(file_path: str | Path) -> str:
    raw = str(file_path or "")
    if not raw:
        return ""
    cached = _RESOLVED_PATHS.get(raw)
    if cached is not None:
        return cached
    try:
        resolved = str(Path(raw).resolve())
    except Exception:
        resolved = raw
    if len(_RESOLVED_PATHS) > _PATH_CACHE_MAX_ENTRIES:
        _RESOLVED_PATHS.clear()
    _RESOLVED_PATHS[raw] = resolved
    return resolved


def _output_mtime_ns(file_path: str | Path) -> int:
    """Modification time of one output, stat'd at most once per _MTIME_TTL_S.

    Called from a UI draw callback, once per visible output row, on every redraw.
    Unthrottled that is a stat per row several times a second for a value that only
    moves when a bake finishes."""
    key = str(file_path or "")
    if not key:
        return 0
    now = time.monotonic()
    cached = _MTIME_CACHE.get(key)
    if cached is not None and (now - cached[0]) < _MTIME_TTL_S:
        return cached[1]
    try:
        mtime_ns = int(Path(key).stat().st_mtime_ns)
    except OSError:
        mtime_ns = 0
    if len(_MTIME_CACHE) > _PATH_CACHE_MAX_ENTRIES:
        for stale_key in [k for k, entry in _MTIME_CACHE.items() if (now - entry[0]) >= _MTIME_TTL_S]:
            _MTIME_CACHE.pop(stale_key, None)
        if len(_MTIME_CACHE) > _PATH_CACHE_MAX_ENTRIES:
            _MTIME_CACHE.clear()
    _MTIME_CACHE[key] = (now, mtime_ns)
    return mtime_ns


def _ensure_preview_collection():
    global _PREVIEW_COLLECTION
    if _PREVIEW_COLLECTION is not None:
        return _PREVIEW_COLLECTION
    previews_api = _preview_api()
    if previews_api is None:
        return None
    _PREVIEW_COLLECTION = previews_api.new()
    return _PREVIEW_COLLECTION


def _preview_icon_id(preview) -> int:
    try:
        return int(getattr(preview, "icon_id", 0) or 0)
    except Exception:
        return 0


def _discard_preview(previews, normalized_path: str) -> None:
    if previews is None or not normalized_path:
        return
    try:
        pop = getattr(previews, "pop", None)
        if callable(pop):
            pop(normalized_path, None)
            return
    except Exception:
        pass
    try:
        del previews[normalized_path]
    except Exception:
        pass


def _load_preview(previews, key: str, normalized_path: str, *, force_reload: bool):
    try:
        if force_reload:
            return previews.load(key, normalized_path, "IMAGE", force_reload=True)
        return previews.load(key, normalized_path, "IMAGE")
    except TypeError:
        if force_reload:
            _discard_preview(previews, key)
        try:
            return previews.load(key, normalized_path, "IMAGE")
        except Exception:
            return previews.get(key)
    except Exception:
        if force_reload:
            _discard_preview(previews, key)
            try:
                return previews.load(key, normalized_path, "IMAGE")
            except Exception:
                return previews.get(key)
        return previews.get(key)


def _drain_pending_discards():
    """Release superseded previews outside any draw callback."""
    global _DISCARD_TIMER_REGISTERED
    _DISCARD_TIMER_REGISTERED = False
    previews = _PREVIEW_COLLECTION
    keys = list(_PENDING_DISCARDS)
    _PENDING_DISCARDS.clear()
    if previews is None:
        return None
    for key in keys:
        _discard_preview(previews, key)
    return None


def _queue_discard(key: str) -> None:
    global _DISCARD_TIMER_REGISTERED
    if not key:
        return
    _PENDING_DISCARDS.add(key)
    if _DISCARD_TIMER_REGISTERED:
        return
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    register_timer = getattr(timers, "register", None)
    if not callable(register_timer):
        # No timer API (headless/test): drop the entry now. Nothing is drawing.
        _drain_pending_discards()
        return
    try:
        register_timer(_drain_pending_discards, first_interval=0.0)
        _DISCARD_TIMER_REGISTERED = True
    except Exception:
        _drain_pending_discards()


def register():
    unregister()
    _ensure_preview_collection()


def unregister():
    global _PREVIEW_COLLECTION
    previews_api = _preview_api()
    if _PREVIEW_COLLECTION is not None and previews_api is not None:
        try:
            previews_api.remove(_PREVIEW_COLLECTION)
        except Exception:
            pass
    _PREVIEW_COLLECTION = None
    _PREVIEW_MTIMES.clear()
    _PREVIEW_ICON_IDS.clear()
    _PENDING_DISCARDS.clear()
    _RESOLVED_PATHS.clear()
    _MTIME_CACHE.clear()


def _preview_key(normalized_path: str, mtime_ns: int) -> str:
    """Collection key for one *version* of an output file.

    Blender caches an ``ImagePreviewCollection`` entry by its key and only reads the
    pixels lazily, the first time the icon is drawn. Re-loading under the SAME key
    after the file changed kept handing the UI the already-realised icon, so a
    re-baked map still showed its previous thumbnail in the outputs list while the
    file on disk was correct. Folding the mtime into the key makes every re-bake a
    genuinely new entry, which cannot serve stale pixels.
    """
    return "{}|{}".format(normalized_path, int(mtime_ns))


def get_output_icon_value(file_path: str | Path) -> int:
    normalized_path = _normalize_output_path(file_path)
    if not normalized_path:
        return 0
    previews = _ensure_preview_collection()
    if previews is None:
        return 0

    current_mtime_ns = _output_mtime_ns(normalized_path)
    if current_mtime_ns <= 0:
        # File is gone or unreadable: keep showing the last icon we managed to build.
        return int(_PREVIEW_ICON_IDS.get(normalized_path, 0) or 0)

    preview_key = _preview_key(normalized_path, current_mtime_ns)
    preview = previews.get(preview_key)
    previous_mtime_ns = int(_PREVIEW_MTIMES.get(normalized_path, 0) or 0)

    if preview is None:
        if previous_mtime_ns and previous_mtime_ns != current_mtime_ns:
            # Queue the superseded version for release so the collection does not grow
            # one entry per re-bake, but never free it from inside this draw.
            _queue_discard(_preview_key(normalized_path, previous_mtime_ns))
        preview = _load_preview(previews, preview_key, normalized_path, force_reload=True)
        if preview is not None:
            _PREVIEW_MTIMES[normalized_path] = current_mtime_ns

    icon_id = _preview_icon_id(preview) or int(_PREVIEW_ICON_IDS.get(normalized_path, 0) or 0)
    if icon_id:
        _PREVIEW_ICON_IDS[normalized_path] = icon_id
    return icon_id
