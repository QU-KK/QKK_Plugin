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
    "name" : "Operation_v3",
    "author" : "渠奎奎", 
    "description" : "操作方式4.2",
    "blender" : (4, 2, 0),
    "version" : (3, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews




def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


addon_keymaps = {}
_icons = None
class SNA_OT_My_Generic_Operator_A753D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a753d"
    bl_label = "贴图材质管理"
    bl_description = "贴图材质管理"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.wm.window_new()
        bpy.context.area.ui_type = 'OUTLINER'
        bpy.context.space_data.display_mode = 'LIBRARIES'
        bpy.context.space_data.filter_id_type = 'IMAGE'
        bpy.context.space_data.use_filter_id_type = True
        bpy.ops.screen.area_split(direction='VERTICAL', factor=0.2)
        bpy.context.area.ui_type = 'OUTLINER'
        bpy.context.space_data.display_mode = 'LIBRARIES'
        bpy.context.space_data.filter_id_type = 'MATERIAL'
        bpy.context.space_data.use_filter_id_type = True
        bpy.ops.screen.area_split(direction='VERTICAL', factor=0.75)
        bpy.context.area.ui_type = 'IMAGE_EDITOR'
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_add_to_topbar_mt_editor_menus_E214F(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('sna.my_generic_operator_a753d', text='窗口', icon_value=string_to_icon('TOPBAR'), emboss=False, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A753D)
    bpy.types.TOPBAR_MT_editor_menus.append(sna_add_to_topbar_mt_editor_menus_E214F)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A753D)
    bpy.types.TOPBAR_MT_editor_menus.remove(sna_add_to_topbar_mt_editor_menus_E214F)
