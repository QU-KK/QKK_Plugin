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

import bpy
from ZenUV.ui.labels import ZuvLabels
from ZenUV.ops.zen_unwrap.props import get_zen_unwrap_addon_prefs
# from ZenUV.prop.zuv_preferences import get_prefs


class ZENUNWRAP_PT_Properties(bpy.types.Panel):
    bl_idname = "ZENUNWRAP_PT_Properties"
    bl_label = "Zen Unwrap Properties"
    bl_context = "mesh_edit"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 14

    def draw(self, context: bpy.types.Context):
        op_global_prefs = get_zen_unwrap_addon_prefs()

        layout = self.layout
        layout.use_property_split = True
        layout.prop(op_global_prefs, "autoActivateUVSync")

        wm = context.window_manager
        op_props = wm.operator_properties_last("uv.zenuv_unwrap")
        if op_props:
            layout.prop(op_props, 'ProcessingMode')
            layout.prop(op_props, 'UnwrapMethod')
            layout.prop(op_props, "post_td_mode")
            layout.prop(op_props, "packAfUnwrap")

        layout.prop(op_global_prefs, "unwrapAutoSorting")


class ZenUV_MT_ZenUnwrap_Popup(bpy.types.Menu):
    bl_label = "Zen Unwrap"
    bl_idname = "ZUV_MT_ZenUnwrap_Popup"
    bl_icon = "KEYTYPE_EXTREME_VEC"

    def draw(self, context):
        layout = self.layout
        layout.label(text=ZuvLabels.ZEN_UNWRAP_POPUP_LABEL)
        layout.separator
        layout.operator("uv.zenuv_unwrap", text="Continue as is").action = "CONTINUE"
        layout.operator("uv.zenuv_unwrap", text=ZuvLabels.ZEN_UNWRAP_AUTO_MODE_LABEL).action = "AUTO"
        layout.operator("uv.zenuv_auto_mark")
        layout.operator("uv.zenuv_seams_by_sharp")
        layout.operator("uv.zenuv_seams_by_uv_islands")


class ZenUV_MT_ZenUnwrap_ConfirmPopup(bpy.types.Menu):
    bl_label = "Zen Unwrap"
    bl_idname = "ZUV_MT_ZenUnwrap_ConfirmPopup"
    bl_icon = "KEYTYPE_EXTREME_VEC"

    def draw(self, context):
        from ZenUV.ops.zen_unwrap.ops import ZUV_OT_ProxyUnwrapAllSelected
        layout = self.layout
        layout.label(text="Nothing is selected. The whole object(s) will be unwrapped.")
        layout.separator
        layout.operator(ZUV_OT_ProxyUnwrapAllSelected.bl_idname, text="Ok").action = "DEFAULT"
        # layout.operator("uv.zenuv_unwrap", text="Ok").action = "DEFAULT"
