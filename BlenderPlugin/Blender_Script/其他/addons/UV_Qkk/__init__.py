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
    "name" : "UV_qkk",
    "author" : "QKK", 
    "description" : "qkkUV工具",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "UV" 
}


import bpy
import bpy.utils.previews
import math
import blf
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
ui = {'sna_isolate_selection': True, }
uv_004 = {'sna_draw_mode_uv': 'NONE', 'sna_draw_mode_3d': 'NONE', }
node_tree = {'sna_keyboard_shortcuts_explanation': False, }


def sna_update_sna_uv_precision_size_DD959(self, context):
    sna_updated_prop = self.sna_uv_precision_size
    bpy.context.scene.univ_settings.size_x = bpy.context.scene.sna_uv_precision_size
    bpy.context.scene.univ_settings.size_y = bpy.context.scene.sna_uv_precision_size


handler_0C8CE = []


def load_preview_icon(path):
    global _icons
    if not path in _icons:
        if os.path.exists(path):
            _icons.load(path, path, "IMAGE")
        else:
            return 0
    return _icons[path].icon_id


class SNA_PT_QKK_UV_37C20(bpy.types.Panel):
    bl_label = 'QKK_UV'
    bl_idname = 'SNA_PT_QKK_UV_37C20'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'UniV'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        split_907CB = layout.split(factor=0.5, align=True)
        split_907CB.alert = False
        split_907CB.enabled = 'EDIT_MESH'==bpy.context.mode
        split_907CB.active = True
        split_907CB.use_property_split = False
        split_907CB.use_property_decorate = False
        split_907CB.scale_x = 1.0
        split_907CB.scale_y = 1.2000000476837158
        split_907CB.alignment = 'Expand'.upper()
        if not True: split_907CB.operator_context = "EXEC_DEFAULT"
        op = split_907CB.operator('sna.my_generic_operator_0475f', text='独显', icon_value=0, emboss=True, depress=False)
        split_B5205 = split_907CB.split(factor=0.5, align=True)
        split_B5205.alert = False
        split_B5205.enabled = True
        split_B5205.active = True
        split_B5205.use_property_split = False
        split_B5205.use_property_decorate = False
        split_B5205.scale_x = 1.0
        split_B5205.scale_y = 1.0
        split_B5205.alignment = 'Expand'.upper()
        if not True: split_B5205.operator_context = "EXEC_DEFAULT"
        op = split_B5205.operator('sna.uv_36619', text='', icon_value=string_to_icon('TEXTURE_DATA'), emboss=True, depress=(not bpy.context.scene.tool_settings.use_uv_select_sync))
        op.sna_model = False
        op = split_B5205.operator('sna.uv_36619', text='', icon_value=string_to_icon('MESH_CUBE'), emboss=True, depress=bpy.context.scene.tool_settings.use_uv_select_sync)
        op.sna_model = True


