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

# Copyright 2023, Valeriy Yatsenko

import bpy

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.blender_zen_utils import update_areas_in_uv, update_areas_in_view3d
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.vlog import Log

from . td_utils import TdDrawUI


def zenuv_delayed_update_draw_all():
    context = bpy.context
    update_areas_in_uv(context)
    update_areas_in_view3d(context)


class TdProps:

    td_is_panel_controlled = bpy.props.BoolProperty(
        name='Use Settings from the UI Panel',
        description='If set to On, the operator will use the values of all properties from the Panel. Leave it Off if you are assigning the operator to a hotkey',
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'})

    def update_td_draw(self, context: bpy.types.Context, force):
        from ZenUV.ui.gizmo_draw import update_all_gizmos_3D, update_all_gizmos_UV
        p_scene = context.scene

        if p_scene.zen_uv.ui.draw_mode_UV in {'TEXEL_DENSITY', 'UV_BORDERS'}:
            update_all_gizmos_UV(context, force=force)

        if p_scene.zen_uv.ui.draw_mode_3D == 'TEXEL_DENSITY':
            update_all_gizmos_3D(context, force=force)

    def update_td_draw_submode(self, context: bpy.types.Context):
        TdProps.update_td_draw(self, context, force=False)

    def update_td_draw_force(self, context: bpy.types.Context):
        TdProps.update_td_draw(self, context, force=True)

    td_draw_submode = bpy.props.EnumProperty(
        name='Draw TD Mode',
        description='Texel density draw mode in combination of gradient and viewport',
        items=[
            ('ALL', 'All', 'Draw texel density gradient scale and mesh in the viewport'),
            ('GRADIENT', 'Gradient', 'Draw texel density gradient scale'),
            ('VIEWPORT', 'Viewport', 'Draw texel density mesh in the viewport'),
        ],
        options=set(),
        default='ALL',
        update=update_td_draw_submode
    )

    td_unit = bpy.props.EnumProperty(
        name='Units',
        description='Texel density calculation units',
        items=[
            ('km', 'px / km', 'KILOMETERS'),
            ('m', 'px / m', 'METERS'),
            ('cm', 'px / cm', 'CENTIMETERS'),
            ('mm', 'px / mm', 'MILLIMETERS'),
            ('um', 'px / um', 'MICROMETERS'),
            ('mil', 'px / mil', 'MILES'),
            ('ft', 'px / ft', 'FEET'),
            ('in', 'px / in', 'INCHES'),
            ('th', 'px / th', 'THOU')
        ],
        options=set(),
        default="m"
    )

    td_set_pivot = bpy.props.EnumProperty(
        name="Pivot",
        description='Set texel density pivot point',
        items=[
                ("br", 'Bottom-Right', '', 0),
                ("bl", 'Bottom-Left', '', 1),
                ("tr", 'Top-Right', '', 2),
                ("tl", 'Top-Left', '', 3),
                ("cen", 'Center', '', 4),
                ("rc", 'Right', '', 5),
                ("lc", 'Left', '', 6),
                ("bc", 'Bottom', '', 7),
                ("tc", 'Top', '', 8),
            ],
        default='cen'
    )

    def image_size_update_function(self, context: bpy.types.Context):

        if self.td_im_size_presets.isdigit():
            self.TD_TextureSizeX = self.TD_TextureSizeY = int(self.td_im_size_presets)

        TdProps.update_td_draw_force(self, context)

    td_im_size_presets = bpy.props.EnumProperty(
        name=ZuvLabels.PREF_TD_TEXTURE_SIZE_LABEL,
        description=ZuvLabels.PREF_IMAGE_SIZE_PRESETS_DESC,
        items=[
            ('16', '16', ''),
            ('32', '32', ''),
            ('64', '64', ''),
            ('128', '128', ''),
            ('256', '256', ''),
            ('512', '512', ''),
            ('1024', '1024', ''),
            ('2048', '2048', ''),
            ('4096', '4096', ''),
            ('8192', '8192', ''),
            ('Custom', 'Custom', '')
        ],
        default='1024',
        options=set(),
        update=image_size_update_function)

    TD_TextureSizeX = bpy.props.IntProperty(
        name='Custom Res, X',
        description=ZuvLabels.PREF_TD_TEXTURE_SIZE_DESC + ', X axis',
        min=1,
        options=set(),
        default=1024,
        update=update_td_draw_force)

    TD_TextureSizeY = bpy.props.IntProperty(
        name='Custom Res, Y',
        description=ZuvLabels.PREF_TD_TEXTURE_SIZE_DESC + ', Y axis',
        min=1,
        options=set(),
        default=1024,
        update=update_td_draw_force)


class ZUV_TdColors(bpy.types.PropertyGroup):

    col_equal: bpy.props.FloatVectorProperty(  # ex col_equal
        name=ZuvLabels.TD_COLOR_EQUAL_LABEL,
        description=ZuvLabels.TD_COLOR_EQUAL_DESC,
        subtype='COLOR',
        default=[0.0, 1.0, 0.0],
        size=3,
        min=0,
        max=1,
        options=set(),
        update=TdProps.update_td_draw_force
    )

    col_less: bpy.props.FloatVectorProperty(  # ex col_less
        name=ZuvLabels.TD_COLOR_LESS_LABEL,
        description=ZuvLabels.TD_COLOR_LESS_DESC,
        subtype='COLOR',
        default=[0.0, 0.0, 1.0],
        size=3,
        min=0,
        max=1,
        options=set(),
        update=TdProps.update_td_draw_force
    )

    col_over: bpy.props.FloatVectorProperty(  # ex col_over
        name=ZuvLabels.TD_COLOR_OVER_LABEL,
        description=ZuvLabels.TD_COLOR_OVER_DESC,
        subtype='COLOR',
        default=[1.0, 0.0, 0.0],
        size=3,
        min=0,
        max=1,
        options=set(),
        update=TdProps.update_td_draw_force
    )

    def get_sel_col_lower(self):
        from ZenUV.ui.gizmo_draw import GradientProperties
        from . td_display_utils import TdDisplayLimits

        try:
            idx = GradientProperties.range_values.index(TdDisplayLimits.lower_limit)
            return GradientProperties.range_colors[idx]
        except Exception as e:
            Log.debug(e)
        return [0, 0, 1]

    def get_sel_col_equal(self):
        from ZenUV.ui.gizmo_draw import GradientProperties
        from . td_display_utils import TdDisplayLimits

        try:
            idx = GradientProperties.range_values.index(TdDisplayLimits.middle)
            return GradientProperties.range_colors[idx]
        except Exception as e:
            Log.debug(e)
        return [0, 1, 0]

    def get_sel_col_over(self):
        from ZenUV.ui.gizmo_draw import GradientProperties
        from . td_display_utils import TdDisplayLimits

        try:
            idx = GradientProperties.range_values.index(TdDisplayLimits.upper_limit)
            return GradientProperties.range_colors[idx]
        except Exception as e:
            Log.debug(e)
        return [1, 0, 0]

    sel_col_equal: bpy.props.FloatVectorProperty(
        name=ZuvLabels.TD_COLOR_EQUAL_LABEL,
        description=ZuvLabels.TD_COLOR_EQUAL_DESC,
        subtype='COLOR',
        size=3,
        min=0,
        max=1,
        options=set(),
        get=get_sel_col_equal
    )

    sel_col_less: bpy.props.FloatVectorProperty(
        name=ZuvLabels.TD_COLOR_LESS_LABEL,
        description=ZuvLabels.TD_COLOR_LESS_DESC,
        subtype='COLOR',
        size=3,
        min=0,
        max=1,
        options=set(),
        get=get_sel_col_lower
    )

    sel_col_over: bpy.props.FloatVectorProperty(
        name=ZuvLabels.TD_COLOR_OVER_LABEL,
        description=ZuvLabels.TD_COLOR_OVER_DESC,
        subtype='COLOR',
        size=3,
        min=0,
        max=1,
        options=set(),
        get=get_sel_col_over
    )


class ZUV_TdDrawProperties(bpy.types.PropertyGroup):

    def update_influence(self, context: bpy.types.Context):
        from .td_islands_storage import TdDataStorage as TDS

        from ZenUV.ui.gizmo_draw import LITERAL_ZENUV_TD_SCOPE
        bpy.app.driver_namespace[LITERAL_ZENUV_TD_SCOPE] = None

        TDS.calc_td_scope(context, self.influence)

        TdProps.update_td_draw_force(self, context)

    influence: bpy.props.EnumProperty(
        name="Mode",
        description="Calculation mode. For each Face or for each Island",
        items=[
            ("FACE", "Face", "For each Face", 'UV_FACESEL', 0),
            ("ISLAND", "Island", "For each Island", 'UV_ISLANDSEL', 1),
            ],
        options=set(),
        default='ISLAND',
        update=update_influence)

    display_method: bpy.props.EnumProperty(
        name="Method",
        description="Texel Density display method",
        items=[
            ("BALANCED", "Balanced", """The value specified in TD Checker will always be the middle color from the user's preferences.
Smaller values are like the first, larger values are like the last""", 'FILE_VOLUME', 1),
            ("SPECTRUM", "Spectrum", "A method for displaying textel density using different color schemes and a specified density range", 'SEQ_HISTOGRAM', 2),
            ("PRESETS", "Presets", "Display texel density presets", 'PRESET', 3),
            ],
        default='SPECTRUM',
        options=set(),
        update=TdProps.update_td_draw_force
    )

    color_scheme_name: bpy.props.EnumProperty(
        name="Color Scheme",
        description="Color Scheme",
        items=[
            ("USER_THREE", "Three Color", "Three colours are used based on user preferences"),
            ("FULL_SPEC", "Full spectrum", "Full spectrum consisting of seven primary colors"),
            ("REVERSED_SPEC", "Reversed spectrum", "The full spectrum of the primary seven colors is reversed"),
            ("USER_LINEAR", "Linear", "Two-color gradient. Colors match the first and last color from the user's preferences"),
            ("MONO", "Mono", "Monochromatic scheme for easy determination of texel density values that fall outside the specified range")
            ],
        default='USER_THREE',
        options=set(),
        update=TdProps.update_td_draw_force)

    is_range_manual: bpy.props.BoolProperty(
        name="Range type",
        description="Adjust the range settings manually or automatically",
        default=False,
        options=set(),
        update=TdProps.update_td_draw_force)

    enable_gradient_widget: TdDrawUI.enable_gradient_widget

    values_filter: TdDrawUI.values_filter

    use_presets_only: bpy.props.BoolProperty(
        name='Presets Only',
        description='Show only texture density values that exist in the preset list. All other values will be displayed in black',
        default=False,
        options=set(),
        update=TdProps.update_td_draw_force)

    # MODE: DEFAULT, BAKE
    def draw(self, context: bpy.types.Context, layout: bpy.types.UILayout, mode='DEFAULT'):
        from .td_utils import TdDrawUI

        col = layout.column(align=False)
        col.use_property_split = True

        addon_prefs = get_prefs()

        if mode == 'BAKE':
            col.prop(self, 'influence')
            col.prop(self, 'display_method')

        if self.display_method == 'PRESETS':
            col.prop(self, 'use_presets_only')
            if mode != 'BAKE':
                col.prop(addon_prefs.td_draw, 'alpha')
            box = layout.box()

            TdDrawUI.draw_current_td_limits(context, box)
        else:
            row = col.row()
            row.enabled = self.display_method == 'SPECTRUM'
            row.prop(self, 'color_scheme_name')

            col = layout.column(align=False)
            self.draw_colors(context, col)

            if mode != 'BAKE':
                col.prop(addon_prefs.td_draw, 'alpha')

            box = layout.box()

            TdDrawUI.draw_current_td_limits(context, box)

            if self.display_method == 'SPECTRUM':
                self.draw_spectrum_method_settings(context, box)
            else:
                self.draw_balanced_method_settings(context, box)

    def draw_spectrum_method_settings(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        row_main = layout.row(align=True)
        row_main.enabled = not self.is_td_are_uniform()
        row = row_main.row(align=True)
        row.enabled = self.is_range_manual
        text = 'User Limits' if self.is_range_manual else 'Auto Limits'
        wm = context.window_manager
        row.prop(wm.zen_uv.td_props, 'td_limits_ui', text=text)
        self.draw_manual_switch(row_main)

    def draw_balanced_method_settings(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        row_main = layout.row(align=True)
        row_main.enabled = not self.is_td_are_uniform()
        row = row_main.row(align=True)
        row.prop(context.window_manager.zen_uv.td_props, 'balanced_checker_ui')
        row.enabled = self.is_range_manual
        self.draw_manual_switch(row_main)

    def draw_manual_switch(self, layout: bpy.types.UILayout):
        ico = 'EVENT_M' if self.is_range_manual else 'EVENT_A'
        layout.prop(self, 'is_range_manual', toggle=True, icon=ico, text='')

    def draw_colors(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        p_col_path = context.scene.zen_uv.td_props.colors
        row = layout.row(align=True)
        row.enabled = self._is_colors_enabled()
        row.prop(p_col_path, "col_less", text='')
        m_row = row.row(align=True)
        m_row.enabled = not self.color_scheme_name == 'USER_LINEAR'
        m_row.prop(p_col_path, "col_equal", text='')
        row.prop(p_col_path, "col_over", text='')

    def _is_colors_enabled(self) -> bool:
        p_ch = self.color_scheme_name
        return not (p_ch == 'FULL_SPEC' or p_ch == 'REVERSED_SPEC' or p_ch == 'MONO')

    def is_td_are_uniform(self) -> bool:
        from .td_display_utils import TdDisplayLimits
        return TdDisplayLimits.lower_limit == TdDisplayLimits.upper_limit


class ZUV_TdProperties(bpy.types.PropertyGroup):

    colors: bpy.props.PointerProperty(name='Texel Density Colors', type=ZUV_TdColors)

    prp_current_td: bpy.props.FloatProperty(  # ex TexelDensity
        name=ZuvLabels.PREF_TEXEL_DENSITY_LABEL,
        description=ZuvLabels.PREF_TEXEL_DENSITY_DESC,
        min=0.001,
        default=1024.0,
        precision=2
    )

    td_global_preset: bpy.props.FloatProperty(  # ex td_checker
        name='Project TD',
        description='The average value of the texel density used in the current project',
        min=0.001,
        default=47.59,
        precision=2
    )

    td_set_mode: bpy.props.EnumProperty(  # ex td_set_mode
        name=ZuvLabels.PREF_TD_SET_MODE_LABEL,
        description=ZuvLabels.PREF_TD_SET_MODE_DESC,
        items=[
            (
                'ISLAND',
                ZuvLabels.PREF_SET_PER_ISLAND_LABEL,
                ZuvLabels.PREF_SET_PER_ISLAND_DESC
            ),
            (
                'OVERALL',
                ZuvLabels.PREF_SET_OVERALL_LABEL,
                ZuvLabels.PREF_SET_OVERALL_DESC
            ),
        ],
        default='OVERALL'
    )

    prp_uv_coverage: bpy.props.FloatProperty(  # ex UVCoverage
        name=ZuvLabels.PREF_UV_COVERAGE_LABEL,
        description=ZuvLabels.PREF_UV_DENSITY_DESC,
        min=0.001,
        default=1.0,
        precision=3
    )

    td_unit: TdProps.td_unit
    TD_TextureSizeX: TdProps.TD_TextureSizeX
    TD_TextureSizeY: TdProps.TD_TextureSizeY
    td_im_size_presets: TdProps.td_im_size_presets

    td_select_type: bpy.props.EnumProperty(
        name="Select",
        description='Selection mode',
        items=[
            ('UNDERRATED', 'Underrated', 'Select islands with a TD value less than the smallest TD value in the presets'),
            ('OVERRATED', 'Overrated', 'Select islands with a TD value greater than the highest TD value in the presets'),
            ('BY_VALUE', 'By Value', 'Select islands with a TD that matches the TD value selected in the presets')
        ],
        default="BY_VALUE"
    )
    td_range_mode: bpy.props.EnumProperty(
        name="Mode",
        description="Calculation mode. For selected objects or for entire scene",
        items=[
            ("SELECTION", "Selected Objects", "For selected objects"),
            ("SCENE", "Scene", "For scene"),
            ],
        default='SELECTION')
    td_use_pivot: bpy.props.BoolProperty(
        name='Use Pivot',
        description='Use Pivot Point when setting texel density',
        default=False
    )
    td_set_pivot: TdProps.td_set_pivot
    sz_current_size: bpy.props.FloatVectorProperty(
        name='Island Size',
        description='Represent size of the island',
        size=2,
        default=(1.0, 1.0),
        min=0.0
    )
    sz_keep_proportion: bpy.props.BoolProperty(
        name="Keep Proportion",
        default=True
    )
    SZ_TextureSizeX: bpy.props.IntProperty(  # ex TD_TextureSizeX
        name='Texture Size X',
        description='Image Size for Island Size computation',
        min=1,
        default=1024)

    SZ_TextureSizeY: bpy.props.IntProperty(  # ex TD_TextureSizeY
        name='Texture Size Y',
        description='Image Size for Island Size computation',
        min=1,
        default=1024)

    def image_size_for_size_update(self, context):
        if self.sz_im_size_presets.isdigit():
            self.SZ_TextureSizeX = self.SZ_TextureSizeY = int(self.sz_im_size_presets)

    sz_im_size_presets: bpy.props.EnumProperty(  # ex td_im_size_presets
        name='Image Size Presets:',
        description='Image Size Preset',
        items=[
            ('16', '16', ''),
            ('32', '32', ''),
            ('64', '64', ''),
            ('128', '128', ''),
            ('256', '256', ''),
            ('512', '512', ''),
            ('1024', '1024', ''),
            ('2048', '2048', ''),
            ('4096', '4096', ''),
            ('8192', '8192', ''),
            ('Custom', 'Custom', '')
        ],
        default='1024',
        update=image_size_for_size_update)

    def update_sz_units(self, context):
        p_correction = [self.TD_TextureSizeX, self.TD_TextureSizeY]
        if self.TD_TextureSizeX == 0 or self.TD_TextureSizeY == 0:
            p_correction = [1.0, 1.0]
        if self.sz_units == 'UNITS':
            self.sz_current_size = [self.sz_current_size[0] / p_correction[0], self.sz_current_size[1] / p_correction[1]]
        else:
            self.sz_current_size = [self.sz_current_size[0] * p_correction[0], self.sz_current_size[1] * p_correction[1]]

    sz_units: bpy.props.EnumProperty(
        name="Units",
        description='Isalnd size units',
        items=[
                ("UNITS", 'Un', 'UV Area units', 0),
                ("PIXELS", 'Px', 'Pixels', 1),
            ],
        default='PIXELS',
        update=update_sz_units
    )

    def upd_sz_x(self, context):
        if self.sz_active_x is False and self.sz_active_y is False:
            self.sz_active_y = True

    def upd_sz_y(self, context):
        if self.sz_active_x is False and self.sz_active_y is False:
            self.sz_active_x = True

    sz_active_x: bpy.props.BoolProperty(
        name="Active X Axis",
        description='Dependence on the X axis',
        default=True,
        update=upd_sz_x
    )
    sz_active_y: bpy.props.BoolProperty(
        name="Active Y Axis",
        description='Dependence on the Y axis',
        default=False,
        update=upd_sz_y
    )
    sz_set_pivot: bpy.props.EnumProperty(
        name="Pivot",
        description='Set texel density pivot point',
        items=[
                ("br", 'Bottom-Right', '', 0),
                ("bl", 'Bottom-Left', '', 1),
                ("tr", 'Top-Right', '', 2),
                ("tl", 'Top-Left', '', 3),
                ("cen", 'Center', '', 4),
                ("rc", 'Right', '', 5),
                ("lc", 'Left', '', 6),
                ("bc", 'Bottom', '', 7),
                ("tc", 'Top', '', 8),
            ],
        default='cen'
    )
    sz_use_pivot: bpy.props.BoolProperty(
        name='Use Pivot',
        description='Use Pivot Point when setting island size',
        default=False
    )
    sz_set_mode: bpy.props.EnumProperty(
        name='Set Size Mode',
        description='Mode for setting island size',
        items=[
            (
                'ISLAND',
                'Island mode',
                'Set size individually for every selected Island'
            ),
            (
                'OVERALL',
                'Overall Mode',
                'Set Texel Density for all selected Islands together'
            ),
        ],
        default='OVERALL'
    )
    td_calc_precision: bpy.props.IntProperty(
        name='TD Calc Precision',
        description="Specifies how many percent of the island's polygons will be used to determine the texel density. Experimental",
        min=1,
        max=100,
        subtype='PERCENTAGE',
        default=100,
    )


# Order is important!!!
classes = [
    ZUV_TdColors,
    ZUV_TdProperties,
    ZUV_TdDrawProperties
]


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)


if __name__ == "__main__":
    pass
