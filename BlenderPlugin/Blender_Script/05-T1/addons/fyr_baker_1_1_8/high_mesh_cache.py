from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid

import bpy

from . import collection_index, floater_faces, mesh_read
from . import constants, mesh_transport, naming, preferences, properties, protocol
from .handler_thread_guard import on_main_thread

_PERSISTENT = getattr(getattr(bpy, "app", None), "handlers", None)
_PERSISTENT = getattr(_PERSISTENT, "persistent", lambda fn: fn)

_OBJECT_CACHE_ID_PROP = "_fyr_baker_high_cache_id"
_MANIFEST_VERSION = 1
_PREWARM_DELAY_SECONDS = 0.75
_PREWARM_RETRY_SECONDS = 0.25
_PREWARM_NEXT_SECONDS = 0.01
_PREWARM_WRITE_POLL_SECONDS = 0.05
#: Main-thread time one prewarm tick may spend capturing meshes before it yields, and how
#: many worker writes (and bytes of captured arrays) may run at once.
_PREWARM_BUDGET_SECONDS = 0.07
_PREWARM_MAX_WRITES = 2
_PREWARM_MAX_WRITE_BYTES = 768 * 1024 * 1024
#: While cage fits are pending, a prewarm batch is followed by this many times its own
#: main-thread time for the fits.
_PREWARM_FIT_SHARE = 3.0
_PREWARM_FIT_NEXT_AT = 0.0
_SESSION_TOKEN = uuid.uuid4().hex


@dataclass(slots=True)
class _ManifestEntry:
    cache_id: str
    signature: str
    relative_path: str
    object_name: str = ""
    #: color_stream.ColorStreamSource.cache_key of the file's colour section: "" for the
    #: active colour attribute (and for every entry written before Attribute rows).
    color_key: str = ""


@dataclass(slots=True)
class _TrackedHighObjectState:
    object_ref: object
    object_key: int
    data_key: int
    cache_id: str
    runtime_ref: protocol.ExportedMeshRef | None = None
    runtime_signature: str = ""
    dirty: bool = True
    #: The cache id this object carried before its last geometry edit. Kept alive in
    #: the manifest so an Undo of that edit (which restores the id property) still
    #: hits; anything older is retired when the id rotates again.
    previous_cache_id: str = ""
    #: Colour source of runtime_ref's colour section (see _ManifestEntry.color_key).
    runtime_color_key: str = ""
    #: Counts every geometry edit, including those made while already dirty: a prewarm
    #: write captured before an edit must not land after it (the cache id only rotates on
    #: the first edit, and the quick signature misses a moved vertex).
    edits: int = 0


#: A high with marked floater faces exports a second piece (floater_faces.PART_FLOATER).
#: It caches beside the object's own entry under the object's cache id plus this suffix,
#: so it rotates and retires with that id.
_FLOATER_CACHE_ID_SUFFIX = "~floater"


@dataclass(slots=True)
class _FloaterPartState:
    """The floater piece's cache slots, keyed off its object's tracked state."""

    base: _TrackedHighObjectState
    base_cache_id: str = ""
    runtime_ref: protocol.ExportedMeshRef | None = None
    runtime_signature: str = ""
    runtime_color_key: str = ""
    dirty: bool = True

    @property
    def cache_id(self) -> str:
        return self.base.cache_id + _FLOATER_CACHE_ID_SUFFIX


_TRACKED_OBJECTS: dict[int, _TrackedHighObjectState] = {}
_FLOATER_STATES: dict[int, _FloaterPartState] = {}
_TRACKED_DATA_KEYS: dict[int, set[int]] = {}
_CACHE_ID_TO_OBJECT_KEY: dict[str, int] = {}
_MANIFEST_ENTRIES: dict[str, _ManifestEntry] | None = None
_PENDING_PREWARM_KEYS: set[int] = set()
# >0 while high_poly_park swaps high-poly mesh datablocks out and back: the content is
# unchanged, so the swap must not rotate cache ids (that forces a full re-export).
_TRACKING_SUSPENDED = 0
_PREWARM_DUE_AT: float = 0.0
_PREWARM_TIMER_REGISTERED = False
# Guards every read-modify-write of _MANIFEST_ENTRIES and every _save_manifest().
# The startup prune runs on a daemon thread (a multi-GB rglob must never block
# addon enable), so a main-thread commit can land mid-prune. Re-entrant because
# the prune path calls _manifest_entries() -> _save_manifest() while holding it.
_MANIFEST_LOCK = threading.RLock()
# True when aliases.json existed but could not be read: the in-memory manifest is then a
# guess, so the unreferenced-file sweep must not run on it (it would delete every canonical
# file, 3.7 GB per large scene).
_MANIFEST_LOAD_FAILED = False
_STARTUP_PRUNE_THREAD: threading.Thread | None = None


