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

""" Zen UV Operatopr local properties (Popups)"""
import bpy
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.blender_zen_utils import prop_with_icon


class STACK_PT_Properties(bpy.types.Panel):
    """ Internal Popover Zen UV STACK Section Properties"""
    bl_idname = "STACK_PT_Properties"
    bl_label = "Stack Properties"
    bl_context = "mesh_edit"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        addon_prefs = get_prefs()
        layout = self.layout
        layout.prop(addon_prefs, "stackMoveOnly")
        layout.separator()
        layout.label(text="Stack Offset:")
        layout.prop(addon_prefs, "stack_offset", text="")
        layout.label(text="Unstack Direction:")
        layout.prop(addon_prefs, "unstack_direction", text="")


class STACK_PT_DrawProperties(bpy.types.Panel):
    """ Internal Popover Zen UV STACK Section Properties"""
    bl_idname = "STACK_PT_DrawProperties"
    bl_label = "Stack Draw Properties"
    bl_context = "__POPUP__"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 12

    def draw(self, context):
        addon_prefs = get_prefs()
        layout = self.layout

        p_scene = context.scene

        wm = context.window_manager
        prop_with_icon(layout, wm.zen_uv.draw_props, 'draw_auto_update', 'FILE_REFRESH', s_icon_operator_id='wm.zuv_draw_update')

        col = layout.column()
        col.use_property_split = True
        col.prop(addon_prefs, "StackedColor")
        col.prop(p_scene.zen_uv, "st_uv_area_only")


class MARK_PT_Properties(bpy.types.Panel):
    """ Internal Popover Zen UV  MARK Section Properties"""
    bl_idname = "MARK_PT_Properties"
    bl_label = "Mark Properties"
    bl_context = "mesh_edit"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        addon_prefs = get_prefs()
        layout = self.layout
        layout.prop(addon_prefs, "useGlobalMarkSettings")
        box = layout.box()
        if addon_prefs.useGlobalMarkSettings:
            box.prop(addon_prefs, 'markSeamEdges')
            box.prop(addon_prefs, 'markSharpEdges')
        else:
            box.label(text="Settings in Local mode.")


class FINISHED_PT_Properties(bpy.types.Panel):
    """ Internal Popover Zen UV FINISHED Section Properties"""
    bl_idname = "FINISHED_PT_Properties"
    bl_label = "Finished Properties"
    bl_context = "__POPUP__"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 14

    def draw(self, context):
        addon_prefs = get_prefs()
        layout = self.layout

        col = layout.column()
        col.use_property_split = True
        col.prop(addon_prefs, 'autoFinishedToPinned')
        col.prop(addon_prefs, 'sortAutoSorting')

        wm = context.window_manager
        prop_with_icon(layout, wm.zen_uv.draw_props, 'draw_auto_update', 'FILE_REFRESH', s_icon_operator_id='wm.zuv_draw_update')

        col = layout.column()
        col.use_property_split = True
        col.prop(addon_prefs, 'FinishedColor')
        col.prop(addon_prefs, 'UnFinishedColor')


class RELAX_PT_Properties(bpy.types.Panel):
    """ Internal Popover Zen UV Relax Section Properties"""
    bl_idname = "RELAX_PT_Properties"
    bl_label = "Relax Properties"
    bl_context = "mesh_edit"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        addon_prefs = get_prefs()
        layout = self.layout
        layout.prop(addon_prefs, 'use_zensets')


# class PACK_PT_Properties(bpy.types.Panel):
#     """ Internal Popover Zen UV PACK Section Properties"""
#     bl_idname = "PACK_PT_Properties"
#     bl_label = "Pack Properties"
#     bl_context = "mesh_edit"
#     bl_space_type = 'PROPERTIES'
#     bl_region_type = 'WINDOW'

#     def draw(self, context):
#         addon_prefs = get_prefs()
#         layout = self.layout
#         if not addon_prefs.packEngine == "UVPACKER":
#             layout.prop(addon_prefs, 'margin_show_in_px')

#         # Select Engine
#         row = layout.row(align=True)
#         row.label(text=ZuvLabels.PREF_PACK_ENGINE_LABEL + ':')
#         row = layout.row(align=True)
#         row.prop(addon_prefs, "packEngine", text="")

#         # Sync settings to UVP
#         if addon_prefs.packEngine == 'UVP':
#             row.operator("uv.zenuv_sync_to_uvp", text="", icon="FILE_REFRESH")

#         # # Custom Engine Settings
#         # if addon_prefs.packEngine == "CUSTOM":
#         #     layout.prop(addon_prefs, "customEngine", text="")


if __name__ == '__main__':
    pass
