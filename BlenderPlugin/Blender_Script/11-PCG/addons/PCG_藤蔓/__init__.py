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
    "name" : "PCG_Automati Vines_v1",
    "author" : "渠奎奎", 
    "description" : "自动藤蔓",
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


class SNA_OT_My_Generic_Operator_429Ef(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_429ef"
    bl_label = "一键配置藤蔓修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0']['Input_213'] = bpy.context.scene.sna_pcg_vine_vegetation
        bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0']['Input_2'] = bpy.context.scene.sna_pcg_vine_collision
        bpy.ops.sna.my_generic_operator_1577a()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_PCG__DEE85(bpy.types.Panel):
    bl_label = 'PCG_自动藤蔓'
    bl_idname = 'SNA_PT_PCG__DEE85'
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
            col_90009 = layout.column(heading='', align=True)
            col_90009.alert = False
            col_90009.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_90009.active = True
            col_90009.use_property_split = False
            col_90009.use_property_decorate = False
            col_90009.scale_x = 1.0
            col_90009.scale_y = 1.0
            col_90009.alignment = 'Expand'.upper()
            col_90009.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals()):
                col_90009.label(text='选中曲线：' + bpy.context.view_layer.objects.active.name, icon_value=236)
            else:
                col_90009.label(text='非曲线：' + bpy.context.view_layer.objects.active.name, icon_value=3)
            col_90009.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_自动藤蔓_v1.0'].node_group.name", globals(), locals()):
                col_2FF35 = col_90009.column(heading='', align=True)
                col_2FF35.alert = False
                col_2FF35.enabled = True
                col_2FF35.active = True
                col_2FF35.use_property_split = False
                col_2FF35.use_property_decorate = False
                col_2FF35.scale_x = 1.0
                col_2FF35.scale_y = 1.0
                col_2FF35.alignment = 'Expand'.upper()
                col_2FF35.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_5EE76 = col_2FF35.split(factor=0.5, align=True)
                split_5EE76.alert = False
                split_5EE76.enabled = True
                split_5EE76.active = True
                split_5EE76.use_property_split = False
                split_5EE76.use_property_decorate = False
                split_5EE76.scale_x = 1.0
                split_5EE76.scale_y = 1.2000000476837158
                split_5EE76.alignment = 'Expand'.upper()
                split_5EE76.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = split_5EE76.operator('sna.my_generic_operator_e10b2', text='清空', icon_value=33, emboss=True, depress=False)
                col_20C69 = split_5EE76.column(heading='', align=True)
                col_20C69.alert = False
                col_20C69.enabled = (len(bpy.context.view_layer.objects.selected.values()) == 1)
                col_20C69.active = True
                col_20C69.use_property_split = False
                col_20C69.use_property_decorate = False
                col_20C69.scale_x = 1.0
                col_20C69.scale_y = 1.0
                col_20C69.alignment = 'Expand'.upper()
                col_20C69.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_20C69.operator('sna.my_generic_operator_a4df6', text='应用', icon_value=36, emboss=True, depress=False)
                col_31409 = col_2FF35.column(heading='', align=False)
                col_31409.alert = False
                col_31409.enabled = True
                col_31409.active = True
                col_31409.use_property_split = False
                col_31409.use_property_decorate = False
                col_31409.scale_x = 1.0
                col_31409.scale_y = 1.0
                col_31409.alignment = 'Expand'.upper()
                col_31409.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                box_819D2 = col_31409.box()
                box_819D2.alert = False
                box_819D2.enabled = True
                box_819D2.active = True
                box_819D2.use_property_split = False
                box_819D2.use_property_decorate = False
                box_819D2.alignment = 'Expand'.upper()
                box_819D2.scale_x = 1.0
                box_819D2.scale_y = 1.0
                box_819D2.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_B32E4 = box_819D2.column(heading='', align=False)
                col_B32E4.alert = False
                col_B32E4.enabled = True
                col_B32E4.active = True
                col_B32E4.use_property_split = False
                col_B32E4.use_property_decorate = False
                col_B32E4.scale_x = 1.0
                col_B32E4.scale_y = 1.0
                col_B32E4.alignment = 'Expand'.upper()
                col_B32E4.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_9E9F0 = col_B32E4.column(heading='', align=False)
                col_9E9F0.alert = False
                col_9E9F0.enabled = True
                col_9E9F0.active = True
                col_9E9F0.use_property_split = False
                col_9E9F0.use_property_decorate = False
                col_9E9F0.scale_x = 1.0
                col_9E9F0.scale_y = 1.5
                col_9E9F0.alignment = 'Expand'.upper()
                col_9E9F0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_9E9F0.operator('sna.my_generic_operator_429ef', text='一键配置', icon_value=0, emboss=True, depress=False)
                col_B32E4.prop(bpy.context.scene, 'sna_pcg_vine_vegetation', text='植被', icon_value=0, emboss=True)
                col_B32E4.prop(bpy.context.scene, 'sna_pcg_vine_collision', text='目标', icon_value=0, emboss=True)
                box_AE4EB = col_31409.box()
                box_AE4EB.alert = False
                box_AE4EB.enabled = True
                box_AE4EB.active = True
                box_AE4EB.use_property_split = False
                box_AE4EB.use_property_decorate = False
                box_AE4EB.alignment = 'Expand'.upper()
                box_AE4EB.scale_x = 1.0
                box_AE4EB.scale_y = 1.0
                box_AE4EB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_365B0 = box_AE4EB.column(heading='', align=False)
                col_365B0.alert = False
                col_365B0.enabled = True
                col_365B0.active = True
                col_365B0.use_property_split = False
                col_365B0.use_property_decorate = False
                col_365B0.scale_x = 1.0
                col_365B0.scale_y = 1.0
                col_365B0.alignment = 'Expand'.upper()
                col_365B0.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_365B0.label(text='植被：', icon_value=488)
                attr_A325A = '["' + str('Input_105' + '"]') 
                col_365B0.prop(bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0'], attr_A325A, text='随机', icon_value=0, emboss=True)
                attr_570CE = '["' + str('Input_108' + '"]') 
                col_365B0.prop(bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0'], attr_570CE, text='密度', icon_value=0, emboss=True)
                attr_AB411 = '["' + str('Input_109' + '"]') 
                col_365B0.prop(bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0'], attr_AB411, text='扩散', icon_value=0, emboss=True)
                attr_29431 = '["' + str('Input_214' + '"]') 
                col_365B0.prop(bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0'], attr_29431, text='偏移', icon_value=0, emboss=True)
                attr_D3770 = '["' + str('Input_215' + '"]') 
                col_365B0.prop(bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0'], attr_D3770, text='缩放', icon_value=0, emboss=True)
            else:
                col_AB289 = col_90009.column(heading='', align=True)
                col_AB289.alert = False
                col_AB289.enabled = True
                col_AB289.active = True
                col_AB289.use_property_split = False
                col_AB289.use_property_decorate = False
                col_AB289.scale_x = 1.0
                col_AB289.scale_y = 2.0
                col_AB289.alignment = 'Expand'.upper()
                col_AB289.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_AB289.operator('sna.my_generic_operator_a63dd', text='自动藤蔓', icon_value=4, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_E10B2(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_e10b2"
    bl_label = "清空藤蔓修改器"
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


class SNA_OT_My_Generic_Operator_1577A(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_1577a"
    bl_label = "刷新藤蔓修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0'].show_viewport = False
        bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_A63Dd(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a63dd"
    bl_label = "加载水桥修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_自动藤蔓_v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_自动藤蔓_v1.0'].node_group = bpy.data.node_groups['PCG_自动藤蔓_v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_自动藤蔓_v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_VINE.blend')) + r'\NodeTree', filename='PCG_自动藤蔓_v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_69CD7 = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_A4Df6(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a4df6"
    bl_label = "应用藤蔓修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        node_tree_002['sna_pcg_modname'] = bpy.context.view_layer.objects.active.name
        collection_name_0_8c999 = sna_new_collection_5BD4A_8C999('PCG_' + node_tree_002['sna_pcg_modname'] + '_集合', False)
        collection_name_0_9ca90 = sna_new_collection_5BD4A_9CA90('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始', False)
        collection_name_0_84ff1 = sna_new_collection_5BD4A_84FF1('PCG_' + node_tree_002['sna_pcg_modname'] + '_藤蔓', False)
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_藤蔓'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_藤蔓'], )
        sna_fnmovetocollection_397D9_4785B('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_2657D('PCG_' + node_tree_002['sna_pcg_modname'] + '_藤蔓')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_pattern(pattern=node_tree_002['sna_pcg_modname'])
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_vine_collision = bpy.props.PointerProperty(name='PCG_Vine Collision', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_vine_vegetation = bpy.props.PointerProperty(name='PCG_Vine Vegetation', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_429Ef)
    bpy.utils.register_class(SNA_PT_PCG__DEE85)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_E10B2)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_1577A)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A63Dd)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A4Df6)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_vine_vegetation
    del bpy.types.Scene.sna_pcg_vine_collision
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_429Ef)
    bpy.utils.unregister_class(SNA_PT_PCG__DEE85)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_E10B2)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_1577A)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A63Dd)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A4Df6)
