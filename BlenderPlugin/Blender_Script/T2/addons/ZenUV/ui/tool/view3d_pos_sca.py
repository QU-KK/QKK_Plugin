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

# Copyright 2023, Alex Zhornyak, Valeriy Yatsenko

import bpy
import math

from mathutils import Vector, Matrix

from .view3d_base import ZuvGizmoBase


class ZuvGizmoPosSca(ZuvGizmoBase):

    # ABSTRACT METHODS

    def _do_up_offset(self, context: bpy.types.Context, p_offset):
        raise NotImplementedError('ABSTRACT> _do_up_offset!')

    def _do_right_offset(self, context: bpy.types.Context, p_offset):
        raise NotImplementedError('ABSTRACT> _do_right_offset!')

    def _do_direction_offset(self, context: bpy.types.Context, p_offset):
        raise NotImplementedError('ABSTRACT> _do_direction_offset!')

    # INHERITED METHODS

    def _check_and_set_drag_completed(self):
        b_drag_completed = False
        if self.gizmo_drag.up != self.mpr_up.is_modal:
            b_is_modal = self.mpr_up.is_modal
            if not b_is_modal:
                b_drag_completed = True
            self.gizmo_drag.up = b_is_modal

        if self.gizmo_drag.right != self.mpr_right.is_modal:
            b_is_modal = self.mpr_right.is_modal
            if not b_is_modal:
                b_drag_completed = True
            self.gizmo_drag.right = b_is_modal

        if self.gizmo_drag.direction != self.mpr_dir.is_modal:
            b_is_modal = self.mpr_dir.is_modal
            if not b_is_modal:
                b_drag_completed = True
            self.gizmo_drag.direction = b_is_modal

        if b_drag_completed:
            self.switch_blender_overlay(bpy.context, True)

        return b_drag_completed

    def _create_dir(self):
        self.mpr_dir = self.gizmos.new("GIZMO_GT_move_3d")
        self.mpr_dir.color = 1.0, 1.0, 0.0
        self.mpr_dir.alpha = 0.5
        self.mpr_dir.color_highlight = 0.0, 0.0, 1.0
        self.mpr_dir.alpha_highlight = 1
        self.mpr_dir.scale_basis = 1.2 if 'SCALE' == self.tool_mode else 0.2
        self.mpr_dir.line_width = 3.0

    def _create_up_right(self):
        self.mpr_up = self.gizmos.new("GIZMO_GT_arrow_3d")
        self.mpr_up.color = 0.0, 1.0, 0.0
        self.mpr_up.alpha = 0.5
        self.mpr_up.color_highlight = 0, 1.0, 1.0
        self.mpr_up.alpha_highlight = 1
        self.mpr_up.line_width = 3.0
        self.mpr_up.scale_basis = 1.0 if 'SCALE' == self.tool_mode else 0.8

        self.mpr_right = self.gizmos.new("GIZMO_GT_arrow_3d")
        self.mpr_right.color = 1.0, 0.0, 0.0
        self.mpr_right.alpha = 0.5
        self.mpr_right.color_highlight = 1.0, 0, 1.0
        self.mpr_right.alpha_highlight = 1
        self.mpr_right.scale_basis = 1.0 if 'SCALE' == self.tool_mode else 0.8

        self.mpr_right.line_width = 3.0

    def _setup_dragged(self, context: bpy.types.Context):
        self._create_dir()
        self._create_up_right()

    def _reset_dragged(self, context: bpy.types.Context):
        self.tool_offset = Vector()
        self.tool_offset_dir = Vector()
        self.drag_started = False
        context.area.header_text_set(None)
        self.tool_offset_value = Vector((1.0, 1.0))

        self.setup_position(context)

    def move_get_cb_up(self):
        return self.tool_offset.y

    def move_set_cb_up(self, value):
        if self.tool_offset.y != value:
            p_offset = value - self.tool_offset.y
            self.tool_offset.y = value

            p_act_obj = bpy.context.active_object

            if p_act_obj and self.obj_data.mesh and p_act_obj.data == self.obj_data.mesh:
                self._do_up_offset(bpy.context, p_offset)
                self.drag_started = True

    def move_get_cb_right(self):
        return self.tool_offset.x

    def move_set_cb_right(self, value):
        if self.tool_offset.x != value:
            p_offset = value - self.tool_offset.x
            self.tool_offset.x = value

            p_act_obj = bpy.context.active_object

            if p_act_obj and self.obj_data.mesh and p_act_obj.data == self.obj_data.mesh:
                self._do_right_offset(bpy.context, p_offset)
                self.drag_started = True

    def move_get_cb_dir(self):
        return self.tool_offset_dir

    def move_set_cb_dir(self, value):
        p_vec = Vector(value)
        if self.tool_offset_dir != p_vec:
            p_offset = p_vec - self.tool_offset_dir
            self.tool_offset_dir = p_vec

            p_act_obj = bpy.context.active_object

            if p_act_obj and self.obj_data.mesh and p_act_obj.data == self.obj_data.mesh:
                self._do_direction_offset(bpy.context, p_offset)
                self.drag_started = True

    def _setup_dragged_position(self, context: bpy.types.Context):
        self.tool_offset = Vector()
        self.tool_offset_dir = Vector()

        mtx_res = self.obj_data.mtx_world @ self.tool_mtx  # type: Matrix
        loc, rot, _ = mtx_res.decompose()
        mtx_res = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()

        mat_rot = Matrix.Rotation(math.radians(-90.0), 4, 'X')
        mat_up = mtx_res @ mat_rot  # type: Matrix

        self.mpr_up.matrix_basis = mat_up.normalized()
        self.mpr_dir.matrix_basis = mtx_res.normalized()

        mat_rot = Matrix.Rotation(math.radians(90.0), 4, 'Y')
        mat_right = mtx_res @ mat_rot  # type: Matrix
        self.mpr_right.matrix_basis = mat_right.normalized()

        self.mpr_up.target_set_handler("offset", get=self.move_get_cb_up, set=self.move_set_cb_up)
        self.mpr_right.target_set_handler("offset", get=self.move_get_cb_right, set=self.move_set_cb_right)
        self.mpr_dir.target_set_handler("offset", get=self.move_get_cb_dir, set=self.move_set_cb_dir)
