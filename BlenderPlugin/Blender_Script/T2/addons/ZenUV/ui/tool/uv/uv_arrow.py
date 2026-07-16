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
from timeit import default_timer as timer
from mathutils import Vector, Matrix

from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils


class UV_GT_zenuv_arrow(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_arrow"
    bl_target_properties = (
        {"id": "offset", "type": 'FLOAT', "array_length": 1},
    )

    __slots__ = (
        "custom_shape",
        "init_mouse",
        "init_value",
        "init_mtx_world",
        "is_up",
        "draw_style",
        "last_update",
    )

    INACTIVE_COLOR = (0.5, 0.5, 0.5)

    def do_draw_box_handle(self, context: bpy.types.Context, matrix: Matrix):
        mtx_scale_line = Matrix.Diagonal((0.01, 0, 0.5)).to_4x4() if self.is_up else Matrix.Diagonal((0, 0.01, 0.5)).to_4x4()
        mtx_pos = Matrix.Translation((0, 0, 0.5))
        mtx_line = mtx_pos @ mtx_scale_line
        self.draw_preset_box(matrix @ mtx_line)

        mtx_scale = Matrix.Diagonal((0.05, 0.05, 0.05)).to_4x4()
        ui_scale = context.preferences.system.ui_scale
        mtx_pos = Matrix.Translation((0, 0 * ui_scale, 1))
        mtx_box = mtx_pos @ mtx_scale
        self.draw_preset_box(matrix @ mtx_box)

    def draw(self, context):
        self._update_offset_matrix()

        was_color = self.color.copy()

        if self.is_modal:
            self.color = self.INACTIVE_COLOR
            if self.draw_style == 'ARROW':
                self.draw_preset_arrow(self.init_mtx_world)
            else:
                self.do_draw_box_handle(context, self.init_mtx_world)

        self.color = self.color_highlight if self.is_highlight else self.color
        if self.draw_style == 'ARROW':
            self.draw_preset_arrow(self.matrix_world)
        else:
            self.do_draw_box_handle(context, self.matrix_world)

        self.color = was_color

    def draw_select(self, context, select_id):
        self._update_offset_matrix()
        self.draw_preset_arrow(self.matrix_world, select_id=select_id)

    def test_select(self, context: bpy.types.Context, location):
        v_pos = self.matrix_world.to_translation()

        ui_scale = context.preferences.system.ui_scale
        d_gizmo_size = context.preferences.view.gizmo_size
        radius = d_gizmo_size / 3
        d_gizmo_size += radius if self.draw_style == 'ARROW' else 10

        if self.is_up:
            left = v_pos.x - 20 * ui_scale
            right = v_pos.x + 20 * ui_scale
            bottom = v_pos.y - 20 * ui_scale
            top = v_pos.y + d_gizmo_size * ui_scale
        else:
            left = v_pos.x - 20 * ui_scale
            right = v_pos.x + d_gizmo_size * ui_scale
            bottom = v_pos.y - 20 * ui_scale
            top = v_pos.y + 20 * ui_scale

        if ZuvTrimsheetUtils.pointInRect(location, left, top, right, bottom):
            return 0

        return -1

    def setup(self):
        if not hasattr(self, 'is_up'):
            self.is_up = False
            self.init_mtx_world = Matrix()
            self.draw_style = 'ARROW'
            self.last_update = 0

    def _update_offset_matrix(self):
        v_pos = Vector((0, 0, self.target_get_value("offset")[0]))
        self.matrix_offset = Matrix.Translation(v_pos)

    def invoke(self, context, event: bpy.types.Event):
        self.init_mouse = event.mouse_y if self.is_up else event.mouse_x

        self.init_value = self.target_get_value("offset")[0]

        self.init_mtx_world = self.matrix_world.copy()
        self.last_update = 0
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        context.area.header_text_set(None)
        if cancel:
            self.target_set_value("offset", self.init_value)

    def modal(self, context: bpy.types.Context, event: bpy.types.Event, tweak):
        # Filter with 60 FPS
        if timer() - self.last_update >= 1/60:
            delta = 0
            if self.is_up:
                delta = self.init_mouse - event.mouse_y
            else:
                delta = self.init_mouse - event.mouse_x
            if 'SNAP' in tweak:
                delta = round(delta)
            if 'PRECISE' in tweak:
                delta /= 10.0
            value = self.init_value - delta

            self.target_set_value("offset", (value,))
            self.last_update = timer()
        return {'RUNNING_MODAL'}
