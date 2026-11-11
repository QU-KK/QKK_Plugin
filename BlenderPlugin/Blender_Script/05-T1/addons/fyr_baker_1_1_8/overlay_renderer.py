from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
import traceback

import bpy
import gpu

from . import properties
from .overlay_keys import overlay_settings_state as _overlay_settings_state
from .overlay_cache import OverlayPass


@dataclass(slots=True)
class OverlayRendererDeps:
    preview_suppressed_for_context: Callable[[object], bool]
    resolve_project_group: Callable[[object], tuple]
    get_overlay_cache: Callable[[object, object, object, object], object]
    overlay_theme_for_settings: Callable[[object], object]
    get_shader: Callable[[], object]
    render_low_depth_mask: Callable[..., object]
    render_cage_depth_mask: Callable[..., object]
    line_render_enabled: Callable[[object, float], bool]
    get_heatmap_mask_shader: Callable[[], object]
    log_mask_error: Callable[[str], None]
    heatmap_low_depth_epsilon_min: float
    ensure_cage_check_debug_result: Callable[..., bool]
    draw_cage_check_overlay: Callable[..., bool]


def paint_offset_active(context, group) -> bool:
    active_object = getattr(context, "active_object", None)
    if active_object is None or str(getattr(active_object, "mode", "") or "") != "TEXTURE_PAINT":
        return False
    scene = getattr(context, "scene", None)
    image_paint = getattr(getattr(scene, "tool_settings", None), "image_paint", None)
    canvas = getattr(image_paint, "canvas", None)
    if canvas is None:
        return False
    paint_state = properties.group_paint_projection_settings_state(group)
    return canvas is getattr(paint_state, "paint_offset_image", None)


def _offset_brush_group_names() -> frozenset:
    """Names of the bake groups the offset brush is painting (empty when none)."""
    try:
        from . import paint_brush

        return paint_brush.session_group_names(paint_brush.KIND_OFFSET)
    except Exception:
        return frozenset()


def _live_offset_coverage_pass(context, group):
    """The offset brush's live cage as a coverage depth pass, or None."""
    try:
        from . import paint_brush

        batch = paint_brush.live_coverage_cage_batch(context, group)
    except Exception:
        return None
    if batch is None:
        return None
    return SimpleNamespace(fill_batch=batch, shader_mode="")


def cage_depth_bias_clip_cap(context, group) -> float:
    """Ceiling for the cage/paint clip-z bias, as a WORLD distance folded with the
    projection scale the vertex shader needs (see overlay_gpu._CAGE_DEPTH_BIAS_GLSL).

    Capping in world units is what keeps the bias from turning into "always on top":
    it may only pull the overlay a fraction of the cage offset toward the viewer, so
    a cage face that is genuinely behind the mesh stays behind it at any zoom. The
    1mm floor keeps the coincident-surface fix alive for a zero-offset cage, which is
    exactly the case that z-fights.
    """
    try:
        offset = max(0.0, float(getattr(group, "cage_offset", 0.0) or 0.0))
    except Exception:
        offset = 0.0
    world_cap = max(1.0e-3, offset * 0.35)
    proj_scale = 0.0
    region_data = getattr(context, "region_data", None)
    window_matrix = getattr(region_data, "window_matrix", None)
    if window_matrix is not None:
        try:
            if bool(getattr(region_data, "is_perspective", True)):
                proj_scale = abs(float(window_matrix[2][3]))
            else:
                proj_scale = abs(float(window_matrix[2][2]))
        except Exception:
            proj_scale = 0.0
    if proj_scale <= 0.0:
        # No projection available (headless/tests): a scale of 1 leaves the cap above
        # the proportional term at working distances, i.e. the uncapped behaviour.
        proj_scale = 1.0
    return world_cap * proj_scale


def draw_batch(shader, batch, color, line_width=None):
    if batch is None:
        return
    if line_width is not None and hasattr(gpu.state, "line_width_set"):
        gpu.state.line_width_set(line_width)
    shader.uniform_float("color", color)
    batch.draw(shader)


