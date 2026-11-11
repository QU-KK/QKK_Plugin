from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

import bpy

from . import cage_session, properties, project_structure
from .overlay_keys import (
    bump_depsgraph_id_revisions as _bump_depsgraph_id_revisions,
    revisions_frozen as _revisions_frozen,
    effective_high_mesh_slots as _effective_high_mesh_slots,
    reset_id_revisions as _reset_id_revisions,
)


@dataclass(slots=True)
class PreviewVisibilitySyncState:
    timer_registered: bool = False
    scene: object | None = None


@dataclass(slots=True)
class OverlayRegistrationState:
    draw_handler: object | None = None
    draw_pixel_handler: object | None = None
    screen_heatmap_image: object | None = None
    screen_heatmap_texture: object | None = None
    screen_heatmap_texture_image_pointer: int = 0
    screen_heatmap_result: object | None = None
    screen_heatmap_result_key: tuple | None = None
    last_view_refresh_key: tuple | None = None
    last_view_refresh_signature: str = ""
    last_view_refresh_at: float = 0.0
    post_load_overlay_grace_until: float = 0.0
    interaction_redraw_due_at: float = 0.0
    interaction_redraw_timer_registered: bool = False


@dataclass(slots=True)
class OverlayTrackingDeps:
    resolve_project_group: Callable[[object], tuple]
    iter_valid_meshes: Callable[[object], object]
    is_valid_object: Callable[[object], bool]
    is_valid_mesh: Callable[[object], bool]
    preview_collection_name: str


@dataclass(slots=True)
class OverlayEventBridgeDeps:
    tracking: OverlayTrackingDeps
    debug_overlay_enabled: Callable[[object], bool]
    invalidate_debug_overlay_export_cache: Callable[..., None]
    request_debug_overlay_refresh: Callable[..., None]
    mark_interaction: Callable[[], None]
    tag_redraw_all_view3d: Callable[..., None]
    invalidate_overlay_cache: Callable[..., None]
    reset_auto_cage_preview_runtime: Callable[[], None]
    reset_distance_average_normals_preview_runtime: Callable[[], None]
    reset_preview_visibility_sync_runtime: Callable[[], None]
    clear_preview_proxy_states: Callable[[], None]
    reset_high_reference_runtime: Callable[[], None]
    sync_preview_visibility: Callable[[object], None]
    invalidate_debug_overlay_cache: Callable[..., None]
    cleanup_preview_runtime: Callable[[], None]
    debug_refresh_delay_seconds: float
    now_fn: Callable[[], float]
    auto_select_group_on_selection: bool = False


@dataclass(slots=True)
class OverlayRegistrationDeps:
    draw_group_overlay_fn: Callable[[], None]
    draw_screen_heatmap_overlay_post_pixel_fn: Callable[[], None]
    depsgraph_update_post_fn: Callable[[object, object], None]
    load_post_fn: Callable[[object], None]
    save_pre_fn: Callable[[object], None]
    save_post_fn: Callable[[object], None]
    event_bridge: OverlayEventBridgeDeps
    interaction_redraw_timer_fn: Callable[[], float | None]


def tag_redraw_all_view3d(*, window=None, all_windows: bool = False) -> None:
    """Redraw VIEW_3D areas.

    Without ``window`` the active window is used when there is one; pass
    ``all_windows=True`` to always sweep every window in the window manager.
    """
    target_window = window
    if target_window is None and not all_windows:
        target_window = getattr(bpy.context, "window", None)
    if target_window is not None:
        screen = getattr(target_window, "screen", None)
        if screen is not None:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            return

    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for candidate_window in getattr(wm, "windows", None) or ():
        screen = getattr(candidate_window, "screen", None)
        for area in getattr(screen, "areas", None) or ():
            if getattr(area, "type", None) == "VIEW_3D":
                area.tag_redraw()


def schedule_preview_visibility_sync(
    state: PreviewVisibilitySyncState,
    *,
    timer_fn: Callable[[], float | None],
    scene=None,
    first_interval: float | None = None,
    post_load_overlay_grace_until: float = 0.0,
    now_fn: Callable[[], float],
) -> bool:
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    state.scene = scene
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return False
    if state.timer_registered:
        return True
    delay_seconds = (
        max(0.05, float(first_interval))
        if first_interval is not None
        else max(0.05, post_load_overlay_grace_until - now_fn())
    )
    try:
        timers.register(timer_fn, first_interval=delay_seconds)
        state.timer_registered = True
        return True
    except Exception:
        return False


