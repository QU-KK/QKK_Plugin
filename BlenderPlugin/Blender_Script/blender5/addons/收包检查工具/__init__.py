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
    "name" : "Visual_Inspection_Tool",
    "author" : "渠奎奎", 
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
import atexit
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
lod = {'sna_obj_lod_list': [], }


def sna_update_sna_lod_wireframe_switch_BAD09(self, context):
    sna_updated_prop = self.sna_lod_wireframe_switch
    name = '_lod'
    length = -5
    obj_list = None
    obj_list = []
    # 遍历当前场景中的所有对象
    for obj in bpy.context.scene.objects:
        # 检查对象名称
        if name in obj.name[length:]:
            for layer in bpy.context.scene.view_layers:
                if obj.name in layer.objects:
                    obj_list.append(obj)
    print('获取物体')
    for i_7FD15 in range(len(obj_list)):
        obj_list[i_7FD15].show_wire = sna_updated_prop


def sna_update_sna_lod_boundary_switch_6048A(self, context):
    sna_updated_prop = self.sna_lod_boundary_switch
    name = '_lod'
    length = -5
    obj_list = None
    obj_list = []
    # 遍历当前场景中的所有对象
    for obj in bpy.context.scene.objects:
        # 检查对象名称
        if name in obj.name[length:]:
            for layer in bpy.context.scene.view_layers:
                if obj.name in layer.objects:
                    obj_list.append(obj)
    print('获取物体')
    for i_FAA11 in range(len(obj_list)):
        obj_list[i_FAA11].show_bounds = sna_updated_prop


def sna_update_sna_collision_wireframe_switch_6FE25(self, context):
    sna_updated_prop = self.sna_collision_wireframe_switch
    name = '_autophy'
    length = -10
    obj_list = None
    obj_list = []
    # 遍历当前场景中的所有对象
    for obj in bpy.context.scene.objects:
        # 检查对象名称
        if name in obj.name[length:]:
            for layer in bpy.context.scene.view_layers:
                if obj.name in layer.objects:
                    obj_list.append(obj)
    print('获取物体')
    for i_BAFCF in range(len(obj_list)):
        obj_list[i_BAFCF].show_wire = sna_updated_prop


class SNA_PT_visual_inspection_tool_C051B(bpy.types.Panel):
    bl_label = '可视检查工具'
    bl_idname = 'SNA_PT_visual_inspection_tool_C051B'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'G108'
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x=0    
    
    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout
        op = layout.operator('sna.my_generic_operator_6dd56', text='重置', icon_value=0, emboss=True, depress=False)

    def draw(self, context):
        layout = self.layout


def before_exit_handler_A594E():
    bpy.ops.sna.my_generic_operator_6dd56()


