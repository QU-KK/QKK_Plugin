import bpy
import bpy.utils.previews
import os




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
class SNA_OT_D_9Ac18(bpy.types.Operator):
    bl_idname = "sna.d_9ac18"
    bl_label = "3D视图操作"
    bl_description = "3D视图操作"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='键位映射', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.preferences.keyconfig_import(filepath=self.sna_new_property)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_operation_preset_26EB4(bpy.types.Panel):
    bl_label = '键位映射'
    bl_idname = 'SNA_PT_operation_preset_26EB4'
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
        op = layout.operator('sna.d_9ac18', text='Maya 3D视图操作方式', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = os.path.join(os.path.dirname(__file__), 'assets', 'Qkk_maya.py')
        op = layout.operator('sna.d_9ac18', text='Max 3D视图操作方式', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = os.path.join(os.path.dirname(__file__), 'assets', 'Qkk_max.py')
        op = layout.operator('sna.d_9ac18', text='Blender默认 3D视图操作方式', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = os.path.join(os.path.dirname(__file__), 'assets', 'Qkk_Blender.py')


def sna_add_to_userpref_pt_navigation_bar_E8243(self, context):
    if not (False):
        layout = self.layout
        layout.popover('SNA_PT_operation_preset_26EB4', text='键位映射', icon_value=string_to_icon('MOUSE_LMB_DRAG'))


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_D_9Ac18)
    bpy.utils.register_class(SNA_PT_operation_preset_26EB4)
    bpy.types.USERPREF_PT_navigation_bar.append(sna_add_to_userpref_pt_navigation_bar_E8243)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_OT_D_9Ac18)
    bpy.utils.unregister_class(SNA_PT_operation_preset_26EB4)
    bpy.types.USERPREF_PT_navigation_bar.remove(sna_add_to_userpref_pt_navigation_bar_E8243)
