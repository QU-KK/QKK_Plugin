from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# How long a cancel-pending worker may go WITHOUT ADVANCING progress before it
# is force-killed. A healthy worker mid-way through the GPU execute span (which
# is cancellation-blind for a whole batch) keeps updating progress and is left
# to reach its next checkpoint — killing it would also force a cold worker on
# the next bake. A stalled one (no movement) is killed to release its committed
# memory (BVH, SDF field, image buffers) from the Windows pagefile.
_CANCEL_FORCE_KILL_TIMEOUT_S = 15.0
# Absolute ceiling: even a worker that keeps reporting progress is killed this
# long after the cancel request (Glow's hard cap on runaway bakes).
_CANCEL_HARD_KILL_TIMEOUT_S = 90.0
_WORKER_SHUTDOWN_TIMEOUT_S = 2.0

# A RUNNING bake (no cancel pending) that stops advancing its progress. The known
# failure is the cancel->rebake fence deadlock: the worker blocks forever in a fence
# wait with the CPU and GPU both idle, and nothing on the addon side ever noticed —
# the tester's only way out was killing Blender. These give the freeze a voice and,
# eventually, an exit.
#
# The warning threshold has to clear the longest legitimately silent span. The
# backend publishes progress per map and per batch, and a single cancellation-blind
# GPU execute window on a heavy 2K/16-map job is the widest gap between two writes,
# so this is deliberately generous: it is a "something is wrong" hint, not a kill.
_RUN_STALL_WARN_TIMEOUT_S = 60.0
# Force-fail ceiling. Past this the bake is not slow, it is wedged: no progress write
# at all for three minutes. Terminate the worker (which also frees its committed BVH /
# SDF / image memory) and fail the bake with a message that says what happened, rather
# than holding the session hostage.
_RUN_STALL_FORCE_FAIL_TIMEOUT_S = 180.0
# The map loop reaches 100% while denoise, dilation, image encode and the file writes
# are still to come, and the backend publishes no progress across that tail. On a big
# job (8K, many maps, slow disk) the tail is legitimately long and completely silent,
# and killing there would throw away an almost-finished bake — so the ceiling is
# multiplied once the overall percentage says the maps are done.
_RUN_STALL_FINALIZING_PERCENT = 99.5
_RUN_STALL_FINALIZING_MULTIPLIER = 3.0


@dataclass(slots=True)
class BakeWorkerControlDeps:
    active_bake_state_cls: type
    bake_worker_state_cls: type
    snapshot_cls: type
    poll_result_cls: type
    constants: Any
    protocol: Any
    queue_module: Any
    threading_module: Any
    subprocess_module: Any
    repo_root_fn: Callable[[], Path]
    path_mtime_ns_fn: Callable[[str | Path | None], int]
    resolve_backend_executable_fn: Callable[[], Path]
    ensure_backend_compatible_fn: Callable[..., str]
    backend_run_log_path_fn: Callable[[str | Path], Path]
    background_bake_live_log_path_fn: Callable[[str | Path], Path]
    resident_bake_worker_stderr_path_fn: Callable[[], Path]
    read_text_if_exists_fn: Callable[[Path], str]
    write_backend_log_fn: Callable[..., None]
    append_launch_log_fn: Callable[..., None]
    maybe_open_backend_log_window_fn: Callable[..., bool]
    load_progress_or_default_fn: Callable[..., Any]
    append_progress_log_fn: Callable[..., None]
    clear_bake_cancel_request_fn: Callable[[str | Path], Path]
    clear_bake_pause_request_fn: Callable[[str | Path], Path]
    write_bake_cancel_request_fn: Callable[..., Path]
    write_bake_pause_request_fn: Callable[..., Path]
    create_bake_progress_event_fn: Callable[[str | Path], object]
    check_and_reset_bake_progress_event_fn: Callable[[object], bool]
    close_bake_progress_event_fn: Callable[[object], None]
    close_log_handle_fn: Callable[[object], None]
    release_workspace_shared_memory_fn: Callable[[str | Path], None]
    build_geometry_transport_retry_job_fn: Callable[[str | Path], Path]
    # Told (with the error text) when a worker is retired because its GPU device
    # failed to initialize; runtime.py uses it to drop negative GPU verdicts and
    # log the recycle. Optional so harnesses that build deps by hand keep working.
    on_gpu_init_failure_retire_fn: Callable[[str], None] | None = None


_STALL_MESSAGE_PREFIX = "No progress for "


def _run_progress_signature(progress) -> tuple:
    """What "the bake moved" means for the stall watchdog.

    Every field the backend advances as real work completes. Deliberately does NOT
    include wall-clock or poll counters — a worker that keeps re-publishing the same
    snapshot is exactly the case being watched for.
    """
    message = str(getattr(progress, "message", "") or "")
    if message.startswith(_STALL_MESSAGE_PREFIX):
        # The watchdog's own warning is written into the cached progress object;
        # counting it as a message change reset the stall clock on every poll and
        # the force-fail ceiling never fired for a deadlocked worker.
        message = ""
    return (
        getattr(progress, "percent", 0.0),
        getattr(progress, "stage_percent", -1.0),
        message,
        str(getattr(progress, "active_map", "") or ""),
        str(getattr(progress, "active_group", "") or ""),
        len(getattr(progress, "produced_files", ()) or ()),
    )


def _apply_run_stall_watchdog(state, progress, deps) -> None:
    """Notice, then break, a running bake whose worker has stopped advancing.

    Kept strictly separate from the cancel-path watchdog above: this one runs while
    the user still expects the bake to finish, so it never kills on elapsed time —
    only on a total absence of progress writes. A slow bake keeps publishing and is
    left alone; a deadlocked one is reported and finally terminated so the user gets
    their Blender session back instead of having to kill the process.
    """
    if not hasattr(state, "run_progress_advanced_at"):
        return
    now = time.monotonic()
    signature = _run_progress_signature(progress)
    if state.run_progress_signature != signature or state.run_progress_advanced_at <= 0.0:
        state.run_progress_signature = signature
        state.run_progress_advanced_at = now
        state.run_progress_updates += 1
        state.stall_reported = False
        return

    # Arm only once the bake has published progress of its own. A run queued behind
    # the background scene prewarm sits on its launch snapshot for as long as the
    # prewarm takes and is not stuck; the panel already labels that wait as warming
    # up. Every observed freeze happened mid-bake, with progress already flowing.
    if state.run_progress_updates < 2:
        return

    stalled_for = now - state.run_progress_advanced_at
    if stalled_for < _RUN_STALL_WARN_TIMEOUT_S:
        return

    try:
        percent = float(getattr(progress, "percent", 0.0) or 0.0)
    except (TypeError, ValueError):
        percent = 0.0
    force_fail_after = _RUN_STALL_FORCE_FAIL_TIMEOUT_S
    if percent >= _RUN_STALL_FINALIZING_PERCENT:
        force_fail_after *= _RUN_STALL_FINALIZING_MULTIPLIER

    if stalled_for >= force_fail_after:
        message = (
            "Bake stopped responding. No progress for "
            f"{stalled_for:.0f}s. Stopping the bake worker; "
            "your scene and any maps already written are untouched."
        )
        progress.status = deps.constants.STATUS_FAILED
        progress.message = message
        if message not in progress.errors:
            progress.errors.append(message)
        # Persist it: `progress` is re-read from the progress file on every poll, so an
        # in-memory-only message would be replaced by the worker's last stale snapshot
        # on the very next tick.
        try:
            deps.protocol.write_progress(state.progress_path, progress)
        except Exception:
            pass
        if hasattr(state, "stall_force_failed"):
            state.stall_force_failed = True
        print(f"[MasterBaker] {message}")
        try:
            state.process.terminate()
        except Exception:
            pass
        return

    # Between warn and force-fail: say so on every progress surface, but let it run.
    progress.message = (
        f"{_STALL_MESSAGE_PREFIX}{stalled_for:.0f}s. The bake may be stuck. "
        "Cancel if it does not move."
    )
    if not state.stall_reported:
        state.stall_reported = True
        print(
            "[MasterBaker] bake progress has not advanced for"
            f" {stalled_for:.0f}s (job {state.job_path})"
        )


