from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from typing import Iterable

from . import constants, preferences, thread_guard


KEEP_SCRATCH_ENV_VAR = "FYR_BAKER_KEEP_SCRATCH"
LOW_DISK_WARNING_GB_ENV_VAR = "FYR_BAKER_LOW_DISK_WARNING_GB"
LOW_DISK_WARNING_GB_DEFAULT = 5
LOW_MEMORY_WARNING_GB_ENV_VAR = "FYR_BAKER_LOW_MEMORY_WARNING_GB"
# A heavy multi-group bake's postprocess (OIDN host staging, seam-margin plans,
# 4096²-per-map intermediates at AA=2X) can need several GB of system RAM in a
# single burst. When less than this is free, the backend can std::bad_alloc mid
# bake ("bad allocation"); warn up front so the failure isn't a mystery 10s in.
LOW_MEMORY_WARNING_GB_DEFAULT = 6

_JOB_KEEP_FILE_NAMES = {
    "job.mbjob",
    "job.json",
    "job.mbfbs",
    "progress.json",
    "support_bundle.zip",
}
_JOB_REMOVE_DIR_NAMES = {
    "meshes",
    "material_bakes",
    "material_inputs",
}
_JOB_REMOVE_SUFFIXES = {
    ".fymesh",
    ".mbmesh",
    ".tmp",
}
_BACKEND_CACHE_DIR_NAMES = {
    "blender_high_exports",
    "canonical_geometry",
    # Both are regenerable addon-written caches. Missing from this set, Clear Cache
    # left them behind -- 33 MB of material_inputs survived a "cleared" cache during
    # the 2026-08-29 RC sweep.
    "material_inputs",
    "material_ir_sidecars",
    "scratch",
    "meshes",
    "low_mesh_derived",
    "high_scenes",
    "signed_distance_fields",
    "diffusive_ao_fields",
    "projection_hits",
    "dxr_blas",
    "auto_cage",
}

# Backend on-disk cache families that share the persistent byte budget (mirrors
# persistent_backend_cache_directories() in backend_mesh_cache.cpp). blender_high_exports
# is included here so usage and Clean Now match the worker budget; the addon also
# LRU-prunes that family in high_mesh_cache.py via the per-object alias manifest.
_BUDGETED_BACKEND_CACHE_DIR_NAMES = (
    # Addon-written, unlike every other family here: the per-corner Material IR
    # sidecars (pointiness, island random, colour attributes, second UV sets, the
    # multi-material index). Content-addressed, so a mesh edit orphans the old file
    # rather than overwriting it, and one UV pair on a 14.7M-triangle high is ~88 MB.
    # Without a line here the sweeper's allow-list would never see the directory and
    # it would grow without bound.
    "material_ir_sidecars",
    # Same argument as material_ir_sidecars: content-addressed staging for material
    # input images, regenerable, and absent from this list it was neither measured nor
    # swept -- 34 MB of it survived a full Clear Cache during the 2026-08-29 RC sweep.
    "material_inputs",
    "scratch",
    "canonical_geometry",
    "blender_high_exports",
    "meshes",
    "low_mesh_derived",
    "high_scenes",
    "signed_distance_fields",
    "diffusive_ao_fields",
    "projection_hits",
    "dxr_blas",
    "auto_cage",
)

# Per-family entry caps. Must stay in sync with backend_mesh_cache.cpp
# (FYR_BAKER_HIGH_SCENE_CACHE_MAX_ENTRIES / DXR_BLAS / PROJECTION_HITS / FIELD).
_FAMILY_ENTRY_CAPS = {
    # One entry is one component of one layer, so a colour attribute is 3-4 and a
    # UV pair is 2. Sixteen covers a handful of layers across a couple of assets
    # before the oldest start going.
    "material_ir_sidecars": 16,
    "high_scenes": 3,
    "dxr_blas": 32,
    "projection_hits": 16,
    "signed_distance_fields": 16,
    "diffusive_ao_fields": 16,
    "auto_cage": 16,
}

# Name prefixes (lower-cased) of entries FyrBaker itself creates directly in the
# system temp dir. The startup sweep only ever removes entries whose name begins
# with one of these AND that are older than the age threshold — every other file
# in %TEMP% (including the user's own work and unrelated "fyr" website/build logs
# that do not use the "fyr_" separator) is left untouched.
#   fyr_                       backend cache fallback, fyr_baker_update, fyr_baker_reproject,
#                              fyr_baker_blender_high_exports, fyr_decimator, fyr_fix_verify_cache,
#                              fyr_seam_ab, and the standalone app's fyr_* scratch
#   fyrbaker / fyrbench        standalone FyrBaker app + benchmark scratch that omit the separator
#   master_baker_             benchmark harness workspaces + all test scratch
#   mb_auto_cage_preview_ /   addon mkdtemp scratch (overlay auto-cage preview builds, cage fit)
#   mb_cage_fit_
_OWNED_TEMP_NAME_PREFIXES = (
    "fyr_",
    "fyrbaker",
    "fyrbench",
    "master_baker_",
    "mb_auto_cage_preview_",
    "mb_cage_fit_",
)

_TEMP_SWEEP_STARTED = False