def preview_visibility_sync_timer_tick(
    state: PreviewVisibilitySyncState,
    *,
    post_load_overlay_grace_active_fn: Callable[[], bool],
    post_load_overlay_grace_delay_fn: Callable[[], float],
    sync_preview_visibility_now_fn: Callable[[object], None],
    tag_redraw_all_view3d_fn: Callable[..., None],
) -> float | None:
    if post_load_overlay_grace_active_fn():
        return post_load_overlay_grace_delay_fn()
    scene = state.scene
    state.scene = None
    state.timer_registered = False
    sync_preview_visibility_now_fn(scene)
    tag_redraw_all_view3d_fn(window=getattr(bpy.context, "window", None))
    return None


def schedule_interaction_redraw(
    state: OverlayRegistrationState,
    *,
    timer_fn: Callable[[], float | None],
    delay_seconds: float,
    now_fn: Callable[[], float],
) -> None:
    timers = getattr(bpy.app, "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    state.interaction_redraw_due_at = max(
        state.interaction_redraw_due_at,
        now_fn() + max(0.01, float(delay_seconds)),
    )
    if state.interaction_redraw_timer_registered:
        return
    try:
        timers.register(timer_fn, first_interval=max(0.01, float(delay_seconds)))
        state.interaction_redraw_timer_registered = True
    except Exception:
        pass


def interaction_redraw_timer_tick(
    state: OverlayRegistrationState,
    *,
    now_fn: Callable[[], float],
    tag_redraw_all_view3d_fn: Callable[..., None],
) -> float | None:
    remaining = state.interaction_redraw_due_at - now_fn()
    if remaining > 0.01:
        return remaining
    state.interaction_redraw_due_at = 0.0
    state.interaction_redraw_timer_registered = False
    tag_redraw_all_view3d_fn(window=getattr(bpy.context, "window", None))
    return None


def tracked_overlay_id_pointers(scene, *, deps: OverlayTrackingDeps) -> set[int]:
    _settings, _project, group = deps.resolve_project_group(scene)
    if group is None:
        return set()

    tracked_groups = [group]
    for preview_group in cage_session.preview_target_groups(scene, context=getattr(bpy, "context", None)):
        if any(existing == preview_group for existing in tracked_groups):
            continue
        tracked_groups.append(preview_group)

    pointers: set[int] = set()

    def _track_object(obj) -> None:
        if not deps.is_valid_object(obj):
            return
        try:
            pointers.add(int(obj.as_pointer()))
        except Exception:
            pass
        data = getattr(obj, "data", None)
        if deps.is_valid_mesh(data):
            try:
                pointers.add(int(data.as_pointer()))
            except Exception:
                pass

    for tracked_group in tracked_groups:
        for obj in deps.iter_valid_meshes(getattr(tracked_group, "low_meshes", [])):
            _track_object(obj)
        for obj in deps.iter_valid_meshes(_effective_high_mesh_slots(tracked_group)):
            _track_object(obj)
        _track_object(getattr(tracked_group, "custom_cage", None))
    return pointers


def paint_only_update(update, paint_only_pointers) -> bool:
    """A depsgraph update that only carries a paint-brush stroke's layer write.

    Blender flags the MESH datablock of a written attribute as updated in transform
    too, so only an Object's transform flag means something actually moved.
    """
    if not paint_only_pointers:
        return False
    id_data = getattr(update, "id", None)
    if id_data is None:
        return False
    try:
        original_id = getattr(id_data, "original", None)
    except Exception:
        original_id = None
    if original_id is None:
        original_id = id_data
    as_pointer = getattr(original_id, "as_pointer", None)
    try:
        pointer = int(as_pointer()) if callable(as_pointer) else None
    except Exception:
        pointer = None
    if pointer not in paint_only_pointers:
        return False
    moved = bool(getattr(update, "is_updated_transform", False)) and hasattr(original_id, "matrix_world")
    return not moved


