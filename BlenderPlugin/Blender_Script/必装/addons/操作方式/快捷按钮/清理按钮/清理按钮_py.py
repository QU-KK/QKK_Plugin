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


def sna_add_to_view3d_mt_editor_menus_AA520(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('outliner.orphans_manage', text='', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
        op = layout.operator('outliner.orphans_purge', text='清理', icon_value=0, emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.VIEW3D_MT_editor_menus.append(sna_add_to_view3d_mt_editor_menus_AA520)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.types.VIEW3D_MT_editor_menus.remove(sna_add_to_view3d_mt_editor_menus_AA520)
