# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2024, Alex Zhornyak, Valeriy Yatsenko

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_circle_2d

import math
from mathutils import Vector, Matrix, Color
from mathutils.geometry import intersect_line_line_2d

from dataclasses import dataclass
from functools import partial
from timeit import default_timer as timer
import ctypes

from ZenUV.utils.blender_zen_utils import (
    get_view_1px_from_region,
    show_message_box,
    get_gizmo_scale,
    is_uv_snap_enabled,
    update_areas_in_uv,
    reset_properties_modified,
    ZenPolls,
    ZenCompat,
    ZenDrawConstants)
from ZenUV.utils.shaders import get_dashed_shader_line_2, Dash_UBO_struct
from ZenUV.ops.transform_sys.transform_utils.tr_object_data import transform_object_loop_data
from ZenUV.prop.scene_ui_props import ZUV_UVToolProps
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.utils.vlog import Log
from ZenUV.utils.simple_geometry import (
    TextRect, Rectangle,
    draw_circle_2d_filled, draw_rounded_rect)
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.generic import calc_uv_editor_image_aspect_ratio
from ZenUV.utils.transform import matrix_by_image_aspect

from .uv_transform_handle import ZuvTransformHandleBase
from ..custom_gizmo_shapes import CustomShapes


LITERAL_TR_GIZMO_OPERATORS = 'zenuv_tr_gizmo_operators'
LITERAL_TR_GIZMO_SELECTION_CENTER = 'zenuv_tr_gizmo_selection_center'


def update_transform_gizmo_selection_center(context: bpy.types.Context):
    p_scene = bpy.context.scene
    tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
    if tool_props.tr_gizmo_auto_setup_by_selection:
        from .uv_base import ZuvUVGizmoBase
        v_center = ZuvUVGizmoBase.getUVSelectedCenter(context.copy())
        bpy.app.driver_namespace[LITERAL_TR_GIZMO_SELECTION_CENTER] = v_center


def zenuv_setup_transform_gizmo_by_selection():
    try:
        from .uv_base import ZuvUVGizmoBase
        p_scene = bpy.context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        p_area = next(
            area
            for window in bpy.context.window_manager.windows
            for area in window.screen.areas
            if area.type == 'IMAGE_EDITOR')
        if p_area and p_area.spaces.active:
            override = bpy.context.copy()
            override["area"] = p_area
            override["space_data"] = p_area.spaces.active

            v_center = ZuvUVGizmoBase.getUVSelectedCenter(override)
            if v_center != bpy.app.driver_namespace.get(LITERAL_TR_GIZMO_SELECTION_CENTER, Vector((math.nan, math.nan))):
                bpy.app.driver_namespace[LITERAL_TR_GIZMO_SELECTION_CENTER] = v_center

                if math.isfinite(v_center.x) and math.isfinite(v_center.y):
                    tool_props.tr_gizmo_active = False
                    with bpy.context.temp_override(**override):
                        tool_props.tr_gizmo_apply_auto_setup_by_selection()
    except Exception as e:
        Log.error("SETUP TRANSFORM GIZMO BY SELECTION:", e)


@dataclass
class ZuvGizmoOriginAndInitData:

    view_origin_pivot: Vector = Vector((0, 0))
    view_origin_head: Vector = Vector((0, 0))
    view_origin_vector: Vector = Vector((0, 0))
    view_origin_direction: Vector = Vector((0, 0))
    view_origin_orthogonal_direction: Vector = Vector((0, 0))

    gizmo_origin_pivot_rgn: Vector = Vector((0, 0))
    gizmo_origin_head_rgn: Vector = Vector((0, 0))
    gizmo_p_handle_rgn: Vector = Vector((0, 0))
    gizmo_a_handle_rgn: Vector = Vector((0, 0))
    gizmo_vector_rgn: Vector = Vector((0, 0))
    gizmo_direction_rgn: Vector = Vector((0, 0))
    gizmo_orthogonal_direction_rgn: Vector = Vector((0, 0))

    tool_props: ZUV_UVToolProps = None

    rgn2d: bpy.types.View2D = None

    gizmo_scale: float = 1.0

    def setup(self, context: bpy.types.Context, tool_props: ZUV_UVToolProps):
        self.tool_props = tool_props
        self.rgn2d = context.region.view2d

        self.view_origin_pivot, self.view_origin_head = Vector(tool_props.tr_gizmo_init_p_handle), Vector(tool_props.tr_gizmo_init_a_handle)
        self.view_origin_vector = self.view_origin_head - self.view_origin_pivot
        self.view_origin_direction = self.view_origin_vector.normalized()
        self.view_origin_orthogonal_direction = self.view_origin_vector.orthogonal().normalized()

        self.gizmo_origin_head_rgn = Vector(self.rgn2d.view_to_region(*tool_props.tr_gizmo_init_a_handle[:], clip=False))
        self.gizmo_origin_pivot_rgn = Vector(self.rgn2d.view_to_region(*tool_props.tr_gizmo_init_p_handle[:], clip=False))
        self.gizmo_origin_vector = self.gizmo_origin_head_rgn - self.gizmo_origin_pivot_rgn
        self.gizmo_origin_direction = self.gizmo_origin_vector.normalized()

        self.gizmo_p_handle_rgn = Vector(self.rgn2d.view_to_region(*tool_props.tr_gizmo_pivot_handle[:], clip=False))
        self.gizmo_a_handle_rgn = Vector(self.rgn2d.view_to_region(*tool_props.tr_gizmo_angle_handle[:], clip=False))
        self.gizmo_vector_rgn = self.gizmo_a_handle_rgn - self.gizmo_p_handle_rgn
        self.gizmo_direction_rgn = self.gizmo_vector_rgn.normalized()
        self.gizmo_orthogonal_direction_rgn = self.gizmo_vector_rgn.orthogonal().normalized()

        self.gizmo_scale = get_gizmo_scale(context)


@dataclass
class ZuvTransformGizmoColors:
    main_handles: Color = Color()
    main_handles_highlight: Color = Color()

    line: Color = Color()
    line_highlight: Color = Color()

    rotate_handle: Color = Color()
    rotate_handle_highlight: Color = Color()

    scale_handle: Color = Color()
    scale_handle_highlight: Color = Color()

    def setup(self, context: bpy.types.Context):
        bl_theme = context.preferences.themes[0].user_interface

        p_color = Color(bl_theme.gizmo_view_align[:3])
        self.main_handles_highlight = p_color.copy()
        p_color.v *= 0.75
        self.main_handles = p_color.copy()

        p_color = Color(bl_theme.axis_z[:3])
        self.rotate_handle_highlight = p_color.copy()
        p_color.v *= 0.75
        self.rotate_handle = p_color.copy()

        p_color = Color(bl_theme.axis_y[:3])
        self.scale_handle_highlight = p_color.copy()
        p_color.v *= 0.75
        self.scale_handle = p_color.copy()

        p_color = Color(bl_theme.axis_x[:3])
        self.line_highlight = p_color.copy()
        p_color.v *= 0.75
        self.line = p_color.copy()


@dataclass
class ZuvTransformTooltipText:
    icon: str = ""
    key1: str = ""
    key2: str = ""
    key3: str = ""
    text: str = ""


@dataclass
class ZuvGizmoGroupModalData:
    rotate_previous_angle: float = None
    rotate_accumuluate_angle: float = None
    snapped_point_region: Vector = None

    is_modal: bool = False

    def clear(self):
        self.rotate_previous_angle = None
        self.rotate_accumuluate_angle = None
        self.is_modal = False
        self.snapped_point_region = None


