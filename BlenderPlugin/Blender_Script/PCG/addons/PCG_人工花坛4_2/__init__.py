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
    "name" : "PCG_curvescatter_4.2_v1",
    "author" : "渠奎奎", 
    "description" : "曲线撒点",
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
node_tree_001 = {'sna_pcg_modname': '', }


def sna_update_sna_pcg_curvescatter_collision_1912F(self, context):
    sna_updated_prop = self.sna_pcg_curvescatter_collision
    bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0']['Input_2'] = bpy.context.scene.sna_pcg_curvescatter_collision
    bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'].show_viewport = True


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


class SNA_OT_My_Generic_Operator_4814B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_4814b"
    bl_label = "清空曲线撒点修改器"
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


class SNA_OT_My_Generic_Operator_36893(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_36893"
    bl_label = "一键配置_曲线撒点"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0']['Input_2'] = bpy.context.scene.sna_pcg_curvescatter_collision
        bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_PCG__70975(bpy.types.Panel):
    bl_label = 'PCG_曲线撒点'
    bl_idname = 'SNA_PT_PCG__70975'
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
            col_848D1 = layout.column(heading='', align=True)
            col_848D1.alert = False
            col_848D1.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_848D1.active = True
            col_848D1.use_property_split = False
            col_848D1.use_property_decorate = False
            col_848D1.scale_x = 1.0
            col_848D1.scale_y = 1.0
            col_848D1.alignment = 'Expand'.upper()
            col_848D1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals()):
                col_848D1.label(text='选中曲线：' + bpy.context.view_layer.objects.active.name, icon_value=236)
            else:
                col_848D1.label(text='非曲线：' + bpy.context.view_layer.objects.active.name, icon_value=3)
            col_848D1.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_曲线撒点v1.0'].node_group.name", globals(), locals()):
                col_47D63 = col_848D1.column(heading='', align=True)
                col_47D63.alert = False
                col_47D63.enabled = True
                col_47D63.active = True
                col_47D63.use_property_split = False
                col_47D63.use_property_decorate = False
                col_47D63.scale_x = 1.0
                col_47D63.scale_y = 1.0
                col_47D63.alignment = 'Expand'.upper()
                col_47D63.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_C75BA = col_47D63.split(factor=0.5, align=True)
                split_C75BA.alert = False
                split_C75BA.enabled = True
                split_C75BA.active = True
                split_C75BA.use_property_split = False
                split_C75BA.use_property_decorate = False
                split_C75BA.scale_x = 1.0
                split_C75BA.scale_y = 1.2000000476837158
                split_C75BA.alignment = 'Expand'.upper()
                if not True: split_C75BA.operator_context = "EXEC_DEFAULT"
                op = split_C75BA.operator('sna.my_generic_operator_4814b', text='清空', icon_value=33, emboss=True, depress=False)
                col_EAEF4 = split_C75BA.column(heading='', align=True)
                col_EAEF4.alert = False
                col_EAEF4.enabled = (len(list(bpy.context.view_layer.objects.selected)) == 1)
                col_EAEF4.active = True
                col_EAEF4.use_property_split = False
                col_EAEF4.use_property_decorate = False
                col_EAEF4.scale_x = 1.0
                col_EAEF4.scale_y = 1.0
                col_EAEF4.alignment = 'Expand'.upper()
                col_EAEF4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_EAEF4.operator('sna.my_generic_operator_c6c6a', text='应用', icon_value=36, emboss=True, depress=False)
                box_09F02 = col_47D63.box()
                box_09F02.alert = False
                box_09F02.enabled = True
                box_09F02.active = True
                box_09F02.use_property_split = False
                box_09F02.use_property_decorate = False
                box_09F02.alignment = 'Expand'.upper()
                box_09F02.scale_x = 1.0
                box_09F02.scale_y = 1.0
                if not True: box_09F02.operator_context = "EXEC_DEFAULT"
                col_B7DDD = box_09F02.column(heading='', align=False)
                col_B7DDD.alert = False
                col_B7DDD.enabled = True
                col_B7DDD.active = True
                col_B7DDD.use_property_split = False
                col_B7DDD.use_property_decorate = False
                col_B7DDD.scale_x = 1.0
                col_B7DDD.scale_y = 1.0
                col_B7DDD.alignment = 'Expand'.upper()
                col_B7DDD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_35EAD = col_B7DDD.column(heading='', align=False)
                col_35EAD.alert = False
                col_35EAD.enabled = True
                col_35EAD.active = True
                col_35EAD.use_property_split = False
                col_35EAD.use_property_decorate = False
                col_35EAD.scale_x = 1.0
                col_35EAD.scale_y = 1.5
                col_35EAD.alignment = 'Expand'.upper()
                col_35EAD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_35EAD.operator('sna.my_generic_operator_36893', text='一键配置', icon_value=4, emboss=True, depress=False)
                col_161A6 = col_B7DDD.column(heading='', align=False)
                col_161A6.alert = False
                col_161A6.enabled = True
                col_161A6.active = True
                col_161A6.use_property_split = False
                col_161A6.use_property_decorate = False
                col_161A6.scale_x = 1.0
                col_161A6.scale_y = 1.2999999523162842
                col_161A6.alignment = 'Expand'.upper()
                col_161A6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_74C0F = col_161A6.split(factor=0.699999988079071, align=True)
                split_74C0F.alert = False
                split_74C0F.enabled = True
                split_74C0F.active = True
                split_74C0F.use_property_split = False
                split_74C0F.use_property_decorate = False
                split_74C0F.scale_x = 1.0
                split_74C0F.scale_y = 1.0
                split_74C0F.alignment = 'Expand'.upper()
                if not True: split_74C0F.operator_context = "EXEC_DEFAULT"
                split_74C0F.prop(bpy.context.scene, 'sna_pcg_curvescatter_collision', text='地面', icon_value=0, emboss=True)
                split_74C0F.prop(bpy.context.scene, 'sna_pcg_curvescatter_layer', text='层数：', icon_value=0, emboss=True)
                for i_C8519 in range(bpy.context.scene.sna_pcg_curvescatter_layer):
                    box_3578B = col_B7DDD.box()
                    box_3578B.alert = False
                    box_3578B.enabled = True
                    box_3578B.active = True
                    box_3578B.use_property_split = False
                    box_3578B.use_property_decorate = False
                    box_3578B.alignment = 'Expand'.upper()
                    box_3578B.scale_x = 1.0
                    box_3578B.scale_y = 1.0
                    if not True: box_3578B.operator_context = "EXEC_DEFAULT"
                    col_1BAE3 = box_3578B.column(heading='', align=True)
                    col_1BAE3.alert = False
                    col_1BAE3.enabled = True
                    col_1BAE3.active = True
                    col_1BAE3.use_property_split = False
                    col_1BAE3.use_property_decorate = False
                    col_1BAE3.scale_x = 1.0
                    col_1BAE3.scale_y = 1.100000023841858
                    col_1BAE3.alignment = 'Expand'.upper()
                    col_1BAE3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    col_1BAE3.label(text='物体' + str(int(i_C8519 + 1.0)) + ':', icon_value=235)
                    attr_C9E59 = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 60.0)) + '"]') 
                    col_1BAE3.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_C9E59, text='物体', icon_value=0, emboss=True)
                    col_1BAE3.separator(factor=0.5)
                    split_C8A5A = col_1BAE3.split(factor=0.5, align=True)
                    split_C8A5A.alert = False
                    split_C8A5A.enabled = True
                    split_C8A5A.active = True
                    split_C8A5A.use_property_split = False
                    split_C8A5A.use_property_decorate = False
                    split_C8A5A.scale_x = 1.0
                    split_C8A5A.scale_y = 1.0
                    split_C8A5A.alignment = 'Expand'.upper()
                    if not True: split_C8A5A.operator_context = "EXEC_DEFAULT"
                    attr_AACF3 = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 61.0)) + '"]') 
                    split_C8A5A.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_AACF3, text='密度：', icon_value=0, emboss=True)
                    attr_BB39D = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 62.0)) + '"]') 
                    split_C8A5A.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_BB39D, text='分布随机', icon_value=0, emboss=True)
                    split_D8F3E = col_1BAE3.split(factor=0.5, align=True)
                    split_D8F3E.alert = False
                    split_D8F3E.enabled = True
                    split_D8F3E.active = True
                    split_D8F3E.use_property_split = False
                    split_D8F3E.use_property_decorate = False
                    split_D8F3E.scale_x = 1.0
                    split_D8F3E.scale_y = 1.0
                    split_D8F3E.alignment = 'Expand'.upper()
                    if not True: split_D8F3E.operator_context = "EXEC_DEFAULT"
                    attr_7F936 = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 63.0)) + '"]') 
                    split_D8F3E.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_7F936, text='缩放最小：', icon_value=0, emboss=True)
                    attr_C5CAE = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 64.0)) + '"]') 
                    split_D8F3E.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_C5CAE, text='缩放最大：', icon_value=0, emboss=True)
                    attr_EEEAC = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 65.0)) + '"]') 
                    col_1BAE3.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_EEEAC, text='缩放随机：', icon_value=0, emboss=True)
                    split_3A879 = col_1BAE3.split(factor=0.5, align=True)
                    split_3A879.alert = False
                    split_3A879.enabled = True
                    split_3A879.active = True
                    split_3A879.use_property_split = False
                    split_3A879.use_property_decorate = False
                    split_3A879.scale_x = 1.0
                    split_3A879.scale_y = 1.0
                    split_3A879.alignment = 'Expand'.upper()
                    if not True: split_3A879.operator_context = "EXEC_DEFAULT"
                    attr_BD653 = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 66.0)) + '"]') 
                    split_3A879.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_BD653, text='旋转最小：', icon_value=0, emboss=True)
                    attr_BFA08 = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 67.0)) + '"]') 
                    split_3A879.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_BFA08, text='旋转最大：', icon_value=0, emboss=True)
                    attr_03A0C = '["' + str('Input_' + str(int(int(i_C8519 * 9.0) + 68.0)) + '"]') 
                    col_1BAE3.prop(bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'], attr_03A0C, text='旋转随机：', icon_value=0, emboss=True)
            else:
                col_7ED3B = col_848D1.column(heading='', align=True)
                col_7ED3B.alert = False
                col_7ED3B.enabled = True
                col_7ED3B.active = True
                col_7ED3B.use_property_split = False
                col_7ED3B.use_property_decorate = False
                col_7ED3B.scale_x = 1.0
                col_7ED3B.scale_y = 2.0
                col_7ED3B.alignment = 'Expand'.upper()
                col_7ED3B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_7ED3B.operator('sna.my_generic_operator_ffabf', text='曲线撒点', icon_value=4, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_Ffabf(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_ffabf"
    bl_label = "加载曲线撒点修改器"
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
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_曲线撒点v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_曲线撒点v1.0'].node_group = bpy.data.node_groups['PCG_曲线撒点v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_曲线撒点v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_CURVESCATTERING.blend')) + r'\NodeTree', filename='PCG_曲线撒点v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_69CD7 = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_C6C6A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_c6c6a"
    bl_label = "应用曲线撒点修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and False:
            cls.poll_message_set()
        return not False

    def execute(self, context):
        node_tree_001['sna_pcg_modname'] = bpy.context.view_layer.objects.active.name
        collection_name_0_8c999 = sna_new_collection_5BD4A_8C999('PCG_' + node_tree_001['sna_pcg_modname'] + '_集合', False)
        collection_name_0_9ca90 = sna_new_collection_5BD4A_9CA90('PCG_' + node_tree_001['sna_pcg_modname'] + '_原始', False)
        collection_name_0_84ff1 = sna_new_collection_5BD4A_84FF1('PCG_' + node_tree_001['sna_pcg_modname'] + '_曲线撒点', False)
        bpy.context.blend_data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_曲线撒点'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_曲线撒点'], )
        sna_fnmovetocollection_397D9_4785B('PCG_' + node_tree_001['sna_pcg_modname'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_2657D('PCG_' + node_tree_001['sna_pcg_modname'] + '_曲线撒点')
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_curvescatter_collision = bpy.props.PointerProperty(name='pcg_curvescatter_collision', description='', options={'HIDDEN'}, type=bpy.types.Collection, update=sna_update_sna_pcg_curvescatter_collision_1912F)
    bpy.types.Scene.sna_pcg_curvescatter_layer = bpy.props.IntProperty(name='pcg_curvescatter_layer', description='', options={'HIDDEN'}, default=1, subtype='NONE', min=1, max=6)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_4814B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_36893)
    bpy.utils.register_class(SNA_PT_PCG__70975)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Ffabf)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_C6C6A)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_curvescatter_layer
    del bpy.types.Scene.sna_pcg_curvescatter_collision
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_4814B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_36893)
    bpy.utils.unregister_class(SNA_PT_PCG__70975)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Ffabf)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_C6C6A)
