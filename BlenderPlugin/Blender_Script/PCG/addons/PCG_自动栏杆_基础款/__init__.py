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
    "name" : "PCG_Automatic Railing Base_v1",
    "author" : "渠奎奎", 
    "description" : "自动栏杆基础款",
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


class SNA_OT_My_Generic_Operator_7D2A3(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_7d2a3"
    bl_label = "清空栏杆改器"
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


class SNA_PT_PCG___9E8A2(bpy.types.Panel):
    bl_label = 'PCG_栏杆_基础款'
    bl_idname = 'SNA_PT_PCG___9E8A2'
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
            col_7EFDF = layout.column(heading='', align=True)
            col_7EFDF.alert = False
            col_7EFDF.enabled = property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals())
            col_7EFDF.active = True
            col_7EFDF.use_property_split = False
            col_7EFDF.use_property_decorate = False
            col_7EFDF.scale_x = 1.0
            col_7EFDF.scale_y = 1.0
            col_7EFDF.alignment = 'Expand'.upper()
            col_7EFDF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if property_exists("bpy.context.view_layer.objects.active.data.splines", globals(), locals()):
                col_7EFDF.label(text='选中曲线：' + bpy.context.view_layer.objects.active.name, icon_value=236)
            else:
                col_7EFDF.label(text='非曲线：' + bpy.context.view_layer.objects.active.name, icon_value=3)
            col_7EFDF.separator(factor=2.0)
            if property_exists("bpy.context.object.modifiers['PCG_自动栏杆基础_v1.0'].node_group.name", globals(), locals()):
                col_0012F = col_7EFDF.column(heading='', align=True)
                col_0012F.alert = False
                col_0012F.enabled = True
                col_0012F.active = True
                col_0012F.use_property_split = False
                col_0012F.use_property_decorate = False
                col_0012F.scale_x = 1.0
                col_0012F.scale_y = 1.0
                col_0012F.alignment = 'Expand'.upper()
                col_0012F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                split_FB895 = col_0012F.split(factor=0.5, align=True)
                split_FB895.alert = False
                split_FB895.enabled = True
                split_FB895.active = True
                split_FB895.use_property_split = False
                split_FB895.use_property_decorate = False
                split_FB895.scale_x = 1.0
                split_FB895.scale_y = 1.2000000476837158
                split_FB895.alignment = 'Expand'.upper()
                split_FB895.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = split_FB895.operator('sna.my_generic_operator_7d2a3', text='清空', icon_value=33, emboss=True, depress=False)
                col_5EB65 = split_FB895.column(heading='', align=True)
                col_5EB65.alert = False
                col_5EB65.enabled = (len(bpy.context.view_layer.objects.selected.values()) == 1)
                col_5EB65.active = True
                col_5EB65.use_property_split = False
                col_5EB65.use_property_decorate = False
                col_5EB65.scale_x = 1.0
                col_5EB65.scale_y = 1.0
                col_5EB65.alignment = 'Expand'.upper()
                col_5EB65.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_5EB65.operator('sna.my_generic_operator_66bbd', text='应用', icon_value=36, emboss=True, depress=False)
                box_3EC14 = col_0012F.box()
                box_3EC14.alert = False
                box_3EC14.enabled = True
                box_3EC14.active = True
                box_3EC14.use_property_split = False
                box_3EC14.use_property_decorate = False
                box_3EC14.alignment = 'Expand'.upper()
                box_3EC14.scale_x = 1.0
                box_3EC14.scale_y = 1.0
                box_3EC14.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_37A99 = box_3EC14.column(heading='', align=False)
                col_37A99.alert = False
                col_37A99.enabled = True
                col_37A99.active = True
                col_37A99.use_property_split = False
                col_37A99.use_property_decorate = False
                col_37A99.scale_x = 1.0
                col_37A99.scale_y = 1.2000000476837158
                col_37A99.alignment = 'Expand'.upper()
                col_37A99.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                attr_DDFBB = '["' + str('Input_2' + '"]') 
                col_37A99.prop(bpy.context.view_layer.objects.active.modifiers['PCG_自动栏杆基础_v1.0'], attr_DDFBB, text='栏杆', icon_value=0, emboss=True)
                attr_0B7D4 = '["' + str('Input_3' + '"]') 
                col_37A99.prop(bpy.context.view_layer.objects.active.modifiers['PCG_自动栏杆基础_v1.0'], attr_0B7D4, text='缩放', icon_value=0, emboss=True)
            else:
                col_4FBBA = col_7EFDF.column(heading='', align=True)
                col_4FBBA.alert = False
                col_4FBBA.enabled = True
                col_4FBBA.active = True
                col_4FBBA.use_property_split = False
                col_4FBBA.use_property_decorate = False
                col_4FBBA.scale_x = 1.0
                col_4FBBA.scale_y = 2.0
                col_4FBBA.alignment = 'Expand'.upper()
                col_4FBBA.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_4FBBA.operator('sna.my_generic_operator_7cbfa', text='自动栏杆', icon_value=4, emboss=True, depress=False)