class ZUV_GGT_UVTransformGizmo(bpy.types.GizmoGroup):
    bl_idname = "ZUV_GGT_UVTransformGizmo"
    bl_label = "Transform (Move)"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SHOW_MODAL_ALL',
    } if bpy.app.version < (3, 3, 0) else {
        'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL',
    }

    INACTIVE_COLOR = (0.5, 0.5, 0.5)

    gizmo_handle_hide_secondaries = False
    gizmo_dial_inner_radius = 100
    gizmo_dial_outer_radius = 200
    gizmo_snap_threshold_px = 15
    gizmo_dial_use_in_range = False

    gizmo_align_inner_radius = 25  # Baked. The changes will not affect the size.
    gizmo_align_outer_radius = 40  # Baked. The changes will not affect the size.

    gizmo_label_text_size = 11

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from .uv_transform_tool import ZuvUVTransformWorkSpaceTool
        if ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context):
            return True
        return False

    def move_get_cb_handle(self):
        return self.tool_offset_handle

    def move_set_cb_handle(self, value):
        p_vec = Vector(value)
        if self.tool_offset_handle != p_vec:
            self.tool_offset_handle = p_vec

    def move_get_cb_line(self):
        return self.tool_offset_line

    def move_set_cb_line(self, value):
        p_vec = Vector(value)
        if self.tool_offset_line != p_vec:
            self.tool_offset_line = p_vec

    def move_get_cb_pivot(self):
        return self.tool_offset_pivot

    def move_set_cb_pivot(self, value):
        p_vec = Vector(value)
        if self.tool_offset_pivot != p_vec:
            self.tool_offset_pivot = p_vec

    def move_get_cb_rot(self):
        return self.tool_offset_rotate

    def move_set_cb_rot(self, value):
        p_vec = Vector(value)
        if self.tool_offset_rotate != p_vec:
            self.tool_offset_rotate = p_vec

    def move_get_cb_sca(self):
        return self.tool_offset_scale

    def move_set_cb_sca(self, value):
        p_vec = Vector(value)
        if self.tool_offset_scale != p_vec:
            self.tool_offset_scale = p_vec

    def draw_prepare(self, context: bpy.types.Context):
        # NOTE: Colors must be setup at first by default
        self.setup_colors(context)

        # NOTE: Colors could be finally tuned by matrices
        self._setup_matrices_final(context)

    @classmethod
    def zenuv_setup_transform_gizmo_line(cls, tool_props: ZUV_UVToolProps, cursor_location: Vector, cursor_offset: Vector):
        v1 = Vector(tool_props.tr_gizmo_pivot_handle)
        v2 = Vector(tool_props.tr_gizmo_angle_handle)

        if tool_props.tr_gizmo_is_pivot:
            v1 = cursor_location
            v2 += cursor_offset
        else:
            v1 += cursor_offset
            v2 = cursor_location

        tool_props.tr_gizmo_line = (*v1.to_tuple()[:2], *v2.to_tuple()[:2])
        tool_props.tr_gizmo_origin = cursor_location[:]
        update_areas_in_uv(bpy.context)

    @classmethod
    def zenuv_setup_transform_gizmo(cls, tool_props: ZUV_UVToolProps, s_gizmo_id, cursor_location: Vector):
        setattr(tool_props, s_gizmo_id, cursor_location)
        tool_props.tr_gizmo_origin = cursor_location[:]
        update_areas_in_uv(bpy.context)

    @classmethod
    def get_gizmo_dial_step_angle(cls, p_tool_props: ZUV_UVToolProps):
        return int(p_tool_props.tr_gizmo_dial_snap_step_angle.split("_", 1)[0])

    def _setup_matrices_final(self, context: bpy.types.Context):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        p_gizmo_data = ZuvGizmoOriginAndInitData()
        p_gizmo_data.setup(context, tool_props)

        if not self.mpr_pivot.is_modal:
            mtx = Matrix.Translation(p_gizmo_data.gizmo_p_handle_rgn.resized(3))
            self.mpr_pivot.matrix_space = mtx
            self.tool_offset_pivot = Vector()

        if not self.mpr_handle.is_modal:
            mtx = Matrix.Translation(p_gizmo_data.gizmo_a_handle_rgn.resized(3))
            self.mpr_handle.matrix_space = mtx
            self.tool_offset_handle = Vector()

        if not self.mpr_line.is_modal:
            self.tool_offset_line = Vector()

        self.mpr_line.start = p_gizmo_data.gizmo_p_handle_rgn.copy()
        self.mpr_line.end = p_gizmo_data.gizmo_a_handle_rgn.copy()

        self.setup_align_gizmo(context, p_gizmo_data)

        self.setup_gizmo_bbox(context, p_gizmo_data)

        self.setup_handle_rotation(context, p_gizmo_data)

        self.setup_handle_scale(context, p_gizmo_data)

        self.setup_handle_scale_no_proportion(context, p_gizmo_data)

    def setup_handle_scale(self, context: bpy.types.Context, gizmo_data: ZuvGizmoOriginAndInitData):
        addon_prefs = get_prefs()

        offset = 26
        length = 8
        width = 8

        p_gizmo_scale = gizmo_data.gizmo_scale
        tool_props = gizmo_data.tool_props

        v_gizmo_angle_handle = gizmo_data.gizmo_a_handle_rgn.copy()

        if gizmo_data.gizmo_vector_rgn.length <= 1e-6:
            v_direction = gizmo_data.view_origin_direction.copy()
            self.mpr_handle_scale.color = (0, 1, 0)
        else:
            v_direction = gizmo_data.gizmo_direction_rgn.copy()

        v_start_position = v_gizmo_angle_handle + (v_direction * offset * p_gizmo_scale)
        self.mpr_handle_scale.start = v_start_position
        self.mpr_handle_scale.end = v_start_position + (v_direction * length * p_gizmo_scale)
        self.mpr_handle_scale.line_width = width * p_gizmo_scale
        self.mpr_handle_scale.hide = (
            tool_props.tr_gizmo_mode == 'SETUP' or
            ("SCALE" not in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state))
        self.mpr_handle_scale.rect_side = 5
        self.mpr_handle_scale.corner = 2 * p_gizmo_scale
        self.mpr_handle_scale.matrix_basis = Matrix.Diagonal((2.2, 2.2)).to_4x4()

    def setup_handle_scale_no_proportion(self, context: bpy.types.Context, gizmo_data: ZuvGizmoOriginAndInitData):
        addon_prefs = get_prefs()

        offset = 26
        length = 15
        width = 4
        b_is_horisontal = True

        p_gizmo_scale = gizmo_data.gizmo_scale
        tool_props = gizmo_data.tool_props

        v_gizmo_angle_handle = gizmo_data.gizmo_a_handle_rgn.copy()

        if gizmo_data.gizmo_vector_rgn.length <= 1e-6:
            v_direction = gizmo_data.view_origin_direction.copy()
            self.mpr_handle_scale_no_proportion.color = (0, 1, 0)
        else:
            v_direction = gizmo_data.gizmo_direction_rgn.copy()
        v_direction.negate()

        v_start_position = v_gizmo_angle_handle + (v_direction * offset * p_gizmo_scale)
        v_end_position = v_start_position + (v_direction * length * p_gizmo_scale)

        if b_is_horisontal:
            v_position = v_start_position
            p_vec = v_end_position - v_start_position
            p_center = p_vec * 0.5

            p_vec_start = p_vec - p_center
            p_vec_end = Vector((0, 0)) - p_center

            v_start_position = Vector((p_vec_start.y, -p_vec_start.x)) + v_position
            v_end_position = Vector((p_vec_end.y, -p_vec_end.x)) + v_position

        self.mpr_handle_scale_no_proportion.start = v_start_position
        self.mpr_handle_scale_no_proportion.end = v_end_position
        self.mpr_handle_scale_no_proportion.line_width = width * p_gizmo_scale
        self.mpr_handle_scale_no_proportion.hide = (
            tool_props.tr_gizmo_mode == 'SETUP' or
            ("SCALE_NON_PROP" not in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state))
        self.mpr_handle_scale_no_proportion.rect_side = 5
        self.mpr_handle_scale_no_proportion.corner = 0
        self.mpr_handle_scale_no_proportion.matrix_basis = Matrix.Diagonal((1, 4)).to_4x4()

    def setup_handle_rotation(self, context: bpy.types.Context, gizmo_data: ZuvGizmoOriginAndInitData):
        addon_prefs = get_prefs()

        offset = 26
        length = 6
        width = 6

        tool_props = gizmo_data.tool_props
        p_gizmo_scale = gizmo_data.gizmo_scale

        v_gizmo_angle_handle = gizmo_data.gizmo_a_handle_rgn.copy()

        if gizmo_data.gizmo_vector_rgn.length <= 1e-6:
            self.mpr_handle_rotate.hide = True
            return
        else:
            v_direction = gizmo_data.gizmo_orthogonal_direction_rgn.copy()

        v_start_position = v_gizmo_angle_handle + (v_direction * offset * p_gizmo_scale)
        self.mpr_handle_rotate.start = v_start_position
        self.mpr_handle_rotate.end = v_start_position + (v_direction * length * p_gizmo_scale)
        self.mpr_handle_rotate.line_width = width * p_gizmo_scale
        self.mpr_handle_rotate.hide = (
            tool_props.tr_gizmo_mode == 'SETUP' or
            ("ROTATION" not in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state))

    def setup_gizmo_bbox(self, context: bpy.types.Context, gizmo_data: ZuvGizmoOriginAndInitData):
        addon_prefs = get_prefs()

        b_hide_bbox = "BBOX" not in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state
        if not b_hide_bbox:
            x1, y1 = gizmo_data.gizmo_p_handle_rgn[:2]
            x2, y2 = gizmo_data.gizmo_a_handle_rgn[:2]

            left = min(x1, x2)
            top = max(y1, y2)
            right = max(x1, x2)
            bottom = min(y1, y2)

            d_m = [
                [left, bottom, left, top],
                [left, top, right, top],
                [right, top, right, bottom],
                [right, bottom, left, bottom]]

            for i, v in enumerate(self.mpr_tool_bbox.values()):
                v.hide = False
                v.start = Vector((d_m[i][0], d_m[i][1]))
                v.end = Vector((d_m[i][2], d_m[i][3]))
        else:
            for v in self.mpr_tool_bbox.values():
                v.hide = True

    def setup_align_gizmo(self, context: bpy.types.Context, gizmo_data: ZuvGizmoOriginAndInitData):
        addon_prefs = get_prefs()

        tool_props = gizmo_data.tool_props

        v_gizmo_pivot_handle = Vector(tool_props.tr_gizmo_pivot_handle)
        v_gizmo_angle_handle = Vector(tool_props.tr_gizmo_angle_handle)

        v_gizmo_vec = v_gizmo_angle_handle - v_gizmo_pivot_handle
        if v_gizmo_vec.length <= 1e-6:
            for v in self.mpr_trim_align.values():
                v.hide = True
            return
        p_gizmo_scale = gizmo_data.gizmo_scale

        #########################################
        # Dial Gizmo generation process
        # Now we use baked vectors, so only
        # the parameters are stored here
        #
        # inner_radius = self.gizmo_align_inner_radius
        # outer_radius = self.gizmo_align_outer_radius
        # num_points = len(self.mpr_trim_align.items())
        # modification_pattern = [1, 0]
        # p_dial_vectors = CustomShapes.get_dial_vectors(
        #     num_points,
        #     inner_radius,
        #     outer_radius,
        #     ui_scale=p_gizmo_scale,
        #     modification_pattern=modification_pattern,
        #     mode_1_length_mult=1,  # length percentage 0-1
        #     mode_1_attributes=[2, False],  # [line_width, hide]
        #     mode_0_length_mult=0.65,  # length percentage 0-1
        #     mode_0_attributes=[2, self.gizmo_handle_hide_secondaries]  # [line_width, hide]
        # )
        #########################################

        p_dial_vectors = CustomShapes.align_gizmo_vectors

        b_hide_gizmo_handles = 'ALIGN' not in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state

        to_position = Matrix.Translation(gizmo_data.gizmo_p_handle_rgn.resized(3))
        M_ui_scale = Matrix.Diagonal((p_gizmo_scale, p_gizmo_scale))
        M = to_position @ M_ui_scale.to_4x4()

        for i, v in enumerate(self.mpr_trim_align.values()):
            v.hide = b_hide_gizmo_handles
            if not v.hide:
                p_line_width = p_dial_vectors[i][2][0]
                p_hide = p_dial_vectors[i][2][1]

                v.line_width = p_line_width * p_gizmo_scale
                v.hide = p_hide

                v.start, v.end = [(M @ v).to_2d() for v in p_dial_vectors[i][:2]]
                dial_length = v.end - v.start
                v.rect_side = 5
                v.corner = 1
                v.matrix_basis = Matrix.Diagonal(Vector((1, dial_length.magnitude / 4 / p_gizmo_scale))).to_4x4()

    def setup_colors(self, context: bpy.types.Context):
        p_scene = bpy.context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        b_is_transform = tool_props.tr_gizmo_mode == 'TRANSFORM'

        self.gizmo_colors.setup(context)

        self.mpr_handle.color = self.gizmo_colors.main_handles.copy()
        self.mpr_handle.alpha = 0.5
        self.mpr_handle.color_highlight = self.gizmo_colors.main_handles_highlight.copy()
        self.mpr_handle.alpha_highlight = 1

        self.mpr_handle_rotate.alpha = 0.5 / 2
        self.mpr_handle_rotate.color = self.gizmo_colors.rotate_handle.copy()
        self.mpr_handle_rotate.color_highlight = self.gizmo_colors.rotate_handle_highlight.copy()
        self.mpr_handle_rotate.alpha_highlight = 1.0

        self.mpr_handle_scale.alpha = 0.5 / 2
        self.mpr_handle_scale.color = self.gizmo_colors.scale_handle.copy()
        self.mpr_handle_scale.color_highlight = self.gizmo_colors.scale_handle_highlight.copy()
        self.mpr_handle_scale.alpha_highlight = 1.0

        self.mpr_handle_scale_no_proportion.alpha = 0.5 / 2
        self.mpr_handle_scale_no_proportion.color = self.gizmo_colors.scale_handle.copy()
        self.mpr_handle_scale_no_proportion.color_highlight = self.gizmo_colors.scale_handle_highlight.copy()
        self.mpr_handle_scale_no_proportion.alpha_highlight = 1.0

        self.mpr_pivot.color = self.gizmo_colors.main_handles.copy()
        self.mpr_pivot.alpha = 0.5
        self.mpr_pivot.color_highlight = self.gizmo_colors.main_handles_highlight.copy()
        self.mpr_pivot.alpha_highlight = 1.0

        self.mpr_line.color = self.gizmo_colors.line.copy() if b_is_transform else self.gizmo_colors.main_handles.copy()
        self.mpr_line.alpha = 0.95
        self.mpr_line.color_highlight = self.gizmo_colors.line_highlight.copy() if b_is_transform else self.gizmo_colors.main_handles_highlight.copy()
        self.mpr_line.alpha_highlight = 0.95  # NOTE: Alpha must not be 1.0 to support line smoothing

        for k in UV_AREA_BBOX.bbox_circle_ordered_handles:
            self.mpr_trim_align[k].alpha = 0.5 / 2
            self.mpr_trim_align[k].color = (
                self.gizmo_colors.rotate_handle.copy() if b_is_transform else self.gizmo_colors.main_handles.copy())
            self.mpr_trim_align[k].color_highlight = (
                self.gizmo_colors.rotate_handle_highlight.copy() if b_is_transform else self.gizmo_colors.main_handles_highlight.copy())
            self.mpr_trim_align[k].alpha_highlight = 1.0

        from .uv_base import ZuvUVGizmoBase
        b_is_any_highlighted = ZuvUVGizmoBase.are_gizmos_highlighted(self)
        if not b_is_any_highlighted:
            self.unregister_tooltip()

    @classmethod
    def get_gizmo_group_by_context(cls, context: bpy.types.Context):
        p_gizmos = bpy.app.driver_namespace.get(ZUV_GGT_UVTransformGizmo.bl_idname, {})
        return p_gizmos.get(context.area.as_pointer(), None)

    def setup(self, context: bpy.types.Context):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        p_gizmos = bpy.app.driver_namespace.get(ZUV_GGT_UVTransformGizmo.bl_idname, {})
        p_gizmos[context.area.as_pointer()] = self
        bpy.app.driver_namespace[ZUV_GGT_UVTransformGizmo.bl_idname] = p_gizmos

        self.gizmo_colors = ZuvTransformGizmoColors()
        self.gizmo_cursor_location = Vector((0, 0))

        self.mpr_tooltip = self.gizmos.new("UV_GT_zenuv_transform_tool_tooltip")
        self.mpr_tooltip.alpha = 1
        self.mpr_tooltip.color = 0.0, 0.0, 0.0
        self.mpr_tooltip.color_highlight = 0.0, 0.0, 1.0
        self.mpr_tooltip.alpha_highlight = 1.0
        self.mpr_tooltip.line_width = 1
        self.mpr_tooltip.use_draw_modal = False
        self.mpr_tooltip.use_draw_value = True
        self.mpr_tooltip.hide = True
        self.mpr_tooltip.use_select_background = False

        self.mpr_handle: UV_GT_zenuv_transform_a_handle = self.gizmos.new("UV_GT_zenuv_transform_a_handle")
        self.mpr_handle.scale_basis = 0.2
        self.mpr_handle.line_width = 1.0
        self.mpr_handle.use_draw_modal = True
        self.mpr_handle.use_draw_value = True
        self.mpr_handle.hide = False
        self.mpr_handle.use_select_background = False
        self.mpr_handle.gizmo_type = "ANGLE_HANDLE"

        self.mpr_handle_rotate: UV_GT_zenuv_rotate_handle = self.gizmos.new("UV_GT_zenuv_rotate_handle")
        self.mpr_handle_rotate.line_width = 1
        self.mpr_handle_rotate.use_draw_modal = True
        self.mpr_handle_rotate.use_draw_value = True
        self.mpr_handle_rotate.hide = False
        self.mpr_handle_rotate.use_select_background = False
        self.mpr_handle_rotate.gizmo_type = "ROTATE"

        self.mpr_handle_scale = self.gizmos.new("UV_GT_zenuv_scale_handle")
        self.mpr_handle_scale.use_draw_modal = True
        self.mpr_handle_scale.use_draw_value = True
        self.mpr_handle_scale.hide = False
        self.mpr_handle_scale.use_select_background = False
        self.mpr_handle_scale.gizmo_type = 'SCALE'
        self.mpr_handle_scale.gizmo_axes_lock = 'SCALE_ALONG_AXIS'

        self.mpr_handle_scale_no_proportion = self.gizmos.new("UV_GT_zenuv_scale_handle")
        self.mpr_handle_scale_no_proportion.use_draw_modal = True
        self.mpr_handle_scale_no_proportion.use_draw_value = True
        self.mpr_handle_scale_no_proportion.hide = False
        self.mpr_handle_scale_no_proportion.use_select_background = False
        self.mpr_handle_scale_no_proportion.gizmo_type = 'SCALE_NON_PROP'
        self.mpr_handle_scale_no_proportion.gizmo_axes_lock = 'SCALE_ALONG_AXIS_NO_PROPORTION'

        self.mpr_pivot = self.gizmos.new("UV_GT_zenuv_transform_pivot")
        self.mpr_pivot.scale_basis = 0.2
        self.mpr_pivot.line_width = 1.0
        self.mpr_pivot.use_draw_modal = True
        self.mpr_pivot.use_draw_value = True
        self.mpr_pivot.hide = False
        self.mpr_pivot.use_select_background = False
        self.mpr_pivot.gizmo_type = "PIVOT_HANDLE"

        self.mpr_trim_align = {}

        for k in UV_AREA_BBOX.bbox_circle_ordered_handles:
            self.mpr_trim_align[k] = self.gizmos.new("UV_GT_zenuv_transform_handle")
            self.mpr_trim_align[k].use_draw_modal = True
            self.mpr_trim_align[k].use_draw_value = True
            self.mpr_trim_align[k].hide = False
            self.mpr_trim_align[k].use_select_background = False

            op_props = self.mpr_trim_align[k].target_set_operator('zenuv.tool_transform_handle')
            op_props.direction = k

        self.mpr_line = self.gizmos.new("UV_GT_zenuv_draggable_line")
        self.mpr_line.line_width = 1.0
        self.mpr_line.use_draw_modal = True
        self.mpr_line.use_draw_value = True
        self.mpr_line.hide = False
        self.mpr_line.use_select_background = False
        self.mpr_line.gizmo_type = 'LINE'

        self.mpr_tool_bbox = {}

        for k in ('left', 'top', 'right', 'bottom'):
            self.mpr_tool_bbox[k] = self.gizmos.new("UV_GT_zenuv_bbox_tool")
            self.mpr_tool_bbox[k].alpha = 1
            self.mpr_tool_bbox[k].color = 1.0, 1.0, 0.0
            self.mpr_tool_bbox[k].color_highlight = 0.0, 0.0, 1.0
            self.mpr_tool_bbox[k].alpha_highlight = 1.0
            self.mpr_tool_bbox[k].line_width = 20
            self.mpr_tool_bbox[k].use_draw_modal = True
            self.mpr_tool_bbox[k].use_draw_value = True
            self.mpr_tool_bbox[k].hide = False
            self.mpr_tool_bbox[k].use_select_background = False

        # NOTE: all moveable gizmos must have offset vector 3D !!! property
        self.tool_offset_pivot = Vector()
        self.tool_offset_handle = Vector()
        self.tool_offset_line = Vector()
        self.tool_offset_rotate = Vector()
        self.tool_offset_scale = Vector()

        if tool_props.tr_gizmo_mode != 'SETUP':

            def zenuv_make_setup_mode():
                tool_props.tr_gizmo_mode = 'SETUP'

            bpy.app.timers.register(zenuv_make_setup_mode)

        self.origin_gizmo = None
        self.active_gizmo = None

        self._setup_matrices_final(context)

        # NOTE: handlers must be set once to measure move delta
        self.mpr_pivot.target_set_handler(
            "offset",
            get=self.move_get_cb_pivot, set=self.move_set_cb_pivot)

        self.mpr_handle.target_set_handler(
            "offset",
            get=self.move_get_cb_handle, set=self.move_set_cb_handle)

        self.mpr_line.target_set_handler(
            "offset",
            get=self.move_get_cb_line, set=self.move_set_cb_line)

        self.mpr_handle_rotate.target_set_handler(
            "offset",
            get=self.move_get_cb_rot, set=self.move_set_cb_rot)

        self.mpr_handle_scale.target_set_handler(
            "offset",
            get=self.move_get_cb_sca, set=self.move_set_cb_sca)

        self.mpr_handle_scale_no_proportion.target_set_handler(
            "offset",
            get=self.move_get_cb_sca, set=self.move_set_cb_sca)

        self.tooltip_handler = None
        self.init_invoke_p_handle_mtx = Matrix()
        self.init_invoke_a_handle_mtx = Matrix()
        self.modal_data = ZuvGizmoGroupModalData()

    def init_tooltip(self, context: bpy.types.Context, gizmo: bpy.types.Gizmo, location: Vector):
        try:
            if context.preferences.view.show_tooltips and gizmo.is_highlight and not gizmo.is_modal:
                p_scene = context.scene
                tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

                s_description = bpy.types.UILayout.enum_item_description(tool_props, 'tr_gizmo_type', gizmo.gizmo_type)

                b_lines_enabled = True

                t_output = []

                for line in s_description.splitlines():
                    if line.startswith("--"):
                        b_lines_enabled = tool_props.tr_gizmo_mode in line
                        continue
                    if b_lines_enabled:
                        if line.startswith(" * Double"):
                            if 'Ctrl' in line:
                                t_output.append(
                                    ZuvTransformTooltipText(
                                        icon='MOUSE_LMB',
                                        key1="x2",
                                        key2="Ctrl",
                                        text=line.replace(" * Double Click + Ctrl - ", ""))
                                )
                            else:
                                t_output.append(
                                    ZuvTransformTooltipText(
                                        icon='MOUSE_LMB',
                                        key1="x2",
                                        text=line.replace(" * Double Click - ", ""))
                                )
                        else:
                            t_output.append(
                                ZuvTransformTooltipText(
                                    icon='MOUSE_LMB_DRAG',
                                    text=line.replace(" * Double Click - ", ""))
                            )

                self.mpr_tooltip.matrix_basis = Matrix.Translation(Vector((*location[:], 0)))
                self.mpr_tooltip.text_items = t_output.copy()
                self.mpr_tooltip.hide = False
        except Exception as e:
            Log.error("INIT GIZMO TOOLTIP:", e)

    def register_tooltip(self, context: bpy.types.Context, gizmo: bpy.types.Gizmo, location):
        if context.preferences.view.show_tooltips:
            addon_prefs = get_prefs()
            if 'HANDLE_TOOLTIP' in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state:
                self.tooltip_handler = partial(self.init_tooltip, context, gizmo, location)
                bpy.app.timers.register(self.tooltip_handler, first_interval=1.0)

    def unregister_tooltip(self):
        self.mpr_tooltip.hide = True
        if self.tooltip_handler and bpy.app.timers.is_registered(self.tooltip_handler):
            bpy.app.timers.unregister(self.tooltip_handler)
            self.tooltip_handler = None

    def cancel_setup_by_selection(self):
        if bpy.app.timers.is_registered(zenuv_setup_transform_gizmo_by_selection):
            bpy.app.timers.unregister(zenuv_setup_transform_gizmo_by_selection)

    def refresh(self, context: bpy.types.Context):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        if tool_props.tr_gizmo_auto_setup_by_selection:  # and tool_props.tr_gizmo_mode == 'SETUP':
            from .uv_base import ZuvUVGizmoBase
            if not ZuvUVGizmoBase.are_gizmos_modal(self):
                self.cancel_setup_by_selection()

                bpy.app.timers.register(
                    zenuv_setup_transform_gizmo_by_selection, first_interval=0.1)


