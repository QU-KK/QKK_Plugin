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
    "name" : "射光剔除_v2",
    "author" : "渠奎奎", 
    "description" : "射光剔除_v2",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "QKK_通用" 
}


import bpy
import bpy.utils.previews
from PIL import Image
import time, sys
import os




def string_to_type(value, to_type, default):
    try:
        value = to_type(value)
    except:
        value = default
    return value


addon_keymaps = {}
_icons = None
uv = {'sna_face_number': 0, }
node_tree = {'sna_face_id': [], }
node_tree = {'sna_obj_list': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_uv_C1631(obj_list):
    for i_E1ABD in range(len(bpy.context.view_layer.objects.selected)):
        if property_exists("bpy.context.view_layer.objects.selected[i_E1ABD].data.uv_layers['剔除_uv']", globals(), locals()):
            bpy.context.view_layer.objects.selected[i_E1ABD].data.uv_layers.remove(layer=bpy.context.view_layer.objects.selected[i_E1ABD].data.uv_layers['剔除_uv'], )
    for i_40C6C in range(len(obj_list)):
        layer_AE2BE = obj_list[i_40C6C].data.uv_layers.new(name='剔除_uv', do_init=True, )
        obj_list[i_40C6C].data.uv_layers['剔除_uv'].active = True
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.reset()
    uv['sna_face_number'] = 0
    for i_73DBB in range(len(bpy.context.view_layer.objects.selected)):
        uv['sna_face_number'] = int(uv['sna_face_number'] + len(bpy.context.view_layer.objects.selected[i_73DBB].data.polygons))
    bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=False, rotate_method='ANY', scale=True, merge_overlap=False, margin_method='SCALED', margin=float(1.0 / uv['sna_face_number']), pin=False, pin_method='LOCKED', shape_method='CONVEX')
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    return


def sna_func_E8F84(img_filepath, obj_list):
    for i_3A300 in range(len(obj_list)):
        bpy.context.view_layer.objects.active = obj_list[i_3A300]
        node_tree['sna_face_id'] = []
        uv_data = None
        # 获取场景中的选定对象
        obj = bpy.context.object
        mesh = obj.data
        uv_data = []
        # 确保至少存在一个UV图层
        if mesh.uv_layers:
            uv_layer = mesh.uv_layers.active
            # 遍历每个UV面
            for idx, face in enumerate(mesh.polygons):    
                uv_coordinates_list = []
                # 遍历UV面中的每个顶点索引
                for loop_idx in face.loop_indices:
                    # 通过loop索引找到UV坐标
                    uv_coords = uv_layer.data[loop_idx].uv
                    uv_coordinates_list.append((uv_coords.x, uv_coords.y))  # 将UV坐标添加为元组到列表中
                uv_data.append([idx] + uv_coordinates_list)
        #print(uv_data)
        img_filepath = img_filepath
        a = None
        # 打开灰度图像
        img_filepath
        img = Image.open(img_filepath).convert('L')
        width, height = img.size
        a = (width, height)
        print('')
        print('处理批次：', str(int(i_3A300 + 1.0)) + '/' + str(len(obj_list)))
        for i_4EFD8 in range(len(uv_data)):
            i = float(int(i_4EFD8 + 1.0) / len(uv_data))

            def update_progress(progress):
                length = 50
                block = int(round(length*progress))
                msg = "\r{0} {1} %  ".format("█"*block + " "*(length-block), round(progress*100))
                sys.stdout.write(msg)
            update_progress(i)
            point1 = (int(uv_data[i_4EFD8][1][0] * int(a[0])), int(float(1.0 - uv_data[i_4EFD8][1][1]) * int(a[1])))
            point2 = (int(uv_data[i_4EFD8][2][0] * int(a[0])), int(float(1.0 - uv_data[i_4EFD8][2][1]) * int(a[1])))
            point3 = (int(uv_data[i_4EFD8][3][0] * int(a[0])), int(float(1.0 - uv_data[i_4EFD8][3][1]) * int(a[1])))
            average_value = None
            # 获取范围内的所有像素的灰度值
            min_x = min(point1[0], point2[0], point3[0])
            max_x = max(point1[0], point2[0], point3[0])
            min_y = min(point1[1], point2[1], point3[1])
            max_y = max(point1[1], point2[1], point3[1])
            # 存储范围内的所有像素的灰度值
            pixel_values = []
            # 遍历范围内的所有像素并获取灰度值
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    pixel_value = img.getpixel((x, y))
                    pixel_values.append(pixel_value)
            # 计算范围内所有像素的平均灰度值
            average_value = sum(pixel_values) / len(pixel_values)
            # 打印范围内的所有像素的灰度值
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    pixel_value = img.getpixel((x, y))
                    #print(f"坐标({x}, {y})的像素灰度值为: {pixel_value}")
            # 打印范围内所有像素的平均灰度值
            #print(f"范围内所有像素的平均灰度值为: {average_value}")
            if (average_value <= 1):
                node_tree['sna_face_id'].append(uv_data[i_4EFD8][0])
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        for i_FD991 in range(len(node_tree['sna_face_id'])):
            bpy.context.view_layer.objects.active.data.polygons[node_tree['sna_face_id'][i_FD991]].select = True
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.delete(type='FACE')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    return


