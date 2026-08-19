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
    "blender" : (5, 2, 0),
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


class SNA_PT_material_tools_1D1DD(bpy.types.Panel):
    bl_label = '材质工具_2026.8.3'
    bl_idname = 'SNA_PT_material_tools_1D1DD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '材质'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout


class SNA_OT_Shader_Mat_2F193(bpy.types.Operator):
    bl_idname = "sna.shader_mat_2f193"
    bl_label = "Shader_Mat"
    bl_description = "打开材质面板"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_material_tools_1D1DD", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


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
        Blender_Path = self.sna_shader_path
        #Shader_Name = 'ZMD_Lit_Two'
        #Blender_Path = 'C:\\Blender_Shader\\ZMD_Lit_Two.blend\\Material\\'
        # 清理重名的旧材质，防止冲突
        Old_Mat = bpy.data.materials.get(Shader_Name)
        if Old_Mat:
            bpy.data.materials.remove(Old_Mat)
        # 追加外部材质并修正节点组引用
        bpy.ops.wm.append(directory=Blender_Path, filename=Shader_Name, link=False)
        New_Mat = bpy.data.materials.get(Shader_Name)
        Node_Name = New_Mat.node_tree.nodes['Shader'].node_tree.name
        if Node_Name != Shader_Name:
            New_Mat.node_tree.nodes['Shader'].node_tree = bpy.data.node_groups[Shader_Name]
            bpy.data.node_groups.remove(bpy.data.node_groups[Node_Name])
        # 记录当前物体材质，并临时替换为新材质
        Active_Mat = bpy.context.active_object.active_material
        bpy.context.active_object.active_material = New_Mat
        # 切换至材质编辑器，复制新材质的节点
        bpy.context.area.ui_type = 'ShaderNodeTree'
        bpy.ops.node.select_all(action='SELECT')
        bpy.ops.node.clipboard_copy()
        # 删除临时材质，清空原材质节点
        bpy.context.blend_data.materials.remove(material=New_Mat)
        # 将复制的节点粘贴到原材质中，并切回3D视图
        Active_Mat.node_tree.nodes.clear()
        bpy.context.active_object.active_material = Active_Mat
        bpy.context.area.ui_type = 'ShaderNodeTree'
        bpy.ops.node.select_all(action='SELECT')
        bpy.ops.node.clipboard_paste()
        bpy.context.area.ui_type = 'VIEW_3D'
        bpy.context.view_layer.objects.active.select_set(True)
        bpy.ops.file.make_paths_absolute()
        self.report({'INFO'}, message='OK！')
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
            shader_list = None
            # 获取文件
            dir_path = os.path.dirname(os.path.abspath(__file__))
            directory=dir_path.split('Blender_Script')[0]+'Blender_Shader'
            shader_list = []
            #directory = ('C:\Blender_Shader')
            for file in os.listdir(directory):
                path = os.path.join(directory,file)
                if os.path.isfile(path) and file.endswith('.blend'):
                    shader_list.append(path)
            shader['sna_shader_list'] = shader_list
        bpy.ops.wm.call_panel(name="SNA_PT_SHADER_LIST_EC7B5", keep_open=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_SHADER_LIST_EC7B5(bpy.types.Panel):
    bl_label = 'Shader_List'
    bl_idname = 'SNA_PT_SHADER_LIST_EC7B5'
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
            op = col_AF01C.operator('sna.input_shader_21057', text=os.path.basename(shader['sna_shader_list'][i_D54E5]).replace('.blend', ''), icon_value=0, emboss=True, depress=False)
            op.sna_shader_name = os.path.basename(shader['sna_shader_list'][i_D54E5]).replace('.blend', '')
            op.sna_blender_path = os.path.join(shader['sna_shader_list'][i_D54E5],'Material')


class SNA_OT_Input_Shader_21057(bpy.types.Operator):
    bl_idname = "sna.input_shader_21057"
    bl_label = "Input_Shader"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_shader_name: bpy.props.StringProperty(name='Shader_Name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_blender_path: bpy.props.StringProperty(name='Blender_Path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):        
        
        # 全局UV命名
        for obj in bpy.context.blend_data.objects:
            if obj.type == 'MESH':    
                # 遍历该对象的所有 UV 通道（按通道顺序索引）
                for index, uv_layer in enumerate(obj.data.uv_layers):
                    # 生成新的名称，例如：1U, 2U, 3U...
                    new_name = f"{index + 1}U"
                    # 修改 UV 通道名称
                    uv_layer.name = new_name
                print("UV通道名称已重命名完成！")
    
        # 设置Shader
        Shader_Name = self.sna_shader_name
        Blender_Path = self.sna_blender_path
        #Shader_Name = 'ZMD_Lit_Two'
        #Blender_Path = 'C:\\Blender_Shader\\ZMD_Lit_Two.blend\\Material\\'
        # 清理重名的旧材质，防止冲突
        Old_Mat = bpy.data.materials.get(Shader_Name)
        if Old_Mat:
            bpy.data.materials.remove(Old_Mat)
        # 追加外部材质并修正节点组引用
        bpy.ops.wm.append(directory=Blender_Path, filename=Shader_Name, link=False)
        New_Mat = bpy.data.materials.get(Shader_Name)
        Node_Name = New_Mat.node_tree.nodes['Shader'].node_tree.name
        if Node_Name != Shader_Name:
            New_Mat.node_tree.nodes['Shader'].node_tree = bpy.data.node_groups[Shader_Name]
            bpy.data.node_groups.remove(bpy.data.node_groups[Node_Name])
        # 记录当前物体材质，并临时替换为新材质
        Active_Mat = bpy.context.active_object.active_material
        bpy.context.active_object.active_material = New_Mat
        # 切换至材质编辑器，复制新材质的节点
        bpy.context.area.ui_type = 'ShaderNodeTree'
        bpy.ops.node.select_all(action='SELECT')
        bpy.ops.node.clipboard_copy()
        # 删除临时材质，清空原材质节点
        bpy.context.blend_data.materials.remove(material=New_Mat)
        # 将复制的节点粘贴到原材质中，并切回3D视图
        Active_Mat.node_tree.nodes.clear()
        bpy.context.active_object.active_material = Active_Mat
        bpy.context.area.ui_type = 'ShaderNodeTree'
        bpy.ops.node.select_all(action='SELECT')
        bpy.ops.node.clipboard_paste()
        bpy.context.area.ui_type = 'VIEW_3D'
        bpy.context.view_layer.objects.active.select_set(True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


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


def sna_func_3C3A3(layout_function, ):
    box_E48C2 = layout_function.box()
    box_E48C2.alert = False
    box_E48C2.enabled = True
    box_E48C2.active = True
    box_E48C2.use_property_split = False
    box_E48C2.use_property_decorate = False
    box_E48C2.alignment = 'Expand'.upper()
    box_E48C2.scale_x = 1.0
    box_E48C2.scale_y = 1.0
    if not True: box_E48C2.operator_context = "EXEC_DEFAULT"
    col_B3203 = box_E48C2.column(heading='', align=True)
    col_B3203.alert = False
    col_B3203.enabled = True
    col_B3203.active = True
    col_B3203.use_property_split = False
    col_B3203.use_property_decorate = False
    col_B3203.scale_x = 1.0
    col_B3203.scale_y = 1.0
    col_B3203.alignment = 'Expand'.upper()
    col_B3203.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    for i_E6069 in range(len(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs)):
        if '贴图包' in bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_E6069].label:
            pass
        else:
            qkk_data = bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_E6069].label
            if '    ' in qkk_data or 'PBR通道' in qkk_data:
                col_B3203.label(text='', icon_value=0)
            else:
                if bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_E6069].is_inactive:
                    pass
                else:
                    if (bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_E6069].type == 'VECTOR'):
                        split_D220F = col_B3203.split(factor=0.5, align=True)
                        split_D220F.alert = False
                        split_D220F.enabled = True
                        split_D220F.active = True
                        split_D220F.use_property_split = False
                        split_D220F.use_property_decorate = False
                        split_D220F.scale_x = 1.0
                        split_D220F.scale_y = 1.0
                        split_D220F.alignment = 'Expand'.upper()
                        if not True: split_D220F.operator_context = "EXEC_DEFAULT"
                        split_D220F.label(text=bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_E6069].label, icon_value=0)
                        row_582F8 = split_D220F.row(heading='', align=True)
                        row_582F8.alert = False
                        row_582F8.enabled = True
                        row_582F8.active = True
                        row_582F8.use_property_split = False
                        row_582F8.use_property_decorate = False
                        row_582F8.scale_x = 1.0
                        row_582F8.scale_y = 1.0
                        row_582F8.alignment = 'Expand'.upper()
                        row_582F8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        row_582F8.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_E6069], 'default_value', text='', icon_value=0, emboss=True)
                    else:
                        split_35CAD = col_B3203.split(factor=0.5, align=True)
                        split_35CAD.alert = False
                        split_35CAD.enabled = True
                        split_35CAD.active = True
                        split_35CAD.use_property_split = False
                        split_35CAD.use_property_decorate = False
                        split_35CAD.scale_x = 1.0
                        split_35CAD.scale_y = 1.0
                        split_35CAD.alignment = 'Expand'.upper()
                        if not True: split_35CAD.operator_context = "EXEC_DEFAULT"
                        split_35CAD.label(text=bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_E6069].label, icon_value=0)
                        split_35CAD.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs[i_E6069], 'default_value', text='', icon_value=0, emboss=True)


