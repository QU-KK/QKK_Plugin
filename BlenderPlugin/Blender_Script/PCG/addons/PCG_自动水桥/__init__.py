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
    "name" : "PCG_Aqueduct_v1",
    "author" : "渠奎奎", 
    "description" : "自动水桥",
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


class SNA_PT_PCG__68398(bpy.types.Panel):
    bl_label = 'PCG_水桥'
    bl_idname = 'SNA_PT_PCG__68398'
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
            col_D4FFD = layout.column(heading='', align=True)
            col_D4FFD.alert = False
            col_D4FFD.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_D4FFD.active = True
            col_D4FFD.use_property_split = False
            col_D4FFD.use_property_decorate = False
            col_D4FFD.scale_x = 1.0
            col_D4FFD.scale_y = 1.0
            col_D4FFD.alignment = 'Expand'.upper()
            col_D4FFD.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals()):
                col_D4FFD.label(text='选中曲线：' + bpy.context.view_layer.objects.active.name, icon_value=236)
            else:
                col_D4FFD.label(text='非曲线：' + bpy.context.view_layer.objects.active.name, icon_value=3)
            col_D4FFD.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_程序化水桥_v1.0'].node_group.name", globals(), locals()):
                col_BECA6 = col_D4FFD.column(heading='', align=True)
                col_BECA6.alert = False
                col_BECA6.enabled = True
                col_BECA6.active = True
                col_BECA6.use_property_split = False
                col_BECA6.use_property_decorate = False
                col_BECA6.scale_x = 1.0
                col_BECA6.scale_y = 1.0
                col_BECA6.alignment = 'Expand'.upper()
                col_BECA6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_AF19A = col_BECA6.split(factor=0.5, align=True)
                split_AF19A.alert = False
                split_AF19A.enabled = True
                split_AF19A.active = True
                split_AF19A.use_property_split = False
                split_AF19A.use_property_decorate = False
                split_AF19A.scale_x = 1.0
                split_AF19A.scale_y = 1.2000000476837158
                split_AF19A.alignment = 'Expand'.upper()
                split_AF19A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = split_AF19A.operator('sna.my_generic_operator_af378', text='清空', icon_value=33, emboss=True, depress=False)
                col_D1C92 = split_AF19A.column(heading='', align=True)
                col_D1C92.alert = False
                col_D1C92.enabled = (len(bpy.context.view_layer.objects.selected.values()) == 1)
                col_D1C92.active = True
                col_D1C92.use_property_split = False
                col_D1C92.use_property_decorate = False
                col_D1C92.scale_x = 1.0
                col_D1C92.scale_y = 1.0
                col_D1C92.alignment = 'Expand'.upper()
                col_D1C92.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_D1C92.operator('sna.my_generic_operator_578bc', text='应用', icon_value=36, emboss=True, depress=False)
                box_FCC25 = col_BECA6.box()
                box_FCC25.alert = False
                box_FCC25.enabled = True
                box_FCC25.active = True
                box_FCC25.use_property_split = False
                box_FCC25.use_property_decorate = False
                box_FCC25.alignment = 'Expand'.upper()
                box_FCC25.scale_x = 1.0
                box_FCC25.scale_y = 1.0
                box_FCC25.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_CEFE4 = box_FCC25.column(heading='', align=False)
                col_CEFE4.alert = False
                col_CEFE4.enabled = True
                col_CEFE4.active = True
                col_CEFE4.use_property_split = False
                col_CEFE4.use_property_decorate = False
                col_CEFE4.scale_x = 1.0
                col_CEFE4.scale_y = 1.0
                col_CEFE4.alignment = 'Expand'.upper()
                col_CEFE4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_A62E9 = col_CEFE4.column(heading='', align=False)
                col_A62E9.alert = False
                col_A62E9.enabled = True
                col_A62E9.active = True
                col_A62E9.use_property_split = False
                col_A62E9.use_property_decorate = False
                col_A62E9.scale_x = 1.0
                col_A62E9.scale_y = 1.5
                col_A62E9.alignment = 'Expand'.upper()
                col_A62E9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_A62E9.operator('sna.my_generic_operator_2f0bc', text='一键配置', icon_value=4, emboss=True, depress=False)
                col_50A7A = col_CEFE4.column(heading='', align=True)
                col_50A7A.alert = False
                col_50A7A.enabled = True
                col_50A7A.active = True
                col_50A7A.use_property_split = False
                col_50A7A.use_property_decorate = False
                col_50A7A.scale_x = 1.0
                col_50A7A.scale_y = 1.0
                col_50A7A.alignment = 'Expand'.upper()
                col_50A7A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_50A7A.prop(bpy.context.scene, 'sna_pcg_board', text='板子', icon_value=0, emboss=True)
                col_50A7A.prop(bpy.context.scene, 'sna_pcg_support', text='支柱', icon_value=0, emboss=True)
                col_50A7A.prop(bpy.context.scene, 'sna_pcg_transom', text='横梁', icon_value=0, emboss=True)
                col_50A7A.prop(bpy.context.scene, 'sna_pcg_beam', text='长梁', icon_value=0, emboss=True)
                box_A4C0B = col_CEFE4.box()
                box_A4C0B.alert = False
                box_A4C0B.enabled = True
                box_A4C0B.active = True
                box_A4C0B.use_property_split = False
                box_A4C0B.use_property_decorate = False
                box_A4C0B.alignment = 'Expand'.upper()
                box_A4C0B.scale_x = 1.0
                box_A4C0B.scale_y = 1.0
                box_A4C0B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_4C33A = box_A4C0B.column(heading='', align=True)
                col_4C33A.alert = False
                col_4C33A.enabled = True
                col_4C33A.active = True
                col_4C33A.use_property_split = False
                col_4C33A.use_property_decorate = False
                col_4C33A.scale_x = 1.0
                col_4C33A.scale_y = 1.0
                col_4C33A.alignment = 'Expand'.upper()
                col_4C33A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_4C33A.label(text='板子：', icon_value=582)
                attr_648CD = '["' + str('Input_13' + '"]') 
                col_4C33A.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_648CD, text='间隔', icon_value=0, emboss=True)
                split_777E2 = col_4C33A.split(factor=0.699999988079071, align=True)
                split_777E2.alert = False
                split_777E2.enabled = True
                split_777E2.active = True
                split_777E2.use_property_split = False
                split_777E2.use_property_decorate = False
                split_777E2.scale_x = 1.0
                split_777E2.scale_y = 1.0
                split_777E2.alignment = 'Expand'.upper()
                split_777E2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_D9B47 = '["' + str('Input_5' + '"]') 
                split_777E2.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_D9B47, text='横向随机偏移', icon_value=0, emboss=True)
                attr_AA966 = '["' + str('Input_6' + '"]') 
                split_777E2.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_AA966, text='种子', icon_value=0, emboss=True)
                split_A9EB9 = col_4C33A.split(factor=0.699999988079071, align=True)
                split_A9EB9.alert = False
                split_A9EB9.enabled = True
                split_A9EB9.active = True
                split_A9EB9.use_property_split = False
                split_A9EB9.use_property_decorate = False
                split_A9EB9.scale_x = 1.0
                split_A9EB9.scale_y = 1.0
                split_A9EB9.alignment = 'Expand'.upper()
                split_A9EB9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_FE6A5 = '["' + str('Input_7' + '"]') 
                split_A9EB9.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_FE6A5, text='上下随机偏移', icon_value=0, emboss=True)
                attr_D9CED = '["' + str('Input_8' + '"]') 
                split_A9EB9.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_D9CED, text='种子', icon_value=0, emboss=True)
                split_C5E8E = col_4C33A.split(factor=0.699999988079071, align=True)
                split_C5E8E.alert = False
                split_C5E8E.enabled = True
                split_C5E8E.active = True
                split_C5E8E.use_property_split = False
                split_C5E8E.use_property_decorate = False
                split_C5E8E.scale_x = 1.0
                split_C5E8E.scale_y = 1.0
                split_C5E8E.alignment = 'Expand'.upper()
                split_C5E8E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_FEC54 = '["' + str('Input_9' + '"]') 
                split_C5E8E.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_FEC54, text='X随机旋转', icon_value=0, emboss=True)
                attr_6392A = '["' + str('Input_10' + '"]') 
                split_C5E8E.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_6392A, text='种子', icon_value=0, emboss=True)
                split_5C350 = col_4C33A.split(factor=0.699999988079071, align=True)
                split_5C350.alert = False
                split_5C350.enabled = True
                split_5C350.active = True
                split_5C350.use_property_split = False
                split_5C350.use_property_decorate = False
                split_5C350.scale_x = 1.0
                split_5C350.scale_y = 1.0
                split_5C350.alignment = 'Expand'.upper()
                split_5C350.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_15C1D = '["' + str('Input_11' + '"]') 
                split_5C350.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_15C1D, text='Y随机旋转', icon_value=0, emboss=True)
                attr_2181E = '["' + str('Input_12' + '"]') 
                split_5C350.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_2181E, text='种子', icon_value=0, emboss=True)
                box_29C9B = col_CEFE4.box()
                box_29C9B.alert = False
                box_29C9B.enabled = True
                box_29C9B.active = True
                box_29C9B.use_property_split = False
                box_29C9B.use_property_decorate = False
                box_29C9B.alignment = 'Expand'.upper()
                box_29C9B.scale_x = 1.0
                box_29C9B.scale_y = 1.0
                box_29C9B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_539D4 = box_29C9B.column(heading='', align=True)
                col_539D4.alert = False
                col_539D4.enabled = True
                col_539D4.active = True
                col_539D4.use_property_split = False
                col_539D4.use_property_decorate = False
                col_539D4.scale_x = 1.0
                col_539D4.scale_y = 1.0
                col_539D4.alignment = 'Expand'.upper()
                col_539D4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_539D4.label(text='支柱：', icon_value=498)
                attr_97309 = '["' + str('Input_20' + '"]') 
                col_539D4.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_97309, text='间隔', icon_value=0, emboss=True)
                attr_8E0C3 = '["' + str('Input_17' + '"]') 
                col_539D4.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_8E0C3, text='内缩', icon_value=0, emboss=True)
                box_85CFB = col_CEFE4.box()
                box_85CFB.alert = False
                box_85CFB.enabled = True
                box_85CFB.active = True
                box_85CFB.use_property_split = False
                box_85CFB.use_property_decorate = False
                box_85CFB.alignment = 'Expand'.upper()
                box_85CFB.scale_x = 1.0
                box_85CFB.scale_y = 1.0
                box_85CFB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_E2819 = box_85CFB.column(heading='', align=True)
                col_E2819.alert = False
                col_E2819.enabled = True
                col_E2819.active = True
                col_E2819.use_property_split = False
                col_E2819.use_property_decorate = False
                col_E2819.scale_x = 1.0
                col_E2819.scale_y = 1.0
                col_E2819.alignment = 'Expand'.upper()
                col_E2819.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_E2819.label(text='长梁：', icon_value=32)
                attr_81738 = '["' + str('Input_16' + '"]') 
                col_E2819.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'], attr_81738, text='内缩', icon_value=0, emboss=True)
            else:
                col_B43D9 = col_D4FFD.column(heading='', align=True)
                col_B43D9.alert = False
                col_B43D9.enabled = True
                col_B43D9.active = True
                col_B43D9.use_property_split = False
                col_B43D9.use_property_decorate = False
                col_B43D9.scale_x = 1.0
                col_B43D9.scale_y = 2.0
                col_B43D9.alignment = 'Expand'.upper()
                col_B43D9.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_B43D9.operator('sna.my_generic_operator_e6ce8', text='自动水桥', icon_value=4, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_2F0Bc(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_2f0bc"
    bl_label = "一键配置水桥修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0']['Input_14'] = bpy.context.scene.sna_pcg_board
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0']['Input_18'] = bpy.context.scene.sna_pcg_support
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0']['Input_21'] = bpy.context.scene.sna_pcg_transom
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0']['Input_15'] = bpy.context.scene.sna_pcg_beam
        bpy.ops.sna.my_generic_operator_1ac97()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_Af378(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_af378"
    bl_label = "清空水桥修改器"
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


class SNA_OT_My_Generic_Operator_1Ac97(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_1ac97"
    bl_label = "刷新水桥_修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'].show_viewport = False
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_E6Ce8(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e6ce8"
    bl_label = "自动水桥修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_程序化水桥_v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化水桥_v1.0'].node_group = bpy.data.node_groups['PCG_程序化水桥_v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_程序化水桥_v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_MIZUHASHI.blend')) + r'\NodeTree', filename='PCG_程序化水桥_v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_69CD7 = None if not new_data else new_data[0]
            print('')
        return self.execute(context)


class SNA_OT_My_Generic_Operator_578Bc(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_578bc"
    bl_label = "应用水桥_修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        node_tree_002['sna_pcg_modname'] = bpy.context.view_layer.objects.active.name
        collection_name_0_8c999 = sna_new_collection_5BD4A_8C999('PCG_' + node_tree_002['sna_pcg_modname'] + '_集合', False)
        collection_name_0_9ca90 = sna_new_collection_5BD4A_9CA90('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始', False)
        collection_name_0_84ff1 = sna_new_collection_5BD4A_84FF1('PCG_' + node_tree_002['sna_pcg_modname'] + '_水桥', False)
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_水桥'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_水桥'], )
        sna_fnmovetocollection_397D9_4785B('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_2657D('PCG_' + node_tree_002['sna_pcg_modname'] + '_水桥')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_pattern(pattern=node_tree_002['sna_pcg_modname'])
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_board = bpy.props.PointerProperty(name='PCG_board', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_beam = bpy.props.PointerProperty(name='PCG_beam', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_support = bpy.props.PointerProperty(name='PCG_support', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_transom = bpy.props.PointerProperty(name='PCG_transom', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.utils.register_class(SNA_PT_PCG__68398)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_2F0Bc)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Af378)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1Ac97)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E6Ce8)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_578Bc)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_transom
    del bpy.types.Scene.sna_pcg_support
    del bpy.types.Scene.sna_pcg_beam
    del bpy.types.Scene.sna_pcg_board
    bpy.utils.unregister_class(SNA_PT_PCG__68398)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_2F0Bc)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Af378)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1Ac97)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E6Ce8)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_578Bc)
