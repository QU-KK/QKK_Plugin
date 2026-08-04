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
    "blender" : (4, 2, 0),
    "version" : (1, 1, 0),
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


def sna_update_sna_qkk_normal_length_53D5B(self, context):
    sna_updated_prop = self.sna_qkk_normal_length
    qkk_normal_length = sna_updated_prop
    bpy.context.space_data.overlay.normals_length = qkk_normal_length


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_PT_vegetation_vaking_D8CD6(bpy.types.Panel):
    bl_label = '植被工具'
    bl_idname = 'SNA_PT_vegetation_vaking_D8CD6'
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
        bpy.ops.object.modifier_add(type='DATA_TRANSFER', use_selected_objects=False)
        bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].use_loop_data = True
        bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].data_types_loops = set(['CUSTOM_NORMAL'])
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
        bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'normal_mod.blend')) + r'\Object', filename=self.sna_mod_name, link=False)
        new_data = list(filter(lambda d: not d in before_data, list(bpy.data.objects)))
        appended_8B3F5 = None if not new_data else new_data[0]
        self.report({'INFO'}, message='导入成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_A69C9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a69c9"
    bl_label = "应用变换"
    bl_description = "应用变换"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        bpy.ops.object.select_pattern(pattern=bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object.name, case_sensitive=True, extend=False)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=False, isolate_users=False)
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
        bpy.ops.wm.call_panel(name="SNA_PT_wap_asset_816DA", keep_open=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_wap_asset_816DA(bpy.types.Panel):
    bl_label = '包裹素材'
    bl_idname = 'SNA_PT_wap_asset_816DA'
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
        for i_BDD5E in range(len(get_blend_contents(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'normal_mod.blend')), 'objects'))-1,-1,-1):
            op = grid_9C999.operator('sna.import_default_fb92f', text=get_blend_contents(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'normal_mod.blend')), 'objects')[i_BDD5E], icon_value=0, emboss=True, depress=False)
            op.sna_mod_name = get_blend_contents(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'normal_mod.blend')), 'objects')[i_BDD5E]


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
    split_67115 = col_84BF0.split(factor=0.5, align=True)
    split_67115.alert = False
    split_67115.enabled = True
    split_67115.active = True
    split_67115.use_property_split = False
    split_67115.use_property_decorate = False
    split_67115.scale_x = 1.0
    split_67115.scale_y = 1.0
    split_67115.alignment = 'Expand'.upper()
    if not True: split_67115.operator_context = "EXEC_DEFAULT"
    split_67115.prop(bpy.context.scene.sna_qkk_obj_input_001.modifiers[0], 'object', text='', icon_value=723, emboss=True)
    if (None != bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object):
        row_966F7 = split_67115.row(heading='', align=True)
        row_966F7.alert = False
        row_966F7.enabled = True
        row_966F7.active = True
        row_966F7.use_property_split = False
        row_966F7.use_property_decorate = False
        row_966F7.scale_x = 1.0
        row_966F7.scale_y = 1.0
        row_966F7.alignment = 'Expand'.upper()
        row_966F7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_966F7.prop(bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object, 'hide_viewport', text='', icon_value=string_to_icon('HIDE_OFF'), emboss=True)
        row_966F7.prop(bpy.context.scene.sna_qkk_obj_input_001.modifiers[0], 'show_viewport', text='', icon_value=string_to_icon('FILE_VOLUME'), emboss=True, invert_checkbox=True)
        col_F7485 = row_966F7.column(heading='', align=True)
        col_F7485.alert = (((1.0, 1.0, 1.0) != (bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object.scale[0], bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object.scale[1], bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object.scale[2])) or ((bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object.rotation_euler[0], bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object.rotation_euler[1], bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object.rotation_euler[2]) != (0.0, 0.0, 0.0)))
        col_F7485.enabled = (not bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].object.hide_viewport)
        col_F7485.active = True
        col_F7485.use_property_split = False
        col_F7485.use_property_decorate = False
        col_F7485.scale_x = 1.0
        col_F7485.scale_y = 1.0
        col_F7485.alignment = 'Expand'.upper()
        col_F7485.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_F7485.operator('sna.my_generic_operator_a69c9', text='应用变换', icon_value=0, emboss=True, depress=False)
    col_84BF0.separator(factor=1.0)


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
        layout_function = split_A15D4
        sna_func_854E5(layout_function, )


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


