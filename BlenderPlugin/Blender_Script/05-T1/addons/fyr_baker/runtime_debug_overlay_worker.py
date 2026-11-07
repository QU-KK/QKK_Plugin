from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import properties


# runtime.py round-trips DebugOverlayRefreshState through module globals field by field, so
# the requested target names do not survive the trip from the request to the timer tick that
# launches the worker. Mirror the pending request's target here (one pending request at a
# time, exactly like the refresh state itself) so the launch resolves the group that asked.
_PENDING_REQUEST_TARGET: tuple[str, str] = ("", "")


def _timer_still_registered(timers, callback) -> bool:
    """True when Blender still owns ``callback``.

    Mirrors runtime._timer_still_registered: non-persistent app timers are discarded
    on file load while the Python "registered" flags that guard their re-registration
    survive it. When ``is_registered`` is unavailable, trust the flag.
    """
    try:
        if hasattr(timers, "is_registered"):
            return bool(timers.is_registered(callback))
    except Exception:
        pass
    return True


def _record_pending_request_target(project_name: str, group_name: str) -> None:
    global _PENDING_REQUEST_TARGET
    _PENDING_REQUEST_TARGET = (str(project_name or ""), str(group_name or ""))


@dataclass(slots=True)
class DebugOverlayRefreshState:
    requested: bool = False
    due_at: float = 0.0
    reason: str = ""
    requested_at: float = 0.0
    view: object = None
    timer_registered: bool = False
    last_request_log_signature: tuple | None = None
    last_request_log_at: float = 0.0
    # Names, never datablock pointers: the request outlives the draw that made it and the
    # collection can be re-sorted or trimmed before the timer launches the worker.
    project_name: str = ""
    group_name: str = ""


@dataclass(slots=True)
class DebugOverlayWorkerProcessDeps:
    debug_worker_state_cls: type
    protocol: Any
    queue_module: Any
    threading_module: Any
    subprocess_module: Any
    repo_root_fn: Callable[[], Path]
    resolve_backend_executable_fn: Callable[[], Path]
    ensure_backend_compatible_fn: Callable[..., str]
    debug_overlay_run_log_path_fn: Callable[[str | Path], Path]
    debug_overlay_live_log_path_fn: Callable[[str | Path], Path]
    close_log_handle_fn: Callable[[object], None]
    append_live_log_fn: Callable[[str | Path, str], None]
    format_debug_overlay_event_block_fn: Callable[..., str]
    maybe_open_backend_log_window_fn: Callable[..., bool]


@dataclass(slots=True)
class DebugOverlayCoordinatorDeps:
    active_debug_state_cls: type
    constants: Any
    protocol: Any
    queue_module: Any
    os_module: Any
    time_monotonic_fn: Callable[[], float]
    debug_overlay_enabled_fn: Callable[[object], bool]
    background_polling_supported_fn: Callable[[], bool]
    active_debug_result_key_fn: Callable[[object, object, object], tuple]
    debug_overlay_run_log_path_fn: Callable[[str | Path], Path]
    peek_debug_overlay_result_fn: Callable[[object, object, object], object | None]
    append_debug_overlay_event_fn: Callable[..., object]
    append_live_log_fn: Callable[[str | Path, str], None]
    format_debug_overlay_event_block_fn: Callable[..., str]
    write_backend_log_fn: Callable[..., object]
    start_debug_overlay_worker_fn: Callable[[str | Path], object]
    stop_debug_overlay_worker_fn: Callable[..., object]
    clear_active_debug_state_fn: Callable[[], None]
    prepare_debug_overlay_job_fn: Callable[..., object]
    peek_active_project_fn: Callable[[object], object | None]
    peek_active_group_fn: Callable[[object], object | None]
    invalidate_overlay_cache_fn: Callable[[], None]
    tag_redraw_all_view3d_fn: Callable[[], None]
    active_debug_getter_fn: Callable[[], object | None]
    build_geometry_transport_retry_job_fn: Callable[[str | Path], Path] = (
        lambda path: Path(path)
    )
    release_workspace_geometry_transports_fn: Callable[[str | Path], None] = (
        lambda _path: None
    )