def depsgraph_requires_static_invalidation(
    scene, depsgraph, *, deps: OverlayTrackingDeps, paint_only_pointers: set[int] | None = None
) -> bool:
    updates = getattr(depsgraph, "updates", None)
    if updates is None:
        return True
    tracked_pointers = tracked_overlay_id_pointers(scene, deps=deps)
    if not tracked_pointers:
        return False

    for update in updates:
        id_data = getattr(update, "id", None)
        if id_data is None:
            return True

        # ``DepsgraphUpdate.id`` hands back the EVALUATED copy of the datablock, whose
        # pointer is never one of the ORIGINAL pointers tracked_overlay_id_pointers
        # collected. Comparing the evaluated pointer therefore matched nothing and this
        # gate answered "no tracked datablock changed" for every real edit, so the
        # static overlay cache (Cage Check coverage included) kept serving the pre-edit
        # result. ``original`` on an original datablock returns itself.
        try:
            original_id = getattr(id_data, "original", None)
        except Exception:
            original_id = None
        if original_id is None:
            original_id = id_data

        id_name = str(getattr(id_data, "name", "") or "")
        if id_name.startswith(deps.preview_collection_name):
            continue
        if id_name.startswith("_MBPreview_"):
            continue
        if bool(getattr(id_data, "get", None)):
            try:
                if bool(id_data.get("_master_baker_preview_proxy")):
                    continue
            except Exception:
                pass

        pointer = None
        as_pointer = getattr(original_id, "as_pointer", None)
        if callable(as_pointer):
            try:
                pointer = int(as_pointer())
            except Exception:
                pointer = None
        if pointer not in tracked_pointers:
            continue
        # A paint-brush stroke writes a layer only: the brush redraws its own live
        # overlay, and the static cage is rebuilt once when the session ends.
        if paint_only_update(update, paint_only_pointers):
            continue

        if bool(getattr(update, "is_updated_geometry", False)):
            return True
        if bool(getattr(update, "is_updated_transform", False)):
            return True
        if bool(getattr(original_id, "is_editmode", False)):
            return True
        if bool(getattr(getattr(original_id, "data", None), "is_editmode", False)):
            return True

    return False


#: Regenerating the skew direction field costs seconds on a real group (measured
#: 4.6-5.8s on 7.5k polys), so a bump is not something to spend per depsgraph tick.
SKEW_PAINT_BUMP_INTERVAL_SECONDS = 1.5
_LAST_SKEW_PAINT_BUMP = 0.0


def skew_paint_session_active(scene, skew_image) -> bool:
    """True only while the artist is actually painting on THIS group's skew canvas.

    The old trigger was ``skew_image.is_dirty``, which is sticky: an image stays dirty
    from its first stroke until it is saved or packed. So a single skew stroke armed a
    full skew-field regeneration on EVERY subsequent depsgraph update, for the rest of
    the session -- seconds of viewport stall per unrelated scene change, forever.
    """
    if skew_image is None or scene is None:
        return False
    view_layer = getattr(bpy.context, "view_layer", None)
    active_object = getattr(getattr(view_layer, "objects", None), "active", None)
    if active_object is None or getattr(active_object, "mode", "") != "TEXTURE_PAINT":
        return False
    image_paint = getattr(getattr(scene, "tool_settings", None), "image_paint", None)
    return getattr(image_paint, "canvas", None) is skew_image


def skew_paint_bump_due(*, now: float | None = None) -> bool:
    """Rate-limit skew-field regeneration to something a viewport can absorb."""
    global _LAST_SKEW_PAINT_BUMP
    moment = time.monotonic() if now is None else float(now)
    if moment - _LAST_SKEW_PAINT_BUMP < SKEW_PAINT_BUMP_INTERVAL_SECONDS:
        return False
    _LAST_SKEW_PAINT_BUMP = moment
    return True


def reset_skew_paint_bump_throttle() -> None:
    """Let the next bump through immediately (used when a paint session ends)."""
    global _LAST_SKEW_PAINT_BUMP
    _LAST_SKEW_PAINT_BUMP = 0.0


