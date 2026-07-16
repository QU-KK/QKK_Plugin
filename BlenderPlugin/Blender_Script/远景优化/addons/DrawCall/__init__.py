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
    "name" : "DrawCall",
    "author" : "QKK", 
    "description" : "",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews
import blf
import os
import mathutils
from bpy.app.handlers import persistent


addon_keymaps = {}
_icons = None
node_tree = {'sna_mesh_data': [], 'sna_mat_data': [], 'sna_mesh_triangles_max': 0, 'sna_mesh_triangles_min': 0, 'sna_drawcall_switch': False, }


def region_by_type(area, region_type):
    for region in area.regions:
        if region.type == region_type:
            return region
    return area.regions[0]


handler_ACB97 = []


def sna_func_E349E():
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_10322, y_10322 = tuple(mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)) + mathutils.Vector((-100.0, -100.0)))
        blf.position(font_id, x_10322, y_10322, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 30.0)
        else:
            blf.size(font_id, 30.0, 72)
        clr = (0.16674983501434326, 0.9755810499191284, 1.0, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 100:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 100)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, 'DrawCall=' + str(len(list(dict.fromkeys(node_tree['sna_mesh_data'])))))
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_21429, y_21429 = tuple(mathutils.Vector(tuple(mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)) + mathutils.Vector((-100.0, -100.0)))) + mathutils.Vector((0.0, -30.0)))
        blf.position(font_id, x_21429, y_21429, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 20.0)
        else:
            blf.size(font_id, 20.0, 72)
        clr = (1.0, 1.0, 1.0, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 100:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 100)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, '模型数量=' + str(len(bpy.context.view_layer.objects.selected)))
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_206F8, y_206F8 = tuple(mathutils.Vector(tuple(mathutils.Vector(tuple(mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)) + mathutils.Vector((-100.0, -100.0)))) + mathutils.Vector((0.0, -30.0)))) + mathutils.Vector((0.0, -30.0)))
        blf.position(font_id, x_206F8, y_206F8, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 20.0)
        else:
            blf.size(font_id, 20.0, 72)
        clr = (1.0, 1.0, 1.0, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 100:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 100)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, '材质数量=' + str(len(list(dict.fromkeys(node_tree['sna_mat_data'])))))
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_A567A, y_A567A = tuple(mathutils.Vector(tuple(mathutils.Vector(tuple(mathutils.Vector(tuple(mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)) + mathutils.Vector((-100.0, -100.0)))) + mathutils.Vector((0.0, -30.0)))) + mathutils.Vector((0.0, -30.0)))) + mathutils.Vector((0.0, -30.0)))
        blf.position(font_id, x_A567A, y_A567A, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 12.0)
        else:
            blf.size(font_id, 12.0, 72)
        clr = (1.0, 0.21131984889507294, 0.11798842251300812, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 100:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 100)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, '最高面数：' + str(node_tree['sna_mesh_triangles_max']))
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_73096, y_73096 = tuple(mathutils.Vector(tuple(mathutils.Vector(tuple(mathutils.Vector(tuple(mathutils.Vector(tuple(mathutils.Vector((region_by_type(bpy.context.area, 'WINDOW').width/2, region_by_type(bpy.context.area, 'WINDOW').height)) + mathutils.Vector((-100.0, -100.0)))) + mathutils.Vector((0.0, -30.0)))) + mathutils.Vector((0.0, -30.0)))) + mathutils.Vector((0.0, -30.0)))) + mathutils.Vector((0.0, -20.0)))
        blf.position(font_id, x_73096, y_73096, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 12.0)
        else:
            blf.size(font_id, 12.0, 72)
        clr = (0.10173476487398148, 1.0, 0.4229322671890259, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 100:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 100)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, '最低面数：' + str(node_tree['sna_mesh_triangles_min']))
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)


@persistent
def depsgraph_update_post_handler_62373(dummy):
    if node_tree['sna_drawcall_switch']:
        if handler_ACB97:
            bpy.types.SpaceView3D.draw_handler_remove(handler_ACB97[0], 'WINDOW')
            handler_ACB97.pop(0)
            for a in bpy.context.screen.areas: a.tag_redraw()
        node_tree['sna_drawcall_switch'] = False


class SNA_OT_Draw_Call_6Ce86(bpy.types.Operator):
    bl_idname = "sna.draw_call_6ce86"
    bl_label = "Draw_Call"
    bl_description = "计算选中模型的DrawCall"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_0DA00 in range(len(bpy.context.view_layer.objects.selected)):
            node_tree['sna_mesh_data'].append(bpy.context.view_layer.objects.selected[i_0DA00].data.name)
        for i_B9DCE in range(len(bpy.context.view_layer.objects.selected)):
            for i_7872C in range(len(bpy.context.view_layer.objects.selected[i_B9DCE].material_slots)):
                node_tree['sna_mat_data'].append(bpy.context.view_layer.objects.selected[i_B9DCE].material_slots[i_7872C].name)
        for i_32449 in range(len(node_tree['sna_mesh_data'])):
            node_tree['sna_mesh_triangles_max'] = int(node_tree['sna_mesh_triangles_max'] + len(bpy.context.blend_data.meshes[node_tree['sna_mesh_data'][i_32449]].loop_triangles))
        for i_7354E in range(len(list(dict.fromkeys(node_tree['sna_mesh_data'])))):
            node_tree['sna_mesh_triangles_min'] = int(node_tree['sna_mesh_triangles_min'] + len(bpy.context.blend_data.meshes[list(dict.fromkeys(node_tree['sna_mesh_data']))[i_7354E]].loop_triangles))
        if handler_ACB97:
            bpy.types.SpaceView3D.draw_handler_remove(handler_ACB97[0], 'WINDOW')
            handler_ACB97.pop(0)
            for a in bpy.context.screen.areas: a.tag_redraw()
        handler_ACB97.append(bpy.types.SpaceView3D.draw_handler_add(sna_func_E349E, (), 'WINDOW', 'POST_PIXEL'))
        for a in bpy.context.screen.areas: a.tag_redraw()
        node_tree['sna_drawcall_switch'] = True
        return {"FINISHED"}

    def invoke(self, context, event):
        node_tree['sna_mesh_data'] = []
        node_tree['sna_mat_data'] = []
        node_tree['sna_mesh_triangles_max'] = 0
        node_tree['sna_mesh_triangles_min'] = 0
        return self.execute(context)


class SNA_PT_DRAWCALL_D8F09(bpy.types.Panel):
    bl_label = 'DrawCall'
    bl_idname = 'SNA_PT_DRAWCALL_D8F09'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '远景工具'
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_7C298 = layout.column(heading='', align=False)
        col_7C298.alert = False
        col_7C298.enabled = True
        col_7C298.active = True
        col_7C298.use_property_split = False
        col_7C298.use_property_decorate = False
        col_7C298.scale_x = 1.0
        col_7C298.scale_y = 1.5
        col_7C298.alignment = 'Expand'.upper()
        col_7C298.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_7C298.operator('sna.draw_call_6ce86', text='DrawCall', icon_value=0, emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post_handler_62373)
    bpy.utils.register_class(SNA_OT_Draw_Call_6Ce86)
    bpy.utils.register_class(SNA_PT_DRAWCALL_D8F09)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post_handler_62373)
    bpy.utils.unregister_class(SNA_OT_Draw_Call_6Ce86)
    if handler_ACB97:
        bpy.types.SpaceView3D.draw_handler_remove(handler_ACB97[0], 'WINDOW')
        handler_ACB97.pop(0)
    bpy.utils.unregister_class(SNA_PT_DRAWCALL_D8F09)
