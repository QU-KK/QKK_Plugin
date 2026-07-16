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
    "name" : "G108_Material",
    "author" : "渠奎奎", 
    "description" : "材质赋值工具_2055.1.3",
    "blender" : (4, 2, 0),
    "version" : (4, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews
import os
from bpy.app.handlers import persistent


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


addon_keymaps = {}
_icons = None
node_tree_001 = {'sna_nod_name': [], 'sna_mat_name': [], }


def get_id_preview_id(data):
    if hasattr(data, "preview"):
        if not data.preview:
            data.preview_ensure()
        if hasattr(data.preview, "icon_id"):
            return data.preview.icon_id
    return 0


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_OT_My_Generic_Operator_9B91A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9b91a"
    bl_label = "新建材质球"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        material_9B836 = bpy.context.blend_data.materials.new(name='新建材质球', )
        bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material = material_9B836
        bpy.context.view_layer.objects.active.active_material.use_nodes = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_01951(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_01951"
    bl_label = "清空材质"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.object.active_material.node_tree.nodes.clear()
        bpy.context.area.ui_type = 'VIEW_3D'
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.context.area.ui_type = 'ShaderNodeTree'
        return context.window_manager.invoke_confirm(self, event)


class SNA_PT_material_assignment_452D5(bpy.types.Panel):
    bl_label = '材质赋值'
    bl_idname = 'SNA_PT_material_assignment_452D5'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'G108'
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout.label(text='2025.1.3版本', icon_value=0)


class SNA_OT_Pbr__Shader_703A0(bpy.types.Operator):
    bl_idname = "sna.pbr__shader_703a0"
    bl_label = "使用PBR  Shader，会清空目前材质信息。"
    bl_description = "使用PBR Shader会清空材质内所有信息"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.active_material.node_tree.nodes.clear()
        bpy.ops.sna.pbr_b1301()
        bpy.context.area.ui_type = 'VIEW_3D'
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.context.area.ui_type = 'ShaderNodeTree'
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_Shader_053Cf(bpy.types.Operator):
    bl_idname = "sna.shader_053cf"
    bl_label = "使用顶点色混  Shader，会清空目前材质信息。"
    bl_description = "使用顶点色 Shader会清空材质内所有信息"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.active_material.node_tree.nodes.clear()
        bpy.ops.sna.my_generic_operator_d27ca()
        bpy.context.area.ui_type = 'VIEW_3D'
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.context.area.ui_type = 'ShaderNodeTree'
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_D27Ca(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d27ca"
    bl_label = "顶点色材质"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.sna.my_generic_operator_3022f()
        if property_exists("bpy.context.object.active_material.node_tree.nodes['Z_材质参数'].name", globals(), locals()):
            pass
        else:
            bpy.ops.node.add_node(type="ShaderNodeGroup", use_transform=True, settings=[{"name":"node_tree", "value":"bpy.data.node_groups['Z_顶点色混合材质组']"}])
            bpy.ops.node.group_ungroup()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Pbr_B1301(bpy.types.Operator):
    bl_idname = "sna.pbr_b1301"
    bl_label = "添加Pbr材质"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.sna.my_generic_operator_3022f()
        if property_exists("bpy.context.object.active_material.node_tree.nodes['PBR_材质'].name", globals(), locals()):
            pass
        else:
            bpy.ops.node.add_node(type="ShaderNodeGroup", use_transform=True, settings=[{"name":"node_tree", "value":"bpy.data.node_groups['Z_PBR材质组']"}])
            bpy.ops.node.group_ungroup()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_3022F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3022f"
    bl_label = "加载资产"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        if ((not property_exists("bpy.data.node_groups['Z_PBR材质组']", globals(), locals())) and (not property_exists("bpy.data.node_groups['Z_PBR_材质']", globals(), locals())) and (not property_exists("bpy.data.node_groups['Z_顶点色混合材质组']", globals(), locals())) and (not property_exists("bpy.data.node_groups['Z_顶点混合材质']", globals(), locals())) and (not property_exists("bpy.data.node_groups['Z_材质参数']", globals(), locals()))):
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath((os.path.join(os.path.dirname(__file__), 'assets', 'Material_Template_3.5.blend') if (bpy.context.scene.sna_g108_material_version_switch == 'Blender3.5') else os.path.join(os.path.dirname(__file__), 'assets', 'Material_Template_4.2.blend'))) + r'\NodeTree', filename='Z_PBR材质组', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_ECD6A = None if not new_data else new_data[0]
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath((os.path.join(os.path.dirname(__file__), 'assets', 'Material_Template_3.5.blend') if (bpy.context.scene.sna_g108_material_version_switch == 'Blender3.5') else os.path.join(os.path.dirname(__file__), 'assets', 'Material_Template_4.2.blend'))) + r'\NodeTree', filename='Z_顶点色混合材质组', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_CF83D = None if not new_data else new_data[0]
            bpy.ops.sna.my_generic_operator_a4928('INVOKE_DEFAULT', )
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_A4928(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a4928"
    bl_label = "锁定"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.data.node_groups['Z_PBR材质组'].use_fake_user = True
        bpy.data.node_groups['Z_PBR_材质'].use_fake_user = True
        bpy.data.node_groups['Z_顶点色混合材质组'].use_fake_user = True
        bpy.data.node_groups['Z_顶点混合材质'].use_fake_user = True
        bpy.data.node_groups['Z_材质参数'].use_fake_user = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_ui_2E426(layout_function, node_name, node_parameters_name):
    for i_C6078 in range(len(node_parameters_name)):
        box_BD7BD = layout_function.box()
        box_BD7BD.alert = False
        box_BD7BD.enabled = True
        box_BD7BD.active = True
        box_BD7BD.use_property_split = False
        box_BD7BD.use_property_decorate = False
        box_BD7BD.alignment = 'Expand'.upper()
        box_BD7BD.scale_x = 1.0
        box_BD7BD.scale_y = 1.0
        if not True: box_BD7BD.operator_context = "EXEC_DEFAULT"
        col_BBAC8 = box_BD7BD.column(heading='', align=True)
        col_BBAC8.alert = False
        col_BBAC8.enabled = True
        col_BBAC8.active = True
        col_BBAC8.use_property_split = False
        col_BBAC8.use_property_decorate = False
        col_BBAC8.scale_x = 1.0
        col_BBAC8.scale_y = 1.0
        col_BBAC8.alignment = 'Expand'.upper()
        col_BBAC8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        for i_28249 in range(len(node_parameters_name[i_C6078])):
            row_80E79 = col_BBAC8.row(heading='', align=True)
            row_80E79.alert = False
            row_80E79.enabled = True
            row_80E79.active = True
            row_80E79.use_property_split = False
            row_80E79.use_property_decorate = False
            row_80E79.scale_x = 1.0
            row_80E79.scale_y = 1.0
            row_80E79.alignment = 'Expand'.upper()
            row_80E79.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            row_80E79.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name].inputs[node_parameters_name[i_C6078][i_28249]], 'default_value', text=node_parameters_name[i_C6078][i_28249], icon_value=0, emboss=True)


def sna_ui_890E7(layout_function, node_name):
    grid_2BAFE = layout_function.grid_flow(columns=2, row_major=True, even_columns=False, even_rows=False, align=True)
    grid_2BAFE.enabled = True
    grid_2BAFE.active = True
    grid_2BAFE.use_property_split = False
    grid_2BAFE.use_property_decorate = False
    grid_2BAFE.alignment = 'Expand'.upper()
    grid_2BAFE.scale_x = 1.0
    grid_2BAFE.scale_y = 1.0
    if not True: grid_2BAFE.operator_context = "EXEC_DEFAULT"
    for i_7F7E2 in range(len(node_name)):
        box_2EB4A = grid_2BAFE.box()
        box_2EB4A.alert = False
        box_2EB4A.enabled = True
        box_2EB4A.active = True
        box_2EB4A.use_property_split = False
        box_2EB4A.use_property_decorate = False
        box_2EB4A.alignment = 'Expand'.upper()
        box_2EB4A.scale_x = 1.0
        box_2EB4A.scale_y = 1.0
        if not True: box_2EB4A.operator_context = "EXEC_DEFAULT"
        col_DA012 = box_2EB4A.column(heading='', align=True)
        col_DA012.alert = False
        col_DA012.enabled = True
        col_DA012.active = True
        col_DA012.use_property_split = False
        col_DA012.use_property_decorate = False
        col_DA012.scale_x = 1.0
        col_DA012.scale_y = 1.0
        col_DA012.alignment = 'Expand'.upper()
        col_DA012.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_09F92 = col_DA012.split(factor=0.6000000238418579, align=False)
        split_09F92.alert = False
        split_09F92.enabled = True
        split_09F92.active = True
        split_09F92.use_property_split = False
        split_09F92.use_property_decorate = False
        split_09F92.scale_x = 1.0
        split_09F92.scale_y = 1.0
        split_09F92.alignment = 'Expand'.upper()
        if not True: split_09F92.operator_context = "EXEC_DEFAULT"
        split_09F92.label(text=node_name[i_7F7E2], icon_value=0)
        if (bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image != None):
            pass
        else:
            op = split_09F92.operator('sna.my_generic_operator_b464e', text='导入', icon_value=0, emboss=True, depress=False)
            op.sna_new_property_001 = node_name[i_7F7E2]
        if (bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image != None):
            col_DF9B0 = col_DA012.column(heading='', align=True)
            col_DF9B0.alert = False
            col_DF9B0.enabled = True
            col_DF9B0.active = True
            col_DF9B0.use_property_split = False
            col_DF9B0.use_property_decorate = False
            col_DF9B0.scale_x = 1.0
            col_DF9B0.scale_y = 1.0
            col_DF9B0.alignment = 'Expand'.upper()
            col_DF9B0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_DF9B0.label(text=str(tuple(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.size)), icon_value=0)
            col_DF9B0.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.colorspace_settings, 'name', text='', icon_value=0, emboss=True)
            col_DF9B0.template_icon(icon_value=get_id_preview_id(bpy.data.images[bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.name]), scale=6.0)
        else:
            col_DA012.separator(factor=42.0)
        col_DA012.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]], 'image', text='', icon_value=0, emboss=True)
        if property_exists("bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.name", globals(), locals()):
            col_FEBF8 = col_DA012.column(heading='', align=True)
            col_FEBF8.alert = False
            col_FEBF8.enabled = os.path.exists(bpy.path.abspath(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.filepath))
            col_FEBF8.active = True
            col_FEBF8.use_property_split = False
            col_FEBF8.use_property_decorate = False
            col_FEBF8.scale_x = 1.0
            col_FEBF8.scale_y = 1.0
            col_FEBF8.alignment = 'Expand'.upper()
            col_FEBF8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            split_87A41 = col_FEBF8.split(factor=0.8999999761581421, align=True)
            split_87A41.alert = (bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.name != os.path.basename(bpy.path.abspath(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.filepath)))
            split_87A41.enabled = True
            split_87A41.active = True
            split_87A41.use_property_split = False
            split_87A41.use_property_decorate = False
            split_87A41.scale_x = 1.0
            split_87A41.scale_y = 1.0
            split_87A41.alignment = 'Expand'.upper()
            if not True: split_87A41.operator_context = "EXEC_DEFAULT"
            split_87A41.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image, 'name', text='', icon_value=0, emboss=True)
            op = split_87A41.operator('sna.my_generic_operator_c5e64', text='', icon_value=string_to_icon('MENU_PANEL'), emboss=True, depress=False)
            op.sna_new_property = bpy.path.abspath(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.filepath)
            op.sna_new_property_001 = bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.name
            split_7AF46 = col_FEBF8.split(factor=0.5, align=True)
            split_7AF46.alert = False
            split_7AF46.enabled = True
            split_7AF46.active = True
            split_7AF46.use_property_split = False
            split_7AF46.use_property_decorate = False
            split_7AF46.scale_x = 1.0
            split_7AF46.scale_y = 1.0
            split_7AF46.alignment = 'Expand'.upper()
            if not True: split_7AF46.operator_context = "EXEC_DEFAULT"
            op = split_7AF46.operator('sna.my_generic_operator_599aa', text='打开', icon_value=0, emboss=True, depress=False)
            op.sna_new_property = bpy.path.abspath(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image.filepath)
            op = split_7AF46.operator('sna.my_generic_operator_fc9cc', text='重载', icon_value=0, emboss=True, depress=False)
            op.sna_new_property = node_name[i_7F7E2]
            col_FEBF8.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes[node_name[i_7F7E2]].image, 'filepath', text='', icon_value=0, emboss=True)


