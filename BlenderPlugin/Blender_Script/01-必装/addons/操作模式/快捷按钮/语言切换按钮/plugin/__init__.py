import bpy
import bpy.utils.previews


addon_keymaps = {}
_icons = None


def sna_add_to_statusbar_ht_header_4ED2A(self, context):
    if not (False):
        layout = self.layout
        if (bpy.context.preferences.view.language == 'zh_HANS'):
            op = layout.operator('sna.language_switch_b775d', text='中文', icon_value=0, emboss=False, depress=False)
            op.sna_language_data = 'en_US'
        if (bpy.context.preferences.view.language == 'en_US'):
            op = layout.operator('sna.language_switch_b775d', text='English', icon_value=0, emboss=False, depress=False)
            op.sna_language_data = 'zh_HANS'


class SNA_OT_Language_Switch_B775D(bpy.types.Operator):
    bl_idname = "sna.language_switch_b775d"
    bl_label = "language_switch"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_language_data: bpy.props.StringProperty(name='language_data', description='', default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.preferences.view.language = self.sna_language_data
        bpy.context.preferences.view.use_translate_new_dataname = False
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.STATUSBAR_HT_header.prepend(sna_add_to_statusbar_ht_header_4ED2A)
    bpy.utils.register_class(SNA_OT_Language_Switch_B775D)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.types.STATUSBAR_HT_header.remove(sna_add_to_statusbar_ht_header_4ED2A)
    bpy.utils.unregister_class(SNA_OT_Language_Switch_B775D)
