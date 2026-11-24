from __future__ import annotations

import inspect
import math
import queue
import sys
import traceback
import time
import types

import bpy
import gpu

try:
    from gpu_extras.presets import draw_texture_2d as _draw_texture_2d
except Exception:  # pragma: no cover - unavailable in unit-test stubs
    _draw_texture_2d = None

from . import cage, cage_session, constants, export, overlay_theme, preferences, properties, runtime
from .handler_thread_guard import on_main_thread


from .overlay_cache import (
    DistanceAverageNormalsPreviewSlotBuildInput,
    _group_paint_projection_settings_state,
    OverlayCacheState,
    OverlayCacheEntry,
    OverlayPass,
    StaticOverlayCacheEntry,
    build_overlay_cache as _build_overlay_cache_impl,
    build_static_overlay_cache as _build_static_overlay_cache_impl,
    get_overlay_cache as _get_overlay_cache_impl,
    invalidate_overlay_cache_state as _invalidate_overlay_cache_state,
)
from .overlay_preview_builds import (
    AutoCagePreviewBuildRequest,
    AutoCagePreviewBuildResult,
    AutoCagePreviewCacheEntry,
    DistanceAverageNormalsPreviewBuildRequest,
    DistanceAverageNormalsPreviewBuildResult,
    DistanceAverageNormalsPreviewCacheEntry,
    DistanceAverageNormalsPreviewSlotBuildResult,
    OverlayPreviewBuildDeps,
    OverlayPreviewBuildRuntimeState,
    auto_cage_preview_build_timer_tick as _auto_cage_preview_build_timer_tick_impl,
    distance_average_normals_preview_build_timer_tick as _distance_average_normals_preview_build_timer_tick_impl,
    enqueue_auto_cage_preview_build as _enqueue_auto_cage_preview_build_impl,
    enqueue_distance_average_normals_preview_build as _enqueue_distance_average_normals_preview_build_impl,
    ensure_auto_cage_preview_build_timer_registered as _ensure_auto_cage_preview_build_timer_registered_impl,
    ensure_distance_average_normals_preview_build_timer_registered as _ensure_distance_average_normals_preview_build_timer_registered_impl,
    reset_auto_cage_preview_runtime as _reset_auto_cage_preview_runtime_impl,
    reset_distance_average_normals_preview_runtime as _reset_distance_average_normals_preview_runtime_impl,
)
from .overlay_preview_visibility import (
    PreviewCleanupDeps,
    PreviewVisibilityDeps,
    cleanup_preview_runtime_for_save as _cleanup_preview_runtime_for_save_impl,
    reset_preview_visibility_sync_runtime as _reset_preview_visibility_sync_runtime_impl,
    sync_preview_visibility as _sync_preview_visibility_impl,
    sync_preview_visibility_now as _sync_preview_visibility_now_impl,
)
from .overlay_runtime_state import (
    LEGACY_RUNTIME_FIELD_MAP,
    OverlayLegacyRuntimeState,
    interaction_active as _interaction_active_impl,
    legacy_runtime_state_get as _legacy_runtime_state_get,
    legacy_runtime_state_set as _legacy_runtime_state_set,
    mark_interaction as _mark_interaction_impl,
    overlay_registration_state_from_legacy_state as _overlay_registration_state_from_legacy_state_impl,
    post_load_overlay_grace_active as _post_load_overlay_grace_active_impl,
    post_load_overlay_grace_delay as _post_load_overlay_grace_delay_impl,
    preview_build_runtime_state_from_legacy_state as _preview_build_runtime_state_from_legacy_state_impl,
    preview_visibility_sync_state_from_legacy_state as _preview_visibility_sync_state_from_legacy_state_impl,
    sync_overlay_registration_legacy_state as _sync_overlay_registration_legacy_state_impl,
    sync_preview_build_runtime_legacy_state as _sync_preview_build_runtime_legacy_state_impl,
    sync_preview_visibility_sync_legacy_state as _sync_preview_visibility_sync_legacy_state_impl,
)
from .overlay_pass_builders import (
    build_lit_batch_from_positions as _build_lit_batch_from_positions_impl,
    build_skew_colored_line_batch as _build_skew_colored_line_batch_impl,
    line_render_enabled as _line_render_enabled_impl,
    make_line_overlay_pass as _make_line_overlay_pass_impl,
    make_lit_heatmap_overlay_pass as _make_lit_heatmap_overlay_pass_impl,
    make_lit_offset_overlay_pass as _make_lit_offset_overlay_pass_impl,
    make_offset_line_overlay_pass as _make_offset_line_overlay_pass_impl,
    make_offset_overlay_pass as _make_offset_overlay_pass_impl,
    make_overlay_pass as _make_overlay_pass_impl,
    make_paint_offset_overlay_pass as _make_paint_offset_overlay_pass_impl,
    skew_overlay_pass_from_batch as _skew_overlay_pass_from_batch_impl,
    triangle_face_normal_from_positions as _triangle_face_normal_from_positions_impl,
)
from .overlay_batch_builders import (
    build_batch as _build_batch_impl,
    build_lit_offset_batch as _build_lit_offset_batch_impl,
    build_offset_batch as _build_offset_batch_impl,
    build_paint_offset_batch as _build_paint_offset_batch_impl,
)
from .overlay_heatmap_geometry import (
    estimate_low_depth_epsilon as _estimate_low_depth_epsilon_impl,
    visible_viewport_triangles as _visible_viewport_triangles_impl,
)
from .overlay_preview_bridge import (
    apply_object_override_material as _apply_object_override_material_impl,
    build_preview_visibility_deps as _build_preview_visibility_deps_impl,
    create_cage_visualization_controller as _create_cage_visualization_controller_impl,
    high_reference_uses_native_preview as _high_reference_uses_native_preview_impl,
)
from .overlay_wiring import (
    build_overlay_cache_builder_deps as _build_overlay_cache_builder_deps_impl,
    build_overlay_event_bridge_deps as _build_overlay_event_bridge_deps_impl,
    build_overlay_registration_deps as _build_overlay_registration_deps_impl,
    build_overlay_tracking_deps as _build_overlay_tracking_deps_impl,
    build_renderer_deps as _build_renderer_deps_impl,
)
from .overlay_screen_heatmap import (
    screen_heatmap_draw_supported as _screen_heatmap_draw_supported_impl,
    use_screen_heatmap_overlay as _use_screen_heatmap_overlay_impl,
)
from .overlay_events import (
    reset_skew_paint_bump_throttle as _reset_skew_paint_bump_throttle,
    OverlayEventBridgeDeps,
    OverlayRegistrationDeps,
    OverlayRegistrationState,
    OverlayTrackingDeps,
    PreviewVisibilitySyncState,
    depsgraph_requires_static_invalidation as _depsgraph_requires_static_invalidation_impl,
    handle_depsgraph_update_post as _handle_depsgraph_update_post_impl,
    handle_load_post as _handle_load_post_impl,
    handle_save_post as _handle_save_post_impl,
    interaction_redraw_timer_tick as _interaction_redraw_timer_tick_impl,
    preview_visibility_sync_timer_tick as _preview_visibility_sync_timer_tick_impl,
    register_overlay_runtime as _register_overlay_runtime_impl,
    schedule_interaction_redraw as _schedule_interaction_redraw_impl,
    schedule_preview_visibility_sync as _schedule_preview_visibility_sync_impl,
    tag_redraw_all_view3d as _tag_redraw_all_view3d_impl,
    tracked_overlay_id_pointers as _tracked_overlay_id_pointers_impl,
    unregister_overlay_runtime as _unregister_overlay_runtime_impl,
)
from .overlay_gpu import (
    OverlayGpuState,
    release_mask_resources as _release_mask_resources_impl,
    build_offset_gpu_batch as _build_offset_gpu_batch_impl,
    ensure_low_depth_mask_resources as _ensure_low_depth_mask_resources_impl,
    ensure_shell_cage_back_depth_mask_resources as _ensure_shell_cage_back_depth_mask_resources_impl,
    ensure_shell_cage_depth_mask_resources as _ensure_shell_cage_depth_mask_resources_impl,
    ensure_shell_low_depth_mask_resources as _ensure_shell_low_depth_mask_resources_impl,
    get_heatmap_mask_shader as _get_heatmap_mask_shader_impl,
    get_lit_batch_format as _get_lit_batch_format_impl,
    get_lit_offset_shader as _get_lit_offset_shader_impl,
    get_lit_shader as _get_lit_shader_impl,
    get_skew_shader as _get_skew_shader_impl,
    get_skew_batch_format as _get_skew_batch_format_impl,
    get_low_depth_mask_shader as _get_low_depth_mask_shader_impl,
    get_offset_batch_format as _get_offset_batch_format_impl,
    get_offset_shader as _get_offset_shader_impl,
    get_paint_offset_batch_format as _get_paint_offset_batch_format_impl,
    get_paint_offset_shader as _get_paint_offset_shader_impl,
    get_shader as _get_shader_impl,
    get_shell_cage_depth_mask_shader as _get_shell_cage_depth_mask_shader_impl,
    get_shell_cage_paint_depth_mask_shader as _get_shell_cage_paint_depth_mask_shader_impl,
    get_shell_low_depth_mask_shader as _get_shell_low_depth_mask_shader_impl,
    log_mask_error_once as _log_mask_error_once_impl,
    low_depth_mask_dimensions as _low_depth_mask_dimensions_impl,
    low_depth_mask_supported as _low_depth_mask_supported_impl,
    render_low_depth_mask as _render_low_depth_mask_impl,
    render_cage_pass_depth_mask as _render_cage_pass_depth_mask_impl,
    render_shell_depth_mask as _render_shell_depth_mask_impl,
)
from .overlay_debug_heatmap import (
    heatmap_overlay_passes_from_debug_result as _heatmap_overlay_passes_from_debug_result_impl,
    matching_error_overlay_passes_from_debug_result as _matching_error_overlay_passes_from_debug_result_impl,
)
from .overlay_cage_check_gpu import (
    clear_cage_check_gpu_cache as _clear_cage_check_gpu_cache_impl,
    draw_cage_check_overlay as _draw_cage_check_overlay_impl,
)
from .overlay_high_reference import (
    HighReferenceBuildRequest,
    HighReferenceBuildResult,
    HighReferenceCacheEntry,
    OverlayHighReferenceRuntimeState,
    high_reference_build_timer_tick as _high_reference_build_timer_tick_impl,
    high_reference_overlay_passes as _high_reference_overlay_passes_impl,
    reset_high_reference_runtime as _reset_high_reference_runtime_impl,
)
from .overlay_keys import (
    all_low_meshes_visible_in_viewport as _all_low_meshes_visible_in_viewport_impl,
    display_overlay_key as _display_overlay_key_impl,
    effective_static_debug_flags as _effective_static_debug_flags_impl,
    id_update_signature as _id_update_signature_impl,
    iter_valid_meshes as _iter_valid_meshes_impl,
    object_bounds_signature as _object_bounds_signature_impl,
    object_cache_signature as _object_cache_signature_impl,
    object_signature as _object_signature_impl,
    object_visible_in_viewport as _object_visible_in_viewport_impl,
    overlay_settings_state as _overlay_settings_state,
    static_overlay_key as _static_overlay_key_impl,
)
from .overlay_renderer import (
    OverlayRendererDeps,
    draw_batch as _draw_batch_impl,
    draw_group_overlay as _draw_group_overlay_impl,
)