def keep_scratch_enabled() -> bool:
    value = str(os.environ.get(KEEP_SCRATCH_ENV_VAR, "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def cache_root() -> Path:
    return preferences.persistent_cache_root()


def scratch_root() -> Path:
    return cache_root() / "scratch"


def low_disk_warning_threshold_bytes() -> int:
    raw_value = str(os.environ.get(LOW_DISK_WARNING_GB_ENV_VAR, "") or "").strip()
    if raw_value:
        try:
            gigabytes = float(raw_value)
            if gigabytes <= 0.0:
                return 0
            return int(gigabytes * 1024 * 1024 * 1024)
        except Exception:
            pass
    return LOW_DISK_WARNING_GB_DEFAULT * 1024 * 1024 * 1024


def _existing_disk_usage_path(path: Path) -> Path | None:
    candidate = path
    while True:
        if candidate.exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent


def _format_gb(byte_count: int) -> str:
    return f"{float(byte_count) / float(1024 * 1024 * 1024):.1f} GB"


def low_disk_space_warnings(entries: Iterable[tuple[str, str | Path | None]]) -> list[str]:
    threshold = low_disk_warning_threshold_bytes()
    if threshold <= 0:
        return []

    checked_volumes: set[str] = set()
    warnings: list[str] = []
    for label, raw_path in entries:
        if not raw_path:
            continue
        path = Path(raw_path)
        usage_path = _existing_disk_usage_path(path)
        if usage_path is None:
            continue
        try:
            resolved = usage_path.resolve(strict=False)
            volume_key = os.path.normcase(str(Path(resolved.anchor or resolved)))
            usage = shutil.disk_usage(usage_path)
        except Exception:
            continue
        if volume_key in checked_volumes:
            continue
        checked_volumes.add(volume_key)
        if int(usage.free) >= threshold:
            continue
        label_text = str(label or "Bake storage").strip() or "Bake storage"
        warnings.append(
            f"Low disk space for {label_text}: {_format_gb(int(usage.free))} free "
            f"(recommended at least {_format_gb(threshold)})"
        )
    return warnings


def low_memory_warning_threshold_bytes() -> int:
    raw_value = str(os.environ.get(LOW_MEMORY_WARNING_GB_ENV_VAR, "") or "").strip()
    if raw_value:
        try:
            gigabytes = float(raw_value)
            if gigabytes <= 0.0:
                return 0
            return int(gigabytes * 1024 * 1024 * 1024)
        except Exception:
            pass
    return LOW_MEMORY_WARNING_GB_DEFAULT * 1024 * 1024 * 1024


def available_system_memory() -> tuple[int, int] | None:
    """Return (available_bytes, total_bytes) of physical RAM, or None if unknown.

    Cross-platform and best-effort: Windows via GlobalMemoryStatusEx, POSIX via
    sysconf. Any failure returns None so callers simply skip the memory check
    rather than blocking a bake on a platform we can't measure."""
    # Windows: GlobalMemoryStatusEx is the only reliable "available" (not just
    # free) figure — it accounts for reclaimable standby memory the way the bake
    # allocator effectively can.
    if os.name == "nt":
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullAvailPhys), int(status.ullTotalPhys)
        except Exception:
            return None
        return None
    # POSIX (Linux, and macOS which exposes SC_AVPHYS_PAGES): pages * page size.
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        total = os.sysconf("SC_PHYS_PAGES") * page_size
        avail = os.sysconf("SC_AVPHYS_PAGES") * page_size
        if total > 0 and avail >= 0:
            return int(avail), int(total)
    except Exception:
        return None
    return None


def _windows_page_file_growth_bytes(total_physical: int, current_page_file_bytes: int) -> int:
    """How much the page files may still grow, from the configured maximum sizes.

    Reads ``Memory Management\\PagingFiles`` ("C:\\pagefile.sys 16384 65536", MB). A
    system-managed entry ("?:\\pagefile.sys" or sizes "0 0") is taken to grow to three
    times RAM, Windows' documented ceiling. Growth is capped by free space on each
    volume. Anything unreadable counts as no growth, which only makes the guard stricter.
    """
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        ) as key:
            entries, _kind = winreg.QueryValueEx(key, "PagingFiles")
    except Exception:
        return 0
    if isinstance(entries, str):
        entries = [entries]
    maximum = 0
    free_by_volume: dict[str, int] = {}
    for entry in entries or ():
        fields = str(entry or "").split()
        if not fields:
            continue
        path = fields[0]
        drive = path[:2] if len(path) >= 2 and path[1] == ":" else ""
        try:
            size_max_mb = int(fields[2]) if len(fields) >= 3 else 0
        except ValueError:
            size_max_mb = 0
        entry_max = 3 * int(total_physical) if drive.startswith("?") or size_max_mb <= 0 else size_max_mb * 1024 * 1024
        if drive and not drive.startswith("?"):
            try:
                free = free_by_volume.setdefault(drive, int(shutil.disk_usage(drive + "\\").free))
            except Exception:
                free = 0
            entry_max = min(entry_max, int(current_page_file_bytes) + free)
        maximum += entry_max
    return max(0, maximum - int(current_page_file_bytes))


def system_memory_status() -> tuple[int, int, int | None] | None:
    """Return (available physical, total physical, available commit) in bytes.

    Available commit is what the OS can still back with RAM + page file: on Windows
    an allocation fails once it is exhausted even with physical RAM free, so a memory
    guard has to look at both. ``None`` in the third slot means the platform exposes
    no meaningful commit figure (macOS); ``None`` overall means unmeasurable.
    """
    if os.name == "nt":
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                # ullAvailPageFile is the commit still available (RAM + page file) at the
                # page file's CURRENT size. Windows grows the page file on demand up to its
                # configured maximum, so an allocation past today's limit still succeeds:
                # a 15M-triangle Cycles bake pushed commit 3 GB past it without failing.
                current_page_files = max(0, int(status.ullTotalPageFile) - int(status.ullTotalPhys))
                growth = _windows_page_file_growth_bytes(int(status.ullTotalPhys), current_page_files)
                return (
                    int(status.ullAvailPhys),
                    int(status.ullTotalPhys),
                    int(status.ullAvailPageFile) + growth,
                )
        except Exception:
            return None
        return None
    meminfo: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="ascii", errors="ignore") as handle:
            for line in handle:
                key, _sep, rest = line.partition(":")
                fields = rest.split()
                if fields:
                    meminfo[key.strip()] = int(fields[0]) * 1024
    except Exception:
        meminfo = {}
    if "MemTotal" in meminfo and "MemAvailable" in meminfo:
        available = meminfo["MemAvailable"]
        commit = available + meminfo.get("SwapFree", 0)
        try:
            with open("/proc/sys/vm/overcommit_memory", "r", encoding="ascii") as handle:
                strict = handle.read().strip() == "2"
        except Exception:
            strict = False
        if strict and "CommitLimit" in meminfo and "Committed_AS" in meminfo:
            commit = max(0, meminfo["CommitLimit"] - meminfo["Committed_AS"])
        return int(available), int(meminfo["MemTotal"]), int(commit)
    measured = available_system_memory()
    if measured is None:
        return None
    return int(measured[0]), int(measured[1]), None


