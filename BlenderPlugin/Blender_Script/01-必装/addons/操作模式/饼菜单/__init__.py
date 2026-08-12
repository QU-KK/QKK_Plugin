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
    "name" : "QKK_PIE",
    "author" : "QKK", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D_饼菜单" 
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
main = {'sna_pie_file': [], 'sna_pie_exp_dir': [], }


def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id


class SNA_MT_527A6(bpy.types.Menu):
    bl_idname = "SNA_MT_527A6"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.menu_pie()
        for i_E3081 in range(len(main['sna_pie_file'])):
            if ((i_E3081 == 2) and (len(main['sna_pie_exp_dir']) != 0)):
                box_8D97E = layout.box()
                box_8D97E.alert = False
                box_8D97E.enabled = True
                box_8D97E.active = True
                box_8D97E.use_property_split = False
                box_8D97E.use_property_decorate = False
                box_8D97E.alignment = 'Expand'.upper()
                box_8D97E.scale_x = 1.0
                box_8D97E.scale_y = 1.0
                if not True: box_8D97E.operator_context = "EXEC_DEFAULT"
                col_F4F50 = box_8D97E.column(heading='', align=True)
                col_F4F50.alert = False
                col_F4F50.enabled = True
                col_F4F50.active = True
                col_F4F50.use_property_split = False
                col_F4F50.use_property_decorate = False
                col_F4F50.scale_x = 1.0
                col_F4F50.scale_y = 1.2999999523162842
                col_F4F50.alignment = 'Expand'.upper()
                col_F4F50.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                for i_E598C in range(len(main['sna_pie_exp_dir'])):
                    box_3A1FE = col_F4F50.box()
                    box_3A1FE.alert = False
                    box_3A1FE.enabled = True
                    box_3A1FE.active = True
                    box_3A1FE.use_property_split = False
                    box_3A1FE.use_property_decorate = False
                    box_3A1FE.alignment = 'Expand'.upper()
                    box_3A1FE.scale_x = 1.0
                    box_3A1FE.scale_y = 1.0
                    if not True: box_3A1FE.operator_context = "EXEC_DEFAULT"
                    if '行' in os.path.basename(main['sna_pie_exp_dir'][i_E598C]):
                        grid_96766 = box_3A1FE.grid_flow(columns=string_to_type(os.path.basename(main['sna_pie_exp_dir'][i_E598C]).split('-')[2], int, 0), row_major=True, even_columns=False, even_rows=False, align=True)
                        grid_96766.enabled = True
                        grid_96766.active = True
                        grid_96766.use_property_split = False
                        grid_96766.use_property_decorate = False
                        grid_96766.alignment = 'Expand'.upper()
                        grid_96766.scale_x = 1.0
                        grid_96766.scale_y = 1.0
                        if not True: grid_96766.operator_context = "EXEC_DEFAULT"
                        for i_6D814 in range(len([os.path.join(main['sna_pie_exp_dir'][i_E598C], f) for f in os.listdir(main['sna_pie_exp_dir'][i_E598C]) if os.path.isfile(os.path.join(main['sna_pie_exp_dir'][i_E598C], f))])):
                            layout_function = grid_96766
                            sna_expansion_panel_C4BF0(layout_function, [os.path.join(main['sna_pie_exp_dir'][i_E598C], f) for f in os.listdir(main['sna_pie_exp_dir'][i_E598C]) if os.path.isfile(os.path.join(main['sna_pie_exp_dir'][i_E598C], f))][i_6D814])
                    else:
                        col_87773 = box_3A1FE.column(heading='', align=True)
                        col_87773.alert = False
                        col_87773.enabled = True
                        col_87773.active = True
                        col_87773.use_property_split = False
                        col_87773.use_property_decorate = False
                        col_87773.scale_x = 1.0
                        col_87773.scale_y = 1.0
                        col_87773.alignment = 'Expand'.upper()
                        col_87773.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        for i_29312 in range(len([os.path.join(main['sna_pie_exp_dir'][i_E598C], f) for f in os.listdir(main['sna_pie_exp_dir'][i_E598C]) if os.path.isfile(os.path.join(main['sna_pie_exp_dir'][i_E598C], f))])):
                            layout_function = col_87773
                            sna_expansion_panel_C4BF0(layout_function, [os.path.join(main['sna_pie_exp_dir'][i_E598C], f) for f in os.listdir(main['sna_pie_exp_dir'][i_E598C]) if os.path.isfile(os.path.join(main['sna_pie_exp_dir'][i_E598C], f))][i_29312])
            else:
                layout_function = layout
                sna_expansion_panel_C4BF0(layout_function, main['sna_pie_file'][i_E3081])