_OVERLAY_CACHE_STATE = OverlayCacheState()
_HIGH_REFERENCE_RUNTIME_STATE = OverlayHighReferenceRuntimeState()
_HIGH_REFERENCE_OBJECT_CACHE: dict[int, "HighReferenceCacheEntry"] = _HIGH_REFERENCE_RUNTIME_STATE.object_cache
_HIGH_REFERENCE_BUILD_QUEUE: dict[int, "HighReferenceBuildRequest"] = _HIGH_REFERENCE_RUNTIME_STATE.build_queue
_HIGH_REFERENCE_BUILD_ORDER: list[int] = _HIGH_REFERENCE_RUNTIME_STATE.build_order
_HIGH_REFERENCE_BUILD_RESULT_QUEUE: "queue.Queue[HighReferenceBuildResult]" = _HIGH_REFERENCE_RUNTIME_STATE.build_result_queue
_OVERLAY_GPU_STATE = OverlayGpuState()
_LEGACY_OVERLAY_RUNTIME_STATE = OverlayLegacyRuntimeState()
_SKEW_PAINT_VERSION = 0
_PAINT_SESSION_VERSION = 0
_DEBUG_RESULT_PASS_CACHE: dict[int, tuple[object, list["OverlayPass"]]] = {}
_LAST_DRAW_ERROR = ""
_PREVIEW_COLLECTION_NAME = "_FYR_BAKER_PREVIEW"
_PREVIEW_MATERIAL_NAME = "_FYR_BAKER_PREVIEW_MAT"
_PREVIEW_MODIFIER_NAME = "_FYR_BAKER_PREVIEW_SOLIDIFY"
_HEATMAP_LOW_DEPTH_EPSILON_MIN = 1.0e-5
_HEATMAP_LOW_DEPTH_EPSILON_MAX = 2.0e-3
_HEATMAP_LOW_DEPTH_EPSILON_BOUNDS_FACTOR = 5.0e-5
_HEATMAP_LOW_DEPTH_EPSILON_EDGE_FACTOR = 2.0e-4
_LOW_DEPTH_MASK_MAX_SUPERSAMPLE_SCALE = 3
_LOW_DEPTH_MASK_SUPERSAMPLE_MAX_TEXELS = 16_777_216
_LOW_DEPTH_MASK_SUPERSAMPLE_MAX_DIMENSION = 8192
_HEATMAP_LIGHT_DIRECTION_RAW = (0.31, 0.42, 0.85)
_HEATMAP_LIGHT_DIRECTION_LENGTH = math.sqrt(
    _HEATMAP_LIGHT_DIRECTION_RAW[0] * _HEATMAP_LIGHT_DIRECTION_RAW[0]
    + _HEATMAP_LIGHT_DIRECTION_RAW[1] * _HEATMAP_LIGHT_DIRECTION_RAW[1]
    + _HEATMAP_LIGHT_DIRECTION_RAW[2] * _HEATMAP_LIGHT_DIRECTION_RAW[2]
)
if _HEATMAP_LIGHT_DIRECTION_LENGTH <= 1.0e-8:
    _HEATMAP_LIGHT_DIRECTION = (0.0, 0.0, 1.0)
else:
    _HEATMAP_LIGHT_DIRECTION = (
        _HEATMAP_LIGHT_DIRECTION_RAW[0] / _HEATMAP_LIGHT_DIRECTION_LENGTH,
        _HEATMAP_LIGHT_DIRECTION_RAW[1] / _HEATMAP_LIGHT_DIRECTION_LENGTH,
        _HEATMAP_LIGHT_DIRECTION_RAW[2] / _HEATMAP_LIGHT_DIRECTION_LENGTH,
    )

def _preview_build_runtime_state_from_globals() -> OverlayPreviewBuildRuntimeState:
    return _preview_build_runtime_state_from_legacy_state_impl(_LEGACY_OVERLAY_RUNTIME_STATE)


def _sync_preview_build_runtime_state(state: OverlayPreviewBuildRuntimeState) -> None:
    _sync_preview_build_runtime_legacy_state_impl(_LEGACY_OVERLAY_RUNTIME_STATE, state)


def _preview_visibility_sync_state_from_globals() -> PreviewVisibilitySyncState:
    return _preview_visibility_sync_state_from_legacy_state_impl(_LEGACY_OVERLAY_RUNTIME_STATE)


def _sync_preview_visibility_sync_state(state: PreviewVisibilitySyncState) -> None:
    _sync_preview_visibility_sync_legacy_state_impl(_LEGACY_OVERLAY_RUNTIME_STATE, state)


def _overlay_registration_state_from_globals() -> OverlayRegistrationState:
    return _overlay_registration_state_from_legacy_state_impl(_LEGACY_OVERLAY_RUNTIME_STATE)


