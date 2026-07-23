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
    "name" : "Check_Mod",
    "author" : "QKK", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "资产质检工具" 
}


import bpy
import bpy.utils.previews




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
zmd_ = {'sna_check_overall_ui': [], 'sna_check_overall_data': [], 'sna_check_overall_mod': [], }
_item_map = dict()


def make_enum_item(_id, name, descr, preview_id, uid):
    lookup = str(_id)+"\0"+str(name)+"\0"+str(descr)+"\0"+str(preview_id)+"\0"+str(uid)
    if not lookup in _item_map:
        _item_map[lookup] = (_id, name, descr, preview_id, uid)
    return _item_map[lookup]


class SNA_PT_panel_6BBA6(bpy.types.Panel):
    bl_label = '终末地质检'
    bl_idname = 'SNA_PT_panel_6BBA6'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'ZMD'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_main_529FA(layout_function, )


def sna_check_category_enum_items(self, context):
    enum_items = zmd_['sna_check_overall_ui']
    return [make_enum_item(item[0], item[1], item[2], item[3], i) for i, item in enumerate(enum_items)]


class SNA_OT_Check_65690(bpy.types.Operator):
    bl_idname = "sna.check_65690"
    bl_label = "Check"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        script_path = None
        Check_Overall_Data = zmd_['sna_check_overall_data']
        Check_Overall_Ui = zmd_['sna_check_overall_ui']
        selected_objects = None
        import os
        os.system('cls')
        print('开始检查!')
        # 获取选中的网格对象
        selected_objects = []
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                selected_objects.append(obj)
        #target_dir = r"C:\QKK_Plugin\BlenderPlugin\Blender_Script\ZMD\addons\ZMD_质量检工具\Check_Py"
        target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Check_Py")
        # 只过滤当前目录下的第一级文件夹
        Contents = [
            os.path.join(target_dir, d)
            for d in os.listdir(target_dir)
            if os.path.isdir(os.path.join(target_dir, d))
        ]
        for path in Contents:
            # 外部脚本路径
            script_path = os.path.join(path, "Run_Check.py")
            namespace = {
                "selected_objects": selected_objects, # 把你的变量传进去
                "Check_Overall_Ui": Check_Overall_Ui, # 把你的变量传进去
                "Check_Overall_Data": Check_Overall_Data # 把你的变量传进去
            }
            # 读取并运行外部 .py 文件
            with open(script_path, 'r', encoding='utf-8') as file:
                script_content = file.read()
            # 核心：使用 exec 执行外部代码，执行的上下文就是我们刚才定义的 namespace
            exec(script_content, namespace)
            # 运行完毕后，从 namespace 中把变量拿出来
            Check_Overall_Ui = namespace.get('Check_Overall_Ui') # 如果外部脚本没生成这个变量，默认给 False
            Check_Overall_Data = namespace.get('Check_Overall_Data')
        print('检查完毕!')
        zmd_['sna_check_overall_mod'] = selected_objects
        return {"FINISHED"}

    def invoke(self, context, event):
        zmd_['sna_check_overall_ui'] = []
        zmd_['sna_check_overall_data'] = []
        zmd_['sna_check_overall_mod'] = []
        return self.execute(context)


