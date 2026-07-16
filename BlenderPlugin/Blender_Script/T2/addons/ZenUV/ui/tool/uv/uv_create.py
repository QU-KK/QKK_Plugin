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
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix

from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.blender_zen_utils import ZenPolls

from .uv_base import ZuvUVGizmoBase


if not bpy.app.background:
    if ZenPolls.version_lower_3_4_0:
        shader_line = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    else:
        if ZenPolls.version_lower_3_5_0:
            shader_line = gpu.shader.from_builtin('2D_POLYLINE_UNIFORM_COLOR')
        else:
            shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')


class UV_GT_zenuv_trim_create(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_trim_create"
    bl_target_properties = ()

    __slots__ = (
        "custom_shape",
        'mouse_x',
        'mouse_y'
    )

    def draw_cross(self, context: bpy.context):
        if self.mouse_x is None or self.mouse_y is None:
            return

        cursor_x = self.mouse_x
        cursor_y = self.mouse_y

        p_size = 50

        shader_line.bind()

        if not ZenPolls.version_lower_3_4_0:
            region = context.region
            imm_viewport = (region.width, region.height)

            shader_line.uniform_float('viewportSize', imm_viewport)

        addon_prefs = get_prefs()
        p_active_border_color = list(addon_prefs.trimsheet.active_border_color[:3]) + [1.0]

        batch_cross = batch_for_shader(
            shader_line, 'LINES', {"pos": [(cursor_x - p_size, cursor_y), (cursor_x + p_size, cursor_y)]}, indices=[(0, 1)])
        shader_line.bind()
        shader_line.uniform_float("color", p_active_border_color)
        batch_cross.draw(shader_line)

        batch_cross_1 = batch_for_shader(
            shader_line, 'LINES', {"pos": [(cursor_x, cursor_y - p_size), (cursor_x, cursor_y + p_size)]}, indices=[(0, 1)])
        shader_line.bind()
        shader_line.uniform_float("color", p_active_border_color)
        batch_cross_1.draw(shader_line)

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        self.draw_custom_shape(self.custom_shape, matrix=self.matrix_world)

        self.draw_cross(context)

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def test_select(self, context: bpy.types.Context, location):

        self.mouse_x = location[0]
        self.mouse_y = location[1]

        v_pos, _, v_sca = self.matrix_world.decompose()

        left = v_pos.x - (0.5 * v_sca.x)
        right = v_pos.x + (0.5 * v_sca.x)
        bottom = v_pos.y - (0.5 * v_sca.y)
        top = v_pos.y + (0.5 * v_sca.y)

        if ZuvTrimsheetUtils.pointInRect(location, left, top, right, bottom):
            context.area.tag_redraw()
            return 0

        self.mouse_x = None
        self.mouse_y = None

        return -1

    def draw_select(self, context: bpy.types.Context, select_id):
        self._do_draw(context, select_id=select_id)

    def setup(self):
        if not hasattr(self, "custom_shape"):
            custom_shape_verts = (
                (-0.5, -0.5), (-0.5, 0.5), (0.5, 0.5),
                (0.5, 0.5), (0.5, -0.5), (-0.5, -0.5)
            )

            self.custom_shape = self.new_custom_shape('TRIS', custom_shape_verts)
            self.mouse_x = None
            self.mouse_y = None

    def exit(self, context, cancel):
        context.area.header_text_set(None)


class ZUV_GGT_UVTrimCreate(bpy.types.GizmoGroup, ZuvUVGizmoBase):
    bl_idname = "ZUV_GGT_UVTrimCreate"
    bl_label = "Trim Create"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SHOW_MODAL_ALL',
    } if bpy.app.version < (3, 3, 0) else {
        'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL',
    }

    tool_mode = {'CREATE'}

    def _setup_dragged(self, context: bpy.types.Context):
        self.mpr_trim_create = self.gizmos.new("UV_GT_zenuv_trim_create")
        self.mpr_trim_create.hide_select = False
        self.mpr_trim_create.use_select_background = True
        self.mpr_trim_create.use_draw_scale = False
        self.mpr_trim_create.target_set_operator('uv.zuv_trim_create')

    def _setup_trimsheet_colors(self, context: bpy.types.Context, p_trimsheet, p_active_color):
        # inherited
        super()._setup_trimsheet_colors(context, p_trimsheet, p_active_color)

        addon_prefs = get_prefs()

        p_scene = context.scene

        b_is_create_mode = p_scene.zen_uv.ui.uv_tool.mode

        self.mpr_trim_create.hide = not b_is_create_mode
        if not self.mpr_trim_create.hide:
            self.mpr_trim_create.color = addon_prefs.trimsheet.background_color[:3]
            self.mpr_trim_create.color_highlight = addon_prefs.trimsheet.background_color[:3]
            self.mpr_trim_create.alpha = addon_prefs.trimsheet.background_color[-1]
            self.mpr_trim_create.alpha_highlight = addon_prefs.trimsheet.background_color[-1]

    def _setup_matrices_final(self, context: bpy.types.Context):
        # inherited
        super()._setup_matrices_final(context)

        if not self.mpr_trim_create.hide:

            ui_scale = context.preferences.system.ui_scale

            p_offsets = ZuvTrimsheetUtils.get_area_offsets(context.area)
            n_top_offset = p_offsets.get('top')
            n_right_offset = 30 * ui_scale
            n_left_offset = p_offsets.get('left')
            n_bottom_offset = p_offsets.get('bottom') + 10 * ui_scale

            v_sca = Vector((context.area.width - n_left_offset - n_right_offset, context.area.height - n_top_offset - n_bottom_offset, 1.0))

            v_region_center = Vector((v_sca.x / 2 + n_left_offset, v_sca.y / 2 + n_bottom_offset, 0))
            self.mpr_trim_create.matrix_basis = (
                Matrix.Translation(v_region_center) @
                Matrix.Diagonal(v_sca).to_4x4())
