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
    "name" : "全量塌陷",
    "author" : "渠奎奎", 
    "description" : "",
    "blender" : (3, 5, 0),
    "version" : (3, 5, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "A_工具插件" 
}


import bpy
import bpy.utils.previews


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)



addon_keymaps = {}
_icons = None
class SNA_PT_ACA_69648(bpy.types.Panel):
    bl_label = '全量塌陷'
    bl_idname = 'SNA_PT_ACA_69648'
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
        col_A9C00 = layout.column(heading='', align=False)
        col_A9C00.alert = False
        col_A9C00.enabled = True
        col_A9C00.active = True
        col_A9C00.use_property_split = False
        col_A9C00.use_property_decorate = False
        col_A9C00.scale_x = 1.0
        col_A9C00.scale_y = 1.0
        col_A9C00.alignment = 'Expand'.upper()
        col_A9C00.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        box_7BE30 = col_A9C00.box()
        box_7BE30.alert = False
        box_7BE30.enabled = True
        box_7BE30.active = True
        box_7BE30.use_property_split = False
        box_7BE30.use_property_decorate = False
        box_7BE30.alignment = 'Expand'.upper()
        box_7BE30.scale_x = 1.0
        box_7BE30.scale_y = 1.0
        box_7BE30.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        box_7BE30.label(text='选中数量：' + str(len(bpy.context.view_layer.objects.selected.values())), icon_value=0)
        col_BB10F = col_A9C00.column(heading='', align=False)
        col_BB10F.alert = False
        col_BB10F.enabled = True
        col_BB10F.active = True
        col_BB10F.use_property_split = False
        col_BB10F.use_property_decorate = False
        col_BB10F.scale_x = 1.0
        col_BB10F.scale_y = 1.5
        col_BB10F.alignment = 'Expand'.upper()
        col_BB10F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_9B3BA = col_BB10F.split(factor=0.699999988079071, align=True)
        split_9B3BA.alert = False
        split_9B3BA.enabled = True
        split_9B3BA.active = True
        split_9B3BA.use_property_split = False
        split_9B3BA.use_property_decorate = False
        split_9B3BA.scale_x = 1.0
        split_9B3BA.scale_y = 1.0
        split_9B3BA.alignment = 'Expand'.upper()
        split_9B3BA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = split_9B3BA.operator('sna.my_generic_operator_3a3e2', text='处理曲线', icon_value=string_to_icon('MOD_THICKNESS'), emboss=True, depress=False)
        op.sna_new_property = 'CURVE'
        op = split_9B3BA.operator('sna.my_generic_operator_fac49', text='选曲线', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = 'CURVE'
        split_4B643 = col_BB10F.split(factor=0.699999988079071, align=True)
        split_4B643.alert = False
        split_4B643.enabled = True
        split_4B643.active = True
        split_4B643.use_property_split = False
        split_4B643.use_property_decorate = False
        split_4B643.scale_x = 1.0
        split_4B643.scale_y = 1.0
        split_4B643.alignment = 'Expand'.upper()
        split_4B643.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = split_4B643.operator('sna.my_generic_operator_3a3e2', text='处理网格', icon_value=string_to_icon('OUTLINER_OB_MESH'), emboss=True, depress=False)
        op.sna_new_property = 'MESH'
        op = split_4B643.operator('sna.my_generic_operator_fac49', text='选网格', icon_value=0, emboss=True, depress=False)
        op.sna_new_property = 'MESH'
        split_B5ED0 = col_BB10F.split(factor=0.699999988079071, align=True)
        split_B5ED0.alert = False
        split_B5ED0.enabled = True
        split_B5ED0.active = True
        split_B5ED0.use_property_split = False
        split_B5ED0.use_property_decorate = False
        split_B5ED0.scale_x = 1.0
        split_B5ED0.scale_y = 1.0
        split_B5ED0.alignment = 'Expand'.upper()
        split_B5ED0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = split_B5ED0.operator('sna.my_generic_operator_ee2b6', text='处理实例', icon_value=string_to_icon('FILE_3D'), emboss=True, depress=False)
        op = split_B5ED0.operator('sna.my_generic_operator_4e7e7', text='选实例', icon_value=0, emboss=True, depress=False)
        layout.separator(factor=1.5)
        col_67C54 = layout.column(heading='', align=False)
        col_67C54.alert = False
        col_67C54.enabled = True
        col_67C54.active = True
        col_67C54.use_property_split = False
        col_67C54.use_property_decorate = False
        col_67C54.scale_x = 1.0
        col_67C54.scale_y = 1.0
        col_67C54.alignment = 'Expand'.upper()
        col_67C54.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_67C54.operator('object.move_to_collection', text='移动到集合', icon_value=string_to_icon('OUTLINER_COLLECTION'), emboss=True, depress=False)
        split_6486C = col_67C54.split(factor=0.5, align=True)
        split_6486C.alert = False
        split_6486C.enabled = True
        split_6486C.active = True
        split_6486C.use_property_split = False
        split_6486C.use_property_decorate = False
        split_6486C.scale_x = 1.0
        split_6486C.scale_y = 1.0
        split_6486C.alignment = 'Expand'.upper()
        split_6486C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = split_6486C.operator('object.parent_clear', text='清除父子集', icon_value=0, emboss=True, depress=False)
        op.type = 'CLEAR_KEEP_TRANSFORM'
        op = split_6486C.operator('outliner.orphans_purge', text='清理数据', icon_value=0, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_49105(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_49105"
    bl_label = "不可选中清理"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        for i_8721D in range(len(bpy.context.scene.collection.children)):
            bpy.context.scene.collection.children[i_8721D].hide_select = False
        for i_D3944 in range(len(bpy.context.scene.objects)):
            bpy.context.scene.objects[i_D3944].hide_select = False
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Ee2B6(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_ee2b6"
    bl_label = "处理实例"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        for obj in bpy.context.scene.objects:
            # 检查对象是否属于实例化集合
            if obj.instance_collection is not None:
                # 选择实例对象
                bpy.context.view_layer.objects.active = obj
        # 遍历场景中的所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象是否属于实例化集合
            if obj.instance_collection is not None:
                # 将实例对象设置为选中状态
                obj.select_set(True)
        bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True, material=False, animation=False, obdata_animation=False)
        bpy.ops.object.duplicates_make_real()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_3A3E2(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3a3e2"
    bl_label = "处理模型"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='类型', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.ops.sna.my_generic_operator_49105()
        bpy.ops.object.select_by_type(extend=False, type=self.sna_new_property)
        for i_34AE8 in range(len(bpy.context.view_layer.objects.selected)):
            pass
        bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_34AE8]
        bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True, material=False, animation=False, obdata_animation=False)
        bpy.ops.object.convert(target='MESH')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Fac49(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_fac49"
    bl_label = "选择"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='类型', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.ops.sna.my_generic_operator_49105()
        bpy.ops.object.select_by_type(extend=False, type=self.sna_new_property)
        for i_ACD5A in range(len(bpy.context.view_layer.objects.selected)):
            pass
        bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_ACD5A]
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_4E7E7(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_4e7e7"
    bl_label = "选实例"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        for obj in bpy.context.scene.objects:
            # 检查对象是否属于实例化集合
            if obj.instance_collection is not None:
                # 选择实例对象
                bpy.context.view_layer.objects.active = obj
        # 遍历场景中的所有对象
        for obj in bpy.context.scene.objects:
            # 检查对象是否属于实例化集合
            if obj.instance_collection is not None:
                # 将实例对象设置为选中状态
                obj.select_set(True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_PT_ACA_69648)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_49105)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Ee2B6)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3A3E2)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Fac49)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_4E7E7)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_PT_ACA_69648)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_49105)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Ee2B6)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3A3E2)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Fac49)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_4E7E7)
