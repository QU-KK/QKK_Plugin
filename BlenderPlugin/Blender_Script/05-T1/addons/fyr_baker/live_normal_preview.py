from __future__ import annotations

from dataclasses import dataclass

from . import properties


@dataclass(slots=True)
class LiveNormalPreviewRuntimeState:
    requested: bool = False
    due_at: float = 0.0
    reason: str = ""
    timer_registered: bool = False
    job: dict[str, object] | None = None
    last_signature: tuple | None = None


def find_live_normal_preview_record(scene_project_records, *, preview_on_low_project_name_fn):
    for scene, settings, project in scene_project_records():
        if settings is None:
            continue
        session_state = properties.preview_session_state(settings)
        if not bool(getattr(session_state, "live_normal_preview_active", False)):
            continue
        scene_name = str(getattr(session_state, "live_normal_preview_scene_name", "") or "")
        if scene_name and scene_name != str(getattr(scene, "name", "") or ""):
            continue
        if str(getattr(session_state, "live_normal_preview_project_name", "") or "") != preview_on_low_project_name_fn(project):
            continue
        group_name = str(getattr(session_state, "live_normal_preview_group_name", "") or "")
        group = next(
            (candidate for candidate in getattr(project, "groups", []) if str(getattr(candidate, "name", "") or "") == group_name),
            None,
        )
        if group is None:
            continue
        return scene, settings, project, group
    return None, None, None, None


def clear_live_normal_preview_request(state: LiveNormalPreviewRuntimeState) -> None:
    state.requested = False
    state.due_at = 0.0
    state.reason = ""
    state.timer_registered = False


def ensure_live_normal_preview_timer_registered(
    state: LiveNormalPreviewRuntimeState,
    *,
    timers,
    timer_fn,
    first_interval: float,
) -> bool:
    if state.timer_registered:
        return True
    if timers is None or not hasattr(timers, "register"):
        return False
    timers.register(timer_fn, first_interval=max(0.01, float(first_interval)))
    state.timer_registered = True
    return True


def cancel_live_normal_preview_runtime(
    state: LiveNormalPreviewRuntimeState,
    *,
    active_bake_snapshot_fn,
    cancel_active_bake_fn,
) -> None:
    snapshot = active_bake_snapshot_fn()
    if (
        state.job is not None
        and snapshot is not None
        and snapshot.running
        and str(getattr(snapshot, "job_id", "") or "") == str(state.job.get("job_id", "") or "")
    ):
        cancel_active_bake_fn()
    state.job = None
    clear_live_normal_preview_request(state)


def live_normal_preview_signature(
    project,
    group,
    *,
    constants_module,
    resolve_live_normal_preview_dimensions_fn,
    find_map_setting_fn,
    effective_normal_format_fn,
    map_flip_green_fn,
    default_normal_format_for_map_fn,
    preview_on_low_project_name_fn,
) -> tuple:
    preview_width, preview_height = resolve_live_normal_preview_dimensions_fn(project)
    normal_map = find_map_setting_fn(project, constants_module.MAP_NORMAL)
    projection_state = properties.group_projection_settings_state(group)
    normal_format = (
        effective_normal_format_fn(normal_map)
        if normal_map is not None
        else default_normal_format_for_map_fn(constants_module.MAP_NORMAL)
    )
    return (
        preview_on_low_project_name_fn(project),
        str(getattr(group, "name", "") or ""),
        preview_width,
        preview_height,
        str(getattr(project, "tangent_basis", "") or ""),
        str(getattr(projection_state, "uv_layer_name", "") or ""),
        str(getattr(projection_state, "cage_mode", "") or ""),
        round(float(getattr(projection_state, "cage_offset", 0.0) or 0.0), 6),
        bool(getattr(projection_state, "average_normals", True)),
        tuple(
            (
                str(getattr(getattr(slot, "object_ref", None), "name", "") or ""),
                round(float(getattr(slot, "cage_offset_delta", 0.0) or 0.0), 6),
            )
            for slot in getattr(group, "low_meshes", [])
            if getattr(slot, "object_ref", None) is not None
        ),
        tuple(
            str(getattr(getattr(slot, "object_ref", None), "name", "") or "")
            for slot in properties.effective_high_mesh_slots(group)
            if getattr(slot, "object_ref", None) is not None
        ),
        properties.group_uses_low_as_high(group),
        str(getattr(getattr(projection_state, "custom_cage", None), "name", "") or ""),
        str(getattr(normal_map, "normal_space", constants_module.MAP_NORMAL_SPACE_TANGENT) or constants_module.MAP_NORMAL_SPACE_TANGENT),
        str(normal_format or ""),
        map_flip_green_fn(normal_map) if normal_map is not None else False,
    )


