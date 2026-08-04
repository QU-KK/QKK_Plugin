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

# Copyright 2023, Valeriy Yatsenko, Alexander Zhornyak

import bpy
from bl_operators.presets import ExecutePreset

from pathlib import Path
import os
import re

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.generic import (
    ZUV_SPACE_TYPE,
    ZUV_REGION_TYPE,
    ZUV_PANEL_CATEGORY,
    ZUV_CONTEXT)
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.blender_zen_utils import ZuvPresets, update_areas_in_all_screens
from ZenUV.utils.adv_generic_ui_list import ZenAddPresetBase

from ..transform_sys.transform_utils.tr_utils import TransformSysOpsProps
from ZenUV.utils.adv_generic_ui_list import zenuv_draw_ui_list
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.prop.world_size_props import ZuvWorldSizeUtils


UV_WORLD_SIZE_PRESET_SUBDIR = "uv_world_size_presets"


class ZUV_PT_WorldSizeMaterial(bpy.types.Panel):
    bl_idname = "ZUV_PT_WorldSizeMaterial"
    bl_label = 'UV World Size Material'
    bl_context = "material"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        layout = self.layout

        p_obj = context.active_object
        if p_obj:
            p_act_mat = p_obj.active_material
            if p_act_mat:
                col = layout.column(align=True)
                col.label(text=p_act_mat.zen_uv.bl_rna.properties['world_size_image'].name)
                col.prop(p_act_mat.zen_uv, 'world_size_image', text='')


