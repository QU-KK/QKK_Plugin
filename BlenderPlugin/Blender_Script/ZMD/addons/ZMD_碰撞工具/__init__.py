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
    "name" : "ZMD碰撞工具",
    "author" : "渠奎奎", 
    "description" : "ZMD碰撞工具",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "Overpass" 
}


import bpy
import bpy.utils.previews

def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


addon_keymaps = {}
_icons = None
node_tree = {'sna_sna_new_variable': [], }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_PT_collision_configuration_35989(bpy.types.Panel):
    bl_label = '碰撞配置'
    bl_idname = 'SNA_PT_collision_configuration_35989'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'ZMD'
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x=11

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        col_379CC = layout.column(heading='', align=True)
        col_379CC.alert = False
        col_379CC.enabled = True
        col_379CC.active = True
        col_379CC.use_property_split = False
        col_379CC.use_property_decorate = False
        col_379CC.scale_x = 1.0
        col_379CC.scale_y = 1.5
        col_379CC.alignment = 'Expand'.upper()
        col_379CC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_379CC.operator('sna.my_generic_operator_eadf8', text='刷新碰撞', icon_value=string_to_icon('PHYSICS'), emboss=True, depress=False)
        col_D05F8 = layout.column(heading='', align=True)
        col_D05F8.alert = False
        col_D05F8.enabled = True
        col_D05F8.active = True
        col_D05F8.use_property_split = False
        col_D05F8.use_property_decorate = False
        col_D05F8.scale_x = 1.0
        col_D05F8.scale_y = 1.0
        col_D05F8.alignment = 'Expand'.upper()
        col_D05F8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        if property_exists("bpy.context.view_layer.objects.active.name", globals(), locals()):
            split_5052B = col_D05F8.split(factor=0.6499999761581421, align=True)
            split_5052B.alert = False
            split_5052B.enabled = True
            split_5052B.active = True
            split_5052B.use_property_split = False
            split_5052B.use_property_decorate = False
            split_5052B.scale_x = 1.0
            split_5052B.scale_y = 1.0
            split_5052B.alignment = 'Expand'.upper()
            if not True: split_5052B.operator_context = "EXEC_DEFAULT"
            split_5052B.label(text=bpy.context.view_layer.objects.active.name, icon_value=string_to_icon('OUTLINER_OB_MESH'))
            split_5052B.label(text='选中数：' + str(len(bpy.context.view_layer.objects.selected)), icon_value=0)
        bool1 = False
        bool2 = True
        if bool1 != True:
            # Get the active object
            obj = bpy.context.active_object
            # Check if the active object is a mesh, curve, surface, meta, font, or volume object
            if obj and obj.type in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME'):
                col_D05F8
                row = layout.row()
                # Create a list of materials
                materials = obj.material_slots
                # Create a UIList to display the materials
                row.template_list("MATERIAL_UL_matslots", "", obj, "material_slots", obj, "active_material_index")
                col = row.column(align=True)
                col.operator("object.material_slot_add", icon='ADD', text="")
                col.operator("object.material_slot_remove", icon='REMOVE', text="")
                col.separator()
                col.menu("MATERIAL_MT_context_menu", icon='DOWNARROW_HLT', text="")
                if len(materials) > 1:
                    col.separator()
                    col.operator("object.material_slot_move", icon='TRIA_UP', text="").direction = 'UP'
                    col.operator("object.material_slot_move", icon='TRIA_DOWN', text="").direction = 'DOWN'
                if obj.mode == 'EDIT':
                    row = layout.row(align=True)
                    row.operator("object.material_slot_assign", text="Assign")
                    row.operator("object.material_slot_select", text="Select")
                    row.operator("object.material_slot_deselect", text="Deselect")
                row = layout.row()
                if obj:
                    row.template_ID(obj, "active_material", new="material.new")
                    slot = getattr(bpy.context, 'material_slot', None)
                    if slot:
                        icon_link = 'MESH_DATA' if slot.link == 'DATA' else 'OBJECT_DATA'
                        row.prop(slot, "link", text="", icon=icon_link, icon_only=True)
                elif mat:
                    layout.template_ID(bpy.context.space_data, "pin_id")
                    layout.separator()
        else:
            pass
        if bool2 != True:

            def find_node_input(node, input_name):
                for input in node.inputs:
                    if input.name == input_name:
                        return input
                return None

            def panel_node_draw(layout, id_data, output_type, input_name):
                if not id_data.use_nodes:
                    layout.operator("cycles.use_shading_nodes", icon='NODETREE')
                    return False
                ntree = id_data.node_tree
                node = ntree.get_output_node(output_type)
                if node:
                    input = find_node_input(node, input_name)
                    if input:
                        layout.template_node_view(ntree, node, input)
                    else:
                        layout.label(text="Incompatible output node")
                else:
                    layout.label(text="No output node")
                return True
            # Get the active object
            obj = bpy.context.active_object
            # Check if the active object is a mesh, curve, surface, meta, font, or volume object
            if obj and obj.type in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME'):
                mat = obj.active_material
                if mat and mat.use_nodes:
                    col_D05F8
                    output_type = 'CYCLES'
                    input_name = 'Surface'
                    panel_node_draw(layout, mat, output_type, input_name)
        else:
            pass
        split_B43CD = layout.split(factor=0.5, align=True)
        split_B43CD.alert = False
        split_B43CD.enabled = True
        split_B43CD.active = True
        split_B43CD.use_property_split = False
        split_B43CD.use_property_decorate = False
        split_B43CD.scale_x = 1.0
        split_B43CD.scale_y = 1.5
        split_B43CD.alignment = 'Expand'.upper()
        if not True: split_B43CD.operator_context = "EXEC_DEFAULT"
        op = split_B43CD.operator('sna.my_generic_operator_58b2a', text='_COL1_UM01', icon_value=0, emboss=True, depress=False)
        op.sna_name = '_COL1_UM01'
        op = split_B43CD.operator('sna.my_generic_operator_58b2a', text='_COL3_UM01', icon_value=0, emboss=True, depress=False)
        op.sna_name = '_COL3_UM01'
        if (len(node_tree['sna_sna_new_variable']) != 0):
            box_A5922 = layout.box()
            box_A5922.alert = False
            box_A5922.enabled = True
            box_A5922.active = True
            box_A5922.use_property_split = False
            box_A5922.use_property_decorate = False
            box_A5922.alignment = 'Expand'.upper()
            box_A5922.scale_x = 1.0
            box_A5922.scale_y = 1.0
            if not True: box_A5922.operator_context = "EXEC_DEFAULT"
            col_FF3FC = box_A5922.column(heading='', align=True)
            col_FF3FC.alert = False
            col_FF3FC.enabled = True
            col_FF3FC.active = True
            col_FF3FC.use_property_split = False
            col_FF3FC.use_property_decorate = False
            col_FF3FC.scale_x = 1.0
            col_FF3FC.scale_y = 1.0
            col_FF3FC.alignment = 'Expand'.upper()
            col_FF3FC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            for i_DEB45 in range(len(node_tree['sna_sna_new_variable'])):
                split_F5A88 = col_FF3FC.split(factor=0.30000001192092896, align=True)
                split_F5A88.alert = False
                split_F5A88.enabled = True
                split_F5A88.active = True
                split_F5A88.use_property_split = False
                split_F5A88.use_property_decorate = False
                split_F5A88.scale_x = 1.0
                split_F5A88.scale_y = 1.0
                split_F5A88.alignment = 'Expand'.upper()
                if not True: split_F5A88.operator_context = "EXEC_DEFAULT"
                split_AAA31 = split_F5A88.split(factor=0.20000000298023224, align=True)
                split_AAA31.alert = False
                split_AAA31.enabled = True
                split_AAA31.active = True
                split_AAA31.use_property_split = False
                split_AAA31.use_property_decorate = False
                split_AAA31.scale_x = 1.0
                split_AAA31.scale_y = 1.0
                split_AAA31.alignment = 'Expand'.upper()
                if not True: split_AAA31.operator_context = "EXEC_DEFAULT"
                if (not property_exists("bpy.data.materials[node_tree['sna_sna_new_variable'][i_DEB45][1]]", globals(), locals())):
                    col_13636 = split_AAA31.column(heading='', align=True)
                    col_13636.alert = False
                    col_13636.enabled = True
                    col_13636.active = True
                    col_13636.use_property_split = False
                    col_13636.use_property_decorate = False
                    col_13636.scale_x = 1.0
                    col_13636.scale_y = 1.0
                    col_13636.alignment = 'Expand'.upper()
                    col_13636.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    op = col_13636.operator('sna.my_generic_operator_efe21', text='', icon_value=string_to_icon('RECORD_OFF'), emboss=True, depress=False)
                    op.sna_new_property = node_tree['sna_sna_new_variable'][i_DEB45][1]
                else:
                    point_color = node_tree['sna_sna_new_variable'][i_DEB45][2]
                    split_AAA31.template_node_socket(color=point_color)
                col_EBBC1 = split_AAA31.column(heading='', align=True)
                col_EBBC1.alert = False
                col_EBBC1.enabled = property_exists("bpy.data.materials[node_tree['sna_sna_new_variable'][i_DEB45][1]]", globals(), locals())
                col_EBBC1.active = True
                col_EBBC1.use_property_split = False
                col_EBBC1.use_property_decorate = False
                col_EBBC1.scale_x = 1.0
                col_EBBC1.scale_y = 1.0
                col_EBBC1.alignment = 'Expand'.upper()
                col_EBBC1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_EBBC1.operator('sna.my_generic_operator_6902c', text=node_tree['sna_sna_new_variable'][i_DEB45][0], icon_value=0, emboss=True, depress=False)
                op.sna_new_property = node_tree['sna_sna_new_variable'][i_DEB45][1]
                col_96ECD = split_F5A88.column(heading='', align=True)
                col_96ECD.alert = False
                col_96ECD.enabled = property_exists("bpy.data.materials[node_tree['sna_sna_new_variable'][i_DEB45][1]]", globals(), locals())
                col_96ECD.active = True
                col_96ECD.use_property_split = False
                col_96ECD.use_property_decorate = False
                col_96ECD.scale_x = 1.0
                col_96ECD.scale_y = 1.0
                col_96ECD.alignment = 'Expand'.upper()
                col_96ECD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_96ECD.label(text=node_tree['sna_sna_new_variable'][i_DEB45][1], icon_value=0)


