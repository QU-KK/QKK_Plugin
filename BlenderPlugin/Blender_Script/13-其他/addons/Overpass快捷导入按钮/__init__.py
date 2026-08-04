# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "Bulk_import",
    "author" : "渠奎奎", 
    "description" : "大批量导入",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews
import time, sys
import pyperclip


addon_keymaps = {}
_icons = None
overpass = {'sna_into_guid': '', }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_OT_My_Generic_Operator_A846E(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a846e"
    bl_label = "大批量导入"
    bl_description = "大批量导入"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.console_toggle()
        for i_06DF4 in range(len(overpass['sna_into_guid'].split(','))):
            bpy.context.scene.overpass_tool.guid = overpass['sna_into_guid'].split(',')[i_06DF4]
            bpy.ops.overpass.import_messiah()
            i = float(float(i_06DF4 + 1.0) / len(overpass['sna_into_guid'].split(',')))

            def update_progress(progress):
                length = 80
                block = int(round(length*progress))
                msg = "\r{0}  {1}% ".format("█"*block + " "*(length-block), round(progress*100) )
                sys.stdout.write(msg)
            update_progress(i)
        bpy.ops.wm.console_toggle()
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.label(text='共计：' + str(len(overpass['sna_into_guid'].split(','))), icon_value=0)

    def invoke(self, context, event):
        overpass['sna_into_guid'] = ''
        clipboard_data = None
        # 读取剪贴板数据
        clipboard_data = pyperclip.paste()
        overpass['sna_into_guid'] = clipboard_data
        return context.window_manager.invoke_props_dialog(self, width=300)


def sna_add_to_view3d_ht_tool_header_362E5(self, context):
    if not ((not property_exists("bpy.context.scene.overpass_tool.guid", globals(), locals()))):
        layout = self.layout
        op = layout.operator('sna.my_generic_operator_a846e', text='', icon_value=706, emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A846E)
    bpy.types.VIEW3D_HT_tool_header.append(sna_add_to_view3d_ht_tool_header_362E5)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A846E)
    bpy.types.VIEW3D_HT_tool_header.remove(sna_add_to_view3d_ht_tool_header_362E5)
