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
    "name" : "自动资产表格整理_v2",
    "author" : "渠奎奎", 
    "description" : "自动资产表格整理_v2",
    "blender" : (4, 2, 0),
    "version" : (2, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_插件工具" 
}


import bpy
import bpy.utils.previews
import os
import win32com.client


addon_keymaps = {}
_icons = None
node_tree = {'sna_sna_new_variable': [], 'sna_sna_new_variable_001': [], 'sna_sna_new_variable_002': [], 'sna_sna_new_variable_003': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_ui_DD837(layout_function, ):
    col_D4780 = layout_function.column(heading='', align=False)
    col_D4780.alert = False
    col_D4780.enabled = True
    col_D4780.active = True
    col_D4780.use_property_split = False
    col_D4780.use_property_decorate = False
    col_D4780.scale_x = 1.0
    col_D4780.scale_y = 1.0
    col_D4780.alignment = 'Expand'.upper()
    col_D4780.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_D4780.prop(bpy.context.scene, 'sna_excel_scene', text='场景', icon_value=0, emboss=True)
    col_D4780.prop(bpy.context.scene, 'sna_excel_category', text='类别', icon_value=0, emboss=True)
    col_D4780.prop(bpy.context.scene, 'sna_excel_tiling', text='是否为Tiling', icon_value=0, emboss=True)
    col_D4780.prop(bpy.context.scene, 'sna_excel_status', text='状态', icon_value=0, emboss=True)
    col_D4780.prop(bpy.context.scene, 'sna_excel_people', text='跟进人', icon_value=0, emboss=True)
    col_D4780.prop(bpy.context.scene, 'sna_excel_start', text='开始时间', icon_value=0, emboss=True)
    col_D4780.prop(bpy.context.scene, 'sna_excel_end', text='结束时间', icon_value=0, emboss=True)
    col_D4780.prop(bpy.context.scene, 'sna_excel_producer', text='制作方', icon_value=0, emboss=True)
    col_D4780.prop(bpy.context.scene, 'sna_excel_lot', text='批次', icon_value=0, emboss=True)


class SNA_OT_My_Generic_Operator_188Ce(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_188ce"
    bl_label = "生成预览图"
    bl_description = "生成预览图"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        import send2trash
        file_or_folder_path = "D:\Blender_填表工具缓存"
        # 检查文件或文件夹是否存在
        if os.path.exists(file_or_folder_path):
            # 将文件或文件夹发送到回收站
            send2trash.send2trash(file_or_folder_path)
            print(f"文件或文件夹 {file_or_folder_path} 已删除到回收站。")
        else:
            print(f"文件或文件夹 {file_or_folder_path} 不存在,无需删除。")
        # 使用合成节点设置开启
        bpy.context.scene.use_nodes = True
        # 获取合成节点树
        tree = bpy.context.scene.node_tree
        # 判断是否存在混合节点
        if 'Mix' not in tree.nodes:
            # 创建一个混合节点
            mix_node = tree.nodes.new(type='CompositorNodeMixRGB')
            mix_node.location = (-200, 0)  # 设置节点位置
            # 获取 Composite 节点
            composite_node = tree.nodes['Composite']
            # 获取 Mix 节点的输出和 Composite 节点的输入
            mix_output = mix_node.outputs['Image']
            composite_input = composite_node.inputs['Image']
            # 链接 Mix 节点的输出到 Composite 节点的输入
            tree.links.new(mix_output, composite_input)
            # 获取 Render Layers 节点和 Mix 节点的输入
            render_layers_node = tree.nodes['Render Layers']
            mix_fac_input = mix_node.inputs['Fac']
            mix_image_input = mix_node.inputs[2]
            # 链接 Render Layers 节点的 Alpha 输出到 Mix 节点的 Fac 输入
            tree.links.new(render_layers_node.outputs['Alpha'], mix_fac_input)
            # 链接 Render Layers 节点的 Image 输出到 Mix 节点的第二个 Image 输入
            tree.links.new(render_layers_node.outputs['Image'], mix_image_input)
            bpy.context.scene.node_tree.nodes["Mix"].inputs[1].default_value = (0.15, 0.15, 0.15, 1)
        bpy.ops.wm.console_toggle()
        bpy.context.scene.render.resolution_x = bpy.context.scene.sna_excel_image[0]
        bpy.context.scene.render.resolution_y = bpy.context.scene.sna_excel_image[1]
        if not os.path.exists(os.path.join(r'D:', '/Blender_填表工具缓存')):
            os.mkdir(os.path.join(r'D:', '/Blender_填表工具缓存'))
        if not os.path.exists(os.path.join(os.path.join(r'D:', '/Blender_填表工具缓存'), '预览图缓存')):
            os.mkdir(os.path.join(os.path.join(r'D:', '/Blender_填表工具缓存'), '预览图缓存'))
        for i_72472 in range(len(node_tree['sna_sna_new_variable'])):
            bpy.ops.object.select_pattern(pattern=node_tree['sna_sna_new_variable'][i_72472], case_sensitive=True, extend=False)
            bpy.context.view_layer.objects.active = bpy.data.objects[node_tree['sna_sna_new_variable'][i_72472]]
            bpy.ops.object.select_grouped(extend=False, type='COLLECTION')
            bpy.ops.view3d.camera_to_view_selected()
            total_faces = None
            # 获取当前选中的对象
            selected_objects = bpy.context.selected_objects
            # 遍历选中的对象，并统计面数
            total_faces = 0
            for obj in selected_objects:
                if obj.type == 'MESH':  # 确保对象是网格模型
                    mesh = obj.data
                    total_faces += len(mesh.loop_triangle_polygons)
            bpy.context.scene.camera.data.lens = 45.0
            output_path = os.path.join(os.path.join(os.path.join(r'D:', '/Blender_填表工具缓存'), '预览图缓存'),node_tree['sna_sna_new_variable'][i_72472].replace('_c1', '').replace('_lod0', '') + '-' + str(total_faces) + '-' + '.JPEG')
            dimension = None
            # 设置渲染参数
            scene = bpy.context.scene
            scene.render.image_settings.file_format = 'JPEG'  # 设置渲染输出格式为PNG
            scene.render.filepath = output_path  # 设置渲染输出路径
            # 获取当前场景
            scene = bpy.context.scene
            # 保存原始物体显示状态
            original_visibility = {}
            for obj in bpy.context.scene.objects:
                original_visibility[obj] = obj.hide_render
            # 将非选中物体隐藏
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and obj not in bpy.context.selected_objects:
                    obj.hide_render = True
            # 执行渲染
            bpy.ops.render.render(write_still=True)
            # 还原原始物体显示状态
            for obj, state in original_visibility.items():
                obj.hide_render = state
            bpy.context.scene.camera.data.lens = 50.0
            print(str(int(float(float(i_72472 + 1.0) / len(node_tree['sna_sna_new_variable'])) * 100.0)), '%', '——预览图生成中！')
        print('预览图生成完毕！')
        for i_9D428 in range(len([os.path.join('D:\Blender_填表工具缓存\预览图缓存', f) for f in os.listdir('D:\Blender_填表工具缓存\预览图缓存') if os.path.isfile(os.path.join('D:\Blender_填表工具缓存\预览图缓存', f))])):
            node_tree['sna_sna_new_variable_002'].append([bpy.context.scene.sna_excel_scene, bpy.context.scene.sna_excel_category, os.path.basename([os.path.join('D:\Blender_填表工具缓存\预览图缓存', f) for f in os.listdir('D:\Blender_填表工具缓存\预览图缓存') if os.path.isfile(os.path.join('D:\Blender_填表工具缓存\预览图缓存', f))][i_9D428]).split('-')[0], '-', bpy.context.scene.sna_excel_tiling, os.path.basename([os.path.join('D:\Blender_填表工具缓存\预览图缓存', f) for f in os.listdir('D:\Blender_填表工具缓存\预览图缓存') if os.path.isfile(os.path.join('D:\Blender_填表工具缓存\预览图缓存', f))][i_9D428]).split('-')[1], bpy.context.scene.sna_excel_status, bpy.context.scene.sna_excel_people, bpy.context.scene.sna_excel_start, bpy.context.scene.sna_excel_end, bpy.context.scene.sna_excel_producer, bpy.context.scene.sna_excel_lot])
            node_tree['sna_sna_new_variable_003'].append([os.path.join('D:\Blender_填表工具缓存\预览图缓存', f) for f in os.listdir('D:\Blender_填表工具缓存\预览图缓存') if os.path.isfile(os.path.join('D:\Blender_填表工具缓存\预览图缓存', f))][i_9D428])
        print(str(len([os.path.join('D:\Blender_填表工具缓存\预览图缓存', f) for f in os.listdir('D:\Blender_填表工具缓存\预览图缓存') if os.path.isfile(os.path.join('D:\Blender_填表工具缓存\预览图缓存', f))])), '组数据导入表中！')
        file_path = os.path.join(os.path.dirname('D:\Blender_填表工具缓存\预览图缓存'),'资产表格.xlsx')
        data_lis = node_tree['sna_sna_new_variable_002']
        image_path = node_tree['sna_sna_new_variable_003']
        path = bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'Form template.xlsx'))
        # 创建 Excel 应用程序
        excel = win32com.client.Dispatch("Excel.Application")
        wb = excel.Workbooks.Open(path)
        sheet = wb.Sheets(1)
        # 要写入的数据
        data = data_lis
        # 将数据写入指定位置
        for i, row in enumerate(data):
            for j, value in enumerate(row):
                sheet.Cells(i+2, j+1).Value = value  # 在第2行开始写入数据
        image_paths = image_path
        # 从第二行开始写入图片
        for i, image_path in enumerate(image_paths):
            cell = sheet.Cells(i+2, 4)  # 从第二行开始写入图片
            shape = sheet.Shapes.AddPicture(image_path, LinkToFile=False, SaveWithDocument=True, Left=cell.Left, Top=cell.Top, Width=-1, Height=-1)
            # 调整图片位置使其居中
            shape.Left = cell.Left + (cell.Width - shape.Width) / 2
            shape.Top = cell.Top + (cell.Height - shape.Height) / 2
        # 另存为新文件
        new_file_path = file_path
        wb.SaveAs(new_file_path)
        wb.Close()
        print('导入成功！')
        bpy.ops.wm.console_toggle()
        file_path = r"D:\Blender_填表工具缓存\资产表格.xlsx"
        try:
            os.startfile(file_path)  # 使用os模块中的startfile函数启动指定文件
        except OSError as e:
            print(f"Error: {e}")
        self.report({'INFO'}, message='执行完毕！')
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        col_B443C = layout.column(heading='', align=False)
        col_B443C.alert = False
        col_B443C.enabled = True
        col_B443C.active = True
        col_B443C.use_property_split = False
        col_B443C.use_property_decorate = False
        col_B443C.scale_x = 1.0
        col_B443C.scale_y = 1.0
        col_B443C.alignment = 'Expand'.upper()
        col_B443C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_B443C.label(text='预生成数量：' + str(len(node_tree['sna_sna_new_variable'])), icon_value=36)
        box_ACAEE = col_B443C.box()
        box_ACAEE.alert = False
        box_ACAEE.enabled = True
        box_ACAEE.active = True
        box_ACAEE.use_property_split = False
        box_ACAEE.use_property_decorate = False
        box_ACAEE.alignment = 'Expand'.upper()
        box_ACAEE.scale_x = 1.0
        box_ACAEE.scale_y = 1.0
        if not True: box_ACAEE.operator_context = "EXEC_DEFAULT"
        col_ECF3A = box_ACAEE.column(heading='', align=False)
        col_ECF3A.alert = True
        col_ECF3A.enabled = True
        col_ECF3A.active = True
        col_ECF3A.use_property_split = False
        col_ECF3A.use_property_decorate = False
        col_ECF3A.scale_x = 1.0
        col_ECF3A.scale_y = 1.0
        col_ECF3A.alignment = 'Expand'.upper()
        col_ECF3A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_ECF3A.label(text='错误集合数量：' + str(len(node_tree['sna_sna_new_variable_001'])), icon_value=33)
        for i_8841F in range(len(node_tree['sna_sna_new_variable_001'])):
            op = col_ECF3A.operator('sna.my_generic_operator_df917', text=node_tree['sna_sna_new_variable_001'][i_8841F], icon_value=0, emboss=True, depress=False)
            op.sna_new_property = node_tree['sna_sna_new_variable_001'][i_8841F]

    def invoke(self, context, event):
        node_tree['sna_sna_new_variable_002'] = []
        node_tree['sna_sna_new_variable_001'] = []
        node_tree['sna_sna_new_variable'] = []
        node_tree['sna_sna_new_variable_003'] = []
        for i_AEF87 in range(len(bpy.data.collections)):
            if (bpy.data.collections[i_AEF87].name[-4:] == '_pre'):
                bpy.ops.object.select_all(action='DESELECT')
                if ((not property_exists("bpy.data.objects[bpy.data.collections[i_AEF87].name[:-4] + '_c1_lod0']", globals(), locals())) and (not property_exists("bpy.data.objects[bpy.data.collections[i_AEF87].name[:-4] + '_lod0']", globals(), locals()))):
                    node_tree['sna_sna_new_variable_001'].append(bpy.data.collections[i_AEF87].name)
                else:
                    node_tree['sna_sna_new_variable'].append((bpy.data.collections[i_AEF87].name[:-4] + '_lod0' if property_exists("bpy.data.objects[bpy.data.collections[i_AEF87].name[:-4] + '_lod0']", globals(), locals()) else bpy.data.collections[i_AEF87].name[:-4] + '_c1_lod0'))
        return context.window_manager.invoke_props_dialog(self, width=300)