def _sync_overlay_registration_state(state: OverlayRegistrationState) -> None:
    _sync_overlay_registration_legacy_state_impl(_LEGACY_OVERLAY_RUNTIME_STATE, state)


def _log_mask_error_once(error_text: str) -> None:
    _log_mask_error_once_impl(_OVERLAY_GPU_STATE, error_text)


def overlay_gpu_diagnostics() -> dict[str, object]:
    shell_low = _OVERLAY_GPU_STATE.shell_low_depth_mask_resources
    shell_cage = _OVERLAY_GPU_STATE.shell_cage_depth_mask_resources
    shell_cage_back = _OVERLAY_GPU_STATE.shell_cage_back_depth_mask_resources
    return {
        "low_depth_mask_supported": _low_depth_mask_supported(),
        "last_mask_error": str(getattr(_OVERLAY_GPU_STATE, "last_mask_error", "") or ""),
        "shell_low_resource": shell_low is not None,
        "shell_low_size": (int(shell_low.width), int(shell_low.height)) if shell_low is not None else (),
        "shell_low_color_format": str(getattr(shell_low, "color_format", "") or "") if shell_low is not None else "",
        "shell_low_depth_format": str(getattr(shell_low, "depth_format", "") or "") if shell_low is not None else "",
        "shell_cage_resource": shell_cage is not None,
        "shell_cage_size": (int(shell_cage.width), int(shell_cage.height)) if shell_cage is not None else (),
        "shell_cage_color_format": str(getattr(shell_cage, "color_format", "") or "") if shell_cage is not None else "",
        "shell_cage_depth_format": str(getattr(shell_cage, "depth_format", "") or "") if shell_cage is not None else "",
        "shell_cage_back_resource": shell_cage_back is not None,
        "shell_cage_back_size": (int(shell_cage_back.width), int(shell_cage_back.height)) if shell_cage_back is not None else (),
        "shell_cage_back_color_format": str(getattr(shell_cage_back, "color_format", "") or "") if shell_cage_back is not None else "",
        "shell_cage_back_depth_format": str(getattr(shell_cage_back, "depth_format", "") or "") if shell_cage_back is not None else "",
    }


def _overlay_theme_for_settings(settings):
    overlay_state = _overlay_settings_state(settings)
    return overlay_theme.build_overlay_theme(
        cage_opacity=float(getattr(overlay_state, "cage_opacity", 1.0)),
        cage_surface_opacity=float(getattr(overlay_state, "cage_surface_opacity", 0.42)),
        cage_wireframe_opacity=float(getattr(overlay_state, "cage_wireframe_opacity", 0.38)),
        low_reference_color=tuple(getattr(overlay_state, "low_reference_color", (0.72, 0.80, 0.88))),
        cage_surface_color=tuple(getattr(overlay_state, "cage_surface_color", (0.18, 0.88, 0.46))),
        cage_wireframe_color=tuple(getattr(overlay_state, "cage_wireframe_color", (0.32, 1.0, 0.62))),
        heatmap_inside_color=tuple(getattr(overlay_state, "heatmap_inside_color", (0.12, 0.46, 1.0))),
        heatmap_outside_color=tuple(getattr(overlay_state, "heatmap_outside_color", (1.0, 0.08, 0.08))),
    )


def _get_shader():
    return _get_shader_impl(_OVERLAY_GPU_STATE)


def _get_offset_shader():
    return _get_offset_shader_impl(_OVERLAY_GPU_STATE)


def _get_lit_offset_shader():
    return _get_lit_offset_shader_impl(_OVERLAY_GPU_STATE)


def _get_paint_offset_shader():
    return _get_paint_offset_shader_impl(_OVERLAY_GPU_STATE)


def _get_lit_shader():
    return _get_lit_shader_impl(_OVERLAY_GPU_STATE)


def _get_heatmap_mask_shader():
    return _get_heatmap_mask_shader_impl(_OVERLAY_GPU_STATE)


def _get_lit_batch_format():
    return _get_lit_batch_format_impl(_OVERLAY_GPU_STATE)


def _get_skew_shader():
    return _get_skew_shader_impl(_OVERLAY_GPU_STATE)


def _get_skew_batch_format():
    return _get_skew_batch_format_impl(_OVERLAY_GPU_STATE)


def _build_batch(primitive_type, positions):
    return _build_batch_impl(
        primitive_type,
        positions,
        get_shader_fn=_get_shader,
    )


def _low_depth_mask_supported() -> bool:
    return _low_depth_mask_supported_impl()


def _low_depth_mask_dimensions(width: int, height: int) -> tuple[int, int]:
    return _low_depth_mask_dimensions_impl(
        width,
        height,
        max_supersample_scale=_LOW_DEPTH_MASK_MAX_SUPERSAMPLE_SCALE,
        max_supersample_texels=_LOW_DEPTH_MASK_SUPERSAMPLE_MAX_TEXELS,
        max_supersample_dimension=_LOW_DEPTH_MASK_SUPERSAMPLE_MAX_DIMENSION,
    )


def _shell_depth_mask_dimensions(width: int, height: int) -> tuple[int, int]:
    return _low_depth_mask_dimensions_impl(
        width,
        height,
        max_supersample_scale=1,
        max_supersample_texels=_LOW_DEPTH_MASK_SUPERSAMPLE_MAX_TEXELS,
        max_supersample_dimension=_LOW_DEPTH_MASK_SUPERSAMPLE_MAX_DIMENSION,
    )


def _render_low_depth_mask(low_depth_batches, width: int, height: int, *, model_view_projection_matrix=None, model_view_matrix=None, shell_depth=False):
    if shell_depth:
        return _render_shell_depth_mask_impl(
            _OVERLAY_GPU_STATE,
            low_depth_batches,
            width,
            height,
            model_view_projection_matrix=model_view_projection_matrix,
            low_depth_mask_dimensions_fn=_shell_depth_mask_dimensions,
            ensure_depth_mask_resources_fn=_ensure_shell_low_depth_mask_resources_impl,
            get_depth_mask_shader_fn=_get_shell_low_depth_mask_shader_impl,
            log_mask_error_fn=_log_mask_error_once_impl,
        )
    return _render_low_depth_mask_impl(
        _OVERLAY_GPU_STATE,
        low_depth_batches,
        width,
        height,
        model_view_projection_matrix=model_view_projection_matrix,
        model_view_matrix=model_view_matrix,
        low_depth_mask_dimensions_fn=_low_depth_mask_dimensions,
        ensure_low_depth_mask_resources_fn=_ensure_low_depth_mask_resources_impl,
        get_low_depth_mask_shader_fn=_get_low_depth_mask_shader_impl,
        log_mask_error_fn=_log_mask_error_once_impl,
    )


def _render_cage_depth_mask(
    pass_offsets,
    width: int,
    height: int,
    *,
    model_view_projection_matrix=None,
    model_view_matrix=None,
):
    return _render_cage_pass_depth_mask_impl(
        _OVERLAY_GPU_STATE,
        pass_offsets,
        width,
        height,
        model_view_projection_matrix=model_view_projection_matrix,
        model_view_matrix=model_view_matrix,
        low_depth_mask_dimensions_fn=_shell_depth_mask_dimensions,
        ensure_depth_mask_resources_fn=_ensure_shell_cage_depth_mask_resources_impl,
        get_depth_mask_shader_fn=_get_shell_cage_depth_mask_shader_impl,
        get_paint_depth_mask_shader_fn=_get_shell_cage_paint_depth_mask_shader_impl,
        log_mask_error_fn=_log_mask_error_once_impl,
    )


def _build_offset_gpu_batch(primitive_type: str, positions, normals, *, uvs=None, paints=None):
    return _build_offset_gpu_batch_impl(
        _OVERLAY_GPU_STATE,
        primitive_type,
        positions,
        normals,
        uvs=uvs,
        paints=paints,
        get_offset_batch_format_fn=_get_offset_batch_format_impl,
        get_paint_offset_batch_format_fn=_get_paint_offset_batch_format_impl,
    )


def _build_offset_batch(buffers: cage.OffsetBatchBuffers, *, primitive_type: str = "TRIS"):
    return _build_offset_batch_impl(
        buffers,
        primitive_type=primitive_type,
        build_offset_gpu_batch_fn=_build_offset_gpu_batch,
        get_offset_shader_fn=_get_offset_shader,
    )