def active_bake_snapshot(active_bake, snapshot_cls):
    if active_bake is None:
        return None
    return snapshot_cls(
        job_id=active_bake.job_id,
        job_path=str(active_bake.job_path),
        progress_path=str(active_bake.progress_path),
        running=active_bake.process.poll() is None,
        cancel_requested=bool(active_bake.cancel_requested),
        cancel_requested_at=float(getattr(active_bake, "cancel_requested_at", 0.0) or 0.0),
        pause_requested=bool(active_bake.pause_requested),
        start_time=float(getattr(active_bake, "start_time", 0.0) or 0.0),
    )


def normalize_selected_map_types(selected_map_types: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """The backend's names for the map types a RUN / bake command selects."""
    from .wire_types import backend_wire_map_type

    if not selected_map_types:
        return ()
    values: list[str] = []
    seen: set[str] = set()
    for raw in selected_map_types:
        # ATTRIBUTE / DERIVATIVE travel under the backend's names, as the job file has them.
        value = backend_wire_map_type(str(raw or "").strip().upper())
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return tuple(values)


def bake_worker_run_command(job_path: Path, selected_map_types: tuple[str, ...]) -> str:
    command = f"RUN\t{job_path}"
    if selected_map_types:
        command = f"{command}\tMAPS={','.join(selected_map_types)}"
    return f"{command}\n"


def bake_worker_log_command(job_path: Path, selected_map_types: tuple[str, ...]) -> list[str]:
    command = ["bake-worker", "RUN", str(job_path)]
    if selected_map_types:
        command.extend(["--maps", ",".join(selected_map_types)])
    return command


def bake_cli_command(job_path: Path, selected_map_types: tuple[str, ...]) -> list[str]:
    command = ["bake", "--job", str(job_path)]
    if selected_map_types:
        command.extend(["--maps", ",".join(selected_map_types)])
    return command


_FATAL_ERROR_TOKENS = (
    # Protocol/resident-state corruption — the worker's internal state is suspect
    # and cannot be recovered without a full restart.
    "stale resident",
    "stale worker",
)

_DEVICE_RECREATABLE_ERROR_TOKENS = (
    # GPU device loss/hang/TDR: the D3D12 device is invalidated but the C++ worker
    # process stays alive. The worker loop catches the exception and writes ERR; on
    # the next bake call ensure_d3d12_runtime() detects device_loss_pending and fully
    # recreates the device. Keep the worker — retire only if the process has exited.
    "device lost",
    "device removed",
    "device hung",
    "dxgi_error_device",
    "tdr",
)

_RECOVERABLE_ERROR_TOKENS = (
    # OOM / allocation failures: the C++ exception is caught by the worker loop,
    # which stays alive. Retire only if the process actually died.
    "e_outofmemory",
    "out of memory",
    "gpu oom",
    "allocation failed",
    # Cache corruption: individual cache entries are stale but the worker process
    # is still healthy. prune_resident_ram_cache handles eviction on the next bake.
    "cache corruption",
    "cache corrupt",
)


_GPU_UNAVAILABLE_MARKER = "gpu_unavailable_use_cycles"
_GPU_GROUP_TOO_LARGE_MARKER = "gpu_group_too_large"
# Device-INIT failures. The backend creates its D3D12 context inside a call_once in
# ensure_d3d12_runtime (master_baker_backend_gpu_d3d12.cpp); a failed first creation
# is latched for the life of the process (only device_loss_pending resets it). So a
# resident worker whose first init hit a transient (driver not ready, TDR, the
# discrete GPU briefly failing) answers GPU_UNAVAILABLE_USE_CYCLES to every later bake
# until Blender restarts. Paired with that marker, these reasons mean "this process
# can never get a device again": retire it so the next bake spawns a fresh one.
_GPU_INIT_FAILURE_TOKENS = (
    "no d3d12-capable hardware adapter",
    "no usable d3d12 gpu",
    "d3d12createdevice failed",
    "createdxgifactory1 failed",
    "d3d12 runtime initialization failed",
    "d3d12 compute queue creation failed",
    "self-test",
    "dxgi_error_device_removed",
    "0x887a0005",
    "dxgi_error_device_hung",
    "device_hung",
    "0x887a0006",
)


def _first_line(text: str, limit: int = 300) -> str:
    line = next((part.strip() for part in str(text or "").splitlines() if part.strip()), "")
    return line if len(line) <= limit else line[: limit - 3] + "..."


def _notify_gpu_init_failure_retire(deps, error_text: str) -> None:
    callback = getattr(deps, "on_gpu_init_failure_retire_fn", None)
    if callable(callback):
        try:
            callback(error_text)
        except Exception:
            pass


# Transient GPU failures: the device went away or ran out of memory mid-bake, and a
# fresh worker (and a smaller batch) has a real chance of finishing on the GPU. The
# device tokens cover DXGI_ERROR_DEVICE_REMOVED / HUNG / RESET, a driver internal error
# and a TDR; the memory tokens only count when the text is about the GPU.
_TRANSIENT_GPU_DEVICE_TOKENS = (
    "device lost",
    "device loss",
    "device removed",
    "device_removed",
    "device hung",
    "device_hung",
    "device reset",
    "device_reset",
    "0x887a0005",
    "0x887a0006",
    "0x887a0007",
    "0x887a0020",
)
_TRANSIENT_GPU_MEMORY_TOKENS = (
    "out of memory",
    "outofmemory",
    "0x8007000e",
    "allocation failed",
    "bad allocation",
    "bad_alloc",
)
_TRANSIENT_GPU_CONTEXT_TOKENS = ("gpu", "d3d12", "dxgi", "dxr", "vram", "video memory")
# A group the GPU can never take (too large for hardware RT) or a map the GPU route does
# not support is not transient: a retry would fail the same way, so it goes to Cycles.
_NON_TRANSIENT_GPU_TOKENS = (
    "gpu_group_too_large",
    "unsupported",
    "not supported",
    "does not support",
)
_TDR_PATTERN = re.compile(r"\btdr\b")


def error_is_transient_gpu_failure(error_text: str) -> bool:
    """True when a failed bake looks like a one-off GPU device loss or GPU out-of-memory.

    Never true for GPU_GROUP_TOO_LARGE or an "unsupported on GPU" refusal.
    """
    normalized = str(error_text or "").casefold()
    if not normalized or any(token in normalized for token in _NON_TRANSIENT_GPU_TOKENS):
        return False
    if any(token in normalized for token in _TRANSIENT_GPU_DEVICE_TOKENS) or _TDR_PATTERN.search(normalized):
        return True
    return any(token in normalized for token in _TRANSIENT_GPU_MEMORY_TOKENS) and any(
        token in normalized for token in _TRANSIENT_GPU_CONTEXT_TOKENS
    )


# Environment variables layered over the preference-driven backend env for the next
# worker spawn only. The GPU retry ladder uses it to hand the backend a smaller
# FYR_BAKER_TEXTURE_SET_BATCH_SOURCES. It is part of the worker's env signature, so the
# worker spawned with it is recycled on the next bake once the overrides are cleared.
_BACKEND_ENV_OVERRIDES: dict[str, str] = {}


def set_backend_env_override(name: str, value: str) -> None:
    _BACKEND_ENV_OVERRIDES[str(name)] = str(value)


def clear_backend_env_overrides() -> None:
    _BACKEND_ENV_OVERRIDES.clear()


def backend_env_overrides() -> dict[str, str]:
    return dict(_BACKEND_ENV_OVERRIDES)


def _configured_batch_sources(constants_module) -> int:
    """Batch size (sources per texture-set batch) a normal run of the backend uses."""
    name = constants_module.GPU_TRANSIENT_RETRY_BATCH_ENV
    raw = ""
    try:
        from . import preferences as _prefs_mod

        raw = str((_prefs_mod.build_backend_env() or {}).get(name, "") or "")
    except Exception:
        raw = ""
    raw = raw or str(os.environ.get(name, "") or "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0
    return value if value >= 1 else int(constants_module.GPU_TEXTURE_SET_BATCH_SOURCES_DEFAULT)


def gpu_retry_batch_sources(constants_module, attempt: int) -> int:
    """Texture-set batch size for retry number ``attempt`` (0 = first): halved, then quartered."""
    divisors = constants_module.GPU_TRANSIENT_RETRY_DIVISORS
    divisor = int(divisors[min(max(0, attempt), len(divisors) - 1)])
    return max(1, _configured_batch_sources(constants_module) // divisor)


def error_requires_gpu_reinit_retire(error_text: str) -> bool:
    """True when a GPU-unavailable reply comes from a latched device-init failure.

    Only GPU_UNAVAILABLE_USE_CYCLES replies qualify, and never a group refused for
    size or VRAM budget (GPU_GROUP_TOO_LARGE): a fresh process would refuse it too.
    Mid-bake device loss arrives as GPU_FAILED_USE_CYCLES and keeps the worker, since
    the backend recreates that device itself (device_loss_pending).
    """
    normalized = str(error_text or "").casefold()
    if _GPU_UNAVAILABLE_MARKER not in normalized or _GPU_GROUP_TOO_LARGE_MARKER in normalized:
        return False
    return any(token in normalized for token in _GPU_INIT_FAILURE_TOKENS)


_WORKER_EXIT_REASONS = {
    0xC0000005: "memory access violation",
    0xC0000017: "out of memory",
    0xC000012D: "out of memory, system commit limit reached",
    0xC00000FD: "stack overflow",
    0xC0000374: "heap corruption",
    0xC0000409: "fatal runtime error",
    3: "aborted",
}


def describe_unexpected_worker_exit(returncode, *, group: str = "", map_name: str = "", stderr_text: str = "") -> str:
    """User-facing headline for a backend process that died without replying."""
    try:
        code = int(returncode) & 0xFFFFFFFF
    except (TypeError, ValueError):
        code = None
    parts = []
    if code is not None:
        reason = _WORKER_EXIT_REASONS.get(code)
        code_text = f"0x{code:08X}" if code > 0xFFFF else str(code)
        parts.append(f"{reason}, exit code {code_text}" if reason else f"exit code {code_text}")
    where = ""
    if group and map_name:
        where = f" while baking {map_name} for group {group}"
    elif group:
        where = f" while baking group {group}"
    message = "The baking backend stopped unexpectedly"
    if parts:
        message += f" ({parts[0]})"
    message += f"{where}."
    last_line = next((line.strip() for line in reversed((stderr_text or "").splitlines()) if line.strip()), "")
    if last_line:
        message += f" Last backend message: {last_line}"
    message += " The next bake starts a fresh backend. If this repeats, create a Support Bundle and send it to us."
    return message


def error_is_gpu_fatal(error_text: str) -> bool:
    """Return True when the error indicates unrecoverable protocol/state corruption."""
    normalized = str(error_text or "").casefold()
    return any(token in normalized for token in _FATAL_ERROR_TOKENS)


def error_is_device_recreatable(error_text: str) -> bool:
    """Return True when the error is a GPU device loss that the C++ worker can recover from.

    The worker process stays alive after device loss; the D3D12 runtime is recreated
    on the next bake call via device_loss_pending / reset_d3d12_runtime_for_device_recreation.
    Keep the worker alive — only retire if the process has actually exited.
    """
    normalized = str(error_text or "").casefold()
    return any(token in normalized for token in _DEVICE_RECREATABLE_ERROR_TOKENS)


def error_is_recoverable(error_text: str) -> bool:
    """Return True when the error may allow the worker process to continue running."""
    normalized = str(error_text or "").casefold()
    return any(token in normalized for token in _RECOVERABLE_ERROR_TOKENS)


def error_requires_worker_retire(error_text: str) -> bool:
    """Return True when this error warrants terminating the resident worker process.

    Only protocol/state corruption errors (stale resident/worker) always require retirement.
    Device loss and OOM errors only require retirement when the worker process has already
    exited — the C++ worker catches those exceptions and stays alive, so we keep the process
    if it is still running.
    Call this function before checking process liveness.
    """
    return error_is_gpu_fatal(error_text)


def spawn_feedback_suppression_kwargs(subprocess_module) -> dict:
    """Popen/run kwargs that stop Windows showing the "app starting" busy
    cursor for backend child processes.

    Windows paints the arrow+spinner feedback cursor for several seconds after
    every CreateProcess unless STARTF_FORCEOFFFEEDBACK is set; a windowless
    console backend never cancels it, so users repeatedly see a "loading"
    cursor with nothing visibly loading (worker spawns/recycles, version
    probes, warmup, cage-fit CLI). No-op off Windows and for the fake
    subprocess modules used by tests."""
    startupinfo_cls = getattr(subprocess_module, "STARTUPINFO", None)
    if os.name != "nt" or startupinfo_cls is None:
        return {}
    try:
        startupinfo = startupinfo_cls()
        startupinfo.dwFlags |= int(
            getattr(subprocess_module, "STARTF_FORCEOFFFEEDBACK", 0x00000080)
        )
        return {"startupinfo": startupinfo}
    except Exception:
        return {}


PARENT_PID_ENV_VAR = "FYR_BAKER_PARENT_PID"

# Windows job-object plumbing for orphan prevention. Blender's stdin-pipe EOF and
# the atexit handler both require Blender to still be executing code; neither
# fires on a segfault or a Task Manager "End task", and a GPU-wedged worker never
# reaches its next stdin read anyway. A job object with
# JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE moves the guarantee into the kernel: when the
# last handle to the job closes -- which the OS does unconditionally as it tears
# down the Blender process, however it died -- every assigned process is
# terminated. The handle is therefore deliberately never closed; it lives for the
# life of the Blender process and is released only by process teardown.
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_KILL_ON_CLOSE_JOB_HANDLE = None
_KILL_ON_CLOSE_JOB_UNAVAILABLE = False
_KILL_ON_CLOSE_NOTE_PRINTED = False


def _note_kill_on_close_failure(message: str) -> None:
    """Report a job-object failure exactly once. Losing the guarantee is a
    degraded-but-working state (the stdin-EOF path still handles clean exits);
    it must never turn into per-bake log spam."""
    global _KILL_ON_CLOSE_NOTE_PRINTED
    if _KILL_ON_CLOSE_NOTE_PRINTED:
        return
    _KILL_ON_CLOSE_NOTE_PRINTED = True
    try:
        print(f"[fyr_baker] {message}; backend workers may outlive a Blender crash")
    except Exception:
        pass


def _kill_on_close_job_handle():
    """Lazily create the process-wide kill-on-close job object, or None."""
    global _KILL_ON_CLOSE_JOB_HANDLE, _KILL_ON_CLOSE_JOB_UNAVAILABLE
    if _KILL_ON_CLOSE_JOB_HANDLE is not None:
        return _KILL_ON_CLOSE_JOB_HANDLE
    if _KILL_ON_CLOSE_JOB_UNAVAILABLE:
        return None
    if sys.platform != "win32" or os.name != "nt":
        _KILL_ON_CLOSE_JOB_UNAVAILABLE = True
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]

        # Unnamed job: nothing outside this process may open a second handle and
        # keep the job (and therefore the workers) alive past Blender's death.
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
        _KILL_ON_CLOSE_JOB_HANDLE = handle
        return _KILL_ON_CLOSE_JOB_HANDLE
    except Exception as exc:
        _KILL_ON_CLOSE_JOB_UNAVAILABLE = True
        _note_kill_on_close_failure(f"kill-on-close job object unavailable ({exc})")
        return None


def assign_process_to_kill_on_close_job(process) -> bool:
    """Assign a spawned backend child to the kill-on-close job object.

    Only ever called with child handles -- Blender's own process is never
    assigned, and no CREATE_BREAKAWAY flags are used, so an outer job Blender may
    already belong to keeps its own semantics. Every failure path (non-Windows,
    fake test Popen without _handle, nested-job restrictions on pre-Windows-8
    kernels) is non-fatal: the worker runs exactly as before, minus the
    hard-crash guarantee."""
    handle = _kill_on_close_job_handle()
    if handle is None:
        return False
    process_handle = getattr(process, "_handle", None)
    if not process_handle:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        if not kernel32.AssignProcessToJobObject(handle, int(process_handle)):
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
        return True
    except Exception as exc:
        _note_kill_on_close_failure(f"could not assign backend worker to job object ({exc})")
        return False


def backend_child_env(env: dict | None) -> dict | None:
    """Child environment carrying FYR_BAKER_PARENT_PID.

    The backend starts a watchdog on this PID as a second, platform-independent
    line of defence behind the job object. A None env means "inherit", which
    Popen cannot combine with a single extra variable -- materialise the parent
    environment first. On failure hand back the original env untouched rather
    than a half-built one: a truncated environment would break the backend far
    worse than a missing watchdog."""
    try:
        child_env = dict(env) if env is not None else os.environ.copy()
        child_env[PARENT_PID_ENV_VAR] = str(os.getpid())
        return child_env
    except Exception:
        return env


def _worker_job_paths_equal(a: str | Path, b: str | Path) -> bool:
    """Case/separator-insensitive path equality for matching worker replies
    (OK/ERR/READY carry the job path they answer) to the command that sent them."""
    try:
        return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))
    except Exception:
        return str(a) == str(b)


