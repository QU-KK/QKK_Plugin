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
    "name" : "Layered_Painting",
    "author" : "渠奎奎", 
    "description" : "",
    "blender" : (3, 5, 0),
    "version" : (2, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews
import os


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)



addon_keymaps = {}
_icons = None
node_tree_001 = {'sna_xiankuangkaiguan': False, }
node_tree = {'sna_dingdseshul': 0, }


def sna_update_sna_g108_penyagan_A830B(self, context):
    sna_updated_prop = self.sna_g108_penyagan
    prev_context = bpy.context.area.type
    bpy.context.area.type = 'VIEW_3D'
    bpy.ops.sna.my_generic_operator_8d1a0('INVOKE_DEFAULT', )
    bpy.context.area.type = prev_context


def sna_update_sna_g108_penqiangdu_2D7A4(self, context):
    sna_updated_prop = self.sna_g108_penqiangdu
    prev_context = bpy.context.area.type
    bpy.context.area.type = 'VIEW_3D'
    bpy.ops.sna.my_generic_operator_8d1a0('INVOKE_DEFAULT', )
    bpy.context.area.type = prev_context


def sna_update_sna_g108_xiangpiyagan_BB917(self, context):
    sna_updated_prop = self.sna_g108_xiangpiyagan
    prev_context = bpy.context.area.type
    bpy.context.area.type = 'VIEW_3D'
    bpy.ops.sna.my_generic_operator_8d1a0('INVOKE_DEFAULT', )
    bpy.context.area.type = prev_context


def sna_update_sna_g108_xiangpiqiangdu_A37FA(self, context):
    sna_updated_prop = self.sna_g108_xiangpiqiangdu
    prev_context = bpy.context.area.type
    bpy.context.area.type = 'VIEW_3D'
    bpy.ops.sna.my_generic_operator_8d1a0('INVOKE_DEFAULT', )
    bpy.context.area.type = prev_context


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_OT_R_C1Ed2(bpy.types.Operator):
    bl_idname = "sna.r_c1ed2"
    bl_label = "R开关"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_2'] = (not bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_2'])
        bpy.context.view_layer.objects.active.modifiers['顶点色分层'].show_in_editmode = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_G_7136A(bpy.types.Operator):
    bl_idname = "sna.g_7136a"
    bl_label = "G开关"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_3'] = (not bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_3'])
        bpy.context.view_layer.objects.active.modifiers['顶点色分层'].show_in_editmode = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_0EDCC(layout_function, ):
    box_AEE16 = layout_function.box()
    box_AEE16.alert = False
    box_AEE16.enabled = True
    box_AEE16.active = True
    box_AEE16.use_property_split = False
    box_AEE16.use_property_decorate = False
    box_AEE16.alignment = 'Expand'.upper()
    box_AEE16.scale_x = 1.0
    box_AEE16.scale_y = 1.0
    if not True: box_AEE16.operator_context = "EXEC_DEFAULT"
    split_3D437 = box_AEE16.split(factor=0.5, align=False)
    split_3D437.alert = False
    split_3D437.enabled = True
    split_3D437.active = True
    split_3D437.use_property_split = False
    split_3D437.use_property_decorate = False
    split_3D437.scale_x = 1.0
    split_3D437.scale_y = 1.5
    split_3D437.alignment = 'Expand'.upper()
    if not True: split_3D437.operator_context = "EXEC_DEFAULT"
    split_3D437.label(text='分层绘制', icon_value=string_to_icon('MOD_OPACITY'))
    split_3D437.label(text='当前绘制层： ' + bpy.context.active_object.data.color_attributes.active_color.name, icon_value=0)
    split_46FA3 = box_AEE16.split(factor=0.8500000238418579, align=False)
    split_46FA3.alert = False
    split_46FA3.enabled = True
    split_46FA3.active = True
    split_46FA3.use_property_split = False
    split_46FA3.use_property_decorate = False
    split_46FA3.scale_x = 1.0
    split_46FA3.scale_y = 1.0
    split_46FA3.alignment = 'Expand'.upper()
    if not True: split_46FA3.operator_context = "EXEC_DEFAULT"
    col_F7E0A = split_46FA3.column(heading='', align=False)
    col_F7E0A.alert = False
    col_F7E0A.enabled = True
    col_F7E0A.active = True
    col_F7E0A.use_property_split = False
    col_F7E0A.use_property_decorate = False
    col_F7E0A.scale_x = 1.0
    col_F7E0A.scale_y = 1.5
    col_F7E0A.alignment = 'Expand'.upper()
    col_F7E0A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_F7E0A.operator('sna.detail_67f26', text='Detail ', icon_value=0, emboss=True, depress=('R' == bpy.context.active_object.data.color_attributes.active_color.name))
    op = col_F7E0A.operator('sna.stain_1_63262', text='Stain_1', icon_value=0, emboss=True, depress=('G' == bpy.context.active_object.data.color_attributes.active_color.name))
    op = col_F7E0A.operator('sna.stain_2_d588c', text='Stain_2', icon_value=0, emboss=True, depress=('B' == bpy.context.active_object.data.color_attributes.active_color.name))
    op = col_F7E0A.operator('sna.alpha_90dd9', text='Alpha', icon_value=0, emboss=True, depress=('A' == bpy.context.active_object.data.color_attributes.active_color.name))
    col_80B2B = split_46FA3.column(heading='', align=False)
    col_80B2B.alert = False
    col_80B2B.enabled = True
    col_80B2B.active = True
    col_80B2B.use_property_split = False
    col_80B2B.use_property_decorate = False
    col_80B2B.scale_x = 1.0
    col_80B2B.scale_y = 1.5
    col_80B2B.alignment = 'Expand'.upper()
    col_80B2B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    if bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_2']:
        op = col_80B2B.operator('sna.r_c1ed2', text='', icon_value=string_to_icon('HIDE_OFF'), emboss=True, depress=False)
    else:
        op = col_80B2B.operator('sna.r_c1ed2', text='', icon_value=string_to_icon('HIDE_ON'), emboss=True, depress=False)
    if bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_3']:
        op = col_80B2B.operator('sna.g_7136a', text='', icon_value=string_to_icon('HIDE_OFF'), emboss=True, depress=False)
    else:
        op = col_80B2B.operator('sna.g_7136a', text='', icon_value=string_to_icon('HIDE_ON'), emboss=True, depress=False)
    if bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_4']:
        op = col_80B2B.operator('sna.b_a7338', text='', icon_value=string_to_icon('HIDE_OFF'), emboss=True, depress=False)
    else:
        op = col_80B2B.operator('sna.b_a7338', text='', icon_value=string_to_icon('HIDE_ON'), emboss=True, depress=False)
    if bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_5']:
        op = col_80B2B.operator('sna.a_5ad5a', text='', icon_value=string_to_icon('HIDE_OFF'), emboss=True, depress=False)
    else:
        op = col_80B2B.operator('sna.a_5ad5a', text='', icon_value=string_to_icon('HIDE_ON'), emboss=True, depress=False)