def debug_worker_reader(stdout_handle, response_queue, *, load_debug_overlay_result_fn) -> None:
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
            parts = line.split("\t", 2)
            status = parts[0]
            if status == "OK":
                output_path = parts[1] if len(parts) >= 2 else ""
                elapsed_ms = 0.0
                if len(parts) >= 3:
                    try:
                        elapsed_ms = float(parts[2])
                    except Exception:
                        elapsed_ms = 0.0
                loaded_result = None
                load_error = ""
                if output_path:
                    try:
                        candidate_path = Path(output_path)
                        if candidate_path.exists():
                            loaded_result = load_debug_overlay_result_fn(candidate_path)
                    except Exception as exc:
                        load_error = str(exc)
                response_queue.put(
                    {
                        "status": "ok",
                        "output": output_path,
                        "elapsed_ms": elapsed_ms,
                        "loaded_result": loaded_result,
                        "load_error": load_error,
                    }
                )
                continue
            if status == "ERR":
                response_queue.put({"status": "error", "error": parts[1] if len(parts) >= 2 else "Debug worker failed"})
                continue
            if status == "TRANSPORT_ERR":
                response_queue.put(
                    {
                        "status": "transport_error",
                        "transport_kind": parts[1] if len(parts) >= 2 else "",
                        "error": parts[2] if len(parts) >= 3 else "Geometry transport failed",
                    }
                )
                continue
            response_queue.put({"status": "error", "error": line})
    except Exception as exc:
        response_queue.put({"status": "error", "error": str(exc)})


def stop_debug_overlay_worker(current_worker, *, terminate: bool = False, close_log_handle_fn):
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

    close_log_handle_fn(worker.stdin_handle)
    close_log_handle_fn(worker.stdout_handle)
    close_log_handle_fn(worker.stderr_handle)
    return None


def start_debug_overlay_worker(
    result_path: str | Path,
    *,
    current_worker,
    deps: DebugOverlayWorkerProcessDeps,
):
    worker = current_worker
    if worker is not None and worker.process.poll() is None:
        return worker
    if worker is not None:
        worker = stop_debug_overlay_worker(worker, terminate=True, close_log_handle_fn=deps.close_log_handle_fn)

    backend_path = deps.resolve_backend_executable_fn()
    backend_log_path = deps.debug_overlay_run_log_path_fn(result_path)
    backend_version = deps.ensure_backend_compatible_fn(backend_path, log_path=backend_log_path)
    stderr_path = deps.debug_overlay_live_log_path_fn(result_path)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.write_text("", encoding="utf-8")
    deps.append_live_log_fn(
        stderr_path,
        deps.format_debug_overlay_event_block_fn(
            "worker-start",
            fields={
                "backend_name": Path(backend_path).name,
                "backend_version": backend_version,
            },
        ),
    )
    deps.maybe_open_backend_log_window_fn(
        stderr_path,
        title=f"Fyr Baker Debug Log: {Path(result_path).stem}",
        follow=True,
    )
    stderr_handle = stderr_path.open("a", encoding="utf-8")
    creation_flags = int(getattr(deps.subprocess_module, "CREATE_NO_WINDOW", 0))
    from .runtime_bake_worker import (
        assign_process_to_kill_on_close_job,
        backend_child_env,
        spawn_feedback_suppression_kwargs,
    )

    process = deps.subprocess_module.Popen(
        [str(backend_path), "debug-worker"],
        cwd=str(deps.repo_root_fn()),
        stdin=deps.subprocess_module.PIPE,
        stdout=deps.subprocess_module.PIPE,
        stderr=stderr_handle,
        text=True,
        bufsize=1,
        creationflags=creation_flags,
        env=backend_child_env(None),
        **spawn_feedback_suppression_kwargs(deps.subprocess_module),
    )
    assign_process_to_kill_on_close_job(process)
    response_queue = deps.queue_module.Queue()
    stdout_handle = getattr(process, "stdout", None)
    stdin_handle = getattr(process, "stdin", None)
    response_thread = deps.threading_module.Thread(
        target=debug_worker_reader,
        args=(stdout_handle, response_queue),
        kwargs={"load_debug_overlay_result_fn": deps.protocol.load_debug_overlay_result},
        name="MasterBakerDebugWorkerReader",
        daemon=True,
    )
    if stdout_handle is not None:
        response_thread.start()

    return deps.debug_worker_state_cls(
        process=process,
        backend_path=backend_path,
        backend_version=backend_version,
        stderr_path=stderr_path,
        stdin_handle=stdin_handle,
        stdout_handle=stdout_handle,
        stderr_handle=stderr_handle,
        response_queue=response_queue,
        response_thread=response_thread,
    )


