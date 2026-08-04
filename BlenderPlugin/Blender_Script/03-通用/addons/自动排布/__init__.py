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
    "name" : "自动物体排布",
    "author" : "渠奎奎", 
    "description" : "自动物体排布",
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
g108 = {'sna_object_lis': [], 'sna_dimension': 0.0, 'sna_collection_or_select': False, 'sna_sort_x_max': 0, }
class SNA_OT_My_Generic_Operator_9808B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9808b"
    bl_label = "排布_操作性"
    bl_description = "排布物体"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        g108['sna_sort_x_max'] = 0
        for i_6B535 in range(len(g108['sna_object_lis'])):
            print(str(int(float(i_6B535 / len(g108['sna_object_lis'])) * 100.0)) + '%', '——排布主程序运行中！')
            g108['sna_dimension'] = 0.0
            for i_119DC in range(len(g108['sna_object_lis'][i_6B535])):
                x = float(bpy.context.scene.sna_starting_position[0] + int(g108['sna_sort_x_max'] * -1.0))
                y = float(bpy.context.scene.sna_starting_position[1] + g108['sna_dimension'])
                z = bpy.context.scene.sna_starting_position[2]
                # 设置3D视图中游标的位置
                bpy.context.scene.cursor.location = (x,y,z)  # 将 (x, y, z) 替换为您想要设置的位置坐标
                g108['sna_dimension'] = float(bpy.context.blend_data.objects[g108['sna_object_lis'][i_6B535][i_119DC][0]].dimensions[1] + g108['sna_dimension'] + bpy.context.scene.sna_sort__interval)
                bpy.ops.object.select_all(action='DESELECT')
                bpy.ops.object.select_pattern(pattern=g108['sna_object_lis'][i_6B535][i_119DC][0], case_sensitive=True, extend=False)
                bpy.ops.object.align('INVOKE_DEFAULT', bb_quality=True, align_mode='OPT_3', relative_to='OPT_2', align_axis={'X'})
                bpy.ops.object.align('INVOKE_DEFAULT', bb_quality=True, align_mode='OPT_1', relative_to='OPT_2', align_axis={'Y', 'Z'})
            g108['sna_sort_x_max'] = int(float(bpy.context.scene.sna_sort_row_interval + g108['sna_object_lis'][i_6B535][i_119DC][2]) + g108['sna_sort_x_max'])
        print('物体排布成功！')
        if g108['sna_collection_or_select']:
            bpy.ops.sna.my_generic_operator_b12da()
        else:
            for i_F5523 in range(len(g108['sna_object_lis'])):
                print(str(int(float(i_F5523 / len(g108['sna_object_lis'])) * 100.0)) + '%', '——获取物体中！')
                for i_DBFAE in range(len(g108['sna_object_lis'][i_F5523])):
                    bpy.ops.object.select_pattern(pattern=g108['sna_object_lis'][i_F5523][i_DBFAE][0], case_sensitive=True, extend=True)
            print('选中物体排布执行完毕！')
            bpy.ops.wm.console_toggle()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_0C541(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_0c541"
    bl_label = "列表_排序"
    bl_description = "列表_排序"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        data = g108['sna_object_lis']
        reversal = (not bpy.context.scene.sna_sort_reversal)
        row = bpy.context.scene.sna_sort_row
        new_data = None
        # 按照大小排序
        sorted_data = sorted(data, key=lambda x: x[1], reverse=reversal)
        # 拆分成多个列表
        merged_data = [sorted_data[i:i+row] for i in range(0, len(sorted_data), row)]
        # 获取每个最内部列表中第三个元素的最大值
        max_third_elements = [max(sublist[2] for sublist in inner_list) for inner_list in merged_data]
        # 将每个最内部列表中第三个元素替换为最大值
        new_data = [[[item[0], item[1], max_third_elements[i]] for item in inner_list] for i, inner_list in enumerate(merged_data)]
        g108['sna_object_lis'] = new_data
        print('列表排序成功！')
        bpy.ops.sna.my_generic_operator_9808b()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_object_arrangement_E8126(bpy.types.Panel):
    bl_label = '物体排布'
    bl_idname = 'SNA_PT_object_arrangement_E8126'
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
        box_F55B6 = layout.box()
        box_F55B6.alert = False
        box_F55B6.enabled = True
        box_F55B6.active = True
        box_F55B6.use_property_split = False
        box_F55B6.use_property_decorate = False
        box_F55B6.alignment = 'Expand'.upper()
        box_F55B6.scale_x = 1.0
        box_F55B6.scale_y = 1.0
        if not True: box_F55B6.operator_context = "EXEC_DEFAULT"
        col_128A9 = box_F55B6.column(heading='', align=False)
        col_128A9.alert = False
        col_128A9.enabled = True
        col_128A9.active = True
        col_128A9.use_property_split = False
        col_128A9.use_property_decorate = False
        col_128A9.scale_x = 1.0
        col_128A9.scale_y = 1.0
        col_128A9.alignment = 'Expand'.upper()
        col_128A9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_9A77B = col_128A9.column(heading='', align=False)
        col_9A77B.alert = False
        col_9A77B.enabled = True
        col_9A77B.active = True
        col_9A77B.use_property_split = False
        col_9A77B.use_property_decorate = False
        col_9A77B.scale_x = 1.0
        col_9A77B.scale_y = 1.0
        col_9A77B.alignment = 'Expand'.upper()
        col_9A77B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_9A77B.label(text='选中物体数量：' + str(len(list(bpy.context.view_layer.objects.selected))), icon_value=0)
        col_4F2A4 = col_9A77B.column(heading='', align=True)
        col_4F2A4.alert = False
        col_4F2A4.enabled = True
        col_4F2A4.active = True
        col_4F2A4.use_property_split = False
        col_4F2A4.use_property_decorate = False
        col_4F2A4.scale_x = 1.0
        col_4F2A4.scale_y = 1.5
        col_4F2A4.alignment = 'Expand'.upper()
        col_4F2A4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_4F2A4.operator('sna.my_generic_operator_fc7cd', text='排布选中物体', icon_value=392, emboss=True, depress=False)
        col_9002C = col_128A9.column(heading='', align=True)
        col_9002C.alert = False
        col_9002C.enabled = True
        col_9002C.active = True
        col_9002C.use_property_split = False
        col_9002C.use_property_decorate = False
        col_9002C.scale_x = 1.0
        col_9002C.scale_y = 1.0
        col_9002C.alignment = 'Expand'.upper()
        col_9002C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_9002C.prop(bpy.context.scene, 'sna_sort_reversal', text=('从小到大' if bpy.context.scene.sna_sort_reversal else '从大到小'), icon_value=0, emboss=True)
        col_9002C.prop(bpy.context.scene, 'sna_sort_row', text='每行数量', icon_value=0, emboss=True)
        col_9002C.prop(bpy.context.scene, 'sna_sort__interval', text='物体间距', icon_value=0, emboss=True)
        col_9002C.prop(bpy.context.scene, 'sna_sort_row_interval', text='每行间距', icon_value=0, emboss=True)
        row_83A8A = col_9002C.row(heading='', align=True)
        row_83A8A.alert = False
        row_83A8A.enabled = True
        row_83A8A.active = True
        row_83A8A.use_property_split = False
        row_83A8A.use_property_decorate = False
        row_83A8A.scale_x = 1.0
        row_83A8A.scale_y = 1.0
        row_83A8A.alignment = 'Expand'.upper()
        row_83A8A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_83A8A.prop(bpy.context.scene, 'sna_starting_position', text='起始位置', icon_value=0, emboss=True)
        col_9002C.prop(bpy.context.scene, 'sna_ranking_weight', text='排序权重：', icon_value=0, emboss=True)
        if bpy.context.scene.sna_ranking_weight:
            box_91FA2 = col_9002C.box()
            box_91FA2.alert = True
            box_91FA2.enabled = True
            box_91FA2.active = True
            box_91FA2.use_property_split = False
            box_91FA2.use_property_decorate = False
            box_91FA2.alignment = 'Expand'.upper()
            box_91FA2.scale_x = 1.0
            box_91FA2.scale_y = 1.0
            if not True: box_91FA2.operator_context = "EXEC_DEFAULT"
            col_1FEC1 = box_91FA2.column(heading='', align=True)
            col_1FEC1.alert = False
            col_1FEC1.enabled = True
            col_1FEC1.active = True
            col_1FEC1.use_property_split = False
            col_1FEC1.use_property_decorate = False
            col_1FEC1.scale_x = 1.0
            col_1FEC1.scale_y = 1.0
            col_1FEC1.alignment = 'Expand'.upper()
            col_1FEC1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_1FEC1.label(text='不适用集合排布！', icon_value=0)
            col_1FEC1.prop(bpy.context.scene, 'sna_volume_weight', text='体积', icon_value=0, emboss=True, slider=True)
            col_1FEC1.prop(bpy.context.scene, 'sna_length_weight', text='宽度', icon_value=0, emboss=True, slider=True)
            col_1FEC1.prop(bpy.context.scene, 'sna_area_weight', text='面积', icon_value=0, emboss=True, slider=True)
            col_1FEC1.prop(bpy.context.scene, 'sna_facenumber_weight', text='面数', icon_value=0, emboss=True, slider=True)


class SNA_OT_My_Generic_Operator_24Fec(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_24fec"
    bl_label = "开始排布"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        g108['sna_collection_or_select'] = True
        g108['sna_dimension'] = 0.0
        g108['sna_object_lis'] = []
        for i_A305C in range(len(bpy.context.scene.sna_selected_collection.children)):
            collection = bpy.context.scene.sna_selected_collection.children[i_A305C]
            obj_name = None
            size_x = None
            size_y = None
            # 获取所需集合
            #collection = bpy.data.collections['cabal_item_decoration001_pre']  # 将 'YourCollectionName' 替换为您的集合名称
            objects = [obj for obj in collection.objects if obj.type == 'MESH']
            # 计算整体包围盒尺寸
            min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
            max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
            for obj in objects:
                bbox = [obj.matrix_world @ v.co for v in obj.data.vertices]
                # 打印第一个物体的名称
                for v in bbox:
                    min_x = min(min_x, v[0])
                    min_y = min(min_y, v[1])
                    max_x = max(max_x, v[0])
                    max_y = max(max_y, v[1])
            # 计算包围盒尺寸
            size_x = max_x - min_x
            size_y = max_y - min_y
            if objects:
                obj_name = objects[0].name
            ## 打印包围盒尺寸和第一个物体的名称
            #for obj in objects:
            #    obj_name = obj.name
            #    print(obj.name)
            g108['sna_object_lis'].append([obj_name, size_y, size_x])
        print('获取集合包围盒尺寸成功成功！')
        bpy.ops.sna.my_generic_operator_0c541()
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.ops.wm.console_toggle()
        return self.execute(context)


class SNA_OT_My_Generic_Operator_B12Da(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b12da"
    bl_label = "集合内匹配"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_D2C04 in range(len(g108['sna_object_lis'])):
            print(str(int(float(i_D2C04 / len(g108['sna_object_lis'])) * 100.0)) + '%', '——处理集合！')
            for i_DA557 in range(len(g108['sna_object_lis'][i_D2C04])):
                bpy.ops.object.select_pattern(pattern=g108['sna_object_lis'][i_D2C04][i_DA557][0], case_sensitive=True, extend=False)
                bpy.context.view_layer.objects.active = bpy.data.objects[g108['sna_object_lis'][i_D2C04][i_DA557][0]]
                bpy.ops.object.select_grouped(extend=False, type='COLLECTION')
                bpy.ops.view3d.snap_selected_to_active()
                # 获取所需集合
                objects = bpy.context.selected_objects
                # 计算整体包围盒
                min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
                max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
                for obj in objects:
                    bbox = [obj.matrix_world @ v.co for v in obj.data.vertices]
                    for v in bbox:
                        min_z = min(min_z, v[2])
                        max_z = max(max_z, v[2])
                # 计算需要移动的距离
                move_z = -min_z
                # 移动所有物体，确保包围盒Z轴最底部为0
                for obj in objects:
                    obj.location.z += move_z
        print('集合排布执行完毕！')
        bpy.ops.wm.console_toggle()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Fc7Cd(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_fc7cd"
    bl_label = "排布选中物体"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        g108['sna_collection_or_select'] = False
        g108['sna_dimension'] = 0.0
        g108['sna_object_lis'] = []
        for i_B3B0A in range(len(bpy.context.view_layer.objects.selected)):
            if True:
                object_name = bpy.context.view_layer.objects.selected[i_B3B0A].name
                surface_area = None
                obj = bpy.data.objects.get(object_name)
                surface_area = sum(f.area for f in obj.data.polygons)
                g108['sna_object_lis'].append([bpy.context.view_layer.objects.selected[i_B3B0A].name, float(float(float(bpy.context.view_layer.objects.selected[i_B3B0A].dimensions[0] * bpy.context.view_layer.objects.selected[i_B3B0A].dimensions[1] * bpy.context.view_layer.objects.selected[i_B3B0A].dimensions[2]) * bpy.context.scene.sna_volume_weight) + float(bpy.context.view_layer.objects.selected[i_B3B0A].dimensions[1] * bpy.context.scene.sna_length_weight * 5.0) + float(surface_area * bpy.context.scene.sna_area_weight) + float(len(list(bpy.context.view_layer.objects.selected[i_B3B0A].data.loop_triangle_polygons)) * bpy.context.scene.sna_facenumber_weight)), bpy.context.view_layer.objects.selected[i_B3B0A].dimensions[0]])
        bpy.ops.sna.my_generic_operator_0c541()
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.ops.wm.console_toggle()
        return self.execute(context)


class SNA_PT_set_arrangement_4514E(bpy.types.Panel):
    bl_label = '集合排布'
    bl_idname = 'SNA_PT_set_arrangement_4514E'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_object_arrangement_E8126'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        box_68C67 = layout.box()
        box_68C67.alert = False
        box_68C67.enabled = True
        box_68C67.active = True
        box_68C67.use_property_split = False
        box_68C67.use_property_decorate = False
        box_68C67.alignment = 'Expand'.upper()
        box_68C67.scale_x = 1.0
        box_68C67.scale_y = 1.0
        if not True: box_68C67.operator_context = "EXEC_DEFAULT"
        col_82AB4 = box_68C67.column(heading='', align=False)
        col_82AB4.alert = False
        col_82AB4.enabled = True
        col_82AB4.active = True
        col_82AB4.use_property_split = False
        col_82AB4.use_property_decorate = False
        col_82AB4.scale_x = 1.0
        col_82AB4.scale_y = 1.0
        col_82AB4.alignment = 'Expand'.upper()
        col_82AB4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_FE5BA = col_82AB4.column(heading='', align=False)
        col_FE5BA.alert = False
        col_FE5BA.enabled = True
        col_FE5BA.active = True
        col_FE5BA.use_property_split = False
        col_FE5BA.use_property_decorate = False
        col_FE5BA.scale_x = 1.0
        col_FE5BA.scale_y = 1.5
        col_FE5BA.alignment = 'Expand'.upper()
        col_FE5BA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_FE5BA.operator('sna.my_generic_operator_24fec', text='G108排布集合', icon_value=581, emboss=True, depress=False)
        col_82AB4.prop(bpy.context.scene, 'sna_selected_collection', text='主集合', icon_value=0, emboss=True)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_selected_collection = bpy.props.PointerProperty(name='selected_collection', description='', type=bpy.types.Collection)
    bpy.types.Scene.sna_sort_reversal = bpy.props.BoolProperty(name='sort_reversal', description='', default=False)
    bpy.types.Scene.sna_sort_row = bpy.props.IntProperty(name='sort_row', description='', default=20, subtype='NONE', soft_min=10, soft_max=200)
    bpy.types.Scene.sna_sort_row_interval = bpy.props.FloatProperty(name='sort_row_interval', description='', default=1.0, subtype='DISTANCE', unit='NONE', soft_min=0.0, soft_max=20.0, step=1, precision=2)
    bpy.types.Scene.sna_sort__interval = bpy.props.FloatProperty(name='sort _interval', description='', default=1.0, subtype='DISTANCE', unit='NONE', soft_min=0.0, soft_max=20.0, step=1, precision=2)
    bpy.types.Scene.sna_starting_position = bpy.props.FloatVectorProperty(name='starting_position', description='', size=3, default=(0.0, 0.0, 0.0), subtype='NONE', unit='NONE', step=1, precision=2)
    bpy.types.Scene.sna_volume_weight = bpy.props.FloatProperty(name='volume_weight', description='', default=1.0, subtype='NONE', unit='NONE', min=0.0, soft_max=10.0, step=1, precision=2)
    bpy.types.Scene.sna_length_weight = bpy.props.FloatProperty(name='length_weight', description='', default=1.0, subtype='NONE', unit='NONE', min=0.0, soft_max=10.0, step=1, precision=2)
    bpy.types.Scene.sna_area_weight = bpy.props.FloatProperty(name='area_weight', description='', default=1.0, subtype='NONE', unit='NONE', min=0.0, soft_max=10.0, step=1, precision=2)
    bpy.types.Scene.sna_facenumber_weight = bpy.props.FloatProperty(name='facenumber_weight', description='', default=0.0, subtype='NONE', unit='NONE', min=0.0, soft_max=10.0, step=1, precision=2)
    bpy.types.Scene.sna_ranking_weight = bpy.props.BoolProperty(name='ranking_weight', description='', default=False)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9808B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_0C541)
    bpy.utils.register_class(SNA_PT_object_arrangement_E8126)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_24Fec)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B12Da)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Fc7Cd)
    bpy.utils.register_class(SNA_PT_set_arrangement_4514E)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_ranking_weight
    del bpy.types.Scene.sna_facenumber_weight
    del bpy.types.Scene.sna_area_weight
    del bpy.types.Scene.sna_length_weight
    del bpy.types.Scene.sna_volume_weight
    del bpy.types.Scene.sna_starting_position
    del bpy.types.Scene.sna_sort__interval
    del bpy.types.Scene.sna_sort_row_interval
    del bpy.types.Scene.sna_sort_row
    del bpy.types.Scene.sna_sort_reversal
    del bpy.types.Scene.sna_selected_collection
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9808B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_0C541)
    bpy.utils.unregister_class(SNA_PT_object_arrangement_E8126)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_24Fec)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B12Da)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Fc7Cd)
    bpy.utils.unregister_class(SNA_PT_set_arrangement_4514E)
