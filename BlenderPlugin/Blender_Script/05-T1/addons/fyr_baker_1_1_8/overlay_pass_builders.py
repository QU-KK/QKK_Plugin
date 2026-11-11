from __future__ import annotations

from array import array
from collections.abc import Callable
import math

import gpu
from gpu_extras.batch import batch_for_shader

from .cage import skew_needle_vertex_streams
from .overlay_cache import OverlayPass


def triangle_face_normal_from_positions(position_a, position_b, position_c):
    edge_ab = (
        position_b[0] - position_a[0],
        position_b[1] - position_a[1],
        position_b[2] - position_a[2],
    )
    edge_ac = (
        position_c[0] - position_a[0],
        position_c[1] - position_a[1],
        position_c[2] - position_a[2],
    )
    normal = (
        edge_ab[1] * edge_ac[2] - edge_ab[2] * edge_ac[1],
        edge_ab[2] * edge_ac[0] - edge_ab[0] * edge_ac[2],
        edge_ab[0] * edge_ac[1] - edge_ab[1] * edge_ac[0],
    )
    normal_length = math.sqrt(
        normal[0] * normal[0]
        + normal[1] * normal[1]
        + normal[2] * normal[2]
    )
    if normal_length <= 1.0e-8:
        return (0.0, 0.0, 1.0)
    inv_length = 1.0 / normal_length
    return (
        normal[0] * inv_length,
        normal[1] * inv_length,
        normal[2] * inv_length,
    )


def shaded_color_from_normal_components(normal_x, normal_y, normal_z, fill_color, *, light_direction):
    light_x, light_y, light_z = light_direction
    normal_length_sq = (
        normal_x * normal_x
        + normal_y * normal_y
        + normal_z * normal_z
    )
    if normal_length_sq <= 1.0e-16:
        light_alignment = light_z
    else:
        inv_normal_length = 1.0 / math.sqrt(normal_length_sq)
        light_alignment = (
            normal_x * inv_normal_length * light_x
            + normal_y * inv_normal_length * light_y
            + normal_z * inv_normal_length * light_z
        )
    brightness = 0.28 + 0.72 * abs(light_alignment)
    return (
        float(fill_color[0]) * brightness,
        float(fill_color[1]) * brightness,
        float(fill_color[2]) * brightness,
        float(fill_color[3]),
    )


