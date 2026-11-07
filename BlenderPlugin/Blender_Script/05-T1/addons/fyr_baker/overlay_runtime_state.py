from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import queue

from .overlay_events import OverlayRegistrationState, PreviewVisibilitySyncState
from .overlay_preview_builds import OverlayPreviewBuildRuntimeState


@dataclass(slots=True)
class OverlayLegacyRuntimeState:
    draw_handler: object | None = None
    draw_pixel_handler: object | None = None
    auto_cage_preview_cache: object | None = None
    auto_cage_preview_pending_request: object | None = None
    auto_cage_preview_build_result_queue: object = field(default_factory=queue.Queue)
    auto_cage_preview_build_thread: object | None = None
    auto_cage_preview_build_active_key: tuple | None = None
    auto_cage_preview_build_timer_registered: bool = False
    auto_cage_preview_build_generation: int = 0
    distance_average_normals_preview_cache: object | None = None
    distance_average_normals_preview_pending_request: object | None = None
    distance_average_normals_preview_build_result_queue: object = field(default_factory=queue.Queue)
    distance_average_normals_preview_build_thread: object | None = None
    distance_average_normals_preview_build_active_key: tuple | None = None
    distance_average_normals_preview_build_timer_registered: bool = False
    distance_average_normals_preview_build_generation: int = 0
    interaction_until: float = 0.0
    interaction_redraw_due_at: float = 0.0
    interaction_redraw_timer_registered: bool = False
    post_load_overlay_grace_until: float = 0.0
    preview_visibility_sync_timer_registered: bool = False
    preview_visibility_sync_scene: object | None = None
    screen_heatmap_image: object | None = None
    screen_heatmap_texture: object | None = None
    screen_heatmap_texture_image_pointer: int = 0
    screen_heatmap_result: object | None = None
    screen_heatmap_result_key: tuple | None = None
    last_view_refresh_key: tuple | None = None
    last_view_refresh_signature: str = ""
    last_view_refresh_at: float = 0.0


LEGACY_RUNTIME_FIELD_MAP: dict[str, str] = {
    "_DRAW_HANDLER": "draw_handler",
    "_DRAW_PIXEL_HANDLER": "draw_pixel_handler",
    "_AUTO_CAGE_PREVIEW_CACHE": "auto_cage_preview_cache",
    "_AUTO_CAGE_PREVIEW_PENDING_REQUEST": "auto_cage_preview_pending_request",
    "_AUTO_CAGE_PREVIEW_BUILD_RESULT_QUEUE": "auto_cage_preview_build_result_queue",
    "_AUTO_CAGE_PREVIEW_BUILD_THREAD": "auto_cage_preview_build_thread",
    "_AUTO_CAGE_PREVIEW_BUILD_ACTIVE_KEY": "auto_cage_preview_build_active_key",
    "_AUTO_CAGE_PREVIEW_BUILD_TIMER_REGISTERED": "auto_cage_preview_build_timer_registered",
    "_AUTO_CAGE_PREVIEW_BUILD_GENERATION": "auto_cage_preview_build_generation",
    "_DISTANCE_AVERAGE_NORMALS_PREVIEW_CACHE": "distance_average_normals_preview_cache",
    "_DISTANCE_AVERAGE_NORMALS_PREVIEW_PENDING_REQUEST": "distance_average_normals_preview_pending_request",
    "_DISTANCE_AVERAGE_NORMALS_PREVIEW_BUILD_RESULT_QUEUE": "distance_average_normals_preview_build_result_queue",
    "_DISTANCE_AVERAGE_NORMALS_PREVIEW_BUILD_THREAD": "distance_average_normals_preview_build_thread",
    "_DISTANCE_AVERAGE_NORMALS_PREVIEW_BUILD_ACTIVE_KEY": "distance_average_normals_preview_build_active_key",
    "_DISTANCE_AVERAGE_NORMALS_PREVIEW_BUILD_TIMER_REGISTERED": "distance_average_normals_preview_build_timer_registered",
    "_DISTANCE_AVERAGE_NORMALS_PREVIEW_BUILD_GENERATION": "distance_average_normals_preview_build_generation",
    "_INTERACTION_UNTIL": "interaction_until",
    "_INTERACTION_REDRAW_DUE_AT": "interaction_redraw_due_at",
    "_INTERACTION_REDRAW_TIMER_REGISTERED": "interaction_redraw_timer_registered",
    "_POST_LOAD_OVERLAY_GRACE_UNTIL": "post_load_overlay_grace_until",
    "_PREVIEW_VISIBILITY_SYNC_TIMER_REGISTERED": "preview_visibility_sync_timer_registered",
    "_PREVIEW_VISIBILITY_SYNC_SCENE": "preview_visibility_sync_scene",
    "_SCREEN_HEATMAP_IMAGE": "screen_heatmap_image",
    "_SCREEN_HEATMAP_TEXTURE": "screen_heatmap_texture",
    "_SCREEN_HEATMAP_TEXTURE_IMAGE_POINTER": "screen_heatmap_texture_image_pointer",
    "_SCREEN_HEATMAP_RESULT": "screen_heatmap_result",
    "_SCREEN_HEATMAP_RESULT_KEY": "screen_heatmap_result_key",
    "_LAST_VIEW_REFRESH_KEY": "last_view_refresh_key",
    "_LAST_VIEW_REFRESH_SIGNATURE": "last_view_refresh_signature",
    "_LAST_VIEW_REFRESH_AT": "last_view_refresh_at",
}


