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
    "name" : "qkk_hard_edge_extrusion",
    "author" : "qkk", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "饼菜单扩展" 
}


import bpy
import bpy.utils.previews


addon_keymaps = {}
_icons = None
visual_scripting_editor = {'sna_xyz': None, }
_DBEF6_running = False
_DBEF6_handle = None
class SNA_OT_Qkk_Hard_Edge_Extrusion_Dbef6(bpy.types.Operator):
    bl_idname = "sna.qkk_hard_edge_extrusion_dbef6"
    bl_label = "qkk_hard_edge_extrusion"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    cursor = "SCROLL_XY"
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
        global _DBEF6_running
        global _DBEF6_handle
        _DBEF6_running = False
        _DBEF6_handle = None
        context.window.cursor_set("DEFAULT")
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}

    def modal(self, context, event):
        global _DBEF6_running
        if not context.area or not _DBEF6_running:
            self.execute(context)
            return {'CANCELLED'}
        self.save_event(event)
        context.window.cursor_set('SCROLL_XY')
        try:
            bpy.ops.mesh.select_more(use_face_step=True)
            bpy.ops.mesh.set_sharpness_by_angle(angle=0.5, extend=False)
            bpy.ops.mesh.select_less(use_face_step=True)
            if ((event.mouse_region_x, event.mouse_region_y) != visual_scripting_editor['sna_xyz']):

                def delayed_58C31():
                    if event.type in ['RIGHTMOUSE', 'ESC']:
                        self.execute(context)
                        return {'CANCELLED'}
                    self.execute(context)
                    return {"FINISHED"}
                bpy.app.timers.register(delayed_58C31, first_interval=0.05000000074505806)
        except Exception as error:
            print(error)
        if event.type in ['RIGHTMOUSE', 'ESC']:
            self.execute(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global _DBEF6_running
        if _DBEF6_running:
            _DBEF6_running = False
            return {'FINISHED'}
        else:
            self.save_event(event)
            self.start_pos = (event.mouse_x, event.mouse_y)
            bpy.ops.view3d.edit_mesh_extrude_move_normal('INVOKE_DEFAULT', )
            visual_scripting_editor['sna_xyz'] = (event.mouse_region_x, event.mouse_region_y)
            context.window_manager.modal_handler_add(self)
            global _DBEF6_handle
            _DBEF6_handle = self._handle
            _DBEF6_running = True
            return {'RUNNING_MODAL'}


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_Qkk_Hard_Edge_Extrusion_Dbef6)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    global _DBEF6_running
    _DBEF6_running = False
    global _DBEF6_handle
    if _DBEF6_handle:
        try:
            bpy.types.SpaceNodeEditor.draw_handler_remove(_DBEF6_handle, 'WINDOW')
        except:
            pass
        _DBEF6_handle = None
    bpy.utils.unregister_class(SNA_OT_Qkk_Hard_Edge_Extrusion_Dbef6)
