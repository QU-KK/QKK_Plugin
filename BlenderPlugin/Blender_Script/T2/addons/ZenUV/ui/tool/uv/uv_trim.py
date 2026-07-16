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
from mathutils import Matrix, Vector

from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.ops.trimsheets.trimsheet_modal import BoxSelectRect
from ZenUV.utils.blender_zen_utils import ZenPolls, ZenCompat
from ZenUV.utils.simple_geometry import TextRect
from ZenUV.utils.constants import UV_AREA_BBOX


if not bpy.app.background:
    if ZenPolls.version_lower_3_4_0:
        shader_line = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
    else:
        if ZenPolls.version_lower_3_5_0:
            shader_line = gpu.shader.from_builtin('2D_POLYLINE_UNIFORM_COLOR')
        else:
            shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')


class UV_GT_zenuv_trim_select(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_trim_select"
    bl_target_properties = ()

    __slots__ = (
        "dimensions",
        "text",
        "active",
        "text_enabled",

        "fill_color",
        "fill_alpha",
        "border_color",
        "border_alpha",
        "text_color",
        "text_align",
        "text_offset",
        "text_offset_mode",

        "custom_shape",
        "custom_shape_border",
        "custom_dimensions",
        "custom_label"
    )

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        self._check_main_shape()

        self.color = self.fill_color
        self.color_highlight = self.fill_color
        self.alpha = self.fill_alpha
        self.alpha_highlight = min(1.0, self.fill_alpha * 2)

        p_scene = context.scene

        if not self.hide_select:
            self.draw_custom_shape(self.custom_shape, select_id=select_id)

        if not self.active or p_scene.zen_uv.ui.uv_tool.tr_handles != 'OFF':
            _, shader = self.custom_shape_border

            shader.bind()

            if not ZenPolls.version_lower_3_4_0:
                region = context.region
                imm_viewport = (region.width, region.height)

                shader.uniform_float('viewportSize', imm_viewport)

            gpu.state.blend_set('ALPHA')

            self.color = (0, 0, 0)
            self.alpha = self.border_alpha

            if not ZenPolls.version_lower_3_4_0:
                shader.bind()
                shader.uniform_float('lineWidth', 4)

            self.draw_custom_shape(self.custom_shape_border, select_id=select_id)

            self.color = self.border_color
            self.color_highlight = self.border_color
            self.alpha = self.border_alpha
            self.alpha_highlight = 1.0

            if not ZenPolls.version_lower_3_4_0:
                shader.bind()
                shader.uniform_float('lineWidth', 1)

            self.draw_custom_shape(self.custom_shape_border, select_id=select_id)

            gpu.state.blend_set('NONE')

        if self.text_enabled and self.text:
            self.build_custom_label(context)

            if (
                    self.is_highlight or self.active or
                    not any(
                        self.custom_label.intersects(it_r)
                        for it_r in self.group.handled_text_rects)):
                self.custom_label.draw_text()
                self.group.handled_text_rects.add(self.custom_label)

    def build_custom_label(self, context: bpy.types.Context):
        addon_prefs = get_prefs()
        ui_scale = context.preferences.system.ui_scale

        i_font_size = addon_prefs.trimsheet.font_size * ui_scale
        if addon_prefs.trimsheet.scale_font:
            i_font_size *= context.space_data.zoom[0]

        ZenCompat.blf_font_size(i_font_size, ui_scale)

        self.custom_label.name = self.text

        p_bbox = UV_AREA_BBOX.get_bbox_with_center_in(Vector((0, 0)))
        v_text_center: Vector = getattr(p_bbox, self.text_align)
        v_text_center = (
            self.matrix_basis @
            Matrix.Diagonal(Vector((self.dimensions[0], self.dimensions[1], 0))).to_4x4() @
            v_text_center.resized(3))

        left, top, right, bottom = ZuvTrimsheetUtils.getTrimTextAlignmentBounds(
            v_text_center, self.dimensions[0], self.dimensions[1],
            self.text, self.active, self
        )

        # NOTE: 'left, bottom' are required to draw label
        self.custom_label.left = left
        self.custom_label.bottom = bottom
        self.custom_label.right = right
        self.custom_label.top = top

        self.custom_label.color = (*self.text_color, 1)

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def test_select(self, context: bpy.types.Context, location):
        if not self.hide_select:
            v_pos = self.matrix_world.to_translation()

            left = v_pos.x - self.dimensions[0] / 2
            right = v_pos.x + self.dimensions[0] / 2
            bottom = v_pos.y - self.dimensions[1] / 2
            top = v_pos.y + self.dimensions[1] / 2

            if ZuvTrimsheetUtils.pointInRect(location, left, top, right, bottom):
                return 0

        return -1

    def draw_select(self, context: bpy.types.Context, select_id):
        self._do_draw(context, select_id=select_id)

    def _build_shape(self):

        self.custom_label = TextRect()

        custom_shape_verts = (
            (-0.5, -0.5), (-0.5, 0.5), (0.5, 0.5),
            (0.5, 0.5), (0.5, -0.5), (-0.5, -0.5)
        )

        if self.dimensions != (0, 0, 0):
            custom_shape_verts = [(co[0] * self.dimensions[0], co[1] * self.dimensions[1]) for co in custom_shape_verts]

        self.custom_shape = self.new_custom_shape('TRIS', custom_shape_verts)

        self.custom_shape_border = [None, shader_line]

        self.custom_shape_border[0] = batch_for_shader(
            shader_line, 'LINE_LOOP',
            {"pos": custom_shape_verts})
        self.custom_shape_border[0].program_set(shader_line)

    def _check_main_shape(self):
        if self.custom_dimensions != self.dimensions:
            self.custom_dimensions = self.dimensions

            self._build_shape()

    def setup(self):
        self.line_width = 3
        if not hasattr(self, "custom_shape"):
            self.custom_dimensions = (0, 0, 0)
            self.dimensions = (0, 0, 0)
            self.text = ''
            self.active = False
            self.fill_color = (1, 1, 1)
            self.fill_alpha = 0.0
            self.border_color = (1, 1, 1)
            self.border_alpha = 1.0
            self.text_color = (1, 1, 1)
            self.text_enabled = False
            self.text_align = 'cen'
            self.text_offset = (0, 0)
            self.text_offset_mode = 'POINT'

            self._build_shape()

    def exit(self, context, cancel):
        context.area.header_text_set(None)


class UV_GT_zenuv_trim_box_select(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_trim_box_select"
    bl_target_properties = ()

    __slots__ = (
        "custom_shape",
        'mouse_x',
        'mouse_y'
    )

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        # self.draw_custom_shape(self.custom_shape, matrix=self.matrix_world)

        t_data = bpy.app.driver_namespace.get('zenuv_box_select', {})
        box_rect: BoxSelectRect = t_data.get(context.area.as_pointer(), None)
        if box_rect:

            # Special case if dragging started inside of trim
            if box_rect.trim_index != -1:
                p_gizmo_group = self.group
                if p_gizmo_group:
                    if box_rect.trim_index in range(len(p_gizmo_group.mpr_trim_select)):
                        p_gizmo_group.mpr_trim_select[box_rect.trim_index]._do_draw(context)

            mtx_pos = Matrix.Translation(Vector(box_rect.center()).resized(3))
            mtx_sca = Matrix.Diagonal(Vector((box_rect.width / 2, box_rect.height / 2, 1.0))).to_4x4()
            mtx = mtx_pos @ mtx_sca
            gpu.state.blend_set('ALPHA')
            self.draw_preset_box(mtx)
            gpu.state.blend_set('NONE')

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def test_select(self, context: bpy.types.Context, location):
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


class UV_GT_zenuv_trim_select_background(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_trim_select_background"
    bl_target_properties = ()

    __slots__ = (
        "custom_shape",
    )

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        ui_scale = context.preferences.system.ui_scale

        p_offsets = ZuvTrimsheetUtils.get_area_offsets(context.area)
        n_top_offset = p_offsets.get('top')
        n_right_offset = 30 * ui_scale
        n_left_offset = p_offsets.get('left')
        n_bottom_offset = p_offsets.get('bottom') + 10 * ui_scale

        v_sca = Vector((context.area.width - n_left_offset - n_right_offset, context.area.height - n_top_offset - n_bottom_offset, 1.0))

        v_region_center = Vector((v_sca.x / 2 + n_left_offset, v_sca.y / 2 + n_bottom_offset, -1))
        self.matrix_basis = (
            Matrix.Translation(v_region_center) @
            Matrix.Diagonal(v_sca).to_4x4())

        self.draw_custom_shape(self.custom_shape, matrix=self.matrix_world)

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def test_select(self, context: bpy.types.Context, location):
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

    def exit(self, context, cancel):
        context.area.header_text_set(None)