class ZuvTransformGizmoBase:

    def exit(self: bpy.types.Gizmo, context: bpy.types.Context, cancel):
        context.area.header_text_set(None)
        if cancel:
            self.target_set_value("offset", self.init_value)
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        tool_props.tr_gizmo_axes_lock = 'NONE'
        tool_props.tr_gizmo_event_mode = 'DEFAULT'
        tool_props.tr_gizmo_display_xy_guidelines = (False, False)

        self.gizmo_internal_axis_lock = (False, False)
        self.gizmo_rotate_with_step = False

        p_group: ZUV_GGT_UVTransformGizmo = self.group
        p_group.modal_data.clear()

        context.area.tag_redraw()
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

        if not cancel:
            b_disable_finalize = False
            if tool_props.tr_gizmo_transform_editing_mode == "LINEAR_FALLOFF":
                if set(tool_props.tr_gizmo_linear_falloff_transformation_type) != set({"ROTATE"}):
                    if self.gizmo_type in {'PIVOT_HANDLE', 'ANGLE_HANDLE'}:
                        b_disable_finalize = True
            if not b_disable_finalize:
                tool_props.tr_gizmo_finalize_cursor_by_tool_op_matrix(context)
        else:
            # NOTE: in setup we are under 'bpy.ops.transform' operation, so we will never get this event
            if tool_props.tr_gizmo_mode == 'TRANSFORM':
                if self.init_operator_transform_data:
                    tool_props.set_tr_gizmo_pivot_handle(self.init_operator_transform_data["matched_pivot"])
                    tool_props.set_tr_gizmo_angle_handle(self.init_operator_transform_data["matched_head"])
                    tool_props.tr_gizmo_setup_cursor_2d(context)

                    from ZenUV.ui.tool.tool_ops import ZUV_OP_ToolTransform
                    ZUV_OP_ToolTransform.revert_transform(context, tool_props, self.init_operator_transform_data)

    def modal(self: bpy.types.Gizmo, context: bpy.types.Context, event: bpy.types.Event, tweak):
        res = {'RUNNING_MODAL'}

        fixed_cursor_location: Vector = None

        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        b_is_setup = tool_props.tr_gizmo_mode == 'SETUP'

        b_is_line = self.gizmo_type == 'LINE'
        b_is_p_handle = self.gizmo_type == 'PIVOT_HANDLE'
        b_is_a_handle = self.gizmo_type == 'ANGLE_HANDLE'
        b_is_rotation = self.gizmo_type == 'ROTATE'

        p_gizmo_group: ZUV_GGT_UVTransformGizmo = self.group

        # NOTE: we need to separate double click from actual movement
        if not p_gizmo_group.modal_data.is_modal:
            v_mouse = Vector((event.mouse_x, event.mouse_y))
            p_gizmo_group.modal_data.is_modal = v_mouse != self.init_mouse.resized(2)

        if not b_is_setup:

            if event.type == 'Z' and event.value == 'PRESS':
                if b_is_line or b_is_a_handle or b_is_p_handle:

                    b_is_x_y_lock_enabled = any(self.gizmo_internal_axis_lock)

                    if b_is_line:
                        b_need_to_lock = b_is_x_y_lock_enabled or tool_props.tr_gizmo_axes_lock != "MOVE_ALONG_AXIS"

                        tool_props.tr_gizmo_axes_lock = (
                            "MOVE_ALONG_AXIS"
                            if b_need_to_lock else
                            "NONE")
                    else:
                        b_need_to_lock = b_is_x_y_lock_enabled or tool_props.tr_gizmo_axes_lock != "SCALE_ALONG_AXIS"

                        tool_props.tr_gizmo_axes_lock = (
                            "SCALE_ALONG_AXIS"
                            if b_need_to_lock else
                            "NONE")

                self.gizmo_internal_axis_lock = (False, False)
                tool_props.tr_gizmo_display_xy_guidelines = (False, False)
            elif event.type == 'A' and event.value == 'PRESS':
                if b_is_rotation:
                    self.gizmo_internal_axis_lock = (False, False)
                    tool_props.tr_gizmo_display_xy_guidelines = (False, False)
                    if not b_is_rotation:
                        tool_props.tr_gizmo_axes_lock = 'NONE'
                    self.gizmo_rotate_with_step = not self.gizmo_rotate_with_step
            else:
                if b_is_line and not tool_props.tr_gizmo_line_lock_along_axis:
                    if event.type == 'X' and event.value == 'PRESS':
                        tool_props.tr_gizmo_axes_lock = "AXIS_LOCK_MOVE_X" if tool_props.tr_gizmo_axes_lock != "AXIS_LOCK_MOVE_X" else "NONE"
                        tool_props.tr_gizmo_display_xy_guidelines = (False, tool_props.tr_gizmo_axes_lock == "AXIS_LOCK_MOVE_X")
                    elif event.type == 'Y' and event.value == 'PRESS':
                        tool_props.tr_gizmo_axes_lock = "AXIS_LOCK_MOVE_Y" if tool_props.tr_gizmo_axes_lock != "AXIS_LOCK_MOVE_Y" else "NONE"
                        tool_props.tr_gizmo_display_xy_guidelines = (tool_props.tr_gizmo_axes_lock == "AXIS_LOCK_MOVE_Y", False)
                else:
                    # NOTE: lock along P-Handle and A-Handle by gizmo movement lock
                    if event.type == 'X' and event.value == 'PRESS':
                        self.gizmo_internal_axis_lock = (False, False) if self.gizmo_internal_axis_lock[1] else (False, True)
                        tool_props.tr_gizmo_display_xy_guidelines = self.gizmo_internal_axis_lock
                        if any(self.gizmo_internal_axis_lock):
                            if b_is_a_handle or b_is_p_handle:
                                tool_props.tr_gizmo_axes_lock = 'NONE'
                            elif b_is_line:
                                tool_props.tr_gizmo_axes_lock = "MOVE_ALONG_AXIS" if tool_props.tr_gizmo_line_lock_along_axis else 'NONE'
                    elif event.type == 'Y' and event.value == 'PRESS':
                        self.gizmo_internal_axis_lock = (False, False) if self.gizmo_internal_axis_lock[0] else (True, False)
                        tool_props.tr_gizmo_display_xy_guidelines = self.gizmo_internal_axis_lock
                        if any(self.gizmo_internal_axis_lock):
                            if b_is_a_handle or b_is_p_handle:
                                tool_props.tr_gizmo_axes_lock = 'NONE'
                            elif b_is_line:
                                tool_props.tr_gizmo_axes_lock = "MOVE_ALONG_AXIS" if tool_props.tr_gizmo_line_lock_along_axis else 'NONE'

        # NOTE: we should avoid "jumps" in interface on double click, so filter only mousemove messages
        if event.type != 'MOUSEMOVE':
            return res

        # Filter with 60 FPS
        if timer() - self.last_update >= 1/60:
            wm = context.window_manager
            rgn2d = context.region.view2d
            v_mouse_rgn = Vector((event.mouse_region_x, event.mouse_region_y))

            # NOTE: reset snap point
            p_gizmo_group.modal_data.snapped_point_region = None

            b_tweak_snap = 'SNAP' in tweak
            self.is_snap_enabled = is_uv_snap_enabled(p_scene, b_tweak_snap)

            delta: Vector = self.init_mouse - Vector((event.mouse_x, event.mouse_y, 0.0))

            b_snap_by_mouse_or_2d_cursor = True

            if not b_snap_by_mouse_or_2d_cursor:
                v_mouse_rgn -= self.init_snap_base

            v_mouse = Vector(rgn2d.region_to_view(x=v_mouse_rgn.x, y=v_mouse_rgn.y))

            # NOTE: if gizmo is locked by X, Y axes we restrict it on gizmo level
            if self.gizmo_internal_axis_lock[0]:
                delta.x = 0
            elif self.gizmo_internal_axis_lock[1]:
                delta.y = 0

            delta_base = delta.copy()

            # NOTE: this is TRANSFORM mode
            #       custom snapping is working only in this mode
            if not b_is_setup:
                v_view_1px = get_view_1px_from_region(context, v_mouse_rgn)

                # NOTE: all snaps must be calculated by original mouse position
                v_snapped_view = transform_object_loop_data.get_snap_point_view(
                    context, v_mouse, v_view_1px, b_tweak_snap, snap_threshold_px=ZUV_GGT_UVTransformGizmo.gizmo_snap_threshold_px
                )

                b_snap_by_origin_is_found = False

                if self.is_snap_enabled:
                    if tool_props.tr_gizmo_snap_to_gizmo_origin_points:
                        p_origin_list: dict = bpy.app.driver_namespace.get("zenuv_tr_gizmo_origin_list", dict())

                        p_origin_points = set()

                        for item in p_origin_list.keys():
                            p_pivot = item[0:2]
                            p_angle = item[2:4]
                            p_origin_points.add(p_pivot)
                            p_origin_points.add(p_angle)

                        p_origin_points.add(tool_props.tr_gizmo_init_a_handle)
                        p_origin_points.add(tool_props.tr_gizmo_init_p_handle)

                        for item in p_origin_points:
                            v_origin = Vector(item)
                            if (v_mouse - v_origin).length < v_view_1px.length * ZUV_GGT_UVTransformGizmo.gizmo_snap_threshold_px:
                                v_snapped_view = v_origin
                                b_snap_by_origin_is_found = True
                                break

                    if tool_props.tr_gizmo_snap_to_gizmo_flip_point:
                        if not b_snap_by_origin_is_found:
                            v_init_cursor = Vector(tool_props.tr_gizmo_init_a_handle) - Vector(tool_props.tr_gizmo_init_p_handle)
                            v_init_cursor.negate()
                            v_init_cursor = Vector(tool_props.tr_gizmo_init_p_handle) + v_init_cursor
                            if (v_mouse - v_init_cursor).length < v_view_1px.length * ZUV_GGT_UVTransformGizmo.gizmo_snap_threshold_px:
                                v_snapped_view = v_init_cursor

                v_snapped_view_original = v_snapped_view.copy()

                # NOTE: if gizmo is restricted by axes we should restricted snapped position by initial axis value
                if self.gizmo_internal_axis_lock[0]:
                    v_snapped_view.x = self.init_cursor_location.x
                elif self.gizmo_internal_axis_lock[1]:
                    v_snapped_view.y = self.init_cursor_location.y

                if v_snapped_view != v_mouse:
                    p_gizmo_group.modal_data.snapped_point_region = Vector(rgn2d.view_to_region(*v_snapped_view_original[:], clip=False))

                    v_snapped = Vector(rgn2d.view_to_region(*v_snapped_view[:], clip=False))
                    fixed_cursor_location = v_snapped_view

                    if b_snap_by_mouse_or_2d_cursor:
                        v_mouse_rgn -= self.init_snap_base
                    delta = delta_base + (v_mouse_rgn - v_snapped).to_3d()

            # NOTE: we should finally correct gizmo by X, Y axes because it could be changed during snap
            if self.gizmo_internal_axis_lock[0]:
                delta.x = 0
            elif self.gizmo_internal_axis_lock[1]:
                delta.y = 0

            if 'PRECISE' in tweak:
                delta /= 10.0

            value = self.init_value - delta

            if not b_is_setup:
                rgn2d = context.region.view2d

                if fixed_cursor_location is None:
                    if delta.length != 0.0:
                        new_cursor = Vector(rgn2d.view_to_region(self.init_cursor_location.x, self.init_cursor_location.y, clip=False))
                        new_cursor -= delta.to_2d()
                        x, y = rgn2d.region_to_view(x=new_cursor.x, y=new_cursor.y)
                        fixed_cursor_location = Vector((x, y))

                if fixed_cursor_location is not None:
                    v_start = Vector(tool_props.tr_gizmo_angle_handle if tool_props.tr_gizmo_is_pivot else tool_props.tr_gizmo_pivot_handle)
                    v_end = Vector(fixed_cursor_location)

                    p_new_location: Vector = None

                    if tool_props.tr_gizmo_axes_lock == "PURE_ROTATION" and self.gizmo_rotate_with_step:
                        image_aspect_ratio = calc_uv_editor_image_aspect_ratio(context)
                        AM = matrix_by_image_aspect(image_aspect_ratio)

                        p_gizmo_data = ZuvGizmoOriginAndInitData()
                        p_gizmo_data.setup(context, tool_props)

                        def restrict_to_angle_step(origin_position, mouse_position, angle_step=5):
                            angle_step = math.radians(angle_step)
                            dynamic_gizmo_vector = AM @ (mouse_position - origin_position)
                            origin_gizmo_vector = AM @ p_gizmo_data.view_origin_vector

                            current_angle = dynamic_gizmo_vector.normalized().angle_signed(Vector((1, 0)), 0.0)
                            origin_angle = origin_gizmo_vector.normalized().angle_signed(Vector((1, 0)), 0.0)

                            rounded_angle = round(current_angle / angle_step) * angle_step
                            rounded_origin_angle = round(origin_angle / angle_step) * angle_step
                            difference_angle = origin_angle - rounded_origin_angle
                            rounded_angle += difference_angle
                            new_direction = AM.inverted() @ Vector((math.cos(rounded_angle), math.sin(rounded_angle)))
                            return origin_position + new_direction * dynamic_gizmo_vector.length

                        if ZUV_GGT_UVTransformGizmo.gizmo_dial_use_in_range:
                            d_gizmo_scale = p_gizmo_data.gizmo_scale

                            p_origin_loc_rgn = Vector(rgn2d.view_to_region(*v_start[:2], clip=False))

                            p_head_loc_rgn = Vector(rgn2d.view_to_region(*fixed_cursor_location[:2], clip=False))

                            min_dist = 0
                            max_dist = ZUV_GGT_UVTransformGizmo.gizmo_dial_outer_radius * d_gizmo_scale

                            b_is_in_range = min_dist <= (p_head_loc_rgn - p_origin_loc_rgn).length <= max_dist
                        else:
                            b_is_in_range = True
                        if b_is_in_range:
                            p_new_location = restrict_to_angle_step(
                                v_start, v_end, angle_step=ZUV_GGT_UVTransformGizmo.get_gizmo_dial_step_angle(tool_props))

                    if p_new_location is not None:
                        restrict_delta = p_new_location - fixed_cursor_location
                        if restrict_delta.length > 0.0:

                            p_new_loc_rgn = Vector(rgn2d.view_to_region(*p_new_location[:2], clip=False))
                            p_fixed_loc_rgn = Vector(rgn2d.view_to_region(*fixed_cursor_location[:2], clip=False))

                            value += (p_new_loc_rgn - p_fixed_loc_rgn).to_3d()

                            fixed_cursor_location = p_new_location

                    # NOTE: we need to fix height cursor 'jumpings'
                    if self.gizmo_internal_axis_lock[0]:
                        fixed_cursor_location.x = self.init_cursor_location.x
                    elif self.gizmo_internal_axis_lock[1]:
                        fixed_cursor_location.y = self.init_cursor_location.y

                    p_cursor_offset = fixed_cursor_location - Vector(tool_props.tr_gizmo_origin)
                    tool_props.tr_gizmo_origin = fixed_cursor_location[:2]
                    tool_props.update_cursor_location_in_uv(context)
                    if p_cursor_offset.length != 0.0:
                        if self.gizmo_type == 'LINE':
                            ZUV_GGT_UVTransformGizmo.zenuv_setup_transform_gizmo_line(
                                tool_props,
                                fixed_cursor_location, p_cursor_offset
                            )
                        else:
                            s_gizmo_id = 'tr_gizmo_pivot_handle' if tool_props.tr_gizmo_is_pivot else 'tr_gizmo_angle_handle'
                            ZUV_GGT_UVTransformGizmo.zenuv_setup_transform_gizmo(tool_props, s_gizmo_id, fixed_cursor_location)

            self.target_set_value("offset", value.to_tuple())

            if b_is_setup:
                if value[:] != (0.0, 0.0, 0.0):
                    res = bpy.ops.transform.translate(
                        'INVOKE_DEFAULT',
                        cursor_transform=True, release_confirm=True)
                    if 'RUNNING_MODAL' in res:
                        bpy.ops.uv.zenuv_tool_transform_setup_modal('INVOKE_DEFAULT')
                    res = {'PASS_THROUGH'}
                    # NOTE: this will terminate Gizmo modal mode !
            else:
                v_delta_view = Vector(tool_props.tr_gizmo_origin) - self.init_cursor_location

                from ZenUV.prop.wm_props import ZuvWMTransformToolGroup
                p_wm_tool: ZuvWMTransformToolGroup = wm.zen_uv.uv_transform_tool

                s_header_text = ""
                if self.gizmo_type == "SCALE_NON_PROP":
                    s_header_text = f"Scale: {p_wm_tool.scale_value:.2f} (Non-Uniform)"
                elif self.gizmo_type == "SCALE":
                    s_header_text = f"Scale: {p_wm_tool.scale_value:.2f}"
                elif self.gizmo_type == "ROTATE":
                    s_header_text = f"Rotation: {math.degrees(p_wm_tool.rotation_angle):.1f}°"
                elif b_is_line:
                    s_header_text = f"Dx: {v_delta_view.x:.4f}, Dy: {v_delta_view.y:.4f} ({value.x:.0f} px, {value.y:.0f} px)"
                    if tool_props.tr_gizmo_axes_lock == 'MOVE_ALONG_AXIS':
                        s_header_text += " along origin"
                else:
                    s_header_text = f"Rotation: {math.degrees(p_wm_tool.rotation_angle):.1f}°, Scale: {p_wm_tool.scale_value:.2f}"
                    if tool_props.tr_gizmo_axes_lock == 'SCALE_ALONG_AXIS':
                        s_header_text += " along origin"

                if self.gizmo_internal_axis_lock[0] or "AXIS_LOCK_MOVE_X" in tool_props.tr_gizmo_axes_lock:
                    s_header_text += " along Y"
                elif self.gizmo_internal_axis_lock[1] or "AXIS_LOCK_MOVE_Y" in tool_props.tr_gizmo_axes_lock:
                    s_header_text += " along X"

                b_is_snap_enabled = self.is_snap_enabled

                if b_is_snap_enabled:
                    s_header_text += " with snap"

                context.area.header_text_set(s_header_text)

                z_axis = 'Lock Axis'
                if b_is_line or b_is_a_handle or b_is_p_handle:
                    b_is_x_y_lock_enabled = any(self.gizmo_internal_axis_lock)
                    if b_is_line:
                        b_need_to_lock = b_is_x_y_lock_enabled or tool_props.tr_gizmo_axes_lock != 'MOVE_ALONG_AXIS'
                        z_axis = "Lock Axis" if b_need_to_lock else "Unlock Axis"
                    else:
                        b_need_to_lock = b_is_x_y_lock_enabled or tool_props.tr_gizmo_axes_lock != 'SCALE_ALONG_AXIS'
                        z_axis = "Lock Axis" if b_need_to_lock else "Unlock Axis"

                step_rotation = None
                if b_is_rotation:
                    step_rotation = self.gizmo_rotate_with_step

                from ZenUV.ui.tool.tool_ops import zenuv_status_text_transform_draw
                context.workspace.status_text_set(
                    lambda self, context: zenuv_status_text_transform_draw(
                        self, context, b_is_snap_enabled,
                        precision_mode=True, z_axis=z_axis, step_rotation=step_rotation)
                )

            context.area.tag_redraw()

            self.last_update = timer()
        return res

    def setup(self):
        if not hasattr(self, "init_mtx_world"):
            self.init_mtx_world = Matrix()
            self.last_update = 0
            self.init_snap_base = Vector((0, 0))
            self.init_cursor_location = Vector((0, 0))
            self._last_click = 0
            self.gizmo_type = ""
            self.is_snap_enabled = False
            self.gizmo_internal_axis_lock = (False, False)
            self.gizmo_rotate_with_step = False
            self.init_operator_transform_data = {}

            self.line_width = 1
            self.border_size = 2  # px: value for one side
            self.corner = 2
            self.rect_side = 4
            self._do_setup_custom_line_shape()
            self._do_setup_custom_dashed_line_shape()

    def _do_setup_custom_line_shape(self):
        if ZenPolls.version_lower_3_4_0:
            shader_line = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        else:
            if ZenPolls.version_lower_3_5_0:
                shader_line = gpu.shader.from_builtin('2D_POLYLINE_UNIFORM_COLOR')
            else:
                shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

        self.custom_shape = [None, shader_line]

        coords = [Vector((0, 0)), Vector((1, 1))]

        self.custom_shape[0] = batch_for_shader(
            shader_line, 'LINES',
            {
                "pos": coords,
            }
        )
        self.custom_shape[0].program_set(shader_line)

    def _do_setup_custom_dashed_line_shape(self):
        shader_dashed_line = get_dashed_shader_line_2()

        self.custom_dashed_line_shape = [None, shader_dashed_line]

        if ZenPolls.version_lower_3_4_0:
            coords = [[0.0] * 2, [1.0] * 2]
            self.custom_dashed_line_shape[0] = batch_for_shader(
                shader_dashed_line, 'LINES',
                {
                    "pos": coords,
                }
            )
        else:
            coords = [[0.0] * 3, [1.0] * 3]
            self.custom_dashed_line_shape[0] = batch_for_shader(
                shader_dashed_line, 'LINES',
                {
                    "pos": coords
                }
            )
        self.custom_dashed_line_shape[0].program_set(shader_dashed_line)

    def _do_invoke(self: bpy.types.Gizmo, context: bpy.types.Context, event: bpy.types.Event, tool_props: ZUV_UVToolProps):
        p_gizmo_group: ZUV_GGT_UVTransformGizmo = self.group
        p_gizmo_group.active_gizmo = self
        p_gizmo_group.unregister_tooltip()
        p_gizmo_group.cancel_setup_by_selection()
        p_gizmo_group.init_invoke_a_handle_mtx = p_gizmo_group.mpr_handle.matrix_world.copy()
        p_gizmo_group.init_invoke_p_handle_mtx = p_gizmo_group.mpr_pivot.matrix_world.copy()
        p_gizmo_group.modal_data.clear()

        tool_props.tr_gizmo_display_xy_guidelines = (False, False)

        self._last_click = timer()
        self.is_snap_enabled = False
        self.gizmo_internal_axis_lock = (False, False)
        self.gizmo_rotate_with_step = False
        self.init_operator_transform_data.clear()

        rgn2d = context.region.view2d

        b_is_pivot = tool_props.tr_gizmo_is_pivot

        # NOTE: this is reposition section, when 2D cursor must be repositioned by the place where it was clicked
        if isinstance(self, (UV_GT_zenuv_transform_pivot, UV_GT_zenuv_transform_a_handle, UV_GT_zenuv_rotate_handle, UV_GT_zenuv_scale_handle)):
            v_origin = Vector(rgn2d.region_to_view(x=self.matrix_world.translation.x, y=self.matrix_world.translation.y))
            v_origin_offset = v_origin - Vector(tool_props.tr_gizmo_origin)

            v_1px = get_view_1px_from_region(context, Vector((event.mouse_region_x, event.mouse_region_y)))
            # NOTE: we understand that gizmo was re-assigned
            if v_origin_offset.length > v_1px.length:
                if b_is_pivot:
                    tool_props.tr_gizmo_origin = tool_props.get_tr_gizmo_pivot_handle_internal()
                else:
                    tool_props.tr_gizmo_origin = tool_props.get_tr_gizmo_angle_handle_internal()

            if b_is_pivot:
                tool_props.set_tr_gizmo_pivot_handle(tool_props.tr_gizmo_origin[:])
            else:
                tool_props.set_tr_gizmo_angle_handle(tool_props.tr_gizmo_origin[:])

            tool_props.update_cursor_location_in_uv(context)

        # NOTE: this operation must be called after cursor installation!
        if tool_props.tr_gizmo_mode == 'TRANSFORM':

            # 1) Nothing Selected
            from ZenUV.utils.selection_utils import SelectionProcessor
            if not SelectionProcessor.is_uv_selected(context):
                show_message_box(message="Select something!", title="WARNING", icon="ERROR")
                return {'FINISHED'}

            # 2) Pivot in falloff
            is_block_handle = tool_props.tr_gizmo_transform_editing_mode in {"LINEAR_FALLOFF", "RADIAL_FALLOFF"}
            if is_block_handle:
                if self.gizmo_type in {'PIVOT_HANDLE', 'LINE'}:
                    show_message_box(message="Locked in Falloff Mode!", title="WARNING", icon="ERROR")
                    return {'FINISHED'}

        self.init_mouse = Vector((event.mouse_x, event.mouse_y, 0.0))
        self.init_cursor_location = Vector(tool_props.tr_gizmo_origin)

        v_cursor_rgn = Vector(rgn2d.view_to_region(*tool_props.tr_gizmo_origin[:2], clip=False))
        self.init_mouse_region = Vector((event.mouse_region_x, event.mouse_region_y))
        self.init_snap_base = self.init_mouse_region - v_cursor_rgn
        self.init_value = Vector(self.target_get_value("offset"))
        self.init_mtx_world = self.matrix_world.copy()
        self.last_update = 0

        tool_props.tr_gizmo_undo_push(commit_in_blender=True)

        if tool_props.tr_gizmo_mode == 'TRANSFORM':

            from ZenUV.ui.tool.tool_ops import ZUV_OP_ToolTransform
            wm = context.window_manager
            op_transform = None
            op_transform_last = None

            if wm.operators:
                op = wm.operators[-1]
                if isinstance(op, ZUV_OP_ToolTransform):
                    op_transform_last = op

            if tool_props.tr_gizmo_active:
                if op_transform_last is not None and p_gizmo_group.origin_gizmo == self:
                    op_transform = op_transform_last

            if op_transform is None and op_transform_last is not None:
                # NOTE: in this case island can be possibly scaled to 0
                if (op.matched_pivot - op.matched_head).length <= 1e-6:
                    tool_props.tr_gizmo_active = True
                    p_gizmo_group.origin_gizmo = self
                    op_transform = op_transform_last

            # NOTE: snap history is invalid or reseted, we are calling new operator:
            if op_transform is None:
                tool_props.tr_gizmo_active = True
                p_gizmo_group.origin_gizmo = self

                from ..tool_ops import ZuvTransformGizmoAxisLockPreset
                p_axis_lock = ZuvTransformGizmoAxisLockPreset()
                p_axis_lock.setup_by_gizmo_lock(tool_props.tr_gizmo_axes_lock)

                op_last = wm.operator_properties_last(ZUV_OP_ToolTransform.bl_idname)
                if op_last:
                    reset_properties_modified(op_last)

                bpy.ops.uv.zenuv_tool_transform(
                    'INVOKE_DEFAULT',
                    True,
                    origin_pivot=tool_props.tr_gizmo_pivot_handle[:],
                    origin_head=tool_props.tr_gizmo_angle_handle[:],

                    matched_pivot=tool_props.tr_gizmo_pivot_handle[:],
                    matched_head=tool_props.tr_gizmo_angle_handle[:],

                    is_pivot=b_is_pivot,
                    is_gizmo_initialization=True,

                    match_pos=p_axis_lock.match_pos,
                    match_rotation=p_axis_lock.match_rotation,
                    match_scale=p_axis_lock.match_scale,
                    lock_scale_axis=p_axis_lock.lock_scale_axis,
                    lock_position_axis=p_axis_lock.lock_position_axis,

                    influence=tool_props.tr_gizmo_influence
                    )

                if wm.operators:
                    op = wm.operators[-1]
                    if isinstance(op, ZUV_OP_ToolTransform):
                        op_transform = op
            else:
                pass

            if op_transform is not None:
                t_operators = bpy.app.driver_namespace.get(LITERAL_TR_GIZMO_OPERATORS, dict())
                t_operators[str(op_transform.as_pointer())] = context.copy()
                bpy.app.driver_namespace[LITERAL_TR_GIZMO_OPERATORS] = t_operators

                self.init_operator_transform_data.clear()

                properties_blacklist = set(bpy.types.Operator.bl_rna.properties.keys())

                properties_blacklist.add("origin_head")
                properties_blacklist.add("origin_pivot")
                properties_blacklist.add("is_gizmo_initialization")
                properties_blacklist.add("info_message")

                prop: bpy.types.Property
                for prop_id, prop in op_transform.properties.bl_rna.properties.items():
                    if prop_id not in properties_blacklist and not prop.is_readonly:
                        p_value = getattr(op_transform, prop_id)
                        is_array = getattr(prop, "is_array", False)
                        if is_array:
                            if prop.subtype == 'MATRIX':
                                p_value = p_value.copy()
                            else:
                                p_value = p_value[:]
                        self.init_operator_transform_data[prop_id] = p_value
            else:
                Log.error("INVOKE TRANSFORM GIZMO: Can not set transform operator!")
                return {'CANCELLED'}

            p_origin_list: dict = bpy.app.driver_namespace.get("zenuv_tr_gizmo_origin_list", dict())
            p_origin_list[tool_props.tr_gizmo_line[:]] = b_is_pivot
            bpy.app.driver_namespace["zenuv_tr_gizmo_origin_list"] = p_origin_list

            context.window.cursor_modal_set('SCROLL_XY')

        return {'RUNNING_MODAL'}

    def _draw_label(self: bpy.types.Gizmo, font_size, position: Vector, text_color: tuple, ui_scale: float, text: str):
        ZenCompat.blf_font_size(font_size, ui_scale)
        blf.color(0, *text_color, 1)
        w, h = blf.dimensions(0, text)
        blf.position(0, position.x - w/2, position.y - h/2, 0)
        blf.draw(0, text)

    def test_select(self: bpy.types.Gizmo, context: bpy.types.Context, location):

        res = self.test_select_internal(context, location)
        if res == 0:
            p_group: ZUV_GGT_UVTransformGizmo = self.group
            p_group.unregister_tooltip()

            if not self.is_modal:
                p_group.register_tooltip(context, self, location)

        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        if tool_props.tr_gizmo_event_mode == 'EVENT_MOVE':
            res = 0 if self.gizmo_type == 'LINE' else -1
        elif tool_props.tr_gizmo_event_mode == 'EVENT_ROTATE':
            res = 0 if self.gizmo_type == 'ROTATE' else -1
        elif tool_props.tr_gizmo_event_mode == 'EVENT_SCALE':
            res = 0 if self.gizmo_type == 'SCALE' else -1

        return res


