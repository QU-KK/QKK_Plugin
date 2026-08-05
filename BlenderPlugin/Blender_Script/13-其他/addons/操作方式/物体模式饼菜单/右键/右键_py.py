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
    "name" : "Operation_v3",
    "author" : "渠奎奎", 
    "description" : "操作方式4.2",
    "blender" : (4, 2, 0),
    "version" : (3, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews
import numpy as np
import math




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
node_tree_005 = {'sna_mod_exist': False, }
class SNA_OT_My_Generic_Operator_8851B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_8851b"
    bl_label = "点模式"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set('INVOKE_DEFAULT', mode='EDIT')
        bpy.ops.mesh.select_mode('INVOKE_DEFAULT', type='VERT')
        bpy.ops.wm.tool_set_by_id('INVOKE_DEFAULT', name='builtin.move')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_B646B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b646b"
    bl_label = "线模式"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set('INVOKE_DEFAULT', mode='EDIT')
        bpy.ops.mesh.select_mode('INVOKE_DEFAULT', type='EDGE')
        bpy.ops.wm.tool_set_by_id('INVOKE_DEFAULT', name='builtin.move')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_7Cf3D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_7cf3d"
    bl_label = "面模式"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set('INVOKE_DEFAULT', mode='EDIT')
        bpy.ops.mesh.select_mode('INVOKE_DEFAULT', type='FACE')
        bpy.ops.wm.tool_set_by_id('INVOKE_DEFAULT', name='builtin.move')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_6B41D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6b41d"
    bl_label = "常规处理"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_De723(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_de723"
    bl_label = "底部居中"
    bl_description = "底部居中"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        from mathutils import Matrix, Vector

        def origin_to_bottom(ob, matrix=Matrix(), use_verts=False):
            me = ob.data
            mw = ob.matrix_world
            if use_verts:
                data = (v.co for v in me.vertices)
            else:
                data = (Vector(v) for v in ob.bound_box)
            coords = np.array([matrix @ v for v in data])
            z = coords.T[2]
            mins = np.take(coords, np.where(z == z.min())[0], axis=0)
            o = Vector(np.mean(mins, axis=0))
            o = matrix.inverted() @ o
            me.transform(Matrix.Translation(-o))
            mw.translation = mw @ o  
        for o in bpy.context.selected_objects:
            if o.type == 'MESH':
                origin_to_bottom(o)
        self.report({'INFO'}, message='底部居中成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_MT_4266A(bpy.types.Menu):
    bl_idname = "SNA_MT_4266A"
    bl_label = "(Qkk_3DMode)Obj右键"

    @classmethod
    def poll(cls, context):
        return not ((None == bpy.context.view_layer.objects.active))

    def draw(self, context):
        layout = self.layout.menu_pie()
        op = layout.operator('sna.my_generic_operator_8851b', text='点', icon_value=string_to_icon('LAYER_ACTIVE'), emboss=True, depress=False)
        if bpy.context.view_layer.objects.active.type == 'CURVE':
            op = layout.operator('object.mode_set', text='曲线', icon_value=string_to_icon('OUTLINER_OB_CURVE'), emboss=True, depress=False)
            op.mode = 'EDIT'
            op.toggle = False
        else:
            op = layout.operator('sna.my_generic_operator_7cf3d', text='面', icon_value=string_to_icon('MESH_PLANE'), emboss=True, depress=False)
        box_C6F38 = layout.box()
        box_C6F38.alert = False
        box_C6F38.enabled = True
        box_C6F38.active = True
        box_C6F38.use_property_split = False
        box_C6F38.use_property_decorate = False
        box_C6F38.alignment = 'Expand'.upper()
        box_C6F38.scale_x = 1.0
        box_C6F38.scale_y = 1.0
        if not True: box_C6F38.operator_context = "EXEC_DEFAULT"
        col_381D5 = box_C6F38.column(heading='', align=True)
        col_381D5.alert = False
        col_381D5.enabled = 'OBJECT'==bpy.context.mode
        col_381D5.active = True
        col_381D5.use_property_split = False
        col_381D5.use_property_decorate = False
        col_381D5.scale_x = 1.0
        col_381D5.scale_y = 1.2999999523162842
        col_381D5.alignment = 'Expand'.upper()
        col_381D5.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        box_743FA = col_381D5.box()
        box_743FA.alert = False
        box_743FA.enabled = True
        box_743FA.active = True
        box_743FA.use_property_split = False
        box_743FA.use_property_decorate = False
        box_743FA.alignment = 'Expand'.upper()
        box_743FA.scale_x = 1.0
        box_743FA.scale_y = 1.0
        if not True: box_743FA.operator_context = "EXEC_DEFAULT"
        col_EB992 = box_743FA.column(heading='', align=True)
        col_EB992.alert = False
        col_EB992.enabled = True
        col_EB992.active = True
        col_EB992.use_property_split = False
        col_EB992.use_property_decorate = False
        col_EB992.scale_x = 1.0
        col_EB992.scale_y = 1.0
        col_EB992.alignment = 'Expand'.upper()
        col_EB992.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_EB992.operator('sna.merge_model_f6016', text='', icon_value=string_to_icon('SNAP_PEEL_OBJECT'), emboss=True, depress=False)
        split_B4C2F = col_EB992.split(factor=0.5, align=True)
        split_B4C2F.alert = False
        split_B4C2F.enabled = True
        split_B4C2F.active = True
        split_B4C2F.use_property_split = False
        split_B4C2F.use_property_decorate = False
        split_B4C2F.scale_x = 1.0
        split_B4C2F.scale_y = 1.0
        split_B4C2F.alignment = 'Expand'.upper()
        if not True: split_B4C2F.operator_context = "EXEC_DEFAULT"
        op = split_B4C2F.operator('sna.my_generic_operator_5f057', text='', icon_value=string_to_icon('IMGDISPLAY'), emboss=True, depress=False)
        op = split_B4C2F.operator('sna.my_generic_operator_c41ea', text='', icon_value=string_to_icon('OUTLINER_DATA_POINTCLOUD'), emboss=True, depress=False)
        box_B8675 = col_381D5.box()
        box_B8675.alert = False
        box_B8675.enabled = True
        box_B8675.active = True
        box_B8675.use_property_split = False
        box_B8675.use_property_decorate = False
        box_B8675.alignment = 'Expand'.upper()
        box_B8675.scale_x = 1.0
        box_B8675.scale_y = 1.0
        if not True: box_B8675.operator_context = "EXEC_DEFAULT"
        col_EFAC1 = box_B8675.column(heading='', align=True)
        col_EFAC1.alert = False
        col_EFAC1.enabled = True
        col_EFAC1.active = True
        col_EFAC1.use_property_split = False
        col_EFAC1.use_property_decorate = False
        col_EFAC1.scale_x = 1.0
        col_EFAC1.scale_y = 1.0
        col_EFAC1.alignment = 'Expand'.upper()
        col_EFAC1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_EFAC1.operator('object.origin_set', text='中心居中', icon_value=string_to_icon('OBJECT_ORIGIN'), emboss=True, depress=False)
        op.type = 'ORIGIN_GEOMETRY'
        op = col_EFAC1.operator('sna.my_generic_operator_de723', text='底部居中', icon_value=string_to_icon('ORIENTATION_GLOBAL'), emboss=True, depress=False)
        op = col_EFAC1.operator('object.align', text='对齐地面', icon_value=string_to_icon('AXIS_TOP'), emboss=True, depress=False)
        op.bb_quality = True
        op.align_mode = 'OPT_1'
        op.relative_to = 'OPT_1'
        op.align_axis = set(['Z'])
        op = col_EFAC1.operator('object.transform_apply', text='冻结变换', icon_value=string_to_icon('ORIENTATION_GLOBAL'), emboss=True, depress=False)
        op.location = False
        op.rotation = True
        op.scale = True
        op.properties = True
        box_2FB4A = col_381D5.box()
        box_2FB4A.alert = False
        box_2FB4A.enabled = True
        box_2FB4A.active = True
        box_2FB4A.use_property_split = False
        box_2FB4A.use_property_decorate = False
        box_2FB4A.alignment = 'Expand'.upper()
        box_2FB4A.scale_x = 1.0
        box_2FB4A.scale_y = 1.0
        if not True: box_2FB4A.operator_context = "EXEC_DEFAULT"
        col_CE271 = box_2FB4A.column(heading='', align=True)
        col_CE271.alert = False
        col_CE271.enabled = True
        col_CE271.active = True
        col_CE271.use_property_split = False
        col_CE271.use_property_decorate = False
        col_CE271.scale_x = 1.0
        col_CE271.scale_y = 1.0
        col_CE271.alignment = 'Expand'.upper()
        col_CE271.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_CE271.operator('sna.my_generic_operator_4531f', text='清空变换', icon_value=string_to_icon('ORIENTATION_GIMBAL'), emboss=True, depress=False)
        op = col_CE271.operator('object.material_slot_remove_unused', text='未使用槽', icon_value=string_to_icon('X'), emboss=True, depress=False)
        col_CE271.prop(bpy.context.area.spaces[0].overlay, 'show_face_orientation', text='法向正反', icon_value=string_to_icon('MOD_EXPLODE'), emboss=True, toggle=True)
        op = layout.operator('sna.my_generic_operator_b646b', text='线', icon_value=563, emboss=True, depress=False)
        op = layout.operator('view3d.localview', text='独显', icon_value=string_to_icon('OBJECT_HIDDEN'), emboss=True, depress=False)
        op = layout.operator('object.mode_set', text='物体', icon_value=string_to_icon('CUBE'), emboss=True, depress=False)
        op.mode = 'OBJECT'
        op = layout.operator('sna.my_generic_operator_882a0', text='平滑模式', icon_value=string_to_icon('IPO_ELASTIC'), emboss=True, depress=False)
        layout.prop(bpy.context.area.spaces[0].overlay, 'show_wireframes', text='线框', icon_value=string_to_icon('SPHERE'), emboss=True)


class SNA_OT_My_Generic_Operator_D4172(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d4172"
    bl_label = "应用变换"
    bl_description = "应用变换"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.ops.object.transforms_to_deltas(mode=bpy.context.scene.sna_controls_increment, reset_values=True)
        self.report({'INFO'}, message='应用变换成功！')
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(bpy.context.scene, 'sna_controls_increment', text='', icon_value=0, emboss=True, toggle=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=150)


class SNA_OT_My_Generic_Operator_882A0(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_882a0"
    bl_label = "平滑模式"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.ops.wm.call_panel(name="SNA_PT_smooth_mode_3B492", keep_open=True)
        return self.execute(context)


class SNA_OT_Uv_Fbb30(bpy.types.Operator):
    bl_idname = "sna.uv_fbb30"
    bl_label = "按UV边届"
    bl_description = "按UV边届分软硬边"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.seams_from_islands(mark_seams=False, mark_sharp=True)
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.report({'INFO'}, message='按UV边届分软硬边成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_3C010(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3c010"
    bl_label = "按角度"
    bl_description = "按角度分软硬边"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        angles = math.radians(bpy.context.scene.sna_controls_smooth_angle)
        edges = bpy.context.scene.sna_controls_sharp_edge
        bpy.ops.object.shade_smooth_by_angle(angle=angles, keep_sharp_edges=edges)
        self.report({'INFO'}, message='按角度分软硬边成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_5F057(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_5f057"
    bl_label = "按孤岛_炸开"
    bl_description = "按孤岛_炸开"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.report({'INFO'}, message='按孤岛炸开成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        for i_5563D in range(len(bpy.context.view_layer.objects.selected)):
            pass
        bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_5563D]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_C41Ea(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_c41ea"
    bl_label = "按材质_炸开"
    bl_description = "按材质_炸开"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.separate(type='MATERIAL')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.report({'INFO'}, message='按材质炸开成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        for i_F3CC3 in range(len(bpy.context.view_layer.objects.selected)):
            pass
        bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_F3CC3]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_4531F(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_4531f"
    bl_label = "清空变换"
    bl_description = "清空变换"
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
        col_16D76 = layout.column(heading='', align=False)
        col_16D76.alert = False
        col_16D76.enabled = True
        col_16D76.active = True
        col_16D76.use_property_split = False
        col_16D76.use_property_decorate = False
        col_16D76.scale_x = 1.0
        col_16D76.scale_y = 1.2000000476837158
        col_16D76.alignment = 'Expand'.upper()
        col_16D76.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_16D76.operator('object.location_clear', text='位置', icon_value=string_to_icon('ORIENTATION_GLOBAL'), emboss=True, depress=False)
        op.clear_delta = True
        op = col_16D76.operator('object.rotation_clear', text='旋转', icon_value=string_to_icon('ORIENTATION_GIMBAL'), emboss=True, depress=False)
        op.clear_delta = True
        op = col_16D76.operator('object.scale_clear', text='缩放', icon_value=string_to_icon('ORIENTATION_LOCAL'), emboss=True, depress=False)
        op.clear_delta = True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=100)


class SNA_OT_My_Generic_Operator_05B21(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_05b21"
    bl_label = "清除自定义法向"
    bl_description = "清除自定义法向"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_7FB96 in range(len(bpy.context.view_layer.objects.selected)):
            bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_7FB96]
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        self.report({'INFO'}, message='清除自定义法向成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_6Daba(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6daba"
    bl_label = "平滑法向"
    bl_description = "平滑法向"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.smooth_normals(factor=0.25)
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.report({'INFO'}, message='平滑法向成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Ce977(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_ce977"
    bl_label = "重置法线"
    bl_description = "重置法线"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.mesh.normals_tools(mode='RESET')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        self.report({'INFO'}, message='重置法线成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Merge_Model_F6016(bpy.types.Operator):
    bl_idname = "sna.merge_model_f6016"
    bl_label = "Merge_Model"
    bl_description = "合并选择物体"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree_005['sna_mod_exist'] = False
        for i_64B53 in range(len(bpy.context.view_layer.objects.selected)):
            if (bpy.context.view_layer.objects.selected[i_64B53] == bpy.context.view_layer.objects.active):
                node_tree_005['sna_mod_exist'] = True
        if node_tree_005['sna_mod_exist']:
            bpy.ops.object.join()
            self.report({'INFO'}, message='合并完成！')
        else:
            for i_2CDA9 in range(len(bpy.context.view_layer.objects.selected)):
                pass
            bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_2CDA9]
            bpy.ops.object.join()
            self.report({'INFO'}, message='合并完成！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_D29Cd(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d29cd"
    bl_label = "使用法向矫正修改器"
    bl_description = "使用法向矫正修改器"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_51CB7 in range(len(bpy.context.view_layer.objects.selected)):
            for i_215B7 in range(len(bpy.context.view_layer.objects.selected[i_51CB7].modifiers)):
                if '法向处理' in bpy.context.view_layer.objects.selected[i_51CB7].modifiers[i_215B7].name:
                    bpy.context.view_layer.objects.selected[i_51CB7].modifiers.remove(modifier=bpy.context.view_layer.objects.selected[i_51CB7].modifiers[i_215B7], )
            modifier_41FA0 = bpy.context.view_layer.objects.selected[i_51CB7].modifiers.new(name='法向处理', type='WEIGHTED_NORMAL', )
            modifier_41FA0.keep_sharp = True
        self.report({'INFO'}, message='使用法向矫正修改器完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_D1Bb9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_d1bb9"
    bl_label = "自定义法向应用"
    bl_description = "自定义法向应用"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_C3AC9 in range(len(bpy.context.view_layer.objects.selected)):
            obj = bpy.context.view_layer.objects.selected[i_C3AC9]
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier="法向处理")
            self.report({'INFO'}, message='自定义法向应用成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_smooth_mode_3B492(bpy.types.Panel):
    bl_label = '平滑模式'
    bl_idname = 'SNA_PT_smooth_mode_3B492'
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
        col_F6671 = layout.column(heading='', align=False)
        col_F6671.alert = False
        col_F6671.enabled = True
        col_F6671.active = True
        col_F6671.use_property_split = False
        col_F6671.use_property_decorate = False
        col_F6671.scale_x = 1.0
        col_F6671.scale_y = 1.2999999523162842
        col_F6671.alignment = 'Expand'.upper()
        col_F6671.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        box_C5027 = col_F6671.box()
        box_C5027.alert = False
        box_C5027.enabled = True
        box_C5027.active = True
        box_C5027.use_property_split = False
        box_C5027.use_property_decorate = False
        box_C5027.alignment = 'Expand'.upper()
        box_C5027.scale_x = 1.0
        box_C5027.scale_y = 1.0
        if not True: box_C5027.operator_context = "EXEC_DEFAULT"
        col_B74BD = box_C5027.column(heading='', align=False)
        col_B74BD.alert = False
        col_B74BD.enabled = True
        col_B74BD.active = True
        col_B74BD.use_property_split = False
        col_B74BD.use_property_decorate = False
        col_B74BD.scale_x = 1.0
        col_B74BD.scale_y = 1.0
        col_B74BD.alignment = 'Expand'.upper()
        col_B74BD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_030D3 = col_B74BD.split(factor=0.5, align=True)
        split_030D3.alert = False
        split_030D3.enabled = True
        split_030D3.active = True
        split_030D3.use_property_split = False
        split_030D3.use_property_decorate = False
        split_030D3.scale_x = 1.0
        split_030D3.scale_y = 1.0
        split_030D3.alignment = 'Expand'.upper()
        if not True: split_030D3.operator_context = "EXEC_DEFAULT"
        op = split_030D3.operator('object.shade_smooth', text='平滑', icon_value=string_to_icon('IPO_CONSTANT'), emboss=True, depress=False)
        op.keep_sharp_edges = False
        op = split_030D3.operator('object.shade_flat', text='平直', icon_value=string_to_icon('IPO_EASE_IN'), emboss=True, depress=False)
        op.keep_sharp_edges = False
        box_FE350 = col_B74BD.box()
        box_FE350.alert = False
        box_FE350.enabled = True
        box_FE350.active = True
        box_FE350.use_property_split = False
        box_FE350.use_property_decorate = False
        box_FE350.alignment = 'Expand'.upper()
        box_FE350.scale_x = 1.0
        box_FE350.scale_y = 1.0
        if not True: box_FE350.operator_context = "EXEC_DEFAULT"
        col_02B9F = box_FE350.column(heading='', align=True)
        col_02B9F.alert = False
        col_02B9F.enabled = True
        col_02B9F.active = True
        col_02B9F.use_property_split = False
        col_02B9F.use_property_decorate = False
        col_02B9F.scale_x = 1.0
        col_02B9F.scale_y = 1.0
        col_02B9F.alignment = 'Expand'.upper()
        col_02B9F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_02B9F.operator('sna.my_generic_operator_3c010', text='按角度', icon_value=string_to_icon('MOD_SMOOTH'), emboss=True, depress=False)
        split_DEC3D = col_02B9F.split(factor=0.5, align=True)
        split_DEC3D.alert = False
        split_DEC3D.enabled = True
        split_DEC3D.active = True
        split_DEC3D.use_property_split = False
        split_DEC3D.use_property_decorate = False
        split_DEC3D.scale_x = 1.0
        split_DEC3D.scale_y = 0.800000011920929
        split_DEC3D.alignment = 'Expand'.upper()
        if not True: split_DEC3D.operator_context = "EXEC_DEFAULT"
        split_DEC3D.prop(bpy.context.scene, 'sna_controls_smooth_angle', text='', icon_value=0, emboss=True)
        split_DEC3D.prop(bpy.context.scene, 'sna_controls_sharp_edge', text='保持锐边', icon_value=0, emboss=True)
        op = col_B74BD.operator('sna.uv_fbb30', text='按UV边', icon_value=string_to_icon('MOD_LATTICE'), emboss=True, depress=False)
        split_CEE39 = col_F6671.split(factor=0.5, align=True)
        split_CEE39.alert = False
        split_CEE39.enabled = True
        split_CEE39.active = True
        split_CEE39.use_property_split = False
        split_CEE39.use_property_decorate = False
        split_CEE39.scale_x = 1.0
        split_CEE39.scale_y = 1.0
        split_CEE39.alignment = 'Expand'.upper()
        if not True: split_CEE39.operator_context = "EXEC_DEFAULT"
        op = split_CEE39.operator('sna.my_generic_operator_d29cd', text='法向修改器', icon_value=string_to_icon('MOD_NORMALEDIT'), emboss=True, depress=False)
        op = split_CEE39.operator('sna.my_generic_operator_d1bb9', text='应用', icon_value=string_to_icon('LOCKED'), emboss=True, depress=False)
        op = col_F6671.operator('sna.my_generic_operator_05b21', text='清除自定义法向', icon_value=string_to_icon('UNLOCKED'), emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_controls_increment = bpy.props.EnumProperty(name='controls_increment', description='', options={'HIDDEN'}, items=[('ALL', 'ALL', '全部', 0, 0), ('LOC', 'LOC', '位置', 593, 1), ('ROT', 'ROT', '旋转', 594, 2), ('SCALE', 'SCALE', '缩放', 618, 3)])
    bpy.types.Scene.sna_controls_sharp_edge = bpy.props.BoolProperty(name='controls_sharp_edge', description='', default=False)
    bpy.types.Scene.sna_controls_smooth_angle = bpy.props.FloatProperty(name='controls_smooth_angle', description='', default=45.0, subtype='NONE', unit='NONE', min=0.0, max=180.0, step=1, precision=1)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_8851B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B646B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_7Cf3D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6B41D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_De723)
    bpy.utils.register_class(SNA_MT_4266A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D4172)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_882A0)
    bpy.utils.register_class(SNA_OT_Uv_Fbb30)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3C010)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_5F057)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_C41Ea)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_4531F)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_05B21)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6Daba)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Ce977)
    bpy.utils.register_class(SNA_OT_Merge_Model_F6016)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D29Cd)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D1Bb9)
    bpy.utils.register_class(SNA_PT_smooth_mode_3B492)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'RIGHTMOUSE', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.name = 'SNA_MT_4266A'
    addon_keymaps['27D75'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_controls_smooth_angle
    del bpy.types.Scene.sna_controls_sharp_edge
    del bpy.types.Scene.sna_controls_increment
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_8851B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B646B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_7Cf3D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6B41D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_De723)
    bpy.utils.unregister_class(SNA_MT_4266A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D4172)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_882A0)
    bpy.utils.unregister_class(SNA_OT_Uv_Fbb30)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3C010)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_5F057)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_C41Ea)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_4531F)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_05B21)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6Daba)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Ce977)
    bpy.utils.unregister_class(SNA_OT_Merge_Model_F6016)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D29Cd)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D1Bb9)
    bpy.utils.unregister_class(SNA_PT_smooth_mode_3B492)
