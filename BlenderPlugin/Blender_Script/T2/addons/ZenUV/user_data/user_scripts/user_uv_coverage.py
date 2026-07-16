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

# Copyright 2023, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy
import blf
from mathutils import Color

from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.blender_zen_utils import ZenDrawConstants


class ZUV_GGT_UVCoverage(bpy.types.GizmoGroup):
    bl_idname = "ZUV_GGT_UVCoverage"
    bl_label = "Trim Viewport Selector"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    def draw_prepare(self, context: bpy.types.Context):
        p_view = context.preferences.view
        ui_scale = context.preferences.system.ui_scale
        widget_size = ((ZenDrawConstants.GIZMO_ICON_SIZE / 2) + 8) * ui_scale

        widget_height = ZenDrawConstants.GIZMO_SIZE * ui_scale

        i_add_y = 0
        if p_view.mini_axis_type == 'MINIMAL':
            i_add_y += p_view.mini_axis_size * 2 * ui_scale
        elif p_view.mini_axis_type == 'GIZMO':
            i_add_y += p_view.gizmo_size_navigate_v3d * ui_scale

        p_offsets = ZuvTrimsheetUtils.get_area_offsets(context.area)

        n_panel_width = p_offsets.get('right')
        base_position = context.region.width - n_panel_width - widget_size
        self.foo_gizmo.matrix_basis[0][3] = base_position

        i_gizmo_col = ZenDrawConstants.GIZMO_COLUMN_INDICES.get('UV_COVERAGE', 0)
        widget_y = (
            context.region.height - p_offsets.get('top') - widget_height * i_gizmo_col - i_add_y)
        self.foo_gizmo.matrix_basis[1][3] = widget_y

        uv_coverage = context.scene.zen_uv.td_props.prp_uv_coverage
        font_id = 0
        empty_space = 100.0 - uv_coverage

        # Draw some text

        font_size = 14 * ui_scale

        blf.size(font_id, font_size)
        s_line_1 = "UV Coverage: %.2f %%" % uv_coverage
        s_line_2 = "Empty Space: %.2f %%" % empty_space

        x_1, y_1 = blf.dimensions(font_id, s_line_1)
        x_2, y_2 = blf.dimensions(font_id, s_line_2)

        x_text = base_position - max(x_1, x_2) - widget_size

        blf.position(font_id, x_text, widget_y + y_1 / 2, 0)
        blf.draw(font_id, s_line_1)

        blf.position(font_id, x_text, widget_y - y_1, 0)
        blf.draw(font_id, s_line_2)

    def setup(self, context):
        mpr = self.gizmos.new("GIZMO_GT_button_2d")
        mpr.show_drag = False
        mpr.icon = 'MOD_UVPROJECT'
        mpr.draw_options = {'BACKDROP', 'OUTLINE'}

        mpr.color = Color((0.02, 0.68, 0.53))
        mpr.alpha = 0.4
        mpr.color_highlight = Color((0.02, 0.68, 0.53))
        mpr.alpha_highlight = 0.2

        mpr.scale_basis = (80 * 0.35) / 2  # Same as buttons defined in C
        _ = mpr.target_set_operator("uv.zenuv_get_uv_coverage")
        self.foo_gizmo = mpr

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'EDIT_MESH', 'OBJECT'}


classes = (
    ZUV_GGT_UVCoverage,
)


def register():
    print('Starting Zen UV user script...')
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    print('Finishing Zen UV user script...')
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