def bake_worker_reader(stdout_handle, response_queue) -> None:
    if stdout_handle is None:
        return
    try:
        for raw_line in stdout_handle:
            line = str(raw_line or "").strip()
            if not line:
                continue
            if line == "BYE":
                response_queue.put({"status": "bye"})
                break
            parts = line.split("\t", 4)
            status = parts[0]
            if status == "OK":
                job_path = parts[1] if len(parts) >= 2 else ""
                elapsed_ms = 0.0
                if len(parts) >= 3:
                    try:
                        elapsed_ms = float(parts[2])
                    except Exception:
                        elapsed_ms = 0.0
                response_queue.put(
                    {
                        "status": "ok",
                        "job_path": job_path,
                        "elapsed_ms": elapsed_ms,
                    }
                )
                continue
            if status == "ERR":
                job_path = parts[1] if len(parts) >= 2 else ""
                error_text = parts[2] if len(parts) >= 3 else "Bake worker failed"
                response_queue.put(
                    {
                        "status": "error",
                        "job_path": job_path,
                        "error": error_text,
                    }
                )
                continue
            if status == "READY":
                # PREPARE acknowledgement from the resident worker. No active
                # bake state owns this response; the polling consumer is
                # expected to drain and discard it.
                job_path = parts[1] if len(parts) >= 2 else ""
                elapsed_ms = 0.0
                if len(parts) >= 3:
                    try:
                        elapsed_ms = float(parts[2])
                    except Exception:
                        elapsed_ms = 0.0
                response_queue.put(
                    {
                        "status": "ready",
                        "job_path": job_path,
                        "elapsed_ms": elapsed_ms,
                    }
                )
                continue
            if status == "TRANSPORT_ERR":
                response_queue.put(
                    {
                        "status": "transport_error",
                        "job_path": parts[1] if len(parts) >= 2 else "",
                        "transport_kind": parts[2] if len(parts) >= 3 else "",
                        "content_hash": parts[3] if len(parts) >= 4 else "",
                        "error": parts[4] if len(parts) >= 5 else "Geometry transport failed",
                        "retryable": True,
                    }
                )
                continue
            if status == "REPROJECT_READY":
                job_path = parts[1] if len(parts) >= 2 else ""
                response_queue.put({"status": "reproject_ready", "job_path": job_path})
                continue
            if status == "REPROJECT_RESULT":
                import json
                job_path = parts[1] if len(parts) >= 2 else ""
                try:
                    payload = json.loads(parts[2]) if len(parts) >= 3 else {}
                except ValueError as exc:
                    # One malformed line must not end the reader for the worker's
                    # lifetime: the next RUN's OK would never be delivered and the
                    # stall watchdog would kill a healthy worker 180 s later.
                    response_queue.put({"status": "error", "job_path": job_path, "error": f"malformed REPROJECT_RESULT: {exc}"})
                    continue
                response_queue.put({"status": "reproject_result", "job_path": job_path, "result": payload})
                continue
            response_queue.put({"status": "error", "job_path": "", "error": line})
    except Exception as exc:
        response_queue.put({"status": "error", "job_path": "", "error": str(exc)})


