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
    "name" : "PCG_Telegraph pole_v1",
    "author" : "渠奎奎", 
    "description" : "程序化电线杆",
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
node_tree = {'sna_pcg_modname': '', }


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


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_OT_My_Generic_Operator_A2E45(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a2e45"
    bl_label = "应用电线杆修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        node_tree['sna_pcg_modname'] = bpy.context.view_layer.objects.active.name
        collection_name_0_8c999 = sna_new_collection_5BD4A_8C999('PCG_' + node_tree['sna_pcg_modname'] + '_集合', False)
        collection_name_0_9ca90 = sna_new_collection_5BD4A_9CA90('PCG_' + node_tree['sna_pcg_modname'] + '_原始', False)
        collection_name_0_84ff1 = sna_new_collection_5BD4A_84FF1('PCG_' + node_tree['sna_pcg_modname'] + '_楼梯', False)
        bpy.context.blend_data.collections['PCG_' + node_tree['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree['sna_pcg_modname'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree['sna_pcg_modname'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + node_tree['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree['sna_pcg_modname'] + '_楼梯'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree['sna_pcg_modname'] + '_楼梯'], )
        sna_fnmovetocollection_397D9_4785B('PCG_' + node_tree['sna_pcg_modname'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_2657D('PCG_' + node_tree['sna_pcg_modname'] + '_楼梯')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_pattern(pattern=node_tree['sna_pcg_modname'])
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_35F2D(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_35f2d"
    bl_label = "刷新电线杆修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'].show_viewport = False
        bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_6A193(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_6a193"
    bl_label = "清空电线杆修改器"
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


class SNA_OT_My_Generic_Operator_2Be65(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2be65"
    bl_label = "一键配置电线杆"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        if (bpy.context.scene.sna_pcg_assetcollection == None):
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_2'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_26'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_3'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_5'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_8'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_10'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_12'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_14'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_4'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_6'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_9'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_11'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_13'] = None
            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_15'] = None
            bpy.ops.sna.my_generic_operator_35f2d()
        else:
            for i_22F1E in range(len(bpy.context.scene.sna_pcg_assetcollection.children)):
                if '杆子_' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E]):
                    bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_2'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E]
                if '线缆_' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E]):
                    bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_26'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E]
                if '接口_' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E]):
                    for i_EF5E9 in range(len(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects)):
                        if '01A' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_3'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '01B' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_4'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '02A' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_5'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '02B' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_6'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '03A' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_8'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '03B' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_9'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '04A' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_10'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '04B' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_11'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '05A' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_12'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '05B' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_13'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '06A' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_14'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
                        if '06B' in str(bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]):
                            bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_15'] = bpy.context.scene.sna_pcg_assetcollection.children[i_22F1E].objects[i_EF5E9]
            bpy.ops.sna.my_generic_operator_35f2d()
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0']['Input_24'] = bpy.context.scene.sna_pcg_groundcollision
        bpy.ops.sna.my_generic_operator_35f2d()
        return self.execute(context)