class SNA_OT_Detail_67F26(bpy.types.Operator):
    bl_idname = "sna.detail_67f26"
    bl_label = "Detail"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.active_object.data.color_attributes.active_color = bpy.context.active_object.data.color_attributes['R']
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Stain_1_63262(bpy.types.Operator):
    bl_idname = "sna.stain_1_63262"
    bl_label = "Stain_1"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.active_object.data.color_attributes.active_color = bpy.context.active_object.data.color_attributes['G']
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Stain_2_D588C(bpy.types.Operator):
    bl_idname = "sna.stain_2_d588c"
    bl_label = "Stain_2"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.active_object.data.color_attributes.active_color = bpy.context.active_object.data.color_attributes['B']
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_00097(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_00097"
    bl_label = "预览混合颜色"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.active_object.data.color_attributes.active_color = bpy.context.active_object.data.color_attributes['RGB']
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Alpha_90Dd9(bpy.types.Operator):
    bl_idname = "sna.alpha_90dd9"
    bl_label = "Alpha"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.active_object.data.color_attributes.active_color = bpy.context.active_object.data.color_attributes['A']
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_B_A7338(bpy.types.Operator):
    bl_idname = "sna.b_a7338"
    bl_label = "B开关"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_4'] = (not bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_4'])
        bpy.context.view_layer.objects.active.modifiers['顶点色分层'].show_in_editmode = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_A_5Ad5A(bpy.types.Operator):
    bl_idname = "sna.a_5ad5a"
    bl_label = "A开关"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_5'] = (not bpy.context.view_layer.objects.active.modifiers['顶点色分层']['Input_5'])
        bpy.context.view_layer.objects.active.modifiers['顶点色分层'].show_in_editmode = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_5Cf09(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_5cf09"
    bl_label = "橡皮赋值0"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.secondary_color = (0, 0, 0)
        bpy.ops.paint.brush_colors_flip('INVOKE_DEFAULT', )
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'VIEW_3D'
        bpy.ops.sna.my_generic_operator_8d1a0('INVOKE_DEFAULT', )
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_F250F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_f250f"
    bl_label = "重置画笔工具"
    bl_description = "重置笔刷配置"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        vertex_paint = bpy.context.scene.tool_settings.vertex_paint
        vertex_paint.unified_paint_settings.use_unified_size = True
        vertex_paint.unified_paint_settings.use_unified_strength = True
        vertex_paint.unified_paint_settings.use_unified_color = True
        vertex_paint.show_brush = True
        #vertex_paint.input_samples = 1
        
        brush = bpy.data.brushes["Paint Hard"]
        brush.blend = 'MIX'
        brush.use_alpha = False
        brush.use_accumulate = True
        brush.use_frontface = True
        brush.stroke_method = 'DOTS'        
        brush.curve_distance_falloff_preset = 'LIN'
        brush.falloff_shape = 'SPHERE'
        
        self.report({'INFO'}, message='成功重置画笔工具设置')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_8E271(layout_function, ):
    box_CB77D = layout_function.box()
    box_CB77D.alert = False
    box_CB77D.enabled = True
    box_CB77D.active = True
    box_CB77D.use_property_split = False
    box_CB77D.use_property_decorate = False
    box_CB77D.alignment = 'Expand'.upper()
    box_CB77D.scale_x = 1.0
    box_CB77D.scale_y = 1.0
    if not True: box_CB77D.operator_context = "EXEC_DEFAULT"
    col_FE691 = box_CB77D.column(heading='', align=False)
    col_FE691.alert = False
    col_FE691.enabled = True
    col_FE691.active = True
    col_FE691.use_property_split = False
    col_FE691.use_property_decorate = False
    col_FE691.scale_x = 1.0
    col_FE691.scale_y = 1.0
    col_FE691.alignment = 'Expand'.upper()
    col_FE691.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_FE691.label(text='绘制工具', icon_value=string_to_icon('BRUSH_DATA'))
    col_B748F = col_FE691.column(heading='', align=False)
    col_B748F.alert = False
    col_B748F.enabled = True
    col_B748F.active = True
    col_B748F.use_property_split = False
    col_B748F.use_property_decorate = False
    col_B748F.scale_x = 1.0
    col_B748F.scale_y = 2.0
    col_B748F.alignment = 'Expand'.upper()
    col_B748F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    if (not ((bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[0], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[1], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[2]) == (0.0, 0.0, 0.0))):
        op = col_B748F.operator('sna.my_generic_operator_5cf09', text='', icon_value=string_to_icon('GREASEPENCIL'), emboss=True, depress=False)
    else:
        op = col_B748F.operator('sna.my_generic_operator_acc41', text='', icon_value=string_to_icon('META_CAPSULE'), emboss=True, depress=False)
    split_09CED = col_FE691.split(factor=0.20000000298023224, align=True)
    split_09CED.alert = False
    split_09CED.enabled = ((not ((bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[0], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[1], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[2]) == (0.0, 0.0, 0.0))) or (((bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[0], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[1], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[2]) == (0.0, 0.0, 0.0)) and ((bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.secondary_color[0], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.secondary_color[1], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.secondary_color[2]) == (0.0, 0.0, 0.0))))
    split_09CED.active = True
    split_09CED.use_property_split = False
    split_09CED.use_property_decorate = False
    split_09CED.scale_x = 1.0
    split_09CED.scale_y = 1.0
    split_09CED.alignment = 'Expand'.upper()
    if not True: split_09CED.operator_context = "EXEC_DEFAULT"
    split_09CED.label(text='颜色:', icon_value=0)
    split_09CED.prop(bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings, 'color', text='', icon_value=0, emboss=True)
    if (not ((bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[0], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[1], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[2]) == (0.0, 0.0, 0.0))):
        col_D15AA = col_FE691.column(heading='', align=False)
        col_D15AA.alert = False
        col_D15AA.enabled = True
        col_D15AA.active = True
        col_D15AA.use_property_split = False
        col_D15AA.use_property_decorate = False
        col_D15AA.scale_x = 1.0
        col_D15AA.scale_y = 1.0
        col_D15AA.alignment = 'Expand'.upper()
        col_D15AA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_11E2D = col_D15AA.split(factor=0.20000000298023224, align=True)
        split_11E2D.alert = False
        split_11E2D.enabled = True
        split_11E2D.active = True
        split_11E2D.use_property_split = False
        split_11E2D.use_property_decorate = False
        split_11E2D.scale_x = 1.0
        split_11E2D.scale_y = 1.0
        split_11E2D.alignment = 'Expand'.upper()
        if not True: split_11E2D.operator_context = "EXEC_DEFAULT"
        split_11E2D.label(text='画笔强度:', icon_value=0)
        split_11E2D.prop(bpy.context.scene, 'sna_g108_penqiangdu', text='', icon_value=0, emboss=True, slider=True)
        split_B3739 = col_D15AA.split(factor=0.20000000298023224, align=False)
        split_B3739.alert = False
        split_B3739.enabled = True
        split_B3739.active = True
        split_B3739.use_property_split = False
        split_B3739.use_property_decorate = False
        split_B3739.scale_x = 1.0
        split_B3739.scale_y = 1.0
        split_B3739.alignment = 'Expand'.upper()
        if not True: split_B3739.operator_context = "EXEC_DEFAULT"
        split_B3739.label(text='画笔流量:', icon_value=0)
        split_B3739.prop(bpy.context.scene, 'sna_g108_penyagan', text='', icon_value=0, emboss=True, slider=True)
    else:
        col_9E39A = col_FE691.column(heading='', align=False)
        col_9E39A.alert = False
        col_9E39A.enabled = True
        col_9E39A.active = True
        col_9E39A.use_property_split = False
        col_9E39A.use_property_decorate = False
        col_9E39A.scale_x = 1.0
        col_9E39A.scale_y = 1.0
        col_9E39A.alignment = 'Expand'.upper()
        col_9E39A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_AEBC3 = col_9E39A.split(factor=0.20000000298023224, align=True)
        split_AEBC3.alert = False
        split_AEBC3.enabled = True
        split_AEBC3.active = True
        split_AEBC3.use_property_split = False
        split_AEBC3.use_property_decorate = False
        split_AEBC3.scale_x = 1.0
        split_AEBC3.scale_y = 1.0
        split_AEBC3.alignment = 'Expand'.upper()
        if not True: split_AEBC3.operator_context = "EXEC_DEFAULT"
        split_AEBC3.label(text='橡皮强度:', icon_value=0)
        split_AEBC3.prop(bpy.context.scene, 'sna_g108_xiangpiqiangdu', text='', icon_value=0, emboss=True, slider=True)
        split_84678 = col_9E39A.split(factor=0.20000000298023224, align=False)
        split_84678.alert = False
        split_84678.enabled = True
        split_84678.active = True
        split_84678.use_property_split = False
        split_84678.use_property_decorate = False
        split_84678.scale_x = 1.0
        split_84678.scale_y = 1.0
        split_84678.alignment = 'Expand'.upper()
        if not True: split_84678.operator_context = "EXEC_DEFAULT"
        split_84678.label(text='橡皮流量:', icon_value=0)
        split_84678.prop(bpy.context.scene, 'sna_g108_xiangpiyagan', text='', icon_value=0, emboss=True, slider=True)
    split_D1832 = col_FE691.split(factor=0.20000000298023224, align=True)
    split_D1832.alert = False
    split_D1832.enabled = True
    split_D1832.active = True
    split_D1832.use_property_split = False
    split_D1832.use_property_decorate = False
    split_D1832.scale_x = 1.0
    split_D1832.scale_y = 1.0
    split_D1832.alignment = 'Expand'.upper()
    if not True: split_D1832.operator_context = "EXEC_DEFAULT"
    split_D1832.label(text='大小:', icon_value=0)
    split_D1832.prop(bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings, 'size', text='', icon_value=0, emboss=True)


class SNA_OT_My_Generic_Operator_8D1A0(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_8d1a0"
    bl_label = "压感模拟"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.strength = (float(bpy.context.scene.sna_g108_penqiangdu * bpy.context.scene.sna_g108_penyagan) if (not ((bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[0], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[1], bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color[2]) == (0.0, 0.0, 0.0))) else float(bpy.context.scene.sna_g108_xiangpiqiangdu * bpy.context.scene.sna_g108_xiangpiyagan))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Acc41(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_acc41"
    bl_label = "切换至画笔"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        bpy.ops.paint.brush_colors_flip('INVOKE_DEFAULT', )
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'VIEW_3D'
        bpy.ops.sna.my_generic_operator_8d1a0('INVOKE_DEFAULT', )
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_layered_painting_A6C01(bpy.types.Panel):
    bl_label = '分层绘制5.0'
    bl_idname = 'SNA_PT_layered_painting_A6C01'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'G108'
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        if property_exists("bpy.context.active_object.data.vertices", globals(), locals()):
            col_88942 = layout.column(heading='', align=False)
            col_88942.alert = False
            col_88942.enabled = True
            col_88942.active = True
            col_88942.use_property_split = False
            col_88942.use_property_decorate = False
            col_88942.scale_x = 1.0
            col_88942.scale_y = 1.0
            col_88942.alignment = 'Expand'.upper()
            col_88942.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            split_7B902 = col_88942.split(factor=0.30000001192092896, align=True)
            split_7B902.alert = False
            split_7B902.enabled = True
            split_7B902.active = True
            split_7B902.use_property_split = False
            split_7B902.use_property_decorate = False
            split_7B902.scale_x = 1.0
            split_7B902.scale_y = 2.0
            split_7B902.alignment = 'Expand'.upper()
            if not True: split_7B902.operator_context = "EXEC_DEFAULT"
            if node_tree_001['sna_xiankuangkaiguan']:
                op = split_7B902.operator('sna.my_generic_operator_3277d', text='', icon_value=string_to_icon('MOD_MULTIRES'), emboss=True, depress=False)
                op.sna_new_property = False
                op.sna_new_property_001 = 1.0
            else:
                op = split_7B902.operator('sna.my_generic_operator_3277d', text='', icon_value=string_to_icon('MOD_MULTIRES'), emboss=True, depress=False)
                op.sna_new_property = True
                op.sna_new_property_001 = 1.0
            col_A0B5A = split_7B902.column(heading='', align=True)
            col_A0B5A.alert = False
            col_A0B5A.enabled = (len(list(bpy.context.active_object.data.color_attributes)) != 0)
            col_A0B5A.active = True
            col_A0B5A.use_property_split = False
            col_A0B5A.use_property_decorate = False
            col_A0B5A.scale_x = 1.0
            col_A0B5A.scale_y = 1.0
            col_A0B5A.alignment = 'Expand'.upper()
            col_A0B5A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_A0B5A.operator('object.mode_set', text='模式切换', icon_value=0, emboss=True, depress=False)
            op.mode = 'VERTEX_PAINT'
            op.toggle = True
            if ((len(list(bpy.context.active_object.data.color_attributes)) == 5) and property_exists("bpy.context.active_object.data.color_attributes['R']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['G']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['B']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['A']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['RGB']", globals(), locals())):
                col_5D108 = col_88942.column(heading='', align=False)
                col_5D108.alert = False
                col_5D108.enabled = True
                col_5D108.active = True
                col_5D108.use_property_split = False
                col_5D108.use_property_decorate = False
                col_5D108.scale_x = 1.0
                col_5D108.scale_y = 1.0
                col_5D108.alignment = 'Expand'.upper()
                col_5D108.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                layout_function = col_5D108
                sna_func_0EDCC(layout_function, )
                layout_function = col_5D108
                sna_func_8E271(layout_function, )
            col_49F9B = col_88942.column(heading='', align=False)
            col_49F9B.alert = False
            col_49F9B.enabled = True
            col_49F9B.active = True
            col_49F9B.use_property_split = False
            col_49F9B.use_property_decorate = False
            col_49F9B.scale_x = 1.0
            col_49F9B.scale_y = 1.5
            col_49F9B.alignment = 'Expand'.upper()
            col_49F9B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if ((len(list(bpy.context.active_object.data.color_attributes)) == 5) and property_exists("bpy.context.active_object.data.color_attributes['R']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['G']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['B']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['A']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['RGB']", globals(), locals())):
                op = col_49F9B.operator('sna.my_generic_operator_127de', text='应用绘制', icon_value=0, emboss=True, depress=False)
            else:
                col_AAF03 = col_49F9B.column(heading='', align=False)
                col_AAF03.alert = (False if ((len(list(bpy.context.active_object.data.color_attributes)) == 1) or (len(list(bpy.context.active_object.data.color_attributes)) == 0)) else True)
                col_AAF03.enabled = ((len(list(bpy.context.active_object.data.color_attributes)) == 1) or (len(list(bpy.context.active_object.data.color_attributes)) == 0))
                col_AAF03.active = True
                col_AAF03.use_property_split = False
                col_AAF03.use_property_decorate = False
                col_AAF03.scale_x = 1.0
                col_AAF03.scale_y = 1.0
                col_AAF03.alignment = 'Expand'.upper()
                col_AAF03.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_AAF03.operator('sna.my_generic_operator_75942', text='顶点分层绘制', icon_value=string_to_icon('XRAY'), emboss=True, depress=False)
        else:
            layout.label(text='请选中实体模型', icon_value=string_to_icon('RECORD_ON'))


class SNA_OT_My_Generic_Operator_0F69E(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_0f69e"
    bl_label = "清理修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_667CE in range(len(bpy.context.active_object.modifiers)):
            for i_53226 in range(len(bpy.context.active_object.modifiers)):
                if '顶点色分层' in str(bpy.context.active_object.modifiers[i_53226]):
                    bpy.context.active_object.modifiers.remove(modifier=bpy.context.active_object.modifiers[i_53226], )
                    break
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_3277D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3277d"
    bl_label = "线框开关"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.BoolProperty(name='开关', description='', options={'HIDDEN'}, default=False)
    sna_new_property_001: bpy.props.FloatProperty(name='值', description='', default=0.0, subtype='NONE', unit='NONE', step=1, precision=2)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        node_tree_001['sna_xiankuangkaiguan'] = self.sna_new_property
        a = self.sna_new_property
        b = self.sna_new_property_001
        bpy.context.space_data.overlay.show_wireframes = a
        bpy.context.space_data.overlay.wireframe_opacity = b
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_D6Ba6(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d6ba6"
    bl_label = "增加修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        if property_exists("bpy.data.node_groups['顶点色分层']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=os.path.join(os.path.dirname(__file__), 'assets', '顶点色分层_节点组.blend') + r'\NodeTree', filename='顶点色分层', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_59FEE = None if not new_data else new_data[0]
        modifier_D4DC0 = bpy.context.active_object.modifiers.new(name='顶点色分层', type='NODES', )
        modifier_D4DC0.node_group = bpy.data.node_groups['顶点色分层']
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_75942(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_75942"
    bl_label = "创建分层绘制"
    bl_description = "红色状态时请检查顶点色层数"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        if (len(list(bpy.context.active_object.data.color_attributes)) == 0):
            bpy.ops.geometry.color_attribute_add(name="R", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.geometry.color_attribute_add(name="G", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.geometry.color_attribute_add(name="B", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.geometry.color_attribute_add(name="A", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.geometry.color_attribute_add(name="RGB", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.sna.my_generic_operator_0f69e()
            bpy.ops.sna.my_generic_operator_d6ba6()
            bpy.context.active_object.data.attributes.active_color_index = 0
            bpy.ops.sna.my_generic_operator_f250f('INVOKE_DEFAULT', )
            bpy.ops.object.mode_set(mode='VERTEX_PAINT')
            bpy.ops.geometry.color_attribute_render_set(name='RGB')
            self.report({'INFO'}, message='成功新建顶点色层')
        if (len(list(bpy.context.active_object.data.color_attributes)) == 1):
            bpy.context.active_object.data.color_attributes[0].name = 'RGBtest'
            bpy.ops.geometry.color_attribute_add(name="R", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.geometry.color_attribute_add(name="G", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.geometry.color_attribute_add(name="B", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.geometry.color_attribute_add(name="A", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            bpy.ops.geometry.color_attribute_add(name="RGB", domain='CORNER', data_type='BYTE_COLOR', color=(0, 0, 0, 0))
            for i_180AD in range(len(bpy.context.active_object.data.color_attributes[0].data)):
                if (bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[0] != 0.0):
                    bpy.context.active_object.data.color_attributes['R'].data[i_180AD].color = (bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[0], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[0], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[0], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[0])
                if (bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[1] != 0.0):
                    bpy.context.active_object.data.color_attributes['G'].data[i_180AD].color = (bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[1], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[1], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[1], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[1])
                if (bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[2] != 0.0):
                    bpy.context.active_object.data.color_attributes['B'].data[i_180AD].color = (bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[2], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[2], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[2], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[2])
                if (bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[3] != 0.0):
                    bpy.context.active_object.data.color_attributes['A'].data[i_180AD].color = (bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[3], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[3], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[3], bpy.context.active_object.data.color_attributes[0].data[i_180AD].color[3])
            bpy.context.active_object.data.vertex_colors.remove(layer=bpy.context.active_object.data.vertex_colors['RGBtest'], )
            bpy.ops.sna.my_generic_operator_0f69e('INVOKE_DEFAULT', )
            bpy.ops.sna.my_generic_operator_d6ba6('INVOKE_DEFAULT', )
            bpy.context.active_object.data.attributes.active_color_index = 0
            bpy.ops.sna.my_generic_operator_f250f('INVOKE_DEFAULT', )
            bpy.ops.geometry.color_attribute_render_set(name='RGB')
            self.report({'INFO'}, message='成功拆分并新建顶点色层')
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_127De(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_127de"
    bl_label = "应用绘制"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        if ((len(list(bpy.context.active_object.data.color_attributes)) == 5) and property_exists("bpy.context.active_object.data.color_attributes['R']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['G']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['B']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['A']", globals(), locals()) and property_exists("bpy.context.active_object.data.color_attributes['RGB']", globals(), locals())):
            for i_70E8A in range(len(bpy.context.active_object.data.color_attributes['RGB'].data)):
                if ((bpy.context.active_object.data.color_attributes['R'].data[i_70E8A].color[0], bpy.context.active_object.data.color_attributes['G'].data[i_70E8A].color[1], bpy.context.active_object.data.color_attributes['B'].data[i_70E8A].color[2], bpy.context.active_object.data.color_attributes['A'].data[i_70E8A].color[0]) == (0.0, 0.0, 0.0, 1.0)):
                    pass
                else:
                    bpy.context.active_object.data.color_attributes['RGB'].data[i_70E8A].color = (bpy.context.active_object.data.color_attributes['R'].data[i_70E8A].color[0], bpy.context.active_object.data.color_attributes['G'].data[i_70E8A].color[1], bpy.context.active_object.data.color_attributes['B'].data[i_70E8A].color[2], bpy.context.active_object.data.color_attributes['A'].data[i_70E8A].color[0])
            bpy.context.active_object.data.vertex_colors.remove(layer=bpy.context.active_object.data.vertex_colors['B'], )
            bpy.context.active_object.data.vertex_colors.remove(layer=bpy.context.active_object.data.vertex_colors['G'], )
            bpy.context.active_object.data.vertex_colors.remove(layer=bpy.context.active_object.data.vertex_colors['R'], )
            bpy.context.active_object.data.vertex_colors.remove(layer=bpy.context.active_object.data.vertex_colors['A'], )
            bpy.ops.sna.my_generic_operator_0f69e('INVOKE_DEFAULT', )
            self.report({'INFO'}, message='成功应用顶点色层')
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_70C14(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_70c14"
    bl_label = "批量烘焙"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        for i_F754A in range(len(bpy.context.view_layer.objects.selected)):
            if ('_lod0' in bpy.context.view_layer.objects.selected[i_F754A].name[-5:] and (1 == len(list(bpy.context.view_layer.objects.selected[i_F754A].data.color_attributes)))):
                bpy.context.view_layer.objects.selected[i_F754A].data.color_attributes[0].name = 'RGB'
                attribute_BBC1B = bpy.context.view_layer.objects.selected[i_F754A].data.color_attributes.new(name='传递顶点色', type='FLOAT_COLOR', domain='CORNER', )
                for i_B062B in range(len(attribute_BBC1B.data)):
                    bpy.context.view_layer.objects.selected[i_F754A].data.color_attributes['传递顶点色'].data[i_B062B].color = bpy.context.view_layer.objects.selected[i_F754A].data.color_attributes['RGB'].data[i_B062B].color
                for i_426EF in range(len([bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'])):
                    if property_exists("bpy.data.objects[[bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'][i_426EF]]", globals(), locals()):
                        if ([bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'][i_426EF][-5:] in str((bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1' if bpy.context.scene.sna_g108_bakelod1 else '_无_')) or [bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'][i_426EF][-5:] in str((bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2' if bpy.context.scene.sna_g108_bakelod2 else '_无_')) or [bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'][i_426EF][-5:] in str((bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3' if bpy.context.scene.sna_g108_bakelod3 else '_无_'))):
                            modifier_06D8B = bpy.context.blend_data.objects[[bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'][i_426EF]].modifiers.new(name='顶点色传递', type='DATA_TRANSFER', )
                            modifier_06D8B.object = bpy.context.view_layer.objects.selected[i_F754A]
                            modifier_06D8B.use_loop_data = True
                            modifier_06D8B.data_types_loops = set(['COLOR_CORNER'])
                            bpy.context.view_layer.objects.active = bpy.data.objects[[bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'][i_426EF]]
                            modifier_06D8B.use_object_transform = False
                            node_tree['sna_dingdseshul'] = len(list(bpy.context.view_layer.objects.active.data.color_attributes))
                            for i_37FDA in range(node_tree['sna_dingdseshul']):
                                bpy.context.view_layer.objects.active.data.color_attributes.remove(attribute=bpy.context.view_layer.objects.active.data.color_attributes[0], )
                            bpy.ops.object.datalayout_transfer(modifier="顶点色传递")
                            bpy.ops.object.modifier_apply(modifier="顶点色传递")
                            for i_1EE5D in range(len(bpy.data.objects[[bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'][i_426EF]].data.color_attributes['RGB'].data)):
                                bpy.context.active_object.data.color_attributes['RGB'].data[i_1EE5D].color = bpy.context.active_object.data.color_attributes['传递顶点色'].data[i_1EE5D].color
                                bpy.data.objects[[bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '1', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '2', bpy.context.view_layer.objects.selected[i_F754A].name[:-1] + '3'][i_426EF]].data.color_attributes.default_color_name = 'RGB'
                            bpy.context.active_object.data.color_attributes.remove(attribute=bpy.context.active_object.data.color_attributes['传递顶点色'], )
                bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_F754A]
                bpy.context.active_object.data.color_attributes.remove(attribute=bpy.context.active_object.data.color_attributes['传递顶点色'], )
                self.report({'INFO'}, message='烘焙成功：' + bpy.context.view_layer.objects.selected[i_F754A].name[:-5])
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_PT_vertex_color_baking_53741(bpy.types.Panel):
    bl_label = '批量顶点色烘焙'
    bl_idname = 'SNA_PT_vertex_color_baking_53741'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_layered_painting_A6C01'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_ECA8A = layout.column(heading='', align=True)
        col_ECA8A.alert = False
        col_ECA8A.enabled = True
        col_ECA8A.active = True
        col_ECA8A.use_property_split = False
        col_ECA8A.use_property_decorate = False
        col_ECA8A.scale_x = 1.0
        col_ECA8A.scale_y = 1.0
        col_ECA8A.alignment = 'Expand'.upper()
        col_ECA8A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_44FE3 = col_ECA8A.column(heading='', align=True)
        col_44FE3.alert = False
        col_44FE3.enabled = True
        col_44FE3.active = True
        col_44FE3.use_property_split = False
        col_44FE3.use_property_decorate = False
        col_44FE3.scale_x = 1.0
        col_44FE3.scale_y = 1.0
        col_44FE3.alignment = 'Expand'.upper()
        col_44FE3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_A3308 = col_44FE3.column(heading='', align=True)
        col_A3308.alert = False
        col_A3308.enabled = True
        col_A3308.active = True
        col_A3308.use_property_split = False
        col_A3308.use_property_decorate = False
        col_A3308.scale_x = 1.0
        col_A3308.scale_y = 2.0
        col_A3308.alignment = 'Expand'.upper()
        col_A3308.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_A3308.operator('sna.my_generic_operator_70c14', text='一键烘焙', icon_value=0, emboss=True, depress=False)
        row_1324A = col_44FE3.row(heading='', align=True)
        row_1324A.alert = False
        row_1324A.enabled = True
        row_1324A.active = True
        row_1324A.use_property_split = False
        row_1324A.use_property_decorate = False
        row_1324A.scale_x = 1.0
        row_1324A.scale_y = 1.2000000476837158
        row_1324A.alignment = 'Expand'.upper()
        row_1324A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_1324A.prop(bpy.context.scene, 'sna_g108_bakelod1', text='Lod1', icon_value=0, emboss=True)
        row_1324A.prop(bpy.context.scene, 'sna_g108_bakelod2', text='Lod2', icon_value=0, emboss=True)
        row_1324A.prop(bpy.context.scene, 'sna_g108_bakelod3', text='Lod3', icon_value=0, emboss=True)
        col_ECA8A.label(text='选择的资产：', icon_value=0)
        for i_F4D73 in range(len(bpy.context.view_layer.objects.selected)):
            box_9830B = col_ECA8A.box()
            box_9830B.alert = False
            box_9830B.enabled = True
            box_9830B.active = True
            box_9830B.use_property_split = False
            box_9830B.use_property_decorate = False
            box_9830B.alignment = 'Expand'.upper()
            box_9830B.scale_x = 1.0
            box_9830B.scale_y = 1.0
            if not True: box_9830B.operator_context = "EXEC_DEFAULT"
            col_B75E2 = box_9830B.column(heading='', align=True)
            col_B75E2.alert = False
            col_B75E2.enabled = True
            col_B75E2.active = True
            col_B75E2.use_property_split = False
            col_B75E2.use_property_decorate = False
            col_B75E2.scale_x = 1.0
            col_B75E2.scale_y = 1.0
            col_B75E2.alignment = 'Expand'.upper()
            col_B75E2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            row_3E49D = col_B75E2.row(heading='', align=True)
            row_3E49D.alert = (not '_lod0' in bpy.context.view_layer.objects.selected[i_F4D73].name[-5:])
            row_3E49D.enabled = True
            row_3E49D.active = True
            row_3E49D.use_property_split = False
            row_3E49D.use_property_decorate = False
            row_3E49D.scale_x = 1.0
            row_3E49D.scale_y = 1.0
            row_3E49D.alignment = 'Expand'.upper()
            row_3E49D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            row_3E49D.label(text=bpy.context.view_layer.objects.selected[i_F4D73].name, icon_value=string_to_icon('OUTLINER_OB_MESH'))
            if '_lod0' in bpy.context.view_layer.objects.selected[i_F4D73].name[-5:]:
                row_608A7 = row_3E49D.row(heading='', align=True)
                row_608A7.alert = (not (1 == len(list(bpy.context.view_layer.objects.selected[i_F4D73].data.color_attributes))))
                row_608A7.enabled = True
                row_608A7.active = True
                row_608A7.use_property_split = False
                row_608A7.use_property_decorate = False
                row_608A7.scale_x = 1.0
                row_608A7.scale_y = 1.0
                row_608A7.alignment = 'Expand'.upper()
                row_608A7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                if (not (1 == len(list(bpy.context.view_layer.objects.selected[i_F4D73].data.color_attributes)))):
                    row_608A7.label(text='颜色属性异常=' + str(len(list(bpy.context.view_layer.objects.selected[i_F4D73].data.color_attributes))), icon_value=0)
            if '_lod0' in bpy.context.view_layer.objects.selected[i_F4D73].name[-5:]:
                row_E55C1 = col_B75E2.row(heading='', align=False)
                row_E55C1.alert = False
                row_E55C1.enabled = True
                row_E55C1.active = True
                row_E55C1.use_property_split = False
                row_E55C1.use_property_decorate = False
                row_E55C1.scale_x = 1.0
                row_E55C1.scale_y = 1.0
                row_E55C1.alignment = 'Expand'.upper()
                row_E55C1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                for i_C8D17 in range(3):
                    col_A9B1E = row_E55C1.column(heading='', align=True)
                    col_A9B1E.alert = (not property_exists("bpy.data.objects[bpy.context.view_layer.objects.selected[i_F4D73].name[:-1] + str(int(i_C8D17 + 1.0))]", globals(), locals()))
                    col_A9B1E.enabled = True
                    col_A9B1E.active = True
                    col_A9B1E.use_property_split = False
                    col_A9B1E.use_property_decorate = False
                    col_A9B1E.scale_x = 1.0
                    col_A9B1E.scale_y = 1.0
                    col_A9B1E.alignment = 'Expand'.upper()
                    col_A9B1E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    col_A9B1E.label(text=bpy.context.view_layer.objects.selected[i_F4D73].name[:-1] + str(int(i_C8D17 + 1.0)), icon_value=string_to_icon('LAYER_ACTIVE'))


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_g108_penyagan = bpy.props.FloatProperty(name='G108_penyagan', description='', default=0.20000000298023224, subtype='NONE', unit='NONE', min=0.0, max=1.0, step=1, precision=2, update=sna_update_sna_g108_penyagan_A830B)
    bpy.types.Scene.sna_g108_penqiangdu = bpy.props.FloatProperty(name='G108_penqiangdu', description='', default=1.0, subtype='NONE', unit='NONE', min=0.0, max=1.0, step=1, precision=2, update=sna_update_sna_g108_penqiangdu_2D7A4)
    bpy.types.Scene.sna_g108_xiangpiqiangdu = bpy.props.FloatProperty(name='G108_xiangpiqiangdu', description='', default=1.0, subtype='NONE', unit='NONE', min=0.0, max=1.0, step=1, precision=2, update=sna_update_sna_g108_xiangpiqiangdu_A37FA)
    bpy.types.Scene.sna_g108_xiangpiyagan = bpy.props.FloatProperty(name='G108_xiangpiyagan', description='', default=1.0, subtype='NONE', unit='NONE', min=0.0, max=1.0, step=1, precision=2, update=sna_update_sna_g108_xiangpiyagan_BB917)
    bpy.types.Scene.sna_g108_bakelod1 = bpy.props.BoolProperty(name='G108_bakelod1', description='', default=False)
    bpy.types.Scene.sna_g108_bakelod2 = bpy.props.BoolProperty(name='G108_bakelod2', description='', default=False)
    bpy.types.Scene.sna_g108_bakelod3 = bpy.props.BoolProperty(name='G108_bakelod3', description='', default=False)
    bpy.utils.register_class(SNA_OT_R_C1Ed2)
    bpy.utils.register_class(SNA_OT_G_7136A)
    bpy.utils.register_class(SNA_OT_Detail_67F26)
    bpy.utils.register_class(SNA_OT_Stain_1_63262)
    bpy.utils.register_class(SNA_OT_Stain_2_D588C)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_00097)
    bpy.utils.register_class(SNA_OT_Alpha_90Dd9)
    bpy.utils.register_class(SNA_OT_B_A7338)
    bpy.utils.register_class(SNA_OT_A_5Ad5A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_5Cf09)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_F250F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_8D1A0)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Acc41)
    bpy.utils.register_class(SNA_PT_layered_painting_A6C01)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_0F69E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3277D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D6Ba6)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_75942)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_127De)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_70C14)
    bpy.utils.register_class(SNA_PT_vertex_color_baking_53741)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_panel', 'B', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_PT_layered_painting_A6C01'
    kmi.properties.keep_open = True
    addon_keymaps['1D4E3'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_g108_bakelod3
    del bpy.types.Scene.sna_g108_bakelod2
    del bpy.types.Scene.sna_g108_bakelod1
    del bpy.types.Scene.sna_g108_xiangpiyagan
    del bpy.types.Scene.sna_g108_xiangpiqiangdu
    del bpy.types.Scene.sna_g108_penqiangdu
    del bpy.types.Scene.sna_g108_penyagan
    bpy.utils.unregister_class(SNA_OT_R_C1Ed2)
    bpy.utils.unregister_class(SNA_OT_G_7136A)
    bpy.utils.unregister_class(SNA_OT_Detail_67F26)
    bpy.utils.unregister_class(SNA_OT_Stain_1_63262)
    bpy.utils.unregister_class(SNA_OT_Stain_2_D588C)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_00097)
    bpy.utils.unregister_class(SNA_OT_Alpha_90Dd9)
    bpy.utils.unregister_class(SNA_OT_B_A7338)
    bpy.utils.unregister_class(SNA_OT_A_5Ad5A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_5Cf09)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_F250F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_8D1A0)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Acc41)
    bpy.utils.unregister_class(SNA_PT_layered_painting_A6C01)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_0F69E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3277D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D6Ba6)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_75942)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_127De)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_70C14)
    bpy.utils.unregister_class(SNA_PT_vertex_color_baking_53741)