def stop_bake_worker(current_worker, *, terminate: bool = False, close_log_handle_fn):
    incoming_worker = current_worker
    worker = current_worker
    if worker is None:
        return None

    process = worker.process
    try:
        if not terminate and process.poll() is None and worker.stdin_handle is not None:
            worker.stdin_handle.write("QUIT\n")
            worker.stdin_handle.flush()
    except Exception:
        pass

    if process.poll() is None:
        try:
            process.terminate()
        except Exception:
            pass

    wait_fn = getattr(process, "wait", None)
    if process.poll() is None and callable(wait_fn):
        try:
            wait_fn(timeout=_WORKER_SHUTDOWN_TIMEOUT_S)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
            try:
                wait_fn(timeout=_WORKER_SHUTDOWN_TIMEOUT_S)
            except Exception:
                pass

    close_log_handle_fn(worker.stdin_handle)
    # Closing a Windows stdout pipe while the reader thread is blocked in
    # readline can deadlock Blender. Only close reader-owned pipes once the
    # child has exited and delivered EOF; otherwise leave the daemon reader to
    # release them after the forced process shutdown completes.
    if process.poll() is not None:
        close_log_handle_fn(worker.stdout_handle)
    # stderr is a plain file we opened for the child, not a reader-owned pipe:
    # nothing blocks on it, so it is safe (and required) to close even when the
    # child refused to exit, or a stubborn worker leaks the handle for good.
    close_log_handle_fn(worker.stderr_handle)
    return None