class SNA_OT_My_Generic_Operator_12495(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_12495"
    bl_label = "新增电线杆修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_电线杆v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'].node_group = bpy.data.node_groups['PCG_电线杆v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_电线杆v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_TELEGRAPH.blend')) + r'\NodeTree', filename='PCG_电线杆v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_7748E = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_PT_PCG__E5207(bpy.types.Panel):
    bl_label = 'PCG_电线杆'
    bl_idname = 'SNA_PT_PCG__E5207'
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
            col_AF556 = layout.column(heading='', align=True)
            col_AF556.alert = False
            col_AF556.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_AF556.active = True
            col_AF556.use_property_split = False
            col_AF556.use_property_decorate = False
            col_AF556.scale_x = 1.0
            col_AF556.scale_y = 1.0
            col_AF556.alignment = 'Expand'.upper()
            col_AF556.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals()):
                col_AF556.label(text='选中曲线：' + bpy.context.view_layer.objects.active.name, icon_value=236)
            else:
                col_AF556.label(text='非曲线：' + bpy.context.view_layer.objects.active.name + '', icon_value=3)
            col_AF556.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_电线杆v1.0'].node_group.name", globals(), locals()):
                col_DC7B6 = col_AF556.column(heading='', align=True)
                col_DC7B6.alert = False
                col_DC7B6.enabled = True
                col_DC7B6.active = True
                col_DC7B6.use_property_split = False
                col_DC7B6.use_property_decorate = False
                col_DC7B6.scale_x = 1.0
                col_DC7B6.scale_y = 1.0
                col_DC7B6.alignment = 'Expand'.upper()
                col_DC7B6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_48A89 = col_DC7B6.split(factor=0.5, align=True)
                split_48A89.alert = False
                split_48A89.enabled = True
                split_48A89.active = True
                split_48A89.use_property_split = False
                split_48A89.use_property_decorate = False
                split_48A89.scale_x = 1.0
                split_48A89.scale_y = 1.2000000476837158
                split_48A89.alignment = 'Expand'.upper()
                split_48A89.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = split_48A89.operator('sna.my_generic_operator_6a193', text='清空', icon_value=33, emboss=True, depress=False)
                col_4D60F = split_48A89.column(heading='', align=True)
                col_4D60F.alert = False
                col_4D60F.enabled = (len(bpy.context.view_layer.objects.selected.values()) == 1)
                col_4D60F.active = True
                col_4D60F.use_property_split = False
                col_4D60F.use_property_decorate = False
                col_4D60F.scale_x = 1.0
                col_4D60F.scale_y = 1.0
                col_4D60F.alignment = 'Expand'.upper()
                col_4D60F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_4D60F.operator('sna.my_generic_operator_a2e45', text='应用', icon_value=36, emboss=True, depress=False)
                box_BB587 = col_DC7B6.box()
                box_BB587.alert = False
                box_BB587.enabled = True
                box_BB587.active = True
                box_BB587.use_property_split = False
                box_BB587.use_property_decorate = False
                box_BB587.alignment = 'Expand'.upper()
                box_BB587.scale_x = 1.0
                box_BB587.scale_y = 1.0
                box_BB587.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_023B9 = box_BB587.column(heading='', align=False)
                col_023B9.alert = False
                col_023B9.enabled = True
                col_023B9.active = True
                col_023B9.use_property_split = False
                col_023B9.use_property_decorate = False
                col_023B9.scale_x = 1.0
                col_023B9.scale_y = 1.0
                col_023B9.alignment = 'Expand'.upper()
                col_023B9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_2326F = col_023B9.column(heading='', align=False)
                col_2326F.alert = False
                col_2326F.enabled = True
                col_2326F.active = True
                col_2326F.use_property_split = False
                col_2326F.use_property_decorate = False
                col_2326F.scale_x = 1.0
                col_2326F.scale_y = 1.5
                col_2326F.alignment = 'Expand'.upper()
                col_2326F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_2326F.operator('sna.my_generic_operator_2be65', text='一键配置', icon_value=0, emboss=True, depress=False)
                col_023B9.prop(bpy.context.scene, 'sna_pcg_assetcollection', text='电线杆', icon_value=0, emboss=True)
                col_023B9.prop(bpy.context.scene, 'sna_pcg_groundcollision', text='地面碰撞', icon_value=0, emboss=True)
                col_42D25 = col_DC7B6.column(heading='', align=True)
                col_42D25.alert = False
                col_42D25.enabled = True
                col_42D25.active = True
                col_42D25.use_property_split = False
                col_42D25.use_property_decorate = False
                col_42D25.scale_x = 1.0
                col_42D25.scale_y = 1.2000000476837158
                col_42D25.alignment = 'Expand'.upper()
                col_42D25.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_DAA1D = '["' + str('Input_25' + '"]') 
                col_42D25.prop(bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'], attr_DAA1D, text='地面碰撞开关', icon_value=0, emboss=True)
                box_28D2D = col_42D25.box()
                box_28D2D.alert = False
                box_28D2D.enabled = True
                box_28D2D.active = True
                box_28D2D.use_property_split = False
                box_28D2D.use_property_decorate = False
                box_28D2D.alignment = 'Expand'.upper()
                box_28D2D.scale_x = 1.0
                box_28D2D.scale_y = 1.0
                box_28D2D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_2C3E5 = box_28D2D.column(heading='', align=True)
                col_2C3E5.alert = False
                col_2C3E5.enabled = True
                col_2C3E5.active = True
                col_2C3E5.use_property_split = False
                col_2C3E5.use_property_decorate = False
                col_2C3E5.scale_x = 1.0
                col_2C3E5.scale_y = 1.0
                col_2C3E5.alignment = 'Expand'.upper()
                col_2C3E5.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_2C3E5.label(text='杆子：', icon_value=297)
                attr_593C8 = '["' + str('Input_21' + '"]') 
                col_2C3E5.prop(bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'], attr_593C8, text='间隔', icon_value=0, emboss=True)
                attr_7B0B9 = '["' + str('Input_22' + '"]') 
                col_2C3E5.prop(bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'], attr_7B0B9, text='缩放', icon_value=0, emboss=True)
                split_47648 = col_2C3E5.split(factor=0.699999988079071, align=True)
                split_47648.alert = False
                split_47648.enabled = True
                split_47648.active = True
                split_47648.use_property_split = False
                split_47648.use_property_decorate = False
                split_47648.scale_x = 1.0
                split_47648.scale_y = 1.0
                split_47648.alignment = 'Expand'.upper()
                split_47648.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_06E2B = '["' + str('Input_19' + '"]') 
                split_47648.prop(bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'], attr_06E2B, text='种类数量', icon_value=0, emboss=True)
                attr_F2005 = '["' + str('Input_20' + '"]') 
                split_47648.prop(bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'], attr_F2005, text='种子', icon_value=0, emboss=True)
                box_F9BAC = col_42D25.box()
                box_F9BAC.alert = False
                box_F9BAC.enabled = True
                box_F9BAC.active = True
                box_F9BAC.use_property_split = False
                box_F9BAC.use_property_decorate = False
                box_F9BAC.alignment = 'Expand'.upper()
                box_F9BAC.scale_x = 1.0
                box_F9BAC.scale_y = 1.0
                box_F9BAC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_0A190 = box_F9BAC.column(heading='', align=True)
                col_0A190.alert = False
                col_0A190.enabled = True
                col_0A190.active = True
                col_0A190.use_property_split = False
                col_0A190.use_property_decorate = False
                col_0A190.scale_x = 1.0
                col_0A190.scale_y = 1.0
                col_0A190.alignment = 'Expand'.upper()
                col_0A190.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_0A190.label(text='电线下垂：', icon_value=537)
                row_5A7FA = col_0A190.row(heading='', align=True)
                row_5A7FA.alert = False
                row_5A7FA.enabled = True
                row_5A7FA.active = True
                row_5A7FA.use_property_split = False
                row_5A7FA.use_property_decorate = False
                row_5A7FA.scale_x = 1.0
                row_5A7FA.scale_y = 1.0
                row_5A7FA.alignment = 'Expand'.upper()
                row_5A7FA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_9C7BE = '["' + str('Input_16' + '"]') 
                row_5A7FA.prop(bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'], attr_9C7BE, text='Min', icon_value=0, emboss=True)
                attr_44F9F = '["' + str('Input_17' + '"]') 
                row_5A7FA.prop(bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'], attr_44F9F, text='Max', icon_value=0, emboss=True)
                attr_EF2D3 = '["' + str('Input_18' + '"]') 
                row_5A7FA.prop(bpy.context.view_layer.objects.active.modifiers['PCG_电线杆v1.0'], attr_EF2D3, text='种子', icon_value=0, emboss=True)
            else:
                col_F860E = col_AF556.column(heading='', align=True)
                col_F860E.alert = False
                col_F860E.enabled = True
                col_F860E.active = True
                col_F860E.use_property_split = False
                col_F860E.use_property_decorate = False
                col_F860E.scale_x = 1.0
                col_F860E.scale_y = 2.0
                col_F860E.alignment = 'Expand'.upper()
                col_F860E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_F860E.operator('sna.my_generic_operator_12495', text='电线杆', icon_value=4, emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_assetcollection = bpy.props.PointerProperty(name='PCG_AssetCollection', description='识别子集名称字符，杆子_，接口_', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_groundcollision = bpy.props.PointerProperty(name='PCG_GroundCollision', description='用于识别杆子接地', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A2E45)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_35F2D)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_6A193)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2Be65)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_12495)
    bpy.utils.register_class(SNA_PT_PCG__E5207)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_groundcollision
    del bpy.types.Scene.sna_pcg_assetcollection
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A2E45)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_35F2D)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_6A193)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2Be65)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_12495)
    bpy.utils.unregister_class(SNA_PT_PCG__E5207)