class ZuvTransformGizmoMainHandles(ZuvTransformGizmoBase):

    def do_draw_box_handle(self, context: bpy.types.Context, matrix: Matrix, is_cross=False):
        if is_cross:
            mtx_box = matrix @ (Matrix.Translation(Vector()) @ Matrix.Diagonal(Vector((1.5, 0.05, 0))).to_4x4())
            self.draw_preset_box(matrix=mtx_box)

            mtx_box = matrix @ (Matrix.Translation(Vector()) @ Matrix.Diagonal(Vector((0.05, 1.5, 0))).to_4x4())
            self.draw_preset_box(matrix=mtx_box)

        self.draw_preset_circle(matrix)
        # NOTE: 1-pixel dot
        mtx = Matrix.Translation(matrix.to_translation()) @ Matrix.Diagonal((1.0, 1.0, 1.0)).to_4x4()
        self.draw_preset_box(mtx)

    def test_select_internal(self, context: bpy.types.Context, location):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils

        v_pos = self.matrix_world.to_translation()

        ui_scale = context.preferences.system.ui_scale
        d_gizmo_size = context.preferences.view.gizmo_size * self.scale_basis
        left = v_pos.x - d_gizmo_size * ui_scale
        right = v_pos.x + d_gizmo_size * ui_scale
        bottom = v_pos.y - d_gizmo_size * ui_scale
        top = v_pos.y + d_gizmo_size * ui_scale

        if ZuvTrimsheetUtils.pointInRect(location, left, top, right, bottom):
            return 0

        return -1

    def setup(self):
        super().setup()
        # NOTE: must be called only once
        if not hasattr(self, 'gizmo_type'):
            self.gizmo_type = "ANGLE_HANDLE"

    def _update_offset_matrix(self):
        v_pos = Vector(self.target_get_value("offset"))
        self.matrix_offset = Matrix.Translation(v_pos)

    def invoke(self, context, event: bpy.types.Event):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        tool_props.set_gizmo_type_and_synchronize_cursor_2d(context, {self.gizmo_type})
        tool_props.tr_gizmo_axes_lock = 'NONE'

        return self._do_invoke(context, event, tool_props)