def _build_lit_offset_batch(buffers: cage.OffsetBatchBuffers):
    return _build_lit_offset_batch_impl(
        buffers,
        build_offset_gpu_batch_fn=_build_offset_gpu_batch,
        get_lit_offset_shader_fn=_get_lit_offset_shader,
    )


def _build_paint_offset_batch(buffers: cage.OffsetBatchBuffers, *, primitive_type: str = "TRIS"):
    return _build_paint_offset_batch_impl(
        buffers,
        primitive_type=primitive_type,
        build_offset_gpu_batch_fn=_build_offset_gpu_batch,
        get_paint_offset_shader_fn=_get_paint_offset_shader,
    )


_triangle_face_normal_from_positions = _triangle_face_normal_from_positions_impl


def _build_lit_batch_from_positions(positions, fill_color, normals=None):
    return _build_lit_batch_from_positions_impl(
        positions,
        fill_color,
        normals=normals,
        light_direction=_HEATMAP_LIGHT_DIRECTION,
        get_lit_batch_format_fn=_get_lit_batch_format,
        get_lit_shader_fn=_get_lit_shader,
    )


_line_render_enabled = _line_render_enabled_impl


def _make_overlay_pass(buffers: cage.DrawBuffers, fill_color, line_color, line_width, *, face_culling_mode: str | None = None) -> OverlayPass:
    return _make_overlay_pass_impl(
        buffers,
        fill_color,
        line_color,
        line_width,
        build_batch_fn=_build_batch,
        face_culling_mode=face_culling_mode,
    )


def _make_offset_overlay_pass(fill_batch, fill_color, offset: float, *, offset_group=None) -> OverlayPass:
    return _make_offset_overlay_pass_impl(
        fill_batch,
        fill_color,
        offset,
        get_offset_shader_fn=_get_offset_shader,
        offset_group=offset_group,
    )


def _make_lit_offset_overlay_pass(fill_batch, fill_color, offset: float, *, offset_group=None) -> OverlayPass:
    return _make_lit_offset_overlay_pass_impl(
        fill_batch,
        fill_color,
        offset,
        get_lit_offset_shader_fn=_get_lit_offset_shader,
        offset_group=offset_group,
    )


def _make_paint_offset_overlay_pass(
    fill_batch,
    fill_color,
    offset: float,
    *,
    paint_texture,
    line_batch=None,
    line_color=(0.0, 0.0, 0.0, 0.0),
    line_width=0.0,
    offset_group=None,
    uses_group_offset: bool = True,
    paint_offset_scale: float = 1.0,
    show_paint_mask: bool = False,
) -> OverlayPass:
    return _make_paint_offset_overlay_pass_impl(
        fill_batch,
        fill_color,
        offset,
        paint_texture=paint_texture,
        get_paint_offset_shader_fn=_get_paint_offset_shader,
        line_batch=line_batch,
        line_color=line_color,
        line_width=line_width,
        offset_group=offset_group,
        uses_group_offset=uses_group_offset,
        paint_offset_scale=paint_offset_scale,
        show_paint_mask=show_paint_mask,
    )


def _make_offset_line_overlay_pass(
    line_batch,
    line_color,
    line_width: float,
    offset: float,
    *,
    uses_group_offset: bool,
    offset_group=None,
) -> OverlayPass:
    return _make_offset_line_overlay_pass_impl(
        line_batch,
        line_color,
        line_width,
        offset,
        uses_group_offset=uses_group_offset,
        get_offset_shader_fn=_get_offset_shader,
        offset_group=offset_group,
    )


def _make_line_overlay_pass(line_batch, line_color, line_width: float) -> OverlayPass:
    return _make_line_overlay_pass_impl(line_batch, line_color, line_width)


def _make_lit_heatmap_overlay_pass(fill_batch, fill_color, *, blend_mode, face_culling_mode) -> OverlayPass:
    return _make_lit_heatmap_overlay_pass_impl(
        fill_batch,
        fill_color,
        blend_mode=blend_mode,
        face_culling_mode=face_culling_mode,
        get_lit_shader_fn=_get_lit_shader,
    )


def _matching_error_overlay_passes_from_debug_result(debug_result, theme, *, include_inside: bool):
    return _matching_error_overlay_passes_from_debug_result_impl(
        _DEBUG_RESULT_PASS_CACHE,
        debug_result,
        theme,
        include_inside=include_inside,
        build_lit_batch_from_positions_fn=_build_lit_batch_from_positions,
        make_lit_heatmap_overlay_pass_fn=_make_lit_heatmap_overlay_pass,
    )


def _heatmap_overlay_passes_from_debug_result(debug_result, theme, *, include_inside: bool):
    return _heatmap_overlay_passes_from_debug_result_impl(
        _DEBUG_RESULT_PASS_CACHE,
        debug_result,
        theme,
        include_inside=include_inside,
        build_lit_batch_from_positions_fn=_build_lit_batch_from_positions,
        make_lit_heatmap_overlay_pass_fn=_make_lit_heatmap_overlay_pass,
    )


def _use_screen_heatmap_overlay(context, debug_result) -> bool:
    return _use_screen_heatmap_overlay_impl(
        context,
        debug_result,
        screen_heatmap_draw_supported_fn=_screen_heatmap_draw_supported,
    )


def _screen_heatmap_draw_supported() -> bool:
    return _screen_heatmap_draw_supported_impl(
        draw_texture_2d_fn=_draw_texture_2d,
        gpu_module=gpu,
    )


def _maybe_request_screen_heatmap_refresh(context, scene, project, group, debug_result) -> None:
    return


def _draw_screen_heatmap_overlay_post_pixel():
    return


_draw_batch = _draw_batch_impl


_iter_valid_meshes = _iter_valid_meshes_impl
_object_visible_in_viewport = _object_visible_in_viewport_impl
_all_low_meshes_visible_in_viewport = _all_low_meshes_visible_in_viewport_impl


def _data_collection(name: str):
    data = getattr(bpy, "data", None)
    if data is None:
        return None
    return getattr(data, name, None)


def _estimate_low_depth_epsilon(low_triangle_sets: list[list[cage.TriangleData]]) -> float:
    return _estimate_low_depth_epsilon_impl(
        low_triangle_sets,
        epsilon_min=_HEATMAP_LOW_DEPTH_EPSILON_MIN,
        epsilon_max=_HEATMAP_LOW_DEPTH_EPSILON_MAX,
        bounds_factor=_HEATMAP_LOW_DEPTH_EPSILON_BOUNDS_FACTOR,
        edge_factor=_HEATMAP_LOW_DEPTH_EPSILON_EDGE_FACTOR,
    )


_object_bounds_signature = _object_bounds_signature_impl
_id_update_signature = _id_update_signature_impl
_object_signature = _object_signature_impl
_object_cache_signature = _object_cache_signature_impl
_effective_static_debug_flags = _effective_static_debug_flags_impl
_static_overlay_key = _static_overlay_key_impl


def bump_skew_paint_version() -> None:
    """Force one skew-field regeneration on the next draw.

    Regeneration is throttled while painting, so the last strokes of a session can
    land after the final scheduled bump; ending the session spends one rebuild to
    make sure the needles match what was actually painted.
    """
    global _SKEW_PAINT_VERSION
    _SKEW_PAINT_VERSION += 1
    _reset_skew_paint_bump_throttle()
    invalidate_overlay_cache(clear_static=False)


def _active_paint_session_version(context, group) -> int:
    """Advance a counter while the artist is painting on this group's canvas.

    Texture paint writes image pixels only: it fires no depsgraph update and moves
    no key term, so the display cache stayed valid and the paint mask kept sampling
    the GPU texture captured when paint mode opened. Returning a fresh number per
    call rebuilds the display cache (~1 ms, static geometry retained) on each redraw
    of a live paint session, and a constant 0 the rest of the time -- so the cost is
    paid only while it buys live feedback.
    """
    global _PAINT_SESSION_VERSION
    active_object = getattr(context, "active_object", None)
    if active_object is None or getattr(active_object, "mode", "") != "TEXTURE_PAINT":
        return 0
    tool_settings = getattr(getattr(context, "scene", None), "tool_settings", None)
    canvas = getattr(getattr(tool_settings, "image_paint", None), "canvas", None)
    if canvas is None or group is None:
        return 0
    paint_state = _group_paint_projection_settings_state(group)
    for image_attr in ("paint_offset_image", "paint_skew_image"):
        if getattr(paint_state, image_attr, None) is canvas:
            _PAINT_SESSION_VERSION += 1
            return _PAINT_SESSION_VERSION
    return 0