def low_memory_warnings() -> list[str]:
    """Warn when free system RAM is below the threshold a heavy bake needs.

    Returns a list so it composes with low_disk_space_warnings() at the bake
    pre-flight; empty when memory is healthy or unmeasurable."""
    threshold = low_memory_warning_threshold_bytes()
    if threshold <= 0:
        return []
    measured = available_system_memory()
    if measured is None:
        return []
    available, total = measured
    if available >= threshold:
        return []
    used_pct = int(round((1.0 - (available / total)) * 100.0)) if total > 0 else 0
    return [
        f"Low system memory: {_format_gb(available)} free ({used_pct}% used). "
        f"The bake may run out of memory. Close other apps, restart Blender, or "
        f"lower Anti-Aliasing/resolution."
    ]


def ensure_scratch_subdir(*parts: str) -> Path:
    path = scratch_root()
    for part in parts:
        token = str(part or "").strip()
        if token:
            path /= token
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remove_tree(path: Path) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _norm_path(path: str | Path | None) -> str:
    if path is None:
        return ""
    try:
        return os.path.normcase(str(Path(path).resolve(strict=False)))
    except Exception:
        return os.path.normcase(str(path))


def delete_workspaces(paths: Iterable[str | Path | None]) -> None:
    if keep_scratch_enabled():
        return
    seen: set[str] = set()
    for raw_path in paths:
        key = _norm_path(raw_path)
        if not key or key in seen:
            continue
        seen.add(key)
        path = Path(raw_path)
        if path.exists():
            _remove_tree(path)


def _looks_like_job_workspace(workspace: Path) -> bool:
    """Only a directory holding a job file is a bake workspace.

    The slimmer walks the whole tree under the path it is given and deletes
    every .fymesh/.mbmesh/.tmp it finds. Handed a relative path such as
    Path("job.mbjob").parent (which is "."), or any directory that is not a
    job workspace, it strips the repository or the project output root of
    mesh files that are not scratch at all - the Live Reproject baseline blobs
    under .fyr_cache went missing exactly this way (2026-09-06).
    """
    if not workspace.is_absolute():
        return False
    return any((workspace / name).is_file() for name in _JOB_KEEP_FILE_NAMES if name.startswith("job."))


def slim_job_workspace(workspace_path: str | Path | None) -> None:
    if keep_scratch_enabled() or not workspace_path:
        return
    workspace = Path(workspace_path)
    if not workspace.exists() or not workspace.is_dir():
        return
    if not _looks_like_job_workspace(workspace):
        return

    for dir_name in _JOB_REMOVE_DIR_NAMES:
        _remove_tree(workspace / dir_name)

    for path in list(workspace.rglob("*")):
        try:
            if not path.is_file() or path.suffix.lower() not in _JOB_REMOVE_SUFFIXES:
                continue
            # The worker writes progress.json through <name>.<n>.tmp and renames
            # it into place. Slimming a workspace the worker is still writing to
            # must never take that temp away or the rename fails the bake.
            if path.name.startswith("progress.json"):
                continue
            _remove_file(path)
        except Exception:
            continue

    for child in list(workspace.iterdir()):
        try:
            if child.is_dir() and child.name != "logs" and not any(child.iterdir()):
                child.rmdir()
        except Exception:
            pass


def clear_owned_scratch(*, keep_paths: Iterable[str | Path | None] = ()) -> None:
    if keep_scratch_enabled():
        return
    root = scratch_root()
    if not root.exists():
        return
    keep = {_norm_path(path) for path in keep_paths if path}
    for child in list(root.iterdir()):
        child_key = _norm_path(child)
        if child_key in keep:
            continue
        if child.is_dir():
            _remove_tree(child)
        else:
            _remove_file(child)


# A job whose progress file was touched this recently is treated as still running
# and is never pruned. Generous on purpose: the cost of keeping a dead workspace for
# another minute is a few KB, the cost of deleting a live one is a failed bake.
_LIVE_JOB_PROGRESS_WINDOW_SECONDS = 120.0


def _job_workspace_looks_live(workspace: Path) -> bool:
    try:
        progress = workspace / "progress.json"
        if not progress.is_file():
            return False
        return (time.time() - progress.stat().st_mtime) < _LIVE_JOB_PROGRESS_WINDOW_SECONDS
    except Exception:
        # Unreadable means unknown; keeping it is the safe direction.
        return True


_RETIRED_BASELINE_DIR_NAME = "reprojection_baselines"
_RETIRED_BASELINE_ROOTS_SWEPT: set[str] = set()


def remove_retired_reprojection_baselines(output_root: str | Path | None) -> int:
    """Delete the worker-side Live Reproject baselines under ``<root>/.fyr_cache``.

    Until 2026-09-06 every bake with the toggle on had the worker persist a full
    linear 4K blob per output map into ``.fyr_cache/<project>/reprojection_baselines``
    and nothing ever pruned them: one tester project held 2755 of them, 80 GB.
    The feature now transfers textures inside Blender and no code reads that
    directory, so the whole tree is orphaned scratch. Returns bytes reclaimed.
    """
    if keep_scratch_enabled() or not output_root:
        return 0
    cache_root_dir = Path(output_root) / ".fyr_cache"
    try:
        if not cache_root_dir.is_dir():
            return 0
        project_dirs = list(cache_root_dir.iterdir())
    except Exception:
        return 0
    reclaimed = 0
    for project_dir in project_dirs:
        baselines = project_dir / _RETIRED_BASELINE_DIR_NAME
        try:
            if not baselines.is_dir() or baselines.is_symlink():
                continue
            size = _directory_size_bytes(baselines)
            _remove_tree(baselines)
            if not baselines.exists():
                reclaimed += size
        except Exception:
            continue
    return reclaimed


