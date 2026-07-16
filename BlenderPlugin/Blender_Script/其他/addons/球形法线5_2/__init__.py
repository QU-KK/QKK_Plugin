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
    "name" : "QKk_Spherical_Normal",
    "author" : "QKK(B站：瑶土豆)", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (3, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "https://space.bilibili.com/261155258/video", 
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
node_tree = {'sna_hide_and_show': False, }


def get_blend_contents(path, data_type):
    if os.path.exists(path):
        with bpy.data.libraries.load(path) as (data_from, data_to):
            return getattr(data_from, data_type)
    return []


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


def sna_update_sna_qkk_normal_length_2CBB1(self, context):
    sna_updated_prop = self.sna_qkk_normal_length
    qkk_normal_length = sna_updated_prop
    bpy.data.screens['Layout'].areas[2].spaces[0].overlay.normals_length = qkk_normal_length


def change_viewmode_skd(viewmode):
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = viewmode


class SNA_PT_vegetation_vaking_E0E4B(bpy.types.Panel):
    bl_label = '植被工具'
    bl_idname = 'SNA_PT_vegetation_vaking_E0E4B'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '便捷功能'
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


class SNA_OT_Spherical_Normal_Run_194D7(bpy.types.Operator):
    bl_idname = "sna.spherical_normal_run_194d7"
    bl_label = "Spherical_Normal_Run"
    bl_description = "启动映射"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active = bpy.context.scene.sna_qkk_obj_input_001
        bpy.ops.object.select_pattern(pattern=bpy.context.scene.sna_qkk_obj_input_001.name, case_sensitive=False, extend=False)
        bpy.context.scene.sna_qkk_obj_input_001.modifiers.clear()
        before_data = list(bpy.data.node_groups)
        bpy.ops.wm.append(directory=bpy.path.abspath('') + r'\NodeTree', filename='法线朝向可视化', link=True)
        new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
        appended_87EB3 = None if not new_data else new_data[0]
        bpy.ops.object.modifier_add(type='NODES', use_selected_objects=False)
        bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].node_group = bpy.data.node_groups['法线朝向可视化']
        bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].name = '法线朝向可视化'
        self.report({'INFO'}, message='配置完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Clear_2824B(bpy.types.Operator):
    bl_idname = "sna.clear_2824b"
    bl_label = "Clear"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active = bpy.context.scene.sna_qkk_obj_input_001
        bpy.ops.object.select_pattern(pattern=bpy.context.scene.sna_qkk_obj_input_001.name, case_sensitive=False, extend=False)
        bpy.context.view_layer.objects.active.modifiers.clear()
        self.report({'INFO'}, message='清空完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_Apply_B79B9(bpy.types.Operator):
    bl_idname = "sna.apply_b79b9"
    bl_label = "Apply"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active = bpy.context.scene.sna_qkk_obj_input_001
        bpy.ops.object.select_pattern(pattern=bpy.context.scene.sna_qkk_obj_input_001.name, case_sensitive=False, extend=False)
        bpy.ops.object.convert(target='MESH')
        self.report({'INFO'}, message='应用完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_Import_Default_Fb92F(bpy.types.Operator):
    bl_idname = "sna.import_default_fb92f"
    bl_label = "Import_Default"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_mod_name: bpy.props.StringProperty(name='mod_name', description='', default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        before_data = list(bpy.data.objects)
        bpy.ops.wm.append(directory=bpy.path.abspath('') + r'\Object', filename=self.sna_mod_name, link=False)
        new_data = list(filter(lambda d: not d in before_data, list(bpy.data.objects)))
        appended_8B3F5 = None if not new_data else new_data[0]
        self.report({'INFO'}, message='导入成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_De403(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_de403"
    bl_label = "素材"
    bl_description = "素材"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_wap_asset_E00E1", keep_open=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_wap_asset_E00E1(bpy.types.Panel):
    bl_label = '包裹素材'
    bl_idname = 'SNA_PT_wap_asset_E00E1'
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
        grid_9C999 = layout.grid_flow(columns=2, row_major=True, even_columns=False, even_rows=False, align=True)
        grid_9C999.enabled = True
        grid_9C999.active = True
        grid_9C999.use_property_split = False
        grid_9C999.use_property_decorate = False
        grid_9C999.alignment = 'Expand'.upper()
        grid_9C999.scale_x = 1.0
        grid_9C999.scale_y = 1.2000000476837158
        if not True: grid_9C999.operator_context = "EXEC_DEFAULT"
        for i_BDD5E in range(len(get_blend_contents(bpy.path.abspath(''), 'objects'))-1,-1,-1):
            op = grid_9C999.operator('sna.import_default_fb92f', text=get_blend_contents(bpy.path.abspath(''), 'objects')[i_BDD5E], icon_value=0, emboss=True, depress=False)
            op.sna_mod_name = get_blend_contents(bpy.path.abspath(''), 'objects')[i_BDD5E]


def sna_func_57533(layout_function, ):
    box_1114E = layout_function.box()
    box_1114E.alert = False
    box_1114E.enabled = True
    box_1114E.active = True
    box_1114E.use_property_split = False
    box_1114E.use_property_decorate = False
    box_1114E.alignment = 'Expand'.upper()
    box_1114E.scale_x = 1.0
    box_1114E.scale_y = 1.0
    if not True: box_1114E.operator_context = "EXEC_DEFAULT"
    col_84BF0 = box_1114E.column(heading='', align=False)
    col_84BF0.alert = False
    col_84BF0.enabled = True
    col_84BF0.active = True
    col_84BF0.use_property_split = False
    col_84BF0.use_property_decorate = False
    col_84BF0.scale_x = 1.0
    col_84BF0.scale_y = 1.100000023841858
    col_84BF0.alignment = 'Expand'.upper()
    col_84BF0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    split_6F317 = col_84BF0.split(factor=0.699999988079071, align=True)
    split_6F317.alert = False
    split_6F317.enabled = True
    split_6F317.active = True
    split_6F317.use_property_split = False
    split_6F317.use_property_decorate = False
    split_6F317.scale_x = 1.0
    split_6F317.scale_y = 1.0
    split_6F317.alignment = 'Expand'.upper()
    if not True: split_6F317.operator_context = "EXEC_DEFAULT"
    split_6F317.label(text='包围体：', icon_value=0)
    op = split_6F317.operator('sna.my_generic_operator_de403', text='包裹素材', icon_value=string_to_icon('MOD_FLUID'), emboss=True, depress=False)
    split_67115 = col_84BF0.split(factor=0.800000011920929, align=True)
    split_67115.alert = False
    split_67115.enabled = True
    split_67115.active = True
    split_67115.use_property_split = False
    split_67115.use_property_decorate = False
    split_67115.scale_x = 1.0
    split_67115.scale_y = 1.0
    split_67115.alignment = 'Expand'.upper()
    if not True: split_67115.operator_context = "EXEC_DEFAULT"
    split_67115.prop(bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].properties.inputs.Socket_6, 'value', text='', icon_value=string_to_icon('FILE_3D'), emboss=True)
    if (None != bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].properties.inputs.Socket_6.value):
        row_6B061 = split_67115.row(heading='', align=True)
        row_6B061.alert = False
        row_6B061.enabled = True
        row_6B061.active = True
        row_6B061.use_property_split = False
        row_6B061.use_property_decorate = False
        row_6B061.scale_x = 1.0
        row_6B061.scale_y = 1.0
        row_6B061.alignment = 'Expand'.upper()
        row_6B061.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_6B061.operator('sna.my_generic_operator_943ba', text='', icon_value=string_to_icon(('RESTRICT_VIEW_ON' if node_tree['sna_hide_and_show'] else 'RESTRICT_VIEW_OFF')), emboss=True, depress=(not node_tree['sna_hide_and_show']))
        row_6B061.prop(bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].properties.inputs.Socket_5, 'value', text='', icon_value=string_to_icon('FILE_VOLUME'), emboss=True, toggle=True)
    col_84BF0.separator(factor=1.0)


class SNA_OT_My_Generic_Operator_943Ba(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_943ba"
    bl_label = "隐藏"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.data.objects[bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].properties.inputs.Socket_6.value.name].hide_set((not node_tree['sna_hide_and_show']))
        node_tree['sna_hide_and_show'] = (not node_tree['sna_hide_and_show'])
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_ui_D365C(layout_function, ):
    box_B2A12 = layout_function.box()
    box_B2A12.alert = False
    box_B2A12.enabled = True
    box_B2A12.active = True
    box_B2A12.use_property_split = False
    box_B2A12.use_property_decorate = False
    box_B2A12.alignment = 'Expand'.upper()
    box_B2A12.scale_x = 1.0
    box_B2A12.scale_y = 1.0
    if not True: box_B2A12.operator_context = "EXEC_DEFAULT"
    col_852AD = box_B2A12.column(heading='', align=False)
    col_852AD.alert = False
    col_852AD.enabled = True
    col_852AD.active = True
    col_852AD.use_property_split = False
    col_852AD.use_property_decorate = False
    col_852AD.scale_x = 1.0
    col_852AD.scale_y = 1.0
    col_852AD.alignment = 'Expand'.upper()
    col_852AD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_852AD.label(text='植被：', icon_value=0)
    col_852AD.prop(bpy.context.scene, 'sna_qkk_obj_input_001', text='', icon_value=string_to_icon('FILE_3D'), emboss=True)
    if property_exists("bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].name", globals(), locals()):
        if property_exists("bpy.context.scene.sna_qkk_obj_input_001.name", globals(), locals()):
            split_A15D4 = col_852AD.split(factor=0.5, align=True)
            split_A15D4.alert = False
            split_A15D4.enabled = True
            split_A15D4.active = True
            split_A15D4.use_property_split = False
            split_A15D4.use_property_decorate = False
            split_A15D4.scale_x = 1.0
            split_A15D4.scale_y = 1.0
            split_A15D4.alignment = 'Expand'.upper()
            if not True: split_A15D4.operator_context = "EXEC_DEFAULT"
            box_3A23B = split_A15D4.box()
            box_3A23B.alert = False
            box_3A23B.enabled = True
            box_3A23B.active = True
            box_3A23B.use_property_split = False
            box_3A23B.use_property_decorate = False
            box_3A23B.alignment = 'Expand'.upper()
            box_3A23B.scale_x = 1.0
            box_3A23B.scale_y = 1.0
            if not True: box_3A23B.operator_context = "EXEC_DEFAULT"
            box_3A23B.template_icon(icon_value=get_id_preview_id(bpy.data.objects[bpy.context.scene.sna_qkk_obj_input_001.name]), scale=4.0)
            if property_exists("bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].name", globals(), locals()):
                layout_function = split_A15D4
                sna_func_854E5(layout_function, )
    else:
        if property_exists("bpy.context.scene.sna_qkk_obj_input_001.name", globals(), locals()):
            box_589A9 = col_852AD.box()
            box_589A9.alert = False
            box_589A9.enabled = True
            box_589A9.active = True
            box_589A9.use_property_split = False
            box_589A9.use_property_decorate = False
            box_589A9.alignment = 'Expand'.upper()
            box_589A9.scale_x = 1.0
            box_589A9.scale_y = 1.0
            if not True: box_589A9.operator_context = "EXEC_DEFAULT"
            box_589A9.template_icon(icon_value=get_id_preview_id(bpy.data.objects[bpy.context.scene.sna_qkk_obj_input_001.name]), scale=4.0)


class SNA_OT_My_Generic_Operator_1F75B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_1f75b"
    bl_label = "法线可视化"
    bl_description = "法线可视化"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        exec("bpy.context.space_data.shading.type = 'SOLID'")
        exec("bpy.context.space_data.shading.light = 'MATCAP'")
        exec("bpy.context.space_data.shading.studio_light = 'check_normal+y.exr'")
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_109Cf(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_109cf"
    bl_label = "关闭法线可视化"
    bl_description = "关闭法线可视化"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        exec("bpy.context.space_data.shading.light = 'STUDIO'")
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_854E5(layout_function, ):
    box_899F6 = layout_function.box()
    box_899F6.alert = False
    box_899F6.enabled = True
    box_899F6.active = True
    box_899F6.use_property_split = False
    box_899F6.use_property_decorate = False
    box_899F6.alignment = 'Expand'.upper()
    box_899F6.scale_x = 1.0
    box_899F6.scale_y = 1.0
    if not True: box_899F6.operator_context = "EXEC_DEFAULT"
    col_7C5CD = box_899F6.column(heading='', align=True)
    col_7C5CD.alert = False
    col_7C5CD.enabled = True
    col_7C5CD.active = True
    col_7C5CD.use_property_split = False
    col_7C5CD.use_property_decorate = False
    col_7C5CD.scale_x = 1.0
    col_7C5CD.scale_y = 1.0
    col_7C5CD.alignment = 'Expand'.upper()
    col_7C5CD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_7C5CD.label(text='可视化：', icon_value=0)
    if ((bpy.context.area.spaces[0].shading.type == 'SOLID') and (bpy.context.area.spaces[0].shading.light == 'MATCAP') and (bpy.context.area.spaces[0].shading.studio_light == 'check_normal+y.exr')):
        op = col_7C5CD.operator('sna.my_generic_operator_109cf', text='法线颜色', icon_value=string_to_icon('RECORD_ON'), emboss=True, depress=True)
    else:
        op = col_7C5CD.operator('sna.my_generic_operator_1f75b', text='法线颜色', icon_value=string_to_icon('RECORD_OFF'), emboss=True, depress=False)
    col_7C5CD.prop(bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].properties.inputs.Socket_4, 'value', text='法线方向', icon_value=string_to_icon(('RECORD_ON' if bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].properties.inputs.Socket_4.value else 'RECORD_OFF')), emboss=True)
    col_7C5CD.prop(bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].properties.inputs.Socket_3, 'value', text='长度', icon_value=0, emboss=True)


