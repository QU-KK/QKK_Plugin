from __future__ import annotations

from .overlay_cache import OverlayCacheBuilderDeps
from .overlay_events import (
    OverlayEventBridgeDeps,
    OverlayRegistrationDeps,
    OverlayTrackingDeps,
)
from .overlay_renderer import OverlayRendererDeps


def build_overlay_cache_builder_deps(
    *,
    overlay_theme_for_settings_fn,
    effective_static_debug_flags_fn,
    line_render_enabled_fn,
    build_batch_fn,
    build_offset_batch_fn,
    build_lit_offset_batch_fn,
    build_paint_offset_batch_fn,
    estimate_low_depth_epsilon_fn,
    iter_valid_meshes_fn,
    make_overlay_pass_fn,
    make_line_overlay_pass_fn,
    make_offset_overlay_pass_fn,
    make_lit_offset_overlay_pass_fn,
    make_paint_offset_overlay_pass_fn,
    make_offset_line_overlay_pass_fn,
    heatmap_overlay_passes_from_debug_result_fn,
    use_screen_heatmap_overlay_fn,
    backend_debug_result_is_stale_fn,
    skew_overlay_pass_from_batch_fn,
    enqueue_auto_cage_preview_build_fn,
    enqueue_distance_average_normals_preview_build_fn,
) -> OverlayCacheBuilderDeps:
    return OverlayCacheBuilderDeps(
        overlay_theme_for_settings=overlay_theme_for_settings_fn,
        effective_static_debug_flags=effective_static_debug_flags_fn,
        line_render_enabled=line_render_enabled_fn,
        build_batch=build_batch_fn,
        build_offset_batch=build_offset_batch_fn,
        build_lit_offset_batch=build_lit_offset_batch_fn,
        build_paint_offset_batch=build_paint_offset_batch_fn,
        estimate_low_depth_epsilon=estimate_low_depth_epsilon_fn,
        iter_valid_meshes=iter_valid_meshes_fn,
        make_overlay_pass=make_overlay_pass_fn,
        make_line_overlay_pass=make_line_overlay_pass_fn,
        make_offset_overlay_pass=make_offset_overlay_pass_fn,
        make_lit_offset_overlay_pass=make_lit_offset_overlay_pass_fn,
        make_paint_offset_overlay_pass=make_paint_offset_overlay_pass_fn,
        make_offset_line_overlay_pass=make_offset_line_overlay_pass_fn,
        heatmap_overlay_passes_from_debug_result=heatmap_overlay_passes_from_debug_result_fn,
        use_screen_heatmap_overlay=use_screen_heatmap_overlay_fn,
        backend_debug_result_is_stale=backend_debug_result_is_stale_fn,
        skew_overlay_pass_from_batch=skew_overlay_pass_from_batch_fn,
        enqueue_auto_cage_preview_build=enqueue_auto_cage_preview_build_fn,
        enqueue_distance_average_normals_preview_build=enqueue_distance_average_normals_preview_build_fn,
    )


def build_renderer_deps(
    *,
    preview_suppressed_for_context_fn,
    resolve_project_group_fn,
    get_overlay_cache_fn,
    overlay_theme_for_settings_fn,
    get_shader_fn,
    render_low_depth_mask_fn,
    render_cage_depth_mask_fn,
    line_render_enabled_fn,
    get_heatmap_mask_shader_fn,
    log_mask_error_fn,
    heatmap_low_depth_epsilon_min: float,
    ensure_cage_check_debug_result_fn=None,
    draw_cage_check_overlay_fn=None,
) -> OverlayRendererDeps:
    return OverlayRendererDeps(
        preview_suppressed_for_context=preview_suppressed_for_context_fn,
        resolve_project_group=resolve_project_group_fn,
        get_overlay_cache=get_overlay_cache_fn,
        overlay_theme_for_settings=overlay_theme_for_settings_fn,
        get_shader=get_shader_fn,
        render_low_depth_mask=render_low_depth_mask_fn,
        render_cage_depth_mask=render_cage_depth_mask_fn or (lambda *_args, **_kwargs: None),
        line_render_enabled=line_render_enabled_fn,
        get_heatmap_mask_shader=get_heatmap_mask_shader_fn,
        log_mask_error=log_mask_error_fn,
        heatmap_low_depth_epsilon_min=heatmap_low_depth_epsilon_min,
        ensure_cage_check_debug_result=ensure_cage_check_debug_result_fn or (lambda *_args, **_kwargs: False),
        draw_cage_check_overlay=draw_cage_check_overlay_fn or (lambda *_args, **_kwargs: False),
    )


