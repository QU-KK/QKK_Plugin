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
class SNA_MT_BB798(bpy.types.Menu):
    bl_idname = "SNA_MT_BB798"
    bl_label = "(Qkk_3DMode)ObjCtrl右键"

    @classmethod
    def poll(cls, context):
        return not ('EDIT_MESH'==bpy.context.mode)

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('object.select_grouped', text='按组选择', icon_value=string_to_icon('OPTIONS'), emboss=True, depress=False)
        op = layout.operator('object.select_by_type', text='按类型择', icon_value=string_to_icon('COMMUNITY'), emboss=True, depress=False)
        op = layout.operator('object.select_camera', text='选择活动相机', icon_value=string_to_icon('VIEW_CAMERA'), emboss=True, depress=False)
        op = layout.operator('object.select_linked', text='按相连元素选择', icon_value=string_to_icon('SHADING_TEXTURE'), emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_MT_BB798)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'ANY',
        ctrl=True, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_MT_BB798'
    addon_keymaps['A34B3'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_MT_BB798)