class UV_GT_zenuv_transform_a_handle(bpy.types.Gizmo, ZuvTransformGizmoMainHandles):
    bl_idname = "UV_GT_zenuv_transform_a_handle"
    bl_target_properties = (
        {"id": "offset", "type": 'FLOAT', "array_length": 3},
    )

    __slots__ = (
        "custom_shape",
        "custom_dashed_line_shape",

        "init_mouse",
        "init_value",
        "init_mtx_world",
        "init_snap_base",
        "init_cursor_location",

        "gizmo_type",
        "last_update",
    )

    def draw(self, context: bpy.types.Context):
        self._update_offset_matrix()

        was_color = self.color.copy()

        self.color = self.color_highlight if self.is_highlight else was_color

        self.do_draw_box_handle(context, self.matrix_world)

        self.color = was_color


class UV_GT_zenuv_transform_pivot(bpy.types.Gizmo, ZuvTransformGizmoMainHandles):
    bl_idname = "UV_GT_zenuv_transform_pivot"
    bl_target_properties = UV_GT_zenuv_transform_a_handle.bl_target_properties

    __slots__ = UV_GT_zenuv_transform_a_handle.__slots__

    def draw_falloff(self, context: bpy.types.Context, gizmo_data: ZuvGizmoOriginAndInitData):
        tool_props = gizmo_data.tool_props
        d_gizmo_scale = gizmo_data.gizmo_scale

        if tool_props.tr_gizmo_transform_editing_mode == 'RADIAL_FALLOFF':
            gpu.state.line_width_set(1.0)

            gizmo_vec = gizmo_data.gizmo_vector_rgn

            if gizmo_vec.magnitude:
                draw_circle_2d(gizmo_data.gizmo_p_handle_rgn, (*ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR, 1), gizmo_vec.magnitude, segments=100)

        elif tool_props.tr_gizmo_transform_editing_mode == 'LINEAR_FALLOFF':
            was_color = self.color.copy()
            was_highlight = self.color_highlight.copy()
            was_alpha = self.alpha
            was_alpha_highlight = self.alpha_highlight

            self.color = ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR
            self.color_highlight = ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR
            self.alpha = 1.0
            self.alpha_highlight = 1.0

            cone_angle = 10 * d_gizmo_scale  # degrees

            a_handle = gizmo_data.gizmo_a_handle_rgn
            p_handle = gizmo_data.gizmo_p_handle_rgn
            gizmo_vec = gizmo_data.gizmo_vector_rgn
            gizmo_orth = gizmo_data.gizmo_orthogonal_direction_rgn

            angle_radians = math.radians(cone_angle)
            base_length = gizmo_vec.length * math.tan(angle_radians)
            v_orth = gizmo_orth * base_length

            v_scale_left = (a_handle + v_orth) - p_handle
            v_scale_right = (a_handle - v_orth) - p_handle

            v_cap_vec = v_scale_right - v_scale_left
            v_cap_root = p_handle + v_scale_left
            v_scale_cap = v_cap_vec

            _, shader = self.custom_shape

            shader.bind()

            gpu.state.blend_set('ALPHA')

            if not ZenPolls.version_lower_3_4_0:
                shader.uniform_float('viewportSize', (context.region.width, context.region.height))
                shader.uniform_float('lineWidth', 1)

            mtx_left = Matrix.Translation(p_handle.resized(3)) @ Matrix.Diagonal((v_scale_left.x, v_scale_left.y, 0)).to_4x4()
            self.draw_custom_shape(self.custom_shape, matrix=mtx_left, select_id=None)

            mtx_right = Matrix.Translation(p_handle.resized(3)) @ Matrix.Diagonal((v_scale_right.x, v_scale_right.y, 0)).to_4x4()
            self.draw_custom_shape(self.custom_shape, matrix=mtx_right, select_id=None)

            mtx_cap = Matrix.Translation(v_cap_root.resized(3)) @ Matrix.Diagonal((v_scale_cap.x, v_scale_cap.y, 0)).to_4x4()
            self.draw_custom_shape(self.custom_shape, matrix=mtx_cap, select_id=None)

            gpu.state.blend_set('NONE')

            self.color = was_color
            self.color_highlight = was_highlight
            self.alpha = was_alpha
            self.alpha_highlight = was_alpha_highlight

    def draw_snap_dial(self, context: bpy.types.Context, gizmo_data: ZuvGizmoOriginAndInitData):
        tool_props = gizmo_data.tool_props
        b_is_setup = tool_props.tr_gizmo_mode == 'SETUP'
        if b_is_setup:
            return

        b_rotate_with_step = False
        p_gizmo_group: ZUV_GGT_UVTransformGizmo = self.group
        if p_gizmo_group.active_gizmo:
            b_rotate_with_step = p_gizmo_group.active_gizmo.gizmo_rotate_with_step

        b_active = 'ROTATE' in tool_props.tr_gizmo_type

        if not b_active:
            return

        image_aspect_ratio = calc_uv_editor_image_aspect_ratio(context)
        AM = matrix_by_image_aspect(image_aspect_ratio)

        dial_in_range_active_color = p_gizmo_group.gizmo_colors.main_handles.copy()

        _, shader = self.custom_shape

        shader.bind()

        gpu.state.blend_set('ALPHA')

        v_origin_vec = AM @ gizmo_data.view_origin_vector
        start_angle = v_origin_vec.normalized().angle_signed(Vector((1, 0)))

        angle_correction_matrix = Matrix.Rotation(start_angle, 4, 'Z')

        p_handle = Vector(tool_props.tr_gizmo_pivot_handle)
        a_handle = Vector(tool_props.tr_gizmo_angle_handle)

        gizmo_vector = a_handle - p_handle
        gizmo_vector_reg = gizmo_data.gizmo_vector_rgn.copy()

        to_position_matrix = Matrix.Translation(gizmo_data.gizmo_p_handle_rgn.resized(3))

        d_gizmo_scale = gizmo_data.gizmo_scale

        angle_step = ZUV_GGT_UVTransformGizmo.get_gizmo_dial_step_angle(tool_props)
        num_points = 360 // angle_step

        p_dial_vectors = CustomShapes.get_dial_vectors(
            num_points,
            ZUV_GGT_UVTransformGizmo.gizmo_dial_inner_radius,
            ZUV_GGT_UVTransformGizmo.gizmo_dial_outer_radius,
            ui_scale=d_gizmo_scale,
            modification_pattern=[],  # [] mean auto generated pattern
            mode_1_length_mult=0.65,  # length percentage 0-1
            mode_1_attributes=[1, False],  # [line_width, hide]
            mode_0_length_mult=0.3,  # length percentage 0-1
            mode_0_attributes=[1, False],  # [line_width, hide]
            b_shorten_from_inside=True,
            b_append_angle_in_attributes=True
        )

        if ZUV_GGT_UVTransformGizmo.gizmo_dial_use_in_range:
            min_dist = 0
            max_dist = ZUV_GGT_UVTransformGizmo.gizmo_dial_outer_radius * d_gizmo_scale

            b_is_in_range = b_rotate_with_step and (
                min_dist <=
                gizmo_vector_reg.length <=
                max_dist)
        else:
            b_is_in_range = b_rotate_with_step

        if not ZenPolls.version_lower_3_4_0:
            shader.uniform_float('viewportSize', gpu.state.viewport_get()[2:])
            line_width = 2.0 if b_is_in_range else 0.5
            shader.uniform_float('lineWidth', line_width)

        gizmo_vector = AM @ gizmo_vector
        current_angle = gizmo_vector.normalized().angle_signed(v_origin_vec.normalized(), 0.0)

        if math.isclose(current_angle, 0, abs_tol=1e-6):
            current_angle = 0

        if p_gizmo_group.modal_data.rotate_previous_angle is None:
            p_gizmo_group.modal_data.rotate_previous_angle = current_angle
            p_gizmo_group.modal_data.rotate_accumuluate_angle = current_angle

        delta_angle = current_angle - p_gizmo_group.modal_data.rotate_previous_angle

        if delta_angle > math.pi:
            delta_angle -= 2 * math.pi
        elif delta_angle < -math.pi:
            delta_angle += 2 * math.pi

        p_gizmo_group.modal_data.rotate_accumuluate_angle += delta_angle
        p_gizmo_group.modal_data.rotate_previous_angle = current_angle

        p_active_color = p_gizmo_group.gizmo_colors.rotate_handle_highlight.copy()

        if p_gizmo_group.modal_data.rotate_accumuluate_angle > 0:
            colors = [p_active_color, dial_in_range_active_color]
        elif p_gizmo_group.modal_data.rotate_accumuluate_angle < 0:
            colors = [dial_in_range_active_color, p_active_color]
        else:
            colors = [dial_in_range_active_color, dial_in_range_active_color]

        for v in p_dial_vectors:
            self.color = colors[1]
            v_start_position = v[0]
            v_end_position = v[1] - v[0]
            point_angle = round((v[2][2] + start_angle) % (2 * math.pi), 5)

            mtx = Matrix.Translation(v_start_position) @ Matrix.Diagonal(v_end_position).to_4x4()

            relative_start = start_angle % (2 * math.pi)
            relative_end = round((start_angle + p_gizmo_group.modal_data.rotate_accumuluate_angle) % (2 * math.pi), 5)

            if relative_end < relative_start:
                if point_angle >= relative_start or point_angle <= relative_end:
                    self.color = colors[0]
            else:
                if relative_start <= point_angle <= relative_end:
                    self.color = colors[0]
            if v[2][2] == 0.0:
                self.color = p_active_color

            self.draw_custom_shape(self.custom_shape, matrix=to_position_matrix @ angle_correction_matrix @ mtx)

        gpu.state.blend_set('NONE')

    def draw_snapped_point(self):
        p_gizmo_group: ZUV_GGT_UVTransformGizmo = self.group
        if p_gizmo_group.modal_data.snapped_point_region is not None:
            self.color = (1, 1, 1)
            mtx_window_sca = Matrix.Diagonal(self.matrix_world.to_scale()).to_4x4()
            mtx_scale_smaller = Matrix.Diagonal((0.5, 0.5, 0.0)).to_4x4()
            mtx = Matrix.Translation(p_gizmo_group.modal_data.snapped_point_region.resized(3)) @ mtx_scale_smaller @ mtx_window_sca
            self.draw_preset_circle(mtx)

    def draw(self, context: bpy.types.Context):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        rgn2d = context.region.view2d
        ui_scale = context.preferences.system.ui_scale
        bl_theme = context.preferences.themes[0].user_interface
        text_color = bl_theme.wcol_tooltip.text[:3]

        p_gizmo_data = ZuvGizmoOriginAndInitData()
        p_gizmo_data.setup(context, tool_props)

        addon_prefs = get_prefs()

        self._update_offset_matrix()

        was_color = self.color.copy()

        b_is_setup_mode = tool_props.tr_gizmo_mode == 'SETUP'

        DEBUG_P_A_HANDLES_INFO = False

        if not b_is_setup_mode:
            if tool_props.tr_gizmo_active:
                from ..tool_ops import ZUV_OP_ToolTransform
                op = ZUV_OP_ToolTransform.get_active_operator(context)
                if op is not None:
                    p_origin_list: dict = bpy.app.driver_namespace.get("zenuv_tr_gizmo_origin_list", dict())

                    ui_scale = context.preferences.system.ui_scale

                    mtx_window_sca = Matrix.Diagonal(self.matrix_world.to_scale()).to_4x4()
                    mtx_scale_smaller = Matrix.Diagonal((0.25, 0.25, 0.0)).to_4x4()

                    d_gizmo_size = context.preferences.view.gizmo_size
                    d_gizmo_size *= ui_scale
                    px_above_gizmo_top = 3 * ui_scale
                    d_gizmo_size = d_gizmo_size * 0.2 * 0.25
                    d_digits_offset_px = d_gizmo_size + px_above_gizmo_top

                    p_font_size = 8

                    p_handled_points = set()

                    self.color = ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR

                    n_origin_list_count = len(p_origin_list)
                    for idx, item in enumerate(reversed(p_origin_list.keys())):
                        p_pivot = item[0:2]
                        p_angle = item[2:4]

                        v_pivot_rgn = Vector(rgn2d.view_to_region(*p_pivot[:], clip=False))
                        v_angle_rgn = Vector(rgn2d.view_to_region(*p_angle[:], clip=False))

                        v_pivot_rgn.resize_3d()
                        v_angle_rgn.resize_3d()

                        mtx_pivot = Matrix.Translation(v_pivot_rgn) @ mtx_scale_smaller @ mtx_window_sca
                        self.do_draw_box_handle(context, mtx_pivot, is_cross=True)

                        mtx_angle = Matrix.Translation(v_angle_rgn) @ mtx_scale_smaller @ mtx_window_sca
                        self.do_draw_box_handle(context, mtx_angle, is_cross=False)

                        if n_origin_list_count > 1:
                            def _draw_origin(mtx: Matrix):
                                index_number = n_origin_list_count - idx

                                if index_number > 1:
                                    ZenCompat.blf_font_size(p_font_size, ui_scale)
                                    blf.color(0, *text_color, 1)
                                    v_pos = mtx.to_translation()
                                    s_text = str(index_number)
                                    w, _ = blf.dimensions(0, s_text)

                                    blf.position(0, v_pos.x - w/2, v_pos.y + d_digits_offset_px, 0)
                                    blf.draw(0, s_text)

                            if p_pivot not in p_handled_points:
                                p_handled_points.add(p_pivot)
                                _draw_origin(mtx_pivot)

                            if p_angle not in p_handled_points:
                                p_handled_points.add(p_angle)
                                _draw_origin(mtx_angle)

                    v_init_cursor = Vector(op.origin_head) - Vector(op.origin_pivot)
                    v_init_cursor.negate()
                    v_init_cursor = Vector(op.origin_pivot) + v_init_cursor

                    v_init_cursor = Vector(rgn2d.view_to_region(*v_init_cursor[:], clip=False))
                    v_init_cursor.resize_3d()

                    mtx = Matrix.Translation(v_init_cursor) @ mtx_window_sca
                    self.do_draw_box_handle(context, mtx)

                    ZenCompat.blf_font_size(10, ui_scale)
                    blf.color(0, *text_color, 1)
                    v_pos = mtx.to_translation()
                    w, h = blf.dimensions(0, "F")
                    blf.position(0, v_pos.x - w/2, v_pos.y - h/2, 0)
                    blf.draw(0, "F")

                    if DEBUG_P_A_HANDLES_INFO:
                        self.color = (1, 0, 0)
                    v_origin_pivot_rgn = Vector(rgn2d.view_to_region(*op.origin_pivot[:], clip=False))
                    v_origin_pivot_rgn.resize_3d()
                    mtx = Matrix.Translation(v_origin_pivot_rgn) @ mtx_window_sca @ Matrix.Diagonal((0.25, 0.25, 0.0)).to_4x4()
                    self.do_draw_box_handle(context, mtx, is_cross=True)
                    if DEBUG_P_A_HANDLES_INFO and op.is_pivot:
                        ZenCompat.blf_font_size(p_font_size, ui_scale)
                        blf.color(0, *self.color[:], 1)
                        v_pos = mtx.to_translation()
                        w, h = blf.dimensions(0, "P")
                        blf.position(0, v_pos.x - w/2, v_pos.y + h, 0)
                        blf.draw(0, "P")

                    if DEBUG_P_A_HANDLES_INFO:
                        self.color = (0, 1, 0)
                    v_origin_head_rgn = Vector(rgn2d.view_to_region(*op.origin_head[:], clip=False))
                    v_origin_head_rgn.resize_3d()
                    mtx = Matrix.Translation(v_origin_head_rgn) @ mtx_window_sca @ Matrix.Diagonal((0.25, 0.25, 0.0)).to_4x4()
                    self.do_draw_box_handle(context, mtx)
                    if DEBUG_P_A_HANDLES_INFO and not op.is_pivot:
                        ZenCompat.blf_font_size(p_font_size, ui_scale)
                        blf.color(0, *self.color[:], 1)
                        v_pos = mtx.to_translation()
                        w, h = blf.dimensions(0, "A")
                        blf.position(0, v_pos.x - w/2, v_pos.y + h, 0)
                        blf.draw(0, "A")

        self.color = ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR

        from .uv_base import ZuvUVGizmoBase
        # NOTE: we are drawing initial position that was present at the start of movement
        p_gizmo_group: ZUV_GGT_UVTransformGizmo = self.group
        if p_gizmo_group.modal_data.is_modal:
            if ZuvUVGizmoBase.are_gizmos_modal(p_gizmo_group):
                if tool_props.tr_gizmo_is_pivot:
                    self.do_draw_box_handle(context, p_gizmo_group.init_invoke_p_handle_mtx)
                else:
                    self.do_draw_box_handle(context, p_gizmo_group.init_invoke_a_handle_mtx)

                self.draw_snapped_point()

            self.draw_snap_dial(context, p_gizmo_data)

        self.draw_guidelines(context, p_gizmo_data)

        self.draw_falloff(context, p_gizmo_data)

        self.color = self.color_highlight if self.is_highlight else was_color

        is_cross = tool_props.tr_gizmo_transform_editing_mode in {"LINEAR_FALLOFF", "RADIAL_FALLOFF"} and tool_props.tr_gizmo_mode == 'TRANSFORM'
        self.do_draw_box_handle(context, self.matrix_world, is_cross=is_cross)

        self.color = was_color

        # NOTE: text must be drawn at the end
        if 'HANDLE_NAME' in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state:
            d_gizmo_size = context.preferences.view.gizmo_size
            radius = d_gizmo_size * 0.2 * ui_scale

            p_handled_rects = dict()

            ZenCompat.blf_font_size(ZUV_GGT_UVTransformGizmo.gizmo_label_text_size, ui_scale)

            TEXT_OFFSET = 2

            def create_text_rect(pos: Vector, s_identifier: str, hor_align: str = 'center', s_label_name: str = ''):
                if not s_label_name:
                    s_label_name = bpy.types.UILayout.enum_item_name(tool_props, "tr_gizmo_type", s_identifier)
                w, h = blf.dimensions(0, s_label_name)

                if hor_align == 'left':
                    left = pos.x
                    top = pos.y + h / 2
                    right = pos.x + w
                    bottom = pos.y - h / 2
                elif hor_align == 'right':
                    left = pos.x - w
                    top = pos.y + h / 2
                    right = pos.x
                    bottom = pos.y - h / 2
                else:
                    left = pos.x - w / 2
                    top = pos.y + h / 2
                    right = pos.x + w / 2
                    bottom = pos.y - h / 2

                p_rect = TextRect(
                    left, top, right, bottom,
                    name=s_label_name,
                    color=(*text_color, 1))

                while any(p_rect.intersects(r) for r in p_handled_rects.keys()):
                    p_rect.top += TEXT_OFFSET
                    p_rect.bottom += TEXT_OFFSET

                p_handled_rects[p_rect] = None

            v_pos_mtx = self.matrix_world.to_translation()
            v_pos = v_pos_mtx.copy()
            v_pos.y -= ZUV_GGT_UVTransformGizmo.gizmo_align_outer_radius * ui_scale - radius
            v_pos.y -= radius + 10 * ui_scale
            create_text_rect(v_pos, 'PIVOT_HANDLE')

            v_pos = v_pos_mtx.copy()
            v_pos.x += ZUV_GGT_UVTransformGizmo.gizmo_align_outer_radius * ui_scale + radius
            v_pos.x += radius * 0.75
            v_pos.y += ZUV_GGT_UVTransformGizmo.gizmo_align_outer_radius * ui_scale - radius
            v_pos.y += radius * 0.75
            create_text_rect(v_pos, '', s_label_name="Align Handles")

            v_scale = self.group.mpr_line.end - self.group.mpr_line.start

            v_pos = self.group.mpr_line.start + v_scale / 2
            create_text_rect(v_pos, 'LINE')

            v_scale += Vector((radius + 10 * ui_scale, 0))
            v_pos = self.group.mpr_line.start + v_scale
            create_text_rect(v_pos, 'ANGLE_HANDLE', hor_align='left')

            if not self.group.mpr_handle_rotate.hide:
                v_scale = self.group.mpr_handle_rotate.end - self.group.mpr_handle_rotate.start
                v_pos = self.group.mpr_handle_rotate.start + v_scale - Vector((10 * ui_scale, 0))
                create_text_rect(v_pos, 'ROTATE', hor_align='right')

            if not self.group.mpr_handle_scale.hide:
                v_scale = self.group.mpr_handle_scale.end - self.group.mpr_handle_scale.start
                v_pos = self.group.mpr_handle_scale.start + v_scale + Vector((10 * ui_scale, 0))
                create_text_rect(v_pos, 'SCALE', hor_align="left")

            if not self.group.mpr_handle_scale_no_proportion.hide:
                v_scale = self.group.mpr_handle_scale_no_proportion.end - self.group.mpr_handle_scale_no_proportion.start
                v_pos = self.group.mpr_handle_scale_no_proportion.start + v_scale + Vector((10 * ui_scale, 0))
                create_text_rect(v_pos, 'SCALE_NON_PROP', hor_align="left")

            for k in p_handled_rects.keys():
                k.draw_text()

    def draw_guidelines(self, context: bpy.types.Context, gizmo_data: ZuvGizmoOriginAndInitData):
        tool_props = gizmo_data.tool_props

        b_xy_enabled = any(tool_props.tr_gizmo_display_xy_guidelines[:])

        b_is_transform = tool_props.tr_gizmo_mode == 'TRANSFORM'
        if b_is_transform or b_xy_enabled:

            from .uv_base import ZuvUVGizmoBase
            if not b_xy_enabled and not ZuvUVGizmoBase.are_gizmos_modal(self.group):
                return

            addon_prefs = get_prefs()
            b_hide_guides = (
                not b_is_transform or
                'GUIDLINES' not in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state)

            b_is_x_y_lock_enabled = (
                b_xy_enabled or
                (b_is_transform and tool_props.tr_gizmo_axes_lock in {
                    'PURE_ROTATION',
                    'AXIS_LOCK_MOVE_X', 'AXIS_LOCK_MOVE_Y',
                    'SCALE_ALONG_AXIS', 'SCALE_ALONG_AXIS_NO_PROPORTION', 'MOVE_ALONG_AXIS'}))

            if b_hide_guides and not b_is_x_y_lock_enabled:
                return

            p_gizmo_group: ZUV_GGT_UVTransformGizmo = self.group

            d_gizmo_scale = get_gizmo_scale(context)

            was_color = self.color.copy()
            was_highlight_color = self.color_highlight.copy()
            was_alpha = self.alpha
            was_alpha_highlight = self.alpha_highlight

            self.color = ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR
            self.color_highlight = ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR
            self.alpha = 0.5
            self.alpha_highlight = 0.5

            viewport_size = Vector((context.region.width, context.region.height))
            bottom_left = Vector((0, 0))
            top_left = Vector((0, viewport_size.y))
            top_right = Vector((viewport_size.x, viewport_size.y))
            bottom_right = Vector((viewport_size.x, 0))

            offset = Vector((0, 0))
            viewport_rect = (
                [bottom_left - offset, top_left - Vector((1, -1))],
                [top_left - Vector((-1, 1)), top_right + Vector((1, 1))],
                [top_right + Vector((1, 1)), bottom_right + offset],
                [bottom_right + Vector((1, -1)), bottom_left - offset]
            )

            p_handle_rgn = gizmo_data.gizmo_p_handle_rgn
            a_handle_rgn = gizmo_data.gizmo_a_handle_rgn

            b_is_draw_guide_cross = False
            b_is_draw_main_guide = True

            b_is_active_p_handle = p_gizmo_group.mpr_pivot.is_modal
            b_is_active_a_handle = p_gizmo_group.mpr_handle.is_modal

            v_guide_direction = Vector((0, 1))
            guide_position = p_handle_rgn if b_is_active_p_handle else a_handle_rgn

            @dataclass
            class GuideLine:
                position: Vector = Vector((0, 0))
                direction: Vector = Vector((0, 0))
                enabled: bool = False

                def draw(self, gizmo: bpy.types.Gizmo, shader):
                    guide_ends = intersect_with_view_rect(self.position, self.direction, viewport_rect)
                    if guide_ends:
                        guide_start = guide_ends[0]
                        guide_end = guide_ends[1]
                        scale = guide_end - guide_start
                        if ZenPolls.version_since_3_2_0:
                            UBO_data = Dash_UBO_struct()
                            UBO_data.colors_len = 1
                            UBO_data.dash_width = 10 * d_gizmo_scale
                            UBO_data.udash_factor = 0.5

                            UBO = gpu.types.GPUUniformBuf(
                                gpu.types.Buffer("UINT", ctypes.sizeof(UBO_data), UBO_data)
                            )

                            shader.uniform_block("g_data", UBO)
                            shader.uniform_float("color2", (0, 0, 0, 0.5))

                            shader.uniform_float("viewport_size", viewport_size)

                        mtx = Matrix.Translation(guide_start.resized(3)) @ Matrix.Diagonal((scale.x, scale.y, 0)).to_4x4()
                        gizmo.draw_custom_shape(gizmo.custom_dashed_line_shape, matrix=mtx, select_id=None)

            xy_guideline = GuideLine()
            alt_guideline = GuideLine()

            def intersect_with_view_rect(guide_position: Vector, guide_direction: Vector, viewport_rect: list):
                guide_direction.normalize()
                guide_start = guide_position + 1e6 * guide_direction
                guide_end = guide_position - 1e6 * guide_direction
                guide_ends = []
                for edge in viewport_rect:
                    point = intersect_line_line_2d(
                        guide_start,
                        guide_end,
                        edge[0], edge[1])
                    if point is not None:
                        guide_ends.append(point)

                return guide_ends * 2 if len(guide_ends) == 1 else guide_ends

            def setup_axes_lock_guides():
                nonlocal b_is_draw_guide_cross
                nonlocal b_is_draw_main_guide
                nonlocal v_guide_direction

                xy_guideline.enabled = b_is_x_y_lock_enabled

                if xy_guideline.enabled:

                    b_gizmo_in_locked_position = True

                    if b_is_transform:
                        p_active_gizmo = p_gizmo_group.active_gizmo
                        if p_active_gizmo and p_active_gizmo.is_modal:
                            b_gizmo_in_locked_position = any(p_active_gizmo.gizmo_internal_axis_lock)

                    if b_gizmo_in_locked_position:
                        xy_guideline.position = (
                            gizmo_data.gizmo_p_handle_rgn
                            if tool_props.tr_gizmo_is_pivot else
                            gizmo_data.gizmo_a_handle_rgn)
                    else:
                        xy_guideline.position = (
                            gizmo_data.gizmo_origin_pivot_rgn
                            if tool_props.tr_gizmo_is_pivot else
                            gizmo_data.gizmo_origin_head_rgn)

                    if tool_props.tr_gizmo_display_xy_guidelines[1]:
                        b_is_draw_guide_cross = False
                        b_is_draw_main_guide = True
                        xy_guideline.direction = Vector((1, 0))
                    elif tool_props.tr_gizmo_display_xy_guidelines[0]:
                        b_is_draw_guide_cross = True
                        b_is_draw_main_guide = False
                        xy_guideline.direction = Vector((0, 1))
                        if 'SCALE_NON_PROP' in tool_props.tr_gizmo_type or 'SCALE' in tool_props.tr_gizmo_type:
                            v_guide_direction = Vector((-v_guide_direction.y, v_guide_direction.x))

            if 'LINE' in tool_props.tr_gizmo_type:
                b_is_draw_guide_cross = True
                v_guide_direction = Vector((0, 1))

                if tool_props.tr_gizmo_is_pivot:
                    guide_position = p_handle_rgn
                elif not tool_props.tr_gizmo_is_pivot:
                    guide_position = a_handle_rgn

                if tool_props.tr_gizmo_axes_lock == "MOVE_ALONG_AXIS":
                    b_is_draw_guide_cross = False
                    b_is_draw_main_guide = True
                    v_base_vec = gizmo_data.gizmo_origin_vector
                    v_guide_direction = gizmo_data.gizmo_origin_vector.orthogonal().normalized()

                    alt_guideline.enabled = True
            elif 'SCALE' in tool_props.tr_gizmo_type:
                guide_position = a_handle_rgn
                v_base_vec = gizmo_data.gizmo_origin_vector
                v_guide_direction = gizmo_data.gizmo_origin_vector.orthogonal().normalized()

                alt_guideline.enabled = True
            elif 'SCALE_NON_PROP' in tool_props.tr_gizmo_type:
                guide_position = a_handle_rgn
                v_base_vec = gizmo_data.gizmo_origin_vector
                v_guide_direction = gizmo_data.gizmo_origin_vector.orthogonal().normalized()

                alt_guideline.enabled = True
            elif 'ROTATE' in tool_props.tr_gizmo_type:
                self.color = Vector(ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR) * 2
                self.alpha = 0.8

                b_is_draw_guide_cross = False

                guide_position = p_handle_rgn

                v_base_vec = a_handle_rgn - p_handle_rgn
                v_guide_direction = v_base_vec.normalized()

                alt_guideline.enabled = True
            elif b_is_active_p_handle:
                b_is_draw_guide_cross = True

                guide_position = p_handle_rgn
                v_guide_direction = Vector((0, 1))

                if tool_props.tr_gizmo_axes_lock == "SCALE_ALONG_AXIS":
                    alt_guideline.enabled = True
            elif b_is_active_a_handle:
                b_is_draw_guide_cross = True

                guide_position = a_handle_rgn
                v_guide_direction = Vector((0, 1))

                if tool_props.tr_gizmo_axes_lock == "SCALE_ALONG_AXIS":
                    alt_guideline.enabled = True

            setup_axes_lock_guides()

            main_guide_ends = intersect_with_view_rect(guide_position, v_guide_direction, viewport_rect)

            _, shader = self.custom_dashed_line_shape

            shader.bind()

            gpu.state.blend_set('ALPHA_PREMULT')

            if not b_hide_guides:
                if b_is_draw_main_guide and main_guide_ends:
                    v_guide_start = main_guide_ends[0]
                    v_guide_end = main_guide_ends[1]
                    v_scale = v_guide_end - v_guide_start
                    if ZenPolls.version_since_3_2_0:
                        UBO_data = Dash_UBO_struct()
                        UBO_data.colors_len = 1
                        UBO_data.dash_width = 10 * d_gizmo_scale
                        UBO_data.udash_factor = 0.5

                        UBO = gpu.types.GPUUniformBuf(
                            gpu.types.Buffer("UINT", ctypes.sizeof(UBO_data), UBO_data)
                        )

                        shader.uniform_block("g_data", UBO)
                        shader.uniform_float("color2", (0, 0, 0, 0.5))

                        shader.uniform_float("viewport_size", viewport_size)

                    mtx = Matrix.Translation(v_guide_start.resized(3)) @ Matrix.Diagonal((v_scale.x, v_scale.y, 0)).to_4x4()
                    self.draw_custom_shape(self.custom_dashed_line_shape, matrix=mtx, select_id=None)

                if b_is_draw_guide_cross:
                    v_guide_direction.rotate(Matrix.Rotation(-math.pi / 2, 2))
                    cross_guide_ends = intersect_with_view_rect(guide_position, v_guide_direction, viewport_rect)
                    if cross_guide_ends:
                        v_guide_start = cross_guide_ends[0]
                        v_guide_end = cross_guide_ends[1]
                        v_scale = v_guide_end - v_guide_start
                        if ZenPolls.version_since_3_2_0:
                            UBO_data = Dash_UBO_struct()
                            UBO_data.colors_len = 1
                            UBO_data.dash_width = 10 * d_gizmo_scale
                            UBO_data.udash_factor = 0.5

                            UBO = gpu.types.GPUUniformBuf(
                                gpu.types.Buffer("UINT", ctypes.sizeof(UBO_data), UBO_data)
                            )

                            shader.uniform_block("g_data", UBO)
                            shader.uniform_float("color2", (0, 0, 0, 0.5))

                            shader.uniform_float("viewport_size", viewport_size)
                        mtx = Matrix.Translation(v_guide_start.resized(3)) @ Matrix.Diagonal((v_scale.x, v_scale.y, 0)).to_4x4()
                        self.draw_custom_shape(self.custom_dashed_line_shape, matrix=mtx, select_id=None)

            if alt_guideline.enabled:
                alt_guideline.direction = gizmo_data.gizmo_origin_direction
                alt_guideline.position = gizmo_data.gizmo_origin_pivot_rgn

                bl_theme = context.preferences.themes[0].user_interface

                self.color = bl_theme.axis_z[:3]
                self.color_highlight = self.color.copy()

                alt_guideline.draw(self, shader)

            # NOTE: special case of X, Y locks
            if xy_guideline.enabled:
                bl_theme = context.preferences.themes[0].user_interface

                # NOTE: is X or Y locked ?
                self.color = bl_theme.axis_x[:3] if xy_guideline.direction.x > 0 else bl_theme.axis_y[:3]
                self.color_highlight = self.color.copy()

                xy_guideline.draw(self, shader)

            gpu.state.blend_set('NONE')

            self.color = was_color
            self.color_highlight = was_highlight_color
            self.alpha = was_alpha
            self.alpha_highlight = was_alpha_highlight