class SNA_OT_My_Generic_Operator_Aa4B9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_aa4b9"
    bl_label = "更新缝合边"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.mark_seam(clear=True)
        bpy.ops.uv.univ_select_border(mode='SELECT', border_mode='BORDER')
        bpy.ops.uv.mark_seam(clear=False)
        bpy.ops.uv.select_all(action='DESELECT')
        bpy.ops.wm.context_set_enum(data_path='scene.zen_uv.ui.draw_mode_UV', value='SEAMS')
        uv_004['sna_draw_mode_uv'] = 'SEAMS'
        self.report({'INFO'}, message='更新缝合边成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_AddonPreferences_7C44E(bpy.types.AddonPreferences):
    bl_idname = __package__

    def sna_units_enum_items(self, context):
        return [("No Items", "No Items", "No generate enum items node found to create items!", "ERROR", 0)]
    sna_units: bpy.props.EnumProperty(name='Units', description='', options={'HIDDEN'}, items=[('m', 'm', 'px / m', 0, 0), ('cm', 'cm', 'px / cm', 0, 1)])
    sna_pixel: bpy.props.FloatProperty(name='Pixel', description='', options={'HIDDEN'}, default=0.0, subtype='PIXEL', unit='NONE', step=1, precision=2)

    def draw(self, context):
        if not (True):
            layout = self.layout 


def sna_add_to_view3d_ht_tool_header_E8E60(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('wm.univ_split_uv_toggle', text='', icon_value=string_to_icon('MESH_GRID'), emboss=True, depress=False)
        op.mode = 'SPLIT'


class SNA_OT_Uv_36619(bpy.types.Operator):
    bl_idname = "sna.uv_36619"
    bl_label = "设置UV模式"
    bl_description = "设置UV模式"
    bl_options = {"REGISTER", "UNDO"}
    sna_model: bpy.props.BoolProperty(name='model', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.scene.tool_settings.use_uv_select_sync = self.sna_model
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_0475F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_0475f"
    bl_label = "独显隐藏"
    bl_description = "独显隐藏"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if ui['sna_isolate_selection']:
            bpy.ops.uv.hide(unselected=True)
            ui['sna_isolate_selection'] = False
        else:
            bpy.ops.uv.reveal(select=False)
            ui['sna_isolate_selection'] = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_E955E(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e955e"
    bl_label = "缝合"
    bl_description = "快捷键  X、I"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.uv.univ_weld(distance=0.0)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_4609D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_4609d"
    bl_label = "标记缝合边"
    bl_description = "快捷键   C"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'IMAGE_EDITOR'
        bpy.ops.uv.univ_cut('INVOKE_DEFAULT', unwrap='NONE')
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_02E18(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_02e18"
    bl_label = "基于法线创建"
    bl_description = "基于法线创建"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.uv.hide(unselected=True)
        bpy.ops.mesh.univ_normal(crop=True, mark_seam=True)
        if ui['sna_isolate_selection']:
            bpy.ops.uv.reveal(select=False)
        bpy.ops.uv.univ_adjust_td(invert=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_34Cdd(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_34cdd"
    bl_label = "旋转"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_direction_of_rotation: bpy.props.StringProperty(name='Direction of rotation', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.uv.univ_rotate(mode=('DEFAULT' if bpy.context.scene.sna_uv_rotation_mode else 'INDIVIDUAL'), rot_dir=self.sna_direction_of_rotation, user_angle=math.radians(bpy.context.scene.sna_uv_rotation_angle), use_correct_aspect=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_94Eb3(bpy.types.Operator):
    bl_idname = "sna.uv_94eb3"
    bl_label = "uv移动"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_move: bpy.props.FloatVectorProperty(name='move', description='', options={'HIDDEN'}, size=2, default=(0.0, 0.0), subtype='NONE', unit='NONE', step=3, precision=6)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.transform.translate(value=(self.sna_move[0], self.sna_move[1], 0.0))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_E4775(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e4775"
    bl_label = "移动设置"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_UV_MOVE_SIZE_D3E66", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_UV_MOVE_SIZE_D3E66(bpy.types.Panel):
    bl_label = 'uv_move_size'
    bl_idname = 'SNA_PT_UV_MOVE_SIZE_D3E66'
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
        layout.label(text='移动单位大小', icon_value=0)
        layout.prop(bpy.context.scene, 'sna_uv_move_size', text='', icon_value=0, emboss=True)


class SNA_OT_Uv__Ca81B(bpy.types.Operator):
    bl_idname = "sna.uv__ca81b"
    bl_label = "uv_对齐"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_direction: bpy.props.StringProperty(name='direction', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.uv.univ_align(mode='ALIGN', direction=self.sna_direction)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv__783Fd(bpy.types.Operator):
    bl_idname = "sna.uv__783fd"
    bl_label = "uv_缩放"
    bl_description = "缩放UV"
    bl_options = {"REGISTER", "UNDO"}
    sna_size: bpy.props.FloatVectorProperty(name='size', description='', options={'HIDDEN'}, size=2, default=(0.0, 0.0), subtype='NONE', unit='NONE', step=1, precision=2)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if bpy.context.scene.sna_uv_size_mode:
            bpy.ops.transform.resize(value=(self.sna_size[0], self.sna_size[1], 1.0), center_override=(bpy.context.scene.sna_uv_size_coordinate[0], bpy.context.scene.sna_uv_size_coordinate[1], 0.0))
        else:
            bpy.ops.transform.resize(value=(self.sna_size[0], self.sna_size[1], 1.0))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv__8Beae(bpy.types.Operator):
    bl_idname = "sna.uv__8beae"
    bl_label = "uv_对称"
    bl_description = "UV对称"
    bl_options = {"REGISTER", "UNDO"}
    sna_xy: bpy.props.StringProperty(name='xy', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.uv.univ_flip(mode=('DEFAULT' if bpy.context.scene.sna_uv_flip_mode else 'INDIVIDUAL'), axis=self.sna_xy)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv__B75E5(bpy.types.Operator):
    bl_idname = "sna.uv__b75e5"
    bl_label = "uv_对齐象限面板"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_uv_quadrant_edge_alignment_4DA3C", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_uv_quadrant_edge_alignment_4DA3C(bpy.types.Panel):
    bl_label = '象限边缘对齐'
    bl_idname = 'SNA_PT_uv_quadrant_edge_alignment_4DA3C'
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
        split_BDBBC = layout.split(factor=0.5, align=True)
        split_BDBBC.alert = False
        split_BDBBC.enabled = True
        split_BDBBC.active = True
        split_BDBBC.use_property_split = False
        split_BDBBC.use_property_decorate = False
        split_BDBBC.scale_x = 1.0
        split_BDBBC.scale_y = 1.0
        split_BDBBC.alignment = 'Expand'.upper()
        if not True: split_BDBBC.operator_context = "EXEC_DEFAULT"
        col_590E2 = split_BDBBC.column(heading='', align=True)
        col_590E2.alert = False
        col_590E2.enabled = True
        col_590E2.active = True
        col_590E2.use_property_split = False
        col_590E2.use_property_decorate = False
        col_590E2.scale_x = 1.0
        col_590E2.scale_y = 1.2999999523162842
        col_590E2.alignment = 'Expand'.upper()
        col_590E2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_7E78E = col_590E2.row(heading='', align=True)
        row_7E78E.alert = False
        row_7E78E.enabled = True
        row_7E78E.active = True
        row_7E78E.use_property_split = False
        row_7E78E.use_property_decorate = False
        row_7E78E.scale_x = 1.0
        row_7E78E.scale_y = 1.0
        row_7E78E.alignment = 'Expand'.upper()
        row_7E78E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_7E78E.label(text='', icon_value=0)
        op = row_7E78E.operator('sna.uv__adfc0', text='顶', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = 'BOTTOM'
        op.sna_new_property_001 = (0, 1)
        row_7E78E.label(text='', icon_value=0)
        row_6F6D2 = col_590E2.row(heading='', align=True)
        row_6F6D2.alert = False
        row_6F6D2.enabled = True
        row_6F6D2.active = True
        row_6F6D2.use_property_split = False
        row_6F6D2.use_property_decorate = False
        row_6F6D2.scale_x = 1.0
        row_6F6D2.scale_y = 1.0
        row_6F6D2.alignment = 'Expand'.upper()
        row_6F6D2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_6F6D2.operator('sna.uv__adfc0', text='左', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = 'RIGHT'
        op.sna_new_property_001 = (0, 0)
        row_6F6D2.label(text='', icon_value=0)
        op = row_6F6D2.operator('sna.uv__adfc0', text='右', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = 'LEFT'
        op.sna_new_property_001 = (1, 0)
        row_16F6C = col_590E2.row(heading='', align=True)
        row_16F6C.alert = False
        row_16F6C.enabled = True
        row_16F6C.active = True
        row_16F6C.use_property_split = False
        row_16F6C.use_property_decorate = False
        row_16F6C.scale_x = 1.0
        row_16F6C.scale_y = 1.0
        row_16F6C.alignment = 'Expand'.upper()
        row_16F6C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_16F6C.label(text='', icon_value=0)
        op = row_16F6C.operator('sna.uv__adfc0', text='底', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = 'UPPER'
        op.sna_new_property_001 = (0, 0)
        row_16F6C.label(text='', icon_value=0)


class SNA_OT_Uv__Adfc0(bpy.types.Operator):
    bl_idname = "sna.uv__adfc0"
    bl_label = "uv_对齐象限"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='方向', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_new_property_001: bpy.props.IntVectorProperty(name='游标位置', description='', options={'HIDDEN'}, size=2, default=(0, 0), subtype='NONE')

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.uv.cursor_set(location=self.sna_new_property_001)
        bpy.ops.uv.univ_align(direction=self.sna_new_property, mode='ALIGN_TO_CURSOR_UNION')
        bpy.ops.uv.cursor_set(location=(0.0, 0.0))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Df204(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_df204"
    bl_label = "选择钉住"
    bl_description = "选择钉住/未钉住"
    bl_options = {"REGISTER", "UNDO"}
    sna_select: bpy.props.BoolProperty(name='Select', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.uv.select_mode(type='VERTEX')
        bpy.ops.uv.select_all(action='DESELECT')
        bpy.ops.uv.select_pinned()
        if self.sna_select:
            bpy.ops.uv.select_all(action='INVERT')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uvpackmaster_Edf0D(bpy.types.Operator):
    bl_idname = "sna.uvpackmaster_edf0d"
    bl_label = "UVPackmaster"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_pack_to_others: bpy.props.BoolProperty(name='pack_to_others', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.context.scene.uvpm3_props.margin = float(bpy.context.scene.sna_uv_tex_overflow / bpy.context.scene.sna_uv_tex_size)
        bpy.ops.uvpackmaster3.pack(mode_id='pack.single_tile')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_236E2(bpy.types.Operator):
    bl_idname = "sna.uv_236e2"
    bl_label = "UV数据显示"
    bl_description = "UV数据显示"
    bl_options = {"REGISTER", "UNDO"}
    sna_draw_mode: bpy.props.StringProperty(name='draw_mode', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        uv_004['sna_draw_mode_uv'] = self.sna_draw_mode
        bpy.ops.wm.context_set_enum(data_path='scene.zen_uv.ui.draw_mode_UV', value=self.sna_draw_mode)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_D_8A15D(bpy.types.Operator):
    bl_idname = "sna.d_8a15d"
    bl_label = "3D同步选中"
    bl_description = "3D同步选中"
    bl_options = {"REGISTER", "UNDO"}
    sna_mode: bpy.props.StringProperty(name='mode', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.context_set_enum(data_path='scene.zen_uv.ui.draw_mode_3D', value=self.sna_mode)
        uv_004['sna_draw_mode_3d'] = self.sna_mode
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_add_to_image_pt_tools_active_801BA(self, context):
    if not (False):
        layout = self.layout
        col_2DD3B = layout.column(heading='', align=True)
        col_2DD3B.alert = False
        col_2DD3B.enabled = True
        col_2DD3B.active = True
        col_2DD3B.use_property_split = False
        col_2DD3B.use_property_decorate = False
        col_2DD3B.scale_x = 1.0
        col_2DD3B.scale_y = 1.2999999523162842
        col_2DD3B.alignment = 'Expand'.upper()
        col_2DD3B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_8ED3D = col_2DD3B.column(heading='', align=True)
        col_8ED3D.alert = False
        col_8ED3D.enabled = 'EDIT_MESH'==bpy.context.mode
        col_8ED3D.active = True
        col_8ED3D.use_property_split = False
        col_8ED3D.use_property_decorate = False
        col_8ED3D.scale_x = 1.0
        col_8ED3D.scale_y = 1.0
        col_8ED3D.alignment = 'Expand'.upper()
        col_8ED3D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_8ED3D.operator('sna.d_8a15d', text='3D同步', icon_value=0, emboss=True, depress=(uv_004['sna_draw_mode_3d'] == 'UV_NO_SYNC'))
        op.sna_mode = ('NONE' if (uv_004['sna_draw_mode_3d'] == 'UV_NO_SYNC') else 'UV_NO_SYNC')
        col_8ED3D.separator(factor=1.0)
        for i_863D6 in range(len([['缝合边', 'SEAMS'], ['边界', 'UV_BORDERS'], ['反面', 'FLIPPED'], ['重叠', 'OVERLAPPED'], ['UV密度', 'TEXEL_DENSITY']])):
            if ([['缝合边', 'SEAMS'], ['边界', 'UV_BORDERS'], ['反面', 'FLIPPED'], ['重叠', 'OVERLAPPED'], ['UV密度', 'TEXEL_DENSITY']][i_863D6][1] != uv_004['sna_draw_mode_uv']):
                op = col_8ED3D.operator('sna.uv_236e2', text=[['缝合边', 'SEAMS'], ['边界', 'UV_BORDERS'], ['反面', 'FLIPPED'], ['重叠', 'OVERLAPPED'], ['UV密度', 'TEXEL_DENSITY']][i_863D6][0], icon_value=0, emboss=True, depress=False)
                op.sna_draw_mode = [['缝合边', 'SEAMS'], ['边界', 'UV_BORDERS'], ['反面', 'FLIPPED'], ['重叠', 'OVERLAPPED'], ['UV密度', 'TEXEL_DENSITY']][i_863D6][1]
            else:
                op = col_8ED3D.operator('sna.uv_236e2', text=[['缝合边', 'SEAMS'], ['边界', 'UV_BORDERS'], ['反面', 'FLIPPED'], ['重叠', 'OVERLAPPED'], ['UV密度', 'TEXEL_DENSITY']][i_863D6][0], icon_value=0, emboss=True, depress=True)
                op.sna_draw_mode = 'NONE'
        col_8ED3D.prop(bpy.context.area.spaces[0].uv_editor, 'show_stretch', text='UV拉伸', icon_value=0, emboss=True, toggle=True)
        col_8ED3D.separator(factor=1.0)
        col_C11BD = col_2DD3B.column(heading='', align=True)
        col_C11BD.alert = False
        col_C11BD.enabled = True
        col_C11BD.active = True
        col_C11BD.use_property_split = False
        col_C11BD.use_property_decorate = False
        col_C11BD.scale_x = 1.0
        col_C11BD.scale_y = 1.0
        col_C11BD.alignment = 'Expand'.upper()
        col_C11BD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_59F34 = col_C11BD.split(factor=0.800000011920929, align=True)
        split_59F34.alert = False
        split_59F34.enabled = True
        split_59F34.active = True
        split_59F34.use_property_split = False
        split_59F34.use_property_decorate = False
        split_59F34.scale_x = 1.0
        split_59F34.scale_y = 1.0
        split_59F34.alignment = 'Expand'.upper()
        if not True: split_59F34.operator_context = "EXEC_DEFAULT"
        op = split_59F34.operator('sna.uv_4653d', text='栅格', icon_value=0, emboss=True, depress=False)
        op = split_59F34.operator('wm.univ_checker_cleanup', text='', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
        col_C11BD.prop(bpy.context.scene, 'sna_uv_xy_tex', text='', icon_value=0, emboss=True)


class SNA_OT_Uv_4653D(bpy.types.Operator):
    bl_idname = "sna.uv_4653d"
    bl_label = "UV栅格检查"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'VIEW_3D'
        bpy.ops.wm.univ_checker_cleanup()
        bpy.context.area.type = prev_context
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'VIEW_3D'
        bpy.ops.mesh.univ_checker(toggle=True, generated_type='UV_GRID', size_x=bpy.context.scene.sna_uv_xy_tex, size_y=bpy.context.scene.sna_uv_xy_tex, lock_size=False)
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_4A729(bpy.types.Menu):
    bl_idname = "SNA_MT_4A729"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not ((not 'EDIT_MESH'==bpy.context.mode))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('sna.my_generic_operator_8a716', text='点', icon_value=644, emboss=True, depress=False)
        op.sna_selection_mode_01 = 'VERT'
        op.sna_selection_mode_02 = 'VERTEX'
        op.sna_selection_mode_03 = 'SHARED_LOCATION'
        op = layout.operator('sna.my_generic_operator_8a716', text='面', icon_value=286, emboss=True, depress=False)
        op.sna_selection_mode_01 = 'FACE'
        op.sna_selection_mode_02 = 'FACE'
        op.sna_selection_mode_03 = 'SHARED_LOCATION'
        op = layout.operator('sna.my_generic_operator_d5090', text='快捷键', icon_value=190, emboss=True, depress=False)
        op = layout.operator('sna.my_generic_operator_8a716', text='边', icon_value=563, emboss=True, depress=False)
        op.sna_selection_mode_01 = 'EDGE'
        op.sna_selection_mode_02 = 'EDGE'
        op.sna_selection_mode_03 = 'SHARED_LOCATION'
        op = layout.operator('sna.my_generic_operator_0475f', text='独显', icon_value=string_to_icon('PIVOT_BOUNDBOX'), emboss=True, depress=False)
        op = layout.operator('sna.my_generic_operator_aa4b9', text='更新缝合边', icon_value=692, emboss=True, depress=False)
        op = layout.operator('uv.select_linked', text='选孤岛', icon_value=454, emboss=True, depress=False)
        op = layout.operator('sna.my_generic_operator_8a716', text='孤岛', icon_value=291, emboss=True, depress=False)
        op.sna_selection_mode_01 = 'NONE'
        op.sna_selection_mode_02 = 'ISLAND'
        op.sna_selection_mode_03 = 'SHARED_LOCATION'


class SNA_OT_My_Generic_Operator_8A716(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_8a716"
    bl_label = "选择模式"
    bl_description = "选择模式切换"
    bl_options = {"REGISTER", "UNDO"}
    sna_selection_mode_01: bpy.props.StringProperty(name='Selection_Mode_01', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_selection_mode_02: bpy.props.StringProperty(name='Selection_Mode_02', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_selection_mode_03: bpy.props.StringProperty(name='Selection_Mode_03', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            if ('NONE' != self.sna_selection_mode_01):
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type=self.sna_selection_mode_01, action='ENABLE')
        else:
            bpy.ops.uv.select_mode(type=self.sna_selection_mode_02)
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.context.scene.tool_settings.uv_sticky_select_mode = self.sna_selection_mode_03
        return self.execute(context)


class SNA_OT_Qkk_Uv_Loop_78D8A(bpy.types.Operator):
    bl_idname = "sna.qkk_uv_loop_78d8a"
    bl_label = "Qkk_UV_Loop"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.BoolProperty(name='扩展选择', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            if bpy.context.tool_settings.mesh_select_mode[0]:
                bpy.ops.uv.select_linked()
            else:
                if bpy.context.tool_settings.mesh_select_mode[1]:
                    prev_context = bpy.context.area.type
                    bpy.context.area.type = 'IMAGE_EDITOR'
                    bpy.ops.uv.select_loop('INVOKE_DEFAULT', extend=self.sna_new_property)
                    bpy.context.area.type = prev_context
                else:
                    if bpy.context.tool_settings.mesh_select_mode[2]:
                        prev_context = bpy.context.area.type
                        bpy.context.area.type = 'IMAGE_EDITOR'
                        bpy.ops.uv.select_loop('INVOKE_DEFAULT', extend=self.sna_new_property)
                        bpy.context.area.type = prev_context
        else:
            if (bpy.context.scene.tool_settings.uv_select_mode == 'VERTEX'):
                bpy.ops.uv.select_linked()
            else:
                if (bpy.context.scene.tool_settings.uv_select_mode == 'EDGE'):
                    prev_context = bpy.context.area.type
                    bpy.context.area.type = 'IMAGE_EDITOR'
                    bpy.ops.uv.select_loop('INVOKE_DEFAULT', extend=self.sna_new_property)
                    bpy.context.area.type = prev_context
                else:
                    if (bpy.context.scene.tool_settings.uv_select_mode == 'FACE'):
                        prev_context = bpy.context.area.type
                        bpy.context.area.type = 'IMAGE_EDITOR'
                        bpy.ops.uv.select_loop('INVOKE_DEFAULT', extend=self.sna_new_property)
                        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Qkk_Uv_Cut_26D51(bpy.types.Operator):
    bl_idname = "sna.qkk_uv_cut_26d51"
    bl_label = "Qkk_UV_Cut"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'IMAGE_EDITOR'
        bpy.ops.uv.univ_cut('INVOKE_DEFAULT', unwrap='NONE')
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Qkk_Uv_Drag_99763(bpy.types.Operator):
    bl_idname = "sna.qkk_uv_drag_99763"
    bl_label = "Qkk_UV_Drag"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'IMAGE_EDITOR'
        bpy.ops.uv.univ_drag('INVOKE_DEFAULT', )
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Qkk_Uv_Snap_87237(bpy.types.Operator):
    bl_idname = "sna.qkk_uv_snap_87237"
    bl_label = "Qkk_UV_Snap"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'IMAGE_EDITOR'
        bpy.ops.uv.univ_quick_snap('INVOKE_DEFAULT', island_mode=True, quick_start=False)
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Qkk_Uv_Weld_F659B(bpy.types.Operator):
    bl_idname = "sna.qkk_uv_weld_f659b"
    bl_label = "Qkk_UV_Weld"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'IMAGE_EDITOR'
        bpy.ops.uv.univ_weld('INVOKE_DEFAULT', use_by_distance=False)
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_func_ABB1C():
    font_id = 0
    if r'' and os.path.exists(r''):
        font_id = blf.load(r'')
    if font_id == -1:
        print("Couldn't load font!")
    else:
        x_D1691, y_D1691 = (10.0, 200.0)
        blf.position(font_id, x_D1691, y_D1691, 0)
        if bpy.app.version >= (3, 4, 0):
            blf.size(font_id, 14.0)
        else:
            blf.size(font_id, 14.0, 72)
        clr = (1.0, 1.0, 1.0, 1.0)
        blf.color(font_id, clr[0], clr[1], clr[2], clr[3])
        if 0:
            blf.enable(font_id, blf.WORD_WRAP)
            blf.word_wrap(font_id, 0)
        if 0.0:
            blf.enable(font_id, blf.ROTATION)
            blf.rotation(font_id, 0.0)
        blf.enable(font_id, blf.WORD_WRAP)
        blf.draw(font_id, 'C  切开' + '\n' + 'X  焊接' + '\n' + 'V  吸附' + '\n' + 'Alt+左键  拖拽' + '\n' + 'Ctrl+左键  最短距离选择' + '\n' + 'A、Shitf+A    循环选择' + '\n')
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.WORD_WRAP)


class SNA_OT_Qkk_Uv_Sewing_Aad37(bpy.types.Operator):
    bl_idname = "sna.qkk_uv_sewing_aad37"
    bl_label = "Qkk_UV_Sewing"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        prev_context = bpy.context.area.type
        bpy.context.area.type = 'IMAGE_EDITOR'
        bpy.ops.uv.stitch('INVOKE_DEFAULT', snap_islands=True, midpoint_snap=False, clear_seams=True, mode='EDGE', stored_mode='EDGE')
        bpy.context.area.type = prev_context
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Qkk_Uv_Select_Islands_F84C9(bpy.types.Operator):
    bl_idname = "sna.qkk_uv_select_islands_f84c9"
    bl_label = "Qkk_UV_Select_Islands"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        bpy.ops.uv.select_linked()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_D5090(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d5090"
    bl_label = "快捷键说明"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        if node_tree['sna_keyboard_shortcuts_explanation']:
            if handler_0C8CE:
                bpy.types.SpaceImageEditor.draw_handler_remove(handler_0C8CE[0], 'WINDOW')
                handler_0C8CE.pop(0)
                for a in bpy.context.screen.areas: a.tag_redraw()
            node_tree['sna_keyboard_shortcuts_explanation'] = False
        else:
            if node_tree['sna_keyboard_shortcuts_explanation']:
                pass
            else:
                if handler_0C8CE:
                    bpy.types.SpaceImageEditor.draw_handler_remove(handler_0C8CE[0], 'WINDOW')
                    handler_0C8CE.pop(0)
                    for a in bpy.context.screen.areas: a.tag_redraw()
                handler_0C8CE.append(bpy.types.SpaceImageEditor.draw_handler_add(sna_func_ABB1C, (), 'WINDOW', 'POST_PIXEL'))
                for a in bpy.context.screen.areas: a.tag_redraw()
                node_tree['sna_keyboard_shortcuts_explanation'] = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_3Dcut_5F763(bpy.types.Operator):
    bl_idname = "sna.uv_3dcut_5f763"
    bl_label = "UV_3dCut"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        bpy.ops.mesh.mark_seam(clear=False)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_3Dtitch_6Ef3A(bpy.types.Operator):
    bl_idname = "sna.uv_3dtitch_6ef3a"
    bl_label = "UV_3dtitch"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not (not 'EDIT_MESH'==bpy.context.mode)

    def execute(self, context):
        bpy.ops.mesh.univ_weld(use_by_distance=False, use_aspect=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_unfold_1DDC1(bpy.types.Panel):
    bl_label = '展开'
    bl_idname = 'SNA_PT_unfold_1DDC1'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 5
    bl_parent_id = 'SNA_PT_QKK_UV_37C20'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_32D41 = layout.column(heading='', align=False)
        col_32D41.alert = False
        col_32D41.enabled = 'EDIT_MESH'==bpy.context.mode
        col_32D41.active = True
        col_32D41.use_property_split = False
        col_32D41.use_property_decorate = False
        col_32D41.scale_x = 1.0
        col_32D41.scale_y = 1.0
        col_32D41.alignment = 'Expand'.upper()
        col_32D41.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_0C221 = col_32D41.column(heading='', align=True)
        col_0C221.alert = False
        col_0C221.enabled = True
        col_0C221.active = True
        col_0C221.use_property_split = False
        col_0C221.use_property_decorate = False
        col_0C221.scale_x = 1.0
        col_0C221.scale_y = 1.2999999523162842
        col_0C221.alignment = 'Expand'.upper()
        col_0C221.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_484C4 = col_0C221.split(factor=0.5, align=True)
        split_484C4.alert = False
        split_484C4.enabled = True
        split_484C4.active = True
        split_484C4.use_property_split = False
        split_484C4.use_property_decorate = False
        split_484C4.scale_x = 1.0
        split_484C4.scale_y = 1.0
        split_484C4.alignment = 'Expand'.upper()
        if not True: split_484C4.operator_context = "EXEC_DEFAULT"
        op = split_484C4.operator('sna.my_generic_operator_02e18', text='创建', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'normalize.png')), emboss=True, depress=False)
        row_B1FFA = split_484C4.row(heading='', align=True)
        row_B1FFA.alert = False
        row_B1FFA.enabled = True
        row_B1FFA.active = True
        row_B1FFA.use_property_split = False
        row_B1FFA.use_property_decorate = False
        row_B1FFA.scale_x = 1.0
        row_B1FFA.scale_y = 1.0
        row_B1FFA.alignment = 'Expand'.upper()
        row_B1FFA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_B1FFA.operator('uv.smart_project', text='角度', icon_value=0, emboss=True, depress=False)
        op = row_B1FFA.operator('uv.univ_relax', text='松弛', icon_value=0, emboss=True, depress=False)
        col_4A972 = col_32D41.column(heading='', align=True)
        col_4A972.alert = False
        col_4A972.enabled = True
        col_4A972.active = True
        col_4A972.use_property_split = False
        col_4A972.use_property_decorate = False
        col_4A972.scale_x = 1.0
        col_4A972.scale_y = 1.2999999523162842
        col_4A972.alignment = 'Expand'.upper()
        col_4A972.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_34755 = col_4A972.split(factor=0.5, align=True)
        split_34755.alert = False
        split_34755.enabled = True
        split_34755.active = True
        split_34755.use_property_split = False
        split_34755.use_property_decorate = False
        split_34755.scale_x = 1.0
        split_34755.scale_y = 1.0
        split_34755.alignment = 'Expand'.upper()
        if not True: split_34755.operator_context = "EXEC_DEFAULT"
        op = split_34755.operator('uv.univ_unwrap', text='展开', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'unwrap.png')), emboss=True, depress=False)
        row_AE854 = split_34755.row(heading='', align=True)
        row_AE854.alert = False
        row_AE854.enabled = True
        row_AE854.active = True
        row_AE854.use_property_split = False
        row_AE854.use_property_decorate = False
        row_AE854.scale_x = 1.0
        row_AE854.scale_y = 1.0
        row_AE854.alignment = 'Expand'.upper()
        row_AE854.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_AE854.operator('uv.univ_adjust_td', text='平均', icon_value=0, emboss=True, depress=False)
        op = row_AE854.operator('uv.univ_normalize', text='3D平均', icon_value=0, emboss=True, depress=False)
        split_64C9A = col_32D41.split(factor=0.5, align=True)
        split_64C9A.alert = False
        split_64C9A.enabled = True
        split_64C9A.active = True
        split_64C9A.use_property_split = False
        split_64C9A.use_property_decorate = False
        split_64C9A.scale_x = 1.0
        split_64C9A.scale_y = 1.0
        split_64C9A.alignment = 'Expand'.upper()
        if not True: split_64C9A.operator_context = "EXEC_DEFAULT"
        row_6E75F = split_64C9A.row(heading='', align=True)
        row_6E75F.alert = False
        row_6E75F.enabled = True
        row_6E75F.active = True
        row_6E75F.use_property_split = False
        row_6E75F.use_property_decorate = False
        row_6E75F.scale_x = 1.0
        row_6E75F.scale_y = 1.2999999523162842
        row_6E75F.alignment = 'Expand'.upper()
        row_6E75F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_6E75F.operator('sna.my_generic_operator_4609d', text='切开', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'cut.png')), emboss=True, depress=False)
        op = row_6E75F.operator('sna.my_generic_operator_e955e', text='缝合', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'stitch.png')), emboss=True, depress=False)
        split_A0F62 = split_64C9A.split(factor=0.5, align=True)
        split_A0F62.alert = False
        split_A0F62.enabled = True
        split_A0F62.active = True
        split_A0F62.use_property_split = False
        split_A0F62.use_property_decorate = False
        split_A0F62.scale_x = 1.0
        split_A0F62.scale_y = 1.2999999523162842
        split_A0F62.alignment = 'Expand'.upper()
        if not True: split_A0F62.operator_context = "EXEC_DEFAULT"
        op = split_A0F62.operator('uv.univ_quadrify', text='拉直', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'quadrify.png')), emboss=True, depress=False)
        row_68396 = split_A0F62.row(heading='', align=True)
        row_68396.alert = False
        row_68396.enabled = True
        row_68396.active = True
        row_68396.use_property_split = False
        row_68396.use_property_decorate = False
        row_68396.scale_x = 1.0
        row_68396.scale_y = 1.0
        row_68396.alignment = 'Expand'.upper()
        row_68396.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_68396.operator('uv.univ_rectify', text=' ', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'rectify.png')), emboss=True, depress=False)
        op = row_68396.operator('uv.univ_straight', text=' ', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'straight.png')), emboss=True, depress=False)


class SNA_PT_uv_conversion_1F7BD(bpy.types.Panel):
    bl_label = '变换'
    bl_idname = 'SNA_PT_uv_conversion_1F7BD'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 6
    bl_parent_id = 'SNA_PT_QKK_UV_37C20'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_3B1BA = layout.column(heading='', align=True)
        col_3B1BA.alert = False
        col_3B1BA.enabled = 'EDIT_MESH'==bpy.context.mode
        col_3B1BA.active = True
        col_3B1BA.use_property_split = False
        col_3B1BA.use_property_decorate = False
        col_3B1BA.scale_x = 1.0
        col_3B1BA.scale_y = 1.0
        col_3B1BA.alignment = 'Expand'.upper()
        col_3B1BA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        box_3EE25 = col_3B1BA.box()
        box_3EE25.alert = False
        box_3EE25.enabled = True
        box_3EE25.active = True
        box_3EE25.use_property_split = False
        box_3EE25.use_property_decorate = False
        box_3EE25.alignment = 'Expand'.upper()
        box_3EE25.scale_x = 1.0
        box_3EE25.scale_y = 1.0
        if not True: box_3EE25.operator_context = "EXEC_DEFAULT"
        col_FD6E4 = box_3EE25.column(heading='', align=True)
        col_FD6E4.alert = False
        col_FD6E4.enabled = True
        col_FD6E4.active = True
        col_FD6E4.use_property_split = False
        col_FD6E4.use_property_decorate = False
        col_FD6E4.scale_x = 1.0
        col_FD6E4.scale_y = 1.0
        col_FD6E4.alignment = 'Expand'.upper()
        col_FD6E4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_BB4DF = col_FD6E4.split(factor=0.5, align=True)
        split_BB4DF.alert = False
        split_BB4DF.enabled = True
        split_BB4DF.active = True
        split_BB4DF.use_property_split = False
        split_BB4DF.use_property_decorate = False
        split_BB4DF.scale_x = 1.0
        split_BB4DF.scale_y = 1.0
        split_BB4DF.alignment = 'Expand'.upper()
        if not True: split_BB4DF.operator_context = "EXEC_DEFAULT"
        split_9BD7F = split_BB4DF.split(factor=0.800000011920929, align=True)
        split_9BD7F.alert = False
        split_9BD7F.enabled = True
        split_9BD7F.active = True
        split_9BD7F.use_property_split = False
        split_9BD7F.use_property_decorate = False
        split_9BD7F.scale_x = 1.0
        split_9BD7F.scale_y = 1.0
        split_9BD7F.alignment = 'Expand'.upper()
        if not True: split_9BD7F.operator_context = "EXEC_DEFAULT"
        col_95891 = split_9BD7F.column(heading='', align=True)
        col_95891.alert = False
        col_95891.enabled = True
        col_95891.active = True
        col_95891.use_property_split = False
        col_95891.use_property_decorate = False
        col_95891.scale_x = 1.0
        col_95891.scale_y = 2.0
        col_95891.alignment = 'Expand'.upper()
        col_95891.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_95891.operator('uv.univ_orient', text='自动对正', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'body.png')), emboss=True, depress=False)
        op.lock_overlap = False
        op.lock_overlap_mode = 'ANY'
        op.threshold = 0.0
        op.edge_dir = 'BOTH'
        col_466FF = split_9BD7F.column(heading='', align=True)
        col_466FF.alert = False
        col_466FF.enabled = True
        col_466FF.active = True
        col_466FF.use_property_split = False
        col_466FF.use_property_decorate = False
        col_466FF.scale_x = 1.0
        col_466FF.scale_y = 1.0
        col_466FF.alignment = 'Expand'.upper()
        col_466FF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_466FF.operator('uv.univ_orient', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'x.png')), emboss=True, depress=False)
        op.lock_overlap = False
        op.lock_overlap_mode = 'ANY'
        op.threshold = 0.0
        op.edge_dir = 'HORIZONTAL'
        op = col_466FF.operator('uv.univ_orient', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'y.png')), emboss=True, depress=False)
        op.lock_overlap = False
        op.lock_overlap_mode = 'ANY'
        op.threshold = 0.0
        op.edge_dir = 'VERTICAL'
        col_99926 = split_BB4DF.column(heading='', align=True)
        col_99926.alert = False
        col_99926.enabled = True
        col_99926.active = True
        col_99926.use_property_split = False
        col_99926.use_property_decorate = False
        col_99926.scale_x = 1.0
        col_99926.scale_y = 1.0
        col_99926.alignment = 'Expand'.upper()
        col_99926.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_45EA7 = col_99926.split(factor=0.5, align=True)
        split_45EA7.alert = False
        split_45EA7.enabled = True
        split_45EA7.active = True
        split_45EA7.use_property_split = False
        split_45EA7.use_property_decorate = False
        split_45EA7.scale_x = 1.0
        split_45EA7.scale_y = 1.0
        split_45EA7.alignment = 'Expand'.upper()
        if not True: split_45EA7.operator_context = "EXEC_DEFAULT"
        op = split_45EA7.operator('sna.my_generic_operator_34cdd', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'p90.png')), emboss=True, depress=False)
        op.sna_direction_of_rotation = 'CCW'
        op = split_45EA7.operator('sna.my_generic_operator_34cdd', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'n90.png')), emboss=True, depress=False)
        op.sna_direction_of_rotation = 'CW'
        split_00783 = col_99926.split(factor=0.5, align=True)
        split_00783.alert = False
        split_00783.enabled = True
        split_00783.active = True
        split_00783.use_property_split = False
        split_00783.use_property_decorate = False
        split_00783.scale_x = 1.0
        split_00783.scale_y = 1.0
        split_00783.alignment = 'Expand'.upper()
        if not True: split_00783.operator_context = "EXEC_DEFAULT"
        split_00783.prop(bpy.context.scene, 'sna_uv_rotation_angle', text='', icon_value=0, emboss=True)
        split_00783.prop(bpy.context.scene, 'sna_uv_rotation_mode', text='整体', icon_value=0, emboss=True)
        split_25F20 = col_3B1BA.split(factor=0.5, align=True)
        split_25F20.alert = False
        split_25F20.enabled = True
        split_25F20.active = True
        split_25F20.use_property_split = False
        split_25F20.use_property_decorate = False
        split_25F20.scale_x = 1.0
        split_25F20.scale_y = 1.0
        split_25F20.alignment = 'Expand'.upper()
        if not True: split_25F20.operator_context = "EXEC_DEFAULT"
        box_824E9 = split_25F20.box()
        box_824E9.alert = False
        box_824E9.enabled = True
        box_824E9.active = True
        box_824E9.use_property_split = False
        box_824E9.use_property_decorate = False
        box_824E9.alignment = 'Expand'.upper()
        box_824E9.scale_x = 1.0
        box_824E9.scale_y = 1.0
        if not True: box_824E9.operator_context = "EXEC_DEFAULT"
        col_086C0 = box_824E9.column(heading='', align=True)
        col_086C0.alert = False
        col_086C0.enabled = True
        col_086C0.active = True
        col_086C0.use_property_split = False
        col_086C0.use_property_decorate = False
        col_086C0.scale_x = 2.0
        col_086C0.scale_y = 1.5
        col_086C0.alignment = 'Expand'.upper()
        col_086C0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_A6630 = col_086C0.row(heading='', align=True)
        row_A6630.alert = False
        row_A6630.enabled = True
        row_A6630.active = True
        row_A6630.use_property_split = False
        row_A6630.use_property_decorate = False
        row_A6630.scale_x = 1.0
        row_A6630.scale_y = 1.0
        row_A6630.alignment = 'Expand'.upper()
        row_A6630.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_A6630.operator('uv.univ_stack', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'stack.png')), emboss=True, depress=False)
        op = row_A6630.operator('sna.uv_94eb3', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'symm_n_y.png')), emboss=True, depress=False)
        op.sna_move = (0.0, bpy.context.scene.sna_uv_move_size)
        op = row_A6630.operator('uv.univ_home', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'home.png')), emboss=True, depress=False)
        op.to_cursor = False
        row_906F7 = col_086C0.row(heading='', align=True)
        row_906F7.alert = False
        row_906F7.enabled = True
        row_906F7.active = True
        row_906F7.use_property_split = False
        row_906F7.use_property_decorate = False
        row_906F7.scale_x = 1.0
        row_906F7.scale_y = 1.0
        row_906F7.alignment = 'Expand'.upper()
        row_906F7.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_906F7.operator('sna.uv_94eb3', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'symm_p_x.png')), emboss=True, depress=False)
        op.sna_move = (float(bpy.context.scene.sna_uv_move_size * -1.0), 0.0)
        op = row_906F7.operator('sna.my_generic_operator_e4775', text='', icon_value=117, emboss=True, depress=False)
        op = row_906F7.operator('sna.uv_94eb3', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'symm_n_x.png')), emboss=True, depress=False)
        op.sna_move = (bpy.context.scene.sna_uv_move_size, 0.0)
        row_5E64C = col_086C0.row(heading='', align=True)
        row_5E64C.alert = False
        row_5E64C.enabled = True
        row_5E64C.active = True
        row_5E64C.use_property_split = False
        row_5E64C.use_property_decorate = False
        row_5E64C.scale_x = 1.0
        row_5E64C.scale_y = 1.0
        row_5E64C.alignment = 'Expand'.upper()
        row_5E64C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_5E64C.separator(factor=4.0)
        op = row_5E64C.operator('sna.uv_94eb3', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'symm_p_y.png')), emboss=True, depress=False)
        op.sna_move = (0.0, float(bpy.context.scene.sna_uv_move_size * -1.0))
        row_5E64C.separator(factor=4.0)
        box_FFD86 = split_25F20.box()
        box_FFD86.alert = False
        box_FFD86.enabled = True
        box_FFD86.active = True
        box_FFD86.use_property_split = False
        box_FFD86.use_property_decorate = False
        box_FFD86.alignment = 'Expand'.upper()
        box_FFD86.scale_x = 1.0
        box_FFD86.scale_y = 1.0
        if not True: box_FFD86.operator_context = "EXEC_DEFAULT"
        col_72891 = box_FFD86.column(heading='', align=True)
        col_72891.alert = False
        col_72891.enabled = True
        col_72891.active = True
        col_72891.use_property_split = False
        col_72891.use_property_decorate = False
        col_72891.scale_x = 2.0
        col_72891.scale_y = 1.5
        col_72891.alignment = 'Expand'.upper()
        col_72891.operator_context = "INVOKE_DEFAULT" if False else "EXEC_DEFAULT"
        row_FD535 = col_72891.row(heading='', align=True)
        row_FD535.alert = False
        row_FD535.enabled = True
        row_FD535.active = True
        row_FD535.use_property_split = False
        row_FD535.use_property_decorate = False
        row_FD535.scale_x = 1.0
        row_FD535.scale_y = 1.0
        row_FD535.alignment = 'Expand'.upper()
        row_FD535.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_FD535.separator(factor=4.0)
        op = row_FD535.operator('sna.uv__ca81b', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'align_top.png')), emboss=True, depress=False)
        op.sna_direction = 'UPPER'
        op = row_FD535.operator('sna.uv__b75e5', text='', icon_value=string_to_icon('SHADING_BBOX'), emboss=True, depress=False)
        row_0079E = col_72891.row(heading='', align=True)
        row_0079E.alert = False
        row_0079E.enabled = True
        row_0079E.active = True
        row_0079E.use_property_split = False
        row_0079E.use_property_decorate = False
        row_0079E.scale_x = 1.0
        row_0079E.scale_y = 1.0
        row_0079E.alignment = 'Expand'.upper()
        row_0079E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_0079E.operator('sna.uv__ca81b', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'align_left.png')), emboss=True, depress=False)
        op.sna_direction = 'LEFT'
        op = row_0079E.operator('sna.uv__ca81b', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'align_center.png')), emboss=True, depress=False)
        op.sna_direction = 'CENTER'
        op = row_0079E.operator('sna.uv__ca81b', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'align_right.png')), emboss=True, depress=False)
        op.sna_direction = 'RIGHT'
        row_277B1 = col_72891.row(heading='', align=True)
        row_277B1.alert = False
        row_277B1.enabled = True
        row_277B1.active = True
        row_277B1.use_property_split = False
        row_277B1.use_property_decorate = False
        row_277B1.scale_x = 1.0
        row_277B1.scale_y = 1.0
        row_277B1.alignment = 'Expand'.upper()
        row_277B1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_277B1.operator('sna.uv__ca81b', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'align_y_center.png')), emboss=True, depress=False)
        op.sna_direction = 'HORIZONTAL'
        op = row_277B1.operator('sna.uv__ca81b', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'align_bottom.png')), emboss=True, depress=False)
        op.sna_direction = 'BOTTOM'
        op = row_277B1.operator('sna.uv__ca81b', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'align_x_center.png')), emboss=True, depress=False)
        op.sna_direction = 'VERTICAL'
        box_6CE27 = col_3B1BA.box()
        box_6CE27.alert = False
        box_6CE27.enabled = True
        box_6CE27.active = True
        box_6CE27.use_property_split = False
        box_6CE27.use_property_decorate = False
        box_6CE27.alignment = 'Expand'.upper()
        box_6CE27.scale_x = 1.0
        box_6CE27.scale_y = 1.0
        if not True: box_6CE27.operator_context = "EXEC_DEFAULT"
        col_93F6A = box_6CE27.column(heading='', align=True)
        col_93F6A.alert = False
        col_93F6A.enabled = True
        col_93F6A.active = True
        col_93F6A.use_property_split = False
        col_93F6A.use_property_decorate = False
        col_93F6A.scale_x = 1.0
        col_93F6A.scale_y = 1.0
        col_93F6A.alignment = 'Expand'.upper()
        col_93F6A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_DC7B0 = col_93F6A.split(factor=0.5, align=True)
        split_DC7B0.alert = False
        split_DC7B0.enabled = True
        split_DC7B0.active = True
        split_DC7B0.use_property_split = False
        split_DC7B0.use_property_decorate = False
        split_DC7B0.scale_x = 1.0
        split_DC7B0.scale_y = 1.0
        split_DC7B0.alignment = 'Expand'.upper()
        if not True: split_DC7B0.operator_context = "EXEC_DEFAULT"
        col_2878F = split_DC7B0.column(heading='', align=True)
        col_2878F.alert = False
        col_2878F.enabled = True
        col_2878F.active = True
        col_2878F.use_property_split = False
        col_2878F.use_property_decorate = False
        col_2878F.scale_x = 1.0
        col_2878F.scale_y = 2.0
        col_2878F.alignment = 'Expand'.upper()
        col_2878F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_353A3 = col_2878F.row(heading='', align=True)
        row_353A3.alert = False
        row_353A3.enabled = True
        row_353A3.active = True
        row_353A3.use_property_split = False
        row_353A3.use_property_decorate = False
        row_353A3.scale_x = 1.0
        row_353A3.scale_y = 1.0
        row_353A3.alignment = 'Expand'.upper()
        row_353A3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_353A3.operator('sna.uv__783fd', text='x0.5', icon_value=string_to_icon('DOT'), emboss=True, depress=False)
        op.sna_size = (0.5, 0.5)
        op = row_353A3.operator('sna.uv__783fd', text='x2', icon_value=string_to_icon('RADIOBUT_ON'), emboss=True, depress=False)
        op.sna_size = (2.0, 2.0)
        split_B9B6A = split_DC7B0.split(factor=0.20000000298023224, align=True)
        split_B9B6A.alert = False
        split_B9B6A.enabled = True
        split_B9B6A.active = True
        split_B9B6A.use_property_split = False
        split_B9B6A.use_property_decorate = False
        split_B9B6A.scale_x = 1.0
        split_B9B6A.scale_y = 1.0
        split_B9B6A.alignment = 'Expand'.upper()
        if not True: split_B9B6A.operator_context = "EXEC_DEFAULT"
        col_29F82 = split_B9B6A.column(heading='', align=True)
        col_29F82.alert = False
        col_29F82.enabled = False
        col_29F82.active = False
        col_29F82.use_property_split = False
        col_29F82.use_property_decorate = False
        col_29F82.scale_x = 1.0
        col_29F82.scale_y = 1.0
        col_29F82.alignment = 'Expand'.upper()
        col_29F82.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_29F82.operator('sn.dummy_button_operator', text='平', icon_value=0, emboss=False, depress=False)
        op = col_29F82.operator('sn.dummy_button_operator', text='竖', icon_value=0, emboss=False, depress=False)
        col_27F48 = split_B9B6A.column(heading='', align=True)
        col_27F48.alert = False
        col_27F48.enabled = True
        col_27F48.active = True
        col_27F48.use_property_split = False
        col_27F48.use_property_decorate = False
        col_27F48.scale_x = 1.0
        col_27F48.scale_y = 1.0
        col_27F48.alignment = 'Expand'.upper()
        col_27F48.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_B85B8 = col_27F48.row(heading='', align=True)
        row_B85B8.alert = False
        row_B85B8.enabled = True
        row_B85B8.active = True
        row_B85B8.use_property_split = False
        row_B85B8.use_property_decorate = False
        row_B85B8.scale_x = 1.0
        row_B85B8.scale_y = 1.0
        row_B85B8.alignment = 'Expand'.upper()
        row_B85B8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_B85B8.operator('sna.uv__783fd', text='x0.5', icon_value=0, emboss=True, depress=False)
        op.sna_size = (0.5, 1.0)
        op = row_B85B8.operator('sna.uv__783fd', text='x2', icon_value=0, emboss=True, depress=False)
        op.sna_size = (2.0, 1.0)
        row_5357C = col_27F48.row(heading='', align=True)
        row_5357C.alert = False
        row_5357C.enabled = True
        row_5357C.active = True
        row_5357C.use_property_split = False
        row_5357C.use_property_decorate = False
        row_5357C.scale_x = 1.0
        row_5357C.scale_y = 1.0
        row_5357C.alignment = 'Expand'.upper()
        row_5357C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_5357C.operator('sna.uv__783fd', text='x0.5', icon_value=0, emboss=True, depress=False)
        op.sna_size = (1.0, 0.5)
        op = row_5357C.operator('sna.uv__783fd', text='x2', icon_value=0, emboss=True, depress=False)
        op.sna_size = (1.0, 2.0)
        col_7C02F = col_93F6A.column(heading='', align=True)
        col_7C02F.alert = False
        col_7C02F.enabled = True
        col_7C02F.active = True
        col_7C02F.use_property_split = False
        col_7C02F.use_property_decorate = False
        col_7C02F.scale_x = 1.0
        col_7C02F.scale_y = 1.0
        col_7C02F.alignment = 'Expand'.upper()
        col_7C02F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_7C02F.prop(bpy.context.scene, 'sna_uv_size_mode', text='高级', icon_value=0, emboss=True)
        if bpy.context.scene.sna_uv_size_mode:
            col_412AB = col_7C02F.column(heading='', align=True)
            col_412AB.alert = False
            col_412AB.enabled = True
            col_412AB.active = True
            col_412AB.use_property_split = False
            col_412AB.use_property_decorate = False
            col_412AB.scale_x = 1.0
            col_412AB.scale_y = 1.0
            col_412AB.alignment = 'Expand'.upper()
            col_412AB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            row_9F8E4 = col_412AB.row(heading='', align=True)
            row_9F8E4.alert = False
            row_9F8E4.enabled = True
            row_9F8E4.active = True
            row_9F8E4.use_property_split = False
            row_9F8E4.use_property_decorate = False
            row_9F8E4.scale_x = 1.0
            row_9F8E4.scale_y = 1.0
            row_9F8E4.alignment = 'Expand'.upper()
            row_9F8E4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            row_9F8E4.prop(bpy.context.scene, 'sna_uv_size_coordinate', text='原点位置', icon_value=0, emboss=True)
            col_412AB.separator(factor=1.0)
            split_D6686 = col_412AB.split(factor=0.5, align=True)
            split_D6686.alert = False
            split_D6686.enabled = True
            split_D6686.active = True
            split_D6686.use_property_split = False
            split_D6686.use_property_decorate = False
            split_D6686.scale_x = 1.0
            split_D6686.scale_y = 1.0
            split_D6686.alignment = 'Expand'.upper()
            if not True: split_D6686.operator_context = "EXEC_DEFAULT"
            col_1A7CD = split_D6686.column(heading='', align=True)
            col_1A7CD.alert = False
            col_1A7CD.enabled = True
            col_1A7CD.active = True
            col_1A7CD.use_property_split = False
            col_1A7CD.use_property_decorate = False
            col_1A7CD.scale_x = 1.0
            col_1A7CD.scale_y = 2.0
            col_1A7CD.alignment = 'Expand'.upper()
            col_1A7CD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_1A7CD.operator('sna.uv__783fd', text='自定义缩放', icon_value=0, emboss=True, depress=False)
            op.sna_size = bpy.context.scene.sna_uv_size
            split_D6686.prop(bpy.context.scene, 'sna_uv_size', text='', icon_value=0, emboss=True)
        box_BB93D = col_3B1BA.box()
        box_BB93D.alert = False
        box_BB93D.enabled = True
        box_BB93D.active = True
        box_BB93D.use_property_split = False
        box_BB93D.use_property_decorate = False
        box_BB93D.alignment = 'Expand'.upper()
        box_BB93D.scale_x = 1.0
        box_BB93D.scale_y = 1.0
        if not True: box_BB93D.operator_context = "EXEC_DEFAULT"
        split_EF950 = box_BB93D.split(factor=0.5, align=True)
        split_EF950.alert = False
        split_EF950.enabled = True
        split_EF950.active = True
        split_EF950.use_property_split = False
        split_EF950.use_property_decorate = False
        split_EF950.scale_x = 1.0
        split_EF950.scale_y = 1.0
        split_EF950.alignment = 'Expand'.upper()
        if not True: split_EF950.operator_context = "EXEC_DEFAULT"
        split_D5971 = split_EF950.split(factor=0.5, align=True)
        split_D5971.alert = False
        split_D5971.enabled = True
        split_D5971.active = True
        split_D5971.use_property_split = False
        split_D5971.use_property_decorate = False
        split_D5971.scale_x = 1.0
        split_D5971.scale_y = 1.0
        split_D5971.alignment = 'Expand'.upper()
        if not True: split_D5971.operator_context = "EXEC_DEFAULT"
        op = split_D5971.operator('sna.uv__8beae', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'flip_x.png')), emboss=True, depress=False)
        op.sna_xy = 'X'
        op = split_D5971.operator('sna.uv__8beae', text='', icon_value=load_preview_icon(os.path.join(bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons')),'flip_y.png')), emboss=True, depress=False)
        op.sna_xy = 'Y'
        split_EF950.prop(bpy.context.scene, 'sna_uv_flip_mode', text='整体', icon_value=0, emboss=True)


class SNA_PT_uv_mapping_35A7A(bpy.types.Panel):
    bl_label = '排布'
    bl_idname = 'SNA_PT_uv_mapping_35A7A'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 8
    bl_parent_id = 'SNA_PT_QKK_UV_37C20'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_ED98B = layout.column(heading='', align=True)
        col_ED98B.alert = False
        col_ED98B.enabled = 'EDIT_MESH'==bpy.context.mode
        col_ED98B.active = True
        col_ED98B.use_property_split = False
        col_ED98B.use_property_decorate = False
        col_ED98B.scale_x = 1.0
        col_ED98B.scale_y = 1.0
        col_ED98B.alignment = 'Expand'.upper()
        col_ED98B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        box_E9037 = col_ED98B.box()
        box_E9037.alert = False
        box_E9037.enabled = True
        box_E9037.active = True
        box_E9037.use_property_split = False
        box_E9037.use_property_decorate = False
        box_E9037.alignment = 'Expand'.upper()
        box_E9037.scale_x = 1.0
        box_E9037.scale_y = 1.0
        if not True: box_E9037.operator_context = "EXEC_DEFAULT"
        col_26926 = box_E9037.column(heading='', align=True)
        col_26926.alert = False
        col_26926.enabled = True
        col_26926.active = True
        col_26926.use_property_split = False
        col_26926.use_property_decorate = False
        col_26926.scale_x = 1.0
        col_26926.scale_y = 1.0
        col_26926.alignment = 'Expand'.upper()
        col_26926.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_D8E3B = col_26926.split(factor=0.800000011920929, align=True)
        split_D8E3B.alert = False
        split_D8E3B.enabled = True
        split_D8E3B.active = True
        split_D8E3B.use_property_split = False
        split_D8E3B.use_property_decorate = False
        split_D8E3B.scale_x = 1.0
        split_D8E3B.scale_y = 1.0
        split_D8E3B.alignment = 'Expand'.upper()
        if not True: split_D8E3B.operator_context = "EXEC_DEFAULT"
        split_14A9B = split_D8E3B.split(factor=0.5, align=True)
        split_14A9B.alert = False
        split_14A9B.enabled = True
        split_14A9B.active = True
        split_14A9B.use_property_split = False
        split_14A9B.use_property_decorate = False
        split_14A9B.scale_x = 1.0
        split_14A9B.scale_y = 1.0
        split_14A9B.alignment = 'Expand'.upper()
        if not True: split_14A9B.operator_context = "EXEC_DEFAULT"
        col_8AB62 = split_14A9B.column(heading='', align=True)
        col_8AB62.alert = False
        col_8AB62.enabled = True
        col_8AB62.active = True
        col_8AB62.use_property_split = False
        col_8AB62.use_property_decorate = False
        col_8AB62.scale_x = 1.0
        col_8AB62.scale_y = 2.0
        col_8AB62.alignment = 'Expand'.upper()
        col_8AB62.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_6F7D4 = col_8AB62.split(factor=0.5, align=True)
        split_6F7D4.alert = False
        split_6F7D4.enabled = True
        split_6F7D4.active = True
        split_6F7D4.use_property_split = False
        split_6F7D4.use_property_decorate = False
        split_6F7D4.scale_x = 1.0
        split_6F7D4.scale_y = 1.0
        split_6F7D4.alignment = 'Expand'.upper()
        if not True: split_6F7D4.operator_context = "EXEC_DEFAULT"
        op = split_6F7D4.operator('sna.uvpackmaster_edf0d', text='打包', icon_value=0, emboss=True, depress=False)
        op.sna_pack_to_others = False
        op = split_6F7D4.operator('sna.uvpackmaster_edf0d', text='插入', icon_value=0, emboss=True, depress=False)
        op.sna_pack_to_others = True
        col_B42E9 = split_14A9B.column(heading='', align=True)
        col_B42E9.alert = False
        col_B42E9.enabled = True
        col_B42E9.active = True
        col_B42E9.use_property_split = False
        col_B42E9.use_property_decorate = False
        col_B42E9.scale_x = 1.0
        col_B42E9.scale_y = 1.0
        col_B42E9.alignment = 'Expand'.upper()
        col_B42E9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_B42E9.prop(bpy.context.scene, 'sna_uv_tex_overflow', text='溢出', icon_value=0, emboss=True)
        col_B42E9.prop(bpy.context.scene, 'sna_uv_tex_size', text='尺寸', icon_value=0, emboss=True)
        col_73123 = split_D8E3B.column(heading='', align=True)
        col_73123.alert = False
        col_73123.enabled = True
        col_73123.active = True
        col_73123.use_property_split = False
        col_73123.use_property_decorate = False
        col_73123.scale_x = 1.0
        col_73123.scale_y = 1.0
        col_73123.alignment = 'Expand'.upper()
        col_73123.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_73123.operator('uv.univ_sort', text='排序', icon_value=0, emboss=True, depress=False)
        op.padding = float(bpy.context.scene.sna_uv_tex_overflow / bpy.context.scene.sna_uv_tex_size)
        op = col_73123.operator('uv.univ_random', text='随机', icon_value=0, emboss=True, depress=False)
        row_19DEE = col_26926.row(heading='', align=True)
        row_19DEE.alert = False
        row_19DEE.enabled = True
        row_19DEE.active = True
        row_19DEE.use_property_split = False
        row_19DEE.use_property_decorate = False
        row_19DEE.scale_x = 1.0
        row_19DEE.scale_y = 1.0
        row_19DEE.alignment = 'Expand'.upper()
        row_19DEE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_19DEE.prop(bpy.context.scene.uvpm3_props.default_main_props, 'rotation_enable', text='锁定旋转', icon_value=0, emboss=True, invert_checkbox=True)
        row_19DEE.prop(bpy.context.scene.uvpm3_props.default_main_props, 'lock_overlapping_enable', text='锁定堆叠', icon_value=0, emboss=True)
        row_19DEE.prop(bpy.context.scene.uvpm3_props.default_main_props, 'precision', text='精度', icon_value=0, emboss=True)
        box_59833 = col_ED98B.box()
        box_59833.alert = False
        box_59833.enabled = True
        box_59833.active = True
        box_59833.use_property_split = False
        box_59833.use_property_decorate = False
        box_59833.alignment = 'Expand'.upper()
        box_59833.scale_x = 1.0
        box_59833.scale_y = 1.0
        if not True: box_59833.operator_context = "EXEC_DEFAULT"
        split_893C6 = box_59833.split(factor=0.5, align=True)
        split_893C6.alert = False
        split_893C6.enabled = True
        split_893C6.active = True
        split_893C6.use_property_split = False
        split_893C6.use_property_decorate = False
        split_893C6.scale_x = 1.0
        split_893C6.scale_y = 1.0
        split_893C6.alignment = 'Expand'.upper()
        if not True: split_893C6.operator_context = "EXEC_DEFAULT"
        split_907DE = split_893C6.split(factor=0.30000001192092896, align=True)
        split_907DE.alert = False
        split_907DE.enabled = True
        split_907DE.active = True
        split_907DE.use_property_split = False
        split_907DE.use_property_decorate = False
        split_907DE.scale_x = 1.0
        split_907DE.scale_y = 1.0
        split_907DE.alignment = 'Expand'.upper()
        if not True: split_907DE.operator_context = "EXEC_DEFAULT"
        op = split_907DE.operator('sna.my_generic_operator_df204', text='', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)
        op.sna_select = False
        op = split_907DE.operator('uv.pin', text='钉', icon_value=string_to_icon('PINNED'), emboss=True, depress=False)
        op.clear = False
        op.invert = False
        split_30952 = split_893C6.split(factor=0.30000001192092896, align=True)
        split_30952.alert = False
        split_30952.enabled = True
        split_30952.active = True
        split_30952.use_property_split = False
        split_30952.use_property_decorate = False
        split_30952.scale_x = 1.0
        split_30952.scale_y = 1.0
        split_30952.alignment = 'Expand'.upper()
        if not True: split_30952.operator_context = "EXEC_DEFAULT"
        op = split_30952.operator('sna.my_generic_operator_df204', text='', icon_value=string_to_icon('RESTRICT_SELECT_ON'), emboss=True, depress=False)
        op.sna_select = True
        op = split_30952.operator('uv.pin', text='解', icon_value=string_to_icon('UNPINNED'), emboss=True, depress=False)
        op.clear = True
        op.invert = False
        box_376DE = col_ED98B.box()
        box_376DE.alert = False
        box_376DE.enabled = True
        box_376DE.active = True
        box_376DE.use_property_split = False
        box_376DE.use_property_decorate = False
        box_376DE.alignment = 'Expand'.upper()
        box_376DE.scale_x = 1.0
        box_376DE.scale_y = 1.0
        if not True: box_376DE.operator_context = "EXEC_DEFAULT"
        row_E9BFD = box_376DE.row(heading='', align=True)
        row_E9BFD.alert = False
        row_E9BFD.enabled = True
        row_E9BFD.active = True
        row_E9BFD.use_property_split = False
        row_E9BFD.use_property_decorate = False
        row_E9BFD.scale_x = 1.0
        row_E9BFD.scale_y = 1.2000000476837158
        row_E9BFD.alignment = 'Expand'.upper()
        row_E9BFD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_E9BFD.operator('uv.univ_texel_density_get', text='获取', icon_value=0, emboss=True, depress=False)
        op = row_E9BFD.operator('uv.univ_texel_density_set', text='设置', icon_value=0, emboss=True, depress=False)
        row_E9BFD.prop(bpy.context.scene.univ_settings, 'texel_density', text='', icon_value=0, emboss=True)
        op = row_E9BFD.operator('uv.univ_select_texel_density', text='', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)
        row_E9BFD.prop(bpy.context.scene, 'sna_uv_precision_size', text='', icon_value=0, emboss=True)
        box_7F4C8 = col_ED98B.box()
        box_7F4C8.alert = False
        box_7F4C8.enabled = True
        box_7F4C8.active = True
        box_7F4C8.use_property_split = False
        box_7F4C8.use_property_decorate = False
        box_7F4C8.alignment = 'Expand'.upper()
        box_7F4C8.scale_x = 1.0
        box_7F4C8.scale_y = 1.0
        if not True: box_7F4C8.operator_context = "EXEC_DEFAULT"
        col_C9BFB = box_7F4C8.column(heading='', align=True)
        col_C9BFB.alert = False
        col_C9BFB.enabled = True
        col_C9BFB.active = True
        col_C9BFB.use_property_split = False
        col_C9BFB.use_property_decorate = False
        col_C9BFB.scale_x = 1.0
        col_C9BFB.scale_y = 1.0
        col_C9BFB.alignment = 'Expand'.upper()
        col_C9BFB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_FF09A = col_C9BFB.split(factor=0.5, align=True)
        split_FF09A.alert = False
        split_FF09A.enabled = True
        split_FF09A.active = True
        split_FF09A.use_property_split = False
        split_FF09A.use_property_decorate = False
        split_FF09A.scale_x = 1.0
        split_FF09A.scale_y = 1.0
        split_FF09A.alignment = 'Expand'.upper()
        if not True: split_FF09A.operator_context = "EXEC_DEFAULT"
        op = split_FF09A.operator('uv.univ_crop', text='缩放', icon_value=0, emboss=True, depress=False)
        op.axis = 'XY'
        op.inplace = False
        split_E96A8 = split_FF09A.split(factor=0.5, align=True)
        split_E96A8.alert = False
        split_E96A8.enabled = True
        split_E96A8.active = True
        split_E96A8.use_property_split = False
        split_E96A8.use_property_decorate = False
        split_E96A8.scale_x = 1.0
        split_E96A8.scale_y = 1.0
        split_E96A8.alignment = 'Expand'.upper()
        if not True: split_E96A8.operator_context = "EXEC_DEFAULT"
        op = split_E96A8.operator('uv.univ_crop', text='宽', icon_value=0, emboss=True, depress=False)
        op.axis = 'X'
        op.inplace = False
        op = split_E96A8.operator('uv.univ_crop', text='高', icon_value=0, emboss=True, depress=False)
        op.axis = 'Y'
        op.inplace = False
        split_FB2BB = col_C9BFB.split(factor=0.5, align=True)
        split_FB2BB.alert = False
        split_FB2BB.enabled = True
        split_FB2BB.active = True
        split_FB2BB.use_property_split = False
        split_FB2BB.use_property_decorate = False
        split_FB2BB.scale_x = 1.0
        split_FB2BB.scale_y = 1.0
        split_FB2BB.alignment = 'Expand'.upper()
        if not True: split_FB2BB.operator_context = "EXEC_DEFAULT"
        op = split_FB2BB.operator('uv.univ_fill', text='拉伸', icon_value=0, emboss=True, depress=False)
        op.axis = 'XY'
        op.inplace = False
        split_D436C = split_FB2BB.split(factor=0.5, align=True)
        split_D436C.alert = False
        split_D436C.enabled = True
        split_D436C.active = True
        split_D436C.use_property_split = False
        split_D436C.use_property_decorate = False
        split_D436C.scale_x = 1.0
        split_D436C.scale_y = 1.0
        split_D436C.alignment = 'Expand'.upper()
        if not True: split_D436C.operator_context = "EXEC_DEFAULT"
        op = split_D436C.operator('uv.univ_fill', text='宽', icon_value=0, emboss=True, depress=False)
        op.axis = 'X'
        op.inplace = False
        op = split_D436C.operator('uv.univ_fill', text='高', icon_value=0, emboss=True, depress=False)
        op.axis = 'Y'
        op.inplace = False


class SNA_PT_panel_58EF1(bpy.types.Panel):
    bl_label = '选择'
    bl_idname = 'SNA_PT_panel_58EF1'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 10
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_QKK_UV_37C20'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        grid_FD464 = layout.grid_flow(columns=2, row_major=True, even_columns=False, even_rows=False, align=True)
        grid_FD464.enabled = 'EDIT_MESH'==bpy.context.mode
        grid_FD464.active = True
        grid_FD464.use_property_split = False
        grid_FD464.use_property_decorate = False
        grid_FD464.alignment = 'Expand'.upper()
        grid_FD464.scale_x = 1.0
        grid_FD464.scale_y = 1.0
        if not True: grid_FD464.operator_context = "EXEC_DEFAULT"
        op = grid_FD464.operator('uv.zenuv_select_uv_borders', text='孤岛边', icon_value=0, emboss=True, depress=False)
        op.clear_selection = True
        op.mode = 'ALL_ISLANDS'
        op = grid_FD464.operator('mesh.zenuv_select_seams', text='缝合边', icon_value=0, emboss=True, depress=False)
        op.clear_selection = True
        op.mode = 'SELECT'
        op = grid_FD464.operator('sna.my_generic_operator_df204', text='钉住', icon_value=0, emboss=True, depress=False)
        op.sna_select = False
        op = grid_FD464.operator('sna.my_generic_operator_df204', text='未钉住', icon_value=0, emboss=True, depress=False)
        op.sna_select = True
        op = grid_FD464.operator('uv.select_overlap', text='重叠', icon_value=0, emboss=True, depress=False)
        op.extend = False
        op = grid_FD464.operator('uv.univ_check_overlap', text='堆叠', icon_value=0, emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_uv_rotation_angle = bpy.props.FloatProperty(name='uv_rotation_angle', description='', default=90.0, subtype='NONE', unit='NONE', min=0.0, max=360.0, step=1, precision=2)
    bpy.types.Scene.sna_uv_rotation_mode = bpy.props.BoolProperty(name='uv_rotation_mode', description='', default=False)
    bpy.types.Scene.sna_uv_move_size = bpy.props.FloatProperty(name='uv_move_size', description='', default=1.0, subtype='NONE', unit='NONE', min=0.0, max=6.0, step=1, precision=2)
    bpy.types.Scene.sna_uv_size = bpy.props.FloatVectorProperty(name='uv_size', description='', size=2, default=(2.0, 2.0), subtype='NONE', unit='NONE', min=0.0, max=4.0, step=1, precision=2)
    bpy.types.Scene.sna_uv_size_mode = bpy.props.BoolProperty(name='uv_size_mode', description='', default=False)
    bpy.types.Scene.sna_uv_size_coordinate = bpy.props.FloatVectorProperty(name='uv_size_coordinate', description='', size=2, default=(0.0, 0.0), subtype='NONE', unit='NONE', soft_min=0.0, soft_max=1.0, step=1, precision=2)
    bpy.types.Scene.sna_uv_flip_mode = bpy.props.BoolProperty(name='uv_flip_mode', description='', default=False)
    bpy.types.Scene.sna_uv_tex_size = bpy.props.IntProperty(name='uv_tex_size', description='', default=1024, subtype='PIXEL', soft_min=64, soft_max=8192)
    bpy.types.Scene.sna_uv_tex_overflow = bpy.props.IntProperty(name='uv_tex_overflow', description='', default=16, subtype='PIXEL', min=0, soft_max=64)
    bpy.types.Scene.sna_uv_precision_size = bpy.props.EnumProperty(name='uv_precision_size', description='', items=[('256', '256', '', 0, 0), ('512', '512', '', 0, 1), ('1024', '1024', '', 0, 2), ('2048', '2048', '', 0, 3), ('4096', '4096', '', 0, 4), ('8192', '8192', '', 0, 5)], update=sna_update_sna_uv_precision_size_DD959)
    bpy.types.Scene.sna_uv_xy_tex = bpy.props.EnumProperty(name='uv_xy_tex', description='', items=[('256', '256', '', 0, 0), ('512', '512', '', 0, 1), ('1024', '1024', '', 0, 2), ('2048', '2048', '', 0, 3), ('4096', '4096', '', 0, 4), ('8192', '8192', '', 0, 5)])
    bpy.utils.register_class(SNA_PT_QKK_UV_37C20)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Aa4B9)
    bpy.utils.register_class(SNA_AddonPreferences_7C44E)
    bpy.types.VIEW3D_HT_tool_header.prepend(sna_add_to_view3d_ht_tool_header_E8E60)
    bpy.utils.register_class(SNA_OT_Uv_36619)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_0475F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E955E)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_4609D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_02E18)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_34Cdd)
    bpy.utils.register_class(SNA_OT_Uv_94Eb3)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E4775)
    bpy.utils.register_class(SNA_PT_UV_MOVE_SIZE_D3E66)
    bpy.utils.register_class(SNA_OT_Uv__Ca81B)
    bpy.utils.register_class(SNA_OT_Uv__783Fd)
    bpy.utils.register_class(SNA_OT_Uv__8Beae)
    bpy.utils.register_class(SNA_OT_Uv__B75E5)
    bpy.utils.register_class(SNA_PT_uv_quadrant_edge_alignment_4DA3C)
    bpy.utils.register_class(SNA_OT_Uv__Adfc0)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Df204)
    bpy.utils.register_class(SNA_OT_Uvpackmaster_Edf0D)
    bpy.utils.register_class(SNA_OT_Uv_236E2)
    bpy.utils.register_class(SNA_OT_D_8A15D)
    bpy.types.IMAGE_PT_tools_active.append(sna_add_to_image_pt_tools_active_801BA)
    bpy.utils.register_class(SNA_OT_Uv_4653D)
    bpy.utils.register_class(SNA_MT_4A729)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_8A716)
    bpy.utils.register_class(SNA_OT_Qkk_Uv_Loop_78D8A)
    bpy.utils.register_class(SNA_OT_Qkk_Uv_Cut_26D51)
    bpy.utils.register_class(SNA_OT_Qkk_Uv_Drag_99763)
    bpy.utils.register_class(SNA_OT_Qkk_Uv_Snap_87237)
    bpy.utils.register_class(SNA_OT_Qkk_Uv_Weld_F659B)
    bpy.utils.register_class(SNA_OT_Qkk_Uv_Sewing_Aad37)
    bpy.utils.register_class(SNA_OT_Qkk_Uv_Select_Islands_F84C9)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D5090)
    bpy.utils.register_class(SNA_OT_Uv_3Dcut_5F763)
    bpy.utils.register_class(SNA_OT_Uv_3Dtitch_6Ef3A)
    bpy.utils.register_class(SNA_PT_unfold_1DDC1)
    bpy.utils.register_class(SNA_PT_uv_conversion_1F7BD)
    bpy.utils.register_class(SNA_PT_uv_mapping_35A7A)
    bpy.utils.register_class(SNA_PT_panel_58EF1)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_MT_4A729'
    addon_keymaps['4B596'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('sna.qkk_uv_loop_78d8a', 'A', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.sna_new_property = False
    addon_keymaps['DD8AE'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('sna.qkk_uv_select_islands_f84c9', 'LEFTMOUSE', 'DOUBLE_CLICK',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['FEF90'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('sna.qkk_uv_cut_26d51', 'C', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['35AE2'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('sna.qkk_uv_drag_99763', 'LEFTMOUSE', 'ANY',
        ctrl=False, alt=True, shift=False, repeat=False)
    addon_keymaps['6A496'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('sna.qkk_uv_snap_87237', 'V', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['B16F8'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('sna.qkk_uv_weld_f659b', 'X', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['9ECB8'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('sna.qkk_uv_sewing_aad37', 'I', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['73739'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('sna.qkk_uv_loop_78d8a', 'A', 'PRESS',
        ctrl=False, alt=False, shift=True, repeat=False)
    kmi.properties.sna_new_property = True
    addon_keymaps['3AED7'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.uv_3dcut_5f763', 'C', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['4C71E'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('sna.uv_3dtitch_6ef3a', 'C', 'DOUBLE_CLICK',
        ctrl=False, alt=False, shift=False, repeat=False)
    addon_keymaps['5C538'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_uv_xy_tex
    del bpy.types.Scene.sna_uv_precision_size
    del bpy.types.Scene.sna_uv_tex_overflow
    del bpy.types.Scene.sna_uv_tex_size
    del bpy.types.Scene.sna_uv_flip_mode
    del bpy.types.Scene.sna_uv_size_coordinate
    del bpy.types.Scene.sna_uv_size_mode
    del bpy.types.Scene.sna_uv_size
    del bpy.types.Scene.sna_uv_move_size
    del bpy.types.Scene.sna_uv_rotation_mode
    del bpy.types.Scene.sna_uv_rotation_angle
    bpy.utils.unregister_class(SNA_PT_QKK_UV_37C20)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Aa4B9)
    bpy.utils.unregister_class(SNA_AddonPreferences_7C44E)
    bpy.types.VIEW3D_HT_tool_header.remove(sna_add_to_view3d_ht_tool_header_E8E60)
    bpy.utils.unregister_class(SNA_OT_Uv_36619)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_0475F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E955E)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_4609D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_02E18)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_34Cdd)
    bpy.utils.unregister_class(SNA_OT_Uv_94Eb3)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E4775)
    bpy.utils.unregister_class(SNA_PT_UV_MOVE_SIZE_D3E66)
    bpy.utils.unregister_class(SNA_OT_Uv__Ca81B)
    bpy.utils.unregister_class(SNA_OT_Uv__783Fd)
    bpy.utils.unregister_class(SNA_OT_Uv__8Beae)
    bpy.utils.unregister_class(SNA_OT_Uv__B75E5)
    bpy.utils.unregister_class(SNA_PT_uv_quadrant_edge_alignment_4DA3C)
    bpy.utils.unregister_class(SNA_OT_Uv__Adfc0)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Df204)
    bpy.utils.unregister_class(SNA_OT_Uvpackmaster_Edf0D)
    bpy.utils.unregister_class(SNA_OT_Uv_236E2)
    bpy.utils.unregister_class(SNA_OT_D_8A15D)
    bpy.types.IMAGE_PT_tools_active.remove(sna_add_to_image_pt_tools_active_801BA)
    bpy.utils.unregister_class(SNA_OT_Uv_4653D)
    bpy.utils.unregister_class(SNA_MT_4A729)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_8A716)
    bpy.utils.unregister_class(SNA_OT_Qkk_Uv_Loop_78D8A)
    bpy.utils.unregister_class(SNA_OT_Qkk_Uv_Cut_26D51)
    bpy.utils.unregister_class(SNA_OT_Qkk_Uv_Drag_99763)
    bpy.utils.unregister_class(SNA_OT_Qkk_Uv_Snap_87237)
    bpy.utils.unregister_class(SNA_OT_Qkk_Uv_Weld_F659B)
    bpy.utils.unregister_class(SNA_OT_Qkk_Uv_Sewing_Aad37)
    bpy.utils.unregister_class(SNA_OT_Qkk_Uv_Select_Islands_F84C9)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D5090)
    if handler_0C8CE:
        bpy.types.SpaceImageEditor.draw_handler_remove(handler_0C8CE[0], 'WINDOW')
        handler_0C8CE.pop(0)
    bpy.utils.unregister_class(SNA_OT_Uv_3Dcut_5F763)
    bpy.utils.unregister_class(SNA_OT_Uv_3Dtitch_6Ef3A)
    bpy.utils.unregister_class(SNA_PT_unfold_1DDC1)
    bpy.utils.unregister_class(SNA_PT_uv_conversion_1F7BD)
    bpy.utils.unregister_class(SNA_PT_uv_mapping_35A7A)
    bpy.utils.unregister_class(SNA_PT_panel_58EF1)
