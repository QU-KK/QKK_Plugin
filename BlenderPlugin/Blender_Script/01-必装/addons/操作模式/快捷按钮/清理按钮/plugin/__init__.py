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


def sna_add_to_topbar_mt_editor_menus_16D48(self, context):
    if not (False):
        layout = self.layout
        row_B9B64 = layout.row(heading='', align=True)
        row_B9B64.alert = False
        row_B9B64.enabled = True
        row_B9B64.active = True
        row_B9B64.use_property_split = False
        row_B9B64.use_property_decorate = False
        row_B9B64.scale_x = 1.0
        row_B9B64.scale_y = 1.0
        row_B9B64.alignment = 'Expand'.upper()
        row_B9B64.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_B9B64.separator(factor=1.0)
        op = row_B9B64.operator('outliner.orphans_purge', text='清理', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.TOPBAR_MT_editor_menus.append(sna_add_to_topbar_mt_editor_menus_16D48)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.types.TOPBAR_MT_editor_menus.remove(sna_add_to_topbar_mt_editor_menus_16D48)
