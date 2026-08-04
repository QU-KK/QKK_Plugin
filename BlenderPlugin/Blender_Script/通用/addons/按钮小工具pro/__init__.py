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
    "name" : "Py_Script_Tool",
    "author" : "qkk", 
    "description" : "",
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




def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


def string_to_type(value, to_type, default):
    try:
        value = to_type(value)
    except:
        value = default
    return value


addon_keymaps = {}
_icons = None
py_script = {'sna_py_script_path': 'None', 'sna_py_script_path_list': [], 'sna_py_script_name': 'None', }
class SNA_PT_PY_769D9(bpy.types.Panel):
    bl_label = 'Py脚本工具'
    bl_idname = 'SNA_PT_PY_769D9'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'Python'
    bl_order = 1
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_1E8CC = layout.column(heading='', align=False)
        col_1E8CC.alert = False
        col_1E8CC.enabled = True
        col_1E8CC.active = True
        col_1E8CC.use_property_split = False
        col_1E8CC.use_property_decorate = False
        col_1E8CC.scale_x = 1.0
        col_1E8CC.scale_y = 1.0
        col_1E8CC.alignment = 'Expand'.upper()
        col_1E8CC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_F183B = col_1E8CC.row(heading='', align=True)
        row_F183B.alert = False
        row_F183B.enabled = True
        row_F183B.active = True
        row_F183B.use_property_split = False
        row_F183B.use_property_decorate = False
        row_F183B.scale_x = 1.0
        row_F183B.scale_y = 1.0
        row_F183B.alignment = 'Right'.upper()
        row_F183B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_F183B.operator('sna.refresh_path_5ca64', text='', icon_value=string_to_icon('FILE_REFRESH'), emboss=True, depress=False)
        op = row_F183B.operator('sna.open_folder_d57f2', text='', icon_value=string_to_icon('FILE_FOLDER'), emboss=True, depress=False)
        op.sna_script_path = py_script['sna_py_script_path']
        row_F183B.prop(bpy.context.scene, 'sna_py_script_debug', text='', icon_value=string_to_icon('SEQ_STRIP_MODIFIER'), emboss=True)
        if (py_script['sna_py_script_path'] == 'None'):
            col_3A2F2 = col_1E8CC.column(heading='', align=False)
            col_3A2F2.alert = False
            col_3A2F2.enabled = True
            col_3A2F2.active = True
            col_3A2F2.use_property_split = False
            col_3A2F2.use_property_decorate = False
            col_3A2F2.scale_x = 1.0
            col_3A2F2.scale_y = 2.0
            col_3A2F2.alignment = 'Expand'.upper()
            col_3A2F2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_3A2F2.operator('sna.refresh_path_5ca64', text='刷新Py脚本', icon_value=string_to_icon('FILE_REFRESH'), emboss=True, depress=False)
        else:
            col_414EA = col_1E8CC.column(heading='', align=False)
            col_414EA.alert = False
            col_414EA.enabled = True
            col_414EA.active = True
            col_414EA.use_property_split = False
            col_414EA.use_property_decorate = False
            col_414EA.scale_x = 1.0
            col_414EA.scale_y = 1.0
            col_414EA.alignment = 'Expand'.upper()
            col_414EA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            grid_57696 = col_414EA.grid_flow(columns=4, row_major=True, even_columns=False, even_rows=False, align=True)
            grid_57696.enabled = True
            grid_57696.active = True
            grid_57696.use_property_split = False
            grid_57696.use_property_decorate = False
            grid_57696.alignment = 'Expand'.upper()
            grid_57696.scale_x = 1.0
            grid_57696.scale_y = 1.5
            if not True: grid_57696.operator_context = "EXEC_DEFAULT"
            for i_A96F2 in range(len(py_script['sna_py_script_path_list'])):
                op = grid_57696.operator('sna.script_name_053ed', text=os.path.basename(py_script['sna_py_script_path_list'][i_A96F2]).split('-')[1], icon_value=0, emboss=True, depress=(py_script['sna_py_script_path_list'][i_A96F2] == py_script['sna_py_script_name']))
                op.sna_script_name = py_script['sna_py_script_path_list'][i_A96F2]
            for i_E9FFD in range(len(py_script['sna_py_script_path_list'])):
                if (py_script['sna_py_script_name'] == py_script['sna_py_script_path_list'][i_E9FFD]):
                    box_FCBDB = col_414EA.box()
                    box_FCBDB.alert = False
                    box_FCBDB.enabled = True
                    box_FCBDB.active = True
                    box_FCBDB.use_property_split = False
                    box_FCBDB.use_property_decorate = False
                    box_FCBDB.alignment = 'Expand'.upper()
                    box_FCBDB.scale_x = 1.0
                    box_FCBDB.scale_y = 1.0
                    if not True: box_FCBDB.operator_context = "EXEC_DEFAULT"
                    col_EB305 = box_FCBDB.column(heading='', align=False)
                    col_EB305.alert = False
                    col_EB305.enabled = True
                    col_EB305.active = True
                    col_EB305.use_property_split = False
                    col_EB305.use_property_decorate = False
                    col_EB305.scale_x = 1.0
                    col_EB305.scale_y = 1.0
                    col_EB305.alignment = 'Expand'.upper()
                    col_EB305.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    for i_FD8DB in range(len([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))])):
                        col_2D975 = col_EB305.column(heading='', align=False)
                        col_2D975.alert = False
                        col_2D975.enabled = True
                        col_2D975.active = True
                        col_2D975.use_property_split = False
                        col_2D975.use_property_decorate = False
                        col_2D975.scale_x = 1.0
                        col_2D975.scale_y = 1.0
                        col_2D975.alignment = 'Expand'.upper()
                        col_2D975.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        if '-列' in os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]):
                            if '-框' in os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]):
                                box_E61CF = col_2D975.box()
                                box_E61CF.alert = False
                                box_E61CF.enabled = True
                                box_E61CF.active = True
                                box_E61CF.use_property_split = False
                                box_E61CF.use_property_decorate = False
                                box_E61CF.alignment = 'Expand'.upper()
                                box_E61CF.scale_x = 1.0
                                box_E61CF.scale_y = 1.0
                                if not True: box_E61CF.operator_context = "EXEC_DEFAULT"
                                col_3B899 = box_E61CF.column(heading='', align='-对齐' in os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]))
                                col_3B899.alert = False
                                col_3B899.enabled = True
                                col_3B899.active = True
                                col_3B899.use_property_split = False
                                col_3B899.use_property_decorate = False
                                col_3B899.scale_x = 1.0
                                col_3B899.scale_y = 1.0
                                col_3B899.alignment = 'Expand'.upper()
                                col_3B899.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                                layout_function = col_3B899
                                sna_py_B70D0(layout_function, [os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB])
                            else:
                                col_D19EA = col_2D975.column(heading='', align='-对齐' in os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]))
                                col_D19EA.alert = False
                                col_D19EA.enabled = True
                                col_D19EA.active = True
                                col_D19EA.use_property_split = False
                                col_D19EA.use_property_decorate = False
                                col_D19EA.scale_x = 1.0
                                col_D19EA.scale_y = 1.0
                                col_D19EA.alignment = 'Expand'.upper()
                                col_D19EA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                                layout_function = col_D19EA
                                sna_py_B70D0(layout_function, [os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB])
                        if '-行' in os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]):
                            if '-框' in os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]):
                                box_B186C = col_2D975.box()
                                box_B186C.alert = False
                                box_B186C.enabled = True
                                box_B186C.active = True
                                box_B186C.use_property_split = False
                                box_B186C.use_property_decorate = False
                                box_B186C.alignment = 'Expand'.upper()
                                box_B186C.scale_x = 1.0
                                box_B186C.scale_y = 1.0
                                if not True: box_B186C.operator_context = "EXEC_DEFAULT"
                                grid_C30A0 = box_B186C.grid_flow(columns=string_to_type(os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]).split('-')[2], int, 0), row_major=True, even_columns=False, even_rows=False, align='-对齐' in os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]))
                                grid_C30A0.enabled = True
                                grid_C30A0.active = True
                                grid_C30A0.use_property_split = False
                                grid_C30A0.use_property_decorate = False
                                grid_C30A0.alignment = 'Expand'.upper()
                                grid_C30A0.scale_x = 1.0
                                grid_C30A0.scale_y = 1.0
                                if not True: grid_C30A0.operator_context = "EXEC_DEFAULT"
                                layout_function = grid_C30A0
                                sna_py_B70D0(layout_function, [os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB])
                            else:
                                grid_DE03A = col_2D975.grid_flow(columns=string_to_type(os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]).split('-')[2], int, 0), row_major=True, even_columns=False, even_rows=False, align='-对齐' in os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB]))
                                grid_DE03A.enabled = True
                                grid_DE03A.active = True
                                grid_DE03A.use_property_split = False
                                grid_DE03A.use_property_decorate = False
                                grid_DE03A.alignment = 'Expand'.upper()
                                grid_DE03A.scale_x = 1.0
                                grid_DE03A.scale_y = 1.0
                                if not True: grid_DE03A.operator_context = "EXEC_DEFAULT"
                                layout_function = grid_DE03A
                                sna_py_B70D0(layout_function, [os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isdir(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_FD8DB])
                    col_754A9 = col_EB305.column(heading='', align=False)
                    col_754A9.alert = False
                    col_754A9.enabled = True
                    col_754A9.active = True
                    col_754A9.use_property_split = False
                    col_754A9.use_property_decorate = False
                    col_754A9.scale_x = 1.0
                    col_754A9.scale_y = 1.0
                    col_754A9.alignment = 'Expand'.upper()
                    col_754A9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    for i_18AB5 in range(len([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isfile(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))])):
                        op = col_754A9.operator('sna.execute_py_script_32961', text=os.path.basename([os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isfile(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_18AB5]).replace('.py', ''), icon_value=0, emboss=True, depress=False)
                        op.sna_script_path = [os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f) for f in os.listdir(py_script['sna_py_script_path_list'][i_E9FFD]) if os.path.isfile(os.path.join(py_script['sna_py_script_path_list'][i_E9FFD], f))][i_18AB5]