def legacy_runtime_state_get(legacy_state: OverlayLegacyRuntimeState, name: str):
    return getattr(legacy_state, LEGACY_RUNTIME_FIELD_MAP[name])


def legacy_runtime_state_set(legacy_state: OverlayLegacyRuntimeState, name: str, value) -> None:
    setattr(legacy_state, LEGACY_RUNTIME_FIELD_MAP[name], value)


def preview_build_runtime_state_from_legacy_state(legacy_state: OverlayLegacyRuntimeState) -> OverlayPreviewBuildRuntimeState:
    return OverlayPreviewBuildRuntimeState(
        auto_cage_preview_cache=legacy_state.auto_cage_preview_cache,
        auto_cage_preview_pending_request=legacy_state.auto_cage_preview_pending_request,
        auto_cage_preview_build_result_queue=legacy_state.auto_cage_preview_build_result_queue,
        auto_cage_preview_build_thread=legacy_state.auto_cage_preview_build_thread,
        auto_cage_preview_build_active_key=legacy_state.auto_cage_preview_build_active_key,
        auto_cage_preview_build_timer_registered=legacy_state.auto_cage_preview_build_timer_registered,
        auto_cage_preview_build_generation=legacy_state.auto_cage_preview_build_generation,
        distance_average_normals_preview_cache=legacy_state.distance_average_normals_preview_cache,
        distance_average_normals_preview_pending_request=legacy_state.distance_average_normals_preview_pending_request,
        distance_average_normals_preview_build_result_queue=legacy_state.distance_average_normals_preview_build_result_queue,
        distance_average_normals_preview_build_thread=legacy_state.distance_average_normals_preview_build_thread,
        distance_average_normals_preview_build_active_key=legacy_state.distance_average_normals_preview_build_active_key,
        distance_average_normals_preview_build_timer_registered=legacy_state.distance_average_normals_preview_build_timer_registered,
        distance_average_normals_preview_build_generation=legacy_state.distance_average_normals_preview_build_generation,
    )


def sync_preview_build_runtime_legacy_state(legacy_state: OverlayLegacyRuntimeState, state: OverlayPreviewBuildRuntimeState) -> None:
    legacy_state.auto_cage_preview_cache = state.auto_cage_preview_cache
    legacy_state.auto_cage_preview_pending_request = state.auto_cage_preview_pending_request
    legacy_state.auto_cage_preview_build_result_queue = state.auto_cage_preview_build_result_queue
    legacy_state.auto_cage_preview_build_thread = state.auto_cage_preview_build_thread
    legacy_state.auto_cage_preview_build_active_key = state.auto_cage_preview_build_active_key
    legacy_state.auto_cage_preview_build_timer_registered = state.auto_cage_preview_build_timer_registered
    legacy_state.auto_cage_preview_build_generation = state.auto_cage_preview_build_generation
    legacy_state.distance_average_normals_preview_cache = state.distance_average_normals_preview_cache
    legacy_state.distance_average_normals_preview_pending_request = state.distance_average_normals_preview_pending_request
    legacy_state.distance_average_normals_preview_build_result_queue = state.distance_average_normals_preview_build_result_queue
    legacy_state.distance_average_normals_preview_build_thread = state.distance_average_normals_preview_build_thread
    legacy_state.distance_average_normals_preview_build_active_key = state.distance_average_normals_preview_build_active_key
    legacy_state.distance_average_normals_preview_build_timer_registered = state.distance_average_normals_preview_build_timer_registered
    legacy_state.distance_average_normals_preview_build_generation = state.distance_average_normals_preview_build_generation


