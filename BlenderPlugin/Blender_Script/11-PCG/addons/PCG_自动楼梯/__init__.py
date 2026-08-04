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
    "name" : "PCG_Automatic staircase_v1",
    "author" : "渠奎奎", 
    "description" : "自动楼梯",
    "blender" : (3, 5, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "PCG_工具" 
}


import bpy
import bpy.utils.previews
import os


addon_keymaps = {}
_icons = None
node_tree_002 = {'sna_pcg_modname': '', }


def sna_new_collection_5BD4A_8C999(Collection_Name, Make_Child_of_Active_Object_Collection):
    collection_CD254 = bpy.data.collections.new(name=Collection_Name, )
    if Make_Child_of_Active_Object_Collection:
        for i_56CB2 in range(len(bpy.context.view_layer.objects.active.users_collection)):
            pass
        bpy.context.view_layer.objects.active.users_collection[i_56CB2].children.link(child=collection_CD254, )
    else:
        bpy.context.scene.collection.children.link(child=collection_CD254, )
    return collection_CD254.name


def sna_new_collection_5BD4A_9CA90(Collection_Name, Make_Child_of_Active_Object_Collection):
    collection_CD254 = bpy.data.collections.new(name=Collection_Name, )
    if Make_Child_of_Active_Object_Collection:
        for i_56CB2 in range(len(bpy.context.view_layer.objects.active.users_collection)):
            pass
        bpy.context.view_layer.objects.active.users_collection[i_56CB2].children.link(child=collection_CD254, )
    else:
        bpy.context.scene.collection.children.link(child=collection_CD254, )
    return collection_CD254.name


def sna_new_collection_5BD4A_84FF1(Collection_Name, Make_Child_of_Active_Object_Collection):
    collection_CD254 = bpy.data.collections.new(name=Collection_Name, )
    if Make_Child_of_Active_Object_Collection:
        for i_56CB2 in range(len(bpy.context.view_layer.objects.active.users_collection)):
            pass
        bpy.context.view_layer.objects.active.users_collection[i_56CB2].children.link(child=collection_CD254, )
    else:
        bpy.context.scene.collection.children.link(child=collection_CD254, )
    return collection_CD254.name


movetocollection_s3_vars_4785B = {'sna_objectstomove': [], }


def sna_fnmovetocollection_397D9_4785B(CollectionName):
    if (len(bpy.context.view_layer.objects.selected.values()) > 0):
        if property_exists("bpy.data.collections[CollectionName]", globals(), locals()):
            sna_fnlinkunlink_41AEA(CollectionName)
        else:
            collection_752A1 = bpy.data.collections.new(name=CollectionName, )
            bpy.context.scene.collection.children.link(child=collection_752A1, )
            sna_fnlinkunlink_41AEA(CollectionName)


movetocollection_s3_vars_2657D = {'sna_objectstomove': [], }


def sna_fnmovetocollection_397D9_2657D(CollectionName):
    if (len(bpy.context.view_layer.objects.selected.values()) > 0):
        if property_exists("bpy.data.collections[CollectionName]", globals(), locals()):
            sna_fnlinkunlink_41AEA(CollectionName)
        else:
            collection_752A1 = bpy.data.collections.new(name=CollectionName, )
            bpy.context.scene.collection.children.link(child=collection_752A1, )
            sna_fnlinkunlink_41AEA(CollectionName)


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_fnlinkunlink_41AEA(CollectionName):
    movetocollection_s3_vars_2657D['sna_objectstomove'] = []
    for i_5B107 in range(len(bpy.context.view_layer.objects.selected)):
        movetocollection_s3_vars_2657D['sna_objectstomove'].append(bpy.context.view_layer.objects.selected[i_5B107])
    for i_18D5A in range(len(bpy.context.view_layer.objects.selected)):
        for i_BE9A3 in range(len(bpy.context.view_layer.objects.selected[i_18D5A].users_collection)):
            if (bpy.context.view_layer.objects.selected[i_18D5A].users_collection[i_BE9A3].name == CollectionName):
                movetocollection_s3_vars_2657D['sna_objectstomove'].remove(bpy.context.view_layer.objects.selected[i_18D5A])
    for i_EC7E0 in range(len(movetocollection_s3_vars_2657D['sna_objectstomove'])):
        for i_726C8 in range(len(movetocollection_s3_vars_2657D['sna_objectstomove'][i_EC7E0].users_collection)):
            movetocollection_s3_vars_2657D['sna_objectstomove'][i_EC7E0].users_collection[i_726C8].objects.unlink(object=movetocollection_s3_vars_2657D['sna_objectstomove'][i_EC7E0], )
    for i_9A186 in range(len(movetocollection_s3_vars_2657D['sna_objectstomove'])):
        bpy.data.collections[CollectionName].objects.link(object=movetocollection_s3_vars_2657D['sna_objectstomove'][i_9A186], )


