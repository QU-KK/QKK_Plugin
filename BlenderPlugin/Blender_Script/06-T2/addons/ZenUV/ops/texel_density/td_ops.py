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

""" Zen UV Texel Density system """

import bpy
import bmesh

from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.generic import (
    resort_objects_by_selection,
    get_mesh_data,
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer,
    UnitsConverter
)
from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens

from . td_utils import (
    TexelDensityFactory,
    TexelDensityProcessor,
    UvFaceArea,
    TdContext,
    TdUtils,
    CoverageReport
)

from .td_display_utils import TdDisplayLimits, TdSysUtils
from .td_islands_storage import TdDataStorage as TDS
from .td_props import TdProps


class ZUV_OT_GetTexelDensity(bpy.types.Operator):
    bl_idname = "uv.zenuv_get_texel_density"
    bl_label = ZuvLabels.OT_GET_TEXEL_DENSITY_LABEL
    bl_description = ZuvLabels.OT_GET_TEXEL_DENSITY_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        if context.mode == 'EDIT_MESH':
            objs = resort_objects_by_selection(context, objs)
            if not objs:
                self.report({'WARNING'}, "Zen UV: Select something.")
                return {'CANCELLED'}

        td_inputs = TdContext(context)
        if context.mode == 'OBJECT':
            td_inputs.obj_mode = True
            context.scene.zen_uv.td_props.prp_current_td, _ = TexelDensityFactory.get_texel_density_in_obj_mode(context, objs, TdContext(context))
        elif context.mode == 'EDIT_MESH':
            context.scene.zen_uv.td_props.prp_current_td, _ = TexelDensityFactory.get_texel_density(context, objs, td_inputs)
        else:
            pass

        update_areas_in_all_screens(context)

        return {'FINISHED'}


class ZUV_OT_GetUVCoverage(bpy.types.Operator):
    bl_idname = "uv.zenuv_get_uv_coverage"
    bl_label = 'Get UV Coverage'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Get UV Coverage'

    mode: bpy.props.EnumProperty(
        name="Mode",
        description='Coverage calculation mode',
        items=[
                ("GENERIC", 'Generic', 'The size of each island is calculated and added to the total value.', 0),
                ("SELECTED", 'Selected', 'Shows area for selected islands only', 1),
                ("ALREADY_STACKED", 'Exclude stacked', 'Excludes similar islands that stacked from the calculation', 2)
            ],
        default='GENERIC'
    )

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'mode')

        box = layout.box()
        box.label(text=f'UV Coverage:    {CoverageReport.coverage} %')
        box.label(text=f'Empty space:    {CoverageReport.empty_space} %')

    def execute(self, context):
        coverage = 0
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)

        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            CoverageReport.clear()
            return {"CANCELLED"}

        if context.mode == 'EDIT_MESH':

            if self.mode == 'GENERIC':
                for obj in objs:
                    _, bm = get_mesh_data(obj)
                    uv_layer = verify_uv_layer(bm)
                    coverage += UvFaceArea.calculate_uv_coverage(uv_layer, bm.faces)

            elif self.mode == 'SELECTED':
                from ZenUV.utils import get_uv_islands as island_util
                p_i_count = 0
                for obj in objs:
                    _, bm = get_mesh_data(obj)
                    uv_layer = verify_uv_layer(bm)
                    islands = island_util.get_island(context, bm, uv_layer)
                    p_i_count += len(islands)
                    p_faces = [f for i in islands for f in i]
                    coverage += UvFaceArea.calculate_uv_coverage(uv_layer, p_faces)

                if p_i_count == 0:
                    self.report({'WARNING'}, "Select some Islands.")
                    CoverageReport.clear()
                    return {"CANCELLED"}

            elif self.mode == 'ALREADY_STACKED':
                from ZenUV.stacks.utils import StacksSystem
                from ZenUV.stacks.utils_for_td import get_unique_islands

                stacks_state = StacksSystem(context).get_current_stacks_state()

                for obj_name, ids in get_unique_islands(stacks_state).items():
                    obj = context.scene.objects[obj_name]
                    _, bm = get_mesh_data(obj)
                    uv_layer = verify_uv_layer(bm)
                    bm.faces.ensure_lookup_table()
                    coverage += UvFaceArea.calculate_uv_coverage(uv_layer, [bm.faces[i] for i in ids])

        else:
            for obj in objs:
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                uv_layer = verify_uv_layer(bm)
                coverage += UvFaceArea.calculate_uv_coverage(uv_layer, bm.faces)
                bm.free()

        context.scene.zen_uv.td_props.prp_uv_coverage = coverage

        CoverageReport.coverage = round(coverage, 2)
        CoverageReport.empty_space = round(100 - CoverageReport.coverage, 2) if CoverageReport.coverage <= 100 else '~'

        update_areas_in_all_screens(context)

        return {'FINISHED'}