class UV_GT_zenuv_draggable_line(bpy.types.Gizmo, ZuvTransformGizmoBase):
    bl_idname = "UV_GT_zenuv_draggable_line"

    bl_target_properties = (
        {"id": "offset", "type": 'FLOAT', "array_length": 3},
    )

    __slots__ = (
        "custom_shape",
        "custom_dashed_line_shape",

        "gizmo_type",

        "init_mouse",
        "init_value",
        "init_mtx_world",
        "init_snap_base",
        "init_cursor_location",

        "start",
        "end",

        "last_update",
    )

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        d_gizmo_size = context.preferences.view.gizmo_size
        ui_scale = context.preferences.system.ui_scale
        d_gizmo_size *= ui_scale
        d_gizmo_size *= self.group.mpr_pivot.scale_basis

        cropped_part = (self.end - self.start).normalized() * d_gizmo_size
        self.start = self.start + cropped_part
        self.end = self.end - cropped_part
        v_scale = self.end - self.start

        mtx = Matrix.Translation(self.start.resized(3)) @ Matrix.Diagonal((v_scale.x, v_scale.y, 0)).to_4x4()

        if tool_props.tr_gizmo_line_lock_along_axis:
            _, shader = self.custom_dashed_line_shape
            shader.bind()

            if ZenPolls.version_since_3_2_0:
                viewport_size = (context.region.width, context.region.height)

                d_gizmo_scale = get_gizmo_scale(context)

                UBO_data = Dash_UBO_struct()
                UBO_data.colors_len = 1
                UBO_data.dash_width = 10 * d_gizmo_scale * 8
                UBO_data.udash_factor = 0.5

                UBO = gpu.types.GPUUniformBuf(
                    gpu.types.Buffer("UINT", ctypes.sizeof(UBO_data), UBO_data)
                )

                shader.uniform_block("g_data", UBO)
                shader.uniform_float("color2", (0, 0, 0, 0.5))

                shader.uniform_float("viewport_size", viewport_size)

            self.draw_custom_shape(self.custom_dashed_line_shape, matrix=mtx, select_id=select_id)
        else:
            batch, shader = self.custom_shape
            shader.bind()

            gpu.state.line_width_set(1.0)

            with gpu.matrix.push_pop():
                gpu.matrix.multiply_matrix(mtx)

                if not ZenPolls.version_lower_3_4_0:
                    shader.uniform_float('viewportSize', (context.region.width, context.region.height))
                    shader.uniform_float('lineWidth', 4)

                shader.uniform_float("color", (0, 0, 0, 0.5))

                gpu.state.blend_set('ALPHA_PREMULT')
                batch.draw()

                if not ZenPolls.version_lower_3_4_0:
                    line_width = 3 if self.is_highlight else 1
                    shader.uniform_float('lineWidth', line_width)

                if self.is_highlight:
                    color = (*self.color_highlight, self.alpha_highlight)
                else:
                    color = (*self.color, self.alpha)
                shader.uniform_float("color", color)

                gpu.state.blend_set('ALPHA')
                batch.draw()

        gpu.state.blend_set('NONE')

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def draw_select(self, context, select_id):
        self._do_draw(context, select_id=select_id)

    def test_select_internal(self, context: bpy.types.Context, location):
        addon_prefs = get_prefs()

        def is_point_on_line(x, y, x1, y1, x2, y2, tolerance=1.0):
            def distance(px, py, qx, qy):
                return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5

            # Calculate the distance from the point to the line segment
            def point_to_line_distance(x, y, x1, y1, x2, y2):
                num = abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1))
                den = distance(x1, y1, x2, y2)
                return num / den if den != 0.0 else 0.0

            # Check if the point is on the line segment considering the tolerance
            if point_to_line_distance(x, y, x1, y1, x2, y2) <= tolerance:
                if min(x1, x2) - tolerance <= x <= max(x1, x2) + tolerance and min(y1, y2) - tolerance <= y <= max(y1, y2) + tolerance:
                    return True
            return False

        x, y = location  # Mouse coordinates
        blind_spot = (self.start - self.end).normalized() * 45 if "ALIGN" in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state else None

        if 'ALIGN' not in addon_prefs.uv_transform_tool.tr_gizmo_handles_display_state:
            x1, y1 = self.start.to_tuple()[:2]
            x2, y2 = self.end.to_tuple()[:2]
        else:
            x1, y1 = (self.start - blind_spot).to_tuple()[:2]
            x2, y2 = self.end.to_tuple()[:2]

        res = is_point_on_line(x, y, x1, y1, x2, y2, tolerance=10)

        return 0 if res else -1

    def setup(self):
        super().setup()

        if not hasattr(self, "start"):
            self.start = Vector((0, 0))
            self.end = Vector((0, 0))

            self.gizmo_type = 'LINE'

    def invoke(self, context, event: bpy.types.Event):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        tool_props.tr_gizmo_type = set(tool_props.tr_gizmo_type).union({'LINE'})
        tool_props.tr_gizmo_axes_lock = 'NONE'

        res = self._do_invoke(context, event, tool_props)

        if 'RUNNING_MODAL' in res:
            if tool_props.tr_gizmo_line_lock_along_axis:
                tool_props.tr_gizmo_axes_lock = 'MOVE_ALONG_AXIS'

        return res

    def exit(self, context: bpy.types.Context, cancel: bool):
        super().exit(context, cancel)

        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        tool_props.tr_gizmo_type = set(tool_props.tr_gizmo_type).difference({'LINE'})


