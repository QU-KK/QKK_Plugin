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

""" Zen Checker Main Panel """

import bpy
from bpy.types import Panel

from .properties import get_prefs
from .zen_checker_labels import ZCheckerLabels as label

from ZenUV.ico import icon_get
from ZenUV.zen_checker import checker
from ZenUV.prop.common import get_combo_panel_order
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.generic import (
    ZUV_REGION_TYPE, ZUV_SPACE_TYPE, ZUV_PANEL_CATEGORY)


class ZUV_PT_Checker(Panel):
    bl_idname = "ZUV_PT_Checker"
    bl_label = label.PANEL_CHECKER_LABEL
    bl_space_type = "VIEW_3D"
    bl_region_type = 'UI'
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_Checker')

    zen_icon_value = 'pn_CheckerMap'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_checker_map

    def draw(self, context):
        draw_checker_panel_3D(self, context)


class ZUV_PT_Checker_UVL(Panel):
    bl_idname = "ZUV_PT_Checker_UVL"
    bl_label = label.PANEL_CHECKER_LABEL
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = 'UI'
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('UV', 'ZUV_PT_Checker_UVL')

    get_icon = ZUV_PT_Checker.get_icon

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_UV_panels.enable_pt_checker_map

    def draw(self, context):
        draw_checker_panel_UV(self, context)


def draw_filtration_sys(context, layout):
    col = layout.column(align=True)
    addon_prefs = get_prefs().uv_checker_props

    row = col.row(align=True)
    col = row.column(align=True)
    row.prop(addon_prefs, "SizesX", text="", index=0)
    col = row.column(align=True)
    if addon_prefs.lock_axes:
        lock_icon = "LOCKED"
    else:
        lock_icon = "UNLOCKED"
    col.prop(addon_prefs, "lock_axes", icon=lock_icon, icon_only=True)
    col = row.column(align=True)
    col.enabled = not addon_prefs.lock_axes
    col.prop(addon_prefs, "SizesY", text="", index=0)
    row.prop(addon_prefs, "chk_orient_filter", icon="EVENT_O", icon_only=True)


class ZenUVCheckerPopover(Panel):
    """ Zen Checker Properties Popover """
    bl_idname = "ZUV_CH_PT_Properties"
    bl_label = "Zen Checker Properties"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        addon_prefs = get_prefs().uv_checker_props
        layout = self.layout
        layout.label(text=label.CHECKER_PANEL_LABEL)

        col = layout.column(align=True)
        row = col.row()
        col = row.column(align=True)
        col.prop(addon_prefs, "checker_assets_path", text="")
        col = row.column(align=True)
        col.operator("ops.zenuv_checker_reset_path", text="Reset Folder")

        layout.operator("view3d.zenuv_checker_append_checker_file", icon="FILEBROWSER")
        layout.operator("view3d.zenuv_checker_collect_images", icon="FILE_REFRESH")
        layout.prop(addon_prefs, "dynamic_update", )
        layout.operator("view3d.zenuv_checker_open_editor")
        layout.operator("view3d.zenuv_checker_reset")


def draw_checker_panel_UV(self, context: bpy.types.Context):
    ''' @Draw Texture Checker Panel UV '''
    addon_prefs = get_prefs().uv_checker_props
    layout = self.layout  # type: bpy.types.UILayout
    col = layout.column(align=True)
    row = col.row(align=True)
    checker.ZUVChecker_OT_CheckerToggle.draw_toggled(row, context)
    row.popover(panel="ZUV_CH_PT_Properties", text="", icon="PREFERENCES")

    # Filtration System
    if addon_prefs.chk_rez_filter:
        draw_filtration_sys(context, layout)

    row = layout.row(align=True)
    row.prop(context.scene.zen_uv, "tex_checker_interpolation", icon_only=True, icon="NODE_TEXTURE")
    row.prop(addon_prefs, "ZenCheckerImages", text='', index=0)

    row.prop(addon_prefs, "chk_rez_filter", icon="FILTER", icon_only=True)