def live_normal_preview_timer_tick(
    state: LiveNormalPreviewRuntimeState,
    *,
    find_live_normal_preview_record_fn,
    active_bake_snapshot_fn,
    now_fn,
    live_normal_preview_signature_fn,
    context,
    prepare_live_normal_preview_job_fn,
    preview_on_low_project_name_fn,
    launch_bake_job_background_fn,
    start_background_polling_fn,
    handle_background_bake_update_fn,
) -> float | None:
    # Blender unregisters a timer whose callback raises, and the caller's state sync
    # (operators._live_normal_preview_timer) never runs on that path -- so an escaping
    # exception left ``timer_registered`` True with no timer alive, and nothing could
    # ever schedule a refresh again for the rest of the session. Everything that can
    # raise runs inside a try that clears the flag on its way out.
    try:
        scene, settings, project, group = find_live_normal_preview_record_fn()
        if scene is None or settings is None or project is None or group is None:
            clear_live_normal_preview_request(state)
            return None

        active_snapshot = active_bake_snapshot_fn()
        if state.job is not None:
            if active_snapshot is not None and active_snapshot.running:
                return 0.25
            state.job = None

        now = now_fn()
        if now < state.due_at:
            return max(0.05, min(0.25, state.due_at - now))

        if active_snapshot is not None and active_snapshot.running:
            return 0.25

        signature = live_normal_preview_signature_fn(project, group)
        if not state.requested and signature == state.last_signature:
            state.timer_registered = False
            return None

        if context is None:
            state.timer_registered = False
            return None
    except Exception:
        state.job = None
        clear_live_normal_preview_request(state)
        state.timer_registered = False
        return None

    try:
        prepared = prepare_live_normal_preview_job_fn(context, project, group)
        session_state = properties.preview_session_state(settings)
        session_state.live_normal_preview_output_path = str(prepared.output_path)
        state.job = {
            "job_id": prepared.job.job_id,
            "scene_name": str(getattr(scene, "name", "") or ""),
            "project_name": preview_on_low_project_name_fn(project),
            "group_name": str(getattr(group, "name", "") or ""),
            "output_path": str(prepared.output_path),
            "signature": signature,
        }
        state.requested = False
        launch_bake_job_background_fn(
            prepared.job_path,
            prepared.progress_path,
            job_id=prepared.job.job_id,
        )
        start_background_polling_fn(handle_background_bake_update_fn)
    except Exception as exc:
        state.job = None
        clear_live_normal_preview_request(state)
        try:
            settings.status_message = f"Live preview failed: {exc}"
        except Exception:
            pass
        state.timer_registered = False
        return None
    # Returning None unregisters the Blender timer, so the bookkeeping flag has to
    # come down with it. Leaving it True made `ensure_live_normal_preview_timer_registered`
    # believe a timer was still live, and no later refresh was ever scheduled again.
    state.timer_registered = False
    return None


def request_live_normal_preview_refresh(
    state: LiveNormalPreviewRuntimeState,
    context,
    *,
    ensure_live_normal_preview_timer_registered_fn,
    now_fn,
    reason: str = "",
    delay_seconds: float = 0.2,
) -> bool:
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if settings is None:
        return False
    session_state = properties.preview_session_state(settings)
    if not bool(getattr(session_state, "live_normal_preview_active", False)):
        return False

    delay_seconds = max(0.0, float(delay_seconds))
    now = now_fn()
    state.requested = True
    state.reason = str(reason or "")
    state.due_at = max(state.due_at, now + delay_seconds)
    return ensure_live_normal_preview_timer_registered_fn(delay_seconds)


def handle_live_normal_preview_background_update(
    state: LiveNormalPreviewRuntimeState,
    result,
    *,
    find_live_normal_preview_record_fn,
    sync_preview_material_for_project_fn,
    tag_redraw_all_view3d_fn,
    ensure_live_normal_preview_timer_registered_fn,
    constants_module,
) -> bool:
    snapshot = getattr(result, "snapshot", None)
    if snapshot is None or state.job is None:
        return False
    if str(getattr(snapshot, "job_id", "") or "") != str(state.job.get("job_id", "") or ""):
        return False

    scene, settings, project, _group = find_live_normal_preview_record_fn()
    if getattr(result, "finished", False):
        if scene is not None and settings is not None and project is not None:
            session_state = properties.preview_session_state(settings)
            progress_status = str(getattr(result.progress, "status", "") or "")
            if not result.progress.errors and progress_status not in {
                constants_module.STATUS_FAILED,
                constants_module.STATUS_CANCELLED,
                constants_module.STATUS_CANCELLING,
            }:
                state.last_signature = state.job.get("signature")
                session_state.live_normal_preview_output_path = str(state.job.get("output_path", "") or "")
                try:
                    sync_preview_material_for_project_fn(scene, project)
                except Exception:
                    pass
                try:
                    tag_redraw_all_view3d_fn(scene=scene)
                except Exception:
                    pass
        state.job = None
        if state.requested:
            ensure_live_normal_preview_timer_registered_fn(0.05)
        return True
    return True