class SNA_OT_My_Generic_Operator_Fc9Cc(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_fc9cc"
    bl_label = "贴图重载"
    bl_description = "重载图片"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='图像重载节点名称', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_8EAAB in range(1):

            def delayed_7EB5C():
                bpy.context.view_layer.objects.active.active_material.node_tree.nodes[self.sna_new_property].image.reload()
            bpy.app.timers.register(delayed_7EB5C, first_interval=0.10000000149011612)
        bpy.context.view_layer.objects.active.active_material.node_tree.nodes[self.sna_new_property].image.update()
        self.report({'INFO'}, message='重载图像完毕')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_599Aa(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_599aa"
    bl_label = "打开目录"
    bl_description = "打开贴图目录"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='图像本地路径', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        imgpath = os.path.dirname(self.sna_new_property)
        imgname = os.path.basename(self.sna_new_property)
        import subprocess
        # 指定目录的路径
        directory_path = imgpath  # 将路径替换为您要打开的目录的实际路径
        # 选中特定的文件（假设文件名为example.txt）
        file_to_select = imgname  # 将文件名替换为您要选中的文件名
        # 在命令行中使用Explorer来选中文件
        subprocess.Popen(f'explorer /select, "{os.path.join(directory_path, file_to_select)}"')
        self.report({'INFO'}, message='定位图像完毕')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_B464E(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b464e"
    bl_label = "图像导入"
    bl_description = "图像导入"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='导入图像路径', description='', options={'HIDDEN'}, default='', subtype='FILE_PATH', maxlen=0)
    sna_new_property_001: bpy.props.StringProperty(name='导入图像节点名称', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        image_5C57A = bpy.context.blend_data.images.load(filepath=bpy.path.abspath(self.sna_new_property), check_existing=True, )
        bpy.context.view_layer.objects.active.active_material.node_tree.nodes[self.sna_new_property_001].image = image_5C57A
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'sna_new_property', text='', icon_value=0, emboss=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)


class SNA_OT_My_Generic_Operator_C5E64(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_c5e64"
    bl_label = "应用图像名称"
    bl_description = "应用图像名称"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='应用图像名称路径', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_new_property_001: bpy.props.StringProperty(name='图像新名称', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        oldimgname = self.sna_new_property
        newimgname = self.sna_new_property_001
        # 指定文件的完整路径
        file_path = oldimgname  # 将路径替换为要修改文件名的文件的实际路径
        # 新的文件名
        new_file_name = newimgname
        # 执行文件名修改
        os.rename(file_path, os.path.join(os.path.dirname(file_path), new_file_name))
        bpy.context.blend_data.images[self.sna_new_property_001].filepath = os.path.join(os.path.dirname(self.sna_new_property),self.sna_new_property_001)
        self.report({'INFO'}, message='名称应用完毕')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_DED65(layout_function, ):
    col_4B66E = layout_function.column(heading='', align=False)
    col_4B66E.alert = False
    col_4B66E.enabled = True
    col_4B66E.active = True
    col_4B66E.use_property_split = False
    col_4B66E.use_property_decorate = False
    col_4B66E.scale_x = 1.0
    col_4B66E.scale_y = 1.0
    col_4B66E.alignment = 'Expand'.upper()
    col_4B66E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_4B66E.prop(bpy.context.scene, 'sna_g108_material_version_switch', text='', icon_value=0, emboss=True)
    split_813E9 = col_4B66E.split(factor=0.6000000238418579, align=True)
    split_813E9.alert = False
    split_813E9.enabled = True
    split_813E9.active = True
    split_813E9.use_property_split = False
    split_813E9.use_property_decorate = False
    split_813E9.scale_x = 1.0
    split_813E9.scale_y = 1.0
    split_813E9.alignment = 'Expand'.upper()
    if not True: split_813E9.operator_context = "EXEC_DEFAULT"
    op = split_813E9.operator('sna.shader_eee96', text='Shader更新', icon_value=0, emboss=True, depress=False)
    op = split_813E9.operator('sna.my_generic_operator_8213d', text='检查', icon_value=0, emboss=True, depress=False)


class SNA_OT_Shader_Eee96(bpy.types.Operator):
    bl_idname = "sna.shader_eee96"
    bl_label = "shader更新"
    bl_description = "shader更新"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        print('移除节点组')
        for i_F2D05 in range(len(node_tree_001['sna_nod_name'])):
            if ('Z_PBR_材质' in node_tree_001['sna_nod_name'][i_F2D05] or 'Z_PBR材质组' in node_tree_001['sna_nod_name'][i_F2D05] or 'Z_材质参数' in node_tree_001['sna_nod_name'][i_F2D05] or 'Z_顶点混合材质' in node_tree_001['sna_nod_name'][i_F2D05] or 'Z_顶点色混合材质组' in node_tree_001['sna_nod_name'][i_F2D05]):
                bpy.context.blend_data.node_groups.remove(tree=bpy.data.node_groups[node_tree_001['sna_nod_name'][i_F2D05]], )
        print('成功移除')
        print('加载节点组')
        for i_0C9CA in range(len(['Z_PBR材质组', 'Z_顶点色混合材质组'])):
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath((os.path.join(os.path.dirname(__file__), 'assets', 'Material_Template_3.5.blend') if (bpy.context.scene.sna_g108_material_version_switch == 'Blender3.5') else os.path.join(os.path.dirname(__file__), 'assets', 'Material_Template_4.2.blend'))) + r'\NodeTree', filename=['Z_PBR材质组', 'Z_顶点色混合材质组'][i_0C9CA], link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_61638 = None if not new_data else new_data[0]
        bpy.ops.sna.my_generic_operator_a4928()
        print('成功加载')
        print('赋值节点组')
        for i_39D0B in range(len(bpy.data.materials)):
            print('材质名称：', bpy.data.materials[i_39D0B].name)
            if bpy.data.materials[i_39D0B].use_nodes:
                if property_exists("bpy.data.materials[i_39D0B].node_tree.nodes['PBR_材质'].node_tree", globals(), locals()):
                    bpy.data.materials[i_39D0B].node_tree.nodes['PBR_材质'].node_tree = bpy.data.node_groups['Z_PBR_材质']
                if property_exists("bpy.data.materials[i_39D0B].node_tree.nodes['Z_顶点混合材质'].node_tree", globals(), locals()):
                    bpy.data.materials[i_39D0B].node_tree.nodes['Z_顶点混合材质'].node_tree = bpy.data.node_groups['Z_顶点混合材质']
                    bpy.data.materials[i_39D0B].node_tree.nodes['Z_材质参数'].node_tree = bpy.data.node_groups['Z_材质参数']
        print('执行完毕！', '处理材质数量：', str(i_39D0B))
        self.report({'INFO'}, message='处理材质数量：' + str(i_39D0B))
        return {"FINISHED"}

    def invoke(self, context, event):
        node_tree_001['sna_nod_name'] = []
        print('获取节点组名称')
        for i_A5A07 in range(len(bpy.data.node_groups)):
            node_tree_001['sna_nod_name'].append(bpy.data.node_groups[i_A5A07].name)
        print('成功获取')
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_8213D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_8213d"
    bl_label = "检查材质"
    bl_description = "检查材质内节点是否存在.00"
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
        box_11AAE = layout.box()
        box_11AAE.alert = False
        box_11AAE.enabled = True
        box_11AAE.active = True
        box_11AAE.use_property_split = False
        box_11AAE.use_property_decorate = False
        box_11AAE.alignment = 'Expand'.upper()
        box_11AAE.scale_x = 1.0
        box_11AAE.scale_y = 1.0
        if not True: box_11AAE.operator_context = "EXEC_DEFAULT"
        col_F2A96 = box_11AAE.column(heading='', align=True)
        col_F2A96.alert = False
        col_F2A96.enabled = True
        col_F2A96.active = True
        col_F2A96.use_property_split = False
        col_F2A96.use_property_decorate = False
        col_F2A96.scale_x = 1.0
        col_F2A96.scale_y = 1.0
        col_F2A96.alignment = 'Expand'.upper()
        col_F2A96.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_F2A96.label(text='可疑材质数量：' + str(len(node_tree_001['sna_mat_name'])), icon_value=0)
        for i_B0CC2 in range(len(node_tree_001['sna_mat_name'])):
            box_B1346 = col_F2A96.box()
            box_B1346.alert = False
            box_B1346.enabled = True
            box_B1346.active = True
            box_B1346.use_property_split = False
            box_B1346.use_property_decorate = False
            box_B1346.alignment = 'Expand'.upper()
            box_B1346.scale_x = 1.0
            box_B1346.scale_y = 1.0
            if not True: box_B1346.operator_context = "EXEC_DEFAULT"
            split_B94D0 = box_B1346.split(factor=0.10000000149011612, align=True)
            split_B94D0.alert = False
            split_B94D0.enabled = True
            split_B94D0.active = True
            split_B94D0.use_property_split = False
            split_B94D0.use_property_decorate = False
            split_B94D0.scale_x = 1.0
            split_B94D0.scale_y = 1.0
            split_B94D0.alignment = 'Expand'.upper()
            if not True: split_B94D0.operator_context = "EXEC_DEFAULT"
            op = split_B94D0.operator('sna.my_generic_operator_04658', text='', icon_value=256, emboss=True, depress=False)
            op.sna_material_name = node_tree_001['sna_mat_name'][i_B0CC2]
            split_B94D0.label(text=node_tree_001['sna_mat_name'][i_B0CC2], icon_value=0)

    def invoke(self, context, event):
        sna_func_14F27()
        return context.window_manager.invoke_props_dialog(self, width=250)


def sna_func_14F27():
    node_tree_001['sna_mat_name'] = []
    for i_6A2FA in range(len(bpy.data.materials)):
        for i_3755C in range(len(bpy.data.materials[i_6A2FA].node_tree.nodes)):
            if '.0' in bpy.data.materials[i_6A2FA].node_tree.nodes[i_3755C].name:
                node_tree_001['sna_mat_name'].append(bpy.data.materials[i_6A2FA].name)
                print(bpy.data.materials[i_6A2FA].node_tree.nodes[i_3755C].name)


class SNA_OT_My_Generic_Operator_04658(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_04658"
    bl_label = "按材质选中模型"
    bl_description = "按材质选中模型"
    bl_options = {"REGISTER", "UNDO"}
    sna_material_name: bpy.props.StringProperty(name='material_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        material_name = self.sna_material_name
        # 清除当前选择
        bpy.ops.object.select_all(action='DESELECT')
        # 用于存储找到的对象列表
        selected_objects = []
        # 遍历所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象是否为网格类型
            if obj.type == 'MESH':
                # 遍历对象的材质槽
                for slot in obj.material_slots:
                    # 如果材质名称匹配，则选择对象
                    if slot.material and slot.material.name == material_name:
                        obj.select_set(True)
                        selected_objects.append(obj)  # 添加到选择的对象列表
                        break  # 找到匹配后，跳出材质槽循环
        # 如果找到至少一个对象，则激活第一个
        if selected_objects:
            bpy.context.view_layer.objects.active = selected_objects[0]
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


@persistent
def save_pre_handler_C8A05(dummy):
    for i_EED5A in range(len(bpy.data.materials)):
        for i_845D9 in range(len(bpy.data.materials[i_EED5A].node_tree.nodes)):
            if (bpy.data.materials[i_EED5A].node_tree.nodes[i_845D9].type == 'TEX_IMAGE'):
                if (bpy.data.materials[i_EED5A].node_tree.nodes[i_845D9].image == None):
                    bpy.data.materials[i_EED5A].node_tree.nodes[i_845D9].mute = True
                else:
                    bpy.data.materials[i_EED5A].node_tree.nodes[i_845D9].mute = False
    print('纹理图像启用与弃用执行完毕！')


def sna_pbr_F5D94(layout_function, ):
    col_BCFBF = layout_function.column(heading='', align=True)
    col_BCFBF.alert = False
    col_BCFBF.enabled = True
    col_BCFBF.active = True
    col_BCFBF.use_property_split = False
    col_BCFBF.use_property_decorate = False
    col_BCFBF.scale_x = 1.0
    col_BCFBF.scale_y = 1.0
    col_BCFBF.alignment = 'Expand'.upper()
    col_BCFBF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_BCFBF.label(text='PBR材质', icon_value=string_to_icon('MATERIAL_DATA'))
    col_BCFBF.separator(factor=2.0)
    col_BCFBF.prop(bpy.context.view_layer.objects.active.active_material, 'use_nodes', text='材质开启', icon_value=0, emboss=True)
    col_B1377 = col_BCFBF.column(heading='', align=True)
    col_B1377.alert = False
    col_B1377.enabled = bpy.context.view_layer.objects.active.active_material.use_nodes
    col_B1377.active = True
    col_B1377.use_property_split = False
    col_B1377.use_property_decorate = False
    col_B1377.scale_x = 1.0
    col_B1377.scale_y = 1.0
    col_B1377.alignment = 'Expand'.upper()
    col_B1377.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_B1377.separator(factor=1.0)
    box_08F33 = col_B1377.box()
    box_08F33.alert = False
    box_08F33.enabled = True
    box_08F33.active = True
    box_08F33.use_property_split = False
    box_08F33.use_property_decorate = False
    box_08F33.alignment = 'Expand'.upper()
    box_08F33.scale_x = 1.0
    box_08F33.scale_y = 1.0
    if not True: box_08F33.operator_context = "EXEC_DEFAULT"
    col_F6D97 = box_08F33.column(heading='', align=True)
    col_F6D97.alert = False
    col_F6D97.enabled = True
    col_F6D97.active = True
    col_F6D97.use_property_split = False
    col_F6D97.use_property_decorate = False
    col_F6D97.scale_x = 1.0
    col_F6D97.scale_y = 1.0
    col_F6D97.alignment = 'Expand'.upper()
    col_F6D97.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_025E5 = col_F6D97.split(factor=0.5, align=True)
    split_025E5.alert = False
    split_025E5.enabled = True
    split_025E5.active = True
    split_025E5.use_property_split = False
    split_025E5.use_property_decorate = False
    split_025E5.scale_x = 1.0
    split_025E5.scale_y = 1.0
    split_025E5.alignment = 'Expand'.upper()
    if not True: split_025E5.operator_context = "EXEC_DEFAULT"
    split_025E5.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['PBR_材质'].inputs['PBR材质类'], 'default_value', text='透明', icon_value=0, emboss=True)
    split_025E5.label(text='0=默认   1=透贴   2=半透', icon_value=0)
    split_298E1 = col_F6D97.split(factor=0.5, align=True)
    split_298E1.alert = False
    split_298E1.enabled = True
    split_298E1.active = True
    split_298E1.use_property_split = False
    split_298E1.use_property_decorate = False
    split_298E1.scale_x = 1.0
    split_298E1.scale_y = 1.0
    split_298E1.alignment = 'Expand'.upper()
    if not True: split_298E1.operator_context = "EXEC_DEFAULT"
    split_298E1.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['PBR_材质'].inputs['双面'], 'default_value', text='双面', icon_value=0, emboss=True)
    split_298E1.label(text='0=单面   1=双面', icon_value=0)
    col_F6D97.prop(bpy.context.view_layer.objects.active.active_material, 'use_backface_culling', text='单面剔除预览', icon_value=0, emboss=True)
    box_D0560 = col_B1377.box()
    box_D0560.alert = False
    box_D0560.enabled = True
    box_D0560.active = True
    box_D0560.use_property_split = False
    box_D0560.use_property_decorate = False
    box_D0560.alignment = 'Expand'.upper()
    box_D0560.scale_x = 1.0
    box_D0560.scale_y = 1.0
    if not True: box_D0560.operator_context = "EXEC_DEFAULT"
    col_51239 = box_D0560.column(heading='', align=True)
    col_51239.alert = False
    col_51239.enabled = True
    col_51239.active = True
    col_51239.use_property_split = False
    col_51239.use_property_decorate = False
    col_51239.scale_x = 1.0
    col_51239.scale_y = 1.100000023841858
    col_51239.alignment = 'Expand'.upper()
    col_51239.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_AE5BD = col_51239.split(factor=0.20000000298023224, align=False)
    split_AE5BD.alert = False
    split_AE5BD.enabled = True
    split_AE5BD.active = True
    split_AE5BD.use_property_split = False
    split_AE5BD.use_property_decorate = False
    split_AE5BD.scale_x = 1.0
    split_AE5BD.scale_y = 1.0
    split_AE5BD.alignment = 'Expand'.upper()
    if not True: split_AE5BD.operator_context = "EXEC_DEFAULT"
    split_AE5BD.label(text='混合颜色:', icon_value=0)
    split_AE5BD.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['PBR_材质'].inputs['BlendColor'], 'default_value', text='', icon_value=0, emboss=True)
    split_C4450 = col_51239.split(factor=0.20000000298023224, align=False)
    split_C4450.alert = False
    split_C4450.enabled = True
    split_C4450.active = True
    split_C4450.use_property_split = False
    split_C4450.use_property_decorate = False
    split_C4450.scale_x = 1.0
    split_C4450.scale_y = 1.0
    split_C4450.alignment = 'Expand'.upper()
    if not True: split_C4450.operator_context = "EXEC_DEFAULT"
    split_C4450.label(text='混合模式:', icon_value=0)
    split_C4450.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['PBR_材质'].inputs['BlendWeight'], 'default_value', text='', icon_value=0, emboss=True)
    split_1ACB3 = col_51239.split(factor=0.20000000298023224, align=False)
    split_1ACB3.alert = False
    split_1ACB3.enabled = True
    split_1ACB3.active = True
    split_1ACB3.use_property_split = False
    split_1ACB3.use_property_decorate = False
    split_1ACB3.scale_x = 1.0
    split_1ACB3.scale_y = 1.0
    split_1ACB3.alignment = 'Expand'.upper()
    if not True: split_1ACB3.operator_context = "EXEC_DEFAULT"
    split_1ACB3.label(text='自发光:', icon_value=0)
    row_5195F = split_1ACB3.row(heading='', align=False)
    row_5195F.alert = False
    row_5195F.enabled = True
    row_5195F.active = True
    row_5195F.use_property_split = False
    row_5195F.use_property_decorate = False
    row_5195F.scale_x = 1.0
    row_5195F.scale_y = 1.0
    row_5195F.alignment = 'Expand'.upper()
    row_5195F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_5195F.prop(bpy.context.view_layer.objects.active.active_material.node_tree.nodes['PBR_材质'].inputs['cEmissionScale'], 'default_value', text='', icon_value=0, emboss=True)
    layout_function = col_B1377
    sna_ui_890E7(layout_function, ['tBaseMap', 'tMixMap', 'tNormalMap', 'tEmissionMap'])


def sna_func_CED42(layout_function, ):
    if True:
        col_1CE7C = layout_function.column(heading='', align=True)
        col_1CE7C.alert = False
        col_1CE7C.enabled = True
        col_1CE7C.active = True
        col_1CE7C.use_property_split = False
        col_1CE7C.use_property_decorate = False
        col_1CE7C.scale_x = 1.0
        col_1CE7C.scale_y = 1.0
        col_1CE7C.alignment = 'Expand'.upper()
        col_1CE7C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_1CE7C.label(text='顶点色混合材质', icon_value=string_to_icon('MATERIAL_DATA'))
        col_1CE7C.separator(factor=1.0)
        col_1CE7C.prop(bpy.context.object.active_material, 'use_nodes', text='启用材质', icon_value=0, emboss=True)
        col_DF441 = col_1CE7C.column(heading='', align=True)
        col_DF441.alert = False
        col_DF441.enabled = bpy.context.object.active_material.use_nodes
        col_DF441.active = True
        col_DF441.use_property_split = False
        col_DF441.use_property_decorate = False
        col_DF441.scale_x = 1.0
        col_DF441.scale_y = 1.0
        col_DF441.alignment = 'Expand'.upper()
        col_DF441.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_DF441.separator(factor=1.0)
        row_A587F = col_DF441.row(heading='', align=True)
        row_A587F.alert = False
        row_A587F.enabled = True
        row_A587F.active = True
        row_A587F.use_property_split = False
        row_A587F.use_property_decorate = False
        row_A587F.scale_x = 1.0
        row_A587F.scale_y = 1.5
        row_A587F.alignment = 'Expand'.upper()
        row_A587F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_A587F.prop(bpy.context.scene, 'sna_g108_mat_shader_img', text=bpy.context.scene.sna_g108_mat_shader_img, icon_value=0, emboss=True, expand=True)
        col_DF441.separator(factor=1.0)
        if (bpy.context.scene.sna_g108_mat_shader_img == '参数'):
            layout_function = col_DF441
            sna_ui_2E426(layout_function, 'Z_材质参数', [['DetailMap_RatioU', 'DetailMap_RatioV', 'StainMap_RatioU', 'StainMap_RatioV'], ['BaseOverlaryColor', 'DetailOverlaryColor', 'EdgeColor', 'StainColor', 'Stain_2_Color'], ['BaseNormal_Intensity', 'BaseOverlaryColor_Alpha', 'Base_Tilling'], ['DetailMask_Alpha', 'DetailMask_Contrast', 'DetailMask_Tilling', 'DetailMask_Uoffset', 'DetailMask_Voffset', 'DetailMetail', 'DetailNormal_Intensity', 'DetailOverlaryColor_Alpha', 'DetailSmoothness', 'Detail_Tilling'], ['EdgeColor_Alpha', 'Edge_Contrast'], ['GlobalAo', 'GlobalNormal_intensity'], ['StainMask_Alpha', 'StainMask_Contrast', 'StainMask_Tilling', 'StainMask_Uoffset', 'StainMask_Voffset', 'StainMetail', 'StainNormal_Intensity', 'StainOverlaryColor_Alpha', 'StainSmoothness', 'StainTilling'], ['Stain_2_Mask_Alpha', 'Stain_2_Mask_Contrast', 'Stain_2_Mask_Tilling', 'Stain_2_Mask_Uoffset', 'Stain_2_Mask_Voffset', 'Stain_2_Metail', 'Stain_2_OverlaryColor_Alpha', 'Stain_2_Smoothness'], ['VertexColor_Contrast', 'zEnableCover_Detail', 'zEnableCover_Stain']])
        else:
            layout_function = col_DF441
            sna_ui_890E7(layout_function, ['BaseColor', 'BaseMix', 'BaseNormal', 'DetailColor', 'DetailNormal', 'StainNormal', 'GlobalNormal'])


@persistent
def depsgraph_update_post_handler_35156(dummy):
    if property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['Z_顶点混合材质']", globals(), locals()):
        if (bpy.context.scene.sna_g108_mat_shader_img == '贴图'):
            bpy.context.view_layer.objects.active.active_material.node_tree.nodes['BaseNormal_Mask'].image = bpy.context.view_layer.objects.active.active_material.node_tree.nodes['BaseNormal'].image
        if (bpy.context.scene.sna_g108_mat_shader_img == '贴图'):
            bpy.context.view_layer.objects.active.active_material.node_tree.nodes['DetailNormal_Mask'].image = bpy.context.view_layer.objects.active.active_material.node_tree.nodes['DetailNormal'].image
        if (bpy.context.scene.sna_g108_mat_shader_img == '贴图'):
            bpy.context.view_layer.objects.active.active_material.node_tree.nodes['StainNormal_Mask'].image = bpy.context.view_layer.objects.active.active_material.node_tree.nodes['StainNormal'].image
            print('顶点色材质贴图mask同步')


class SNA_PT_material_settings_BF188(bpy.types.Panel):
    bl_label = '材质设置'
    bl_idname = 'SNA_PT_material_settings_BF188'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_material_assignment_452D5'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        if property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['Z_顶点混合材质']", globals(), locals()):
            layout_function = layout
            sna_func_CED42(layout_function, )
        if property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['PBR_材质']", globals(), locals()):
            layout_function = layout
            sna_pbr_F5D94(layout_function, )
        if (property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['Z_顶点混合材质']", globals(), locals()) or property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['PBR_材质']", globals(), locals())):
            pass
        else:
            col_FF339 = layout.column(heading='', align=False)
            col_FF339.alert = True
            col_FF339.enabled = True
            col_FF339.use_property_split = False
            col_FF339.use_property_decorate = False
            col_FF339.scale_x = 1.0
            col_FF339.scale_y = 1.0
            col_FF339.alignment = 'Expand'.upper()
            layout.label(text='无项目材质', icon_value=string_to_icon('MATERIAL_DATA'))


class SNA_PT_SHADER___E9917(bpy.types.Panel):
    bl_label = 'Shader  设置'
    bl_idname = 'SNA_PT_SHADER___E9917'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_material_assignment_452D5'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        if ((None != bpy.context.view_layer.objects.active) and (not bpy.context.view_layer.objects.active.hide_viewport)):
            if (property_exists("bpy.context.view_layer.objects.active.active_material.name", globals(), locals()) and (len(list(bpy.context.active_object.material_slots)) == 1)):
                col_B9C21 = layout.column(heading='', align=False)
                col_B9C21.alert = False
                col_B9C21.enabled = True
                col_B9C21.active = True
                col_B9C21.use_property_split = False
                col_B9C21.use_property_decorate = False
                col_B9C21.scale_x = 1.0
                col_B9C21.scale_y = 1.0
                col_B9C21.alignment = 'Expand'.upper()
                col_B9C21.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_661BE = col_B9C21.split(factor=0.5, align=False)
                split_661BE.alert = False
                split_661BE.enabled = True
                split_661BE.active = True
                split_661BE.use_property_split = False
                split_661BE.use_property_decorate = False
                split_661BE.scale_x = 1.0
                split_661BE.scale_y = 1.0
                split_661BE.alignment = 'Expand'.upper()
                if not True: split_661BE.operator_context = "EXEC_DEFAULT"
                col_6FA9A = split_661BE.column(heading='', align=False)
                col_6FA9A.alert = False
                col_6FA9A.enabled = True
                col_6FA9A.active = True
                col_6FA9A.use_property_split = False
                col_6FA9A.use_property_decorate = False
                col_6FA9A.scale_x = 1.0
                col_6FA9A.scale_y = 1.0
                col_6FA9A.alignment = 'Expand'.upper()
                col_6FA9A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_6FA9A.prop(bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index], 'material', text='', icon_value=0, emboss=True)
                box_F5AA8 = col_6FA9A.box()
                box_F5AA8.alert = False
                box_F5AA8.enabled = True
                box_F5AA8.active = True
                box_F5AA8.use_property_split = False
                box_F5AA8.use_property_decorate = False
                box_F5AA8.alignment = 'Expand'.upper()
                box_F5AA8.scale_x = 1.0
                box_F5AA8.scale_y = 1.0
                if not True: box_F5AA8.operator_context = "EXEC_DEFAULT"
                box_F5AA8.template_icon(icon_value=get_id_preview_id(bpy.data.materials[bpy.context.object.active_material.name]), scale=6.0)
                box_3A572 = split_661BE.box()
                box_3A572.alert = False
                box_3A572.enabled = True
                box_3A572.active = True
                box_3A572.use_property_split = False
                box_3A572.use_property_decorate = False
                box_3A572.alignment = 'Expand'.upper()
                box_3A572.scale_x = 1.0
                box_3A572.scale_y = 1.0
                if not True: box_3A572.operator_context = "EXEC_DEFAULT"
                col_73271 = box_3A572.column(heading='', align=False)
                col_73271.alert = False
                col_73271.enabled = True
                col_73271.active = True
                col_73271.use_property_split = False
                col_73271.use_property_decorate = False
                col_73271.scale_x = 1.0
                col_73271.scale_y = 1.5
                col_73271.alignment = 'Expand'.upper()
                col_73271.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_73271.label(text='Shader 选择', icon_value=string_to_icon('MENU_PANEL'))
                col_26F40 = col_73271.column(heading='', align=False)
                col_26F40.alert = False
                col_26F40.enabled = True
                col_26F40.active = True
                col_26F40.use_property_split = False
                col_26F40.use_property_decorate = False
                col_26F40.scale_x = 1.0
                col_26F40.scale_y = 1.0
                col_26F40.alignment = 'Expand'.upper()
                col_26F40.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_7EBE7 = col_26F40.column(heading='', align=False)
                col_7EBE7.alert = ((not property_exists("bpy.data.node_groups['Z_PBR材质组']", globals(), locals())) or (not property_exists("bpy.data.node_groups['Z_PBR_材质']", globals(), locals())))
                col_7EBE7.enabled = True
                col_7EBE7.active = True
                col_7EBE7.use_property_split = False
                col_7EBE7.use_property_decorate = False
                col_7EBE7.scale_x = 1.0
                col_7EBE7.scale_y = 1.0
                col_7EBE7.alignment = 'Expand'.upper()
                col_7EBE7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_7EBE7.operator('sna.pbr__shader_703a0', text='PBR  Shader', icon_value=0, emboss=True, depress=False)
                col_D5000 = col_26F40.column(heading='', align=False)
                col_D5000.alert = ((not property_exists("bpy.data.node_groups['Z_顶点色混合材质组']", globals(), locals())) or (not property_exists("bpy.data.node_groups['Z_顶点混合材质']", globals(), locals())) or (not property_exists("bpy.data.node_groups['Z_材质参数']", globals(), locals())))
                col_D5000.enabled = True
                col_D5000.active = True
                col_D5000.use_property_split = False
                col_D5000.use_property_decorate = False
                col_D5000.scale_x = 1.0
                col_D5000.scale_y = 1.0
                col_D5000.alignment = 'Expand'.upper()
                col_D5000.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_D5000.operator('sna.shader_053cf', text='顶点色混合  Shader', icon_value=0, emboss=True, depress=False)
                layout_function = box_3A572
                sna_func_DED65(layout_function, )
                col_B9C21.prop(bpy.context.object.active_material, 'name', text='', icon_value=0, emboss=True)
                box_01A3B = col_B9C21.box()
                box_01A3B.alert = False
                box_01A3B.enabled = True
                box_01A3B.active = True
                box_01A3B.use_property_split = False
                box_01A3B.use_property_decorate = False
                box_01A3B.alignment = 'Expand'.upper()
                box_01A3B.scale_x = 1.0
                box_01A3B.scale_y = 1.0
                if not True: box_01A3B.operator_context = "EXEC_DEFAULT"
                split_505BB = box_01A3B.split(factor=0.4000000059604645, align=True)
                split_505BB.alert = False
                split_505BB.enabled = True
                split_505BB.active = True
                split_505BB.use_property_split = False
                split_505BB.use_property_decorate = False
                split_505BB.scale_x = 1.0
                split_505BB.scale_y = 1.0
                split_505BB.alignment = 'Expand'.upper()
                if not True: split_505BB.operator_context = "EXEC_DEFAULT"
                split_505BB.label(text='当前Shader：', icon_value=0)
                if property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['Z_顶点混合材质']", globals(), locals()):
                    split_505BB.label(text='顶点色混合 Shader', icon_value=string_to_icon('DESKTOP'))
                if property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['PBR_材质']", globals(), locals()):
                    split_505BB.label(text='PBR  Shader', icon_value=string_to_icon('DESKTOP'))
                if (property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['Z_顶点混合材质']", globals(), locals()) or property_exists("bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index].material.node_tree.nodes['PBR_材质']", globals(), locals())):
                    pass
                else:
                    split_505BB.label(text='无', icon_value=string_to_icon('DESKTOP'))
            else:
                if (len(list(bpy.context.active_object.material_slots)) == 1):
                    split_E2DE1 = layout.split(factor=0.5, align=False)
                    split_E2DE1.alert = False
                    split_E2DE1.enabled = True
                    split_E2DE1.active = True
                    split_E2DE1.use_property_split = False
                    split_E2DE1.use_property_decorate = False
                    split_E2DE1.scale_x = 1.0
                    split_E2DE1.scale_y = 1.0
                    split_E2DE1.alignment = 'Expand'.upper()
                    if not True: split_E2DE1.operator_context = "EXEC_DEFAULT"
                    split_E2DE1.prop(bpy.context.active_object.material_slots[bpy.context.view_layer.objects.active.active_material_index], 'material', text='', icon_value=0, emboss=True)
                    op = split_E2DE1.operator('sna.my_generic_operator_9b91a', text='新建材质', icon_value=string_to_icon('ADD'), emboss=True, depress=False)
                else:
                    if (len(list(bpy.context.active_object.material_slots)) == 0):
                        op = layout.operator('object.material_slot_add', text='增加材质槽', icon_value=0, emboss=True, depress=False)
                    else:
                        col_D8A4C = layout.column(heading='', align=False)
                        col_D8A4C.alert = True
                        col_D8A4C.enabled = True
                        col_D8A4C.use_property_split = False
                        col_D8A4C.use_property_decorate = False
                        col_D8A4C.scale_x = 1.0
                        col_D8A4C.scale_y = 1.0
                        col_D8A4C.alignment = 'Expand'.upper()
                        layout.label(text='材质槽大于1', icon_value=0)
        else:
            layout.label(text='请选择中物体', icon_value=0)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_g108_material_version_switch = bpy.props.EnumProperty(name='g108_material_version_switch', description='', options={'HIDDEN'}, items=[('Blender4.2', 'Blender4.2', '', 0, 0), ('Blender3.5', 'Blender3.5', '', 0, 1)])
    bpy.types.Scene.sna_g108_mat_shader_img = bpy.props.EnumProperty(name='g108_mat_shader_img', description='', items=[('参数', '参数', '', 'ALIGN_JUSTIFY', 0), ('贴图', '贴图', '', 'FILE_IMAGE', 1)])
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9B91A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_01951)
    bpy.utils.register_class(SNA_PT_material_assignment_452D5)
    bpy.utils.register_class(SNA_OT_Pbr__Shader_703A0)
    bpy.utils.register_class(SNA_OT_Shader_053Cf)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D27Ca)
    bpy.utils.register_class(SNA_OT_Pbr_B1301)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3022F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A4928)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Fc9Cc)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_599Aa)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B464E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_C5E64)
    bpy.utils.register_class(SNA_OT_Shader_Eee96)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_8213D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_04658)
    bpy.app.handlers.save_pre.append(save_pre_handler_C8A05)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post_handler_35156)
    bpy.utils.register_class(SNA_PT_material_settings_BF188)
    bpy.utils.register_class(SNA_PT_SHADER___E9917)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_g108_mat_shader_img
    del bpy.types.Scene.sna_g108_material_version_switch
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9B91A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_01951)
    bpy.utils.unregister_class(SNA_PT_material_assignment_452D5)
    bpy.utils.unregister_class(SNA_OT_Pbr__Shader_703A0)
    bpy.utils.unregister_class(SNA_OT_Shader_053Cf)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D27Ca)
    bpy.utils.unregister_class(SNA_OT_Pbr_B1301)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3022F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A4928)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Fc9Cc)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_599Aa)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B464E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_C5E64)
    bpy.utils.unregister_class(SNA_OT_Shader_Eee96)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_8213D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_04658)
    bpy.app.handlers.save_pre.remove(save_pre_handler_C8A05)
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post_handler_35156)
    bpy.utils.unregister_class(SNA_PT_material_settings_BF188)
    bpy.utils.unregister_class(SNA_PT_SHADER___E9917)