def sna_func_17265(obj_list_):
    if property_exists("bpy.data.materials['剔除_mat']", globals(), locals()):
        bpy.context.blend_data.materials.remove(material=bpy.data.materials['剔除_mat'], )
    if property_exists("bpy.data.images['剔除_tex']", globals(), locals()):
        bpy.context.blend_data.images.remove(image=bpy.data.images['剔除_tex'], )
    material_78477 = bpy.context.blend_data.materials.new(name='剔除_mat', )
    bpy.context.view_layer.material_override = material_78477
    image_347FB = bpy.context.blend_data.images.new(name='剔除_tex', width=int(string_to_type(bpy.context.scene.sna_cull_accuracy, float, 0) * 1.0), height=int(string_to_type(bpy.context.scene.sna_cull_accuracy, float, 0) * 1.0), alpha=False, )
    for i_781D0 in range(len(obj_list_)):
        for i_CF54D in range(len(obj_list_[i_781D0].material_slots)):
            mat_name = obj_list_[i_781D0].material_slots[i_CF54D].name
            tex_name = '剔除_tex'
            material = bpy.data.materials.get(mat_name)
            texture_node_exists = any(node.name == "剔除_nod" for node in material.node_tree.nodes)
            if not texture_node_exists:
            # 创建新的图像纹理节点
                texture_node = material.node_tree.nodes.new('ShaderNodeTexImage')
                texture_node.name = "剔除_nod"
                texture_node.image = bpy.data.images.get(tex_name)
                material.node_tree.nodes.active = texture_node  # 将新增的节点设置为活动节点
    return


def sna_func_6C209(clear_mat, clear_tex, clear_nod, clear_uv):
    if clear_mat:
        if property_exists("bpy.data.materials['剔除_mat']", globals(), locals()):
            bpy.context.blend_data.materials.remove(material=bpy.data.materials['剔除_mat'], )
    if clear_tex:
        if property_exists("bpy.data.images['剔除_tex']", globals(), locals()):
            bpy.context.blend_data.images.remove(image=bpy.data.images['剔除_tex'], )
    if clear_nod:
        # 获取选中的所有对象
        selected_objects = bpy.context.selected_objects
        # 遍历选中的所有对象
        for obj in selected_objects:
            if obj.type == 'MESH':
                # 遍历对象的所有材质
                for slot in obj.material_slots:
                    if slot.material:
                        material = slot.material
                        if material.node_tree:
                            # 在材质的节点树中查找名称为"剔除_nod"的节点并删除它
                            for node in material.node_tree.nodes:
                                if node.name == "剔除_nod":
                                    material.node_tree.nodes.remove(node)
    if clear_uv:
        for i_548D0 in range(len(bpy.context.view_layer.objects.selected)):
            if property_exists("bpy.context.view_layer.objects.selected[i_548D0].data.uv_layers['剔除_uv']", globals(), locals()):
                bpy.context.view_layer.objects.selected[i_548D0].data.uv_layers.remove(layer=bpy.context.view_layer.objects.selected[i_548D0].data.uv_layers['剔除_uv'], )
        return


class SNA_PT_baking_culling_110D8(bpy.types.Panel):
    bl_label = '射光烘焙剔除'
    bl_idname = 'SNA_PT_baking_culling_110D8'
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
        col_D87BA = layout.column(heading='', align=True)
        col_D87BA.alert = False
        col_D87BA.enabled = True
        col_D87BA.active = True
        col_D87BA.use_property_split = False
        col_D87BA.use_property_decorate = False
        col_D87BA.scale_x = 1.0
        col_D87BA.scale_y = 1.0
        col_D87BA.alignment = 'Expand'.upper()
        col_D87BA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_B4F8F = col_D87BA.column(heading='', align=True)
        col_B4F8F.alert = False
        col_B4F8F.enabled = True
        col_B4F8F.active = True
        col_B4F8F.use_property_split = False
        col_B4F8F.use_property_decorate = False
        col_B4F8F.scale_x = 1.0
        col_B4F8F.scale_y = 1.5
        col_B4F8F.alignment = 'Expand'.upper()
        col_B4F8F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_B4F8F.operator('sna.operation_f28b0', text='执行', icon_value=73, emboss=True, depress=False)
        col_D87BA.prop(bpy.context.scene, 'sna_cull_automatic_uv', text='自动UV', icon_value=0, emboss=True)
        layout.prop(bpy.context.scene, 'sna_cull_accuracy', text='精度', icon_value=0, emboss=True)
        layout.prop(bpy.context.scene, 'sna_cull_cache_path', text='缓存路径', icon_value=0, emboss=True)


