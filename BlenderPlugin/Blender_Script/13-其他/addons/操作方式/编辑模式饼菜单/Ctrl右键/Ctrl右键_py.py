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
class SNA_MT_EB6F6(bpy.types.Menu):
    bl_idname = "SNA_MT_EB6F6"
    bl_label = "(Qkk_3DMode)MeshCtrl右键"

    @classmethod
    def poll(cls, context):
        return not ((not 'EDIT_MESH'==bpy.context.mode))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('mesh.select_edge_loop_multi', text='选循环边', icon_value=string_to_icon('GP_SELECT_POINTS'), emboss=True, depress=False)
        op = layout.operator('mesh.select_more', text='扩展选区', icon_value=string_to_icon('STICKY_UVS_LOC'), emboss=True, depress=False)
        op.use_face_step = False
        box_034FF = layout.box()
        box_034FF.alert = False
        box_034FF.enabled = True
        box_034FF.active = True
        box_034FF.use_property_split = False
        box_034FF.use_property_decorate = False
        box_034FF.alignment = 'Expand'.upper()
        box_034FF.scale_x = 1.0
        box_034FF.scale_y = 1.0
        if not True: box_034FF.operator_context = "EXEC_DEFAULT"
        col_D1AE2 = box_034FF.column(heading='', align=True)
        col_D1AE2.alert = False
        col_D1AE2.enabled = True
        col_D1AE2.active = True
        col_D1AE2.use_property_split = False
        col_D1AE2.use_property_decorate = False
        col_D1AE2.scale_x = 1.2000000476837158
        col_D1AE2.scale_y = 1.5
        col_D1AE2.alignment = 'Expand'.upper()
        col_D1AE2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_D1AE2.operator('mesh.select_face_by_sides', text='      选多边面', icon_value=string_to_icon('SEQ_CHROMA_SCOPE'), emboss=True, depress=False)
        op.number = 4
        op.type = 'GREATER'
        op = col_D1AE2.operator('mesh.select_non_manifold', text='      选非流形', icon_value=string_to_icon('ROOTCURVE'), emboss=True, depress=False)
        op = col_D1AE2.operator('mesh.select_interior_faces', text='      选内侧面', icon_value=string_to_icon('CON_SIZELIMIT'), emboss=True, depress=False)
        op = col_D1AE2.operator('mesh.select_loose', text='      松散元素', icon_value=string_to_icon('GRIP'), emboss=True, depress=False)
        op = layout.operator('mesh.select_all', text='反选', icon_value=string_to_icon('STICKY_UVS_VERT'), emboss=True, depress=False)
        op.action = 'INVERT'
        op = layout.operator('mesh.region_to_loop', text='选轮廓边', icon_value=string_to_icon('SELECT_SET'), emboss=True, depress=False)
        op = layout.operator('mesh.select_nth', text='间隔选取', icon_value=string_to_icon('CENTER_ONLY'), emboss=True, depress=False)
        op.offset = 1
        op = layout.operator('mesh.select_edge_ring_multi', text='选并排边', icon_value=string_to_icon('ALIGN_JUSTIFY'), emboss=True, depress=False)
        op = layout.operator('mesh.faces_select_linked_flat', text='选取元素块', icon_value=string_to_icon('SNAP_VERTEX'), emboss=True, depress=False)
        op.sharpness = 180.0


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_MT_EB6F6)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'ANY',
        ctrl=True, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_MT_EB6F6'
    addon_keymaps['4D821'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_MT_EB6F6)
