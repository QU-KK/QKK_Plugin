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

""" Zen UV Pack Sys UI """


import bpy

from ZenUV.ico import icon_get
from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.generic import (
    ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE,
    ZUV_SPACE_TYPE)
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.prop.common import get_combo_panel_order
from ZenUV.utils.blender_zen_utils import ZenPolls

from .pack import UVPmPoll, UVPmData


def draw_pack_engine(self, context):
    ''' @Draw Pack Engine '''
    addon_prefs = get_prefs()
    layout = self.layout
    # Select Engine
    row = layout.row(align=True)
    row.label(text=ZuvLabels.PREF_PACK_ENGINE_LABEL + ':')
    row = layout.row(align=True)
    row.prop(addon_prefs, "packEngine", text="")

    if not addon_prefs.packEngine == "UVPACKER":
        layout.prop(addon_prefs, 'margin_show_in_px')

    # Sync settings to UVP
    if addon_prefs.packEngine == 'UVP':
        row.operator("uv.zenuv_sync_to_uvp", text="", icon="FILE_REFRESH")

    # # Custom Engine Settings
    # if addon_prefs.packEngine == "CUSTOM":
    #     layout.prop(addon_prefs, "customEngine", text="")


def draw_pack(self, context):
    ''' @Draw Pack '''
    from ZenUV.zen_checker.check_utils import ZUV_OT_CalculateRecommendedMargin
    addon_prefs = get_prefs()
    layout = self.layout
    prop = context.scene.zen_uv

    # Pack Section
    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator("uv.zenuv_pack", icon_value=icon_get('pack')).display_uv = True
    # row.popover(panel="PACK_PT_Properties", text="", icon="PREFERENCES")
    if not addon_prefs.packEngine == "UVPACKER":
        row = col.row(align=True)
        if addon_prefs.margin_show_in_px:
            row.prop(addon_prefs, 'margin_px')
        else:
            row.prop(addon_prefs, 'margin')
        if context.space_data.type == 'IMAGE_EDITOR':
            row.operator(ZUV_OT_CalculateRecommendedMargin.bl_idname, icon='DESKTOP', text='')
    else:
        col.prop(prop, "pack_uv_packer_margin")

    draw_uv_coverage(context, layout)


def draw_uv_coverage(context, layout):
    prop = context.scene.zen_uv
    box = layout.box()

    row = box.row(align=True)
    row.prop(prop, 'get_uv_coverage_mode')
    row.operator("uv.zenuv_get_uv_coverage", icon="FILE_REFRESH", text="").mode = prop.get_uv_coverage_mode

    row = box.row(align=True)
    p_cov_value = round(context.scene.zen_uv.td_props.prp_uv_coverage, 2)
    uv_coverage_label = "UV Coverage: " + str(p_cov_value) + " %"
    row.label(text=uv_coverage_label)
    p_empty = round(100 - p_cov_value, 2) if p_cov_value <= 100 else '~'
    box.label(text=f'Empty space: {p_empty} %')


