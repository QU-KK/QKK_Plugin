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
import gpu
from mathutils import Matrix
from gpu_extras.batch import batch_for_shader

from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.blender_zen_utils import ZenPolls


if not bpy.app.background:
    if ZenPolls.version_lower_3_5_0:
        shader_line = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    else:
        shader_line = gpu.shader.from_builtin('UNIFORM_COLOR')


class UV_GT_zenuv_trim_align(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_trim_align"
    bl_target_properties = ()

    __slots__ = (
        "custom_shape",
        "custom_shape_border",
        "direction",
        "is_pivot",
        "color_bottom_left"
    )

    def draw(self, context: bpy.types.Context):
        was_color = self.color.copy()
        was_alpha = self.alpha

        self.alpha = 1.0 if self.is_pivot else 0.75

        self.color = (0, 0, 0)
        self.color_highlight = (0, 0, 0)
        self.alpha_highlight = self.alpha

        d_scale = 1.0 if self.is_highlight else 0.6
        d_inner_scale = 0.8 if self.is_highlight else 0.4

        self.draw_custom_shape(
            self.custom_shape, matrix=self.matrix_world @ Matrix.Diagonal((d_scale, d_scale, 0.0)).to_4x4())

        self.color = self.color_bottom_left if self.direction == 'bl' else was_color
        self.color_highlight = self.color.copy()

        self.alpha = 1.0
        self.alpha_highlight = 1.0

        if self.is_pivot:
            if bpy.app.version < (3, 5, 0):
                import bgl
                bgl.glDisable(bgl.GL_LINE_SMOOTH)
            self.draw_custom_shape(self.custom_shape_border, matrix=self.matrix_world @ Matrix.Diagonal((d_inner_scale, d_inner_scale, 0.0)).to_4x4())
        else:
            self.draw_custom_shape(self.custom_shape, matrix=self.matrix_world @ Matrix.Diagonal((d_inner_scale, d_inner_scale, 0.0)).to_4x4())

        self.color = was_color
        self.alpha = was_alpha

        gpu.state.blend_set('NONE')

    def test_select(self, context: bpy.types.Context, location):
        v_pos = self.matrix_world.to_translation()

        left = v_pos.x - 10
        right = v_pos.x + 10
        bottom = v_pos.y - 10
        top = v_pos.y + 10

        if ZuvTrimsheetUtils.pointInRect(location, left, top, right, bottom):
            return 0

        return -1

    def setup(self):
        if not hasattr(self, "custom_shape"):
            custom_shape_verts = (
                (-0.5, -0.5, 0), (-0.5, 0.5, 0), (0.5, 0.5, 0),
                (0.5, 0.5, 0), (0.5, -0.5, 0), (-0.5, -0.5, 0)
            )
            self.custom_shape = self.new_custom_shape('TRIS', custom_shape_verts)

            self.custom_shape_border = [None, shader_line]

            custom_border_shape_verts = (
                (-0.5, -0.5, 0), (-0.5, 0.5, 0),
                (-0.5, 0.5, 0), (0.5, 0.5, 0),
                (0.5, 0.5, 0), (0.5, -0.5, 0),
                (0.5, -0.5, 0), (-0.5, -0.5, 0)
            )
            self.custom_shape_border[0] = batch_for_shader(
                shader_line, 'LINES',
                {"pos": custom_border_shape_verts})
            self.custom_shape_border[0].program_set(shader_line)

            self.direction = 'cen'
            self.is_pivot = False
            self.color_bottom_left = (0, 1, 0)

    def exit(self, context, cancel):
        context.area.header_text_set(None)