def skew_screen_size_uniforms(projection_matrix, viewport_size, enabled: bool) -> tuple[bool, float, bool]:
    """(enabled, world units per pixel at unit depth, is perspective) for the skew shader.

    Blender's projection matrix has P[1][1] = 2 / visible height (orthographic) or
    2 * near / frustum height (perspective); dividing 2 / P[1][1] by the viewport
    height in pixels gives the world size of one pixel at unit view depth, which
    the shader multiplies by the needle base's depth under perspective.
    """
    if not enabled or projection_matrix is None or viewport_size is None:
        return False, 0.0, True
    try:
        scale_y = float(projection_matrix[1][1])
        is_perspective = abs(float(projection_matrix[3][3])) < 1.0e-9
        height = float(viewport_size[1])
    except Exception:
        return False, 0.0, True
    if abs(scale_y) <= 1.0e-12 or height <= 0.0:
        return False, 0.0, is_perspective
    return True, 2.0 / (abs(scale_y) * height), is_perspective


def draw_triangle_pass(
    shader,
    draw_pass: OverlayPass,
    *,
    deps: OverlayRendererDeps,
    model_view_projection_matrix=None,
    model_view_matrix=None,
    offset_override=None,
    heatmap_low_depth_texture=None,
    heatmap_viewport_origin=None,
    heatmap_low_depth_texture_size=None,
    heatmap_viewport_size=None,
    heatmap_low_depth_epsilon=None,
    depth_bias_clip_cap: float = 0.0,
    skew_needle_scale: float = 1.0,
    skew_constant_screen_size: bool = False,
    skew_pixel_to_world: float = 0.0,
    skew_is_perspective: bool = True,
):
    if draw_pass.depth_test_mode is not None and hasattr(gpu.state, "depth_test_set"):
        gpu.state.depth_test_set(draw_pass.depth_test_mode)
    if hasattr(gpu.state, "depth_mask_set"):
        gpu.state.depth_mask_set(bool(draw_pass.depth_write))
    if draw_pass.face_culling_mode is not None and hasattr(gpu.state, "face_culling_set"):
        gpu.state.face_culling_set(draw_pass.face_culling_mode)
    if draw_pass.blend_mode is not None and hasattr(gpu.state, "blend_set"):
        gpu.state.blend_set(draw_pass.blend_mode)
    color_mask_supported = hasattr(gpu.state, "color_mask_set")
    if color_mask_supported and not bool(getattr(draw_pass, "color_write", True)):
        gpu.state.color_mask_set(False, False, False, False)
    if draw_pass.shader is not None:
        draw_shader = draw_pass.shader
        masked_heatmap = False
        if (
            draw_pass.kind == "heatmap"
            and heatmap_low_depth_texture is not None
            and heatmap_viewport_origin is not None
            and heatmap_low_depth_texture_size is not None
            and heatmap_viewport_size is not None
            and model_view_matrix is not None
        ):
            try:
                draw_shader = deps.get_heatmap_mask_shader()
                masked_heatmap = True
            except Exception:
                deps.log_mask_error(traceback.format_exc())
                draw_shader = draw_pass.shader
        draw_shader.bind()
        if masked_heatmap:
            draw_shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
            draw_shader.uniform_float("ModelViewMatrix", model_view_matrix)
            draw_shader.uniform_float("viewportOrigin", heatmap_viewport_origin)
            draw_shader.uniform_float("viewportSize", heatmap_viewport_size)
            draw_shader.uniform_float("lowDepthTextureSize", heatmap_low_depth_texture_size)
            draw_shader.uniform_float(
                "lowDepthEpsilon",
                float(
                    deps.heatmap_low_depth_epsilon_min
                    if heatmap_low_depth_epsilon is None
                    else heatmap_low_depth_epsilon
                ),
            )
            if hasattr(draw_shader, "uniform_sampler"):
                draw_shader.uniform_sampler("lowDepthTexture", heatmap_low_depth_texture)
        elif model_view_projection_matrix is not None:
            draw_shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
        if draw_pass.shader_mode in ("offset", "offset_lit", "offset_paint"):
            # Breaks the depth tie against the mesh these passes hug, bounded in world
            # units so genuinely occluded faces stay occluded.
            draw_shader.uniform_float("depthBiasClipCap", float(depth_bias_clip_cap))
        if draw_pass.shader_mode == "offset":
            offset_value = float(draw_pass.offset if offset_override is None else offset_override)
            draw_shader.uniform_float("offset", offset_value)
        elif draw_pass.shader_mode == "offset_lit":
            offset_value = float(draw_pass.offset if offset_override is None else offset_override)
            draw_shader.uniform_float("offset", offset_value)
        elif draw_pass.shader_mode == "offset_paint":
            offset_scale_value = float(draw_pass.offset if offset_override is None else offset_override)
            offset_scale_value *= float(getattr(draw_pass, "paint_offset_scale", 1.0))
            draw_shader.uniform_float("offset_scale", offset_scale_value)
            draw_shader.uniform_float(
                "show_paint_mask",
                1.0 if bool(getattr(draw_pass, "show_paint_mask", False)) else 0.0,
            )
            if draw_pass.paint_texture is not None and hasattr(draw_shader, "uniform_sampler"):
                draw_shader.uniform_sampler("paintOffsetTexture", draw_pass.paint_texture)
        elif draw_pass.shader_mode == "skew_color":
            # Needle length is a push constant read from the live slider, so the
            # field is never regenerated for a length change (see get_skew_shader).
            draw_shader.uniform_float("needleScale", float(skew_needle_scale))
            if model_view_matrix is not None:
                # Orientation shading happens in view space (see get_skew_shader).
                draw_shader.uniform_float("ModelViewMatrix", model_view_matrix)
            constant = bool(skew_constant_screen_size) and float(skew_pixel_to_world) > 0.0
            draw_shader.uniform_float("constantScreenSize", 1.0 if constant else 0.0)
            draw_shader.uniform_float("pixelToWorld", float(skew_pixel_to_world) if constant else 0.0)
            draw_shader.uniform_float("isPersp", 1.0 if skew_is_perspective else 0.0)
            if draw_pass.line_width > 0.0 and hasattr(gpu.state, "line_width_set"):
                gpu.state.line_width_set(float(draw_pass.line_width))
            if draw_pass.fill_batch is not None:
                draw_pass.fill_batch.draw(draw_shader)
            shader.bind()
            if hasattr(gpu.state, "depth_mask_set"):
                gpu.state.depth_mask_set(False)
            if draw_pass.depth_test_mode is not None and hasattr(gpu.state, "depth_test_set"):
                gpu.state.depth_test_set("LESS_EQUAL")
            if draw_pass.blend_mode is not None and hasattr(gpu.state, "blend_set"):
                gpu.state.blend_set("ALPHA")
            return
        elif draw_pass.shader_mode == "vertex_color":
            if draw_pass.fill_batch is not None:
                draw_pass.fill_batch.draw(draw_shader)
            if deps.line_render_enabled(draw_pass.line_color, draw_pass.line_width):
                draw_batch(shader, draw_pass.line_batch, draw_pass.line_color, line_width=draw_pass.line_width)
            shader.bind()
            if hasattr(gpu.state, "depth_mask_set"):
                gpu.state.depth_mask_set(False)
            if color_mask_supported and not bool(getattr(draw_pass, "color_write", True)):
                gpu.state.color_mask_set(True, True, True, True)
            if draw_pass.face_culling_mode is not None and hasattr(gpu.state, "face_culling_set"):
                gpu.state.face_culling_set("NONE")
            if draw_pass.depth_test_mode is not None and hasattr(gpu.state, "depth_test_set"):
                gpu.state.depth_test_set("LESS_EQUAL")
            if draw_pass.blend_mode is not None and hasattr(gpu.state, "blend_set"):
                gpu.state.blend_set("ALPHA")
            return
        draw_batch(draw_shader, draw_pass.fill_batch, draw_pass.fill_color)
        if deps.line_render_enabled(draw_pass.line_color, draw_pass.line_width):
            draw_batch(draw_shader, draw_pass.line_batch, draw_pass.line_color, line_width=draw_pass.line_width)
        shader.bind()
    else:
        draw_batch(shader, draw_pass.fill_batch, draw_pass.fill_color)
        if deps.line_render_enabled(draw_pass.line_color, draw_pass.line_width):
            draw_batch(shader, draw_pass.line_batch, draw_pass.line_color, line_width=draw_pass.line_width)
    if hasattr(gpu.state, "depth_mask_set"):
        gpu.state.depth_mask_set(False)
    if color_mask_supported and not bool(getattr(draw_pass, "color_write", True)):
        gpu.state.color_mask_set(True, True, True, True)
    if draw_pass.face_culling_mode is not None and hasattr(gpu.state, "face_culling_set"):
        gpu.state.face_culling_set("NONE")
    if draw_pass.depth_test_mode is not None and hasattr(gpu.state, "depth_test_set"):
        gpu.state.depth_test_set("LESS_EQUAL")
    if draw_pass.blend_mode is not None and hasattr(gpu.state, "blend_set"):
        gpu.state.blend_set("ALPHA")


