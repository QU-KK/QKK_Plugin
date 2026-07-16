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
    "name" : "Material_Tools",
    "author" : "渠奎奎", 
    "description" : "通用型材质工具",
    "blender" : (5, 0, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews
import os
import subprocess
import platform
from bpy_extras.io_utils import ImportHelper, ExportHelper




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
shader = {'sna_shader_list': [], }


def open_folder_skd(directory):
    # Normalize the path
    path = os.path.abspath(directory)
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.Popen(["open", path])
    else:  # Linux and other Unix-based systems
        subprocess.Popen(["xdg-open", path])


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def get_id_preview_id(data):
    if hasattr(data, "preview"):
        if not data.preview:
            data.preview_ensure()
        if hasattr(data.preview, "icon_id"):
            return data.preview.icon_id
    return 0


class SNA_PT_material_tools_DFC75(bpy.types.Panel):
    bl_label = '材质工具_2025.8.2'
    bl_idname = 'SNA_PT_material_tools_DFC75'
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


class SNA_OT_Shader_649Db(bpy.types.Operator):
    bl_idname = "sna.shader_649db"
    bl_label = "关联Shader"
    bl_description = "关联Shader"
    bl_options = {"REGISTER", "UNDO"}
    sna_shader_path: bpy.props.StringProperty(name='shader_path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        shader_path = self.sna_shader_path
        func_name = 'Linked_Shader'
        import os
        # 获取文件
        shader_list = []

        def Get_The_File():
            directory = ('C:\Blender_Shader')
            for file in os.listdir(directory):
                path = os.path.join(directory,file)
                if os.path.isfile(path) and file.endswith('.blend'):
                    shader_list.append(path)
        # 关联Shader

        def Linked_Shader():
            # 文件名称
            base_name = os.path.basename(shader_path)
            # 替换字符
            group_name = base_name.replace('.blend', '_GROUP')
            # 判断是否存在
            if group_name in bpy.data.node_groups:
                pass
            else:  
                # 关联节点
                bpy.ops.wm.append(directory=os.path.join(shader_path, 'NodeTree'), filename = group_name, link = True)
            # 锁定节点组
            bpy.data.node_groups[group_name].use_fake_user = True
            # 当前材质
            mat = bpy.context.object.active_material
            # 材质节点
            mat_nodes = mat.node_tree.nodes
            # 清空节点
            mat_nodes.clear()
            # 新建节点组
            node = mat_nodes.new(type ='ShaderNodeGroup')
            # 设置节点树
            node.node_tree = bpy.data.node_groups[group_name]
            # 切换至材质视口
            bpy.context.area.ui_type = 'ShaderNodeTree'
            # 解散节点组
            bpy.ops.node.group_ungroup()
            #bpy.ops.node.select_all(action='DESELECT')
            #node = mat_nodes.new(type ='ShaderNodeGroup')
            #node.node_tree = bpy.data.node_groups[group_name]
            #bpy.ops.node.mute_toggle()
            #bpy.ops.node.hide_toggle()
            #bpy.ops.node.select_all(action='DESELECT')
            # 切换回3D视口
            bpy.context.area.ui_type = 'VIEW_3D'
            #bpy.ops.file.make_paths_absolute()
        # 调用函数
        functions = {
            "Get_The_File": Get_The_File,
            "Linked_Shader": Linked_Shader,
        }
        functions[func_name]()
        bpy.ops.file.make_paths_absolute()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Shader_D6429(bpy.types.Operator):
    bl_idname = "sna.shader_d6429"
    bl_label = "Shader"
    bl_description = "Shader"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if (len(shader['sna_shader_list']) == 0):
            func_name = 'Get_The_File'
            shader_list = None
            import os
            # 获取文件
            shader_list = []

            def Get_The_File():
                directory = ('C:\Blender_Shader')
                for file in os.listdir(directory):
                    path = os.path.join(directory,file)
                    if os.path.isfile(path) and file.endswith('.blend'):
                        shader_list.append(path)
            # 关联Shader

            def Linked_Shader():
                # 文件名称
                base_name = os.path.basename(shader_path)
                # 替换字符
                group_name = base_name.replace('.blend', '_GROUP')
                # 判断是否存在
                if group_name in bpy.data.node_groups:
                    pass
                else:  
                    # 关联节点
                    bpy.ops.wm.append(directory=os.path.join(shader_path, 'NodeTree'), filename = group_name, link = True)
                # 锁定节点组
                bpy.data.node_groups[group_name].use_fake_user = True
                # 当前材质
                mat = bpy.context.object.active_material
                # 材质节点
                mat_nodes = mat.node_tree.nodes
                # 清空节点
                mat_nodes.clear()
                # 新建节点组
                node = mat_nodes.new(type ='ShaderNodeGroup')
                # 设置节点树
                node.node_tree = bpy.data.node_groups[group_name]
                # 切换至材质视口
                bpy.context.area.ui_type = 'ShaderNodeTree'
                # 解散节点组
                bpy.ops.node.group_ungroup()
                #bpy.ops.node.select_all(action='DESELECT')
                #node = mat_nodes.new(type ='ShaderNodeGroup')
                #node.node_tree = bpy.data.node_groups[group_name]
                #bpy.ops.node.mute_toggle()
                #bpy.ops.node.hide_toggle()
                #bpy.ops.node.select_all(action='DESELECT')
                # 切换回3D视口
                bpy.context.area.ui_type = 'VIEW_3D'
                #bpy.ops.file.make_paths_absolute()
            # 调用函数
            functions = {
                "Get_The_File": Get_The_File,
                "Linked_Shader": Linked_Shader,
            }
            functions[func_name]()
            shader['sna_shader_list'] = shader_list
        bpy.ops.wm.call_panel(name="SNA_PT_SHADER_LIST_35635", keep_open=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_SHADER_LIST_35635(bpy.types.Panel):
    bl_label = 'Shader_List'
    bl_idname = 'SNA_PT_SHADER_LIST_35635'
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
        col_AF01C = layout.column(heading='', align=True)
        col_AF01C.alert = False
        col_AF01C.enabled = True
        col_AF01C.active = True
        col_AF01C.use_property_split = False
        col_AF01C.use_property_decorate = False
        col_AF01C.scale_x = 1.0
        col_AF01C.scale_y = 1.0
        col_AF01C.alignment = 'Expand'.upper()
        col_AF01C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        for i_D54E5 in range(len(shader['sna_shader_list'])):
            op = col_AF01C.operator('sna.shader_649db', text=os.path.basename(shader['sna_shader_list'][i_D54E5]).replace('.blend', ''), icon_value=0, emboss=True, depress=False)
            op.sna_shader_path = shader['sna_shader_list'][i_D54E5]


def sna_func_055CC(layout_function, img):
    col_3FE3A = layout_function.column(heading='', align=True)
    col_3FE3A.alert = False
    col_3FE3A.enabled = True
    col_3FE3A.active = True
    col_3FE3A.use_property_split = False
    col_3FE3A.use_property_decorate = False
    col_3FE3A.scale_x = 1.0
    col_3FE3A.scale_y = 1.0
    col_3FE3A.alignment = 'Expand'.upper()
    col_3FE3A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_29D9F = col_3FE3A.row(heading='', align=True)
    row_29D9F.alert = (img.name != os.path.basename(bpy.path.abspath(img.filepath)))
    row_29D9F.enabled = (not (len(img.packed_files) != 0))
    row_29D9F.active = True
    row_29D9F.use_property_split = False
    row_29D9F.use_property_decorate = False
    row_29D9F.scale_x = 1.0
    row_29D9F.scale_y = 1.0
    row_29D9F.alignment = 'Expand'.upper()
    row_29D9F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_29D9F.prop(img, 'name', text='', icon_value=0, emboss=True)
    op = row_29D9F.operator('sna.my_generic_operator_e47b8', text='', icon_value=string_to_icon('CHECKMARK'), emboss=True, depress=False)
    op.sna_oldimgname = bpy.path.abspath(img.filepath)
    op.sna_newimgname = img.name
    row_06849 = col_3FE3A.row(heading='', align=True)
    row_06849.alert = False
    row_06849.enabled = True
    row_06849.active = True
    row_06849.use_property_split = False
    row_06849.use_property_decorate = False
    row_06849.scale_x = 1.0
    row_06849.scale_y = 1.0
    row_06849.alignment = 'Expand'.upper()
    row_06849.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_06849.prop(img.colorspace_settings, 'name', text='', icon_value=0, emboss=True)
    row_E6E82 = row_06849.row(heading='', align=True)
    row_E6E82.alert = False
    row_E6E82.enabled = (not (len(img.packed_files) != 0))
    row_E6E82.active = True
    row_E6E82.use_property_split = False
    row_E6E82.use_property_decorate = False
    row_E6E82.scale_x = 1.0
    row_E6E82.scale_y = 1.0
    row_E6E82.alignment = 'Expand'.upper()
    row_E6E82.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = row_E6E82.operator('sna.my_generic_operator_246a7', text='', icon_value=string_to_icon('FOLDER_REDIRECT'), emboss=True, depress=False)
    op.sna_imgpath = bpy.path.abspath(img.filepath)
    op = row_E6E82.operator('sna.my_generic_operator_2a3bd', text='', icon_value=string_to_icon('IMAGE_BACKGROUND'), emboss=True, depress=False)
    op.sna_imgpath = bpy.path.abspath(img.filepath)
    op = row_E6E82.operator('sna.my_generic_operator_dfe15', text='', icon_value=string_to_icon('FILE_REFRESH'), emboss=True, depress=False)
    op.sna_img_name = img.name
    op = row_06849.operator('sna.my_generic_operator_6afaf', text='', icon_value=string_to_icon('FILE_TICK'), emboss=True, depress=False)
    op.sna_img_name = img.name
    if (len(img.packed_files) != 0):
        row_E6CCC = col_3FE3A.row(heading='', align=True)
        row_E6CCC.alert = False
        row_E6CCC.enabled = True
        row_E6CCC.active = True
        row_E6CCC.use_property_split = False
        row_E6CCC.use_property_decorate = False
        row_E6CCC.scale_x = 1.0
        row_E6CCC.scale_y = 1.0
        row_E6CCC.alignment = 'Expand'.upper()
        row_E6CCC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_E6CCC.label(text='已打包', icon_value=string_to_icon('DECORATE_LOCKED'))
        op = row_E6CCC.operator('sna.my_generic_operator_24614', text='', icon_value=string_to_icon('DECORATE_UNLOCKED'), emboss=True, depress=False)
        op.sna_img_name = img.name
    else:
        col_A321B = col_3FE3A.column(heading='', align=True)
        col_A321B.alert = (not os.path.exists(bpy.path.abspath(img.filepath)))
        col_A321B.enabled = True
        col_A321B.active = True
        col_A321B.use_property_split = False
        col_A321B.use_property_decorate = False
        col_A321B.scale_x = 1.0
        col_A321B.scale_y = 1.0
        col_A321B.alignment = 'Expand'.upper()
        col_A321B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_A6E17 = col_A321B.row(heading='', align=True)
        row_A6E17.alert = False
        row_A6E17.enabled = True
        row_A6E17.active = True
        row_A6E17.use_property_split = False
        row_A6E17.use_property_decorate = False
        row_A6E17.scale_x = 1.0
        row_A6E17.scale_y = 1.0
        row_A6E17.alignment = 'Expand'.upper()
        row_A6E17.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_A6E17.prop(img, 'filepath', text='', icon_value=0, emboss=True)
        op = row_A6E17.operator('sna.my_generic_operator_66857', text='', icon_value=string_to_icon('DECORATE_LOCKED'), emboss=True, depress=False)
        op.sna_img_name = img.name


class SNA_OT_My_Generic_Operator_246A7(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_246a7"
    bl_label = "打开目录"
    bl_description = "打开目录"
    bl_options = {"REGISTER", "UNDO"}
    sna_imgpath: bpy.props.StringProperty(name='imgpath', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        imgpath = os.path.dirname(self.sna_imgpath)
        imgname = os.path.basename(self.sna_imgpath)
        import subprocess
        # 指定目录的路径
        directory_path = imgpath  # 将路径替换为您要打开的目录的实际路径
        # 选中特定的文件（假设文件名为example.txt）
        file_to_select = imgname  # 将文件名替换为您要选中的文件名
        # 在命令行中使用Explorer来选中文件
        subprocess.Popen(f'explorer /select, "{os.path.join(directory_path, file_to_select)}"')
        self.report({'INFO'}, message='打开目录，定位图片！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_2A3Bd(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2a3bd"
    bl_label = "打开图片"
    bl_description = "打开图片"
    bl_options = {"REGISTER", "UNDO"}
    sna_imgpath: bpy.props.StringProperty(name='imgpath', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        open_folder_skd(self.sna_imgpath)
        self.report({'INFO'}, message='打开图片！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Dfe15(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_dfe15"
    bl_label = "重载图像"
    bl_description = "重载图像"
    bl_options = {"REGISTER", "UNDO"}
    sna_img_name: bpy.props.StringProperty(name='img_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.blend_data.images[self.sna_img_name].reload()
        self.report({'INFO'}, message='重载完成！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_6Afaf(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6afaf"
    bl_label = "另存图像"
    bl_description = "另存图像"
    bl_options = {"REGISTER", "UNDO"}
    sna_img_name: bpy.props.StringProperty(name='img_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.area.ui_type = 'IMAGE_EDITOR'
        imgname = self.sna_img_name
        # 获取图像
        image = bpy.data.images[imgname]  # 用您的图像名称替换 'YourImageName'
        # 获取图像编辑器区域
        for area in bpy.context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                # 设置活动图像
                area.spaces.active.image = image
                break
        bpy.ops.image.save_as('INVOKE_DEFAULT', )
        bpy.context.area.ui_type = 'VIEW_3D'
        self.report({'INFO'}, message='另存图片！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_E47B8(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e47b8"
    bl_label = "应用图像名称"
    bl_description = "应用图像名称"
    bl_options = {"REGISTER", "UNDO"}
    sna_oldimgname: bpy.props.StringProperty(name='oldimgname', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_newimgname: bpy.props.StringProperty(name='newimgname', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        oldimgname = self.sna_oldimgname
        newimgname = self.sna_newimgname
        # 指定文件的完整路径
        file_path = oldimgname  # 将路径替换为要修改文件名的文件的实际路径
        # 新的文件名
        new_file_name = newimgname
        # 执行文件名修改
        os.rename(file_path, os.path.join(os.path.dirname(file_path), new_file_name))
        bpy.context.blend_data.images[self.sna_newimgname].filepath = os.path.join(os.path.dirname(self.sna_oldimgname),self.sna_newimgname)
        self.report({'INFO'}, message='应用名称完成！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_24614(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_24614"
    bl_label = "解包图像"
    bl_description = "解包图像"
    bl_options = {"REGISTER", "UNDO"}
    sna_img_name: bpy.props.StringProperty(name='img_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.blend_data.images[self.sna_img_name].unpack()
        self.report({'INFO'}, message='解包完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_66857(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_66857"
    bl_label = "打包图像"
    bl_description = "打包图像"
    bl_options = {"REGISTER", "UNDO"}
    sna_img_name: bpy.props.StringProperty(name='img_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.blend_data.images[self.sna_img_name].pack()
        self.report({'INFO'}, message='打包完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_4CD8E(layout_function, ):
    if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs", globals(), locals()):
        box_E880D = layout_function.box()
        box_E880D.alert = False
        box_E880D.enabled = True
        box_E880D.active = True
        box_E880D.use_property_split = False
        box_E880D.use_property_decorate = False
        box_E880D.alignment = 'Expand'.upper()
        box_E880D.scale_x = 1.0
        box_E880D.scale_y = 1.0
        if not True: box_E880D.operator_context = "EXEC_DEFAULT"
        col_0B275 = box_E880D.column(heading='', align=True)
        col_0B275.alert = False
        col_0B275.enabled = True
        col_0B275.active = True
        col_0B275.use_property_split = False
        col_0B275.use_property_decorate = False
        col_0B275.scale_x = 1.0
        col_0B275.scale_y = 1.0
        col_0B275.alignment = 'Expand'.upper()
        col_0B275.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        for i_75A1F in range(len(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs)):
            if ('BOOLEAN' == bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F].type):
                col_0B275.label(text=bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F].name, icon_value=0)
            else:
                if (bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F].type == 'RGBA'):
                    split_0ABD0 = col_0B275.split(factor=0.5, align=True)
                    split_0ABD0.alert = False
                    split_0ABD0.enabled = True
                    split_0ABD0.active = True
                    split_0ABD0.use_property_split = False
                    split_0ABD0.use_property_decorate = False
                    split_0ABD0.scale_x = 1.0
                    split_0ABD0.scale_y = 1.0
                    split_0ABD0.alignment = 'Expand'.upper()
                    if not True: split_0ABD0.operator_context = "EXEC_DEFAULT"
                    split_0ABD0.label(text=bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F].name, icon_value=0)
                    split_0ABD0.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F], 'default_value', text='', icon_value=0, emboss=True)
                else:
                    if (bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F].type == 'VECTOR'):
                        row_51AB1 = col_0B275.row(heading='', align=True)
                        row_51AB1.alert = False
                        row_51AB1.enabled = True
                        row_51AB1.active = True
                        row_51AB1.use_property_split = False
                        row_51AB1.use_property_decorate = False
                        row_51AB1.scale_x = 1.0
                        row_51AB1.scale_y = 1.0
                        row_51AB1.alignment = 'Expand'.upper()
                        row_51AB1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        row_51AB1.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F], 'default_value', text=bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F].name, icon_value=0, emboss=True)
                    else:
                        if (bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F].type == 'VALUE'):
                            col_0B275.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F], 'default_value', text=bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_75A1F].name, icon_value=0, emboss=True)
    else:
        layout_function.label(text='无项目Shader', icon_value=0)


def sna_func_D01F1(layout_function, ):
    if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs", globals(), locals()):
        grid_63111 = layout_function.grid_flow(columns=2, row_major=True, even_columns=True, even_rows=False, align=True)
        grid_63111.enabled = True
        grid_63111.active = True
        grid_63111.use_property_split = False
        grid_63111.use_property_decorate = False
        grid_63111.alignment = 'Expand'.upper()
        grid_63111.scale_x = 1.0
        grid_63111.scale_y = 1.0
        if not True: grid_63111.operator_context = "EXEC_DEFAULT"
        for i_C1188 in range(len(bpy.context.view_layer.objects.active.active_material.node_tree.nodes)):
            if (bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].type == 'TEX_IMAGE'):
                box_AB4C4 = grid_63111.box()
                box_AB4C4.alert = False
                box_AB4C4.enabled = True
                box_AB4C4.active = True
                box_AB4C4.use_property_split = False
                box_AB4C4.use_property_decorate = False
                box_AB4C4.alignment = 'Expand'.upper()
                box_AB4C4.scale_x = 1.0
                box_AB4C4.scale_y = 1.0
                if not True: box_AB4C4.operator_context = "EXEC_DEFAULT"
                col_09021 = box_AB4C4.column(heading='', align=True)
                col_09021.alert = False
                col_09021.enabled = True
                col_09021.active = True
                col_09021.use_property_split = False
                col_09021.use_property_decorate = False
                col_09021.scale_x = 1.0
                col_09021.scale_y = 1.0
                col_09021.alignment = 'Expand'.upper()
                col_09021.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_9D661 = col_09021.row(heading='', align=False)
                row_9D661.alert = False
                row_9D661.enabled = True
                row_9D661.active = True
                row_9D661.use_property_split = False
                row_9D661.use_property_decorate = False
                row_9D661.scale_x = 1.0
                row_9D661.scale_y = 1.0
                row_9D661.alignment = 'Expand'.upper()
                row_9D661.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_70E50 = row_9D661.row(heading='', align=False)
                row_70E50.alert = False
                row_70E50.enabled = True
                row_70E50.active = True
                row_70E50.use_property_split = False
                row_70E50.use_property_decorate = False
                row_70E50.scale_x = 1.0
                row_70E50.scale_y = 1.0
                row_70E50.alignment = 'Left'.upper()
                row_70E50.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_70E50.label(text=bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].name, icon_value=0)
                if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].image.name", globals(), locals()):
                    row_0025E = row_9D661.row(heading='', align=False)
                    row_0025E.alert = False
                    row_0025E.enabled = True
                    row_0025E.active = True
                    row_0025E.use_property_split = False
                    row_0025E.use_property_decorate = False
                    row_0025E.scale_x = 1.0
                    row_0025E.scale_y = 1.0
                    row_0025E.alignment = 'Right'.upper()
                    row_0025E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    row_0025E.label(text=str(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].image.size[0]) + ' X ' + str(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].image.size[1]), icon_value=0)
                box_CF574 = col_09021.box()
                box_CF574.alert = False
                box_CF574.enabled = True
                box_CF574.active = True
                box_CF574.use_property_split = False
                box_CF574.use_property_decorate = False
                box_CF574.alignment = 'Expand'.upper()
                box_CF574.scale_x = 1.0
                box_CF574.scale_y = 1.0
                if not True: box_CF574.operator_context = "EXEC_DEFAULT"
                if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].image.name", globals(), locals()):
                    box_CF574.template_icon(icon_value=get_id_preview_id(bpy.data.images[bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].image.name]), scale=5.0)
                else:
                    col_BD791 = box_CF574.column(heading='', align=True)
                    col_BD791.alert = False
                    col_BD791.enabled = True
                    col_BD791.active = True
                    col_BD791.use_property_split = False
                    col_BD791.use_property_decorate = False
                    col_BD791.scale_x = 1.0
                    col_BD791.scale_y = 5.0
                    col_BD791.alignment = 'Expand'.upper()
                    col_BD791.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    col_BD791.separator(factor=1.0)
                    op = col_BD791.operator('sna.my_generic_operator_6f86e', text='', icon_value=string_to_icon('NEWFOLDER'), emboss=False, depress=False)
                    op.sna_nod_name = bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].name
                    col_BD791.separator(factor=1.0)
                col_09021.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188], 'image', text='', icon_value=0, emboss=True)
                if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].image.name", globals(), locals()):
                    layout_function = col_09021
                    sna_func_055CC(layout_function, bpy.context.view_layer.objects.active.active_material.node_tree.nodes[i_C1188].image)
    else:
        layout_function.label(text='无项目Shader', icon_value=0)


