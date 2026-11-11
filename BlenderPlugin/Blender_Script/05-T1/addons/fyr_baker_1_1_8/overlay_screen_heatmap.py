from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .overlay_events import OverlayRegistrationState


def use_screen_heatmap_overlay(
    context,
    debug_result,
    *,
    screen_heatmap_draw_supported_fn: Callable[[], bool],
) -> bool:
    if debug_result is None:
        return False
    if not screen_heatmap_draw_supported_fn():
        return False
    return False


def screen_heatmap_draw_supported(*, draw_texture_2d_fn, gpu_module) -> bool:
    gpu_texture = getattr(gpu_module, "texture", None)
    return bool(
        draw_texture_2d_fn is not None
        and gpu_texture is not None
        and hasattr(gpu_texture, "from_image")
    )


def current_debug_view(context, *, build_debug_view_fn: Callable[[object, object], object]):
    region = getattr(context, "region", None)
    region_data = getattr(context, "region_data", None)
    if region is None or region_data is None:
        return None
    return build_debug_view_fn(region, region_data)


def current_view_refresh_key(scene, project, group, context) -> tuple:
    region = getattr(context, "region", None)
    region_data = getattr(context, "region_data", None)
    return (
        scene.as_pointer() if scene is not None and hasattr(scene, "as_pointer") else 0,
        str(getattr(project, "name", "") or ""),
        str(getattr(group, "name", "") or ""),
        id(region),
        id(region_data),
    )


def screen_heatmap_image_for_result(
    state: OverlayRegistrationState,
    *,
    result_key,
    debug_result,
    load_managed_output_image_fn: Callable[[Path], object],
):
    if debug_result is None:
        return None
    image_path = str(getattr(debug_result, "heatmap_image_path", "") or "").strip()
    if not image_path:
        return None
    if (
        state.screen_heatmap_result is debug_result
        and state.screen_heatmap_result_key == result_key
        and state.screen_heatmap_image is not None
    ):
        return state.screen_heatmap_image
    try:
        resolved_path = Path(image_path)
        if not resolved_path.exists():
            return None
        image = load_managed_output_image_fn(resolved_path)
    except Exception:
        return None
    state.screen_heatmap_image = image
    state.screen_heatmap_result = debug_result
    state.screen_heatmap_result_key = result_key
    return image


def image_pointer(image) -> int:
    if image is None:
        return 0
    as_pointer = getattr(image, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(image)


def screen_heatmap_texture_for_image(
    state: OverlayRegistrationState,
    *,
    image,
    texture_from_image_fn: Callable[[object], object],
):
    if image is None:
        return None
    pointer = image_pointer(image)
    if (
        state.screen_heatmap_texture is not None
        and state.screen_heatmap_texture_image_pointer == pointer
    ):
        return state.screen_heatmap_texture
    texture = texture_from_image_fn(image)
    if texture is None:
        return None
    state.screen_heatmap_texture = texture
    state.screen_heatmap_texture_image_pointer = pointer
    return texture


def draw_screen_heatmap_overlay(
    state: OverlayRegistrationState,
    *,
    context,
    image,
    screen_heatmap_draw_supported_fn: Callable[[], bool],
    texture_from_image_fn: Callable[[object], object],
    draw_texture_2d_fn,
    gpu_module,
) -> bool:
    if image is None or not screen_heatmap_draw_supported_fn():
        return False
    region = getattr(context, "region", None)
    if region is None:
        return False
    try:
        texture = screen_heatmap_texture_for_image(
            state,
            image=image,
            texture_from_image_fn=texture_from_image_fn,
        )
        if texture is None:
            return False
        if hasattr(gpu_module.state, "depth_test_set"):
            gpu_module.state.depth_test_set("NONE")
        if hasattr(gpu_module.state, "depth_mask_set"):
            gpu_module.state.depth_mask_set(False)
        gpu_module.state.blend_set("ALPHA")
        draw_texture_2d_fn(
            texture,
            (0, 0),
            int(max(1, getattr(region, "width", 0))),
            int(max(1, getattr(region, "height", 0))),
        )
        return True
    except Exception:
        return False