def build_lit_batch_from_positions(
    positions,
    fill_color,
    *,
    normals=None,
    light_direction,
    get_lit_batch_format_fn: Callable[[], object],
    get_lit_shader_fn: Callable[[], object],
):
    if not positions:
        return None
    flat_positions = positions if isinstance(positions, array) else array("f")
    flat_colors = array("f")
    flat_colors_extend = flat_colors.extend
    use_vertex_normals = bool(normals) and len(normals) == len(positions)
    if use_vertex_normals:
        if isinstance(positions, array):
            vertex_range = range(0, len(positions) - 2, 3)
            for vertex_start in vertex_range:
                shaded_color = shaded_color_from_normal_components(
                    normals[vertex_start],
                    normals[vertex_start + 1],
                    normals[vertex_start + 2],
                    fill_color,
                    light_direction=light_direction,
                )
                flat_colors_extend(shaded_color)
        else:
            flat_positions_extend = flat_positions.extend
            for vertex_index in range(len(positions)):
                px, py, pz = positions[vertex_index]
                nx, ny, nz = normals[vertex_index]
                flat_positions_extend((px, py, pz))
                flat_colors_extend(
                    shaded_color_from_normal_components(
                        nx,
                        ny,
                        nz,
                        fill_color,
                        light_direction=light_direction,
                    )
                )
    elif isinstance(positions, array):
        triangle_range = range(0, len(positions) - 8, 9)
        for triangle_start in triangle_range:
            ax = positions[triangle_start]
            ay = positions[triangle_start + 1]
            az = positions[triangle_start + 2]
            bx = positions[triangle_start + 3]
            by = positions[triangle_start + 4]
            bz = positions[triangle_start + 5]
            cx = positions[triangle_start + 6]
            cy = positions[triangle_start + 7]
            cz = positions[triangle_start + 8]
            edge_ab_x = bx - ax
            edge_ab_y = by - ay
            edge_ab_z = bz - az
            edge_ac_x = cx - ax
            edge_ac_y = cy - ay
            edge_ac_z = cz - az
            shaded_color = shaded_color_from_normal_components(
                edge_ab_y * edge_ac_z - edge_ab_z * edge_ac_y,
                edge_ab_z * edge_ac_x - edge_ab_x * edge_ac_z,
                edge_ab_x * edge_ac_y - edge_ab_y * edge_ac_x,
                fill_color,
                light_direction=light_direction,
            )
            flat_colors_extend(shaded_color)
            flat_colors_extend(shaded_color)
            flat_colors_extend(shaded_color)
    else:
        triangle_range = range(0, len(positions) - 2, 3)
        flat_positions_extend = flat_positions.extend
        for triangle_start in triangle_range:
            ax, ay, az = positions[triangle_start]
            bx, by, bz = positions[triangle_start + 1]
            cx, cy, cz = positions[triangle_start + 2]
            edge_ab_x = bx - ax
            edge_ab_y = by - ay
            edge_ab_z = bz - az
            edge_ac_x = cx - ax
            edge_ac_y = cy - ay
            edge_ac_z = cz - az
            shaded_color = shaded_color_from_normal_components(
                edge_ab_y * edge_ac_z - edge_ab_z * edge_ac_y,
                edge_ab_z * edge_ac_x - edge_ab_x * edge_ac_z,
                edge_ab_x * edge_ac_y - edge_ab_y * edge_ac_x,
                fill_color,
                light_direction=light_direction,
            )
            flat_positions_extend((ax, ay, az, bx, by, bz, cx, cy, cz))
            flat_colors_extend(shaded_color)
            flat_colors_extend(shaded_color)
            flat_colors_extend(shaded_color)
    if not flat_positions:
        return None
    try:
        vertex_count = len(flat_positions) // 3
        vertex_buffer = gpu.types.GPUVertBuf(get_lit_batch_format_fn(), vertex_count)
        # attr_fill wants one item per vertex: flat arrays are rejected, so this used to
        # always drop into the per-vertex tuple fallback below. (N, k) views go straight in.
        vertex_buffer.attr_fill("pos", memoryview(flat_positions).cast("B").cast("f", (vertex_count, 3)))
        vertex_buffer.attr_fill("color", memoryview(flat_colors).cast("B").cast("f", (vertex_count, 4)))
        return gpu.types.GPUBatch(type="TRIS", buf=vertex_buffer)
    except Exception:
        fallback_positions: list[tuple[float, float, float]] = []
        fallback_colors: list[tuple[float, float, float, float]] = []
        for vertex_index in range(0, len(flat_positions), 3):
            fallback_positions.append(
                (
                    float(flat_positions[vertex_index]),
                    float(flat_positions[vertex_index + 1]),
                    float(flat_positions[vertex_index + 2]),
                )
            )
        for color_index in range(0, len(flat_colors), 4):
            fallback_colors.append(
                (
                    float(flat_colors[color_index]),
                    float(flat_colors[color_index + 1]),
                    float(flat_colors[color_index + 2]),
                    float(flat_colors[color_index + 3]),
                )
            )
        return batch_for_shader(
            get_lit_shader_fn(),
            "TRIS",
            {
                "pos": fallback_positions,
                "color": fallback_colors,
            },
        )


def line_render_enabled(line_color, line_width) -> bool:
    return bool(line_width > 0.0 and len(line_color) >= 4 and line_color[3] > 0.0)


def make_overlay_pass(buffers, fill_color, line_color, line_width, *, build_batch_fn: Callable[..., object], face_culling_mode: str | None = None) -> OverlayPass:
    draw_lines = line_render_enabled(line_color, line_width)
    return OverlayPass(
        fill_batch=build_batch_fn("TRIS", buffers.fill_positions),
        line_batch=build_batch_fn("LINES", buffers.line_positions) if draw_lines else None,
        fill_color=fill_color,
        line_color=line_color,
        line_width=line_width,
        face_culling_mode=face_culling_mode,
    )


def make_offset_overlay_pass(
    fill_batch,
    fill_color,
    offset: float,
    *,
    get_offset_shader_fn: Callable[[], object],
    offset_group=None,
) -> OverlayPass:
    return OverlayPass(
        fill_batch=fill_batch,
        line_batch=None,
        fill_color=fill_color,
        line_color=(0.0, 0.0, 0.0, 0.0),
        line_width=0.0,
        shader=get_offset_shader_fn(),
        offset=float(offset),
        uses_group_offset=True,
        shader_mode="offset",
        depth_test_mode="LESS_EQUAL",
        offset_group_name=str(getattr(offset_group, "name", "") or ""),
    )


def make_lit_offset_overlay_pass(
    fill_batch,
    fill_color,
    offset: float,
    *,
    get_lit_offset_shader_fn: Callable[[], object],
    offset_group=None,
) -> OverlayPass:
    return OverlayPass(
        fill_batch=fill_batch,
        line_batch=None,
        fill_color=fill_color,
        line_color=(0.0, 0.0, 0.0, 0.0),
        line_width=0.0,
        shader=get_lit_offset_shader_fn(),
        offset=float(offset),
        uses_group_offset=True,
        shader_mode="offset_lit",
        depth_test_mode="LESS_EQUAL",
        offset_group_name=str(getattr(offset_group, "name", "") or ""),
    )