class SNA_OT_Run_Py_30311(bpy.types.Operator):
    bl_idname = "sna.run_py_30311"
    bl_label = "Run_Py"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_py_script_path: bpy.props.StringProperty(name='Py_Script_Path', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if bpy.context.scene.sna_qkk_pie_debug:
            Py_Script_Path = self.sna_py_script_path
            # 打开指定目录并选中
            # 注意：/select, 后面不要有空格
            subprocess.Popen(f'explorer /select, "{Py_Script_Path}"')
            self.report({'INFO'}, message='调试模式运行完毕！')
        else:
            Py_Script_Path = self.sna_py_script_path
            # 运行指定路径脚本
            exec(open(Py_Script_Path).read())
            # 读取并运行外部 .py 文件
            #with open(Py_Script_Path, 'r', encoding='utf-8') as file:
                #script_content = file.read()
            # 使用 exec 执行外部代码
            #exec(script_content)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Qkk_Pie_B6877(bpy.types.Operator):
    bl_idname = "sna.qkk_pie_b6877"
    bl_label = "QKK_PIE"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_mode: bpy.props.StringProperty(name='Mode', description='', options={'HIDDEN'}, default='', subtype='DIR_PATH', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        print((self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if ((self.sna_mode != '空格') and (bpy.context.mode == 'EDIT_MESH')) else bpy.context.mode) + '-' + self.sna_mode))
        Py_Path = None
        #Py_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "饼菜单配置")
        Py_Path = r'C:\QKK_Plugin\BlenderPlugin\Blender_Script\01-必装\addons\操作模式\饼菜单\饼菜单配置'
        #Py_Path = r'D:\QKK_Plugin\BlenderPlugin\Blender_Script\01-必装\addons\操作模式\饼菜单\饼菜单配置'
        main['sna_pie_file'] = [os.path.join(os.path.join(Py_Path,(self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if ((self.sna_mode != '空格') and (bpy.context.mode == 'EDIT_MESH')) else bpy.context.mode) + '-' + self.sna_mode)), f) for f in os.listdir(os.path.join(Py_Path,(self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if ((self.sna_mode != '空格') and (bpy.context.mode == 'EDIT_MESH')) else bpy.context.mode) + '-' + self.sna_mode))) if os.path.isfile(os.path.join(os.path.join(Py_Path,(self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if ((self.sna_mode != '空格') and (bpy.context.mode == 'EDIT_MESH')) else bpy.context.mode) + '-' + self.sna_mode)), f))]
        if os.path.exists(os.path.join(os.path.join(Py_Path,(self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if ((self.sna_mode != '空格') and (bpy.context.mode == 'EDIT_MESH')) else bpy.context.mode) + '-' + self.sna_mode)),'扩展')):
            main['sna_pie_exp_dir'] = [os.path.join(os.path.join(os.path.join(Py_Path,(self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if ((self.sna_mode != '空格') and (bpy.context.mode == 'EDIT_MESH')) else bpy.context.mode) + '-' + self.sna_mode)),'扩展'), f) for f in os.listdir(os.path.join(os.path.join(Py_Path,(self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if ((self.sna_mode != '空格') and (bpy.context.mode == 'EDIT_MESH')) else bpy.context.mode) + '-' + self.sna_mode)),'扩展')) if os.path.isdir(os.path.join(os.path.join(os.path.join(Py_Path,(self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if ((self.sna_mode != '空格') and (bpy.context.mode == 'EDIT_MESH')) else bpy.context.mode) + '-' + self.sna_mode)),'扩展'), f))]
        bpy.ops.wm.call_menu_pie(name="SNA_MT_527A6")
        return {"FINISHED"}

    def invoke(self, context, event):
        main['sna_pie_file'] = []
        main['sna_pie_exp_dir'] = []
        return self.execute(context)


