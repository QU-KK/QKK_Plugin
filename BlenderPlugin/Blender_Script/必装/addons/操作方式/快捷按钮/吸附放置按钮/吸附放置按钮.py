import bpy
import bpy.utils.previews
import blf
import os
import mathutils




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
class dotdict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def region_by_type(area, region_type):
    for region in area.regions:
        if region.type == region_type:
            return region
    return area.regions[0]


_DFE71_running = False
class SNA_OT_Place_Dfe71(bpy.types.Operator):
    bl_idname = "sna.place_dfe71"
    bl_label = "Place"
    bl_description = "吸附放置，至少选中一个模型"
    bl_options = {"REGISTER", "UNDO"}
    cursor = "PAINT_CROSS"
    _handle = None
    _event = {}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        if not True or context.area.spaces[0].bl_rna.identifier == 'SpaceView3D':
            return not False
        return False

    def save_event(self, event):
        event_options = ["type", "value", "alt", "shift", "ctrl", "oskey", "mouse_region_x", "mouse_region_y", "mouse_x", "mouse_y", "pressure", "tilt"]
        if bpy.app.version >= (3, 2, 1):
            event_options += ["type_prev", "value_prev"]
        for option in event_options: self._event[option] = getattr(event, option)

    def draw_callback_px(self, context):
        event = self._event
        if event.keys():
            event = dotdict(event)
            try:
                font_id = 0
                if r'' and os.path.exists(r''):
                    font_id = blf.load(r'')
                if font_id == -1:
                    print("Couldn't load font!")
                else:
                    x_1BB43, y_1BB43 = tuple(mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)) + mathutils.Vector((-100.0, -80.0)))
                    blf.position(font_id, x_1BB43, y_1BB43, 0)
                    if bpy.app.version >= (3, 4, 0):
                        blf.size(font_id, 20.0)
                    else:
                        blf.size(font_id, 20.0, 72)
                    clr = (1.0, 0.9537574648857117, 0.06075764447450638, 1.0)
                    blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
                    if 0:
                        blf.enable(font_id, blf.WORD_WRAP)
                        blf.word_wrap(font_id, 0)
                    if 0.0:
                        blf.enable(font_id, blf.ROTATION)
                        blf.rotation(font_id, 0.0)
                    blf.enable(font_id, blf.WORD_WRAP)
                    blf.draw(font_id, '点击放置')
                    blf.disable(font_id, blf.ROTATION)
                    blf.disable(font_id, blf.WORD_WRAP)
            except Exception as error:
                print(error)

    def execute(self, context):
        global _DFE71_running
        _DFE71_running = False
        context.window.cursor_set("DEFAULT")
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        bpy.ops.view3d.cursor3d('INVOKE_DEFAULT', use_depth=True, orientation='GEOM')
        bpy.ops.view3d.snap_selected_to_cursor(use_offset=False)
        bpy.ops.transform.transform(mode='ALIGN', orient_type='CURSOR')
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}

    def modal(self, context, event):
        global _DFE71_running
        if not context.area or not _DFE71_running:
            self.execute(context)
            return {'CANCELLED'}
        self.save_event(event)
        context.area.tag_redraw()
        context.window.cursor_set('PAINT_CROSS')
        try:
            if (event.type == 'LEFTMOUSE' and event.value == 'PRESS' and event.alt == False and event.shift == False and event.ctrl == False):
                bpy.context.scene.sna_controls_place = False
                if event.type in ['RIGHTMOUSE', 'ESC']:
                    self.execute(context)
                    return {'CANCELLED'}
                self.execute(context)
                return {"FINISHED"}
        except Exception as error:
            print(error)
        if event.type in ['RIGHTMOUSE', 'ESC']:
            self.execute(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global _DFE71_running
        if _DFE71_running:
            _DFE71_running = False
            return {'FINISHED'}
        else:
            self.save_event(event)
            self.start_pos = (event.mouse_x, event.mouse_y)
            bpy.context.scene.sna_controls_place = True
            args = (context,)
            self._handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            _DFE71_running = True
            return {'RUNNING_MODAL'}


def sna_add_to_view3d_pt_tools_active_395BC(self, context):
    if not (False):
        layout = self.layout
        box_06D00 = layout.box()
        box_06D00.alert = False
        box_06D00.enabled = ('OBJECT'==bpy.context.mode and (len(bpy.context.view_layer.objects.selected) > 0))
        box_06D00.active = True
        box_06D00.use_property_split = False
        box_06D00.use_property_decorate = False
        box_06D00.alignment = 'Expand'.upper()
        box_06D00.scale_x = 1.0
        box_06D00.scale_y = 1.0
        if not True: box_06D00.operator_context = "EXEC_DEFAULT"
        op = box_06D00.operator('sna.place_dfe71', text='', icon_value=string_to_icon('STYLUS_PRESSURE'), emboss=bpy.context.scene.sna_controls_place, depress=bpy.context.scene.sna_controls_place)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_controls_place = bpy.props.BoolProperty(name='controls_place', description='', default=False)
    bpy.utils.register_class(SNA_OT_Place_Dfe71)
    bpy.types.VIEW3D_PT_tools_active.prepend(sna_add_to_view3d_pt_tools_active_395BC)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_controls_place
    bpy.utils.unregister_class(SNA_OT_Place_Dfe71)
    bpy.types.VIEW3D_PT_tools_active.remove(sna_add_to_view3d_pt_tools_active_395BC)
