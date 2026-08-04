import bpy
import bpy.utils.previews
import blf
import os
import mathutils


addon_keymaps = {}
_icons = None
handler_6E846 = []


def region_by_type(area, region_type):
    for region in area.regions:
        if region.type == region_type:
            return region
    return area.regions[0]


class SNA_OT_My_Generic_Operator_896Aa(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_896aa"
    bl_label = "(Qkk_3DMode)V吸附"
    bl_description = "(Qkk_3DMode)V吸附"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        if ('OBJECT'==bpy.context.mode or 'EDIT_MESH'==bpy.context.mode):
            if bpy.context.scene.tool_settings.use_snap:
                bpy.context.scene.tool_settings.use_snap = False
                for i_42D99 in range(2):
                    if handler_6E846:
                        bpy.types.SpaceView3D.draw_handler_remove(handler_6E846[0], 'WINDOW')
                        handler_6E846.pop(0)
                        for a in bpy.context.screen.areas: a.tag_redraw()
                self.report({'INFO'}, message='已关闭吸附')
            else:
                bpy.context.scene.tool_settings.use_snap = True
                bpy.context.scene.tool_settings.snap_elements = {'VERTEX'}
                bpy.context.scene.tool_settings.snap_target = 'CENTER'
                bpy.context.scene.tool_settings.use_snap_selectable = False
                bpy.context.scene.tool_settings.use_snap_align_rotation = False
                bpy.context.scene.tool_settings.use_snap_backface_culling = False
                bpy.context.scene.tool_settings.use_snap_translate = True
                bpy.context.scene.tool_settings.use_snap_rotate = False
                bpy.context.scene.tool_settings.use_snap_scale = False
                handler_6E846.append(bpy.types.SpaceView3D.draw_handler_add(sna_func_7B6DB, (), 'WINDOW', 'POST_PIXEL'))
                for a in bpy.context.screen.areas: a.tag_redraw()
                self.report({'INFO'}, message='已开启吸附')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_7B6DB():
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_0F1DE, y_0F1DE = tuple(mathutils.Vector((-60.0, -120.0)) + mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)))
        blf.position(font_id, x_0F1DE, y_0F1DE, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 20.0)
        else:
            blf.size(font_id, 20.0, 72)
        clr = (1.0, 0.9448611736297607, 0.1964220106601715, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 0:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 0)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, '顶点吸附中')
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_896Aa)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.my_generic_operator_896aa', 'V', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['E2DFC'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_896Aa)
    if handler_6E846:
        bpy.types.SpaceView3D.draw_handler_remove(handler_6E846[0], 'WINDOW')
        handler_6E846.pop(0)
