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
    "name" : "Model_normalization",
    "author" : "渠奎奎", 
    "description" : "G108_模型规整",
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
import math
import time, sys


addon_keymaps = {}
_icons = None
node_tree = {'sna_sna_new_variable': [], }
node_tree = {'sna_mat__caoid': 0, 'sna_mat_id': 0, 'sna_mat_jilu': [], }
node_tree_001 = {'sna_obj_name_list': [], }
node_tree_002 = {'sna_obj_name_list': [], 'sna_obj_location': None, }
node_tree_001 = {'sna_lod_matname': '', 'sna_new_matname': '', }
pre = {'sna_pre_mod_name': [], 'sna_pre_progress': 0.0, }
c1c2 = {'sna_chucun': '', 'sna_liebiao': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_PT_main_panel_1CA4E(bpy.types.Panel):
    bl_label = '模型规整'
    bl_idname = 'SNA_PT_main_panel_1CA4E'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '便捷功能'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout


class SNA_OT_My_Generic_Operator_969F9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_969f9"
    bl_label = "一键清理相似"
    bl_description = "一键清理相似"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.console_toggle()
        if bpy.context.scene.sna_clear_position:
            bpy.ops.object.location_clear()
            print('清空位置')
        if bpy.context.scene.sna_clear_zoom:
            bpy.ops.object.scale_clear()
            print('清空缩放')
        if bpy.context.scene.sna_clear_rotation:
            for i_BD316 in range(len(bpy.context.view_layer.objects.selected)):
                bpy.context.view_layer.objects.selected[i_BD316].rotation_euler = (math.radians(bpy.context.scene.sna_rotation_value[0]), math.radians(bpy.context.scene.sna_rotation_value[1]), math.radians(bpy.context.scene.sna_rotation_value[2]))
            print('清空旋转')
        node_tree['sna_sna_new_variable'] = []
        for i_8041E in range(len(bpy.context.view_layer.objects.selected)):
            if (bpy.context.view_layer.objects.selected[i_8041E].data.id_data.id_type == 'MESH'):
                node_tree['sna_sna_new_variable'].append(bpy.context.view_layer.objects.selected[i_8041E])
        print('处理资产数量：', str(len(node_tree['sna_sna_new_variable'])))
        for i_3E4FF in range(len(node_tree['sna_sna_new_variable'])):
            i = float(int(i_3E4FF + 1.0) / len(node_tree['sna_sna_new_variable']))

            def update_progress(progress):
                length = 30
                block = int(round(length*progress))
                msg = "\r{0}  {1}%".format("█"*block + " "*(length-block), round(progress*100))
                sys.stdout.write(msg)
            update_progress(i)
            if property_exists("node_tree['sna_sna_new_variable'][i_3E4FF].name", globals(), locals()):
                bpy.ops.object.select_all(action='DESELECT')
                bpy.context.view_layer.objects.active = node_tree['sna_sna_new_variable'][i_3E4FF]
                if bpy.context.scene.sna_complete_similarity_switch:
                    # 选择要比较的基准模型
                    base_object = bpy.context.active_object
                    # 遍历场景中的所有对象
                    for obj in bpy.context.scene.objects:
                        # 排除基准模型和已经选择的对象
                        if obj != base_object and not obj.select_get():
                            # 比较模型的某些属性（可根据需求进行修改）
                            if (obj.data.vertices[0].co.x == base_object.data.vertices[0].co.x and
                                obj.data.vertices[0].co.y == base_object.data.vertices[0].co.y and
                                obj.data.vertices[0].co.z == base_object.data.vertices[0].co.z and
                                obj.data.vertices[1].co.x == base_object.data.vertices[1].co.x and
                                obj.data.vertices[1].co.y == base_object.data.vertices[1].co.y and
                                obj.data.vertices[1].co.z == base_object.data.vertices[1].co.z and
                                obj.data.vertices[2].co.x == base_object.data.vertices[2].co.x and
                                obj.data.vertices[2].co.y == base_object.data.vertices[2].co.y and
                                obj.data.vertices[2].co.z == base_object.data.vertices[2].co.z and
                                len(obj.data.vertices) ==  len(base_object.data.vertices) and
                                len(obj.data.edges) ==  len(base_object.data.edges) and
                                len(obj.data.polygons) ==  len(base_object.data.polygons) and
                                len(obj.data.uv_layers) ==  len(base_object.data.uv_layers) and
                                len(obj.material_slots) ==  len(base_object.material_slots)            
                                ):
                                # 选择相似的模型
                                obj.select_set(True)
                    bpy.ops.object.delete(use_global=True, confirm=False)
                else:
                    # 选择要比较的基准模型
                    base_object = bpy.context.active_object
                    # 遍历场景中的所有对象
                    for obj in bpy.context.scene.objects:
                        # 排除基准模型和已经选择的对象
                        if obj != base_object and not obj.select_get():
                            # 比较模型的某些属性（可根据需求进行修改）
                            if (            
                                len(obj.data.vertices) ==  len(base_object.data.vertices) and
                                len(obj.data.edges) ==  len(base_object.data.edges) and
                                len(obj.data.polygons) ==  len(base_object.data.polygons) and
                                len(obj.data.uv_layers) ==  len(base_object.data.uv_layers) and
                                len(obj.material_slots) ==  len(base_object.material_slots)
                                ):
                                # 选择相似的模型
                                obj.select_set(True)
                    bpy.ops.object.delete(use_global=True, confirm=False)
        bpy.ops.wm.console_toggle()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_2675B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2675b"
    bl_label = "运行"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def invoke(self, context, event):
        bpy.ops.object.material_slot_remove_unused() # 清理空材质槽

        objects = bpy.context.view_layer.objects # 视图物体
        obj_name_list = [] # 物体名称列表
        # 循环储存选中的物体名称到列表
        for obj in objects.selected:
            obj_name_list.append(obj.name)

        bpy.ops.object.select_all(action='DESELECT') # 取消选择

        # 循环获取物体
        for obj_name in obj_name_list:
            obj = bpy.data.objects[obj_name] # 按名称获取物体
            objects.active = obj # 设置当前激活物体
            obj.select_set(True) # 选中模型
            mat_slot_ids = len(obj.material_slots) # 材质槽数量
            bpy.ops.object.mode_set(mode='EDIT') # 进入编辑模型

            # 循环获取材质槽
            for slots_id in range(mat_slot_ids):
                bpy.ops.mesh.select_all(action='DESELECT') # 取消mesh选择
                # 循环获取材质槽
                for id in range(mat_slot_ids):
                    obj.active_material_index = id # 设置当前激活的材质槽
                    # 判断当前材质槽名称是否相同
                    if (obj.material_slots[slots_id].name == obj.material_slots[id].name):
                        bpy.ops.object.material_slot_select() # 按材质槽选择面

                obj.active_material_index = slots_id # 设置当前激活的材质槽
                bpy.ops.object.material_slot_assign() # 将选中的面设置当前激活的材质槽
                bpy.ops.mesh.select_all(action='DESELECT') # 取消面选择

            bpy.ops.object.mode_set(mode='OBJECT') # 进入物体模式
            bpy.ops.object.material_slot_remove_unused() # 清理空材质槽
            obj.select_set(False) # 取消选中模型
        return {"FINISHED"}


class SNA_OT_My_Generic_Operator_B68F1(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b68f1"
    bl_label = "按名称删除操作性"
    bl_description = "按名称删除"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree_001['sna_obj_name_list'] = []
        for i_FDDAA in range(len(bpy.context.view_layer.objects.selected)):
            node_tree_001['sna_obj_name_list'].append(bpy.context.view_layer.objects.selected[i_FDDAA].name)
        for i_B6E39 in range(len(node_tree_001['sna_obj_name_list'])):
            for i_0C440 in range(len(bpy.context.scene.sna_clear_name.split(','))):
                if bpy.context.scene.sna_clear_name.split(',')[i_0C440] in node_tree_001['sna_obj_name_list'][i_B6E39]:
                    bpy.context.blend_data.objects.remove(object=bpy.data.objects[node_tree_001['sna_obj_name_list'][i_B6E39]], )
                    print('删除：', node_tree_001['sna_obj_name_list'][i_B6E39])
                    break
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        self.report({'INFO'}, message='删除成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_9D201(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9d201"
    bl_label = "检测"
    bl_description = "检测"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree_002['sna_obj_name_list'] = []
        for i_80BB1 in range(len(bpy.context.scene.collection.children)):
            if '_pre' in bpy.context.scene.collection.children[i_80BB1].name:
                node_tree_002['sna_obj_location'] = None
                for i_BB39B in range(len(bpy.context.scene.collection.children[i_80BB1].all_objects)):
                    if (None == node_tree_002['sna_obj_location']):
                        node_tree_002['sna_obj_location'] = bpy.context.scene.collection.children[i_80BB1].all_objects[i_BB39B].location
                    if (node_tree_002['sna_obj_location'] != bpy.context.scene.collection.children[i_80BB1].all_objects[i_BB39B].location):
                        node_tree_002['sna_obj_name_list'].append(bpy.context.scene.collection.children[i_80BB1].all_objects[i_BB39B].name)
                        break
        self.report({'INFO'}, message='问题数量=' + str(len(node_tree_002['sna_obj_name_list'])))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_611C7(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_611c7"
    bl_label = "选择"
    bl_description = "选择"
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
        self.report({'INFO'}, message='ok!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_74Db1(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_74db1"
    bl_label = "清理"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_F9446 in range(len(bpy.context.view_layer.objects.selected)):
            for i_4214E in range(len(bpy.context.view_layer.objects.selected[i_F9446].material_slots)):
                if '.0' in bpy.context.view_layer.objects.selected[i_F9446].material_slots[i_4214E].material.name[-4:]:
                    node_tree_001['sna_lod_matname'] = bpy.context.view_layer.objects.selected[i_F9446].material_slots[i_4214E].material.name
                    node_tree_001['sna_new_matname'] = bpy.context.view_layer.objects.selected[i_F9446].material_slots[i_4214E].material.name[:-4]
                    if property_exists("bpy.data.materials[bpy.context.view_layer.objects.selected[i_F9446].material_slots[i_4214E].material.name[:-4]]", globals(), locals()):
                        bpy.context.view_layer.objects.selected[i_F9446].material_slots[i_4214E].material = bpy.data.materials[bpy.context.view_layer.objects.selected[i_F9446].material_slots[i_4214E].material.name[:-4]]
                        self.report({'INFO'}, message=node_tree_001['sna_lod_matname'] + '替换为' + node_tree_001['sna_new_matname'])
                    else:
                        bpy.context.view_layer.objects.selected[i_F9446].material_slots[i_4214E].material.name = bpy.context.view_layer.objects.selected[i_F9446].material_slots[i_4214E].material.name[:-4]
                        self.report({'INFO'}, message=node_tree_001['sna_lod_matname'] + '重命名' + node_tree_001['sna_new_matname'])
            bpy.ops.outliner.orphans_purge(do_recursive=True)
            node_tree_001['sna_lod_matname'] = ''
            node_tree_001['sna_new_matname'] = ''
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_6Ec18(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6ec18"
    bl_label = "清理.0贴图"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_9217B in range(len(bpy.data.images)):
            if '.0' in bpy.data.images[i_9217B].name[-4:]:
                old = bpy.data.images[i_9217B].name
                new = bpy.data.images[i_9217B].name[:-4]
                result = None
                # 要替换的贴图名称
                old_texture_name = old
                # 新的贴图名称
                new_texture_name = new
                # 存储转换结果的列表
                result_list = []
                # 遍历场景中的所有材质
                for material in bpy.data.materials:
                    # 检查材质是否有节点树
                    if material.use_nodes:
                        # 遍历节点树中的所有节点
                        for node in material.node_tree.nodes:
                            # 检查节点是否为图像节点并且图像名称匹配
                            if node.type == 'TEX_IMAGE' and node.image is not None and node.image.name == old_texture_name:
                                # 查找新的贴图
                                new_image = bpy.data.images.get(new_texture_name)
                                if new_image is None:
                                    # 如果没有找到新的贴图，则将旧的贴图重命名为新的贴图名称
                                    node.image.name = new_texture_name
                                    result_list.append(f"{old_texture_name} 重命名 {new_texture_name}")
                                else:
                                    # 否则将节点的贴图替换为新的贴图
                                    node.image = new_image
                                    result_list.append(f"{old_texture_name} 替换为 {new_texture_name}")
                # 输出转换结果
                for result in result_list:
                    print(result)
                self.report({'INFO'}, message=result)
        bpy.ops.outliner.orphans_purge(do_recursive=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_B88A9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b88a9"
    bl_label = "清理材质槽"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_D1C22 in range(len(bpy.context.view_layer.objects.selected)):
            bpy.ops.object.material_slot_remove_unused()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_8E302():
    pre['sna_pre_mod_name'] = []
    for i_3FFE8 in range(len(bpy.context.view_layer.objects.selected)):
        pre['sna_pre_mod_name'].append(bpy.context.view_layer.objects.selected[i_3FFE8].name.replace('_autophy_s', '').replace('_autophy', '').replace('_c1_', '').replace('_c2_', '').replace('_c3_', '').replace('_c4_', '').replace('_c5_', '').replace('_c6_', '').replace('_c7_', '').replace('_c14_', '').replace('_c13_', '').replace('_c12_', '').replace('_c11_', '').replace('_c10_', '').replace('_c9_', '').replace('_c8_', '').replace('_c20_', '').replace('_c19_', '').replace('_c18_', '').replace('_c17_', '').replace('_c16_', '').replace('_c15_', '').replace('_lod6', '').replace('_lod5', '').replace('_lod4', '').replace('_lod3', '').replace('_lod2', '').replace('_lod1', '').replace('_lod0', '').replace('lod6', '').replace('lod5', '').replace('lod4', '').replace('lod3', '').replace('lod2', '').replace('lod1', '').replace('lod0', ''))
    original_list = pre['sna_pre_mod_name']
    unique_items = None
    unique_items = list(set(original_list))
    return unique_items


def sna_func_09BED(original_list):
    for i_4800A in range(len(original_list)):
        if property_exists("bpy.data.collections[original_list[i_4800A] + '_pre']", globals(), locals()):
            print('已经存在集合：', original_list[i_4800A] + '_pre')
        else:
            collection_name = original_list[i_4800A] + '_pre'
            # 创建一个新的集合
            new_collection = bpy.data.collections.new(collection_name)
            # 将新集合添加到场景中
            bpy.context.scene.collection.children.link(new_collection)
    return original_list


def sna_func_766AB(pre_mod_name):
    for i_45C99 in range(len(pre_mod_name)):
        for i_7D976 in range(len(bpy.context.view_layer.objects.selected)):
            if pre_mod_name[i_45C99] in bpy.context.view_layer.objects.selected[i_7D976].name:
                mod_name = bpy.context.view_layer.objects.selected[i_7D976].name
                collection_name = pre_mod_name[i_45C99] + '_pre'
                # 指定物体名称和目标集合名称
                object_name = mod_name  # 更改为您要移动的物体的名称
                target_collection_name = collection_name  # 更改为目标集合的名称
                # 获取要移动的物体和目标集合
                obj = bpy.data.objects.get(object_name)
                target_collection = bpy.data.collections.get(target_collection_name)
                # 如果找到物体和目标集合，则将物体移动到目标集合
                if obj and target_collection:
                    if obj.users_collection:
                        for collection in obj.users_collection:
                            collection.objects.unlink(obj)
                    target_collection.objects.link(obj)
                else:
                    print("未找到指定的物体或目标集合")
    return


class SNA_OT_Pre_20C0A(bpy.types.Operator):
    bl_idname = "sna.pre_20c0a"
    bl_label = "自动_pre操作项"
    bl_description = "自动_pre操作项"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        pre['sna_pre_progress'] = 0.0
        pre_mod_name_0_25117 = sna_func_8E302()
        pre['sna_pre_progress'] = 0.30000001192092896

        def delayed_BB70E():
            original_list_0_137e9 = sna_func_09BED(pre_mod_name_0_25117)
            pre['sna_pre_progress'] = 0.6000000238418579

            def delayed_E8ABA():
                sna_func_766AB(original_list_0_137e9)
                pre['sna_pre_progress'] = 1.0

                def delayed_17755():
                    pre['sna_pre_progress'] = 0.0
                    if bpy.context and bpy.context.screen:
                        for a in bpy.context.screen.areas:
                            a.tag_redraw()
                bpy.app.timers.register(delayed_17755, first_interval=0.10000000149011612)
            bpy.app.timers.register(delayed_E8ABA, first_interval=0.05000000074505806)
        bpy.app.timers.register(delayed_BB70E, first_interval=0.05000000074505806)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_4F651(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_4f651"
    bl_label = "命名"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_1886C in range(len(bpy.context.view_layer.objects.selected)):
            bpy.context.view_layer.objects.selected[i_1886C].name = '' + bpy.context.scene.sna_name_qiming00 + str((str('0000' + str(int(i_1886C + 1.0)))[int(len(str(int(i_1886C + 1.0))) + int(4.0 - bpy.context.scene.sna_name_qiming01_weishu)):] if bpy.context.scene.sna_name_qiming01_paixiu else bpy.context.scene.sna_name_qiming01)) + bpy.context.scene.sna_name_qiming02 + str((int(i_1886C + 1.0) if bpy.context.scene.sna_name_weizhui_switch else ''))
            bpy.context.view_layer.objects.selected[i_1886C].data.name = '' + bpy.context.scene.sna_name_qiming00 + str((str('0000' + str(int(i_1886C + 1.0)))[int(len(str(int(i_1886C + 1.0))) + int(4.0 - bpy.context.scene.sna_name_qiming01_weishu)):] if bpy.context.scene.sna_name_qiming01_paixiu else bpy.context.scene.sna_name_qiming01)) + bpy.context.scene.sna_name_qiming02 + str((int(i_1886C + 1.0) if bpy.context.scene.sna_name_weizhui_switch else '')) + '_mesh'
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_41Ba9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_41ba9"
    bl_label = "自动拆分命名"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        c1c2['sna_liebiao'] = []
        for i_4E6EA in range(len(bpy.context.view_layer.objects.selected)):
            c1c2['sna_liebiao'].append(bpy.context.view_layer.objects.selected[i_4E6EA].name)
        bpy.ops.object.select_all(action='DESELECT')
        for i_62AFA in range(len(c1c2['sna_liebiao'])):
            bpy.ops.object.select_pattern(pattern=c1c2['sna_liebiao'][i_62AFA], case_sensitive=True, extend=False)
            bpy.context.view_layer.objects.active = bpy.data.objects[c1c2['sna_liebiao'][i_62AFA]]
            bpy.ops.mesh.separate(type='MATERIAL')
            c1c2['sna_chucun'] = bpy.context.view_layer.objects.active.name
            for i_1F4D7 in range(len(bpy.context.view_layer.objects.selected)):
                bpy.context.view_layer.objects.selected[i_1F4D7].name = c1c2['sna_chucun'] + '_c' + str(int(i_1F4D7 + 1.0)) + '_lod0'
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_2Cec5(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2cec5"
    bl_label = "相似模型"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        if bpy.context.scene.sna_complete_similarity_switch:
            # 选择要比较的基准模型
            base_object = bpy.context.active_object
            # 遍历场景中的所有对象
            for obj in bpy.context.scene.objects:
                # 排除基准模型和已经选择的对象
                if obj != base_object and not obj.select_get():
                    # 比较模型的某些属性（可根据需求进行修改）
                    if (obj.data.vertices[0].co.x == base_object.data.vertices[0].co.x and
                        obj.data.vertices[0].co.y == base_object.data.vertices[0].co.y and
                        obj.data.vertices[0].co.z == base_object.data.vertices[0].co.z and
                        obj.data.vertices[1].co.x == base_object.data.vertices[1].co.x and
                        obj.data.vertices[1].co.y == base_object.data.vertices[1].co.y and
                        obj.data.vertices[1].co.z == base_object.data.vertices[1].co.z and
                        obj.data.vertices[2].co.x == base_object.data.vertices[2].co.x and
                        obj.data.vertices[2].co.y == base_object.data.vertices[2].co.y and
                        obj.data.vertices[2].co.z == base_object.data.vertices[2].co.z and
                        len(obj.data.vertices) ==  len(base_object.data.vertices) and
                        len(obj.data.edges) ==  len(base_object.data.edges) and
                        len(obj.data.polygons) ==  len(base_object.data.polygons) and
                        len(obj.data.uv_layers) ==  len(base_object.data.uv_layers) and
                        len(obj.material_slots) ==  len(base_object.material_slots)            
                        ):
                        # 选择相似的模型
                        obj.select_set(True)
        else:
            if bpy.context.scene.sna_complete_uvmat_switch:
                # 选择要比较的基准模型
                base_object = bpy.context.active_object
                # 遍历场景中的所有对象
                for obj in bpy.context.scene.objects:
                    # 排除基准模型和已经选择的对象
                    if obj != base_object and not obj.select_get():
                        # 比较模型的某些属性（可根据需求进行修改）
                        if (            
                            len(obj.data.vertices) ==  len(base_object.data.vertices) and
                            len(obj.data.edges) ==  len(base_object.data.edges) and
                            len(obj.data.polygons) ==  len(base_object.data.polygons) and
                            len(obj.data.uv_layers) ==  len(base_object.data.uv_layers) and
                            len(obj.material_slots) ==  len(base_object.material_slots)
                            ):
                            # 选择相似的模型
                            obj.select_set(True)
            else:
                # 选择要比较的基准模型
                base_object = bpy.context.active_object
                # 遍历场景中的所有对象
                for obj in bpy.context.scene.objects:
                    # 排除基准模型和已经选择的对象
                    if obj != base_object and not obj.select_get():
                        # 比较模型的某些属性（可根据需求进行修改）
                        if (            
                            len(obj.data.vertices) ==  len(base_object.data.vertices) and
                            len(obj.data.edges) ==  len(base_object.data.edges) and
                            len(obj.data.polygons) ==  len(base_object.data.polygons)
                            ):
                            # 选择相似的模型
                            obj.select_set(True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_delete_similarity_B2D20(bpy.types.Panel):
    bl_label = '一键清理相似'
    bl_idname = 'SNA_PT_delete_similarity_B2D20'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 10
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_E3DBF = layout.column(heading='', align=True)
        col_E3DBF.alert = False
        col_E3DBF.enabled = True
        col_E3DBF.active = True
        col_E3DBF.use_property_split = False
        col_E3DBF.use_property_decorate = False
        col_E3DBF.scale_x = 1.0
        col_E3DBF.scale_y = 1.0
        col_E3DBF.alignment = 'Expand'.upper()
        col_E3DBF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_52D8D = col_E3DBF.column(heading='', align=True)
        col_52D8D.alert = False
        col_52D8D.enabled = True
        col_52D8D.active = True
        col_52D8D.use_property_split = False
        col_52D8D.use_property_decorate = False
        col_52D8D.scale_x = 1.0
        col_52D8D.scale_y = 2.0
        col_52D8D.alignment = 'Expand'.upper()
        col_52D8D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_52D8D.operator('sna.my_generic_operator_969f9', text='一键清理相似', icon_value=21, emboss=True, depress=False)
        col_E3DBF.prop(bpy.context.scene, 'sna_complete_similarity_switch', text='开启顶点位置判断', icon_value=0, emboss=True)
        box_17716 = layout.box()
        box_17716.alert = False
        box_17716.enabled = True
        box_17716.active = True
        box_17716.use_property_split = False
        box_17716.use_property_decorate = False
        box_17716.alignment = 'Expand'.upper()
        box_17716.scale_x = 1.0
        box_17716.scale_y = 1.0
        if not True: box_17716.operator_context = "EXEC_DEFAULT"
        col_04EA0 = box_17716.column(heading='', align=False)
        col_04EA0.alert = False
        col_04EA0.enabled = True
        col_04EA0.active = True
        col_04EA0.use_property_split = False
        col_04EA0.use_property_decorate = False
        col_04EA0.scale_x = 1.0
        col_04EA0.scale_y = 1.0
        col_04EA0.alignment = 'Expand'.upper()
        col_04EA0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_04EA0.prop(bpy.context.scene, 'sna_clear_position', text='清空位置', icon_value=0, emboss=True)
        col_04EA0.prop(bpy.context.scene, 'sna_clear_zoom', text='清空缩放', icon_value=0, emboss=True)
        col_04EA0.prop(bpy.context.scene, 'sna_clear_rotation', text='清空旋转', icon_value=0, emboss=True)
        row_7A518 = col_04EA0.row(heading='', align=True)
        row_7A518.alert = False
        row_7A518.enabled = True
        row_7A518.active = True
        row_7A518.use_property_split = False
        row_7A518.use_property_decorate = False
        row_7A518.scale_x = 1.0
        row_7A518.scale_y = 1.0
        row_7A518.alignment = 'Expand'.upper()
        row_7A518.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_7A518.prop(bpy.context.scene, 'sna_rotation_value', text='', icon_value=0, emboss=True)


class SNA_PT_merge_material_DBA1D(bpy.types.Panel):
    bl_label = '合并同名材质槽'
    bl_idname = 'SNA_PT_merge_material_DBA1D'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_3F25C = layout.column(heading='', align=False)
        col_3F25C.alert = False
        col_3F25C.enabled = True
        col_3F25C.active = True
        col_3F25C.use_property_split = False
        col_3F25C.use_property_decorate = False
        col_3F25C.scale_x = 1.0
        col_3F25C.scale_y = 1.2999999523162842
        col_3F25C.alignment = 'Expand'.upper()
        col_3F25C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_3F25C.operator('sna.my_generic_operator_2675b', text='合并同名材质槽', icon_value=0, emboss=True, depress=False)


class SNA_PT_delete_by_name_94C31(bpy.types.Panel):
    bl_label = '按名称删除'
    bl_idname = 'SNA_PT_delete_by_name_94C31'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 11
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_E3BF1 = layout.column(heading='', align=False)
        col_E3BF1.alert = False
        col_E3BF1.enabled = True
        col_E3BF1.active = True
        col_E3BF1.use_property_split = False
        col_E3BF1.use_property_decorate = False
        col_E3BF1.scale_x = 1.0
        col_E3BF1.scale_y = 1.0
        col_E3BF1.alignment = 'Expand'.upper()
        col_E3BF1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_D3C51 = col_E3BF1.column(heading='', align=False)
        col_D3C51.alert = False
        col_D3C51.enabled = True
        col_D3C51.active = True
        col_D3C51.use_property_split = False
        col_D3C51.use_property_decorate = False
        col_D3C51.scale_x = 1.0
        col_D3C51.scale_y = 2.0
        col_D3C51.alignment = 'Expand'.upper()
        col_D3C51.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_D3C51.operator('sna.my_generic_operator_b68f1', text='按名称删除', icon_value=21, emboss=True, depress=False)
        col_E3BF1.label(text='选中：' + str(len(bpy.context.view_layer.objects.selected)), icon_value=235)
        col_66CF4 = col_E3BF1.column(heading='', align=True)
        col_66CF4.alert = False
        col_66CF4.enabled = True
        col_66CF4.active = True
        col_66CF4.use_property_split = False
        col_66CF4.use_property_decorate = False
        col_66CF4.scale_x = 1.0
        col_66CF4.scale_y = 1.0
        col_66CF4.alignment = 'Expand'.upper()
        col_66CF4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_66CF4.prop(bpy.context.scene, 'sna_clear_name', text='', icon_value=0, emboss=True)
        box_549F2 = col_66CF4.box()
        box_549F2.alert = False
        box_549F2.enabled = True
        box_549F2.active = True
        box_549F2.use_property_split = False
        box_549F2.use_property_decorate = False
        box_549F2.alignment = 'Expand'.upper()
        box_549F2.scale_x = 1.0
        box_549F2.scale_y = 1.0
        if not True: box_549F2.operator_context = "EXEC_DEFAULT"
        col_87178 = box_549F2.column(heading='', align=True)
        col_87178.alert = False
        col_87178.enabled = True
        col_87178.active = True
        col_87178.use_property_split = False
        col_87178.use_property_decorate = False
        col_87178.scale_x = 1.0
        col_87178.scale_y = 1.0
        col_87178.alignment = 'Expand'.upper()
        col_87178.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        for i_89339 in range(len(bpy.context.scene.sna_clear_name.split(','))):
            col_87178.label(text='删除' + '：' + bpy.context.scene.sna_clear_name.split(',')[i_89339], icon_value=0)


class SNA_PT_check_coordinate_synchronization_status_0025F(bpy.types.Panel):
    bl_label = '检测坐标同步情况'
    bl_idname = 'SNA_PT_check_coordinate_synchronization_status_0025F'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        op = layout.operator('sna.my_generic_operator_9d201', text='检测', icon_value=0, emboss=True, depress=False)
        for i_D02B7 in range(len(node_tree_002['sna_obj_name_list'])):
            box_E517D = layout.box()
            box_E517D.alert = False
            box_E517D.enabled = True
            box_E517D.active = True
            box_E517D.use_property_split = False
            box_E517D.use_property_decorate = False
            box_E517D.alignment = 'Expand'.upper()
            box_E517D.scale_x = 1.0
            box_E517D.scale_y = 1.0
            if not True: box_E517D.operator_context = "EXEC_DEFAULT"
            col_FBF09 = box_E517D.column(heading='', align=True)
            col_FBF09.alert = True
            col_FBF09.enabled = True
            col_FBF09.active = True
            col_FBF09.use_property_split = False
            col_FBF09.use_property_decorate = False
            col_FBF09.scale_x = 1.0
            col_FBF09.scale_y = 1.0
            col_FBF09.alignment = 'Expand'.upper()
            col_FBF09.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_FBF09.operator('sna.my_generic_operator_611c7', text=node_tree_002['sna_obj_name_list'][i_D02B7], icon_value=0, emboss=True, depress=False)
            op.sna_obj_name = node_tree_002['sna_obj_name_list'][i_D02B7]


class SNA_PT_clean_material_17646(bpy.types.Panel):
    bl_label = '清理名称  .0  材质'
    bl_idname = 'SNA_PT_clean_material_17646'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_203DB = layout.column(heading='', align=False)
        col_203DB.alert = False
        col_203DB.enabled = True
        col_203DB.active = True
        col_203DB.use_property_split = False
        col_203DB.use_property_decorate = False
        col_203DB.scale_x = 1.0
        col_203DB.scale_y = 1.2999999523162842
        col_203DB.alignment = 'Expand'.upper()
        col_203DB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_203DB.operator('sna.my_generic_operator_74db1', text='清理', icon_value=0, emboss=True, depress=False)


class SNA_PT_clean_image_CA7A9(bpy.types.Panel):
    bl_label = '清理名称  .0  贴图'
    bl_idname = 'SNA_PT_clean_image_CA7A9'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_88BDF = layout.column(heading='', align=False)
        col_88BDF.alert = False
        col_88BDF.enabled = True
        col_88BDF.active = True
        col_88BDF.use_property_split = False
        col_88BDF.use_property_decorate = False
        col_88BDF.scale_x = 1.0
        col_88BDF.scale_y = 1.2000000476837158
        col_88BDF.alignment = 'Expand'.upper()
        col_88BDF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_88BDF.operator('sna.my_generic_operator_6ec18', text='清理', icon_value=0, emboss=True, depress=False)


class SNA_PT_clean_unused_material_CD78E(bpy.types.Panel):
    bl_label = '清理空材质槽'
    bl_idname = 'SNA_PT_clean_unused_material_CD78E'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_2F567 = layout.column(heading='', align=False)
        col_2F567.alert = False
        col_2F567.enabled = True
        col_2F567.active = True
        col_2F567.use_property_split = False
        col_2F567.use_property_decorate = False
        col_2F567.scale_x = 1.0
        col_2F567.scale_y = 1.2999999523162842
        col_2F567.alignment = 'Expand'.upper()
        col_2F567.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_2F567.operator('sna.my_generic_operator_b88a9', text='清理空材质槽', icon_value=0, emboss=True, depress=False)


class SNA_PT_PRE_E11ED(bpy.types.Panel):
    bl_label = '自动_pre'
    bl_idname = 'SNA_PT_PRE_E11ED'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_64D84 = layout.column(heading='', align=True)
        col_64D84.alert = False
        col_64D84.enabled = True
        col_64D84.active = True
        col_64D84.use_property_split = False
        col_64D84.use_property_decorate = False
        col_64D84.scale_x = 1.0
        col_64D84.scale_y = 1.0
        col_64D84.alignment = 'Expand'.upper()
        col_64D84.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_64D84.operator('sna.pre_20c0a', text='自动_pre', icon_value=0, emboss=True, depress=False)
        col_D2FB8 = col_64D84.column(heading='', align=True)
        col_D2FB8.alert = False
        col_D2FB8.enabled = True
        col_D2FB8.active = True
        col_D2FB8.use_property_split = False
        col_D2FB8.use_property_decorate = False
        col_D2FB8.scale_x = 1.0
        col_D2FB8.scale_y = 0.30000001192092896
        col_D2FB8.alignment = 'Expand'.upper()
        col_D2FB8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_D2FB8.progress(text='', factor=pre['sna_pre_progress'], type='RING' if False else 'BAR')


class SNA_PT_batch_naming_6679C(bpy.types.Panel):
    bl_label = '批量物体命名'
    bl_idname = 'SNA_PT_batch_naming_6679C'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_2D11D = layout.column(heading='', align=False)
        col_2D11D.alert = False
        col_2D11D.enabled = True
        col_2D11D.active = True
        col_2D11D.use_property_split = False
        col_2D11D.use_property_decorate = False
        col_2D11D.scale_x = 1.0
        col_2D11D.scale_y = 1.2999999523162842
        col_2D11D.alignment = 'Expand'.upper()
        col_2D11D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_2D11D.operator('sna.my_generic_operator_4f651', text='命名', icon_value=0, emboss=True, depress=False)
        col_376FB = col_2D11D.column(heading='', align=False)
        col_376FB.alert = False
        col_376FB.enabled = True
        col_376FB.active = True
        col_376FB.use_property_split = False
        col_376FB.use_property_decorate = False
        col_376FB.scale_x = 1.0
        col_376FB.scale_y = 1.0
        col_376FB.alignment = 'Expand'.upper()
        col_376FB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_E496B = col_376FB.column(heading='', align=False)
        col_E496B.alert = False
        col_E496B.enabled = True
        col_E496B.active = True
        col_E496B.use_property_split = False
        col_E496B.use_property_decorate = False
        col_E496B.scale_x = 1.0
        col_E496B.scale_y = 1.0
        col_E496B.alignment = 'Expand'.upper()
        col_E496B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_E496B.prop(bpy.context.scene, 'sna_name_qiming00', text='', icon_value=0, emboss=True)
        split_4BB4D = col_E496B.split(factor=0.10000000149011612, align=True)
        split_4BB4D.alert = False
        split_4BB4D.enabled = True
        split_4BB4D.active = True
        split_4BB4D.use_property_split = False
        split_4BB4D.use_property_decorate = False
        split_4BB4D.scale_x = 1.0
        split_4BB4D.scale_y = 1.0
        split_4BB4D.alignment = 'Expand'.upper()
        if not True: split_4BB4D.operator_context = "EXEC_DEFAULT"
        split_4BB4D.prop(bpy.context.scene, 'sna_name_qiming01_paixiu', text='', icon_value=396, emboss=True)
        if bpy.context.scene.sna_name_qiming01_paixiu:
            split_4BB4D.prop(bpy.context.scene, 'sna_name_qiming01_weishu', text='位数', icon_value=0, emboss=True)
        else:
            split_4BB4D.prop(bpy.context.scene, 'sna_name_qiming01', text='', icon_value=0, emboss=True)
        col_E496B.prop(bpy.context.scene, 'sna_name_qiming02', text='', icon_value=0, emboss=True)
        col_376FB.prop(bpy.context.scene, 'sna_name_weizhui_switch', text='按照序号加尾缀', icon_value=0, emboss=True)


class SNA_PT_C1C2_2CB69(bpy.types.Panel):
    bl_label = '拆分C1C2等'
    bl_idname = 'SNA_PT_C1C2_2CB69'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_CF43A = layout.column(heading='', align=False)
        col_CF43A.alert = False
        col_CF43A.enabled = True
        col_CF43A.active = True
        col_CF43A.use_property_split = False
        col_CF43A.use_property_decorate = False
        col_CF43A.scale_x = 1.0
        col_CF43A.scale_y = 1.2999999523162842
        col_CF43A.alignment = 'Expand'.upper()
        col_CF43A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_CF43A.operator('sna.my_generic_operator_41ba9', text='自动拆分', icon_value=0, emboss=True, depress=False)


class SNA_PT_select_similar_models_94B87(bpy.types.Panel):
    bl_label = '选择相似模型'
    bl_idname = 'SNA_PT_select_similar_models_94B87'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_main_panel_1CA4E'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_B466A = layout.column(heading='', align=False)
        col_B466A.alert = False
        col_B466A.enabled = True
        col_B466A.active = True
        col_B466A.use_property_split = False
        col_B466A.use_property_decorate = False
        col_B466A.scale_x = 1.0
        col_B466A.scale_y = 1.2999999523162842
        col_B466A.alignment = 'Expand'.upper()
        col_B466A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_B466A.operator('sna.my_generic_operator_2cec5', text='选择相似模型', icon_value=0, emboss=True, depress=False)
        col_B466A.prop(bpy.context.scene, 'sna_complete_uvmat_switch', text='开启UV层+材质槽判断', icon_value=0, emboss=True)
        col_B466A.prop(bpy.context.scene, 'sna_complete_similarity_switch', text='开启顶点位置判断', icon_value=0, emboss=True)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_name_qiming00 = bpy.props.StringProperty(name='name_qiming00', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_name_qiming01 = bpy.props.StringProperty(name='name_qiming01', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_name_qiming01_paixiu = bpy.props.BoolProperty(name='name_qiming01_paixiu', description='', options={'HIDDEN'}, default=False)
    bpy.types.Scene.sna_name_qiming01_weishu = bpy.props.IntProperty(name='name_qiming01_weishu', description='', options={'HIDDEN'}, default=3, subtype='NONE', min=1, max=4)
    bpy.types.Scene.sna_name_qiming02 = bpy.props.StringProperty(name='name_qiming02', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_name_weizhui_switch = bpy.props.BoolProperty(name='name_weizhui_switch', description='', options={'HIDDEN'}, default=False)
    bpy.types.Scene.sna_clear_position = bpy.props.BoolProperty(name='Clear_position', description='', default=False)
    bpy.types.Scene.sna_clear_zoom = bpy.props.BoolProperty(name='Clear_zoom', description='', default=True)
    bpy.types.Scene.sna_clear_rotation = bpy.props.BoolProperty(name='Clear_rotation', description='', default=True)
    bpy.types.Scene.sna_rotation_value = bpy.props.FloatVectorProperty(name='Rotation_value', description='', size=3, default=(-90.0, 0.0, 0.0), subtype='NONE', unit='NONE', step=1, precision=1)
    bpy.types.Scene.sna_clear_name = bpy.props.StringProperty(name='clear_name', description='', default='_lod1,_lod2,_lod3,_autophy,_autophy_s', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_complete_similarity_switch = bpy.props.BoolProperty(name='complete_similarity_switch', description='', default=False)
    bpy.types.Scene.sna_complete_uvmat_switch = bpy.props.BoolProperty(name='complete_uvmat_switch', description='', default=True)
    bpy.utils.register_class(SNA_PT_main_panel_1CA4E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_969F9)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2675B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B68F1)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9D201)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_611C7)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_74Db1)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6Ec18)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B88A9)
    bpy.utils.register_class(SNA_OT_Pre_20C0A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_4F651)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_41Ba9)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2Cec5)
    bpy.utils.register_class(SNA_PT_delete_similarity_B2D20)
    #bpy.utils.register_class(SNA_PT_merge_material_DBA1D)
    bpy.utils.register_class(SNA_PT_delete_by_name_94C31)
    bpy.utils.register_class(SNA_PT_check_coordinate_synchronization_status_0025F)
    bpy.utils.register_class(SNA_PT_clean_material_17646)
    bpy.utils.register_class(SNA_PT_clean_image_CA7A9)
    #bpy.utils.register_class(SNA_PT_clean_unused_material_CD78E)
    bpy.utils.register_class(SNA_PT_PRE_E11ED)
    #bpy.utils.register_class(SNA_PT_batch_naming_6679C)
    #bpy.utils.register_class(SNA_PT_C1C2_2CB69)
    bpy.utils.register_class(SNA_PT_select_similar_models_94B87)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_complete_uvmat_switch
    del bpy.types.Scene.sna_complete_similarity_switch
    del bpy.types.Scene.sna_clear_name
    del bpy.types.Scene.sna_rotation_value
    del bpy.types.Scene.sna_clear_rotation
    del bpy.types.Scene.sna_clear_zoom
    del bpy.types.Scene.sna_clear_position
    del bpy.types.Scene.sna_name_weizhui_switch
    del bpy.types.Scene.sna_name_qiming02
    del bpy.types.Scene.sna_name_qiming01_weishu
    del bpy.types.Scene.sna_name_qiming01_paixiu
    del bpy.types.Scene.sna_name_qiming01
    del bpy.types.Scene.sna_name_qiming00
    bpy.utils.unregister_class(SNA_PT_main_panel_1CA4E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_969F9)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2675B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B68F1)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9D201)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_611C7)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_74Db1)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6Ec18)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B88A9)
    bpy.utils.unregister_class(SNA_OT_Pre_20C0A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_4F651)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_41Ba9)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2Cec5)
    bpy.utils.unregister_class(SNA_PT_delete_similarity_B2D20)
    #bpy.utils.unregister_class(SNA_PT_merge_material_DBA1D)
    bpy.utils.unregister_class(SNA_PT_delete_by_name_94C31)
    bpy.utils.unregister_class(SNA_PT_check_coordinate_synchronization_status_0025F)
    bpy.utils.unregister_class(SNA_PT_clean_material_17646)
    bpy.utils.unregister_class(SNA_PT_clean_image_CA7A9)
    #bpy.utils.unregister_class(SNA_PT_clean_unused_material_CD78E)
    bpy.utils.unregister_class(SNA_PT_PRE_E11ED)
    #bpy.utils.unregister_class(SNA_PT_batch_naming_6679C)
    #bpy.utils.unregister_class(SNA_PT_C1C2_2CB69)
    bpy.utils.unregister_class(SNA_PT_select_similar_models_94B87)