class SNA_PT_check_FF52B(bpy.types.Panel):
    bl_label = '检查器'
    bl_idname = 'SNA_PT_check_FF52B'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_vegetation_vaking_E0E4B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        box_7DBC0 = layout.box()
        box_7DBC0.alert = False
        box_7DBC0.enabled = True
        box_7DBC0.active = True
        box_7DBC0.use_property_split = False
        box_7DBC0.use_property_decorate = False
        box_7DBC0.alignment = 'Expand'.upper()
        box_7DBC0.scale_x = 1.0
        box_7DBC0.scale_y = 1.0
        if not True: box_7DBC0.operator_context = "EXEC_DEFAULT"
        split_33EE0 = box_7DBC0.split(factor=0.800000011920929, align=True)
        split_33EE0.alert = False
        split_33EE0.enabled = True
        split_33EE0.active = True
        split_33EE0.use_property_split = False
        split_33EE0.use_property_decorate = False
        split_33EE0.scale_x = 1.0
        split_33EE0.scale_y = 1.0
        split_33EE0.alignment = 'Expand'.upper()
        if not True: split_33EE0.operator_context = "EXEC_DEFAULT"
        col_E4E85 = split_33EE0.column(heading='', align=True)
        col_E4E85.alert = False
        col_E4E85.enabled = True
        col_E4E85.active = True
        col_E4E85.use_property_split = False
        col_E4E85.use_property_decorate = False
        col_E4E85.scale_x = 1.0
        col_E4E85.scale_y = 1.0
        col_E4E85.alignment = 'Expand'.upper()
        col_E4E85.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_E4E85.operator('sna.my_generic_operator_6ea10', text='检查模型法线', icon_value=0, emboss=True, depress=False)
        col_E4E85.prop(bpy.context.scene, 'sna_qkk_normal_length', text='', icon_value=0, emboss=True)
        col_D0B5C = split_33EE0.column(heading='', align=True)
        col_D0B5C.alert = False
        col_D0B5C.enabled = True
        col_D0B5C.active = True
        col_D0B5C.use_property_split = False
        col_D0B5C.use_property_decorate = False
        col_D0B5C.scale_x = 1.0
        col_D0B5C.scale_y = 2.0
        col_D0B5C.alignment = 'Expand'.upper()
        col_D0B5C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_D0B5C.operator('object.mode_set', text='关闭', icon_value=0, emboss=True, depress=False)
        op.mode = 'OBJECT'
        op.toggle = False
        box_A527F = layout.box()
        box_A527F.alert = False
        box_A527F.enabled = True
        box_A527F.active = True
        box_A527F.use_property_split = False
        box_A527F.use_property_decorate = False
        box_A527F.alignment = 'Expand'.upper()
        box_A527F.scale_x = 1.0
        box_A527F.scale_y = 1.0
        if not True: box_A527F.operator_context = "EXEC_DEFAULT"
        col_5ED28 = box_A527F.column(heading='', align=True)
        col_5ED28.alert = False
        col_5ED28.enabled = True
        col_5ED28.active = True
        col_5ED28.use_property_split = False
        col_5ED28.use_property_decorate = False
        col_5ED28.scale_x = 1.0
        col_5ED28.scale_y = 1.0
        col_5ED28.alignment = 'Expand'.upper()
        col_5ED28.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_CCB71 = col_5ED28.row(heading='', align=True)
        row_CCB71.alert = False
        row_CCB71.enabled = True
        row_CCB71.active = True
        row_CCB71.use_property_split = False
        row_CCB71.use_property_decorate = False
        row_CCB71.scale_x = 1.0
        row_CCB71.scale_y = 1.0
        row_CCB71.alignment = 'Expand'.upper()
        row_CCB71.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_CCB71.operator('sna.rgb_c9d3c', text='RGB', icon_value=0, emboss=True, depress=False)
        op.sna_rgb = 0
        op = row_CCB71.operator('sna.rgb_c9d3c', text='R', icon_value=0, emboss=True, depress=False)
        op.sna_rgb = 1
        op = row_CCB71.operator('sna.rgb_c9d3c', text='G', icon_value=0, emboss=True, depress=False)
        op.sna_rgb = 2
        op = row_CCB71.operator('sna.rgb_c9d3c', text='B', icon_value=0, emboss=True, depress=False)
        op.sna_rgb = 3
        op = col_5ED28.operator('sna.my_generic_operator_3e61b', text='关闭', icon_value=0, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_6Ea10(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6ea10"
    bl_label = "检查模型法线"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        exec("bpy.ops.object.mode_set(mode='EDIT')")
        exec('bpy.context.space_data.overlay.show_split_normals = True')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_3E61B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3e61b"
    bl_label = "关闭"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Rgb_C9D3C(bpy.types.Operator):
    bl_idname = "sna.rgb_c9d3c"
    bl_label = "顶点色检查RGB"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_rgb: bpy.props.IntProperty(name='RGB', description='', options={'HIDDEN'}, default=0, subtype='NONE')

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES', use_selected_objects=False)
        bpy.context.view_layer.objects.active.modifiers[0].name = '顶点色检查节点'
        bpy.context.view_layer.objects.active.modifiers['顶点色检查节点'].node_group = bpy.data.node_groups['顶点色检查节点']
        bpy.context.view_layer.objects.active.modifiers['顶点色检查节点'].properties.inputs.Socket_2.value = self.sna_rgb
        bpy.context.view_layer.objects.active.modifiers['顶点色检查节点'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        before_data = list(bpy.data.node_groups)
        bpy.ops.wm.append(directory=bpy.path.abspath('') + r'\NodeTree', filename='顶点色检查节点', link=True)
        new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
        appended_3BC37 = None if not new_data else new_data[0]
        return self.execute(context)


def sna_func_12053(layout_function, ):
    box_C5E34 = layout_function.box()
    box_C5E34.alert = False
    box_C5E34.enabled = True
    box_C5E34.active = True
    box_C5E34.use_property_split = False
    box_C5E34.use_property_decorate = False
    box_C5E34.alignment = 'Expand'.upper()
    box_C5E34.scale_x = 1.0
    box_C5E34.scale_y = 1.0
    if not True: box_C5E34.operator_context = "EXEC_DEFAULT"
    col_3ADD4 = box_C5E34.column(heading='', align=False)
    col_3ADD4.alert = False
    col_3ADD4.enabled = True
    col_3ADD4.active = True
    col_3ADD4.use_property_split = False
    col_3ADD4.use_property_decorate = False
    col_3ADD4.scale_x = 1.0
    col_3ADD4.scale_y = 1.0
    col_3ADD4.alignment = 'Expand'.upper()
    col_3ADD4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_3ADD4.label(text='顶点色：', icon_value=0)
    col_3ADD4.prop(bpy.context.scene, 'sna_qkk_obj_input_002', text='', icon_value=string_to_icon('FILE_3D'), emboss=True)
    col_3ADD4.separator(factor=1.0)
    if property_exists("bpy.context.scene.sna_qkk_obj_input_002.name", globals(), locals()):
        col_9B095 = col_3ADD4.column(heading='', align=False)
        col_9B095.alert = False
        col_9B095.enabled = True
        col_9B095.active = True
        col_9B095.use_property_split = False
        col_9B095.use_property_decorate = False
        col_9B095.scale_x = 1.0
        col_9B095.scale_y = 1.0
        col_9B095.alignment = 'Expand'.upper()
        col_9B095.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        box_D211A = col_9B095.box()
        box_D211A.alert = False
        box_D211A.enabled = True
        box_D211A.active = True
        box_D211A.use_property_split = False
        box_D211A.use_property_decorate = False
        box_D211A.alignment = 'Expand'.upper()
        box_D211A.scale_x = 1.0
        box_D211A.scale_y = 1.0
        if not True: box_D211A.operator_context = "EXEC_DEFAULT"
        box_D211A.template_icon(icon_value=get_id_preview_id(bpy.data.objects[bpy.context.scene.sna_qkk_obj_input_002.name]), scale=4.699999809265137)
        box_9D22F = col_9B095.box()
        box_9D22F.alert = False
        box_9D22F.enabled = True
        box_9D22F.active = True
        box_9D22F.use_property_split = False
        box_9D22F.use_property_decorate = False
        box_9D22F.alignment = 'Expand'.upper()
        box_9D22F.scale_x = 1.0
        box_9D22F.scale_y = 1.0
        if not True: box_9D22F.operator_context = "EXEC_DEFAULT"
        if property_exists("bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_12.value", globals(), locals()):
            col_AFD82 = box_9D22F.column(heading='', align=False)
            col_AFD82.alert = False
            col_AFD82.enabled = True
            col_AFD82.active = True
            col_AFD82.use_property_split = False
            col_AFD82.use_property_decorate = False
            col_AFD82.scale_x = 1.0
            col_AFD82.scale_y = 1.0
            col_AFD82.alignment = 'Expand'.upper()
            col_AFD82.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_1125C = col_AFD82.column(heading='', align=True)
            col_1125C.alert = False
            col_1125C.enabled = True
            col_1125C.active = True
            col_1125C.use_property_split = False
            col_1125C.use_property_decorate = False
            col_1125C.scale_x = 1.0
            col_1125C.scale_y = 1.0
            col_1125C.alignment = 'Expand'.upper()
            col_1125C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_1125C.operator('sna.my_generic_operator_79ad8', text='RGB合并', icon_value=0, emboss=True, depress=(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_17.value == 0))
            op.sna_id = 0
            row_43E8D = col_1125C.row(heading='', align=True)
            row_43E8D.alert = False
            row_43E8D.enabled = True
            row_43E8D.active = True
            row_43E8D.use_property_split = False
            row_43E8D.use_property_decorate = False
            row_43E8D.scale_x = 1.0
            row_43E8D.scale_y = 1.0
            row_43E8D.alignment = 'Expand'.upper()
            row_43E8D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = row_43E8D.operator('sna.my_generic_operator_79ad8', text='R_距离AO', icon_value=0, emboss=True, depress=(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_17.value == 1))
            op.sna_id = 1
            op = row_43E8D.operator('sna.my_generic_operator_79ad8', text='G_渐变', icon_value=0, emboss=True, depress=(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_17.value == 2))
            op.sna_id = 2
            op = row_43E8D.operator('sna.my_generic_operator_79ad8', text='B_AO', icon_value=0, emboss=True, depress=(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_17.value == 3))
            op.sna_id = 3
            if (bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_17.value == 1):
                col_940E3 = col_AFD82.column(heading='', align=True)
                col_940E3.alert = False
                col_940E3.enabled = True
                col_940E3.active = True
                col_940E3.use_property_split = False
                col_940E3.use_property_decorate = False
                col_940E3.scale_x = 1.0
                col_940E3.scale_y = 1.0
                col_940E3.alignment = 'Expand'.upper()
                col_940E3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                box_C20FE = col_940E3.box()
                box_C20FE.alert = False
                box_C20FE.enabled = True
                box_C20FE.active = True
                box_C20FE.use_property_split = False
                box_C20FE.use_property_decorate = False
                box_C20FE.alignment = 'Expand'.upper()
                box_C20FE.scale_x = 1.0
                box_C20FE.scale_y = 1.0
                if not True: box_C20FE.operator_context = "EXEC_DEFAULT"
                col_F0B74 = box_C20FE.column(heading='', align=True)
                col_F0B74.alert = False
                col_F0B74.enabled = True
                col_F0B74.active = True
                col_F0B74.use_property_split = False
                col_F0B74.use_property_decorate = False
                col_F0B74.scale_x = 1.0
                col_F0B74.scale_y = 1.0
                col_F0B74.alignment = 'Expand'.upper()
                col_F0B74.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_3DA19 = col_F0B74.row(heading='', align=True)
                row_3DA19.alert = False
                row_3DA19.enabled = True
                row_3DA19.active = True
                row_3DA19.use_property_split = False
                row_3DA19.use_property_decorate = False
                row_3DA19.scale_x = 1.0
                row_3DA19.scale_y = 1.0
                row_3DA19.alignment = 'Expand'.upper()
                row_3DA19.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                row_3DA19.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_12, 'value', text='球形衰减', icon_value=0, emboss=True)
                row_3DA19.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_7, 'value', text='衰减可视', icon_value=0, emboss=True)
                col_F0B74.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_4, 'value', text='中心偏移', icon_value=0, emboss=True)
                col_F0B74.separator(factor=1.0)
                col_F0B74.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_5, 'value', text='衰减内', icon_value=0, emboss=True)
                col_F0B74.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_6, 'value', text='衰减外', icon_value=0, emboss=True)
                col_F0B74.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_13, 'value', text='最暗值', icon_value=0, emboss=True)
                box_BA494 = col_940E3.box()
                box_BA494.alert = False
                box_BA494.enabled = True
                box_BA494.active = True
                box_BA494.use_property_split = False
                box_BA494.use_property_decorate = False
                box_BA494.alignment = 'Expand'.upper()
                box_BA494.scale_x = 1.0
                box_BA494.scale_y = 1.0
                if not True: box_BA494.operator_context = "EXEC_DEFAULT"
                col_5E573 = box_BA494.column(heading='', align=True)
                col_5E573.alert = False
                col_5E573.enabled = True
                col_5E573.active = True
                col_5E573.use_property_split = False
                col_5E573.use_property_decorate = False
                col_5E573.scale_x = 1.0
                col_5E573.scale_y = 1.0
                col_5E573.alignment = 'Expand'.upper()
                col_5E573.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_5E573.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_3, 'value', text='自定义网格', icon_value=0, emboss=True)
                col_B0F3B = col_5E573.column(heading='', align=True)
                col_B0F3B.alert = False
                col_B0F3B.enabled = bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_3.value
                col_B0F3B.active = True
                col_B0F3B.use_property_split = False
                col_B0F3B.use_property_decorate = False
                col_B0F3B.scale_x = 1.0
                col_B0F3B.scale_y = 1.0
                col_B0F3B.alignment = 'Expand'.upper()
                col_B0F3B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_B0F3B.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_10, 'value', text='自定义衰减可视', icon_value=0, emboss=True)
                col_B0F3B.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_9, 'value', text='物体', icon_value=0, emboss=True)
                col_B0F3B.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_11, 'value', text='外扩', icon_value=0, emboss=True)
                col_B0F3B.prop(bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_14, 'value', text='最暗值', icon_value=0, emboss=True)
            split_A9958 = col_AFD82.split(factor=0.699999988079071, align=True)
            split_A9958.alert = False
            split_A9958.enabled = True
            split_A9958.active = True
            split_A9958.use_property_split = False
            split_A9958.use_property_decorate = False
            split_A9958.scale_x = 1.0
            split_A9958.scale_y = 1.5
            split_A9958.alignment = 'Expand'.upper()
            if not True: split_A9958.operator_context = "EXEC_DEFAULT"
            op = split_A9958.operator('sna.my_generic_operator_304ef', text='应用', icon_value=string_to_icon('CHECKMARK'), emboss=True, depress=False)
            op = split_A9958.operator('sna.my_generic_operator_b45d5', text='放弃', icon_value=85, emboss=True, depress=False)
        else:
            col_19146 = box_9D22F.column(heading='', align=True)
            col_19146.alert = False
            col_19146.enabled = True
            col_19146.active = True
            col_19146.use_property_split = False
            col_19146.use_property_decorate = False
            col_19146.scale_x = 1.0
            col_19146.scale_y = 1.5
            col_19146.alignment = 'Expand'.upper()
            col_19146.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_19146.operator('sna.my_generic_operator_1b318', text='初始化', icon_value=string_to_icon('STICKY_UVS_DISABLE'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_304Ef(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_304ef"
    bl_label = "烘焙顶点色"
    bl_description = "R=0     G=纵向渐变    B=AO"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        exec("bpy.context.scene.render.engine = 'CYCLES'")
        exec("bpy.context.scene.cycles.device = 'GPU'")
        exec('bpy.context.scene.cycles.samples = 1024')
        exec('bpy.context.scene.cycles.use_denoising = True')
        exec('bpy.context.scene.cycles.samples = 1024')
        exec("bpy.context.scene.cycles.bake_type = 'COMBINED'")
        exec("bpy.context.scene.render.bake.target = 'VERTEX_COLORS'")
        exec('bpy.context.scene.render.bake.use_selected_to_active = False')
        bpy.context.view_layer.objects.active = bpy.context.scene.sna_qkk_obj_input_002
        bpy.ops.object.select_pattern(pattern=bpy.context.view_layer.objects.active.name, case_sensitive=True, extend=False)
        bpy.ops.sna.my_generic_operator_dd095()
        bpy.ops.geometry.color_attribute_add(name='RGB', domain='CORNER', data_type='BYTE_COLOR', color=(0.0, 0.0, 0.0, 1.0))
        bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_17.value = 0
        bpy.ops.object.bake(type='COMBINED', target='VERTEX_COLORS')
        bpy.ops.sna.my_generic_operator_b45d5()
        self.report({'INFO'}, message='植被顶点色烘焙完毕!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Dd095(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_dd095"
    bl_label = "清空顶点色"
    bl_description = "清空顶点色"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_DF3AC in range(len(bpy.context.scene.sna_qkk_obj_input_002.data.vertex_colors)):
            bpy.ops.geometry.color_attribute_remove()
        return {"FINISHED"}

    def invoke(self, context, event):
        self.report({'INFO'}, message='清空顶点色完成！')
        return self.execute(context)


class SNA_OT_My_Generic_Operator_1B318(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_1b318"
    bl_label = "初始化"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.scene.sna_qkk_obj_input_002.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES', use_selected_objects=False)
        bpy.context.scene.sna_qkk_obj_input_002.modifiers[0].name = '顶点色烘焙节点'
        bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].node_group = bpy.data.node_groups['顶点色烘焙节点']
        self.report({'INFO'}, message='初始化完成！')
        return {"FINISHED"}

    def invoke(self, context, event):
        before_data = list(bpy.data.node_groups)
        bpy.ops.wm.append(directory=bpy.path.abspath('') + r'\NodeTree', filename='法线朝向可视化', link=True)
        new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
        appended_0C811 = None if not new_data else new_data[0]
        before_data = list(bpy.data.node_groups)
        bpy.ops.wm.append(directory=bpy.path.abspath('') + r'\NodeTree', filename='顶点色烘焙节点', link=True)
        new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
        appended_F73EB = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_B45D5(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b45d5"
    bl_label = "放弃"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.scene.sna_qkk_obj_input_002.modifiers.clear()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_79Ad8(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_79ad8"
    bl_label = "通道显示"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_id: bpy.props.IntProperty(name='通道ID', description='', options={'HIDDEN'}, default=0, subtype='NONE')

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        change_viewmode_skd("MATERIAL")
        bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].properties.inputs.Socket_17.value = self.sna_id
        sna_func_CC744()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_CC744():
    bpy.context.scene.sna_qkk_obj_input_002.modifiers['顶点色烘焙节点'].show_viewport = True


class SNA_PT_spherical_normal_29AC8(bpy.types.Panel):
    bl_label = '球形法线'
    bl_idname = 'SNA_PT_spherical_normal_29AC8'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_vegetation_vaking_E0E4B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        box_C115C = layout.box()
        box_C115C.alert = False
        box_C115C.enabled = True
        box_C115C.active = True
        box_C115C.use_property_split = False
        box_C115C.use_property_decorate = False
        box_C115C.alignment = 'Expand'.upper()
        box_C115C.scale_x = 1.0
        box_C115C.scale_y = 1.0
        if not True: box_C115C.operator_context = "EXEC_DEFAULT"
        col_D5E2D = box_C115C.column(heading='', align=True)
        col_D5E2D.alert = False
        col_D5E2D.enabled = True
        col_D5E2D.active = True
        col_D5E2D.use_property_split = False
        col_D5E2D.use_property_decorate = False
        col_D5E2D.scale_x = 1.0
        col_D5E2D.scale_y = 1.0
        col_D5E2D.alignment = 'Expand'.upper()
        col_D5E2D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        layout_function = col_D5E2D
        sna_ui_D365C(layout_function, )
        if property_exists("bpy.context.scene.sna_qkk_obj_input_001.name", globals(), locals()):
            col_D0B61 = col_D5E2D.column(heading='', align=True)
            col_D0B61.alert = False
            col_D0B61.enabled = True
            col_D0B61.active = True
            col_D0B61.use_property_split = False
            col_D0B61.use_property_decorate = False
            col_D0B61.scale_x = 1.0
            col_D0B61.scale_y = 1.0
            col_D0B61.alignment = 'Expand'.upper()
            col_D0B61.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].name", globals(), locals()):
                pass
            else:
                col_9802F = col_D0B61.column(heading='', align=True)
                col_9802F.alert = False
                col_9802F.enabled = True
                col_9802F.active = True
                col_9802F.use_property_split = False
                col_9802F.use_property_decorate = False
                col_9802F.scale_x = 1.0
                col_9802F.scale_y = 1.5
                col_9802F.alignment = 'Expand'.upper()
                col_9802F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_9802F.operator('sna.spherical_normal_run_194d7', text='启动映射', icon_value=string_to_icon('NORMALS_FACE'), emboss=True, depress=False)
            if property_exists("bpy.context.scene.sna_qkk_obj_input_001.modifiers['法线朝向可视化'].name", globals(), locals()):
                col_4B354 = col_D0B61.column(heading='', align=True)
                col_4B354.alert = False
                col_4B354.enabled = True
                col_4B354.active = True
                col_4B354.use_property_split = False
                col_4B354.use_property_decorate = False
                col_4B354.scale_x = 1.0
                col_4B354.scale_y = 1.0
                col_4B354.alignment = 'Expand'.upper()
                col_4B354.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                layout_function = col_4B354
                sna_func_57533(layout_function, )
                split_487F6 = col_4B354.split(factor=0.699999988079071, align=True)
                split_487F6.alert = False
                split_487F6.enabled = True
                split_487F6.active = True
                split_487F6.use_property_split = False
                split_487F6.use_property_decorate = False
                split_487F6.scale_x = 1.0
                split_487F6.scale_y = 1.5
                split_487F6.alignment = 'Expand'.upper()
                if not True: split_487F6.operator_context = "EXEC_DEFAULT"
                op = split_487F6.operator('sna.apply_b79b9', text='应用', icon_value=string_to_icon('CHECKMARK'), emboss=True, depress=False)
                op = split_487F6.operator('sna.clear_2824b', text='放弃', icon_value=string_to_icon('X'), emboss=True, depress=False)


class SNA_PT_vertex_color_BF948(bpy.types.Panel):
    bl_label = '植被顶点色'
    bl_idname = 'SNA_PT_vertex_color_BF948'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_vegetation_vaking_E0E4B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        sna_func_12053(layout_function, )


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_qkk_obj_input_001 = bpy.props.PointerProperty(name='qkk_obj_input_001', description='植被', type=bpy.types.Object)
    bpy.types.Scene.sna_qkk_normal_length = bpy.props.FloatProperty(name='qkk_normal_length', description='法线长度', default=0.20000000298023224, subtype='NONE', unit='LENGTH', min=0.0, soft_max=1.0, step=1, precision=2, update=sna_update_sna_qkk_normal_length_2CBB1)
    bpy.types.Scene.sna_qkk_obj_input_002 = bpy.props.PointerProperty(name='qkk_obj_input_002', description='植被', type=bpy.types.Object)
    bpy.utils.register_class(SNA_PT_vegetation_vaking_E0E4B)
    bpy.utils.register_class(SNA_OT_Spherical_Normal_Run_194D7)
    bpy.utils.register_class(SNA_OT_Clear_2824B)
    bpy.utils.register_class(SNA_OT_Apply_B79B9)
    bpy.utils.register_class(SNA_OT_Import_Default_Fb92F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_De403)
    bpy.utils.register_class(SNA_PT_wap_asset_E00E1)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_943Ba)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1F75B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_109Cf)
    bpy.utils.register_class(SNA_PT_check_FF52B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6Ea10)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3E61B)
    bpy.utils.register_class(SNA_OT_Rgb_C9D3C)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_304Ef)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Dd095)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1B318)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B45D5)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_79Ad8)
    bpy.utils.register_class(SNA_PT_spherical_normal_29AC8)
    bpy.utils.register_class(SNA_PT_vertex_color_BF948)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_qkk_obj_input_002
    del bpy.types.Scene.sna_qkk_normal_length
    del bpy.types.Scene.sna_qkk_obj_input_001
    bpy.utils.unregister_class(SNA_PT_vegetation_vaking_E0E4B)
    bpy.utils.unregister_class(SNA_OT_Spherical_Normal_Run_194D7)
    bpy.utils.unregister_class(SNA_OT_Clear_2824B)
    bpy.utils.unregister_class(SNA_OT_Apply_B79B9)
    bpy.utils.unregister_class(SNA_OT_Import_Default_Fb92F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_De403)
    bpy.utils.unregister_class(SNA_PT_wap_asset_E00E1)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_943Ba)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1F75B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_109Cf)
    bpy.utils.unregister_class(SNA_PT_check_FF52B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6Ea10)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3E61B)
    bpy.utils.unregister_class(SNA_OT_Rgb_C9D3C)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_304Ef)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Dd095)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1B318)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B45D5)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_79Ad8)
    bpy.utils.unregister_class(SNA_PT_spherical_normal_29AC8)
    bpy.utils.unregister_class(SNA_PT_vertex_color_BF948)
