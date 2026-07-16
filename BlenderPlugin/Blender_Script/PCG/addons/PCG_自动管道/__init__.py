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
    "name" : "PCG_Hose_v1",
    "author" : "渠奎奎", 
    "description" : "自动化软管",
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
pcg_ = {'sna_pcg_mod_name': '', }


def sna_new_collection_5BD4A_F5687(Collection_Name, Make_Child_of_Active_Object_Collection):
    collection_CD254 = bpy.data.collections.new(name=Collection_Name, )
    if Make_Child_of_Active_Object_Collection:
        for i_56CB2 in range(len(bpy.context.view_layer.objects.active.users_collection)):
            pass
        bpy.context.view_layer.objects.active.users_collection[i_56CB2].children.link(child=collection_CD254, )
    else:
        bpy.context.scene.collection.children.link(child=collection_CD254, )
    return collection_CD254.name


def sna_new_collection_5BD4A_CB89B(Collection_Name, Make_Child_of_Active_Object_Collection):
    collection_CD254 = bpy.data.collections.new(name=Collection_Name, )
    if Make_Child_of_Active_Object_Collection:
        for i_56CB2 in range(len(bpy.context.view_layer.objects.active.users_collection)):
            pass
        bpy.context.view_layer.objects.active.users_collection[i_56CB2].children.link(child=collection_CD254, )
    else:
        bpy.context.scene.collection.children.link(child=collection_CD254, )
    return collection_CD254.name


def sna_new_collection_5BD4A_B64A2(Collection_Name, Make_Child_of_Active_Object_Collection):
    collection_CD254 = bpy.data.collections.new(name=Collection_Name, )
    if Make_Child_of_Active_Object_Collection:
        for i_56CB2 in range(len(bpy.context.view_layer.objects.active.users_collection)):
            pass
        bpy.context.view_layer.objects.active.users_collection[i_56CB2].children.link(child=collection_CD254, )
    else:
        bpy.context.scene.collection.children.link(child=collection_CD254, )
    return collection_CD254.name


def sna_new_collection_5BD4A_3CE19(Collection_Name, Make_Child_of_Active_Object_Collection):
    collection_CD254 = bpy.data.collections.new(name=Collection_Name, )
    if Make_Child_of_Active_Object_Collection:
        for i_56CB2 in range(len(bpy.context.view_layer.objects.active.users_collection)):
            pass
        bpy.context.view_layer.objects.active.users_collection[i_56CB2].children.link(child=collection_CD254, )
    else:
        bpy.context.scene.collection.children.link(child=collection_CD254, )
    return collection_CD254.name


movetocollection_s3_vars_F3C8A = {'sna_objectstomove': [], }


def sna_fnmovetocollection_397D9_F3C8A(CollectionName):
    if (len(bpy.context.view_layer.objects.selected.values()) > 0):
        if property_exists("bpy.data.collections[CollectionName]", globals(), locals()):
            sna_fnlinkunlink_41AEA(CollectionName)
        else:
            collection_752A1 = bpy.data.collections.new(name=CollectionName, )
            bpy.context.scene.collection.children.link(child=collection_752A1, )
            sna_fnlinkunlink_41AEA(CollectionName)


movetocollection_s3_vars_3F4EC = {'sna_objectstomove': [], }


def sna_fnmovetocollection_397D9_3F4EC(CollectionName):
    if (len(bpy.context.view_layer.objects.selected.values()) > 0):
        if property_exists("bpy.data.collections[CollectionName]", globals(), locals()):
            sna_fnlinkunlink_41AEA(CollectionName)
        else:
            collection_752A1 = bpy.data.collections.new(name=CollectionName, )
            bpy.context.scene.collection.children.link(child=collection_752A1, )
            sna_fnlinkunlink_41AEA(CollectionName)


movetocollection_s3_vars_F0F62 = {'sna_objectstomove': [], }


def sna_fnmovetocollection_397D9_F0F62(CollectionName):
    if (len(bpy.context.view_layer.objects.selected.values()) > 0):
        if property_exists("bpy.data.collections[CollectionName]", globals(), locals()):
            sna_fnlinkunlink_41AEA(CollectionName)
        else:
            collection_752A1 = bpy.data.collections.new(name=CollectionName, )
            bpy.context.scene.collection.children.link(child=collection_752A1, )
            sna_fnlinkunlink_41AEA(CollectionName)


