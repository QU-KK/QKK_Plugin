from __future__ import annotations

import atexit
import copy
import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
import queue
import subprocess
import threading
from datetime import datetime, timezone
import time
import traceback

import bpy

from . import (
    backend_install,
    constants,
    mesh_transport,
    preferences,
    properties,
    protocol,
    runtime_backend_logs,
    runtime_bake_worker,
    runtime_debug_event_log,
    runtime_debug_overlay_worker,
    runtime_output_images,
    runtime_support_bundle,
    storage_cleanup,
    update_policy,
)


@dataclass(slots=True)
class BackgroundBakeSnapshot:
    job_id: str
    job_path: str
    progress_path: str
    running: bool
    cancel_requested: bool = False
    # Monotonic timestamp of the cancel request, so the panel can say how long the
    # cancel has been pending. A cancel is honoured at the worker's next checkpoint,
    # and on a slow machine that wait is long enough to read as "Stop did nothing".
    cancel_requested_at: float = 0.0
    pause_requested: bool = False
    # Wall-clock monotonic timestamp captured when the bake was launched. Lets
    # the UI compute total elapsed time once the bake finishes. 0.0 if unknown.
    start_time: float = 0.0


@dataclass(slots=True)
class BackgroundBakePollResult:
    snapshot: BackgroundBakeSnapshot
    progress: protocol.BakeProgress
    finished: bool


@dataclass(slots=True)
class _ActiveDebugOverlayState:
    result_key: tuple
    job_path: Path
    result_path: Path
    backend_log_path: Path
    backend_path: Path
    backend_version: str
    refresh_reason: str = ""
    requested_at_monotonic: float = 0.0
    launched_at_monotonic: float = 0.0
    elapsed_ms: float = 0.0
    input_signature: tuple | None = None
    group_name: str = ""
    transport_retry_count: int = 0


@dataclass(slots=True)
class _DebugWorkerState:
    process: subprocess.Popen
    backend_path: Path
    backend_version: str
    stderr_path: Path
    stdin_handle: object
    stdout_handle: object
    stderr_handle: object
    response_queue: queue.Queue
    response_thread: threading.Thread


@dataclass(slots=True)
class _BakeWorkerState:
    process: subprocess.Popen
    backend_path: Path
    backend_version: str
    backend_mtime_ns: int
    cpu_threads: int
    stderr_path: Path
    stdin_handle: object
    stdout_handle: object
    stderr_handle: object
    response_queue: queue.Queue
    response_thread: threading.Thread
    # Digest of the backend env the worker was spawned with; a warm worker is
    # recycled when the preference-driven env changes.
    env_signature: str = ""


@dataclass(slots=True)
class _ActiveBakeState:
    job_id: str
    job_path: Path
    progress_path: Path
    backend_log_path: Path
    backend_path: Path
    backend_version: str
    process: subprocess.Popen
    stdout_path: Path
    stderr_path: Path
    stdout_handle: object
    stderr_handle: object
    # Byte offset into the shared resident-worker stderr when this job started;
    # failure reports quote only the text written after it.
    stderr_offset: int = 0
    cancel_requested: bool = False
    cancel_requested_at: float = 0.0
    # Progress-movement tracking while a cancel is pending: the worker is only
    # force-killed when it stops ADVANCING, not merely for being mid-span (the
    # GPU execute path is cancellation-blind for a whole batch, so a healthy
    # worker may legitimately need >15s to reach its next checkpoint; killing
    # it also forces a cold worker on the next bake).
    cancel_progress_signature: tuple | None = None
    cancel_progress_advanced_at: float = 0.0
    # Progress-movement tracking for a NORMALLY RUNNING bake (no cancel pending).
    # A worker that deadlocks mid-bake leaves Blender waiting forever with an idle
    # CPU and GPU and nothing on screen but a frozen percentage; these let the poll
    # notice the freeze, say so, and eventually give the user their session back.
    run_progress_signature: tuple | None = None
    run_progress_advanced_at: float = 0.0
    run_progress_updates: int = 0
    stall_reported: bool = False
    stall_force_failed: bool = False
    pause_requested: bool = False
    selected_map_types: tuple[str, ...] = ()
    last_progress_log_signature: tuple | None = None
    last_progress: protocol.BakeProgress | None = None
    progress_event_handle: object = None
    transport_retry_count: int = 0
    # Transient-GPU-failure retries already spent on this bake (fresh worker + smaller batches).
    gpu_retry_count: int = 0
    # time.monotonic() captured when the bake was launched. Used to compute
    # the human-readable total bake duration shown to the user when the bake
    # finishes.
    start_time: float = 0.0


_ACTIVE_BAKE: _ActiveBakeState | None = None
_ACTIVE_DEBUG: _ActiveDebugOverlayState | None = None
_BAKE_WORKER: _BakeWorkerState | None = None
_DEBUG_WORKER: _DebugWorkerState | None = None
_POLL_UPDATE_CALLBACK = None
# Optional callable(). When set, invoked by the bake timer whenever no job is running
# and the dirty tracker has pending changes whose debounce has elapsed.
_DIRTY_REBAKE_CALLBACK = None
_DEBUG_RESULTS: dict[tuple, protocol.DebugOverlayResult] = {}
_DEBUG_RESULT_INPUT_SIGNATURES: dict[tuple, tuple] = {}
_DEBUG_REFRESH_REQUESTED = False
_DEBUG_REFRESH_DUE_AT = 0.0
_DEBUG_REFRESH_REASON = ""
_DEBUG_REFRESH_REQUESTED_AT = 0.0
_DEBUG_REFRESH_VIEW: protocol.DebugViewConfig | None = None
_DEBUG_TIMER_REGISTERED = False
_LAST_DEBUG_REQUEST_LOG_SIGNATURE: tuple | None = None
_LAST_DEBUG_REQUEST_LOG_AT = 0.0
_BACKEND_VERSION_CACHE: dict[str, str] = {}
# Capabilities probe results, keyed by (normcased path, mtime_ns, size). Spawning the
# backend executable costs ~0.9s -- it links OIDN/TBB/OpenVDB/Embree/D3D12, so process
# start is dominated by DLL loading -- and ensure_backend_compatible runs twice per bake,
# which put ~1.8s of pure overhead on every bake. The answer can only change when the
# executable itself changes, so key the cache on its identity.
_BACKEND_CAPABILITIES_CACHE: dict[tuple[str, int, int], "BackendProbeVerdict"] = {}
# The in-memory cache above is per-Blender-session, so a fresh Blender paid the
# ~0.85s `capabilities --json` probe (it creates a D3D12 device) on every start.
# A positive answer depends only on the executable's identity, so it is also
# persisted next to the other backend caches and reloaded lazily on the next
# session. A negative GPU verdict is NOT persisted: it depends on the adapter and
# driver, so a new session always re-probes, and within a session the bake-start
# gate re-probes it once it is older than _NEGATIVE_BACKEND_VERDICT_TTL_S.
_BACKEND_CAPABILITIES_DISK_CACHE: dict[str, "BackendProbeVerdict"] | None = None
# Version 3 (2026-10-18): verdicts carry the adapter list the Bake GPU picker shows, so
# version 2 answers (no list) are probed once more.
_BACKEND_CAPABILITIES_DISK_VERSION = 3
# A negative GPU verdict is frequently transient: the driver is still coming up after
# boot, an earlier GPU error removed/reset the device (TDR), or the discrete GPU briefly
# failed device creation so the backend fell through to the integrated one (the backend
# picks the adapter with the most dedicated VRAM that can create a device). Holding
# such a verdict for the whole session routed every later bake to Cycles, or failed it,
# until Blender was restarted (tester report, RTX 4090 + AMD iGPU). The bake-start gate
# therefore forgets a negative verdict once it is older than this TTL and re-probes.
# 60 s recovers on the next bake after a transient while a machine that genuinely lacks
# DXR does not pay the ~0.9 s probe on every bake of a quick iteration loop. Positive
# verdicts never expire, and draw code never re-probes.
_NEGATIVE_BACKEND_VERDICT_TTL_S = 60.0
# time.monotonic() at which each NEGATIVE in-memory verdict was stored, keyed like
# _BACKEND_CAPABILITIES_CACHE. Empty on a healthy machine, so the gate costs nothing.
_BACKEND_NEGATIVE_VERDICT_AT: dict[tuple, float] = {}
#: A/B hatch for the DXR gate: set to "1" to let the addon launch the backend on a
#: GPU without DirectX Raytracing (the software-BVH compute route). Never set in
#: production; the route is unmeasured, which is why the gate exists.
_ALLOW_NO_DXR_ENV_VAR = "FYR_BAKER_ALLOW_NO_DXR"
_BACKEND_CAPABILITIES_DISK_MAX_ENTRIES = 16
# Control subcommands (--version, capabilities) answer in milliseconds when the
# backend is healthy. A hung one must fail the probe, not wedge Blender forever.
_BACKEND_CONTROL_SUBPROCESS_TIMEOUT_S = 30.0
_BACKEND_LOG_VIEWERS: dict[str, subprocess.Popen] = {}
_MANAGED_OUTPUT_PATH_KEY = "_master_baker_output_path"
_MANAGED_OUTPUT_MTIME_KEY = "_master_baker_output_mtime_ns"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def backend_executable_name() -> str:
    return "fyr_baker_backend.exe" if os.name == "nt" else "fyr_baker_backend"


def backend_platform_tag() -> str:
    system = platform.system().strip().lower()
    if system == "darwin":
        os_tag = "macos"
    elif system == "windows":
        os_tag = "windows"
    elif system == "linux":
        os_tag = "linux"
    else:
        os_tag = system or "unknown"

    machine = platform.machine().strip().lower()
    architecture_map = {
        "amd64": "x64",
        "x86_64": "x64",
        "x64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86": "x86",
        "i386": "x86",
        "i686": "x86",
    }
    architecture = architecture_map.get(machine, machine or "unknown")
    return f"{os_tag}-{architecture}"


def _bundled_backend_candidates() -> list[Path]:
    bin_root = Path(__file__).resolve().parent / "bin"
    executable_name = backend_executable_name()
    return [
        bin_root / backend_platform_tag() / executable_name,
        bin_root / executable_name,
    ]


def bundled_backend_path() -> Path:
    return _bundled_backend_candidates()[0]


def _build_backend_candidates(build_root: Path) -> list[Path]:
    executable_name = backend_executable_name()
    return [
        build_root / "bin" / executable_name,
        build_root / executable_name,
        build_root / "Release" / executable_name,
        build_root / "Debug" / executable_name,
        build_root / "Release" / "bin" / executable_name,
        build_root / "Debug" / "bin" / executable_name,
    ]


def _repo_build_backend_paths() -> list[Path]:
    return _build_backend_candidates(repo_root() / "backend" / "build")


def _profiling_backend_paths() -> list[Path]:
    return _build_backend_candidates(repo_root() / "backend" / "build_profiling")


def installed_backend_paths() -> list[Path]:
    """Candidate executables from a standalone backend installation."""
    return backend_install.payload_paths(backend_executable_name())


def resolve_installed_backend() -> Path | None:
    """Newest existing executable from a standalone installation, if any."""
    return _resolve_newest_backend_candidate(installed_backend_paths())


def backend_is_bundled() -> bool:
    """True when this build carries its own backend next to the add-on.

    False on the Superhive channel, where the archive has no native payload and
    the backend comes from the separate installer.
    """
    return any(candidate.exists() for candidate in _bundled_backend_candidates())


def candidate_backend_paths() -> list[Path]:
    build_candidates = _repo_build_backend_paths()
    bundled_candidates = _bundled_backend_candidates()
    repo_bin_root = (repo_root() / "addon" / "bin").resolve(strict=False)
    external_bundled: list[Path] = []
    repo_bundled: list[Path] = []
    for bundled in bundled_candidates:
        try:
            bundled_root = bundled.resolve(strict=False).parent
        except Exception:
            bundled_root = bundled.parent
        if bundled_root == repo_bin_root or bundled_root.parent == repo_bin_root:
            repo_bundled.append(bundled)
        else:
            external_bundled.append(bundled)
    return [*external_bundled, *build_candidates, *repo_bundled]


def _existing_backend_candidates(paths: list[Path] | None = None) -> list[tuple[int, Path]]:
    candidates: list[tuple[int, Path]] = []
    seen: set[str] = set()
    source_paths = candidate_backend_paths() if paths is None else paths
    for index, candidate in enumerate(source_paths):
        try:
            resolved_key = os.path.normcase(str(candidate.resolve(strict=False)))
        except Exception:
            resolved_key = os.path.normcase(str(candidate))
        if resolved_key in seen or not candidate.exists():
            continue
        seen.add(resolved_key)
        candidates.append((index, candidate))
    return candidates


def _backend_candidate_sort_key(index: int, path: Path) -> tuple[int, int]:
    try:
        mtime_ns = int(path.stat().st_mtime_ns)
    except Exception:
        mtime_ns = -1
    return (mtime_ns, -int(index))


def _path_mtime_ns(path: str | Path | None) -> int:
    raw_path = str(path or "").strip()
    if not raw_path:
        return 0
    try:
        return int(Path(raw_path).stat().st_mtime_ns)
    except Exception:
        return 0


def _resolve_newest_backend_candidate(paths: list[Path] | None = None) -> Path | None:
    existing_candidates = _existing_backend_candidates(paths)
    if not existing_candidates:
        return None
    _index, resolved = max(
        existing_candidates,
        key=lambda item: _backend_candidate_sort_key(item[0], item[1]),
    )
    return resolved


def _ensure_executable(path: Path) -> Path:
    if os.name == "nt":
        return path
    if not os.access(path, os.X_OK):
        try:
            current = path.stat().st_mode
            path.chmod(current | 0o111)
        except Exception:
            pass
    return path


def backend_missing_message() -> str:
    """Why there is no backend, phrased for the build the user is running.

    A Superhive customer has no bundled backend by design and needs the
    installer; telling them to "build the backend" would be nonsense. A direct
    customer with no backend has a damaged install, which is a different problem
    with a different fix.
    """
    if os.name != "nt":
        return (
            "The Fyr backend runs on Windows only. Baking will use Cycles on this platform."
        )
    if backend_is_bundled():
        return (
            "fyr_baker_backend was not found. Build the backend or set an override in "
            "Add-on Preferences."
        )
    if update_policy.updater_available():
        # Only the direct (fyrplugins.com) archive carries the updater, and that
        # archive bundles the backend. Reaching here means the exe was removed
        # after install, usually by antivirus quarantine or a partial extract.
        # There is no installer for this customer to run.
        return (
            "The Fyr Baker backend file is missing from the add-on folder "
            "(bin/windows-x64/fyr_baker_backend.exe). Antivirus software may have "
            "quarantined it. Restore it from quarantine, or reinstall the downloaded ZIP "
            "with Edit > Preferences > Get Extensions > Install from Disk, then restart "
            f"Blender. Get help at {constants.BACKEND_INSTALLER_HELP_URL}."
        )
    return (
        "The Fyr Baker backend is not installed. Run the Fyr Baker Backend installer "
        "that came with your purchase, then restart Blender. You can also point at an "
        "existing backend with Backend Executable in Add-on Preferences, or get help at "
        f"{constants.BACKEND_INSTALLER_HELP_URL}."
    )


def resolve_backend_executable() -> Path:
    addon_preferences = preferences.get_preferences()
    if addon_preferences is not None:
        raw_override = (addon_preferences.backend_executable or "").strip()
        if raw_override:
            override = Path(raw_override)
            if override.exists():
                return _ensure_executable(override)
            raise FileNotFoundError(f"Configured backend executable was not found: {override}")

    if preferences.developer_mode_enabled(addon_preferences):
        # Pick the newest executable across BOTH dev candidate roots
        # (build_profiling/ and build/). The previous behaviour always preferred
        # build_profiling/ first, which silently let stale binaries win when only
        # one of the two trees had been rebuilt.
        dev_candidates = [
            *_profiling_backend_paths(),
            *_repo_build_backend_paths(),
        ]
        dev_backend = _resolve_newest_backend_candidate(dev_candidates)
        if dev_backend is not None:
            return _ensure_executable(dev_backend)

    resolved = _resolve_newest_backend_candidate()
    if resolved is not None:
        return _ensure_executable(resolved)

    # Only now: a build that bundles a backend must always run ITS backend, which
    # is version-matched to the add-on. A standalone installation is what the
    # Superhive channel relies on, and for a bundled build it is a leftover from
    # some other install whose protocol version nobody has checked.
    installed = resolve_installed_backend()
    if installed is not None:
        return _ensure_executable(installed)

    raise FileNotFoundError(backend_missing_message())


def _backend_run_log_path(progress_path: str | Path) -> Path:
    return Path(progress_path).parent / "logs" / "backend_run.log"


def _support_bundle_path(progress_path: str | Path) -> Path:
    return Path(progress_path).parent / "support_bundle.zip"


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _format_backend_log(
    *,
    title: str,
    backend_path: str | Path | None,
    command: list[str],
    cwd: str | Path,
    returncode: int,
    stdout: str,
    stderr: str,
    backend_version: str = "",
    note: str = "",
) -> str:
    return runtime_backend_logs.format_backend_log(
        title=title,
        backend_path=backend_path,
        command=command,
        cwd=cwd,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        backend_version=backend_version,
        note=note,
        protocol_version=constants.PROTOCOL_VERSION,
        list2cmdline_fn=subprocess.list2cmdline,
    )


def _write_backend_log(
    log_path: str | Path,
    *,
    title: str,
    backend_path: str | Path | None,
    command: list[str],
    cwd: str | Path,
    returncode: int,
    stdout: str,
    stderr: str,
    backend_version: str = "",
    note: str = "",
) -> Path:
    return runtime_backend_logs.write_backend_log(
        log_path,
        title=title,
        backend_path=backend_path,
        command=command,
        cwd=cwd,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        backend_version=backend_version,
        note=note,
        format_backend_log_fn=_format_backend_log,
        write_text_atomic_fn=_write_text_atomic,
    )


def _append_live_log(path: str | Path, text: str) -> None:
    runtime_backend_logs.append_live_log(path, text)


def _live_log_time_text(moment: datetime | None = None) -> str:
    return runtime_backend_logs.live_log_time_text(moment)


def _short_log_path(path: str | Path | None, *, parts: int = 2) -> str:
    return runtime_backend_logs.short_log_path(path, parts=parts)


def _append_live_log_block(path: str | Path, title: str, details: list[str] | tuple[str, ...] | None = None) -> None:
    runtime_backend_logs.append_live_log_block(path, title, details)


def _copyable_log_window_enabled() -> bool:
    return runtime_backend_logs.copyable_log_window_enabled(get_preferences_fn=preferences.get_preferences)


def _powershell_executable() -> str:
    return runtime_backend_logs.powershell_executable(os_environ=os.environ)


def _powershell_single_quote(value: str | Path) -> str:
    return runtime_backend_logs.powershell_single_quote(value)


def _log_viewer_state_path(log_path: str | Path) -> Path:
    return runtime_backend_logs.log_viewer_state_path(log_path)


def _process_is_alive(pid: int) -> bool:
    return runtime_backend_logs.process_is_alive(pid, os_name=os.name, os_module=os)


def _read_log_viewer_state(log_path: str | Path) -> dict[str, object]:
    return runtime_backend_logs.read_log_viewer_state(log_path, log_viewer_state_path_fn=_log_viewer_state_path)


def _write_log_viewer_state(log_path: str | Path, *, pid: int, host_pid: int, title: str) -> None:
    runtime_backend_logs.write_log_viewer_state(
        log_path,
        pid=pid,
        host_pid=host_pid,
        title=title,
        write_text_atomic_fn=_write_text_atomic,
        log_viewer_state_path_fn=_log_viewer_state_path,
    )


def _remove_log_viewer_state(log_path: str | Path) -> None:
    runtime_backend_logs.remove_log_viewer_state(log_path, log_viewer_state_path_fn=_log_viewer_state_path)


def _existing_log_viewer_running(log_path: str | Path) -> bool:
    return runtime_backend_logs.existing_log_viewer_running(
        log_path,
        viewers=_BACKEND_LOG_VIEWERS,
        os_module=os,
        read_log_viewer_state_fn=_read_log_viewer_state,
        process_is_alive_fn=_process_is_alive,
        remove_log_viewer_state_fn=_remove_log_viewer_state,
    )


def open_backend_log_window(log_path: str | Path, *, title: str = "Fyr Baker Backend Log", follow: bool = True) -> bool:
    return runtime_backend_logs.open_backend_log_window(
        log_path,
        title=title,
        follow=follow,
        viewers=_BACKEND_LOG_VIEWERS,
        os_module=os,
        subprocess_module=subprocess,
        powershell_executable_fn=_powershell_executable,
        powershell_single_quote_fn=_powershell_single_quote,
        log_viewer_state_path_fn=_log_viewer_state_path,
        existing_log_viewer_running_fn=_existing_log_viewer_running,
        write_log_viewer_state_fn=_write_log_viewer_state,
    )


def maybe_open_backend_log_window(log_path: str | Path, *, title: str, follow: bool = True) -> bool:
    return runtime_backend_logs.maybe_open_backend_log_window(
        log_path,
        title=title,
        follow=follow,
        copyable_log_window_enabled_fn=_copyable_log_window_enabled,
        open_backend_log_window_fn=open_backend_log_window,
    )