def coverage_cage_check_status(coverage_group, active_group, active_status):
    """Full cage-check status for the active group, a minimal one for every other.

    Only the active group's status carries ``distance_degenerate_offset``, which is
    what makes a Distance cage with a ~zero offset draw its solid red warning.

    Matching must use ``==``, not ``is``: RNA hands out a fresh wrapper for every
    CollectionProperty access, so even ``groups[0] is groups[0]`` is False and the
    active group silently fell through to the minimal status, which killed the
    warning for every group. ``==`` compares the underlying RNA pointer, and unlike
    matching on ``.name`` it stays False for a same-named group in another project.
    """
    if active_group is not None and coverage_group == active_group:
        return active_status
    return {"show_cage_check": True}


def draw_group_overlay(*, last_draw_error: str, deps: OverlayRendererDeps) -> str:
    context = bpy.context
    if context is None or context.scene is None:
        return last_draw_error

    settings = getattr(context.scene, "fyr_baker_settings", None)
    overlay_state = _overlay_settings_state(settings) if settings is not None else None
    if settings is None or overlay_state is None:
        return last_draw_error
    cage_visible = bool(overlay_state.show_cage_overlay)
    # Skew needles are their own overlay: they draw with the cage hidden too, in which
    # case every cage pass (fill, wireframe, coverage, paint mask) is skipped and only
    # the needle passes reach the GPU.
    needles_only = not cage_visible
    if needles_only and not bool(getattr(overlay_state, "show_skew_debug", False)):
        return last_draw_error
    if deps.preview_suppressed_for_context(context):
        return last_draw_error

    _settings, project, group = deps.resolve_project_group(context.scene)
    if project is None or group is None:
        return last_draw_error

    try:
        cache = deps.get_overlay_cache(context, settings, project, group)
        theme = deps.overlay_theme_for_settings(settings)
        shader = deps.get_shader()
        gpu.state.blend_set("ALPHA")
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("LESS_EQUAL")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)
        shader.bind()
        projection_matrix = gpu.matrix.get_projection_matrix()
        model_view_matrix = gpu.matrix.get_model_view_matrix()
        model_view_projection_matrix = projection_matrix @ model_view_matrix
        # Depends on the live view matrix, so it is resolved per draw rather than
        # cached with the passes: a zoom changes it.
        depth_bias_clip_cap = cage_depth_bias_clip_cap(context, group)
        skew_needle_scale = float(getattr(overlay_state, "skew_debug_length", 1.0) or 0.0)
        heatmap_low_depth_texture = None
        cage_check_low_depth_resources = None
        cage_check_cage_depth_resources = None
        heatmap_viewport_origin = None
        heatmap_low_depth_texture_size = None
        heatmap_viewport_size = None
        cage_check_cache_status = {
            "show_cage_check": bool(getattr(overlay_state, "show_error_heatmap", False)),
            "distance_mode": getattr(group, "cage_mode", "") == "DISTANCE",
            "low_depth_batch_count": len(getattr(cache, "low_depth_batches", []) or []),
            "cage_depth_batch_count": len(getattr(cache, "cage_depth_batches", []) or []),
            "viewport_size_available": False,
            "low_depth_rendered": False,
            "cage_depth_rendered_count": 0,
        }
        viewport = gpu.state.viewport_get() if hasattr(gpu.state, "viewport_get") else None
        viewport_origin = (0.0, 0.0)
        viewport_size = None
        if viewport is not None and len(viewport) >= 4:
            viewport_origin = (
                float(viewport[0]),
                float(viewport[1]),
            )
            viewport_size = (
                float(max(1, int(viewport[2]) or 1)),
                float(max(1, int(viewport[3]) or 1)),
            )
        region = getattr(context, "region", None)
        if viewport_size is None and region is not None:
            viewport_origin = (
                float(getattr(region, "x", 0) or 0),
                float(getattr(region, "y", 0) or 0),
            )
            viewport_size = (
                float(max(1, int(getattr(region, "width", 1) or 1))),
                float(max(1, int(getattr(region, "height", 1) or 1))),
            )
        cage_check_cache_status["viewport_size_available"] = viewport_size is not None
        skew_constant_screen_size, skew_pixel_to_world, skew_is_perspective = skew_screen_size_uniforms(
            projection_matrix,
            viewport_size,
            bool(getattr(overlay_state, "skew_debug_constant_screen_size", False)),
        )
        if (
            bool(getattr(overlay_state, "show_error_heatmap", False))
            and getattr(group, "cage_mode", "") != "DISTANCE"
            and cache.low_depth_batches
            and viewport_size is not None
        ):
            low_depth_resources = deps.render_low_depth_mask(
                cache.low_depth_batches,
                int(viewport_size[0]),
                int(viewport_size[1]),
                model_view_projection_matrix=model_view_projection_matrix,
                model_view_matrix=model_view_matrix,
            )
            if low_depth_resources is not None:
                heatmap_low_depth_texture = low_depth_resources.color_texture
                heatmap_viewport_origin = viewport_origin
                heatmap_low_depth_texture_size = (
                    float(max(1, int(getattr(low_depth_resources, "width", 1) or 1))),
                    float(max(1, int(getattr(low_depth_resources, "height", 1) or 1))),
                )
                heatmap_viewport_size = viewport_size
        if (
            bool(getattr(overlay_state, "show_error_heatmap", False))
            and getattr(group, "cage_mode", "") == "DISTANCE"
            and cache.cage_depth_batches
        ):
            cage_batches_by_offset: dict[float, list[object]] = {}
            group_offset = float(getattr(group, "cage_offset", 0.0) or 0.0)
            for cage_batch, slot_delta in cache.cage_depth_batches:
                cage_batches_by_offset.setdefault(max(0.0, group_offset + float(slot_delta)), []).append(cage_batch)
            max_cage_offset = max(cage_batches_by_offset.keys(), default=0.0)
            cage_check_cache_status["distance_cage_max_offset"] = float(max_cage_offset)
            cage_check_cache_status["distance_degenerate_offset"] = max_cage_offset <= 1.0e-7
            cage_check_cache_status["distance_cage_check_path"] = "screen_mask"
        # Coverage is per-group: draw it for every group whose show_cage_coverage flag is on
        # (gated by the global show_error_heatmap master), independent of the active selection,
        # so selecting a different group no longer moves the overlay.
        coverage_groups = []
        if cage_visible and bool(getattr(overlay_state, "show_error_heatmap", False)):
            for coverage_group in getattr(project, "groups", []):
                if bool(getattr(coverage_group, "show_cage_coverage", False)):
                    coverage_groups.append(coverage_group)
        # While the offset brush paints a group it draws that group's live cage itself;
        # the static cage still holds the values from before the session, so its
        # coverage is judged against the brush's live cage instead (draw_cage_check_once).
        offset_brush_groups = _offset_brush_group_names()
        offset_brush_live = bool(offset_brush_groups)
        active_group_name = str(getattr(group, "name", "") or "")
        show_cage_check = bool(coverage_groups)
        cage_check_drawn = False
        coverage_beneath_cage_fill = paint_offset_active(context, group)

        def draw_cage_check_once() -> None:
            nonlocal cage_check_drawn
            if cage_check_drawn or not show_cage_check:
                return
            for coverage_group in coverage_groups:
                pass_offsets = []
                coverage_passes = getattr(cache, "coverage_cage_passes", {}) or {}
                live_pass = _live_offset_coverage_pass(context, coverage_group)
                if live_pass is not None:
                    # Already in world space at the painted offsets.
                    pass_offsets.append((live_pass, 0.0))
                    coverage_passes = {}
                for cage_pass in coverage_passes.get(str(getattr(coverage_group, "name", "") or ""), ()):
                    resolved_offset = float(getattr(cage_pass, "offset", 0.0) or 0.0)
                    if bool(getattr(cage_pass, "uses_group_offset", False)):
                        offset_owner = coverage_group
                        owner_name = str(getattr(cage_pass, "offset_group_name", "") or "")
                        if owner_name:
                            resolved = getattr(project, "groups", {}).get(owner_name)
                            if resolved is not None:
                                offset_owner = resolved
                        resolved_offset += max(0.0, float(getattr(offset_owner, "cage_offset", 0.0) or 0.0))
                    pass_offsets.append((cage_pass, max(0.0, resolved_offset)))
                coverage_depth_resources = None
                if pass_offsets and viewport_size is not None:
                    coverage_depth_resources = deps.render_cage_depth_mask(
                        pass_offsets,
                        int(viewport_size[0]),
                        int(viewport_size[1]),
                        model_view_projection_matrix=model_view_projection_matrix,
                        model_view_matrix=model_view_matrix,
                    )
                # The active group carries the full cache status; other groups only
                # need the mask status assembled above. No backend SDF request or
                # high-vertex classifier is needed.
                coverage_status = coverage_cage_check_status(
                    coverage_group, group, cage_check_cache_status
                )
                coverage_status = dict(coverage_status)
                coverage_status["screen_cage_pass_count"] = len(pass_offsets)
                coverage_status["screen_cage_mask_rendered"] = coverage_depth_resources is not None
                deps.draw_cage_check_overlay(
                    context,
                    settings,
                    project,
                    coverage_group,
                    theme,
                    model_view_projection_matrix,
                    viewport_origin=viewport_origin,
                    viewport_size=viewport_size,
                    low_depth_resources=cage_check_low_depth_resources,
                    cage_depth_resources=coverage_depth_resources,
                    low_depth_epsilon=cache.low_depth_epsilon,
                    shell_cache_status=coverage_status,
                    depth_write=True,
                )
            cage_check_drawn = True
            if hasattr(gpu.state, "depth_mask_set"):
                gpu.state.depth_mask_set(False)
            if hasattr(gpu.state, "blend_set"):
                gpu.state.blend_set("ALPHA")
            shader.bind()

        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("ALPHA")
        for draw_pass in cache.passes:
            if needles_only and draw_pass.shader_mode != "skew_color":
                continue
            pass_kind = str(getattr(draw_pass, "kind", "") or "")
            # Normally coverage sits above the translucent cage fill so green
            # cannot contaminate its red/blue classification. During Paint
            # Offset the cage itself is the thing being judged, so compose the
            # coverage first and let the adjustable cage fill remain visible.
            # The brush's live cage draws in its own handler after this one, so
            # it lands above the coverage the same way.
            draw_before_kind = "cage_fill" if (coverage_beneath_cage_fill or offset_brush_live) else "cage_line"
            if show_cage_check and not cage_check_drawn and pass_kind == draw_before_kind:
                draw_cage_check_once()
            # The brush draws the painted groups' live cages itself; only their static
            # cages (still at the pre-session offsets) step aside. Every other group's
            # cage stays on screen.
            if (
                offset_brush_live
                and (pass_kind in ("cage_fill", "cage_line") or draw_pass.shader_mode == "offset_paint")
                and (str(getattr(draw_pass, "cage_group_name", "") or "") or active_group_name) in offset_brush_groups
            ):
                continue
            offset_override = None
            if draw_pass.shader is not None and draw_pass.uses_group_offset:
                # Re-resolve by name against the live project every draw. The pass
                # caches only a string, so a project/group added since the cache was
                # built cannot leave us dereferencing freed RNA here.
                offset_owner = group
                owner_name = str(getattr(draw_pass, "offset_group_name", "") or "")
                if owner_name:
                    resolved = getattr(project, "groups", {}).get(owner_name)
                    if resolved is not None:
                        offset_owner = resolved
                offset_override = max(0.0, float(getattr(offset_owner, "cage_offset", 0.0)) + float(draw_pass.offset))
            draw_triangle_pass(
                shader,
                draw_pass,
                deps=deps,
                depth_bias_clip_cap=depth_bias_clip_cap,
                skew_needle_scale=skew_needle_scale,
                skew_constant_screen_size=skew_constant_screen_size,
                skew_pixel_to_world=skew_pixel_to_world,
                skew_is_perspective=skew_is_perspective,
                model_view_projection_matrix=model_view_projection_matrix,
                model_view_matrix=model_view_matrix,
                offset_override=offset_override,
                heatmap_low_depth_texture=heatmap_low_depth_texture,
                heatmap_viewport_origin=heatmap_viewport_origin,
                heatmap_low_depth_texture_size=heatmap_low_depth_texture_size,
                heatmap_viewport_size=heatmap_viewport_size,
                heatmap_low_depth_epsilon=cache.low_depth_epsilon,
            )
        draw_cage_check_once()

        if cage_visible and bool(getattr(overlay_state, "show_ray_miss_debug", False)):
            draw_batch(shader, cache.miss_batch, theme.miss_line, line_width=theme.miss_line_width)
        return ""
    except Exception:
        error_text = traceback.format_exc()
        if error_text != last_draw_error:
            print(error_text)
        return error_text
    finally:
        if hasattr(gpu.state, "line_width_set"):
            gpu.state.line_width_set(1.0)
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(True)
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("NONE")
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("NONE")
