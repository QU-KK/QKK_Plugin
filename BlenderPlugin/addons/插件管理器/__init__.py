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
    "name" : "Plug-in_Manager_v6",
    "author" : "渠奎奎", 
    "description" : "插件管理器",
    "blender" : (5, 2, 0),
    "version" : (6, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "Development" 
}


import bpy
import bpy.utils.previews
import sys
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
node_tree = {'sna_addons_activate_list': [], 'sna_addons_directories': [], 'sna_addons_class_name': '必装', 'sna_addons_path': '', }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_OT_Python_Module_2Dc15(bpy.types.Operator):
    bl_idname = "sna.python_module_2dc15"
    bl_label = "python_module"
    bl_description = "安装Python模块"
    bl_options = {"REGISTER", "UNDO"}
    sna_python_module: bpy.props.StringProperty(name='python_module', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        blender_settings_path = None
        blender_settings_path=sys.exec_prefix
        python_module_name = 'start cmd /k ' + blender_settings_path + '\\bin\\python.exe' + ' -m pip install ' + self.sna_python_module
        os.system(python_module_name)
        self.report({'INFO'}, message='已运行！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Py_Mod_E1215(bpy.types.Operator):
    bl_idname = "sna.py_mod_e1215"
    bl_label = "py_mod"
    bl_description = "打开Py模块安装"
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
        box_E5D9D = layout.box()
        box_E5D9D.alert = False
        box_E5D9D.enabled = True
        box_E5D9D.active = True
        box_E5D9D.use_property_split = False
        box_E5D9D.use_property_decorate = False
        box_E5D9D.alignment = 'Expand'.upper()
        box_E5D9D.scale_x = 1.0
        box_E5D9D.scale_y = 1.0
        if not True: box_E5D9D.operator_context = "EXEC_DEFAULT"
        box_E5D9D.label(text='Python 模组安装：', icon_value=string_to_icon('SCRIPT'))
        col_6A86E = box_E5D9D.column(heading='', align=True)
        col_6A86E.alert = False
        col_6A86E.enabled = True
        col_6A86E.active = True
        col_6A86E.use_property_split = False
        col_6A86E.use_property_decorate = False
        col_6A86E.scale_x = 1.0
        col_6A86E.scale_y = 1.0
        col_6A86E.alignment = 'Expand'.upper()
        col_6A86E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        for i_F773C in range(len(bpy.context.scene.sna_bl_py_module.split(','))):
            op = col_6A86E.operator('sna.python_module_2dc15', text=bpy.context.scene.sna_bl_py_module.split(',')[i_F773C], icon_value=string_to_icon('MEMORY'), emboss=True, depress=False)
            op.sna_python_module = bpy.context.scene.sna_bl_py_module.split(',')[i_F773C]
        col_6A86E.label(text='模块名称预设：', icon_value=0)
        col_6A86E.prop(bpy.context.scene, 'sna_bl_py_module', text='', icon_value=0, emboss=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)


class SNA_OT_My_Generic_Operator_8D541(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_8d541"
    bl_label = "插件开关"
    bl_description = "开关切换"
    bl_options = {"REGISTER", "UNDO"}
    sna_mod_name: bpy.props.StringProperty(name='mod_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_mod_bi: bpy.props.BoolProperty(name='mod_bi', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if self.sna_mod_bi:
            bpy.ops.preferences.addon_enable(module=self.sna_mod_name)
        else:
            bpy.ops.preferences.addon_disable(module=self.sna_mod_name)
        bpy.ops.wm.save_userpref()
        sna_func_36762()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_04323(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_04323"
    bl_label = "类别切换"
    bl_description = "类别切换"
    bl_options = {"REGISTER", "UNDO"}
    sna_name: bpy.props.StringProperty(name='name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree['sna_addons_class_name'] = self.sna_name
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_BA1A6(path):
    if os.path.exists(path):
        for i_E9151 in range(len([os.path.join(path, f) for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))])):
            if (property_exists("bpy.context.preferences.filepaths.script_directories", globals(), locals()) and os.path.basename([os.path.join(path, f) for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))][i_E9151]) in bpy.context.preferences.filepaths.script_directories):
                bpy.ops.preferences.script_directory_remove(index=bpy.context.preferences.filepaths.script_directories.find(os.path.basename([os.path.join(path, f) for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))][i_E9151])))
        for i_71A48 in range(len([os.path.join(path, f) for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))])):
            bpy.ops.preferences.script_directory_add(directory=[os.path.join(path, f) for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))][i_71A48])
        bpy.ops.wm.save_userpref()