class SNA_OT_My_Generic_Operator_6Dd56(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6dd56"
    bl_label = "重置"
    bl_description = "重置"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        # 遍历当前场景中的所有对象
        for obj in bpy.context.scene.objects:    
            if '_lod' in obj.name[-5:] or '_autophy' in obj.name[-10:]:# 检查对象名称
                for layer in bpy.context.scene.view_layers:
                    if obj.name in layer.objects:
                        obj.hide_set(not True)
                        obj.hide_render=(not True)
                        obj.show_bounds = False
                        obj.show_wire = False
                        # 清理修改器
                        modifiers_list = ['碰撞_几何节点','UV精度_几何节点','UV可视化_几何节点']
                        for modifiers_name in modifiers_list:
                            modifier = obj.modifiers.get(modifiers_name)
                            if modifier:
                                obj.modifiers.remove(modifier)
        bpy.context.space_data.shading.render_pass = 'COMBINED'
        self.report({'INFO'}, message='ok!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_add_to_view3d_mt_editor_menus_167BB(self, context):
    if not (False):
        layout = self.layout
        layout.popover('SNA_PT_display_switching_7B93F', text='显示', icon_value=string_to_icon('NODE_SOCKET_STRING'))


class SNA_PT_display_switching_7B93F(bpy.types.Panel):
    bl_label = '显示切换'
    bl_idname = 'SNA_PT_display_switching_7B93F'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_context = ''
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_06C41 = layout.column(heading='', align=False)
        col_06C41.alert = False
        col_06C41.enabled = True
        col_06C41.active = True
        col_06C41.use_property_split = False
        col_06C41.use_property_decorate = False
        col_06C41.scale_x = 1.0
        col_06C41.scale_y = 1.5
        col_06C41.alignment = 'Expand'.upper()
        col_06C41.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_06C41.operator('sna.my_generic_operator_6dd56', text='重置', icon_value=string_to_icon('RECOVER_LAST'), emboss=True, depress=False)
        box_C6D58 = layout.box()
        box_C6D58.alert = False
        box_C6D58.enabled = True
        box_C6D58.active = True
        box_C6D58.use_property_split = False
        box_C6D58.use_property_decorate = False
        box_C6D58.alignment = 'Expand'.upper()
        box_C6D58.scale_x = 1.0
        box_C6D58.scale_y = 1.0
        if not True: box_C6D58.operator_context = "EXEC_DEFAULT"
        layout_function = box_C6D58
        sna_lod_interface_C0C4C(layout_function, )
        box_1A130 = layout.box()
        box_1A130.alert = False
        box_1A130.enabled = True
        box_1A130.active = True
        box_1A130.use_property_split = False
        box_1A130.use_property_decorate = False
        box_1A130.alignment = 'Expand'.upper()
        box_1A130.scale_x = 1.0
        box_1A130.scale_y = 1.0
        if not True: box_1A130.operator_context = "EXEC_DEFAULT"
        layout_function = box_1A130
        sna_pbr_59497(layout_function, )


class SNA_OT_Lod_Level_Switch_3C8Bc(bpy.types.Operator):
    bl_idname = "sna.lod_level_switch_3c8bc"
    bl_label = "Lod_Level_Switch"
    bl_description = "切换lod级别"
    bl_options = {"REGISTER", "UNDO"}
    sna_lod_level: bpy.props.StringProperty(name='Lod_Level', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        lod = '_lod' + self.sna_lod_level
        # 遍历当前场景中的所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象名称最后五个字符是否包含 '_lod'
            if '_lod' in obj.name[-5:]:
                for layer in bpy.context.scene.view_layers:
                    if obj.name in layer.objects:
                        if lod == obj.name[-5:]:        
                            obj.hide_set(not True)
                            obj.hide_render=(not True)
                        else:
                            obj.hide_set(not False)
                            obj.hide_render=(not False)
        print('切换完成')
        bpy.ops.sna.my_generic_operator_00efd(sna_switch=False, sna_collisiona='_autophy', sna_collisionb='_autophy_s')
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Lod_Global_Control_73Cb9(bpy.types.Operator):
    bl_idname = "sna.lod_global_control_73cb9"
    bl_label = "Lod_Global_Control"
    bl_description = "显示隐藏全部lod"
    bl_options = {"REGISTER", "UNDO"}
    sna_lod_global_display: bpy.props.BoolProperty(name='Lod_Global_Display', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        Switch = self.sna_lod_global_display
        # 遍历当前场景中的所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象名称最后五个字符是否包含 '_lod'
            if '_lod' in obj.name[-5:]:
                for layer in bpy.context.scene.view_layers:
                    if obj.name in layer.objects:
                        obj.hide_set(not Switch)
                        obj.hide_render=(not Switch)
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_lod_interface_C0C4C(layout_function, ):
    col_D9630 = layout_function.column(heading='', align=False)
    col_D9630.alert = False
    col_D9630.enabled = True
    col_D9630.active = True
    col_D9630.use_property_split = False
    col_D9630.use_property_decorate = False
    col_D9630.scale_x = 1.0
    col_D9630.scale_y = 1.0
    col_D9630.alignment = 'Expand'.upper()
    col_D9630.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_9C14A = col_D9630.split(factor=0.5, align=True)
    split_9C14A.alert = False
    split_9C14A.enabled = True
    split_9C14A.active = True
    split_9C14A.use_property_split = False
    split_9C14A.use_property_decorate = False
    split_9C14A.scale_x = 1.0
    split_9C14A.scale_y = 1.5
    split_9C14A.alignment = 'Expand'.upper()
    if not True: split_9C14A.operator_context = "EXEC_DEFAULT"
    op = split_9C14A.operator('sna.lod_global_control_73cb9', text='Lod 显示', icon_value=0, emboss=True, depress=False)
    op.sna_lod_global_display = True
    op = split_9C14A.operator('sna.lod_global_control_73cb9', text='Lod 隐藏', icon_value=0, emboss=True, depress=False)
    op.sna_lod_global_display = False
    col_9C36E = col_D9630.column(heading='', align=True)
    col_9C36E.alert = False
    col_9C36E.enabled = True
    col_9C36E.active = True
    col_9C36E.use_property_split = False
    col_9C36E.use_property_decorate = False
    col_9C36E.scale_x = 1.0
    col_9C36E.scale_y = 1.2000000476837158
    col_9C36E.alignment = 'Expand'.upper()
    col_9C36E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    for i_80D8D in range(4):
        op = col_9C36E.operator('sna.lod_level_switch_3c8bc', text='lod' + str(i_80D8D), icon_value=0, emboss=True, depress=False)
        op.sna_lod_level = str(i_80D8D)
    row_E2B7B = col_D9630.row(heading='', align=True)
    row_E2B7B.alert = False
    row_E2B7B.enabled = True
    row_E2B7B.active = True
    row_E2B7B.use_property_split = False
    row_E2B7B.use_property_decorate = False
    row_E2B7B.scale_x = 1.0
    row_E2B7B.scale_y = 1.0
    row_E2B7B.alignment = 'Expand'.upper()
    row_E2B7B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_E2B7B.prop(bpy.context.area.spaces[0].overlay, 'show_face_orientation', text='正反', icon_value=0, emboss=True)
    row_E2B7B.prop(bpy.context.area.spaces[0].overlay, 'show_stats', text='统计', icon_value=0, emboss=True)
    row_E2B7B.prop(bpy.context.scene, 'sna_lod_wireframe_switch', text='线框', icon_value=0, emboss=True)
    row_E2B7B.prop(bpy.context.scene, 'sna_lod_boundary_switch', text='边界', icon_value=0, emboss=True)


class SNA_OT_Pbr_09F62(bpy.types.Operator):
    bl_idname = "sna.pbr_09f62"
    bl_label = "PBR通道切换"
    bl_description = "PBR通道切换"
    bl_options = {"REGISTER", "UNDO"}
    sna_pbr_name: bpy.props.StringProperty(name='pbr_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        aov_list = '颜色,粗糙度,金属度,法线,Ao,自发光,透贴,顶点色'.split(',')
        pbr_name = self.sna_pbr_name
        aovs = bpy.context.view_layer.aovs
        # 检查当前 AOV 的数量
        if len(aovs) == 8:
            pass
        else:
            # 删除当前所有 AOV
            for i in range(len(aovs)):
                bpy.ops.scene.view_layer_remove_aov()
            # 添加新的 AOV
            for name in aov_list:
                bpy.ops.scene.view_layer_add_aov()  # 添加新的 AOV
                bpy.context.view_layer.active_aov.name = name  # 设置 AOV 名称
        bpy.context.space_data.shading.render_pass = pbr_name
        self.report({'INFO'}, message='OK！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_pbr_59497(layout_function, ):
    col_0E679 = layout_function.column(heading='', align=False)
    col_0E679.alert = False
    col_0E679.enabled = True
    col_0E679.active = True
    col_0E679.use_property_split = False
    col_0E679.use_property_decorate = False
    col_0E679.scale_x = 1.0
    col_0E679.scale_y = 1.5
    col_0E679.alignment = 'Expand'.upper()
    col_0E679.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_0E679.operator('sna.pbr_09f62', text='PBR', icon_value=0, emboss=True, depress=False)
    op.sna_pbr_name = 'COMBINED'
    grid_233A1 = layout_function.grid_flow(columns=2, row_major=True, even_columns=False, even_rows=False, align=True)
    grid_233A1.enabled = True
    grid_233A1.active = True
    grid_233A1.use_property_split = False
    grid_233A1.use_property_decorate = False
    grid_233A1.alignment = 'Expand'.upper()
    grid_233A1.scale_x = 1.0
    grid_233A1.scale_y = 1.0
    if not True: grid_233A1.operator_context = "EXEC_DEFAULT"
    for i_84A52 in range(len('颜色,粗糙度,金属度,法线,Ao,自发光,透贴,顶点色'.split(','))):
        op = grid_233A1.operator('sna.pbr_09f62', text='颜色,粗糙度,金属度,法线,Ao,自发光,透贴,顶点色'.split(',')[i_84A52], icon_value=0, emboss=True, depress=False)
        op.sna_pbr_name = '颜色,粗糙度,金属度,法线,Ao,自发光,透贴,顶点色'.split(',')[i_84A52]


def sna_uv_A550C(layout_function, ):
    col_4D755 = layout_function.column(heading='', align=False)
    col_4D755.alert = False
    col_4D755.enabled = True
    col_4D755.active = True
    col_4D755.use_property_split = False
    col_4D755.use_property_decorate = False
    col_4D755.scale_x = 1.0
    col_4D755.scale_y = 1.0
    col_4D755.alignment = 'Expand'.upper()
    col_4D755.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_5B770 = col_4D755.split(factor=0.800000011920929, align=True)
    split_5B770.alert = False
    split_5B770.enabled = True
    split_5B770.active = True
    split_5B770.use_property_split = False
    split_5B770.use_property_decorate = False
    split_5B770.scale_x = 1.0
    split_5B770.scale_y = 1.0
    split_5B770.alignment = 'Expand'.upper()
    if not True: split_5B770.operator_context = "EXEC_DEFAULT"
    col_2BC6C = split_5B770.column(heading='', align=True)
    col_2BC6C.alert = False
    col_2BC6C.enabled = True
    col_2BC6C.active = True
    col_2BC6C.use_property_split = False
    col_2BC6C.use_property_decorate = False
    col_2BC6C.scale_x = 1.0
    col_2BC6C.scale_y = 1.0
    col_2BC6C.alignment = 'Expand'.upper()
    col_2BC6C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_8FBA4 = col_2BC6C.split(factor=0.5, align=True)
    split_8FBA4.alert = False
    split_8FBA4.enabled = True
    split_8FBA4.active = True
    split_8FBA4.use_property_split = False
    split_8FBA4.use_property_decorate = False
    split_8FBA4.scale_x = 1.0
    split_8FBA4.scale_y = 1.5
    split_8FBA4.alignment = 'Expand'.upper()
    if not True: split_8FBA4.operator_context = "EXEC_DEFAULT"
    op = split_8FBA4.operator('sna.uv_d97b3', text='1U', icon_value=0, emboss=True, depress=False)
    op.sna_clear = True
    op.sna_uv_id = 0
    op = split_8FBA4.operator('sna.uv_d97b3', text='2U', icon_value=0, emboss=True, depress=False)
    op.sna_clear = True
    op.sna_uv_id = 1
    row_E0C1D = col_2BC6C.row(heading='', align=True)
    row_E0C1D.alert = False
    row_E0C1D.enabled = True
    row_E0C1D.active = True
    row_E0C1D.use_property_split = False
    row_E0C1D.use_property_decorate = False
    row_E0C1D.scale_x = 1.0
    row_E0C1D.scale_y = 1.0
    row_E0C1D.alignment = 'Expand'.upper()
    row_E0C1D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_E0C1D.prop(bpy.context.scene, 'sna_uv_id_visible', text=bpy.context.scene.sna_uv_id_visible, icon_value=0, emboss=True, expand=True)
    col_84B13 = split_5B770.column(heading='', align=True)
    col_84B13.alert = False
    col_84B13.enabled = True
    col_84B13.active = True
    col_84B13.use_property_split = False
    col_84B13.use_property_decorate = False
    col_84B13.scale_x = 1.0
    col_84B13.scale_y = 2.5
    col_84B13.alignment = 'Expand'.upper()
    col_84B13.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_84B13.operator('sna.uv_d97b3', text='关闭', icon_value=0, emboss=True, depress=False)
    op.sna_clear = False
    op.sna_uv_id = 0
    row_344DA = col_4D755.row(heading='', align=True)
    row_344DA.alert = False
    row_344DA.enabled = True
    row_344DA.active = True
    row_344DA.use_property_split = False
    row_344DA.use_property_decorate = False
    row_344DA.scale_x = 1.0
    row_344DA.scale_y = 1.0
    row_344DA.alignment = 'Expand'.upper()
    row_344DA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_344DA.prop(bpy.context.scene, 'sna_uv_cid_visible_switch', text=bpy.context.scene.sna_uv_cid_visible_switch, icon_value=0, emboss=True, expand=True)


class SNA_OT_Uv_D97B3(bpy.types.Operator):
    bl_idname = "sna.uv_d97b3"
    bl_label = "UV可视化"
    bl_description = "UV可视化"
    bl_options = {"REGISTER", "UNDO"}
    sna_clear: bpy.props.BoolProperty(name='clear', description='', options={'HIDDEN'}, default=False)
    sna_uv_id: bpy.props.IntProperty(name='UV_ID', description='', options={'HIDDEN'}, default=0, subtype='NONE')

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        asset_path = bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'ass.blend'))
        clear = self.sna_clear
        UV_Model = (2 if (bpy.context.scene.sna_uv_id_visible == '面') else (1 if (bpy.context.scene.sna_uv_id_visible == '线') else 0))
        CID = bpy.context.scene.sna_uv_cid_visible_switch
        UV_ID = self.sna_uv_id
        obj_list = []
        # 遍历当前场景中的所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象名称
            if '_lod' in obj.name[-5:]:    
                for layer in bpy.context.scene.view_layers:
                    if obj.name in layer.objects:
                        obj_list.append(obj) 
        node_name = 'UV可视化_几何节点'
        for obj in obj_list:
            modifier = obj.modifiers.get(node_name) # 清理修改器
            if modifier:
                obj.modifiers.remove(modifier)
            if clear:
                if node_name in bpy.data.node_groups: # 判断是否存在
                    pass
                else:
                    bpy.ops.wm.append(directory = bpy.path.abspath(asset_path) + '/NodeTree', filename = node_name, link=True) #关联节点
                if (CID in obj.name[-8:] or '_c' not in obj.name[-8:]) and len(obj.data.uv_layers) > UV_ID: #判断尾缀名称，UV长度判断
                    obj.modifiers.new(name=node_name, type='NODES', ).node_group = bpy.data.node_groups[node_name] # 使用节点
                    # 判断相关碰撞模型是否存在，存在则使用到几何节点
                    if '_c' in obj.name[-8:]:
                        if obj.name[:-8] + '_autophy_s' in bpy.data.objects:
                            obj.modifiers[node_name]['Socket_2'] = bpy.context.blend_data.objects[obj.name[:-8] + '_autophy_s']
                    else:
                        if obj.name[:-8] + '_autophy_s' in bpy.data.objects:
                            obj.modifiers[node_name]['Socket_2'] = bpy.context.blend_data.objects[obj.name[:-5] + '_autophy_s']            
                    # 配置几何节点参数
                    obj.modifiers[node_name]['Socket_3'] = obj.id_data.data.uv_layers[UV_ID].name
                    obj.modifiers[node_name]['Socket_4'] = UV_Model
        print('UV可视化 完成')
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_33067(bpy.types.Operator):
    bl_idname = "sna.uv_33067"
    bl_label = "UV精度检查"
    bl_description = "UV精度检查"
    bl_options = {"REGISTER", "UNDO"}
    sna_uv_id: bpy.props.IntProperty(name='UV_ID', description='', options={'HIDDEN'}, default=0, subtype='NONE')
    sna_clear: bpy.props.BoolProperty(name='clear', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        asset_path = bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'ass.blend'))
        UV_ID = self.sna_uv_id
        UV1 = bpy.context.scene.sna_uv_1_precision
        UV2 = bpy.context.scene.sna_uv_2_precision
        clear = (not self.sna_clear)
        obj_list = []
        # 遍历当前场景中的所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象名称最后10个字符是否包含 '_autophy'
            if '_lod' in obj.name[-5:]:
                for layer in bpy.context.scene.view_layers:
                    if obj.name in layer.objects:
                        obj_list.append(obj) 
        node_name = 'UV精度_几何节点'
        for obj in obj_list:
            modifier = obj.modifiers.get(node_name) # 清理修改器
            if modifier:
                obj.modifiers.remove(modifier)
            if clear:
                if node_name in bpy.data.node_groups: # 判断是否存在
                    pass
                else:
                    bpy.ops.wm.append(directory = bpy.path.abspath(asset_path) + '/NodeTree', filename = node_name, link=True) #关联节点
                obj.modifiers.new(name=node_name, type='NODES', ).node_group = bpy.data.node_groups[node_name] # 使用节点
                obj.modifiers[node_name]['Socket_0'] = UV_ID
                obj.modifiers[node_name]['Socket_1'] = UV1
                obj.modifiers[node_name]['Socket_2'] = UV2
        print('UV精度_可视化 完成')
        self.report({'INFO'}, message='ok！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_uv_precision_interface_19117(layout_function, ):
    split_AAEC3 = layout_function.split(factor=0.800000011920929, align=True)
    split_AAEC3.alert = False
    split_AAEC3.enabled = True
    split_AAEC3.active = True
    split_AAEC3.use_property_split = False
    split_AAEC3.use_property_decorate = False
    split_AAEC3.scale_x = 1.0
    split_AAEC3.scale_y = 1.0
    split_AAEC3.alignment = 'Expand'.upper()
    if not True: split_AAEC3.operator_context = "EXEC_DEFAULT"
    col_A277D = split_AAEC3.column(heading='', align=True)
    col_A277D.alert = False
    col_A277D.enabled = True
    col_A277D.active = True
    col_A277D.use_property_split = False
    col_A277D.use_property_decorate = False
    col_A277D.scale_x = 1.0
    col_A277D.scale_y = 1.0
    col_A277D.alignment = 'Expand'.upper()
    col_A277D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_EB349 = col_A277D.split(factor=0.5, align=True)
    split_EB349.alert = False
    split_EB349.enabled = True
    split_EB349.active = True
    split_EB349.use_property_split = False
    split_EB349.use_property_decorate = False
    split_EB349.scale_x = 1.0
    split_EB349.scale_y = 1.5
    split_EB349.alignment = 'Expand'.upper()
    if not True: split_EB349.operator_context = "EXEC_DEFAULT"
    op = split_EB349.operator('sna.uv_33067', text='1U', icon_value=0, emboss=True, depress=False)
    op.sna_uv_id = 0
    op.sna_clear = False
    op = split_EB349.operator('sna.uv_33067', text='2U', icon_value=0, emboss=True, depress=False)
    op.sna_uv_id = 1
    op.sna_clear = False
    split_CF6E1 = col_A277D.split(factor=0.5, align=True)
    split_CF6E1.alert = False
    split_CF6E1.enabled = True
    split_CF6E1.active = True
    split_CF6E1.use_property_split = False
    split_CF6E1.use_property_decorate = False
    split_CF6E1.scale_x = 1.0
    split_CF6E1.scale_y = 1.0
    split_CF6E1.alignment = 'Expand'.upper()
    if not True: split_CF6E1.operator_context = "EXEC_DEFAULT"
    split_CF6E1.prop(bpy.context.scene, 'sna_uv_1_precision', text='缩放', icon_value=0, emboss=True)
    split_CF6E1.prop(bpy.context.scene, 'sna_uv_2_precision', text='缩放', icon_value=0, emboss=True)
    col_C5DCD = split_AAEC3.column(heading='', align=True)
    col_C5DCD.alert = False
    col_C5DCD.enabled = True
    col_C5DCD.active = True
    col_C5DCD.use_property_split = False
    col_C5DCD.use_property_decorate = False
    col_C5DCD.scale_x = 1.0
    col_C5DCD.scale_y = 2.5
    col_C5DCD.alignment = 'Expand'.upper()
    col_C5DCD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_C5DCD.operator('sna.uv_33067', text='关闭', icon_value=0, emboss=True, depress=False)
    op.sna_uv_id = 0
    op.sna_clear = True


def sna_collision_interface_B37B4(layout_function, ):
    split_1715F = layout_function.split(factor=0.699999988079071, align=False)
    split_1715F.alert = False
    split_1715F.enabled = True
    split_1715F.active = True
    split_1715F.use_property_split = False
    split_1715F.use_property_decorate = False
    split_1715F.scale_x = 1.0
    split_1715F.scale_y = 1.0
    split_1715F.alignment = 'Expand'.upper()
    if not True: split_1715F.operator_context = "EXEC_DEFAULT"
    col_37933 = split_1715F.column(heading='', align=True)
    col_37933.alert = False
    col_37933.enabled = True
    col_37933.active = True
    col_37933.use_property_split = False
    col_37933.use_property_decorate = False
    col_37933.scale_x = 1.0
    col_37933.scale_y = 1.0
    col_37933.alignment = 'Expand'.upper()
    col_37933.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_DCA2A = col_37933.split(factor=0.699999988079071, align=True)
    split_DCA2A.alert = False
    split_DCA2A.enabled = True
    split_DCA2A.active = True
    split_DCA2A.use_property_split = False
    split_DCA2A.use_property_decorate = False
    split_DCA2A.scale_x = 1.0
    split_DCA2A.scale_y = 1.0
    split_DCA2A.alignment = 'Expand'.upper()
    if not True: split_DCA2A.operator_context = "EXEC_DEFAULT"
    col_830E7 = split_DCA2A.column(heading='', align=True)
    col_830E7.alert = False
    col_830E7.enabled = True
    col_830E7.active = True
    col_830E7.use_property_split = False
    col_830E7.use_property_decorate = False
    col_830E7.scale_x = 1.0
    col_830E7.scale_y = 2.0
    col_830E7.alignment = 'Expand'.upper()
    col_830E7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_830E7.operator('sna.my_generic_operator_00efd', text='全部显示', icon_value=string_to_icon('HIDE_OFF'), emboss=True, depress=False)
    op.sna_switch = True
    op.sna_collisiona = '_autophy'
    op.sna_collisionb = '_autophy_s'
    col_94C2B = split_DCA2A.column(heading='', align=True)
    col_94C2B.alert = False
    col_94C2B.enabled = True
    col_94C2B.active = True
    col_94C2B.use_property_split = False
    col_94C2B.use_property_decorate = False
    col_94C2B.scale_x = 1.0
    col_94C2B.scale_y = 1.0
    col_94C2B.alignment = 'Expand'.upper()
    col_94C2B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_94C2B.operator('sna.my_generic_operator_00efd', text='子弹', icon_value=0, emboss=True, depress=False)
    op.sna_switch = True
    op.sna_collisiona = '_autophy'
    op.sna_collisionb = '_autophy'
    op = col_94C2B.operator('sna.my_generic_operator_00efd', text='行走', icon_value=0, emboss=True, depress=False)
    op.sna_switch = True
    op.sna_collisiona = '_autophy_s'
    op.sna_collisionb = '_autophy_s'
    split_0E150 = col_37933.split(factor=0.699999988079071, align=True)
    split_0E150.alert = False
    split_0E150.enabled = True
    split_0E150.active = True
    split_0E150.use_property_split = False
    split_0E150.use_property_decorate = False
    split_0E150.scale_x = 1.0
    split_0E150.scale_y = 1.0
    split_0E150.alignment = 'Expand'.upper()
    if not True: split_0E150.operator_context = "EXEC_DEFAULT"
    col_0E282 = split_0E150.column(heading='', align=True)
    col_0E282.alert = False
    col_0E282.enabled = True
    col_0E282.active = True
    col_0E282.use_property_split = False
    col_0E282.use_property_decorate = False
    col_0E282.scale_x = 1.0
    col_0E282.scale_y = 2.0
    col_0E282.alignment = 'Expand'.upper()
    col_0E282.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_0E282.operator('sna.my_generic_operator_00efd', text='全部隐藏', icon_value=string_to_icon('HIDE_ON'), emboss=True, depress=False)
    op.sna_switch = False
    op.sna_collisiona = '_autophy'
    op.sna_collisionb = '_autophy_s'
    col_97BAF = split_0E150.column(heading='', align=True)
    col_97BAF.alert = False
    col_97BAF.enabled = True
    col_97BAF.active = True
    col_97BAF.use_property_split = False
    col_97BAF.use_property_decorate = False
    col_97BAF.scale_x = 1.0
    col_97BAF.scale_y = 1.0
    col_97BAF.alignment = 'Expand'.upper()
    col_97BAF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_97BAF.operator('sna.my_generic_operator_00efd', text='子弹', icon_value=0, emboss=True, depress=False)
    op.sna_switch = False
    op.sna_collisiona = '_autophy'
    op.sna_collisionb = '_autophy'
    op = col_97BAF.operator('sna.my_generic_operator_00efd', text='行走', icon_value=0, emboss=True, depress=False)
    op.sna_switch = False
    op.sna_collisiona = '_autophy_s'
    op.sna_collisionb = '_autophy_s'
    col_7F06D = split_1715F.column(heading='', align=True)
    col_7F06D.alert = False
    col_7F06D.enabled = True
    col_7F06D.active = True
    col_7F06D.use_property_split = False
    col_7F06D.use_property_decorate = False
    col_7F06D.scale_x = 1.0
    col_7F06D.scale_y = 2.0
    col_7F06D.alignment = 'Expand'.upper()
    col_7F06D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_7F06D.operator('sna.my_generic_operator_cb2ef', text='行走可视', icon_value=0, emboss=True, depress=False)
    op.sna_name = '_autophy_s'
    op = col_7F06D.operator('sna.my_generic_operator_cb2ef', text='子弹可视', icon_value=0, emboss=True, depress=False)
    op.sna_name = '_autophy'
    layout_function.prop(bpy.context.scene, 'sna_collision_wireframe_switch', text='线框', icon_value=0, emboss=True)


class SNA_OT_My_Generic_Operator_00Efd(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_00efd"
    bl_label = "碰撞显示切换"
    bl_description = "碰撞显示切换"
    bl_options = {"REGISTER", "UNDO"}
    sna_switch: bpy.props.BoolProperty(name='Switch', description='', options={'HIDDEN'}, default=False)
    sna_collisiona: bpy.props.StringProperty(name='CollisionA', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_collisionb: bpy.props.StringProperty(name='CollisionB', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        Switch = self.sna_switch
        CollisionA = self.sna_collisiona
        CollisionB = self.sna_collisionb
        obj_list = []
        # 遍历当前场景中的所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象名称
            if CollisionA == obj.name[-8:] or CollisionB == obj.name[-10:]:
                for layer in bpy.context.scene.view_layers:
                    if obj.name in layer.objects:                
                        obj.hide_set(not Switch)
                        obj.hide_render=(not Switch)
                        modifier = obj.modifiers.get('碰撞_几何节点')
                        if modifier:
                            obj.modifiers.remove(modifier)
        print('碰撞隐藏/显示')
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Cb2Ef(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_cb2ef"
    bl_label = "碰撞可视化"
    bl_description = "碰撞可视化"
    bl_options = {"REGISTER", "UNDO"}
    sna_name: bpy.props.StringProperty(name='name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        name = self.sna_name
        asset_path = bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'ass.blend'))
        obj_list = []
        length = len(name) *-1
        # 遍历当前场景中的所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象名称最后10个字符是否包含 '_autophy'
            if '_autophy' in obj.name[-10:]:
                for layer in bpy.context.scene.view_layers:
                    if obj.name in layer.objects:
                        obj_list.append(obj) 
        for obj in obj_list:
            if name == obj.name[length:]:
                obj.hide_set(not True)
                obj.hide_render=(not True)
            else:
                obj.hide_set(not False)
                obj.hide_render=(not False)
        node_name = '碰撞_几何节点'
        for obj in obj_list:
            modifier = obj.modifiers.get(node_name) # 清理修改器
            if modifier:
                obj.modifiers.remove(modifier)    
            if node_name in bpy.data.node_groups: # 判断是否存在
                pass
            else:
                bpy.ops.wm.append(directory = bpy.path.abspath(asset_path) + '/NodeTree', filename = node_name, link=True) #关联节点
            obj.modifiers.new(name=node_name, type='NODES', ).node_group = bpy.data.node_groups[node_name] # 使用节点
            mat_get = bpy.data.materials.get
            obj.modifiers[node_name]['Socket_3'] = mat_get('default_phymat')
            obj.modifiers[node_name]['Socket_4'] = mat_get('metal_phymat')
            obj.modifiers[node_name]['Socket_5'] = mat_get('build_phymat')
            obj.modifiers[node_name]['Socket_6'] = mat_get('stone_phymat')
            obj.modifiers[node_name]['Socket_7'] = mat_get('wood_phymat')
            obj.modifiers[node_name]['Socket_8'] = mat_get('cloth_phymat')
            obj.modifiers[node_name]['Socket_9'] = mat_get('glass_phymat')
            obj.modifiers[node_name]['Socket_10'] = mat_get('leather_phymat')
            obj.modifiers[node_name]['Socket_11'] = mat_get('rubber_phymat')
            obj.modifiers[node_name]['Socket_12'] = mat_get('soil_phymat')
            obj.modifiers[node_name]['Socket_13'] = mat_get('ice_phymat')
            obj.modifiers[node_name]['Socket_14'] = mat_get('water_phymat')
        print('碰撞_可视化 完成')
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_LOD_AC2EF(bpy.types.Panel):
    bl_label = 'Lod'
    bl_idname = 'SNA_PT_LOD_AC2EF'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_visual_inspection_tool_C051B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_lod_interface_C0C4C(layout_function, )


class SNA_PT_collision_interface_6C4E5(bpy.types.Panel):
    bl_label = '碰撞'
    bl_idname = 'SNA_PT_collision_interface_6C4E5'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_visual_inspection_tool_C051B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_collision_interface_B37B4(layout_function, )


class SNA_PT_UV_54E49(bpy.types.Panel):
    bl_label = 'UV精度'
    bl_idname = 'SNA_PT_UV_54E49'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_visual_inspection_tool_C051B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_uv_precision_interface_19117(layout_function, )


class SNA_PT_UV_6D02B(bpy.types.Panel):
    bl_label = 'UV可视化'
    bl_idname = 'SNA_PT_UV_6D02B'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_visual_inspection_tool_C051B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_uv_A550C(layout_function, )


class SNA_PT_PBR_D1E85(bpy.types.Panel):
    bl_label = 'PBR通道'
    bl_idname = 'SNA_PT_PBR_D1E85'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_visual_inspection_tool_C051B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_pbr_59497(layout_function, )


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_lod_wireframe_switch = bpy.props.BoolProperty(name='lod_wireframe_switch', description='', default=False, update=sna_update_sna_lod_wireframe_switch_BAD09)
    bpy.types.Scene.sna_lod_boundary_switch = bpy.props.BoolProperty(name='lod_boundary_switch', description='', default=False, update=sna_update_sna_lod_boundary_switch_6048A)
    bpy.types.Scene.sna_collision_wireframe_switch = bpy.props.BoolProperty(name='collision_wireframe_switch', description='', default=False, update=sna_update_sna_collision_wireframe_switch_6FE25)
    bpy.types.Scene.sna_uv_1_precision = bpy.props.FloatProperty(name='uv_1_precision', description='', default=1.0, subtype='NONE', unit='NONE', soft_min=0.0, soft_max=20.0, step=1, precision=2)
    bpy.types.Scene.sna_uv_2_precision = bpy.props.FloatProperty(name='uv_2_precision', description='', default=1.0, subtype='NONE', unit='NONE', soft_min=0.0, soft_max=20.0, step=1, precision=2)
    bpy.types.Scene.sna_uv_id_visible = bpy.props.EnumProperty(name='uv_id_visible', description='', items=[('线面', '线面', '', 0, 0), ('线', '线', '', 0, 1), ('面', '面', '', 0, 2)])
    bpy.types.Scene.sna_uv_cid_visible_switch = bpy.props.EnumProperty(name='uv_cid_visible_switch', description='', items=[('c1', 'c1', '', 0, 0), ('c2', 'c2', '', 0, 1), ('c3', 'c3', '', 0, 2), ('c4', 'c4', '', 0, 3), ('c5', 'c5', '', 0, 4), ('c6', 'c6', '', 0, 5), ('c7', 'c7', '', 0, 6), ('c8', 'c8', '', 0, 7)])
    bpy.utils.register_class(SNA_PT_visual_inspection_tool_C051B)
    atexit.register(before_exit_handler_A594E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6Dd56)
    bpy.types.VIEW3D_MT_editor_menus.prepend(sna_add_to_view3d_mt_editor_menus_167BB)
    bpy.utils.register_class(SNA_PT_display_switching_7B93F)
    bpy.utils.register_class(SNA_OT_Lod_Level_Switch_3C8Bc)
    bpy.utils.register_class(SNA_OT_Lod_Global_Control_73Cb9)
    bpy.utils.register_class(SNA_OT_Pbr_09F62)
    bpy.utils.register_class(SNA_OT_Uv_D97B3)
    bpy.utils.register_class(SNA_OT_Uv_33067)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_00Efd)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Cb2Ef)
    bpy.utils.register_class(SNA_PT_LOD_AC2EF)
    bpy.utils.register_class(SNA_PT_collision_interface_6C4E5)
    bpy.utils.register_class(SNA_PT_UV_54E49)
    bpy.utils.register_class(SNA_PT_UV_6D02B)
    bpy.utils.register_class(SNA_PT_PBR_D1E85)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_uv_cid_visible_switch
    del bpy.types.Scene.sna_uv_id_visible
    del bpy.types.Scene.sna_uv_2_precision
    del bpy.types.Scene.sna_uv_1_precision
    del bpy.types.Scene.sna_collision_wireframe_switch
    del bpy.types.Scene.sna_lod_boundary_switch
    del bpy.types.Scene.sna_lod_wireframe_switch
    bpy.utils.unregister_class(SNA_PT_visual_inspection_tool_C051B)
    atexit.unregister(before_exit_handler_A594E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6Dd56)
    bpy.types.VIEW3D_MT_editor_menus.remove(sna_add_to_view3d_mt_editor_menus_167BB)
    bpy.utils.unregister_class(SNA_PT_display_switching_7B93F)
    bpy.utils.unregister_class(SNA_OT_Lod_Level_Switch_3C8Bc)
    bpy.utils.unregister_class(SNA_OT_Lod_Global_Control_73Cb9)
    bpy.utils.unregister_class(SNA_OT_Pbr_09F62)
    bpy.utils.unregister_class(SNA_OT_Uv_D97B3)
    bpy.utils.unregister_class(SNA_OT_Uv_33067)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_00Efd)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Cb2Ef)
    bpy.utils.unregister_class(SNA_PT_LOD_AC2EF)
    bpy.utils.unregister_class(SNA_PT_collision_interface_6C4E5)
    bpy.utils.unregister_class(SNA_PT_UV_54E49)
    bpy.utils.unregister_class(SNA_PT_UV_6D02B)
    bpy.utils.unregister_class(SNA_PT_PBR_D1E85)
