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

# Copyright 2023, Alex Zhornyak

import bpy
import math
from mathutils import Vector, Matrix
from functools import partial

from .uv_pos_sca import ZuvUVGizmoPosSca
from ZenUV.ops.event_service import get_blender_event
from ZenUV.utils.blender_zen_utils import ZenPolls


class ZUV_GGT_UVTransformScale(bpy.types.GizmoGroup, ZuvUVGizmoPosSca):
    bl_idname = "ZUV_GGT_UVTransformScale"
    bl_label = "Transform (Scale)"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SHOW_MODAL_ALL',
    } if bpy.app.version < (3, 3, 0) else {
        'PERSISTENT', 'SHOW_MODAL_ALL', 'TOOL_FALLBACK_KEYMAP'
    }

    tool_mode = {'SCALE'}

    pivot_prop = 'zen_uv.ui.uv_tool.scale_island_pivot'

    def setup(self, context):
        super().setup(context)

        self.mpr_up.draw_style = 'BOX'
        self.mpr_right.draw_style = 'BOX'

    def _setup_dragged(self, context: bpy.types.Context):

        # Do not change Gizmo Order !

        self._create_up_right()

        self._create_dir()

        self.mpr_line = self.gizmos.new("UV_GT_zenuv_transform_line")
        self.mpr_line.color = 0.0, 1.0, 0.0
        self.mpr_line.alpha = 1.0
        self.mpr_line.color_highlight = 0, 1.0, 1.0
        self.mpr_line.alpha_highlight = 1
        self.mpr_line.use_draw_value = True
        self.mpr_line.use_draw_scale = False
        self.mpr_line.use_select_background = False
        self.mpr_line.use_event_handle_all = False
        self.mpr_line.use_grab_cursor = False
        self.mpr_line.hide_select = True
        self.mpr_line.use_draw_self_line = True

        self.tool_region = Vector((0, 0))
        self.tool_dir_increase = False
        self.tool_scale = 1.0
        self.tool_event_pt = Vector((0, 0))

    def _setup_matrices_final(self, context: bpy.types.Context) -> bool:
        if super()._setup_matrices_final(context):
            rgn2d = context.region.view2d

            x, y, = rgn2d.view_to_region(self.uv_selection_center.x, self.uv_selection_center.y, clip=False)

            mtx = Matrix.Translation(Vector((x, y, 0)))

            self.tool_offset = Vector((0.0, 0.0))

            self.mpr_dir.matrix_space = mtx
            self.tool_offset_dir = Vector()
            self.tool_offset_value = Vector((1.0, 1.0))

            self.tool_region = Vector((x, y))
            self.tool_event_pt = Vector((0, 0))
            self.tool_event_length = 0.0
            self.tool_dir_increase = False
            self.tool_scale = 1.0
            self.tool_x_negative = False
            self.tool_y_negative = False
            self.tool_angle_x = 0.0
            self.tool_angle_y = 0.0
            self.mpr_dir.target_set_handler(
                "offset",
                get=partial(self.move_get_cb_dir), set=partial(self.move_set_cb_dir))

            self.mpr_up.matrix_space = mtx
            self.mpr_right.matrix_space = mtx

            return True

        return False

    def _do_offset(self, context: bpy.types.Context, v_offset: Vector):

        self.tool_offset_value *= v_offset

        b_executed = False

        from ZenUV.ops.transform_sys.trim_depend_transform import ZUV_OT_TrUVScaleInTrim

        # prevent endless undo chain
        wm = bpy.context.window_manager
        if self.drag_started and wm.operators:
            op = wm.operators[-1]
            if isinstance(op, ZUV_OT_TrUVScaleInTrim):
                op.allow_negative = False
                op.is_offset_mode = True
                op.op_tr_scale_positive_only = v_offset.to_tuple()
                op.scale_offset = self.tool_offset_value[:]

                op.execute(context)
                b_executed = True

        # First time call from dragging
        if not b_executed:
            # call with undo
            bpy.ops.uv.zenuv_scale_in_trim(
                'INVOKE_DEFAULT', True,
                allow_negative=False, op_tr_scale_positive_only=v_offset.to_tuple(),
                is_offset_mode=True,
                scale_offset=self.tool_offset_value[:])

        s_info = ''

        op_props = wm.operator_properties_last(ZUV_OT_TrUVScaleInTrim.bl_idname)
        if op_props:
            if op_props.info_message:
                s_info = '    Info: ' + op_props.info_message

        context.area.header_text_set(
            f'Scale: {self.tool_offset_value.x:.4f}, {self.tool_offset_value.y:.4f}{s_info}')

        # HACK: we stopped receive refresh message so here is the only place to get it
        if ZenPolls.version_since_4_2_0:
            self.do_refresh(context)

    def move_set_cb_right(self, value):
        if self.tool_offset.x != value:
            self.tool_offset.x = value

            self._do_scale(axis='X')

    def move_set_cb_up(self, value):
        if self.tool_offset.y != value:
            self.tool_offset.y = value

            self._do_scale(axis='Y')

    def move_set_cb_dir(self, value):
        p_vec = Vector(value)
        if self.tool_offset_dir != p_vec:
            self.tool_offset_dir = p_vec

            self._do_scale()

    def _do_scale(self, axis='XY'):
        if self.tool_scale == 0:
            return

        ctx = bpy.context

        p_event = get_blender_event(force=True)
        self.tool_event_pt = Vector(
            (p_event.get('mouse_region_x', 0.0), p_event.get('mouse_region_y', 0.0)))

        new_axis = self.tool_event_pt - self.tool_region  # type: Vector
        if new_axis.length == 0:
            return

        v_offset = Vector((0, 0))
        if axis == 'XY':
            v_offset = self.tool_offset_dir.resized(2)
        else:
            v_offset = self.tool_offset

        tool_event_init_pt = self.tool_event_pt - v_offset  # type: Vector

        tool_event_init_axis = tool_event_init_pt - self.tool_region  # type: Vector
        tool_event_init_length = tool_event_init_axis.length

        if tool_event_init_length == 0:
            return

        axis_X = Vector((1, 0))
        axis_Y = Vector((0, 1))
        angle_init = tool_event_init_axis.angle_signed(axis_Y)

        b_init_drag_from_up = (
            (angle_init > -math.pi / 4 and angle_init < math.pi / 4) or
            angle_init < -math.pi / 4 * 3 or angle_init > math.pi / 4 * 3
        )

        b_flip_x = False
        b_flip_y = False

        b_flip_enabled = False  # TODO Maybe better to have option in prefs ?

        if b_init_drag_from_up:
            if 'Y' in axis:
                new_angle = new_axis.angle_signed(axis_X)
                if self.tool_angle_y != 0.0 and new_angle != 0.0:
                    sign_was = math.copysign(1, self.tool_angle_y)
                    sign_new = math.copysign(1, new_angle)

                    if sign_was != sign_new:
                        b_flip_y = True

                self.tool_angle_y = new_angle
        else:
            if 'X' in axis:
                new_angle = new_axis.angle_signed(axis_Y)
                if self.tool_angle_x != 0.0 and new_angle != 0.0:
                    sign_was = math.copysign(1, self.tool_angle_x)
                    sign_new = math.copysign(1, new_angle)

                    if sign_was != sign_new:
                        b_flip_x = True

                self.tool_angle_x = new_angle

        new_length = new_axis.length
        new_increase = new_length >= self.tool_event_length

        self.tool_dir_increase = new_increase
        self.tool_event_length = new_length

        d_ratio = new_length / tool_event_init_length

        d_offset = (d_ratio - self.tool_scale) / self.tool_scale

        d_new_scale = self.tool_scale * (1.0 + d_offset)

        if d_new_scale != 0.0:
            self.tool_scale = d_new_scale

            if self.is_uv_selected():
                p_act_obj = ctx.active_object
                if p_act_obj and p_act_obj.type == 'MESH':

                    x_offset = 1.0 + d_offset if 'X' in axis else 1.0
                    y_offset = 1.0 + d_offset if 'Y' in axis else 1.0

                    if b_flip_enabled:
                        if b_flip_x:
                            x_offset *= -1
                        if b_flip_y:
                            y_offset *= -1

                    res = Vector((x_offset, y_offset))
                    self._do_offset(ctx, res)
                    self.drag_started = True

    def _setup_trimsheet_colors(self, context: bpy.types.Context, p_trimsheet, p_active_color):
        super()._setup_trimsheet_colors(context, p_trimsheet, p_active_color)

        if not self.mpr_dir.hide:
            self.mpr_dir.alpha_highlight = 0.0 if self.mpr_dir.is_modal else 1.0
        self.mpr_up.hide = self.mpr_up.hide or self.mpr_dir.is_modal
        self.mpr_right.hide = self.mpr_right.hide or self.mpr_dir.is_modal

        self.mpr_line.hide = (
            (
                not self.mpr_dir.is_modal and
                not self.mpr_up.is_modal and
                not self.mpr_right.is_modal) or
            self.tool_event_pt[:] == (0, 0))

        if not self.mpr_line.hide:
            self.mpr_line.start = self.tool_region
            self.mpr_line.end = self.tool_event_pt
            self.mpr_line.color = (0, 0, 0) if self.tool_dir_increase else (0, 0, 0)

        self.setup_operator_pivot(context)
