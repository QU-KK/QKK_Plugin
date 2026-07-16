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

""" Zen UV Texel Density Tools """


import bpy
import bmesh

from ZenUV.utils.register_util import RegisterUtils

from .td_islands_storage import TdDataStorage as TDS
from .td_utils import TdUtils, TdContext

from ZenUV.utils.generic import (
    UnitsConverter,
    resort_by_type_mesh_in_edit_mode_and_sel,
    switch_shading_style
)
from ZenUV.utils.vlog import Log


class TDPR_OT_CreatePresets(bpy.types.Operator):
    """ Create presets from selected island"""
    bl_idname = "zen_tdpr.create_presets_from_islands"
    bl_label = 'Create Presets'
    bl_description = 'Creates new presets from selected islands'
    bl_options = {'REGISTER', 'UNDO'}

    colorize: bpy.props.BoolProperty(
        name='Colorize',
        description='Assign colors to the created presets according to the current color scheme in the Display TD system',
        default=True
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from .td_presets import new_list_item
        from .td_display_utils import TdSysUtils

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        td_inputs = TdContext(context)
        td_inputs.selected_only = True

        Scope = TdUtils.get_td_data_with_precision(context, objs, td_inputs, False)

        if not len(Scope.islands):
            self.report({'INFO'}, "No selected islands.")
            return {'CANCELLED'}

        scene = context.scene
        r_to = UnitsConverter.get_count_after_point(TdUtils.get_current_units_string(context, full=False)) + 1
        p_values = [round(i.value, r_to) for i in scene.zen_tdpr_list]

        count = 0
        for i in Scope.islands:
            p_value = round(i.td, r_to)
            if p_value not in p_values:
                p_values.append(p_value)
                new_list_item(context)
                scene.zen_tdpr_list[scene.zen_tdpr_list_index].value = p_value
                count += 1

        if count == 0:
            self.report({'INFO'}, "All values are already in the list.")
            return {'CANCELLED'}

        TdSysUtils.update_display_presets(context)

        if self.colorize:
            if bpy.ops.zen_tdpr.colorize_presets.poll():
                bpy.ops.zen_tdpr.colorize_presets()

        from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetUtils
        ZuvTrimsheetUtils.fix_undo()

        return {'FINISHED'}


class TDPR_OT_ColorizePresets(bpy.types.Operator):
    bl_idname = "zen_tdpr.colorize_presets"
    bl_label = 'Colorize Presets'
    bl_description = 'Creates colors for existing presets'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from . td_display_utils import TdColorProcessor, TdSysUtils

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        Scope = TdUtils.create_scope_from_presets(context)

        if Scope.is_empty():
            self.report({'INFO'}, "There are no presets in the list")
            return {'CANCELLED'}

        td_inputs = TdContext(context)

        CP = TdColorProcessor(context, Scope, self.properties, update_ui_limits=False)
        CP.is_range_manual = False
        CP.init(context)
        Scope = CP.calc_output_range(context, td_inputs, 'SPECTRUM')

        colorized_dict = {i.td: i.color for i in Scope.islands}
        for pr in context.scene.zen_tdpr_list:
            pr.display_color = colorized_dict[round(pr.value, td_inputs.round_value)]

        TdSysUtils.update_display_presets(context)

        return {'FINISHED'}


class CalcTexSizeOutData:

    td: float = 0.0
    im_size: float = 1024


class ZUV_OT_TD_Calculator(bpy.types.Operator):
    bl_idname = "zenuv.td_calculator"
    bl_label = 'TD Calculator'
    bl_description = 'Calculates texture size or texel density for selected objects'
    bl_options = {'REGISTER', 'UNDO'}

    calc_mode: bpy.props.EnumProperty(
            name='Mode',
            description='Calculation mode',
            items=[
                ("TEXEL_DENSITY", 'Texel Density', 'As a result, you will get the recommended texture size at the specified texel density'),
                ("TEXTURE_SIZE", 'Texture Size', 'As a result, will get a texel density at a specified texture size'),
            ],
            default='TEXEL_DENSITY'
        )

    texel_density: bpy.props.FloatProperty(
        name='Texel Density',
        description='Input value of texel density',
        default=10.24
    )
    texture_size: bpy.props.FloatProperty(
        name='Texture Size',
        description='Input texture size',
        default=1024.0
    )
    margin_area: bpy.props.FloatProperty(
        name='Margin Area',
        description='The approximate percentage of the texture area that will be used for margin',
        default=15.0,
        min=0.0,
        max=100,
        subtype='PERCENTAGE'
    )
    without_stacked: bpy.props.BoolProperty(
        name='Without Stacked Islands',
        description='Works in Edit Mode only. Excludes islands that can be stacked from the calculation. For the correct calculation, the mesh must be divided into islands',
        default=True
    )

    def draw(self, context):
        from .td_utils import TdUtils
        layout = self.layout

        layout.label(text='Result:')
        res_box = layout.box()

        layout.label(text='Input:')

        inp_box = layout.box()

        row = inp_box.row(align=True)
        row.prop(self, 'calc_mode', expand=True)

        if self.calc_mode == 'TEXEL_DENSITY':
            self.draw_td_prop(context, inp_box)
        elif self.calc_mode == 'TEXTURE_SIZE':
            inp_box.prop(self, 'texture_size')

        inp_box.prop(self, 'margin_area')
        row = inp_box.row()
        row.enabled = context.mode == 'EDIT_MESH'
        row.prop(self, 'without_stacked', toggle=1)

        if self.calc_mode == 'TEXEL_DENSITY':
            res_box.label(text=f'Texture Size: {CalcTexSizeOutData.im_size} px')

        elif self.calc_mode == 'TEXTURE_SIZE':
            res_box.label(text=f'Texel Density: {CalcTexSizeOutData.td} {TdUtils.get_current_units_string(context)}')

    def draw_td_prop(self, context, res_box):
        row = res_box.row(align=True)
        s = row.split(factor=0.8)

        s.prop(self, 'texel_density')
        s.label(text=f' {TdUtils.get_current_units_string(context)}')

    def execute(self, context):

        if context.mode == 'OBJECT':
            self.without_stacked = False
            self.report({'WARNING'}, "Zen UV: 'Without Stacked Islands' works in Edit Mode only")

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        import math
        from ZenUV.utils.generic import UnitsConverter
        from .td_utils import TdUtils

        td_props = context.scene.zen_uv.td_props

        faces_area = 0.0
        if self.without_stacked:
            from ZenUV.stacks.utils import StacksSystem
            from ZenUV.stacks.utils_for_td import get_unique_islands

            Stacks = StacksSystem(context)

            forecast = Stacks.forecast_full()

            for obj_name, ids in get_unique_islands(forecast).items():
                obj = context.scene.objects[obj_name]
                bm = bmesh.from_edit_mesh(obj.data)
                bm.faces.ensure_lookup_table()
                faces_area += sum([bm.faces[i].calc_area() for i in ids]) * pow(obj.matrix_world.median_scale, 2)

        else:
            for obj in objs:
                if obj.mode == 'EDIT_MESH':
                    bm = bmesh.from_edit_mesh(obj.data)
                    faces_area += sum([f.calc_area() for f in bm.faces]) * pow(obj.matrix_world.median_scale, 2)
                else:
                    me = obj.data
                    me.update()
                    faces_area += sum([p.area for p in me.polygons]) * pow(obj.matrix_world.median_scale, 2)

        faces_area += faces_area * (self.margin_area * 0.01)

        un_string = TdUtils.get_current_units_string(context, full=False)

        if self.calc_mode == 'TEXEL_DENSITY':

            CalcTexSizeOutData.im_size = round(self.texel_density * UnitsConverter.rev_con[un_string] * math.sqrt(faces_area))
            self.report({'INFO'}, f'Zen UV: Texture Size {CalcTexSizeOutData.im_size} px.')

        elif self.calc_mode == 'TEXTURE_SIZE':
            if faces_area != 0.0:
                p_td = self.texture_size / math.sqrt(faces_area) * (UnitsConverter.converter[td_props.td_unit] * 0.01)
                CalcTexSizeOutData.td = round(p_td, 2)
                self.report({'INFO'}, f'Zen UV: Texel Density {CalcTexSizeOutData.td} {un_string}.')
            else:
                self.report({'WARNING'}, "The area of the faces is empty. The selected objects may not have faces")
                return {'CANCELLED'}

        else:
            self.report({'WARNING'}, "Incorrect parameter 'calc_mode'")
            return {'CANCELLED'}

        return {'FINISHED'}


class ZUV_OT_Bake_TD_to_VC(bpy.types.Operator):
    """ Display Texel Density """
    bl_idname = 'uv.zenuv_bake_td_to_vc'
    bl_label = 'Bake TD to VC'
    bl_description = 'Bake texel density to the vertex color'
    bl_options = {'REGISTER', 'UNDO'}

#     def update_influence(self, context: bpy.types.Context):
#         TDS.calc_td_scope(context, self.influence)

#     influence: bpy.props.EnumProperty(
#         name="Mode",
#         description="Calculation mode. For each Face or for each Island",
#         items=[
#             ("FACE", "Face", "For each Face"),
#             ("ISLAND", "Island", "For each Island"),
#             ],
#         default='ISLAND',
#         update=update_influence)

#     display_method: bpy.props.EnumProperty(
#         name="Method",
#         description="Texel Density display method",
#         items=[
#             ("BALANCED", "Balanced", """The value specified in TD Checker will always be the middle color from the user's preferences.
# Smaller values are like the first, larger values are like the last"""),
#             ("SPECTRUM", "Spectrum", "A method for displaying textel density using different color schemes and a specified density range"),
#             # ("PRESETS", "Presets", "Display texel density presets"),
#             ],
#         default='SPECTRUM')

#     color_scheme_name: bpy.props.EnumProperty(
#         name="Color Scheme",
#         description="Color Scheme",
#         items=[
#             ("USER_THREE", "Three Color", "Three colours are used based on user preferences"),
#             ("FULL_SPEC", "Full spectrum", "Full spectrum consisting of seven primary colors"),
#             ("REVERSED_SPEC", "Reversed spectrum", "The full spectrum of the primary seven colors is reversed"),
#             ("USER_LINEAR", "Linear", "Two-color gradient. Colors match the first and last color from the user's preferences"),
#             ("MONO", "Mono", "Monochromatic scheme for easy determination of texel density values that fall outside the specified range")
#             ],
#         default='USER_THREE')

#     is_range_manual: bpy.props.BoolProperty(
#         name="Range type",
#         description="Adjust the range settings manually or automatically",
#         default=False)

#     enable_gradient_widget: TdDrawUI.enable_gradient_widget

#     values_filter: TdDrawUI.values_filter

    @classmethod
    def poll(cls, context):
        return context.selected_objects or context.objects_in_mode

    def draw(self, context):
        context.scene.zen_uv.td_draw_props.draw(context, self.layout, mode='BAKE')

    # def draw(self, context):
    #     from .td_utils import TdDrawUI
    #     layout = self.layout
    #     PROPS = context.scene.zen_uv.td_draw_props

    #     layout.prop(PROPS, 'influence')
    #     layout.prop(PROPS, 'display_method')

    #     row = layout.row()
    #     row.enabled = PROPS.display_method == 'SPECTRUM'
    #     row.prop(PROPS, 'color_scheme_name')
    #     self.draw_colors(context, layout, PROPS)

    #     box = layout.box()

    #     TdDrawUI.draw_current_td_limits(context, box)

    #     if PROPS.display_method == 'SPECTRUM':
    #         self.draw_spectrum_method_settings(context, box, PROPS)
    #     else:
    #         self.draw_balanced_method_settings(context, box, PROPS)

    #     # TdDrawUI.draw_gradient_setup(self, context, layout, PROPS)

    # def draw_spectrum_method_settings(self, context: bpy.types.Context, layout: bpy.types.UILayout, PROPS: ZUV_TdDrawProperties):
    #     row_main = layout.row(align=True)
    #     row_main.enabled = not self.is_td_are_uniform()
    #     row = row_main.row(align=True)
    #     row.enabled = PROPS.is_range_manual
    #     text = 'User Limits' if PROPS.is_range_manual else 'Auto Limits'
    #     wm = context.window_manager
    #     row.prop(wm.zen_uv.td_props, 'td_limits', text=text)
    #     self.draw_manual_switch(row_main, PROPS)

    # def draw_balanced_method_settings(self, context: bpy.types.Context, layout: bpy.types.UILayout, PROPS: ZUV_TdDrawProperties):
    #     row_main = layout.row(align=True)
    #     row_main.enabled = not self.is_td_are_uniform()
    #     row = row_main.row(align=True)
    #     row.prop(context.window_manager.zen_uv.td_props, 'balanced_checker')
    #     row.enabled = PROPS.is_range_manual
    #     self.draw_manual_switch(row_main, PROPS)

    # def draw_manual_switch(self, layout, PROPS: ZUV_TdDrawProperties):
    #     ico = 'EVENT_M' if PROPS.is_range_manual else 'EVENT_A'
    #     layout.prop(PROPS, 'is_range_manual', toggle=True, icon=ico, text='')

    # def draw_colors(self, context, layout, PROPS: ZUV_TdDrawProperties):
    #     p_col_path = context.scene.zen_uv.td_props.colors
    #     row = layout.row(align=True)
    #     row.enabled = self._is_colors_enabled(PROPS)
    #     row.prop(p_col_path, "col_less", text='')
    #     m_row = row.row(align=True)
    #     m_row.enabled = not PROPS.color_scheme_name == 'USER_LINEAR'
    #     m_row.prop(p_col_path, "col_equal", text='')
    #     row.prop(p_col_path, "col_over", text='')

    # def _is_colors_enabled(self, PROPS: ZUV_TdDrawProperties) -> bool:
    #     p_ch = PROPS.color_scheme_name
    #     return not (p_ch == 'FULL_SPEC' or p_ch == 'REVERSED_SPEC' or p_ch == 'MONO')

    # def is_td_are_uniform(self) -> bool:
    #     return TdDisplayLimits.lower_limit == TdDisplayLimits.upper_limit

    def invoke(self, context, event):
        from .td_utils import TdUtils
        PROPS = context.scene.zen_uv.td_draw_props

        TDS.clear()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        TDS.td_inputs = TdContext(context)
        TDS.td_inputs.obj_mode = context.object.mode == 'OBJECT'
        TDS.objs = objs
        if PROPS.influence == 'FACE':
            TDS.td_inputs.td_calc_precision = 100

        TDS.Scope = TdUtils.get_td_data_with_precision(
            context,
            TDS.objs,
            TDS.td_inputs,
            PROPS.influence)

        return self.execute(context)

    def execute(self, context):

        from .td_display_utils import TdColorProcessor

        if TDS.is_empty():
            self.report({'WARNING'}, "There are no Islands for displaying")
            return {'CANCELLED'}

        PROPS = context.scene.zen_uv.td_draw_props

        if bpy.ops.uv.zenuv_clear_baked_texel_density.poll():
            bpy.ops.uv.zenuv_clear_baked_texel_density(map_type='ALL')

        CP = TdColorProcessor(context, TDS.Scope, PROPS)
        CP.calc_output_range(context, TDS.td_inputs, PROPS.display_method)

        CP.bake_texel_density_to_vc(context, TDS.td_inputs)

        switch_shading_style(context, "VERTEX", switch=False)

        return {'FINISHED'}


class ZUV_OT_Clear_Baked_TD(bpy.types.Operator):
    bl_idname = "uv.zenuv_clear_baked_texel_density"
    bl_label = 'Clear Baked TD'
    bl_description = 'Remove texel density vertex color layer from object'
    bl_options = {'REGISTER', 'UNDO'}

    map_type: bpy.props.EnumProperty(
        name="Map Type",
        items=[
            ("BALANCED", "Balanced", ""),
            ("PRESETS", "Presets", ""),
            ("ALL", "All", ""),
        ],
        default="BALANCED",
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, context):
        return context.selected_objects or context.objects_in_mode

    def execute(self, context):
        from ZenUV.utils import vc_processor as vc
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if self.map_type == "BALANCED":
            for obj in objs:
                vc.disable_zen_vc_map(obj, vc.Z_TD_BALANCED_V_MAP_NAME)
        if self.map_type == "PRESETS":
            for obj in objs:
                vc.disable_zen_vc_map(obj, vc.Z_TD_PRESETS_V_MAP_NAME)
        if self.map_type == "ALL":
            for obj in objs:
                vc.disable_zen_vc_map(obj, vc.Z_TD_PRESETS_V_MAP_NAME)
                vc.disable_zen_vc_map(obj, vc.Z_TD_BALANCED_V_MAP_NAME)
        switch_shading_style(context, "TEXTURE", switch=False)
        return {"FINISHED"}


td_tools_classes = [
    TDPR_OT_CreatePresets,
    TDPR_OT_ColorizePresets,
    ZUV_OT_TD_Calculator,
    ZUV_OT_Bake_TD_to_VC,
    ZUV_OT_Clear_Baked_TD
]


def register():
    RegisterUtils.register(td_tools_classes)


def unregister():
    RegisterUtils.unregister(td_tools_classes)