def preview_visibility_sync_state_from_legacy_state(legacy_state: OverlayLegacyRuntimeState) -> PreviewVisibilitySyncState:
    return PreviewVisibilitySyncState(
        timer_registered=legacy_state.preview_visibility_sync_timer_registered,
        scene=legacy_state.preview_visibility_sync_scene,
    )


def sync_preview_visibility_sync_legacy_state(legacy_state: OverlayLegacyRuntimeState, state: PreviewVisibilitySyncState) -> None:
    legacy_state.preview_visibility_sync_timer_registered = state.timer_registered
    legacy_state.preview_visibility_sync_scene = state.scene


def overlay_registration_state_from_legacy_state(legacy_state: OverlayLegacyRuntimeState) -> OverlayRegistrationState:
    return OverlayRegistrationState(
        draw_handler=legacy_state.draw_handler,
        draw_pixel_handler=legacy_state.draw_pixel_handler,
        screen_heatmap_image=legacy_state.screen_heatmap_image,
        screen_heatmap_texture=legacy_state.screen_heatmap_texture,
        screen_heatmap_texture_image_pointer=legacy_state.screen_heatmap_texture_image_pointer,
        screen_heatmap_result=legacy_state.screen_heatmap_result,
        screen_heatmap_result_key=legacy_state.screen_heatmap_result_key,
        last_view_refresh_key=legacy_state.last_view_refresh_key,
        last_view_refresh_signature=legacy_state.last_view_refresh_signature,
        last_view_refresh_at=legacy_state.last_view_refresh_at,
        post_load_overlay_grace_until=legacy_state.post_load_overlay_grace_until,
        interaction_redraw_due_at=legacy_state.interaction_redraw_due_at,
        interaction_redraw_timer_registered=legacy_state.interaction_redraw_timer_registered,
    )


def sync_overlay_registration_legacy_state(legacy_state: OverlayLegacyRuntimeState, state: OverlayRegistrationState) -> None:
    legacy_state.draw_handler = state.draw_handler
    legacy_state.draw_pixel_handler = state.draw_pixel_handler
    legacy_state.screen_heatmap_image = state.screen_heatmap_image
    legacy_state.screen_heatmap_texture = state.screen_heatmap_texture
    legacy_state.screen_heatmap_texture_image_pointer = state.screen_heatmap_texture_image_pointer
    legacy_state.screen_heatmap_result = state.screen_heatmap_result
    legacy_state.screen_heatmap_result_key = state.screen_heatmap_result_key
    legacy_state.last_view_refresh_key = state.last_view_refresh_key
    legacy_state.last_view_refresh_signature = state.last_view_refresh_signature
    legacy_state.last_view_refresh_at = state.last_view_refresh_at
    legacy_state.post_load_overlay_grace_until = state.post_load_overlay_grace_until
    legacy_state.interaction_redraw_due_at = state.interaction_redraw_due_at
    legacy_state.interaction_redraw_timer_registered = state.interaction_redraw_timer_registered


def interaction_active(*, legacy_state: OverlayLegacyRuntimeState, now_fn: Callable[[], float]) -> bool:
    return now_fn() < legacy_state.interaction_until


def post_load_overlay_grace_active(*, legacy_state: OverlayLegacyRuntimeState, now_fn: Callable[[], float]) -> bool:
    return now_fn() < legacy_state.post_load_overlay_grace_until


def post_load_overlay_grace_delay(
    *,
    legacy_state: OverlayLegacyRuntimeState,
    now_fn: Callable[[], float],
    minimum_delay: float = 0.05,
) -> float:
    return max(minimum_delay, legacy_state.post_load_overlay_grace_until - now_fn())


def mark_interaction(
    *,
    legacy_state: OverlayLegacyRuntimeState,
    duration: float,
    now_fn: Callable[[], float],
    debug_refresh_delay_seconds: float,
) -> float:
    delay = max(debug_refresh_delay_seconds * 2.0, float(duration))
    legacy_state.interaction_until = max(legacy_state.interaction_until, now_fn() + delay)
    return delay + debug_refresh_delay_seconds