def _display_overlay_key(context, settings, project, group, static_key):
    return _display_overlay_key_impl(
        context,
        settings,
        project,
        group,
        static_key,
        interaction_active=_interaction_active(),
        skew_paint_version=_SKEW_PAINT_VERSION,
        paint_session_version=_active_paint_session_version(context, group),
    )


def _backend_debug_result_is_stale(scene, project, group, debug_result) -> bool:
    if scene is None or project is None or group is None or debug_result is None:
        return False
    try:
        input_signature = export.debug_overlay_input_signature(project, group)
    except Exception:
        return False
    return not runtime.debug_overlay_result_matches_input_signature(scene, project, group, input_signature)


def _reset_high_reference_runtime() -> None:
    _reset_high_reference_runtime_impl(
        _HIGH_REFERENCE_RUNTIME_STATE,
        timer_fn=_high_reference_build_timer,
    )


def _reset_auto_cage_preview_runtime() -> None:
    state = _preview_build_runtime_state_from_globals()
    _reset_auto_cage_preview_runtime_impl(state, timer_fn=_auto_cage_preview_build_timer)
    _sync_preview_build_runtime_state(state)


def _reset_distance_average_normals_preview_runtime() -> None:
    state = _preview_build_runtime_state_from_globals()
    _reset_distance_average_normals_preview_runtime_impl(
        state,
        timer_fn=_distance_average_normals_preview_build_timer,
    )
    _sync_preview_build_runtime_state(state)


def _reset_preview_visibility_sync_runtime() -> None:
    state = _preview_visibility_sync_state_from_globals()
    _reset_preview_visibility_sync_runtime_impl(
        state,
        timer_fn=_preview_visibility_sync_timer,
    )
    _sync_preview_visibility_sync_state(state)


def _enqueue_auto_cage_preview_build(group, key) -> None:
    state = _preview_build_runtime_state_from_globals()
    _enqueue_auto_cage_preview_build_impl(
        state,
        group=group,
        key=key,
        ensure_timer_registered_fn=lambda interval: _ensure_auto_cage_preview_build_timer_registered_impl(
            state,
            timer_fn=_auto_cage_preview_build_timer,
            first_interval=interval,
        ),
    )
    _sync_preview_build_runtime_state(state)


def _enqueue_distance_average_normals_preview_build(
    key: tuple,
    slots: list[DistanceAverageNormalsPreviewSlotBuildInput],
) -> None:
    state = _preview_build_runtime_state_from_globals()
    _enqueue_distance_average_normals_preview_build_impl(
        state,
        key=key,
        slots=slots,
        ensure_timer_registered_fn=lambda interval: _ensure_distance_average_normals_preview_build_timer_registered_impl(
            state,
            timer_fn=_distance_average_normals_preview_build_timer,
            first_interval=interval,
        ),
    )
    _sync_preview_build_runtime_state(state)


def _high_reference_build_timer():
    return _high_reference_build_timer_tick_impl(_HIGH_REFERENCE_RUNTIME_STATE)


def _auto_cage_preview_build_timer():
    state = _preview_build_runtime_state_from_globals()
    delay = _auto_cage_preview_build_timer_tick_impl(
        state,
        deps=_preview_build_deps(),
    )
    _sync_preview_build_runtime_state(state)
    return delay


def _distance_average_normals_preview_build_timer():
    state = _preview_build_runtime_state_from_globals()
    delay = _distance_average_normals_preview_build_timer_tick_impl(
        state,
        deps=_preview_build_deps(),
    )
    _sync_preview_build_runtime_state(state)
    return delay


def invalidate_overlay_cache(*, clear_static: bool = True, clear_cage_check: bool = False):
    # The cage-coverage (cage-check) batches are expensive to rebuild (per-high-vertex
    # nearest-surface pass) and self-validate by geometry signature, so they must NOT be
    # dropped on every clear_static (which fires on selection / group switch / mode change).
    # Only real geometry edits — routed here with clear_cage_check=True from the depsgraph
    # handler — invalidate them; config changes are caught by the signature instead.
    _invalidate_overlay_cache_state(_OVERLAY_CACHE_STATE, clear_static=clear_static)
    if clear_cage_check:
        _clear_cage_check_gpu_cache_impl()


def _interaction_active() -> bool:
    return _interaction_active_impl(
        legacy_state=_LEGACY_OVERLAY_RUNTIME_STATE,
        now_fn=lambda: time.monotonic(),
    )


def _prewarm_overlay_deferred() -> bool:
    try:
        return bool(runtime.overlay_work_deferred())
    except Exception:
        return False


def _post_load_overlay_grace_active() -> bool:
    # Also holds while bake-critical prewarm work (exports, cage fits, the speculative
    # PREPARE) is queued, so overlay rebuilds do not share that main-thread time.
    return _post_load_overlay_grace_active_impl(
        legacy_state=_LEGACY_OVERLAY_RUNTIME_STATE,
        now_fn=lambda: time.monotonic(),
    ) or _prewarm_overlay_deferred()


def _post_load_overlay_grace_delay() -> float:
    delay = _post_load_overlay_grace_delay_impl(
        legacy_state=_LEGACY_OVERLAY_RUNTIME_STATE,
        now_fn=lambda: time.monotonic(),
    )
    if _prewarm_overlay_deferred():
        # Poll slowly: a 50 ms retry would redraw the viewport 20 times a second for nothing.
        return max(delay, runtime.overlay_defer_poll_seconds())
    return delay


def _preview_build_deps() -> OverlayPreviewBuildDeps:
    return OverlayPreviewBuildDeps(
        iter_valid_meshes=_iter_valid_meshes,
        post_load_overlay_grace_active=_post_load_overlay_grace_active,
        post_load_overlay_grace_delay=_post_load_overlay_grace_delay,
        invalidate_overlay_cache=lambda: invalidate_overlay_cache(clear_static=True),
        tag_redraw_all_view3d=lambda: _tag_redraw_all_view3d(window=getattr(bpy.context, "window", None)),
    )


def _schedule_interaction_redraw(delay_seconds: float) -> None:
    state = _overlay_registration_state_from_globals()
    _schedule_interaction_redraw_impl(
        state,
        timer_fn=_interaction_redraw_timer,
        delay_seconds=delay_seconds,
        now_fn=lambda: time.monotonic(),
    )
    _sync_overlay_registration_state(state)


def mark_interaction(duration: float = constants.VIEWPORT_INTERACTION_GRACE_SECONDS) -> None:
    redraw_delay = _mark_interaction_impl(
        legacy_state=_LEGACY_OVERLAY_RUNTIME_STATE,
        duration=float(duration),
        now_fn=lambda: time.monotonic(),
        debug_refresh_delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
    )
    _schedule_interaction_redraw(redraw_delay)


def _interaction_redraw_timer():
    state = _overlay_registration_state_from_globals()
    delay = _interaction_redraw_timer_tick_impl(
        state,
        now_fn=lambda: time.monotonic(),
        tag_redraw_all_view3d_fn=_tag_redraw_all_view3d,
    )
    _sync_overlay_registration_state(state)
    return delay


def _schedule_preview_visibility_sync(scene=None, *, first_interval: float | None = None) -> bool:
    state = _preview_visibility_sync_state_from_globals()
    scheduled = _schedule_preview_visibility_sync_impl(
        state,
        timer_fn=_preview_visibility_sync_timer,
        scene=scene,
        first_interval=first_interval,
        post_load_overlay_grace_until=_LEGACY_OVERLAY_RUNTIME_STATE.post_load_overlay_grace_until,
        now_fn=lambda: time.monotonic(),
    )
    _sync_preview_visibility_sync_state(state)
    return scheduled