def resolve_requested_project_group(scene, deps: DebugOverlayCoordinatorDeps, *, project_name: str = "", group_name: str = ""):
    """Resolve the project/group a refresh was requested for, falling back to the active
    pair. Coverage draws for non-active groups request their own refresh, so resolving the
    active group instead would leave those groups permanently without a debug result."""
    project = deps.peek_active_project_fn(scene) if scene is not None else None
    if project_name:
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        for candidate in getattr(settings, "projects", None) or ():
            if str(getattr(candidate, "name", "") or "") == project_name:
                project = candidate
                break
    group = None
    if project is not None and group_name:
        for candidate in getattr(project, "groups", None) or ():
            if str(getattr(candidate, "name", "") or "") == group_name:
                group = candidate
                break
    if group is None and project is not None:
        group = deps.peek_active_group_fn(project)
    return project, group


def launch_debug_overlay_process(context, refresh_state: DebugOverlayRefreshState, *, deps: DebugOverlayCoordinatorDeps):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if scene is None or settings is None or not deps.debug_overlay_enabled_fn(settings):
        return None, refresh_state

    project_name = refresh_state.project_name
    group_name = refresh_state.group_name
    if not group_name:
        project_name, group_name = _PENDING_REQUEST_TARGET
    project, group = resolve_requested_project_group(
        scene,
        deps,
        project_name=project_name,
        group_name=group_name,
    )
    if project is None or group is None:
        return None, refresh_state

    launch_started_at = deps.time_monotonic_fn()
    prepared = deps.prepare_debug_overlay_job_fn(context, project, group, debug_view=refresh_state.view)
    result_key = deps.active_debug_result_key_fn(scene, project, group)
    result_path = prepared.result_path
    backend_log_path = deps.debug_overlay_run_log_path_fn(result_path)
    worker = deps.start_debug_overlay_worker_fn(result_path)
    deps.append_debug_overlay_event_fn(
        "launch",
        context=context,
        scene=scene,
        project=project,
        group=group,
        result_path=result_path,
        reason=refresh_state.reason or "unspecified",
        result_key=result_key,
        job_path=prepared.job_path,
        result_path_text=prepared.result_path,
        low_mesh_count=sum(1 for item in getattr(group, "low_meshes", []) if getattr(item, "object_ref", None) is not None),
        high_mesh_count=sum(1 for item in properties.effective_high_mesh_slots(group) if getattr(item, "object_ref", None) is not None),
        cage_mode=str(getattr(group, "cage_mode", "") or ""),
        cage_offset=round(float(getattr(group, "cage_offset", 0.0)), 6),
        cached_result=deps.peek_debug_overlay_result_fn(scene, project, group) is not None,
        view_signature=str(getattr(getattr(getattr(prepared, "job", None), "debug_view", None), "view_signature", "") or "")[:12],
    )
    try:
        if worker.stdin_handle is not None:
            deps.append_live_log_fn(
                worker.stderr_path,
                deps.format_debug_overlay_event_block_fn(
                    "run",
                    project=project,
                    group=group,
                    fields={
                        "group_name": prepared.group_name,
                        "job_path": prepared.job_path,
                    },
                ),
            )
            worker.stdin_handle.write(
                f"RUN\t{prepared.job_path}\t{prepared.group_name}\t{prepared.result_path}\n"
            )
            worker.stdin_handle.flush()
    except Exception:
        deps.stop_debug_overlay_worker_fn(terminate=True)
        raise

    refresh_state.view = None
    refresh_state.project_name = ""
    refresh_state.group_name = ""
    _record_pending_request_target("", "")
    return (
        deps.active_debug_state_cls(
            result_key=result_key,
            job_path=prepared.job_path,
            result_path=prepared.result_path,
            backend_log_path=backend_log_path,
            backend_path=worker.backend_path,
            backend_version=worker.backend_version,
            refresh_reason=refresh_state.reason or "unspecified",
            requested_at_monotonic=float(refresh_state.requested_at),
            launched_at_monotonic=launch_started_at,
            input_signature=getattr(prepared, "input_signature", None),
            group_name=prepared.group_name,
        ),
        refresh_state,
    )


