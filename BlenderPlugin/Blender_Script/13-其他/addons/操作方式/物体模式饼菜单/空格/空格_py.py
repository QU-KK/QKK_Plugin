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
    "name" : "Operation_v3",
    "author" : "渠奎奎", 
    "description" : "操作方式4.2",
    "blender" : (4, 2, 0),
    "version" : (3, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


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
class SNA_MT_68C0B(bpy.types.Menu):
    bl_idname = "SNA_MT_68C0B"
    bl_label = "(Qkk_3DMode)Obj空格"

    @classmethod
    def poll(cls, context):
        return not ((not 'OBJECT'==bpy.context.mode))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('view3d.camera_to_view', text='相机对齐视口', icon_value=string_to_icon('RESTRICT_VIEW_ON'), emboss=True, depress=False)
        op = layout.operator('screen.screen_full_area', text='专家模式', icon_value=string_to_icon('FULLSCREEN_ENTER'), emboss=True, depress=False)
        box_A0C1B = layout.box()
        box_A0C1B.alert = False
        box_A0C1B.enabled = True
        box_A0C1B.active = True
        box_A0C1B.use_property_split = False
        box_A0C1B.use_property_decorate = False
        box_A0C1B.alignment = 'Expand'.upper()
        box_A0C1B.scale_x = 1.0
        box_A0C1B.scale_y = 1.0
        if not True: box_A0C1B.operator_context = "EXEC_DEFAULT"
        split_D4C26 = box_A0C1B.split(factor=0.5, align=True)
        split_D4C26.alert = False
        split_D4C26.enabled = True
        split_D4C26.active = True
        split_D4C26.use_property_split = False
        split_D4C26.use_property_decorate = False
        split_D4C26.scale_x = 1.2999999523162842
        split_D4C26.scale_y = 1.5
        split_D4C26.alignment = 'Expand'.upper()
        if not True: split_D4C26.operator_context = "EXEC_DEFAULT"
        op = split_D4C26.operator('object.camera_add', text='', icon_value=string_to_icon('CAMERA_DATA'), emboss=True, depress=False)
        op = split_D4C26.operator('object.light_add', text='', icon_value=string_to_icon('LIGHT'), emboss=True, depress=False)
        op.location = (0.0, 0.0, 0.0)
        row_C244D = box_A0C1B.row(heading='', align=True)
        row_C244D.alert = False
        row_C244D.enabled = True
        row_C244D.active = True
        row_C244D.use_property_split = False
        row_C244D.use_property_decorate = False
        row_C244D.scale_x = 1.2999999523162842
        row_C244D.scale_y = 1.5
        row_C244D.alignment = 'Expand'.upper()
        row_C244D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_C244D.operator('mesh.primitive_monkey_add', text='', icon_value=string_to_icon('MESH_MONKEY'), emboss=True, depress=False)
        op.location = (0.0, 0.0, 1.0)
        op = row_C244D.operator('mesh.primitive_cube_add', text='', icon_value=string_to_icon('MESH_CUBE'), emboss=True, depress=False)
        op.location = (0.0, 0.0, 1.0)
        op = row_C244D.operator('mesh.primitive_plane_add', text='', icon_value=string_to_icon('MESH_PLANE'), emboss=True, depress=False)
        op.location = (0.0, 0.0, 0.0)
        op = row_C244D.operator('mesh.primitive_uv_sphere_add', text='', icon_value=string_to_icon('MESH_UVSPHERE'), emboss=True, depress=False)
        op.location = (0.0, 0.0, 1.0)
        op = row_C244D.operator('mesh.primitive_cylinder_add', text='', icon_value=string_to_icon('MESH_CYLINDER'), emboss=True, depress=False)
        op.location = (0.0, 0.0, 1.0)
        op = row_C244D.operator('sna.create_curve_execute_94a2d', text='', icon_value=string_to_icon('FORCE_CURVE'), emboss=True, depress=False)
        box_FF02B = box_A0C1B.box()
        box_FF02B.alert = False
        box_FF02B.enabled = True
        box_FF02B.active = True
        box_FF02B.use_property_split = False
        box_FF02B.use_property_decorate = False
        box_FF02B.alignment = 'Expand'.upper()
        box_FF02B.scale_x = 1.0
        box_FF02B.scale_y = 1.0
        if not True: box_FF02B.operator_context = "EXEC_DEFAULT"
        split_01AD8 = box_FF02B.split(factor=0.5, align=True)
        split_01AD8.alert = False
        split_01AD8.enabled = True
        split_01AD8.active = True
        split_01AD8.use_property_split = False
        split_01AD8.use_property_decorate = False
        split_01AD8.scale_x = 0.5
        split_01AD8.scale_y = 1.0
        split_01AD8.alignment = 'Expand'.upper()
        if not True: split_01AD8.operator_context = "EXEC_DEFAULT"
        col_4E359 = split_01AD8.column(heading='', align=True)
        col_4E359.alert = False
        col_4E359.enabled = True
        col_4E359.active = True
        col_4E359.use_property_split = False
        col_4E359.use_property_decorate = False
        col_4E359.scale_x = 1.0
        col_4E359.scale_y = 1.0
        col_4E359.alignment = 'Expand'.upper()
        col_4E359.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_4E359.label(text='导入', icon_value=string_to_icon('IMPORT'))
        row_EB648 = col_4E359.row(heading='', align=True)
        row_EB648.alert = False
        row_EB648.enabled = True
        row_EB648.active = True
        row_EB648.use_property_split = False
        row_EB648.use_property_decorate = False
        row_EB648.scale_x = 1.0
        row_EB648.scale_y = 1.5
        row_EB648.alignment = 'Expand'.upper()
        row_EB648.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_EB648.operator('image.open', text=' ', icon_value=string_to_icon('OUTLINER_OB_IMAGE'), emboss=True, depress=False)
        op = row_EB648.operator('import_scene.fbx', text=' ', icon_value=string_to_icon('EVENT_F'), emboss=True, depress=False)
        op = row_EB648.operator('wm.obj_import', text=' ', icon_value=string_to_icon('EVENT_O'), emboss=True, depress=False)
        col_4F6DF = split_01AD8.column(heading='', align=True)
        col_4F6DF.alert = False
        col_4F6DF.enabled = True
        col_4F6DF.active = True
        col_4F6DF.use_property_split = False
        col_4F6DF.use_property_decorate = False
        col_4F6DF.scale_x = 1.0
        col_4F6DF.scale_y = 1.0
        col_4F6DF.alignment = 'Expand'.upper()
        col_4F6DF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_4F6DF.label(text='导出', icon_value=string_to_icon('EXPORT'))
        row_97DD1 = col_4F6DF.row(heading='', align=True)
        row_97DD1.alert = False
        row_97DD1.enabled = True
        row_97DD1.active = True
        row_97DD1.use_property_split = False
        row_97DD1.use_property_decorate = False
        row_97DD1.scale_x = 1.0
        row_97DD1.scale_y = 1.5
        row_97DD1.alignment = 'Expand'.upper()
        row_97DD1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_97DD1.operator('export_scene.fbx', text=' ', icon_value=string_to_icon('EVENT_F'), emboss=True, depress=False)
        op.use_selection = True
        op.object_types = {'MESH'}
        op.bake_anim = False
        op = row_97DD1.operator('wm.obj_export', text=' ', icon_value=string_to_icon('EVENT_O'), emboss=True, depress=False)
        op.export_animation = False
        op.export_selected_objects = True
        op.export_materials = False
        op = row_97DD1.operator('wm.alembic_export', text=' ', icon_value=string_to_icon('EVENT_A'), emboss=True, depress=False)
        op.selected = True
        op = layout.operator('object.move_to_collection', text='归整集合', icon_value=string_to_icon('GROUP'), emboss=True, depress=False)
        layout.prop(bpy.context.area.spaces[0], 'lock_camera', text='锁定摄像机', icon_value=string_to_icon('CAMERA_DATA'), emboss=True)
        op = layout.operator('render.render', text='渲染图像', icon_value=string_to_icon('IMAGE_RGB_ALPHA'), emboss=True, depress=False)


class SNA_OT_Create_Curve_Execute_94A2D(bpy.types.Operator):
    bl_idname = "sna.create_curve_execute_94a2d"
    bl_label = "Create_Curve_Execute"
    bl_description = "创建曲线"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.curve.primitive_nurbs_path_add(enter_editmode=True)
        bpy.ops.curve.delete(type='VERT')
        bpy.ops.wm.tool_set_by_id(name='builtin.draw')
        bpy.context.scene.tool_settings.curve_paint_settings.depth_mode = 'SURFACE'
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_MT_68C0B)
    bpy.utils.register_class(SNA_OT_Create_Curve_Execute_94A2D)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'SPACE', 'ANY',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_MT_68C0B'
    addon_keymaps['0C4B5'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_MT_68C0B)
    bpy.utils.unregister_class(SNA_OT_Create_Curve_Execute_94A2D)