class SNA_OT_My_Generic_Operator_6F86E(bpy.types.Operator, ImportHelper):
    bl_idname = "sna.my_generic_operator_6f86e"
    bl_label = "导入图像"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    filter_glob: bpy.props.StringProperty( default='*.png;*.jpg;*.exr;*.tga;*.tif', options={'HIDDEN'} )
    sna_nod_name: bpy.props.StringProperty(name='nod_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        path = self.filepath
        nod_name = self.sna_nod_name
        func_name = 'Import_Img'
        import os
        # 打开目录

        def Open_Directory():
            # 指定目录的路径
            directory_path = imgpath  # 将路径替换为您要打开的目录的实际路径
            # 选中特定的文件（假设文件名为example.txt）
            file_to_select = imgname  # 将文件名替换为您要选中的文件名
            # 在命令行中使用Explorer来选中文件
            subprocess.Popen(f'explorer /select, "{os.path.join(directory_path, file_to_select)}"')
        # 打开图像

        def Open_Img():
            # 获取图像
            image = bpy.data.images[imgname]  # 用您的图像名称替换 'YourImageName'
            # 获取图像编辑器区域
            for area in bpy.context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    # 设置活动图像
                    area.spaces.active.image = image
                    break
        # 导入图像

        def Import_Img():
            # 绝对路径
            img_path = bpy.path.abspath(path)  
            # 图像名称
            img_name = os.path.basename(img_path)  
            # 导入图像
            bpy.ops.image.open(filepath=img_path)  
            # 获取图像
            img = bpy.data.images[img_name]  
            # 获取当前材质的节点树中的指定节点
            nod = bpy.context.object.active_material.node_tree.nodes[nod_name]  
            # 将图像赋值给节点，并确保节点未被静音
            nod.image = img  
            nod.mute = False  
        # 调用函数
        functions = {
            "Open_Directory": Open_Directory,
            "Open_Img": Import_Img,
            "Import_Img": Import_Img,
        }
        functions[func_name]()
        self.report({'INFO'}, message='导入成功！')
        return {"FINISHED"}


class SNA_PT_material_tools_parameter_61AD5(bpy.types.Panel):
    bl_label = '参数'
    bl_idname = 'SNA_PT_material_tools_parameter_61AD5'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_material_tools_DFC75'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_1E5C6 = layout.column(heading='', align=False)
        col_1E5C6.alert = False
        col_1E5C6.enabled = True
        col_1E5C6.active = True
        col_1E5C6.use_property_split = False
        col_1E5C6.use_property_decorate = False
        col_1E5C6.scale_x = 1.0
        col_1E5C6.scale_y = 1.0
        col_1E5C6.alignment = 'Expand'.upper()
        col_1E5C6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_0AC8E = col_1E5C6.row(heading='', align=False)
        row_0AC8E.alert = False
        row_0AC8E.enabled = True
        row_0AC8E.active = True
        row_0AC8E.use_property_split = False
        row_0AC8E.use_property_decorate = False
        row_0AC8E.scale_x = 1.0
        row_0AC8E.scale_y = 1.5
        row_0AC8E.alignment = 'Expand'.upper()
        row_0AC8E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_0AC8E.prop(bpy.context.scene, 'sna_mat_ui_switch', text=bpy.context.scene.sna_mat_ui_switch, icon_value=0, emboss=True, expand=True)
        if (bpy.context.scene.sna_mat_ui_switch == '参数'):
            layout_function = col_1E5C6
            sna_func_4CD8E(layout_function, )
        else:
            layout_function = col_1E5C6
            sna_func_D01F1(layout_function, )


class SNA_PT_SHADER__747B4(bpy.types.Panel):
    bl_label = 'Shader '
    bl_idname = 'SNA_PT_SHADER__747B4'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_material_tools_DFC75'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        if (bpy.context.view_layer.objects.active != None):
            box_81805 = layout.box()
            box_81805.alert = False
            box_81805.enabled = True
            box_81805.active = True
            box_81805.use_property_split = False
            box_81805.use_property_decorate = False
            box_81805.alignment = 'Expand'.upper()
            box_81805.scale_x = 1.0
            box_81805.scale_y = 1.0
            if not True: box_81805.operator_context = "EXEC_DEFAULT"
            col_E2812 = box_81805.column(heading='', align=False)
            col_E2812.alert = False
            col_E2812.enabled = True
            col_E2812.active = True
            col_E2812.use_property_split = False
            col_E2812.use_property_decorate = False
            col_E2812.scale_x = 1.0
            col_E2812.scale_y = 1.0
            col_E2812.alignment = 'Expand'.upper()
            col_E2812.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if (len(bpy.context.view_layer.objects.active.material_slots) != 0):
                col_E2812.prop(bpy.context.view_layer.objects.active.material_slots[bpy.context.view_layer.objects.active.active_material_index], 'material', text='', icon_value=0, emboss=True)
            else:
                op = col_E2812.operator('object.material_slot_add', text='增加材质槽', icon_value=0, emboss=True, depress=False)
            if (bpy.context.object.active_material != None):
                col_3CD69 = col_E2812.column(heading='', align=False)
                col_3CD69.alert = False
                col_3CD69.enabled = True
                col_3CD69.active = True
                col_3CD69.use_property_split = False
                col_3CD69.use_property_decorate = False
                col_3CD69.scale_x = 1.0
                col_3CD69.scale_y = 1.0
                col_3CD69.alignment = 'Expand'.upper()
                col_3CD69.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_3CD69.label(text='当前Shader：', icon_value=0)
                op = col_3CD69.operator('sna.shader_d6429', text=(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].node_tree.name if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].node_tree.name", globals(), locals()) else '无项目Shader'), icon_value=string_to_icon('SHADING_RENDERED'), emboss=True, depress=False)
        else:
            layout.label(text='需要选中模型', icon_value=0)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_mat_ui_switch = bpy.props.EnumProperty(name='mat_ui_switch', description='', items=[('参数', '参数', '', 0, 0), ('纹理', '纹理', '', 0, 1)])
    bpy.utils.register_class(SNA_PT_material_tools_DFC75)
    bpy.utils.register_class(SNA_OT_Shader_649Db)
    bpy.utils.register_class(SNA_OT_Shader_D6429)
    bpy.utils.register_class(SNA_PT_SHADER_LIST_35635)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_246A7)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2A3Bd)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Dfe15)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6Afaf)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E47B8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_24614)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_66857)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6F86E)
    bpy.utils.register_class(SNA_PT_material_tools_parameter_61AD5)
    bpy.utils.register_class(SNA_PT_SHADER__747B4)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_mat_ui_switch
    bpy.utils.unregister_class(SNA_PT_material_tools_DFC75)
    bpy.utils.unregister_class(SNA_OT_Shader_649Db)
    bpy.utils.unregister_class(SNA_OT_Shader_D6429)
    bpy.utils.unregister_class(SNA_PT_SHADER_LIST_35635)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_246A7)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2A3Bd)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Dfe15)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6Afaf)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E47B8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_24614)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_66857)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6F86E)
    bpy.utils.unregister_class(SNA_PT_material_tools_parameter_61AD5)
    bpy.utils.unregister_class(SNA_PT_SHADER__747B4)