def _preview_visibility_sync_timer():
    state = _preview_visibility_sync_state_from_globals()
    try:
        delay = _preview_visibility_sync_timer_tick_impl(
            state,
            post_load_overlay_grace_active_fn=_post_load_overlay_grace_active,
            post_load_overlay_grace_delay_fn=_post_load_overlay_grace_delay,
            sync_preview_visibility_now_fn=_sync_preview_visibility_now,
            tag_redraw_all_view3d_fn=_tag_redraw_all_view3d,
        )
    except Exception:
        traceback.print_exc()
        delay = None
    _sync_preview_visibility_sync_state(state)
    return delay


def _is_valid_object(obj) -> bool:
    if obj is None:
        return False
    try:
        return obj.as_pointer() != 0
    except Exception:
        return False


def _is_valid_mesh(mesh) -> bool:
    if mesh is None:
        return False
    try:
        return mesh.as_pointer() != 0
    except Exception:
        return False


_CAGE_VISUALIZATION = _create_cage_visualization_controller_impl(
    constants_module=constants,
    data_collection_fn=_data_collection,
    is_valid_object_fn=_is_valid_object,
    is_valid_mesh_fn=_is_valid_mesh,
    object_signature_fn=_object_signature,
    iter_valid_meshes_fn=_iter_valid_meshes,
    preview_collection_name=_PREVIEW_COLLECTION_NAME,
    preview_material_name=_PREVIEW_MATERIAL_NAME,
    preview_modifier_name=_PREVIEW_MODIFIER_NAME,
)
_PREVIEW_HIDDEN_STATE = _CAGE_VISUALIZATION.preview_hidden_state
_PREVIEW_PROXY_STATE = _CAGE_VISUALIZATION.preview_proxy_state

_high_reference_native_preview_supported = _CAGE_VISUALIZATION.high_reference_native_preview_supported
_sync_high_reference_preview_objects = _CAGE_VISUALIZATION.sync_high_reference_preview_objects
_clear_preview_proxy_states = _CAGE_VISUALIZATION.clear_preview_proxy_states
_restore_preview_hidden_objects = _CAGE_VISUALIZATION.restore_preview_hidden_objects
_sync_generated_custom_cage_visibility = _CAGE_VISUALIZATION.sync_generated_custom_cage_visibility
_sync_preview_proxy_objects = _CAGE_VISUALIZATION.sync_preview_proxy_objects
_sync_heatmap_preview = _CAGE_VISUALIZATION.sync_heatmap_preview
_clear_heatmap_preview = _CAGE_VISUALIZATION.clear_heatmap_preview
_apply_object_override_material = _apply_object_override_material_impl


def _high_reference_uses_native_preview(settings, group) -> bool:
    return _high_reference_uses_native_preview_impl(
        _high_reference_native_preview_supported,
        settings,
        group,
    )


def _preview_visibility_deps() -> PreviewVisibilityDeps:
    return _build_preview_visibility_deps_impl(
        preview_suppressed_for_context_fn=cage_session.preview_suppressed_for_context,
        resolve_project_group_fn=cage_session.resolve_project_group,
        restore_preview_hidden_objects_fn=_restore_preview_hidden_objects,
        clear_preview_proxy_states_fn=_clear_preview_proxy_states,
        clear_heatmap_preview_fn=_clear_heatmap_preview,
        sync_generated_custom_cage_visibility_fn=_sync_generated_custom_cage_visibility,
        reset_high_reference_runtime_fn=_reset_high_reference_runtime,
        sync_high_reference_preview_objects_fn=_sync_high_reference_preview_objects,
        sync_preview_proxy_objects_fn=_sync_preview_proxy_objects,
        sync_heatmap_preview_fn=_sync_heatmap_preview,
    )


def _sync_preview_visibility_now(scene=None) -> None:
    _sync_preview_visibility_now_impl(scene, deps=_preview_visibility_deps())

def sync_preview_visibility(scene=None) -> None:
    _sync_preview_visibility_impl(
        scene,
        post_load_overlay_grace_active_fn=_post_load_overlay_grace_active,
        schedule_preview_visibility_sync_fn=_schedule_preview_visibility_sync,
        sync_preview_visibility_now_fn=_sync_preview_visibility_now,
    )


def _cleanup_preview_runtime_for_save() -> None:
    _cleanup_preview_runtime_for_save_impl(
        deps=PreviewCleanupDeps(
            reset_preview_visibility_sync_runtime=_reset_preview_visibility_sync_runtime,
            cleanup_preview_runtime=_CAGE_VISUALIZATION.cleanup_preview_runtime,
            reset_high_reference_runtime=_reset_high_reference_runtime,
            reset_auto_cage_preview_runtime=_reset_auto_cage_preview_runtime,
            reset_distance_average_normals_preview_runtime=_reset_distance_average_normals_preview_runtime,
            invalidate_overlay_cache=invalidate_overlay_cache,
        )
    )


_visible_viewport_triangles = _visible_viewport_triangles_impl


def _high_reference_overlay_passes(context, group, theme) -> list[OverlayPass]:
    return _high_reference_overlay_passes_impl(
        _HIGH_REFERENCE_RUNTIME_STATE,
        context,
        group,
        theme,
    )


def _build_skew_colored_line_batch(buffers: cage.OffsetBatchBuffers):
    return _build_skew_colored_line_batch_impl(
        buffers,
        get_skew_batch_format_fn=_get_skew_batch_format,
        get_skew_shader_fn=_get_skew_shader,
    )


def _skew_overlay_pass_from_batch(buffers: cage.OffsetBatchBuffers, theme) -> OverlayPass | None:
    return _skew_overlay_pass_from_batch_impl(
        buffers,
        theme,
        build_skew_colored_line_batch_fn=_build_skew_colored_line_batch,
        build_batch_fn=_build_batch,
        make_line_overlay_pass_fn=_make_line_overlay_pass,
        get_skew_shader_fn=_get_skew_shader,
    )


_CACHE_BUILD_DEPS = _build_overlay_cache_builder_deps_impl(
    overlay_theme_for_settings_fn=lambda settings: _overlay_theme_for_settings(settings),
    effective_static_debug_flags_fn=lambda settings: _effective_static_debug_flags(settings),
    line_render_enabled_fn=lambda line_color, line_width: _line_render_enabled(line_color, line_width),
    build_batch_fn=lambda primitive_type, positions: _build_batch(primitive_type, positions),
    build_offset_batch_fn=lambda buffers, primitive_type="TRIS": _build_offset_batch(buffers, primitive_type=primitive_type),
    build_lit_offset_batch_fn=lambda buffers: _build_lit_offset_batch(buffers),
    build_paint_offset_batch_fn=lambda buffers, primitive_type="TRIS": _build_paint_offset_batch(buffers, primitive_type=primitive_type),
    estimate_low_depth_epsilon_fn=lambda triangle_sets: _estimate_low_depth_epsilon(triangle_sets),
    iter_valid_meshes_fn=lambda slot_collection: _iter_valid_meshes(slot_collection),
    make_overlay_pass_fn=lambda buffers, fill_color, line_color, line_width, face_culling_mode=None: _make_overlay_pass(
        buffers,
        fill_color,
        line_color,
        line_width,
        face_culling_mode=face_culling_mode,
    ),
    make_line_overlay_pass_fn=lambda line_batch, line_color, line_width: _make_line_overlay_pass(line_batch, line_color, line_width),
    make_offset_overlay_pass_fn=lambda fill_batch, fill_color, offset, offset_group=None: _make_offset_overlay_pass(
        fill_batch,
        fill_color,
        offset,
        offset_group=offset_group,
    ),
    make_lit_offset_overlay_pass_fn=lambda fill_batch, fill_color, offset, offset_group=None: _make_lit_offset_overlay_pass(
        fill_batch,
        fill_color,
        offset,
        offset_group=offset_group,
    ),
    make_paint_offset_overlay_pass_fn=lambda fill_batch, fill_color, offset, paint_texture, line_batch=None, line_color=(0.0, 0.0, 0.0, 0.0), line_width=0.0, offset_group=None, uses_group_offset=True, paint_offset_scale=1.0, show_paint_mask=False: _make_paint_offset_overlay_pass(
        fill_batch,
        fill_color,
        offset,
        paint_texture=paint_texture,
        line_batch=line_batch,
        line_color=line_color,
        line_width=line_width,
        offset_group=offset_group,
        uses_group_offset=uses_group_offset,
        paint_offset_scale=paint_offset_scale,
        show_paint_mask=show_paint_mask,
    ),
    make_offset_line_overlay_pass_fn=lambda line_batch, line_color, line_width, offset, uses_group_offset, offset_group=None: _make_offset_line_overlay_pass(
        line_batch,
        line_color,
        line_width,
        offset,
        uses_group_offset=uses_group_offset,
        offset_group=offset_group,
    ),
    heatmap_overlay_passes_from_debug_result_fn=lambda debug_result, theme, include_inside: _heatmap_overlay_passes_from_debug_result(
        debug_result,
        theme,
        include_inside=include_inside,
    ),
    use_screen_heatmap_overlay_fn=lambda context, debug_result: _use_screen_heatmap_overlay(context, debug_result),
    backend_debug_result_is_stale_fn=lambda scene, project, group, debug_result: _backend_debug_result_is_stale(
        scene,
        project,
        group,
        debug_result,
    ),
    skew_overlay_pass_from_batch_fn=lambda buffers, theme: _skew_overlay_pass_from_batch(buffers, theme),
    enqueue_auto_cage_preview_build_fn=lambda group, key: _enqueue_auto_cage_preview_build(group, key),
    enqueue_distance_average_normals_preview_build_fn=lambda key, slots: _enqueue_distance_average_normals_preview_build(key, slots),
)


