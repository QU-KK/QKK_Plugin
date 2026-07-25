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
main = {'sna_py_path': '', }
class SNA_MT_527A6(bpy.types.Menu):
    bl_idname = "SNA_MT_527A6"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw(self, context):
        layout = self.layout.menu_pie()
        for i_E3081 in range(len([os.path.join(main['sna_py_path'], f) for f in os.listdir(main['sna_py_path']) if os.path.isfile(os.path.join(main['sna_py_path'], f))])):
            if (i_E3081 == 2):
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
                col_F4F50.scale_y = 1.5
                col_F4F50.alignment = 'Expand'.upper()
                col_F4F50.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                for i_E598C in range(len([os.path.join(os.path.join(main['sna_py_path'],'扩展'),'A'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'B'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'C')])):
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
                    if (i_E598C == 0):
                        grid_96766 = box_3A1FE.grid_flow(columns=2, row_major=False, even_columns=False, even_rows=True, align=True)
                        grid_96766.enabled = True
                        grid_96766.active = True
                        grid_96766.use_property_split = False
                        grid_96766.use_property_decorate = False
                        grid_96766.alignment = 'Expand'.upper()
                        grid_96766.scale_x = 1.0
                        grid_96766.scale_y = 1.0
                        if not True: grid_96766.operator_context = "EXEC_DEFAULT"
                        layout_function = grid_96766
                        sna_expansion_panel_958FC(layout_function, [os.path.join([os.path.join(os.path.join(main['sna_py_path'],'扩展'),'A'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'B'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'C')][i_E598C], f) for f in os.listdir([os.path.join(os.path.join(main['sna_py_path'],'扩展'),'A'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'B'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'C')][i_E598C]) if os.path.isfile(os.path.join([os.path.join(os.path.join(main['sna_py_path'],'扩展'),'A'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'B'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'C')][i_E598C], f))])
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
                        layout_function = col_87773
                        sna_expansion_panel_958FC(layout_function, [os.path.join([os.path.join(os.path.join(main['sna_py_path'],'扩展'),'A'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'B'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'C')][i_E598C], f) for f in os.listdir([os.path.join(os.path.join(main['sna_py_path'],'扩展'),'A'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'B'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'C')][i_E598C]) if os.path.isfile(os.path.join([os.path.join(os.path.join(main['sna_py_path'],'扩展'),'A'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'B'), os.path.join(os.path.join(main['sna_py_path'],'扩展'),'C')][i_E598C], f))])
            else:
                op = layout.operator('sna.run_py_30311', text=os.path.basename([os.path.join(main['sna_py_path'], f) for f in os.listdir(main['sna_py_path']) if os.path.isfile(os.path.join(main['sna_py_path'], f))][i_E3081]).replace('.py', '').split('-')[1], icon_value=string_to_icon(os.path.basename([os.path.join(main['sna_py_path'], f) for f in os.listdir(main['sna_py_path']) if os.path.isfile(os.path.join(main['sna_py_path'], f))][i_E3081]).replace('.py', '').split('-')[2]), emboss=True, depress=False)
                op.sna_py_script_path = [os.path.join(main['sna_py_path'], f) for f in os.listdir(main['sna_py_path']) if os.path.isfile(os.path.join(main['sna_py_path'], f))][i_E3081]


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
        Py_Script_Path = self.sna_py_script_path
        # 读取并运行外部 .py 文件
        with open(Py_Script_Path, 'r', encoding='utf-8') as file:
            script_content = file.read()
        # 使用 exec 执行外部代码
        exec(script_content)
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
        print((self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if (bpy.context.mode == 'EDIT_MESH') else bpy.context.mode) + '-' + self.sna_mode))
        Py_Path = None
        Py_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "饼菜单配置")
        #Py_Path = r'C:\Users\qkk666\Desktop\饼菜单\饼菜单配置'
        main['sna_py_path'] = os.path.join(Py_Path,(self.sna_mode if (self.sna_mode == '全模式-右键') else (bpy.context.mode + '-' + ('点' if bpy.context.tool_settings.mesh_select_mode[0] else '') + ('线' if bpy.context.tool_settings.mesh_select_mode[1] else '') + ('面' if bpy.context.tool_settings.mesh_select_mode[2] else '') if (bpy.context.mode == 'EDIT_MESH') else bpy.context.mode) + '-' + self.sna_mode))
        bpy.ops.wm.call_menu_pie(name="SNA_MT_527A6")
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_expansion_panel_958FC(layout_function, py_file_data_list):
    for i_B2508 in range(len(py_file_data_list)):
        op = layout_function.operator('sna.run_py_30311', text=os.path.basename(py_file_data_list[i_B2508]).replace('.py', '').split('-')[1], icon_value=string_to_icon(os.path.basename(py_file_data_list[i_B2508]).replace('.py', '').split('-')[2]), emboss=True, depress=False)
        op.sna_py_script_path = py_file_data_list[i_B2508]


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_MT_527A6)
    bpy.utils.register_class(SNA_OT_Run_Py_30311)
    bpy.utils.register_class(SNA_OT_Qkk_Pie_B6877)
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
    bpy.utils.unregister_class(SNA_MT_527A6)
    bpy.utils.unregister_class(SNA_OT_Run_Py_30311)
    bpy.utils.unregister_class(SNA_OT_Qkk_Pie_B6877)
