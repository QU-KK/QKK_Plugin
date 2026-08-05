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
    "name" : "Py_Script_Button",
    "author" : "qkk", 
    "description" : "",
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
node_tree = {'sna_script_path': 'None', 'sna_directories_list': [], }


def sna_update_sna_script_folder_FF0B8(self, context):
    sna_updated_prop = self.sna_script_folder
    bpy.ops.wm.save_userpref()
    bpy.ops.sna.refresh_script_folder_def57()


class SNA_PT_PY_8454F(bpy.types.Panel):
    bl_label = 'Py工具脚本'
    bl_idname = 'SNA_PT_PY_8454F'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'Python'
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
        if os.path.exists(bpy.path.abspath(bpy.context.preferences.addons[__package__].preferences.sna_script_folder)):
            col_753CB = layout.column(heading='', align=False)
            col_753CB.alert = False
            col_753CB.enabled = True
            col_753CB.active = True
            col_753CB.use_property_split = False
            col_753CB.use_property_decorate = False
            col_753CB.scale_x = 1.0
            col_753CB.scale_y = 1.0
            col_753CB.alignment = 'Expand'.upper()
            col_753CB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            row_CAB83 = col_753CB.row(heading='', align=True)
            row_CAB83.alert = False
            row_CAB83.enabled = True
            row_CAB83.active = True
            row_CAB83.use_property_split = False
            row_CAB83.use_property_decorate = False
            row_CAB83.scale_x = 1.0
            row_CAB83.scale_y = 1.0
            row_CAB83.alignment = 'Right'.upper()
            row_CAB83.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = row_CAB83.operator('sna.refresh_script_folder_def57', text='', icon_value=string_to_icon('FILE_REFRESH'), emboss=True, depress=False)
            op = row_CAB83.operator('sna.script_folder_79a07', text='', icon_value=string_to_icon('MODIFIER'), emboss=True, depress=False)
            op = row_CAB83.operator('sna.open_folder_dab7e', text='', icon_value=string_to_icon('FILE_FOLDER'), emboss=True, depress=False)
            op.sna_folder_path = bpy.path.abspath(bpy.context.preferences.addons[__package__].preferences.sna_script_folder)
            grid_302CF = col_753CB.grid_flow(columns=4, row_major=True, even_columns=False, even_rows=False, align=True)
            grid_302CF.enabled = True
            grid_302CF.active = True
            grid_302CF.use_property_split = False
            grid_302CF.use_property_decorate = False
            grid_302CF.alignment = 'Expand'.upper()
            grid_302CF.scale_x = 1.0
            grid_302CF.scale_y = 1.5
            if not True: grid_302CF.operator_context = "EXEC_DEFAULT"
            for i_5E918 in range(len(node_tree['sna_directories_list'])):
                op = grid_302CF.operator('sna.script_name_a82ce', text=os.path.basename(node_tree['sna_directories_list'][i_5E918]), icon_value=0, emboss=True, depress=(os.path.basename(node_tree['sna_directories_list'][i_5E918]) == os.path.basename(node_tree['sna_script_path'])))
                op.sna_script_path = node_tree['sna_directories_list'][i_5E918]
            if (len(node_tree['sna_directories_list']) != 0):
                box_4D2D3 = col_753CB.box()
                box_4D2D3.alert = False
                box_4D2D3.enabled = True
                box_4D2D3.active = True
                box_4D2D3.use_property_split = False
                box_4D2D3.use_property_decorate = False
                box_4D2D3.alignment = 'Expand'.upper()
                box_4D2D3.scale_x = 1.0
                box_4D2D3.scale_y = 1.0
                if not True: box_4D2D3.operator_context = "EXEC_DEFAULT"
                col_3FCEB = box_4D2D3.column(heading='', align=False)
                col_3FCEB.alert = False
                col_3FCEB.enabled = True
                col_3FCEB.active = True
                col_3FCEB.use_property_split = False
                col_3FCEB.use_property_decorate = False
                col_3FCEB.scale_x = 1.0
                col_3FCEB.scale_y = 1.0
                col_3FCEB.alignment = 'Expand'.upper()
                col_3FCEB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                for i_64069 in range(len(node_tree['sna_directories_list'])):
                    if (node_tree['sna_directories_list'][i_64069] == node_tree['sna_script_path']):
                        for i_48EDF in range(len([os.path.join(node_tree['sna_directories_list'][i_64069], f) for f in os.listdir(node_tree['sna_directories_list'][i_64069]) if os.path.isfile(os.path.join(node_tree['sna_directories_list'][i_64069], f))])):
                            op = col_3FCEB.operator('sna.execute_py_script_c59f3', text=os.path.basename([os.path.join(node_tree['sna_directories_list'][i_64069], f) for f in os.listdir(node_tree['sna_directories_list'][i_64069]) if os.path.isfile(os.path.join(node_tree['sna_directories_list'][i_64069], f))][i_48EDF]).replace(os.path.splitext([os.path.join(node_tree['sna_directories_list'][i_64069], f) for f in os.listdir(node_tree['sna_directories_list'][i_64069]) if os.path.isfile(os.path.join(node_tree['sna_directories_list'][i_64069], f))][i_48EDF])[1], ''), icon_value=0, emboss=True, depress=False)
                            op.sna_script_path = [os.path.join(node_tree['sna_directories_list'][i_64069], f) for f in os.listdir(node_tree['sna_directories_list'][i_64069]) if os.path.isfile(os.path.join(node_tree['sna_directories_list'][i_64069], f))][i_48EDF]
            else:
                col_81E94 = col_753CB.column(heading='', align=True)
                col_81E94.alert = False
                col_81E94.enabled = True
                col_81E94.active = True
                col_81E94.use_property_split = False
                col_81E94.use_property_decorate = False
                col_81E94.scale_x = 1.0
                col_81E94.scale_y = 2.0
                col_81E94.alignment = 'Expand'.upper()
                col_81E94.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_81E94.operator('sna.refresh_script_folder_def57', text='刷新插件', icon_value=string_to_icon('FILE_REFRESH'), emboss=True, depress=False)
        else:
            layout.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_script_folder', text='脚本目录', icon_value=0, emboss=True)