def start_bake_worker(
    progress_path: str | Path,
    backend_log_path: str | Path,
    *,
    current_worker,
    deps: BakeWorkerControlDeps,
):
    backend_path = deps.resolve_backend_executable_fn()
    backend_version = deps.ensure_backend_compatible_fn(backend_path, log_path=backend_log_path)
    backend_mtime_ns = deps.path_mtime_ns_fn(backend_path)
    cpu_threads = 0
    try:
        from . import preferences as _prefs_mod
        prefs = _prefs_mod.get_preferences()
        if prefs is not None:
            cpu_threads = int(getattr(prefs, "cpu_threads", 0) or 0)
    except Exception:
        pass

    backend_env = None
    try:
        from . import preferences as _prefs_mod
        backend_env = _prefs_mod.build_backend_env()
    except Exception as exc:
        # The worker still starts, but without the RAM-cache budget, thread count and
        # fast-path flags: say so instead of baking slower with no explanation.
        print(f"[MasterBaker] backend settings unavailable, starting the bake worker with defaults: {exc!r}")
    if _BACKEND_ENV_OVERRIDES:
        backend_env = dict(backend_env) if backend_env is not None else dict(os.environ)
        backend_env.update(_BACKEND_ENV_OVERRIDES)
    env_signature = _backend_env_signature(backend_env)

    worker = current_worker
    if worker is not None and worker.process.poll() is None:
        same_backend = os.path.normcase(str(worker.backend_path)) == os.path.normcase(str(backend_path))
        same_threads = getattr(worker, "cpu_threads", 0) == cpu_threads
        # The preference-driven env (AA path flags, cache budgets, ...) reaches the
        # worker only at spawn; a warm worker kept the old flags for the rest of
        # the session after the artist changed them.
        # Workers spawned before the signature existed carry "" and are kept.
        same_env = (getattr(worker, "env_signature", "") or env_signature) == env_signature
        if same_backend and worker.backend_mtime_ns == backend_mtime_ns and same_threads and same_env:
            return worker
        worker = stop_bake_worker(worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)
    elif worker is not None:
        worker = stop_bake_worker(worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)

    stderr_path = deps.resident_bake_worker_stderr_path_fn()
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.write_text("", encoding="utf-8")
    stderr_handle = stderr_path.open("a", encoding="utf-8")
    creation_flags = int(getattr(deps.subprocess_module, "CREATE_NO_WINDOW", 0))
    creation_flags |= int(getattr(deps.subprocess_module, "BELOW_NORMAL_PRIORITY_CLASS", 0))
    try:
        process = deps.subprocess_module.Popen(
            [str(backend_path), "bake-worker"],
            cwd=str(deps.repo_root_fn()),
            stdin=deps.subprocess_module.PIPE,
            stdout=deps.subprocess_module.PIPE,
            stderr=stderr_handle,
            text=True,
            bufsize=1,
            creationflags=creation_flags,
            env=backend_child_env(backend_env),
            **spawn_feedback_suppression_kwargs(deps.subprocess_module),
        )
    except BaseException:
        # A failed spawn (missing or locked backend exe) must not leak the stderr
        # log handle; on Windows an open handle also keeps the file locked.
        deps.close_log_handle_fn(stderr_handle)
        raise
    assign_process_to_kill_on_close_job(process)
    response_queue = deps.queue_module.Queue()
    stdout_handle = getattr(process, "stdout", None)
    stdin_handle = getattr(process, "stdin", None)
    response_thread = deps.threading_module.Thread(
        target=bake_worker_reader,
        args=(stdout_handle, response_queue),
        name="MasterBakerBakeWorkerReader",
        daemon=True,
    )
    if stdout_handle is not None:
        response_thread.start()

    worker_state = deps.bake_worker_state_cls(
        process=process,
        backend_path=backend_path,
        backend_version=backend_version,
        backend_mtime_ns=backend_mtime_ns,
        cpu_threads=cpu_threads,
        stderr_path=stderr_path,
        stdin_handle=stdin_handle,
        stdout_handle=stdout_handle,
        stderr_handle=stderr_handle,
        response_queue=response_queue,
        response_thread=response_thread,
    )
    worker_state.env_signature = env_signature
    return worker_state


def _backend_env_signature(backend_env) -> str:
    """Stable digest of the preference-driven worker environment."""
    import hashlib

    if not backend_env:
        return ""
    try:
        items = sorted((str(key), str(value)) for key, value in dict(backend_env).items())
    except Exception:
        return ""
    return hashlib.blake2b(repr(items).encode("utf-8"), digest_size=8).hexdigest()