class ZUV_PT_3DV_TextureCheckerSetup(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = "Setup"
    bl_parent_id = "ZUV_PT_CheckerSetup"
    bl_region_type = ZUV_REGION_TYPE
    bl_idname = "SYSTEM_PT_CheckerSetup"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_Checker"

    def draw(self, context):
        draw_texture_checker_setup_3D(self, context)


def draw_checker_panel_3D(self, context: bpy.types.Context):
    ''' @Draw Texture Checker Panel 3D '''
    from . import checker
    from . import ZUV_CheckerProperties
    from .files import ZUVChecker_OT_GetCheckerOverrideImage
    addon_prefs = get_prefs().uv_checker_props
    checker_prefs: ZUV_CheckerProperties = context.scene.zen_uv_checker

    layout = self.layout  # type: bpy.types.UILayout

    col = layout.column(align=True)
    row = col.row(align=True)
    checker.ZUVChecker_OT_CheckerToggle.draw_toggled(row, context)
    row.popover(panel="ZUV_CH_PT_Properties", text="", icon="PREFERENCES")
    col.operator("view3d.zenuv_checker_remove")

    # Filtration System
    if addon_prefs.chk_rez_filter and not checker_prefs.use_custom_image:
        draw_filtration_sys(context, layout)

    row = layout.row(align=True)

    row.prop(context.scene.zen_uv, "tex_checker_interpolation", icon_only=True, icon="NODE_TEXTURE")
    if checker_prefs.use_custom_image:
        row.prop(checker_prefs, 'override_image_name', text='')
        row.operator(ZUVChecker_OT_GetCheckerOverrideImage.bl_idname, icon="IMPORT", text='')
    else:
        row.prop(addon_prefs, "ZenCheckerImages", text='', index=0)
        row.prop(addon_prefs, "chk_rez_filter", icon="FILTER", icon_only=True)


def draw_texture_checker_setup_3D(self, context: bpy.types.Context):
    from ZenUV.prop.zuv_preferences import get_scene_props
    addon_scene_props = get_scene_props(context)
    cheker_prefs = context.scene.zen_uv_checker
    layout = self.layout

    layout.prop(cheker_prefs, 'use_custom_image', toggle=True)

    box = layout.box()
    b_is_active = context.area is not None and context.area.type == 'VIEW_3D' and len(context.area.spaces) and context.area.spaces[0].shading.type in {'RENDERED', 'MATERIAL'}
    box.enabled = b_is_active
    if not b_is_active:
        col = box.column(align=True)
        col.label(text='Available in Viewport Shading:')
        col.separator()
        col.label(text='Material Preview', icon='MATERIAL')
        col.label(text='Rendered', icon='SHADING_RENDERED')

    box.prop(addon_scene_props, "tex_checker_tiling")
    box.prop(addon_scene_props, "tex_checker_offset")


class ZUV_MT_ZenChecker_Popup(bpy.types.Menu):
    bl_label = "Zen Checker"
    bl_idname = "ZUV_MT_ZenChecker_Popup"
    bl_icon = "KEYTYPE_EXTREME_VEC"

    def draw(self, context):
        from .checker import ZUVChecker_OT_OpenEditor, ZUVChecker_OT_Reset

        if context.scene.zen_uv_checker.use_custom_image:
            layout = self.layout
            layout.label(text="Overrided Checker Texture is missing.")
            layout.label(text="Best way - Reset Checker to Default state.")
            layout.operator(ZUVChecker_OT_Reset.bl_idname)
            layout.label(text="Or set in the Checker panel override texture image name corectly.")
            layout.label(text="If you know what Nodes are, you can Open Shader Editor and do it manually.")
            layout.operator(ZUVChecker_OT_OpenEditor.bl_idname)
        else:
            layout = self.layout
            layout.label(text="Checker Texture is missing in nodes.")
            layout.label(text="Best way - Reset Checker to Default state.")
            layout.operator(ZUVChecker_OT_Reset.bl_idname)
            layout.label(text="If you know what Nodes are, you can Open Shader Editor and do it manually.")
            layout.operator(ZUVChecker_OT_OpenEditor.bl_idname)


classes = [
    ZenUVCheckerPopover,
    ZUV_MT_ZenChecker_Popup
]


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)


if __name__ == "__main__":
    pass