class SNA_PT_automatic_asset_guide_88A21(bpy.types.Panel):
    bl_label = '资产全自动导表'
    bl_idname = 'SNA_PT_automatic_asset_guide_88A21'
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
        if property_exists("bpy.context.scene.camera.data", globals(), locals()):
            pass
        else:
            col_FBCED = layout.column(heading='', align=False)
            col_FBCED.alert = True
            col_FBCED.enabled = True
            col_FBCED.active = True
            col_FBCED.use_property_split = False
            col_FBCED.use_property_decorate = False
            col_FBCED.scale_x = 1.0
            col_FBCED.scale_y = 1.0
            col_FBCED.alignment = 'Expand'.upper()
            col_FBCED.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_FBCED.label(text='无活动相机！需要创建相机。', icon_value=0)
        col_349CD = layout.column(heading='', align=False)
        col_349CD.alert = False
        col_349CD.enabled = property_exists("bpy.context.scene.camera.data", globals(), locals())
        col_349CD.active = True
        col_349CD.use_property_split = False
        col_349CD.use_property_decorate = False
        col_349CD.scale_x = 1.0
        col_349CD.scale_y = 1.0
        col_349CD.alignment = 'Expand'.upper()
        col_349CD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_7CAA6 = col_349CD.split(factor=0.8500000238418579, align=False)
        split_7CAA6.alert = False
        split_7CAA6.enabled = True
        split_7CAA6.active = True
        split_7CAA6.use_property_split = False
        split_7CAA6.use_property_decorate = False
        split_7CAA6.scale_x = 1.0
        split_7CAA6.scale_y = 1.0
        split_7CAA6.alignment = 'Expand'.upper()
        if not True: split_7CAA6.operator_context = "EXEC_DEFAULT"
        split_7CAA6.separator(factor=1.0)
        op = split_7CAA6.operator('sna.my_generic_operator_4689c', text='', icon_value=117, emboss=False, depress=False)
        split_01E13 = col_349CD.split(factor=0.8999999761581421, align=True)
        split_01E13.alert = False
        split_01E13.enabled = True
        split_01E13.active = True
        split_01E13.use_property_split = False
        split_01E13.use_property_decorate = False
        split_01E13.scale_x = 1.0
        split_01E13.scale_y = 1.5
        split_01E13.alignment = 'Expand'.upper()
        if not True: split_01E13.operator_context = "EXEC_DEFAULT"
        op = split_01E13.operator('sna.my_generic_operator_188ce', text='自动填表', icon_value=744, emboss=True, depress=False)
        op = split_01E13.operator('sna.my_generic_operator_f30c2', text='', icon_value=693, emboss=True, depress=False)
        box_A3828 = col_349CD.box()
        box_A3828.alert = False
        box_A3828.enabled = True
        box_A3828.active = True
        box_A3828.use_property_split = False
        box_A3828.use_property_decorate = False
        box_A3828.alignment = 'Expand'.upper()
        box_A3828.scale_x = 1.0
        box_A3828.scale_y = 1.0
        if not True: box_A3828.operator_context = "EXEC_DEFAULT"
        layout_function = box_A3828
        sna_ui_DD837(layout_function, )