def sna_main_529FA(layout_function, ):
    col_348DE = layout_function.column(heading='', align=True)
    col_348DE.alert = False
    col_348DE.enabled = (len(bpy.context.view_layer.objects.selected) != 0)
    col_348DE.active = True
    col_348DE.use_property_split = False
    col_348DE.use_property_decorate = False
    col_348DE.scale_x = 1.0
    col_348DE.scale_y = 1.5
    col_348DE.alignment = 'Expand'.upper()
    col_348DE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_348DE.operator('sna.check_65690', text='检查', icon_value=string_to_icon('MOD_TIME'), emboss=True, depress=False)
    if (len(zmd_['sna_check_overall_ui']) != 0):
        col_B20DF = layout_function.column(heading='', align=False)
        col_B20DF.alert = False
        col_B20DF.enabled = True
        col_B20DF.active = True
        col_B20DF.use_property_split = False
        col_B20DF.use_property_decorate = False
        col_B20DF.scale_x = 1.0
        col_B20DF.scale_y = 1.0
        col_B20DF.alignment = 'Expand'.upper()
        col_B20DF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_4C932 = col_B20DF.row(heading='', align=False)
        row_4C932.alert = False
        row_4C932.enabled = True
        row_4C932.active = True
        row_4C932.use_property_split = False
        row_4C932.use_property_decorate = False
        row_4C932.scale_x = 1.0
        row_4C932.scale_y = 1.0
        row_4C932.alignment = 'Right'.upper()
        row_4C932.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_4C932.label(text='当前选中 = ' + str(len(bpy.context.view_layer.objects.selected)), icon_value=0)
        row_4C932.label(text='检查模型数 = ' + str(len(zmd_['sna_check_overall_mod'])), icon_value=0)
        op = row_4C932.operator('sna.my_generic_operator_2b330', text='选中', icon_value=string_to_icon('FILE_3D'), emboss=True, depress=False)
        split_071AE = col_B20DF.split(factor=0.800000011920929, align=True)
        split_071AE.alert = False
        split_071AE.enabled = True
        split_071AE.active = True
        split_071AE.use_property_split = False
        split_071AE.use_property_decorate = False
        split_071AE.scale_x = 1.0
        split_071AE.scale_y = 1.0
        split_071AE.alignment = 'Expand'.upper()
        if not True: split_071AE.operator_context = "EXEC_DEFAULT"
        split_02767 = split_071AE.split(factor=0.20000000298023224, align=True)
        split_02767.alert = False
        split_02767.enabled = True
        split_02767.active = True
        split_02767.use_property_split = False
        split_02767.use_property_decorate = False
        split_02767.scale_x = 1.0
        split_02767.scale_y = 1.0
        split_02767.alignment = 'Expand'.upper()
        if not True: split_02767.operator_context = "EXEC_DEFAULT"
        box_35621 = split_02767.box()
        box_35621.alert = False
        box_35621.enabled = True
        box_35621.active = True
        box_35621.use_property_split = False
        box_35621.use_property_decorate = False
        box_35621.alignment = 'Expand'.upper()
        box_35621.scale_x = 1.0
        box_35621.scale_y = 1.0
        if not True: box_35621.operator_context = "EXEC_DEFAULT"
        col_CF307 = box_35621.column(heading='', align=False)
        col_CF307.alert = False
        col_CF307.enabled = True
        col_CF307.active = True
        col_CF307.use_property_split = False
        col_CF307.use_property_decorate = False
        col_CF307.scale_x = 1.0
        col_CF307.scale_y = 1.0
        col_CF307.alignment = 'Expand'.upper()
        col_CF307.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_CF307.prop(bpy.context.scene, 'sna_check_category', text=bpy.context.scene.sna_check_category, icon_value=0, emboss=True, expand=True)
        col_DBC95 = split_02767.column(heading='', align=True)
        col_DBC95.alert = False
        col_DBC95.enabled = True
        col_DBC95.active = True
        col_DBC95.use_property_split = False
        col_DBC95.use_property_decorate = False
        col_DBC95.scale_x = 1.0
        col_DBC95.scale_y = 1.0
        col_DBC95.alignment = 'Expand'.upper()
        col_DBC95.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        for i_E6AD3 in range(len(zmd_['sna_check_overall_data'])):
            if (bpy.context.scene.sna_check_category == zmd_['sna_check_overall_data'][i_E6AD3][0]):
                for i_DBCC1 in range(len(zmd_['sna_check_overall_data'][i_E6AD3])):
                    if (i_DBCC1 != 0):
                        box_F7A37 = col_DBC95.box()
                        box_F7A37.alert = False
                        box_F7A37.enabled = True
                        box_F7A37.active = True
                        box_F7A37.use_property_split = False
                        box_F7A37.use_property_decorate = False
                        box_F7A37.alignment = 'Expand'.upper()
                        box_F7A37.scale_x = 1.0
                        box_F7A37.scale_y = 1.0
                        if not True: box_F7A37.operator_context = "EXEC_DEFAULT"
                        row_988BC = box_F7A37.row(heading='', align=False)
                        row_988BC.alert = False
                        row_988BC.enabled = True
                        row_988BC.active = True
                        row_988BC.use_property_split = False
                        row_988BC.use_property_decorate = False
                        row_988BC.scale_x = 1.0
                        row_988BC.scale_y = 1.0
                        row_988BC.alignment = 'Expand'.upper()
                        row_988BC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        op = row_988BC.operator('sna.my_generic_operator_46c90', text='', icon_value=30, emboss=True, depress=(bpy.context.view_layer.objects.active.name == zmd_['sna_check_overall_data'][i_E6AD3][i_DBCC1][0]))
                        op.sna_obj_name = zmd_['sna_check_overall_data'][i_E6AD3][i_DBCC1][0]
                        split_299B6 = row_988BC.split(factor=0.6000000238418579, align=True)
                        split_299B6.alert = False
                        split_299B6.enabled = True
                        split_299B6.active = True
                        split_299B6.use_property_split = False
                        split_299B6.use_property_decorate = False
                        split_299B6.scale_x = 1.0
                        split_299B6.scale_y = 1.0
                        split_299B6.alignment = 'Expand'.upper()
                        if not True: split_299B6.operator_context = "EXEC_DEFAULT"
                        split_299B6.label(text=zmd_['sna_check_overall_data'][i_E6AD3][i_DBCC1][0], icon_value=0)
                        split_299B6.label(text=zmd_['sna_check_overall_data'][i_E6AD3][i_DBCC1][1], icon_value=0)
                    else:
                        if (1 == len(zmd_['sna_check_overall_data'][i_E6AD3])):
                            box_EAC77 = col_DBC95.box()
                            box_EAC77.alert = False
                            box_EAC77.enabled = True
                            box_EAC77.active = True
                            box_EAC77.use_property_split = False
                            box_EAC77.use_property_decorate = False
                            box_EAC77.alignment = 'Expand'.upper()
                            box_EAC77.scale_x = 1.0
                            box_EAC77.scale_y = 1.0
                            if not True: box_EAC77.operator_context = "EXEC_DEFAULT"
                            box_EAC77.label(text='检查通过！！！', icon_value=string_to_icon('CHECKMARK'))
        layout_function = split_071AE
        sna_function_interface_5C46D(layout_function, )


