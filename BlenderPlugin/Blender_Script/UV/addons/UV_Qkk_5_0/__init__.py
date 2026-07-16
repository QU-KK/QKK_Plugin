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
    "name" : "UV_Qkk_5_1",
    "author" : "QKK", 
    "description" : "qkkUV工具",
    "blender" : (5, 0, 1),
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
uv_004 = {'sna_draw_mode_uv': 'NONE', }
node_tree = {'sna_keyboard_shortcuts_explanation': False, }


def get_id_preview_id(data):
    if hasattr(data, "preview"):
        if not data.preview:
            data.preview_ensure()
        if hasattr(data.preview, "icon_id"):
            return data.preview.icon_id
    return 0


handler_0C8CE = []
class SNA_PT_QKK_UV_F373B(bpy.types.Panel):
    bl_label = 'QKK_UV'
    bl_idname = 'SNA_PT_QKK_UV_F373B'
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
        split_50CE9 = layout.split(factor=0.5, align=True)
        split_50CE9.alert = False
        split_50CE9.enabled = 'EDIT_MESH'==bpy.context.mode
        split_50CE9.active = True
        split_50CE9.use_property_split = False
        split_50CE9.use_property_decorate = False
        split_50CE9.scale_x = 1.0
        split_50CE9.scale_y = 1.2000000476837158
        split_50CE9.alignment = 'Expand'.upper()
        if not True: split_50CE9.operator_context = "EXEC_DEFAULT"
        op = split_50CE9.operator('sna.uv_36619', text='3D-UV 同步', icon_value=string_to_icon('MESH_CUBE'), emboss=True, depress=bpy.context.scene.tool_settings.use_uv_select_sync)
        op.sna_model = True
        op = split_50CE9.operator('sna.uv_36619', text='UV', icon_value=string_to_icon('MOD_MULTIRES'), emboss=True, depress=(not bpy.context.scene.tool_settings.use_uv_select_sync))
        op.sna_model = False