_LIVE_REPROJECT_DIR_NAME = "live_reproject"


def reproject_store_token(value: str) -> str:
    """Folder token for a project's Live Reproject store (mirrors texture_reprojection)."""
    result = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or ""))
    return result or "item"


def prune_live_reproject_stores(output_root: str | Path | None, *, keep_tokens: Iterable[str]) -> int:
    """Delete ``<root>/.fyr_cache/<token>/live_reproject`` for projects that no longer exist.

    A store is written when Live Reproject is switched on and deliberately kept
    after switch-off so Restore Textures still works. Nothing removed it once the
    project itself was renamed or deleted, so every retired project left its
    reference pixels (tens of MB per 2K output) behind for good. Returns bytes
    reclaimed.
    """
    if keep_scratch_enabled() or not output_root:
        return 0
    cache_root_dir = Path(output_root) / ".fyr_cache"
    try:
        if not cache_root_dir.is_dir():
            return 0
        project_dirs = list(cache_root_dir.iterdir())
    except Exception:
        return 0
    keep = {str(token) for token in keep_tokens if token}
    reclaimed = 0
    for project_dir in project_dirs:
        if project_dir.name in keep:
            continue
        store = project_dir / _LIVE_REPROJECT_DIR_NAME
        try:
            if store.is_dir() and not store.is_symlink():
                size = _directory_size_bytes(store)
                _remove_tree(store)
                if not store.exists():
                    reclaimed += size
            # Drop the project folder once nothing lives in it (the retired
            # baseline sweep leaves empty shells behind as well).
            if project_dir.is_dir() and not project_dir.is_symlink() and not any(project_dir.iterdir()):
                project_dir.rmdir()
        except Exception:
            continue
    return reclaimed


def _launch_retired_baseline_sweep(output_root: Path) -> None:
    """Once per output root per session, off the UI thread: the tree can be tens of GB."""
    key = _norm_path(output_root)
    if key in _RETIRED_BASELINE_ROOTS_SWEPT:
        return
    _RETIRED_BASELINE_ROOTS_SWEPT.add(key)
    try:
        if not (output_root / ".fyr_cache").is_dir():
            return
    except Exception:
        return
    try:
        threading.Thread(
            target=thread_guard.guarded(lambda: remove_retired_reprojection_baselines(output_root), "baseline-sweep"),
            name="fyr-baker-retired-baseline-sweep",
            daemon=True,
        ).start()
    except Exception:
        try:
            remove_retired_reprojection_baselines(output_root)
        except Exception:
            pass


def prune_job_workspaces(output_root: str | Path | None, *, keep_paths: Iterable[str | Path | None]) -> None:
    if keep_scratch_enabled() or not output_root:
        return
    _launch_retired_baseline_sweep(Path(output_root))
    # Workspaces from builds before the FyrBaker rename lived under
    # ".master_baker"; new workspaces are only ever created under ".fyr_baker",
    # so the whole legacy tree is scratch and goes away wholesale.
    legacy_root = Path(output_root) / ".master_baker"
    if legacy_root.exists():
        _remove_tree(legacy_root)
    jobs_root = Path(output_root) / ".fyr_baker" / "jobs"
    if not jobs_root.exists():
        return
    keep = {_norm_path(path) for path in keep_paths if path}
    for child in list(jobs_root.iterdir()):
        if not child.is_dir():
            continue
        if _norm_path(child) in keep:
            continue
        if _job_workspace_looks_live(child):
            # The keep set is read from `last_bake_workspace_path`, which a bake
            # launch stamps AFTER this export has already built its list. A prepare
            # that started before the launch therefore prunes with a stale keep set
            # and can delete the workspace of the bake that just started. Observed
            # 2026-08-31 as a hard bake failure: the backend lost `progress.json`
            # mid-shading and aborted a group whose GPU work had already finished.
            #
            # A running job rewrites progress.json continuously, so a recent mtime
            # is direct evidence the job is alive -- and it needs no knowledge of
            # who holds which pointer.
            continue
        _remove_tree(child)


_GLOBAL_LOG_NAMES = ("worker_diagnostics.log", "worker_diagnostics.log.1")


def clear_job_workspace_logs(output_root: str | Path | None) -> int:
    """Delete the bake logs under ``<root>/.fyr_baker/jobs/*/logs``; live jobs are kept.

    Returns files removed. Job files, progress and outputs are untouched: only the
    per-run backend logs go, which is what "Clear Logs" promises.
    """
    if not output_root:
        return 0
    jobs_root = Path(output_root) / ".fyr_baker" / "jobs"
    try:
        if not jobs_root.is_dir():
            return 0
        workspaces = [child for child in jobs_root.iterdir() if child.is_dir()]
    except Exception:
        return 0
    removed = 0
    for workspace in workspaces:
        if _job_workspace_looks_live(workspace):
            continue
        logs_dir = workspace / "logs"
        try:
            candidates = list(logs_dir.glob("*.log")) if logs_dir.is_dir() else []
        except Exception:
            continue
        for path in candidates:
            try:
                path.unlink()
                removed += 1
            except Exception:
                continue
    return removed


def clear_global_diagnostic_logs() -> int:
    """Delete the worker diagnostics log (and its rotation) and the GPU fallback log.

    A log the running worker still holds open cannot be unlinked on Windows; that
    one is skipped rather than reported as an error. Returns files removed.
    """
    root = cache_root()
    candidates = [root / "logs" / name for name in _GLOBAL_LOG_NAMES]
    candidates.append(root.parent / "gpu_fallback.log")
    removed = 0
    for path in candidates:
        try:
            if path.is_file():
                path.unlink()
                removed += 1
        except Exception:
            continue
    return removed


