"""One automatic-cage fit per group geometry, shared by the viewport preview and the bake,
kept in memory and on disk.

Fitting a group's automatic cage (coverage fit plus the ray reach check) took ~3 s per
group on a customer's 73-group gun: about 3.5 minutes before every cage showed, and the
bake then fitted all of it again. The fit depends only on the low and high geometry
and three switches, so it is stored under a hash of exactly that: the preview's fit
feeds the bake, and reopening the file finds every cage already fitted.

Keys hash the evaluated geometry CONTENT (positions, topology counts, world matrix; see
cage_offset_estimator._mesh_content_digest), so any edit, even with the add-on off, is a
different key. Values are the per-vertex offsets keyed exactly as cage.build_coverage_offsets
returns them, plus the fit's diagnostics.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import threading

#: Bump with any change to the fit (coverage fit, ray reach check, clamps).
FIT_VERSION = "cage_fit_v3"


def fit_version() -> str:
    """The GPU ray check fits slightly differently from the BVH one (same algorithm, evaluation
    order), so the two never share stored fits."""
    try:
        from . import cage_gpu_fit

        if not cage_gpu_fit.available():
            return FIT_VERSION
        if not cage_gpu_fit.native_enabled():
            return FIT_VERSION + "+gpu1"
        return FIT_VERSION + ("+gpu3" if cage_gpu_fit.coverage_enabled() else "+gpu2")
    except Exception:
        return FIT_VERSION

_MEMORY: dict = {}
_MEMORY_ORDER: list = []
_MEMORY_MAX = 512
_DISK_MAX_FILES = 2048


def _store_dir():
    try:
        from . import high_mesh_cache

        return high_mesh_cache.persistent_cache_root_path() / "cage_fits"
    except Exception:
        return None


#: Session memo: the objects' cheap change signatures -> their content hash. Hashing reads
#: every high position (a dense gun: ~0.4 s a group), and the preview, the bake prefit
#: and the export each ask for the same groups.
_KEY_MEMO: dict = {}


def _cheap_signature(objects):
    from .overlay_keys import object_cache_signature, object_revision_signature

    return tuple((object_revision_signature(obj), object_cache_signature(obj)) for obj in objects)


def content_key(low_objs, high_objs, depsgraph, *, smooth_normals: bool, match_by_isolation: bool) -> str | None:
    """Hash of everything the fit reads, or None when a mesh could not be read."""
    try:
        memo_key = (fit_version(), bool(smooth_normals), bool(match_by_isolation), _cheap_signature(low_objs), _cheap_signature(high_objs))
    except Exception:
        memo_key = None
    if memo_key is not None:
        cached = _KEY_MEMO.get(memo_key)
        if cached is not None:
            return cached
    value = _content_key(low_objs, high_objs, depsgraph, smooth_normals=smooth_normals, match_by_isolation=match_by_isolation)
    if memo_key is not None and value is not None:
        _KEY_MEMO[memo_key] = value
        while len(_KEY_MEMO) > 2048:
            _KEY_MEMO.pop(next(iter(_KEY_MEMO)))
    return value


def _content_key(low_objs, high_objs, depsgraph, *, smooth_normals: bool, match_by_isolation: bool) -> str | None:
    from . import cage_offset_estimator

    digest = hashlib.blake2b(digest_size=20)
    digest.update(f"{fit_version()}|{bool(smooth_normals)}|{bool(match_by_isolation)}".encode("ascii"))
    for role, objects in (("low", low_objs), ("high", high_objs)):
        for obj in objects:
            digest.update(f"|{role}|{getattr(obj, 'name', '')}|".encode("utf-8"))
            if not cage_offset_estimator._mesh_content_digest(obj, depsgraph, digest, corner_normals=role == "low"):
                return None
    return digest.hexdigest()


def _remember(key: str, value) -> None:
    if key in _MEMORY:
        return
    _MEMORY[key] = value
    _MEMORY_ORDER.append(key)
    while len(_MEMORY_ORDER) > _MEMORY_MAX:
        _MEMORY.pop(_MEMORY_ORDER.pop(0), None)


#: Keys on disk, listed once per session: probing the disk per group took 1 to 4 s a
#: probe on a customer's gun while the high-mesh prewarm was writing gigabytes beside it.
_ON_DISK: set | None = None


def _on_disk(directory) -> set:
    global _ON_DISK
    if _ON_DISK is None:
        try:
            _ON_DISK = {entry.name[:-4] for entry in os.scandir(directory) if entry.name.endswith(".npz")}
        except OSError:
            _ON_DISK = set()
    return _ON_DISK


def _load(key: str):
    directory = _store_dir()
    if directory is None:
        return None
    if key not in _on_disk(directory):
        return None
    path = directory / f"{key}.npz"
    if not path.is_file():
        return None
    try:
        import numpy as np

        with np.load(path, allow_pickle=False) as data:
            names = [str(name) for name in data["names"]]
            object_index = data["object_index"]
            positions = data["positions"]
            values = data["values"]
            diagnostics = json.loads(str(data["diagnostics"]))
        offsets = {
            (names[int(index)], (float(position[0]), float(position[1]), float(position[2]))): float(value)
            for index, position, value in zip(object_index, positions, values)
        }
        try:
            os.utime(path, None)  # least-recently-used pruning goes by mtime
        except OSError:
            pass
        return offsets, diagnostics
    except Exception:
        return None


#: Saves run on one background thread: the main thread only needs the fit in memory (300
#: groups spent 0.4 s writing npz files inside the bake's prepare). Numpy and file I/O mostly
#: release the GIL, and nothing here touches Blender data. A save lost to a Blender exit
#: costs one refit, never a wrong value (the file is moved into place whole).
_SAVE_QUEUE: "queue.Queue" = queue.Queue()
_SAVE_THREAD: "threading.Thread | None" = None
_SAVE_THREAD_LOCK = threading.Lock()


def _save_worker() -> None:
    while True:
        item = _SAVE_QUEUE.get()
        try:
            _save_now(*item)
        except Exception:
            pass
        finally:
            _SAVE_QUEUE.task_done()


def _save(key: str, offsets: dict, diagnostics: dict) -> None:
    global _SAVE_THREAD
    if _store_dir() is None or not offsets:
        return
    with _SAVE_THREAD_LOCK:
        if _SAVE_THREAD is None or not _SAVE_THREAD.is_alive():
            _SAVE_THREAD = threading.Thread(target=_save_worker, name="fyr-cage-fit-save", daemon=True)
            _SAVE_THREAD.start()
    _SAVE_QUEUE.put((key, offsets, diagnostics))


def flush_saves() -> None:
    """Block until every queued save has been written (tests, harnesses)."""
    _SAVE_QUEUE.join()


def _save_now(key: str, offsets: dict, diagnostics: dict) -> None:
    directory = _store_dir()
    if directory is None or not offsets:
        return
    try:
        import numpy as np

        names: list[str] = []
        name_index: dict = {}
        object_index = np.empty(len(offsets), dtype=np.int32)
        positions = np.empty((len(offsets), 3), dtype=np.float64)
        values = np.empty(len(offsets), dtype=np.float64)
        for row, ((name, position), value) in enumerate(offsets.items()):
            index = name_index.get(name)
            if index is None:
                index = name_index[name] = len(names)
                names.append(str(name))
            object_index[row] = index
            positions[row] = position
            values[row] = value
        plain_diagnostics = {
            name: value for name, value in (diagnostics or {}).items() if isinstance(value, (int, float, str, dict, list))
        }
        directory.mkdir(parents=True, exist_ok=True)
        temp = directory / f"{key}.{os.getpid()}.tmp.npz"
        np.savez(
            temp,
            names=np.array(names, dtype=np.str_),
            object_index=object_index,
            positions=positions,
            values=values,
            diagnostics=np.array(json.dumps(plain_diagnostics, default=str), dtype=np.str_),
        )
        os.replace(temp, directory / f"{key}.npz")
        known = _on_disk(directory)
        known.add(key)
        if len(known) > _DISK_MAX_FILES:  # sorting every file by mtime is not free
            _prune(directory)
    except Exception:
        pass


def _prune(directory) -> None:
    try:
        files = sorted(directory.glob("*.npz"), key=lambda path: path.stat().st_mtime)
    except Exception:
        return
    for path in files[: max(0, len(files) - _DISK_MAX_FILES)]:
        try:
            path.unlink()
            if _ON_DISK is not None:
                _ON_DISK.discard(path.stem)
        except OSError:
            pass


def cached(key: str | None):
    """(offsets, diagnostics) already fitted for ``key``, from memory or disk, else None."""
    if key is None:
        return None
    value = _MEMORY.get(key)
    if value is not None:
        return value
    value = _load(key)
    if value is not None:
        _remember(key, value)
    return value


def put(key: str | None, value) -> None:
    """Keep a fit made elsewhere (the preview's worker thread), in memory and on disk."""
    if key is None or value is None or not value[0]:
        return
    _remember(key, value)
    _save(key, value[0], value[1])


def get_or_fit(key: str | None, compute):
    """(offsets, diagnostics) for ``key``; ``compute()`` runs only when nothing is stored.

    Returns copies-safe values: callers must not mutate the returned offsets."""
    value = cached(key)
    if value is not None:
        return value
    value = compute()
    if value is None or key is None:
        return value
    offsets, diagnostics = value
    if offsets:
        _remember(key, value)
        _save(key, offsets, diagnostics)
    return value
