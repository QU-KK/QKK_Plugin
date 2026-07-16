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
class SNA_MT_B6303(bpy.types.Menu):
    bl_idname = "SNA_MT_B6303"
    bl_label = "(Qkk_3DMode)Mesh空格"

    @classmethod
    def poll(cls, context):
        return not ((not 'EDIT_MESH'==bpy.context.mode))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('mesh.hide', text='隐藏选中', icon_value=string_to_icon('VIS_SEL_01'), emboss=True, depress=False)
        op.unselected = False
        op = layout.operator('mesh.hide', text='独显选中', icon_value=string_to_icon('VIS_SEL_11'), emboss=True, depress=False)
        op.unselected = True
        layout.separator(factor=1.0)
        op = layout.operator('mesh.reveal', text='全部显示', icon_value=string_to_icon('HIDE_OFF'), emboss=True, depress=False)
        op.select = False


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_MT_B6303)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'SPACE', 'ANY',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_MT_B6303'
    addon_keymaps['17581'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_MT_B6303)