class SNA_OT_My_Generic_Operator_87B0F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_87b0f"
    bl_label = "插件"
    bl_description = "插件管理器"
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
        col_037F4 = layout.column(heading='', align=True)
        col_037F4.alert = False
        col_037F4.enabled = True
        col_037F4.active = True
        col_037F4.use_property_split = False
        col_037F4.use_property_decorate = False
        col_037F4.scale_x = 1.0
        col_037F4.scale_y = 1.0
        col_037F4.alignment = 'Expand'.upper()
        col_037F4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_4F8C6 = col_037F4.row(heading='', align=True)
        row_4F8C6.alert = False
        row_4F8C6.enabled = True
        row_4F8C6.active = True
        row_4F8C6.use_property_split = False
        row_4F8C6.use_property_decorate = False
        row_4F8C6.scale_x = 1.0
        row_4F8C6.scale_y = 1.0
        row_4F8C6.alignment = 'Right'.upper()
        row_4F8C6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_4F8C6.operator('sna.py_mod_e1215', text='', icon_value=string_to_icon('SCRIPT'), emboss=False, depress=False)
        op = row_4F8C6.operator('sna.my_generic_operator_30228', text='', icon_value=string_to_icon('FILE_FOLDER'), emboss=False, depress=False)
        col_037F4.separator(factor=1.0)
        if os.path.exists(bpy.path.abspath(node_tree['sna_addons_path']).replace('addons\插件管理器', 'Blender_Script')):
            col_5B07A = col_037F4.column(heading='', align=True)
            col_5B07A.alert = False
            col_5B07A.enabled = True
            col_5B07A.active = True
            col_5B07A.use_property_split = False
            col_5B07A.use_property_decorate = False
            col_5B07A.scale_x = 1.0
            col_5B07A.scale_y = 1.0
            col_5B07A.alignment = 'Expand'.upper()
            col_5B07A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_5B07A.label(text='类别分类：', icon_value=string_to_icon('ANCHOR_LEFT'))
            grid_BE71D = col_5B07A.grid_flow(columns=6, row_major=True, even_columns=False, even_rows=False, align=True)
            grid_BE71D.enabled = True
            grid_BE71D.active = True
            grid_BE71D.use_property_split = False
            grid_BE71D.use_property_decorate = False
            grid_BE71D.alignment = 'Expand'.upper()
            grid_BE71D.scale_x = 1.0
            grid_BE71D.scale_y = 1.5
            if not True: grid_BE71D.operator_context = "EXEC_DEFAULT"
            for i_BD473 in range(len(node_tree['sna_addons_directories'])):
                op = grid_BE71D.operator('sna.my_generic_operator_04323', text=os.path.basename(node_tree['sna_addons_directories'][i_BD473]), icon_value=0, emboss=True, depress=(os.path.basename(node_tree['sna_addons_directories'][i_BD473]) == node_tree['sna_addons_class_name']))
                op.sna_name = os.path.basename(node_tree['sna_addons_directories'][i_BD473])
            for i_3734C in range(len(node_tree['sna_addons_directories'])):
                if (node_tree['sna_addons_class_name'] == os.path.basename(node_tree['sna_addons_directories'][i_3734C])):
                    for i_686BC in range(len([os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f) for f in os.listdir(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons')) if os.path.isdir(os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f))])):
                        box_ECB34 = col_5B07A.box()
                        box_ECB34.alert = False
                        box_ECB34.enabled = True
                        box_ECB34.active = True
                        box_ECB34.use_property_split = False
                        box_ECB34.use_property_decorate = False
                        box_ECB34.alignment = 'Expand'.upper()
                        box_ECB34.scale_x = 1.0
                        box_ECB34.scale_y = 1.0
                        if not True: box_ECB34.operator_context = "EXEC_DEFAULT"
                        split_AA7CF = box_ECB34.split(factor=0.699999988079071, align=True)
                        split_AA7CF.alert = False
                        split_AA7CF.enabled = True
                        split_AA7CF.active = True
                        split_AA7CF.use_property_split = False
                        split_AA7CF.use_property_decorate = False
                        split_AA7CF.scale_x = 1.0
                        split_AA7CF.scale_y = 1.0
                        split_AA7CF.alignment = 'Expand'.upper()
                        if not True: split_AA7CF.operator_context = "EXEC_DEFAULT"
                        split_AA7CF.label(text=os.path.basename([os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f) for f in os.listdir(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons')) if os.path.isdir(os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f))][i_686BC]), icon_value=string_to_icon('DISK_DRIVE'))
                        if os.path.basename([os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f) for f in os.listdir(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons')) if os.path.isdir(os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f))][i_686BC]) in node_tree['sna_addons_activate_list']:
                            op = split_AA7CF.operator('sna.my_generic_operator_8d541', text='已启用', icon_value=0, emboss=True, depress=True)
                            op.sna_mod_name = os.path.basename([os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f) for f in os.listdir(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons')) if os.path.isdir(os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f))][i_686BC])
                            op.sna_mod_bi = False
                        else:
                            op = split_AA7CF.operator('sna.my_generic_operator_8d541', text='已关闭', icon_value=0, emboss=True, depress=False)
                            op.sna_mod_name = os.path.basename([os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f) for f in os.listdir(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons')) if os.path.isdir(os.path.join(os.path.join(node_tree['sna_addons_directories'][i_3734C],'addons'), f))][i_686BC])
                            op.sna_mod_bi = True

    def invoke(self, context, event):
        addon_path = None
        import os
        # 只有当插件被启用时，才能直接这样获取
        addon_path = os.path.dirname(__file__)
        print(f"插件路径: {addon_path}")
        node_tree['sna_addons_path'] = addon_path
        sna_func_36762()
        sna_func_BA1A6(bpy.path.abspath(node_tree['sna_addons_path']).replace('addons\插件管理器', 'Blender_Script'))
        if os.path.exists(bpy.path.abspath(node_tree['sna_addons_path']).replace('addons\插件管理器', 'Blender_Script')):
            node_tree['sna_addons_directories'] = [os.path.join(bpy.path.abspath(node_tree['sna_addons_path']).replace('addons\插件管理器', 'Blender_Script'), f) for f in os.listdir(bpy.path.abspath(node_tree['sna_addons_path']).replace('addons\插件管理器', 'Blender_Script')) if os.path.isdir(os.path.join(bpy.path.abspath(node_tree['sna_addons_path']).replace('addons\插件管理器', 'Blender_Script'), f))]
        return context.window_manager.invoke_props_dialog(self, width=400)


def sna_add_to_view3d_ht_tool_header_3B763(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('sna.my_generic_operator_87b0f', text='插件', icon_value=string_to_icon('DISC'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_30228(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_30228"
    bl_label = "打开目录"
    bl_description = "打开目录"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        folder_path = os.path.dirname(bpy.path.abspath(node_tree['sna_addons_path']).replace('addons\插件管理器', 'Blender_Script'))
        # 打开文件夹
        os.startfile(folder_path)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_36762():
    addons_list = None
    # 获取已激活的插件名称及其模块名
    active_addons = bpy.context.preferences.addons
    addons_list = []
    # 遍历已激活的插件并打印它们的名称和模块名
    for addon_key in active_addons.keys():
        addon = active_addons[addon_key]
        print(f"Name: {addon_key}, Module: {addon.module}")
        addons_list.append(addon_key)
    node_tree['sna_addons_activate_list'] = addons_list


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_bl_py_module = bpy.props.StringProperty(name='bl_py_module', description='', default='--upgrade pip,pyperclip,openpyxl,pillow,pywin32,send2trash', subtype='NONE', maxlen=0)
    bpy.utils.register_class(SNA_OT_Python_Module_2Dc15)
    bpy.utils.register_class(SNA_OT_Py_Mod_E1215)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_8D541)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_04323)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_87B0F)
    bpy.types.VIEW3D_HT_tool_header.append(sna_add_to_view3d_ht_tool_header_3B763)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_30228)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_bl_py_module
    bpy.utils.unregister_class(SNA_OT_Python_Module_2Dc15)
    bpy.utils.unregister_class(SNA_OT_Py_Mod_E1215)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_8D541)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_04323)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_87B0F)
    bpy.types.VIEW3D_HT_tool_header.remove(sna_add_to_view3d_ht_tool_header_3B763)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_30228)