_RUNTIME_SESSION_OWNER_FILE = "owner.pid"


def mark_runtime_session_owner(session_dir: str | Path) -> None:
    """Stamp a runtime session directory with the pid of the Blender that owns it."""
    try:
        Path(session_dir).mkdir(parents=True, exist_ok=True)
        (Path(session_dir) / _RUNTIME_SESSION_OWNER_FILE).write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                still_active = 259
                if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return int(exit_code.value) == still_active
                return True
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return True


def session_owner_alive(session_dir: str | Path) -> bool:
    """Is the Blender that stamped this session directory still running?

    Public because every per-session cache root under the shared cache has to ask
    it before deleting a sibling's directory, not just the runtime high-mesh one.
    """
    return _runtime_session_owner_alive(Path(session_dir))


def _runtime_session_owner_alive(session_dir: Path) -> bool:
    owner_file = session_dir / _RUNTIME_SESSION_OWNER_FILE
    try:
        pid = int(owner_file.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        # Sessions from builds without an owner stamp: treat as dead once they
        # are older than an hour, live otherwise (a crash-recovery reopen).
        try:
            return (time.time() - session_dir.stat().st_mtime) < 3600.0
        except Exception:
            return False
    return _process_is_alive(pid)


def prune_high_mesh_runtime_sessions(*, current_session_token: str = "") -> None:
    """Remove runtime high-mesh sessions whose owning Blender is gone.

    Two Blenders share this cache root (a headless QA run beside the live
    session, two artists' files open at once). Removing every session but our
    own deleted the OTHER process's runtime exports from under its bake
    ("Failed to open cache file ... runtime/<session>/..."), and unregister
    removed even the live ones. Only sessions with no living owner go.
    """
    if keep_scratch_enabled():
        return
    runtime_root = cache_root() / "blender_high_exports" / "runtime"
    if not runtime_root.exists():
        return
    current = str(current_session_token or "").strip()
    for child in list(runtime_root.iterdir()):
        if not child.is_dir():
            continue
        if current and child.name == current:
            continue
        if _runtime_session_owner_alive(child):
            continue
        _remove_tree(child)


def remove_high_mesh_runtime_session(session_token: str) -> None:
    """Remove exactly this process's runtime session (addon disable)."""
    if keep_scratch_enabled():
        return
    token = str(session_token or "").strip()
    if not token:
        return
    _remove_tree(cache_root() / "blender_high_exports" / "runtime" / token)


def clear_known_cache_entries() -> None:
    root = cache_root()
    for name in _BACKEND_CACHE_DIR_NAMES:
        _remove_tree(root / name)
    try:
        for child in list(root.iterdir()):
            if _is_orphan_aside_dir(child):
                _remove_tree(child)
    except Exception:
        pass
    try:
        for child in root.glob("pso_cache_*"):
            if child.is_dir():
                _remove_tree(child)
            else:
                _remove_file(child)
    except Exception:
        pass


def temp_sweep_disabled() -> bool:
    value = str(os.environ.get(constants.DISABLE_TEMP_SWEEP_ENV_VAR, "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def temp_sweep_age_seconds() -> float:
    raw_value = str(os.environ.get(constants.TEMP_SWEEP_AGE_HOURS_ENV_VAR, "") or "").strip()
    hours = constants.TEMP_SWEEP_AGE_HOURS_DEFAULT
    if raw_value:
        try:
            parsed = float(raw_value)
            if parsed >= 0.0:
                hours = parsed
        except Exception:
            hours = constants.TEMP_SWEEP_AGE_HOURS_DEFAULT
    return float(hours) * 3600.0


def system_temp_root() -> Path:
    return Path(tempfile.gettempdir())


def _name_is_owned_temp_entry(name: str) -> bool:
    lowered = str(name or "").strip().lower()
    if not lowered:
        return False
    return any(lowered.startswith(prefix) for prefix in _OWNED_TEMP_NAME_PREFIXES)


def _entry_size_bytes(path: Path) -> int:
    try:
        if path.is_dir() and not path.is_symlink():
            return _directory_size_bytes(path)
        return int(path.lstat().st_size)
    except Exception:
        return 0


def _directory_size_bytes(path: Path) -> int:
    total = 0
    try:
        for child in path.rglob("*"):
            try:
                if child.is_file() and not child.is_symlink():
                    total += int(child.lstat().st_size)
            except Exception:
                continue
    except Exception:
        pass
    return total


def _protected_temp_paths() -> set[str]:
    """Paths under the system temp dir that must never be swept even when their
    mtime looks stale — the active cache root / scratch root when a build routes
    them into %TEMP% (no LOCALAPPDATA, or FYR_BAKER_DISABLE_PERSISTENT_CACHE)."""
    protected: set[str] = set()
    for candidate in (cache_root(), scratch_root(), system_temp_root() / "fyr_baker_blender_high_exports"):
        try:
            protected.add(os.path.normcase(str(candidate.resolve(strict=False))))
        except Exception:
            protected.add(os.path.normcase(str(candidate)))
    return protected


def sweep_stale_system_temp(
    *,
    temp_root: str | Path | None = None,
    age_seconds: float | None = None,
    now: float | None = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Best-effort removal of stale FyrBaker-owned entries from the system temp dir.

    Only removes entries whose name starts with an owned prefix (see
    _OWNED_TEMP_NAME_PREFIXES) and whose modification time is older than the age
    threshold. Locked/in-use entries are skipped silently. Returns
    (removed_entry_count, reclaimed_bytes). Never touches non-owned entries or the
    active cache/scratch roots."""
    if temp_sweep_disabled() or keep_scratch_enabled():
        return (0, 0)
    root = Path(temp_root) if temp_root is not None else system_temp_root()
    try:
        if not root.exists():
            return (0, 0)
    except Exception:
        return (0, 0)
    threshold = float(age_seconds) if age_seconds is not None else temp_sweep_age_seconds()
    reference_time = float(now) if now is not None else time.time()
    protected = _protected_temp_paths()

    removed_count = 0
    reclaimed_bytes = 0
    try:
        children = list(root.iterdir())
    except Exception:
        return (0, 0)

    for child in children:
        try:
            if not _name_is_owned_temp_entry(child.name):
                continue
            try:
                child_key = os.path.normcase(str(child.resolve(strict=False)))
            except Exception:
                child_key = os.path.normcase(str(child))
            if child_key in protected:
                continue
            try:
                mtime = child.lstat().st_mtime
            except Exception:
                continue
            if threshold > 0.0 and (reference_time - mtime) < threshold:
                continue
            size = _entry_size_bytes(child)
            if dry_run:
                removed_count += 1
                reclaimed_bytes += size
                continue
            removed = False
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
                removed = not child.exists()
            else:
                try:
                    child.unlink(missing_ok=True)
                    removed = True
                except Exception:
                    removed = False
            if removed:
                removed_count += 1
                reclaimed_bytes += size
        except Exception:
            continue
    return (removed_count, reclaimed_bytes)


def _is_orphan_aside_dir(path: Path) -> bool:
    # Case-insensitive: a 518 MB projection_hits_ASIDE sat outside every sweep
    # (2026-09-06) because the check only knew the lower-case spelling.
    name = str(path.name or "").casefold()
    return path.is_dir() and not path.is_symlink() and name.endswith("_aside")


def remove_orphan_cache_asides() -> int:
    """Delete leftover ``<family>_aside`` trees that nothing reads.

    Cache-format migrations sometimes renamed a live family to ``*_aside``
    instead of deleting it. Those directories are outside the budgeted name
    list, so they can double on-disk use while the UI still reports the limit.
    Returns bytes reclaimed.
    """
    if keep_scratch_enabled():
        return 0
    root = cache_root()
    try:
        if not root.exists():
            return 0
        children = list(root.iterdir())
    except Exception:
        return 0
    reclaimed = 0
    for child in children:
        try:
            if not _is_orphan_aside_dir(child):
                continue
            size = _directory_size_bytes(child)
            _remove_tree(child)
            if not child.exists():
                reclaimed += size
        except Exception:
            continue
    return reclaimed


def remove_stale_cache_tmp_files() -> int:
    """Drop crash leftovers from atomic persist writes (``*.tmp`` older than 1 hour)."""
    if keep_scratch_enabled():
        return 0
    root = cache_root()
    reclaimed = 0
    now = time.time()
    min_age = 3600.0
    for name in _BUDGETED_BACKEND_CACHE_DIR_NAMES:
        directory = root / name
        try:
            if not directory.exists():
                continue
        except Exception:
            continue
        try:
            children = list(directory.rglob("*"))
        except Exception:
            continue
        for path in children:
            try:
                if not path.is_file() or path.is_symlink():
                    continue
                if path.suffix.lower() != ".tmp":
                    continue
                age = now - float(path.stat().st_mtime)
                if age < min_age:
                    continue
                size = int(path.lstat().st_size)
                _remove_file(path)
                if not path.exists():
                    reclaimed += size
            except Exception:
                continue
    return reclaimed


def remove_stale_pso_backups() -> int:
    """Drop leftover PSO library files that the current backend will never load.

    Filenames are keyed by adapter LUID + driver + build stamp, so a driver
    bump or a rebuilt backend leaves orphans. Keep the newest ``.bin`` (likely
    the live cache) and delete every older ``.bin`` plus all ``.bak`` copies.
    """
    if keep_scratch_enabled():
        return 0
    root = cache_root()
    try:
        if not root.exists():
            return 0
        files = [path for path in root.glob("pso_cache_*") if path.is_file() and not path.is_symlink()]
    except Exception:
        return 0
    bins = [path for path in files if path.suffix.lower() == ".bin"]
    backups = [path for path in files if path.suffix.lower() == ".bak"]
    keep: Path | None = None
    if bins:
        try:
            keep = max(bins, key=lambda path: path.stat().st_mtime)
        except Exception:
            keep = bins[0]
    reclaimed = 0
    for path in backups + [path for path in bins if keep is None or path != keep]:
        try:
            size = int(path.lstat().st_size)
            _remove_file(path)
            if not path.exists():
                reclaimed += size
        except Exception:
            continue
    return reclaimed


def cleanup_update_staging(keep_archive: str | Path | None = None) -> None:
    """Remove a leftover in-addon update download from the system temp dir.

    ``keep_archive`` is the archive a failed install deliberately left behind
    (updater.record_install_failure): the recovery dialog names it and offers
    "Show Downloaded File", so the staging tree stays while that file is in it.
    """
    if keep_scratch_enabled():
        return
    staging = system_temp_root() / "fyr_baker_update"
    if keep_archive:
        try:
            archive = Path(keep_archive)
            if archive.is_file() and os.path.normcase(str(archive.resolve())).startswith(
                os.path.normcase(str(staging.resolve()))
            ):
                return
        except Exception:
            pass
    _remove_tree(staging)


def cache_root_usage_bytes() -> int:
    """Bytes occupied by the same families governed by the one cache budget."""
    root = cache_root()
    try:
        if not root.exists():
            return 0
        children = list(root.iterdir())
    except Exception:
        return 0
    total = 0
    for child in children:
        try:
            # Every child counts. Restricting this to _BUDGETED_BACKEND_CACHE_DIR_NAMES
            # meant an unlisted family or a loose file in the root was invisible to the
            # readout AND to budget enforcement -- hang_traceback.log alone reached
            # 91.5 MB unnoticed (RC sweep 2026-08-29, findings 10 and 11).
            total += _directory_size_bytes(child) if child.is_dir() else int(child.lstat().st_size)
        except Exception:
            continue
    return total


def _cache_entry_groups(directory: Path) -> list[dict]:
    groups: dict[str, dict] = {}
    try:
        if not directory.exists():
            return []
        children = list(directory.rglob("*"))
    except Exception:
        return []
    for path in children:
        try:
            if not path.is_file() or path.is_symlink():
                continue
            stat = path.lstat()
        except Exception:
            continue
        group_key = os.path.normcase(str(path.parent)) + "|" + path.stem
        group = groups.setdefault(
            group_key,
            {"paths": [], "bytes": 0, "mtime": 0.0},
        )
        group["paths"].append(path)
        group["bytes"] += int(stat.st_size)
        if stat.st_mtime > group["mtime"]:
            group["mtime"] = float(stat.st_mtime)
    return list(groups.values())


_FAMILY_ENTRY_BUDGET_ENV_VAR = "FYR_BAKER_FAMILY_ENTRY_BUDGET_GB"
_DEFAULT_FAMILY_ENTRY_BUDGET_BYTES = 8 * 1024 * 1024 * 1024


def _family_entry_budget_bytes() -> int:
    """Byte size under which a family's entry-count cap does not evict at all.

    Mirrors persistent_family_entry_budget_bytes() in backend_mesh_cache.cpp, same env
    var and default. A count cap on a per-group resource evicts the working set of any
    job with more groups than the cap: the 66-group Ubrion demo bakes 9 texture-set
    batches, so the 3-entry high_scenes cap deleted 6 scenes at every bake start (it
    then ran from prepare_bake_job; see launch_idle_cache_reclaim) and the bake rebuilt
    them, +10 s and +4 GB peak working set. The overall persistent-cache byte budget
    still bounds the disk. 0 restores the pure count cap.
    """
    raw = os.environ.get(_FAMILY_ENTRY_BUDGET_ENV_VAR, "").strip()
    if raw:
        try:
            gb = float(raw)
        except ValueError:
            return _DEFAULT_FAMILY_ENTRY_BUDGET_BYTES
        return 0 if gb <= 0.0 else int(gb * 1024 * 1024 * 1024)
    return _DEFAULT_FAMILY_ENTRY_BUDGET_BYTES


def enforce_family_entry_caps(
    *,
    keep_paths: Iterable[str | Path | None] = (),
) -> int:
    """Keep only the newest N groups per family, matching the backend worker caps.

    Clean Now and addon register used to enforce the 12 GB byte budget without
    these caps, so a full ``high_scenes`` tree could survive as long as asides
    were deleted first. Like the backend, a family over its count cap is left alone
    while its total size is within _family_entry_budget_bytes(). Returns bytes reclaimed.
    """
    if keep_scratch_enabled():
        return 0
    keep = {_norm_path(path) for path in keep_paths if path}
    root = cache_root()
    budget_bytes = _family_entry_budget_bytes()
    reclaimed = 0
    for name, max_entries in _FAMILY_ENTRY_CAPS.items():
        if max_entries <= 0:
            continue
        groups = _cache_entry_groups(root / name)
        if len(groups) <= max_entries:
            continue
        if budget_bytes and sum(int(group["bytes"]) for group in groups) <= budget_bytes:
            continue
        groups.sort(key=lambda item: item["mtime"], reverse=True)
        for group in groups[max_entries:]:
            if any(_norm_path(path) in keep for path in group["paths"]):
                continue
            removed = True
            for path in group["paths"]:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    removed = False
            if removed:
                reclaimed += int(group["bytes"])
    return reclaimed


_reclaim_lock = threading.Lock()
_last_idle_reclaim_monotonic = 0.0


def reclaim_idle_cache(*, force: bool = False, enforce_family_caps: bool = True) -> int:
    """Best-effort aside / PSO / family-cap reclaim without waiting for the worker.

    enforce_family_caps=False skips enforce_family_entry_caps(); see
    launch_idle_cache_reclaim() for why the bake-start path must.
    """
    if keep_scratch_enabled():
        return 0
    global _last_idle_reclaim_monotonic
    with _reclaim_lock:
        now = time.monotonic()
        if not force and _last_idle_reclaim_monotonic and (now - _last_idle_reclaim_monotonic) < 300.0:
            return 0
        _last_idle_reclaim_monotonic = now
    reclaimed = remove_orphan_cache_asides()
    reclaimed += remove_stale_pso_backups()
    reclaimed += remove_stale_cache_tmp_files()
    if enforce_family_caps:
        reclaimed += enforce_family_entry_caps()
    return reclaimed


def launch_idle_cache_reclaim(*, force: bool = False) -> None:
    """Run aside / PSO / stale-tmp reclaim off the UI thread. Multi-GB trees can take seconds.

    The caller is prepare_bake_job, i.e. a job is about to run, so the per-family entry
    caps are NOT enforced here. They run without keep paths (the job's scene / BLAS /
    hit keys are derived by the backend and are not known to the add-on at this point),
    and a newest-N cap over a family past its byte gate deletes the job's own entries:
    a 4+-batch job with high_scenes over 8 GB lost every scene past the newest 3 on a
    background thread while the bake was being prepared, and the backend rebuilt them.
    The caps stay enforced where no job is racing them or where the job's key is known:
    addon startup reclaim, Clean Now, and the backend worker (at start and after each
    persist, keeping the entry it just wrote), so the family bound on disk is unchanged.
    """
    if keep_scratch_enabled():
        return
    try:
        thread = threading.Thread(
            target=thread_guard.guarded(lambda: reclaim_idle_cache(force=force, enforce_family_caps=False), "cache-reclaim"),
            name="fyr-baker-cache-reclaim",
            daemon=True,
        )
        thread.start()
    except Exception:
        try:
            reclaim_idle_cache(force=force, enforce_family_caps=False)
        except Exception:
            pass


def _startup_cleanup_worker(keep_update_archive: str = "") -> None:
    """Filesystem-only startup reclaim. Must never touch bpy — this runs off the UI thread."""
    try:
        clear_owned_scratch()
    except Exception:
        pass
    try:
        cleanup_update_staging(keep_archive=keep_update_archive or None)
    except Exception:
        pass
    if not temp_sweep_disabled() and not keep_scratch_enabled():
        try:
            sweep_stale_system_temp()
        except Exception:
            pass
    try:
        reclaim_idle_cache(force=True)
    except Exception:
        pass


def enforce_persistent_cache_budget(
    budget_gb: int | float,
    *,
    keep_paths: Iterable[str | Path | None] = (),
    budget_bytes: int | None = None,
) -> int:
    """Evict oldest backend cache entries until the budgeted families fit the byte
    budget. Mirrors prune_persistent_backend_cache() in backend_mesh_cache.cpp:
    files are grouped by (parent, stem) so a revision file and its data file are
    evicted together, and the oldest group (by newest mtime within the group) goes
    first. Returns bytes reclaimed. Used by the Clean Now operator so enforcement
    happens immediately without waiting for the next worker start.

    budget_bytes overrides the GB budget (test hook — the GB API cannot express a
    sub-GiB budget)."""
    if keep_scratch_enabled():
        return 0
    reclaimed_asides = remove_orphan_cache_asides()
    reclaimed_asides += remove_stale_pso_backups()
    reclaimed_asides += remove_stale_cache_tmp_files()
    if budget_bytes is None:
        try:
            budget_bytes = max(1, int(budget_gb)) * 1024 * 1024 * 1024
        except Exception:
            return reclaimed_asides
    else:
        budget_bytes = int(budget_bytes)
    root = cache_root()
    keep = {_norm_path(path) for path in keep_paths if path}
    pins_path = root / "active_project_pins.txt"
    try:
        keep.update(
            _norm_path(line.strip())
            for line in pins_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except Exception:
        pass
    reclaimed_asides += enforce_family_entry_caps(keep_paths=keep)

    groups: dict[str, dict] = {}
    total_bytes = 0
    exempt_bytes = 0
    for name in _BUDGETED_BACKEND_CACHE_DIR_NAMES:
        directory = root / name
        try:
            if not directory.exists():
                continue
        except Exception:
            continue
        for path in directory.rglob("*"):
            try:
                if not path.is_file() or path.is_symlink():
                    continue
                stat = path.lstat()
            except Exception:
                continue
            group_key = os.path.normcase(str(path.parent)) + "|" + path.stem
            priority = (
                3 if name == "canonical_geometry"
                else 2 if name == "dxr_blas"
                else 1 if name == "high_scenes"
                else 0
            )
            group = groups.setdefault(
                group_key,
                {"paths": [], "bytes": 0, "mtime": 0.0, "priority": priority},
            )
            group["paths"].append(path)
            group["bytes"] += int(stat.st_size)
            if stat.st_mtime > group["mtime"]:
                group["mtime"] = float(stat.st_mtime)
            if name == "blender_high_exports":
                exempt_bytes += int(stat.st_size)
            else:
                total_bytes += int(stat.st_size)

    # blender_high_exports is the live session's own working set (runtime high exports,
    # low-mesh payloads); it is pruned by its owner (dead-owner sessions, sibling payload
    # sessions, the alias-manifest LRU), never by the byte budget. Mirrors the worker.
    #
    # Exempt bytes still consume the budget first, so the other families are trimmed to
    # whatever is left: exactly the minimum that brings the whole cache within budget.
    # When the exports alone already exceed the budget, no amount of eviction can get
    # there, and chasing it deleted EVERY unpinned entry (13 GB of exports against a
    # 12 GB budget left the next bake fully cold while the cache stayed over budget).
    # In that case the evictable families are held to the budget on their own instead,
    # so disk stays bounded (exports + budget) without wiping the warm cache.
    if exempt_bytes < budget_bytes:
        evictable_budget_bytes = budget_bytes - exempt_bytes
    else:
        evictable_budget_bytes = budget_bytes
    if total_bytes <= evictable_budget_bytes:
        return reclaimed_asides

    # Least recently used first; family priority only breaks ties. Mirrors the worker's
    # prune: ranking priority first kept days-old BLAS blobs over the high scene a bake
    # had just written, so every cold worker rebuilt it.
    ordered = sorted(
        groups.values(),
        key=lambda item: (item["mtime"], item["priority"], item["bytes"]),
    )
    reclaimed = 0
    exports_root = _norm_path(root / "blender_high_exports")
    for group in ordered:
        if total_bytes <= evictable_budget_bytes:
            break
        if any(_norm_path(path) in keep for path in group["paths"]):
            continue
        if any(_norm_path(path).startswith(exports_root) for path in group["paths"]):
            continue
        for path in group["paths"]:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                continue
        total_bytes -= int(group["bytes"])
        reclaimed += int(group["bytes"])
    return reclaimed + reclaimed_asides


def register() -> None:
    """Start cache reclaim in the background.

    Do not delete trees on this thread. Addon enable/disable runs inside
    Blender's UI loop; a multi-GB scratch walk here keeps WM_main blocked after
    operator/panel RNA is already gone. Blender 5.1 then crashes drawing leftover
    string widgets (``RNA_property_subtype`` / ``button_text_password_hide``).
    """
    global _TEMP_SWEEP_STARTED
    _TEMP_SWEEP_STARTED = True
    # Resolved here, on the main thread, because the state path comes from bpy.
    keep_update_archive = ""
    try:
        from . import updater_state

        keep_update_archive = str(updater_state.install_failure().get("archive") or "")
    except Exception:
        keep_update_archive = ""
    try:
        thread = threading.Thread(
            target=_startup_cleanup_worker,
            args=(keep_update_archive,),
            name="fyr-baker-startup-cleanup",
            daemon=True,
        )
        thread.start()
    except Exception:
        _startup_cleanup_worker(keep_update_archive)


def unregister() -> None:
    global _TEMP_SWEEP_STARTED
    _TEMP_SWEEP_STARTED = False