class SNA_OT_Execute_Py_Script_C59F3(bpy.types.Operator):
    bl_idname = "sna.execute_py_script_c59f3"
    bl_label = "Execute_Py_script"
    bl_description = "执行Py脚本"
    bl_options = {"REGISTER", "UNDO"}
    sna_script_path: bpy.props.StringProperty(name='script_path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        script_path = self.sna_script_path
        # 运行指定路径脚本
        exec(open(script_path).read())
        print('执行Py脚本完毕！')
        self.report({'INFO'}, message='执行Py脚本完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Script_Name_A82Ce(bpy.types.Operator):
    bl_idname = "sna.script_name_a82ce"
    bl_label = "script_name"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_script_path: bpy.props.StringProperty(name='script_path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree['sna_script_path'] = self.sna_script_path
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_AddonPreferences_8A840(bpy.types.AddonPreferences):
    bl_idname = __package__
    sna_script_folder: bpy.props.StringProperty(name='script_folder', description='', options={'HIDDEN'}, default='', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_script_folder_FF0B8)

    def draw(self, context):
        if not (False):
            layout = self.layout 
            layout.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_script_folder', text='脚本目录', icon_value=0, emboss=True)


class SNA_OT_Open_Folder_Dab7E(bpy.types.Operator):
    bl_idname = "sna.open_folder_dab7e"
    bl_label = "Open_Folder"
    bl_description = "打开目录"
    bl_options = {"REGISTER", "UNDO"}
    sna_folder_path: bpy.props.StringProperty(name='folder_path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        folder_path = self.sna_folder_path
        # 打开文件夹
        os.startfile(folder_path)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Script_Folder_79A07(bpy.types.Operator):
    bl_idname = "sna.script_folder_79a07"
    bl_label = "script_folder"
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
        layout.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_script_folder', text='脚本目录', icon_value=0, emboss=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)


class SNA_OT_Refresh_Script_Folder_Def57(bpy.types.Operator):
    bl_idname = "sna.refresh_script_folder_def57"
    bl_label = "refresh_script_folder"
    bl_description = "刷新插件目录"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree['sna_directories_list'] = [os.path.join(bpy.path.abspath(bpy.context.preferences.addons[__package__].preferences.sna_script_folder), f) for f in os.listdir(bpy.path.abspath(bpy.context.preferences.addons[__package__].preferences.sna_script_folder)) if os.path.isdir(os.path.join(bpy.path.abspath(bpy.context.preferences.addons[__package__].preferences.sna_script_folder), f))]
        node_tree['sna_script_path'] = [os.path.join(bpy.path.abspath(bpy.context.preferences.addons[__package__].preferences.sna_script_folder), f) for f in os.listdir(bpy.path.abspath(bpy.context.preferences.addons[__package__].preferences.sna_script_folder)) if os.path.isdir(os.path.join(bpy.path.abspath(bpy.context.preferences.addons[__package__].preferences.sna_script_folder), f))][0]
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Operator_On_Keypress_Py_Script_Button_Ac7E9(bpy.types.Operator):
    bl_idname = "sna.operator_on_keypress_py_script_button_ac7e9"
    bl_label = "Operator_On_Keypress_Py_Script_Button"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.sna.refresh_script_folder_def57()
        bpy.ops.wm.call_panel(name="SNA_PT_PY_8454F", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_PT_PY_8454F)
    bpy.utils.register_class(SNA_OT_Execute_Py_Script_C59F3)
    bpy.utils.register_class(SNA_OT_Script_Name_A82Ce)
    bpy.utils.register_class(SNA_AddonPreferences_8A840)
    bpy.utils.register_class(SNA_OT_Open_Folder_Dab7E)
    bpy.utils.register_class(SNA_OT_Script_Folder_79A07)
    bpy.utils.register_class(SNA_OT_Refresh_Script_Folder_Def57)
    bpy.utils.register_class(SNA_OT_Operator_On_Keypress_Py_Script_Button_Ac7E9)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.operator_on_keypress_py_script_button_ac7e9', 'ACCENT_GRAVE', 'PRESS',
        ctrl=True, alt=False, shift=False, repeat=False)
    addon_keymaps['74B13'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_PT_PY_8454F)
    bpy.utils.unregister_class(SNA_OT_Execute_Py_Script_C59F3)
    bpy.utils.unregister_class(SNA_OT_Script_Name_A82Ce)
    bpy.utils.unregister_class(SNA_AddonPreferences_8A840)
    bpy.utils.unregister_class(SNA_OT_Open_Folder_Dab7E)
    bpy.utils.unregister_class(SNA_OT_Script_Folder_79A07)
    bpy.utils.unregister_class(SNA_OT_Refresh_Script_Folder_Def57)
    bpy.utils.unregister_class(SNA_OT_Operator_On_Keypress_Py_Script_Button_Ac7E9)
