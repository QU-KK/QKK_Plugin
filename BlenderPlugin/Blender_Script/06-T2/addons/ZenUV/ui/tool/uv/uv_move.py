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

from mathutils import Vector
from ZenUV.utils.vlog import Log

from .uv_pos_sca import ZuvUVGizmoPosSca
from ZenUV.ops.event_service import is_skipped_by_continious_drag
from ZenUV.utils.blender_zen_utils import ZenPolls


class ZUV_GGT_UVTransformMove(bpy.types.GizmoGroup, ZuvUVGizmoPosSca):
    bl_idname = "ZUV_GGT_UVTransformMove"
    bl_label = "Transform (Move)"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SHOW_MODAL_ALL',
    } if bpy.app.version < (3, 3, 0) else {
        'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL',
    }

    tool_mode = {'MOVE'}

    def _setup_matrices_final(self, context: bpy.types.Context) -> bool:
        if super()._setup_matrices_final(context):
            self.tool_offset_move = Vector((0, 0))

    def _do_offset(self, context: bpy.types.Context, v_offset: Vector):

        if is_skipped_by_continious_drag(context):
            return

        self.tool_offset_move += v_offset

        b_executed = False

        from ZenUV.ops.transform_sys.trim_depend_transform import ZUV_OT_TrUVMoveInTrim

        # prevent endless undo chain
        wm = bpy.context.window_manager
        if self.drag_started and wm.operators:
            op = wm.operators[-1]

            if isinstance(op, ZUV_OT_TrUVMoveInTrim):
                op.op_tr_increment = v_offset.to_tuple()
                op.move_offset = self.tool_offset_move.to_tuple()
                op.is_offset_mode = True
                op.execute(context)

                b_executed = True


        # call with undo
        if not b_executed:
            bpy.ops.uv.zenuv_move_in_trim(
                'INVOKE_DEFAULT', True,
                is_offset_mode=True,
                move_offset=self.tool_offset_move.to_tuple(),
                op_tr_increment=v_offset.to_tuple())

        s_info = ''

        op_props = wm.operator_properties_last(ZUV_OT_TrUVMoveInTrim.bl_idname)
        if op_props:
            if op_props.info_message:
                s_info = '    Info: ' + op_props.info_message

        context.area.header_text_set(
            f'Move: {self.tool_offset_move.x:.4f}, {self.tool_offset_move.y:.4f}{s_info}')

        # HACK: we stopped receive refresh message so here is the only place to get it
        if ZenPolls.version_since_4_2_0:
            self.do_refresh(context)

    def _do_up_offset(self, context: bpy.types.Context, p_offset):
        self._do_offset(context, Vector((0.0, p_offset)))

    def _do_right_offset(self, context: bpy.types.Context, p_offset):
        self._do_offset(context, Vector((p_offset, 0.0)))

    def _do_direction_offset(self, context: bpy.types.Context, v_offset: Vector):
        self._do_offset(context, v_offset)