def finalize_active_debug_process(
    current_active_debug,
    current_worker,
    *,
    debug_results: dict,
    debug_result_input_signatures: dict,
    deps: DebugOverlayCoordinatorDeps,
):
    state = current_active_debug
    worker = current_worker
    if state is None or worker is None:
        return current_active_debug

    if worker.process.poll() is not None and worker.response_queue.empty():
        deps.append_debug_overlay_event_fn(
            "worker-exit",
            result_path=state.result_path,
            reason=state.refresh_reason or "unspecified",
            returncode=worker.process.poll(),
            note="worker exited before reporting a result",
        )
        deps.stop_debug_overlay_worker_fn(terminate=True)
        deps.release_workspace_geometry_transports_fn(state.job_path.parent)
        deps.clear_active_debug_state_fn()
        return None

    handled_response = False
    while True:
        try:
            response = worker.response_queue.get_nowait()
        except deps.queue_module.Empty:
            break

        handled_response = True
        if state is None:
            # The ok/error branches below finalise the run and drop the state; any
            # further queued response has nothing to attach to and used to hit
            # state.result_path on None.
            continue
        status = str(response.get("status", ""))
        if status == "transport_error":
            if int(getattr(state, "transport_retry_count", 0) or 0) == 0:
                try:
                    retry_path = deps.build_geometry_transport_retry_job_fn(
                        state.job_path
                    )
                    state.transport_retry_count = 1
                    state.job_path = Path(retry_path)
                    worker.stdin_handle.write(
                        f"RUN\t{state.job_path}\t{state.group_name}\t{state.result_path}\n"
                    )
                    worker.stdin_handle.flush()
                    continue
                except Exception as exc:
                    response = {
                        "status": "error",
                        "error": str(exc),
                    }
                    status = "error"
            else:
                response = {
                    "status": "error",
                    "error": str(
                        response.get(
                            "error",
                            "Geometry transport retry failed",
                        )
                    ),
                }
                status = "error"
        if status == "ok":
            output_path = str(response.get("output", "") or "")
            deps.append_live_log_fn(
                worker.stderr_path,
                deps.format_debug_overlay_event_block_fn(
                    "ok",
                    project=None,
                    group=None,
                    fields={
                        "elapsed_ms": float(response.get("elapsed_ms", 0.0)),
                        "output_path": output_path,
                    },
                ),
            )
            if output_path and deps.os_module.path.normcase(output_path) == deps.os_module.path.normcase(str(state.result_path)) and state.result_path.exists():
                try:
                    loaded_result = response.get("loaded_result")
                    if loaded_result is None:
                        loaded_result = deps.protocol.load_debug_overlay_result(state.result_path)
                    debug_results[state.result_key] = loaded_result
                    if state.input_signature is not None:
                        debug_result_input_signatures[state.result_key] = state.input_signature
                    total_ms = 0.0
                    if state.requested_at_monotonic > 0.0:
                        total_ms = max(0.0, (deps.time_monotonic_fn() - state.requested_at_monotonic) * 1000.0)
                    queue_ms = 0.0
                    if state.requested_at_monotonic > 0.0 and state.launched_at_monotonic > 0.0:
                        queue_ms = max(0.0, (state.launched_at_monotonic - state.requested_at_monotonic) * 1000.0)
                    deps.append_debug_overlay_event_fn(
                        "result",
                        result_path=state.result_path,
                        reason=state.refresh_reason or "unspecified",
                        backend_elapsed_ms=float(response.get("elapsed_ms", 0.0)),
                        total_ms=total_ms,
                        queue_ms=queue_ms,
                        low_tris=deps.protocol.debug_overlay_triangle_count(getattr(loaded_result, "heatmap_low_fill_positions", [])),
                        medium_tris=deps.protocol.debug_overlay_triangle_count(getattr(loaded_result, "heatmap_medium_fill_positions", [])),
                        high_tris=deps.protocol.debug_overlay_triangle_count(getattr(loaded_result, "heatmap_high_fill_positions", [])),
                        miss_segments=deps.protocol.debug_overlay_segment_count(getattr(loaded_result, "ray_miss_line_positions", [])),
                        heatmap_image=Path(str(getattr(loaded_result, "heatmap_image_path", "") or "")).name,
                        view_signature=str(getattr(loaded_result, "view_signature", "") or "")[:12],
                    )
                    deps.invalidate_overlay_cache_fn()
                    deps.tag_redraw_all_view3d_fn()
                except Exception as exc:
                    deps.append_debug_overlay_event_fn(
                        "result-error",
                        result_path=state.result_path,
                        reason=state.refresh_reason or "unspecified",
                        error=str(exc),
                    )
            else:
                deps.append_debug_overlay_event_fn(
                    "result-mismatch",
                    result_path=state.result_path,
                    reason=state.refresh_reason or "unspecified",
                    output_path=output_path,
                    expected_path=state.result_path,
                    exists=state.result_path.exists(),
                )
            deps.write_backend_log_fn(
                state.backend_log_path,
                title="Backend debug overlay refresh",
                backend_path=state.backend_path,
                command=["debug-worker", str(state.job_path), state.result_key[2], str(state.result_path)],
                cwd=str(state.job_path.parent),
                returncode=0,
                stdout=f"elapsed_ms={float(response.get('elapsed_ms', 0.0)):.2f}\n",
                stderr="",
                backend_version=state.backend_version,
            )
            state = None
            deps.release_workspace_geometry_transports_fn(
                Path(current_active_debug.job_path).parent
            )
            continue

        if status == "error":
            error_text = str(response.get("error", "Debug worker failed") or "Debug worker failed")
            deps.append_debug_overlay_event_fn(
                "worker-error",
                result_path=state.result_path,
                reason=state.refresh_reason or "unspecified",
                error=error_text,
            )
            deps.write_backend_log_fn(
                state.backend_log_path,
                title="Backend debug overlay refresh failed",
                backend_path=state.backend_path,
                command=["debug-worker", str(state.job_path), state.result_key[2], str(state.result_path)],
                cwd=str(state.job_path.parent),
                returncode=1,
                stdout="",
                stderr=error_text,
                backend_version=state.backend_version,
            )
            deps.release_workspace_geometry_transports_fn(
                Path(state.job_path).parent
            )
            state = None

    if handled_response and worker.process.poll() is not None:
        deps.stop_debug_overlay_worker_fn(terminate=True)
    return state