def sna_func_D01F1(layout_function, ):
    if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].inputs", globals(), locals()):
        col_23C3A = layout_function.column(heading='', align=False)
        col_23C3A.alert = False
        col_23C3A.enabled = True
        col_23C3A.active = True
        col_23C3A.use_property_split = False
        col_23C3A.use_property_decorate = False
        col_23C3A.scale_x = 1.0
        col_23C3A.scale_y = 1.0
        col_23C3A.alignment = 'Expand'.upper()
        col_23C3A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_23C3A.separator(factor=0.5)
        split_842B7 = col_23C3A.split(factor=0.5, align=True)
        split_842B7.alert = False
        split_842B7.enabled = True
        split_842B7.active = True
        split_842B7.use_property_split = False
        split_842B7.use_property_decorate = False
        split_842B7.scale_x = 1.0
        split_842B7.scale_y = 1.2000000476837158
        split_842B7.alignment = 'Expand'.upper()
        if not True: split_842B7.operator_context = "EXEC_DEFAULT"
        op = split_842B7.operator('sna.image_color_space_abdf8', text='图像色彩空间', icon_value=0, emboss=True, depress=False)
        op = split_842B7.operator('sna.uv_name_set_3ead6', text='模型UV名称', icon_value=0, emboss=True, depress=False)
        grid_63111 = col_23C3A.grid_flow(columns=2, row_major=True, even_columns=True, even_rows=False, align=True)
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
            # 1. 转换系统绝对路径并提取文件名
            abs_new_path = bpy.path.abspath(path)
            img_name = os.path.basename(abs_new_path)
            # 2. 查找 bpy.data.images 中是否已存在同名图像
            img = bpy.data.images.get(img_name)
            if img:
                # 逻辑 1：同名图像已被打包 -> 移除包数据，更新路径并重载
                if img.packed_file:
                    img.unpack(method='REMOVE')  # 'REMOVE' 表示仅移除打包数据块，不把包写出到硬盘
                    img.filepath = path
                    img.reload()
                    print(f"[更新] 图像 '{img_name}' 原已被打包，已移除内置包并更新为新路径: {path}")
                else:
                    old_abs_path = bpy.path.abspath(img.filepath) if img.filepath else ""
                    # 逻辑 2：未打包但路径丢失（文件不存在） -> 更新路径并重载
                    if not old_abs_path or not os.path.exists(old_abs_path):
                        img.filepath = path
                        img.reload()
                        print(f"[更新] 图像 '{img_name}' 原路径丢失，已重新指定路径并刷新: {path}")
                    else:
                        # 路径正常，直接引用
                        print(f"[提示] 图像 '{img_name}' 已存在且路径正常，直接引用。")
            else:
                # 逻辑 3：不存在同名图像，直接加载导入
                img = bpy.data.images.load(path)
                print(f"[导入] 成功导入新图像数据块: {img_name}")
            # 3. 将图像赋予当前选中对象的材质节点
            obj = bpy.context.object
            if obj and obj.active_material and obj.active_material.node_tree:
                nodes = obj.active_material.node_tree.nodes
                if nod_name in nodes:
                    nod = nodes[nod_name]
                    nod.image = img
                    nod.mute = False
                    print(f"[成功] 图像已赋予节点 '{nod_name}'。")
                else:
                    print(f"[错误] 材质中找不到名称为 '{nod_name}' 的节点。")
            else:
                print("[错误] 当前未选中对象，或对象没有启用节点的材质。")
            #图像色彩空间
            # 统一将A通道设置为 “通道打包”
            img.alpha_mode = 'CHANNEL_PACKED'
            # 直接使用原始名称进行字符串包含判断
            if ("_N." in img.name) or ("_NRO." in img.name) or ("_M." in img.name):
                img.colorspace_settings.name = 'Non-Color'
                print(f"贴图 [{img.name}] 已直接设置为: Non-Color")
            elif ("_D." in img.name) or ("_E." in img.name):
                img.colorspace_settings.name = 'sRGB'
                print(f"贴图 [{img.name}] 已直接设置为: sRGB")
            #模型UV名称命名
            obj = bpy.context.active_object
            # 遍历该对象的所有 UV 通道（按通道顺序索引）
            for index, uv_layer in enumerate(obj.data.uv_layers):
                # 生成新的名称，例如：1U, 2U, 3U...
                new_name = f"{index + 1}U"        
                # 修改 UV 通道名称
                uv_layer.name = new_name            
            print("UV 通道名称已重命名完成！")
        # 调用函数
        functions = {
            "Open_Directory": Open_Directory,
            "Open_Img": Import_Img,
            "Import_Img": Import_Img,
        }
        functions[func_name]()
        self.report({'INFO'}, message='导入成功！')
        return {"FINISHED"}


