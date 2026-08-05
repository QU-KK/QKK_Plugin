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
from mathutils import Matrix

from .view3d_base import ZuvGizmoBase
from ZenUV.utils.blender_zen_utils import ZenPolls


class ZUV_GGT_3DVTransformRot(bpy.types.GizmoGroup, ZuvGizmoBase):
    bl_idname = "ZUV_GGT_3DVTransformRot"
    bl_label = "Transform (Rotate)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {
        '3D', 'PERSISTENT', 'SHOW_MODAL_ALL'
    } if bpy.app.version < (3, 3, 0) else {
        '3D', 'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL'
    }

    tool_mode = 'ROTATE'

    pivot_prop = 'zen_uv.ui.view3d_tool.rotate_island_pivot'

    # INHERITED METHODS

    def _check_and_set_drag_completed(self):
        b_drag_completed = False
        if self.gizmo_drag.direction != self.mpr_rot.is_modal:
            b_is_modal = self.mpr_rot.is_modal
            if not b_is_modal:
                b_drag_completed = True
            self.gizmo_drag.direction = b_is_modal

        if b_drag_completed:
            self.switch_blender_overlay(bpy.context, True)

        return b_drag_completed

    def _setup_dragged(self, context: bpy.types.Context):
        self.mpr_rot = self.gizmos.new("GIZMO_GT_dial_3d")
        self.mpr_rot.draw_options = {'ANGLE_START_Y', 'ANGLE_VALUE'}
        self.mpr_rot.color = 0.0, 1.0, 0.0
        self.mpr_rot.alpha = 0.5
        self.mpr_rot.color_highlight = 0, 1.0, 1.0
        self.mpr_rot.alpha_highlight = 1
        self.mpr_rot.line_width = 3
        self.mpr_rot.use_draw_value = True
        self.mpr_rot.use_select_background = False
        self.mpr_rot.use_event_handle_all = False
        self.mpr_rot.use_grab_cursor = False
        self.angle_offset = 0

    def _reset_dragged(self, context: bpy.types.Context):
        self.tool_offset = 0.0  # Direction Angle
        self.drag_started = False

        self.setup_position(context)

        def direction_get_cb():
            return self.tool_offset

        def direction_set_cb(value):
            if self.tool_offset != value:
                p_offset = value - self.tool_offset
                self.tool_offset = value

                p_act_obj = bpy.context.active_object

                if p_act_obj and self.obj_data.mesh and p_act_obj.data == self.obj_data.mesh:
                    self._do_offset(context, math.degrees(p_offset))
                    self.drag_started = True

        self.mpr_rot.target_set_handler("offset", get=direction_get_cb, set=direction_set_cb)
        context.area.header_text_set(None)

    def _setup_dragged_position(self, context: bpy.types.Context):
        self.tool_offset = 0.0  # Direction Angle
        self.angle_offset = 0.0

        mtx_res = self.obj_data.mtx_world @ self.tool_mtx.normalized()  # type: Matrix
        loc, rot, _ = mtx_res.decompose()
        self.mpr_rot.matrix_basis = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
        self.mpr_rot.matrix_space = Matrix()

    def _do_offset(self, context: bpy.types.Context, dir_angle: float):
        # prevent endless undo chain
        wm = context.window_manager

        self.angle_offset += dir_angle

        b_executed = False

        from ZenUV.ops.transform_sys.trim_depend_transform import ZUV_OT_Tr3DVRotateInTrim

        if self.drag_started and wm.operators:
            op = wm.operators[-1]
            if isinstance(op, ZUV_OT_Tr3DVRotateInTrim):
                op.tr_rot_inc_full_range = dir_angle
                op.is_offset_mode = True
                op.rotate_offset_rad = math.radians(self.angle_offset)
                op.execute(context)

                context.area.tag_redraw()

                b_executed = True

        if not b_executed:

            self.switch_blender_overlay(bpy.context, False)

            # call with undo
            bpy.ops.view3d.zenuv_rotate_in_trim(
                'INVOKE_DEFAULT', True,
                tr_rot_inc_full_range=dir_angle,
                is_offset_mode=True,
                rotate_offset_rad=math.radians(self.angle_offset)
            )

        s_info = ''

        op_props = wm.operator_properties_last(ZUV_OT_Tr3DVRotateInTrim.bl_idname)
        if op_props:
            if op_props.info_message:
                s_info = '    Info: ' + op_props.info_message

        context.area.header_text_set(f'Rotate: {self.angle_offset:.4f}°{s_info}')

        # HACK: we stopped receive refresh message so here is the only place to get it
        if ZenPolls.version_since_4_2_0:
            self.do_refresh(context)

    def _setup_trimsheet_colors(self, context: bpy.types.Context, p_trimsheet, p_active_color):
        super()._setup_trimsheet_colors(context, p_trimsheet, p_active_color)

        self.setup_operator_pivot(context)