class SNA_PT_PCG__60993(bpy.types.Panel):
    bl_label = 'PCG_楼梯'
    bl_idname = 'SNA_PT_PCG__60993'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'PCG'
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
        if (bpy.context.view_layer.objects.active != None):
            col_BAD9B = layout.column(heading='', align=True)
            col_BAD9B.alert = False
            col_BAD9B.enabled = property_exists("bpy.context.view_layer.objects.active.data.polygons", globals(), locals())
            col_BAD9B.active = True
            col_BAD9B.use_property_split = False
            col_BAD9B.use_property_decorate = False
            col_BAD9B.scale_x = 1.0
            col_BAD9B.scale_y = 1.0
            col_BAD9B.alignment = 'Expand'.upper()
            col_BAD9B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.polygons", globals(), locals()):
                col_BAD9B.label(text='选中模型：' + bpy.context.view_layer.objects.active.name, icon_value=235)
            else:
                col_BAD9B.label(text='非模型：' + bpy.context.view_layer.objects.active.name, icon_value=3)
            col_BAD9B.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_GN_楼梯节点_v1.0'].node_group.name", globals(), locals()):
                col_BB8E1 = col_BAD9B.column(heading='', align=True)
                col_BB8E1.alert = False
                col_BB8E1.enabled = True
                col_BB8E1.active = True
                col_BB8E1.use_property_split = False
                col_BB8E1.use_property_decorate = False
                col_BB8E1.scale_x = 1.0
                col_BB8E1.scale_y = 1.0
                col_BB8E1.alignment = 'Expand'.upper()
                col_BB8E1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_4E278 = col_BB8E1.split(factor=0.5, align=True)
                split_4E278.alert = False
                split_4E278.enabled = True
                split_4E278.active = True
                split_4E278.use_property_split = False
                split_4E278.use_property_decorate = False
                split_4E278.scale_x = 1.0
                split_4E278.scale_y = 1.2000000476837158
                split_4E278.alignment = 'Expand'.upper()
                split_4E278.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = split_4E278.operator('sna.my_generic_operator_6dd28', text='清空', icon_value=33, emboss=True, depress=False)
                col_1226F = split_4E278.column(heading='', align=True)
                col_1226F.alert = False
                col_1226F.enabled = (len(bpy.context.view_layer.objects.selected.values()) == 1)
                col_1226F.active = True
                col_1226F.use_property_split = False
                col_1226F.use_property_decorate = False
                col_1226F.scale_x = 1.0
                col_1226F.scale_y = 1.0
                col_1226F.alignment = 'Expand'.upper()
                col_1226F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_1226F.operator('sna.my_generic_operator_6044a', text='应用', icon_value=36, emboss=True, depress=False)
                col_790E9 = col_BB8E1.column(heading='', align=True)
                col_790E9.alert = False
                col_790E9.enabled = True
                col_790E9.active = True
                col_790E9.use_property_split = False
                col_790E9.use_property_decorate = False
                col_790E9.scale_x = 1.0
                col_790E9.scale_y = 1.0
                col_790E9.alignment = 'Expand'.upper()
                col_790E9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                box_3B387 = col_790E9.box()
                box_3B387.alert = False
                box_3B387.enabled = True
                box_3B387.active = True
                box_3B387.use_property_split = False
                box_3B387.use_property_decorate = False
                box_3B387.alignment = 'Expand'.upper()
                box_3B387.scale_x = 1.0
                box_3B387.scale_y = 1.0
                box_3B387.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_76BF5 = box_3B387.column(heading='', align=True)
                col_76BF5.alert = False
                col_76BF5.enabled = True
                col_76BF5.active = True
                col_76BF5.use_property_split = False
                col_76BF5.use_property_decorate = False
                col_76BF5.scale_x = 1.0
                col_76BF5.scale_y = 1.5
                col_76BF5.alignment = 'Expand'.upper()
                col_76BF5.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_76BF5.operator('sna.my_generic_operator_1134d', text='一键配置', icon_value=4, emboss=True, depress=False)
                col_5E0EE = box_3B387.column(heading='', align=True)
                col_5E0EE.alert = False
                col_5E0EE.enabled = True
                col_5E0EE.active = True
                col_5E0EE.use_property_split = False
                col_5E0EE.use_property_decorate = False
                col_5E0EE.scale_x = 1.0
                col_5E0EE.scale_y = 1.0
                col_5E0EE.alignment = 'Expand'.upper()
                col_5E0EE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_5E0EE.prop(bpy.context.scene, 'sna_pcg_ladder01', text='阶梯', icon_value=0, emboss=True)
                col_5E0EE.prop(bpy.context.scene, 'sna_pcg_ladder02', text='包边', icon_value=0, emboss=True)
                col_5E0EE.prop(bpy.context.scene, 'sna_pcg_banister01', text='栏杆', icon_value=0, emboss=True)
                col_5E0EE.prop(bpy.context.scene, 'sna_pcg_banister02', text='扶手', icon_value=0, emboss=True)
                col_5E0EE.prop(bpy.context.scene, 'sna_pcg_bottom01', text='底部', icon_value=0, emboss=True)
                col_5E0EE.prop(bpy.context.scene, 'sna_pcg_bottom02', text='大梁', icon_value=0, emboss=True)
                box_0BDF8 = col_790E9.box()
                box_0BDF8.alert = False
                box_0BDF8.enabled = True
                box_0BDF8.active = True
                box_0BDF8.use_property_split = False
                box_0BDF8.use_property_decorate = False
                box_0BDF8.alignment = 'Expand'.upper()
                box_0BDF8.scale_x = 1.0
                box_0BDF8.scale_y = 1.0
                box_0BDF8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_B33B9 = box_0BDF8.column(heading='', align=True)
                col_B33B9.alert = False
                col_B33B9.enabled = True
                col_B33B9.active = True
                col_B33B9.use_property_split = False
                col_B33B9.use_property_decorate = False
                col_B33B9.scale_x = 1.0
                col_B33B9.scale_y = 1.2000000476837158
                col_B33B9.alignment = 'Expand'.upper()
                col_B33B9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_B33B9.label(text='阶梯设置：', icon_value=525)
                attr_D58A9 = '["' + str('Input_20' + '"]') 
                col_B33B9.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_D58A9, text='间距', icon_value=0, emboss=True)
                box_3B7AB = col_790E9.box()
                box_3B7AB.alert = False
                box_3B7AB.enabled = True
                box_3B7AB.active = True
                box_3B7AB.use_property_split = False
                box_3B7AB.use_property_decorate = False
                box_3B7AB.alignment = 'Expand'.upper()
                box_3B7AB.scale_x = 1.0
                box_3B7AB.scale_y = 1.0
                box_3B7AB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_FFA1B = box_3B7AB.column(heading='', align=True)
                col_FFA1B.alert = False
                col_FFA1B.enabled = True
                col_FFA1B.active = True
                col_FFA1B.use_property_split = False
                col_FFA1B.use_property_decorate = False
                col_FFA1B.scale_x = 1.0
                col_FFA1B.scale_y = 1.2000000476837158
                col_FFA1B.alignment = 'Expand'.upper()
                col_FFA1B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_FFA1B.label(text='栏杆设置：', icon_value=390)
                attr_DDE30 = '["' + str('Input_19' + '"]') 
                col_FFA1B.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_DDE30, text='数量', icon_value=0, emboss=True)
                attr_DF464 = '["' + str('Input_21' + '"]') 
                col_FFA1B.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_DF464, text='内缩', icon_value=0, emboss=True)
                attr_D3692 = '["' + str('Input_37' + '"]') 
                col_FFA1B.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_D3692, text='偏移', icon_value=0, emboss=True)
                split_1B40C = col_FFA1B.split(factor=0.30000001192092896, align=True)
                split_1B40C.alert = False
                split_1B40C.enabled = True
                split_1B40C.active = True
                split_1B40C.use_property_split = False
                split_1B40C.use_property_decorate = False
                split_1B40C.scale_x = 1.0
                split_1B40C.scale_y = 1.0
                split_1B40C.alignment = 'Expand'.upper()
                split_1B40C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_E3BEB = '["' + str('Input_33' + '"]') 
                split_1B40C.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_E3BEB, text='副杆开关', icon_value=0, emboss=True)
                attr_6BFCC = '["' + str('Input_35' + '"]') 
                split_1B40C.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_6BFCC, text='偏移', icon_value=0, emboss=True)
                box_4FAD4 = col_790E9.box()
                box_4FAD4.alert = False
                box_4FAD4.enabled = True
                box_4FAD4.active = True
                box_4FAD4.use_property_split = False
                box_4FAD4.use_property_decorate = False
                box_4FAD4.alignment = 'Expand'.upper()
                box_4FAD4.scale_x = 1.0
                box_4FAD4.scale_y = 1.0
                box_4FAD4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_6D4C1 = box_4FAD4.column(heading='', align=True)
                col_6D4C1.alert = False
                col_6D4C1.enabled = True
                col_6D4C1.active = True
                col_6D4C1.use_property_split = False
                col_6D4C1.use_property_decorate = False
                col_6D4C1.scale_x = 1.0
                col_6D4C1.scale_y = 1.2000000476837158
                col_6D4C1.alignment = 'Expand'.upper()
                col_6D4C1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_6D4C1.label(text='底部组件设置：', icon_value=431)
                attr_01280 = '["' + str('Input_32' + '"]') 
                col_6D4C1.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_01280, text='数量', icon_value=0, emboss=True)
                attr_DB80E = '["' + str('Input_31' + '"]') 
                col_6D4C1.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_DB80E, text='内缩', icon_value=0, emboss=True)
                box_89D17 = col_790E9.box()
                box_89D17.alert = False
                box_89D17.enabled = True
                box_89D17.active = True
                box_89D17.use_property_split = False
                box_89D17.use_property_decorate = False
                box_89D17.alignment = 'Expand'.upper()
                box_89D17.scale_x = 1.0
                box_89D17.scale_y = 1.0
                box_89D17.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_CC293 = box_89D17.column(heading='', align=True)
                col_CC293.alert = False
                col_CC293.enabled = True
                col_CC293.active = True
                col_CC293.use_property_split = False
                col_CC293.use_property_decorate = False
                col_CC293.scale_x = 1.0
                col_CC293.scale_y = 1.2000000476837158
                col_CC293.alignment = 'Expand'.upper()
                col_CC293.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_CC293.label(text='底部大梁设置：', icon_value=526)
                attr_ABD34 = '["' + str('Input_9' + '"]') 
                col_CC293.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_ABD34, text='数量', icon_value=0, emboss=True)
                attr_74C71 = '["' + str('Input_22' + '"]') 
                col_CC293.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_74C71, text='内缩', icon_value=0, emboss=True)
                attr_1270C = '["' + str('Input_12' + '"]') 
                col_CC293.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_1270C, text='粗细', icon_value=0, emboss=True)
                attr_CAD17 = '["' + str('Input_10' + '"]') 
                col_CC293.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_CAD17, text='延长', icon_value=0, emboss=True)
                attr_CD557 = '["' + str('Input_36' + '"]') 
                col_CC293.prop(bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'], attr_CD557, text='偏移', icon_value=0, emboss=True)
            else:
                col_A7E6C = col_BAD9B.column(heading='', align=True)
                col_A7E6C.alert = False
                col_A7E6C.enabled = True
                col_A7E6C.active = True
                col_A7E6C.use_property_split = False
                col_A7E6C.use_property_decorate = False
                col_A7E6C.scale_x = 1.0
                col_A7E6C.scale_y = 2.0
                col_A7E6C.alignment = 'Expand'.upper()
                col_A7E6C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_A7E6C.operator('sna.my_generic_operator_50832', text='自动楼梯', icon_value=4, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_6Dd28(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6dd28"
    bl_label = "清空楼梯修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_1134D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_1134d"
    bl_label = "一键配置楼梯修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0']['Input_24'] = bpy.context.scene.sna_pcg_ladder01
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0']['Input_29'] = bpy.context.scene.sna_pcg_ladder02
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0']['Input_25'] = bpy.context.scene.sna_pcg_banister01
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0']['Input_26'] = bpy.context.scene.sna_pcg_banister02
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0']['Input_30'] = bpy.context.scene.sna_pcg_bottom01
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0']['Input_27'] = bpy.context.scene.sna_pcg_bottom02
        bpy.ops.sna.my_generic_operator_2bc1a()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_2Bc1A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2bc1a"
    bl_label = "刷新楼梯修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'].show_viewport = False
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_50832(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_50832"
    bl_label = "加载楼梯修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_GN_楼梯节点_v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_GN_楼梯节点_v1.0'].node_group = bpy.data.node_groups['PCG_GN_楼梯节点_v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_GN_楼梯节点_v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_STAIRCASE.blend')) + r'\NodeTree', filename='PCG_GN_楼梯节点_v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_69CD7 = None if not new_data else new_data[0]
            print('')
        return self.execute(context)


class SNA_OT_My_Generic_Operator_6044A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6044a"
    bl_label = "应用楼梯修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        node_tree_002['sna_pcg_modname'] = bpy.context.view_layer.objects.active.name
        collection_name_0_8c999 = sna_new_collection_5BD4A_8C999('PCG_' + node_tree_002['sna_pcg_modname'] + '_集合', False)
        collection_name_0_9ca90 = sna_new_collection_5BD4A_9CA90('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始', False)
        collection_name_0_84ff1 = sna_new_collection_5BD4A_84FF1('PCG_' + node_tree_002['sna_pcg_modname'] + '_楼梯', False)
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_楼梯'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_楼梯'], )
        sna_fnmovetocollection_397D9_4785B('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_2657D('PCG_' + node_tree_002['sna_pcg_modname'] + '_楼梯')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_pattern(pattern=node_tree_002['sna_pcg_modname'])
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_ladder01 = bpy.props.PointerProperty(name='PCG_ladder01', description='', options={'HIDDEN'}, type=bpy.types.Object)
    bpy.types.Scene.sna_pcg_ladder02 = bpy.props.PointerProperty(name='PCG_ladder02', description='', options={'HIDDEN'}, type=bpy.types.Object)
    bpy.types.Scene.sna_pcg_banister01 = bpy.props.PointerProperty(name='PCG_banister01', description='', options={'HIDDEN'}, type=bpy.types.Object)
    bpy.types.Scene.sna_pcg_banister02 = bpy.props.PointerProperty(name='PCG_banister02', description='', options={'HIDDEN'}, type=bpy.types.Object)
    bpy.types.Scene.sna_pcg_bottom01 = bpy.props.PointerProperty(name='PCG_bottom01', description='', options={'HIDDEN'}, type=bpy.types.Object)
    bpy.types.Scene.sna_pcg_bottom02 = bpy.props.PointerProperty(name='PCG_bottom02', description='', options={'HIDDEN'}, type=bpy.types.Object)
    bpy.utils.register_class(SNA_PT_PCG__60993)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6Dd28)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1134D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2Bc1A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_50832)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6044A)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_bottom02
    del bpy.types.Scene.sna_pcg_bottom01
    del bpy.types.Scene.sna_pcg_banister02
    del bpy.types.Scene.sna_pcg_banister01
    del bpy.types.Scene.sna_pcg_ladder02
    del bpy.types.Scene.sna_pcg_ladder01
    bpy.utils.unregister_class(SNA_PT_PCG__60993)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6Dd28)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1134D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2Bc1A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_50832)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6044A)
