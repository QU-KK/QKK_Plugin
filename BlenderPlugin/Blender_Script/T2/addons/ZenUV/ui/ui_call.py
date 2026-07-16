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

""" Zen UV Call Operators """
import bpy

popup_areas = set()


class ZUV_OT_Main_Popup_call(bpy.types.Operator):
    bl_idname = "zenuv.call_popup"
    bl_label = "Zen UV Popup Panel"
    bl_description = "Calls Zen UV popup panel"
    bl_options = {"REGISTER", "UNDO"}

    def draw(self, context: bpy.types.Context):

        global popup_areas
        popup_areas.add(context.area.as_pointer())

        if hasattr(context, 'space_data') and context.space_data is not None:
            if context.space_data.type == 'IMAGE_EDITOR':
                from ZenUV.ui.combo_panel import ZuvComboBase, ZUV_PT_UVL_ComboPanel
                pnl = ZuvComboBase()
                pnl.bl_space_type = ZUV_PT_UVL_ComboPanel.bl_space_type
                pnl.layout = self.layout
                pnl.draw(context)
            elif context.space_data.type == 'VIEW_3D':
                from ZenUV.ui.combo_panel import ZuvComboBase, ZUV_PT_3DV_ComboPanel
                pnl = ZuvComboBase()
                pnl.bl_space_type = ZUV_PT_3DV_ComboPanel.bl_space_type
                pnl.layout = self.layout
                pnl.draw(context)

    def execute(self, context: bpy.types.Context):
        wm = context.window_manager
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        return wm.invoke_popup(self, width=addon_prefs.combo_panel.combo_popup_width)
