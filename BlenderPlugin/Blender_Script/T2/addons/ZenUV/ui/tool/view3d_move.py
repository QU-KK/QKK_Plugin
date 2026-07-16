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

from mathutils import Vector, Matrix

from .view3d_pos_sca import ZuvGizmoPosSca

from ZenUV.utils.blender_zen_utils import calc_pixel_size, ZenPolls
from ZenUV.ops.event_service import is_skipped_by_continious_drag


class ZUV_GGT_3DVTransformMove(bpy.types.GizmoGroup, ZuvGizmoPosSca):
    bl_idname = "ZUV_GGT_3DVTransformMove"
    bl_label = "Transform (Move)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {
        '3D', 'PERSISTENT', 'SHOW_MODAL_ALL',
    } if bpy.app.version < (3, 3, 0) else {
        '3D', 'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL'
    }

    tool_mode = 'MOVE'

    def _setup_matrices_final(self, context: bpy.types.Context):
        super()._setup_matrices_final(context)

        p_scale = calc_pixel_size(context, self.mpr_up.matrix_basis.to_translation())

        p_scale *= context.preferences.system.ui_scale  # depends on UI scale

        d_gizmo_size = context.preferences.view.gizmo_size
        radius_dial = d_gizmo_size * 0.2

        v_pos = Vector((0, 0, radius_dial * p_scale))

        self.mpr_up.matrix_offset = Matrix.Translation(v_pos)
        self.mpr_right.matrix_offset = Matrix.Translation(v_pos)

    def _do_offset(self, context: bpy.types.Context, v_offset: Vector):

        if is_skipped_by_continious_drag(context):
            return

        self.tool_offset_value += v_offset  # type: Vector

        b_executed = False

        from ZenUV.ops.transform_sys.trim_depend_transform import ZUV_OT_Tr3DVMoveInTrim

        # prevent endless undo chain
        wm = context.window_manager
        if self.drag_started and wm.operators:
            op = wm.operators[-1]

            if isinstance(op, ZUV_OT_Tr3DVMoveInTrim):
                op.op_tr_increment = v_offset.to_tuple()
                op.is_offset_mode = True
                op.move_offset = self.tool_offset_value.to_tuple()
                op.execute(context)
                context.area.tag_redraw()

                b_executed = True

        # call with undo
        if not b_executed:

            self.switch_blender_overlay(context, False)

            bpy.ops.view3d.zenuv_move_in_trim(
                'INVOKE_DEFAULT', True,
                is_offset_mode=True,
                move_offset=self.tool_offset_value.to_tuple(),
                op_tr_increment=v_offset.to_tuple())

        s_info = ''

        op_props = wm.operator_properties_last(ZUV_OT_Tr3DVMoveInTrim.bl_idname)
        if op_props:
            if op_props.info_message:
                s_info = '    Info: ' + op_props.info_message

        context.area.header_text_set(
            f'Move: {self.tool_offset_value.x:.4f}, {self.tool_offset_value.y:.4f}{s_info}')

        # HACK: we stopped receive refresh message so here is the only place to get it
        if ZenPolls.version_since_4_2_0:
            self.do_refresh(context)

    def _do_up_offset(self, context: bpy.types.Context, p_offset):

        self._do_offset(context, Vector((0.0, p_offset)) * self.offset_correction)

    def _do_right_offset(self, context: bpy.types.Context, p_offset):

        self._do_offset(context, Vector((p_offset, 0.0)) * self.offset_correction)

    def _do_direction_offset(self, context: bpy.types.Context, p_offset: Vector):
        self._do_offset(context, self._calc_offset(p_offset))

    def _calc_offset(self, p_offset: Vector, axis: Vector = Vector((1.0, 1.0))) -> Vector:
        loc, rot, sca = self.mpr_dir.matrix_world.decompose()

        return (p_offset @ rot.normalized().to_matrix().to_4x4()).to_2d() * axis * self.offset_correction