class UV_GT_zenuv_bbox_tool(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_bbox_tool"

    bl_target_properties = (
        {"id": "offset", "type": 'FLOAT', "array_length": 3},
    )

    __slots__ = (
        "custom_shape",
        "custom_dashed_line_shape",

        "init_mouse",
        "init_value",
        "init_mtx_world",
        "init_snap_base",
        "init_cursor_location",

        "start",
        "end",

        "last_update",
    )

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        was_color = self.color.copy()

        _, shader = self.custom_dashed_line_shape

        shader.bind()

        gpu.state.blend_set('ALPHA_PREMULT')

        v_scale = self.end - self.start

        if ZenPolls.version_since_3_2_0:
            viewport_size = (context.region.width, context.region.height)

            d_gizmo_scale = get_gizmo_scale(context)

            UBO_data = Dash_UBO_struct()
            UBO_data.colors_len = 1
            UBO_data.dash_width = 10 * d_gizmo_scale
            UBO_data.udash_factor = 0.5

            UBO = gpu.types.GPUUniformBuf(
                gpu.types.Buffer("UINT", ctypes.sizeof(UBO_data), UBO_data)
            )

            shader.uniform_block("g_data", UBO)
            shader.uniform_float("color2", (0, 0, 0, 0.5))

            shader.uniform_float("viewport_size", viewport_size)

        self.color = ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR
        self.alpha = 0.95

        mtx = Matrix.Translation(self.start.resized(3)) @ Matrix.Diagonal((v_scale.x, v_scale.y, 0)).to_4x4()
        self.draw_custom_shape(self.custom_dashed_line_shape, matrix=mtx, select_id=select_id)

        gpu.state.blend_set('NONE')

        self.color = was_color

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def setup(self):
        if not hasattr(self, "start"):
            self.init_mtx_world = Matrix()
            self.last_update = 0
            self.start = Vector((0, 0))
            self.end = Vector((0, 0))
            self.init_snap_base = Vector((0, 0))
            self.init_cursor_location = Vector((0, 0))

            ZuvTransformGizmoBase._do_setup_custom_line_shape(self)
            ZuvTransformGizmoBase._do_setup_custom_dashed_line_shape(self)


class UV_GT_zenuv_rotate_handle(bpy.types.Gizmo, ZuvTransformGizmoBase, ZuvTransformHandleBase):
    bl_idname = "UV_GT_zenuv_rotate_handle"

    bl_target_properties = UV_GT_zenuv_transform_pivot.bl_target_properties

    __slots__ = UV_GT_zenuv_transform_pivot.__slots__

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        color = self.color_highlight if self.is_highlight else self.color
        alpha = self.alpha_highlight if self.is_highlight else self.alpha

        _, shader = self.custom_shape

        shader.bind()

        gpu.state.blend_set('ALPHA')

        v_start_position = self.start.resized(3)
        v_end_position = (self.end - self.start).resized(3)
        v_middle = v_start_position + v_end_position / 2

        mtx = Matrix.Translation(v_middle) @ Matrix.Diagonal((v_end_position.length, v_end_position.length)).to_4x4()

        draw_circle_2d_filled(v_middle.x, v_middle.y, radius=v_end_position.length, color=(*color[:], alpha))

        gpu.state.line_width_set(1.0)

        if v_end_position.length:
            draw_circle_2d(mtx.to_translation(), (*color[:], 1.0), v_end_position.length)

        gpu.state.blend_set('NONE')

    def invoke(self, context, event: bpy.types.Event):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        tool_props.tr_gizmo_axes_lock = 'NONE'

        s_gizmo_type = 'ANGLE_HANDLE'
        tool_props.set_gizmo_type_and_synchronize_cursor_2d(context, {s_gizmo_type, self.gizmo_type})
        res = self._do_invoke(context, event, tool_props)
        tool_props.tr_gizmo_axes_lock = 'PURE_ROTATION'
        return res

    def exit(self, context: bpy.types.Context, cancel):
        super().exit(context, cancel)

        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        tool_props.tr_gizmo_active = False
        tool_props.tr_gizmo_type = set(tool_props.tr_gizmo_type).difference({self.gizmo_type})


class UV_GT_zenuv_scale_handle(bpy.types.Gizmo, ZuvTransformGizmoBase, ZuvTransformHandleBase):
    bl_idname = "UV_GT_zenuv_scale_handle"

    bl_target_properties = UV_GT_zenuv_transform_pivot.bl_target_properties

    __slots__ = sum((UV_GT_zenuv_transform_pivot.__slots__, ("gizmo_axes_lock", )), ())

    def invoke(self, context, event: bpy.types.Event):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        tool_props.tr_gizmo_axes_lock = 'NONE'

        s_gizmo_type = 'ANGLE_HANDLE'
        tool_props.set_gizmo_type_and_synchronize_cursor_2d(context, {s_gizmo_type, self.gizmo_type})

        res = self._do_invoke(context, event, tool_props)
        tool_props.tr_gizmo_axes_lock = self.gizmo_axes_lock
        return res

    def exit(self, context: bpy.types.Context, cancel):
        super().exit(context, cancel)

        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        tool_props.tr_gizmo_type = set(tool_props.tr_gizmo_type).difference({self.gizmo_type})


class UV_GT_zenuv_transform_tool_tooltip(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_transform_tool_tooltip"

    bl_target_properties = ()

    __slots__ = (
        "text_items",
        "uniform_shader",
        "line_shader"
    )

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        view_width, view_height = context.region.width, context.region.height

        ui_scale = context.preferences.system.ui_scale

        v_pos = self.matrix_basis.to_translation()

        # NOTE: cursor offset
        v_pos.x -= 20 * ui_scale
        v_pos.y -= 20 * ui_scale

        line_width = 1

        icon_size = ZenDrawConstants.GIZMO_ICON_SIZE * ui_scale

        bl_theme = bpy.context.preferences.themes[0].user_interface
        p_color = bl_theme.wcol_tooltip.inner[:3]
        p_text_color = bl_theme.wcol_tooltip.text[:3]

        scale_factor = ZenDrawConstants.GIZMO_BTN_ICON_SCALE_FACTOR * ui_scale

        ZenCompat.blf_font_size(11, ui_scale)

        col_offset = 5 * ui_scale

        v_text = v_pos.copy()

        color = p_color
        round_rect_alpha = 1.0

        corner = 8

        max_text_width = 0
        max_columns_width = 0
        max_text_height = 0

        t_columns = {
            "key1": [20 * ui_scale, False],  # NOTE: in this row 'x2'
            "key2": [20 * ui_scale, False],  # NOTE: in this row 'Ctrl'
            "key3": [20 * ui_scale, False],  # NOTE: in this row 'Shift'
        }

        item_line: ZuvTransformTooltipText
        for item_line in self.text_items:
            t_w = 0
            for k in t_columns.keys():
                if getattr(item_line, k):
                    t_w += t_columns[k][0]
                    t_columns[k][1] = True
            if t_w > max_columns_width:
                max_columns_width = t_w

            w, h = blf.dimensions(0, item_line.text)

            if w > max_text_width:
                max_text_width = w
            if h > max_text_height:
                max_text_height = h

        width = max_text_width + max_columns_width + col_offset * 6 + icon_size
        height = len(self.text_items) * icon_size

        rect = Rectangle(v_pos.x, v_pos.y - height, v_pos.x + width, v_pos.y)

        z_offset = 10  # NOTE: we need to create offset by Z-axis to force display above all gizmos

        gpu.state.blend_set('NONE')

        with gpu.matrix.push_pop():
            matrix = Matrix.Translation((0, 0, z_offset))
            gpu.matrix.multiply_matrix(matrix)

            draw_rounded_rect(
                rect,
                view_width, view_height,
                self.uniform_shader,
                (*color[:], round_rect_alpha), 1.0, line_width,
                tl=corner, tr=corner, br=corner, bl=corner, outline=False)

            draw_rounded_rect(
                rect,
                view_width, view_height,
                self.line_shader,
                (*color[:], round_rect_alpha), 1.0, line_width,
                tl=corner, tr=corner, br=corner, bl=corner, outline=True)

        def draw_text(x, y, color, text):
            blf.position(0, x, y, 0)

            blf.color(0, *color)

            blf.enable(0, blf.SHADOW)
            blf.shadow(0, 3, 0.0, 0.0, 0.0, 1.0)
            blf.shadow_offset(0, 1, -1)

            blf.draw(0, text)

            blf.disable(0, blf.SHADOW)

        for item_line in self.text_items:

            v_text.x = v_pos.x + col_offset

            y_pos = v_text.y

            with gpu.matrix.push_pop():

                matrix = Matrix.Translation((v_text.x, y_pos - icon_size, z_offset)) @ Matrix.Diagonal((scale_factor, scale_factor)).to_4x4()
                gpu.matrix.multiply_matrix(matrix)

                p_batch = ZenDrawConstants.get_ui_icon_batch(item_line.icon)
                if p_batch:

                    gpu.state.blend_set('ALPHA')

                    ZenDrawConstants.icon_shader.bind()
                    ZenDrawConstants.icon_shader.uniform_float("color", (*p_text_color[:], 0.75))
                    p_batch.draw(ZenDrawConstants.icon_shader)

            with gpu.matrix.push_pop():
                matrix = Matrix.Translation((0, 0, z_offset))
                gpu.matrix.multiply_matrix(matrix)

                v_text.x += icon_size

                _, h = blf.dimensions(0, item_line.text)
                y_pos = v_text.y - icon_size / 2 - h / 2

                for k in t_columns.keys():
                    s_key = getattr(item_line, k)
                    if s_key:
                        draw_text(v_text.x, y_pos, (*p_text_color[:], 1.0), s_key)
                    if t_columns[k][1]:
                        v_text.x += t_columns[k][0]

                if item_line.text:
                    v_text.x += col_offset * 3
                    draw_text(v_text.x, y_pos, (*p_text_color[:], 1.0), item_line.text)

            v_text.y -= icon_size

        gpu.state.blend_set('NONE')

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def setup(self):
        if not hasattr(self, "text_items"):
            self.text_items = []
            self.uniform_shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
            self.line_shader = gpu.shader.from_builtin(ZenCompat.get_3d_polyline_smooth())


class ZUV_GGT_UVTransformButton(bpy.types.GizmoGroup):
    bl_idname = "ZUV_GGT_UVTransformButton"
    bl_label = "Tool Transform UI Button"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    poll = ZUV_GGT_UVTransformGizmo.poll

    def draw_prepare(self, context):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        addon_prefs = get_prefs()
        self.mpr_set_transform_mode.hide = not addon_prefs.show_uv_tool_transform_gizmo_button or tool_props.tr_gizmo_mode != 'TRANSFORM'
        self.mpr_set_setup_mode.hide = not addon_prefs.show_uv_tool_transform_gizmo_button or tool_props.tr_gizmo_mode != 'SETUP'

        if not self.mpr_set_transform_mode.hide:
            self.gizmo_colors.setup(context)

            self.mpr_set_transform_mode.color = self.gizmo_colors.line.copy()
            self.mpr_set_transform_mode.alpha = 0.4
            self.mpr_set_transform_mode.color_highlight = 0.8, 0.8, 0.8
            self.mpr_set_transform_mode.alpha_highlight = 0.2

            from ZenUV.ui.gizmo_draw import GizmoColumnButton
            GizmoColumnButton.set_position(self.mpr_set_transform_mode, context, 'TOOL_TRANSFORM')
        if not self.mpr_set_setup_mode.hide:
            from ZenUV.ui.gizmo_draw import GizmoColumnButton
            GizmoColumnButton.set_position(self.mpr_set_setup_mode, context, 'TOOL_TRANSFORM')

    def setup(self, context):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        # NOTE: we need 2 separate buttons, because icon does not change in the "fly"
        self.mpr_set_setup_mode = self.gizmos.new("GIZMO_GT_button_2d")
        self.mpr_set_setup_mode.show_drag = False
        self.mpr_set_setup_mode.draw_options = {'BACKDROP', 'OUTLINE'}
        self.mpr_set_setup_mode.scale_basis = (80 * 0.35) / 2  # Same as buttons defined in C
        self.mpr_set_setup_mode.icon = next(
            item.icon
            for item in tool_props.bl_rna.properties["tr_gizmo_mode"].enum_items
            if item.identifier == "SETUP"
        )

        op = self.mpr_set_setup_mode.target_set_operator("wm.context_toggle_enum")
        op.data_path = "scene.zen_uv.ui.uv_tool.tr_gizmo_mode"
        op.value_1 = "SETUP"
        op.value_2 = "TRANSFORM"

        self.mpr_set_transform_mode = self.gizmos.new("GIZMO_GT_button_2d")
        self.mpr_set_transform_mode.show_drag = False
        self.mpr_set_transform_mode.draw_options = {'BACKDROP', 'OUTLINE'}
        self.mpr_set_transform_mode.scale_basis = (80 * 0.35) / 2  # Same as buttons defined in C
        self.mpr_set_transform_mode.icon = next(
            item.icon
            for item in tool_props.bl_rna.properties["tr_gizmo_mode"].enum_items
            if item.identifier == "TRANSFORM"
        )

        op = self.mpr_set_transform_mode.target_set_operator("wm.context_toggle_enum")
        op.data_path = "scene.zen_uv.ui.uv_tool.tr_gizmo_mode"
        op.value_1 = "TRANSFORM"
        op.value_2 = "SETUP"

        self.gizmo_colors = ZuvTransformGizmoColors()

        self.mpr_set_setup_mode.color = 0.0, 0.0, 0.0
        self.mpr_set_setup_mode.alpha = 0.4
        self.mpr_set_setup_mode.color_highlight = 0.8, 0.8, 0.8
        self.mpr_set_setup_mode.alpha_highlight = 0.2