def project_backend_log_path(project, *, prefer_live: bool = True, scene=None) -> Path | None:
    scene_settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    debug_path = _debug_overlay_log_path(scene=scene, project=project, prefer_live=prefer_live)
    if debug_path is not None and (debug_path.exists() or debug_overlay_enabled(scene_settings) or _ACTIVE_DEBUG is not None):
        return debug_path

    raw_workspace_path = str(getattr(project, "last_workspace_path", "") or "").strip()
    if not raw_workspace_path:
        return None
    progress_path = Path(raw_workspace_path).expanduser() / "progress.json"
    live_path = _background_bake_live_log_path(progress_path)
    run_path = _backend_run_log_path(progress_path)
    if prefer_live and live_path.exists():
        return live_path
    if run_path.exists():
        return run_path
    return live_path if prefer_live else run_path


def _background_bake_live_log_path(progress_path: str | Path) -> Path:
    return Path(progress_path).parent / "logs" / "backend_live.log"


def _fnv1a64_hex(text: str) -> str:
    hash_value = 14695981039346656037
    for byte in str(text or "").encode("utf-8"):
        hash_value ^= int(byte)
        hash_value = (hash_value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{hash_value:016x}"


def _bake_cancel_event_name(progress_path: str | Path) -> str:
    return f"Local\\MasterBakerBakeCancel_{_fnv1a64_hex(str(Path(progress_path)))}"


def _bake_pause_event_name(progress_path: str | Path) -> str:
    return f"Local\\MasterBakerBakePause_{_fnv1a64_hex(str(Path(progress_path)))}"


def _open_bake_cancel_event_handle(progress_path: str | Path):
    if os.name != "nt":
        return None
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateEventW.restype = ctypes.c_void_p
        kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
        return kernel32.CreateEventW(None, 1, 0, _bake_cancel_event_name(progress_path))
    except Exception:
        return None


def _open_bake_pause_event_handle(progress_path: str | Path):
    if os.name != "nt":
        return None
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateEventW.restype = ctypes.c_void_p
        kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
        return kernel32.CreateEventW(None, 1, 0, _bake_pause_event_name(progress_path))
    except Exception:
        return None


def _reset_bake_cancel_event(progress_path: str | Path) -> bool:
    handle = _open_bake_cancel_event_handle(progress_path)
    if not handle:
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.ResetEvent.argtypes = [ctypes.c_void_p]
        kernel32.ResetEvent.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        return bool(kernel32.ResetEvent(handle))
    finally:
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass


def _signal_bake_cancel_event(progress_path: str | Path) -> bool:
    handle = _open_bake_cancel_event_handle(progress_path)
    if not handle:
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetEvent.argtypes = [ctypes.c_void_p]
        kernel32.SetEvent.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        return bool(kernel32.SetEvent(handle))
    finally:
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass


def _reset_bake_pause_event(progress_path: str | Path) -> bool:
    handle = _open_bake_pause_event_handle(progress_path)
    if not handle:
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.ResetEvent.argtypes = [ctypes.c_void_p]
        kernel32.ResetEvent.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        return bool(kernel32.ResetEvent(handle))
    finally:
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass


def _signal_bake_pause_event(progress_path: str | Path) -> bool:
    handle = _open_bake_pause_event_handle(progress_path)
    if not handle:
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetEvent.argtypes = [ctypes.c_void_p]
        kernel32.SetEvent.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        return bool(kernel32.SetEvent(handle))
    finally:
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass


def _bake_progress_event_name(progress_path: str | Path) -> str:
    """Derive the Win32 event name the backend signals after each write_progress_json call.
    Uses the same FNV-1a hash and path normalization (str(Path(...)) → backslashes on Windows)
    as the cancel/pause event names so backend and addon agree on the event name."""
    return f"Local\\MasterBakerProgress_{_fnv1a64_hex(str(Path(progress_path)))}"


def _create_bake_progress_event(progress_path: str | Path):
    """Create the manual-reset, initially-unsignaled Win32 event that the backend will signal
    after every progress.json write. Returns the HANDLE (opaque int) or None on non-Windows."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateEventW.restype = ctypes.c_void_p
        kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
        # bManualReset=1 so the addon controls when to reset; bInitialState=0 (not signaled)
        return kernel32.CreateEventW(None, 1, 0, _bake_progress_event_name(progress_path))
    except Exception:
        return None


def _check_and_reset_bake_progress_event(handle) -> bool:
    """Non-blocking check: returns True if the backend has signaled a new progress write.
    Resets the event so the next call returns False until the backend signals again."""
    if not handle:
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.ResetEvent.argtypes = [ctypes.c_void_p]
        kernel32.ResetEvent.restype = ctypes.c_int
        WAIT_OBJECT_0 = 0x00000000
        if kernel32.WaitForSingleObject(handle, 0) == WAIT_OBJECT_0:
            kernel32.ResetEvent(handle)
            return True
        return False
    except Exception:
        return False


def _close_bake_progress_event(handle) -> None:
    """Close the Win32 event handle created by _create_bake_progress_event."""
    if not handle:
        return
    try:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(handle))
    except Exception:
        pass


def _bake_cancel_request_path(progress_path: str | Path) -> Path:
    return Path(progress_path).parent / "cancel.request"


def _bake_pause_request_path(progress_path: str | Path) -> Path:
    return Path(progress_path).parent / "pause.request"


def _clear_bake_cancel_request(progress_path: str | Path) -> Path:
    cancel_path = _bake_cancel_request_path(progress_path)
    try:
        cancel_path.unlink()
    except FileNotFoundError:
        pass
    _reset_bake_cancel_event(progress_path)
    return cancel_path


def _clear_bake_pause_request(progress_path: str | Path) -> Path:
    pause_path = _bake_pause_request_path(progress_path)
    try:
        pause_path.unlink()
    except FileNotFoundError:
        pass
    _reset_bake_pause_event(progress_path)
    return pause_path


def _write_bake_cancel_request(progress_path: str | Path, *, job_id: str = "") -> Path:
    cancel_path = _bake_cancel_request_path(progress_path)
    payload = {
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "job_id": str(job_id or ""),
    }
    _write_text_atomic(cancel_path, json.dumps(payload, indent=2, sort_keys=True))
    _signal_bake_cancel_event(progress_path)
    return cancel_path


def _write_bake_pause_request(progress_path: str | Path, *, job_id: str = "") -> Path:
    pause_path = _bake_pause_request_path(progress_path)
    payload = {
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "job_id": str(job_id or ""),
    }
    _write_text_atomic(pause_path, json.dumps(payload, indent=2, sort_keys=True))
    _signal_bake_pause_event(progress_path)
    return pause_path


def _resident_bake_worker_stderr_path() -> Path:
    return storage_cleanup.ensure_scratch_subdir("backend_worker") / "bake_worker_stderr.log"


def _debug_overlay_live_log_path(result_path: str | Path) -> Path:
    return Path(result_path).parent / "logs" / "debug_worker_live.log"


def _debug_overlay_result_path(project, group) -> Path | None:
    if project is None or group is None:
        return None
    from . import workspace

    debug_root = storage_cleanup.ensure_scratch_subdir("debug_overlay") / workspace.slugify_name(getattr(project, "name", ""))
    return debug_root / workspace.slugify_name(getattr(group, "name", "")) / "debug_overlay.json"


def _resolve_debug_overlay_project_group(scene=None, project=None, group=None):
    if project is not None and group is not None:
        return project, group
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    if scene is None:
        return project, group
    from . import properties

    if project is None:
        project = properties.peek_active_project(scene)
    if group is None and project is not None:
        group = properties.peek_active_group(project)
    return project, group


def _debug_overlay_log_path(*, scene=None, project=None, group=None, prefer_live: bool = True) -> Path | None:
    if _ACTIVE_DEBUG is not None:
        active_key = _ACTIVE_DEBUG.result_key
        if project is None or str(getattr(project, "name", "") or "") == active_key[1]:
            if group is None or str(getattr(group, "name", "") or "") == active_key[2]:
                live_path = _debug_overlay_live_log_path(_ACTIVE_DEBUG.result_path)
                run_path = _debug_overlay_run_log_path(_ACTIVE_DEBUG.result_path)
                if prefer_live and live_path.exists():
                    return live_path
                if run_path.exists():
                    return run_path
                return live_path if prefer_live else run_path

    project, group = _resolve_debug_overlay_project_group(scene=scene, project=project, group=group)
    result_path = _debug_overlay_result_path(project, group)
    if result_path is None:
        return None
    live_path = _debug_overlay_live_log_path(result_path)
    run_path = _debug_overlay_run_log_path(result_path)
    if prefer_live and live_path.exists():
        return live_path
    if run_path.exists():
        return run_path
    return live_path if prefer_live else run_path


_format_debug_log_value = runtime_debug_event_log.format_debug_log_value
_debug_overlay_scope_label = runtime_debug_event_log.debug_overlay_scope_label
_format_duration_ms = runtime_debug_event_log.format_duration_ms


def _format_debug_overlay_event_block(event: str, *, project=None, group=None, fields: dict[str, object]) -> str:
    return runtime_debug_event_log.format_debug_overlay_event_block(
        event,
        project=project,
        group=group,
        fields=fields,
        live_log_time_text_fn=_live_log_time_text,
        short_log_path_fn=_short_log_path,
    )


def _append_debug_overlay_event(
    event: str,
    *,
    context=None,
    scene=None,
    project=None,
    group=None,
    result_path: str | Path | None = None,
    **fields,
) -> Path | None:
    resolved_scene = scene if scene is not None else getattr(context, "scene", None)
    if (
        result_path is None
        and _DEBUG_WORKER is None
        and _ACTIVE_DEBUG is None
        and not _DEBUG_REFRESH_REQUESTED
        and not debug_overlay_enabled(getattr(resolved_scene, "fyr_baker_settings", None))
    ):
        return None

    target_path = None
    if result_path is not None:
        target_path = _debug_overlay_live_log_path(result_path)
    elif _DEBUG_WORKER is not None and getattr(_DEBUG_WORKER, "stderr_path", None) is not None:
        target_path = _DEBUG_WORKER.stderr_path
    else:
        target_path = _debug_overlay_log_path(scene=resolved_scene, project=project, group=group, prefer_live=True)
    if target_path is None:
        return None

    _append_live_log(
        target_path,
        _format_debug_overlay_event_block(
            event,
            project=project,
            group=group,
            fields=fields,
        ),
    )
    return target_path


def _support_bundle_manifest(project, *, job_path: Path, progress_path: Path, backend_log_path: Path) -> dict:
    return runtime_support_bundle.support_bundle_manifest(
        project,
        job_path=job_path,
        progress_path=progress_path,
        backend_log_path=backend_log_path,
        constants=constants,
        repo_root_fn=repo_root,
        bpy_module=bpy,
    )


def write_support_bundle(
    project,
    destination_path: str | Path | None = None,
    extra_artifacts=None,
) -> Path:
    artifacts = list(extra_artifacts or ())
    try:
        from . import hang_watchdog

        artifacts.extend(
            runtime_support_bundle.global_log_artifacts(
                cache_root=Path(preferences.persistent_cache_root()),
                hang_log_path=hang_watchdog.log_path(),
            )
        )
    except Exception:
        pass
    return runtime_support_bundle.write_support_bundle(
        project,
        destination_path=destination_path,
        backend_run_log_path_fn=_backend_run_log_path,
        support_bundle_path_fn=_support_bundle_path,
        support_bundle_manifest_fn=_support_bundle_manifest,
        extra_artifacts=artifacts,
    )


def query_backend_version(backend_path: str | Path, log_path: str | Path | None = None) -> str:
    backend_path = Path(backend_path)
    try:
        completed = subprocess.run(
            [str(backend_path), "--version"],
            capture_output=True,
            text=True,
            timeout=_BACKEND_CONTROL_SUBPROCESS_TIMEOUT_S,
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
            **runtime_bake_worker.spawn_feedback_suppression_kwargs(subprocess),
        )
    except subprocess.TimeoutExpired as exc:
        # A backend that never answers --version must surface as an ordinary
        # incompatibility (the caller's RuntimeError path), never as a hang.
        note = (
            "fyr_baker_backend did not answer --version within "
            f"{_BACKEND_CONTROL_SUBPROCESS_TIMEOUT_S:.0f}s"
        )
        if log_path is not None:
            _write_backend_log(
                log_path,
                title="Backend version check timed out",
                backend_path=backend_path,
                command=["--version"],
                cwd=str(backend_path.parent),
                returncode=-1,
                stdout="",
                stderr="",
                backend_version="",
                note=note,
            )
        raise RuntimeError(note) from exc
    version = (completed.stdout or completed.stderr or "").strip()
    if log_path is not None:
        _write_backend_log(
            log_path,
            title="Backend version check",
            backend_path=backend_path,
            command=["--version"],
            cwd=str(backend_path.parent),
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            backend_version=version,
        )
    if completed.returncode != 0 or not version:
        raise RuntimeError("fyr_baker_backend did not report a compatible version")
    return version


@dataclass(frozen=True)
class BackendProbeVerdict:
    """What ``fyr_baker_backend capabilities --json`` said about this machine.

    ``gpu_projection_available`` is False only when the backend positively reported
    that it cannot bake on the active adapter: no D3D12 device at all, or a device
    without hardware raytracing (``raytracing_hardware_supported`` false). A payload
    that omits those keys (older backend, truncated output) leaves it True, so the
    gate can only ever refuse on evidence, never on silence. ``raytracing_supported``
    and the self-test flags are deliberately NOT consulted: on a healthy RTX box the
    probe answers with the self-test still pending.
    """

    indexed_geometry: bool = False
    gpu_projection_available: bool = True
    gpu_unavailable_reason: str = ""
    adapter_name: str = ""
    #: Every hardware adapter the probe enumerated: (name, dedicated VRAM MB, DXR tier).
    adapters: tuple = ()

    def to_json(self) -> dict:
        return {
            "indexed_geometry": bool(self.indexed_geometry),
            "gpu_projection_available": bool(self.gpu_projection_available),
            "gpu_unavailable_reason": str(self.gpu_unavailable_reason or ""),
            "adapter_name": str(self.adapter_name or ""),
            "adapters": [list(entry) for entry in self.adapters],
        }

    @classmethod
    def from_json(cls, payload) -> "BackendProbeVerdict | None":
        if not isinstance(payload, dict):
            return None
        indexed = payload.get("indexed_geometry")
        gpu_ok = payload.get("gpu_projection_available")
        if not isinstance(indexed, bool) or not isinstance(gpu_ok, bool):
            return None
        return cls(
            indexed_geometry=indexed,
            gpu_projection_available=gpu_ok,
            gpu_unavailable_reason=str(payload.get("gpu_unavailable_reason") or ""),
            adapter_name=str(payload.get("adapter_name") or ""),
            adapters=_adapter_entries(payload.get("adapters")),
        )


def _adapter_entries(raw) -> tuple:
    """(name, VRAM MB, DXR tier) per adapter, from the capabilities JSON or a stored verdict."""
    entries = []
    for item in raw if isinstance(raw, (list, tuple)) else ():
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            vram = int(item.get("dedicated_video_memory_bytes") or 0) // (1024 * 1024)
            tier = str(item.get("raytracing_tier") or "")
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            name, vram, tier = str(item[0] or "").strip(), int(item[1] or 0), str(item[2] or "")
        else:
            continue
        if name:
            entries.append((name, vram, tier))
    return tuple(entries)


def _probe_verdict_from_capabilities(payload) -> BackendProbeVerdict:
    """Turn the backend's capabilities JSON into a verdict. Missing keys never refuse."""
    if not isinstance(payload, dict):
        return BackendProbeVerdict()
    indexed = bool(payload.get("indexed_geometry_shm_v1", False))
    adapter = str(payload.get("adapter_name") or "").strip()
    available = payload.get("available")
    hardware_rt = payload.get("raytracing_hardware_supported")
    gpu_ok = True
    reason = ""
    if available is False:
        gpu_ok = False
        detail = str(payload.get("unavailable_reason") or "").strip()
        reason = "No DirectX 12 device"
        if detail:
            reason += f" ({detail})"
    elif hardware_rt is False:
        gpu_ok = False
        reason = f"No DirectX Raytracing on {adapter or 'this GPU'}"
    return BackendProbeVerdict(
        indexed_geometry=indexed,
        gpu_projection_available=gpu_ok,
        gpu_unavailable_reason=reason,
        adapter_name=adapter,
        adapters=_adapter_entries(payload.get("adapters")),
    )


def _no_dxr_override_enabled() -> bool:
    value = str(os.environ.get(_ALLOW_NO_DXR_ENV_VAR, "") or "").strip().lower()
    return value in ("1", "true", "yes", "on")


def _gpu_unavailable_message(verdict: BackendProbeVerdict) -> str:
    """Artist-facing refusal text: what Fyr saw, and what to do about it.

    Customer text: no em dashes. Names the adapter whenever the backend reported one.
    """
    reason = str(verdict.gpu_unavailable_reason or "").strip() or "GPU unavailable"
    adapter = str(verdict.adapter_name or "").strip()
    if adapter and adapter not in reason:
        reason = f"{reason} on {adapter}"
    return (
        f"Fyr cannot use the GPU right now: {reason}. "
        "Fyr checks the GPU again on later bakes; if this keeps happening, update the GPU "
        "driver and set Blender to High performance in Windows Graphics settings."
    )


def _remember_backend_verdict(
    capabilities_key: tuple,
    verdict: BackendProbeVerdict,
    now: float | None = None,
) -> None:
    """Store a verdict in the session cache, stamping negatives for the TTL re-probe."""
    _BACKEND_CAPABILITIES_CACHE[capabilities_key] = verdict
    if verdict.gpu_projection_available:
        _BACKEND_NEGATIVE_VERDICT_AT.pop(capabilities_key, None)
    else:
        _BACKEND_NEGATIVE_VERDICT_AT[capabilities_key] = (
            time.monotonic() if now is None else float(now)
        )


def expire_stale_negative_backend_verdicts(now: float | None = None, *, force: bool = False) -> int:
    """Forget negative GPU verdicts older than the TTL; return how many were dropped.

    Called by the bake-start gate right before its blocking probe, so the next
    ``ensure_backend_compatible`` re-runs ``capabilities --json`` instead of
    replaying a transient failure for the rest of the session. ``force`` drops
    every negative verdict regardless of age (a worker just proved its GPU init
    was transient-class and was retired). Never probes by itself, never touches
    positive verdicts or the disk cache, and on a healthy machine (no negative
    verdicts) returns immediately. Not for draw code.
    """
    if not _BACKEND_NEGATIVE_VERDICT_AT:
        return 0
    current = time.monotonic() if now is None else float(now)
    expired = [
        key
        for key, stored_at in list(_BACKEND_NEGATIVE_VERDICT_AT.items())
        if force or (current - stored_at) >= _NEGATIVE_BACKEND_VERDICT_TTL_S
    ]
    for key in expired:
        _BACKEND_NEGATIVE_VERDICT_AT.pop(key, None)
        cached = _BACKEND_CAPABILITIES_CACHE.get(key)
        if cached is not None and not cached.gpu_projection_available:
            _BACKEND_CAPABILITIES_CACHE.pop(key, None)
    return len(expired)


def last_backend_probe_verdict() -> BackendProbeVerdict | None:
    """The most recent capabilities verdict this session, for UI text. Never probes."""
    if not _BACKEND_CAPABILITIES_CACHE:
        return None
    try:
        return next(reversed(_BACKEND_CAPABILITIES_CACHE.values()))
    except (StopIteration, RuntimeError):
        # The bake gate (or the background probe thread) mutated the cache mid-read.
        return None


def _backend_capabilities_cache_path() -> Path:
    return preferences.persistent_cache_root() / "backend_capabilities.json"


def _backend_capabilities_disk_key(cache_key: tuple) -> str:
    key = f"{cache_key[0]}|{cache_key[1]}|{cache_key[2]}"
    # A GPU chosen in Preferences (FYR_BAKER_ADAPTER) is its own answer; Automatic keeps
    # the key every existing entry was stored under.
    return key + (f"|adapter={cache_key[3]}" if len(cache_key) > 3 and cache_key[3] else "")


def _selected_gpu_adapter() -> str:
    try:
        return str(getattr(preferences.get_preferences(), "gpu_adapter", "") or "").strip()
    except Exception:
        return ""


def _load_backend_capabilities_disk_cache() -> dict[str, BackendProbeVerdict]:
    """Lazily read the persisted capabilities answers. Tolerates any corruption."""
    global _BACKEND_CAPABILITIES_DISK_CACHE
    if _BACKEND_CAPABILITIES_DISK_CACHE is not None:
        return _BACKEND_CAPABILITIES_DISK_CACHE
    entries: dict[str, BackendProbeVerdict] = {}
    try:
        payload = json.loads(_backend_capabilities_cache_path().read_text(encoding="utf-8"))
        if (
            isinstance(payload, dict)
            and int(payload.get("version", 0)) == _BACKEND_CAPABILITIES_DISK_VERSION
        ):
            raw_entries = payload.get("entries")
            if isinstance(raw_entries, dict):
                for key, value in raw_entries.items():
                    verdict = BackendProbeVerdict.from_json(value)
                    if isinstance(key, str) and verdict is not None:
                        entries[key] = verdict
    except Exception:
        # Missing, unreadable, truncated or foreign-version file: start empty and
        # let the next successful probe rewrite it.
        entries = {}
    _BACKEND_CAPABILITIES_DISK_CACHE = entries
    return entries


def _store_backend_capabilities_disk_cache(disk_key: str, verdict: BackendProbeVerdict) -> None:
    entries = _load_backend_capabilities_disk_cache()
    if entries.get(disk_key) == verdict:
        return
    entries.pop(disk_key, None)
    entries[disk_key] = verdict
    # Every rebuild of the backend mints a new key; keep the file bounded by
    # dropping the oldest insertions rather than letting it grow forever.
    while len(entries) > _BACKEND_CAPABILITIES_DISK_MAX_ENTRIES:
        entries.pop(next(iter(entries)))
    destination = _backend_capabilities_cache_path()
    temp_path = destination.with_name(f"{destination.name}.{os.getpid()}.tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            json.dumps(
                {
                    "version": _BACKEND_CAPABILITIES_DISK_VERSION,
                    "entries": {key: value.to_json() for key, value in entries.items()},
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(temp_path, destination)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _apply_probe_verdict(
    verdict: BackendProbeVerdict,
    backend_path: Path,
    backend_version: str,
    log_path: str | Path | None,
) -> None:
    """Publish the verdict to the indexed-geometry switch, then refuse if the GPU cannot bake."""
    from . import indexed_geometry

    indexed_geometry.set_backend_compatible(
        bool(verdict.indexed_geometry and verdict.gpu_projection_available)
    )
    if verdict.gpu_projection_available or _no_dxr_override_enabled():
        return
    message = _gpu_unavailable_message(verdict)
    if log_path is not None:
        _write_backend_log(
            log_path,
            title="Backend GPU unavailable",
            backend_path=backend_path,
            command=["capabilities", "--json"],
            cwd=str(backend_path.parent),
            returncode=0,
            stdout="",
            stderr="",
            backend_version=backend_version,
            note=message,
        )
    raise RuntimeError(message)


def ensure_backend_compatible(backend_path: str | Path, log_path: str | Path | None = None) -> str:
    backend_path = Path(backend_path)
    # Keyed like the capabilities cache: a backend rebuilt in place (new mtime /
    # size) must be re-queried, or a bumped PROTOCOL_VERSION slipped past the
    # mismatch guard and an incompatible job was fed to the new exe.
    try:
        stat = backend_path.stat()
        cache_key = (os.path.normcase(str(backend_path)), int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        cache_key = (os.path.normcase(str(backend_path)), 0, 0)
    backend_version = _BACKEND_VERSION_CACHE.get(cache_key, "")
    if not backend_version:
        if log_path is None:
            backend_version = query_backend_version(backend_path)
        else:
            backend_version = query_backend_version(backend_path, log_path=log_path)
        _BACKEND_VERSION_CACHE[cache_key] = backend_version
    if backend_version != constants.PROTOCOL_VERSION:
        if log_path is not None:
            _write_backend_log(
                log_path,
                title="Backend version mismatch",
                backend_path=backend_path,
                command=["--version"],
                cwd=str(backend_path.parent),
                returncode=0,
                stdout=f"{backend_version}\n",
                stderr="",
                backend_version=backend_version,
                note=f"Expected addon protocol {constants.PROTOCOL_VERSION}",
            )
        raise RuntimeError(
            f"fyr_baker_backend version {backend_version} does not match addon protocol {constants.PROTOCOL_VERSION}"
        )
    capabilities_key: tuple | None = None
    selected_adapter = _selected_gpu_adapter()
    try:
        backend_stat = backend_path.stat()
        capabilities_key = (cache_key, int(backend_stat.st_mtime_ns), int(backend_stat.st_size))
        if selected_adapter:
            capabilities_key = capabilities_key + (selected_adapter,)
    except OSError:
        capabilities_key = None
    if capabilities_key is not None and capabilities_key in _BACKEND_CAPABILITIES_CACHE:
        _apply_probe_verdict(
            _BACKEND_CAPABILITIES_CACHE[capabilities_key], backend_path, backend_version, log_path
        )
        return backend_version
    disk_key = (
        _backend_capabilities_disk_key(capabilities_key)
        if capabilities_key is not None
        else ""
    )
    if disk_key:
        cached = _load_backend_capabilities_disk_cache().get(disk_key)
        if cached is not None:
            _remember_backend_verdict(capabilities_key, cached)
            _apply_probe_verdict(cached, backend_path, backend_version, log_path)
            return backend_version
    verdict = BackendProbeVerdict()
    probe_succeeded = False
    try:
        probe_env = None
        if selected_adapter:
            # The probe must answer for the GPU the worker will use.
            probe_env = os.environ.copy()
            probe_env["FYR_BAKER_ADAPTER"] = selected_adapter
        completed = subprocess.run(
            [str(backend_path), "capabilities", "--json"],
            capture_output=True,
            text=True,
            env=probe_env,
            timeout=_BACKEND_CONTROL_SUBPROCESS_TIMEOUT_S,
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
            **runtime_bake_worker.spawn_feedback_suppression_kwargs(subprocess),
        )
        payload = json.loads(completed.stdout) if completed.returncode == 0 else {}
        verdict = _probe_verdict_from_capabilities(payload)
        probe_succeeded = completed.returncode == 0
    except subprocess.TimeoutExpired:
        # Treat a wedged probe as "no indexed geometry" for this session, but do
        # not persist that verdict: the next session gets a fresh chance.
        verdict = BackendProbeVerdict()
    except Exception:
        verdict = BackendProbeVerdict()
    if capabilities_key is not None:
        # Negatives are stamped so the bake-start gate re-probes them after
        # _NEGATIVE_BACKEND_VERDICT_TTL_S; they are never written to disk.
        _remember_backend_verdict(capabilities_key, verdict)
        if probe_succeeded and disk_key and verdict.gpu_projection_available:
            _store_backend_capabilities_disk_cache(disk_key, verdict)
    _apply_probe_verdict(verdict, backend_path, backend_version, log_path)
    return backend_version


def _background_polling_supported() -> bool:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    return timers is not None and hasattr(timers, "register")


def background_polling_supported() -> bool:
    return _background_polling_supported()


def debug_overlay_enabled(settings) -> bool:
    if settings is None:
        return False
    from . import properties

    overlay_state = properties.overlay_settings_state(settings)
    return bool(getattr(overlay_state, "show_ray_miss_debug", False))


def _active_debug_result_key(scene, project, group) -> tuple:
    return (
        int(scene.as_pointer()) if scene is not None and hasattr(scene, "as_pointer") else 0,
        str(getattr(project, "name", "") or ""),
        str(getattr(group, "name", "") or ""),
    )


def peek_debug_overlay_result(scene, project, group) -> protocol.DebugOverlayResult | None:
    return _DEBUG_RESULTS.get(_active_debug_result_key(scene, project, group))


def clear_debug_overlay_results() -> None:
    _DEBUG_RESULTS.clear()
    _DEBUG_RESULT_INPUT_SIGNATURES.clear()


def debug_overlay_result_matches_input_signature(scene, project, group, input_signature: tuple | None) -> bool:
    if input_signature is None:
        return False
    result_key = _active_debug_result_key(scene, project, group)
    return _DEBUG_RESULT_INPUT_SIGNATURES.get(result_key) == input_signature


def invalidate_debug_overlay_export_cache(*, context=None, scene=None, project=None, group=None, reason: str = "") -> None:
    from . import export

    _append_debug_overlay_event(
        "invalidate-export",
        context=context,
        scene=scene,
        project=project,
        group=group,
        reason=reason or "unspecified",
    )
    export.invalidate_debug_overlay_export_cache()


def invalidate_debug_overlay_cache(*, context=None, scene=None, project=None, group=None, reason: str = "") -> None:
    clear_debug_overlay_results()
    _append_debug_overlay_event(
        "invalidate-results",
        context=context,
        scene=scene,
        project=project,
        group=group,
        reason=reason or "unspecified",
    )
    invalidate_debug_overlay_export_cache(context=context, scene=scene, project=project, group=group, reason=reason or "unspecified")


def debug_overlay_refresh_pending(scene=None, project=None, group=None) -> bool:
    if _ACTIVE_DEBUG is None and not _DEBUG_REFRESH_REQUESTED:
        return False
    if scene is None or project is None or group is None:
        return bool(_ACTIVE_DEBUG is not None or _DEBUG_REFRESH_REQUESTED)
    result_key = _active_debug_result_key(scene, project, group)
    if _ACTIVE_DEBUG is not None:
        return _ACTIVE_DEBUG.result_key == result_key
    return bool(_DEBUG_REFRESH_REQUESTED)


def _debug_overlay_refresh_state_from_globals() -> runtime_debug_overlay_worker.DebugOverlayRefreshState:
    return runtime_debug_overlay_worker.DebugOverlayRefreshState(
        requested=bool(_DEBUG_REFRESH_REQUESTED),
        due_at=float(_DEBUG_REFRESH_DUE_AT),
        reason=str(_DEBUG_REFRESH_REASON or ""),
        requested_at=float(_DEBUG_REFRESH_REQUESTED_AT),
        view=_DEBUG_REFRESH_VIEW,
        timer_registered=bool(_DEBUG_TIMER_REGISTERED),
        last_request_log_signature=_LAST_DEBUG_REQUEST_LOG_SIGNATURE,
        last_request_log_at=float(_LAST_DEBUG_REQUEST_LOG_AT),
    )


def _sync_debug_overlay_refresh_state(state: runtime_debug_overlay_worker.DebugOverlayRefreshState) -> None:
    global _DEBUG_REFRESH_REQUESTED, _DEBUG_REFRESH_DUE_AT, _DEBUG_REFRESH_REASON
    global _DEBUG_REFRESH_REQUESTED_AT, _DEBUG_REFRESH_VIEW, _DEBUG_TIMER_REGISTERED
    global _LAST_DEBUG_REQUEST_LOG_SIGNATURE, _LAST_DEBUG_REQUEST_LOG_AT
    _DEBUG_REFRESH_REQUESTED = bool(state.requested)
    _DEBUG_REFRESH_DUE_AT = float(state.due_at)
    _DEBUG_REFRESH_REASON = str(state.reason or "")
    _DEBUG_REFRESH_REQUESTED_AT = float(state.requested_at)
    _DEBUG_REFRESH_VIEW = state.view
    _DEBUG_TIMER_REGISTERED = bool(state.timer_registered)
    _LAST_DEBUG_REQUEST_LOG_SIGNATURE = state.last_request_log_signature
    _LAST_DEBUG_REQUEST_LOG_AT = float(state.last_request_log_at)


def _debug_overlay_worker_process_deps() -> runtime_debug_overlay_worker.DebugOverlayWorkerProcessDeps:
    return runtime_debug_overlay_worker.DebugOverlayWorkerProcessDeps(
        debug_worker_state_cls=_DebugWorkerState,
        protocol=protocol,
        queue_module=queue,
        threading_module=threading,
        subprocess_module=subprocess,
        repo_root_fn=repo_root,
        resolve_backend_executable_fn=resolve_backend_executable,
        ensure_backend_compatible_fn=ensure_backend_compatible,
        debug_overlay_run_log_path_fn=_debug_overlay_run_log_path,
        debug_overlay_live_log_path_fn=_debug_overlay_live_log_path,
        close_log_handle_fn=_close_log_handle,
        append_live_log_fn=_append_live_log,
        format_debug_overlay_event_block_fn=_format_debug_overlay_event_block,
        maybe_open_backend_log_window_fn=maybe_open_backend_log_window,
    )


def _prepare_debug_overlay_job(context, project, group, *, debug_view=None):
    from . import export

    return export.prepare_debug_overlay_job(context, project, group, debug_view=debug_view)


def _peek_active_project(scene):
    from . import properties

    return properties.peek_active_project(scene)


def _peek_active_group(project):
    from . import properties

    return properties.peek_active_group(project)


def _invalidate_overlay_cache_for_debug_refresh() -> None:
    from . import overlays

    overlays.invalidate_overlay_cache(clear_static=False)


def _tag_redraw_all_view3d_for_debug_refresh() -> None:
    from . import overlays

    overlays.tag_redraw_all_view3d()


def _debug_overlay_coordinator_deps() -> runtime_debug_overlay_worker.DebugOverlayCoordinatorDeps:
    return runtime_debug_overlay_worker.DebugOverlayCoordinatorDeps(
        active_debug_state_cls=_ActiveDebugOverlayState,
        constants=constants,
        protocol=protocol,
        queue_module=queue,
        os_module=os,
        time_monotonic_fn=time.monotonic,
        debug_overlay_enabled_fn=debug_overlay_enabled,
        background_polling_supported_fn=_background_polling_supported,
        active_debug_result_key_fn=_active_debug_result_key,
        debug_overlay_run_log_path_fn=_debug_overlay_run_log_path,
        peek_debug_overlay_result_fn=peek_debug_overlay_result,
        append_debug_overlay_event_fn=_append_debug_overlay_event,
        append_live_log_fn=_append_live_log,
        format_debug_overlay_event_block_fn=_format_debug_overlay_event_block,
        write_backend_log_fn=_write_backend_log,
        start_debug_overlay_worker_fn=_start_debug_overlay_worker,
        stop_debug_overlay_worker_fn=_stop_debug_overlay_worker,
        clear_active_debug_state_fn=_clear_active_debug_state,
        prepare_debug_overlay_job_fn=_prepare_debug_overlay_job,
        peek_active_project_fn=_peek_active_project,
        peek_active_group_fn=_peek_active_group,
        invalidate_overlay_cache_fn=_invalidate_overlay_cache_for_debug_refresh,
        tag_redraw_all_view3d_fn=_tag_redraw_all_view3d_for_debug_refresh,
        active_debug_getter_fn=lambda: _ACTIVE_DEBUG,
        build_geometry_transport_retry_job_fn=_build_geometry_transport_retry_job,
        release_workspace_geometry_transports_fn=_release_workspace_geometry_transports,
    )


def _default_bake_progress() -> protocol.BakeProgress:
    return protocol.BakeProgress(status=constants.STATUS_BAKING, message=constants.STATUS_BAKING)


def _load_progress_or_default(
    progress_path: Path,
    *,
    fallback: protocol.BakeProgress | None = None,
) -> protocol.BakeProgress:
    if not progress_path.exists():
        return fallback or _default_bake_progress()

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            return protocol.load_progress(progress_path)
        except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(0.01)

    if fallback is not None:
        return fallback
    if last_error is not None:
        raise last_error
    return _default_bake_progress()


def _close_log_handle(handle) -> None:
    if handle is None:
        return
    try:
        handle.close()
    except Exception:
        pass


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _background_progress_log_signature(progress: protocol.BakeProgress) -> tuple:
    first_miss = None
    miss_diagnostics = list(getattr(progress, "miss_diagnostics", []) or [])
    if miss_diagnostics:
        first_miss = miss_diagnostics[0]
    return (
        str(getattr(progress, "status", "") or ""),
        str(getattr(progress, "message", "") or ""),
        round(float(getattr(progress, "percent", 0.0) or 0.0), 3),
        str(getattr(progress, "active_group", "") or ""),
        str(getattr(progress, "active_map", "") or ""),
        (
            str(getattr(first_miss, "group_name", "") or ""),
            tuple(str(item or "") for item in getattr(first_miss, "map_types", [])[:2]),
            int(getattr(first_miss, "miss_pixels", 0) or 0),
            int(getattr(first_miss, "covered_pixels", 0) or 0),
        ),
        tuple(str(item or "") for item in getattr(progress, "warnings", [])[:2]),
        tuple(str(item or "") for item in getattr(progress, "errors", [])[:3]),
    )


def _format_background_miss_summary(diagnostic) -> str:
    group_name = str(getattr(diagnostic, "group_name", "") or "")
    map_types = [str(item or "") for item in getattr(diagnostic, "map_types", []) if str(item or "")]
    covered_pixels = int(getattr(diagnostic, "covered_pixels", 0) or 0)
    miss_pixels = int(getattr(diagnostic, "miss_pixels", 0) or 0)
    if covered_pixels <= 0 or miss_pixels <= 0:
        return ""
    miss_ratio = float(getattr(diagnostic, "miss_ratio", 0.0) or 0.0)
    if miss_ratio <= 0.0:
        miss_ratio = miss_pixels / max(1, covered_pixels)
    target_label = group_name
    if map_types:
        joined_maps = ", ".join(map_types)
        target_label = f"{group_name} / {joined_maps}" if group_name else joined_maps
    return f"Miss: {target_label} {miss_ratio * 100.0:.1f}% ({miss_pixels}/{covered_pixels})"


def _append_background_bake_progress_log(state: _ActiveBakeState, progress: protocol.BakeProgress, *, force: bool = False) -> None:
    signature = _background_progress_log_signature(progress)
    if not force and state.last_progress_log_signature == signature:
        return
    state.last_progress_log_signature = signature

    percent_text = f"{max(0.0, float(getattr(progress, 'percent', 0.0) or 0.0)):.1f}%"
    status_text = str(getattr(progress, "status", "") or "Bake")
    active_group = str(getattr(progress, "active_group", "") or "")
    active_map = str(getattr(progress, "active_map", "") or "")
    message = str(getattr(progress, "message", "") or "")
    details: list[str] = []
    if active_group and active_map:
        details.append(f"Active: {active_group} / {active_map}")
    elif active_group:
        details.append(f"Active: {active_group}")
    if message:
        details.append(f"Status: {message}")
    miss_diagnostics = list(getattr(progress, "miss_diagnostics", []) or [])
    if miss_diagnostics:
        miss_summary = _format_background_miss_summary(miss_diagnostics[0])
        if miss_summary:
            details.append(miss_summary)
    if getattr(progress, "warnings", None):
        warnings = list(getattr(progress, "warnings", []))
        details.append(f"Warnings: {len(warnings)}")
        details.append(f"Warn: {str(warnings[0])}")
    if getattr(progress, "errors", None):
        details.append(f"Errors: {len(getattr(progress, 'errors', []))}")
    _append_live_log_block(
        state.stdout_path,
        f"{status_text} {percent_text}",
        details,
    )


def _append_background_bake_launch_log(
    live_log_path: str | Path,
    *,
    job_path: str | Path,
    backend_path: str | Path | None,
    backend_version: str = "",
    resident_worker: bool = False,
) -> None:
    details = [f"Job: {_short_log_path(job_path, parts=3)}"]
    if backend_path is not None:
        backend_name = Path(backend_path).name
        executable_detail = f"Backend: {backend_name}"
        if backend_version:
            executable_detail += f" ({backend_version})"
        details.append(executable_detail)
        details.append(f"Executable: {_short_log_path(backend_path, parts=4)}")
    if resident_worker:
        details.append("Mode: resident bake worker")
    _append_live_log_block(live_log_path, "Bake started", details)


def _append_background_bake_callback_error_log(state: _ActiveBakeState, exc: Exception) -> None:
    details = [f"Error: {exc.__class__.__name__}: {exc}"]
    formatted = traceback.format_exc().strip()
    if formatted:
        details.append(formatted.splitlines()[-1])
    _append_live_log_block(state.stdout_path, "UI update error", details)


def _append_background_bake_poll_error_log(state: _ActiveBakeState, exc: Exception) -> None:
    details = [f"Error: {exc.__class__.__name__}: {exc}"]
    formatted = traceback.format_exc().strip()
    if formatted:
        details.append(formatted.splitlines()[-1])
    _append_live_log_block(state.stdout_path, "Progress poll error", details)


def _clear_active_bake_state(*, keep_requests: bool = False) -> None:
    global _ACTIVE_BAKE
    state = _ACTIVE_BAKE
    if state is None:
        return
    if not keep_requests:
        # Deleting the cancel/pause request files also resets their Win32 events.
        # A caller that has just asked the worker to stop must pass
        # keep_requests=True or it revokes its own request microseconds later.
        _clear_bake_cancel_request(state.progress_path)
        _clear_bake_pause_request(state.progress_path)
    _close_log_handle(state.stdout_handle)
    _close_log_handle(state.stderr_handle)
    _close_bake_progress_event(state.progress_event_handle)
    state.progress_event_handle = None
    # Only the finishing poll releases a job's shared-memory payloads, and this path
    # exists precisely because that poll will never come (file load / cache clear), so
    # every mapped high mesh of the abandoned job -- hundreds of MB to GB, page-file
    # backed -- stayed open for the rest of the session. Our handles are not the
    # mapping's only reference, so a worker still finishing the doomed job keeps its
    # own view alive.
    try:
        released = mesh_transport.release_workspace_shared_memory(state.job_path.parent)
    except Exception as exc:
        print(f"[MasterBaker] could not release the abandoned job's shared memory: {exc!r}")
        released = 0
    if released:
        print(f"[MasterBaker] released {released} shared-memory payload(s) from the abandoned bake")
    _ACTIVE_BAKE = None


def clear_active_bake_state(*, keep_requests: bool = False) -> None:
    """Drop the active-bake bookkeeping without terminating the resident worker.

    The snapshot's ``running`` flag is ``process.poll() is None`` — i.e. the
    resident worker being alive — so it never flips false on its own; only a
    poll that consumes the finished response clears ``_ACTIVE_BAKE``. On file
    load/revert the in-flight job's project is gone (its result can't be
    finalized) and background polling has already been stopped, so without this
    the freshly loaded file would open onto a phantom "a bake is running" state.
    Leaves ``_BAKE_WORKER`` alone so the next bake stays warm.

    ``keep_requests=True`` drops the in-memory bookkeeping but leaves the on-disk
    cancel/pause request files (and their signalled events) in place. Callers
    that cancel and then clear - the file-load handler does exactly that - need
    it, otherwise the clear unlinks the cancel request the cancel just wrote and
    the worker never sees it.
    """
    _clear_active_bake_state(keep_requests=keep_requests)


def shutdown_workers_for_cache_clear() -> None:
    global _PREPARE_IN_FLIGHT, _PREPARE_READY_TIMER_REGISTERED
    stop_background_polling()
    cancel_debug_overlay_refresh()
    # A PREPARE in flight dies with the worker. Left armed, the ready-check
    # timer saw worker is None and reported a prewarm FAILURE, which disabled
    # mesh prewarm for the session and blamed the backend for a Clear Cache.
    _PREPARE_IN_FLIGHT = False
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "is_registered"):
        try:
            if timers.is_registered(_prepare_ready_check_timer):
                timers.unregister(_prepare_ready_check_timer)
        except Exception:
            pass
    _PREPARE_READY_TIMER_REGISTERED = False
    _stop_bake_worker(terminate=True)
    _clear_active_bake_state()
    _stop_debug_overlay_worker(terminate=True)
    _clear_active_debug_state()
    mesh_transport.release_all_shared_memory()


def _clear_active_debug_state() -> None:
    global _ACTIVE_DEBUG, _DEBUG_REFRESH_VIEW
    _ACTIVE_DEBUG = None
    _DEBUG_REFRESH_VIEW = None


def _absolute_image_path(file_path: str | Path | None) -> str:
    """Resolve Blender's ``//`` relative prefix before any filesystem lookup.

    After Save As with Remap Relative every managed image path starts with
    ``//``; fed to the cache verbatim it stat()s to mtime 0 (so a rebake never
    reloaded pixels) and normalised to a key no output path could ever match.
    """
    raw = str(file_path or "").strip()
    if raw.startswith("//"):
        try:
            return str(bpy.path.abspath(raw))
        except Exception:
            return raw
    return raw


def _normalize_image_path(file_path: str | Path | None) -> str:
    return runtime_output_images.normalize_image_path(_absolute_image_path(file_path), os_module=os)


def _image_file_mtime_ns(file_path: str | Path | None) -> int:
    return runtime_output_images.image_file_mtime_ns(_absolute_image_path(file_path))


def _image_metadata_get(image, key: str, default=None):
    return runtime_output_images.image_metadata_get(image, key, default)


def _image_metadata_set(image, key: str, value) -> None:
    runtime_output_images.image_metadata_set(image, key, value)


def _image_filepath(image) -> str:
    return runtime_output_images.image_filepath(image)


def _mark_managed_output_image(image, file_path: str | Path) -> None:
    runtime_output_images.mark_managed_output_image(
        image,
        file_path,
        managed_output_path_key=_MANAGED_OUTPUT_PATH_KEY,
        managed_output_mtime_key=_MANAGED_OUTPUT_MTIME_KEY,
        image_metadata_set_fn=_image_metadata_set,
        normalize_image_path_fn=_normalize_image_path,
        image_file_mtime_ns_fn=_image_file_mtime_ns,
    )


def _image_matches_output_path(image, normalized_file_path: str) -> bool:
    return runtime_output_images.image_matches_output_path(
        image,
        normalized_file_path,
        managed_output_path_key=_MANAGED_OUTPUT_PATH_KEY,
        image_metadata_get_fn=_image_metadata_get,
        normalize_image_path_fn=_normalize_image_path,
        image_filepath_fn=_image_filepath,
    )


def _find_existing_image_for_path(images, normalized_file_path: str):
    return runtime_output_images.find_existing_image_for_path(
        images,
        normalized_file_path,
        image_matches_output_path_fn=_image_matches_output_path,
    )


def load_managed_output_image(file_path: str | Path):
    images = getattr(getattr(bpy, "data", None), "images", None)
    return runtime_output_images.load_managed_output_image(
        file_path,
        images=images,
        managed_output_mtime_key=_MANAGED_OUTPUT_MTIME_KEY,
        normalize_image_path_fn=_normalize_image_path,
        find_existing_image_for_path_fn=_find_existing_image_for_path,
        image_metadata_get_fn=_image_metadata_get,
        image_file_mtime_ns_fn=_image_file_mtime_ns,
        mark_managed_output_image_fn=_mark_managed_output_image,
    )


def invalidate_output_image_cache(file_paths: list[str] | tuple[str, ...]) -> int:
    images = getattr(getattr(bpy, "data", None), "images", None)
    return runtime_output_images.invalidate_output_image_cache(
        file_paths,
        images=images,
        normalize_image_path_fn=_normalize_image_path,
        image_matches_output_path_fn=_image_matches_output_path,
        image_filepath_fn=_image_filepath,
        image_file_mtime_ns_fn=_image_file_mtime_ns,
        image_metadata_get_fn=_image_metadata_get,
        managed_output_mtime_key=_MANAGED_OUTPUT_MTIME_KEY,
        mark_managed_output_image_fn=_mark_managed_output_image,
    )


def refresh_project_output_images(project) -> int:
    with runtime_output_images.normalized_path_cache():
        return _refresh_project_output_images(project)


def _refresh_project_output_images(project) -> int:
    reloaded = runtime_output_images.refresh_project_output_images(
        project,
        invalidate_output_image_cache_fn=invalidate_output_image_cache,
    )
    try:
        _images = getattr(getattr(bpy, "data", None), "images", None)
        if _images is not None:
            runtime_output_images.apply_output_image_colorspaces(
                project,
                find_existing_image_for_path_fn=lambda path: _find_existing_image_for_path(
                    _images, _normalize_image_path(path)
                ),
                colorspace_name_fn=constants.map_output_colorspace_name,
            )
    except Exception:
        pass
    # Tiled outputs are a separate datablock shape (one TILED image per logical map, not one
    # image per file), and the plain refresh above cannot see them: their filepath carries
    # the <UDIM> token and never matches a concrete produced path. Untiled projects have no
    # tiled entries and skip this entirely.
    from . import udim_images

    images = getattr(getattr(bpy, "data", None), "images", None)
    if images is not None:
        try:
            udim_images.sync_project_output_images(project, images=images)
        except Exception:
            pass
    return reloaded


def _bake_worker_control_deps() -> runtime_bake_worker.BakeWorkerControlDeps:
    return runtime_bake_worker.BakeWorkerControlDeps(
        active_bake_state_cls=_ActiveBakeState,
        bake_worker_state_cls=_BakeWorkerState,
        snapshot_cls=BackgroundBakeSnapshot,
        poll_result_cls=BackgroundBakePollResult,
        constants=constants,
        protocol=protocol,
        queue_module=queue,
        threading_module=threading,
        subprocess_module=subprocess,
        repo_root_fn=repo_root,
        path_mtime_ns_fn=_path_mtime_ns,
        resolve_backend_executable_fn=resolve_backend_executable,
        ensure_backend_compatible_fn=ensure_backend_compatible,
        backend_run_log_path_fn=_backend_run_log_path,
        background_bake_live_log_path_fn=_background_bake_live_log_path,
        resident_bake_worker_stderr_path_fn=_resident_bake_worker_stderr_path,
        read_text_if_exists_fn=_read_text_if_exists,
        write_backend_log_fn=_write_backend_log,
        append_launch_log_fn=_append_background_bake_launch_log,
        maybe_open_backend_log_window_fn=maybe_open_backend_log_window,
        load_progress_or_default_fn=_load_progress_or_default,
        append_progress_log_fn=_append_background_bake_progress_log,
        clear_bake_cancel_request_fn=_clear_bake_cancel_request,
        clear_bake_pause_request_fn=_clear_bake_pause_request,
        write_bake_cancel_request_fn=_write_bake_cancel_request,
        write_bake_pause_request_fn=_write_bake_pause_request,
        create_bake_progress_event_fn=_create_bake_progress_event,
        check_and_reset_bake_progress_event_fn=_check_and_reset_bake_progress_event,
        close_bake_progress_event_fn=_close_bake_progress_event,
        close_log_handle_fn=_close_log_handle,
        release_workspace_shared_memory_fn=_release_workspace_geometry_transports,
        build_geometry_transport_retry_job_fn=_build_geometry_transport_retry_job,
        on_gpu_init_failure_retire_fn=_on_bake_worker_gpu_init_failure,
    )


def _on_bake_worker_gpu_init_failure(error_text: str) -> None:
    """The resident worker latched a failed GPU init and is being retired.

    The backend's ``ensure_d3d12_runtime`` never retries a failed first device
    creation inside one process, so the worker is stopped by the poller and the
    next bake spawns a fresh one. Here: say so once, drop the prepared-scene claim
    (those caches die with the process), and forget any negative GPU verdict so
    the next bake-start gate re-probes instead of waiting out the TTL.
    """
    first_line = next(
        (line.strip() for line in str(error_text or "").splitlines() if line.strip()), ""
    )
    try:
        print(f"[fyr_baker] gpu-init-failure recycle: retiring the bake worker ({first_line})")
    except Exception:
        pass
    forget_prepared_scene_signature()
    try:
        expire_stale_negative_backend_verdicts(force=True)
    except Exception:
        pass


def active_bake_snapshot() -> BackgroundBakeSnapshot | None:
    return runtime_bake_worker.active_bake_snapshot(_ACTIVE_BAKE, BackgroundBakeSnapshot)


_normalize_selected_map_types = runtime_bake_worker.normalize_selected_map_types
_bake_worker_run_command = runtime_bake_worker.bake_worker_run_command
_bake_worker_log_command = runtime_bake_worker.bake_worker_log_command
_bake_cli_command = runtime_bake_worker.bake_cli_command


def launch_bake_job_background(
    job_path: str | Path,
    progress_path: str | Path,
    *,
    job_id: str = "",
    selected_map_types: list[str] | tuple[str, ...] | None = None,
) -> BackgroundBakeSnapshot:
    global _ACTIVE_BAKE, _BAKE_WORKER, _PREPARE_IN_FLIGHT, _BAKE_STARTED_DURING_PREWARM
    # RUN is about to be queued; clear the in-flight flag and release any
    # speculative shared memory (backend is done reading it via PREPARE).
    # Remember whether the worker was still prewarming: the RUN queues behind the
    # in-flight PREPARE, so the bake sits at "Baking 0%" until the prewarm finishes.
    # The UI uses this to label that wait as warming-up instead of a stuck bake.
    _BAKE_STARTED_DURING_PREWARM = bool(_PREPARE_IN_FLIGHT)
    _PREPARE_IN_FLIGHT = False
    # A RUN reuses, and may evict, whatever PREPARE primed. Rather than reason
    # about what survives it, drop the claim: the post-bake speculative prepare
    # then re-primes exactly once (the behaviour before the skip gate existed)
    # and records the fingerprint again, so bake speed cannot regress while
    # repeated triggers on an unchanged scene still stand down.
    forget_prepared_scene_signature()
    _release_speculative_prepare_workspace()

    existing = active_bake_snapshot()
    if existing is not None and existing.running:
        raise RuntimeError("Another bake is already running")
    if existing is not None and not existing.running:
        poll_active_bake()

    _ACTIVE_BAKE, _BAKE_WORKER = runtime_bake_worker.launch_bake_job_background(
        job_path,
        progress_path,
        job_id=job_id,
        selected_map_types=selected_map_types,
        current_worker=_BAKE_WORKER,
        deps=_bake_worker_control_deps(),
    )
    return active_bake_snapshot()


def poll_active_bake() -> BackgroundBakePollResult | None:
    global _ACTIVE_BAKE, _BAKE_WORKER
    result, _ACTIVE_BAKE, _BAKE_WORKER = runtime_bake_worker.poll_active_bake(
        _ACTIVE_BAKE,
        _BAKE_WORKER,
        deps=_bake_worker_control_deps(),
    )
    return result


def cancel_active_bake(*, force: bool = False) -> BackgroundBakeSnapshot | None:
    global _ACTIVE_BAKE, _BAKE_WORKER
    _ACTIVE_BAKE, _BAKE_WORKER = runtime_bake_worker.cancel_active_bake(
        _ACTIVE_BAKE,
        _BAKE_WORKER,
        deps=_bake_worker_control_deps(),
        force=force,
    )
    return active_bake_snapshot()


def bake_cancel_is_pending() -> bool:
    """Whether a cancel has been requested and the worker has not stopped yet."""
    state = _ACTIVE_BAKE
    return bool(state is not None and getattr(state, "cancel_requested", False))


def pause_active_bake() -> BackgroundBakeSnapshot | None:
    global _ACTIVE_BAKE, _BAKE_WORKER
    _ACTIVE_BAKE, _BAKE_WORKER = runtime_bake_worker.pause_active_bake(
        _ACTIVE_BAKE,
        _BAKE_WORKER,
        deps=_bake_worker_control_deps(),
    )
    return active_bake_snapshot()


def resume_active_bake() -> BackgroundBakeSnapshot | None:
    global _ACTIVE_BAKE, _BAKE_WORKER
    _ACTIVE_BAKE, _BAKE_WORKER = runtime_bake_worker.resume_active_bake(
        _ACTIVE_BAKE,
        _BAKE_WORKER,
        deps=_bake_worker_control_deps(),
    )
    return active_bake_snapshot()


def _background_bake_timer():
    global _POLL_UPDATE_CALLBACK
    try:
        result = poll_active_bake()
    except Exception as exc:
        state = _ACTIVE_BAKE
        if state is None:
            _POLL_UPDATE_CALLBACK = None
            return None
        _append_background_bake_poll_error_log(state, exc)
        return 0.05 if (state.progress_event_handle is not None) else 0.25
    if result is None:
        # No active bake — check if the dirty tracker wants to fire a rebake.
        if _DIRTY_REBAKE_CALLBACK is not None:
            try:
                _DIRTY_REBAKE_CALLBACK()
            except Exception:
                pass
        _POLL_UPDATE_CALLBACK = None
        return None
    if _POLL_UPDATE_CALLBACK is not None:
        try:
            _POLL_UPDATE_CALLBACK(result)
        except Exception as exc:
            state = _ACTIVE_BAKE
            if state is not None:
                _append_background_bake_callback_error_log(state, exc)
    if result.finished:
        _POLL_UPDATE_CALLBACK = None
        # Capture the just-finished job path for PREPARE-on-respawn so the
        # next time the worker is restarted (e.g. backend update, manual
        # restart) we can prime its caches before the user resubmits.
        try:
            progress = result.progress
            status = str(getattr(progress, "status", "") or "")
            failed = status in {
                constants.STATUS_FAILED,
                constants.STATUS_CANCELLED,
                constants.STATUS_CANCELLING,
            }
            if not failed and (progress is None or not getattr(progress, "errors", None)):
                # The finishing poll already dropped _ACTIVE_BAKE, so reading it here
                # always recorded None and the worker respawn re-exported the whole
                # scene instead of PREPARE-ing the job that had just baked.
                _record_last_successful_bake(result.snapshot)
        except Exception:
            pass
        # Bake just finished — also give the dirty tracker a chance to fire
        # in case changes accumulated while the previous bake was running.
        if _DIRTY_REBAKE_CALLBACK is not None:
            try:
                _DIRTY_REBAKE_CALLBACK()
            except Exception:
                pass
        return 0.25
    # Bake in progress: use 50 ms when the Win32 progress event is available (near-zero
    # cost per tick — WaitForSingleObject with timeout=0) so we respond to backend
    # signals within <50 ms instead of up to 250 ms.
    state = _ACTIVE_BAKE
    if state is not None and state.progress_event_handle is not None:
        return 0.05
    return 0.25


def set_dirty_rebake_callback(callback) -> None:
    """Register a zero-argument callable invoked whenever no bake is running and the
    dirty tracker has pending changes whose debounce has elapsed."""
    global _DIRTY_REBAKE_CALLBACK
    _DIRTY_REBAKE_CALLBACK = callback


def clear_dirty_rebake_callback() -> None:
    global _DIRTY_REBAKE_CALLBACK
    _DIRTY_REBAKE_CALLBACK = None


def _dirty_check_timer() -> float | None:
    """Lightweight persistent timer that fires the dirty-rebake callback when no bake is running."""
    if _DIRTY_REBAKE_CALLBACK is None:
        return None  # Unregister — callback was cleared.
    if _ACTIVE_BAKE is not None:
        return 0.25  # Bake in progress; check again shortly.
    try:
        _DIRTY_REBAKE_CALLBACK()
    except Exception:
        pass
    return 0.25


def start_dirty_check_timer() -> None:
    """Start the persistent timer that auto-triggers incremental rebakes."""
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None:
        return
    try:
        timers.unregister(_dirty_check_timer)
    except Exception:
        pass
    timers.register(_dirty_check_timer, first_interval=0.5)


def stop_dirty_check_timer() -> None:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None:
        return
    try:
        timers.unregister(_dirty_check_timer)
    except Exception:
        pass


def start_background_polling(update_callback) -> bool:
    global _POLL_UPDATE_CALLBACK
    if not _background_polling_supported():
        return False
    _POLL_UPDATE_CALLBACK = update_callback
    timers = bpy.app.timers
    try:
        timers.unregister(_background_bake_timer)
    except Exception:
        pass
    timers.register(_background_bake_timer, first_interval=0.1)
    return True


def stop_background_polling() -> None:
    global _POLL_UPDATE_CALLBACK
    _POLL_UPDATE_CALLBACK = None
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None:
        return
    try:
        timers.unregister(_background_bake_timer)
    except Exception:
        pass


def _debug_overlay_run_log_path(result_path: str | Path) -> Path:
    return Path(result_path).parent / "logs" / "debug_overlay_run.log"


_bake_worker_reader = runtime_bake_worker.bake_worker_reader


def _stop_bake_worker(*, terminate: bool = False) -> None:
    global _BAKE_WORKER, _PENDING_PREPARE_SIGNATURE, _PREPARED_SCENE_SIGNATURE
    # The worker owns the prepared caches; they die with the process.
    _PENDING_PREPARE_SIGNATURE = ""
    _PREPARED_SCENE_SIGNATURE = ""
    _BAKE_WORKER = runtime_bake_worker.stop_bake_worker(
        _BAKE_WORKER,
        terminate=terminate,
        close_log_handle_fn=_close_log_handle,
    )


def _atexit_stop_workers() -> None:
    # Belt-and-suspenders: terminate any resident backend processes when
    # Python exits (covers Blender crash / force-quit where unregister() is
    # never called).  safe to call multiple times — stop_bake_worker is idempotent.
    try:
        _stop_bake_worker(terminate=True)
    except Exception:
        pass
    try:
        _stop_debug_overlay_worker(terminate=True)
    except Exception:
        pass


atexit.register(_atexit_stop_workers)


def _start_bake_worker(progress_path: str | Path, backend_log_path: str | Path) -> _BakeWorkerState:
    global _BAKE_WORKER, _PENDING_BAKE_NOTICE
    _BAKE_WORKER = runtime_bake_worker.start_bake_worker(
        progress_path,
        backend_log_path,
        current_worker=_BAKE_WORKER,
        deps=_bake_worker_control_deps(),
    )
    if _PENDING_BAKE_NOTICE:
        _write_bake_pending_notice(_BAKE_WORKER, _PENDING_BAKE_NOTICE)
        _PENDING_BAKE_NOTICE = ""
    return _BAKE_WORKER


def _debug_worker_reader(stdout_handle, response_queue) -> None:
    runtime_debug_overlay_worker.debug_worker_reader(
        stdout_handle,
        response_queue,
        load_debug_overlay_result_fn=protocol.load_debug_overlay_result,
    )


def _stop_debug_overlay_worker(*, terminate: bool = False) -> None:
    global _DEBUG_WORKER
    _DEBUG_WORKER = runtime_debug_overlay_worker.stop_debug_overlay_worker(
        _DEBUG_WORKER,
        terminate=terminate,
        close_log_handle_fn=_close_log_handle,
    )


def _start_debug_overlay_worker(result_path: str | Path) -> _DebugWorkerState:
    global _DEBUG_WORKER
    _DEBUG_WORKER = runtime_debug_overlay_worker.start_debug_overlay_worker(
        result_path,
        current_worker=_DEBUG_WORKER,
        deps=_debug_overlay_worker_process_deps(),
    )
    worker = _DEBUG_WORKER
    return worker


def _launch_debug_overlay_process(context) -> None:
    global _ACTIVE_DEBUG
    refresh_state = _debug_overlay_refresh_state_from_globals()
    previous_active_debug = _ACTIVE_DEBUG
    active_debug, refresh_state = runtime_debug_overlay_worker.launch_debug_overlay_process(
        context,
        refresh_state,
        deps=_debug_overlay_coordinator_deps(),
    )
    if active_debug is not None or previous_active_debug is None:
        _ACTIVE_DEBUG = active_debug
    _sync_debug_overlay_refresh_state(refresh_state)


def _finalize_active_debug_process() -> None:
    global _ACTIVE_DEBUG
    _ACTIVE_DEBUG = runtime_debug_overlay_worker.finalize_active_debug_process(
        _ACTIVE_DEBUG,
        _DEBUG_WORKER,
        debug_results=_DEBUG_RESULTS,
        debug_result_input_signatures=_DEBUG_RESULT_INPUT_SIGNATURES,
        deps=_debug_overlay_coordinator_deps(),
    )


def _debug_overlay_timer():
    refresh_state = _debug_overlay_refresh_state_from_globals()
    interval, refresh_state = runtime_debug_overlay_worker.debug_overlay_timer(
        refresh_state,
        finalize_active_debug_process_fn=_finalize_active_debug_process,
        active_debug_getter_fn=lambda: _ACTIVE_DEBUG,
        launch_debug_overlay_process_fn=_launch_debug_overlay_process,
        append_debug_overlay_event_fn=_append_debug_overlay_event,
        clear_active_debug_state_fn=_clear_active_debug_state,
        context_getter_fn=lambda: bpy.context,
        time_monotonic_fn=time.monotonic,
        traceback_format_exc_fn=traceback.format_exc,
        print_fn=print,
        constants=constants,
    )
    _sync_debug_overlay_refresh_state(refresh_state)
    return interval


def request_debug_overlay_refresh(
    context,
    *,
    delay_seconds: float | None = None,
    reason: str = "unspecified",
    debug_view: protocol.DebugViewConfig | None = None,
    project=None,
    group=None,
) -> None:
    refresh_state = _debug_overlay_refresh_state_from_globals()
    refresh_state = runtime_debug_overlay_worker.request_debug_overlay_refresh(
        context,
        refresh_state,
        delay_seconds=delay_seconds,
        reason=reason,
        debug_view=debug_view,
        project=project,
        group=group,
        timers=bpy.app.timers,
        debug_overlay_timer_fn=_debug_overlay_timer,
        deps=_debug_overlay_coordinator_deps(),
    )
    _sync_debug_overlay_refresh_state(refresh_state)


def cancel_debug_overlay_refresh() -> None:
    refresh_state = _debug_overlay_refresh_state_from_globals()
    refresh_state = runtime_debug_overlay_worker.cancel_debug_overlay_refresh(
        refresh_state,
        append_debug_overlay_event_fn=_append_debug_overlay_event,
        timers=getattr(getattr(bpy, "app", None), "timers", None),
        debug_overlay_timer_fn=_debug_overlay_timer,
    )
    _sync_debug_overlay_refresh_state(refresh_state)


# A one-shot CLI bake is real work, not a control query, so it gets its own
# ceiling. It still has one: without it a wedged backend blocks the calling
# Blender thread forever with no way out but killing the process.
_ONE_SHOT_BAKE_SUBPROCESS_TIMEOUT_S = 1800.0


def _one_shot_bake_timeout_message() -> str:
    return (
        "fyr_baker_backend did not finish the bake within "
        f"{_ONE_SHOT_BAKE_SUBPROCESS_TIMEOUT_S / 60.0:.0f} minutes and was stopped"
    )


def run_bake_job(
    job_path: str | Path,
    progress_path: str | Path,
    selected_map_types: list[str] | tuple[str, ...] | None = None,
) -> protocol.BakeProgress:
    resolved_job_path = Path(job_path)
    original_job_path = resolved_job_path
    resolved_progress_path = Path(progress_path)
    backend_log_path = _backend_run_log_path(resolved_progress_path)
    selected_maps = _normalize_selected_map_types(selected_map_types)
    command = _bake_cli_command(resolved_job_path, selected_maps)
    backend_path: Path | None = None
    backend_version = ""
    try:
        _clear_bake_cancel_request(resolved_progress_path)
        _clear_bake_pause_request(resolved_progress_path)
        backend_path = resolve_backend_executable()
        backend_version = ensure_backend_compatible(backend_path, log_path=backend_log_path)
        backend_env = None
        try:
            from . import preferences as _prefs_mod
            backend_env = _prefs_mod.build_backend_env()
        except Exception:
            pass
        try:
            completed = subprocess.run(
                [str(backend_path), *command],
                cwd=str(resolved_job_path.parent),
                capture_output=True,
                text=True,
                env=backend_env,
                timeout=_ONE_SHOT_BAKE_SUBPROCESS_TIMEOUT_S,
                creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
                **runtime_bake_worker.spawn_feedback_suppression_kwargs(subprocess),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(_one_shot_bake_timeout_message()) from exc
        error_output = (completed.stderr or completed.stdout or "").strip()
        if (
            completed.returncode != 0
            and error_output.startswith("TRANSPORT_ERR\t")
        ):
            resolved_job_path = _build_geometry_transport_retry_job(
                original_job_path
            )
            command = _bake_cli_command(resolved_job_path, selected_maps)
            try:
                completed = subprocess.run(
                    [str(backend_path), *command],
                    cwd=str(resolved_job_path.parent),
                    capture_output=True,
                    text=True,
                    env=backend_env,
                    timeout=_ONE_SHOT_BAKE_SUBPROCESS_TIMEOUT_S,
                    creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
                    **runtime_bake_worker.spawn_feedback_suppression_kwargs(
                        subprocess
                    ),
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(_one_shot_bake_timeout_message()) from exc
    except Exception as exc:
        _write_backend_log(
            backend_log_path,
            title="Backend bake launch failed",
            backend_path=backend_path,
            command=command,
            cwd=str(resolved_job_path.parent),
            returncode=-1,
            stdout="",
            stderr="",
            backend_version=backend_version,
            note=str(exc),
        )
        raise

    if resolved_progress_path.exists():
        progress = protocol.load_progress(resolved_progress_path)
    else:
        progress = protocol.BakeProgress()

    _write_backend_log(
        backend_log_path,
        title="Backend bake run",
        backend_path=backend_path,
        command=command,
        cwd=str(resolved_job_path.parent),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        backend_version=backend_version,
    )

    if completed.returncode == 0:
        _clear_bake_cancel_request(resolved_progress_path)
        _clear_bake_pause_request(resolved_progress_path)
        _release_workspace_geometry_transports(resolved_job_path.parent)
        # Track the most recently completed successful job so a subsequent
        # background prewarm can issue PREPARE for it.
        global _LAST_SUCCEEDED_BAKE_JOB_PATH
        if not getattr(progress, "errors", None):
            _LAST_SUCCEEDED_BAKE_JOB_PATH = (
                original_job_path
                if resolved_job_path == original_job_path
                else None
            )
        return progress

    error_text = (completed.stderr or completed.stdout or "").strip()
    progress.status = constants.STATUS_FAILED
    if error_text:
        progress.message = error_text
    if error_text and error_text not in progress.errors:
        progress.errors.append(error_text)
    protocol.write_progress(resolved_progress_path, progress)
    _clear_bake_cancel_request(resolved_progress_path)
    _clear_bake_pause_request(resolved_progress_path)
    _release_workspace_geometry_transports(resolved_job_path.parent)
    return progress


_PREWARM_INITIAL_DELAY_SECONDS = 0.15
_PREWARM_LOG_DIR_NAME = "prewarm"
_PREWARM_REQUESTED_REASON: str | None = None
_PREWARM_REQUESTED_UNTIL = 0.0
_PSO_PRIMING_REQUESTED = False
# Callable() invoked by the speculative-prepare timer to export a probe job and
# send PREPARE to the warm worker. Set by operators.py after its classes register.
_SPECULATIVE_PREPARE_CALLBACK = None
_SPECULATIVE_PREPARE_TIMER_REGISTERED = False
# Workspace path for the speculative export whose shared memory must be released
# once the worker sends READY (the backend has finished reading the mesh data).
_SPECULATIVE_PREPARE_WORKSPACE_PATH: Path | None = None
# Settings-triggered prepare sets this False so cold multi-million highs are not
# captured on the main thread (Not Responding). File-open / membership keep True.
_SPECULATIVE_PREPARE_ALLOW_COLD_HIGH_WARM: bool = True
_PREPARE_INFLIGHT_LOCK = threading.Lock()
_PREPARE_INFLIGHT_KEY: tuple | None = None
_MESH_PREWARM_DISABLED_FOR_SESSION = False
_LAST_PREWARM_FAILURE_MESSAGE = ""
# Path of the most recently completed (successful) bake job. We send a PREPARE
# for this path to any freshly spawned bake worker so the high-mesh BVH and
# associated caches are loaded before the next interactive bake submission.
# Cleared when the path no longer exists on disk.
_LAST_SUCCEEDED_BAKE_JOB_PATH: Path | None = None
# Track which (worker_id, job_path) we have already issued PREPARE for so we
# never re-issue against the same warm worker. Worker identity uses the OS pid
# so a respawn invalidates the gate.
_PREPARE_ISSUED_FOR: tuple[int, str] | None = None
# Original (non-normcased) job path of the most recent PREPARE sent to the warm
# worker. Activity-driven GPU keep-warm (WARMKEEP_ARM/DISARM) reuses this exact
# path so the backend resolves the same resident group it already prepared.
_LAST_PREPARED_JOB_PATH: Path | None = None
_PREPARE_TRANSPORT_RETRY_COUNT: int = 0
_GEOMETRY_TRANSPORT_RETRY_FILES: dict[str, set[Path]] = {}


def _workspace_retry_key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _build_geometry_transport_retry_job(job_path: str | Path) -> Path:
    """Create the one-shot FILE_FYMESH job after a section mapping failure."""
    from . import indexed_geometry

    source_path = Path(job_path)
    owner = protocol.binary_job_retry_owner(source_path)
    if owner is None:
        raise RuntimeError(
            "Geometry transport retry is unavailable because the in-memory job owner was released"
        )
    retry_job = copy.deepcopy(owner)
    retry_root = source_path.parent / "transport_fallback"
    converted = 0
    retry_files: set[Path] = set()
    for group_index, group in enumerate(retry_job.groups):
        for mesh_index, ref in enumerate(group.high_meshes):
            if ref.transport_kind != protocol.MESH_TRANSPORT_WIN32_SECTION:
                continue
            canonical_path = Path(ref.path)
            indexed_geometry.wait_for_canonical_path(canonical_path)
            token = str(ref.content_hash or f"{group_index}_{mesh_index}")
            safe_token = "".join(
                character if character.isalnum() else "_"
                for character in token
            )[-48:]
            destination = retry_root / (
                f"high_{group_index:03d}_{mesh_index:03d}_{safe_token}.fymesh"
            )
            fallback_path = indexed_geometry.write_temporary_fymesh(
                canonical_path, destination
            )
            retry_files.add(fallback_path)
            ref.path = str(fallback_path)
            ref.transport_kind = protocol.MESH_TRANSPORT_FILE_FYMESH
            ref.geometry_schema = ""
            ref.transport_locator = ""
            ref.byte_size = 0
            ref.content_hash = ""
            converted += 1
    if converted == 0:
        raise RuntimeError("Geometry transport retry job has no WIN32_SECTION high meshes")
    retry_path = source_path.with_name(
        source_path.stem + ".transport-fallback.mbjob"
    )
    protocol.write_binary_job(retry_path, retry_job)
    retry_files.add(retry_path)
    key = _workspace_retry_key(source_path.parent)
    _GEOMETRY_TRANSPORT_RETRY_FILES.setdefault(key, set()).update(retry_files)
    # Let the canonical writers finish first, like every other release site: closing a
    # section a writer thread still holds a memoryview over raises BufferError, and the
    # mapping (multi-GB for a high mesh) then stays committed.
    try:
        from . import indexed_geometry

        indexed_geometry.wait_for_workspace_canonical_writes(source_path.parent)
    except Exception:
        pass
    mesh_transport.release_workspace_shared_memory(source_path.parent)
    return retry_path


def _release_workspace_geometry_transports(workspace_path: str | Path) -> None:
    from . import high_mesh_cache, indexed_geometry

    indexed_geometry.wait_for_workspace_canonical_writes(workspace_path)
    high_mesh_cache.finalize_pending_canonical_aliases()
    mesh_transport.release_workspace_shared_memory(workspace_path)
    key = _workspace_retry_key(workspace_path)
    workspace = Path(workspace_path)
    for job_path in workspace.glob("*.mbjob"):
        protocol.forget_binary_job_retry_owner(job_path)
    for path in _GEOMETRY_TRANSPORT_RETRY_FILES.pop(key, set()):
        try:
            protocol.forget_binary_job_retry_owner(path)
            path.unlink(missing_ok=True)
        except Exception:
            pass
    retry_root = Path(workspace_path) / "transport_fallback"
    try:
        retry_root.rmdir()
    except OSError:
        pass


def release_workspace_geometry_transports(workspace_path: str | Path) -> None:
    _release_workspace_geometry_transports(workspace_path)
# Activity-driven GPU keep-warm state.
#   _WARMKEEP_LAST_ACTIVITY_AT  monotonic timestamp of the last bake-setting change.
#   _WARMKEEP_ARMED             True once a WARMKEEP_ARM has been sent and not yet disarmed.
#   _WARMKEEP_IDLE_TIMER_REGISTERED  guards the bpy.app.timers idle-poll registration.
#   _WARMKEEP_ARM_TIMER_REGISTERED   guards the debounce (trailing-edge) arm timer.
# After ~_WARMKEEP_IDLE_SECONDS with no activity the idle timer sends WARMKEEP_DISARM.
_WARMKEEP_IDLE_SECONDS: float = 180.0
_WARMKEEP_IDLE_POLL_SECONDS: float = 30.0
_WARMKEEP_ARM_DEBOUNCE_SECONDS: float = 0.4
_WARMKEEP_LAST_ACTIVITY_AT: float = 0.0
_WARMKEEP_ARMED: bool = False
_WARMKEEP_IDLE_TIMER_REGISTERED: bool = False
_WARMKEEP_ARM_TIMER_REGISTERED: bool = False
# A bake press that found no worker: sent to the worker that the bake starts.
_PENDING_BAKE_NOTICE: str = ""
# True between the moment PREPARE is written to stdin and the moment the worker
# sends back READY (or the worker is killed).  Used by the bake launch path to
# show "Loading scene caches…" in the initial status instead of a bare 0%.
_PREPARE_IN_FLIGHT: bool = False
# True when the most recent bake's RUN was queued while a PREPARE was still in flight, i.e. the
# bake had to wait for the background prewarm (high-scene BVH + GPU resource build) to finish. Lets
# the UI label the resulting "Baking 0%" wait as warming-up instead of a stuck/slow bake.
_BAKE_STARTED_DURING_PREWARM: bool = False
# True when the most recent worker restart/prewarm was triggered by an
# out-of-memory recovery (not a manual Restart Backend or session start). The UI
# uses this to label the "Warming up scene cache…" wait as OOM recovery, so a
# re-prewarm right after a bake failure isn't a mystery to the user.
_PREWARM_IS_OOM_RECOVERY: bool = False
# Set by the background-prepare depsgraph handler when a bake-relevant change arrives while a
# PREPARE is already in flight.  Cleared + re-triggered by _prepare_ready_check_timer on READY.
_BG_PREPARE_STALE: bool = False


# Work handed from a background thread back to Blender's main thread. Only the
# main thread may register a bpy timer, so the producer side is push-only: the
# main thread arms the drain timer BEFORE starting the worker, and the worker
# only appends to the queue.
_MAIN_THREAD_CALL_QUEUE: "queue.Queue" = queue.Queue()
_MAIN_THREAD_CALL_TIMER_REGISTERED = False
_MAIN_THREAD_CALL_PENDING = 0
_MAIN_THREAD_CALL_POLL_SECONDS = 0.5


def _noop_main_thread_call() -> None:
    return None


def _post_main_thread_call(call) -> None:
    """Queue ``call`` for execution on Blender's main thread. Thread-safe."""
    try:
        _MAIN_THREAD_CALL_QUEUE.put_nowait(call)
    except Exception:
        pass


def _main_thread_call_timer():
    global _MAIN_THREAD_CALL_TIMER_REGISTERED, _MAIN_THREAD_CALL_PENDING
    drained = 0
    while True:
        try:
            call = _MAIN_THREAD_CALL_QUEUE.get_nowait()
        except Exception:
            break
        drained += 1
        try:
            call()
        except Exception:
            pass
    _MAIN_THREAD_CALL_PENDING = max(0, _MAIN_THREAD_CALL_PENDING - drained)
    if _MAIN_THREAD_CALL_PENDING <= 0:
        _MAIN_THREAD_CALL_TIMER_REGISTERED = False
        return None
    return _MAIN_THREAD_CALL_POLL_SECONDS


def _arm_main_thread_call_timer() -> None:
    """Register the drain timer for one expected posted call. Main thread only."""
    global _MAIN_THREAD_CALL_TIMER_REGISTERED, _MAIN_THREAD_CALL_PENDING
    _MAIN_THREAD_CALL_PENDING += 1
    if _MAIN_THREAD_CALL_TIMER_REGISTERED:
        return
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    try:
        # persistent: a file load mid-warmup must not strand the queued call.
        timers.register(
            _main_thread_call_timer,
            first_interval=_MAIN_THREAD_CALL_POLL_SECONDS,
            persistent=True,
        )
        _MAIN_THREAD_CALL_TIMER_REGISTERED = True
    except Exception:
        pass


def _reset_main_thread_call_queue() -> None:
    global _MAIN_THREAD_CALL_TIMER_REGISTERED, _MAIN_THREAD_CALL_PENDING
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "is_registered"):
        try:
            if timers.is_registered(_main_thread_call_timer):
                timers.unregister(_main_thread_call_timer)
        except Exception:
            pass
    while True:
        try:
            _MAIN_THREAD_CALL_QUEUE.get_nowait()
        except Exception:
            break
    _MAIN_THREAD_CALL_TIMER_REGISTERED = False
    _MAIN_THREAD_CALL_PENDING = 0


def _backend_signature(backend_path: str | Path) -> str:
    """Stable signature combining backend path and mtime for PSO-prime gating."""
    path = Path(backend_path)
    try:
        mtime_ns = int(_path_mtime_ns(path))
    except Exception:
        mtime_ns = 0
    return f"{os.path.normcase(str(path))}::{mtime_ns}"


def _apply_pso_priming_signature(signature: str) -> None:
    """Main-thread half of the PSO priming run: stamp the prefs.

    ``prefs`` is RNA. Writing it from the warmup thread is a data race against
    Blender's own main loop, so the thread only enqueues this call.
    """
    prefs = preferences.get_preferences()
    if prefs is None:
        return
    try:
        prefs.backend_prewarm_pso_priming_signature = signature
    except Exception:
        pass


def _run_offline_warmup_blocking(
    backend_path: Path, signature: str, backend_env: dict | None = None
) -> None:
    """Run `fyr_baker_backend warmup` once on a worker thread.

    ``backend_env`` is computed by the caller on the main thread - building it
    reads addon preferences (RNA) - and the success stamp is handed back to the
    main thread through ``_post_main_thread_call``. This function must not touch
    ``bpy`` itself. It always posts exactly one call so the drain timer's pending
    count settles even when the warmup fails.
    """
    creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    creation_flags |= int(getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
    succeeded = False
    try:
        completed = subprocess.run(
            [str(backend_path), "warmup"],
            cwd=str(repo_root()),
            capture_output=True,
            text=True,
            creationflags=creation_flags,
            env=backend_env,
            timeout=60.0,
            **runtime_bake_worker.spawn_feedback_suppression_kwargs(subprocess),
        )
        succeeded = completed.returncode == 0
    except Exception:
        succeeded = False
    if succeeded:
        _post_main_thread_call(lambda: _apply_pso_priming_signature(signature))
    else:
        _post_main_thread_call(_noop_main_thread_call)


#: Shown while the backend build has not baked successfully on this machine yet: its first
#: bake compiles the GPU shaders for that build (about 90 s on an RTX 4070), which looks
#: like a hang to someone who just updated.
SHADER_COMPILE_NOTICE = (
    "First bake after an update: Fyr compiles its GPU shaders for this version. "
    "This takes a minute or two, once. Later bakes are fast."
)
_SHADER_NOTICE_CACHE: dict = {"at": 0.0, "pending": False}


def first_bake_after_update_pending() -> bool:
    """True until a bake on the current backend build has finished on this machine.

    Draw-safe: no probe, at most one stat every couple of seconds. False when Cycles is the
    renderer (nothing to compile) or the backend cannot be found.
    """
    now = time.monotonic()
    if now - float(_SHADER_NOTICE_CACHE["at"]) < 2.0:
        return bool(_SHADER_NOTICE_CACHE["pending"])
    pending = False
    try:
        prefs = preferences.get_preferences()
        if prefs is not None and preferences.normalize_render_backend_preference(
            getattr(prefs, "render_backend", None)
        ) != constants.RENDER_BACKEND_CYCLES:
            stamp = str(getattr(prefs, "backend_shaders_ready_signature", "") or "")
            pending = stamp != _backend_signature(resolve_backend_executable())
    except Exception:
        pending = False
    _SHADER_NOTICE_CACHE.update(at=now, pending=pending)
    return pending


def mark_backend_shaders_ready() -> None:
    """A bake on the current backend build finished: its shaders are compiled."""
    try:
        prefs = preferences.get_preferences()
        if prefs is None:
            return
        signature = _backend_signature(resolve_backend_executable())
        if str(getattr(prefs, "backend_shaders_ready_signature", "") or "") != signature:
            prefs.backend_shaders_ready_signature = signature
    except Exception:
        return
    _SHADER_NOTICE_CACHE.update(at=0.0, pending=False)


def request_pso_priming_once(*, force: bool = False) -> None:
    """Run the offline warmup subcommand on a worker thread the first time the
    addon sees a given backend executable. Idempotent.
    """
    global _PSO_PRIMING_REQUESTED
    if _PSO_PRIMING_REQUESTED and not force:
        return
    if preferences.resolve_backend_prewarm_mode() == constants.BACKEND_PREWARM_OFF and not force:
        return
    try:
        backend_path = resolve_backend_executable()
    except Exception:
        return
    if not backend_path or not Path(backend_path).exists():
        return
    signature = _backend_signature(backend_path)
    prefs = preferences.get_preferences()
    if not force and prefs is not None:
        if str(getattr(prefs, "backend_prewarm_pso_priming_signature", "") or "") == signature:
            _PSO_PRIMING_REQUESTED = True
            return
    _PSO_PRIMING_REQUESTED = True
    # Both bpy reads happen here, on the main thread: the env snapshot the worker
    # will pass to the subprocess, and arming the timer that will apply its result.
    backend_env = None
    try:
        backend_env = preferences.build_backend_env()
    except Exception:
        backend_env = None
    _arm_main_thread_call_timer()
    threading.Thread(
        target=_run_offline_warmup_blocking,
        args=(Path(backend_path), signature, backend_env),
        name="MasterBakerPsoPriming",
        daemon=True,
    ).start()


def _prewarm_log_root() -> Path:
    temp_root = Path(getattr(getattr(bpy, "app", None), "tempdir", "") or Path.cwd())
    path = temp_root / "fyr_baker_backend" / _PREWARM_LOG_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _prewarm_progress_path() -> Path:
    """Synthetic progress path for the prewarm worker.

    The bake worker only consults `progress_path` when a job is running, but
    `start_bake_worker` resolves a `backend_run.log` location from it for any
    eventual launch failure log.  Using a stable path under the per-session
    tempdir keeps prewarm logs grouped together and out of any real bake
    workspace.
    """
    return _prewarm_log_root() / "progress.json"


def _bake_worker_alive() -> bool:
    worker = _BAKE_WORKER
    if worker is None:
        return False
    process = getattr(worker, "process", None)
    if process is None:
        return False
    try:
        return process.poll() is None
    except Exception:
        return False


def is_bake_worker_warm() -> bool:
    """True when a resident bake worker process is alive and ready for RUN/PREPARE."""
    return _bake_worker_alive()


# Cache-state classification for the "why was my bake slow" UI badge. This is
# derived entirely from state the addon already tracks (worker liveness +
# which (pid, job_path) PREPARE was last issued for) — no backend protocol
# change. It does not know about internal C++ cache hits (e.g. BLAS/geometry
# pack), only the addon-level resident-worker/prepare distinction, which is
# the dominant factor per docs/MARMOSET_SPEED_PARITY_RESEARCH.md.
_CACHE_STATE_DISPLAY = {
    "cold": ("Cold (one-shot)", "RADIOBUT_OFF"),
    "warm_prepared": ("Warm (prepared)", "RADIOBUT_ON"),
    "warm_unprepared": ("Warm (loading)", "TIME"),
}


def classify_bake_cache_state(job_path: str | Path) -> str:
    """Classify whether `job_path` is about to hit a warm resident-worker cache.

    Returns one of:
      "cold"            - no resident worker; this bake pays full one-shot setup.
      "warm_prepared"   - resident worker alive and this exact job was pre-warmed
                          via PREPARE before RUN, so setup already overlapped.
      "warm_unprepared" - resident worker alive but this job wasn't pre-warmed;
                          RUN itself will pay any cache-miss cost synchronously.
    """
    if not is_bake_worker_warm():
        return "cold"
    worker = _BAKE_WORKER
    pid = int(getattr(getattr(worker, "process", None), "pid", 0) or 0)
    key = (pid, os.path.normcase(str(job_path)))
    if _PREPARE_ISSUED_FOR == key:
        return "warm_prepared"
    return "warm_unprepared"


def bake_cache_state_display(state: str) -> tuple[str, str]:
    """(label, icon) pair for a cache-state string, for the UI badge."""
    return _CACHE_STATE_DISPLAY.get(str(state or ""), ("", "QUESTION"))


def is_prepare_in_flight() -> bool:
    """True while a background PREPARE is loading scene caches before a bake.

    Callers can use this to show a 'Loading scene caches…' message instead of
    a bare 0% progress when the user presses Bake while PREPARE is still running.
    """
    return bool(_PREPARE_IN_FLIGHT)


def is_bake_started_during_prewarm() -> bool:
    """True when the active bake's RUN was queued while a prewarm PREPARE was still running.

    The RUN waits behind the in-flight PREPARE, so the bake sits at "Baking 0%" until the
    prewarm (high-scene BVH + GPU resource build) completes. The UI uses this to label that
    early wait as warming-up. Stays set until the next bake re-evaluates it; callers should
    gate on the bake being active and still at ~0% progress.
    """
    return bool(_BAKE_STARTED_DURING_PREWARM)


def prewarm_is_oom_recovery() -> bool:
    """True when the current prewarm is re-warming the scene cache after the
    backend was restarted to recover from an out-of-memory bake failure."""
    return bool(_PREWARM_IS_OOM_RECOVERY)


def clear_prewarm_oom_recovery() -> None:
    """Reset the OOM-recovery prewarm marker (call once a bake succeeds)."""
    global _PREWARM_IS_OOM_RECOVERY
    _PREWARM_IS_OOM_RECOVERY = False


def bake_worker_rss_bytes() -> int | None:
    """Resident (working-set) memory of the live resident bake worker, or None.

    The C++ worker keeps its per-bake working set (readback rings, OIDN host
    staging, seam-margin plans, host high-scene copies) resident as a high-water
    mark that does not shrink between bakes, so RSS ratchets upward across a
    session until a large allocation std::bad_alloc's. The memory watchdog reads
    this to recycle the worker before it exhausts system RAM."""
    worker = _BAKE_WORKER
    process = getattr(worker, "process", None) if worker is not None else None
    pid = getattr(process, "pid", None) if process is not None else None
    if not pid or (process is not None and process.poll() is not None):
        return None
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

            class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
            )
            if not handle:
                return None
            try:
                counters = _PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
                if ctypes.windll.psapi.GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb
                ):
                    return int(counters.WorkingSetSize)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
            return None
        # POSIX: field 2 of /proc/<pid>/statm is resident pages.
        with open(f"/proc/{pid}/statm", "r", encoding="ascii") as handle:
            resident_pages = int(handle.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return None


def _env_gb(name: str, default_gb: float) -> float:
    raw = str(os.environ.get(name, "") or "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0.0:
                return value
        except Exception:
            pass
    return default_gb


def worker_memory_recycle_decision() -> tuple[bool, str, bool]:
    """Decide whether to recycle the resident worker to reclaim host RAM.

    The resident worker's warm state (BVH, hits, packed geometry — often
    10-16 GB for a dense scene) is the WHOLE POINT: it makes bakes fast.
    Recycling it costs a ~20-24 s cold rebuild, so it must be a genuine
    imminent-OOM last resort, NOT a routine post-bake action. An earlier
    proactive rule fired at ~22% free RAM, which on a well-provisioned box
    that simply hovers near that line recycled the warm worker after *every*
    bake — the "constantly warming up scene cache" thrash. The mimalloc
    post-bake trim ([[project_worker_ram_leak_watchdog]]) already bounds the
    per-bake ratchet at the source, and a real bad_alloc is caught by the
    OOM-recovery restart path, so the watchdog can afford to be conservative.

    Returns (should_recycle, reason, is_critical). is_critical=True means free
    RAM is so low the recycle must happen even inside the cooldown window.
    All thresholds default to fractions of total RAM and are env-overridable."""
    rss = bake_worker_rss_bytes()
    if rss is None:
        return False, "", False
    gib = 1024 ** 3
    rss_gb = rss / gib
    measured = storage_cleanup.available_system_memory()
    if measured is None:
        return False, "", False
    free_gb = measured[0] / gib
    total_gb = measured[1] / gib
    # Runaway backstop: worker alone past ~45% of RAM regardless of what's free
    # — that is a genuine leak, not legitimate warm state.
    hard_cap_gb = _env_gb("FYR_BAKER_WORKER_RECYCLE_HARD_RSS_GB", max(24.0, 0.45 * total_gb))
    if rss_gb >= hard_cap_gb:
        return True, f"worker RSS {rss_gb:.1f} GB over hard cap {hard_cap_gb:.0f} GB", True
    # Genuine imminent-OOM only: free RAM below ~8% of total (a heavy bake's
    # transient working set is a few GB, so this leaves no headroom), and the
    # worker is a meaningful chunk to reclaim. Normal operation on a heavy scene
    # (10-16 GB resident, plenty of free RAM) must NOT trip this.
    min_rss_gb = _env_gb("FYR_BAKER_WORKER_RECYCLE_MIN_RSS_GB", 10.0)
    min_free_gb = _env_gb("FYR_BAKER_WORKER_RECYCLE_MIN_FREE_GB", max(5.0, 0.08 * total_gb))
    critical_free_gb = _env_gb("FYR_BAKER_WORKER_RECYCLE_CRITICAL_FREE_GB", max(3.0, 0.05 * total_gb))
    if rss_gb >= min_rss_gb and free_gb < min_free_gb:
        return True, (
            f"worker RSS {rss_gb:.1f} GB with only {free_gb:.1f} GB RAM free "
            f"(< {min_free_gb:.1f} GB), recycling before the next bake OOMs"
        ), free_gb < critical_free_gb
    return False, "", False


# Suppress repeat proactive recycles so a box that briefly dips under the free
# threshold can't thrash the warm worker; a genuinely critical dip bypasses it.
_LAST_WORKER_RECYCLE_AT: float = 0.0
_WORKER_RECYCLE_COOLDOWN_S: float = 120.0


def release_bake_worker_for_memory(reason: str = "") -> None:
    """Stop the resident worker to hand its memory back (its high-scene caches only
    speed up the next bake, which then prepares cold). No respawn here: the next
    bake or prewarm spawns a fresh worker on demand."""
    if _ACTIVE_BAKE is not None:
        return
    try:
        print(f"[fyr_baker] releasing bake worker for memory: {reason}")
    except Exception:
        pass
    _stop_bake_worker(terminate=True)


def maybe_recycle_worker_for_memory() -> bool:
    """Recycle the worker if its footprint threatens the next bake, then re-prewarm.

    Call from an *idle* point (a bake has just finalized), never mid-bake. Best
    effort — a failure here must never break bake finalization. Returns True when
    a recycle happened."""
    global _LAST_WORKER_RECYCLE_AT
    try:
        should, reason, is_critical = worker_memory_recycle_decision()
    except Exception:
        return False
    if not should:
        return False
    import time as _time
    now = _time.monotonic()
    if not is_critical and (now - _LAST_WORKER_RECYCLE_AT) < _WORKER_RECYCLE_COOLDOWN_S:
        # Recently recycled and not critical — skip to avoid post-bake thrash.
        return False
    try:
        print(f"[fyr_baker] worker-memory-watchdog recycle: {reason}")
    except Exception:
        pass
    try:
        restart_backend_worker()
        _LAST_WORKER_RECYCLE_AT = now
        return True
    except Exception:
        return False


def _record_last_successful_bake(state) -> None:
    """Capture the job path of a freshly completed successful bake.

    Called from the polling timer when a bake transitions to finished without
    errors, before `_clear_active_bake_state` resets `_ACTIVE_BAKE`.
    """
    global _LAST_SUCCEEDED_BAKE_JOB_PATH
    if state is None:
        return
    job_path = getattr(state, "job_path", None)
    if job_path is None:
        return
    try:
        candidate = Path(job_path)
    except Exception:
        return
    _LAST_SUCCEEDED_BAKE_JOB_PATH = candidate


_PREPARE_READY_TIMER_REGISTERED = False
_PREPARE_STARTED_AT: float = 0.0
#: Scene fingerprint (export.speculative_prepare_signature) of the PREPARE that
#: is currently in flight, and of the last one the worker actually acknowledged.
#: The speculative-prepare caller skips the whole export when the scene still
#: matches what the resident worker is primed for — without that gate any
#: repeating trigger (depsgraph churn, membership refresh, a post-bake refire)
#: re-exports an unchanged scene forever and the panel never leaves
#: "Warming up scene cache".
_PENDING_PREPARE_SIGNATURE: str = ""
_PREPARED_SCENE_SIGNATURE: str = ""
_STATUS_LOADING_CACHES = "Loading scene caches..."
_STATUS_SCENE_READY = "Scene ready"


def _mesh_prewarm_enabled_for_session() -> bool:
    return bool(preferences.backend_prewarm_prepare_meshes_enabled()) and not _MESH_PREWARM_DISABLED_FOR_SESSION


def _normalize_prepare_failure_message(error_text: str) -> str:
    text = str(error_text or "").strip()
    if text.lower().startswith("bake-failed error="):
        text = text.split("=", 1)[1].strip()
    return text or "worker exited before scene cache warmup completed"


def _clear_prepare_in_flight_status() -> None:
    """After PREPARE completes, update any project showing the loading status."""
    import time as _time
    elapsed = _time.monotonic() - _PREPARE_STARTED_AT if _PREPARE_STARTED_AT > 0.0 else 0.0
    if elapsed >= 60.0:
        elapsed_str = f"{elapsed / 60.0:.1f}m"
    else:
        elapsed_str = f"{elapsed:.1f}s"
    scene_ready_msg = f"Scene ready (prewarm: {elapsed_str})"
    print(f"[MasterBaker] PREPARE done, prewarm took {elapsed_str}")
    try:
        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None) if context is not None else None
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        if settings is None:
            return
        changed = False
        for project in getattr(settings, "projects", []) or []:
            msg = str(getattr(project, "last_status_message", "") or "")
            if msg == _STATUS_LOADING_CACHES:
                project.last_status_message = scene_ready_msg
                changed = True
        if str(getattr(settings, "status_message", "") or "") == _STATUS_LOADING_CACHES:
            # With no bake project in the file there is nothing the readiness
            # claim could apply to — clear the label instead of announcing
            # "Scene ready" for a project that doesn't exist.
            has_projects = bool(getattr(settings, "projects", []) or [])
            settings.status_message = scene_ready_msg if has_projects else ""
            changed = True
        if changed:
            try:
                from . import overlays as _overlays
                _overlays.tag_redraw_all_view3d(scene=scene)
            except Exception:
                pass
    except Exception:
        pass


def _set_prepare_failure_status(message: str) -> None:
    status_message = f"Scene-cache prewarm failed: {message}. Mesh prewarm disabled for this session."
    try:
        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None) if context is not None else None
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        if settings is None:
            return
        changed = False
        for project in getattr(settings, "projects", []) or []:
            msg = str(getattr(project, "last_status_message", "") or "")
            if msg == _STATUS_LOADING_CACHES:
                project.last_status_message = status_message
                changed = True
        if str(getattr(settings, "status_message", "") or "") == _STATUS_LOADING_CACHES:
            settings.status_message = status_message
            changed = True
        if changed:
            try:
                from . import overlays as _overlays
                _overlays.tag_redraw_all_view3d(scene=scene)
            except Exception:
                pass
    except Exception:
        pass


def _worker_exit_failure_text(stderr_text: str, returncode) -> str:
    """Why the worker died during a prewarm, for the status line.

    The last stderr line is usually an unrelated diagnostic: 2026-09-29 a worker killed for
    lack of system memory was reported as "Scene-cache prewarm failed: [worker] idle-release
    main-thread-collect private_after_mb=286". Only a line that reads as an error is quoted.
    """
    base = f"worker exited during scene cache warmup (exit code {returncode})"
    for line in reversed(str(stderr_text or "").splitlines()):
        text = line.strip()
        if not text or text.startswith("[worker]"):
            continue
        lowered = text.lower()
        if "error" in lowered or "fail" in lowered or "exception" in lowered:
            return f"{base}: {text}"
    return base


def _handle_prepare_failure(error_text: str) -> None:
    global _PREPARE_IN_FLIGHT, _MESH_PREWARM_DISABLED_FOR_SESSION, _LAST_PREWARM_FAILURE_MESSAGE
    global _PENDING_PREPARE_SIGNATURE, _PREPARED_SCENE_SIGNATURE
    _PREPARE_IN_FLIGHT = False
    _PENDING_PREPARE_SIGNATURE = ""
    _PREPARED_SCENE_SIGNATURE = ""
    _MESH_PREWARM_DISABLED_FOR_SESSION = True
    _LAST_PREWARM_FAILURE_MESSAGE = _normalize_prepare_failure_message(error_text)
    import time as _time
    elapsed = _time.monotonic() - _PREPARE_STARTED_AT if _PREPARE_STARTED_AT > 0.0 else 0.0
    elapsed_str = f"{elapsed / 60.0:.1f}m" if elapsed >= 60.0 else f"{elapsed:.1f}s"
    print(f"[MasterBaker] PREPARE failed after {elapsed_str}: {_LAST_PREWARM_FAILURE_MESSAGE}")
    _release_speculative_prepare_workspace()
    _set_prepare_failure_status(_LAST_PREWARM_FAILURE_MESSAGE)
    _stop_bake_worker(terminate=True)


def _release_speculative_prepare_workspace() -> None:
    global _SPECULATIVE_PREPARE_WORKSPACE_PATH
    workspace = _SPECULATIVE_PREPARE_WORKSPACE_PATH
    _SPECULATIVE_PREPARE_WORKSPACE_PATH = None
    if workspace is not None:
        try:
            _release_workspace_geometry_transports(workspace)
        except Exception:
            pass


def _prepare_ready_check_timer():
    global _PREPARE_IN_FLIGHT, _PREPARE_READY_TIMER_REGISTERED
    _PREPARE_READY_TIMER_REGISTERED = False
    if not _PREPARE_IN_FLIGHT:
        return None
    worker = _BAKE_WORKER
    if worker is None:
        _handle_prepare_failure("worker exited before scene cache warmup completed")
        return None
    response_queue = getattr(worker, "response_queue", None)
    if response_queue is not None:
        try:
            import queue as _queue_mod
            while True:
                candidate = response_queue.get_nowait()
                candidate_status = str(candidate.get("status", ""))
                # Replies carry the job path they answer; only accept ones for
                # the PREPARE we actually sent. A stray reply from a superseded
                # earlier command must not complete/fail this prepare — the
                # positional mismatch is what desynced bake reply matching.
                candidate_path = str(candidate.get("job_path", "") or "")
                if (
                    candidate_status in ("ready", "error")
                    and candidate_path
                    and _LAST_PREPARED_JOB_PATH is not None
                    and not runtime_bake_worker._worker_job_paths_equal(
                        candidate_path, _LAST_PREPARED_JOB_PATH
                    )
                ):
                    print(
                        "[MasterBaker] dropping stale worker reply during prewarm"
                        f" status={candidate_status} job_path={candidate_path}"
                        f" (expected: {_LAST_PREPARED_JOB_PATH})"
                    )
                    continue
                if candidate_status == "ready":
                    global _BG_PREPARE_STALE, _PREPARED_SCENE_SIGNATURE
                    _PREPARE_IN_FLIGHT = False
                    # The worker is now primed for the scene this PREPARE
                    # described; record it so an unchanged scene does not
                    # re-export and re-prewarm on the next trigger.
                    _PREPARED_SCENE_SIGNATURE = _PENDING_PREPARE_SIGNATURE
                    _release_speculative_prepare_workspace()
                    _clear_prepare_in_flight_status()
                    if _BG_PREPARE_STALE:
                        _BG_PREPARE_STALE = False
                        fn = _SPECULATIVE_PREPARE_CALLBACK
                        if fn is not None:
                            try:
                                fn()
                            except Exception:
                                pass
                    return None
                if candidate_status == "transport_error":
                    global _PREPARE_TRANSPORT_RETRY_COUNT
                    if (
                        bool(candidate.get("retryable", False))
                        and _PREPARE_TRANSPORT_RETRY_COUNT == 0
                        and _LAST_PREPARED_JOB_PATH is not None
                    ):
                        try:
                            retry_path = _build_geometry_transport_retry_job(
                                _LAST_PREPARED_JOB_PATH
                            )
                            _PREPARE_TRANSPORT_RETRY_COUNT = 1
                            _PREPARE_IN_FLIGHT = False
                            if _send_prepare_to_warm_worker(
                                retry_path, force=True, is_transport_retry=True
                            ):
                                return 0.5
                            raise RuntimeError(
                                "resident worker rejected the transport retry"
                            )
                        except Exception as retry_error:
                            _handle_prepare_failure(str(retry_error))
                            return None
                    _handle_prepare_failure(
                        str(
                            candidate.get("error", "")
                            or "geometry transport retry failed"
                        )
                    )
                    return None
                if candidate_status == "error":
                    _handle_prepare_failure(str(candidate.get("error", "") or "scene cache warmup failed"))
                    return None
                if candidate_status == "bye":
                    _handle_prepare_failure("worker exited during scene cache warmup")
                    return None
        except _queue_mod.Empty:
            pass
        except Exception:
            pass
    returncode = getattr(getattr(worker, "process", None), "poll", lambda: 1)()
    if returncode is not None:
        stderr_text = _read_text_if_exists(getattr(worker, "stderr_path", ""))
        _handle_prepare_failure(_worker_exit_failure_text(stderr_text, returncode))
        return None
    # READY not received yet. Keep the bake panel live so the "Warming up scene cache…" status
    # appears (and stays current) while the prewarm runs on file open — not only after Bake.
    try:
        from . import overlays as _overlays
        _overlays.tag_redraw_all_view3d(sync_preview=False)
    except Exception:
        pass
    _PREPARE_READY_TIMER_REGISTERED = True
    return 0.5


def _timer_still_registered(timers, callback) -> bool:
    """True when Blender still owns ``callback``.

    Non-persistent app timers are discarded on file load while the Python
    "registered" flags that guard their re-registration survive it. A guard that
    trusts the flag alone then becomes a permanent no-op for the session, so every
    guard cross-checks with Blender before honouring the flag. When ``is_registered``
    is unavailable, trust the flag.
    """
    try:
        if hasattr(timers, "is_registered"):
            return bool(timers.is_registered(callback))
    except Exception:
        pass
    return True


def _schedule_prepare_ready_check() -> None:
    global _PREPARE_READY_TIMER_REGISTERED
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    if _PREPARE_READY_TIMER_REGISTERED:
        if _timer_still_registered(timers, _prepare_ready_check_timer):
            return
        _PREPARE_READY_TIMER_REGISTERED = False
    _PREPARE_READY_TIMER_REGISTERED = True
    try:
        timers.register(_prepare_ready_check_timer, first_interval=0.5)
    except Exception:
        _PREPARE_READY_TIMER_REGISTERED = False


_PREPARE_MEMORY_SKIP_LOGGED: str = ""


def _speculative_prepare_fits_memory(job_path) -> bool:
    """A speculative PREPARE loads the whole high-poly into the worker (SvAT: 22.9 GB)
    while Blender still holds it too; on a machine without that much commit left it
    pushes the system into the pagefile or out of memory before anyone pressed Bake.
    Skip it then: the bake prepares on demand, after high_poly_park has freed
    Blender's copy."""
    global _PREPARE_MEMORY_SKIP_LOGGED
    try:
        from . import high_mesh_cache, high_poly_park

        scene = getattr(getattr(bpy, "context", None), "scene", None)
        objects = list(high_mesh_cache._iter_scene_high_objects(scene)) if scene is not None else []
        largest_group = 0
        settings = getattr(scene, "fyr_baker_settings", None)
        for project in getattr(settings, "projects", []):
            for group in getattr(project, "groups", []):
                slots = properties.effective_high_mesh_slots(group)
                largest_group = max(largest_group, high_poly_park.triangle_count(
                    [getattr(slot, "object_ref", None) for slot in slots]))
        park, reason = high_poly_park.should_park(
            objects, largest_group_triangles=largest_group, record=False)
    except Exception:
        return True
    if not park:
        return True
    key = os.path.normcase(str(job_path))
    if _PREPARE_MEMORY_SKIP_LOGGED != key:
        _PREPARE_MEMORY_SKIP_LOGGED = key
        print(f"[Fyr Baker] speculative prepare skipped: not enough free memory ({reason})")
    return False


def _send_prepare_to_warm_worker(
    job_path: Path,
    *,
    force: bool = False,
    is_transport_retry: bool = False,
) -> bool:
    """Write a `PREPARE\\t<job_path>` command to the resident worker stdin.

    Returns True when the command was written successfully, False otherwise.
    Idempotent against (worker_pid, job_path); the second call for the same
    pair is a no-op so we don't redundantly load the same scene.
    """
    global _PREPARE_ISSUED_FOR
    worker = _BAKE_WORKER
    if worker is None:
        return False
    process = getattr(worker, "process", None)
    if process is None:
        return False
    try:
        if process.poll() is not None:
            return False
    except Exception:
        return False
    stdin_handle = getattr(worker, "stdin_handle", None)
    if stdin_handle is None:
        return False
    pid = int(getattr(process, "pid", 0) or 0)
    key = (pid, os.path.normcase(str(job_path)))
    if _PREPARE_ISSUED_FOR == key and not force:
        return False
    if _ACTIVE_BAKE is not None:
        # Don't interleave PREPARE with an in-flight RUN; the worker will
        # serialize commands but the user-facing latency is what we care
        # about and the cache will be loaded by the RUN itself anyway.
        return False
    if not force and not _speculative_prepare_fits_memory(job_path):
        return False
    try:
        stdin_handle.write(f"PREPARE\t{job_path}\n")
        stdin_handle.flush()
    except Exception:
        return False
    _PREPARE_ISSUED_FOR = key
    global _LAST_PREPARED_JOB_PATH
    _LAST_PREPARED_JOB_PATH = job_path
    global _PREPARE_IN_FLIGHT, _PREPARE_STARTED_AT, _PREPARE_TRANSPORT_RETRY_COUNT
    import time as _time
    _PREPARE_IN_FLIGHT = True
    if not is_transport_retry:
        _PREPARE_TRANSPORT_RETRY_COUNT = 0
    _PREPARE_STARTED_AT = _time.monotonic()
    if not is_transport_retry:
        # A retry re-sends the SAME scene, so it keeps the pending fingerprint.
        # Any other send describes a different scene than the caller that set it;
        # send_prepare_for_job re-stamps it right after this returns.
        global _PENDING_PREPARE_SIGNATURE
        _PENDING_PREPARE_SIGNATURE = ""
    _schedule_prepare_ready_check()
    return True


def _maybe_send_prepare_for_last_bake() -> bool:
    """If a remembered last-successful-bake job exists on disk, send PREPARE."""
    job_path = _LAST_SUCCEEDED_BAKE_JOB_PATH
    if job_path is None:
        return False
    try:
        if not job_path.exists():
            return False
    except Exception:
        return False
    return _send_prepare_to_warm_worker(job_path)


# --- Activity-driven GPU keep-warm -------------------------------------------
#
# When the user changes a bake setting we want the next bake to start warm:
#  * the resident BVH/geometry stays pinned in VRAM (no re-page-in), and
#  * the GPU clocks are spun up (the first heavy dispatch after idle otherwise
#    ramps from idle clocks, ~2-3s slower on the first group).
# The only non-admin way to raise GPU clocks is to RUN real GPU work, so the
# backend's WARMKEEP_ARM handler re-pins residency AND fires a short ray-warmup
# burst. After ~3 min of no activity we send WARMKEEP_DISARM so the OS can
# reclaim the VRAM. We never spawn a worker just to warm — keep-warm is a no-op
# unless a resident worker and a known prepared job already exist.


def _resolve_warmkeep_job_path() -> Path | None:
    """Best known job path to warm against: the most recent PREPARE'd job, then
    the last successful bake. Returns None when neither is available on disk."""
    for candidate in (_LAST_PREPARED_JOB_PATH, _LAST_SUCCEEDED_BAKE_JOB_PATH):
        if candidate is None:
            continue
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue
    return None


def _write_warmkeep_command(command: str, job_path: Path) -> bool:
    """Write a `<command>\\t<job_path>\\n` line to the resident worker stdin.

    `command` is WARMKEEP_ARM or WARMKEEP_DISARM. Silent no-op (returns False)
    if there is no live worker, no stdin, or a bake is in flight. Never raises.
    """
    worker = _BAKE_WORKER
    if worker is None:
        return False
    process = getattr(worker, "process", None)
    if process is None:
        return False
    try:
        if process.poll() is not None:
            return False
    except Exception:
        return False
    stdin_handle = getattr(worker, "stdin_handle", None)
    if stdin_handle is None:
        return False
    if _ACTIVE_BAKE is not None:
        # Don't interleave keep-warm with an in-flight RUN; the bake itself keeps
        # the GPU hot, and we don't want a warmup dispatch contending with it.
        return False
    try:
        stdin_handle.write(f"{command}\t{job_path}\n")
        stdin_handle.flush()
    except Exception:
        return False
    return True


def _warmkeep_arm_timer():
    """Trailing-edge debounce: actually send WARMKEEP_ARM after activity settles."""
    global _WARMKEEP_ARM_TIMER_REGISTERED, _WARMKEEP_ARMED
    _WARMKEEP_ARM_TIMER_REGISTERED = False
    try:
        if _ACTIVE_BAKE is not None:
            return None
        if not _bake_worker_alive():
            return None
        job_path = _resolve_warmkeep_job_path()
        if job_path is None:
            return None
        if _write_warmkeep_command("WARMKEEP_ARM", job_path):
            _WARMKEEP_ARMED = True
            _schedule_warmkeep_idle_check()
    except Exception:
        pass
    return None


def schedule_warmkeep_arm(reason: str = "") -> None:
    """Record activity and (debounced) re-warm the GPU for the next bake.

    Called on every bake-setting change. Resets the idle timer and coalesces
    rapid changes (e.g. dragging a slider / typing) into a single trailing-edge
    WARMKEEP_ARM. Fully guarded: a missing worker or unknown job is a no-op and
    nothing here ever raises into Blender.
    """
    global _WARMKEEP_LAST_ACTIVITY_AT, _WARMKEEP_ARM_TIMER_REGISTERED
    try:
        mode = preferences.resolve_backend_prewarm_mode()
        if mode == constants.BACKEND_PREWARM_OFF:
            return
        _WARMKEEP_LAST_ACTIVITY_AT = time.monotonic()
        # Only warm when a resident worker + a known prepared job already exist;
        # never spawn a worker just to warm.
        if not _bake_worker_alive():
            return
        if _resolve_warmkeep_job_path() is None:
            return
        timers = getattr(getattr(bpy, "app", None), "timers", None)
        if timers is None or not hasattr(timers, "register"):
            return
        if _WARMKEEP_ARM_TIMER_REGISTERED:
            # Already queued; the trailing-edge timer will pick up the refreshed
            # activity timestamp when it fires.
            if _timer_still_registered(timers, _warmkeep_arm_timer):
                return
            _WARMKEEP_ARM_TIMER_REGISTERED = False
        _WARMKEEP_ARM_TIMER_REGISTERED = True
        try:
            timers.register(_warmkeep_arm_timer, first_interval=_WARMKEEP_ARM_DEBOUNCE_SECONDS)
        except Exception:
            _WARMKEEP_ARM_TIMER_REGISTERED = False
    except Exception:
        pass


def _warmkeep_idle_timer():
    """Periodic idle poll: after _WARMKEEP_IDLE_SECONDS of no activity, disarm once."""
    global _WARMKEEP_IDLE_TIMER_REGISTERED, _WARMKEEP_ARMED
    try:
        if not _WARMKEEP_ARMED:
            _WARMKEEP_IDLE_TIMER_REGISTERED = False
            return None
        if not _bake_worker_alive():
            # Worker gone — nothing to disarm; the residency died with it.
            _WARMKEEP_ARMED = False
            _WARMKEEP_IDLE_TIMER_REGISTERED = False
            return None
        idle_for = time.monotonic() - _WARMKEEP_LAST_ACTIVITY_AT
        if idle_for >= _WARMKEEP_IDLE_SECONDS and _ACTIVE_BAKE is None:
            job_path = _resolve_warmkeep_job_path()
            if job_path is not None:
                _write_warmkeep_command("WARMKEEP_DISARM", job_path)
            _WARMKEEP_ARMED = False
            _WARMKEEP_IDLE_TIMER_REGISTERED = False
            return None
    except Exception:
        _WARMKEEP_IDLE_TIMER_REGISTERED = False
        return None
    # Still armed and not yet idle — keep polling.
    return _WARMKEEP_IDLE_POLL_SECONDS


def _schedule_warmkeep_idle_check() -> None:
    global _WARMKEEP_IDLE_TIMER_REGISTERED
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    if _WARMKEEP_IDLE_TIMER_REGISTERED:
        if _timer_still_registered(timers, _warmkeep_idle_timer):
            return
        _WARMKEEP_IDLE_TIMER_REGISTERED = False
    _WARMKEEP_IDLE_TIMER_REGISTERED = True
    try:
        timers.register(_warmkeep_idle_timer, first_interval=_WARMKEEP_IDLE_POLL_SECONDS)
    except Exception:
        _WARMKEEP_IDLE_TIMER_REGISTERED = False


def _speculative_prepare_timer():
    global _SPECULATIVE_PREPARE_TIMER_REGISTERED
    _SPECULATIVE_PREPARE_TIMER_REGISTERED = False
    if _ACTIVE_BAKE is not None:
        return None
    if _viewport_cage_fits_pending():
        # The cages the artist is looking at come first: the prewarm's high-mesh captures
        # (seconds each on a dense gun) ran between the cage fits on the same thread and
        # roughly doubled how long the cages took to appear. Retry once they are done.
        _SPECULATIVE_PREPARE_TIMER_REGISTERED = True
        return 1.0
    if not _mesh_prewarm_enabled_for_session():
        return None
    if not _bake_worker_alive():
        return None
    fn = _SPECULATIVE_PREPARE_CALLBACK
    if fn is None:
        return None
    try:
        fn()
    except Exception:
        pass
    return None


def _viewport_cage_fits_pending() -> bool:
    try:
        from . import auto_cage_fit_queue, distance_offset_queue

        return bool(auto_cage_fit_queue.pending_count() or distance_offset_queue.pending_count())
    except Exception:
        return False


def restart_backend_worker(*, oom_recovery: bool = False) -> None:
    """Terminate the resident bake backend and immediately schedule a fresh
    speculative prepare so a new worker spawns and re-runs the scene prewarm.
    Testing hook (Restart Backend button): lets the user eject the backend from
    the UI and measure a cold prewarm/bake without restarting Blender.

    oom_recovery=True marks the ensuing prewarm as an out-of-memory recovery so
    the UI can explain why the scene cache is warming up again."""
    global _MESH_PREWARM_DISABLED_FOR_SESSION, _LAST_PREWARM_FAILURE_MESSAGE
    global _PREWARM_IS_OOM_RECOVERY
    _PREWARM_IS_OOM_RECOVERY = bool(oom_recovery)
    _stop_bake_worker(terminate=True)
    # A previous prepare failure (e.g. the old worker was killed externally)
    # latches prewarm off for the rest of the session; a manual restart is an
    # explicit request for a fresh prewarm, so clear the latch first.
    _MESH_PREWARM_DISABLED_FOR_SESSION = False
    _LAST_PREWARM_FAILURE_MESSAGE = ""
    # ensure_bake_worker_prewarmed spawns the fresh worker AND primes it via
    # PREPARE (the speculative timer alone only prepares an already-live
    # worker — it never spawns one).
    ensure_bake_worker_prewarmed(reason="manual-restart")


def schedule_speculative_prepare(
    delay: float = 0.25,
    restart: bool = False,
    *,
    allow_cold_high_warm: bool = True,
) -> None:
    """Schedule a one-shot timer that will export a probe job and send PREPARE to the
    warm worker.  Safe to call when the worker is already alive or just spawning.

    restart=True debounces from the LAST call instead of the first: an already
    pending timer is cancelled and re-registered with the fresh delay. Use this
    for high-frequency triggers (e.g. dragging a samples slider fires a property
    update per step) so the export runs once, after the user settles, with the
    final value.

    allow_cold_high_warm=False refuses to capture unevaluated multi-million highs
    on the main thread (settings-change path). Geometry warm stays on file-open,
    membership changes, and explicit bake.
    """
    global _SPECULATIVE_PREPARE_TIMER_REGISTERED
    global _SPECULATIVE_PREPARE_ALLOW_COLD_HIGH_WARM
    if _SPECULATIVE_PREPARE_CALLBACK is None:
        return
    if not _mesh_prewarm_enabled_for_session():
        return
    if restart or not _SPECULATIVE_PREPARE_TIMER_REGISTERED:
        _SPECULATIVE_PREPARE_ALLOW_COLD_HIGH_WARM = bool(allow_cold_high_warm)
    elif not allow_cold_high_warm:
        # Pending timer from a colder-friendly caller: keep the stricter flag.
        _SPECULATIVE_PREPARE_ALLOW_COLD_HIGH_WARM = False
    if _SPECULATIVE_PREPARE_TIMER_REGISTERED:
        if not restart:
            return
        timers = getattr(getattr(bpy, "app", None), "timers", None)
        if timers is not None and hasattr(timers, "unregister"):
            try:
                timers.unregister(_speculative_prepare_timer)
            except Exception:
                pass
        _SPECULATIVE_PREPARE_TIMER_REGISTERED = False
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    _SPECULATIVE_PREPARE_TIMER_REGISTERED = True
    try:
        timers.register(_speculative_prepare_timer, first_interval=delay)
    except Exception:
        _SPECULATIVE_PREPARE_TIMER_REGISTERED = False


def reset_prepare_state_for_file_load() -> None:
    """Forget a PREPARE that belonged to the file being closed.

    _PREPARE_IN_FLIGHT is only ever cleared by _prepare_ready_check_timer, and that
    timer is non-persistent, so a file load drops it. Nothing re-arms it either:
    ensure_bake_worker_prewarmed only re-issues PREPARE when the worker just came
    up (`alive and not was_alive`), and the worker survives a file load. So a load
    during a prewarm latched the flag True for the rest of the session -- the bake
    panel sat on "Warming up scene cache" with an elapsed time counting from the
    PREVIOUS file's prepare, every speculative prepare in the new file bailed on
    is_prepare_in_flight(), so the first real bake there was cold, and the closed
    file's workspace sections (hundreds of MB to GB) stayed committed. Pressing
    Bake cleared it by accident, and mislabelled that bake as "started during
    prewarm" for the prewarm that ended with the other file.
    """
    global _PREPARE_IN_FLIGHT, _BG_PREPARE_STALE, _PREPARE_STARTED_AT
    # Forgetting it is not enough: the worker keeps building the closed file's
    # scenes unless told to stop. load_pre normally did this already (then this
    # is a no-op); load_post repeats it in case load_pre never ran (2026-09-26).
    cancel_prepare_for_closing_file()
    _PREPARE_IN_FLIGHT = False
    _BG_PREPARE_STALE = False
    _PREPARE_STARTED_AT = 0.0
    # The prepared caches describe the file that just closed.
    _release_speculative_prepare_workspace()


def cancel_speculative_prepare() -> None:
    """Cancel the one-shot scene-prepare timer, including during add-on reload."""
    global _SPECULATIVE_PREPARE_TIMER_REGISTERED
    global _SPECULATIVE_PREPARE_ALLOW_COLD_HIGH_WARM

    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "unregister"):
        should_unregister = _SPECULATIVE_PREPARE_TIMER_REGISTERED
        if hasattr(timers, "is_registered"):
            try:
                should_unregister = bool(timers.is_registered(_speculative_prepare_timer))
            except Exception:
                pass
        if should_unregister:
            try:
                timers.unregister(_speculative_prepare_timer)
            except Exception:
                pass
    _SPECULATIVE_PREPARE_TIMER_REGISTERED = False
    _SPECULATIVE_PREPARE_ALLOW_COLD_HIGH_WARM = True


def speculative_prepare_allows_cold_high_warm() -> bool:
    return bool(_SPECULATIVE_PREPARE_ALLOW_COLD_HIGH_WARM)


def set_speculative_prepare_callback(fn) -> None:
    global _SPECULATIVE_PREPARE_CALLBACK
    _SPECULATIVE_PREPARE_CALLBACK = fn


def set_speculative_prepare_workspace(workspace_path) -> None:
    """Record the workspace path of the in-flight speculative export so shared
    memory can be released once the worker sends READY."""
    global _SPECULATIVE_PREPARE_WORKSPACE_PATH
    _SPECULATIVE_PREPARE_WORKSPACE_PATH = Path(workspace_path) if workspace_path else None


def send_prepare_for_job(job_path, *, scene_signature: str = "") -> bool:
    """Send PREPARE for the given job path to the warm worker (public API for operators).

    `scene_signature` is the caller's fingerprint of the scene this job was
    exported from; it is committed to `prepared_scene_signature()` once the
    worker replies READY.
    """
    global _PENDING_PREPARE_SIGNATURE
    sent = _send_prepare_to_warm_worker(Path(job_path))
    if sent:
        _PENDING_PREPARE_SIGNATURE = str(scene_signature or "")
    return sent


def prepared_scene_signature() -> str:
    """Scene fingerprint the resident worker's caches are currently primed for.

    Empty when nothing is prepared, when the fingerprint is unknown, or when the
    worker died (its caches went with it), so callers fall through to preparing.
    """
    if not _bake_worker_alive():
        return ""
    return _PREPARED_SCENE_SIGNATURE


def forget_prepared_scene_signature() -> None:
    """Drop the prepared-scene fingerprint so the next trigger prepares again."""
    global _PENDING_PREPARE_SIGNATURE, _PREPARED_SCENE_SIGNATURE
    _PENDING_PREPARE_SIGNATURE = ""
    _PREPARED_SCENE_SIGNATURE = ""


def cancel_inflight_prepare_for_bake() -> bool:
    """Abort the in-flight speculative PREPARE because the user pressed Bake.

    The RUN queues behind the PREPARE on the worker's stdin, so a prewarm that
    no longer matches the bake (settings changed since it was issued) would
    make the user sit at "Warming up scene cache" for its full duration
    (observed live: 25s at 2X/2048 before the user gave up and cancelled).
    Writing the job's cancel.request file makes the worker's PREPARE abort at
    its next phase boundary; completed groups keep their caches, the worker
    replies READY, and the queued RUN re-prepares only what is missing."""
    global _BG_PREPARE_STALE
    if not _PREPARE_IN_FLIGHT or _LAST_PREPARED_JOB_PATH is None:
        return False
    if not _write_prepare_cancel_request(_LAST_PREPARED_JOB_PATH, "superseded by bake"):
        return False
    # The stale-refire would immediately re-send a speculative PREPARE ahead of
    # the bake's RUN; the bake itself warms everything it needs.
    _BG_PREPARE_STALE = False
    # This PREPARE stops at the next phase boundary and still replies READY, so
    # it must not claim the scene is fully primed — the RUN behind it finishes
    # the job, and the post-bake prepare re-primes from a clean slate.
    global _PENDING_PREPARE_SIGNATURE
    _PENDING_PREPARE_SIGNATURE = ""
    print("[MasterBaker] cancelling in-flight prewarm (bake pressed)")
    return True


def _write_bake_pending_notice(worker, notice: str) -> bool:
    stdin_handle = getattr(worker, "stdin_handle", None)
    if stdin_handle is None:
        return False
    try:
        stdin_handle.write(notice)
        stdin_handle.flush()
    except Exception:
        return False
    return True


def notify_worker_bake_pending(map_types=()) -> bool:
    """Tell the resident worker a RUN follows once the job export ends, and which
    maps the press selected. Idle work stays off the bake, and a selection that
    binds the megakernel starts its background compile now. With no worker the
    notice waits for the next start. No reply. Never raises."""
    global _PENDING_BAKE_NOTICE
    names = ",".join(str(name) for name in map_types if name)
    notice = f"BAKE_PENDING\t-\tMAPS={names}\n" if names else "BAKE_PENDING\n"
    if not _bake_worker_alive():
        _PENDING_BAKE_NOTICE = notice
        return False
    _PENDING_BAKE_NOTICE = ""
    return _write_bake_pending_notice(_BAKE_WORKER, notice)


def _write_prepare_cancel_request(job_path, reason: str) -> bool:
    """Drop cancel.request next to a PREPARE'd job; False when it could not be written.

    The worker's PREPARE polls `<progress_path parent>/cancel.request`, and a
    speculative job writes progress.json beside its job file, so the job's own
    directory is the one it watches."""
    try:
        cancel_path = Path(job_path).parent / "cancel.request"
        cancel_path.write_text(str(reason or "cancelled"), encoding="utf-8")
    except Exception:
        return False
    return True


def _prepare_cancel_would_hit_active_bake(job_path) -> bool:
    """True when a cancel.request for ``job_path`` would land in a RUN's directory.

    The file is scoped by directory, not by command, so one written where the
    user's own bake polls would stop that bake. A RUN without a known progress
    path is treated as a hit: skipping a prewarm cancel costs time, cancelling a
    bake costs the user's work."""
    state = _ACTIVE_BAKE
    if state is None:
        return False
    progress_path = getattr(state, "progress_path", None)
    if not progress_path:
        return True
    try:
        return _workspace_retry_key(Path(progress_path).parent) == _workspace_retry_key(
            Path(job_path).parent
        )
    except Exception:
        return True


def cancel_prepare_for_closing_file() -> bool:
    """Stop prewarm work that belongs to the .blend being closed. Returns True
    when an in-flight PREPARE was asked to cancel.

    Measured 2026-09-26: SvAT.blend (88M triangles) queued a PREPARE, then
    BakeTester3.blend was opened. The closed file's PREPARE kept running in the
    resident worker -- a 41.4M-triangle high scene for ~30s, 45.9 GB of commit --
    and the new file's first bake waited ~133s behind it on the worker's stdin.
    Resetting the add-on's flags on load (reset_prepare_state_for_file_load) only
    forgot that PREPARE; the worker never heard about it.

    Uses the cancel path the worker already honours for PREPARE (the one
    cancel_inflight_prepare_for_bake writes): it aborts at the next phase
    boundary, keeps completed groups, and still replies READY, which the new
    file's ready-check drops by job path. Only background prewarm is touched: a
    user-started RUN is never cancelled from here. Called from load_pre, so it
    must stay cheap -- no waits, no workspace release (load_post does that).
    Idempotent, and a no-op without a live worker."""
    global _BG_PREPARE_STALE, _PENDING_PREPARE_SIGNATURE
    global _LAST_PREPARED_JOB_PATH, _LAST_SUCCEEDED_BAKE_JOB_PATH
    # The post-READY refire would re-export whatever scene is open by then.
    _BG_PREPARE_STALE = False
    in_flight_job = _LAST_PREPARED_JOB_PATH if _PREPARE_IN_FLIGHT else None
    # Both paths name the closed file's jobs. A worker respawn PREPAREs
    # _LAST_SUCCEEDED_BAKE_JOB_PATH, and keep-warm ARM/DISARM run
    # prepare_bake_group_data for the resolved path with no cancel hook, so either
    # would rebuild the closed file's high scenes inside the new file's session.
    _LAST_SUCCEEDED_BAKE_JOB_PATH = None
    _LAST_PREPARED_JOB_PATH = None
    _cancel_warmkeep_arm_timer()
    if in_flight_job is None or not _bake_worker_alive():
        return False
    if _prepare_cancel_would_hit_active_bake(in_flight_job):
        return False
    if not _write_prepare_cancel_request(in_flight_job, "file closed"):
        return False
    # It stops early but still replies READY; never let that claim a primed scene.
    _PENDING_PREPARE_SIGNATURE = ""
    print("[MasterBaker] cancelling in-flight prewarm (file closed)")
    return True


def _cancel_warmkeep_arm_timer() -> None:
    """Drop a debounced WARMKEEP_ARM that has not been written to the worker yet."""
    global _WARMKEEP_ARM_TIMER_REGISTERED
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "unregister"):
        should_unregister = _WARMKEEP_ARM_TIMER_REGISTERED
        if hasattr(timers, "is_registered"):
            try:
                should_unregister = bool(timers.is_registered(_warmkeep_arm_timer))
            except Exception:
                pass
        if should_unregister:
            try:
                timers.unregister(_warmkeep_arm_timer)
            except Exception:
                pass
    _WARMKEEP_ARM_TIMER_REGISTERED = False


def prepare_in_flight_status_label() -> str:
    """The exact status string written to project.last_status_message while PREPARE is running."""
    return _STATUS_LOADING_CACHES


def prewarm_elapsed_str() -> str:
    """Human-readable elapsed time since PREPARE was issued (empty string if not in flight)."""
    if not _PREPARE_IN_FLIGHT or _PREPARE_STARTED_AT <= 0.0:
        return ""
    import time as _time
    elapsed = _time.monotonic() - _PREPARE_STARTED_AT
    if elapsed >= 60.0:
        return f"{elapsed / 60.0:.1f}m"
    return f"{elapsed:.0f}s"


def format_duration(seconds: float) -> str:
    """Canonical compact elapsed-time formatter shared by the bake timer and the UI.

    Sub-minute -> "12.3s"; minute-range -> "1m 23s"; hour-plus -> "1h 05m".
    Returns "" for non-positive/invalid input so callers can skip the label.
    """
    try:
        total = float(seconds)
    except Exception:
        return ""
    if total <= 0.0:
        return ""
    if total < 60.0:
        return f"{total:.1f}s"
    if total < 3600.0:
        minutes = int(total // 60)
        secs = int(round(total - minutes * 60))
        if secs >= 60:
            minutes += 1
            secs = 0
        return f"{minutes}m {secs:02d}s"
    hours = int(total // 3600)
    minutes = int((total - hours * 3600) // 60)
    return f"{hours}h {minutes:02d}m"


# --- Removed-item undo stash ----------------------------------------------------
# Single-slot, in-memory serialization of the most recently removed piece of a bake
# project: the project itself, a bake group, a map row, a texture set, or one role
# (low/high) mesh slot.
#
# None of those ops can carry {"UNDO"}: a memfile-undo step reallocates the whole
# fyr_baker_settings IDProperty and dangles retained custom-panel text buttons bound
# to per-project data (Blender T74067). So each destructive op stashes a payload here
# and one restore operator pops it back — a crash-free "undo remove" that never
# touches Blender's global undo stack.
#
# ONE slot on purpose, not one per kind. It is what guarantees the sidebar can only
# ever offer a single "Undo Remove" row: a second removal (or any structural action
# that calls clear_removed_item_stash) retires the previous offer, exactly as the
# project stash behaved on its own.
STASH_KIND_PROJECT = "PROJECT"
STASH_KIND_GROUP = "GROUP"
STASH_KIND_MAP = "MAP"
STASH_KIND_TEXTURE_SET = "TEXTURE_SET"
STASH_KIND_ROLE_SLOT = "ROLE_SLOT"

_REMOVED_ITEM_STASH = None


def stash_removed_item(kind: str, payload, *, label: str = "", location=None) -> None:
    """Hold a just-removed item so the removal can be undone.

    ``payload`` is the serialization the restore operator replays; ``location`` is
    everything needed to put it back where it was (project name, index, texture-set
    membership, role). A ``payload`` of ``None`` clears the stash: a serialization
    that failed must not leave a Restore button that cannot restore anything.
    """
    global _REMOVED_ITEM_STASH
    if payload is None:
        _REMOVED_ITEM_STASH = None
        return
    _REMOVED_ITEM_STASH = {
        "kind": str(kind or ""),
        "label": str(label or ""),
        "payload": payload,
        "location": dict(location or {}),
    }


def peek_removed_item(kind: str | None = None):
    """The stashed entry, or None when nothing is stashed / the kind does not match."""
    entry = _REMOVED_ITEM_STASH
    if entry is None:
        return None
    if kind is not None and entry.get("kind") != kind:
        return None
    return entry


def has_removed_item(kind: str | None = None) -> bool:
    return peek_removed_item(kind) is not None


def removed_item_undo_label(kind: str | None = None, **location_match) -> str:
    """The button text for the pending undo, or "" when there is nothing to offer.

    ``location_match`` narrows by stashed location, so a per-role list can ask for
    "the undo that belongs to MY role" and stay blank for the sibling list.
    """
    entry = peek_removed_item(kind)
    if entry is None:
        return ""
    location = entry.get("location") or {}
    for key, value in location_match.items():
        if location.get(key) != value:
            return ""
    return str(entry.get("label", "") or "")


def pop_removed_item(kind: str | None = None):
    """Return the stashed entry (clearing it) or None when the kind does not match."""
    global _REMOVED_ITEM_STASH
    entry = peek_removed_item(kind)
    if entry is None:
        return None
    _REMOVED_ITEM_STASH = None
    return entry


def clear_removed_item_stash() -> None:
    """Drop the pending Undo Remove payload.

    Called from two places: a file load (the stash is process-global while the payload
    belongs to one .blend, so the sidebar must not offer to restore an item into a
    different scene), and every structural action that means the artist has moved past
    the removal. Leaving it armed after an add offered "Undo Remove 'X'" next to a live
    X and then ADDED a second same-named item instead of undoing anything (RC sweep
    2026-08-29, finding 2).
    """
    global _REMOVED_ITEM_STASH
    _REMOVED_ITEM_STASH = None


# --- Project-shaped wrappers ----------------------------------------------------
# remove_project / restore_removed_project predate the generic stash and keep their
# own names; they are the same single slot underneath.


def stash_removed_project(payload) -> None:
    """Hold the payload of a just-removed project so the removal can be undone."""
    name = ""
    try:
        name = str((payload or {}).get("name", "") or "")
    except AttributeError:
        name = ""
    stash_removed_item(
        STASH_KIND_PROJECT,
        payload,
        label=f"Undo Remove '{name}'" if name else "Undo Remove Project",
    )


def has_removed_project() -> bool:
    return has_removed_item(STASH_KIND_PROJECT)


def peek_removed_project_name() -> str:
    entry = peek_removed_item(STASH_KIND_PROJECT)
    if entry is None:
        return ""
    try:
        return str((entry.get("payload") or {}).get("name", "") or "")
    except AttributeError:
        return ""


def pop_removed_project():
    """Return the stashed project payload (clearing it) or None if nothing is stashed."""
    entry = pop_removed_item(STASH_KIND_PROJECT)
    return entry.get("payload") if entry else None


def clear_removed_project_stash() -> None:
    """Legacy alias kept for legacy_cleanup's load_post handler."""
    clear_removed_item_stash()


def flag_bg_prepare_stale() -> None:
    """Mark that a bake-relevant change arrived while PREPARE was in flight.
    _prepare_ready_check_timer will re-trigger the speculative-prepare callback on READY."""
    global _BG_PREPARE_STALE
    _BG_PREPARE_STALE = True


def fyr_native_lifecycle_enabled() -> bool:
    """False when Cycles owns baking; prewarm and the FYR worker must stay down."""
    try:
        from . import bake_backends

        return bake_backends.fyr_native_lifecycle_enabled()
    except Exception:
        return False


def ensure_bake_worker_prewarmed(reason: str = "") -> bool:
    """Idempotently spawn the resident bake worker for prewarm.

    Returns True when a live worker is available after the call (whether already
    running or freshly spawned). Errors are swallowed so prewarm never blocks
    the addon's normal lifecycle - a real bake will surface them.
    """
    del reason  # Reserved for future structured logging.
    if not fyr_native_lifecycle_enabled():
        return _bake_worker_alive()
    if _ACTIVE_BAKE is not None:
        return _bake_worker_alive()
    was_alive = _bake_worker_alive()
    try:
        progress_path = _prewarm_progress_path()
        backend_log_path = _backend_run_log_path(progress_path)
        _start_bake_worker(progress_path, backend_log_path)
    except Exception:
        return False
    alive = _bake_worker_alive()
    if not _mesh_prewarm_enabled_for_session():
        return alive
    # If the worker was just spawned (or replaced), prime its high-mesh caches
    # via PREPARE.  Try the current-session in-memory path first (always valid
    # for the current .fymesh files); otherwise schedule a fresh speculative
    # export.  The persisted last_bake_job_path from the scene property is
    # intentionally skipped here: it may reference stale mesh files from a
    # prior session (e.g. .mbmesh paths before the FyrBaker rename), which
    # would prime the session cache under a different key than the actual bake.
    if alive and not was_alive:
        try:
            sent = _maybe_send_prepare_for_last_bake()
            if not sent:
                # No current-session job path — schedule speculative export+PREPARE
                # so the worker gets warm before the user's first bake.
                schedule_speculative_prepare()
        except Exception:
            pass
    return alive


def _backend_prewarm_eligible_for_active_scene() -> bool:
    """True when the active scene has at least one bake group with a high mesh assigned."""
    context = getattr(bpy, "context", None)
    scene = getattr(context, "scene", None) if context is not None else None
    if scene is None:
        return False
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None:
        return False
    for project in getattr(settings, "projects", []) or []:
        for group in getattr(project, "groups", []) or []:
            for slot in properties.effective_high_mesh_slots(group):
                obj = getattr(slot, "object_ref", None)
                if obj is None:
                    continue
                if str(getattr(obj, "type", "") or "") == "MESH":
                    return True
    return False


def request_backend_prewarm(reason: str = "") -> bool:
    """Spawn the bake worker if the addon's prewarm preference allows it.

    Returns True when prewarm was attempted (or already warm); False when the
    current preference disabled it or the scene didn't qualify.
    """
    if not fyr_native_lifecycle_enabled():
        return False
    mode = preferences.resolve_backend_prewarm_mode()
    if mode == constants.BACKEND_PREWARM_OFF:
        return False
    if mode == constants.BACKEND_PREWARM_ON_PROJECT_DETECTED and not _backend_prewarm_eligible_for_active_scene():
        return False
    return ensure_bake_worker_prewarmed(reason)


def _deferred_prewarm_timer():
    global _PREWARM_REQUESTED_REASON, _PREWARM_REQUESTED_UNTIL
    reason = _PREWARM_REQUESTED_REASON or ""
    # The FYR-vs-Cycles decision spawns `fyr_baker_backend capabilities --json`
    # on a cold cache, which creates a D3D12 device and costs ~0.85s. It is
    # evaluated here, on the timer, never inline with addon enable or file load.
    try:
        native_enabled = fyr_native_lifecycle_enabled()
    except Exception:
        native_enabled = False
    if not native_enabled:
        _PREWARM_REQUESTED_REASON = None
        _PREWARM_REQUESTED_UNTIL = 0.0
        return None
    try:
        attempted = request_backend_prewarm(reason)
    except Exception:
        attempted = False
    if (
        not attempted
        and preferences.resolve_backend_prewarm_mode() == constants.BACKEND_PREWARM_ON_PROJECT_DETECTED
        and time.monotonic() < _PREWARM_REQUESTED_UNTIL
    ):
        return 0.5
    _PREWARM_REQUESTED_REASON = None
    _PREWARM_REQUESTED_UNTIL = 0.0
    return None


def schedule_backend_prewarm(reason: str = "") -> None:
    """Schedule a prewarm attempt on the next available Blender timer tick.

    Used from `register()` and load/depsgraph handlers so we never run
    `Popen()` inline with addon enable or scene loading. Deliberately does NOT
    ask `fyr_native_lifecycle_enabled()` here: that probe spawns the backend
    executable and is what made addon enable block for ~1.5s. The timer callback
    asks it instead, so nothing in this function costs more than a dict lookup.
    """
    global _PREWARM_REQUESTED_REASON, _PREWARM_REQUESTED_UNTIL
    mode = preferences.resolve_backend_prewarm_mode()
    if mode == constants.BACKEND_PREWARM_OFF:
        return
    if _bake_worker_alive():
        # Worker already alive (e.g. user opened a different blend file while
        # Blender stayed running). The spawn path won't fire, so schedule a
        # speculative prepare here so PREPARE goes out for the new scene.
        schedule_speculative_prepare()
        return
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    if _PREWARM_REQUESTED_REASON is not None:
        # Coalesce only when Blender still owns the timer. Timer registrations
        # can be discarded during file-load/add-on lifecycle transitions while
        # this Python flag survives, leaving prewarm permanently "queued" but
        # impossible to execute.
        try:
            if hasattr(timers, "is_registered") and timers.is_registered(_deferred_prewarm_timer):
                return
        except Exception:
            pass
        _PREWARM_REQUESTED_REASON = None
        _PREWARM_REQUESTED_UNTIL = 0.0
    _PREWARM_REQUESTED_REASON = reason
    _PREWARM_REQUESTED_UNTIL = time.monotonic() + 10.0
    try:
        timers.register(_deferred_prewarm_timer, first_interval=_PREWARM_INITIAL_DELAY_SECONDS)
    except Exception:
        _PREWARM_REQUESTED_REASON = None
        _PREWARM_REQUESTED_UNTIL = 0.0


def register() -> None:
    try:
        request_pso_priming_once()
    except Exception:
        pass
    schedule_backend_prewarm(reason="addon_register")


def unregister() -> None:
    global _PREPARE_IN_FLIGHT, _MESH_PREWARM_DISABLED_FOR_SESSION, _LAST_PREWARM_FAILURE_MESSAGE
    global _PREWARM_REQUESTED_REASON, _PREWARM_REQUESTED_UNTIL
    _PREPARE_IN_FLIGHT = False
    _MESH_PREWARM_DISABLED_FOR_SESSION = False
    _LAST_PREWARM_FAILURE_MESSAGE = ""
    cancel_speculative_prepare()
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and hasattr(timers, "is_registered"):
        try:
            if timers.is_registered(_deferred_prewarm_timer):
                timers.unregister(_deferred_prewarm_timer)
        except Exception:
            pass
    _PREWARM_REQUESTED_REASON = None
    _PREWARM_REQUESTED_UNTIL = 0.0
    _reset_main_thread_call_queue()
    _release_speculative_prepare_workspace()
    stop_background_polling()
    cancel_debug_overlay_refresh()
    _stop_bake_worker(terminate=True)
    _clear_active_bake_state()
    _stop_debug_overlay_worker(terminate=True)
    _clear_active_debug_state()
    mesh_transport.release_all_shared_memory()
    invalidate_debug_overlay_cache(scene=getattr(bpy.context, "scene", None), reason="runtime_unregister")
    # Scratch delete is filesystem-only and can take seconds on a large cache.
    # Doing it here blocks Blender after operator RNA is already unregistered,
    # which is the RNA_property_subtype / leftover-popup crash on the next draw.
    # The next register() startup worker reclaims scratch instead.