class SNA_OT_Open_F0C59(bpy.types.Operator):
    bl_idname = "sna.open_f0c59"
    bl_label = "Open"
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
        layout_function = layout
        sna_main_529FA(layout_function, )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=700)


def sna_add_to_view3d_mt_editor_menus_4E6CC(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('sna.open_f0c59', text='质检', icon_value=1013, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_46C90(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_46c90"
    bl_label = "选中物体"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_obj_name: bpy.props.StringProperty(name='obj_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.select_pattern(pattern=self.sna_obj_name, case_sensitive=True, extend=False)
        bpy.context.view_layer.objects.active = bpy.data.objects[self.sna_obj_name]
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_2B330(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2b330"
    bl_label = "批量选中物体"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        obj_list = zmd_['sna_check_overall_mod']
        bpy.ops.object.select_all(action='DESELECT')
        for obj in obj_list:
            obj_name = obj.name
            bpy.ops.object.select_pattern(pattern=obj_name, case_sensitive=True, extend=True)
            bpy.context.view_layer.objects.active = obj
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_function_interface_5C46D(layout_function, ):
    box_ACA1D = layout_function.box()
    box_ACA1D.alert = False
    box_ACA1D.enabled = True
    box_ACA1D.active = True
    box_ACA1D.use_property_split = False
    box_ACA1D.use_property_decorate = False
    box_ACA1D.alignment = 'Expand'.upper()
    box_ACA1D.scale_x = 1.0
    box_ACA1D.scale_y = 1.0
    if not True: box_ACA1D.operator_context = "EXEC_DEFAULT"
    op = box_ACA1D.operator('sn.dummy_button_operator', text=bpy.context.scene.sna_check_category, icon_value=0, emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_check_category = bpy.props.EnumProperty(name='check_category', description='', items=sna_check_category_enum_items)
    bpy.utils.register_class(SNA_PT_panel_6BBA6)
    bpy.utils.register_class(SNA_OT_Check_65690)
    bpy.utils.register_class(SNA_OT_Open_F0C59)
    bpy.types.VIEW3D_MT_editor_menus.prepend(sna_add_to_view3d_mt_editor_menus_4E6CC)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_46C90)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2B330)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_check_category
    bpy.utils.unregister_class(SNA_PT_panel_6BBA6)
    bpy.utils.unregister_class(SNA_OT_Check_65690)
    bpy.utils.unregister_class(SNA_OT_Open_F0C59)
    bpy.types.VIEW3D_MT_editor_menus.remove(sna_add_to_view3d_mt_editor_menus_4E6CC)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_46C90)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2B330)