class ZUV_OT_SetTexelDensity(bpy.types.Operator):
    bl_idname = "uv.zenuv_set_texel_density"
    bl_label = 'Set TD'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Set Texel Density to selected Islands'

    global_mode: bpy.props.BoolProperty(
        name='Global Mode',
        description='In global mode, all settings are taken from the "Texture Density" panel',
        default=True)

    td_value: bpy.props.FloatProperty(
        name='Td Value',
        description='Texel density value',
        min=0.001,
        default=10.24)

    units: TdProps.td_unit

    island_pivot: TdProps.td_set_pivot

    set_mode: bpy.props.EnumProperty(
        name="Set TD Mode",
        description='Mode for setting Texel Density',
        items=[
            (
                'ISLAND',
                'Island Mode',
                'Set Texel Density individually for every selected Island'
            ),
            (
                'OVERALL',
                'Overall Mode',
                'Set Texel Density for all selected Islands together'
            ),
        ],
        default='OVERALL')

    image_size_x: bpy.props.IntProperty(
        name="Texture Size X",
        min=1,
        default=1024)

    image_size_y: bpy.props.IntProperty(
        name="Texture Size Y",
        min=1,
        default=1024)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'global_mode')

        box = layout.box()
        box.enabled = not self.global_mode

        if self.global_mode:
            td_props = context.scene.zen_uv.td_props
            col = box.column(align=True)
            row = col.row(align=True)
            row.prop(td_props, 'prp_current_td', text='')
            row.prop(td_props, 'td_unit', text='')
            col.prop(td_props, 'td_set_mode', text='')

            col = box.column(align=True)
            col.prop(td_props, 'TD_TextureSizeX', text='Texture Size X')
            col.prop(td_props, 'TD_TextureSizeY', text='Texture Size Y')

            box.prop(td_props, 'td_set_pivot')
        else:
            col = box.column(align=True)
            row = col.row(align=True)
            row.prop(self, 'td_value', text='')
            row.prop(self, 'units', text='')
            col.prop(self, 'set_mode', text='')

            col = box.column(align=True)
            col.prop(self, 'image_size_x')
            col.prop(self, 'image_size_y')

            box.prop(self, 'island_pivot')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        if context.mode == 'EDIT_MESH':
            objs = resort_objects_by_selection(context, objs)
            if not objs:
                self.report({'WARNING'}, "Zen UV: Select something.")
                return {'CANCELLED'}

        td_inputs = TdContext(context)
        td_inputs.obj_mode = context.mode == 'OBJECT'

        if self.global_mode is False:
            td_inputs.td = self.td_value
            td_inputs.units = UnitsConverter.converter[self.units]
            td_inputs.set_mode = self.set_mode
            td_inputs.image_size = [self.image_size_x, self.image_size_y]
            td_inputs.td_set_pivot_name = self.island_pivot

        TexelDensityProcessor.set_td(context, objs, td_inputs)

        if context.mode == 'OBJECT':
            TdSysUtils.update_view3d_in_all_screens(context)

        return {'FINISHED'}


