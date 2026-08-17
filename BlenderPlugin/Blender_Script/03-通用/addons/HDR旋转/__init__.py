# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "HDR_Rotate",
    "author" : "qkk", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "HDR" 
}


import bpy
import bpy.utils.previews
import math


addon_keymaps = {}
_icons = None
hdr = {'sna_mouse_region': 0.0, 'sna_rotate': 0.0, }
_47C6D_running = False
_47C6D_handle = None
class SNA_OT_Moda_Hdr_Rotate_47C6D(bpy.types.Operator):
    bl_idname = "sna.moda_hdr_rotate_47c6d"
    bl_label = "Moda_HDR_Rotate"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    cursor = "SCROLL_X"
    _handle = None
    _event = {}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        if not False or context.area.spaces[0].bl_rna.identifier == 'SpaceNodeEditor':
            return not False
        return False

    def save_event(self, event):
        event_options = ["type", "value", "alt", "shift", "ctrl", "oskey", "mouse_region_x", "mouse_region_y", "mouse_x", "mouse_y", "pressure", "tilt"]
        if bpy.app.version >= (3, 2, 1):
            event_options += ["type_prev", "value_prev"]
        for option in event_options: self._event[option] = getattr(event, option)

    def draw_callback_px(self, context):
        try:
            _ = self.bl_idname
        except ReferenceError:
            return
        event = self._event
        if event.keys():
            event = dotdict(event)
            try:
                pass
            except Exception as error:
                print(error)

    def execute(self, context):
        global _47C6D_running
        global _47C6D_handle
        _47C6D_running = False
        _47C6D_handle = None
        context.window.cursor_set("DEFAULT")
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}

    def modal(self, context, event):
        global _47C6D_running
        if not context.area or not _47C6D_running:
            self.execute(context)
            return {'CANCELLED'}
        self.save_event(event)
        context.window.cursor_set('SCROLL_X')
        try:
            rotate = float(hdr['sna_rotate'] + math.radians(float(float((event.mouse_region_x, event.mouse_region_y)[0] - hdr['sna_mouse_region']) * 0.5)))
            bpy.data.screens['Layout'].areas[2].spaces[0].shading.studiolight_rotate_z = rotate
        except Exception as error:
            print(error)
        if event.type in ['RIGHTMOUSE', 'ESC']:
            self.execute(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global _47C6D_running
        if _47C6D_running:
            _47C6D_running = False
            return {'FINISHED'}
        else:
            self.save_event(event)
            self.start_pos = (event.mouse_x, event.mouse_y)
            hdr['sna_mouse_region'] = (event.mouse_region_x, event.mouse_region_y)[0]
            rotate = None
            rotate = bpy.data.screens['Layout'].areas[2].spaces[0].shading.studiolight_rotate_z
            hdr['sna_rotate'] = rotate
            context.window_manager.modal_handler_add(self)
            global _47C6D_handle
            _47C6D_handle = self._handle
            _47C6D_running = True
            return {'RUNNING_MODAL'}


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_Moda_Hdr_Rotate_47C6D)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.moda_hdr_rotate_47c6d', 'RIGHTMOUSE', 'PRESS',
        ctrl=True, alt=False, shift=True, repeat=False)
    addon_keymaps['6C049'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    global _47C6D_running
    _47C6D_running = False
    global _47C6D_handle
    if _47C6D_handle:
        try:
            bpy.types.SpaceNodeEditor.draw_handler_remove(_47C6D_handle, 'WINDOW')
        except:
            pass
        _47C6D_handle = None
    bpy.utils.unregister_class(SNA_OT_Moda_Hdr_Rotate_47C6D)