def sna_add_to_statusbar_ht_header_C4608(self, context):
    if not (False):
        layout = self.layout
        layout.prop(bpy.context.scene, 'sna_qkk_pie_debug', text='', icon_value=string_to_icon('SEQ_STRIP_MODIFIER'), emboss=True)


def sna_expansion_panel_C4BF0(layout_function, py_file_data):
    if '-操作项=' in os.path.basename(py_file_data):
        op = layout_function.operator('sn.dummy_button_operator', text=os.path.basename(py_file_data).replace('.py', '').split('-')[1], icon_value=(load_preview_icon(os.path.join(py_file_data.split('饼菜单配置')[0],'图标',os.path.basename(py_file_data).replace('.py', '').split('-')[2].split('=')[1] + '.png')) if '-图标=' in os.path.basename(py_file_data) else string_to_icon(os.path.basename(py_file_data).replace('.py', '').split('-')[2])), emboss=True, depress=False)
        layout_function.label(text=os.path.basename(py_file_data).replace('.py', '').split('-')[3].split('=')[1], icon_value=0)
    else:
        op = layout_function.operator('sna.run_py_30311', text=os.path.basename(py_file_data).replace('.py', '').split('-')[1], icon_value=(load_preview_icon(os.path.join(py_file_data.split('饼菜单配置')[0],'图标',os.path.basename(py_file_data).replace('.py', '').split('-')[2].split('=')[1] + '.png')) if '-图标=' in os.path.basename(py_file_data) else string_to_icon(os.path.basename(py_file_data).replace('.py', '').split('-')[2])), emboss=True, depress=False)
        op.sna_py_script_path = py_file_data


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_qkk_pie_debug = bpy.props.BoolProperty(name='qkk_pie_debug', description='饼菜单调试', default=False)
    bpy.utils.register_class(SNA_MT_527A6)
    bpy.utils.register_class(SNA_OT_Run_Py_30311)
    bpy.utils.register_class(SNA_OT_Qkk_Pie_B6877)
    bpy.types.STATUSBAR_HT_header.append(sna_add_to_statusbar_ht_header_C4608)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.qkk_pie_b6877', 'RIGHTMOUSE', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.sna_mode = '全模式-右键'
    addon_keymaps['4666F'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.qkk_pie_b6877', 'RIGHTMOUSE', 'PRESS',
        ctrl=True, alt=False, shift=False, repeat=False)
    kmi.properties.sna_mode = 'Ctrl右键'
    addon_keymaps['86D7F'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.qkk_pie_b6877', 'RIGHTMOUSE', 'PRESS',
        ctrl=False, alt=False, shift=True, repeat=False)
    kmi.properties.sna_mode = 'Shift右键'
    addon_keymaps['90FAA'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.qkk_pie_b6877', 'SPACE', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.sna_mode = '空格'
    addon_keymaps['65249'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_qkk_pie_debug
    bpy.utils.unregister_class(SNA_MT_527A6)
    bpy.utils.unregister_class(SNA_OT_Run_Py_30311)
    bpy.utils.unregister_class(SNA_OT_Qkk_Pie_B6877)
    bpy.types.STATUSBAR_HT_header.remove(sna_add_to_statusbar_ht_header_C4608)
