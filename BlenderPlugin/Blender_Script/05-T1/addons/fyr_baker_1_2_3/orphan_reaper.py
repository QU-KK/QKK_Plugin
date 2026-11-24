"""Startup reaping of cache folders whose owning Blender is gone.

``blender_high_exports/payloads/<session>`` (low-mesh and high payload files written by the
export) and ``blender_high_exports/runtime/<session>`` belong to one Blender process, named
by an ``owner.pid`` stamp. Nothing reads another process's folder, so a folder whose owner is
dead is garbage, yet the export's own prune only ran oldest-first down to a 2 GB budget: a
real cache kept 220 dead sessions (about 340 MB) for a week because they were under it.

A bare "is that pid running" test is not enough on Windows, which reuses pids: a dead
session's pid taken by an unrelated process made the folder look live for good. The stamp
file's modification time is when the session started, so a process that was created AFTER
the stamp cannot be the one that wrote it.

Also removes ``<family>_PARKED_<tag>`` folders at the cache root: a developer or harness
renames a live cache family aside to cold-start a measurement; nothing in the add-on reads
them, and they sit outside every budget (a 196 MB ``projection_hits_PARKED_0959`` survived
two months).

Filesystem only: runs on a daemon thread and must never touch ``bpy``.
"""

from __future__ import annotations

import os
from pathlib import Path
import time

from . import storage_cleanup

#: A process created more than this many seconds after the owner stamp was written is a
#: different process that was handed the dead owner's pid.
_PID_REUSE_SLACK_SECONDS = 5.0
#: A session folder with no readable stamp is dead once this old (matches storage_cleanup).
_UNSTAMPED_DEAD_AFTER_SECONDS = 3600.0
#: A PARKED family must have been untouched this long before it is removed.
PARKED_MIN_AGE_SECONDS = 7 * 24 * 3600.0

_ERROR_ACCESS_DENIED = 5
_STILL_ACTIVE = 259
_FILETIME_EPOCH_OFFSET = 116444736000000000


def _windows_process_state(pid: int):
    """(alive, creation_time_epoch_or_None) for ``pid`` on Windows.

    Access denied means the process exists but is not ours to query (elevated): alive,
    creation time unknown, so it is never reaped on the strength of a guess."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ctypes.GetLastError() == _ERROR_ACCESS_DENIED, None
    try:
        exit_code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) and int(exit_code.value) != _STILL_ACTIVE:
            return False, None
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            return True, None
        raw = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        return True, (raw - _FILETIME_EPOCH_OFFSET) / 1e7
    finally:
        kernel32.CloseHandle(handle)


def process_state(pid: int):
    """(alive, creation_time_epoch_or_None). Creation time is only known on Windows."""
    if pid <= 0:
        return False, None
    if os.name == "nt":
        try:
            return _windows_process_state(pid)
        except Exception:
            return True, None
    return storage_cleanup._process_is_alive(pid), None  # noqa: SLF001


def session_owner_is_dead(session_dir: Path, *, now: float | None = None) -> bool:
    """True when the Blender that stamped ``session_dir`` is certainly gone.

    Unsure always means alive: only an absent process, a process created after the stamp
    (pid reuse) or a long-unstamped folder counts as dead."""
    now = time.time() if now is None else now
    owner_file = Path(session_dir) / storage_cleanup._RUNTIME_SESSION_OWNER_FILE  # noqa: SLF001
    try:
        pid = int(owner_file.read_text(encoding="utf-8").strip() or "0")
        stamped_at = owner_file.stat().st_mtime
    except Exception:
        try:
            return (now - Path(session_dir).stat().st_mtime) >= _UNSTAMPED_DEAD_AFTER_SECONDS
        except Exception:
            return False
    alive, created_at = process_state(pid)
    if not alive:
        return True
    if created_at is not None and created_at > stamped_at + _PID_REUSE_SLACK_SECONDS:
        return True
    return False


def _newest_mtime(path: Path) -> float:
    newest = 0.0
    try:
        newest = path.stat().st_mtime
        for child in path.rglob("*"):
            try:
                newest = max(newest, child.stat().st_mtime)
            except OSError:
                continue
    except OSError:
        pass
    return newest


def _is_parked_family(path: Path) -> bool:
    name = path.name.casefold()
    return path.is_dir() and not path.is_symlink() and "_parked" in name


def reap_dead_owner_sessions(cache_root: Path, *, now: float | None = None) -> int:
    """Remove payload/runtime session folders whose owner is dead. Returns folders removed."""
    removed = 0
    for family in ("payloads", "runtime"):
        parent = Path(cache_root) / "blender_high_exports" / family
        try:
            children = [child for child in parent.iterdir() if child.is_dir() and not child.is_symlink()]
        except OSError:
            continue
        for child in children:
            try:
                if not session_owner_is_dead(child, now=now):
                    continue
                storage_cleanup._remove_tree(child)  # noqa: SLF001
                if not child.exists():
                    removed += 1
            except Exception:
                continue
    return removed


def reap_stale_parked_families(cache_root: Path, *, now: float | None = None, min_age_seconds: float = PARKED_MIN_AGE_SECONDS) -> int:
    """Remove ``*_PARKED_*`` folders at the cache root untouched for ``min_age_seconds``."""
    now = time.time() if now is None else now
    removed = 0
    try:
        children = list(Path(cache_root).iterdir())
    except OSError:
        return 0
    for child in children:
        try:
            if not _is_parked_family(child):
                continue
            if (now - _newest_mtime(child)) < min_age_seconds:
                continue
            storage_cleanup._remove_tree(child)  # noqa: SLF001
            if not child.exists():
                removed += 1
        except Exception:
            continue
    return removed


def reap_orphans(cache_root: Path | None = None) -> tuple[int, int]:
    """(session folders removed, parked families removed). Never raises."""
    if storage_cleanup.keep_scratch_enabled():
        return (0, 0)
    try:
        root = Path(cache_root) if cache_root is not None else storage_cleanup.cache_root()
        sessions = reap_dead_owner_sessions(root)
        parked = reap_stale_parked_families(root)
    except Exception:
        return (0, 0)
    if sessions or parked:
        print(f"[MasterBaker] cache cleanup removed {sessions} dead-session folder(s) and {parked} parked cache folder(s)")
    return (sessions, parked)