class SNA_OT_My_Generic_Operator_F30C2(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_f30c2"
    bl_label = "打开缓存路径"
    bl_description = "打开缓存路径"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if os.path.exists(r'D:\Blender_填表工具缓存\预览图缓存'):
            directory_path = os.path.dirname(r'D:\Blender_填表工具缓存\预览图缓存')
            # 使用操作系统默认的文件管理器打开指定目录
            os.startfile(directory_path)
            self.report({'INFO'}, message='路径打开成功！')
        else:
            self.report({'INFO'}, message='路径不存在！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_4689C(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_4689c"
    bl_label = "设置_界面"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        box_4F6A3 = layout.box()
        box_4F6A3.alert = False
        box_4F6A3.enabled = True
        box_4F6A3.active = True
        box_4F6A3.use_property_split = False
        box_4F6A3.use_property_decorate = False
        box_4F6A3.alignment = 'Expand'.upper()
        box_4F6A3.scale_x = 1.0
        box_4F6A3.scale_y = 1.0
        if not True: box_4F6A3.operator_context = "EXEC_DEFAULT"
        col_8379A = box_4F6A3.column(heading='', align=False)
        col_8379A.alert = False
        col_8379A.enabled = True
        col_8379A.active = True
        col_8379A.use_property_split = False
        col_8379A.use_property_decorate = False
        col_8379A.scale_x = 1.0
        col_8379A.scale_y = 1.0
        col_8379A.alignment = 'Expand'.upper()
        col_8379A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_8379A.label(text='集合带_pre,子物体需要有_lod0', icon_value=679)
        col_8379A.label(text='最佳相机视角：X=60  Y=0  Z=50', icon_value=772)
        row_ACCA9 = col_8379A.row(heading='', align=False)
        row_ACCA9.alert = False
        row_ACCA9.enabled = True
        row_ACCA9.active = True
        row_ACCA9.use_property_split = False
        row_ACCA9.use_property_decorate = False
        row_ACCA9.scale_x = 1.0
        row_ACCA9.scale_y = 1.0
        row_ACCA9.alignment = 'Expand'.upper()
        row_ACCA9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_ACCA9.prop(bpy.context.scene, 'sna_excel_image', text='分辨率', icon_value=755, emboss=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)


class SNA_OT_My_Generic_Operator_Df917(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_df917"
    bl_label = "复制名称"
    bl_description = "复制名称"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='复制文本', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        collection_name = self.sna_new_property
        collection_name = collection_name
        # 通过名称获取集合
        collection = bpy.data.collections.get(collection_name)
        for obj in collection.objects:
            obj.select_set(True)
        for i_37FCD in range(len(bpy.context.view_layer.objects.selected)):
            pass
        bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_37FCD]
        self.report({'INFO'}, message='定位物体成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_excel_scene = bpy.props.StringProperty(name='Excel_Scene', description='', default='通用', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_category = bpy.props.StringProperty(name='Excel_Category', description='', default='建筑', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_tiling = bpy.props.StringProperty(name='Excel_Tiling', description='', default='✔✘', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_status = bpy.props.StringProperty(name='Excel_Status', description='', default='验收', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_people = bpy.props.StringProperty(name='Excel_People', description='', default='xxx', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_start = bpy.props.StringProperty(name='Excel_Start', description='', default='n月n日', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_end = bpy.props.StringProperty(name='Excel_End', description='', default='n月n日', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_producer = bpy.props.StringProperty(name='Excel_Producer', description='', default='外包', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_lot = bpy.props.StringProperty(name='Excel_Lot', description='', default='第n批', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_excel_image = bpy.props.IntVectorProperty(name='Excel_Image', description='', size=2, default=(144, 100), subtype='NONE')
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_188Ce)
    bpy.utils.register_class(SNA_PT_automatic_asset_guide_88A21)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_F30C2)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_4689C)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Df917)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_excel_image
    del bpy.types.Scene.sna_excel_lot
    del bpy.types.Scene.sna_excel_producer
    del bpy.types.Scene.sna_excel_end
    del bpy.types.Scene.sna_excel_start
    del bpy.types.Scene.sna_excel_people
    del bpy.types.Scene.sna_excel_status
    del bpy.types.Scene.sna_excel_tiling
    del bpy.types.Scene.sna_excel_category
    del bpy.types.Scene.sna_excel_scene
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_188Ce)
    bpy.utils.unregister_class(SNA_PT_automatic_asset_guide_88A21)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_F30C2)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_4689C)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Df917)