def draw_packer_props(self, context: bpy.types.Context):
    ''' @Draw Packer Properties '''
    addon_prefs = get_prefs()
    layout: bpy.types.UILayout = self.layout
    zen_props = context.scene.zen_uv
    draw_pack_engine(self, context)
    if addon_prefs.packEngine == 'UVPACKER':
        box = layout.box()
        box.label(text='UV-Packer can not pack correctly')
        box.label(text=' if UV Editor image is non-square.')
    box = layout.box()
    if addon_prefs.packEngine != 'UVP':
        from ZenUV.ops.operators import ZUV_OT_SetTextureSizePreset
        ZUV_OT_SetTextureSizePreset.draw_image_size_preset(
            'scene.zen_uv.td_props.td_im_size_presets',
            context, box)

    # General Settings
    box.prop(addon_prefs, 'averageBeforePack')
    box.prop(addon_prefs, 'rotateOnPack')
    box.prop(addon_prefs, 'packSelectedIslOnly')
    if addon_prefs.packEngine == 'BLDR':
        if ZenPolls.version_greater_3_6_0:
            # box.prop(addon_prefs, 'packSelectedIslOnly')
            box.prop(addon_prefs, "lock_overlapping_enable")
            box.prop(addon_prefs, 'pack_blen_margin_method')
            box.prop(addon_prefs, 'packInTrim')

    # UVP Settings
    if addon_prefs.packEngine == 'UVP':
        # layout.prop(addon_prefs, "keepStacked")
        # box.prop(addon_prefs, 'packSelectedIslOnly')
        box.prop(addon_prefs, "packFixedScale")
        box.prop(addon_prefs, "lock_overlapping_mode")
        if UVPmPoll.version_since_3_4_0():
            box.prop(addon_prefs, 'packInTrim')
            try:
                p_prefs = UVPmData.get_packmaster_prefs()
                if not p_prefs:
                    raise RuntimeError("Can not get UVPackmaster preferences!")

                active_mode = p_prefs.get_active_main_mode(context)
                box = layout.box()
                box.label(text="PackingMode:")
                row = box.row(align=True)
                row.menu("UVPM3_MT_BrowseModes", text=type(active_mode).enum_name(), icon='COLLAPSEMENU')

                UVP_PANELS_MODULE = UVPmData.get_packmaster_pack_panels_module()
                if not UVP_PANELS_MODULE:
                    raise RuntimeError("Can not import 'pack_panels' module!")

                panel_t = getattr(UVP_PANELS_MODULE, "UVPM3_PT_TileSetup", None)
                if panel_t is None:
                    raise RuntimeError("UVPM3_PT_TileSetup not found!")

                b_poll_disabled = hasattr(panel_t, 'poll') and not panel_t.poll(context)
                if not b_poll_disabled:
                    panel = panel_t()
                    panel.multi_panel = True
                    panel.layout = box
                    panel.draw(context)
            except Exception as e:
                box.label(text="Failed to embed UVPM3:", icon='ERROR')
                box.label(text=str(e))

        elif UVPmPoll.version_since_3():
            uvp_3_scene_props = context.scene.uvpm3_props
            box.prop(addon_prefs, 'packInTrim')
            pm = box.column(align=True)
            pm.label(text="PackingMode:")
            pm.prop(zen_props, 'uvp3_packing_method', text='')
            packing_method = zen_props.uvp3_packing_method
            if packing_method == 'pack.single_tile':
                pass
            elif packing_method == 'pack.tiles':
                box = layout.box()
                col = box.column(align=True)
                tile_col = col.column(align=True)
                tile_col.prop(uvp_3_scene_props, "tile_count_x")
                tile_col.prop(uvp_3_scene_props, "tile_count_y")

            if packing_method in ['pack.groups_to_tiles', 'pack.groups_together']:
                box = layout.box()
                col = box.column(align=True)
                col.label(text="Grouping Method:")
                col.prop(uvp_3_scene_props, "group_method", text='')

            if packing_method == 'pack.groups_to_tiles':
                if uvp_3_scene_props.group_method != '4':
                    col.label(text='Grouping options:')
                    box_in = col.box()
                    col_in = box_in.column(align=True)
                    col_in.label(text='Texel Density Policy:')
                    col_in.prop(uvp_3_scene_props.auto_group_options, "tdensity_policy", text='')
                    col.prop(uvp_3_scene_props.auto_group_options.base, "tiles_in_row")
            if packing_method == 'pack.groups_together':
                if uvp_3_scene_props.group_method != '4':
                    col.label(text='Grouping options:')
                    col.prop(uvp_3_scene_props.auto_group_options.base, "group_compactness")
        elif UVPmPoll.version_2():
            if hasattr(context.scene, "uvp2_props") and hasattr(context.scene.uvp2_props, "margin"):
                uvp_2_scene_props = context.scene.uvp2_props
                pm = box.column(align=True)
                pm.label(text="PackingMode:")
                pm.prop(uvp_2_scene_props, "pack_mode", text='')
                if uvp_2_scene_props.pack_mode in ["2", "3"]:
                    col = box.column(align=True)
                    col.label(text="Grouping Method:")
                    col.prop(uvp_2_scene_props, "group_method", text='')
                if uvp_2_scene_props.pack_mode == "2":
                    pm.prop(uvp_2_scene_props, "group_compactness")
                if uvp_2_scene_props.pack_mode == "3":
                    pm.prop(uvp_2_scene_props, "tiles_in_row")
                if uvp_2_scene_props.pack_mode in ["1", ]:
                    col = box.column(align=True)
                    tile_col = col.column(align=True)
                    # tile_col.enabled = tile_col_enabled
                    tile_col.prop(uvp_2_scene_props, "tile_count")
                    tile_col.prop(uvp_2_scene_props, "tiles_in_row")


class ZUV_PT_UVL_Pack(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_idname = "ZUV_PT_UVL_Pack"
    bl_label = ZuvLabels.PANEL_PACK_LABEL
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('UV', 'ZUV_PT_UVL_Pack')

    zen_icon_value = 'pn_Pack'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_UV_panels.enable_pt_pack and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit Mode'

    def draw(self, context):
        draw_pack(self, context)


class ZUV_PT_Pack(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_idname = "ZUV_PT_Pack"
    bl_label = ZuvLabels.PANEL_PACK_LABEL
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_Pack')

    zen_icon_value = 'pn_Pack'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_pack and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context: bpy.types.Context):
        return context.mode in {'EDIT_MESH', 'OBJECT'}

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit and Object Modes'

    def draw(self, context: bpy.types.Context):
        if context.mode == 'EDIT_MESH':
            draw_pack(self, context)
        elif context.mode == 'OBJECT':
            draw_uv_coverage(context, self.layout)


class PROPS_PT_Packer(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = "Pack Engine"
    bl_parent_id = "ZUV_PT_Pack"
    bl_region_type = ZUV_REGION_TYPE
    bl_idname = "PROPS_PT_Packer"
    # bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh Mode'
        return ''

    def draw(self, context):
        draw_packer_props(self, context)


class PROPS_PT_UVL_Packer(bpy.types.Panel):
    bl_idname = "PROPS_PT_UVL_Packer"
    bl_space_type = "IMAGE_EDITOR"
    bl_label = "Pack Engine"
    bl_parent_id = "ZUV_PT_UVL_Pack"
    bl_region_type = ZUV_REGION_TYPE
    # bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh Mode'
        return ''

    def draw(self, context):
        draw_packer_props(self, context)


pack_ui_parented_panels = [
    # ZUV_PT_Pack,
    # ZUV_PT_UVL_Pack,
    PROPS_PT_UVL_Packer,
    PROPS_PT_Packer,
]