def handle_depsgraph_update_post(_scene, _depsgraph, *, skew_paint_version: int, deps: OverlayEventBridgeDeps) -> int:
    if _revisions_frozen():
        # high_poly_park's lossless mesh swap: nothing the overlays draw changed.
        return skew_paint_version
    try:
        from . import paint_brush

        paint_only_pointers = paint_brush.take_paint_only_update_pointers()
    except Exception:
        paint_only_pointers = set()
    # Stamp first: the overlay key reads these revisions instead of re-hashing every
    # tracked object's matrix and bound_box on every viewport redraw. A stroke's layer
    # write is not stamped: it would rebuild the whole static overlay (and re-subdivide
    # the painted cages) on every stroke release while the brush already draws them
    # live; paint_brush.end_session stamps the painted meshes once instead.
    _bump_depsgraph_id_revisions(
        _depsgraph, skip=lambda update: paint_only_update(update, paint_only_pointers)
    )
    if depsgraph_requires_static_invalidation(
        _scene, _depsgraph, deps=deps.tracking, paint_only_pointers=paint_only_pointers
    ):
        deps.reset_auto_cage_preview_runtime()
        deps.reset_distance_average_normals_preview_runtime()
        # A tracked mesh's geometry/transform actually changed here, so the cage-coverage
        # batches are genuinely stale — clear them (unlike plain selection/mode changes).
        deps.invalidate_overlay_cache(clear_static=True, clear_cage_check=True)
        settings = getattr(_scene, "fyr_baker_settings", None) if _scene is not None else None
        if deps.debug_overlay_enabled(settings):
            deps.invalidate_debug_overlay_export_cache(scene=_scene, reason="tracked_scene_update")
            deps.request_debug_overlay_refresh(
                bpy.context,
                delay_seconds=deps.debug_refresh_delay_seconds,
                reason="tracked_scene_update",
            )
    if _scene is not None:
        try:
            _settings, _proj, _grp = deps.tracking.resolve_project_group(_scene)
            if _grp is not None:
                _offset_img = getattr(_grp, "paint_offset_image", None)
                _skew_img = getattr(_grp, "paint_skew_image", None)
                if _offset_img is not None and getattr(_offset_img, "is_dirty", False):
                    deps.mark_interaction()
                    deps.tag_redraw_all_view3d(scene=_scene, sync_preview=False)
                if _skew_img is not None and skew_paint_session_active(_scene, _skew_img):
                    if skew_paint_bump_due():
                        skew_paint_version += 1
                        deps.invalidate_overlay_cache(clear_static=False)
                    deps.tag_redraw_all_view3d(scene=_scene, sync_preview=False)
            
            # Auto-select group on selection if enabled
            # Read the setting dynamically instead of from cached deps
            settings = getattr(_scene, "fyr_baker_settings", None) if _scene is not None else None
            overlay_state = properties.overlay_settings_state(settings) if settings is not None else None
            auto_select_enabled = bool(getattr(overlay_state, "auto_select_group_on_selection", False)) if overlay_state is not None else False
            
            if auto_select_enabled and _proj is not None:
                active_object = getattr(bpy.context, "active_object", None)
                if active_object is not None:
                    result = project_structure.find_group_for_object(_proj, active_object)
                    if result is not None:
                        group_index, _group = result
                        current_index = getattr(_proj, "active_group_index", 0)
                        if group_index != current_index:
                            # Write the ID property directly: that bypasses the RNA
                            # update callback (no static-cache invalidation on every
                            # selection change). The old code read prop.update, which
                            # bpy.types.Property does not expose, so it raised before
                            # the assignment and auto-select never switched the group.
                            try:
                                _proj["active_group_index"] = int(group_index)
                            except Exception:
                                _proj.active_group_index = group_index
        except Exception:
            pass
    return skew_paint_version


def handle_load_post(_dummy, *, deps: OverlayEventBridgeDeps) -> float:
    # A new file brings a new session_uid namespace; carrying stamps across would let a
    # reused uid read as "already current" against a key from the previous file.
    _reset_id_revisions()
    deps.reset_preview_visibility_sync_runtime()
    deps.clear_preview_proxy_states()
    deps.reset_high_reference_runtime()
    deps.reset_auto_cage_preview_runtime()
    deps.reset_distance_average_normals_preview_runtime()
    deps.invalidate_overlay_cache()
    post_load_overlay_grace_until = deps.now_fn() + max(0.35, deps.debug_refresh_delay_seconds * 2.0)
    scene = getattr(bpy.context, "scene", None)
    deps.invalidate_debug_overlay_cache(context=bpy.context, scene=scene, reason="load_post")
    deps.sync_preview_visibility(scene)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if deps.debug_overlay_enabled(settings):
        deps.request_debug_overlay_refresh(
            bpy.context,
            delay_seconds=deps.debug_refresh_delay_seconds,
            reason="load_post",
        )
    return post_load_overlay_grace_until


def handle_save_post(_dummy, *, sync_preview_visibility_fn: Callable[[object], None], tag_redraw_all_view3d_fn: Callable[..., None]) -> None:
    scene = getattr(bpy.context, "scene", None)
    sync_preview_visibility_fn(scene)
    tag_redraw_all_view3d_fn(window=getattr(bpy.context, "window", None))