def debug_overlay_timer(
    refresh_state: DebugOverlayRefreshState,
    *,
    finalize_active_debug_process_fn,
    active_debug_getter_fn,
    launch_debug_overlay_process_fn,
    append_debug_overlay_event_fn,
    clear_active_debug_state_fn,
    context_getter_fn,
    time_monotonic_fn,
    traceback_format_exc_fn,
    print_fn,
    constants,
):
    try:
        finalize_active_debug_process_fn()
    except Exception:
        # Blender drops a timer whose callback raises, but timer_registered would
        # stay True and no refresh could ever be scheduled again this session.
        # Log-file I/O inside finalize (a cleared log folder, a read-only drive)
        # is the usual cause; clear the run and keep the timer alive.
        print_fn(traceback_format_exc_fn())
        try:
            clear_active_debug_state_fn()
        except Exception:
            pass

    if active_debug_getter_fn() is None and refresh_state.requested and time_monotonic_fn() >= refresh_state.due_at:
        refresh_state.requested = False
        try:
            launch_debug_overlay_process_fn(context_getter_fn())
        except Exception as exc:
            append_debug_overlay_event_fn(
                "launch-error",
                context=context_getter_fn(),
                reason=refresh_state.reason or "unspecified",
                error=str(exc),
            )
            print_fn(traceback_format_exc_fn())
            clear_active_debug_state_fn()

    if active_debug_getter_fn() is not None or refresh_state.requested:
        return constants.VIEWPORT_DEBUG_POLL_INTERVAL_SECONDS, refresh_state
    refresh_state.timer_registered = False
    return None, refresh_state