def sna_fnlinkunlink_41AEA(CollectionName):
    movetocollection_s3_vars_F0F62['sna_objectstomove'] = []
    for i_5B107 in range(len(bpy.context.view_layer.objects.selected)):
        movetocollection_s3_vars_F0F62['sna_objectstomove'].append(bpy.context.view_layer.objects.selected[i_5B107])
    for i_18D5A in range(len(bpy.context.view_layer.objects.selected)):
        for i_BE9A3 in range(len(bpy.context.view_layer.objects.selected[i_18D5A].users_collection)):
            if (bpy.context.view_layer.objects.selected[i_18D5A].users_collection[i_BE9A3].name == CollectionName):
                movetocollection_s3_vars_F0F62['sna_objectstomove'].remove(bpy.context.view_layer.objects.selected[i_18D5A])
    for i_EC7E0 in range(len(movetocollection_s3_vars_F0F62['sna_objectstomove'])):
        for i_726C8 in range(len(movetocollection_s3_vars_F0F62['sna_objectstomove'][i_EC7E0].users_collection)):
            movetocollection_s3_vars_F0F62['sna_objectstomove'][i_EC7E0].users_collection[i_726C8].objects.unlink(object=movetocollection_s3_vars_F0F62['sna_objectstomove'][i_EC7E0], )
    for i_9A186 in range(len(movetocollection_s3_vars_F0F62['sna_objectstomove'])):
        bpy.data.collections[CollectionName].objects.link(object=movetocollection_s3_vars_F0F62['sna_objectstomove'][i_9A186], )


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


