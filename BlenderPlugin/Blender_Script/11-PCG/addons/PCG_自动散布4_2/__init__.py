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
    "name" : "PCG_Scatter_4.2_v1",
    "author" : "渠奎奎", 
    "description" : "自动散布",
    "blender" : (4, 2, 0),
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


class SNA_PT_PCG__AB37C(bpy.types.Panel):
    bl_label = 'PCG_散布'
    bl_idname = 'SNA_PT_PCG__AB37C'
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
            col_EA2A0 = layout.column(heading='', align=True)
            col_EA2A0.alert = False
            col_EA2A0.enabled = property_exists("bpy.context.view_layer.objects.active.data.polygons", globals(), locals())
            col_EA2A0.active = True
            col_EA2A0.use_property_split = False
            col_EA2A0.use_property_decorate = False
            col_EA2A0.scale_x = 1.0
            col_EA2A0.scale_y = 1.0
            col_EA2A0.alignment = 'Expand'.upper()
            col_EA2A0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.polygons", globals(), locals()):
                col_EA2A0.label(text='选中模型：' + bpy.context.view_layer.objects.active.name, icon_value=235)
            else:
                col_EA2A0.label(text='非模型：' + bpy.context.view_layer.objects.active.name, icon_value=3)
            col_EA2A0.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_摆放节点_v1.0'].node_group.name", globals(), locals()):
                col_F8737 = col_EA2A0.column(heading='', align=False)
                col_F8737.alert = False
                col_F8737.enabled = True
                col_F8737.active = True
                col_F8737.use_property_split = False
                col_F8737.use_property_decorate = False
                col_F8737.scale_x = 1.0
                col_F8737.scale_y = 1.0
                col_F8737.alignment = 'Expand'.upper()
                col_F8737.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_5CF8E = col_F8737.split(factor=0.5, align=True)
                split_5CF8E.alert = False
                split_5CF8E.enabled = True
                split_5CF8E.active = True
                split_5CF8E.use_property_split = False
                split_5CF8E.use_property_decorate = False
                split_5CF8E.scale_x = 1.0
                split_5CF8E.scale_y = 1.2000000476837158
                split_5CF8E.alignment = 'Expand'.upper()
                if not True: split_5CF8E.operator_context = "EXEC_DEFAULT"
                op = split_5CF8E.operator('sna.my_generic_operator_fd0b9', text='清空', icon_value=33, emboss=True, depress=False)
                col_9CDC6 = split_5CF8E.column(heading='', align=True)
                col_9CDC6.alert = False
                col_9CDC6.enabled = (len(list(bpy.context.view_layer.objects.selected)) == 1)
                col_9CDC6.active = True
                col_9CDC6.use_property_split = False
                col_9CDC6.use_property_decorate = False
                col_9CDC6.scale_x = 1.0
                col_9CDC6.scale_y = 1.0
                col_9CDC6.alignment = 'Expand'.upper()
                col_9CDC6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_9CDC6.operator('sna.my_generic_operator_9762a', text='应用', icon_value=36, emboss=True, depress=False)
                box_B9819 = col_F8737.box()
                box_B9819.alert = False
                box_B9819.enabled = True
                box_B9819.active = True
                box_B9819.use_property_split = False
                box_B9819.use_property_decorate = False
                box_B9819.alignment = 'Expand'.upper()
                box_B9819.scale_x = 1.0
                box_B9819.scale_y = 1.0
                if not True: box_B9819.operator_context = "EXEC_DEFAULT"
                col_C835F = box_B9819.column(heading='', align=False)
                col_C835F.alert = False
                col_C835F.enabled = True
                col_C835F.active = True
                col_C835F.use_property_split = False
                col_C835F.use_property_decorate = False
                col_C835F.scale_x = 1.0
                col_C835F.scale_y = 1.0
                col_C835F.alignment = 'Expand'.upper()
                col_C835F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_2877E = col_C835F.column(heading='', align=False)
                col_2877E.alert = False
                col_2877E.enabled = True
                col_2877E.active = True
                col_2877E.use_property_split = False
                col_2877E.use_property_decorate = False
                col_2877E.scale_x = 1.0
                col_2877E.scale_y = 1.5
                col_2877E.alignment = 'Expand'.upper()
                col_2877E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_2877E.operator('sna.my_generic_operator_e070d', text='一键配置', icon_value=4, emboss=True, depress=False)
                col_C835F.prop(bpy.context.scene, 'sna_pcg_scatter_instances', text='实例集合', icon_value=0, emboss=True)
                col_C835F.prop(bpy.context.scene, 'sna_pcg_scatter_collision', text='碰撞集合', icon_value=0, emboss=True)
                col_C835F.prop(bpy.context.scene, 'sna_pcg_scatter_boolean', text='布尔剔除', icon_value=0, emboss=True)
                row_2A5A3 = col_C835F.row(heading='', align=False)
                row_2A5A3.alert = False
                row_2A5A3.enabled = True
                row_2A5A3.active = True
                row_2A5A3.use_property_split = False
                row_2A5A3.use_property_decorate = False
                row_2A5A3.scale_x = 1.0
                row_2A5A3.scale_y = 1.0
                row_2A5A3.alignment = 'Expand'.upper()
                row_2A5A3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_E4B07 = '["' + str('Input_17' + '"]') 
                row_2A5A3.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_E4B07, text='碰撞开关', icon_value=0, emboss=True)
                attr_1AD02 = '["' + str('Input_21' + '"]') 
                row_2A5A3.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_1AD02, text='方向匹配', icon_value=0, emboss=True)
                attr_B5DBF = '["' + str('Input_23' + '"]') 
                row_2A5A3.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_B5DBF, text='布尔剔除', icon_value=0, emboss=True)
                box_CB88E = col_F8737.box()
                box_CB88E.alert = False
                box_CB88E.enabled = True
                box_CB88E.active = True
                box_CB88E.use_property_split = False
                box_CB88E.use_property_decorate = False
                box_CB88E.alignment = 'Expand'.upper()
                box_CB88E.scale_x = 1.0
                box_CB88E.scale_y = 1.0
                if not True: box_CB88E.operator_context = "EXEC_DEFAULT"
                col_1A067 = box_CB88E.column(heading='', align=True)
                col_1A067.alert = False
                col_1A067.enabled = True
                col_1A067.active = True
                col_1A067.use_property_split = False
                col_1A067.use_property_decorate = False
                col_1A067.scale_x = 1.0
                col_1A067.scale_y = 1.2000000476837158
                col_1A067.alignment = 'Expand'.upper()
                col_1A067.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_1A067.label(text='分布：', icon_value=385)
                attr_8BEBA = '["' + str('Input_4' + '"]') 
                col_1A067.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_8BEBA, text='间距最小值', icon_value=0, emboss=True)
                attr_768C1 = '["' + str('Input_5' + '"]') 
                col_1A067.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_768C1, text='密度最大值', icon_value=0, emboss=True)
                attr_48527 = '["' + str('Input_6' + '"]') 
                col_1A067.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_48527, text='分布随机种子', icon_value=0, emboss=True)
                box_CC81B = col_F8737.box()
                box_CC81B.alert = False
                box_CC81B.enabled = True
                box_CC81B.active = True
                box_CC81B.use_property_split = False
                box_CC81B.use_property_decorate = False
                box_CC81B.alignment = 'Expand'.upper()
                box_CC81B.scale_x = 1.0
                box_CC81B.scale_y = 1.0
                if not True: box_CC81B.operator_context = "EXEC_DEFAULT"
                col_6BD79 = box_CC81B.column(heading='', align=False)
                col_6BD79.alert = False
                col_6BD79.enabled = True
                col_6BD79.active = True
                col_6BD79.use_property_split = False
                col_6BD79.use_property_decorate = False
                col_6BD79.scale_x = 1.0
                col_6BD79.scale_y = 1.0
                col_6BD79.alignment = 'Expand'.upper()
                col_6BD79.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_6BD79.label(text='偏移：', icon_value=593)
                row_3EE46 = col_6BD79.row(heading='', align=True)
                row_3EE46.alert = False
                row_3EE46.enabled = True
                row_3EE46.active = True
                row_3EE46.use_property_split = False
                row_3EE46.use_property_decorate = False
                row_3EE46.scale_x = 1.0
                row_3EE46.scale_y = 1.0
                row_3EE46.alignment = 'Expand'.upper()
                row_3EE46.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_7489B = '["' + str('Input_14' + '"]') 
                row_3EE46.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_7489B, text='最小值', icon_value=0, emboss=True)
                row_D49D6 = col_6BD79.row(heading='', align=True)
                row_D49D6.alert = False
                row_D49D6.enabled = True
                row_D49D6.active = True
                row_D49D6.use_property_split = False
                row_D49D6.use_property_decorate = False
                row_D49D6.scale_x = 1.0
                row_D49D6.scale_y = 1.0
                row_D49D6.alignment = 'Expand'.upper()
                row_D49D6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_4FDD6 = '["' + str('Input_15' + '"]') 
                row_D49D6.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_4FDD6, text='最大值', icon_value=0, emboss=True)
                attr_E5BC0 = '["' + str('Input_16' + '"]') 
                col_6BD79.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_E5BC0, text='随机种子', icon_value=0, emboss=True)
                box_F3BA1 = col_F8737.box()
                box_F3BA1.alert = False
                box_F3BA1.enabled = True
                box_F3BA1.active = True
                box_F3BA1.use_property_split = False
                box_F3BA1.use_property_decorate = False
                box_F3BA1.alignment = 'Expand'.upper()
                box_F3BA1.scale_x = 1.0
                box_F3BA1.scale_y = 1.0
                if not True: box_F3BA1.operator_context = "EXEC_DEFAULT"
                col_86B12 = box_F3BA1.column(heading='', align=False)
                col_86B12.alert = False
                col_86B12.enabled = True
                col_86B12.active = True
                col_86B12.use_property_split = False
                col_86B12.use_property_decorate = False
                col_86B12.scale_x = 1.0
                col_86B12.scale_y = 1.0
                col_86B12.alignment = 'Expand'.upper()
                col_86B12.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_86B12.label(text='旋转：', icon_value=594)
                row_DA095 = col_86B12.row(heading='', align=True)
                row_DA095.alert = False
                row_DA095.enabled = True
                row_DA095.active = True
                row_DA095.use_property_split = False
                row_DA095.use_property_decorate = False
                row_DA095.scale_x = 1.0
                row_DA095.scale_y = 1.0
                row_DA095.alignment = 'Expand'.upper()
                row_DA095.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_F3B5A = '["' + str('Input_11' + '"]') 
                row_DA095.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_F3B5A, text='最小值', icon_value=0, emboss=True)
                row_FB1C2 = col_86B12.row(heading='', align=True)
                row_FB1C2.alert = False
                row_FB1C2.enabled = True
                row_FB1C2.active = True
                row_FB1C2.use_property_split = False
                row_FB1C2.use_property_decorate = False
                row_FB1C2.scale_x = 1.0
                row_FB1C2.scale_y = 1.0
                row_FB1C2.alignment = 'Expand'.upper()
                row_FB1C2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_A5453 = '["' + str('Input_12' + '"]') 
                row_FB1C2.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_A5453, text='最大值', icon_value=0, emboss=True)
                attr_E6C42 = '["' + str('Input_13' + '"]') 
                col_86B12.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_E6C42, text='随机种子', icon_value=0, emboss=True)
                box_28B25 = col_F8737.box()
                box_28B25.alert = False
                box_28B25.enabled = True
                box_28B25.active = True
                box_28B25.use_property_split = False
                box_28B25.use_property_decorate = False
                box_28B25.alignment = 'Expand'.upper()
                box_28B25.scale_x = 1.0
                box_28B25.scale_y = 1.0
                if not True: box_28B25.operator_context = "EXEC_DEFAULT"
                col_84A9A = box_28B25.column(heading='', align=False)
                col_84A9A.alert = False
                col_84A9A.enabled = True
                col_84A9A.active = True
                col_84A9A.use_property_split = False
                col_84A9A.use_property_decorate = False
                col_84A9A.scale_x = 1.0
                col_84A9A.scale_y = 1.0
                col_84A9A.alignment = 'Expand'.upper()
                col_84A9A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_03C66 = col_84A9A.column(heading='', align=False)
                col_03C66.alert = False
                col_03C66.enabled = True
                col_03C66.active = True
                col_03C66.use_property_split = False
                col_03C66.use_property_decorate = False
                col_03C66.scale_x = 1.0
                col_03C66.scale_y = 1.0
                col_03C66.alignment = 'Expand'.upper()
                col_03C66.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_03C66.label(text='统一缩放：', icon_value=595)
                row_4136B = col_03C66.row(heading='', align=True)
                row_4136B.alert = False
                row_4136B.enabled = True
                row_4136B.active = True
                row_4136B.use_property_split = False
                row_4136B.use_property_decorate = False
                row_4136B.scale_x = 1.0
                row_4136B.scale_y = 1.0
                row_4136B.alignment = 'Expand'.upper()
                row_4136B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_54505 = '["' + str('Input_18' + '"]') 
                row_4136B.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_54505, text='最小值', icon_value=0, emboss=True)
                row_68033 = col_03C66.row(heading='', align=True)
                row_68033.alert = False
                row_68033.enabled = True
                row_68033.active = True
                row_68033.use_property_split = False
                row_68033.use_property_decorate = False
                row_68033.scale_x = 1.0
                row_68033.scale_y = 1.0
                row_68033.alignment = 'Expand'.upper()
                row_68033.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_A8F82 = '["' + str('Input_19' + '"]') 
                row_68033.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_A8F82, text='最大值', icon_value=0, emboss=True)
                attr_D1796 = '["' + str('Input_20' + '"]') 
                col_03C66.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_D1796, text='随机种子', icon_value=0, emboss=True)
                col_84A9A.prop(bpy.context.scene, 'sna_pcg_scatter_scale', text='拆分缩放：', icon_value=0, emboss=True)
                if bpy.context.scene.sna_pcg_scatter_scale:
                    col_32717 = col_84A9A.column(heading='', align=False)
                    col_32717.alert = False
                    col_32717.enabled = True
                    col_32717.active = True
                    col_32717.use_property_split = False
                    col_32717.use_property_decorate = False
                    col_32717.scale_x = 1.0
                    col_32717.scale_y = 1.0
                    col_32717.alignment = 'Expand'.upper()
                    col_32717.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    row_F191B = col_32717.row(heading='', align=True)
                    row_F191B.alert = False
                    row_F191B.enabled = True
                    row_F191B.active = True
                    row_F191B.use_property_split = False
                    row_F191B.use_property_decorate = False
                    row_F191B.scale_x = 1.0
                    row_F191B.scale_y = 1.0
                    row_F191B.alignment = 'Expand'.upper()
                    row_F191B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    attr_FA6E7 = '["' + str('Input_7' + '"]') 
                    row_F191B.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_FA6E7, text='最小值', icon_value=0, emboss=True)
                    row_8AF5F = col_32717.row(heading='', align=True)
                    row_8AF5F.alert = False
                    row_8AF5F.enabled = True
                    row_8AF5F.active = True
                    row_8AF5F.use_property_split = False
                    row_8AF5F.use_property_decorate = False
                    row_8AF5F.scale_x = 1.0
                    row_8AF5F.scale_y = 1.0
                    row_8AF5F.alignment = 'Expand'.upper()
                    row_8AF5F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    attr_C0444 = '["' + str('Input_9' + '"]') 
                    row_8AF5F.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_C0444, text='最大值', icon_value=0, emboss=True)
                    attr_45E0D = '["' + str('Input_10' + '"]') 
                    col_32717.prop(bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'], attr_45E0D, text='随机种子', icon_value=0, emboss=True)
            else:
                col_FF270 = col_EA2A0.column(heading='', align=True)
                col_FF270.alert = False
                col_FF270.enabled = True
                col_FF270.active = True
                col_FF270.use_property_split = False
                col_FF270.use_property_decorate = False
                col_FF270.scale_x = 1.0
                col_FF270.scale_y = 2.0
                col_FF270.alignment = 'Expand'.upper()
                col_FF270.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_FF270.operator('sna.my_generic_operator_2d208', text='随机摆放', icon_value=4, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_Fd0B9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_fd0b9"
    bl_label = "清空散布修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_E070D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e070d"
    bl_label = "一键配置自动散布"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0']['Input_3'] = bpy.context.scene.sna_pcg_scatter_instances
        bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0']['Input_2'] = bpy.context.scene.sna_pcg_scatter_collision
        bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0']['Input_22'] = bpy.context.scene.sna_pcg_scatter_boolean
        bpy.ops.sna.my_generic_operator_697b9()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_697B9(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_697b9"
    bl_label = "刷新散布修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'].show_viewport = False
        bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_2D208(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2d208"
    bl_label = "加载散布修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_摆放节点_v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_摆放节点_v1.0'].node_group = bpy.data.node_groups['PCG_摆放节点_v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_摆放节点_v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_ARRANGEMENT.blend')) + r'\NodeTree', filename='PCG_摆放节点_v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_17F26 = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_9762A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9762a"
    bl_label = "应用散布修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        node_tree_002['sna_pcg_modname'] = bpy.context.view_layer.objects.active.name
        collection_name_0_8c999 = sna_new_collection_5BD4A_8C999('PCG_' + node_tree_002['sna_pcg_modname'] + '_集合', False)
        collection_name_0_9ca90 = sna_new_collection_5BD4A_9CA90('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始', False)
        collection_name_0_84ff1 = sna_new_collection_5BD4A_84FF1('PCG_' + node_tree_002['sna_pcg_modname'] + '_散布', False)
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_散布'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_散布'], )
        sna_fnmovetocollection_397D9_4785B('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_2657D('PCG_' + node_tree_002['sna_pcg_modname'] + '_散布')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_pattern(pattern=node_tree_002['sna_pcg_modname'])
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_scatter_instances = bpy.props.PointerProperty(name='pcg_scatter_instances', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_scatter_collision = bpy.props.PointerProperty(name='PCG_scatter_collision', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_scatter_boolean = bpy.props.PointerProperty(name='PCG_scatter_boolean', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_scatter_scale = bpy.props.BoolProperty(name='PCG_scatter_scale', description='', options={'HIDDEN'}, default=False)
    bpy.utils.register_class(SNA_PT_PCG__AB37C)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Fd0B9)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E070D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_697B9)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2D208)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9762A)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_scatter_scale
    del bpy.types.Scene.sna_pcg_scatter_boolean
    del bpy.types.Scene.sna_pcg_scatter_collision
    del bpy.types.Scene.sna_pcg_scatter_instances
    bpy.utils.unregister_class(SNA_PT_PCG__AB37C)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Fd0B9)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E070D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_697B9)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2D208)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9762A)