def _build_static_overlay_cache(context, settings, group, key):
    return _build_static_overlay_cache_impl(
        context=context,
        settings=settings,
        group=group,
        key=key,
        auto_cage_preview_cache=_LEGACY_OVERLAY_RUNTIME_STATE.auto_cage_preview_cache,
        distance_average_normals_preview_cache=_LEGACY_OVERLAY_RUNTIME_STATE.distance_average_normals_preview_cache,
        deps=_CACHE_BUILD_DEPS,
    )

def _build_overlay_cache(context, settings, project, group, static_cache, key):
    return _build_overlay_cache_impl(
        context=context,
        settings=settings,
        project=project,
        group=group,
        static_cache=static_cache,
        key=key,
        interaction_active=_interaction_active(),
        deps=_CACHE_BUILD_DEPS,
        skew_paint_version=_SKEW_PAINT_VERSION,
    )


def _get_overlay_cache(context, settings, project, group):
    return _get_overlay_cache_impl(
        _OVERLAY_CACHE_STATE,
        context=context,
        settings=settings,
        project=project,
        group=group,
        static_key_fn=_static_overlay_key,
        display_key_fn=_display_overlay_key,
        build_static_cache_fn=_build_static_overlay_cache,
        build_overlay_cache_fn=_build_overlay_cache,
        post_load_overlay_grace_active_fn=_post_load_overlay_grace_active,
        schedule_interaction_redraw_fn=lambda delay: _schedule_interaction_redraw(
            max(delay, runtime.overlay_defer_poll_seconds()) if _prewarm_overlay_deferred() else delay
        ),
        post_load_overlay_grace_until=_LEGACY_OVERLAY_RUNTIME_STATE.post_load_overlay_grace_until,
    )


def _request_debug_overlay_refresh_for_group(context, project, group, *, delay_seconds, reason) -> None:
    request_fn = getattr(runtime, "request_debug_overlay_refresh", None)
    if not callable(request_fn):
        return
    kwargs = {"delay_seconds": delay_seconds, "reason": reason}
    # Coverage is drawn for every visible group, not just the active one, so the request has
    # to name the group that drew it. Probe the wrapper instead of assuming it forwards the
    # target, so an older runtime signature degrades to the active-group lookup rather than
    # raising out of the draw callback.
    try:
        parameters = inspect.signature(request_fn).parameters
    except (TypeError, ValueError):
        parameters = {}
    accepts_any_keyword = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    if project is not None and (accepts_any_keyword or "project" in parameters):
        kwargs["project"] = project
    if group is not None and (accepts_any_keyword or "group" in parameters):
        kwargs["group"] = group
    request_fn(context, **kwargs)


def _ensure_cage_check_debug_result(context, scene, project, group) -> bool:
    if context is None or scene is None or project is None or group is None:
        return False
    settings = getattr(scene, "fyr_baker_settings", None)
    overlay_state = _overlay_settings_state(settings) if settings is not None else None
    if overlay_state is None or not bool(getattr(overlay_state, "show_error_heatmap", False)):
        return False
    input_signature = export.debug_overlay_input_signature(project, group)
    debug_result = runtime.peek_debug_overlay_result(scene, project, group)
    has_sdf = bool(str(getattr(debug_result, "cage_sdf_path", "") or "").strip()) if debug_result is not None else False
    if has_sdf and runtime.debug_overlay_result_matches_input_signature(scene, project, group, input_signature):
        return True
    refresh_pending_fn = getattr(runtime, "debug_overlay_refresh_pending", None)
    if callable(refresh_pending_fn) and refresh_pending_fn(scene, project, group):
        return False
    _request_debug_overlay_refresh_for_group(
        context,
        project,
        group,
        delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        reason="cage_check_missing_sdf",
    )
    return False


def _renderer_deps() -> OverlayRendererDeps:
    return _build_renderer_deps_impl(
        preview_suppressed_for_context_fn=cage_session.preview_suppressed_for_context,
        resolve_project_group_fn=cage_session.resolve_project_group,
        get_overlay_cache_fn=_get_overlay_cache,
        overlay_theme_for_settings_fn=_overlay_theme_for_settings,
        get_shader_fn=_get_shader,
        render_low_depth_mask_fn=lambda low_depth_batches, width, height, model_view_projection_matrix=None, model_view_matrix=None, shell_depth=False: _render_low_depth_mask(
            low_depth_batches,
            width,
            height,
            model_view_projection_matrix=model_view_projection_matrix,
            model_view_matrix=model_view_matrix,
            shell_depth=shell_depth,
        ),
        render_cage_depth_mask_fn=lambda pass_offsets, width, height, model_view_projection_matrix=None, model_view_matrix=None: _render_cage_depth_mask(
            pass_offsets,
            width,
            height,
            model_view_projection_matrix=model_view_projection_matrix,
            model_view_matrix=model_view_matrix,
        ),
        line_render_enabled_fn=_line_render_enabled,
        get_heatmap_mask_shader_fn=_get_heatmap_mask_shader,
        log_mask_error_fn=_log_mask_error_once,
        heatmap_low_depth_epsilon_min=_HEATMAP_LOW_DEPTH_EPSILON_MIN,
        ensure_cage_check_debug_result_fn=_ensure_cage_check_debug_result,
        draw_cage_check_overlay_fn=_draw_cage_check_overlay_impl,
    )


def _overlay_tracking_deps() -> OverlayTrackingDeps:
    return _build_overlay_tracking_deps_impl(
        resolve_project_group_fn=cage_session.resolve_project_group,
        iter_valid_meshes_fn=_iter_valid_meshes,
        is_valid_object_fn=_is_valid_object,
        is_valid_mesh_fn=_is_valid_mesh,
        preview_collection_name=_PREVIEW_COLLECTION_NAME,
    )


def _overlay_event_bridge_deps() -> OverlayEventBridgeDeps:
    return _build_overlay_event_bridge_deps_impl(
        tracking=_overlay_tracking_deps(),
        debug_overlay_enabled_fn=runtime.debug_overlay_enabled,
        invalidate_debug_overlay_export_cache_fn=runtime.invalidate_debug_overlay_export_cache,
        request_debug_overlay_refresh_fn=runtime.request_debug_overlay_refresh,
        mark_interaction_fn=mark_interaction,
        tag_redraw_all_view3d_fn=tag_redraw_all_view3d,
        invalidate_overlay_cache_fn=invalidate_overlay_cache,
        reset_auto_cage_preview_runtime_fn=_reset_auto_cage_preview_runtime,
        reset_distance_average_normals_preview_runtime_fn=_reset_distance_average_normals_preview_runtime,
        reset_preview_visibility_sync_runtime_fn=_reset_preview_visibility_sync_runtime,
        clear_preview_proxy_states_fn=_CAGE_VISUALIZATION.clear_preview_proxy_states,
        reset_high_reference_runtime_fn=_reset_high_reference_runtime,
        sync_preview_visibility_fn=sync_preview_visibility,
        invalidate_debug_overlay_cache_fn=runtime.invalidate_debug_overlay_cache,
        cleanup_preview_runtime_fn=_CAGE_VISUALIZATION.cleanup_preview_runtime,
        debug_refresh_delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        now_fn=time.monotonic,
    )