class SNA_OT_Operation_F28B0(bpy.types.Operator):
    bl_idname = "sna.operation_f28b0"
    bl_label = "operation"
    bl_description = "执行剔除"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree['sna_obj_list'] = []
        for i_8FF5E in range(len(bpy.context.view_layer.objects.selected)):
            node_tree['sna_obj_list'].append(bpy.context.view_layer.objects.selected[i_8FF5E])
        print('obj_list  获取成功！')
        print('开始——预处理')
        sna_func_17265(node_tree['sna_obj_list'])
        print('完毕——预处理')
        if bpy.context.scene.sna_cull_automatic_uv:
            print('开始——UV处理')
            sna_uv_C1631(node_tree['sna_obj_list'])
            print('完毕——UV处理')
        print('开始——烘焙')
        bpy.ops.object.bake()

        def delayed_CDCA5():
            img_filepath = os.path.join(bpy.path.abspath(bpy.context.scene.sna_cull_cache_path),'剔除_tex.png')
            # 获取当前场景
            scene = bpy.context.scene
            # 获取图像对象
            image = bpy.data.images['剔除_tex']  # 请将 'YourImageName' 替换为您图像的名称
            #img_filepath = 'C:\\Users\\qukuikui\\Desktop\\全新剔除\\资产\\剔除_tex.png'
            # 保存图像到本地
            image.filepath_raw = img_filepath
            image.save()
            # 打开图像并转换为灰度图
            img = Image.open(img_filepath)  # 替换为您的图片文件名和格式
            # 转换为灰度图
            img_gray = img.convert('L')
            # 保存灰度图
            img_gray.save(img_filepath)
            print('完毕——烘焙')
            print('开始——清理')
            sna_func_6C209(True, False, True, False)
            print('完毕——清理')
            print('开始——剔除')

            def delayed_14AF1():
                sna_func_E8F84(os.path.join(bpy.path.abspath(bpy.context.scene.sna_cull_cache_path),'剔除_tex.png'), node_tree['sna_obj_list'])
                sna_func_6C209(False, False, False, bpy.context.scene.sna_cull_automatic_uv)
                node_tree['sna_obj_list'] = []
                print('结束')
                bpy.ops.wm.console_toggle()
            bpy.app.timers.register(delayed_14AF1, first_interval=0.20000000298023224)
        bpy.app.timers.register(delayed_CDCA5, first_interval=0.05000000074505806)
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.ops.wm.console_toggle()
        print('————————————————')
        sna_func_6C209(True, True, True, bpy.context.scene.sna_cull_automatic_uv)
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.device = 'GPU'
        bpy.context.scene.cycles.preview_samples = 64
        bpy.context.scene.cycles.samples = 256
        bpy.context.scene.cycles.use_denoising = False
        bpy.context.scene.cycles.max_bounces = 0
        bpy.context.scene.cycles.bake_type = 'DIFFUSE'
        bpy.context.scene.render.bake.use_pass_indirect = False
        bpy.context.scene.render.bake.use_pass_color = False
        bpy.context.scene.render.bake.margin = 0
        print('开始')
        return self.execute(context)