def sna_add_to_view3d_ht_tool_header_A112F(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('wm.univ_split_uv_toggle', text='', icon_value=string_to_icon('MOD_UVPROJECT'), emboss=True, depress=False)
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
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            bpy.ops.uv.select_all(action='SELECT')
        bpy.context.scene.tool_settings.use_uv_select_sync = self.sna_model
        bpy.ops.uv.select_all(action='DESELECT')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_92E7D(bpy.types.Operator):
    bl_idname = "sna.uv_92e7d"
    bl_label = "UV操作"
    bl_description = "UV操作"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        # 创建

        def univ_normal():
            bpy.ops.mesh.univ_normal(crop=True, orient=True, individual=False, mark_seam=True, use_correct_aspect=True)
        # 松弛

        def univ_relax():
            bpy.ops.uv.univ_relax(use_correct_aspect=True, legacy=False)
        # 展开

        def univ_unwrap():
            bpy.ops.uv.univ_unwrap(unwrap='ANGLE_BASED', unwrap_along='UV', blend_factor=1.0, mark_seam_inner_island=True, use_correct_aspect=True)
        # 平均

        def univ_adjust_td():
            bpy.ops.uv.univ_adjust_td(lock_overlap=False, shear=False, xy_scale=True, use_aspect=True)
        # 3D平均

        def univ_normalize():
            bpy.ops.uv.univ_normalize(lock_overlap=False, shear=False, xy_scale=True, use_aspect=True)
        # 拉直

        def univ_quadrify():
            bpy.ops.uv.univ_quadrify(shear=False, xy_scale=True, use_aspect=True)
        # 4点拉直

        def univ_rectify():
            if bpy.context.scene.tool_settings.use_uv_select_sync:
                pass
            else:
                bpy.ops.uv.univ_rectify(xy_scale=True, user_boundary_priority_factor=1, use_aspect=True)
        # 切开

        def univ_cut():
            bpy.ops.uv.univ_cut(addition=False, unwrap='NONE')
        # 缝合焊接

        def univ_weld():
            bpy.ops.uv.univ_weld(use_by_distance=False, distance=0.0, use_aspect=True)
        # 调用函数
        functions = {
            "univ_normal": univ_normal,  #创建
            "univ_relax": univ_relax,  #松弛
            "univ_unwrap": univ_unwrap,  #展开
            "univ_adjust_td": univ_adjust_td,  #平均
            "univ_normalize": univ_normalize,  #3D平均
            "univ_quadrify": univ_quadrify,  #拉直
            "univ_rectify": univ_rectify,  #4点拉直
            "univ_cut": univ_cut,  #切开
            "univ_weld": univ_weld,  #缝合焊接
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_E4775(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e4775"
    bl_label = "移动设置"
    bl_description = "移动设置"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_UV_MOVE_SIZE_F4130", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_UV_MOVE_SIZE_F4130(bpy.types.Panel):
    bl_label = 'uv_move_size'
    bl_idname = 'SNA_PT_UV_MOVE_SIZE_F4130'
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
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_direction: bpy.props.StringProperty(name='direction', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        uv_direction = self.sna_direction
        # 自动定向

        def univ_orient():
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='BOTH', use_correct_aspect=True)

        def univ_orient_x(): #水平
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='HORIZONTAL', use_correct_aspect=True)

        def univ_orient_y(): #垂直
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='VERTICAL', use_correct_aspect=True)
        # 旋转

        def univ_rotate_ccw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CCW', user_angle=rotate_angle, use_correct_aspect=True)

        def univ_rotate_cw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CW', user_angle=rotate_angle, use_correct_aspect=True)
        # 堆叠

        def univ_stack():
            bpy.ops.uv.univ_stack(between_selected=False, walk_mode='BOTH', island_mode='UV', ignore_mark_seam=True)
        # 回归第一象限

        def univ_home():
            bpy.ops.uv.univ_home(to_cursor=False)
        # 平移

        def uv_move():
            bpy.ops.transform.translate(value = uv_move_value)
        # 对齐

        def univ_align():
            bpy.ops.uv.univ_align(mode='ALIGN', direction = uv_direction)
        # UV象限边界对齐

        def uv_quadrant_align():
            bpy.ops.uv.cursor_set(location= Cursor_Position )
            bpy.ops.uv.univ_align(direction = UV_Direction, mode='ALIGN_TO_CURSOR_UNION')
            bpy.ops.uv.cursor_set(location = (0.0, 0.0))
        # UV缩放

        def uv_scale():
            if advanced:
                bpy.ops.transform.resize(value=scale, center_override=cursor)
            else:
                bpy.ops.transform.resize(value=scale)
        # UV翻转

        def uv_flip():
            bpy.ops.uv.univ_flip(mode=flip_mode, axis=flip_axis)
        # 调用函数
        functions = {
            "univ_orient": univ_orient,  #定向自动
            "univ_orient_x": univ_orient_x,  #定向水平
            "univ_orient_y": univ_orient_y,  #定向垂直    
            "univ_rotate_ccw": univ_rotate_ccw,  #旋转
            "univ_rotate_cw": univ_rotate_cw,  #旋转
            "univ_stack": univ_stack,  #堆叠
            "univ_home": univ_home,  #回归第一象限
            "uv_move": uv_move,  #平移
            "univ_align": univ_align,  #对齐
            "uv_quadrant_align": uv_quadrant_align,  #UV象限边界对齐    
            "uv_scale": uv_scale,  #UV缩放    
            "uv_flip": uv_flip,  #UV翻转
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv__783Fd(bpy.types.Operator):
    bl_idname = "sna.uv__783fd"
    bl_label = "uv_缩放"
    bl_description = "缩放UV"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_size: bpy.props.FloatVectorProperty(name='size', description='', options={'HIDDEN'}, size=2, default=(0.0, 0.0), subtype='NONE', unit='NONE', step=1, precision=2)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        scale = (self.sna_size[0], self.sna_size[1], 1.0)
        cursor = (bpy.context.scene.sna_uv_size_coordinate[0], bpy.context.scene.sna_uv_size_coordinate[1], 0.0)
        advanced = bpy.context.scene.sna_uv_size_mode
        # 自动定向

        def univ_orient():
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='BOTH', use_correct_aspect=True)

        def univ_orient_x(): #水平
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='HORIZONTAL', use_correct_aspect=True)

        def univ_orient_y(): #垂直
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='VERTICAL', use_correct_aspect=True)
        # 旋转

        def univ_rotate_ccw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CCW', user_angle=rotate_angle, use_correct_aspect=True)

        def univ_rotate_cw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CW', user_angle=rotate_angle, use_correct_aspect=True)
        # 堆叠

        def univ_stack():
            bpy.ops.uv.univ_stack(between_selected=False, walk_mode='BOTH', island_mode='UV', ignore_mark_seam=True)
        # 回归第一象限

        def univ_home():
            bpy.ops.uv.univ_home(to_cursor=False)
        # 平移

        def uv_move():
            bpy.ops.transform.translate(value = uv_move_value)
        # 对齐

        def univ_align():
            bpy.ops.uv.univ_align(mode='ALIGN', direction = uv_direction)
        # UV象限边界对齐

        def uv_quadrant_align():
            bpy.ops.uv.cursor_set(location= Cursor_Position )
            bpy.ops.uv.univ_align(direction = UV_Direction, mode='ALIGN_TO_CURSOR_UNION')
            bpy.ops.uv.cursor_set(location = (0.0, 0.0))
        # UV缩放

        def uv_scale():
            if advanced:
                bpy.ops.transform.resize(value=scale, center_override=cursor)
            else:
                bpy.ops.transform.resize(value=scale)
        # UV翻转

        def uv_flip():
            bpy.ops.uv.univ_flip(mode=flip_mode, axis=flip_axis)
        # 调用函数
        functions = {
            "univ_orient": univ_orient,  #定向自动
            "univ_orient_x": univ_orient_x,  #定向水平
            "univ_orient_y": univ_orient_y,  #定向垂直    
            "univ_rotate_ccw": univ_rotate_ccw,  #旋转
            "univ_rotate_cw": univ_rotate_cw,  #旋转
            "univ_stack": univ_stack,  #堆叠
            "univ_home": univ_home,  #回归第一象限
            "uv_move": uv_move,  #平移
            "univ_align": univ_align,  #对齐
            "uv_quadrant_align": uv_quadrant_align,  #UV象限边界对齐    
            "uv_scale": uv_scale,  #UV缩放    
            "uv_flip": uv_flip,  #UV翻转
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv__8Beae(bpy.types.Operator):
    bl_idname = "sna.uv__8beae"
    bl_label = "uv_对称"
    bl_description = "UV对称"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_xy: bpy.props.StringProperty(name='xy', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        flip_mode = ('DEFAULT' if bpy.context.scene.sna_uv_flip_mode else 'INDIVIDUAL')
        flip_axis = self.sna_xy
        # 自动定向

        def univ_orient():
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='BOTH', use_correct_aspect=True)

        def univ_orient_x(): #水平
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='HORIZONTAL', use_correct_aspect=True)

        def univ_orient_y(): #垂直
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='VERTICAL', use_correct_aspect=True)
        # 旋转

        def univ_rotate_ccw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CCW', user_angle=rotate_angle, use_correct_aspect=True)

        def univ_rotate_cw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CW', user_angle=rotate_angle, use_correct_aspect=True)
        # 堆叠

        def univ_stack():
            bpy.ops.uv.univ_stack(between_selected=False, walk_mode='BOTH', island_mode='UV', ignore_mark_seam=True)
        # 回归第一象限

        def univ_home():
            bpy.ops.uv.univ_home(to_cursor=False)
        # 平移

        def uv_move():
            bpy.ops.transform.translate(value = uv_move_value)
        # 对齐

        def univ_align():
            bpy.ops.uv.univ_align(mode='ALIGN', direction = uv_direction)
        # UV象限边界对齐

        def uv_quadrant_align():
            bpy.ops.uv.cursor_set(location= Cursor_Position )
            bpy.ops.uv.univ_align(direction = UV_Direction, mode='ALIGN_TO_CURSOR_UNION')
            bpy.ops.uv.cursor_set(location = (0.0, 0.0))
        # UV缩放

        def uv_scale():
            if advanced:
                bpy.ops.transform.resize(value=scale, center_override=cursor)
            else:
                bpy.ops.transform.resize(value=scale)
        # UV翻转

        def uv_flip():
            bpy.ops.uv.univ_flip(mode=flip_mode, axis=flip_axis)
        # 调用函数
        functions = {
            "univ_orient": univ_orient,  #定向自动
            "univ_orient_x": univ_orient_x,  #定向水平
            "univ_orient_y": univ_orient_y,  #定向垂直    
            "univ_rotate_ccw": univ_rotate_ccw,  #旋转
            "univ_rotate_cw": univ_rotate_cw,  #旋转
            "univ_stack": univ_stack,  #堆叠
            "univ_home": univ_home,  #回归第一象限
            "uv_move": uv_move,  #平移
            "univ_align": univ_align,  #对齐
            "uv_quadrant_align": uv_quadrant_align,  #UV象限边界对齐    
            "uv_scale": uv_scale,  #UV缩放    
            "uv_flip": uv_flip,  #UV翻转
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK！')
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
        bpy.ops.wm.call_panel(name="SNA_PT_uv_quadrant_edge_alignment_EA384", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_uv_quadrant_edge_alignment_EA384(bpy.types.Panel):
    bl_label = '象限边缘对齐'
    bl_idname = 'SNA_PT_uv_quadrant_edge_alignment_EA384'
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
        op.sna_func_name = 'uv_quadrant_align'
        op.sna_cursor_position = (0, 1)
        op.sna_uv_direction = 'BOTTOM'
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
        op.sna_func_name = 'uv_quadrant_align'
        op.sna_cursor_position = (0, 0)
        op.sna_uv_direction = 'RIGHT'
        row_6F6D2.label(text='', icon_value=0)
        op = row_6F6D2.operator('sna.uv__adfc0', text='右', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'uv_quadrant_align'
        op.sna_cursor_position = (1, 0)
        op.sna_uv_direction = 'LEFT'
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
        op.sna_func_name = 'uv_quadrant_align'
        op.sna_cursor_position = (0, 0)
        op.sna_uv_direction = 'UPPER'
        row_16F6C.label(text='', icon_value=0)


class SNA_OT_Uv__Adfc0(bpy.types.Operator):
    bl_idname = "sna.uv__adfc0"
    bl_label = "uv_对齐象限"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_cursor_position: bpy.props.IntVectorProperty(name='Cursor_Position', description='', options={'HIDDEN'}, size=2, default=(0, 0), subtype='NONE')
    sna_uv_direction: bpy.props.StringProperty(name='UV_Direction', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        Cursor_Position = self.sna_cursor_position
        UV_Direction = self.sna_uv_direction
        # 自动定向

        def univ_orient():
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='BOTH', use_correct_aspect=True)

        def univ_orient_x(): #水平
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='HORIZONTAL', use_correct_aspect=True)

        def univ_orient_y(): #垂直
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='VERTICAL', use_correct_aspect=True)
        # 旋转

        def univ_rotate_ccw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CCW', user_angle=rotate_angle, use_correct_aspect=True)

        def univ_rotate_cw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CW', user_angle=rotate_angle, use_correct_aspect=True)
        # 堆叠

        def univ_stack():
            bpy.ops.uv.univ_stack(between_selected=False, walk_mode='BOTH', island_mode='UV', ignore_mark_seam=True)
        # 回归第一象限

        def univ_home():
            bpy.ops.uv.univ_home(to_cursor=False)
        # 平移

        def uv_move():
            bpy.ops.transform.translate(value = uv_move_value)
        # 对齐

        def univ_align():
            bpy.ops.uv.univ_align(mode='ALIGN', direction = uv_direction)
        # UV象限边界对齐

        def uv_quadrant_align():
            bpy.ops.uv.cursor_set(location= Cursor_Position )
            bpy.ops.uv.univ_align(direction = UV_Direction, mode='ALIGN_TO_CURSOR_UNION')
            bpy.ops.uv.cursor_set(location = (0.0, 0.0))
        # UV缩放

        def uv_scale():
            if advanced:
                bpy.ops.transform.resize(value=scale, center_override=cursor)
            else:
                bpy.ops.transform.resize(value=scale)
        # UV翻转

        def uv_flip():
            bpy.ops.uv.univ_flip(mode=flip_mode, axis=flip_axis)
        # 调用函数
        functions = {
            "univ_orient": univ_orient,  #定向自动
            "univ_orient_x": univ_orient_x,  #定向水平
            "univ_orient_y": univ_orient_y,  #定向垂直    
            "univ_rotate_ccw": univ_rotate_ccw,  #旋转
            "univ_rotate_cw": univ_rotate_cw,  #旋转
            "univ_stack": univ_stack,  #堆叠
            "univ_home": univ_home,  #回归第一象限
            "uv_move": uv_move,  #平移
            "univ_align": univ_align,  #对齐
            "uv_quadrant_align": uv_quadrant_align,  #UV象限边界对齐    
            "uv_scale": uv_scale,  #UV缩放    
            "uv_flip": uv_flip,  #UV翻转
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_Dac55(bpy.types.Operator):
    bl_idname = "sna.uv_dac55"
    bl_label = "UV变换"
    bl_description = "UV变换"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        rotate_mode = ('DEFAULT' if bpy.context.scene.sna_uv_rotation_mode else 'INDIVIDUAL')
        rotate_angle = math.radians(bpy.context.scene.sna_uv_rotation_angle)
        # 自动定向

        def univ_orient():
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='BOTH', use_correct_aspect=True)

        def univ_orient_x(): #水平
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='HORIZONTAL', use_correct_aspect=True)

        def univ_orient_y(): #垂直
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='VERTICAL', use_correct_aspect=True)
        # 旋转

        def univ_rotate_ccw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CCW', user_angle=rotate_angle, use_correct_aspect=True)

        def univ_rotate_cw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CW', user_angle=rotate_angle, use_correct_aspect=True)
        # 堆叠

        def univ_stack():
            bpy.ops.uv.univ_stack(between_selected=False, walk_mode='BOTH', island_mode='UV', ignore_mark_seam=True)
        # 回归第一象限

        def univ_home():
            bpy.ops.uv.univ_home(to_cursor=False)
        # 平移

        def uv_move():
            bpy.ops.transform.translate(value = uv_move_value)
        # 对齐

        def univ_align():
            bpy.ops.uv.univ_align(mode='ALIGN', direction = uv_direction)
        # UV象限边界对齐

        def uv_quadrant_align():
            bpy.ops.uv.cursor_set(location= Cursor_Position )
            bpy.ops.uv.univ_align(direction = UV_Direction, mode='ALIGN_TO_CURSOR_UNION')
            bpy.ops.uv.cursor_set(location = (0.0, 0.0))
        # UV缩放

        def uv_scale():
            if advanced:
                bpy.ops.transform.resize(value=scale, center_override=cursor)
            else:
                bpy.ops.transform.resize(value=scale)
        # UV翻转

        def uv_flip():
            bpy.ops.uv.univ_flip(mode=flip_mode, axis=flip_axis)
        # 调用函数
        functions = {
            "univ_orient": univ_orient,  #定向自动
            "univ_orient_x": univ_orient_x,  #定向水平
            "univ_orient_y": univ_orient_y,  #定向垂直    
            "univ_rotate_ccw": univ_rotate_ccw,  #旋转
            "univ_rotate_cw": univ_rotate_cw,  #旋转
            "univ_stack": univ_stack,  #堆叠
            "univ_home": univ_home,  #回归第一象限
            "uv_move": uv_move,  #平移
            "univ_align": univ_align,  #对齐
            "uv_quadrant_align": uv_quadrant_align,  #UV象限边界对齐    
            "uv_scale": uv_scale,  #UV缩放    
            "uv_flip": uv_flip,  #UV翻转
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_Ce841(bpy.types.Operator):
    bl_idname = "sna.uv_ce841"
    bl_label = "UV平移对齐"
    bl_description = "UV平移对齐"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_uv_move_value: bpy.props.FloatVectorProperty(name='uv_move_value', description='', options={'HIDDEN'}, size=3, default=(0.0, 0.0, 0.0), subtype='NONE', unit='NONE', step=3, precision=6)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        uv_move_value = self.sna_uv_move_value
        # 自动定向

        def univ_orient():
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='BOTH', use_correct_aspect=True)

        def univ_orient_x(): #水平
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='HORIZONTAL', use_correct_aspect=True)

        def univ_orient_y(): #垂直
            bpy.ops.uv.univ_orient(lock_overlap=False, edge_dir='VERTICAL', use_correct_aspect=True)
        # 旋转

        def univ_rotate_ccw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CCW', user_angle=rotate_angle, use_correct_aspect=True)

        def univ_rotate_cw():
            bpy.ops.uv.univ_rotate(mode=rotate_mode, rot_dir='CW', user_angle=rotate_angle, use_correct_aspect=True)
        # 堆叠

        def univ_stack():
            bpy.ops.uv.univ_stack(between_selected=False, walk_mode='BOTH', island_mode='UV', ignore_mark_seam=True)
        # 回归第一象限

        def univ_home():
            bpy.ops.uv.univ_home(to_cursor=False)
        # 平移

        def uv_move():
            bpy.ops.transform.translate(value = uv_move_value)
        # 对齐

        def univ_align():
            bpy.ops.uv.univ_align(mode='ALIGN', direction = uv_direction)
        # UV象限边界对齐

        def uv_quadrant_align():
            bpy.ops.uv.cursor_set(location= Cursor_Position )
            bpy.ops.uv.univ_align(direction = UV_Direction, mode='ALIGN_TO_CURSOR_UNION')
            bpy.ops.uv.cursor_set(location = (0.0, 0.0))
        # UV缩放

        def uv_scale():
            if advanced:
                bpy.ops.transform.resize(value=scale, center_override=cursor)
            else:
                bpy.ops.transform.resize(value=scale)
        # UV翻转

        def uv_flip():
            bpy.ops.uv.univ_flip(mode=flip_mode, axis=flip_axis)
        # 调用函数
        functions = {
            "univ_orient": univ_orient,  #定向自动
            "univ_orient_x": univ_orient_x,  #定向水平
            "univ_orient_y": univ_orient_y,  #定向垂直    
            "univ_rotate_ccw": univ_rotate_ccw,  #旋转
            "univ_rotate_cw": univ_rotate_cw,  #旋转
            "univ_stack": univ_stack,  #堆叠
            "univ_home": univ_home,  #回归第一象限
            "uv_move": uv_move,  #平移
            "univ_align": univ_align,  #对齐
            "uv_quadrant_align": uv_quadrant_align,  #UV象限边界对齐    
            "uv_scale": uv_scale,  #UV缩放    
            "uv_flip": uv_flip,  #UV翻转
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uvpackmaster_Edf0D(bpy.types.Operator):
    bl_idname = "sna.uvpackmaster_edf0d"
    bl_label = "UVPackmaster"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        padding = float(bpy.context.scene.sna_uv_tex_overflow / bpy.context.scene.sna_uv_tex_size)
        univ_pre = bpy.context.preferences.addons['univ_qkk'].preferences
        # UV排布

        def uv_pack():
            uvpack = bpy.context.scene.uvpm4_props.default_main_props
            uvpack.margin = padding
            bpy.ops.uvpackmaster4.pack(mode_id="pack.single_tile", pack_op_type= '0')
        # UV插入

        def uv_insert():
            uvpack = bpy.context.scene.uvpm4_props.default_main_props
            uvpack.margin = padding
            bpy.ops.uvpackmaster4.pack(mode_id="pack.single_tile", pack_op_type='1')
        # UV排序

        def uv_sort():
            bpy.ops.uv.univ_sort(lock_overlap=False, axis='X', padding_multiplayer=1)
        # UV随机

        def uv_randomly():
            bpy.ops.uv.univ_random()
        # 切换点模式

        def VERT():
            UV_Panel = bpy.context.scene.tool_settings
            Sync = UV_Panel.use_uv_select_sync
            # 切换模式
            mode_mesh = bpy.ops.mesh.select_mode
            mode_uv = bpy.ops.uv.select_mode
            UV_Panel.use_uv_select_island = False
            UV_Panel.uv_sticky_select_mode = 'SHARED_LOCATION'
            if Sync:
                mode_mesh(type='VERT')
            else:
                mode_uv(type='VERTEX')   
        # UV固定

        def uv_pinned():
            VERT()
            bpy.ops.uv.pin(clear=False)
        # 解锁固定

        def uv_unlock():
            VERT()
            bpy.ops.uv.pin(clear=True)
        # 选择固定

        def uv_select_pinned():
            VERT()
            bpy.ops.uv.select_all(action='DESELECT')
            bpy.ops.uv.select_pinned()
        # 选择解锁

        def uv_select_unlock():
            VERT()
            bpy.ops.uv.select_all(action='DESELECT')
            bpy.ops.uv.select_pinned()
            bpy.ops.uv.select_all(action='INVERT')
        # 同步参数

        def related_parameters():    
            univ_pre.size_x = size_xy
            univ_pre.size_y = size_xy
            #bpy.context.window_manager.univ_settings.size_x = size_xy
            #bpy.context.window_manager.univ_settings.size_y = size_xy
        # 获取像素密度

        def univ_texel_density_get():
            related_parameters()
            bpy.ops.uv.univ_texel_density_get()
        # 设置像素密度

        def univ_texel_density_set():
            related_parameters()
            univ_pre.texel_density = texel_density
            #bpy.context.window_manager.univ_settings.texel_density 
            bpy.ops.uv.univ_texel_density_set(td_preset_idx=-1)
        # 按像素密度选中

        def univ_select_texel_density():
            bpy.ops.uv.univ_select_texel_density(mode='SELECT', island_mode='ISLAND', target_texel=texel_density)
        # 规格化缩放

        def univ_crop():
            bpy.ops.uv.univ_fit(axis=axis, inplace=False,padding_multiplayer=0.0,individual=individual)
        # 规格化拉伸

        def univ_fill():
            bpy.ops.uv.univ_fill(axis=axis, inplace=False,padding_multiplayer=0.0,individual=individual)
        # 调用函数
        functions = {
            "uv_pack": uv_pack,  #UV排布
            "uv_insert": uv_insert,  #UV插入
            "uv_sort": uv_sort,  #UV排序
            "uv_randomly": uv_randomly,  #UV随机
            "uv_pinned": uv_pinned,  #UV固定
            "uv_unlock": uv_unlock,  #解锁固定
            "uv_select_pinned": uv_select_pinned,  #选择固定
            "uv_select_unlock": uv_select_unlock,  #选择解锁
            "univ_texel_density_get": univ_texel_density_get,  #获取像素密度
            "univ_texel_density_set": univ_texel_density_set,  #设置像素密度
            "univ_select_texel_density": univ_select_texel_density,  #按像素密度选中
             "univ_crop": univ_crop,  #规格化缩放
              "univ_fill": univ_fill,  #规格化拉伸
            }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Uv_Density_585B1(bpy.types.Operator):
    bl_idname = "sna.uv_density_585b1"
    bl_label = "uv_density"
    bl_description = "uv_density"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        size_xy = bpy.context.scene.sna_uv_precision_size
        texel_density = bpy.context.preferences.addons['univ_qkk'].preferences.texel_density
        univ_pre = bpy.context.preferences.addons['univ_qkk'].preferences
        # UV排布

        def uv_pack():
            uvpack = bpy.context.scene.uvpm4_props.default_main_props
            uvpack.margin = padding
            bpy.ops.uvpackmaster4.pack(mode_id="pack.single_tile", pack_op_type= '0')
        # UV插入

        def uv_insert():
            uvpack = bpy.context.scene.uvpm4_props.default_main_props
            uvpack.margin = padding
            bpy.ops.uvpackmaster4.pack(mode_id="pack.single_tile", pack_op_type='1')
        # UV排序

        def uv_sort():
            bpy.ops.uv.univ_sort(lock_overlap=False, axis='X', padding_multiplayer=1)
        # UV随机

        def uv_randomly():
            bpy.ops.uv.univ_random()
        # 切换点模式

        def VERT():
            UV_Panel = bpy.context.scene.tool_settings
            Sync = UV_Panel.use_uv_select_sync
            # 切换模式
            mode_mesh = bpy.ops.mesh.select_mode
            mode_uv = bpy.ops.uv.select_mode
            UV_Panel.use_uv_select_island = False
            UV_Panel.uv_sticky_select_mode = 'SHARED_LOCATION'
            if Sync:
                mode_mesh(type='VERT')
            else:
                mode_uv(type='VERTEX')   
        # UV固定

        def uv_pinned():
            VERT()
            bpy.ops.uv.pin(clear=False)
        # 解锁固定

        def uv_unlock():
            VERT()
            bpy.ops.uv.pin(clear=True)
        # 选择固定

        def uv_select_pinned():
            VERT()
            bpy.ops.uv.select_all(action='DESELECT')
            bpy.ops.uv.select_pinned()
        # 选择解锁

        def uv_select_unlock():
            VERT()
            bpy.ops.uv.select_all(action='DESELECT')
            bpy.ops.uv.select_pinned()
            bpy.ops.uv.select_all(action='INVERT')
        # 同步参数

        def related_parameters():    
            univ_pre.size_x = size_xy
            univ_pre.size_y = size_xy
            #bpy.context.window_manager.univ_settings.size_x = size_xy
            #bpy.context.window_manager.univ_settings.size_y = size_xy
        # 获取像素密度

        def univ_texel_density_get():
            related_parameters()
            bpy.ops.uv.univ_texel_density_get()
        # 设置像素密度

        def univ_texel_density_set():
            related_parameters()
            univ_pre.texel_density = texel_density
            #bpy.context.window_manager.univ_settings.texel_density 
            bpy.ops.uv.univ_texel_density_set(td_preset_idx=-1)
        # 按像素密度选中

        def univ_select_texel_density():
            bpy.ops.uv.univ_select_texel_density(mode='SELECT', island_mode='ISLAND', target_texel=texel_density)
        # 规格化缩放

        def univ_crop():
            bpy.ops.uv.univ_fit(axis=axis, inplace=False,padding_multiplayer=0.0,individual=individual)
        # 规格化拉伸

        def univ_fill():
            bpy.ops.uv.univ_fill(axis=axis, inplace=False,padding_multiplayer=0.0,individual=individual)
        # 调用函数
        functions = {
            "uv_pack": uv_pack,  #UV排布
            "uv_insert": uv_insert,  #UV插入
            "uv_sort": uv_sort,  #UV排序
            "uv_randomly": uv_randomly,  #UV随机
            "uv_pinned": uv_pinned,  #UV固定
            "uv_unlock": uv_unlock,  #解锁固定
            "uv_select_pinned": uv_select_pinned,  #选择固定
            "uv_select_unlock": uv_select_unlock,  #选择解锁
            "univ_texel_density_get": univ_texel_density_get,  #获取像素密度
            "univ_texel_density_set": univ_texel_density_set,  #设置像素密度
            "univ_select_texel_density": univ_select_texel_density,  #按像素密度选中
             "univ_crop": univ_crop,  #规格化缩放
              "univ_fill": univ_fill,  #规格化拉伸
            }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Univ_Crop_C9Fd5(bpy.types.Operator):
    bl_idname = "sna.univ_crop_c9fd5"
    bl_label = "univ_crop"
    bl_description = "univ_crop"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_axis: bpy.props.StringProperty(name='axis', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        axis = self.sna_axis
        individual = bpy.context.scene.sna_uv_individual
        univ_pre = bpy.context.preferences.addons['univ_qkk'].preferences
        # UV排布

        def uv_pack():
            uvpack = bpy.context.scene.uvpm4_props.default_main_props
            uvpack.margin = padding
            bpy.ops.uvpackmaster4.pack(mode_id="pack.single_tile", pack_op_type= '0')
        # UV插入

        def uv_insert():
            uvpack = bpy.context.scene.uvpm4_props.default_main_props
            uvpack.margin = padding
            bpy.ops.uvpackmaster4.pack(mode_id="pack.single_tile", pack_op_type='1')
        # UV排序

        def uv_sort():
            bpy.ops.uv.univ_sort(lock_overlap=False, axis='X', padding_multiplayer=1)
        # UV随机

        def uv_randomly():
            bpy.ops.uv.univ_random()
        # 切换点模式

        def VERT():
            UV_Panel = bpy.context.scene.tool_settings
            Sync = UV_Panel.use_uv_select_sync
            # 切换模式
            mode_mesh = bpy.ops.mesh.select_mode
            mode_uv = bpy.ops.uv.select_mode
            UV_Panel.use_uv_select_island = False
            UV_Panel.uv_sticky_select_mode = 'SHARED_LOCATION'
            if Sync:
                mode_mesh(type='VERT')
            else:
                mode_uv(type='VERTEX')   
        # UV固定

        def uv_pinned():
            VERT()
            bpy.ops.uv.pin(clear=False)
        # 解锁固定

        def uv_unlock():
            VERT()
            bpy.ops.uv.pin(clear=True)
        # 选择固定

        def uv_select_pinned():
            VERT()
            bpy.ops.uv.select_all(action='DESELECT')
            bpy.ops.uv.select_pinned()
        # 选择解锁

        def uv_select_unlock():
            VERT()
            bpy.ops.uv.select_all(action='DESELECT')
            bpy.ops.uv.select_pinned()
            bpy.ops.uv.select_all(action='INVERT')
        # 同步参数

        def related_parameters():    
            univ_pre.size_x = size_xy
            univ_pre.size_y = size_xy
            #bpy.context.window_manager.univ_settings.size_x = size_xy
            #bpy.context.window_manager.univ_settings.size_y = size_xy
        # 获取像素密度

        def univ_texel_density_get():
            related_parameters()
            bpy.ops.uv.univ_texel_density_get()
        # 设置像素密度

        def univ_texel_density_set():
            related_parameters()
            univ_pre.texel_density = texel_density
            #bpy.context.window_manager.univ_settings.texel_density 
            bpy.ops.uv.univ_texel_density_set(td_preset_idx=-1)
        # 按像素密度选中

        def univ_select_texel_density():
            bpy.ops.uv.univ_select_texel_density(mode='SELECT', island_mode='ISLAND', target_texel=texel_density)
        # 规格化缩放

        def univ_crop():
            bpy.ops.uv.univ_fit(axis=axis, inplace=False,padding_multiplayer=0.0,individual=individual)
        # 规格化拉伸

        def univ_fill():
            bpy.ops.uv.univ_fill(axis=axis, inplace=False,padding_multiplayer=0.0,individual=individual)
        # 调用函数
        functions = {
            "uv_pack": uv_pack,  #UV排布
            "uv_insert": uv_insert,  #UV插入
            "uv_sort": uv_sort,  #UV排序
            "uv_randomly": uv_randomly,  #UV随机
            "uv_pinned": uv_pinned,  #UV固定
            "uv_unlock": uv_unlock,  #解锁固定
            "uv_select_pinned": uv_select_pinned,  #选择固定
            "uv_select_unlock": uv_select_unlock,  #选择解锁
            "univ_texel_density_get": univ_texel_density_get,  #获取像素密度
            "univ_texel_density_set": univ_texel_density_set,  #设置像素密度
            "univ_select_texel_density": univ_select_texel_density,  #按像素密度选中
             "univ_crop": univ_crop,  #规格化缩放
              "univ_fill": univ_fill,  #规格化拉伸
            }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_add_to_image_pt_tools_active_233B9(self, context):
    if not ((not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV')))):
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
        op = col_8ED3D.operator('sna.image_tags_operation_e3b60', text='图像标签', icon_value=0, emboss=True, depress=False)
        col_8ED3D.separator(factor=1.0)
        col_8ED3D.prop(bpy.context.preferences.addons['univ_qkk'].preferences, 'overlay_2d_enable', text='缝合边', icon_value=0, emboss=True, toggle=True)
        split_7B75E = col_8ED3D.split(factor=0.800000011920929, align=True)
        split_7B75E.alert = False
        split_7B75E.enabled = True
        split_7B75E.active = True
        split_7B75E.use_property_split = False
        split_7B75E.use_property_decorate = False
        split_7B75E.scale_x = 1.0
        split_7B75E.scale_y = 1.0
        split_7B75E.alignment = 'Expand'.upper()
        if not True: split_7B75E.operator_context = "EXEC_DEFAULT"
        split_7B75E.prop(bpy.context.preferences.addons['univ_qkk'].preferences, 'overlay_3d_enable', text='3D同步', icon_value=0, emboss=True, toggle=True)
        split_7B75E.prop(bpy.context.preferences.addons['univ_qkk'].preferences, 'overlay_toggle_xray', text='透', icon_value=0, emboss=True, toggle=True)
        op = col_8ED3D.operator('uv.select_overlap', text='选重叠', icon_value=0, emboss=True, depress=False)
        op.extend = False
        op = col_8ED3D.operator('uv.univ_check_flipped', text='选翻转', icon_value=0, emboss=True, depress=False)
        op = col_8ED3D.operator('uvpackmaster4.measure_area', text='UV占比', icon_value=0, emboss=True, depress=False)
        op.merged = False
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
        bpy.ops.wm.univ_checker_cleanup()
        bpy.ops.mesh.univ_checker()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_5A68B(bpy.types.Menu):
    bl_idname = "SNA_MT_5A68B"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return not ((not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV'))))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('sna.uv_15342', text='点', icon_value=string_to_icon('DOT'), emboss=True, depress=False)
        op.sna_func_name = 'VERT'
        op = layout.operator('sna.uv_15342', text='面', icon_value=string_to_icon('SNAP_FACE'), emboss=True, depress=False)
        op.sna_func_name = 'FACE'
        op = layout.operator('sna.my_generic_operator_d5090', text='快捷键', icon_value=string_to_icon('COLLAPSEMENU'), emboss=True, depress=False)
        op = layout.operator('sna.uv_15342', text='线', icon_value=string_to_icon('REMOVE'), emboss=True, depress=False)
        op.sna_func_name = 'EDGE'
        op = layout.operator('sna.uv_15342', text='独显', icon_value=string_to_icon('OBJECT_HIDDEN'), emboss=True, depress=False)
        op.sna_func_name = 'Display_Switc'
        op = layout.operator('sna.uv_15342', text='更新缝合边', icon_value=string_to_icon('RECOVER_LAST'), emboss=True, depress=False)
        op.sna_func_name = 'Update_Seams'
        op = layout.operator('sna.uv_15342', text='选孤岛', icon_value=string_to_icon('VIEW_ORTHO'), emboss=True, depress=False)
        op.sna_func_name = 'Select_Related'
        op = layout.operator('sna.uv_15342', text='孤岛', icon_value=string_to_icon('IMGDISPLAY'), emboss=True, depress=False)
        op.sna_func_name = 'Island'


class SNA_OT_Uv_15342(bpy.types.Operator):
    bl_idname = "sna.uv_15342"
    bl_label = "UV"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        import bmesh
        UV_Panel = bpy.context.scene.tool_settings
        Sync = UV_Panel.use_uv_select_sync
        # 切换模式
        mode_mesh = bpy.ops.mesh.select_mode
        mode_uv = bpy.ops.uv.select_mode

        def VERT():
            UV_Panel.use_uv_select_island = False
            UV_Panel.uv_sticky_select_mode = 'SHARED_LOCATION'
            if Sync:
                mode_mesh(type='VERT')
            else:
                mode_uv(type='VERTEX')        

        def EDGE():
            UV_Panel.use_uv_select_island = False
            UV_Panel.uv_sticky_select_mode = 'SHARED_LOCATION'
            if Sync:
                mode_mesh(type='EDGE')
            else:
                mode_uv(type='EDGE')    

        def FACE():
            UV_Panel.use_uv_select_island = False
            UV_Panel.uv_sticky_select_mode = 'SHARED_LOCATION'
            if Sync:
                mode_mesh(type='FACE')
            else:
                mode_uv(type='FACE')    

        def Island():
            UV_Panel.use_uv_select_island = True
            UV_Panel.uv_sticky_select_mode = 'SHARED_LOCATION'
            if Sync:
                mode_mesh(type='FACE')
            else:
                mode_uv(type='FACE')
        # 独显切换

        def Display_Switc():
            # 获取当前活动对象
            obj = bpy.context.active_object
            bm = bmesh.from_edit_mesh(obj.data)
            if Sync:
                # 选中mod的顶点数
                selected_vert = sum(1 for v in bm.verts if v.select)  
            else:
                # 获取 UV 图层
                uv_layer = bm.loops.layers.uv.active
                # 选中的 UV 点数
                selected_vert = sum(1 for face in bm.faces for loop in face.loops if loop[uv_layer].select)
            if selected_vert > 0:
                # 独显
                bpy.ops.uv.hide(unselected=True)
            else:
                # 全显
                bpy.ops.uv.reveal(select=False)
        # 选择相关

        def Select_Related():
            bpy.ops.uv.select_linked()
        # 更新缝合边

        def Update_Seams():
            a = bpy.context.scene.tool_settings.use_uv_select_sync
            bpy.ops.uv.select_all(action='SELECT')
            bpy.ops.uv.mark_seam(clear=True)    
            bpy.ops.uv.univ_select_border(mode='SELECT', border_mode='BORDER') #Univ
            bpy.ops.uv.mark_seam(clear=False)    
            if a:
                bpy.context.scene.tool_settings.use_uv_select_sync = True
            bpy.ops.uv.select_all(action='DESELECT')    
            bpy.context.preferences.addons['univ_qkk'].preferences.overlay_2d_enable = True #Univ
            #bpy.context.window_manager.univ_settings.overlay_2d_enable = True  #Univ
        # 调用函数
        functions = {
            "VERT": VERT,  # 
            "EDGE": EDGE,  #
            "FACE": FACE,  #
            "Island": Island,  #
            "Display_Switc": Display_Switc,  #独显切换
            "Select_Related": Select_Related,  #选择相关
            "Update_Seams": Update_Seams,  #选择相关
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Image_Tags_Operation_E3B60(bpy.types.Operator):
    bl_idname = "sna.image_tags_operation_e3b60"
    bl_label = "Image_Tags_Operation"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_IMAGE_TAGS_348EA", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_IMAGE_TAGS_348EA(bpy.types.Panel):
    bl_label = 'Image_Tags'
    bl_idname = 'SNA_PT_IMAGE_TAGS_348EA'
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
        grid_7B220 = layout.grid_flow(columns=2, row_major=True, even_columns=False, even_rows=False, align=True)
        grid_7B220.enabled = True
        grid_7B220.active = True
        grid_7B220.use_property_split = False
        grid_7B220.use_property_decorate = False
        grid_7B220.alignment = 'Expand'.upper()
        grid_7B220.scale_x = 1.0
        grid_7B220.scale_y = 1.0
        if not True: grid_7B220.operator_context = "EXEC_DEFAULT"
        for i_4E35A in range(len(bpy.data.images)):
            if bpy.data.images[i_4E35A].use_fake_user:
                box_96842 = layout.box()
                box_96842.alert = False
                box_96842.enabled = True
                box_96842.active = True
                box_96842.use_property_split = False
                box_96842.use_property_decorate = False
                box_96842.alignment = 'Expand'.upper()
                box_96842.scale_x = 1.0
                box_96842.scale_y = 1.0
                if not True: box_96842.operator_context = "EXEC_DEFAULT"
                col_7CFF6 = layout.column(heading='', align=True)
                col_7CFF6.alert = False
                col_7CFF6.enabled = True
                col_7CFF6.active = True
                col_7CFF6.use_property_split = False
                col_7CFF6.use_property_decorate = False
                col_7CFF6.scale_x = 1.0
                col_7CFF6.scale_y = 1.0
                col_7CFF6.alignment = 'Expand'.upper()
                col_7CFF6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                layout.template_icon(icon_value=get_id_preview_id(bpy.data.images[bpy.data.images[i_4E35A].name]), scale=4.0)
                op = layout.operator('sna.operator_cd023', text='使用', icon_value=0, emboss=True, depress=False)
                op.sna_imgname = bpy.data.images[i_4E35A].name


class SNA_OT_Operator_Cd023(bpy.types.Operator):
    bl_idname = "sna.operator_cd023"
    bl_label = "Operator"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_imgname: bpy.props.StringProperty(name='imgname', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_ACCC0 in range(len(bpy.context.area.spaces)):
            if (bpy.context.area.spaces[i_ACCC0].type == 'IMAGE_EDITOR'):
                bpy.context.area.spaces[i_ACCC0].image = bpy.data.images[self.sna_imgname]
                self.report({'INFO'}, message='图像设置完成！')
        return {"FINISHED"}

    def invoke(self, context, event):
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
        return not (not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV')))

    def execute(self, context):
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            if bpy.context.tool_settings.mesh_select_mode[0]:
                bpy.ops.uv.select_linked()
            else:
                if bpy.context.tool_settings.mesh_select_mode[1]:
                    bpy.ops.uv.select_loop('INVOKE_DEFAULT', extend=self.sna_new_property)
                else:
                    if bpy.context.tool_settings.mesh_select_mode[2]:
                        bpy.ops.uv.select_loop('INVOKE_DEFAULT', extend=self.sna_new_property)
        else:
            if (bpy.context.scene.tool_settings.uv_select_mode == 'VERTEX'):
                bpy.ops.uv.select_linked()
            else:
                if (bpy.context.scene.tool_settings.uv_select_mode == 'EDGE'):
                    bpy.ops.uv.select_loop('INVOKE_DEFAULT', extend=self.sna_new_property)
                else:
                    if (bpy.context.scene.tool_settings.uv_select_mode == 'FACE'):
                        bpy.ops.uv.select_loop('INVOKE_DEFAULT', extend=self.sna_new_property)
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
        return not (not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV')))

    def execute(self, context):
        bpy.ops.uv.univ_cut('INVOKE_DEFAULT', unwrap='NONE')
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
        return not (not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV')))

    def execute(self, context):
        bpy.ops.uv.univ_drag('INVOKE_DEFAULT', )
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
        return not (not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV')))

    def execute(self, context):
        bpy.ops.uv.univ_quick_snap('INVOKE_DEFAULT', island_mode=True, quick_start=False)
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
        return not (not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV')))

    def execute(self, context):
        bpy.ops.uv.univ_weld('INVOKE_DEFAULT', use_by_distance=False)
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
        return not (not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV')))

    def execute(self, context):
        bpy.ops.uv.stitch('INVOKE_DEFAULT', snap_islands=True, midpoint_snap=False, clear_seams=True, mode='EDGE', stored_mode='EDGE')
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
        return not (not ('EDIT_MESH'==bpy.context.mode and (bpy.context.area.ui_type == 'UV')))

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


class SNA_PT_unfold_ADE36(bpy.types.Panel):
    bl_label = '展开'
    bl_idname = 'SNA_PT_unfold_ADE36'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 5
    bl_parent_id = 'SNA_PT_QKK_UV_F373B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_E487C = layout.column(heading='', align=False)
        col_E487C.alert = False
        col_E487C.enabled = 'EDIT_MESH'==bpy.context.mode
        col_E487C.active = True
        col_E487C.use_property_split = False
        col_E487C.use_property_decorate = False
        col_E487C.scale_x = 1.0
        col_E487C.scale_y = 1.2999999523162842
        col_E487C.alignment = 'Expand'.upper()
        col_E487C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_046F0 = col_E487C.split(factor=0.5, align=True)
        split_046F0.alert = False
        split_046F0.enabled = True
        split_046F0.active = True
        split_046F0.use_property_split = False
        split_046F0.use_property_decorate = False
        split_046F0.scale_x = 1.0
        split_046F0.scale_y = 1.0
        split_046F0.alignment = 'Expand'.upper()
        if not True: split_046F0.operator_context = "EXEC_DEFAULT"
        op = split_046F0.operator('sna.uv_92e7d', text='创建', icon_value=_icons['normalize.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_normal'
        split_8EB91 = split_046F0.split(factor=0.5, align=True)
        split_8EB91.alert = False
        split_8EB91.enabled = True
        split_8EB91.active = True
        split_8EB91.use_property_split = False
        split_8EB91.use_property_decorate = False
        split_8EB91.scale_x = 1.0
        split_8EB91.scale_y = 1.0
        split_8EB91.alignment = 'Expand'.upper()
        if not True: split_8EB91.operator_context = "EXEC_DEFAULT"
        op = split_8EB91.operator('uv.smart_project', text='角度', icon_value=0, emboss=True, depress=False)
        op = split_8EB91.operator('sna.uv_92e7d', text='松弛', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_relax'
        split_AD955 = col_E487C.split(factor=0.5, align=True)
        split_AD955.alert = False
        split_AD955.enabled = True
        split_AD955.active = True
        split_AD955.use_property_split = False
        split_AD955.use_property_decorate = False
        split_AD955.scale_x = 1.0
        split_AD955.scale_y = 1.0
        split_AD955.alignment = 'Expand'.upper()
        if not True: split_AD955.operator_context = "EXEC_DEFAULT"
        op = split_AD955.operator('sna.uv_92e7d', text='展开', icon_value=_icons['unwrap.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_unwrap'
        split_9AC4A = split_AD955.split(factor=0.5, align=True)
        split_9AC4A.alert = False
        split_9AC4A.enabled = True
        split_9AC4A.active = True
        split_9AC4A.use_property_split = False
        split_9AC4A.use_property_decorate = False
        split_9AC4A.scale_x = 1.0
        split_9AC4A.scale_y = 1.0
        split_9AC4A.alignment = 'Expand'.upper()
        if not True: split_9AC4A.operator_context = "EXEC_DEFAULT"
        op = split_9AC4A.operator('sna.uv_92e7d', text='平均', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_adjust_td'
        op = split_9AC4A.operator('sna.uv_92e7d', text='3D平均', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_normalize'
        split_B46DC = col_E487C.split(factor=0.5, align=True)
        split_B46DC.alert = False
        split_B46DC.enabled = True
        split_B46DC.active = True
        split_B46DC.use_property_split = False
        split_B46DC.use_property_decorate = False
        split_B46DC.scale_x = 1.0
        split_B46DC.scale_y = 1.0
        split_B46DC.alignment = 'Expand'.upper()
        if not True: split_B46DC.operator_context = "EXEC_DEFAULT"
        split_8FDA0 = split_B46DC.split(factor=0.5, align=True)
        split_8FDA0.alert = False
        split_8FDA0.enabled = True
        split_8FDA0.active = True
        split_8FDA0.use_property_split = False
        split_8FDA0.use_property_decorate = False
        split_8FDA0.scale_x = 1.0
        split_8FDA0.scale_y = 1.0
        split_8FDA0.alignment = 'Expand'.upper()
        if not True: split_8FDA0.operator_context = "EXEC_DEFAULT"
        op = split_8FDA0.operator('sna.uv_92e7d', text='拉直', icon_value=_icons['quadrify.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_quadrify'
        op = split_8FDA0.operator('sna.uv_92e7d', text='', icon_value=_icons['rectify.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_rectify'
        split_2D020 = split_B46DC.split(factor=0.5, align=True)
        split_2D020.alert = False
        split_2D020.enabled = True
        split_2D020.active = True
        split_2D020.use_property_split = False
        split_2D020.use_property_decorate = False
        split_2D020.scale_x = 1.0
        split_2D020.scale_y = 1.0
        split_2D020.alignment = 'Expand'.upper()
        if not True: split_2D020.operator_context = "EXEC_DEFAULT"
        op = split_2D020.operator('sna.uv_92e7d', text='切开', icon_value=_icons['cut.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_cut'
        op = split_2D020.operator('sna.uv_92e7d', text='缝合', icon_value=_icons['stitch.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_weld'


class SNA_PT_uv_conversion_B5EFB(bpy.types.Panel):
    bl_label = '变换'
    bl_idname = 'SNA_PT_uv_conversion_B5EFB'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 6
    bl_parent_id = 'SNA_PT_QKK_UV_F373B'
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_58318 = layout.column(heading='', align=True)
        col_58318.alert = False
        col_58318.enabled = 'EDIT_MESH'==bpy.context.mode
        col_58318.active = True
        col_58318.use_property_split = False
        col_58318.use_property_decorate = False
        col_58318.scale_x = 1.0
        col_58318.scale_y = 1.0
        col_58318.alignment = 'Expand'.upper()
        col_58318.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        box_D7459 = col_58318.box()
        box_D7459.alert = False
        box_D7459.enabled = True
        box_D7459.active = True
        box_D7459.use_property_split = False
        box_D7459.use_property_decorate = False
        box_D7459.alignment = 'Expand'.upper()
        box_D7459.scale_x = 1.0
        box_D7459.scale_y = 1.0
        if not True: box_D7459.operator_context = "EXEC_DEFAULT"
        col_FD6E4 = box_D7459.column(heading='', align=True)
        col_FD6E4.alert = False
        col_FD6E4.enabled = True
        col_FD6E4.active = True
        col_FD6E4.use_property_split = False
        col_FD6E4.use_property_decorate = False
        col_FD6E4.scale_x = 1.0
        col_FD6E4.scale_y = 1.0
        col_FD6E4.alignment = 'Expand'.upper()
        col_FD6E4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_30745 = col_FD6E4.split(factor=0.5, align=True)
        split_30745.alert = False
        split_30745.enabled = True
        split_30745.active = True
        split_30745.use_property_split = False
        split_30745.use_property_decorate = False
        split_30745.scale_x = 1.0
        split_30745.scale_y = 1.0
        split_30745.alignment = 'Expand'.upper()
        if not True: split_30745.operator_context = "EXEC_DEFAULT"
        split_352FA = split_30745.split(factor=0.800000011920929, align=True)
        split_352FA.alert = False
        split_352FA.enabled = True
        split_352FA.active = True
        split_352FA.use_property_split = False
        split_352FA.use_property_decorate = False
        split_352FA.scale_x = 1.0
        split_352FA.scale_y = 1.0
        split_352FA.alignment = 'Expand'.upper()
        if not True: split_352FA.operator_context = "EXEC_DEFAULT"
        col_95891 = split_352FA.column(heading='', align=True)
        col_95891.alert = False
        col_95891.enabled = True
        col_95891.active = True
        col_95891.use_property_split = False
        col_95891.use_property_decorate = False
        col_95891.scale_x = 1.0
        col_95891.scale_y = 2.0
        col_95891.alignment = 'Expand'.upper()
        col_95891.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_95891.operator('sna.uv_dac55', text='', icon_value=_icons['body.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_orient'
        col_466FF = split_352FA.column(heading='', align=True)
        col_466FF.alert = False
        col_466FF.enabled = True
        col_466FF.active = True
        col_466FF.use_property_split = False
        col_466FF.use_property_decorate = False
        col_466FF.scale_x = 1.0
        col_466FF.scale_y = 1.0
        col_466FF.alignment = 'Expand'.upper()
        col_466FF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_466FF.operator('sna.uv_dac55', text='', icon_value=_icons['x.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_orient_x'
        op = col_466FF.operator('sna.uv_dac55', text='', icon_value=_icons['y.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_orient_y'
        col_99926 = split_30745.column(heading='', align=True)
        col_99926.alert = False
        col_99926.enabled = True
        col_99926.active = True
        col_99926.use_property_split = False
        col_99926.use_property_decorate = False
        col_99926.scale_x = 1.0
        col_99926.scale_y = 1.0
        col_99926.alignment = 'Expand'.upper()
        col_99926.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_9A439 = col_99926.split(factor=0.5, align=True)
        split_9A439.alert = False
        split_9A439.enabled = True
        split_9A439.active = True
        split_9A439.use_property_split = False
        split_9A439.use_property_decorate = False
        split_9A439.scale_x = 1.0
        split_9A439.scale_y = 1.0
        split_9A439.alignment = 'Expand'.upper()
        if not True: split_9A439.operator_context = "EXEC_DEFAULT"
        op = split_9A439.operator('sna.uv_dac55', text='', icon_value=_icons['p90.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_rotate_ccw'
        op = split_9A439.operator('sna.uv_dac55', text='', icon_value=_icons['n90.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_rotate_cw'
        split_7A24B = col_99926.split(factor=0.5, align=True)
        split_7A24B.alert = False
        split_7A24B.enabled = True
        split_7A24B.active = True
        split_7A24B.use_property_split = False
        split_7A24B.use_property_decorate = False
        split_7A24B.scale_x = 1.0
        split_7A24B.scale_y = 1.0
        split_7A24B.alignment = 'Expand'.upper()
        if not True: split_7A24B.operator_context = "EXEC_DEFAULT"
        split_7A24B.prop(bpy.context.scene, 'sna_uv_rotation_angle', text='', icon_value=0, emboss=True)
        split_7A24B.prop(bpy.context.scene, 'sna_uv_rotation_mode', text='整体', icon_value=0, emboss=True)
        split_9626E = col_58318.split(factor=0.5, align=True)
        split_9626E.alert = False
        split_9626E.enabled = True
        split_9626E.active = True
        split_9626E.use_property_split = False
        split_9626E.use_property_decorate = False
        split_9626E.scale_x = 1.0
        split_9626E.scale_y = 1.0
        split_9626E.alignment = 'Expand'.upper()
        if not True: split_9626E.operator_context = "EXEC_DEFAULT"
        box_032E4 = split_9626E.box()
        box_032E4.alert = False
        box_032E4.enabled = True
        box_032E4.active = True
        box_032E4.use_property_split = False
        box_032E4.use_property_decorate = False
        box_032E4.alignment = 'Expand'.upper()
        box_032E4.scale_x = 1.0
        box_032E4.scale_y = 1.0
        if not True: box_032E4.operator_context = "EXEC_DEFAULT"
        col_086C0 = box_032E4.column(heading='', align=True)
        col_086C0.alert = False
        col_086C0.enabled = True
        col_086C0.active = True
        col_086C0.use_property_split = False
        col_086C0.use_property_decorate = False
        col_086C0.scale_x = 2.0
        col_086C0.scale_y = 1.5
        col_086C0.alignment = 'Expand'.upper()
        col_086C0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_D0B62 = col_086C0.row(heading='', align=True)
        row_D0B62.alert = False
        row_D0B62.enabled = True
        row_D0B62.active = True
        row_D0B62.use_property_split = False
        row_D0B62.use_property_decorate = False
        row_D0B62.scale_x = 1.0
        row_D0B62.scale_y = 1.0
        row_D0B62.alignment = 'Expand'.upper()
        row_D0B62.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_D0B62.operator('sna.uv_dac55', text='', icon_value=_icons['stack.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_stack'
        op = row_D0B62.operator('sna.uv_ce841', text='', icon_value=_icons['symm_n_y.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'uv_move'
        op.sna_uv_move_value = (0.0, bpy.context.scene.sna_uv_move_size, 0.0)
        op = row_D0B62.operator('sna.uv_dac55', text='', icon_value=_icons['home.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_home'
        row_9354B = col_086C0.row(heading='', align=True)
        row_9354B.alert = False
        row_9354B.enabled = True
        row_9354B.active = True
        row_9354B.use_property_split = False
        row_9354B.use_property_decorate = False
        row_9354B.scale_x = 1.0
        row_9354B.scale_y = 1.0
        row_9354B.alignment = 'Expand'.upper()
        row_9354B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_9354B.operator('sna.uv_ce841', text='', icon_value=_icons['symm_p_x.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'uv_move'
        op.sna_uv_move_value = (float(bpy.context.scene.sna_uv_move_size * -1.0), 0.0, 0.0)
        op = row_9354B.operator('sna.my_generic_operator_e4775', text='', icon_value=string_to_icon('ADD'), emboss=True, depress=False)
        op = row_9354B.operator('sna.uv_ce841', text='', icon_value=_icons['symm_n_x.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'uv_move'
        op.sna_uv_move_value = (bpy.context.scene.sna_uv_move_size, 0.0, 0.0)
        row_20FB0 = col_086C0.row(heading='', align=True)
        row_20FB0.alert = False
        row_20FB0.enabled = True
        row_20FB0.active = True
        row_20FB0.use_property_split = False
        row_20FB0.use_property_decorate = False
        row_20FB0.scale_x = 1.0
        row_20FB0.scale_y = 1.0
        row_20FB0.alignment = 'Expand'.upper()
        row_20FB0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_20FB0.separator(factor=4.0)
        op = row_20FB0.operator('sna.uv_ce841', text='', icon_value=_icons['symm_p_y.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'uv_move'
        op.sna_uv_move_value = (0.0, float(bpy.context.scene.sna_uv_move_size * -1.0), 0.0)
        row_20FB0.separator(factor=4.0)
        box_4D66C = split_9626E.box()
        box_4D66C.alert = False
        box_4D66C.enabled = True
        box_4D66C.active = True
        box_4D66C.use_property_split = False
        box_4D66C.use_property_decorate = False
        box_4D66C.alignment = 'Expand'.upper()
        box_4D66C.scale_x = 1.0
        box_4D66C.scale_y = 1.0
        if not True: box_4D66C.operator_context = "EXEC_DEFAULT"
        col_BAE7E = box_4D66C.column(heading='', align=True)
        col_BAE7E.alert = False
        col_BAE7E.enabled = True
        col_BAE7E.active = True
        col_BAE7E.use_property_split = False
        col_BAE7E.use_property_decorate = False
        col_BAE7E.scale_x = 2.0
        col_BAE7E.scale_y = 1.5
        col_BAE7E.alignment = 'Expand'.upper()
        col_BAE7E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_FD535 = col_BAE7E.row(heading='', align=True)
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
        op = row_FD535.operator('sna.uv__ca81b', text='', icon_value=_icons['align_top.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_align'
        op.sna_direction = 'UPPER'
        op = row_FD535.operator('sna.uv__b75e5', text='', icon_value=string_to_icon('SHADING_BBOX'), emboss=True, depress=False)
        row_0079E = col_BAE7E.row(heading='', align=True)
        row_0079E.alert = False
        row_0079E.enabled = True
        row_0079E.active = True
        row_0079E.use_property_split = False
        row_0079E.use_property_decorate = False
        row_0079E.scale_x = 1.0
        row_0079E.scale_y = 1.0
        row_0079E.alignment = 'Expand'.upper()
        row_0079E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_0079E.operator('sna.uv__ca81b', text='', icon_value=_icons['align_left.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_align'
        op.sna_direction = 'LEFT'
        op = row_0079E.operator('sna.uv__ca81b', text='', icon_value=_icons['align_center.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_align'
        op.sna_direction = 'CENTER'
        op = row_0079E.operator('sna.uv__ca81b', text='', icon_value=_icons['align_right.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_align'
        op.sna_direction = 'RIGHT'
        row_277B1 = col_BAE7E.row(heading='', align=True)
        row_277B1.alert = False
        row_277B1.enabled = True
        row_277B1.active = True
        row_277B1.use_property_split = False
        row_277B1.use_property_decorate = False
        row_277B1.scale_x = 1.0
        row_277B1.scale_y = 1.0
        row_277B1.alignment = 'Expand'.upper()
        row_277B1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = row_277B1.operator('sna.uv__ca81b', text='', icon_value=_icons['align_y_center.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_align'
        op.sna_direction = 'HORIZONTAL'
        op = row_277B1.operator('sna.uv__ca81b', text='', icon_value=_icons['align_bottom.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_align'
        op.sna_direction = 'BOTTOM'
        op = row_277B1.operator('sna.uv__ca81b', text='', icon_value=_icons['align_x_center.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'univ_align'
        op.sna_direction = 'VERTICAL'
        box_9168E = col_58318.box()
        box_9168E.alert = False
        box_9168E.enabled = True
        box_9168E.active = True
        box_9168E.use_property_split = False
        box_9168E.use_property_decorate = False
        box_9168E.alignment = 'Expand'.upper()
        box_9168E.scale_x = 1.0
        box_9168E.scale_y = 1.0
        if not True: box_9168E.operator_context = "EXEC_DEFAULT"
        col_BE58A = box_9168E.column(heading='', align=True)
        col_BE58A.alert = False
        col_BE58A.enabled = True
        col_BE58A.active = True
        col_BE58A.use_property_split = False
        col_BE58A.use_property_decorate = False
        col_BE58A.scale_x = 1.0
        col_BE58A.scale_y = 1.0
        col_BE58A.alignment = 'Expand'.upper()
        col_BE58A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_4F093 = col_BE58A.split(factor=0.5, align=True)
        split_4F093.alert = False
        split_4F093.enabled = True
        split_4F093.active = True
        split_4F093.use_property_split = False
        split_4F093.use_property_decorate = False
        split_4F093.scale_x = 1.0
        split_4F093.scale_y = 1.0
        split_4F093.alignment = 'Expand'.upper()
        if not True: split_4F093.operator_context = "EXEC_DEFAULT"
        col_2878F = split_4F093.column(heading='', align=True)
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
        op.sna_func_name = 'uv_scale'
        op.sna_size = (0.5, 0.5)
        op = row_353A3.operator('sna.uv__783fd', text='x2', icon_value=string_to_icon('RADIOBUT_ON'), emboss=True, depress=False)
        op.sna_func_name = 'uv_scale'
        op.sna_size = (2.0, 2.0)
        row_EED36 = split_4F093.row(heading='', align=True)
        row_EED36.alert = False
        row_EED36.enabled = True
        row_EED36.active = True
        row_EED36.use_property_split = False
        row_EED36.use_property_decorate = False
        row_EED36.scale_x = 1.0
        row_EED36.scale_y = 1.0
        row_EED36.alignment = 'Left'.upper()
        row_EED36.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_29F82 = row_EED36.column(heading='', align=True)
        col_29F82.alert = False
        col_29F82.enabled = False
        col_29F82.active = False
        col_29F82.use_property_split = False
        col_29F82.use_property_decorate = False
        col_29F82.scale_x = 1.0
        col_29F82.scale_y = 1.0
        col_29F82.alignment = 'Left'.upper()
        col_29F82.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_29F82.label(text='横', icon_value=0)
        col_29F82.label(text='竖', icon_value=0)
        col_27F48 = row_EED36.column(heading='', align=True)
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
        op.sna_func_name = 'uv_scale'
        op.sna_size = (0.5, 1.0)
        op = row_B85B8.operator('sna.uv__783fd', text='x2', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'uv_scale'
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
        op.sna_func_name = 'uv_scale'
        op.sna_size = (1.0, 0.5)
        op = row_5357C.operator('sna.uv__783fd', text='x2', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'uv_scale'
        op.sna_size = (1.0, 2.0)
        col_7C02F = col_BE58A.column(heading='', align=True)
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
            op.sna_func_name = 'uv_scale'
            op.sna_size = bpy.context.scene.sna_uv_size
            split_D6686.prop(bpy.context.scene, 'sna_uv_size', text='', icon_value=0, emboss=True)
        box_BB93D = col_58318.box()
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
        op = split_D5971.operator('sna.uv__8beae', text='', icon_value=_icons['flip_x.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'uv_flip'
        op.sna_xy = 'X'
        op = split_D5971.operator('sna.uv__8beae', text='', icon_value=_icons['flip_y.png'].icon_id, emboss=True, depress=False)
        op.sna_func_name = 'uv_flip'
        op.sna_xy = 'Y'
        split_EF950.prop(bpy.context.scene, 'sna_uv_flip_mode', text='整体', icon_value=0, emboss=True)


class SNA_PT_uv_mapping_564D9(bpy.types.Panel):
    bl_label = '排布'
    bl_idname = 'SNA_PT_uv_mapping_564D9'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 8
    bl_parent_id = 'SNA_PT_QKK_UV_F373B'
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
        op.sna_func_name = 'uv_pack'
        op = split_6F7D4.operator('sna.uvpackmaster_edf0d', text='插入', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'uv_insert'
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
        op = col_73123.operator('sna.uvpackmaster_edf0d', text='排序', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'uv_sort'
        op = col_73123.operator('sna.uvpackmaster_edf0d', text='随机', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'uv_randomly'
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
        row_19DEE.prop(bpy.context.scene.uvpm4_props.default_main_props, 'rotation_enable', text='锁定旋转', icon_value=0, emboss=True, invert_checkbox=True)
        row_19DEE.prop(bpy.context.scene.uvpm4_props.default_main_props, 'lock_overlapping_enable', text='锁定堆叠', icon_value=0, emboss=True)
        row_19DEE.prop(bpy.context.scene.uvpm4_props.default_main_props, 'precision', text='精度', icon_value=0, emboss=True)
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
        op = split_907DE.operator('sna.uvpackmaster_edf0d', text='', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)
        op.sna_func_name = 'uv_select_pinned'
        op = split_907DE.operator('sna.uvpackmaster_edf0d', text='钉', icon_value=string_to_icon('PINNED'), emboss=True, depress=False)
        op.sna_func_name = 'uv_pinned'
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
        op = split_30952.operator('sna.uvpackmaster_edf0d', text='', icon_value=string_to_icon('RESTRICT_SELECT_ON'), emboss=True, depress=False)
        op.sna_func_name = 'uv_select_unlock'
        op = split_30952.operator('sna.uvpackmaster_edf0d', text='解', icon_value=string_to_icon('UNPINNED'), emboss=True, depress=False)
        op.sna_func_name = 'uv_unlock'
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
        op = row_E9BFD.operator('sna.uv_density_585b1', text='获取', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_texel_density_get'
        op = row_E9BFD.operator('sna.uv_density_585b1', text='设置', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_texel_density_set'
        row_E9BFD.prop(bpy.context.preferences.addons['univ_qkk'].preferences, 'texel', text='', icon_value=0, emboss=True)
        op = row_E9BFD.operator('sna.uv_density_585b1', text='', icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)
        op.sna_func_name = 'univ_select_texel_density'
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
        split_81F8C = box_7F4C8.split(factor=0.800000011920929, align=False)
        split_81F8C.alert = False
        split_81F8C.enabled = True
        split_81F8C.active = True
        split_81F8C.use_property_split = False
        split_81F8C.use_property_decorate = False
        split_81F8C.scale_x = 1.0
        split_81F8C.scale_y = 1.0
        split_81F8C.alignment = 'Expand'.upper()
        if not True: split_81F8C.operator_context = "EXEC_DEFAULT"
        col_C9BFB = split_81F8C.column(heading='', align=True)
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
        op = split_FF09A.operator('sna.univ_crop_c9fd5', text='缩放', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_crop'
        op.sna_axis = 'XY'
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
        op = split_E96A8.operator('sna.univ_crop_c9fd5', text='宽', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_crop'
        op.sna_axis = 'X'
        op = split_E96A8.operator('sna.univ_crop_c9fd5', text='高', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_crop'
        op.sna_axis = 'Y'
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
        op = split_FB2BB.operator('sna.univ_crop_c9fd5', text='拉伸', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_fill'
        op.sna_axis = 'XY'
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
        op = split_D436C.operator('sna.univ_crop_c9fd5', text='宽', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_fill'
        op.sna_axis = 'X'
        op = split_D436C.operator('sna.univ_crop_c9fd5', text='高', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'univ_fill'
        op.sna_axis = 'Y'
        col_8F2D2 = split_81F8C.column(heading='', align=True)
        col_8F2D2.alert = False
        col_8F2D2.enabled = True
        col_8F2D2.active = True
        col_8F2D2.use_property_split = False
        col_8F2D2.use_property_decorate = False
        col_8F2D2.scale_x = 1.0
        col_8F2D2.scale_y = 1.0
        col_8F2D2.alignment = 'Expand'.upper()
        col_8F2D2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_8F2D2.separator(factor=1.5)
        col_8F2D2.prop(bpy.context.scene, 'sna_uv_individual', text='各面', icon_value=0, emboss=True)


class SNA_PT_panel_3497E(bpy.types.Panel):
    bl_label = '选择'
    bl_idname = 'SNA_PT_panel_3497E'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = ''
    bl_order = 10
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'SNA_PT_QKK_UV_F373B'
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
        op = grid_FD464.operator('uv.univ_select_border', text='孤岛边', icon_value=0, emboss=True, depress=False)
        op.mode = 'SELECT'
        op.border_mode = 'BORDER'
        op = grid_FD464.operator('uv.univ_check_flipped', text='反转', icon_value=0, emboss=True, depress=False)
        op = grid_FD464.operator('sna.uvpackmaster_edf0d', text='钉住', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'uv_select_pinned'
        op = grid_FD464.operator('sna.uvpackmaster_edf0d', text='未钉住', icon_value=0, emboss=True, depress=False)
        op.sna_func_name = 'uv_select_unlock'
        op = grid_FD464.operator('uv.select_overlap', text='重叠', icon_value=0, emboss=True, depress=False)
        op.extend = False
        op = grid_FD464.operator('uv.univ_check_overlap', text='堆叠', icon_value=0, emboss=True, depress=False)


class SNA_AddonPreferences_7C44E(bpy.types.AddonPreferences):
    bl_idname = __package__

    def sna_units_enum_items(self, context):
        return [("No Items", "No Items", "No generate enum items node found to create items!", "ERROR", 0)]
    sna_units: bpy.props.EnumProperty(name='Units', description='', options={'HIDDEN'}, items=[('m', 'm', 'px / m', 0, 0), ('cm', 'cm', 'px / cm', 0, 1)])
    sna_pixel: bpy.props.FloatProperty(name='Pixel', description='', options={'HIDDEN'}, default=0.0, subtype='PIXEL', unit='NONE', step=1, precision=2)

    def draw(self, context):
        if not (True):
            layout = self.layout 


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
    bpy.types.Scene.sna_uv_precision_size = bpy.props.EnumProperty(name='uv_precision_size', description='', items=[('256', '256', '', 0, 0), ('512', '512', '', 0, 1), ('1024', '1024', '', 0, 2), ('2048', '2048', '', 0, 3), ('4096', '4096', '', 0, 4), ('8192', '8192', '', 0, 5)])
    bpy.types.Scene.sna_uv_xy_tex = bpy.props.EnumProperty(name='uv_xy_tex', description='', items=[('256', '256', '', 0, 0), ('512', '512', '', 0, 1), ('1024', '1024', '', 0, 2), ('2048', '2048', '', 0, 3), ('4096', '4096', '', 0, 4), ('8192', '8192', '', 0, 5)])
    bpy.types.Scene.sna_uv_individual = bpy.props.BoolProperty(name='uv_individual', description='', default=False)
    bpy.utils.register_class(SNA_PT_QKK_UV_F373B)
    bpy.utils.register_class(SNA_AddonPreferences_7C44E)
    bpy.types.VIEW3D_HT_tool_header.prepend(sna_add_to_view3d_ht_tool_header_A112F)
    bpy.utils.register_class(SNA_OT_Uv_36619)
    bpy.utils.register_class(SNA_OT_Uv_92E7D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E4775)
    bpy.utils.register_class(SNA_PT_UV_MOVE_SIZE_F4130)
    bpy.utils.register_class(SNA_OT_Uv__Ca81B)
    bpy.utils.register_class(SNA_OT_Uv__783Fd)
    bpy.utils.register_class(SNA_OT_Uv__8Beae)
    bpy.utils.register_class(SNA_OT_Uv__B75E5)
    bpy.utils.register_class(SNA_PT_uv_quadrant_edge_alignment_EA384)
    bpy.utils.register_class(SNA_OT_Uv__Adfc0)
    bpy.utils.register_class(SNA_OT_Uv_Dac55)
    bpy.utils.register_class(SNA_OT_Uv_Ce841)
    bpy.utils.register_class(SNA_OT_Uvpackmaster_Edf0D)
    bpy.utils.register_class(SNA_OT_Uv_Density_585B1)
    bpy.utils.register_class(SNA_OT_Univ_Crop_C9Fd5)
    bpy.types.IMAGE_PT_tools_active.append(sna_add_to_image_pt_tools_active_233B9)
    bpy.utils.register_class(SNA_OT_Uv_4653D)
    bpy.utils.register_class(SNA_MT_5A68B)
    bpy.utils.register_class(SNA_OT_Uv_15342)
    bpy.utils.register_class(SNA_OT_Image_Tags_Operation_E3B60)
    bpy.utils.register_class(SNA_PT_IMAGE_TAGS_348EA)
    bpy.utils.register_class(SNA_OT_Operator_Cd023)
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
    bpy.utils.register_class(SNA_PT_unfold_ADE36)
    if not 'normalize.png' in _icons: _icons.load('normalize.png', os.path.join(os.path.dirname(__file__), 'icons', 'normalize.png'), "IMAGE")
    if not 'unwrap.png' in _icons: _icons.load('unwrap.png', os.path.join(os.path.dirname(__file__), 'icons', 'unwrap.png'), "IMAGE")
    if not 'quadrify.png' in _icons: _icons.load('quadrify.png', os.path.join(os.path.dirname(__file__), 'icons', 'quadrify.png'), "IMAGE")
    if not 'rectify.png' in _icons: _icons.load('rectify.png', os.path.join(os.path.dirname(__file__), 'icons', 'rectify.png'), "IMAGE")
    if not 'cut.png' in _icons: _icons.load('cut.png', os.path.join(os.path.dirname(__file__), 'icons', 'cut.png'), "IMAGE")
    if not 'stitch.png' in _icons: _icons.load('stitch.png', os.path.join(os.path.dirname(__file__), 'icons', 'stitch.png'), "IMAGE")
    bpy.utils.register_class(SNA_PT_uv_conversion_B5EFB)
    if not 'body.png' in _icons: _icons.load('body.png', os.path.join(os.path.dirname(__file__), 'icons', 'body.png'), "IMAGE")
    if not 'x.png' in _icons: _icons.load('x.png', os.path.join(os.path.dirname(__file__), 'icons', 'x.png'), "IMAGE")
    if not 'y.png' in _icons: _icons.load('y.png', os.path.join(os.path.dirname(__file__), 'icons', 'y.png'), "IMAGE")
    if not 'p90.png' in _icons: _icons.load('p90.png', os.path.join(os.path.dirname(__file__), 'icons', 'p90.png'), "IMAGE")
    if not 'n90.png' in _icons: _icons.load('n90.png', os.path.join(os.path.dirname(__file__), 'icons', 'n90.png'), "IMAGE")
    if not 'stack.png' in _icons: _icons.load('stack.png', os.path.join(os.path.dirname(__file__), 'icons', 'stack.png'), "IMAGE")
    if not 'symm_n_y.png' in _icons: _icons.load('symm_n_y.png', os.path.join(os.path.dirname(__file__), 'icons', 'symm_n_y.png'), "IMAGE")
    if not 'home.png' in _icons: _icons.load('home.png', os.path.join(os.path.dirname(__file__), 'icons', 'home.png'), "IMAGE")
    if not 'symm_p_x.png' in _icons: _icons.load('symm_p_x.png', os.path.join(os.path.dirname(__file__), 'icons', 'symm_p_x.png'), "IMAGE")
    if not 'symm_n_x.png' in _icons: _icons.load('symm_n_x.png', os.path.join(os.path.dirname(__file__), 'icons', 'symm_n_x.png'), "IMAGE")
    if not 'symm_p_y.png' in _icons: _icons.load('symm_p_y.png', os.path.join(os.path.dirname(__file__), 'icons', 'symm_p_y.png'), "IMAGE")
    if not 'align_top.png' in _icons: _icons.load('align_top.png', os.path.join(os.path.dirname(__file__), 'icons', 'align_top.png'), "IMAGE")
    if not 'align_left.png' in _icons: _icons.load('align_left.png', os.path.join(os.path.dirname(__file__), 'icons', 'align_left.png'), "IMAGE")
    if not 'align_center.png' in _icons: _icons.load('align_center.png', os.path.join(os.path.dirname(__file__), 'icons', 'align_center.png'), "IMAGE")
    if not 'align_right.png' in _icons: _icons.load('align_right.png', os.path.join(os.path.dirname(__file__), 'icons', 'align_right.png'), "IMAGE")
    if not 'align_y_center.png' in _icons: _icons.load('align_y_center.png', os.path.join(os.path.dirname(__file__), 'icons', 'align_y_center.png'), "IMAGE")
    if not 'align_bottom.png' in _icons: _icons.load('align_bottom.png', os.path.join(os.path.dirname(__file__), 'icons', 'align_bottom.png'), "IMAGE")
    if not 'align_x_center.png' in _icons: _icons.load('align_x_center.png', os.path.join(os.path.dirname(__file__), 'icons', 'align_x_center.png'), "IMAGE")
    if not 'flip_x.png' in _icons: _icons.load('flip_x.png', os.path.join(os.path.dirname(__file__), 'icons', 'flip_x.png'), "IMAGE")
    if not 'flip_y.png' in _icons: _icons.load('flip_y.png', os.path.join(os.path.dirname(__file__), 'icons', 'flip_y.png'), "IMAGE")
    bpy.utils.register_class(SNA_PT_uv_mapping_564D9)
    bpy.utils.register_class(SNA_PT_panel_3497E)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_MT_5A68B'
    addon_keymaps['7C159'] = (km, kmi)
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
    kmi = km.keymap_items.new('sna.uv_3dtitch_6ef3a', 'X', 'PRESS',
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
    del bpy.types.Scene.sna_uv_individual
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
    bpy.utils.unregister_class(SNA_PT_QKK_UV_F373B)
    bpy.utils.unregister_class(SNA_AddonPreferences_7C44E)
    bpy.types.VIEW3D_HT_tool_header.remove(sna_add_to_view3d_ht_tool_header_A112F)
    bpy.utils.unregister_class(SNA_OT_Uv_36619)
    bpy.utils.unregister_class(SNA_OT_Uv_92E7D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E4775)
    bpy.utils.unregister_class(SNA_PT_UV_MOVE_SIZE_F4130)
    bpy.utils.unregister_class(SNA_OT_Uv__Ca81B)
    bpy.utils.unregister_class(SNA_OT_Uv__783Fd)
    bpy.utils.unregister_class(SNA_OT_Uv__8Beae)
    bpy.utils.unregister_class(SNA_OT_Uv__B75E5)
    bpy.utils.unregister_class(SNA_PT_uv_quadrant_edge_alignment_EA384)
    bpy.utils.unregister_class(SNA_OT_Uv__Adfc0)
    bpy.utils.unregister_class(SNA_OT_Uv_Dac55)
    bpy.utils.unregister_class(SNA_OT_Uv_Ce841)
    bpy.utils.unregister_class(SNA_OT_Uvpackmaster_Edf0D)
    bpy.utils.unregister_class(SNA_OT_Uv_Density_585B1)
    bpy.utils.unregister_class(SNA_OT_Univ_Crop_C9Fd5)
    bpy.types.IMAGE_PT_tools_active.remove(sna_add_to_image_pt_tools_active_233B9)
    bpy.utils.unregister_class(SNA_OT_Uv_4653D)
    bpy.utils.unregister_class(SNA_MT_5A68B)
    bpy.utils.unregister_class(SNA_OT_Uv_15342)
    bpy.utils.unregister_class(SNA_OT_Image_Tags_Operation_E3B60)
    bpy.utils.unregister_class(SNA_PT_IMAGE_TAGS_348EA)
    bpy.utils.unregister_class(SNA_OT_Operator_Cd023)
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
    bpy.utils.unregister_class(SNA_PT_unfold_ADE36)
    bpy.utils.unregister_class(SNA_PT_uv_conversion_B5EFB)
    bpy.utils.unregister_class(SNA_PT_uv_mapping_564D9)
    bpy.utils.unregister_class(SNA_PT_panel_3497E)