def sna_py_B70D0(layout_function, path):
    for i_40330 in range(len([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])):
        if '-题头' in os.path.basename([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))][i_40330]).replace('.py', ''):
            layout_function.label(text=os.path.basename([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))][i_40330]).replace('.py', '').split('-')[1], icon_value=string_to_icon(os.path.basename([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))][i_40330]).replace('.py', '').split('-')[2]))
        else:
            col_55626 = layout_function.column(heading='', align=True)
            col_55626.alert = False
            col_55626.enabled = True
            col_55626.active = True
            col_55626.use_property_split = False
            col_55626.use_property_decorate = False
            col_55626.scale_x = 1.0
            col_55626.scale_y = string_to_type(os.path.basename([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))][i_40330]).replace('.py', '').split('-')[3], float, 0)
            col_55626.alignment = 'Expand'.upper()
            col_55626.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_55626.operator('sna.execute_py_script_32961', text=os.path.basename([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))][i_40330]).replace('.py', '').split('-')[1], icon_value=string_to_icon(os.path.basename([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))][i_40330]).replace('.py', '').split('-')[2]), emboss=True, depress=False)
            op.sna_script_path = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))][i_40330]


class SNA_OT_Refresh_Path_5Ca64(bpy.types.Operator):
    bl_idname = "sna.refresh_path_5ca64"
    bl_label = "Refresh_Path"
    bl_description = "刷新Py脚本主路径"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        Py_Path = None
        Py_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Python脚本")
        #Py_Path = r'C:\QKK_Plugin\BlenderPlugin\Blender_Script\通用\addons\按钮小工具pro\Python脚本'
        py_script['sna_py_script_path'] = Py_Path
        py_script['sna_py_script_path_list'] = [os.path.join(Py_Path, f) for f in os.listdir(Py_Path) if os.path.isdir(os.path.join(Py_Path, f))]
        if (py_script['sna_py_script_name'] == 'None'):
            bpy.ops.sna.script_name_053ed(sna_script_name=py_script['sna_py_script_path_list'][0])
        self.report({'INFO'}, message='Py脚本刷新完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Execute_Py_Script_32961(bpy.types.Operator):
    bl_idname = "sna.execute_py_script_32961"
    bl_label = "Execute_Py_Script"
    bl_description = "运行Py脚本"
    bl_options = {"REGISTER", "UNDO"}
    sna_script_path: bpy.props.StringProperty(name='script_path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if bpy.context.scene.sna_py_script_debug:
            script_path = self.sna_script_path
            # 打开指定目录并选中
            # 注意：/select, 后面不要有空格
            subprocess.Popen(f'explorer /select, "{script_path}"')
            self.report({'INFO'}, message='定位完成!')
        else:
            script_path = self.sna_script_path
            # 运行指定路径脚本
            exec(open(script_path).read())
            self.report({'INFO'}, message='运行Py脚本完成!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Open_Folder_D57F2(bpy.types.Operator):
    bl_idname = "sna.open_folder_d57f2"
    bl_label = "Open_Folder"
    bl_description = "打开Py脚本路径"
    bl_options = {"REGISTER", "UNDO"}
    sna_script_path: bpy.props.StringProperty(name='script_path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        folder_path = self.sna_script_path
        # 打开文件夹
        os.startfile(folder_path)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Script_Name_053Ed(bpy.types.Operator):
    bl_idname = "sna.script_name_053ed"
    bl_label = "Script_Name"
    bl_description = "切换脚本类型"
    bl_options = {"REGISTER", "UNDO"}
    sna_script_name: bpy.props.StringProperty(name='script_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        py_script['sna_py_script_name'] = self.sna_script_name
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Open_Python_Script_Tool_D24Cf(bpy.types.Operator):
    bl_idname = "sna.open_python_script_tool_d24cf"
    bl_label = "Open_Python_Script_Tool"
    bl_description = "打开Py脚本工具界面"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_PY_769D9", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_py_script_debug = bpy.props.BoolProperty(name='py_script_debug', description='', default=False)
    bpy.utils.register_class(SNA_PT_PY_769D9)
    bpy.utils.register_class(SNA_OT_Refresh_Path_5Ca64)
    bpy.utils.register_class(SNA_OT_Execute_Py_Script_32961)
    bpy.utils.register_class(SNA_OT_Open_Folder_D57F2)
    bpy.utils.register_class(SNA_OT_Script_Name_053Ed)
    bpy.utils.register_class(SNA_OT_Open_Python_Script_Tool_D24Cf)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_py_script_debug
    bpy.utils.unregister_class(SNA_PT_PY_769D9)
    bpy.utils.unregister_class(SNA_OT_Refresh_Path_5Ca64)
    bpy.utils.unregister_class(SNA_OT_Execute_Py_Script_32961)
    bpy.utils.unregister_class(SNA_OT_Open_Folder_D57F2)
    bpy.utils.unregister_class(SNA_OT_Script_Name_053Ed)
    bpy.utils.unregister_class(SNA_OT_Open_Python_Script_Tool_D24Cf)