class SNA_OT_Image_Color_Space_Abdf8(bpy.types.Operator):
    bl_idname = "sna.image_color_space_abdf8"
    bl_label = "Image_Color_Space"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        # 直接遍历 Blender 里的所有图像文件
        for img in bpy.data.images:
            # 统一将A通道设置为 “通道打包”
            img.alpha_mode = 'CHANNEL_PACKED'
            # 直接使用原始名称进行字符串包含判断
            if ("_N." in img.name) or ("_NRO." in img.name) or ("_M." in img.name):
                img.colorspace_settings.name = 'Non-Color'
                print(f"贴图 [{img.name}] 已直接设置为: Non-Color")
            elif ("_D." in img.name) or ("_E." in img.name):
                img.colorspace_settings.name = 'sRGB'
                print(f"贴图 [{img.name}] 已直接设置为: sRGB")
        self.report({'INFO'}, message='图像色彩空间设置完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_Name_Set_3Ead6(bpy.types.Operator):
    bl_idname = "sna.uv_name_set_3ead6"
    bl_label = "UV_Name_Set"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        # 获取当前所有选中的网格对象
        selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            print("未选中任何网格对象(Mesh)！")
        else:
            # 遍历每个选中的对象
            for obj in selected_objects:
                print(f"正在处理对象: {obj.name}")
                # 遍历该对象的所有 UV 通道（按通道顺序索引）
                for index, uv_layer in enumerate(obj.data.uv_layers):
                    # 生成新的名称，例如：1U, 2U, 3U...
                    new_name = f"{index + 1}U"
                    # 修改 UV 通道名称
                    uv_layer.name = new_name
            print("所有选中对象的 UV 通道名称已重命名完成！")
        self.report({'INFO'}, message='模型UV名称处理完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_material_tools_parameter_38332(bpy.types.Panel):
    bl_label = '参数'
    bl_idname = 'SNA_PT_material_tools_parameter_38332'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_material_tools_1D1DD'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes['Shader'].name", globals(), locals()):
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
            if (bpy.context.scene.sna_mat_ui_switch == '图像'):
                layout_function = col_1E5C6
                sna_func_D01F1(layout_function, )
            else:
                layout_function = col_1E5C6
                sna_func_3C3A3(layout_function, )


class SNA_PT_SHADER__F2352(bpy.types.Panel):
    bl_label = 'Shader '
    bl_idname = 'SNA_PT_SHADER__F2352'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 1
    bl_parent_id = 'SNA_PT_material_tools_1D1DD'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        bool1 = False
        bool2 = True
        if bool1 != True:
            # Get the active object
            obj = bpy.context.active_object
            # Check if the active object is a mesh, curve, surface, meta, font, or volume object
            if obj and obj.type in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME'):
                layout
                row = layout.row()
                # Create a list of materials
                materials = obj.material_slots
                # Create a UIList to display the materials
                row.template_list("MATERIAL_UL_matslots", "", obj, "material_slots", obj, "active_material_index")
                col = row.column(align=True)
                col.operator("object.material_slot_add", icon='ADD', text="")
                col.operator("object.material_slot_remove", icon='REMOVE', text="")
                col.separator()
                col.menu("MATERIAL_MT_context_menu", icon='DOWNARROW_HLT', text="")
                if len(materials) > 1:
                    col.separator()
                    col.operator("object.material_slot_move", icon='TRIA_UP', text="").direction = 'UP'
                    col.operator("object.material_slot_move", icon='TRIA_DOWN', text="").direction = 'DOWN'
                if obj.mode == 'EDIT':
                    row = layout.row(align=True)
                    row.operator("object.material_slot_assign", text="Assign")
                    row.operator("object.material_slot_select", text="Select")
                    row.operator("object.material_slot_deselect", text="Deselect")
                row = layout.row()
                if obj:
                    row.template_ID(obj, "active_material", new="material.new")
                    slot = getattr(bpy.context, 'material_slot', None)
                    if slot:
                        icon_link = 'MESH_DATA' if slot.link == 'DATA' else 'OBJECT_DATA'
                        row.prop(slot, "link", text="", icon=icon_link, icon_only=True)
                elif mat:
                    layout.template_ID(bpy.context.space_data, "pin_id")
                    layout.separator()
        else:
            pass
        if bool2 != True:

            def find_node_input(node, input_name):
                for input in node.inputs:
                    if input.name == input_name:
                        return input
                return None

            def panel_node_draw(layout, id_data, output_type, input_name):
                if not id_data.use_nodes:
                    layout.operator("cycles.use_shading_nodes", icon='NODETREE')
                    return False
                ntree = id_data.node_tree
                node = ntree.get_output_node(output_type)
                if node:
                    input = find_node_input(node, input_name)
                    if input:
                        layout.template_node_view(ntree, node, input)
                    else:
                        layout.label(text="Incompatible output node")
                else:
                    layout.label(text="No output node")
                return True
            # Get the active object
            obj = bpy.context.active_object
            # Check if the active object is a mesh, curve, surface, meta, font, or volume object
            if obj and obj.type in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME'):
                mat = obj.active_material
                if mat and mat.use_nodes:
                    layout
                    output_type = 'CYCLES'
                    input_name = 'Surface'
                    panel_node_draw(layout, mat, output_type, input_name)
        else:
            pass
        if (bpy.context.view_layer.objects.active != None):
            if (bpy.context.object.active_material != None):
                box_0E076 = layout.box()
                box_0E076.alert = False
                box_0E076.enabled = True
                box_0E076.active = True
                box_0E076.use_property_split = False
                box_0E076.use_property_decorate = False
                box_0E076.alignment = 'Expand'.upper()
                box_0E076.scale_x = 1.0
                box_0E076.scale_y = 1.0
                if not True: box_0E076.operator_context = "EXEC_DEFAULT"
                col_3CD69 = box_0E076.column(heading='', align=False)
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
    bpy.types.Scene.sna_mat_ui_switch = bpy.props.EnumProperty(name='mat_ui_switch', description='', items=[('图像', '图像', '', 0, 0), ('参数', '参数', '', 0, 1)])
    bpy.utils.register_class(SNA_PT_material_tools_1D1DD)
    bpy.utils.register_class(SNA_OT_Shader_Mat_2F193)
    bpy.utils.register_class(SNA_OT_Shader_649Db)
    bpy.utils.register_class(SNA_OT_Shader_D6429)
    bpy.utils.register_class(SNA_PT_SHADER_LIST_EC7B5)
    bpy.utils.register_class(SNA_OT_Input_Shader_21057)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_246A7)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2A3Bd)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Dfe15)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6Afaf)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E47B8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_24614)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_66857)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6F86E)
    bpy.utils.register_class(SNA_OT_Image_Color_Space_Abdf8)
    bpy.utils.register_class(SNA_OT_Uv_Name_Set_3Ead6)
    bpy.utils.register_class(SNA_PT_material_tools_parameter_38332)
    bpy.utils.register_class(SNA_PT_SHADER__F2352)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_mat_ui_switch
    bpy.utils.unregister_class(SNA_PT_material_tools_1D1DD)
    bpy.utils.unregister_class(SNA_OT_Shader_Mat_2F193)
    bpy.utils.unregister_class(SNA_OT_Shader_649Db)
    bpy.utils.unregister_class(SNA_OT_Shader_D6429)
    bpy.utils.unregister_class(SNA_PT_SHADER_LIST_EC7B5)
    bpy.utils.unregister_class(SNA_OT_Input_Shader_21057)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_246A7)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2A3Bd)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Dfe15)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6Afaf)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E47B8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_24614)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_66857)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6F86E)
    bpy.utils.unregister_class(SNA_OT_Image_Color_Space_Abdf8)
    bpy.utils.unregister_class(SNA_OT_Uv_Name_Set_3Ead6)
    bpy.utils.unregister_class(SNA_PT_material_tools_parameter_38332)
    bpy.utils.unregister_class(SNA_PT_SHADER__F2352)