def launch_bake_job_background(
    job_path: str | Path,
    progress_path: str | Path,
    *,
    job_id: str = "",
    selected_map_types: list[str] | tuple[str, ...] | None = None,
    current_worker,
    deps: BakeWorkerControlDeps,
):
    # A new bake starts from the artist's own settings; only the retry ladder, which
    # resends an existing job, layers overrides on the worker.
    clear_backend_env_overrides()
    resolved_job_path = Path(job_path)
    resolved_progress_path = Path(progress_path)
    backend_log_path = deps.backend_run_log_path_fn(resolved_progress_path)
    live_log_path = deps.background_bake_live_log_path_fn(resolved_progress_path)
    backend_path: Path | None = None
    backend_version = ""
    selected_maps = normalize_selected_map_types(selected_map_types)
    worker_command = bake_worker_run_command(resolved_job_path, selected_maps)
    worker_log_command = bake_worker_log_command(resolved_job_path, selected_maps)
    incoming_worker = current_worker
    worker = current_worker
    try:
        live_log_path.parent.mkdir(parents=True, exist_ok=True)
        live_log_path.write_text("", encoding="utf-8")
        deps.clear_bake_cancel_request_fn(resolved_progress_path)
        deps.clear_bake_pause_request_fn(resolved_progress_path)
        worker = start_bake_worker(resolved_progress_path, backend_log_path, current_worker=worker, deps=deps)
        backend_path = worker.backend_path
        backend_version = worker.backend_version
        deps.append_launch_log_fn(
            live_log_path,
            job_path=resolved_job_path,
            backend_path=backend_path,
            backend_version=backend_version,
            resident_worker=True,
        )
        deps.maybe_open_backend_log_window_fn(
            live_log_path,
            title=f"Fyr Baker Bake Log: {resolved_job_path.stem}",
            follow=True,
        )
        if worker.stdin_handle is None:
            raise RuntimeError("Bake worker stdin is unavailable")
        try:
            worker.stdin_handle.write(worker_command)
            worker.stdin_handle.flush()
        except Exception:
            if incoming_worker is None or worker is not incoming_worker:
                raise
            worker = stop_bake_worker(worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)
            worker = start_bake_worker(resolved_progress_path, backend_log_path, current_worker=None, deps=deps)
            backend_path = worker.backend_path
            backend_version = worker.backend_version
            if worker.stdin_handle is None:
                raise RuntimeError("Bake worker stdin is unavailable after stale-worker restart")
            worker.stdin_handle.write(worker_command)
            worker.stdin_handle.flush()
    except Exception as exc:
        worker = stop_bake_worker(worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)
        deps.write_backend_log_fn(
            backend_log_path,
            title="Backend bake launch failed",
            backend_path=backend_path,
            command=worker_log_command,
            cwd=str(resolved_job_path.parent),
            returncode=-1,
            stdout=deps.read_text_if_exists_fn(live_log_path),
            stderr="",
            backend_version=backend_version,
            note=str(exc),
        )
        raise

    active_bake = deps.active_bake_state_cls(
        job_id=job_id or resolved_job_path.stem,
        job_path=resolved_job_path,
        progress_path=resolved_progress_path,
        backend_log_path=backend_log_path,
        backend_path=backend_path,
        backend_version=backend_version,
        process=worker.process,
        stdout_path=live_log_path,
        stderr_path=worker.stderr_path,
        stdout_handle=None,
        stderr_handle=None,
        selected_map_types=selected_maps,
        pause_requested=False,
        last_progress_log_signature=None,
        progress_event_handle=deps.create_bake_progress_event_fn(resolved_progress_path),
        start_time=time.monotonic(),
    )
    # Remember where the shared worker stderr stood when this job started so a
    # failure report only quotes this job's lines (see the failure branch).
    # Measured through the same reader the failure path uses (text mode, so
    # the offset is in characters, not bytes: CRLF logs differ between the two).
    try:
        stderr_size = len(deps.read_text_if_exists_fn(worker.stderr_path) or "") if worker.stderr_path else 0
    except Exception:
        stderr_size = 0
    try:
        active_bake.stderr_offset = int(stderr_size or 0)
    except Exception:
        pass
    return active_bake, worker


def _retry_transient_gpu_failure(state, current_worker, response, progress, deps):
    """Retry a bake that failed on a transient GPU error before anything hands it to Cycles.

    Ladder rungs 1 and 2: on device removed / hung / reset, a TDR or GPU out-of-memory,
    stop the worker, spawn a fresh one (clean D3D12 device) and resend the SAME job with
    FYR_BAKER_TEXTURE_SET_BATCH_SOURCES halved on the first retry and quartered on the
    second. Successful bakes never reach this path, so their pixels are untouched.
    Returns the (poll result, state, worker) triple while the retry is running, or None
    when the failure is not transient, the retries are used up, or the relaunch failed
    (the caller then reports the original failure and the Cycles gate decides).
    """
    constants_module = deps.constants
    attempt = int(getattr(state, "gpu_retry_count", 0) or 0)
    if attempt >= int(constants_module.GPU_TRANSIENT_RETRY_MAX):
        return None
    error_text = str(response.get("error", "") or "").strip()
    if not error_is_transient_gpu_failure(error_text):
        return None
    sources = gpu_retry_batch_sources(constants_module, attempt)
    retry_number = attempt + 1
    retry_total = int(constants_module.GPU_TRANSIENT_RETRY_MAX)
    message = (
        f"GPU reset, retrying with smaller batches ({sources} per batch, "
        f"retry {retry_number} of {retry_total})"
    )
    print(f"[MasterBaker] {message}: {_first_line(error_text)}")
    set_backend_env_override(constants_module.GPU_TRANSIENT_RETRY_BATCH_ENV, str(sources))
    try:
        if current_worker is not None:
            stop_bake_worker(current_worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)
        worker = start_bake_worker(
            state.progress_path, state.backend_log_path, current_worker=None, deps=deps
        )
        if worker.stdin_handle is None:
            raise RuntimeError("Bake worker stdin is unavailable")
        worker.stdin_handle.write(bake_worker_run_command(state.job_path, state.selected_map_types))
        worker.stdin_handle.flush()
    except Exception as exc:
        clear_backend_env_overrides()
        print(f"[MasterBaker] GPU retry could not relaunch the bake worker: {exc!r}")
        return None
    try:
        deps.write_backend_log_fn(
            state.backend_log_path,
            title="Backend bake run (GPU failure, retrying)",
            backend_path=state.backend_path,
            command=bake_worker_log_command(state.job_path, state.selected_map_types),
            cwd=str(state.job_path.parent),
            returncode=1,
            stdout=deps.read_text_if_exists_fn(state.stdout_path),
            stderr="",
            backend_version=state.backend_version,
            note=f"{message}: {_first_line(error_text)}",
        )
    except Exception:
        pass
    state.gpu_retry_count = retry_number
    state.process = worker.process
    state.stderr_path = worker.stderr_path
    state.stderr_offset = 0
    state.run_progress_signature = None
    state.run_progress_advanced_at = time.monotonic()
    progress.status = constants_module.STATUS_BAKING
    progress.message = message
    progress.errors = []
    note = (
        f"GPU device failure on attempt {retry_number}; "
        f"retried on a fresh backend with {sources}-source batches"
    )
    if note not in progress.warnings:
        progress.warnings.append(note)
    try:
        deps.protocol.write_progress(state.progress_path, progress)
    except Exception:
        pass
    state.last_progress = progress
    return (
        deps.poll_result_cls(
            snapshot=active_bake_snapshot(state, deps.snapshot_cls),
            progress=progress,
            finished=False,
        ),
        state,
        worker,
    )


