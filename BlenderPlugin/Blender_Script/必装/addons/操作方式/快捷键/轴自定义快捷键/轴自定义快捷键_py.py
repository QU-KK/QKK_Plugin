import bpy
import bpy.utils.previews
import blf
import os
import mathutils


addon_keymaps = {}
_icons = None
node_tree_006 = {'sna_transparency': 1.0, }
handler_D2DC0 = []
count_AFCB7 = 0
handler_71B9F = []


def region_by_type(area, region_type):
    for region in area.regions:
        if region.type == region_type:
            return region
    return area.regions[0]


class SNA_OT_My_Generic_Operator_95174(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_95174"
    bl_label = "(Qkk_3DMode)D自定义轴"
    bl_description = "(Qkk_3DMode)D自定义轴"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        if 'OBJECT'==bpy.context.mode:
            if bpy.context.scene.tool_settings.use_transform_data_origin:
                bpy.context.scene.tool_settings.use_transform_data_origin = False
                for i_EA82C in range(2):
                    if handler_D2DC0:
                        bpy.types.SpaceView3D.draw_handler_remove(handler_D2DC0[0], 'WINDOW')
                        handler_D2DC0.pop(0)
                        for a in bpy.context.screen.areas: a.tag_redraw()
                self.report({'INFO'}, message='已关闭轴心自定义')
            else:
                bpy.context.scene.tool_settings.use_transform_data_origin = True
                handler_D2DC0.append(bpy.types.SpaceView3D.draw_handler_add(sna_function_execute_CA24A, (), 'WINDOW', 'POST_PIXEL'))
                for a in bpy.context.screen.areas: a.tag_redraw()
                self.report({'INFO'}, message='已开启轴心自定义')
        else:
            if 'EDIT_MESH'==bpy.context.mode:
                bpy.ops.transform.create_orientation(name='临时坐标系', use=True, overwrite=True)
                sna_func_75892('设置临时坐标', (70.0, 80.0))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_B4F86(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b4f86"
    bl_label = "(Qkk_3DMode)DD临时坐标"
    bl_description = "(Qkk_3DMode)DD临时坐标"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if (bpy.context.scene.transform_orientation_slots[0].type == '临时坐标系'):
            bpy.ops.transform.delete_orientation()
            sna_func_75892('清除临时坐标', (70.0, 50.0))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_8FB66(transparent, content, position):
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_A4333, y_A4333 = position
        blf.position(font_id, x_A4333, y_A4333, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 20.0)
        else:
            blf.size(font_id, 20.0, 72)
        clr = (1.0, 1.0, 1.0, transparent)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 0:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 0)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, content)
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)


def sna_func_75892(content, position):
    node_tree_006['sna_transparency'] = 1.0
    global count_AFCB7
    count_AFCB7 = 0

    def delayed_AFCB7():
        global count_AFCB7
        node_tree_006['sna_transparency'] = float(node_tree_006['sna_transparency'] - 0.05000000074505806)
        handler_71B9F.append(bpy.types.SpaceView3D.draw_handler_add(sna_func_8FB66, (node_tree_006['sna_transparency'], content, position, ), 'WINDOW', 'POST_PIXEL'))
        for a in bpy.context.screen.areas: a.tag_redraw()

        def delayed_F2114():
            if handler_71B9F:
                bpy.types.SpaceView3D.draw_handler_remove(handler_71B9F[0], 'WINDOW')
                handler_71B9F.pop(0)
                for a in bpy.context.screen.areas: a.tag_redraw()
        bpy.app.timers.register(delayed_F2114, first_interval=1.0)
        count_AFCB7 += 1
        if count_AFCB7 >= 20:
            return None
        return 0.10000000149011612
    bpy.app.timers.register(delayed_AFCB7, first_interval=0.0)


def sna_function_execute_CA24A():
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_3758F, y_3758F = tuple(mathutils.Vector((-60.0, -90.0)) + mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)))
        blf.position(font_id, x_3758F, y_3758F, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 20.0)
        else:
            blf.size(font_id, 20.0, 72)
        clr = (0.408194899559021, 0.825076699256897, 1.0, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 0:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 0)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, '自定义轴心')
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_95174)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B4F86)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.my_generic_operator_95174', 'D', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['5642F'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.my_generic_operator_b4f86', 'D', 'DOUBLE_CLICK',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['7FA5D'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_95174)
    if handler_D2DC0:
        bpy.types.SpaceView3D.draw_handler_remove(handler_D2DC0[0], 'WINDOW')
        handler_D2DC0.pop(0)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B4F86)
    if handler_71B9F:
        bpy.types.SpaceView3D.draw_handler_remove(handler_71B9F[0], 'WINDOW')
        handler_71B9F.pop(0)
