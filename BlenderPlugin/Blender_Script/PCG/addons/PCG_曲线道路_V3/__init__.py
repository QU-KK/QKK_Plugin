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
    "name" : "PCG_Curved Road_v3",
    "author" : "渠奎奎", 
    "description" : "曲线道路v3_8.2日",
    "blender" : (4, 2, 0),
    "version" : (2, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "PCG_工具" 
}


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
node_tree_001 = {'sna_obj_name': '', }
node_tree_001 = {'sna_pcg_modname': '', }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_PT_PCG__82_04C21(bpy.types.Panel):
    bl_label = 'PCG_曲线道路_8.2日'
    bl_idname = 'SNA_PT_PCG__82_04C21'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'PCG'
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
        layout_function = layout
        sna_add_3B2E4(layout_function, )
        if (bpy.context.view_layer.objects.active != None):
            col_4B7E7 = layout.column(heading='', align=True)
            col_4B7E7.alert = False
            col_4B7E7.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_4B7E7.active = True
            col_4B7E7.use_property_split = False
            col_4B7E7.use_property_decorate = False
            col_4B7E7.scale_x = 1.0
            col_4B7E7.scale_y = 1.0
            col_4B7E7.alignment = 'Expand'.upper()
            col_4B7E7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_4B7E7.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_道路节点_v2'].node_group.name", globals(), locals()):
                col_E230A = col_4B7E7.column(heading='', align=True)
                col_E230A.alert = False
                col_E230A.enabled = True
                col_E230A.active = True
                col_E230A.use_property_split = False
                col_E230A.use_property_decorate = False
                col_E230A.scale_x = 1.0
                col_E230A.scale_y = 1.0
                col_E230A.alignment = 'Expand'.upper()
                col_E230A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                box_F00E7 = col_E230A.box()
                box_F00E7.alert = False
                box_F00E7.enabled = True
                box_F00E7.active = True
                box_F00E7.use_property_split = False
                box_F00E7.use_property_decorate = False
                box_F00E7.alignment = 'Expand'.upper()
                box_F00E7.scale_x = 1.0
                box_F00E7.scale_y = 1.0
                if not True: box_F00E7.operator_context = "EXEC_DEFAULT"
                split_7BFE0 = box_F00E7.split(factor=0.20000000298023224, align=True)
                split_7BFE0.alert = False
                split_7BFE0.enabled = True
                split_7BFE0.active = True
                split_7BFE0.use_property_split = False
                split_7BFE0.use_property_decorate = False
                split_7BFE0.scale_x = 1.0
                split_7BFE0.scale_y = 1.0
                split_7BFE0.alignment = 'Expand'.upper()
                if not True: split_7BFE0.operator_context = "EXEC_DEFAULT"
                col_D66F0 = split_7BFE0.column(heading='', align=True)
                col_D66F0.alert = False
                col_D66F0.enabled = True
                col_D66F0.active = True
                col_D66F0.use_property_split = False
                col_D66F0.use_property_decorate = False
                col_D66F0.scale_x = 1.0
                col_D66F0.scale_y = 2.0
                col_D66F0.alignment = 'Expand'.upper()
                col_D66F0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                if 'OBJECT'==bpy.context.mode:
                    op = col_D66F0.operator('object.mode_set', text='编辑', icon_value=0, emboss=True, depress=False)
                    op.mode = 'EDIT'
                    op.toggle = False
                if 'EDIT_CURVE'==bpy.context.mode:
                    op = col_D66F0.operator('object.mode_set', text='退出', icon_value=0, emboss=True, depress=True)
                    op.mode = 'OBJECT'
                    op.toggle = False
                col_34424 = col_D66F0.column(heading='', align=True)
                col_34424.alert = False
                col_34424.enabled = 'OBJECT'==bpy.context.mode
                col_34424.active = True
                col_34424.use_property_split = False
                col_34424.use_property_decorate = False
                col_34424.scale_x = 1.0
                col_34424.scale_y = 1.0
                col_34424.alignment = 'Expand'.upper()
                col_34424.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_34424.operator('sna.my_generic_operator_e343b', text='应用', icon_value=0, emboss=True, depress=False)
                col_9BA8A = split_7BFE0.column(heading='', align=True)
                col_9BA8A.alert = False
                col_9BA8A.enabled = 'EDIT_CURVE'==bpy.context.mode
                col_9BA8A.active = True
                col_9BA8A.use_property_split = False
                col_9BA8A.use_property_decorate = False
                col_9BA8A.scale_x = 1.0
                col_9BA8A.scale_y = 1.0
                col_9BA8A.alignment = 'Expand'.upper()
                col_9BA8A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_48139 = col_9BA8A.split(factor=0.5, align=True)
                split_48139.alert = False
                split_48139.enabled = True
                split_48139.active = True
                split_48139.use_property_split = False
                split_48139.use_property_decorate = False
                split_48139.scale_x = 1.0
                split_48139.scale_y = 1.0
                split_48139.alignment = 'Expand'.upper()
                if not True: split_48139.operator_context = "EXEC_DEFAULT"
                op = split_48139.operator('wm.tool_set_by_id', text='框选', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)
                op.name = 'builtin.select_box'
                op = split_48139.operator('wm.tool_set_by_id', text='移动', icon_value=string_to_icon('ORIENTATION_GLOBAL'), emboss=True, depress=False)
                op.name = 'builtin.move'
                split_59452 = col_9BA8A.split(factor=0.5, align=True)
                split_59452.alert = False
                split_59452.enabled = True
                split_59452.active = True
                split_59452.use_property_split = False
                split_59452.use_property_decorate = False
                split_59452.scale_x = 1.0
                split_59452.scale_y = 1.0
                split_59452.alignment = 'Expand'.upper()
                if not True: split_59452.operator_context = "EXEC_DEFAULT"
                op = split_59452.operator('wm.tool_set_by_id', text='旋转', icon_value=string_to_icon('ORIENTATION_GIMBAL'), emboss=True, depress=False)
                op.name = 'builtin.rotate'
                op = split_59452.operator('wm.tool_set_by_id', text='绘制', icon_value=string_to_icon('GREASEPENCIL'), emboss=True, depress=False)
                op.name = 'builtin.draw'
                split_C0B83 = col_9BA8A.split(factor=0.5, align=True)
                split_C0B83.alert = False
                split_C0B83.enabled = True
                split_C0B83.active = True
                split_C0B83.use_property_split = False
                split_C0B83.use_property_decorate = False
                split_C0B83.scale_x = 1.0
                split_C0B83.scale_y = 1.0
                split_C0B83.alignment = 'Expand'.upper()
                if not True: split_C0B83.operator_context = "EXEC_DEFAULT"
                op = split_C0B83.operator('curve.subdivide', text='细分', icon_value=0, emboss=True, depress=False)
                op.number_cuts = 0
                op = split_C0B83.operator('curve.delete', text='删点', icon_value=0, emboss=True, depress=False)
                op.type = 'VERT'
                split_61E7C = col_9BA8A.split(factor=0.5, align=True)
                split_61E7C.alert = False
                split_61E7C.enabled = True
                split_61E7C.active = True
                split_61E7C.use_property_split = False
                split_61E7C.use_property_decorate = False
                split_61E7C.scale_x = 1.0
                split_61E7C.scale_y = 1.0
                split_61E7C.alignment = 'Expand'.upper()
                if not True: split_61E7C.operator_context = "EXEC_DEFAULT"
                op = split_61E7C.operator('curve.handle_type_set', text='平滑', icon_value=0, emboss=True, depress=False)
                op.type = 'AUTOMATIC'
                op = split_61E7C.operator('wm.tool_set_by_id', text='挤出', icon_value=0, emboss=True, depress=False)
                op.name = 'builtin.extrude_cursor'
                box_07801 = col_E230A.box()
                box_07801.alert = False
                box_07801.enabled = True
                box_07801.active = True
                box_07801.use_property_split = False
                box_07801.use_property_decorate = False
                box_07801.alignment = 'Expand'.upper()
                box_07801.scale_x = 1.0
                box_07801.scale_y = 1.0
                if not True: box_07801.operator_context = "EXEC_DEFAULT"
                col_B2F75 = box_07801.column(heading='', align=False)
                col_B2F75.alert = False
                col_B2F75.enabled = True
                col_B2F75.active = True
                col_B2F75.use_property_split = False
                col_B2F75.use_property_decorate = False
                col_B2F75.scale_x = 1.0
                col_B2F75.scale_y = 1.2000000476837158
                col_B2F75.alignment = 'Expand'.upper()
                col_B2F75.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_812E2 = '["' + str('Input_2' + '"]') 
                col_B2F75.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_812E2, text='地表', icon_value=0, emboss=True)
                split_358FA = col_B2F75.split(factor=0.5, align=True)
                split_358FA.alert = False
                split_358FA.enabled = True
                split_358FA.active = True
                split_358FA.use_property_split = False
                split_358FA.use_property_decorate = False
                split_358FA.scale_x = 1.0
                split_358FA.scale_y = 1.0
                split_358FA.alignment = 'Expand'.upper()
                if not True: split_358FA.operator_context = "EXEC_DEFAULT"
                attr_CAB51 = '["' + str('Input_9' + '"]') 
                split_358FA.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_CAB51, text='路宽', icon_value=0, emboss=True)
                attr_D6569 = '["' + str('Input_4' + '"]') 
                split_358FA.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_D6569, text='宽度细分', icon_value=0, emboss=True)
                attr_4A34D = '["' + str('Input_5' + '"]') 
                col_B2F75.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_4A34D, text='长度细分间隔', icon_value=0, emboss=True)
                attr_86709 = '["' + str('Input_10' + '"]') 
                col_B2F75.prop(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'], attr_86709, text='垂直贴合偏移', icon_value=0, emboss=True)
                col_31374 = col_B2F75.column(heading='', align=True)
                col_31374.alert = False
                col_31374.enabled = True
                col_31374.active = True
                col_31374.use_property_split = False
                col_31374.use_property_decorate = False
                col_31374.scale_x = 1.0
                col_31374.scale_y = 1.0
                col_31374.alignment = 'Expand'.upper()
                col_31374.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_31374.label(text='UV比例：', icon_value=0)
                row_4F558 = col_31374.row(heading='', align=True)
                row_4F558.alert = False
                row_4F558.enabled = True
                row_4F558.active = True
                row_4F558.use_property_split = False
                row_4F558.use_property_decorate = False
                row_4F558.scale_x = 1.0
                row_4F558.scale_y = 1.0
                row_4F558.alignment = 'Expand'.upper()
                row_4F558.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = row_4F558.operator('sna.uv_962af', text='1:1', icon_value=0, emboss=True, depress=(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Socket_0'] == 0))
                op.sna_uv = 0
                op = row_4F558.operator('sna.uv_962af', text='2:1', icon_value=0, emboss=True, depress=(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Socket_0'] == 1))
                op.sna_uv = 1
                op = row_4F558.operator('sna.uv_962af', text='4:1', icon_value=0, emboss=True, depress=(bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Socket_0'] == 2))
                op.sna_uv = 2


class SNA_OT_Uv_962Af(bpy.types.Operator):
    bl_idname = "sna.uv_962af"
    bl_label = "uv比例设置"
    bl_description = "使用贴图的高:宽"
    bl_options = {"REGISTER", "UNDO"}
    sna_uv: bpy.props.IntProperty(name='UV', description='', options={'HIDDEN'}, default=0, subtype='NONE')

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Socket_0'] = self.sna_uv
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Ef8E8(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_ef8e8"
    bl_label = "删除曲线点"
    bl_description = "删除曲线点"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.delete(type='VERT')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.report({'INFO'}, message='删除曲线点成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_3D66B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3d66b"
    bl_label = "加载曲线道路修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        if property_exists("bpy.data.node_groups['PCG_道路节点_v2']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_WAY.blend')) + r'\NodeTree', filename='PCG_道路节点_v2', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_01AE6 = None if not new_data else new_data[0]
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_道路节点_v2'
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2'].node_group = bpy.data.node_groups['PCG_道路节点_v2']
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_add_3B2E4(layout_function, ):
    col_DF4A7 = layout_function.column(heading='', align=False)
    col_DF4A7.alert = False
    col_DF4A7.enabled = ((len(bpy.context.view_layer.objects.selected) == 1) and 'OBJECT'==bpy.context.mode and (bpy.context.view_layer.objects.active.id_data.type == 'MESH'))
    col_DF4A7.active = True
    col_DF4A7.use_property_split = False
    col_DF4A7.use_property_decorate = False
    col_DF4A7.scale_x = 1.0
    col_DF4A7.scale_y = 1.5
    col_DF4A7.alignment = 'Expand'.upper()
    col_DF4A7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_DF4A7.operator('sna.my_generic_operator_638a1', text='增加道路', icon_value=9, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_638A1(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_638a1"
    bl_label = "增加道路"
    bl_description = "增加道路"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree_001['sna_obj_name'] = bpy.context.view_layer.objects.active.name
        bpy.ops.curve.primitive_bezier_curve_add(location=bpy.context.view_layer.objects.active.location, rotation=bpy.context.view_layer.objects.active.rotation_euler, scale=(1.0, 1.0, 1.0))
        bpy.ops.sna.my_generic_operator_3d66b()
        bpy.context.view_layer.objects.active.modifiers['PCG_道路节点_v2']['Input_2'] = bpy.data.objects[node_tree_001['sna_obj_name']]
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.context.scene.tool_settings.curve_paint_settings.depth_mode = 'SURFACE'
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.delete(type='VERT')
        bpy.ops.wm.tool_set_by_id(name='builtin.draw')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_E343B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e343b"
    bl_label = "应用曲线道路修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.duplicate_move()
        bpy.ops.object.convert()
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False, isolate_users=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_PT_PCG__82_04C21)
    bpy.utils.register_class(SNA_OT_Uv_962Af)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Ef8E8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3D66B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_638A1)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E343B)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_PT_PCG__82_04C21)
    bpy.utils.unregister_class(SNA_OT_Uv_962Af)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Ef8E8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3D66B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_638A1)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E343B)
