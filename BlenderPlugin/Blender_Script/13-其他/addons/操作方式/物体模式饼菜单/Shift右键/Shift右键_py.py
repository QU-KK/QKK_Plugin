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
class SNA_MT_50BBC(bpy.types.Menu):
    bl_idname = "SNA_MT_50BBC"
    bl_label = "(Qkk_3DMode)ObjShift右键"

    @classmethod
    def poll(cls, context):
        return not ('EDIT_MESH'==bpy.context.mode)

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('object.convert', text='转换到', icon_value=string_to_icon('DECORATE_DRIVER'), emboss=True, depress=False)
        op = layout.operator('view3d.snap_selected_to_active', text='PSR', icon_value=string_to_icon('PIVOT_INDIVIDUAL'), emboss=True, depress=False)
        op = layout.operator('object.make_links_data', text='关联材质', icon_value=string_to_icon('GEOMETRY_NODES'), emboss=True, depress=False)
        op.type = 'MATERIAL'
        op = layout.operator('object.duplicates_make_real', text='实例独立化', icon_value=string_to_icon('MONKEY'), emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_MT_50BBC)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'PRESS',
        ctrl=False, alt=False, shift=True, repeat=False)
    kmi.properties.name = 'SNA_MT_50BBC'
    addon_keymaps['33583'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_MT_50BBC)
