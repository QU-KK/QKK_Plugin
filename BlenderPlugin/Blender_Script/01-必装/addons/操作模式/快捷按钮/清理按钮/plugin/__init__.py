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


def sna_add_to_topbar_mt_editor_menus_4A3E3(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('outliner.orphans_purge', text='清理', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.TOPBAR_MT_editor_menus.append(sna_add_to_topbar_mt_editor_menus_4A3E3)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.types.TOPBAR_MT_editor_menus.remove(sna_add_to_topbar_mt_editor_menus_4A3E3)
