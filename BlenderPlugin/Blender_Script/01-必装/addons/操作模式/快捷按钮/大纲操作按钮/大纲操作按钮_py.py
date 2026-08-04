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


def sna_add_to_outliner_ht_header_B09FF(self, context):
    if not (False):
        layout = self.layout
        grid_BC2A8 = layout.grid_flow(columns=3, row_major=False, even_columns=False, even_rows=False, align=True)
        grid_BC2A8.enabled = True
        grid_BC2A8.active = True
        grid_BC2A8.use_property_split = False
        grid_BC2A8.use_property_decorate = False
        grid_BC2A8.alignment = 'Expand'.upper()
        grid_BC2A8.scale_x = 1.0
        grid_BC2A8.scale_y = 1.0
        if not True: grid_BC2A8.operator_context = "EXEC_DEFAULT"
        op = grid_BC2A8.operator('outliner.show_active', text='', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)
        op = grid_BC2A8.operator('object.select_grouped', text='', icon_value=string_to_icon('PRESET'), emboss=True, depress=False)
        op.extend = True
        op.type = 'COLLECTION'
        op = grid_BC2A8.operator('outliner.show_one_level', text='', icon_value=string_to_icon('OUTLINER_COLLECTION'), emboss=True, depress=False)
        op.open = False


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.OUTLINER_HT_header.prepend(sna_add_to_outliner_ht_header_B09FF)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.types.OUTLINER_HT_header.remove(sna_add_to_outliner_ht_header_B09FF)