class ZUV_OT_GetIslandSize(bpy.types.Operator):
    bl_idname = "uv.zenuv_get_island_size"
    bl_label = 'Get Island Size'
    bl_description = 'Get the size of the island in units or pixels'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        objs = resort_objects_by_selection(context, objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        from .td_utils import IslandSizeProcessor

        sz_props = context.scene.zen_uv.td_props
        # td_inputs = TdContext(context)

        p_is_size = IslandSizeProcessor.get_island_size(context)

        if sz_props.sz_units == 'UNITS':
            sz_props.sz_current_size = [p_is_size.units.x, p_is_size.units.y]
        else:
            sz_props.sz_current_size = [p_is_size.pixels.x, p_is_size.pixels.y]

        return {'FINISHED'}


class ZUV_OT_SetIslandSize(bpy.types.Operator):
    bl_idname = "uv.zenuv_set_island_size"
    bl_label = 'Set Island Size'
    bl_description = 'Set the size of the island in units or pixels'
    bl_options = {'REGISTER', 'UNDO'}

    # manual_mode: bpy.props.BoolProperty(
    #     name='Manual Mode',
    #     description='Use an explicit TD value instead of a global value',
    #     default=False
    # )

    def update_units(self, context):
        sz_props = context.scene.zen_uv.td_props
        p_correction = [sz_props.SZ_TextureSizeX, sz_props.SZ_TextureSizeY]
        if sz_props.SZ_TextureSizeX == 0 or sz_props.SZ_TextureSizeY == 0:
            p_correction = [1.0, 1.0]
        if self.units == 'UNITS':
            # NOTE: use dict assignment to avoid recursive update
            self["size"] = [self.size[0] / p_correction[0], self.size[1] / p_correction[1]]
        else:
            self["size"] = [self.size[0] * p_correction[0], self.size[1] * p_correction[1]]

    units: bpy.props.EnumProperty(
        name="Units",
        description='Isalnd size units',
        items=[
                ("UNITS", 'Un', 'Units', 0),
                ("PIXELS", 'Px', 'Pixels', 1),
            ],
        default='PIXELS',
        update=update_units
    )

    size: bpy.props.FloatVectorProperty(
        name='Island Size',
        description='Represent size of the island',
        size=2,
        default=(1.0, 1.0),
        min=0.0
    )

    def update_active_x(self, context):
        if self.active_x is False and self.active_y is False:
            # NOTE: use dict assignment to avoid recursive update
            self["active_y"] = True

    def update_active_y(self, context):
        if self.active_x is False and self.active_y is False:
            # NOTE: use dict assignment to avoid recursive update
            self["active_x"] = True

    active_x: bpy.props.BoolProperty(
        name="Active X",
        description='Dependence on the X axis',
        default=True,
        update=update_active_x
    )
    active_y: bpy.props.BoolProperty(
        name="Active Y",
        description='Dependence on the Y axis',
        default=False,
        update=update_active_y
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'units')
        layout.prop(self, 'size')
        row = layout.row(align=True)
        row.prop(self, 'active_x', toggle=1)
        row.prop(self, 'active_y', toggle=1)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        return self.execute(context)

    def execute(self, context):
        from .td_utils import IslandSizeProcessor, SzContext

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        objs = resort_objects_by_selection(context, objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        sz_inputs = SzContext(context)

        sz_inputs.sz_units = self.units
        sz_inputs.sz_reference_size = TdUtils.compound_island_size(sz_inputs, self.size)
        if self.units == 'UNITS':
            sz_inputs.sz_reference_size = TdUtils.compound_island_size(sz_inputs, self.size)
        else:
            if sz_inputs.image_size[0] == 0.0 or sz_inputs.image_size[1] == 0.0:
                sz_inputs.image_size = [1.0, 1.0]
            sz_inputs.sz_reference_size = TdUtils.compound_island_size(
                sz_inputs,
                (
                    self.size[0] / sz_inputs.image_size[0],
                    self.size[1] / sz_inputs.image_size[1]
                ))

        sz_inputs.sz_active_axis_list = [self.active_x, self.active_y]

        IslandSizeProcessor.set_island_size(context, objs, sz_inputs)

        return {'FINISHED'}


class ZUV_OT_GetTdRange(bpy.types.Operator):
    bl_idname = "zenuv.get_td_range"
    bl_label = 'Calculate Texel Density Range'
    bl_description = 'Calculates the current minimum and maximum TD values for the entire scene'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # from ZenUV.ui.gizmo_draw import GradientProperties
        td_inputs = TdContext(context)
        props = context.scene.zen_uv.td_props
        if props.td_range_mode == 'SCENE':
            td_inputs.obj_mode = True
            objs = [obj for obj in context.scene.objects if obj.type == 'MESH']
        elif props.td_range_mode == 'SELECTION':
            td_inputs.obj_mode = context.mode == 'OBJECT'
            objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        td_values = TdUtils.get_td_data_with_precision(context, objs, td_inputs).get_sorted_td_values()

        TdDisplayLimits.cl_td_limits = [min(td_values), max(td_values)]

        # Temporary disabled
        # if TdSysUtils.is_gradient_widget_active(context):
        #     GradientProperties.range_values = td_values
        #     GradientProperties.range_labels = TdSysUtils.td_labels_filter(td_values, 10)
        #     context.area.tag_redraw()

        return {"FINISHED"}


class ZUV_OT_SelectByTd(bpy.types.Operator):
    """ Select Islands By Texel Density """
    bl_idname = "uv.zenuv_select_by_texel_density"
    bl_label = 'Select by TD'
    bl_description = 'Select islands by texel density'
    bl_options = {'REGISTER', 'UNDO'}

    influence: bpy.props.EnumProperty(
        name="Influence",
        description="Calculation mode. For each Face or for each Island",
        items=[
            ("FACE", "Face", "For each Face"),
            ("ISLAND", "Island", "For each Island"),
            ],
        default='ISLAND')

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    selection_mode: bpy.props.EnumProperty(
        name="Sel. Mode",
        description="Selection mode",
        items=[
            ("TRESHOLD", "Treshold", "Use the TD base value and threshold"),
            ("RANGE", "Range", "Use the range specified by the minimum and maximum TD values"),
            ("SKIP", "Skip", "Do not select islands by TD"),
            ],
        default='TRESHOLD')

    texel_density: bpy.props.FloatProperty(
        name="Texel Density",
        description="",
        precision=2,
        default=0.0,
        step=1,
        min=0.0)

    treshold: bpy.props.FloatProperty(
        name="Treshold",
        description="",
        precision=2,
        default=0.01,
        step=1,
        min=0.0)

    range_low: bpy.props.FloatProperty(
        name="Low",
        description="Lower value of the range",
        default=0.0,
        min=0.0)

    range_hi: bpy.props.FloatProperty(
        name="Hi",
        description="Upper value of the range",
        default=1.0,
        min=0.0)

    sel_underrated: bpy.props.BoolProperty(
        name='Select Underrated',
        description='Select islands with a TD value less than the smallest TD value in the presets',
        default=False)

    sel_overrated: bpy.props.BoolProperty(
        name='Select Overrated',
        description='Select islands with a TD value greater than the highest TD value in the preset',
        default=False)

    desc: bpy.props.StringProperty(
        name="Description",
        default='Select islands by texel density',
        options={'HIDDEN'}
    )

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_desctiption

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        from ZenUV.ops.texel_density.td_utils import TdUtils

        TDS.clear()

        p_objects = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not p_objects:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        TDS.objs = p_objects
        TDS.td_inputs = TdContext(context)
        TDS.td_inputs.obj_mode = context.object.mode == 'OBJECT'

        TDS.Scope = TdUtils.get_td_data_with_precision(context, TDS.objs, TDS.td_inputs, self.influence)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "influence")

        layout.prop(self, "clear_selection")
        box = layout.box()
        box.label(text=f'Current range: {round(TDS.min_range, 2)} - {round(TDS.max_range, 2)}')
        box.label(text=f'Selected: {TDS.i_count} islands')

        box = layout.box()
        box.prop(self, 'selection_mode')
        col = box.column()
        col.enabled = self.selection_mode != 'SKIP'
        if self.selection_mode == 'TRESHOLD':
            self.draw_treshold_mode(context, col)
        else:
            self.draw_range_mode(context, col)
        pr_box = layout.box()
        pr_box.label(text='Presets:')
        pr_box.prop(self, "sel_underrated")
        pr_box.prop(self, "sel_overrated")

    def draw_treshold_mode(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        layout.prop(self, "texel_density")
        layout.prop(self, "treshold")

    def draw_range_mode(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        layout.prop(self, 'range_low')
        layout.prop(self, 'range_hi')

    def execute(self, context):
        TDS.i_count = 0
        if TDS.is_empty():
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        TDS.calc_td_scope(context, self.influence)

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        if self.selection_mode == 'TRESHOLD':
            TDS.min_range = self.texel_density - self.treshold
            TDS.max_range = self.texel_density + self.treshold
        elif self.selection_mode == 'RANGE':
            TDS.min_range = self.range_low
            TDS.max_range = self.range_hi
        else:
            TDS.min_range = 0.0
            TDS.max_range = 0.0

        TdUtils.select_by_td(
            context,
            TDS.Scope,
            [
                TDS.min_range,
                TDS.max_range
            ],
            TDS.td_inputs
            )
        if self.sel_underrated or self.sel_overrated:
            from .td_islands_storage import TdPresetsStorage
            TdPresetsStorage.collect_presets(context)

            if TdPresetsStorage.is_empty():
                self.report({'WARNING'}, "Zen UV: The preset list is empty")
                return {'FINISHED'}

            p_presets_range = TdPresetsStorage.get_presets_td_range()

        if self.sel_underrated:
            TdUtils.select_by_td(
                context,
                TDS.Scope,
                (0, p_presets_range[0] - 0.001),
                TDS.td_inputs
                )

        if self.sel_overrated:
            TdUtils.select_by_td(
                context,
                TDS.Scope,
                (p_presets_range[1] + 0.001, p_presets_range[1] * 2),
                TDS.td_inputs
                )

        return {'FINISHED'}


class ZUV_OT_SelectByCurrentTd(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_by_current_texel_density"
    bl_label = 'Select by current TD'
    bl_description = 'Select the islands by texel density, which is displayed in the value in the panel'
    bl_options = {'REGISTER', 'UNDO'}

    influence: bpy.props.EnumProperty(
        name="Influence",
        description="Calculation mode. For each Face or for each Island",
        items=[
            ("FACE", "Face", "For each Face"),
            ("ISLAND", "Island", "For each Island"),
            ],
        default='ISLAND')

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    texel_density: bpy.props.FloatProperty(
        name="Texel Density",
        description="",
        precision=2,
        default=0.0,
        step=1,
        min=0.0)

    treshold: bpy.props.FloatProperty(
        name="Treshold",
        description="",
        precision=2,
        default=0.01,
        step=1,
        min=0.0)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        from ZenUV.ops.texel_density.td_utils import TdUtils

        TDS.clear()

        p_objects = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not p_objects:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        TDS.objs = p_objects
        TDS.td_inputs = TdContext(context)
        TDS.td_inputs.obj_mode = context.object.mode == 'OBJECT'

        TDS.Scope = TdUtils.get_td_data_with_precision(context, TDS.objs, TDS.td_inputs, self.influence)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "influence")

        layout.prop(self, "clear_selection")
        box = layout.box()
        box.label(text=f'Current range: {round(TDS.min_range, 2)} - {round(TDS.max_range, 2)}')
        box.label(text=f'Selected: {TDS.i_count} islands')

        box = layout.box()
        col = box.column()
        col.prop(self, "texel_density")
        col.prop(self, "treshold")

    def execute(self, context):
        TDS.i_count = 0
        if TDS.is_empty():
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        TDS.calc_td_scope(context, self.influence)

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        TDS.min_range = self.texel_density - self.treshold
        TDS.max_range = self.texel_density + self.treshold

        TdUtils.select_by_td(
            context,
            TDS.Scope,
            [
                TDS.min_range,
                TDS.max_range
            ],
            TDS.td_inputs
            )

        return {'FINISHED'}


class ZUV_OT_SelectBySize(bpy.types.Operator):
    """ Select islands by their size """
    bl_idname = "uv.zenuv_select_islands_by_size"
    bl_label = 'Select by Size'
    bl_description = 'Select Islands by their size'
    bl_options = {'REGISTER', 'UNDO'}

    def update_influence(self, context: bpy.types.Context):
        TDS.td_inputs = TDS.sz_inputs
        TDS.calc_size_scope(context, self.influence)

    influence: bpy.props.EnumProperty(
        name="Influence",
        description="Calculation mode. For each Face or for each Island",
        items=[
            ("FACE", "Face", "For each Face"),
            ("ISLAND", "Island", "For each Island"),
            ],
        default='ISLAND',
        update=update_influence)

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    selection_mode: bpy.props.EnumProperty(
        name="Sel. Mode",
        description="Selection mode",
        items=[
            ("TRESHOLD", "Treshold", "Use the TD base value and threshold"),
            ("RANGE", "Range", "Use the range specified by the minimum and maximum TD values"),
            ("SKIP", "Skip", "Do not select islands by TD"),
            ],
        default='TRESHOLD')

    def update_units(self, context):
        sz_props = context.scene.zen_uv.td_props
        p_correction = [sz_props.SZ_TextureSizeX, sz_props.SZ_TextureSizeY]
        if sz_props.SZ_TextureSizeX == 0 or sz_props.SZ_TextureSizeY == 0:
            p_correction = [1.0, 1.0]
        if self.units == 'UNITS':
            self["size"] = self.size / p_correction[0]
        else:
            self["size"] = self.size * p_correction[0]

    units: bpy.props.EnumProperty(
        name="Units",
        description='Isalnd size units',
        items=[
                ("UNITS", 'Un', 'Units', 0),
                ("PIXELS", 'Px', 'Pixels', 1),
            ],
        default='PIXELS',
        update=update_units
    )

    def update_active_x(self, context):
        if self.active_x is False and self.active_y is False:
            # NOTE: use dict assignment to avoid recursive update
            self["active_y"] = True

    def update_active_y(self, context):
        if self.active_x is False and self.active_y is False:
            # NOTE: use dict assignment to avoid recursive update
            self["active_x"] = True

    active_x: bpy.props.BoolProperty(
        name="Active X",
        description='Dependence on the X axis',
        default=True,
        update=update_active_x
    )
    active_y: bpy.props.BoolProperty(
        name="Active Y",
        description='Dependence on the Y axis',
        default=False,
        update=update_active_y
    )

    size: bpy.props.FloatProperty(
        name="Size",
        description="The size of the Island",
        precision=2,
        default=0.0,
        step=1,
        min=0.0)

    treshold: bpy.props.FloatProperty(
        name="Treshold",
        description="",
        precision=2,
        default=0.01,
        step=1,
        min=0.0)

    range_low: bpy.props.FloatProperty(
        name="Low",
        description="Lower value of the range",
        default=0.0,
        min=0.0)

    range_hi: bpy.props.FloatProperty(
        name="Hi",
        description="Upper value of the range",
        default=1.0,
        min=0.0)

    desc: bpy.props.StringProperty(
        name="Description",
        default='Select Islands by their size',
        options={'HIDDEN'}
    )

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_desctiption

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        from .td_utils import TdUtils, SzContext

        TDS.clear()

        p_objects = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not p_objects:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        TDS.objs = p_objects
        TDS.sz_inputs = SzContext(context)
        TDS.Scope = TdUtils.get_sizes_data(context, TDS.objs, TDS.sz_inputs, self.influence)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "influence")

        col.prop(self, "clear_selection")
        box = col.box()
        box.label(text=f'Current range: {round(TDS.min_range, 2)} - {round(TDS.max_range, 2)}')
        box.label(text=f'Selected: {TDS.i_count} islands')

        box = col.box()
        box.prop(self, 'selection_mode')
        box.prop(self, 'units')
        row = layout.row(align=True)
        row.prop(self, 'active_x', toggle=1)
        row.prop(self, 'active_y', toggle=1)
        col = box.column()
        col.enabled = self.selection_mode != 'SKIP'
        if self.selection_mode == 'TRESHOLD':
            self.draw_treshold_mode(context, col)
        else:
            self.draw_range_mode(context, col)

    def draw_treshold_mode(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        layout.prop(self, "size")
        layout.prop(self, "treshold")

    def draw_range_mode(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        layout.prop(self, 'range_low')
        layout.prop(self, 'range_hi')

    def execute(self, context):
        TDS.i_count = 0
        if TDS.is_empty():
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        from ZenUV.utils.generic import bpy_select_by_context

        if self.clear_selection:
            bpy_select_by_context(context, action='DESELECT')

        TDS.sz_inputs.sz_units = self.units

        TDS.sz_inputs.sz_active_axis_list = [self.active_x, self.active_y]

        if self.selection_mode == 'TRESHOLD':
            TDS.min_range = self.size - self.treshold
            TDS.max_range = self.size + self.treshold
        elif self.selection_mode == 'RANGE':
            TDS.min_range = self.range_low
            TDS.max_range = self.range_hi
        else:
            TDS.min_range = 0.0
            TDS.max_range = 0.0

        TdUtils.select_by_size(
            context,
            TDS.Scope,
            [
                TDS.min_range,
                TDS.max_range
            ],
            TDS.sz_inputs
            )

        return {'FINISHED'}


td_classes = (
    ZUV_OT_GetTexelDensity,
    # ZUV_OT_GetTexelDensityOBJ,
    ZUV_OT_SetTexelDensity,
    # ZUV_OT_SetTexelDensityOBJ,
    ZUV_OT_GetTdRange,
    ZUV_OT_GetUVCoverage,
    ZUV_OT_SelectByTd,
    ZUV_OT_SelectByCurrentTd,
    ZUV_OT_GetIslandSize,
    ZUV_OT_SetIslandSize,
    ZUV_OT_SelectBySize
)