def poll_active_bake(current_active_bake, current_worker, *, deps: BakeWorkerControlDeps):
    state = current_active_bake
    if state is None:
        return None, current_active_bake, current_worker

    if state.progress_event_handle is not None:
        if deps.check_and_reset_bake_progress_event_fn(state.progress_event_handle):
            progress = deps.load_progress_or_default_fn(state.progress_path, fallback=state.last_progress)
            state.last_progress = progress
        else:
            progress = state.last_progress or deps.load_progress_or_default_fn(state.progress_path)
    else:
        progress = deps.load_progress_or_default_fn(state.progress_path, fallback=state.last_progress)
        state.last_progress = progress
    response = None
    if current_worker is not None:
        while True:
            try:
                candidate = current_worker.response_queue.get_nowait()
            except deps.queue_module.Empty:
                break
            candidate_status = str(candidate.get("status", ""))
            if candidate_status == "bye":
                continue
            if candidate_status == "ready":
                # PREPARE acknowledgement from a prior idle warmup; not tied
                # to the active bake submission.  Discard and keep draining.
                continue
            if candidate_status == "transport_error":
                if (
                    bool(candidate.get("retryable", False))
                    and int(getattr(state, "transport_retry_count", 0) or 0) == 0
                ):
                    try:
                        retry_path = deps.build_geometry_transport_retry_job_fn(
                            state.job_path
                        )
                        state.transport_retry_count = 1
                        state.job_path = Path(retry_path)
                        if (
                            current_worker.stdin_handle is None
                            or current_worker.process.poll() is not None
                        ):
                            raise RuntimeError(
                                "resident worker exited before geometry transport retry"
                            )
                        current_worker.stdin_handle.write(
                            bake_worker_run_command(
                                state.job_path, state.selected_map_types
                            )
                        )
                        current_worker.stdin_handle.flush()
                        continue
                    except Exception as exc:
                        candidate = {
                            "status": "error",
                            "job_path": str(state.job_path),
                            "error": str(exc),
                        }
                        candidate_status = "error"
                else:
                    candidate = {
                        "status": "error",
                        "job_path": str(state.job_path),
                        "error": str(
                            candidate.get("error", "")
                            or "Geometry transport retry failed"
                        ),
                    }
                    candidate_status = "error"
            # The worker tags every OK/ERR reply with the job path it answers.
            # Only a reply for THIS bake's job may terminate the bake: a stray
            # reply left over from an earlier command (e.g. a speculative
            # PREPARE that failed after its workspace was superseded) consumed
            # positionally shifts every later bake one reply behind — observed
            # as bakes "finishing" in 0.1s with the previous job's error while
            # the worker was still baking the real job. Path-less replies
            # (reader exceptions, unparseable worker lines) still terminate
            # the bake conservatively.
            candidate_path = str(candidate.get("job_path", "") or "")
            if candidate_path and not _worker_job_paths_equal(candidate_path, state.job_path):
                print(
                    "[MasterBaker] dropping stale bake-worker reply"
                    f" status={candidate_status} job_path={candidate_path}"
                    f" (active job: {state.job_path})"
                )
                continue
            response = candidate
            break

    if (
        response is not None
        and str(response.get("status", "")) == "error"
        and not state.cancel_requested
    ):
        retried = _retry_transient_gpu_failure(state, current_worker, response, progress, deps)
        if retried is not None:
            return retried

    returncode = state.process.poll()
    if response is None and returncode is None:
        if state.cancel_requested:
            progress.status = deps.constants.STATUS_CANCELLING
            progress.message = deps.constants.STATUS_CANCELLING
            # Kill on STALL, not on elapsed time alone: a worker that keeps
            # advancing progress is finishing its cancellation-blind GPU span
            # and will honor the cancel at its next checkpoint, keeping itself
            # warm for the next bake. One that stops moving is stuck in a long
            # TBB task and is killed to release its committed memory.
            now = time.monotonic()
            cancel_at = getattr(state, "cancel_requested_at", 0.0) or 0.0
            signature = (progress.percent, getattr(progress, "stage_percent", -1.0), progress.message)
            if getattr(state, "cancel_progress_signature", None) != signature:
                if hasattr(state, "cancel_progress_signature"):
                    state.cancel_progress_signature = signature
                    state.cancel_progress_advanced_at = now
            advanced_at = getattr(state, "cancel_progress_advanced_at", 0.0) or 0.0
            stall_reference = max(cancel_at, advanced_at)
            stalled = (
                stall_reference > 0.0
                and (now - stall_reference) > _CANCEL_FORCE_KILL_TIMEOUT_S
            )
            hard_capped = cancel_at > 0.0 and (now - cancel_at) > _CANCEL_HARD_KILL_TIMEOUT_S
            if stalled or hard_capped:
                try:
                    state.process.terminate()
                except Exception:
                    pass
        elif state.pause_requested:
            progress.status = deps.constants.STATUS_PAUSED
            progress.message = deps.constants.STATUS_PAUSED
        else:
            if progress.status == deps.constants.STATUS_EXPORTED:
                progress.status = deps.constants.STATUS_BAKING
                progress.message = deps.constants.STATUS_BAKING
            _apply_run_stall_watchdog(state, progress, deps)
        deps.append_progress_log_fn(state, progress)
        return (
            deps.poll_result_cls(
                snapshot=active_bake_snapshot(state, deps.snapshot_cls),
                progress=progress,
                finished=False,
            ),
            state,
            current_worker,
        )

    stdout_text = deps.read_text_if_exists_fn(state.stdout_path)
    stderr_text = deps.read_text_if_exists_fn(state.stderr_path)
    # The resident worker's stderr is shared by every bake of the session and
    # truncated only at spawn; report only what this job wrote, or a failed bake
    # showed a multi-bake dump and an OLD "bad allocation" line restarted the
    # warm worker needlessly.
    stderr_offset = int(getattr(state, "stderr_offset", 0) or 0)
    if stderr_text and 0 < stderr_offset <= len(stderr_text):
        stderr_text = stderr_text[stderr_offset:]
    note = ""
    retire_worker = False
    response_status = str(response.get("status", "")) if response is not None else ""

    # A successful reply outranks a cancel. Stop pressed inside the polling
    # window used to rewrite an already-queued "ok" into CANCELLED, so the
    # finished bake's outputs were never finalized and the maps the worker had
    # just written were thrown away. Cancel only decides the outcome when the
    # worker did not (or could not) report success.
    if response_status == "ok":
        returncode = 0
        elapsed_ms = float(response.get("elapsed_ms", 0.0) or 0.0)
        if elapsed_ms > 0.0:
            note = f"Resident bake worker elapsed {elapsed_ms:.0f} ms"
    elif state.cancel_requested:
        progress.status = deps.constants.STATUS_CANCELLED
        progress.message = deps.constants.STATUS_CANCELLED
        progress.errors = []
        note = "Cancelled by user"
        # The cancel decides the OUTCOME, not the worker's health. A fatal state
        # error arriving inside the cancel window used to be dropped with the rest
        # of the errors, so a worker with corrupt resident state was kept and the
        # next bake ran against it.
        cancel_error_text = str(response.get("error", "") or "").strip() if response_status == "error" else ""
        if cancel_error_text and (
            error_requires_worker_retire(cancel_error_text)
            or error_requires_gpu_reinit_retire(cancel_error_text)
        ):
            retire_worker = True
            if cancel_error_text not in progress.warnings:
                progress.warnings.append(cancel_error_text)
            note = "Cancelled by user; worker reported a fatal state error and is being retired"
            if error_requires_gpu_reinit_retire(cancel_error_text):
                _notify_gpu_init_failure_retire(deps, cancel_error_text)
                note = (
                    "Cancelled by user; worker could not initialize its GPU device "
                    f"({_first_line(cancel_error_text)}) and is being retired"
                )
        deps.protocol.write_progress(state.progress_path, progress)
    elif response_status == "error":
        error_text = str(response.get("error", "") or "").strip() or (stderr_text or stdout_text or "").strip()
        progress.status = deps.constants.STATUS_FAILED
        if error_text:
            progress.message = error_text
            if error_text not in progress.errors:
                progress.errors.append(error_text)
        gpu_init_failed = error_requires_gpu_reinit_retire(error_text)
        if error_requires_worker_retire(error_text) or gpu_init_failed:
            retire_worker = True
        elif error_is_device_recreatable(error_text) or error_is_recoverable(error_text):
            # Device loss and OOM errors are caught by the C++ worker loop — the process
            # stays alive. Do not force-retire; the liveness check below retires only if
            # the process has exited. On the next bake, ensure_d3d12_runtime() will
            # recreate the device if device_loss_pending is set.
            pass
        deps.protocol.write_progress(state.progress_path, progress)
        if gpu_init_failed:
            note = (
                "Resident bake worker could not initialize its GPU device "
                f"({_first_line(error_text)}); retiring it so the next bake starts a fresh "
                "backend that re-creates the device"
            )
            _notify_gpu_init_failure_retire(deps, error_text)
        elif retire_worker:
            note = "Resident bake worker reported a fatal state error; retiring worker before the next bake"
        elif error_is_device_recreatable(error_text):
            note = "Resident bake worker reported GPU device loss; keeping worker alive for device recreation"
        elif error_is_recoverable(error_text):
            note = "Resident bake worker reported a recoverable error; keeping worker if still running"
        else:
            note = "Resident bake worker reported an error"
        returncode = 1
    elif returncode != 0:
        # Only stderr is error text. The job's live log (stdout_path) is the start
        # banner and progress lines; quoting it made a crashed worker read as
        # "Bake failed" followed by "Bake started" with no reason (SvAT, 2026-09-26).
        detail_text = (stderr_text or "").strip()
        progress.status = deps.constants.STATUS_FAILED
        stall_force_failed = bool(getattr(state, "stall_force_failed", False))
        # A worker we terminated ourselves keeps the watchdog's explanation as the
        # headline; whatever it printed on the way down is kept as detail.
        if not stall_force_failed:
            headline = describe_unexpected_worker_exit(
                returncode,
                group=str(getattr(progress, "active_group", "") or ""),
                map_name=str(getattr(progress, "active_map", "") or ""),
                stderr_text=detail_text,
            )
            progress.message = headline
            progress.errors = [headline]
        if detail_text and detail_text not in progress.errors:
            progress.errors.append(detail_text)
        deps.protocol.write_progress(state.progress_path, progress)
        note = (
            "Bake worker terminated by the stall watchdog"
            if stall_force_failed
            else "Resident bake worker exited unexpectedly"
        )
    deps.append_progress_log_fn(state, progress, force=True)
    state.last_progress = progress

    deps.write_backend_log_fn(
        state.backend_log_path,
        title="Backend bake run",
        backend_path=state.backend_path,
        command=bake_worker_log_command(state.job_path, state.selected_map_types),
        cwd=str(state.job_path.parent),
        returncode=int(returncode if returncode is not None else 1),
        stdout=stdout_text,
        stderr=stderr_text,
        backend_version=state.backend_version,
        note=note,
    )
    snapshot = deps.snapshot_cls(
        job_id=state.job_id,
        job_path=str(state.job_path),
        progress_path=str(state.progress_path),
        running=False,
        cancel_requested=bool(state.cancel_requested),
        cancel_requested_at=float(getattr(state, "cancel_requested_at", 0.0) or 0.0),
        pause_requested=bool(state.pause_requested),
        start_time=float(getattr(state, "start_time", 0.0) or 0.0),
    )
    if current_worker is not None and current_worker.process.poll() is not None:
        current_worker = stop_bake_worker(current_worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)
    elif retire_worker and current_worker is not None:
        current_worker = stop_bake_worker(current_worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)
    deps.clear_bake_cancel_request_fn(state.progress_path)
    deps.clear_bake_pause_request_fn(state.progress_path)
    deps.release_workspace_shared_memory_fn(state.job_path.parent)
    # This is the only path that retires the active bake, so it is the only place
    # the per-bake Win32 progress event is guaranteed to be closed. It used to be
    # closed solely by _clear_active_bake_state (file load / cache clear), which
    # leaked one kernel handle per completed bake for the life of the session.
    if state.progress_event_handle is not None:
        try:
            deps.close_bake_progress_event_fn(state.progress_event_handle)
        except Exception:
            pass
        state.progress_event_handle = None
    # The bake is over, retried or not: the next worker spawn uses the artist's settings.
    clear_backend_env_overrides()
    return deps.poll_result_cls(snapshot=snapshot, progress=progress, finished=True), None, current_worker


