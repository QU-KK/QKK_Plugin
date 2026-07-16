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
    "name" : "Batch_Renaming",
    "author" : "Qkk", 
    "description" : "",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "QKK_通用" 
}


import bpy
import bpy.utils.previews


addon_keymaps = {}
_icons = None
node_tree = {'sna_name_id': '', }
class SNA_PT_batch_renaming_097E6(bpy.types.Panel):
    bl_label = '批量重命名'
    bl_idname = 'SNA_PT_batch_renaming_097E6'
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
        box_372BD = layout.box()
        box_372BD.alert = False
        box_372BD.enabled = True
        box_372BD.active = True
        box_372BD.use_property_split = False
        box_372BD.use_property_decorate = False
        box_372BD.alignment = 'Expand'.upper()
        box_372BD.scale_x = 1.0
        box_372BD.scale_y = 1.0
        if not True: box_372BD.operator_context = "EXEC_DEFAULT"
        col_D02FD = box_372BD.column(heading='', align=True)
        col_D02FD.alert = False
        col_D02FD.enabled = True
        col_D02FD.active = True
        col_D02FD.use_property_split = False
        col_D02FD.use_property_decorate = False
        col_D02FD.scale_x = 1.0
        col_D02FD.scale_y = 1.2000000476837158
        col_D02FD.alignment = 'Expand'.upper()
        col_D02FD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_ADE64 = col_D02FD.column(heading='', align=True)
        col_ADE64.alert = False
        col_ADE64.enabled = True
        col_ADE64.active = True
        col_ADE64.use_property_split = False
        col_ADE64.use_property_decorate = False
        col_ADE64.scale_x = 1.0
        col_ADE64.scale_y = 1.0
        col_ADE64.alignment = 'Expand'.upper()
        col_ADE64.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        split_42586 = col_ADE64.split(factor=0.30000001192092896, align=True)
        split_42586.alert = False
        split_42586.enabled = True
        split_42586.active = True
        split_42586.use_property_split = False
        split_42586.use_property_decorate = False
        split_42586.scale_x = 1.0
        split_42586.scale_y = 1.0
        split_42586.alignment = 'Expand'.upper()
        if not True: split_42586.operator_context = "EXEC_DEFAULT"
        split_42586.prop(bpy.context.scene, 'sna_base_name_bool', text='基础名称：', icon_value=0, emboss=True)
        split_42586.prop(bpy.context.scene, 'sna_base_name', text='', icon_value=0, emboss=True)
        col_ADE64.separator(factor=1.0)
        split_83238 = col_ADE64.split(factor=0.30000001192092896, align=True)
        split_83238.alert = False
        split_83238.enabled = True
        split_83238.active = True
        split_83238.use_property_split = False
        split_83238.use_property_decorate = False
        split_83238.scale_x = 1.0
        split_83238.scale_y = 1.0
        split_83238.alignment = 'Expand'.upper()
        if not True: split_83238.operator_context = "EXEC_DEFAULT"
        split_83238.prop(bpy.context.scene, 'sna_replace_in_string_bool', text='替换：', icon_value=0, emboss=True)
        col_DFED9 = split_83238.column(heading='', align=True)
        col_DFED9.alert = False
        col_DFED9.enabled = True
        col_DFED9.active = True
        col_DFED9.use_property_split = False
        col_DFED9.use_property_decorate = False
        col_DFED9.scale_x = 1.0
        col_DFED9.scale_y = 1.0
        col_DFED9.alignment = 'Expand'.upper()
        col_DFED9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_DFED9.prop(bpy.context.scene, 'sna_replace_in_string_input', text='原始', icon_value=0, emboss=True)
        col_DFED9.prop(bpy.context.scene, 'sna_replace_in_string_output', text='新增', icon_value=0, emboss=True)
        col_D02FD.separator(factor=2.0)
        split_2D837 = col_D02FD.split(factor=0.30000001192092896, align=True)
        split_2D837.alert = False
        split_2D837.enabled = True
        split_2D837.active = True
        split_2D837.use_property_split = False
        split_2D837.use_property_decorate = False
        split_2D837.scale_x = 1.0
        split_2D837.scale_y = 1.0
        split_2D837.alignment = 'Expand'.upper()
        if not True: split_2D837.operator_context = "EXEC_DEFAULT"
        split_2D837.prop(bpy.context.scene, 'sna_qian_name_bool', text='前缀：', icon_value=0, emboss=True)
        split_2D837.prop(bpy.context.scene, 'sna_qian_name', text='', icon_value=0, emboss=True)
        split_789B9 = col_D02FD.split(factor=0.30000001192092896, align=True)
        split_789B9.alert = False
        split_789B9.enabled = True
        split_789B9.active = True
        split_789B9.use_property_split = False
        split_789B9.use_property_decorate = False
        split_789B9.scale_x = 1.0
        split_789B9.scale_y = 1.0
        split_789B9.alignment = 'Expand'.upper()
        if not True: split_789B9.operator_context = "EXEC_DEFAULT"
        split_789B9.prop(bpy.context.scene, 'sna_qian_delete_bool', text='删除前：', icon_value=0, emboss=True)
        split_789B9.prop(bpy.context.scene, 'sna_qian_delete_id', text='', icon_value=0, emboss=True)
        col_D02FD.separator(factor=2.0)
        split_0E95D = col_D02FD.split(factor=0.30000001192092896, align=True)
        split_0E95D.alert = False
        split_0E95D.enabled = True
        split_0E95D.active = True
        split_0E95D.use_property_split = False
        split_0E95D.use_property_decorate = False
        split_0E95D.scale_x = 1.0
        split_0E95D.scale_y = 1.0
        split_0E95D.alignment = 'Expand'.upper()
        if not True: split_0E95D.operator_context = "EXEC_DEFAULT"
        split_0E95D.prop(bpy.context.scene, 'sna_id_bool', text='ID：', icon_value=0, emboss=True)
        split_0E95D.prop(bpy.context.scene, 'sna_id_weishu', text='位数', icon_value=0, emboss=True)
        col_D02FD.separator(factor=2.0)
        split_A53CB = col_D02FD.split(factor=0.30000001192092896, align=True)
        split_A53CB.alert = False
        split_A53CB.enabled = True
        split_A53CB.active = True
        split_A53CB.use_property_split = False
        split_A53CB.use_property_decorate = False
        split_A53CB.scale_x = 1.0
        split_A53CB.scale_y = 1.0
        split_A53CB.alignment = 'Expand'.upper()
        if not True: split_A53CB.operator_context = "EXEC_DEFAULT"
        split_A53CB.prop(bpy.context.scene, 'sna_hou_name_bool', text='后缀：', icon_value=0, emboss=True)
        split_A53CB.prop(bpy.context.scene, 'sna_hou_name', text='', icon_value=0, emboss=True)
        split_46A5F = col_D02FD.split(factor=0.30000001192092896, align=True)
        split_46A5F.alert = False
        split_46A5F.enabled = True
        split_46A5F.active = True
        split_46A5F.use_property_split = False
        split_46A5F.use_property_decorate = False
        split_46A5F.scale_x = 1.0
        split_46A5F.scale_y = 1.0
        split_46A5F.alignment = 'Expand'.upper()
        if not True: split_46A5F.operator_context = "EXEC_DEFAULT"
        split_46A5F.prop(bpy.context.scene, 'sna_hou_delete_bool', text='删除后：', icon_value=0, emboss=True)
        split_46A5F.prop(bpy.context.scene, 'sna_hou_delete_id', text='', icon_value=0, emboss=True)
        col_D02FD.separator(factor=2.0)
        col_D02FD.prop(bpy.context.scene, 'sna_name_id', text='编号', icon_value=0, emboss=True)
        col_7FD41 = layout.column(heading='', align=True)
        col_7FD41.alert = False
        col_7FD41.enabled = True
        col_7FD41.active = True
        col_7FD41.use_property_split = False
        col_7FD41.use_property_decorate = False
        col_7FD41.scale_x = 1.0
        col_7FD41.scale_y = 1.5
        col_7FD41.alignment = 'Expand'.upper()
        col_7FD41.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_7FD41.operator('sna.ace_8da21', text='重命名', icon_value=0, emboss=True, depress=False)