class SNA_OT_My_Generic_Operator_Eadf8(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_eadf8"
    bl_label = "刷新碰撞"
    bl_description = "刷新碰撞"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        data_phymat_list_0_4f065 = sna_get_phymat_list_9D092()
        node_tree['sna_sna_new_variable'] = data_phymat_list_0_4f065
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Efe21(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_efe21"
    bl_label = "创建碰撞材质"
    bl_description = "创建碰撞材质"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='碰撞材质名称', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        material_E43CD = bpy.context.blend_data.materials.new(name=self.sna_new_property, )
        data_phymat_list_0_e7a7f = sna_get_phymat_list_9D092()
        self.report({'INFO'}, message=self.sna_new_property + '    创建成功！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_6902C(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6902c"
    bl_label = "使用碰撞材质"
    bl_description = "使用碰撞材质"
    bl_options = {"REGISTER", "UNDO"}
    sna_new_property: bpy.props.StringProperty(name='碰撞材质名称', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_DC528 in range(len(bpy.context.view_layer.objects.selected)):
            bpy.context.view_layer.objects.selected[i_DC528].material_slots[bpy.context.view_layer.objects.selected[i_DC528].active_material_index].material = bpy.data.materials[self.sna_new_property]
        data_phymat_list_0_a5534 = sna_get_phymat_list_9D092()
        self.report({'INFO'}, message='碰撞材质设置成功！    ' + self.sna_new_property)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_get_phymat_list_9D092():
    phymat_list = None
    phymat_list = [
    ['金属','PM_Metal', [0.23, 0.23, 0.23, 1.0]], 
    ['混凝土','PM_Concrete', [0.0, 0.49, 0.06, 1.0]], 
    ['木头','PM_Wood', [0.1, 0.1, 0.1, 1.0]], 
    ['泥土','PM_Dirt', [0.26, 0.23, 0.09, 1.0]], 
    ['石头','PM_Stone', [0.24, 0.12, 0.04, 1.0]], 
    ['橡胶','PM_Rubber', [0.7, 0.46, 0.08, 1.0]], 
    ['玻璃','PM_', [0.24, 0.34, 0.53, 1.0]],
    ['雪地','PM_Snow', [0.11, 0.01, 0.23, 1.0]], 
    ['水晶','PM_Crystal', [0.8, 0.22, 0.45, 1.0]], 
    ['冰    ','PM_Ice', [0.02, 0.05, 0.6, 1.0]],
    ['水    ','PM_Wet', [0.03, 0.3, 0.6, 1.0]], 
    ]
    #子弹碰撞颜色设置
    for name, material_name, color in phymat_list:
        material = bpy.data.materials.get(material_name)
        if material:
            material.diffuse_color = color
            print(f"材质 '{material_name}' 颜色设置成功")
        else:
            print(f"材质 '{material_name}' 不存在")
    return phymat_list


class SNA_OT_My_Generic_Operator_58B2A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_58b2a"
    bl_label = "碰撞后缀"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    sna_name: bpy.props.StringProperty(name='name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_CAF60 in range(len(bpy.context.view_layer.objects.selected)):
            bpy.context.view_layer.objects.selected[i_CAF60].name = str(bpy.context.view_layer.objects.selected[i_CAF60].name).replace('_COL1_UM01', '').replace('_COL3_UM01', '') + self.sna_name
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_PT_collision_configuration_35989)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Eadf8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Efe21)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6902C)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_58B2A)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_PT_collision_configuration_35989)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Eadf8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Efe21)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6902C)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_58B2A)
