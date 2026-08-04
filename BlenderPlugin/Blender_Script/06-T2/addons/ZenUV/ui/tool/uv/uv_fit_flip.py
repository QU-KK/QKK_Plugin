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
from mathutils import Matrix, Quaternion
from gpu_extras.batch import batch_for_shader

from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.ops.event_service import get_blender_event
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.utils.blender_zen_utils import ZenPolls

from ..custom_gizmo_shapes import CustomShapes

if not bpy.app.background:
    if ZenPolls.version_lower_3_5_0:
        shader_line = gpu.shader.from_builtin('3D_POLYLINE_UNIFORM_COLOR')
    else:
        shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')


class UV_GT_zenuv_trim_fitflip(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_trim_fitflip"
    bl_target_properties = ()

    __slots__ = (
        "custom_shape_fit_op",
        "custom_shape_fit_2_op",

        "custom_shape_flip_op",
        "custom_shape_flip_2_op",

        "custom_shape_rot_op",
        "custom_shape_rot_2_op",

        "custom_shape_orient_op",

        "direction"
    )

    def draw_outline(self, context, p_shape, p_mtx):
        region = context.region
        imm_viewport = (region.width, region.height)

        was_color = self.color.copy()

        self.color = (0, 0, 0)
        self.alpha = 0.99  # Do not change

        shader_line.bind()
        shader_line.uniform_float('viewportSize', imm_viewport)
        shader_line.uniform_float('lineWidth', 4)
        self.draw_custom_shape(p_shape, matrix=p_mtx)

        b_is_left_bottom = self.direction == 'bl'
        if b_is_left_bottom:
            self.color = (0, 1.0, 0)
            self.alpha = 1

        if p_shape == self.custom_shape_flip_op:
            self.draw_custom_shape(
                    self.custom_shape_flip_2_op,
                    matrix=p_mtx)

        if p_shape == self.custom_shape_rot_op:
            self.draw_custom_shape(
                    self.custom_shape_rot_2_op,
                    matrix=p_mtx)

        if p_shape == self.custom_shape_fit_op:
            self.draw_custom_shape(
                self.custom_shape_fit_2_op,
                matrix=p_mtx)

        self.alpha = 0.99  # Do not change !!!
        self.color = was_color

        shader_line.bind()
        shader_line.uniform_float('lineWidth', 1)
        self.draw_custom_shape(p_shape, matrix=p_mtx)

    def draw(self, context):
        p_event_dict = get_blender_event()

        b_shift = p_event_dict.get('shift', False)
        b_ctrl = p_event_dict.get('ctrl', False)

        if b_shift and b_ctrl:
            if not self.direction == 'cen':
                self.draw_outline(
                    context, self.custom_shape_flip_op,
                    self.matrix_world @ Matrix.Diagonal((0.8, 0.8, 0)).to_4x4())
        elif b_shift:
            if not self.direction == 'cen':
                self.draw_outline(
                    context, self.custom_shape_fit_op,
                    self.matrix_world)
        elif b_ctrl:
            if not self.direction == 'cen' and self.direction not in UV_AREA_BBOX.bbox_middle_handles:
                self.draw_outline(
                    context, self.custom_shape_rot_op,
                    self.matrix_world)
            if self.direction in UV_AREA_BBOX.bbox_middle_handles:

                # Black Box under Orient Markers
                was_color = self.color.copy()
                was_alpha = self.alpha
                self.color = (0, 0, 0)
                self.alpha = 1.0
                self.draw_preset_box(
                    self.matrix_world @ Matrix.Diagonal(
                        (0.5, 0.05, 0)).to_4x4())
                self.alpha = was_alpha
                self.color = was_color

                # Orient markers
                self.draw_outline(
                    context, self.custom_shape_orient_op,
                    self.matrix_world)

    @classmethod
    def get_direction_rotation_matrix(cls, p_direction) -> Matrix:
        dir_vec = (UV_AREA_BBOX().cen - getattr(UV_AREA_BBOX, p_direction))
        q: Quaternion = dir_vec.to_3d().to_track_quat('X', 'Z')
        return q.to_matrix().to_4x4()

    def draw_select(self, context, select_id):
        pass

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
        if hasattr(self, "direction"):
            # 2-TWO WAY Flip Gizmo
            self.custom_shape_flip_op = [None, shader_line]
            self.custom_shape_flip_op[0] = batch_for_shader(
                shader_line, 'LINES',
                {"pos": CustomShapes.mirror_gizmo_lines})
            self.custom_shape_flip_op[0].program_set(shader_line)

            self.custom_shape_flip_2_op = self.new_custom_shape('TRIS', CustomShapes.mirror_gizmo_faces)

            # 1-ONE WAY Fit Gizmo
            self.custom_shape_fit_op = [None, shader_line]
            self.custom_shape_fit_op[0] = batch_for_shader(
                shader_line, 'LINES',
                {"pos": CustomShapes.one_way_arrow_lines})
            self.custom_shape_fit_op[0].program_set(shader_line)
            self.custom_shape_fit_2_op = self.new_custom_shape('TRIS', CustomShapes.one_way_arrow_faces)

            #  RADIAL Rotation Gizmo
            self.custom_shape_rot_op = [None, shader_line]
            self.custom_shape_rot_op[0] = batch_for_shader(
                shader_line, 'LINES',
                {"pos": CustomShapes.rotate_gizmo_lines})
            self.custom_shape_rot_op[0].program_set(shader_line)
            self.custom_shape_rot_2_op = self.new_custom_shape('TRIS', CustomShapes.rotate_gizmo_faces)

            # Rotation ORIENT
            self.custom_shape_orient_op = [None, shader_line]
            self.custom_shape_orient_op[0] = batch_for_shader(
                shader_line, 'LINES',
                {"pos": CustomShapes.orient_gizmo_lines})
            self.custom_shape_orient_op[0].program_set(shader_line)

    def exit(self, context, cancel):
        context.area.header_text_set(None)
