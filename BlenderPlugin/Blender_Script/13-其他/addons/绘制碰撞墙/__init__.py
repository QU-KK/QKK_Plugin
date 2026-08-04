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
    "name" : "Drawing_Collision_v1",
    "author" : "渠奎奎", 
    "description" : "曲线绘制碰撞",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews


addon_keymaps = {}
_icons = None


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_OT_My_Generic_Operator_46F93(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_46f93"
    bl_label = "创建碰撞面片"
    bl_description = "创建碰撞面片"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.active_object.modifiers.clear()
        bpy.ops.node.new_geometry_nodes_modifier()
        node_45BBE = bpy.context.active_object.modifiers[0].node_group.nodes.new(type='GeometryNodeCurveToMesh', )
        node_1217D = bpy.context.active_object.modifiers[0].node_group.nodes.new(type='GeometryNodeExtrudeMesh', )
        node_D2963 = bpy.context.active_object.modifiers[0].node_group.nodes.new(type='ShaderNodeCombineXYZ', )
        link_list = None
        link_list = [['Group Input', 0, 'Curve to Mesh', 0], ['Curve to Mesh', 0, 'Extrude Mesh', 0],['Extrude Mesh', 0, 'Group Output', 0], ['Combine XYZ', 0, 'Extrude Mesh', 2]]
        for i_394BB in range(len(link_list)):
            a_out_name = link_list[i_394BB][0]
            a_out_id = link_list[i_394BB][1]
            b_in_name = link_list[i_394BB][2]
            b_in_id = link_list[i_394BB][3]
            node_group_name = bpy.context.active_object.modifiers.active.node_group.name
            # 获取指定名称的节点组
            node_group = bpy.data.node_groups.get(node_group_name)
            # 获取名为"a"的节点和名为"b"的节点
            node_a = node_group.nodes.get(a_out_name)
            node_b = node_group.nodes.get(b_in_name)
            # 连接节点
            node_group.links.new(node_a.outputs[a_out_id], node_b.inputs[b_in_id])
        bpy.data.node_groups[bpy.context.active_object.modifiers.active.node_group.name].nodes['Combine XYZ'].inputs[2].default_value = 2.0
        bpy.data.node_groups[bpy.context.active_object.modifiers.active.node_group.name].nodes['Extrude Mesh'].mode = 'EDGES'
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_CAA_2318A(bpy.types.Panel):
    bl_label = '绘制碰撞墙'
    bl_idname = 'SNA_PT_CAA_2318A'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '便捷功能'
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
        split_25FD5 = layout.split(factor=0.699999988079071, align=True)
        split_25FD5.alert = False
        split_25FD5.enabled = True
        split_25FD5.active = True
        split_25FD5.use_property_split = False
        split_25FD5.use_property_decorate = False
        split_25FD5.scale_x = 1.0
        split_25FD5.scale_y = 1.0
        split_25FD5.alignment = 'Expand'.upper()
        if not True: split_25FD5.operator_context = "EXEC_DEFAULT"
        col_35313 = split_25FD5.column(heading='', align=True)
        col_35313.alert = False
        col_35313.enabled = True
        col_35313.active = True
        col_35313.use_property_split = False
        col_35313.use_property_decorate = False
        col_35313.scale_x = 1.0
        col_35313.scale_y = 1.5
        col_35313.alignment = 'Expand'.upper()
        col_35313.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_35313.operator('sna.my_generic_operator_a30d0', text='绘制曲线', icon_value=197, emboss=True, depress=False)
        op.sna_new_property = 'builtin.draw'
        split_F51D6 = col_35313.split(factor=0.699999988079071, align=True)
        split_F51D6.alert = False
        split_F51D6.enabled = True
        split_F51D6.active = True
        split_F51D6.use_property_split = False
        split_F51D6.use_property_decorate = False
        split_F51D6.scale_x = 1.0
        split_F51D6.scale_y = 1.0
        split_F51D6.alignment = 'Expand'.upper()
        if not True: split_F51D6.operator_context = "EXEC_DEFAULT"
        op = split_F51D6.operator('sna.my_generic_operator_a30d0', text='选择点', icon_value=218, emboss=True, depress=False)
        op.sna_new_property = 'builtin.move'
        op = split_F51D6.operator('sna.my_generic_operator_a30d0', text='加点', icon_value=31, emboss=True, depress=False)
        op.sna_new_property = 'builtin.pen'
        col_B51D7 = split_25FD5.column(heading='', align=True)
        col_B51D7.alert = False
        col_B51D7.enabled = (not 'OBJECT'==bpy.context.mode)
        col_B51D7.active = True
        col_B51D7.use_property_split = False
        col_B51D7.use_property_decorate = False
        col_B51D7.scale_x = 1.0
        col_B51D7.scale_y = 3.0
        col_B51D7.alignment = 'Expand'.upper()
        col_B51D7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_B51D7.operator('object.mode_set', text='物体模式', icon_value=235, emboss=True, depress=False)
        op.mode = 'OBJECT'
        op.toggle = False
        box_CED38 = layout.box()
        box_CED38.alert = False
        box_CED38.enabled = True
        box_CED38.active = True
        box_CED38.use_property_split = False
        box_CED38.use_property_decorate = False
        box_CED38.alignment = 'Expand'.upper()
        box_CED38.scale_x = 1.0
        box_CED38.scale_y = 1.0
        if not True: box_CED38.operator_context = "EXEC_DEFAULT"
        col_F6C88 = box_CED38.column(heading='', align=False)
        col_F6C88.alert = False
        col_F6C88.enabled = 'EDIT_CURVE'==bpy.context.mode
        col_F6C88.active = True
        col_F6C88.use_property_split = False
        col_F6C88.use_property_decorate = False
        col_F6C88.scale_x = 1.0
        col_F6C88.scale_y = 1.0
        col_F6C88.alignment = 'Expand'.upper()
        col_F6C88.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_F6C88.label(text='编辑功能', icon_value=0)
        col_F6C88.prop(bpy.context.scene.tool_settings.curve_paint_settings, 'curve_type', text='绘制类型', icon_value=346, emboss=True)
        row_964EC = col_F6C88.row(heading='', align=True)
        row_964EC.alert = False
        row_964EC.enabled = True
        row_964EC.active = True
        row_964EC.use_property_split = False
        row_964EC.use_property_decorate = False
        row_964EC.scale_x = 1.0
        row_964EC.scale_y = 1.5
        row_964EC.alignment = 'Expand'.upper()
        row_964EC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_964EC.operator('sna.my_generic_operator_1d0cb', text='连接点', icon_value=146, emboss=True, depress=False)
        op = row_964EC.operator('curve.separate', text='拆分', icon_value=613, emboss=True, depress=False)
        op = row_964EC.operator('curve.handle_type_set', text='自动', icon_value=559, emboss=True, depress=False)
        op.type = 'AUTOMATIC'
        box_A5BD8 = layout.box()
        box_A5BD8.alert = False
        box_A5BD8.enabled = True
        box_A5BD8.active = True
        box_A5BD8.use_property_split = False
        box_A5BD8.use_property_decorate = False
        box_A5BD8.alignment = 'Expand'.upper()
        box_A5BD8.scale_x = 1.0
        box_A5BD8.scale_y = 1.0
        if not True: box_A5BD8.operator_context = "EXEC_DEFAULT"
        split_EE450 = box_A5BD8.split(factor=0.5, align=True)
        split_EE450.alert = False
        split_EE450.enabled = 'OBJECT'==bpy.context.mode
        split_EE450.active = True
        split_EE450.use_property_split = False
        split_EE450.use_property_decorate = False
        split_EE450.scale_x = 1.0
        split_EE450.scale_y = 1.0
        split_EE450.alignment = 'Expand'.upper()
        if not True: split_EE450.operator_context = "EXEC_DEFAULT"
        col_58365 = split_EE450.column(heading='', align=True)
        col_58365.alert = False
        col_58365.enabled = True
        col_58365.active = True
        col_58365.use_property_split = False
        col_58365.use_property_decorate = False
        col_58365.scale_x = 1.0
        col_58365.scale_y = 1.0
        col_58365.alignment = 'Expand'.upper()
        col_58365.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_A1A4A = col_58365.column(heading='', align=True)
        col_A1A4A.alert = False
        col_A1A4A.enabled = (not property_exists("bpy.data.node_groups[bpy.context.active_object.modifiers.active.node_group.name].nodes['Combine XYZ'].inputs[2].default_value", globals(), locals()))
        col_A1A4A.active = True
        col_A1A4A.use_property_split = False
        col_A1A4A.use_property_decorate = False
        col_A1A4A.scale_x = 1.0
        col_A1A4A.scale_y = 1.0
        col_A1A4A.alignment = 'Expand'.upper()
        col_A1A4A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_A1A4A.operator('sna.my_generic_operator_46f93', text='生成碰撞面片', icon_value=243, emboss=True, depress=False)
        if property_exists("bpy.data.node_groups[bpy.context.active_object.modifiers.active.node_group.name].nodes['Combine XYZ'].inputs[2].default_value", globals(), locals()):
            col_58365.prop(bpy.data.node_groups[bpy.context.active_object.modifiers.active.node_group.name].nodes['Combine XYZ'].inputs[2], 'default_value', text='', icon_value=0, emboss=True)
        else:
            col_58365.label(text='无', icon_value=19)
        if property_exists("bpy.data.node_groups[bpy.context.active_object.modifiers.active.node_group.name].nodes['Combine XYZ'].inputs[2].default_value", globals(), locals()):
            split_C8679 = split_EE450.split(factor=0.20000000298023224, align=True)
            split_C8679.alert = False
            split_C8679.enabled = True
            split_C8679.active = True
            split_C8679.use_property_split = False
            split_C8679.use_property_decorate = False
            split_C8679.scale_x = 1.0
            split_C8679.scale_y = 2.0
            split_C8679.alignment = 'Expand'.upper()
            if not True: split_C8679.operator_context = "EXEC_DEFAULT"
            split_C8679.prop(bpy.context.view_layer.objects.active.modifiers[0], 'show_viewport', text='', icon_value=253, emboss=True)
            col_AFF43 = split_C8679.column(heading='', align=True)
            col_AFF43.alert = False
            col_AFF43.enabled = True
            col_AFF43.active = True
            col_AFF43.use_property_split = False
            col_AFF43.use_property_decorate = False
            col_AFF43.scale_x = 1.0
            col_AFF43.scale_y = 1.0
            col_AFF43.alignment = 'Expand'.upper()
            col_AFF43.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_AFF43.operator('object.convert', text='生成网格', icon_value=235, emboss=True, depress=False)
            op.target = 'MESH'
            op.keep_original = True


class SNA_OT_My_Generic_Operator_1D0Cb(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_1d0cb"
    bl_label = "连接碰撞"
    bl_description = "连接碰撞"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.curve.make_segment()
        bpy.ops.curve.normals_make_consistent()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_A30D0(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a30d0"
    bl_label = "模式切换"
    bl_description = "模式切换"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='工具名称', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.wm.tool_set_by_id(name=self.sna_new_property)
        bpy.context.scene.tool_settings.curve_paint_settings.depth_mode = 'SURFACE'
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_46F93)
    bpy.utils.register_class(SNA_PT_CAA_2318A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1D0Cb)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A30D0)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_46F93)
    bpy.utils.unregister_class(SNA_PT_CAA_2318A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1D0Cb)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A30D0)