class SNA_OT_My_Generic_Operator_4756B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_4756b"
    bl_label = "法线方向"
    bl_description = "法线方向"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active = bpy.context.scene.sna_qkk_obj_input_001
        bpy.ops.object.select_pattern(pattern=bpy.context.scene.sna_qkk_obj_input_001.name, case_sensitive=True, extend=True)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        exec('bpy.context.space_data.overlay.show_edge_sharp = False')
        exec('bpy.context.space_data.overlay.show_edge_crease = False')
        exec('bpy.context.space_data.overlay.show_edge_bevel_weight = False')
        exec('bpy.context.space_data.overlay.show_edge_seams = False')
        exec('bpy.context.space_data.overlay.show_split_normals = True')
        if property_exists("bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].data_types_loops", globals(), locals()):
            exec('bpy.context.object.modifiers["DataTransfer"].show_in_editmode = True')
            exec('bpy.context.object.modifiers["DataTransfer"].show_on_cage = True')
            qkk_normal_length = bpy.context.scene.sna_qkk_normal_length
            bpy.context.space_data.overlay.normals_length = qkk_normal_length
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_D1B88(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d1b88"
    bl_label = "关闭法线方向"
    bl_description = "关闭法线方向"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
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
    if ('EDIT_MESH'==bpy.context.mode and bpy.context.area.spaces[0].overlay.show_split_normals and (property_exists("bpy.context.view_layer.objects.selected", globals(), locals()) and bpy.context.scene.sna_qkk_obj_input_001.name in bpy.context.view_layer.objects.selected)):
        op = col_7C5CD.operator('sna.my_generic_operator_d1b88', text='法线方向', icon_value=string_to_icon('RECORD_ON'), emboss=True, depress=True)
    else:
        op = col_7C5CD.operator('sna.my_generic_operator_4756b', text='法线方向', icon_value=string_to_icon('RECORD_OFF'), emboss=True, depress=False)
    col_7C5CD.prop(bpy.context.scene, 'sna_qkk_normal_length', text='法线长度', icon_value=0, emboss=True)


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
        split_7823F = col_3ADD4.split(factor=0.5, align=True)
        split_7823F.alert = False
        split_7823F.enabled = True
        split_7823F.active = True
        split_7823F.use_property_split = False
        split_7823F.use_property_decorate = False
        split_7823F.scale_x = 1.0
        split_7823F.scale_y = 1.0
        split_7823F.alignment = 'Expand'.upper()
        if not True: split_7823F.operator_context = "EXEC_DEFAULT"
        box_D211A = split_7823F.box()
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
        box_C6FDD = split_7823F.box()
        box_C6FDD.alert = False
        box_C6FDD.enabled = True
        box_C6FDD.active = True
        box_C6FDD.use_property_split = False
        box_C6FDD.use_property_decorate = False
        box_C6FDD.alignment = 'Expand'.upper()
        box_C6FDD.scale_x = 1.0
        box_C6FDD.scale_y = 1.0
        if not True: box_C6FDD.operator_context = "EXEC_DEFAULT"
        col_9B095 = box_C6FDD.column(heading='', align=False)
        col_9B095.alert = False
        col_9B095.enabled = True
        col_9B095.active = True
        col_9B095.use_property_split = False
        col_9B095.use_property_decorate = False
        col_9B095.scale_x = 1.0
        col_9B095.scale_y = 1.5
        col_9B095.alignment = 'Expand'.upper()
        col_9B095.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_9B095.operator('sna.my_generic_operator_304ef', text='烘焙植被顶点色', icon_value=string_to_icon('STICKY_UVS_DISABLE'), emboss=True, depress=False)
        col_76708 = col_9B095.column(heading='', align=False)
        col_76708.alert = False
        col_76708.enabled = (len(bpy.context.scene.sna_qkk_obj_input_002.data.vertex_colors) >= 1)
        col_76708.active = True
        col_76708.use_property_split = False
        col_76708.use_property_decorate = False
        col_76708.scale_x = 1.0
        col_76708.scale_y = 1.0
        col_76708.alignment = 'Expand'.upper()
        col_76708.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        if 'PAINT_VERTEX'==bpy.context.mode:
            op = col_76708.operator('object.mode_set', text='预览顶点色', icon_value=string_to_icon('RADIOBUT_ON'), emboss=True, depress=True)
            op.mode = 'OBJECT'
            op.toggle = False
        else:
            op = col_76708.operator('sna.my_generic_operator_2a864', text='预览顶点色', icon_value=string_to_icon('RADIOBUT_OFF'), emboss=True, depress=False)
        col_B4B2F = col_76708.column(heading='', align=True)
        col_B4B2F.alert = False
        col_B4B2F.enabled = 'OBJECT'==bpy.context.mode
        col_B4B2F.active = True
        col_B4B2F.use_property_split = False
        col_B4B2F.use_property_decorate = False
        col_B4B2F.scale_x = 1.0
        col_B4B2F.scale_y = 1.0
        col_B4B2F.alignment = 'Expand'.upper()
        col_B4B2F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_B4B2F.operator('sna.my_generic_operator_dd095', text='清空顶点色', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_304Ef(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_304ef"
    bl_label = "烘焙顶点色"
    bl_description = "R=纵向渐变    G=AO    B=无"
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
        before_data = list(bpy.data.materials)
        bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'normal_mod.blend')) + r'\Material', filename='植被顶点色烘焙', link=True)
        new_data = list(filter(lambda d: not d in before_data, list(bpy.data.materials)))
        appended_0C811 = None if not new_data else new_data[0]
        bpy.context.view_layer.material_override = bpy.data.materials['植被顶点色烘焙']
        bpy.context.view_layer.objects.active = bpy.context.scene.sna_qkk_obj_input_002
        bpy.ops.object.select_pattern(pattern=bpy.context.view_layer.objects.active.name, case_sensitive=True, extend=False)
        if (len(bpy.context.scene.sna_qkk_obj_input_002.data.vertex_colors) >= 1):
            bpy.ops.object.bake(type='COMBINED', target='VERTEX_COLORS')
        else:
            bpy.ops.geometry.color_attribute_add(name='RGB', domain='CORNER', data_type='BYTE_COLOR', color=(0.0, 0.0, 0.0, 1.0))
            bpy.ops.object.bake(type='COMBINED', target='VERTEX_COLORS')
        bpy.context.blend_data.materials.remove(material=bpy.data.materials['植被顶点色烘焙'], )
        self.report({'INFO'}, message='植被顶点色烘焙完毕！  R=纵向渐变    G=AO    B=无')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_2A864(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2a864"
    bl_label = "预览顶点色"
    bl_description = "预览顶点色"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active = bpy.context.scene.sna_qkk_obj_input_002
        bpy.ops.object.select_pattern(pattern=bpy.context.view_layer.objects.active.name, case_sensitive=True, extend=False)
        bpy.ops.object.mode_set(mode='VERTEX_PAINT', toggle=False)
        bpy.context.area.spaces[0].shading.type = 'SOLID'
        self.report({'INFO'}, message='预览顶点色！')
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


class SNA_PT_spherical_normal001_ADE4E(bpy.types.Panel):
    bl_label = '球形法线'
    bl_idname = 'SNA_PT_spherical_normal001_ADE4E'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_vegetation_vaking_D8CD6'
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
            if property_exists("bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].data_types_loops", globals(), locals()):
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
            if property_exists("bpy.context.scene.sna_qkk_obj_input_001.modifiers[0].data_types_loops", globals(), locals()):
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
                op = split_487F6.operator('sna.clear_2824b', text='放弃', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)


class SNA_PT_vertex_color_0CB71(bpy.types.Panel):
    bl_label = '植被顶点色'
    bl_idname = 'SNA_PT_vertex_color_0CB71'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_vegetation_vaking_D8CD6'
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
    bpy.types.Scene.sna_qkk_normal_length = bpy.props.FloatProperty(name='qkk_normal_length', description='法线长度', default=0.20000000298023224, subtype='NONE', unit='LENGTH', min=0.0, soft_max=1.0, step=1, precision=2, update=sna_update_sna_qkk_normal_length_53D5B)
    bpy.types.Scene.sna_qkk_obj_input_002 = bpy.props.PointerProperty(name='qkk_obj_input_002', description='植被', type=bpy.types.Object)
    bpy.utils.register_class(SNA_PT_vegetation_vaking_D8CD6)
    bpy.utils.register_class(SNA_OT_Spherical_Normal_Run_194D7)
    bpy.utils.register_class(SNA_OT_Clear_2824B)
    bpy.utils.register_class(SNA_OT_Apply_B79B9)
    bpy.utils.register_class(SNA_OT_Import_Default_Fb92F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A69C9)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_De403)
    bpy.utils.register_class(SNA_PT_wap_asset_816DA)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1F75B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_109Cf)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_4756B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D1B88)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_304Ef)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2A864)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Dd095)
    bpy.utils.register_class(SNA_PT_spherical_normal001_ADE4E)
    bpy.utils.register_class(SNA_PT_vertex_color_0CB71)


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
    bpy.utils.unregister_class(SNA_PT_vegetation_vaking_D8CD6)
    bpy.utils.unregister_class(SNA_OT_Spherical_Normal_Run_194D7)
    bpy.utils.unregister_class(SNA_OT_Clear_2824B)
    bpy.utils.unregister_class(SNA_OT_Apply_B79B9)
    bpy.utils.unregister_class(SNA_OT_Import_Default_Fb92F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A69C9)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_De403)
    bpy.utils.unregister_class(SNA_PT_wap_asset_816DA)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1F75B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_109Cf)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_4756B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D1B88)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_304Ef)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2A864)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Dd095)
    bpy.utils.unregister_class(SNA_PT_spherical_normal001_ADE4E)
    bpy.utils.unregister_class(SNA_PT_vertex_color_0CB71)