def register_overlay_runtime(state: OverlayRegistrationState, *, deps: OverlayRegistrationDeps) -> OverlayRegistrationState:
    if state.draw_handler is None:
        state.draw_handler = bpy.types.SpaceView3D.draw_handler_add(deps.draw_group_overlay_fn, (), "WINDOW", "POST_VIEW")
    if state.draw_pixel_handler is None:
        state.draw_pixel_handler = bpy.types.SpaceView3D.draw_handler_add(
            deps.draw_screen_heatmap_overlay_post_pixel_fn,
            (),
            "WINDOW",
            "POST_PIXEL",
        )
    if deps.depsgraph_update_post_fn not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(deps.depsgraph_update_post_fn)
    if deps.load_post_fn not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(deps.load_post_fn)
    save_pre = getattr(bpy.app.handlers, "save_pre", None)
    if save_pre is not None and deps.save_pre_fn not in save_pre:
        save_pre.append(deps.save_pre_fn)
    save_post = getattr(bpy.app.handlers, "save_post", None)
    if save_post is not None and deps.save_post_fn not in save_post:
        save_post.append(deps.save_post_fn)

    state.screen_heatmap_image = None
    state.screen_heatmap_texture = None
    state.screen_heatmap_texture_image_pointer = 0
    state.screen_heatmap_result = None
    state.screen_heatmap_result_key = None
    state.last_view_refresh_key = None
    state.last_view_refresh_signature = ""
    state.last_view_refresh_at = 0.0
    state.post_load_overlay_grace_until = deps.event_bridge.now_fn() + max(
        0.35,
        deps.event_bridge.debug_refresh_delay_seconds * 2.0,
    )

    deps.event_bridge.reset_preview_visibility_sync_runtime()
    deps.event_bridge.clear_preview_proxy_states()
    deps.event_bridge.reset_high_reference_runtime()
    deps.event_bridge.reset_auto_cage_preview_runtime()
    deps.event_bridge.reset_distance_average_normals_preview_runtime()
    deps.event_bridge.invalidate_overlay_cache()
    scene = getattr(bpy.context, "scene", None)
    deps.event_bridge.invalidate_debug_overlay_cache(context=bpy.context, scene=scene, reason="register")
    # The draw handlers are already installed at this point. A scene-dependent failure
    # here (cage_visualization raises RuntimeError in some states) must not abort
    # registration and leave those handlers behind with nothing recorded to remove
    # them; the overlay simply syncs on the next preview change instead.
    try:
        deps.event_bridge.sync_preview_visibility(scene)
    except Exception:
        pass
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if deps.event_bridge.debug_overlay_enabled(settings):
        deps.event_bridge.request_debug_overlay_refresh(
            bpy.context,
            delay_seconds=deps.event_bridge.debug_refresh_delay_seconds,
            reason="register",
        )
    return state


def unregister_overlay_runtime(state: OverlayRegistrationState, *, deps: OverlayRegistrationDeps) -> OverlayRegistrationState:
    if state.draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(state.draw_handler, "WINDOW")
        state.draw_handler = None
    if state.draw_pixel_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(state.draw_pixel_handler, "WINDOW")
        state.draw_pixel_handler = None
    if deps.depsgraph_update_post_fn in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(deps.depsgraph_update_post_fn)
    if deps.load_post_fn in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(deps.load_post_fn)
    save_pre = getattr(bpy.app.handlers, "save_pre", None)
    if save_pre is not None and deps.save_pre_fn in save_pre:
        save_pre.remove(deps.save_pre_fn)
    save_post = getattr(bpy.app.handlers, "save_post", None)
    if save_post is not None and deps.save_post_fn in save_post:
        save_post.remove(deps.save_post_fn)

    _reset_id_revisions()
    deps.event_bridge.cleanup_preview_runtime()
    deps.event_bridge.reset_preview_visibility_sync_runtime()
    deps.event_bridge.reset_high_reference_runtime()
    deps.event_bridge.reset_auto_cage_preview_runtime()
    deps.event_bridge.reset_distance_average_normals_preview_runtime()
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and state.interaction_redraw_timer_registered:
        try:
            timers.unregister(deps.interaction_redraw_timer_fn)
        except Exception:
            pass
    state.interaction_redraw_due_at = 0.0
    state.interaction_redraw_timer_registered = False
    state.screen_heatmap_image = None
    state.screen_heatmap_texture = None
    state.screen_heatmap_texture_image_pointer = 0
    state.screen_heatmap_result = None
    state.screen_heatmap_result_key = None
    state.last_view_refresh_key = None
    state.last_view_refresh_signature = ""
    state.last_view_refresh_at = 0.0
    deps.event_bridge.invalidate_overlay_cache()
    deps.event_bridge.invalidate_debug_overlay_cache(
        context=bpy.context,
        scene=getattr(bpy.context, "scene", None),
        reason="unregister",
    )
    return state
