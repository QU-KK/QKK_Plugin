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
from mathutils import Matrix, Vector
from gpu_extras.batch import batch_for_shader

from ZenUV.utils.blender_zen_utils import ZenPolls, ZenCompat, get_gizmo_scale
from ZenUV.utils.simple_geometry import draw_rounded_rect, Rectangle


if not bpy.app.background:
    if ZenPolls.version_lower_3_5_0:
        shader_line = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    else:
        shader_line = gpu.shader.from_builtin('UNIFORM_COLOR')


class ZuvTransformHandleBase:

    INACTIVE_COLOR = (0.5, 0.5, 0.5)

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def draw_select(self, context, select_id):
        self._do_draw(context, select_id=select_id)

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        # NOTE: we are creating square rectangle, round corners must be greater 1,
        #       that's why we shoud use sides greater that corners

        p_sca = self.matrix_basis.to_scale()

        rect_side = 4 if self.rect_side < 4 else self.rect_side
        if self.corner == 0:
            corner = int(min(rect_side * p_sca.x, rect_side * p_sca.y) / 2)
        else:
            corner = 2 if self.corner < 2 else round(self.corner)
            corner = rect_side / 2 if corner > rect_side / 2 else corner

        line_width = 1

        rect = Rectangle(-rect_side / 2 * p_sca.x, rect_side / 2 * p_sca.y, rect_side / 2 * p_sca.x, -rect_side / 2 * p_sca.y)

        uniform_shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
        line_shader = gpu.shader.from_builtin(ZenCompat.get_3d_polyline_smooth())

        view_width, view_height = context.region.width, context.region.height

        start = self.start.resized(3)
        v_scale = (self.end - self.start).resized(3)
        angle = v_scale.normalized().resized(2).angle_signed(Vector((0, 1)), 0.0)

        ui_scale = get_gizmo_scale(context)

        matrix = (
            Matrix.Translation(start + v_scale / 2) @ Matrix.Rotation(angle, 4, (0, 0, 1)).to_4x4()
            @ Matrix.Diagonal((ui_scale, ui_scale)).to_4x4())

        color = self.color_highlight if self.is_highlight else self.color
        alpha = self.alpha_highlight if self.is_highlight else self.alpha

        gpu.state.blend_set('ALPHA')

        with gpu.matrix.push_pop():
            gpu.matrix.multiply_matrix(matrix)

            draw_rounded_rect(
                rect,
                view_width, view_height,
                uniform_shader,
                (*color[:], alpha), 1, line_width,
                tl=corner, tr=corner, br=corner, bl=corner, outline=False)

            draw_rounded_rect(
                rect,
                view_width, view_height,
                line_shader,
                (*color[:], 1.0), 1, line_width,
                tl=corner, tr=corner, br=corner, bl=corner, outline=True)

        gpu.state.blend_set('NONE')

    def setup(self):
        if not hasattr(self, "start"):
            self.start = Vector((0, 0))
            self.end = Vector((0, 0))

            self.line_width = 1
            self.border_size = 2  # px: value for one side
            self.corner = 2
            self.rect_side = 4

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

    def test_select_internal(self, context: bpy.types.Context, location):

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
        x1, y1 = self.start.resized(3).to_tuple()[:2]  # Line segment start point
        x2, y2 = self.end.resized(3).to_tuple()[:2]  # Line segment end point

        res = is_point_on_line(x, y, x1, y1, x2, y2, tolerance=10)

        return 0 if res else -1

    def test_select(self, context: bpy.types.Context, location):
        res = self.test_select_internal(context, location)
        if res == 0:
            from .uv_transform_gizmo import ZUV_GGT_UVTransformGizmo
            p_group: ZUV_GGT_UVTransformGizmo = self.group
            p_group.unregister_tooltip()

        return res

    def exit(self, context: bpy.types.Context, cancel):
        context.area.header_text_set(None)
        context.area.tag_redraw()


class UV_GT_zenuv_transform_handle(bpy.types.Gizmo, ZuvTransformHandleBase):
    bl_idname = "UV_GT_zenuv_transform_handle"
    bl_target_properties = ()