class ZUV_PT_3DV_SubWorldSize(bpy.types.Panel):
    bl_label = "UV World Size"
    bl_context = ZUV_CONTEXT
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_Texel_Density"

    @classmethod
    def get_icon(cls):
        return 'WORLD'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh Mode'
        return ''

    def draw(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        def draw_world_size_operators(context, p_image: bpy.types.Image, layout: bpy.types.UILayout):
            r_scale = layout.row(align=True)
            r_scale.label(text='Size:')
            r_scale.prop(p_image.zen_uv.world_size, 'size', text='')
            r_scale.prop(p_image.zen_uv.world_size, 'units', text='')

            row = layout.row(align=True)
            ot = row.operator(ZUV_OT_GetWorldSize.bl_idname, text='Get')
            ot.write_to_current_texture = True
            ot.units = p_image.zen_uv.world_size.units

            ot = row.operator(ZUV_OT_SetWorldSize.bl_idname, text='Set')
            ot.size = p_image.zen_uv.world_size.size
            ot.units = p_image.zen_uv.world_size.units

            layout.operator(ZUV_OT_GetWorldSize.bl_idname, text='Calculate World Size').write_to_current_texture = False

            col = layout.column(align=True)
            col.label(text=p_image.zen_uv.bl_rna.properties['trimsheet_with_size'].name)
            row = col.row(align=True)
            # NOTE: this need to generate items
            p_world_size_trims = p_image.zen_uv.get_trimsheet_with_size_items(context)

            if len(p_world_size_trims) == 0:
                op = row.operator("wm.url_open", text='No trims with world size property set', icon='INFO')
                op.url = ZenPolls.doc_url + "texel_density/#uv-world-size"
            else:
                # NOTE: we use this to prevent warning in console
                idx_trim = p_image.zen_uv.get_trimsheet_with_size()

                row.prop(p_image.zen_uv, 'trimsheet_with_size', text="")

                row_op = row.row(align=True)
                op = row_op.operator(ZUV_OT_WorldSizeByTrim.bl_idname, text='', icon='KEYFRAME_HLT')
                op.image_name = p_image.name
                op.trim_uuid = p_image.zen_uv.trimsheet_with_size if idx_trim != - 1 else ''

        def draw_world_size_presets():
            row = layout.row(align=True)
            r1 = row.row(align=True)
            r1.alignment = 'LEFT'
            r1.separator(factor=2)
            r1.prop(
                addon_prefs.uv_world_size, 'world_size_presets_expanded',
                icon='TRIA_DOWN' if addon_prefs.uv_world_size.world_size_presets_expanded else 'TRIA_RIGHT', emboss=False)

            r2 = row.row(align=True)
            r2.alignment = 'RIGHT'
            r2.operator(ZUV_OT_WorldSizeAutoDetect.bl_idname, text="", icon="EVENT_A")

            if not addon_prefs.uv_world_size.world_size_presets_expanded:
                return

            row = layout.row(align=True)
            row.menu("ZUV_MT_StoreWorldSizePresets", text=ZUV_MT_StoreWorldSizePresets.bl_label)

            s_preset_name = ZUV_MT_StoreWorldSizePresets.bl_label

            op = row.operator(ZUV_OT_WorldSizeAddPreset.bl_idname, text="", icon="ADD")
            if s_preset_name and s_preset_name != ZUV_MT_StoreWorldSizePresets.default_label:
                op.name = s_preset_name
            op = row.operator(ZUV_OT_WorldSizeAddPreset.bl_idname, text="", icon="REMOVE")
            op.remove_active = True

            s_preset_folder_name = UV_WORLD_SIZE_PRESET_SUBDIR
            target_path = os.path.join("presets", ZuvPresets.get_preset_path(s_preset_folder_name))
            target_path = bpy.utils.user_resource('SCRIPTS', path=target_path, create=True)

            row.operator(
                'wm.path_open',
                icon='FILEBROWSER',
                text='').filepath = target_path

            _ = zenuv_draw_ui_list(
                layout,
                context,
                class_name="ZUV_UL_WorldSizeList",
                list_path="preferences.addons['ZenUV'].preferences.uv_world_size.world_size_items",
                active_index_path="preferences.addons['ZenUV'].preferences.uv_world_size.world_size_items_index",
                unique_id="name",
                new_name_attr="name",
                new_name_val="Item"
            )

            if addon_prefs.uv_world_size.world_size_items_index in range(len(addon_prefs.uv_world_size.world_size_items)):
                col = layout.column(align=True)
                col.use_property_split = True
                p_item = addon_prefs.uv_world_size.world_size_items[addon_prefs.uv_world_size.world_size_items_index]
                col.prop(p_item, 'size')
                col.prop(p_item, 'units')
                col.prop(p_item, 'regex')

        p_mat_image = None
        p_act_mat = None
        p_image = ZuvWorldSizeUtils.getActiveImage(context)
        b_is_UV = self.bl_space_type == 'IMAGE_EDITOR'
        if not b_is_UV:
            p_obj = context.active_object
            if p_obj:
                p_act_mat = p_obj.active_material
                if p_act_mat:
                    p_mat_image = p_act_mat.zen_uv.world_size_image

        layout = self.layout

        if p_image is not None:
            row = layout.row(align=True)
            box = row.box()
            r_line = box.row(align=True)
            r1 = r_line.row(align=True)
            r1.alert = p_mat_image is not None
            r1.label(text=p_image.name, icon='FILE_IMAGE')

            if p_act_mat is not None:
                r2 = r_line.row(align=True)
                r2.alignment = 'RIGHT'
                r2.popover(panel=ZUV_PT_WorldSizeMaterial.bl_idname, text='', icon='PREFERENCES')

            draw_world_size_operators(context, p_image, layout)

            draw_world_size_presets()

        else:
            box = layout.box()
            if p_act_mat is not None:
                box.prop(p_act_mat.zen_uv, 'world_size_image', text='')

            row = box.row(align=True)
            row.alignment = 'CENTER'
            row.label(text='No active image', icon='ERROR')


class ZUV_PT_UVL_SubWorldSize(bpy.types.Panel):
    bl_label = ZUV_PT_3DV_SubWorldSize.bl_label
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Texel_Density"

    get_icon = ZUV_PT_3DV_SubWorldSize.get_icon

    poll = ZUV_PT_3DV_SubWorldSize.poll

    poll_reason = ZUV_PT_3DV_SubWorldSize.poll_reason

    draw = ZUV_PT_3DV_SubWorldSize.draw


class ZuvSetWorldSizeBase:
    size: bpy.props.FloatProperty(
        name='Size',
        description='UV world size value',
        min=0.001,
        default=1.0
    )
    units: TransformSysOpsProps.get_units_enum()
    island_pivot: bpy.props.EnumProperty(
            name='Island Pivot',
            description='The pivot point of the transformation',
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
    align: bpy.props.BoolProperty(
        name='Align to UV Area',
        description='Align islands to the UV Area',
        default=False
    )
    align_direction: TransformSysOpsProps.get_align_direction(default=1)

    def draw(self, context):
        layout: bpy.types.UILayout = self.layout

        col = layout.column()
        col.use_property_split = True
        row = col.row(align=True)
        row.prop(self, 'size')
        row.prop(self, 'units', text='')

        col.prop(self, 'island_pivot')

        box = layout.box()
        box.label(text='Postprocess:')
        m_row = box.row(align=True)
        m_row.prop(self, 'align')
        row = m_row.row(align=True)
        row.enabled = self.align
        row.prop(self, 'align_direction', text='')

    @classmethod
    def poll(cls, context: bpy.types.Context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel, resort_objects_by_selection
        from ZenUV.ops.texel_density.td_utils import TdContext, TexelDensityProcessor, TexelDensityFactory
        from mathutils import Matrix, Vector

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        objs = resort_objects_by_selection(context, objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        td_inputs = TdContext(context)

        p_image = ZuvWorldSizeUtils.getActiveImage(context)

        if p_image is not None:
            p_ref_size = p_image.zen_uv.world_size.size

            from ZenUV.utils.generic import UnitsConverter

            p_ref_image_size = p_image.size[:]

            p_ref_td = round(TexelDensityFactory._calc_referenced_td_world_size(p_ref_image_size, td_inputs)[0], 2) * UnitsConverter.rev_con[self.units]

            p_ma = Matrix.Diagonal(Vector.Fill(3, p_ref_size)).to_3x3()
            scalar = p_ma.inverted().median_scale

        else:
            self.report({'INFO'}, "No active image detected.")
            return {'CANCELLED'}

        td_inputs.td = p_ref_td * scalar
        td_inputs.td_set_pivot_name = self.island_pivot
        td_inputs.set_mode = 'ISLAND'
        td_inputs.image_size = p_ref_image_size

        TexelDensityProcessor.set_td(context, objs, td_inputs)

        if self.align:
            bpy.ops.uv.zenuv_align(
                influence_mode='ISLAND',
                op_order='ONE_BY_ONE',
                align_to='TO_UV_AREA',
                align_direction=self.align_direction,
                i_pivot_as_direction=True)

        return {'FINISHED'}


class ZuvSetWorldSizeByMode(ZuvSetWorldSizeBase):
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="UV world size apply mode",
        items=[
            ("DEFAULT", "To Image and Mesh", "Apply to image and mesh"),
            ("TO_IMAGE", "To Image", "Apply to image only"),
            ("TO_MESH", "To Mesh", "Apply to mesh only"),
        ],
        default="DEFAULT"
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.prop(self, "mode")

        if self.mode in {'DEFAULT', 'TO_MESH'}:
            super().draw(context)


class ZUV_OT_SetWorldSize(ZuvSetWorldSizeBase, bpy.types.Operator):
    bl_idname = "uv.zenuv_set_world_size"
    bl_label = "Set World Size"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Sets the size of the island so that the texture of this island in the scene fills the size specified in the Size field"


class ZUV_OT_GetWorldSize(bpy.types.Operator):
    bl_idname = "uv.zenuv_get_world_size"
    bl_label = "Get World Size"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Get the texture size in real units"

    size: bpy.props.FloatProperty(
        name='Size',
        description='Size value',
        min=0.001,
        default=1.0
    )
    units: TransformSysOpsProps.get_units_enum()
    write_to_current_texture: bpy.props.BoolProperty(
        name='Write to Texture',
        description='Write world size value to the active texture',
        default=False)

    def draw(self, context):
        layout = self.layout

        box = layout.box()

        row = box.row(align=True)
        row.label(text='Size: ')

        row = row.row(align=True)
        row.alignment = 'RIGHT'
        row.prop(self, 'size', text='')
        row.prop(self, 'units', text='')
        layout.prop(self, 'write_to_current_texture')

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel, resort_objects_by_selection
        from ZenUV.ops.texel_density.td_utils import TdContext, TexelDensityFactory
        from mathutils import Matrix, Vector

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        objs = resort_objects_by_selection(context, objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        td_inputs = TdContext(context)

        p_image = ZuvWorldSizeUtils.getActiveImage(context)

        if p_image is not None:

            if p_image.size[0] == 0 or p_image.size[1] == 0:
                self.report({'WARNING'}, "Zen UV: It looks like selected texture isn't loaded into the scene.")
                return {'CANCELLED'}

            from ZenUV.utils.generic import UnitsConverter

            p_ref_image_size = p_image.size[:]
            td_inputs.image_size = p_ref_image_size

            td_inputs.units = UnitsConverter.converter[self.units]
            p_input_td = TexelDensityFactory.get_texel_density(context, objs, td_inputs)[0]

            p_ref_td = round(TexelDensityFactory._calc_referenced_td_world_size(p_ref_image_size, td_inputs)[0], 2)

        else:
            self.report({'INFO'}, "No active image detected.")
            return {'CANCELLED'}

        p_ma = Matrix.Diagonal(Vector.Fill(3, p_input_td / p_ref_td)).to_3x3()

        self.size = p_ma.inverted(p_ma).median_scale * UnitsConverter.rev_con[self.units]

        if self.write_to_current_texture:
            p_image.zen_uv.world_size.size = self.size
            p_image.zen_uv.world_size.units = self.units

        from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetUtils
        ZuvTrimsheetUtils.fix_undo()

        self.report({'INFO'}, f"Image: {p_image.name} - Size: {round(self.size, 2)} {self.units}")

        return {'FINISHED'}


class ZUV_OT_WorldSizeByTrim(ZuvSetWorldSizeByMode, bpy.types.Operator):
    bl_idname = "uv.zuv_world_size_by_trim"
    bl_label = 'Set UV World Size By Trim'
    bl_description = 'Set UV world size by active trim'
    bl_options = {'REGISTER', 'UNDO'}

    image_name: bpy.props.StringProperty(
        name='Image Name',
        default='',
        options={'HIDDEN'}
    )

    trim_uuid: bpy.props.StringProperty(
        name='Trim Uuid',
        default='',
        options={'HIDDEN'}
    )

    def execute(self, context: bpy.types.Context):
        try:
            p_image = bpy.data.images.get(self.image_name, None)
            if p_image is None:
                raise RuntimeError('Active image is not defined!')

            from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetUtils
            p_trimsheet = p_image.zen_uv.trimsheet
            idx = ZuvTrimsheetUtils.indexOfTrimByUuid(p_trimsheet, self.trim_uuid)
            if idx == -1:
                raise RuntimeError('Active trim is not defined!')

            p_trim = p_trimsheet[idx]

            d_real_width = p_trim.world_size[0]
            if d_real_width == 0:
                raise RuntimeError("World Size of active trim is not defined!")

            d_img_width = p_image.size[0]
            if d_img_width == 0:
                raise RuntimeError('Image width is zero!')

            p_pixel_width = p_trim.width_px
            if p_pixel_width == 0:
                raise RuntimeError('Trim pixel width is zero!')

            d_pixel_ratio = d_real_width / p_pixel_width
            d_real_image_size = d_img_width * d_pixel_ratio

            self.size = d_real_image_size
            self.units = p_trim.world_size_units

            if self.mode in {'DEFAULT', 'TO_IMAGE'}:
                p_image.zen_uv.world_size.size = self.size
                p_image.zen_uv.world_size.units = self.units

            if self.mode in {'DEFAULT', 'TO_MESH'}:
                super().execute(context)

            return {'FINISHED'}
        except Exception as e:
            self.report({'WARNING'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_WorldSizeExecutePreset(bpy.types.Operator):
    bl_idname = "wm.zuv_world_size_execute_preset"
    bl_options = {'REGISTER', 'UNDO'}

    bl_label = 'Load UV World Size Preset'
    bl_description = "Load uv world size preset from file"

    filepath: bpy.props.StringProperty(
        subtype='FILE_PATH',
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    # we need this to prevent 'getattr()' is None
    menu_idname: bpy.props.StringProperty(
        name="Menu ID Name",
        description="ID name of the menu this was called from",
        options={'SKIP_SAVE', 'HIDDEN'},
        default='ZUV_MT_StoreWorldSizePresets'
    )

    def get_preset_name(self):
        return Path(self.filepath).stem

    preset_name: bpy.props.StringProperty(
        name='Preset Name',
        get=get_preset_name
    )

    enable_confirmation: bpy.props.BoolProperty(
        name='Enable Confirmation',
        default=True
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if self.enable_confirmation:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        return self.execute(context)

    def execute(self, context):
        # Use this method because if it is inherited, can not change Blender theme !
        res = ExecutePreset.execute(self, context)

        update_areas_in_all_screens(context)

        return res


class ZUV_MT_StoreWorldSizePresets(bpy.types.Menu):
    bl_label = 'UV World Size Presets *'

    default_label = 'UV World Size Presets *'

    preset_subdir = ZuvPresets.get_preset_path(UV_WORLD_SIZE_PRESET_SUBDIR)
    preset_operator = 'wm.zuv_world_size_execute_preset'

    draw = bpy.types.Menu.draw_preset


class ZUV_OT_WorldSizeAddPreset(ZenAddPresetBase, bpy.types.Operator):
    bl_idname = 'uv.zuv_add_world_size_preset'
    bl_label = 'Add|Remove Preset'
    preset_menu = 'ZUV_MT_StoreWorldSizePresets'

    @classmethod
    def description(cls, context, properties):
        if properties:
            return ('Remove' if properties.remove_active else 'Add') + ' world size preset'
        else:
            return cls.bl_description

    # Common variable used for all preset values
    preset_defines = [
        'prefs = bpy.context.preferences.addons["ZenUV"].preferences.uv_world_size'
    ]

    # Properties to store in the preset
    preset_values = [
        'prefs.world_size_items',
        'prefs.world_size_items_index',
    ]

    # Directory to store the presets
    preset_subdir = ZuvPresets.get_preset_path(UV_WORLD_SIZE_PRESET_SUBDIR)


class ZUV_UL_WorldSizeList(bpy.types.UIList):

    def draw_item(self, context: bpy.types.Context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        # act_idx = getattr(active_data, active_propname)
        # b_active = index == act_idx

        row = layout.row(align=True)
        r1 = row.row(align=True)
        r1.prop(item, 'name', emboss=False, text="")

        r2 = row.row(align=True)
        r2.alignment = 'RIGHT'

        r2.label(text=f'{item.size:.2f} {item.units}')

        r2.separator()

        op = r2.operator(ZUV_OT_WorldSizeByPreset.bl_idname, icon="IMPORT", text="")
        op.item_index = index


class ZUV_OT_WorldSizeByPreset(ZuvSetWorldSizeByMode, bpy.types.Operator):
    bl_idname = "uv.zuv_world_size_by_preset"
    bl_label = 'UV World Size By Preset'
    bl_description = 'Set UV world size by active preset item'
    bl_options = {'REGISTER', 'UNDO'}

    item_index: bpy.props.IntProperty(
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def get_caption(self):
        addon_prefs = get_prefs()
        if self.item_index in range(len(addon_prefs.uv_world_size.world_size_items)):
            p_item = addon_prefs.uv_world_size.world_size_items[self.item_index]
            return f"{p_item.name} {p_item.size} {p_item.units}"

        return ""

    caption: bpy.props.StringProperty(
        name="Preset",
        get=get_caption
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.prop(self, "caption")

        if self.mode in {'DEFAULT', 'TO_MESH'}:
            super().draw(context)

    def execute(self, context: bpy.types.Context):
        try:
            p_image = ZuvWorldSizeUtils.getActiveImage(context)
            if p_image is None:
                raise RuntimeError('Active image is not defined!')

            addon_prefs = get_prefs()
            if self.item_index not in range(len(addon_prefs.uv_world_size.world_size_items)):
                raise RuntimeError("No active UV world size item!")

            p_item = addon_prefs.uv_world_size.world_size_items[self.item_index]

            self.size = p_item.size
            self.units = p_item.units

            if self.mode in {'DEFAULT', 'TO_IMAGE'}:
                p_image.zen_uv.world_size.size = self.size
                p_image.zen_uv.world_size.units = self.units

            if self.mode in {'DEFAULT', 'TO_MESH'}:
                super().execute(context)

            return {'FINISHED'}
        except Exception as e:
            self.report({'WARNING'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_WorldSizeAutoDetect(ZuvSetWorldSizeByMode, bpy.types.Operator):
    bl_idname = "uv.zuv_world_size_auto_detect"
    bl_label = 'UV World Size Auto Detect'
    bl_description = 'Set UV world size comparing image name with regular expression'
    bl_options = {'REGISTER', 'UNDO'}

    def get_caption(self):
        addon_prefs = get_prefs()
        if addon_prefs.uv_world_size.world_size_items_index in range(len(addon_prefs.uv_world_size.world_size_items)):
            p_item = addon_prefs.uv_world_size.world_size_items[addon_prefs.uv_world_size.world_size_items_index]
            return f"{p_item.name} {p_item.size} {p_item.units}"

        return ""

    caption: bpy.props.StringProperty(
        name="Preset",
        get=get_caption
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.prop(self, "caption")

        if self.mode in {'DEFAULT', 'TO_MESH'}:
            super().draw(context)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        addon_prefs = get_prefs()
        return len(addon_prefs.uv_world_size.world_size_items) > 0

    def execute(self, context: bpy.types.Context):
        try:
            p_image = ZuvWorldSizeUtils.getActiveImage(context)
            if p_image is None:
                raise RuntimeError('Active image is not defined!')

            addon_prefs = get_prefs()

            item_index = -1

            for idx, it in enumerate(addon_prefs.uv_world_size.world_size_items):
                if it.regex:
                    match = re.search(it.regex, p_image.filepath)
                    if match:
                        item_index = idx
                        break

            if item_index == -1:
                raise RuntimeError("Can not find any matches!")

            p_item = addon_prefs.uv_world_size.world_size_items[idx]
            addon_prefs.uv_world_size.world_size_items_index = item_index

            self.size = p_item.size
            self.units = p_item.units

            if self.mode in {'DEFAULT', 'TO_IMAGE'}:
                p_image.zen_uv.world_size.size = self.size
                p_image.zen_uv.world_size.units = self.units

            if self.mode in {'DEFAULT', 'TO_MESH'}:
                super().execute(context)

            return {'FINISHED'}
        except Exception as e:
            self.report({'WARNING'}, str(e))
        return {'CANCELLED'}


classes = (
    ZUV_PT_WorldSizeMaterial,
    ZUV_OT_SetWorldSize,
    ZUV_OT_GetWorldSize,
    ZUV_OT_WorldSizeByTrim,
    ZUV_OT_WorldSizeByPreset,
    ZUV_OT_WorldSizeAutoDetect,

    ZUV_OT_WorldSizeExecutePreset,
    ZUV_MT_StoreWorldSizePresets,
    ZUV_OT_WorldSizeAddPreset,

    ZUV_UL_WorldSizeList
)


def register_world_size():
    RegisterUtils.register(classes)


def unregister_world_size():
    RegisterUtils.unregister(classes)