def request_debug_overlay_refresh(
    context,
    refresh_state: DebugOverlayRefreshState,
    *,
    delay_seconds: float | None = None,
    reason: str = "unspecified",
    debug_view=None,
    project=None,
    group=None,
    timers,
    debug_overlay_timer_fn,
    deps: DebugOverlayCoordinatorDeps,
):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    # Coverage stays on for non-active groups by design, so a draw that asks for a refresh
    # has to name the group it drew; only fall back to the active pair when it does not.
    requested_group = group
    if project is None:
        project = deps.peek_active_project_fn(scene) if scene is not None else None
    if group is None:
        group = deps.peek_active_group_fn(project) if project is not None else None
    overlay_state = None
    if settings is not None:
        try:
            from . import properties

            overlay_state = properties.overlay_settings_state(settings)
        except Exception:
            overlay_state = settings
    if not deps.debug_overlay_enabled_fn(settings):
        deps.append_debug_overlay_event_fn(
            "request-skip",
            context=context,
            scene=scene,
            project=project,
            group=group,
            requested_reason=reason or "unspecified",
            skip_reason="disabled",
        )
        return refresh_state
    if (
        group is not None
        and str(getattr(group, "cage_mode", "") or "") == "DISTANCE"
        and overlay_state is not None
        and bool(getattr(overlay_state, "show_error_heatmap", False))
        and not bool(getattr(overlay_state, "show_ray_miss_debug", False))
    ):
        deps.append_debug_overlay_event_fn(
            "request-skip",
            context=context,
            scene=scene,
            project=project,
            group=group,
            requested_reason=reason or "unspecified",
            skip_reason="distance-live-shell",
        )
        return refresh_state
    if not deps.background_polling_supported_fn():
        deps.append_debug_overlay_event_fn(
            "request-skip",
            context=context,
            scene=scene,
            project=project,
            group=group,
            requested_reason=reason or "unspecified",
            skip_reason="background-polling-unsupported",
        )
        return refresh_state
    delay_seconds = max(
        deps.constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        float(delay_seconds if delay_seconds is not None else deps.constants.VIEWPORT_INTERACTION_GRACE_SECONDS),
    )
    view_signature = str(getattr(debug_view, "view_signature", "") or "")[:12]
    cached_result = deps.peek_debug_overlay_result_fn(scene, project, group) is not None if project is not None and group is not None else False
    request_log_signature = (
        reason or "unspecified",
        refresh_state.reason if refresh_state.requested and refresh_state.reason else "",
        round(delay_seconds, 3),
        bool(refresh_state.requested),
        bool(deps.active_debug_getter_fn() is not None),
        bool(cached_result),
        view_signature,
    )
    now_monotonic = deps.time_monotonic_fn()
    if (
        request_log_signature != refresh_state.last_request_log_signature
        or (now_monotonic - refresh_state.last_request_log_at) >= 0.25
    ):
        deps.append_debug_overlay_event_fn(
            "request",
            context=context,
            scene=scene,
            project=project,
            group=group,
            reason=reason or "unspecified",
            previous_reason=refresh_state.reason if refresh_state.requested and refresh_state.reason else "",
            delay_seconds=delay_seconds,
            pending=refresh_state.requested,
            active=deps.active_debug_getter_fn() is not None,
            cached_result=cached_result,
            view_signature=view_signature,
        )
        refresh_state.last_request_log_signature = request_log_signature
        refresh_state.last_request_log_at = now_monotonic
    refresh_state.requested = True
    refresh_state.due_at = now_monotonic + delay_seconds
    refresh_state.reason = reason or "unspecified"
    refresh_state.requested_at = now_monotonic
    refresh_state.view = debug_view
    if requested_group is not None:
        refresh_state.project_name = str(getattr(project, "name", "") or "")
        refresh_state.group_name = str(getattr(requested_group, "name", "") or "")
    else:
        refresh_state.project_name = ""
        refresh_state.group_name = ""
    _record_pending_request_target(refresh_state.project_name, refresh_state.group_name)
    if refresh_state.timer_registered and not _timer_still_registered(timers, debug_overlay_timer_fn):
        # Non-persistent app timers are discarded on file load while the Python flag
        # that guards re-registration survives it, so this guard became a permanent
        # no-op: after File > Open the viewport debug/coverage overlay never refreshed
        # again for the rest of the session, however much the cage, UVs or membership
        # changed. Worse, load_post itself requests a refresh, so the very first thing
        # the new file did was hit the dead branch. runtime._timer_still_registered
        # exists for exactly this and every other guard uses it; this one was missed.
        refresh_state.timer_registered = False
    if not refresh_state.timer_registered:
        timers.register(debug_overlay_timer_fn, first_interval=deps.constants.VIEWPORT_DEBUG_POLL_INTERVAL_SECONDS)
        refresh_state.timer_registered = True
    return refresh_state


def cancel_debug_overlay_refresh(
    refresh_state: DebugOverlayRefreshState,
    *,
    append_debug_overlay_event_fn,
    timers,
    debug_overlay_timer_fn,
):
    append_debug_overlay_event_fn("cancel", reason=refresh_state.reason or "unspecified", pending=refresh_state.requested)
    refresh_state.requested = False
    refresh_state.due_at = 0.0
    refresh_state.reason = ""
    refresh_state.requested_at = 0.0
    refresh_state.view = None
    refresh_state.project_name = ""
    refresh_state.group_name = ""
    _record_pending_request_target("", "")
    if timers is not None:
        try:
            timers.unregister(debug_overlay_timer_fn)
        except Exception:
            pass
    refresh_state.timer_registered = False
    return refresh_state