def cancel_active_bake(current_active_bake, current_worker, *, deps: BakeWorkerControlDeps, force: bool = False):
    state = current_active_bake
    if state is None:
        return current_active_bake, current_worker
    if force:
        # Second press of Stop. A graceful cancel lands at the worker's next
        # checkpoint, which on a slow machine is long enough that users conclude the
        # button is broken and press again. Take that second press literally and stop
        # the worker now, at the cost of a cold worker on the next bake.
        print("[MasterBaker] force-stopping the bake worker on a repeated cancel request")
        try:
            deps.write_bake_cancel_request_fn(state.progress_path, job_id=state.job_id)
        except Exception:
            pass
        if current_worker is not None:
            current_worker = stop_bake_worker(
                current_worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn
            )
        try:
            if state.process.poll() is None:
                state.process.terminate()
        except Exception:
            pass
        return state, current_worker
    state.cancel_requested = True
    if hasattr(state, "cancel_requested_at"):
        state.cancel_requested_at = time.monotonic()
    try:
        deps.write_bake_cancel_request_fn(state.progress_path, job_id=state.job_id)
    except Exception:
        if current_worker is not None:
            current_worker = stop_bake_worker(current_worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)
        elif state.process.poll() is None:
            state.process.terminate()
    return state, current_worker


def pause_active_bake(current_active_bake, current_worker, *, deps: BakeWorkerControlDeps):
    state = current_active_bake
    if state is None:
        return current_active_bake, current_worker
    state.pause_requested = True
    try:
        deps.write_bake_pause_request_fn(state.progress_path, job_id=state.job_id)
    except Exception:
        pass
    return state, current_worker


def resume_active_bake(current_active_bake, current_worker, *, deps: BakeWorkerControlDeps):
    state = current_active_bake
    if state is None:
        return current_active_bake, current_worker
    state.pause_requested = False
    deps.clear_bake_pause_request_fn(state.progress_path)
    return state, current_worker