def _overlay_registration_deps() -> OverlayRegistrationDeps:
    return _build_overlay_registration_deps_impl(
        draw_group_overlay_fn=_draw_group_overlay,
        draw_screen_heatmap_overlay_post_pixel_fn=_draw_screen_heatmap_overlay_post_pixel,
        depsgraph_update_post_fn=_depsgraph_update_post,
        load_post_fn=_load_post,
        save_pre_fn=_save_pre,
        save_post_fn=_save_post,
        event_bridge=_overlay_event_bridge_deps(),
        interaction_redraw_timer_fn=_interaction_redraw_timer,
    )


def _draw_group_overlay():
    global _LAST_DRAW_ERROR
    with properties.role_sync_once_per_pass():
        _LAST_DRAW_ERROR = _draw_group_overlay_impl(
            last_draw_error=_LAST_DRAW_ERROR,
            deps=_renderer_deps(),
        )


def _tag_redraw_all_view3d(*, window=None):
    _tag_redraw_all_view3d_impl(window=window)


_persistent = getattr(bpy.app.handlers, "persistent", lambda fn: fn)


def _tracked_overlay_id_pointers(scene) -> set[int]:
    return _tracked_overlay_id_pointers_impl(scene, deps=_overlay_tracking_deps())


def _depsgraph_requires_static_invalidation(scene, depsgraph) -> bool:
    return _depsgraph_requires_static_invalidation_impl(scene, depsgraph, deps=_overlay_tracking_deps())


@_persistent
def _depsgraph_update_post(_scene, _depsgraph):
    global _SKEW_PAINT_VERSION
    # Blender also calls this from a bake/render job thread (handler_thread_guard).
    if not on_main_thread():
        return
    _SKEW_PAINT_VERSION = _handle_depsgraph_update_post_impl(
        _scene,
        _depsgraph,
        skew_paint_version=_SKEW_PAINT_VERSION,
        deps=_overlay_event_bridge_deps(),
    )
    return


@_persistent
def _load_post(_dummy):
    # The cage module's BVH / fitted-cage memos are keyed by runtime pointers, so an
    # entry built for the previous file could be handed to a mesh that happens to land
    # at the same address in this one.
    try:
        from . import cage

        cage.clear_geometry_caches()
        from .overlay_cache import clear_preview_target_batches

        clear_preview_target_batches()
    except Exception:
        pass
    _LEGACY_OVERLAY_RUNTIME_STATE.post_load_overlay_grace_until = _handle_load_post_impl(
        _dummy,
        deps=_overlay_event_bridge_deps(),
    )


@_persistent
def _save_pre(_dummy):
    _cleanup_preview_runtime_for_save()


@_persistent
def _save_post(_dummy):
    _handle_save_post_impl(
        _dummy,
        sync_preview_visibility_fn=sync_preview_visibility,
        tag_redraw_all_view3d_fn=_tag_redraw_all_view3d,
    )


def tag_redraw_all_view3d(*, scene=None, clear_static: bool = False, window=None, sync_preview: bool = True):
    if clear_static:
        invalidate_overlay_cache(clear_static=True)
    if sync_preview:
        sync_preview_visibility(scene)
    _tag_redraw_all_view3d(window=window)


def register():
    state = _overlay_registration_state_from_globals()
    try:
        state = _register_overlay_runtime_impl(
            state,
            deps=_overlay_registration_deps(),
        )
    finally:
        # register_overlay_runtime adds the two SpaceView3D draw handlers first and
        # then does scene work that can raise (sync_preview_visibility reaches into
        # cage_visualization, which raises RuntimeError in some states). It mutates
        # this same state object in place, so syncing it in a finally records the
        # handlers even on the exception path. Without that the module globals still
        # said draw_handler is None, unregister() had nothing to remove, and every
        # subsequent enable stacked another POST_VIEW handler on the class.
        _sync_overlay_registration_state(state)


def unregister():
    state = _overlay_registration_state_from_globals()
    state = _unregister_overlay_runtime_impl(
        state,
        deps=_overlay_registration_deps(),
    )
    _sync_overlay_registration_state(state)
    # Deterministically free the cage-check GPU resources (per-vertex batches, SDF /
    # compute textures) and unregister the chunked build timer on disable. The runtime
    # unregister above only drops the draw handlers; without this the large GPU batches
    # linger until GC and the build timer keeps firing against the stale module. On a
    # disable→purge→enable reload that stacks fresh VRAM allocations on top of the
    # not-yet-freed old ones, which can spike VRAM enough to TDR the GPU.
    try:
        _clear_cage_check_gpu_cache_impl()
    except Exception:
        pass
    # The pooled depth-mask offscreens (colour + depth per viewport size) were
    # never released here; a disable/reload stacked fresh ones on the old.
    try:
        _release_mask_resources_impl(_OVERLAY_GPU_STATE)
    except Exception:
        pass


def suspend_bake_overlay_draw_handlers() -> bool:
    """Bake low-impact L2: remove our two SpaceView3D draw handlers so the cage/
    coverage overlay draw (and its offscreen depth-mask passes) stops competing for
    the GPU while the baker worker owns it. The handlers are class-wide (not
    per-space), so this quiets every 3D viewport across every window at once.

    Returns True if any handler was present and removed; idempotent (a second call
    with no handlers installed is a no-op). Pair with resume_bake_overlay_draw_handlers
    on bake end."""
    state = _overlay_registration_state_from_globals()
    removed = False
    if state.draw_handler is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(state.draw_handler, "WINDOW")
        except Exception:
            pass
        state.draw_handler = None
        removed = True
    if state.draw_pixel_handler is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(state.draw_pixel_handler, "WINDOW")
        except Exception:
            pass
        state.draw_pixel_handler = None
        removed = True
    _sync_overlay_registration_state(state)
    return removed


def resume_bake_overlay_draw_handlers() -> None:
    """Bake low-impact L2: re-add the SpaceView3D draw handlers removed by
    suspend_bake_overlay_draw_handlers, exactly as register_overlay_runtime installs
    them (POST_VIEW group overlay + POST_PIXEL screen heatmap). Idempotent — only adds
    handlers that are currently absent, so a stray double-call cannot double-register."""
    state = _overlay_registration_state_from_globals()
    if state.draw_handler is None:
        try:
            state.draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                _draw_group_overlay, (), "WINDOW", "POST_VIEW"
            )
        except Exception:
            pass
    if state.draw_pixel_handler is None:
        try:
            state.draw_pixel_handler = bpy.types.SpaceView3D.draw_handler_add(
                _draw_screen_heatmap_overlay_post_pixel, (), "WINDOW", "POST_PIXEL"
            )
        except Exception:
            pass
    _sync_overlay_registration_state(state)


class _OverlayCompatModule(types.ModuleType):
    def __getattribute__(self, name):
        if name in LEGACY_RUNTIME_FIELD_MAP:
            state = types.ModuleType.__getattribute__(self, "_LEGACY_OVERLAY_RUNTIME_STATE")
            return _legacy_runtime_state_get(state, name)
        return types.ModuleType.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name in LEGACY_RUNTIME_FIELD_MAP:
            state = types.ModuleType.__getattribute__(self, "_LEGACY_OVERLAY_RUNTIME_STATE")
            _legacy_runtime_state_set(state, name, value)
            return
        return types.ModuleType.__setattr__(self, name, value)


_module = sys.modules.get(__name__)
if _module is not None and not isinstance(_module, _OverlayCompatModule):
    _module.__class__ = _OverlayCompatModule
