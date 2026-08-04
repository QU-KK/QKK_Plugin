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
from ZenUV.utils.vlog import Log

from functools import partial

from .uv_base import ZuvUVGizmoBase


class ZuvUVGizmoPosSca(ZuvUVGizmoBase):

    # ABSTRACT METHODS

    def _do_up_offset(self, context: bpy.types.Context, p_offset):
        raise NotImplementedError('ABSTRACT> _do_up_offset!')

    def _do_right_offset(self, context: bpy.types.Context, p_offset):
        raise NotImplementedError('ABSTRACT> _do_right_offset!')

    def _do_direction_offset(self, context: bpy.types.Context, p_offset):
        raise NotImplementedError('ABSTRACT> _do_direction_offset!')

    # INHERITED METHODS

    def _check_object_data_after_refresh(self, context: bpy.types.Context):
        if self.is_trimsheet_modified(context):
            self.setup_position(context, update_drag=False)

        self.enqueue_gizmo_check(context)

    def _create_dir(self):
        self.mpr_dir = self.gizmos.new("GIZMO_GT_move_3d")
        self.mpr_dir.color = 1.0, 1.0, 0.0
        self.mpr_dir.alpha = 0.5
        self.mpr_dir.color_highlight = 0.0, 0.0, 1.0
        self.mpr_dir.alpha_highlight = 1
        self.mpr_dir.scale_basis = 1.2 if 'SCALE' in self.tool_mode else 0.2
        self.mpr_dir.line_width = 3.0
        self.mpr_dir.use_draw_modal = True
        self.mpr_dir.use_draw_value = True
        self.mpr_dir.hide = False
        self.mpr_dir.use_select_background = False

        self.gizmo_drag[self.mpr_dir] = False

    def _create_up_right(self):
        self.mpr_up = self.gizmos.new("UV_GT_zenuv_arrow")
        self.mpr_up.color = 0.0, 1.0, 0.0
        self.mpr_up.alpha = 0.5
        self.mpr_up.color_highlight = 0, 1.0, 1.0
        self.mpr_up.alpha_highlight = 1
        self.mpr_up.use_draw_modal = True
        self.mpr_up.use_draw_value = True
        self.mpr_up.is_up = True
        self.mpr_up.scale_basis = 1.0 if 'SCALE' in self.tool_mode else 0.8

        self.mpr_up.line_width = 3.0

        self.gizmo_drag[self.mpr_up] = False

        self.mpr_right = self.gizmos.new("UV_GT_zenuv_arrow")
        self.mpr_right.color = 1.0, 0.0, 0.0
        self.mpr_right.alpha = 0.5
        self.mpr_right.color_highlight = 1.0, 0, 1.0
        self.mpr_right.alpha_highlight = 1
        self.mpr_right.use_draw_modal = True
        self.mpr_right.is_up = False
        self.mpr_right.scale_basis = 1.0 if 'SCALE' in self.tool_mode else 0.8

        self.mpr_right.line_width = 3.0

        self.mpr_up.matrix_basis = Matrix.Rotation(math.radians(-90.0), 4, 'X')
        self.mpr_right.matrix_basis = Matrix.Rotation(math.radians(90.0), 4, 'Y')

        self.gizmo_drag[self.mpr_right] = False

    def _setup_dragged(self, context: bpy.types.Context):
        self._create_dir()
        self._create_up_right()

    def _reset_dragged(self, context: bpy.types.Context):
        self.tool_offset = Vector()
        self.tool_offset_dir = Vector()
        self.drag_started = False
        context.area.header_text_set(None)

        self.setup_position(context)

    def _setup_matrices_final(self, context: bpy.types.Context) -> bool:
        if super()._setup_matrices_final(context):
            if not self.are_gizmos_modal() and self.is_uv_selected():
                rgn2d = context.region.view2d

                x, y, = rgn2d.view_to_region(self.uv_selection_center.x, self.uv_selection_center.y, clip=False)

                mtx = Matrix.Translation(Vector((x, y, 0)))

                p_scale = context.preferences.system.ui_scale  # depends on UI scale
                d_gizmo_size = context.preferences.view.gizmo_size
                radius_dial = d_gizmo_size * 0.2

                v_pos = Vector((0, 0, radius_dial * p_scale))

                self.tool_offset = Vector((v_pos.z, v_pos.z))

                self.mpr_dir.matrix_space = mtx
                self.tool_offset_dir = Vector()
                self.mpr_dir.target_set_handler(
                    "offset",
                    get=partial(self.move_get_cb_dir), set=partial(self.move_set_cb_dir))

                self.mpr_up.matrix_space = mtx
                self.mpr_right.matrix_space = mtx

                return True

        return False

    def move_get_cb_dir(self):
        return self.tool_offset_dir

    def move_set_cb_dir(self, value):
        p_vec = Vector(value)
        if self.tool_offset_dir != p_vec:
            p_offset = p_vec - self.tool_offset_dir  # type: Vector
            self.tool_offset_dir = p_vec

            if self.is_uv_selected():
                ctx = bpy.context

                p_act_obj = ctx.active_object
                if p_act_obj and p_act_obj.type == 'MESH':
                    rgn2d = ctx.region.view2d
                    v_pos = self.mpr_dir.matrix_world.to_translation()
                    v_was = Vector(rgn2d.region_to_view(v_pos.x, v_pos.y))
                    v_new = Vector(rgn2d.region_to_view(v_pos.x + p_offset.x, v_pos.y + p_offset.y))

                    self._do_direction_offset(ctx, v_new - v_was)
                    self.drag_started = True

    def move_get_cb_up(self):
        return self.tool_offset.y

    def move_set_cb_up(self, value):
        if self.tool_offset.y != value:
            p_offset = value - self.tool_offset.y
            self.tool_offset.y = value

            context = bpy.context

            if self.is_uv_selected():
                p_act_obj = context.active_object

                if p_act_obj and p_act_obj.type == 'MESH':

                    rgn2d = context.region.view2d
                    v_pos = self.mpr_up.matrix_world.to_translation()
                    v_was = Vector(rgn2d.region_to_view(v_pos.x, v_pos.y))
                    v_new = Vector(rgn2d.region_to_view(v_pos.x, v_pos.y + p_offset))

                    self._do_up_offset(context, (v_new - v_was).y)
                    self.drag_started = True

    def move_get_cb_right(self):
        return self.tool_offset.x

    def move_set_cb_right(self, value):
        if self.tool_offset.x != value:
            p_offset = value - self.tool_offset.x
            self.tool_offset.x = value

            context = bpy.context

            if self.is_uv_selected():
                p_act_obj = context.active_object

                if p_act_obj and p_act_obj.type == 'MESH':

                    rgn2d = context.region.view2d
                    v_pos = self.mpr_up.matrix_world.to_translation()
                    v_was = Vector(rgn2d.region_to_view(v_pos.x, v_pos.y))
                    v_new = Vector(rgn2d.region_to_view(v_pos.x + p_offset, v_pos.y))

                    self._do_right_offset(context, (v_new - v_was).x)
                    self.drag_started = True

    def _setup_dragged_position(self, context: bpy.types.Context):
        self.tool_offset = Vector()
        self.tool_offset_dir = Vector()

        self.mpr_up.target_set_handler("offset", get=self.move_get_cb_up, set=self.move_set_cb_up)
        self.mpr_right.target_set_handler("offset", get=self.move_get_cb_right, set=self.move_set_cb_right)
        self.mpr_dir.target_set_handler(
            "offset",
            get=partial(self.move_get_cb_dir), set=partial(self.move_set_cb_dir))

    def _setup_trimsheet_colors(self, context: bpy.types.Context, p_trimsheet, p_active_color):
        super()._setup_trimsheet_colors(context, p_trimsheet, p_active_color)

        b_edit_mesh_selected = self.poll_edit_mesh_selected(context)

        b_require_hide = not b_edit_mesh_selected or self.is_hide_required(context)

        self.mpr_dir.hide = b_require_hide
        self.mpr_up.hide = b_require_hide
        self.mpr_right.hide = b_require_hide
