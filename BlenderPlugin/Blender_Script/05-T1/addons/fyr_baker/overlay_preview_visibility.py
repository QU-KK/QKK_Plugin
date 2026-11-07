from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import bpy

from . import properties
from .overlay_keys import overlay_settings_state as _overlay_settings_state
from .overlay_events import PreviewVisibilitySyncState


@dataclass(slots=True)
class PreviewVisibilityDeps:
    preview_suppressed_for_context: Callable[[object], bool]
    resolve_project_group: Callable[[object], tuple]
    restore_preview_hidden_objects: Callable[..., None]
    clear_preview_proxy_states: Callable[..., None]
    clear_heatmap_preview: Callable[[], None]
    sync_generated_custom_cage_visibility: Callable[[object, object], None]
    reset_high_reference_runtime: Callable[[], None]
    sync_high_reference_preview_objects: Callable[[object, object, object], set[int]]
    sync_preview_proxy_objects: Callable[[object, object, object], None]
    sync_heatmap_preview: Callable[[object, object, object], None]


@dataclass(slots=True)
class PreviewCleanupDeps:
    reset_preview_visibility_sync_runtime: Callable[[], None]
    cleanup_preview_runtime: Callable[[], None]
    reset_high_reference_runtime: Callable[[], None]
    reset_auto_cage_preview_runtime: Callable[[], None]
    reset_distance_average_normals_preview_runtime: Callable[[], None]
    invalidate_overlay_cache: Callable[..., None]


def reset_preview_visibility_sync_runtime(
    state: PreviewVisibilitySyncState,
    *,
    timer_fn: Callable[[], float | None],
) -> None:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and state.timer_registered and hasattr(timers, "unregister"):
        try:
            timers.unregister(timer_fn)
        except Exception:
            pass
    state.timer_registered = False
    state.scene = None


def _preview_session_active(settings) -> bool:
    """True while any map/PBR/live-normal preview session owns the low materials."""
    try:
        session = properties.preview_session_state(settings)
    except Exception:
        return False
    if session is None:
        return False
    return any(
        bool(getattr(session, flag, False))
        for flag in ("preview_on_low_active", "preview_pbr_on_low_active", "live_normal_preview_active")
    )


def _ensure_all_baked_outputs_previewed(project) -> None:
    """Preview every baked output in ``project.latest_outputs``, enabled or not."""
    from . import preview_materials

    for output in getattr(project, "latest_outputs", []):
        image = getattr(output, "image", None)
        if image is not None:
            preview_materials.apply_preview_output(project, output, image)


def sync_preview_visibility_now(scene=None, *, deps: PreviewVisibilityDeps) -> None:
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if settings is None:
        deps.restore_preview_hidden_objects()
        deps.clear_preview_proxy_states()
        deps.clear_heatmap_preview()
        return
    if deps.preview_suppressed_for_context(getattr(bpy, "context", None)):
        deps.restore_preview_hidden_objects()
        deps.clear_preview_proxy_states()
        deps.clear_heatmap_preview()
        return
    _settings, _project, group = deps.resolve_project_group(scene)
    if _project is not None and _preview_session_active(settings):
        # Re-apply the previewed outputs only while a preview session is on.
        # Running this on every redraw sync reassigned the preview material to
        # every low right after Restore Original Materials, and the loop's
        # per-output restore meant only the last output ever stayed applied.
        try:
            _ensure_all_baked_outputs_previewed(_project)
        except Exception:
            pass
    if group is None:
        deps.restore_preview_hidden_objects()
        deps.clear_preview_proxy_states()
        deps.clear_heatmap_preview()
        return
    overlay_state = _overlay_settings_state(settings)
    if bool(getattr(overlay_state, "show_cage_overlay", False)):
        keep_hidden_keys: set[int] = set()
        deps.sync_generated_custom_cage_visibility(group, settings)
        deps.reset_high_reference_runtime()
        keep_hidden_keys.update(deps.sync_high_reference_preview_objects(scene, settings, group))
        deps.restore_preview_hidden_objects(keep_keys=keep_hidden_keys)
        deps.sync_preview_proxy_objects(scene, settings, group)
    else:
        deps.restore_preview_hidden_objects()
        deps.clear_preview_proxy_states()
    deps.sync_heatmap_preview(scene, settings, group)


def sync_preview_visibility(
    scene=None,
    *,
    post_load_overlay_grace_active_fn: Callable[[], bool],
    schedule_preview_visibility_sync_fn: Callable[[object], bool],
    sync_preview_visibility_now_fn: Callable[[object], None],
) -> None:
    if post_load_overlay_grace_active_fn():
        schedule_preview_visibility_sync_fn(scene)
        return
    sync_preview_visibility_now_fn(scene)


def cleanup_preview_runtime_for_save(*, deps: PreviewCleanupDeps) -> None:
    deps.reset_preview_visibility_sync_runtime()
    deps.cleanup_preview_runtime()
    deps.reset_high_reference_runtime()
    deps.reset_auto_cage_preview_runtime()
    deps.reset_distance_average_normals_preview_runtime()
    deps.invalidate_overlay_cache()