def make_paint_offset_overlay_pass(
    fill_batch,
    fill_color,
    offset: float,
    *,
    paint_texture,
    get_paint_offset_shader_fn: Callable[[], object],
    line_batch=None,
    line_color=(0.0, 0.0, 0.0, 0.0),
    line_width=0.0,
    offset_group=None,
    uses_group_offset: bool = True,
    paint_offset_scale: float = 1.0,
    show_paint_mask: bool = False,
) -> OverlayPass:
    return OverlayPass(
        fill_batch=fill_batch,
        line_batch=line_batch,
        fill_color=fill_color,
        line_color=line_color,
        line_width=float(line_width),
        shader=get_paint_offset_shader_fn(),
        offset=float(offset),
        uses_group_offset=bool(uses_group_offset),
        shader_mode="offset_paint",
        depth_test_mode="LESS_EQUAL",
        blend_mode="ALPHA",
        paint_texture=paint_texture,
        paint_offset_scale=float(paint_offset_scale),
        show_paint_mask=bool(show_paint_mask),
        offset_group_name=str(getattr(offset_group, "name", "") or ""),
    )


def make_offset_line_overlay_pass(
    line_batch,
    line_color,
    line_width: float,
    offset: float,
    *,
    uses_group_offset: bool,
    get_offset_shader_fn: Callable[[], object],
    offset_group=None,
) -> OverlayPass:
    return OverlayPass(
        fill_batch=None,
        line_batch=line_batch,
        fill_color=(0.0, 0.0, 0.0, 0.0),
        line_color=line_color,
        line_width=float(line_width),
        shader=get_offset_shader_fn(),
        offset=float(offset),
        uses_group_offset=uses_group_offset,
        shader_mode="offset",
        depth_test_mode="LESS_EQUAL",
        offset_group_name=str(getattr(offset_group, "name", "") or ""),
    )


def make_line_overlay_pass(line_batch, line_color, line_width: float) -> OverlayPass:
    return OverlayPass(
        fill_batch=None,
        line_batch=line_batch,
        fill_color=(0.0, 0.0, 0.0, 0.0),
        line_color=line_color,
        line_width=float(line_width),
        depth_test_mode="LESS_EQUAL",
    )


def make_lit_heatmap_overlay_pass(fill_batch, fill_color, *, blend_mode, face_culling_mode, get_lit_shader_fn: Callable[[], object]) -> OverlayPass:
    return OverlayPass(
        fill_batch=fill_batch,
        line_batch=None,
        fill_color=(0.0, 0.0, 0.0, 0.0),
        line_color=(0.0, 0.0, 0.0, 0.0),
        line_width=0.0,
        shader=get_lit_shader_fn(),
        depth_test_mode="LESS_EQUAL",
        depth_write=True,
        face_culling_mode=face_culling_mode,
        shader_mode="vertex_color",
        blend_mode=blend_mode,
        kind="heatmap",
    )


def build_skew_colored_line_batch(buffers, *, get_skew_batch_format_fn: Callable[[], object], get_skew_shader_fn: Callable[[], object]):
    n = len(buffers.positions)
    if n == 0 or len(buffers.colors) != n:
        return None
    pos_stream, needle_stream, color_stream, dir_stream = skew_needle_vertex_streams(buffers)
    if not pos_stream:
        return None
    try:
        vertex_buffer = gpu.types.GPUVertBuf(get_skew_batch_format_fn(), len(pos_stream))
        vertex_buffer.attr_fill("pos", pos_stream)
        vertex_buffer.attr_fill("needle", needle_stream)
        vertex_buffer.attr_fill("color", color_stream)
        vertex_buffer.attr_fill("dir", dir_stream)
        return gpu.types.GPUBatch(type="LINES", buf=vertex_buffer)
    except Exception:
        try:
            return batch_for_shader(
                get_skew_shader_fn(),
                "LINES",
                {"pos": pos_stream, "needle": needle_stream, "color": color_stream, "dir": dir_stream},
            )
        except Exception:
            return None


def skew_overlay_pass_from_batch(
    buffers,
    theme,
    *,
    build_skew_colored_line_batch_fn: Callable[[object], object],
    build_batch_fn: Callable[..., object],
    make_line_overlay_pass_fn: Callable[..., OverlayPass],
    get_skew_shader_fn: Callable[[], object],
) -> OverlayPass | None:
    if not buffers.positions:
        return None
    if buffers.colors:
        batch = build_skew_colored_line_batch_fn(buffers)
        if batch is None:
            return None
        return OverlayPass(
            fill_batch=batch,
            line_batch=None,
            fill_color=(0.0, 0.0, 0.0, 0.0),
            line_color=(0.0, 0.0, 0.0, 0.0),
            line_width=theme.skew_line_width,
            shader=get_skew_shader_fn(),
            shader_mode="skew_color",
            blend_mode="ALPHA",
            depth_test_mode="LESS_EQUAL",
        )
    batch = build_batch_fn("LINES", buffers.positions)
    return make_line_overlay_pass_fn(batch, theme.skew_line, theme.skew_line_width)