class SNA_OT_My_Generic_Operator_7Cbfa(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_7cbfa"
    bl_label = "自动栏杆基础_修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        bpy.context.view_layer.objects.active.modifiers.clear()
        bpy.ops.object.modifier_add(type='NODES')
        bpy.context.view_layer.objects.active.modifiers[0].name = 'PCG_自动栏杆基础_v1.0'
        bpy.context.view_layer.objects.active.modifiers['PCG_自动栏杆基础_v1.0'].node_group = bpy.data.node_groups['PCG_自动栏杆基础_v1.0']
        return {"FINISHED"}

    def invoke(self, context, event):
        if property_exists("bpy.data.node_groups['PCG_自动栏杆基础_v1.0']", globals(), locals()):
            pass
        else:
            before_data = list(bpy.data.node_groups)
            bpy.ops.wm.append(directory=bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'PCG_GN_RAILING_01.blend')) + r'\NodeTree', filename='PCG_自动栏杆基础_v1.0', link=False)
            new_data = list(filter(lambda d: not d in before_data, list(bpy.data.node_groups)))
            appended_69CD7 = None if not new_data else new_data[0]
        return self.execute(context)


class SNA_OT_My_Generic_Operator_66Bbd(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_66bbd"
    bl_label = "应用栏杆基础_修改器"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not False

    def execute(self, context):
        node_tree_001['sna_pcg_modname'] = bpy.context.view_layer.objects.active.name
        collection_name_0_8c999 = sna_new_collection_5BD4A_8C999('PCG_' + node_tree_001['sna_pcg_modname'] + '_集合', False)
        collection_name_0_9ca90 = sna_new_collection_5BD4A_9CA90('PCG_' + node_tree_001['sna_pcg_modname'] + '_原始', False)
        collection_name_0_84ff1 = sna_new_collection_5BD4A_84FF1('PCG_' + node_tree_001['sna_pcg_modname'] + '_栏杆基础', False)
        bpy.context.blend_data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_原始'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_原始'], )
        bpy.context.blend_data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_集合'].children.link(child=bpy.data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_栏杆基础'], )
        bpy.context.scene.collection.children.unlink(child=bpy.data.collections['PCG_' + node_tree_001['sna_pcg_modname'] + '_栏杆基础'], )
        sna_fnmovetocollection_397D9_4785B('PCG_' + node_tree_001['sna_pcg_modname'] + '_原始')
        bpy.ops.object.duplicates_make_real()
        sna_fnmovetocollection_397D9_2657D('PCG_' + node_tree_001['sna_pcg_modname'] + '_栏杆基础')
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_7D2A3)
    bpy.utils.register_class(SNA_PT_PCG___9E8A2)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_7Cbfa)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_66Bbd)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_7D2A3)
    bpy.utils.unregister_class(SNA_PT_PCG___9E8A2)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_7Cbfa)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_66Bbd)
