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
    "name" : "Parameter Set",
    "author" : "qkk", 
    "description" : "材质变体",
    "blender" : (5, 0, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews




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


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_add_to_sna_pt_material_tools_dfc75_B8F6A(self, context):
    if not (False):
        layout = self.layout
        if ((bpy.context.view_layer.objects.active != None) and (bpy.context.object.active_material != None)):
            box_53A74 = layout.box()
            box_53A74.alert = False
            box_53A74.enabled = True
            box_53A74.active = True
            box_53A74.use_property_split = False
            box_53A74.use_property_decorate = False
            box_53A74.alignment = 'Expand'.upper()
            box_53A74.scale_x = 1.0
            box_53A74.scale_y = 1.0
            if not True: box_53A74.operator_context = "EXEC_DEFAULT"
            col_2181A = box_53A74.column(heading='', align=False)
            col_2181A.alert = False
            col_2181A.enabled = True
            col_2181A.active = True
            col_2181A.use_property_split = False
            col_2181A.use_property_decorate = False
            col_2181A.scale_x = 1.0
            col_2181A.scale_y = 1.0
            col_2181A.alignment = 'Expand'.upper()
            col_2181A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            layout_function = col_2181A
            sna_function_interface_6EFB8(layout_function, bpy.context.view_layer.objects.active.active_material.name, string_to_icon('SHADING_RENDERED'), False)
            for i_B0EB9 in range(len(bpy.data.materials)):
                if ((bpy.data.materials[i_B0EB9].name.split('_')[int(len(bpy.data.materials[i_B0EB9].name.split('_')) - 1.0)] == 'mat') and (bpy.data.materials[i_B0EB9].name.replace('_' + bpy.data.materials[i_B0EB9].name.split('_')[int(len(bpy.data.materials[i_B0EB9].name.split('_')) - 2.0)], '') == bpy.context.view_layer.objects.active.active_material.name) and (len(bpy.data.materials[i_B0EB9].name.split('_')) == int(len(bpy.context.view_layer.objects.active.active_material.name.split('_')) + 1.0))):
                    layout_function = col_2181A
                    sna_function_interface_6EFB8(layout_function, bpy.data.materials[i_B0EB9].name, string_to_icon('HOLDOUT_OFF'), True)


class SNA_OT_Mat_Set_E1900(bpy.types.Operator):
    bl_idname = "sna.mat_set_e1900"
    bl_label = "mat_set"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_mat_name: bpy.props.StringProperty(name='mat_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)
    sna_set_modifier: bpy.props.BoolProperty(name='set_modifier', description='', options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        set_modifier = self.sna_set_modifier
        mat_name = self.sna_mat_name
        asset_path ='C:\Blender_Shader\Parameter Set\Parameter Set.blend'
        obj_list = []
        # 遍历当前场景中的所有对象
        for obj in bpy.data.objects:
            active_obj_name = bpy.context.active_object.name
            # 检查对象名称
            if active_obj_name[:-5] == obj.name[:-5]:
                obj_list.append(obj)
        node_name = 'Parameter Set'
        for obj in obj_list:
            modifier = obj.modifiers.get(node_name)
            if modifier:
                obj.modifiers.remove(modifier)
            if set_modifier:
                if node_name in bpy.data.node_groups: # 判断是否存在
                    pass
                else:
                    bpy.ops.wm.append(directory = bpy.path.abspath(asset_path) + '/NodeTree', filename = node_name, link=True) #关联节点
                obj.modifiers.new(name=node_name, type='NODES', ).node_group = bpy.data.node_groups[node_name] # 使用节点
                obj.modifiers[node_name]['Socket_2'] = bpy.data.materials.get(mat_name)
                obj.modifiers["Parameter Set"].show_viewport = True
        print('材质变体修改器 完成')
        self.report({'INFO'}, message='ok！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_function_interface_6EFB8(layout_function, mat_name, input, input_001):
    row_4783C = layout_function.row(heading='', align=False)
    row_4783C.alert = False
    row_4783C.enabled = True
    row_4783C.active = True
    row_4783C.use_property_split = False
    row_4783C.use_property_decorate = False
    row_4783C.scale_x = 1.0
    row_4783C.scale_y = 1.0
    row_4783C.alignment = 'Expand'.upper()
    row_4783C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = row_4783C.operator('sna.mat_set_e1900', text='', icon_value=(string_to_icon('RADIOBUT_ON') if (mat_name == (bpy.context.view_layer.objects.active.modifiers['Parameter Set']['Socket_2'].name if property_exists("bpy.context.view_layer.objects.active.modifiers['Parameter Set']['Socket_2']", globals(), locals()) else bpy.context.view_layer.objects.active.active_material.name)) else string_to_icon('RADIOBUT_OFF')), emboss=True, depress=(mat_name == (bpy.context.view_layer.objects.active.modifiers['Parameter Set']['Socket_2'].name if property_exists("bpy.context.view_layer.objects.active.modifiers['Parameter Set']['Socket_2']", globals(), locals()) else bpy.context.view_layer.objects.active.active_material.name)))
    op.sna_mat_name = mat_name
    op.sna_set_modifier = input_001
    col_0D611 = row_4783C.column(heading='', align=True)
    col_0D611.alert = False
    col_0D611.enabled = True
    col_0D611.active = (mat_name == (bpy.context.view_layer.objects.active.modifiers['Parameter Set']['Socket_2'].name if property_exists("bpy.context.view_layer.objects.active.modifiers['Parameter Set']['Socket_2']", globals(), locals()) else bpy.context.view_layer.objects.active.active_material.name))
    col_0D611.use_property_split = False
    col_0D611.use_property_decorate = False
    col_0D611.scale_x = 1.0
    col_0D611.scale_y = 1.0
    col_0D611.alignment = 'Expand'.upper()
    col_0D611.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    col_0D611.label(text=mat_name, icon_value=input)
    row_B3201 = row_4783C.row(heading='', align=False)
    row_B3201.alert = False
    row_B3201.enabled = True
    row_B3201.active = True
    row_B3201.use_property_split = False
    row_B3201.use_property_decorate = False
    row_B3201.scale_x = 1.0
    row_B3201.scale_y = 1.0
    row_B3201.alignment = 'Right'.upper()
    row_B3201.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_B3201.label(text=str(bpy.data.materials[mat_name].users), icon_value=0)
    row_B3201.prop(bpy.data.materials[mat_name], 'use_fake_user', text='', icon_value=0, emboss=True)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.SNA_PT_material_tools_DFC75.append(sna_add_to_sna_pt_material_tools_dfc75_B8F6A)
    bpy.utils.register_class(SNA_OT_Mat_Set_E1900)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.types.SNA_PT_material_tools_DFC75.remove(sna_add_to_sna_pt_material_tools_dfc75_B8F6A)
    bpy.utils.unregister_class(SNA_OT_Mat_Set_E1900)
