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
class SNA_PT_WALK_38C43(bpy.types.Panel):
    bl_label = 'walk'
    bl_idname = 'SNA_PT_WALK_38C43'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_context = ''
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_CDEF7 = layout.column(heading='', align=False)
        col_CDEF7.alert = False
        col_CDEF7.enabled = True
        col_CDEF7.active = True
        col_CDEF7.use_property_split = False
        col_CDEF7.use_property_decorate = False
        col_CDEF7.scale_x = 1.0
        col_CDEF7.scale_y = 1.0
        col_CDEF7.alignment = 'Expand'.upper()
        col_CDEF7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_CDEF7.prop(bpy.context.preferences.inputs.walk_navigation, 'walk_speed', text='速度', icon_value=0, emboss=True)
        col_CDEF7.prop(bpy.context.preferences.inputs.walk_navigation, 'mouse_speed', text='视角灵敏度', icon_value=0, emboss=True)
        col_CDEF7.prop(bpy.context.preferences.inputs.walk_navigation, 'use_gravity', text='重力', icon_value=0, emboss=True)
        if bpy.context.preferences.inputs.walk_navigation.use_gravity:
            col_90169 = col_CDEF7.column(heading='', align=False)
            col_90169.alert = False
            col_90169.enabled = True
            col_90169.active = True
            col_90169.use_property_split = False
            col_90169.use_property_decorate = False
            col_90169.scale_x = 1.0
            col_90169.scale_y = 1.0
            col_90169.alignment = 'Expand'.upper()
            col_90169.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_90169.prop(bpy.context.preferences.inputs.walk_navigation, 'jump_height', text='跳跃高度', icon_value=0, emboss=True)
            col_90169.prop(bpy.context.preferences.inputs.walk_navigation, 'view_height', text='视角高度', icon_value=0, emboss=True)


def sna_add_to_view3d_mt_editor_menus_58825(self, context):
    if not (False):
        layout = self.layout
        split_CCEA2 = layout.split(factor=0.800000011920929, align=True)
        split_CCEA2.alert = False
        split_CCEA2.enabled = True
        split_CCEA2.active = True
        split_CCEA2.use_property_split = False
        split_CCEA2.use_property_decorate = False
        split_CCEA2.scale_x = 1.0
        split_CCEA2.scale_y = 1.0
        split_CCEA2.alignment = 'Expand'.upper()
        if not True: split_CCEA2.operator_context = "EXEC_DEFAULT"
        op = split_CCEA2.operator('view3d.walk', text='行走', icon_value=string_to_icon('ARMATURE_DATA'), emboss=True, depress=False)
        split_CCEA2.popover('SNA_PT_WALK_38C43', text='', icon_value=0)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_PT_WALK_38C43)
    bpy.types.VIEW3D_MT_editor_menus.append(sna_add_to_view3d_mt_editor_menus_58825)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_PT_WALK_38C43)
    bpy.types.VIEW3D_MT_editor_menus.remove(sna_add_to_view3d_mt_editor_menus_58825)