class SNA_OT_Ace_8Da21(bpy.types.Operator):
    bl_idname = "sna.ace_8da21"
    bl_label = "ace"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_FDAD7 in range(len(bpy.context.view_layer.objects.selected)):
            if bpy.context.scene.sna_base_name_bool:
                bpy.context.view_layer.objects.selected[i_FDAD7].name = bpy.context.scene.sna_base_name
            if bpy.context.scene.sna_replace_in_string_bool:
                bpy.context.view_layer.objects.selected[i_FDAD7].name = bpy.context.view_layer.objects.selected[i_FDAD7].name.replace(bpy.context.scene.sna_replace_in_string_input, bpy.context.scene.sna_replace_in_string_output)
                print(bpy.context.view_layer.objects.selected[i_FDAD7].name.replace(bpy.context.scene.sna_replace_in_string_input, bpy.context.scene.sna_replace_in_string_output))
            if bpy.context.scene.sna_qian_name_bool:
                bpy.context.view_layer.objects.selected[i_FDAD7].name = bpy.context.scene.sna_qian_name + bpy.context.view_layer.objects.selected[i_FDAD7].name
            if bpy.context.scene.sna_qian_delete_bool:
                bpy.context.view_layer.objects.selected[i_FDAD7].name = bpy.context.view_layer.objects.selected[i_FDAD7].name[bpy.context.scene.sna_qian_delete_id:]
            if bpy.context.scene.sna_id_bool:
                node_tree['sna_name_id'] = '000000' + str(int(i_FDAD7 + 1.0))
                bpy.context.view_layer.objects.selected[i_FDAD7].name = bpy.context.view_layer.objects.selected[i_FDAD7].name + node_tree['sna_name_id'][int(bpy.context.scene.sna_id_weishu * -1.0):]
            if bpy.context.scene.sna_hou_name_bool:
                bpy.context.view_layer.objects.selected[i_FDAD7].name = bpy.context.view_layer.objects.selected[i_FDAD7].name + bpy.context.scene.sna_hou_name
            if bpy.context.scene.sna_hou_delete_bool:
                bpy.context.view_layer.objects.selected[i_FDAD7].name = bpy.context.view_layer.objects.selected[i_FDAD7].name[:int(bpy.context.scene.sna_hou_delete_id * -1.0)]
            if bpy.context.scene.sna_name_id:
                bpy.context.view_layer.objects.selected[i_FDAD7].name = bpy.context.view_layer.objects.selected[i_FDAD7].name + str(int(i_FDAD7 + 1.0))
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_base_name_bool = bpy.props.BoolProperty(name='base_name_bool', description='', default=False)
    bpy.types.Scene.sna_base_name = bpy.props.StringProperty(name='base_name', description='', default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_qian_name_bool = bpy.props.BoolProperty(name='qian_name_bool', description='', default=False)
    bpy.types.Scene.sna_qian_name = bpy.props.StringProperty(name='qian_name', description='', default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_qian_delete_bool = bpy.props.BoolProperty(name='qian_delete_bool', description='', default=False)
    bpy.types.Scene.sna_qian_delete_id = bpy.props.IntProperty(name='qian_delete_id', description='', default=0, subtype='NONE', min=0)
    bpy.types.Scene.sna_hou_name_bool = bpy.props.BoolProperty(name='hou_name_bool', description='', default=False)
    bpy.types.Scene.sna_hou_name = bpy.props.StringProperty(name='hou_name', description='', default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_hou_delete_bool = bpy.props.BoolProperty(name='hou_delete_bool', description='', default=False)
    bpy.types.Scene.sna_hou_delete_id = bpy.props.IntProperty(name='hou_delete_id', description='', default=0, subtype='NONE', min=0)
    bpy.types.Scene.sna_name_id = bpy.props.BoolProperty(name='name_id', description='', default=False)
    bpy.types.Scene.sna_id_bool = bpy.props.BoolProperty(name='id_bool', description='', default=False)
    bpy.types.Scene.sna_id_weishu = bpy.props.IntProperty(name='id_weishu', description='', default=0, subtype='NONE', min=1, soft_max=6)
    bpy.types.Scene.sna_replace_in_string_bool = bpy.props.BoolProperty(name='replace_in_string_bool', description='', default=False)
    bpy.types.Scene.sna_replace_in_string_input = bpy.props.StringProperty(name='replace_in_string_input', description='', default='', subtype='NONE', maxlen=0)
    bpy.types.Scene.sna_replace_in_string_output = bpy.props.StringProperty(name='replace_in_string_output', description='', default='', subtype='NONE', maxlen=0)
    bpy.utils.register_class(SNA_PT_batch_renaming_097E6)
    bpy.utils.register_class(SNA_OT_Ace_8Da21)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_replace_in_string_output
    del bpy.types.Scene.sna_replace_in_string_input
    del bpy.types.Scene.sna_replace_in_string_bool
    del bpy.types.Scene.sna_id_weishu
    del bpy.types.Scene.sna_id_bool
    del bpy.types.Scene.sna_name_id
    del bpy.types.Scene.sna_hou_delete_id
    del bpy.types.Scene.sna_hou_delete_bool
    del bpy.types.Scene.sna_hou_name
    del bpy.types.Scene.sna_hou_name_bool
    del bpy.types.Scene.sna_qian_delete_id
    del bpy.types.Scene.sna_qian_delete_bool
    del bpy.types.Scene.sna_qian_name
    del bpy.types.Scene.sna_qian_name_bool
    del bpy.types.Scene.sna_base_name
    del bpy.types.Scene.sna_base_name_bool
    bpy.utils.unregister_class(SNA_PT_batch_renaming_097E6)
    bpy.utils.unregister_class(SNA_OT_Ace_8Da21)