def build_overlay_tracking_deps(
    *,
    resolve_project_group_fn,
    iter_valid_meshes_fn,
    is_valid_object_fn,
    is_valid_mesh_fn,
    preview_collection_name: str,
) -> OverlayTrackingDeps:
    return OverlayTrackingDeps(
        resolve_project_group=resolve_project_group_fn,
        iter_valid_meshes=iter_valid_meshes_fn,
        is_valid_object=is_valid_object_fn,
        is_valid_mesh=is_valid_mesh_fn,
        preview_collection_name=preview_collection_name,
    )


def build_overlay_event_bridge_deps(
    *,
    tracking: OverlayTrackingDeps,
    debug_overlay_enabled_fn,
    invalidate_debug_overlay_export_cache_fn,
    request_debug_overlay_refresh_fn,
    mark_interaction_fn,
    tag_redraw_all_view3d_fn,
    invalidate_overlay_cache_fn,
    reset_auto_cage_preview_runtime_fn,
    reset_distance_average_normals_preview_runtime_fn,
    reset_preview_visibility_sync_runtime_fn,
    clear_preview_proxy_states_fn,
    reset_high_reference_runtime_fn,
    sync_preview_visibility_fn,
    invalidate_debug_overlay_cache_fn,
    cleanup_preview_runtime_fn,
    debug_refresh_delay_seconds: float,
    now_fn,
) -> OverlayEventBridgeDeps:
    return OverlayEventBridgeDeps(
        tracking=tracking,
        debug_overlay_enabled=debug_overlay_enabled_fn,
        invalidate_debug_overlay_export_cache=invalidate_debug_overlay_export_cache_fn,
        request_debug_overlay_refresh=request_debug_overlay_refresh_fn,
        mark_interaction=mark_interaction_fn,
        tag_redraw_all_view3d=tag_redraw_all_view3d_fn,
        invalidate_overlay_cache=invalidate_overlay_cache_fn,
        reset_auto_cage_preview_runtime=reset_auto_cage_preview_runtime_fn,
        reset_distance_average_normals_preview_runtime=reset_distance_average_normals_preview_runtime_fn,
        reset_preview_visibility_sync_runtime=reset_preview_visibility_sync_runtime_fn,
        clear_preview_proxy_states=clear_preview_proxy_states_fn,
        reset_high_reference_runtime=reset_high_reference_runtime_fn,
        sync_preview_visibility=sync_preview_visibility_fn,
        invalidate_debug_overlay_cache=invalidate_debug_overlay_cache_fn,
        cleanup_preview_runtime=cleanup_preview_runtime_fn,
        debug_refresh_delay_seconds=debug_refresh_delay_seconds,
        now_fn=now_fn,
    )


def build_overlay_registration_deps(
    *,
    draw_group_overlay_fn,
    draw_screen_heatmap_overlay_post_pixel_fn,
    depsgraph_update_post_fn,
    load_post_fn,
    save_pre_fn,
    save_post_fn,
    event_bridge: OverlayEventBridgeDeps,
    interaction_redraw_timer_fn,
) -> OverlayRegistrationDeps:
    return OverlayRegistrationDeps(
        draw_group_overlay_fn=draw_group_overlay_fn,
        draw_screen_heatmap_overlay_post_pixel_fn=draw_screen_heatmap_overlay_post_pixel_fn,
        depsgraph_update_post_fn=depsgraph_update_post_fn,
        load_post_fn=load_post_fn,
        save_pre_fn=save_pre_fn,
        save_post_fn=save_post_fn,
        event_bridge=event_bridge,
        interaction_redraw_timer_fn=interaction_redraw_timer_fn,
    )
