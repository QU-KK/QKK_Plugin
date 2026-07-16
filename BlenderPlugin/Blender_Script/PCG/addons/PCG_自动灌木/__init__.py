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
    "name" : "PCG_Automatic shrubbery_v1",
    "author" : "渠奎奎", 
    "description" : "自动灌木",
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


class SNA_OT_Pcg__086Ae(bpy.types.Operator):
    bl_idname = "sna.pcg__086ae"
    bl_label = "PCG_灌木生成"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0']['Input_4'] = bpy.context.scene.sna_pcg_bush01
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0']['Input_2'] = bpy.context.scene.sna_pcg_bush02
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0']['Input_5'] = bpy.context.scene.sna_pcg_bush03
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0']['Input_6'] = bpy.context.scene.sna_pcg_bush04
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0']['Input_3'] = bpy.context.scene.sna_pcg_bush05
        bpy.ops.sna.my_generic_operator_fd6f0()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_A33Aa(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_a33aa"
    bl_label = "清空灌木改器"
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


class SNA_PT_PCG__238BE(bpy.types.Panel):
    bl_label = 'PCG_灌木'
    bl_idname = 'SNA_PT_PCG__238BE'
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
            col_8C528 = layout.column(heading='', align=True)
            col_8C528.alert = False
            col_8C528.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_8C528.active = True
            col_8C528.use_property_split = False
            col_8C528.use_property_decorate = False
            col_8C528.scale_x = 1.0
            col_8C528.scale_y = 1.0
            col_8C528.alignment = 'Expand'.upper()
            col_8C528.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals()):
                col_8C528.label(text='选中曲线：' + bpy.context.view_layer.objects.active.name, icon_value=236)
            else:
                col_8C528.label(text='非曲线：' + bpy.context.view_layer.objects.active.name, icon_value=3)
            col_8C528.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_程序化灌木v1.0'].node_group.name", globals(), locals()):
                col_C55D6 = col_8C528.column(heading='', align=True)
                col_C55D6.alert = False
                col_C55D6.enabled = True
                col_C55D6.active = True
                col_C55D6.use_property_split = False
                col_C55D6.use_property_decorate = False
                col_C55D6.scale_x = 1.0
                col_C55D6.scale_y = 1.0
                col_C55D6.alignment = 'Expand'.upper()
                col_C55D6.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_8D961 = col_C55D6.split(factor=0.5, align=True)
                split_8D961.alert = False
                split_8D961.enabled = True
                split_8D961.active = True
                split_8D961.use_property_split = False
                split_8D961.use_property_decorate = False
                split_8D961.scale_x = 1.0
                split_8D961.scale_y = 1.2000000476837158
                split_8D961.alignment = 'Expand'.upper()
                split_8D961.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = split_8D961.operator('sna.my_generic_operator_a33aa', text='清空', icon_value=33, emboss=True, depress=False)
                col_4355D = split_8D961.column(heading='', align=True)
                col_4355D.alert = False
                col_4355D.enabled = (len(bpy.context.view_layer.objects.selected.values()) == 1)
                col_4355D.active = True
                col_4355D.use_property_split = False
                col_4355D.use_property_decorate = False
                col_4355D.scale_x = 1.0
                col_4355D.scale_y = 1.0
                col_4355D.alignment = 'Expand'.upper()
                col_4355D.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_4355D.operator('sna.my_generic_operator_b5af4', text='应用', icon_value=36, emboss=True, depress=False)
                col_65D19 = col_C55D6.column(heading='', align=False)
                col_65D19.alert = False
                col_65D19.enabled = True
                col_65D19.active = True
                col_65D19.use_property_split = False
                col_65D19.use_property_decorate = False
                col_65D19.scale_x = 1.0
                col_65D19.scale_y = 1.0
                col_65D19.alignment = 'Expand'.upper()
                col_65D19.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                box_9887C = col_65D19.box()
                box_9887C.alert = False
                box_9887C.enabled = True
                box_9887C.active = True
                box_9887C.use_property_split = False
                box_9887C.use_property_decorate = False
                box_9887C.alignment = 'Expand'.upper()
                box_9887C.scale_x = 1.0
                box_9887C.scale_y = 1.0
                box_9887C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_0253C = box_9887C.column(heading='', align=False)
                col_0253C.alert = False
                col_0253C.enabled = True
                col_0253C.active = True
                col_0253C.use_property_split = False
                col_0253C.use_property_decorate = False
                col_0253C.scale_x = 1.0
                col_0253C.scale_y = 1.0
                col_0253C.alignment = 'Expand'.upper()
                col_0253C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_91D05 = col_0253C.column(heading='', align=False)
                col_91D05.alert = False
                col_91D05.enabled = True
                col_91D05.active = True
                col_91D05.use_property_split = False
                col_91D05.use_property_decorate = False
                col_91D05.scale_x = 1.0
                col_91D05.scale_y = 1.5
                col_91D05.alignment = 'Expand'.upper()
                col_91D05.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_91D05.operator('sna.pcg__086ae', text='一键配置', icon_value=4, emboss=True, depress=False)
                col_0253C.prop(bpy.context.scene, 'sna_pcg_bush01', text='内芯', icon_value=0, emboss=True)
                col_0253C.prop(bpy.context.scene, 'sna_pcg_bush02', text='侧面', icon_value=0, emboss=True)
                col_0253C.prop(bpy.context.scene, 'sna_pcg_bush03', text='顶部', icon_value=0, emboss=True)
                col_0253C.prop(bpy.context.scene, 'sna_pcg_bush04', text='零碎', icon_value=0, emboss=True)
                col_0253C.prop(bpy.context.scene, 'sna_pcg_bush05', text='砖块', icon_value=0, emboss=True)
                box_59446 = col_65D19.box()
                box_59446.alert = False
                box_59446.enabled = True
                box_59446.active = True
                box_59446.use_property_split = False
                box_59446.use_property_decorate = False
                box_59446.alignment = 'Expand'.upper()
                box_59446.scale_x = 1.0
                box_59446.scale_y = 1.0
                box_59446.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                box_59446.label(text='灌木参数：', icon_value=394)
                col_856F5 = box_59446.column(heading='', align=False)
                col_856F5.alert = False
                col_856F5.enabled = True
                col_856F5.active = True
                col_856F5.use_property_split = False
                col_856F5.use_property_decorate = False
                col_856F5.scale_x = 1.0
                col_856F5.scale_y = 1.0
                col_856F5.alignment = 'Expand'.upper()
                col_856F5.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_76C67 = '["' + str('Input_9' + '"]') 
                col_856F5.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0'], attr_76C67, text='侧面密度', icon_value=0, emboss=True)
                attr_726FA = '["' + str('Input_8' + '"]') 
                col_856F5.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0'], attr_726FA, text='顶部密度', icon_value=0, emboss=True)
                attr_B42C1 = '["' + str('Input_7' + '"]') 
                col_856F5.prop(bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0'], attr_B42C1, text='随机种子', icon_value=0, emboss=True)
            else:
                col_889EB = col_8C528.column(heading='', align=True)
                col_889EB.alert = False
                col_889EB.enabled = True
                col_889EB.active = True
                col_889EB.use_property_split = False
                col_889EB.use_property_decorate = False
                col_889EB.scale_x = 1.0
                col_889EB.scale_y = 2.0
                col_889EB.alignment = 'Expand'.upper()
                col_889EB.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_889EB.operator('sna.my_generic_operator_79aed', text='自动灌木', icon_value=4, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_Fd6F0(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_fd6f0"
    bl_label = "刷新灌木_修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0'].show_viewport = False
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0'].show_viewport = True
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_My_Generic_Operator_79Aed(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_79aed"
    bl_label = "灌木_修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_程序化灌木v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_程序化灌木v1.0'].node_group = bpy.data.node_groups['PCG_程序化灌木v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_程序化灌木v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_BUSH.blend')) + r'\NodeTree', filename='PCG_程序化灌木v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_69CD7 = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_B5Af4(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_b5af4"
    bl_label = "应用灌木_修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        node_tree_002['sna_pcg_modname'] = bpy.context.view_layer.objects.active.name
        collection_name_0_8c999 = sna_new_collection_5BD4A_8C999('PCG_' + node_tree_002['sna_pcg_modname'] + '_集合', False)
        collection_name_0_9ca90 = sna_new_collection_5BD4A_9CA90('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始', False)
        collection_name_0_84ff1 = sna_new_collection_5BD4A_84FF1('PCG_' + node_tree_002['sna_pcg_modname'] + '_灌木', False)
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_灌木'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_002['sna_pcg_modname'] + '_灌木'], )
        sna_fnmovetocollection_397D9_4785B('PCG_' + node_tree_002['sna_pcg_modname'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_2657D('PCG_' + node_tree_002['sna_pcg_modname'] + '_灌木')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_pattern(pattern=node_tree_002['sna_pcg_modname'])
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_pcg_bush01 = bpy.props.PointerProperty(name='PCG_bush01', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_bush02 = bpy.props.PointerProperty(name='PCG_bush02', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_bush03 = bpy.props.PointerProperty(name='PCG_bush03', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_bush04 = bpy.props.PointerProperty(name='PCG_bush04', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.types.Scene.sna_pcg_bush05 = bpy.props.PointerProperty(name='PCG_bush05', description='', options={'HIDDEN'}, type=bpy.types.Collection)
    bpy.utils.register_class(SNA_OT_Pcg__086Ae)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_A33Aa)
    bpy.utils.register_class(SNA_PT_PCG__238BE)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_Fd6F0)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_79Aed)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_B5Af4)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_pcg_bush05
    del bpy.types.Scene.sna_pcg_bush04
    del bpy.types.Scene.sna_pcg_bush03
    del bpy.types.Scene.sna_pcg_bush02
    del bpy.types.Scene.sna_pcg_bush01
    bpy.utils.unregister_class(SNA_OT_Pcg__086Ae)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_A33Aa)
    bpy.utils.unregister_class(SNA_PT_PCG__238BE)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_Fd6F0)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_79Aed)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_B5Af4)
