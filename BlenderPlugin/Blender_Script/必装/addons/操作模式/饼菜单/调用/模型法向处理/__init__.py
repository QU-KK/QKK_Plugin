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
    "name" : "Mod_Normal",
    "author" : "qkk", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "命令集" 
}


import bpy
import bpy.utils.previews
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


class SNA_OT_Mod_Normal_33321(bpy.types.Operator):
    bl_idname = "sna.mod_normal_33321"
    bl_label = "Mod_Normal"
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

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_controls_sharp_edge = bpy.props.BoolProperty(name='controls_sharp_edge', description='', default=False)
    bpy.types.Scene.sna_controls_smooth_angle = bpy.props.FloatProperty(name='controls_smooth_angle', description='', default=45.0, subtype='NONE', unit='NONE', min=0.0, max=180.0, step=1, precision=1)
    bpy.utils.register_class(SNA_OT_Uv_Fbb30)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3C010)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_05B21)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D29Cd)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_D1Bb9)
    bpy.utils.register_class(SNA_OT_Mod_Normal_33321)


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
    bpy.utils.unregister_class(SNA_OT_Uv_Fbb30)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3C010)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_05B21)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D29Cd)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_D1Bb9)
    bpy.utils.unregister_class(SNA_OT_Mod_Normal_33321)