def _env_flag_enabled(name: str) -> bool:
    value = str(os.environ.get(name, "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _persistent_cache_root() -> Path:
    if _env_flag_enabled(constants.DISABLE_PERSISTENT_CACHE_ENV_VAR):
        return Path(tempfile.gettempdir()) / "fyr_baker_blender_high_exports"
    return preferences.persistent_cache_root() / "blender_high_exports"


def _canonical_geometry_root() -> Path:
    path = preferences.persistent_cache_root() / "canonical_geometry"
    mesh_transport.ensure_dir(path)
    return path


def _committed_root() -> Path:
    path = _persistent_cache_root() / "committed"
    mesh_transport.ensure_dir(path)
    return path


_RUNTIME_ROOT_STAMPED = False


def _runtime_root() -> Path:
    global _RUNTIME_ROOT_STAMPED
    path = _persistent_cache_root() / "runtime" / _SESSION_TOKEN
    mesh_transport.ensure_dir(path)
    # Owner stamp: another Blender's prune must be able to tell a live session from a
    # dead one instead of deleting everything that is not its own. Re-stamp whenever the
    # file is missing, not once per process: on 2026-09-14 a live session had lost its
    # owner.pid (its directory had been removed and recreated underneath it), so to every
    # other Blender it read as unowned and its exports were fair game an hour later.
    try:
        from . import storage_cleanup as _storage_cleanup

        owner_file = path / _storage_cleanup._RUNTIME_SESSION_OWNER_FILE  # noqa: SLF001
        if not _RUNTIME_ROOT_STAMPED or not owner_file.exists():
            _RUNTIME_ROOT_STAMPED = True
            _storage_cleanup.mark_runtime_session_owner(path)
    except Exception:
        pass
    return path


def _manifest_path() -> Path:
    path = preferences.persistent_cache_root() / "canonical_geometry"
    mesh_transport.ensure_dir(path)
    return path / "aliases.json"


def _legacy_manifest_path() -> Path:
    return _persistent_cache_root() / "manifest.json"


def _active_project_pins_path() -> Path:
    return preferences.persistent_cache_root() / "active_project_pins.txt"


_PERSIST_DEFER_DEPTH = 0
_PERSIST_DEFERRED = {"manifest": False, "pins": False}


class defer_persistence:
    """Coalesce manifest and pin-file writes inside the block into one write at the end.

    Resolving each of G high meshes rewrote the whole alias manifest and the pin list
    every time (O(G^2): 300 groups spent about 4.6 s of a 15 s prepare on it). Nothing
    reads either file until the job runs, so one write at exit is equivalent.
    """

    def __init__(self, *, flush: bool = True):
        # flush=False: the caller writes both files itself right after the block (the
        # prewarm tick, which must save once per high, after the canonical write is
        # queued); the deferred requests are dropped instead of written twice.
        self._flush = flush

    def __enter__(self):
        global _PERSIST_DEFER_DEPTH
        _PERSIST_DEFER_DEPTH += 1
        return self

    def __exit__(self, *_exc):
        global _PERSIST_DEFER_DEPTH
        _PERSIST_DEFER_DEPTH = max(0, _PERSIST_DEFER_DEPTH - 1)
        if _PERSIST_DEFER_DEPTH == 0:
            manifest, pins = _PERSIST_DEFERRED["manifest"], _PERSIST_DEFERRED["pins"]
            _PERSIST_DEFERRED["manifest"] = _PERSIST_DEFERRED["pins"] = False
            if not self._flush:
                return False
            if manifest:
                _save_manifest()
            if pins:
                _save_active_project_pins()
        return False


_PIN_RESOLVE_MEMO: dict[str, str] = {}


def _resolved_pin_path(path) -> str:
    """str(Path(path).resolve(strict=False)), remembered: the pins file is rewritten for
    every registered mesh and resolved every tracked path each time (O(G^2) syscalls)."""
    key = str(path)
    resolved = _PIN_RESOLVE_MEMO.get(key)
    if resolved is None:
        if len(_PIN_RESOLVE_MEMO) > 50000:
            _PIN_RESOLVE_MEMO.clear()
        resolved = _PIN_RESOLVE_MEMO[key] = str(Path(key).resolve(strict=False))
    return resolved


def _save_active_project_pins() -> None:
    if _PERSIST_DEFER_DEPTH:
        _PERSIST_DEFERRED["pins"] = True
        return
    manifest = _manifest_entries()
    paths: set[str] = {
        str(_manifest_path().resolve(strict=False)),
    }
    for state in _TRACKED_OBJECTS.values():
        runtime_ref = state.runtime_ref
        if runtime_ref is not None and Path(runtime_ref.path).suffix.lower() == ".fyrgeom":
            paths.add(_resolved_pin_path(runtime_ref.path))
            continue
        entry = manifest.get(state.cache_id)
        if entry is None:
            continue
        path = Path(entry.relative_path)
        path = path if path.is_absolute() else _committed_root() / path
        if path.suffix.lower() == ".fyrgeom" and path.exists():
            paths.add(_resolved_pin_path(path))
    destination = _active_project_pins_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        "".join(f"{path}\n" for path in sorted(paths)),
        encoding="utf-8",
    )
    temporary.replace(destination)


def _normalize_scalar(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(float(value), 6)
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return repr(value)


def _normalize_sequence(value):
    try:
        return tuple(_normalize_value(item) for item in value)
    except Exception:
        return repr(value)


def _normalize_pointer_target(value):
    if value is None:
        return None
    library = getattr(value, "library", None)
    return (
        getattr(value, "__class__", type(value)).__name__,
        str(getattr(value, "name", "") or ""),
        str(getattr(library, "filepath", "") or ""),
    )


def _normalize_value(value):
    if isinstance(value, (bool, int, float, str)) or value is None:
        return _normalize_scalar(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return _normalize_sequence(value)
    if hasattr(value, "to_tuple"):
        try:
            return _normalize_sequence(value.to_tuple())
        except Exception:
            return repr(value)
    if hasattr(value, "__iter__") and not isinstance(value, dict):
        return _normalize_sequence(value)
    if hasattr(value, "name"):
        return _normalize_pointer_target(value)
    return repr(value)


def _matrix_signature(matrix_world) -> tuple:
    if matrix_world is None:
        return ()
    try:
        return tuple(round(float(value), 6) for row in matrix_world for value in row)
    except Exception:
        return ()


def _cheap_modifier_stack_signature(obj) -> tuple:
    """Modifier signature that avoids bl_rna.properties introspection.

    Uses only modifier name, type, and visibility flags — fast for any modifier type
    including complex Geometry Nodes setups where property enumeration can be expensive.
    Depsgraph updates already mark state dirty when modifier configurations change,
    so the signature only needs to cover identity, not full property state.
    """
    result = []
    for modifier in getattr(obj, "modifiers", []) or []:
        result.append((
            str(getattr(modifier, "name", "") or ""),
            str(getattr(modifier, "type", "") or ""),
            bool(getattr(modifier, "show_viewport", True)),
            bool(getattr(modifier, "show_render", True)),
        ))
    return tuple(result)


def _quick_source_signature(obj) -> str:
    """Cheap change-detection signature for high-poly objects.

    Deliberately avoids:
    - obj.bound_box: may trigger full modifier-stack evaluation (BVH build etc.) for objects
      with unevaluated SubDiv or Geometry Nodes, causing multi-second freezes in the main thread.
    - modifier.bl_rna.properties enumeration + getattr per property: slow for complex GN setups
      with many sockets; geometry changes from modifier edits are already covered by the
      depsgraph_update_post handler that marks state dirty.

    The "HIGH_V4" prefix invalidates any V2/V3 cached exports so they are re-exported as V4.
    """
    data = getattr(obj, "data", None)
    payload = (
        "HIGH_V5",  # V5: local-space export — matrix_world excluded from key, passed separately
        str(getattr(obj, "type", "") or ""),
        str(getattr(obj, "name", "") or ""),
        str(getattr(getattr(obj, "library", None), "filepath", "") or ""),
        str(getattr(data, "name", "") or ""),
        str(getattr(getattr(data, "library", None), "filepath", "") or ""),
        _cheap_modifier_stack_signature(obj),
        # Use base-mesh stats from the unevaluated data block (no depsgraph trigger)
        mesh_read.element_count(data, "vertices"),
        mesh_read.element_count(data, "polygons"),
    )
    floater_token = floater_faces.cache_token(obj)
    if floater_token:
        # Marked floater faces: the export writes a body or a floater piece. Appended only
        # when faces are marked, so every existing signature is unchanged.
        payload = payload + (floater_token,)
    digest = hashlib.blake2b(digest_size=16)
    digest.update(repr(payload).encode("utf-8"))
    return digest.hexdigest()


def _object_key(obj) -> int:
    session_uid = getattr(obj, "session_uid", 0)
    try:
        session_value = int(session_uid)
    except Exception:
        session_value = 0
    if session_value:
        return session_value
    as_pointer = getattr(obj, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(obj)


def _data_key(obj) -> int:
    data = getattr(obj, "data", None)
    if data is None:
        return 0
    session_uid = getattr(data, "session_uid", 0)
    try:
        session_value = int(session_uid)
    except Exception:
        session_value = 0
    if session_value:
        return session_value
    as_pointer = getattr(data, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(data)


def _object_prop_get(obj, key: str, default: str = "") -> str:
    getter = getattr(obj, "get", None)
    if callable(getter):
        try:
            value = getter(key, default)
            return str(value or default)
        except Exception:
            pass
    return str(getattr(obj, key, default) or default)


def _object_prop_set(obj, key: str, value: str) -> None:
    try:
        obj[key] = value
        return
    except Exception:
        pass
    try:
        setattr(obj, key, value)
    except Exception:
        return


def _object_prop_delete(obj, key: str) -> None:
    try:
        del obj[key]
        return
    except Exception:
        pass
    try:
        delattr(obj, key)
    except Exception:
        return


def _ensure_object_cache_id(obj) -> str:
    cache_id = _object_prop_get(obj, _OBJECT_CACHE_ID_PROP, "").strip()
    object_key = _object_key(obj)
    if cache_id:
        other_key = _CACHE_ID_TO_OBJECT_KEY.get(cache_id)
        if other_key is None or other_key == object_key:
            _CACHE_ID_TO_OBJECT_KEY[cache_id] = object_key
            return cache_id

    cache_id = uuid.uuid4().hex
    _object_prop_set(obj, _OBJECT_CACHE_ID_PROP, cache_id)
    _CACHE_ID_TO_OBJECT_KEY[cache_id] = object_key
    return cache_id


def _manifest_entries() -> dict[str, _ManifestEntry]:
    global _MANIFEST_ENTRIES
    if _MANIFEST_ENTRIES is not None:
        return _MANIFEST_ENTRIES
    with _MANIFEST_LOCK:
        if _MANIFEST_ENTRIES is not None:
            return _MANIFEST_ENTRIES
        return _load_manifest_entries_locked()


def _read_manifest_payload(path: Path):
    """(payload, readable) of an alias manifest file. A file that exists but cannot be read
    or parsed (another Blender mid-replace, a truncated write) is NOT an empty manifest:
    callers must not treat every canonical file as unreferenced because of it."""
    last_error = None
    for attempt in range(3):
        try:
            return json.loads(path.read_text(encoding="utf-8")), True
        except FileNotFoundError:
            return None, True
        except Exception as exc:  # PermissionError during a sibling's replace, bad JSON
            last_error = exc
            if attempt < 2:
                time.sleep(0.05)
    del last_error
    return None, False


def _load_manifest_entries_locked() -> dict[str, _ManifestEntry]:
    global _MANIFEST_ENTRIES, _MANIFEST_LOAD_FAILED
    path = _manifest_path()
    if not path.exists() and _legacy_manifest_path().exists():
        path = _legacy_manifest_path()
    if not path.exists():
        _MANIFEST_ENTRIES = {}
        return _MANIFEST_ENTRIES
    payload, readable = _read_manifest_payload(path)
    if not readable:
        _MANIFEST_LOAD_FAILED = True
        _MANIFEST_ENTRIES = {}
        return _MANIFEST_ENTRIES
    entries = {}
    for item in payload.get("objects", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        cache_id = str(item.get("cache_id", "") or "").strip()
        signature = str(item.get("signature", "") or "").strip()
        relative_path = str(item.get("relative_path", "") or "").strip()
        if not cache_id or not signature or not relative_path:
            continue
        entries[cache_id] = _ManifestEntry(
            cache_id=cache_id,
            signature=signature,
            relative_path=relative_path,
            object_name=str(item.get("object_name", "") or ""),
            color_key=str(item.get("color_key", "") or ""),
        )
    _MANIFEST_ENTRIES = entries
    _cleanup_missing_manifest_entries_locked()
    return _MANIFEST_ENTRIES


def _other_sessions_live_paths() -> set[str] | None:
    """Normalised paths another Blender (or the worker's pin list) keeps alive: the aliases
    currently on disk plus active_project_pins.txt. None when the on-disk manifest exists but
    cannot be read, in which case nothing may be swept this time."""
    live: set[str] = set()
    path = _manifest_path()
    if path.exists():
        payload, readable = _read_manifest_payload(path)
        if not readable:
            return None
        for item in payload.get("objects", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("relative_path", "") or "").strip()
            if not text:
                continue
            entry_path = Path(text)
            entry_path = entry_path if entry_path.is_absolute() else _committed_root() / entry_path
            live.add(_live_path_key(entry_path))
    try:
        for line in _active_project_pins_path().read_text(encoding="utf-8").splitlines():
            if line.strip():
                live.add(_live_path_key(Path(line.strip())))
    except OSError:
        pass
    return live


def _live_path_key(path: Path) -> str:
    try:
        return os.path.normcase(str(path.resolve(strict=False)))
    except Exception:
        return os.path.normcase(str(path))


def _save_manifest() -> None:
    with _MANIFEST_LOCK:
        _save_manifest_locked()


_REMOVED_ALIAS_IDS: set[str] = set()
# Clear Cache wipes the manifest on purpose: its next save must replace the file, not merge.
_MANIFEST_REPLACE_ON_NEXT_SAVE = False


def _forget_alias(cache_id: str, entries=None) -> bool:
    """Remove an alias on purpose. Remembered so the next save does not merge the on-disk
    copy of it back in (other aliases written by another Blender are kept)."""
    entries = _manifest_entries() if entries is None else entries
    _REMOVED_ALIAS_IDS.add(cache_id)
    return entries.pop(cache_id, None) is not None


class _manifest_file_lock:
    """Cross-process lock on a sidecar file around the aliases.json read-merge-write.
    Waits briefly; on timeout it proceeds unlocked rather than stalling the main thread."""

    def __init__(self, timeout: float = 2.0):
        self._timeout = timeout
        self._handle = None

    def __enter__(self):
        try:
            import msvcrt
        except ImportError:
            return self
        try:
            handle = open(_manifest_path().with_suffix(".lock"), "a+b")
        except OSError:
            return self
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                self._handle = handle
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    handle.close()
                    return self
                time.sleep(0.02)

    def __exit__(self, *_exc):
        handle, self._handle = self._handle, None
        if handle is not None:
            try:
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            handle.close()
        return False


def _merge_disk_aliases_locked() -> None:
    """Fold aliases another process published into the in-memory manifest (called under the
    file lock). Our own entries win; ids we removed on purpose stay removed."""
    global _MANIFEST_REPLACE_ON_NEXT_SAVE
    if _MANIFEST_REPLACE_ON_NEXT_SAVE:
        _MANIFEST_REPLACE_ON_NEXT_SAVE = False
        return
    path = _manifest_path()
    if not path.exists():
        return
    payload, readable = _read_manifest_payload(path)
    if not readable or not isinstance(payload, dict):
        return
    entries = _manifest_entries()
    for item in payload.get("objects", []):
        if not isinstance(item, dict):
            continue
        cache_id = str(item.get("cache_id", "") or "").strip()
        signature = str(item.get("signature", "") or "").strip()
        relative_path = str(item.get("relative_path", "") or "").strip()
        if not cache_id or not signature or not relative_path:
            continue
        if cache_id in entries or cache_id in _REMOVED_ALIAS_IDS:
            continue
        entries[cache_id] = _ManifestEntry(
            cache_id=cache_id,
            signature=signature,
            relative_path=relative_path,
            object_name=str(item.get("object_name", "") or ""),
            color_key=str(item.get("color_key", "") or ""),
        )


def _save_manifest_locked() -> None:
    if _PERSIST_DEFER_DEPTH:
        _PERSIST_DEFERRED["manifest"] = True
        return
    with _manifest_file_lock():
        _merge_disk_aliases_locked()
        _write_manifest_unlocked()


def _write_manifest_unlocked() -> None:
    entries = sorted(
        (
            entry
            for entry in _manifest_entries().values()
            if (
                Path(entry.relative_path)
                if Path(entry.relative_path).is_absolute()
                else _committed_root() / entry.relative_path
            ).exists()
        ),
        key=lambda item: item.cache_id,
    )
    payload = {
        "version": _MANIFEST_VERSION,
        "objects": [
            {
                "cache_id": entry.cache_id,
                "signature": entry.signature,
                "relative_path": entry.relative_path,
                "object_name": entry.object_name,
                **({"color_key": entry.color_key} if entry.color_key else {}),
            }
            for entry in entries
        ],
    }
    destination = _manifest_path()
    temp_path = destination.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(destination)
    # One-release migration compatibility: if an installation still has the
    # legacy manifest, keep its aliases coherent while the canonical manifest
    # becomes authoritative. No new legacy geometry is created here.
    legacy_destination = _legacy_manifest_path()
    if legacy_destination.exists():
        legacy_temp = legacy_destination.with_suffix(".tmp")
        legacy_temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        legacy_temp.replace(legacy_destination)


def finalize_pending_canonical_aliases() -> None:
    """Publish aliases only after their asynchronous canonical writes verify."""
    _save_manifest()
    _save_active_project_pins()


def _touch_path(path: Path) -> None:
    # LRU freshness marker for _prune_persistent_cache. Only atime may be
    # bumped: the backend memoizes its full-file revision hash on
    # (path, size, mtime), so touching mtime on every cache hit forces it to
    # re-stream and re-hash hundreds of MB of committed meshes per bake.
    try:
        stat = path.stat()
        # ns API: the float-seconds form of os.utime round-trips mtime through
        # a double and perturbs it by ~100ns, which still invalidates the memo.
        os.utime(path, ns=(time.time_ns(), stat.st_mtime_ns))
    except Exception:
        pass


def _cleanup_missing_manifest_entries() -> None:
    with _MANIFEST_LOCK:
        _cleanup_missing_manifest_entries_locked()


def _cleanup_missing_manifest_entries_locked() -> None:
    manifest = _MANIFEST_ENTRIES
    if manifest is None:
        return
    removed = False
    for cache_id, entry in list(manifest.items()):
        entry_path = Path(entry.relative_path)
        if (entry_path if entry_path.is_absolute() else _committed_root() / entry_path).exists():
            continue
        _forget_alias(cache_id, manifest)
        removed = True
    if removed:
        _save_manifest()


def _prune_persistent_cache() -> None:
    # The manifest scan is short and must be atomic against a concurrent commit;
    # the unreferenced-file sweep below is an rglob over the whole cache root and
    # deliberately runs outside the lock so it cannot stall a main-thread commit.
    with _MANIFEST_LOCK:
        manifest = _manifest_entries()
        updated = False

        live_paths: set[str] = set()
        for cache_id, entry in list(manifest.items()):
            entry_path = Path(entry.relative_path)
            path = entry_path if entry_path.is_absolute() else _committed_root() / entry_path
            if not path.exists():
                _forget_alias(cache_id, manifest)
                updated = True
                continue
            try:
                live_paths.add(os.path.normcase(str(path.resolve(strict=False))))
            except Exception:
                live_paths.add(os.path.normcase(str(path)))
        if updated:
            _save_manifest_locked()
        load_failed = _MANIFEST_LOAD_FAILED
    if load_failed:
        return
    # Another Blender (or a harness) shares this root: its aliases, written after this
    # process loaded the manifest, and the pin list name files this process never heard of.
    # Read lazily, only once a sweep candidate exists (usually none).
    _delete_unreferenced_geometry_files(live_paths, other_live_paths=_other_sessions_live_paths)


def _delete_unreferenced_geometry_files(live_paths: set[str], other_live_paths=None) -> None:
    """Remove committed/canonical files the alias manifest no longer names.

    Geometry identity changes allocate a new cache id; the old file is otherwise
    left behind forever. Skip files written in the last hour so an in-flight
    canonical write cannot be deleted before its alias is published.
    """
    now = time.time()
    others: set[str] | None = None
    for root in (_committed_root(), _canonical_geometry_root()):
        try:
            if not root.exists():
                continue
            children = list(root.rglob("*"))
        except Exception:
            continue
        for path in children:
            try:
                if not path.is_file() or path.is_symlink():
                    continue
                if path.name in {"aliases.json", "aliases.tmp", "aliases.lock"} or path.suffix.lower() == ".tmp":
                    continue
                try:
                    key = os.path.normcase(str(path.resolve(strict=False)))
                except Exception:
                    key = os.path.normcase(str(path))
                if key in live_paths:
                    continue
                if (now - path.stat().st_mtime) < 3600.0:
                    continue
                if other_live_paths is not None:
                    if others is None:
                        others = other_live_paths()
                        if others is None:
                            return  # a manifest on disk could not be read: sweep nothing
                    if key in others:
                        continue
                path.unlink(missing_ok=True)
            except Exception:
                continue


def _committed_mesh_relative_path(cache_id: str) -> Path:
    return Path(cache_id[:2]) / f"{cache_id}.fymesh"


def _committed_mesh_path(cache_id: str) -> Path:
    return _committed_root() / _committed_mesh_relative_path(cache_id)


def _runtime_mesh_path(cache_id: str) -> Path:
    return _runtime_root() / cache_id[:2] / f"{cache_id}.fymesh"


def _persistent_cache_key(cache_id: str, signature: str = "") -> str:
    signature_token = str(signature or "").strip()
    if signature_token:
        return f"HIGH_CACHE:{cache_id}:{signature_token}"
    return f"HIGH_CACHE:{cache_id}"


def geometry_revision_key(obj) -> str:
    """Identity of ``obj``'s evaluated geometry, as this cache tracks it.

    The same ``HIGH_CACHE:<cache_id>:<signature>`` token a high ref carries as its
    ``cache_key``: the cache id rotates on every depsgraph GEOMETRY update of the object
    (edit-mode edits, face material reassignment, modifier changes), and the signature
    covers the cheap object/data/modifier-stack facts. Sidecars derived purely from the
    evaluated topology (the ID map's per-triangle material slots) key on it so a warm
    bake reuses them without re-evaluating the mesh.
    """
    state = _ensure_state(obj)
    return _persistent_cache_key(state.cache_id, _quick_source_signature(obj))


def _delete_legacy_backend_mesh_entry(cache_id: str, signature: str) -> None:
    """Remove the parsed generic mesh made obsolete by a verified FYRGEOM1 alias."""
    from . import indexed_geometry

    lookup_key = f"cache:{_persistent_cache_key(cache_id, signature)}"
    stem = indexed_geometry.xxh3_text_hex(lookup_key)
    mesh_root = preferences.persistent_cache_root() / "meshes"
    for suffix in (".revision", ".fymesh"):
        (mesh_root / f"{stem}{suffix}").unlink(missing_ok=True)


def _flatten_matrix(matrix) -> list[float]:
    try:
        return [float(value) for row in matrix for value in row]
    except Exception:
        return [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ]


def _world_to_object_matrix_values(obj) -> list[float]:
    matrix_world = getattr(obj, "matrix_world", None)
    if matrix_world is None:
        return _flatten_matrix(None)
    try:
        return _flatten_matrix(matrix_world.inverted_safe())
    except Exception:
        return _flatten_matrix(None)


def _matrix_world_values(obj) -> list[float]:
    return _flatten_matrix(getattr(obj, "matrix_world", None))


def _resolve_object_material_name(obj) -> str:
    active_material = getattr(obj, "active_material", None)
    if active_material is not None and getattr(active_material, "name", None):
        return str(active_material.name)
    slots = getattr(obj, "material_slots", None)
    if slots:
        for slot in slots:
            material = getattr(slot, "material", None)
            if material is not None and getattr(material, "name", None):
                return str(material.name)
    data = getattr(obj, "data", None)
    materials = getattr(data, "materials", None) if data is not None else None
    if materials:
        for material in materials:
            if material is not None and getattr(material, "name", None):
                return str(material.name)
    return ""


def _resolve_object_collection_name(obj) -> str:
    collections = collection_index.users_collection(obj)
    if collections:
        for collection in collections:
            name = str(getattr(collection, "name", "") or "").strip()
            if name:
                return name
    return ""


def _build_ref_from_path(obj, path: Path, cache_id: str, signature: str = "") -> protocol.ExportedMeshRef:
    from . import export

    if path.suffix.lower() == ".fyrgeom":
        from . import indexed_geometry

        byte_size, content_hash = indexed_geometry.inspect_canonical_file(path)
        return protocol.ExportedMeshRef(
            name=naming.sanitize_token(str(getattr(obj, "name", "") or "")),
            object_name=str(getattr(obj, "name", "") or ""),
            role=constants.OBJECT_ROLE_HIGH,
            path=str(path),
            cache_key=_persistent_cache_key(cache_id, signature),
            material_name=_resolve_object_material_name(obj),
            material_color=export._resolve_object_material_color(obj),
            collection_name=_resolve_object_collection_name(obj),
            file_id_key=export._resolve_object_file_id_key(obj),
            world_to_object=_world_to_object_matrix_values(obj),
            matrix_world=_matrix_world_values(obj),
            transport_kind=protocol.MESH_TRANSPORT_CANONICAL_CACHE,
            geometry_schema=protocol.GEOMETRY_SCHEMA_FYRGEOM1,
            transport_locator=str(path),
            byte_size=byte_size,
            content_hash=content_hash,
        )

    return protocol.ExportedMeshRef(
        name=naming.sanitize_token(str(getattr(obj, "name", "") or "")),
        object_name=str(getattr(obj, "name", "") or ""),
        role=constants.OBJECT_ROLE_HIGH,
        path=str(path),
        cache_key=_persistent_cache_key(cache_id, signature),
        material_name=_resolve_object_material_name(obj),
        material_color=export._resolve_object_material_color(obj),
        collection_name=_resolve_object_collection_name(obj),
        file_id_key=export._resolve_object_file_id_key(obj),
        world_to_object=_world_to_object_matrix_values(obj),
        matrix_world=_matrix_world_values(obj),
    )


def _ensure_state(obj) -> _TrackedHighObjectState:
    object_key = _object_key(obj)
    existing = _TRACKED_OBJECTS.get(object_key)
    if existing is not None:
        existing.object_ref = obj
        return existing
    cache_id = _ensure_object_cache_id(obj)
    state = _TrackedHighObjectState(
        object_ref=obj,
        object_key=object_key,
        data_key=_data_key(obj),
        cache_id=cache_id,
    )
    _TRACKED_OBJECTS[object_key] = state
    if state.data_key:
        _TRACKED_DATA_KEYS.setdefault(state.data_key, set()).add(object_key)
    return state


def _export_state(obj):
    """The cache state an export of ``obj`` reads and fills: the object's own, or its
    floater piece's while a floater_faces.export_part(PART_FLOATER) block is active."""
    state = _ensure_state(obj)
    if floater_faces.current_part(obj) != floater_faces.PART_FLOATER:
        return state
    part = _FLOATER_STATES.get(state.object_key)
    if part is None or part.base is not state:
        part = _FloaterPartState(base=state)
        _FLOATER_STATES[state.object_key] = part
    if part.base_cache_id != state.cache_id:
        # The object's id rotated (an edit): the piece's runtime slot is stale too.
        part.base_cache_id = state.cache_id
        part.runtime_ref = None
        part.runtime_signature = ""
        part.runtime_color_key = ""
        part.dirty = True
    return part


def _mark_state_dirty(state: _TrackedHighObjectState) -> None:
    state.edits += 1
    if state.dirty:
        return
    old_cache_id = state.cache_id
    new_cache_id = uuid.uuid4().hex
    state.cache_id = new_cache_id
    _object_prop_set(state.object_ref, _OBJECT_CACHE_ID_PROP, new_cache_id)
    _CACHE_ID_TO_OBJECT_KEY.pop(old_cache_id, None)
    _CACHE_ID_TO_OBJECT_KEY[new_cache_id] = state.object_key
    # Every rotation used to leave the old alias in the manifest forever, and the
    # unreferenced-file sweep only deletes files the manifest does NOT name, so
    # each edit + save of a 1.3 GB high mesh pinned one more full copy for good.
    # Keep exactly one previous alias per object (Undo restores that id), retire
    # the one before it.
    retired = str(getattr(state, "previous_cache_id", "") or "")
    state.previous_cache_id = old_cache_id
    if retired and retired not in (old_cache_id, new_cache_id):
        try:
            with _MANIFEST_LOCK:
                popped = _forget_alias(retired)
                popped = _forget_alias(retired + _FLOATER_CACHE_ID_SUFFIX) or popped
                if popped:
                    _save_manifest_locked()
        except Exception:
            pass
    state.runtime_ref = None
    state.runtime_signature = ""
    state.runtime_color_key = ""
    state.dirty = True


def _committed_color_key(cache_id: str) -> str:
    entry = _manifest_entries().get(cache_id)
    return str(getattr(entry, "color_key", "") or "") if entry is not None else ""


def _resolved_committed_ref(obj, cache_id: str, signature: str) -> protocol.ExportedMeshRef | None:
    entry = _manifest_entries().get(cache_id)
    if entry is None or entry.signature != signature:
        return None
    entry_path = Path(entry.relative_path)
    path = entry_path if entry_path.is_absolute() else _committed_root() / entry_path
    if not path.exists():
        _forget_alias(cache_id)
        return None
    _touch_path(path)
    return _build_ref_from_path(obj, path, cache_id, signature)


def resolve_indexed_high_mesh_ref(
    obj,
    depsgraph,
    workspace_key: str | Path,
    *,
    include_corner_colors: bool = False,
    color_source=None,
    cancel_check=None,
    retain_section: bool = True,
) -> protocol.ExportedMeshRef:
    from . import export, indexed_geometry

    if floater_faces.has_floater_faces(obj) and floater_faces.current_part(obj) is None:
        # Outside an export (prewarm, warm-before-bake) a high with floater faces resolves
        # its body, the piece the bake exports under the object's own cache id.
        with floater_faces.export_part(obj, floater_faces.PART_BODY):
            return resolve_indexed_high_mesh_ref(
                obj,
                depsgraph,
                workspace_key,
                include_corner_colors=include_corner_colors,
                color_source=color_source,
                cancel_check=cancel_check,
                retain_section=retain_section,
            )

    # The colour section's CONTENT identity: "" for the active colour attribute (every
    # file written before Attribute rows existed), else the attribute source. A file
    # whose colours came from another source must not serve this request.
    color_key = color_source.cache_key if (include_corner_colors and color_source is not None) else ""

    if _parked_placeholder(obj) and not _restore_parked_when_idle(obj):
        raise ParkedHighMeshError(f"{obj.name} is parked for the bake; not exporting its placeholder")
    state = _export_state(obj)
    signature = _quick_source_signature(obj)
    if state.runtime_ref is not None and state.runtime_signature == signature and not state.dirty:
        path = Path(state.runtime_ref.path)
        if path.suffix.lower() != ".fyrgeom":
            path = None
        elif not path.exists():
            try:
                indexed_geometry.wait_for_canonical_path(path)
            except RuntimeError:
                # The background write of this file failed (disk full, file removed): export
                # the mesh again below instead of failing the bake on a file that never came.
                path = None
        if path is not None and path.exists() and (
            not include_corner_colors
            or (
                indexed_geometry.canonical_colors_resolved(path)
                and str(getattr(state, "runtime_color_key", "") or "") == color_key
            )
        ):
            return _build_ref_from_path(obj, path, state.cache_id, signature)
    committed_ref = _resolved_committed_ref(obj, state.cache_id, signature)
    if committed_ref is not None and (
        not include_corner_colors
        or (
            indexed_geometry.canonical_colors_resolved(committed_ref.path)
            and _committed_color_key(state.cache_id) == color_key
        )
    ):
        state.runtime_ref = committed_ref
        state.runtime_color_key = _committed_color_key(state.cache_id)
        state.runtime_signature = signature
        state.dirty = False
        return committed_ref

    transport = indexed_geometry.create_evaluated_high_section(
        obj,
        depsgraph,
        workspace_key,
        include_corner_colors=include_corner_colors,
        color_source=color_source if include_corner_colors else None,
        canonical_root=_canonical_geometry_root(),
        cancel_check=cancel_check,
        retain_section=retain_section,
    )
    canonical_ref = protocol.ExportedMeshRef(
        name=naming.sanitize_token(str(getattr(obj, "name", "") or "")),
        object_name=str(getattr(obj, "name", "") or ""),
        role=constants.OBJECT_ROLE_HIGH,
        path=str(transport.canonical_path),
        cache_key=_persistent_cache_key(state.cache_id, signature),
        material_name=_resolve_object_material_name(obj),
        material_color=export._resolve_object_material_color(obj),
        collection_name=_resolve_object_collection_name(obj),
        file_id_key=export._resolve_object_file_id_key(obj),
        world_to_object=_world_to_object_matrix_values(obj),
        matrix_world=_matrix_world_values(obj),
        transport_kind=protocol.MESH_TRANSPORT_CANONICAL_CACHE,
        geometry_schema=protocol.GEOMETRY_SCHEMA_FYRGEOM1,
        transport_locator=str(transport.canonical_path),
        byte_size=transport.byte_size,
        content_hash=transport.content_hash,
    )
    state.runtime_ref = canonical_ref
    state.runtime_color_key = color_key
    state.runtime_signature = signature
    state.dirty = False
    with _MANIFEST_LOCK:
        _manifest_entries()[state.cache_id] = _ManifestEntry(
            cache_id=state.cache_id,
            signature=signature,
            relative_path=str(transport.canonical_path),
            object_name=str(getattr(obj, "name", "") or ""),
            color_key=color_key,
        )
        _save_manifest_locked()
    _save_active_project_pins()
    return protocol.ExportedMeshRef(
        name=canonical_ref.name,
        object_name=canonical_ref.object_name,
        role=constants.OBJECT_ROLE_HIGH,
        # Canonical compact fallback is carried separately from the primary named
        # section locator. It is not copied into the bake workspace.
        path=str(transport.canonical_path),
        cache_key=canonical_ref.cache_key,
        material_name=canonical_ref.material_name,
        material_color=canonical_ref.material_color,
        collection_name=canonical_ref.collection_name,
        file_id_key=canonical_ref.file_id_key,
        world_to_object=canonical_ref.world_to_object,
        matrix_world=canonical_ref.matrix_world,
        transport_kind=protocol.MESH_TRANSPORT_WIN32_SECTION,
        geometry_schema=protocol.GEOMETRY_SCHEMA_FYRGEOM1,
        transport_locator=transport.mapping_name,
        byte_size=transport.byte_size,
        content_hash=transport.content_hash,
    )


def export_indexed_canonical(obj, depsgraph) -> Path | None:
    """The canonical FYRGEOM1 file of ``obj``, exported now (main thread) unless it is warm.

    The Automatic cage fit used to write a second, native ``.fymesh`` of every high for the GPU
    cage tool (a full capture of the mesh), and the bake then captured it again as FYRGEOM1.
    The tool reads FYRGEOM1 as well, so the fit exports the one file the bake uses. The file
    write finishes on a worker thread (``indexed_geometry.wait_for_canonical_path`` joins it);
    the path may not exist yet. None when it cannot be exported here (parked, no mesh)."""
    from . import indexed_geometry

    if not indexed_geometry.enabled():
        return None
    warm = warm_indexed_high_mesh_path(obj)
    if warm is not None:
        return warm
    try:
        state = _ensure_state(obj)
        runtime_ref = state.runtime_ref
        if (
            runtime_ref is not None
            and state.runtime_signature == _quick_source_signature(obj)
            and not state.dirty
            and Path(runtime_ref.path).suffix.lower() == ".fyrgeom"
        ):
            return Path(runtime_ref.path)  # exported already, its file write may still be running
        scratch_key = preferences.persistent_cache_root() / "scratch" / "indexed_prewarm" / state.cache_id
        indexed_geometry.throttle_canonical_writes()
        ref = resolve_indexed_high_mesh_ref(obj, depsgraph, scratch_key, retain_section=False)
    except Exception:
        return None
    return Path(ref.path)


def _export_runtime_ref(obj, depsgraph, state: _TrackedHighObjectState, signature: str) -> protocol.ExportedMeshRef:
    from . import export

    if _parked_placeholder(obj) and not _restore_parked_when_idle(obj):
        # The bake running beside the park reads this very runtime file: exporting the
        # empty placeholder over it baked a customer's 71-high gun with 0 high triangles.
        raise ParkedHighMeshError(f"{obj.name} is parked for the bake; not exporting its placeholder")

    destination = _runtime_mesh_path(state.cache_id)
    mesh_transport.ensure_dir(destination.parent)
    ref = export.write_evaluated_high_obj(
        obj,
        depsgraph,
        destination,
        cache_key_override=_persistent_cache_key(state.cache_id, signature),
    )
    ref.role = constants.OBJECT_ROLE_HIGH
    state.runtime_ref = ref
    state.runtime_color_key = ""
    state.runtime_signature = signature
    state.dirty = False
    return ref


def _parked_placeholder(obj) -> bool:
    """True while high_poly_park has swapped this object's mesh for an empty placeholder."""
    try:
        from . import high_poly_park

        data = getattr(obj, "data", None)
        return str(getattr(data, "name", "") or "").endswith(high_poly_park.PLACEHOLDER_SUFFIX) or bool(
            obj.get(high_poly_park.OBJECT_MESH_PROP)
        )
    except Exception:
        return False


def _restore_parked_when_idle(obj) -> bool:
    """With no bake running, a placeholder only means the restore has not reached this
    high yet (it comes back in timer slices): bring it back now and export the real mesh.
    True when ``obj`` is a real mesh again."""
    try:
        from . import high_poly_park

        high_poly_park.ensure_restored([obj], only_when_idle=True)
    except Exception:
        return False
    return not _parked_placeholder(obj)


def geometry_edit_token(obj):
    """Identity of ``obj``'s geometry edit history, or None when it is not tracked.

    Equal tokens mean no geometry edit reached the tracker in between (the same signal
    that lets a repeat bake reuse the exported high). high_poly_park reuses its park
    file only for meshes whose token is unchanged."""
    try:
        state = _TRACKED_OBJECTS.get(_object_key(obj))
        if state is None:
            return None
        data = getattr(obj, "data", None)
        return (
            state.cache_id,
            state.edits,
            mesh_read.element_count(data, "vertices"),
            mesh_read.element_count(data, "polygons"),
        )
    except Exception:
        return None


class ParkedHighMeshError(RuntimeError):
    """A parked high's placeholder must never be exported over its real geometry."""


def resolve_high_mesh_ref(obj, depsgraph) -> protocol.ExportedMeshRef:
    if floater_faces.has_floater_faces(obj) and floater_faces.current_part(obj) is None:
        # See resolve_indexed_high_mesh_ref: outside an export this is the body.
        with floater_faces.export_part(obj, floater_faces.PART_BODY):
            return resolve_high_mesh_ref(obj, depsgraph)
    state = _export_state(obj)
    signature = _quick_source_signature(obj)
    if floater_faces.current_part(obj) is None:
        _await_prewarm_write(state.object_key)
    runtime_ref = state.runtime_ref
    if runtime_ref is not None and Path(runtime_ref.path).exists() and state.runtime_signature == signature and not state.dirty:
        return _build_ref_from_path(obj, Path(runtime_ref.path), state.cache_id, signature)

    committed_ref = _resolved_committed_ref(obj, state.cache_id, signature)
    if committed_ref is not None:
        state.dirty = False
        state.runtime_signature = signature
        return committed_ref

    return _export_runtime_ref(obj, depsgraph, state, signature)


def export_legacy_high_mesh_ref(obj, depsgraph) -> protocol.ExportedMeshRef:
    """Export ``obj`` as an FYMESH triangle soup even when a canonical FYRGEOM1 is warm."""
    if floater_faces.has_floater_faces(obj) and floater_faces.current_part(obj) is None:
        with floater_faces.export_part(obj, floater_faces.PART_BODY):
            return export_legacy_high_mesh_ref(obj, depsgraph)
    state = _export_state(obj)
    return _export_runtime_ref(obj, depsgraph, state, _quick_source_signature(obj))


def high_mesh_ref_is_warm(obj) -> bool:
    """True when resolve_high_mesh_ref would return without the multi-second
    evaluated-mesh capture + serialize (runtime ref current, or a committed
    cache entry matches). Lets callers amortize cold captures one object per
    timer tick instead of freezing the UI for the whole scene at once."""
    try:
        state = _ensure_state(obj)
        signature = _quick_source_signature(obj)
    except Exception:
        return False
    runtime_ref = state.runtime_ref
    if (
        runtime_ref is not None
        and Path(runtime_ref.path).exists()
        and state.runtime_signature == signature
        and not state.dirty
    ):
        return True
    entry = _manifest_entries().get(state.cache_id)
    return (
        entry is not None
        and entry.signature == signature
        and (_committed_root() / entry.relative_path).exists()
    )


def warm_high_mesh_path(obj) -> Path | None:
    """Return a current persistent high-mesh path without exporting geometry."""
    try:
        state = _ensure_state(obj)
        signature = _quick_source_signature(obj)
    except Exception:
        return None
    runtime_ref = state.runtime_ref
    if (
        runtime_ref is not None
        and state.runtime_signature == signature
        and not state.dirty
    ):
        path = Path(runtime_ref.path)
        if path.suffix.lower() in {".fyrgeom", ".fymesh"} and path.exists():
            return path
    entry = _manifest_entries().get(state.cache_id)
    if entry is None or entry.signature != signature:
        return None
    path = Path(entry.relative_path)
    path = path if path.is_absolute() else _committed_root() / path
    return path if path.suffix.lower() in {".fyrgeom", ".fymesh"} and path.exists() else None


def warm_indexed_high_mesh_path(obj) -> Path | None:
    path = warm_high_mesh_path(obj)
    return path if path is not None and path.suffix.lower() == ".fyrgeom" else None


def _iter_scene_high_objects(scene):
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None:
        return
    for project in getattr(settings, "projects", []):
        for group in getattr(project, "groups", []):
            for slot in properties.effective_high_mesh_slots(group):
                obj = getattr(slot, "object_ref", None)
                if obj is None or str(getattr(obj, "type", "") or "") != "MESH":
                    continue
                yield obj


def _loaded_scenes_with(scene):
    seen: set[int] = set()
    scenes = getattr(getattr(bpy, "data", None), "scenes", None)
    if scenes is not None:
        for candidate in scenes:
            candidate_id = id(candidate)
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            yield candidate
    if scene is not None and id(scene) not in seen:
        yield scene


def reconcile_scene_tracking(scene) -> None:
    """Drop runtime tracking for high meshes no longer used by any loaded project."""
    referenced_keys = {
        _object_key(obj)
        for loaded_scene in _loaded_scenes_with(scene)
        for obj in _iter_scene_high_objects(loaded_scene)
    }
    stale_keys = set(_TRACKED_OBJECTS).difference(referenced_keys)
    if not stale_keys:
        return

    for object_key in stale_keys:
        _FLOATER_STATES.pop(object_key, None)
        state = _TRACKED_OBJECTS.pop(object_key, None)
        if state is None:
            continue
        if _CACHE_ID_TO_OBJECT_KEY.get(state.cache_id) == object_key:
            _CACHE_ID_TO_OBJECT_KEY.pop(state.cache_id, None)
        # Vertex-position edits do not change the cheap topology signature. Removing
        # the identity prevents a mesh edited while untracked from later reusing its
        # pre-removal committed export when it is assigned to a new project.
        _object_prop_delete(state.object_ref, _OBJECT_CACHE_ID_PROP)

    for data_key, object_keys in list(_TRACKED_DATA_KEYS.items()):
        object_keys.difference_update(stale_keys)
        if not object_keys:
            _TRACKED_DATA_KEYS.pop(data_key, None)
    _PENDING_PREWARM_KEYS.difference_update(stale_keys)


def request_context_prewarm(context, *, reason: str = "") -> None:
    """Schedule a background export pass for all high-poly objects in the scene.

    The signature check is now cheap (no bound_box, no modifier property introspection)
    and the export uses the compact V4 format (~45% smaller than V2), so this runs without
    the multi-minute freeze that the old code caused for large meshes.
    """
    del reason
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    for obj in _iter_scene_high_objects(scene):
        state = _ensure_state(obj)
        _PENDING_PREWARM_KEYS.add(state.object_key)
    _save_active_project_pins()
    _ensure_prewarm_timer()


def _prewarm_depsgraph():
    context = getattr(bpy, "context", None)
    getter = getattr(context, "evaluated_depsgraph_get", None) if context is not None else None
    if not callable(getter):
        return None
    try:
        return getter()
    except Exception:
        return None


def _ensure_prewarm_timer(*, first_interval: float | None = None) -> None:
    global _PREWARM_TIMER_REGISTERED, _PREWARM_DUE_AT
    if not _PENDING_PREWARM_KEYS:
        return
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    _PREWARM_DUE_AT = time.monotonic() + max(0.05, float(first_interval if first_interval is not None else _PREWARM_DELAY_SECONDS))
    if _PREWARM_TIMER_REGISTERED:
        return
    _PREWARM_TIMER_REGISTERED = True
    timers.register(_prewarm_timer, first_interval=max(0.05, float(first_interval if first_interval is not None else _PREWARM_DELAY_SECONDS)))


def _abandon_prewarm_write() -> None:
    """Forget the in-flight writes (file load, Clear Cache, unregister): their object
    state is gone, so the files are never used; a helper thread deletes each once written."""
    jobs = list(_PREWARM_WRITES)
    _PREWARM_WRITES.clear()
    for job in jobs:
        if job.thread is None:
            continue

        def _discard(job=job):
            try:
                job.thread.join()
                job.temp_path.unlink()
            except BaseException:  # noqa: BLE001 - a missing file or a dead thread is fine
                pass

        threading.Thread(target=_discard, name="FyrHighPrewarmDiscard", daemon=True).start()


def _reset_runtime_state() -> None:
    global _PENDING_PREWARM_KEYS, _PREWARM_DUE_AT
    _abandon_prewarm_write()
    _TRACKED_OBJECTS.clear()
    _TRACKED_DATA_KEYS.clear()
    _CACHE_ID_TO_OBJECT_KEY.clear()
    _PENDING_PREWARM_KEYS = set()
    _PREWARM_DUE_AT = 0.0


def _schedule_park_prewrite() -> None:
    """The prewarm has drained: use the idle time to write the park file a Bake would
    otherwise wait for (high_poly_park decides whether that Bake would park at all)."""
    try:
        from . import high_poly_park

        high_poly_park.schedule_prewrite()
    except Exception:
        pass


def _prewarm_timer():
    interval = _prewarm_timer_tick()
    if interval is None:
        _schedule_park_prewrite()
    return interval


def _prewarm_timer_tick():
    global _PREWARM_TIMER_REGISTERED, _PREWARM_FIT_NEXT_AT
    if not _PENDING_PREWARM_KEYS and not _PREWARM_WRITES:
        _PREWARM_TIMER_REGISTERED = False
        return None
    remaining = _PREWARM_DUE_AT - time.monotonic()
    if remaining > 0.0:
        return max(0.05, remaining)
    try:
        from . import high_poly_park

        if high_poly_park.is_parked():
            # The highs are empty placeholders until the bake restores them; their keys
            # stay queued for after the restore.
            return 2.0
    except Exception:
        pass
    try:
        from . import operators

        if getattr(operators, "_DEFERRED_BAKE_STATE", None) is not None:
            # The bake's own setup is exporting the remaining highs on this same write
            # pool; two timers' time budgets would only stretch each other's frames.
            return 0.25
    except Exception:
        pass

    reap_prewarm_writes()
    if not _PENDING_PREWARM_KEYS:
        if _PREWARM_WRITES:
            return _PREWARM_WRITE_POLL_SECONDS
        _PREWARM_TIMER_REGISTERED = False
        return None

    fits_pending = False
    try:
        from . import runtime

        fits_pending = bool(runtime._viewport_cage_fits_pending())
    except Exception:
        pass
    if fits_pending:
        # Cage fits and exports share the main thread. Starving the exports left every
        # high for the Bake press (the customer's gun waited ~20 s there), while running
        # them back to back more than doubled how long the cages took to show
        # (2026-10-28). So the exports take a bounded share: after a batch that held the
        # main thread for T seconds the fits get _PREWARM_FIT_SHARE * T before the next.
        wait = _PREWARM_FIT_NEXT_AT - time.monotonic()
        if wait > 0.0:
            return min(max(0.05, wait), 1.0)

    depsgraph = _prewarm_depsgraph()
    if depsgraph is None:
        return _PREWARM_RETRY_SECONDS

    started = time.perf_counter()
    busy = False
    while _PENDING_PREWARM_KEYS:
        object_key = _PENDING_PREWARM_KEYS.pop()
        state = _TRACKED_OBJECTS.get(object_key)
        obj = getattr(state, "object_ref", None) if state is not None else None
        if obj is None:
            continue
        indexed = False
        try:
            from . import indexed_geometry

            indexed = indexed_geometry.enabled()
            if indexed:
                # The capture is on this thread; the file write finishes on a worker (at most
                # two at a time, each holds its section until written), so the next high
                # is captured while this one is written. The tick used to join the write.
                # The export's own manifest and pin writes are deferred: finalize below
                # writes each file once per high (it used to be twice for the manifest
                # and three times for the pins, every one stat-ing every entry). The
                # alias is published only after the export returned, so a crash before
                # that point loses at worst one alias and the high is exported again.
                with defer_persistence(flush=False):
                    canonical_path = export_indexed_canonical(obj, depsgraph)
                if canonical_path is None:
                    raise RuntimeError("indexed prewarm export unavailable")
                finalize_pending_canonical_aliases()
                # The canonical entry is now authoritative for this object. Remove the
                # legacy Blender export only after the manifest alias flipped.
                _committed_mesh_path(state.cache_id).unlink(missing_ok=True)
                _delete_legacy_backend_mesh_entry(
                    state.cache_id, state.runtime_signature
                )
            else:
                status = submit_high_write(obj, depsgraph)
                if status == WRITE_BUSY:
                    _PENDING_PREWARM_KEYS.add(object_key)
                    busy = True
                    break
                if status == WRITE_SYNC:
                    resolve_high_mesh_ref(obj, depsgraph)
        except Exception:
            pass
        if indexed or time.perf_counter() - started >= _PREWARM_BUDGET_SECONDS:
            break
    if fits_pending:
        _PREWARM_FIT_NEXT_AT = time.monotonic() + (time.perf_counter() - started) * _PREWARM_FIT_SHARE

    if _PENDING_PREWARM_KEYS:
        # Next batch on the next event-loop pass: the UI still redraws in between, and a
        # fixed 0.25 s pause per object added 18 s to a 71-high scene. Waiting on a busy
        # writer polls instead of spinning.
        return _PREWARM_WRITE_POLL_SECONDS if busy else _PREWARM_NEXT_SECONDS
    if _PREWARM_WRITES:
        return _PREWARM_WRITE_POLL_SECONDS
    _PREWARM_TIMER_REGISTERED = False
    return None


@dataclass(slots=True)
class _PrewarmWrite:
    object_key: int
    cache_id: str
    signature: str
    temp_path: Path
    final_path: Path
    edits: int = 0
    thread: object = None
    written: Path | None = None
    error: BaseException | None = None
    nbytes: int = 0


#: The high exports in flight, oldest first. Writing a high's file on the main thread
#: froze a customer's 71-high gun 45 times (0.4 to 15.7 s each) for two minutes after its
#: cages had shown (2026-10-28): only reading the mesh needs Blender, so the main thread
#: captures the arrays and a worker thread writes them. Up to _PREWARM_MAX_WRITES run at
#: once so the capture of the next mesh overlaps the write of the previous one (a write
#: costs about twice a capture); the bytes of captured arrays held by running writes are
#: bounded too.
_PREWARM_WRITES: list[_PrewarmWrite] = []

WRITE_STARTED = "started"
WRITE_PENDING = "pending"
WRITE_BUSY = "busy"
WRITE_SYNC = "sync"


def _captured_nbytes(captured) -> int:
    total = 0
    for part in captured[1:]:
        total += int(getattr(part, "nbytes", 0) or 0)
    return total


def write_in_flight(obj) -> bool:
    """True while a worker thread is writing ``obj``'s export."""
    if not _PREWARM_WRITES:
        return False
    try:
        key = _object_key(obj)
    except Exception:
        return False
    return any(job.object_key == key for job in _PREWARM_WRITES)


def prewarm_writes_in_flight() -> int:
    return len(_PREWARM_WRITES)


def reap_prewarm_writes() -> None:
    """Main thread: record every finished worker write."""
    for job in list(_PREWARM_WRITES):
        if job.thread is None or not job.thread.is_alive():
            _finish_prewarm_write(job)


def submit_high_write(obj, depsgraph) -> str:
    """Capture ``obj``'s evaluated mesh (main thread) and hand its file write to a worker.

    WRITE_STARTED: capture done, write running. WRITE_PENDING: a write of it is already
    running. WRITE_BUSY: the writer is full, nothing captured, try again shortly.
    WRITE_SYNC: no worker write applies (already exported, floater faces, parked, or the
    mesh cannot take the fast path); the caller resolves it synchronously, which is
    cheap when it is already warm."""
    if floater_faces.has_floater_faces(obj) or _parked_placeholder(obj):
        return WRITE_SYNC
    state = _ensure_state(obj)
    if any(job.object_key == state.object_key for job in _PREWARM_WRITES):
        return WRITE_PENDING
    signature = _quick_source_signature(obj)
    runtime_ref = state.runtime_ref
    if runtime_ref is not None and Path(runtime_ref.path).exists() and state.runtime_signature == signature and not state.dirty:
        return WRITE_SYNC
    entry = _manifest_entries().get(state.cache_id)
    if entry is not None and entry.signature == signature:
        return WRITE_SYNC  # the committed copy resolves without writing anything
    if len(_PREWARM_WRITES) >= _PREWARM_MAX_WRITES or (
        _PREWARM_WRITES and sum(job.nbytes for job in _PREWARM_WRITES) >= _PREWARM_MAX_WRITE_BYTES
    ):
        return WRITE_BUSY
    from . import export

    captured = export.capture_high_obj_corner_arrays(obj, depsgraph)
    if captured is None:
        return WRITE_SYNC
    final_path = mesh_transport.binary_mesh_path(_runtime_mesh_path(state.cache_id))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    job = _PrewarmWrite(
        object_key=state.object_key,
        cache_id=state.cache_id,
        signature=signature,
        temp_path=final_path.with_name(f"{final_path.stem}.prewarm{os.getpid()}{final_path.suffix}"),
        final_path=final_path,
        edits=state.edits,
        nbytes=_captured_nbytes(captured),
    )

    def _write(job=job, captured=captured):
        try:
            job.written = export.write_high_corner_arrays(job.temp_path, captured)
        except BaseException as exc:  # reported on the main thread by _finish_prewarm_write
            job.error = exc

    job.thread = threading.Thread(target=_write, name="FyrHighPrewarmWrite", daemon=True)
    _PREWARM_WRITES.append(job)
    job.thread.start()
    return WRITE_STARTED


def _start_prewarm_write(obj, depsgraph) -> bool:
    """True when a worker write of ``obj`` is now running (see :func:`submit_high_write`)."""
    return submit_high_write(obj, depsgraph) == WRITE_STARTED


def _finish_prewarm_write(job: _PrewarmWrite) -> None:
    """Main thread, once the worker is done: move the file into place and record it,
    unless the object changed (or was exported synchronously) meanwhile."""
    if job in _PREWARM_WRITES:
        _PREWARM_WRITES.remove(job)
    written = job.written
    state = _TRACKED_OBJECTS.get(job.object_key)
    obj = getattr(state, "object_ref", None) if state is not None else None
    if job.error is not None:
        print(f"[Fyr Baker] Background high-poly export failed, the bake will export it: {job.error!r}")
    usable = (
        written is not None
        and job.error is None
        and obj is not None
        and state.cache_id == job.cache_id
        and state.edits == job.edits
    )
    if usable:
        try:
            usable = _quick_source_signature(obj) == job.signature and not _parked_placeholder(obj)
        except Exception:
            usable = False
    if usable:
        current = state.runtime_ref
        if current is not None and state.runtime_signature == job.signature and not state.dirty and Path(current.path).exists():
            usable = False  # a synchronous export got there first
    if not usable:
        try:
            job.temp_path.unlink()
        except OSError:
            pass
        if obj is not None and state is not None and job.error is None:
            _PENDING_PREWARM_KEYS.add(job.object_key)
        return
    try:
        os.replace(written, job.final_path)
    except OSError as exc:
        print(f"[Fyr Baker] Could not move a background high-poly export into place, the bake will export it: {exc!r}")
        try:
            job.temp_path.unlink()
        except OSError:
            pass
        return
    state.runtime_ref = _build_ref_from_path(obj, job.final_path, state.cache_id, job.signature)
    state.runtime_color_key = ""
    state.runtime_signature = job.signature
    state.dirty = False


def _await_prewarm_write(object_key: int) -> None:
    """A synchronous resolve of an object the prewarm is writing waits for that write
    rather than writing the same file again beside it."""
    for job in list(_PREWARM_WRITES):
        if job.object_key == object_key:
            job.thread.join()
            _finish_prewarm_write(job)


def is_mesh_prewarm_pending() -> bool:
    """True while background mesh re-export is queued or in progress."""
    return bool(_PENDING_PREWARM_KEYS) or _PREWARM_TIMER_REGISTERED or bool(_PREWARM_WRITES)


def _promote_runtime_exports() -> None:
    with _MANIFEST_LOCK:
        updated = _promote_runtime_exports_locked()
    if updated:
        _prune_persistent_cache()


def _promote_runtime_exports_locked() -> bool:
    updated = False
    manifest = _manifest_entries()
    for state in _TRACKED_OBJECTS.values():
        runtime_ref = state.runtime_ref
        if runtime_ref is None or not state.runtime_signature:
            continue
        runtime_path = Path(runtime_ref.path)
        if not runtime_path.exists():
            continue
        if runtime_ref.transport_kind == protocol.MESH_TRANSPORT_CANONICAL_CACHE:
            manifest[state.cache_id] = _ManifestEntry(
                cache_id=state.cache_id,
                signature=state.runtime_signature,
                relative_path=str(runtime_path),
                object_name=str(getattr(state.object_ref, "name", "") or ""),
                color_key=str(getattr(state, "runtime_color_key", "") or ""),
            )
            updated = True
            continue
        committed_path = _committed_mesh_path(state.cache_id)
        committed_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = committed_path.with_suffix(".tmp")
        shutil.copy2(runtime_path, temp_path)
        temp_path.replace(committed_path)
        manifest[state.cache_id] = _ManifestEntry(
            cache_id=state.cache_id,
            signature=state.runtime_signature,
            relative_path=str(_committed_mesh_relative_path(state.cache_id)),
            object_name=str(getattr(state.object_ref, "name", "") or ""),
        )
        updated = True
    if updated:
        _save_manifest_locked()
    return updated


class suspend_tracking:
    """Ignore geometry updates (high_poly_park's lossless mesh swaps)."""

    def __enter__(self):
        global _TRACKING_SUSPENDED
        _TRACKING_SUSPENDED += 1
        return self

    def __exit__(self, *_exc):
        global _TRACKING_SUSPENDED
        _TRACKING_SUSPENDED = max(0, _TRACKING_SUSPENDED - 1)
        return False


def rebind_data_keys(objects) -> None:
    """Point tracked objects at their current mesh datablock without dirtying them
    (the datablock was replaced by an identical one)."""
    for obj in objects:
        state = _TRACKED_OBJECTS.get(_object_key(obj))
        if state is None:
            continue
        old_key = state.data_key
        new_key = _data_key(obj)
        if old_key == new_key:
            continue
        if old_key:
            members = _TRACKED_DATA_KEYS.get(old_key)
            if members is not None:
                members.discard(state.object_key)
                if not members:
                    _TRACKED_DATA_KEYS.pop(old_key, None)
        state.data_key = new_key
        state.object_ref = obj
        if new_key:
            _TRACKED_DATA_KEYS.setdefault(new_key, set()).add(state.object_key)


@_PERSISTENT
def _depsgraph_update_post(_scene, depsgraph):
    if _TRACKING_SUSPENDED:
        return
    # Blender also calls this from a bake/render job thread (handler_thread_guard),
    # with the job's render depsgraph: its updates are not artist edits.
    if not on_main_thread():
        return
    settings = getattr(_scene, "fyr_baker_settings", None)
    if settings is None or not getattr(settings, "projects", None):
        reconcile_scene_tracking(_scene)
        return
    updates = getattr(depsgraph, "updates", None)
    if updates is None:
        return
    for update in updates:
        id_data = getattr(update, "id", None)
        if id_data is None:
            continue
        # ``DepsgraphUpdate.id`` is the EVALUATED copy. Its session_uid is 0 and its
        # pointer is not the original's, so _object_key() never matched a tracked
        # object: no edit ever rotated the cache id, and a sculpt or Geometry Nodes
        # change that kept the base counts re-baked the previous high-poly export.
        # ``original`` on an original datablock returns itself.
        id_data = getattr(id_data, "original", None) or id_data
        is_geometry = bool(getattr(update, "is_updated_geometry", False))
        is_transform = bool(getattr(update, "is_updated_transform", False))
        if not is_geometry and not is_transform:
            continue
        # Pure transform changes don't affect local-space export content;
        # the dirty_tracker handles bake re-triggering for those independently.
        if not is_geometry:
            continue
        if isinstance(id_data, bpy.types.Object):
            state = _TRACKED_OBJECTS.get(_object_key(id_data))
            if state is not None:
                _mark_state_dirty(state)
        data_targets = _TRACKED_DATA_KEYS.get(_object_key(id_data))
        if data_targets:
            for object_key in data_targets:
                state = _TRACKED_OBJECTS.get(object_key)
                if state is not None:
                    _mark_state_dirty(state)


@_PERSISTENT
def _load_post(_dummy):
    global _PREWARM_TIMER_REGISTERED
    _reset_runtime_state()
    # Loading a file drops non-persistent timers: a stale flag would stop the prewarm
    # timer from ever being registered again in this session.
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    is_registered = getattr(timers, "is_registered", None)
    if callable(is_registered) and not is_registered(_prewarm_timer):
        _PREWARM_TIMER_REGISTERED = False
    _start_startup_prune()
    request_context_prewarm(getattr(bpy, "context", None), reason="load_post")
    try:
        from . import runtime as _runtime
        _runtime.schedule_backend_prewarm(reason="load_post")
    except Exception:
        pass


@_PERSISTENT
def _save_post(_dummy):
    _promote_runtime_exports()


def _startup_prune_worker(session_token: str) -> None:
    """Reclaim the persistent high-mesh cache off the main thread.

    MUST NOT touch ``bpy``: this runs while Blender is still inside addon enable.
    Everything below resolves paths from environment variables and walks the
    filesystem only. ``storage_cleanup.register`` documents why: a multi-GB disk
    walk on the main thread keeps ``WM_main`` blocked through addon
    enable/disable and Blender 5.1 then crashes drawing leftover widgets.

    The manifest half is serialised with ``_MANIFEST_LOCK`` so a main-thread
    commit landing mid-prune is safe, and the unreferenced-file sweep skips
    anything written in the last hour so an in-flight canonical write survives.
    """
    try:
        from . import storage_cleanup as _storage_cleanup

        _storage_cleanup.prune_high_mesh_runtime_sessions(current_session_token=session_token)
    except Exception:
        pass
    try:
        from . import orphan_reaper

        # Dead sessions' payload/runtime folders and stale *_PARKED_* families: the export
        # prune only trims payloads past a 2 GB budget, so smaller piles stayed forever.
        orphan_reaper.reap_orphans()
    except Exception:
        pass
    try:
        _manifest_entries()
        _prune_persistent_cache()
    except Exception:
        pass


def _start_startup_prune() -> None:
    global _STARTUP_PRUNE_THREAD
    thread = _STARTUP_PRUNE_THREAD
    if thread is not None and thread.is_alive():
        return
    try:
        thread = threading.Thread(
            target=_startup_prune_worker,
            args=(_SESSION_TOKEN,),
            name="fyr-baker-high-mesh-prune",
            daemon=True,
        )
        thread.start()
    except Exception:
        # No thread available (rare, e.g. a locked-down embedded interpreter):
        # fall back to the old inline behaviour rather than skipping reclaim.
        _startup_prune_worker(_SESSION_TOKEN)
        return
    _STARTUP_PRUNE_THREAD = thread


def register() -> None:
    global _PREWARM_TIMER_REGISTERED
    # Handler registration stays on the main thread; only the disk walk moves off.
    _start_startup_prune()
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None:
        depsgraph_update_post = getattr(handlers, "depsgraph_update_post", None)
        if depsgraph_update_post is not None and _depsgraph_update_post not in depsgraph_update_post:
            depsgraph_update_post.append(_depsgraph_update_post)
        load_post = getattr(handlers, "load_post", None)
        if load_post is not None and _load_post not in load_post:
            load_post.append(_load_post)
        save_post = getattr(handlers, "save_post", None)
        if save_post is not None and _save_post not in save_post:
            save_post.append(_save_post)
    _PREWARM_TIMER_REGISTERED = False


def unregister() -> None:
    global _PREWARM_TIMER_REGISTERED
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None:
        depsgraph_update_post = getattr(handlers, "depsgraph_update_post", None)
        if depsgraph_update_post is not None and _depsgraph_update_post in depsgraph_update_post:
            depsgraph_update_post.remove(_depsgraph_update_post)
        load_post = getattr(handlers, "load_post", None)
        if load_post is not None and _load_post in load_post:
            load_post.remove(_load_post)
        save_post = getattr(handlers, "save_post", None)
        if save_post is not None and _save_post in save_post:
            save_post.remove(_save_post)
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "unregister") and _PREWARM_TIMER_REGISTERED:
        try:
            timers.unregister(_prewarm_timer)
        except Exception:
            pass
    _PREWARM_TIMER_REGISTERED = False
    _reset_runtime_state()
    try:
        from . import storage_cleanup as _storage_cleanup

        # Only THIS process's session: disabling the addon (or a dev reload) used
        # to wipe every other Blender's runtime exports as well.
        _storage_cleanup.remove_high_mesh_runtime_session(_SESSION_TOKEN)
    except Exception:
        pass


def clear_persistent_cache() -> None:
    shutil.rmtree(_persistent_cache_root(), ignore_errors=True)
    clear_persistent_cache_state()


def clear_persistent_cache_state() -> None:
    """Forget every in-memory alias, tracked object and pending prewarm.

    The main-thread half of Clear Cache; the tree delete itself runs off the UI
    thread (see MASTER_BAKER_OT_clear_all_caches).
    """
    global _MANIFEST_ENTRIES, _PREWARM_TIMER_REGISTERED, _MANIFEST_LOAD_FAILED, _MANIFEST_REPLACE_ON_NEXT_SAVE
    _MANIFEST_ENTRIES = {}
    _MANIFEST_LOAD_FAILED = False
    _REMOVED_ALIAS_IDS.clear()
    _MANIFEST_REPLACE_ON_NEXT_SAVE = True
    _PREWARM_TIMER_REGISTERED = False
    _reset_runtime_state()


def persistent_cache_root_path() -> Path:
    return _persistent_cache_root()
