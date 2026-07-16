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
    "name" : "Asset_Archiving_Tool_v3",
    "author" : "渠奎奎", 
    "description" : "自动资产表格整理_v3",
    "blender" : (5, 0, 0),
    "version" : (3, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_插件工具" 
}


import bpy
import bpy.utils.previews
import win32com.client
#import os



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
py = {'sna_pre_list': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_PT_asset_archiving_tool_22FD2(bpy.types.Panel):
    bl_label = '资产归档工具_2026.1.1'
    bl_idname = 'SNA_PT_asset_archiving_tool_22FD2'
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
        split_F63EC = layout.split(factor=0.800000011920929, align=True)
        split_F63EC.alert = False
        split_F63EC.enabled = True
        split_F63EC.active = True
        split_F63EC.use_property_split = False
        split_F63EC.use_property_decorate = False
        split_F63EC.scale_x = 1.0
        split_F63EC.scale_y = 1.5
        split_F63EC.alignment = 'Expand'.upper()
        if not True: split_F63EC.operator_context = "EXEC_DEFAULT"
        col_9E429 = split_F63EC.column(heading='', align=True)
        col_9E429.alert = False
        col_9E429.enabled = property_exists("bpy.context.scene.camera.data", globals(), locals())
        col_9E429.active = True
        col_9E429.use_property_split = False
        col_9E429.use_property_decorate = False
        col_9E429.scale_x = 1.0
        col_9E429.scale_y = 1.0
        col_9E429.alignment = 'Expand'.upper()
        col_9E429.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_9E429.operator('sna.start_processing_9c33a', text='执行资产归档', icon_value=0, emboss=True, depress=False)
        op = split_F63EC.operator('sna.open_cache_8dce6', text='', icon_value=string_to_icon('FILEBROWSER'), emboss=True, depress=False)


class SNA_OT_Start_Processing_9C33A(bpy.types.Operator):
    bl_idname = "sna.start_processing_9c33a"
    bl_label = "Start_Processing"
    bl_description = "自动识别_pre集合，禁用集合渲染可跳过此资产"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if (len(py['sna_pre_list']) == 0):
            import os
            import send2trash
            os.system('cls')
            node_path = bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'node.blend'))
            xlsx_path = bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'Form template.xlsx'))

            def delete_cache():
                # 检查文件或文件夹是否存在
                if os.path.exists(output_path):
                    # 将文件或文件夹发送到回收站
                    send2trash.send2trash(output_path)
                    print(f"文件夹 {output_path} 已删除到回收站。")
                else:
                    print(f"文件夹 {output_path} 不存在,无需删除。")
            # 设置合成器

            def set_compositor(node_path):
                if not bpy.data.node_groups.get('输出表格'):
                    bpy.ops.wm.append(directory= node_path + '\\NodeTree', filename='输出表格', link=False)
                node = bpy.data.node_groups.get('输出表格')
                bpy.context.scene.compositing_node_group = node
                node.nodes['渲染层'].scene = bpy.context.scene
                node.nodes["输出路径"].directory = output_path + '\\预览图缓存'
            # 储存集合,物体
            all_collection_list = []
            all_obj_list = []

            def storage_data():
                for collection in bpy.data.collections:
                    collection_data = [collection,collection.hide_render]
                    all_collection_list.append(collection_data)    
                for obj in bpy.data.objects:
                    obj_data = [obj,obj.hide_render]
                    all_obj_list.append(obj_data)
            # 筛选集合

            def filter_collection():
                collection_list = []
                for collection in bpy.data.collections:
                    suffix = collection.name.split('_')[len(collection.name.split('_')) - 1]
                    if collection.hide_render == False and suffix == 'pre':
                        collection_list.append(collection)
                        collection.hide_render = True
                    else:        
                        collection.hide_render = True
                # 选中物体
                progress = 0
                for collection in collection_list:
                    bpy.ops.object.select_all(action='DESELECT')
                    collection.hide_render = False
                    for obj in collection.objects:
                        suffix = obj.name.split('_')[len(obj.name.split('_')) - 1]
                        if suffix == 'lod0' and obj.data.id_type == 'MESH':
                            obj.hide_render = False
                            obj.select_set(True) # 选中模型
                        else:
                            obj.hide_render = True
                            obj.select_set(False) # 不选中模型
                    camera_align()
                    progress += 1
                    data = str(progress) + '/' + str(len(collection_list)) + '  ' + collection.name
                    print("\033[32m" + data + "\033[0m")
                    render_image(collection)
                    collection.hide_render = True
            # 摄像机对齐

            def camera_align():
                # 渲染尺寸
                bpy.context.scene.render.resolution_x = 144
                bpy.context.scene.render.resolution_y = 100
                bpy.context.scene.render.resolution_percentage = 100
                camera = bpy.context.scene.camera.data
                camera.sensor_width = 33
                bpy.ops.view3d.camera_to_view_selected()
                camera.sensor_width = 36
            # 渲染

            def render_image(collection):
                triangles = 0
                for obj in bpy.context.selected_objects:
                    triangles += len(obj.data.loop_triangles)
                img_name = collection.name + '~' + str(triangles)
                bpy.data.node_groups["输出表格"].nodes["输出路径"].file_name = img_name
                bpy.ops.render.render(use_viewport=True)        
            # 还原集合,物体

            def restore_data():
                for collection_data in all_collection_list:
                    collection_data[0].hide_render = collection_data[1]  
                for obj_data in all_obj_list:
                    obj_data[0].hide_render = obj_data[1]
            # 导入至表格

            def import_xlsx(xlsx_path):
                # 创建 Excel 应用程序
                excel = win32com.client.Dispatch("Excel.Application")
                wb = excel.Workbooks.Open(xlsx_path)
                sheet = wb.Sheets(1)
                path = output_path + '\\预览图缓存'
                row = 0 #行
                xlsx_progress = 0 #导表进度
                # 获取指定路径内文件
                for entry in os.scandir(path):
                    image_path = entry.path
                    if '.jpg' in image_path:
                        row += 1
                        cell = sheet.Cells(row+1, 4)  # 从第二行开始写入图片
                        shape = sheet.Shapes.AddPicture(image_path, LinkToFile=False, SaveWithDocument=True, Left=cell.Left, Top=cell.Top, Width=-1, Height=-1)
                        # 调整图片位置使其居中
                        shape.Left = cell.Left + (cell.Width - shape.Width) / 2
                        shape.Top = cell.Top + (cell.Height - shape.Height) / 2
                        # 设置单元格数据
                        name_data=os.path.basename(image_path).replace('.jpg','').split('~')
                        sheet.Cells(row+1, 3).Value = name_data[0]
                        sheet.Cells(row+1, 6).Value = name_data[1]
                        # 导表进度
                        xlsx_progress += 1
                        data = str(xlsx_progress) + '/' + str(len(os.listdir(path))) + '  ' + name_data[0]
                        print("\033[32m" + data + "\033[0m")
                wb.SaveAs(output_path + '\\资产表格.xlsx')
                wb.Close()
            bpy.ops.wm.console_toggle()
            output_path = 'D:\\Blender_填表工具缓存'
            delete_cache() # 删除缓存
            print('配置合成器')
            set_compositor(node_path) # 设置合成器
            print('识别并获取物体')
            storage_data() # 储存集合,物体
            filter_collection() # 筛选集合
            print('还原集合、物体配置')
            restore_data() # 还原集合,物体
            print('导入至表格')
            import_xlsx(xlsx_path) # 导入至表格
            print('完成')
            bpy.ops.wm.console_toggle()
            os.startfile(output_path)
            ## 启动xlsx文件
            #file_path = output_path + '\\资产表格.xlsx'
            #try:
            #    os.startfile(file_path)  # 使用os模块中的startfile函数启动指定文件
            #except OSError as e:
            #    print(f"Error: {e}")
            self.report({'INFO'}, message='ok！')
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        if (len(py['sna_pre_list']) == 0):
            layout.label(text='未发现问题集合，确定运行！', icon_value=0)
        else:
            col_B4AB4 = layout.column(heading='', align=True)
            col_B4AB4.alert = True
            col_B4AB4.enabled = True
            col_B4AB4.active = True
            col_B4AB4.use_property_split = False
            col_B4AB4.use_property_decorate = False
            col_B4AB4.scale_x = 1.0
            col_B4AB4.scale_y = 1.0
            col_B4AB4.alignment = 'Expand'.upper()
            col_B4AB4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_B4AB4.label(text='疑似问题集合', icon_value=0)
            for i_FD129 in range(len(py['sna_pre_list'])):
                op = col_B4AB4.operator('sn.dummy_button_operator', text=py['sna_pre_list'][i_FD129], icon_value=0, emboss=True, depress=False)

    def invoke(self, context, event):
        py['sna_pre_list'] = []
        data_list = None
        data_list = []
        for collection in bpy.data.collections:    
            if collection.name[-4:] == '_pre':
                check = True       
                for obj in collection.objects:
                    if obj.name == collection.name[:-4] + '_lod0' or obj.name == collection.name[:-4] + '_c1_lod0':
                        check = False
                        break
                col = collection.name.split('_')
                col_name = col[0] + '_' + col[1] + '_' + col[2]
                for obj in collection.objects:
                    obj = obj.name.split('_')
                    obj_name = obj[0] + '_' + obj[1] + '_' + obj[2]
                    if obj_name != col_name:
                        check = True
                        break
                if check:
                    data_list.append(collection.name)
        py['sna_pre_list'] = data_list
        return context.window_manager.invoke_props_dialog(self, width=300)


class SNA_OT_Open_Cache_8Dce6(bpy.types.Operator):
    bl_idname = "sna.open_cache_8dce6"
    bl_label = "Open_Cache"
    bl_description = "打开缓存目录"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        exec('import os')
        exec("os.startfile('D:\\Blender_填表工具缓存')")
        self.report({'INFO'}, message='ok！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_PT_asset_archiving_tool_22FD2)
    bpy.utils.register_class(SNA_OT_Start_Processing_9C33A)
    bpy.utils.register_class(SNA_OT_Open_Cache_8Dce6)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_PT_asset_archiving_tool_22FD2)
    bpy.utils.unregister_class(SNA_OT_Start_Processing_9C33A)
    bpy.utils.unregister_class(SNA_OT_Open_Cache_8Dce6)
