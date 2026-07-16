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
    "name" : "MessiahLight",
    "author" : "QKK", 
    "description" : "Messia日光角度对齐",
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
import gpu
import gpu_extras
import math


addon_keymaps = {}
_icons = None
handler_15076 = []


def sna_update_sna_time_9CF90(self, context):
    sna_updated_prop = self.sna_time
    sna_func_38A9A()


def sna_update_sna_longitude_F6375(self, context):
    sna_updated_prop = self.sna_longitude
    sna_func_38A9A()


class SNA_PT_messiahlight_50701(bpy.types.Panel):
    bl_label = '弥赛亚日光'
    bl_idname = 'SNA_PT_messiahlight_50701'
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
        layout.prop(bpy.context.scene, 'sna_sun', text='日光', icon_value=0, emboss=True)
        col_CA452 = layout.column(heading='', align=True)
        col_CA452.alert = False
        col_CA452.enabled = True
        col_CA452.active = True
        col_CA452.use_property_split = False
        col_CA452.use_property_decorate = False
        col_CA452.scale_x = 1.0
        col_CA452.scale_y = 1.2000000476837158
        col_CA452.alignment = 'Expand'.upper()
        col_CA452.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_CA452.prop(bpy.context.scene, 'sna_time', text='时间  (太阳高度)', icon_value=0, emboss=True, slider=True)
        col_CA452.prop(bpy.context.scene, 'sna_longitude', text='经度  (太阳旋转)', icon_value=0, emboss=True, slider=True)


def sna_func_38A9A():
    bpy.context.scene.sna_sun.rotation_euler = (0.0, float(math.radians(float((eval("bpy.context.scene.sna_time * -15.0 + 180.0") if ((bpy.context.scene.sna_time >= 6.0) and (bpy.context.scene.sna_time <= 18.0)) else (eval("bpy.context.scene.sna_time * -15.0 + 360.0") if ((bpy.context.scene.sna_time >= 18.0) and (bpy.context.scene.sna_time <= 24.0)) else eval("bpy.context.scene.sna_time * -15.0 "))) * -1.0)) * -1.0), float(math.radians(bpy.context.scene.sna_longitude) * -1.0))


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_time = bpy.props.FloatProperty(name='time', description='', default=12.0, subtype='NONE', unit='NONE', min=0.0, max=24.0, step=1, precision=2, update=sna_update_sna_time_9CF90)
    bpy.types.Scene.sna_longitude = bpy.props.FloatProperty(name='longitude', description='', default=0.0, subtype='NONE', unit='NONE', min=0.0, max=360.0, step=1, precision=2, update=sna_update_sna_longitude_F6375)
    bpy.types.Scene.sna_sun = bpy.props.PointerProperty(name='sun', description='', type=bpy.types.Object)
    bpy.utils.register_class(SNA_PT_messiahlight_50701)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_sun
    del bpy.types.Scene.sna_longitude
    del bpy.types.Scene.sna_time
    bpy.utils.unregister_class(SNA_PT_messiahlight_50701)
    if handler_15076:
        bpy.types.SpaceView3D.draw_handler_remove(handler_15076[0], 'WINDOW')
        handler_15076.pop(0)
