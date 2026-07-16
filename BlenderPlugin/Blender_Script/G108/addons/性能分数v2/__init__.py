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
    "name" : "Performance_score_v2",
    "author" : "qkk", 
    "description" : "",
    "blender" : (5, 0, 0),
    "version" : (2, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews
from statistics import median
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
node_tree = {'sna_folded_id': [], 'sna_pre_data_list': [], }
class SNA_PT_performance_score_3F3B7(bpy.types.Panel):
    bl_label = '性能分数2.0'
    bl_idname = 'SNA_PT_performance_score_3F3B7'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'G108'
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
        split_688A2 = layout.split(factor=0.5, align=False)
        split_688A2.alert = False
        split_688A2.enabled = True
        split_688A2.active = True
        split_688A2.use_property_split = False
        split_688A2.use_property_decorate = False
        split_688A2.scale_x = 1.0
        split_688A2.scale_y = 1.5
        split_688A2.alignment = 'Expand'.upper()
        if not True: split_688A2.operator_context = "EXEC_DEFAULT"
        op = split_688A2.operator('sna.pre_data_list_377d6', text='性能评分', icon_value=string_to_icon('ALIGN_LEFT'), emboss=True, depress=False)
        split_4EF87 = split_688A2.split(factor=0.5, align=True)
        split_4EF87.alert = False
        split_4EF87.enabled = True
        split_4EF87.active = True
        split_4EF87.use_property_split = False
        split_4EF87.use_property_decorate = False
        split_4EF87.scale_x = 1.0
        split_4EF87.scale_y = 1.0
        split_4EF87.alignment = 'Expand'.upper()
        if not True: split_4EF87.operator_context = "EXEC_DEFAULT"
        op = split_4EF87.operator('sna.open_xslx_24e53', text='分数表', icon_value=0, emboss=True, depress=False)
        split_4EF87.prop(bpy.context.scene, 'sna_reference_score', text='分数线', icon_value=0, emboss=True)
        col_095C1 = layout.column(heading='', align=True)
        col_095C1.alert = False
        col_095C1.enabled = True
        col_095C1.active = True
        col_095C1.use_property_split = False
        col_095C1.use_property_decorate = False
        col_095C1.scale_x = 1.0
        col_095C1.scale_y = 1.0
        col_095C1.alignment = 'Expand'.upper()
        col_095C1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_095C1.prop(bpy.context.scene, 'sna_obj_name_input', text='', icon_value=string_to_icon('VIEWZOOM'), emboss=True)
        col_095C1.separator(factor=1.0)
        for i_DBD38 in range(len(node_tree['sna_pre_data_list'])):
            if ((node_tree['sna_pre_data_list'][i_DBD38][0][1] > bpy.context.scene.sna_reference_score) and bpy.context.scene.sna_obj_name_input in node_tree['sna_pre_data_list'][i_DBD38][0][0]):
                box_6464A = col_095C1.box()
                box_6464A.alert = False
                box_6464A.enabled = True
                box_6464A.active = True
                box_6464A.use_property_split = False
                box_6464A.use_property_decorate = False
                box_6464A.alignment = 'Expand'.upper()
                box_6464A.scale_x = 1.0
                box_6464A.scale_y = 1.0
                if not True: box_6464A.operator_context = "EXEC_DEFAULT"
                row_DC995 = box_6464A.row(heading='', align=False)
                row_DC995.alert = False
                row_DC995.enabled = True
                row_DC995.active = True
                row_DC995.use_property_split = False
                row_DC995.use_property_decorate = False
                row_DC995.scale_x = 1.0
                row_DC995.scale_y = 1.0
                row_DC995.alignment = 'Expand'.upper()
                row_DC995.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_DC995.label(text=node_tree['sna_pre_data_list'][i_DBD38][0][0], icon_value=string_to_icon('GROUP'))
                row_6260D = row_DC995.row(heading='', align=False)
                row_6260D.alert = False
                row_6260D.enabled = True
                row_6260D.active = True
                row_6260D.use_property_split = False
                row_6260D.use_property_decorate = False
                row_6260D.scale_x = 1.0
                row_6260D.scale_y = 1.0
                row_6260D.alignment = 'Right'.upper()
                row_6260D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_6260D.label(text=str(node_tree['sna_pre_data_list'][i_DBD38][0][1]), icon_value=0)
                op = row_6260D.operator('sna.folded_id_b937a', text='', icon_value=(string_to_icon('TRIA_DOWN') if node_tree['sna_pre_data_list'][i_DBD38][0][0] in node_tree['sna_folded_id'] else string_to_icon('TRIA_LEFT')), emboss=True, depress=False)
                op.sna_pre_name = node_tree['sna_pre_data_list'][i_DBD38][0][0]
                if node_tree['sna_pre_data_list'][i_DBD38][0][0] in node_tree['sna_folded_id']:
                    row_D4E53 = box_6464A.row(heading='', align=False)
                    row_D4E53.alert = False
                    row_D4E53.enabled = True
                    row_D4E53.active = True
                    row_D4E53.use_property_split = False
                    row_D4E53.use_property_decorate = False
                    row_D4E53.scale_x = 1.0
                    row_D4E53.scale_y = 1.0
                    row_D4E53.alignment = 'Expand'.upper()
                    row_D4E53.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    row_D4E53.separator(factor=1.0)
                    row_D4E53.separator(factor=1.0)
                    col_A1ED6 = row_D4E53.column(heading='', align=True)
                    col_A1ED6.alert = False
                    col_A1ED6.enabled = True
                    col_A1ED6.active = True
                    col_A1ED6.use_property_split = False
                    col_A1ED6.use_property_decorate = False
                    col_A1ED6.scale_x = 1.0
                    col_A1ED6.scale_y = 1.0
                    col_A1ED6.alignment = 'Expand'.upper()
                    col_A1ED6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    for i_D1474 in range(len(node_tree['sna_pre_data_list'][i_DBD38][1])):
                        row_E3852 = col_A1ED6.row(heading='', align=True)
                        row_E3852.alert = False
                        row_E3852.enabled = True
                        row_E3852.active = True
                        row_E3852.use_property_split = False
                        row_E3852.use_property_decorate = False
                        row_E3852.scale_x = 1.0
                        row_E3852.scale_y = 1.0
                        row_E3852.alignment = 'Expand'.upper()
                        row_E3852.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        box_1B0D7 = row_E3852.box()
                        box_1B0D7.alert = False
                        box_1B0D7.enabled = True
                        box_1B0D7.active = True
                        box_1B0D7.use_property_split = False
                        box_1B0D7.use_property_decorate = False
                        box_1B0D7.alignment = 'Expand'.upper()
                        box_1B0D7.scale_x = 1.0
                        box_1B0D7.scale_y = 1.0
                        if not True: box_1B0D7.operator_context = "EXEC_DEFAULT"
                        op = box_1B0D7.operator('sna.select_the_model_eb449', text='', icon_value=string_to_icon('MESH_DATA'), emboss=True, depress=False)
                        op.sna_obj_name = node_tree['sna_pre_data_list'][i_DBD38][1][i_D1474][0]
                        split_2904C = row_E3852.split(factor=0.5, align=True)
                        split_2904C.alert = False
                        split_2904C.enabled = True
                        split_2904C.active = True
                        split_2904C.use_property_split = False
                        split_2904C.use_property_decorate = False
                        split_2904C.scale_x = 1.0
                        split_2904C.scale_y = 1.0
                        split_2904C.alignment = 'Expand'.upper()
                        if not True: split_2904C.operator_context = "EXEC_DEFAULT"
                        box_7EF31 = split_2904C.box()
                        box_7EF31.alert = False
                        box_7EF31.enabled = True
                        box_7EF31.active = True
                        box_7EF31.use_property_split = False
                        box_7EF31.use_property_decorate = False
                        box_7EF31.alignment = 'Expand'.upper()
                        box_7EF31.scale_x = 1.0
                        box_7EF31.scale_y = 1.0
                        if not True: box_7EF31.operator_context = "EXEC_DEFAULT"
                        box_7EF31.label(text=node_tree['sna_pre_data_list'][i_DBD38][1][i_D1474][0], icon_value=0)
                        row_7BD42 = split_2904C.row(heading='', align=True)
                        row_7BD42.alert = False
                        row_7BD42.enabled = True
                        row_7BD42.active = True
                        row_7BD42.use_property_split = False
                        row_7BD42.use_property_decorate = False
                        row_7BD42.scale_x = 1.0
                        row_7BD42.scale_y = 1.0
                        row_7BD42.alignment = 'Right'.upper()
                        row_7BD42.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        box_67BF1 = row_7BD42.box()
                        box_67BF1.alert = False
                        box_67BF1.enabled = True
                        box_67BF1.active = True
                        box_67BF1.use_property_split = False
                        box_67BF1.use_property_decorate = False
                        box_67BF1.alignment = 'Expand'.upper()
                        box_67BF1.scale_x = 1.0
                        box_67BF1.scale_y = 1.0
                        if not True: box_67BF1.operator_context = "EXEC_DEFAULT"
                        box_67BF1.label(text=str(node_tree['sna_pre_data_list'][i_DBD38][1][i_D1474][1]), icon_value=0)
                        box_15152 = row_7BD42.box()
                        box_15152.alert = False
                        box_15152.enabled = True
                        box_15152.active = True
                        box_15152.use_property_split = False
                        box_15152.use_property_decorate = False
                        box_15152.alignment = 'Expand'.upper()
                        box_15152.scale_x = 1.0
                        box_15152.scale_y = 1.0
                        if not True: box_15152.operator_context = "EXEC_DEFAULT"
                        box_15152.label(text='面：' + str(node_tree['sna_pre_data_list'][i_DBD38][1][i_D1474][2]), icon_value=0)


class SNA_OT_Folded_Id_B937A(bpy.types.Operator):
    bl_idname = "sna.folded_id_b937a"
    bl_label = "folded_id"
    bl_description = "折叠"
    bl_options = {"REGISTER", "UNDO"}
    sna_pre_name: bpy.props.StringProperty(name='pre_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if self.sna_pre_name in node_tree['sna_folded_id']:
            node_tree['sna_folded_id'].remove(self.sna_pre_name)
        else:
            node_tree['sna_folded_id'].append(self.sna_pre_name)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Pre_Data_List_377D6(bpy.types.Operator):
    bl_idname = "sna.pre_data_list_377d6"
    bl_label = "pre_data_list"
    bl_description = "获取性能分数"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree['sna_pre_data_list'] = []
        pre_data_list = None
        import math

        def get_score(obj):
            # 获取对象的面数
            tri_count = sum(len(p.vertices) - 2 for p in obj.data.polygons)
            # 获取对象的表面积
            area = sum(f.area for f in obj.data.polygons)
            # 获取对象的体积
            volume = obj.dimensions.x * obj.dimensions.y * obj.dimensions.z
            # 计算对角线长度
            diagonal_length = math.sqrt(obj.dimensions.x**2 + obj.dimensions.y**2 + obj.dimensions.z**2)
            # 计算结果
            result_1 = tri_count * (tri_count / area + tri_count / (volume + diagonal_length)) / 1000
            # 创建一个空的面积列表
            areas = []
            # 遍历对象的每个面
            for face in obj.data.loop_triangles:
                # 计算面的中位数面积
                area_each = face.area
                # 将中位数面积添加到列表中
                areas.append(area_each)
            median_value = median(areas)
            # 定义一个变量来存储结果总和
            result_2 = 0
            # 循环迭代列表areas
            for num in areas:
                if num < median_value:  # 仅处理小于A的数值
                    result = (median_value - num) / median_value  # 计算每个数值的结果
                    result_2 += result  # 将结果累加到总和中
            result_3 = int(result_1 + result_2)
            return result_3
        # 按照名称给列表排序

        def list_name():
            obj_list_name = []
            for obj in collection.objects:
                if obj.name[-5:] == '_lod0':
                    obj_list_name.append(obj.name)
            obj_list_name = sorted(obj_list_name)
            return obj_list_name
        #列表数据
        pre_data_list = []
        # 获取_pre集合
        for collection in bpy.data.collections:
            if collection.name[-4:] == '_pre': 
                obj_data_list = [] #物体数据列表
                pre_score = 0 #pre分数
                pre_triangles = 0 #pre三角面数
                # 按照名称给列表排序
                obj_list_name = list_name()
                # 循环遍历排序好的列的列表
                for obj_name in obj_list_name:
                    obj = bpy.data.objects.get(obj_name) #获取物体
                    obj_score = get_score(obj) #获取单个物体分数
                    obj_triangles = len(obj.data.loop_triangles) #获取单个物体三角面数
                    obj_data_list.append([obj.name,obj_score,obj_triangles]) #分数加入列表
                    pre_score += obj_score #pre分数所有obj分数和
                data = [[collection.name,pre_score,pre_triangles],obj_data_list] #一个pre列表数据
                pre_data_list.append(data)
        #print(pre_data_list)
        pre_data_list = sorted(pre_data_list, key=lambda x: x[0][1], reverse=True)
        #print(pre_data_list)
        #A = 面数*(面数/表面积+面数/(体积+对角线长度))/1
        node_tree['sna_pre_data_list'] = pre_data_list
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Select_The_Model_Eb449(bpy.types.Operator):
    bl_idname = "sna.select_the_model_eb449"
    bl_label = "select_the_model"
    bl_description = "选中模型"
    bl_options = {"REGISTER", "UNDO"}
    sna_obj_name: bpy.props.StringProperty(name='obj_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active = bpy.data.objects[self.sna_obj_name]
        bpy.ops.object.select_pattern(pattern=self.sna_obj_name, case_sensitive=True, extend=False)
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Open_Xslx_24E53(bpy.types.Operator):
    bl_idname = "sna.open_xslx_24e53"
    bl_label = "open_xslx"
    bl_description = "打开分数表"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        file_path = bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'score_table.xlsx'))
        os.startfile(file_path)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_reference_score = bpy.props.IntProperty(name='reference_score', description='', default=0, subtype='NONE', soft_min=0, soft_max=10000)
    bpy.types.Scene.sna_obj_name_input = bpy.props.StringProperty(name='obj_name_input', description='', default='', subtype='NONE', maxlen=0)
    bpy.utils.register_class(SNA_PT_performance_score_3F3B7)
    bpy.utils.register_class(SNA_OT_Folded_Id_B937A)
    bpy.utils.register_class(SNA_OT_Pre_Data_List_377D6)
    bpy.utils.register_class(SNA_OT_Select_The_Model_Eb449)
    bpy.utils.register_class(SNA_OT_Open_Xslx_24E53)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_obj_name_input
    del bpy.types.Scene.sna_reference_score
    bpy.utils.unregister_class(SNA_PT_performance_score_3F3B7)
    bpy.utils.unregister_class(SNA_OT_Folded_Id_B937A)
    bpy.utils.unregister_class(SNA_OT_Pre_Data_List_377D6)
    bpy.utils.unregister_class(SNA_OT_Select_The_Model_Eb449)
    bpy.utils.unregister_class(SNA_OT_Open_Xslx_24E53)