class SNA_OT_Uv_Unfolding_290F7(bpy.types.Operator):
    bl_idname = "sna.uv_unfolding_290f7"
    bl_label = "uv_unfolding"
    bl_description = "UV测试展开"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree['sna_obj_list'] = []
        for i_664CB in range(len(bpy.context.view_layer.objects.selected)):
            node_tree['sna_obj_list'].append(bpy.context.view_layer.objects.selected[i_664CB])
            sna_uv_C1631(node_tree['sna_obj_list'])
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'INFO'}, message='测试展开完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_D42Ce(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d42ce"
    bl_label = "清理"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        sna_func_6C209(bpy.context.scene.sna_cull_mat, bpy.context.scene.sna_cull_tex, bpy.context.scene.sna_cull_nod, bpy.context.scene.sna_cull_uv)
        self.report({'INFO'}, message='清理完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_advanced_0531C(bpy.types.Panel):
    bl_label = '高级'
    bl_idname = 'SNA_PT_advanced_0531C'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_baking_culling_110D8'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        box_181CB = layout.box()
        box_181CB.alert = False
        box_181CB.enabled = True
        box_181CB.active = True
        box_181CB.use_property_split = False
        box_181CB.use_property_decorate = False
        box_181CB.alignment = 'Expand'.upper()
        box_181CB.scale_x = 1.0
        box_181CB.scale_y = 1.0
        if not True: box_181CB.operator_context = "EXEC_DEFAULT"
        col_D1E63 = box_181CB.column(heading='', align=True)
        col_D1E63.alert = False
        col_D1E63.enabled = True
        col_D1E63.active = True
        col_D1E63.use_property_split = False
        col_D1E63.use_property_decorate = False
        col_D1E63.scale_x = 1.0
        col_D1E63.scale_y = 1.2000000476837158
        col_D1E63.alignment = 'Expand'.upper()
        col_D1E63.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_D1E63.operator('sna.uv_unfolding_290f7', text='UV测试展开', icon_value=0, emboss=True, depress=False)
        op = col_D1E63.operator('sna.my_generic_operator_d42ce', text='清理', icon_value=0, emboss=True, depress=False)
        row_6B868 = col_D1E63.row(heading='', align=True)
        row_6B868.alert = False
        row_6B868.enabled = True
        row_6B868.active = True
        row_6B868.use_property_split = False
        row_6B868.use_property_decorate = False
        row_6B868.scale_x = 1.0
        row_6B868.scale_y = 1.0
        row_6B868.alignment = 'Expand'.upper()
        row_6B868.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_6B868.prop(bpy.context.scene, 'sna_cull_mat', text='_mat', icon_value=0, emboss=True)
        row_6B868.prop(bpy.context.scene, 'sna_cull_tex', text='_tex', icon_value=0, emboss=True)
        row_6B868.prop(bpy.context.scene, 'sna_cull_nod', text='_nod', icon_value=0, emboss=True)
        row_6B868.prop(bpy.context.scene, 'sna_cull_uv', text='_uv', icon_value=0, emboss=True)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_cull_accuracy = bpy.props.EnumProperty(name='cull_accuracy', description='精度越高，剔除准确度越好，越慢', items=[('512', '512', '', 0, 0), ('1024', '1024', '', 0, 1), ('2048', '2048', '', 0, 2), ('4096', '4096', '', 0, 3), ('6344', '6344', '', 0, 4), ('8192', '8192', '', 0, 5), ('12288', '12288', '', 0, 6)])
    bpy.types.Scene.sna_cull_cache_path = bpy.props.StringProperty(name='cull_cache_path', description='', default='', subtype='DIR_PATH', maxlen=0)
    bpy.types.Scene.sna_cull_automatic_uv = bpy.props.BoolProperty(name='cull_automatic_uv', description='', default=True)
    bpy.types.Scene.sna_cull_mat = bpy.props.BoolProperty(name='cull_mat', description='', default=True)
    bpy.types.Scene.sna_cull_tex = bpy.props.BoolProperty(name='cull_tex', description='', default=True)
    bpy.types.Scene.sna_cull_nod = bpy.props.BoolProperty(name='cull_nod', description='', default=True)
    bpy.types.Scene.sna_cull_uv = bpy.props.BoolProperty(name='cull_uv', description='', default=True)
    bpy.utils.register_class(SNA_PT_baking_culling_110D8)
    bpy.utils.register_class(SNA_OT_Operation_F28B0)
    bpy.utils.register_class(SNA_OT_Uv_Unfolding_290F7)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D42Ce)
    bpy.utils.register_class(SNA_PT_advanced_0531C)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_cull_uv
    del bpy.types.Scene.sna_cull_nod
    del bpy.types.Scene.sna_cull_tex
    del bpy.types.Scene.sna_cull_mat
    del bpy.types.Scene.sna_cull_automatic_uv
    del bpy.types.Scene.sna_cull_cache_path
    del bpy.types.Scene.sna_cull_accuracy
    bpy.utils.unregister_class(SNA_PT_baking_culling_110D8)
    bpy.utils.unregister_class(SNA_OT_Operation_F28B0)
    bpy.utils.unregister_class(SNA_OT_Uv_Unfolding_290F7)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D42Ce)
    bpy.utils.unregister_class(SNA_PT_advanced_0531C)