class SNA_OT_My_Generic_Operator_69209(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_69209"
    bl_label = "一键配置软管"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0']['Input_2'] = bpy.context.scene.sna_pcg_pipe_jointa
        bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0']['Input_3'] = bpy.context.scene.sna_pcg__pipe_jointb
        bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0']['Input_7'] = bpy.context.scene.sna_pcg__pipe_material
        bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0'].show_viewport = False
        bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_9Ba76(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_9ba76"
    bl_label = "新增软管修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_管道v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0'].node_group = bpy.data.node_groups['PCG_管道v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_管道v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_PIPE.blend')) + r'\NodeTree', filename='PCG_管道v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_C35DB = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_1B0Cc(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_1b0cc"
    bl_label = "清空软管修改器"
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


class SNA_OT_My_Generic_Operator_3815B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_3815b"
    bl_label = "应用软管修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        pcg_['sna_pcg_mod_name'] = bpy.context.view_layer.objects.active.name
        collection_name_0_f5687 = sna_new_collection_5BD4A_F5687('PCG_' + pcg_['sna_pcg_mod_name'] + '_集合', False)
        collection_name_0_cb89b = sna_new_collection_5BD4A_CB89B('PCG_' + pcg_['sna_pcg_mod_name'] + '_原始', False)
        collection_name_0_b64a2 = sna_new_collection_5BD4A_B64A2('PCG_' + pcg_['sna_pcg_mod_name'] + '_接口', False)
        collection_name_0_3ce19 = sna_new_collection_5BD4A_3CE19('PCG_' + pcg_['sna_pcg_mod_name'] + '_管道', False)
        bpy.context.blend_data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_接口'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_接口'], )
        bpy.context.blend_data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_管道'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + pcg_['sna_pcg_mod_name'] + '_管道'], )
        sna_fnmovetocollection_397D9_F3C8A('PCG_' + pcg_['sna_pcg_mod_name'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_3F4EC('PCG_' + pcg_['sna_pcg_mod_name'] + '_接口')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.blend_data.objects.remove(object=bpy.data.objects[pcg_['sna_pcg_mod_name'] + '.001'], )
        bpy.ops.object.select_pattern(pattern=pcg_['sna_pcg_mod_name'])
        bpy.ops.object.convert(keep_original=True)
        sna_fnmovetocollection_397D9_F0F62('PCG_' + pcg_['sna_pcg_mod_name'] + '_管道')
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_PT_PCG__EC878(bpy.types.Panel):
    bl_label = 'PCG_软管'
    bl_idname = 'SNA_PT_PCG__EC878'
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
            col_66E7C = layout.column(heading='', align=True)
            col_66E7C.alert = False
            col_66E7C.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_66E7C.active = True
            col_66E7C.use_property_split = False
            col_66E7C.use_property_decorate = False
            col_66E7C.scale_x = 1.0
            col_66E7C.scale_y = 1.0
            col_66E7C.alignment = 'Expand'.upper()
            col_66E7C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals()):
                col_66E7C.label(text='选中曲线：' + bpy.context.view_layer.objects.active.name, icon_value=236)
            else:
                col_66E7C.label(text='非曲线：' + bpy.context.view_layer.objects.active.name + '', icon_value=3)
            col_66E7C.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_管道v1.0'].node_group.name", globals(), locals()):
                col_3A0B1 = col_66E7C.column(heading='', align=True)
                col_3A0B1.alert = False
                col_3A0B1.enabled = True
                col_3A0B1.active = True
                col_3A0B1.use_property_split = False
                col_3A0B1.use_property_decorate = False
                col_3A0B1.scale_x = 1.0
                col_3A0B1.scale_y = 1.2000000476837158
                col_3A0B1.alignment = 'Expand'.upper()
                col_3A0B1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_FCC29 = col_3A0B1.split(factor=0.5, align=True)
                split_FCC29.alert = False
                split_FCC29.enabled = True
                split_FCC29.active = True
                split_FCC29.use_property_split = False
                split_FCC29.use_property_decorate = False
                split_FCC29.scale_x = 1.0
                split_FCC29.scale_y = 1.2000000476837158
                split_FCC29.alignment = 'Expand'.upper()
                split_FCC29.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = split_FCC29.operator('sna.my_generic_operator_1b0cc', text='清空', icon_value=33, emboss=True, depress=False)
                col_289C8 = split_FCC29.column(heading='', align=True)
                col_289C8.alert = False
                col_289C8.enabled = (len(bpy.context.view_layer.objects.selected.values()) == 1)
                col_289C8.active = True
                col_289C8.use_property_split = False
                col_289C8.use_property_decorate = False
                col_289C8.scale_x = 1.0
                col_289C8.scale_y = 1.0
                col_289C8.alignment = 'Expand'.upper()
                col_289C8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_289C8.operator('sna.my_generic_operator_3815b', text='应用', icon_value=36, emboss=True, depress=False)
                box_097B2 = col_3A0B1.box()
                box_097B2.alert = False
                box_097B2.enabled = True
                box_097B2.active = True
                box_097B2.use_property_split = False
                box_097B2.use_property_decorate = False
                box_097B2.alignment = 'Expand'.upper()
                box_097B2.scale_x = 1.0
                box_097B2.scale_y = 1.0
                box_097B2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_2840A = box_097B2.column(heading='', align=True)
                col_2840A.alert = False
                col_2840A.enabled = True
                col_2840A.active = True
                col_2840A.use_property_split = False
                col_2840A.use_property_decorate = False
                col_2840A.scale_x = 1.0
                col_2840A.scale_y = 1.5
                col_2840A.alignment = 'Expand'.upper()
                col_2840A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_2840A.operator('sna.my_generic_operator_69209', text='一键配置', icon_value=0, emboss=True, depress=False)
                col_80E16 = box_097B2.column(heading='', align=False)
                col_80E16.alert = False
                col_80E16.enabled = True
                col_80E16.active = True
                col_80E16.use_property_split = False
                col_80E16.use_property_decorate = False
                col_80E16.scale_x = 1.0
                col_80E16.scale_y = 1.0
                col_80E16.alignment = 'Expand'.upper()
                col_80E16.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_80E16.prop(bpy.context.scene, 'sna_pcg_pipe_jointa', text='接口A', icon_value=0, emboss=True)
                col_80E16.prop(bpy.context.scene, 'sna_pcg__pipe_jointb', text='接口B', icon_value=0, emboss=True)
                col_80E16.prop(bpy.context.scene, 'sna_pcg__pipe_material', text='管道材质', icon_value=0, emboss=True)
                box_3645A = col_3A0B1.box()
                box_3645A.alert = False
                box_3645A.enabled = True
                box_3645A.active = True
                box_3645A.use_property_split = False
                box_3645A.use_property_decorate = False
                box_3645A.alignment = 'Expand'.upper()
                box_3645A.scale_x = 1.0
                box_3645A.scale_y = 1.0
                box_3645A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_DBC04 = box_3645A.column(heading='', align=True)
                col_DBC04.alert = False
                col_DBC04.enabled = True
                col_DBC04.active = True
                col_DBC04.use_property_split = False
                col_DBC04.use_property_decorate = False
                col_DBC04.scale_x = 1.0
                col_DBC04.scale_y = 1.2000000476837158
                col_DBC04.alignment = 'Expand'.upper()
                col_DBC04.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_DBC04.label(text='管道控制：', icon_value=236)
                attr_352CA = '["' + str('Input_4' + '"]') 
                col_DBC04.prop(bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0'], attr_352CA, text='管道段数', icon_value=0, emboss=True)
                attr_F31E4 = '["' + str('Input_5' + '"]') 
                col_DBC04.prop(bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0'], attr_F31E4, text='截面段数', icon_value=0, emboss=True)
                attr_E703A = '["' + str('Input_6' + '"]') 
                col_DBC04.prop(bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0'], attr_E703A, text='管道半径', icon_value=0, emboss=True)
                box_D5E3C = col_3A0B1.box()
                box_D5E3C.alert = False
                box_D5E3C.enabled = True
                box_D5E3C.active = True
                box_D5E3C.use_property_split = False
                box_D5E3C.use_property_decorate = False
                box_D5E3C.alignment = 'Expand'.upper()
                box_D5E3C.scale_x = 1.0
                box_D5E3C.scale_y = 1.0
                box_D5E3C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_A334B = box_D5E3C.column(heading='', align=True)
                col_A334B.alert = False
                col_A334B.enabled = True
                col_A334B.active = True
                col_A334B.use_property_split = False
                col_A334B.use_property_decorate = False
                col_A334B.scale_x = 1.0
                col_A334B.scale_y = 1.0
                col_A334B.alignment = 'Expand'.upper()
                col_A334B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_A334B.label(text='UV控制：', icon_value=263)
                split_9D621 = col_A334B.split(factor=0.5, align=True)
                split_9D621.alert = False
                split_9D621.enabled = True
                split_9D621.active = True
                split_9D621.use_property_split = False
                split_9D621.use_property_decorate = False
                split_9D621.scale_x = 1.0
                split_9D621.scale_y = 1.0
                split_9D621.alignment = 'Expand'.upper()
                split_9D621.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_0328E = '["' + str('Input_9' + '"]') 
                split_9D621.prop(bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0'], attr_0328E, text='UV比例', icon_value=0, emboss=True)
                attr_F8693 = '["' + str('Input_10' + '"]') 
                split_9D621.prop(bpy.context.view_layer.objects.active.modifiers['PCG_管道v1.0'], attr_F8693, text='UV名称', icon_value=0, emboss=True)
            else:
                col_23D88 = col_66E7C.column(heading='', align=True)
                col_23D88.alert = False
                col_23D88.enabled = True
                col_23D88.active = True
                col_23D88.use_property_split = False
                col_23D88.use_property_decorate = False
                col_23D88.scale_x = 1.0
                col_23D88.scale_y = 2.0
                col_23D88.alignment = 'Expand'.upper()
                col_23D88.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_23D88.operator('sna.my_generic_operator_9ba76', text='管道', icon_value=4, emboss=True, depress=False)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_pipe_jointa = bpy.props.PointerProperty(name='PCG_Pipe jointA', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg__pipe_jointb = bpy.props.PointerProperty(name='PCG_ Pipe jointB', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg__pipe_material = bpy.props.PointerProperty(name='PCG_ Pipe material', description='', options={'HIDDEN'}, type=bpy.types.Material)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_69209)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_9Ba76)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1B0Cc)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_3815B)
    bpy.utils.register_class(SNA_PT_PCG__EC878)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg__pipe_material
    del bpy.types.Scene.sna_pcg__pipe_jointb
    del bpy.types.Scene.sna_pcg_pipe_jointa
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_69209)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_9Ba76)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1B0Cc)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_3815B)
    bpy.utils.unregister_class(SNA_PT_PCG__EC878)
