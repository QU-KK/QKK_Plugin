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
    "name" : "Axis_Comparison",
    "author" : "去奎奎", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews




def string_to_int(value):
    if value.isdigit():
        return int(value)
    return 0


def string_to_icon(value):
    if value in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[value].value
    return string_to_int(value)


addon_keymaps = {}
_icons = None
_item_map = dict()


def make_enum_item(_id, name, descr, preview_id, uid):
    lookup = str(_id)+"\0"+str(name)+"\0"+str(descr)+"\0"+str(preview_id)+"\0"+str(uid)
    if not lookup in _item_map:
        _item_map[lookup] = (_id, name, descr, preview_id, uid)
    return _item_map[lookup]


def sna_update_sna_project_a_a_94840(self, context):
    sna_updated_prop = self.sna_project_a_a
    bpy.ops.wm.save_userpref()


def sna_update_sna_project_b_b_692A6(self, context):
    sna_updated_prop = self.sna_project_b_b
    bpy.ops.wm.save_userpref()


def sna_update_sna_project_c_c_9CF6B(self, context):
    sna_updated_prop = self.sna_project_c_c
    bpy.ops.wm.save_userpref()


def sna_update_sna_project_d_d_69857(self, context):
    sna_updated_prop = self.sna_project_d_d
    bpy.ops.wm.save_userpref()


class SNA_PT_axis_comparison_67845(bpy.types.Panel):
    bl_label = '坐标轴对比'
    bl_idname = 'SNA_PT_axis_comparison_67845'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '坐标轴'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout.prop(bpy.context.scene, 'sna_switch_a', text='项目', icon_value=0, emboss=True)
        layout.prop(bpy.context.scene, 'sna_branch_a', text='', icon_value=0, emboss=True)
        if bpy.context.scene.sna_switch_a:
            box_923A3 = layout.box()
            box_923A3.alert = False
            box_923A3.enabled = True
            box_923A3.active = True
            box_923A3.use_property_split = False
            box_923A3.use_property_decorate = False
            box_923A3.alignment = 'Expand'.upper()
            box_923A3.scale_x = 1.0
            box_923A3.scale_y = 1.0
            if not True: box_923A3.operator_context = "EXEC_DEFAULT"
            col_59649 = box_923A3.column(heading='', align=False)
            col_59649.alert = False
            col_59649.enabled = True
            col_59649.active = True
            col_59649.use_property_split = False
            col_59649.use_property_decorate = False
            col_59649.scale_x = 1.0
            col_59649.scale_y = 1.0
            col_59649.alignment = 'Expand'.upper()
            col_59649.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_59649.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_project_a_a', text='', icon_value=0, emboss=True)
            col_59649.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_project_b_b', text='', icon_value=0, emboss=True)
            col_59649.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_project_c_c', text='', icon_value=0, emboss=True)
            col_59649.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_project_d_d', text='', icon_value=0, emboss=True)
        split_3F517 = layout.split(factor=0.8299999833106995, align=True)
        split_3F517.alert = False
        split_3F517.enabled = True
        split_3F517.active = True
        split_3F517.use_property_split = False
        split_3F517.use_property_decorate = False
        split_3F517.scale_x = 1.0
        split_3F517.scale_y = 1.5
        split_3F517.alignment = 'Expand'.upper()
        if not True: split_3F517.operator_context = "EXEC_DEFAULT"
        op = split_3F517.operator('sna.import_unity_d209f', text='轴心对比', icon_value=string_to_icon('ORIENTATION_LOCAL'), emboss=True, depress=False)
        op = split_3F517.operator('sna.delete_cache_b7cd7', text='', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)


class SNA_OT_Import_Unity_D209F(bpy.types.Operator):
    bl_idname = "sna.import_unity_d209f"
    bl_label = "Import_Unity"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        Project_Data = bpy.context.scene.sna_branch_a
        Print = None
        import os

        def New_Mat():
            Mat = bpy.context.blend_data.materials.get('轴心材质')
            if Mat == None:
                Mat = bpy.context.blend_data.materials.new(name='轴心材质')
                Data = Mat.node_tree.nodes["Principled BSDF"]
                Data.inputs[0].default_value = (1,0,0,1)
                Data.inputs[4].default_value = 0.5
                Mat.diffuse_color = (1,0,0,1)
                Mat.surface_render_method = 'BLENDED'
                Mat.use_transparency_overlap = False
            for i in bpy.context.active_object.material_slots:
                bpy.ops.object.material_slot_remove()
            bpy.ops.object.material_slot_add()
            bpy.context.active_object.material_slots[0].material = Mat
        # 项目路径
        #Project_Data = r'E:\v2d0\qukuikui_DM42.Beyond_Beyond_v2d0_project'
        # Mod名称
        Mod_Name_Data = bpy.context.active_object.name
        # 资产文件夹名称
        Folder_Name = Mod_Name_Data.replace('_lod0', '').replace('S_', '').replace('_1_', '+1_')
        Data = Folder_Name.split('_')
        Folder_Name = Folder_Name[:-len(Data[4])][:-1].capitalize()
        # 场景名称
        Scene_Name = Data[1].capitalize()
        # 资产类别
        Type_Name = Data[0].capitalize()
        # 路径拼接
        Project_Path = os.path.join(Project_Data,'Assets','Beyond','Arts','Environment','SceneAssets')
        # 资产最终路径
        Ass_Path = os.path.join(Project_Path,Scene_Name,Type_Name,Folder_Name,'Models',(Mod_Name_Data+'.fbx'))
        # 获取位置
        Location = bpy.context.active_object.location
        # 导入fbx
        if os.path.isfile(Ass_Path):
            bpy.ops.wm.fbx_import(filepath=Ass_Path, mtl_name_collision_mode='REFERENCE_EXISTING', use_anim=False)
            name = bpy.context.active_object.name[:-4]
            bpy.context.active_object.name = name + '_轴心对比'
            print(Ass_Name,'导入')
            print('路径:',Ass_Path)
            # 应用旋转缩放
            bpy.ops.object.transform_apply(rotation=True, scale=True)
            # 设置位置
            bpy.context.active_object.location = Location
            # 配置材质
            New_Mat()
            Print = '导入完成!  ' + Mod_Name_Data
        else:
            print('不存在:',Ass_Path)
            Print = '不存在!  ' + Mod_Name_Data
        self.report({'INFO'}, message=Print)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Delete_Cache_B7Cd7(bpy.types.Operator):
    bl_idname = "sna.delete_cache_b7cd7"
    bl_label = "Delete_Cache"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for obj in bpy.data.objects:
            if '_轴心对比' in obj.name:
                bpy.data.objects.remove(obj)
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        self.report({'INFO'}, message='清理完成！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_branch_a_enum_items(self, context):
    enum_items = [[bpy.context.preferences.addons[__package__].preferences.sna_project_a_a, bpy.context.preferences.addons[__package__].preferences.sna_project_a_a, '', 0], [bpy.context.preferences.addons[__package__].preferences.sna_project_b_b, bpy.context.preferences.addons[__package__].preferences.sna_project_b_b, '', 0], [bpy.context.preferences.addons[__package__].preferences.sna_project_c_c, bpy.context.preferences.addons[__package__].preferences.sna_project_c_c, '', 0], [bpy.context.preferences.addons[__package__].preferences.sna_project_d_d, bpy.context.preferences.addons[__package__].preferences.sna_project_d_d, '', 0]]
    return [make_enum_item(item[0], item[1], item[2], item[3], i) for i, item in enumerate(enum_items)]


class SNA_AddonPreferences_026DE(bpy.types.AddonPreferences):
    bl_idname = __package__
    sna_project_a_a: bpy.props.StringProperty(name='Project_A_A', description='', options={'HIDDEN'}, default='无', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_project_a_a_94840)
    sna_project_b_b: bpy.props.StringProperty(name='Project_B_B', description='', options={'HIDDEN'}, default='无', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_project_b_b_692A6)
    sna_project_c_c: bpy.props.StringProperty(name='Project_C_C', description='', options={'HIDDEN'}, default='无', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_project_c_c_9CF6B)
    sna_project_d_d: bpy.props.StringProperty(name='Project_D_D', description='', options={'HIDDEN'}, default='无', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_project_d_d_69857)

    def draw(self, context):
        if not (False):
            layout = self.layout 


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_branch_a = bpy.props.EnumProperty(name='Branch_A', description='', items=sna_branch_a_enum_items)
    bpy.types.Scene.sna_switch_a = bpy.props.BoolProperty(name='Switch_A', description='', default=False)
    bpy.utils.register_class(SNA_PT_axis_comparison_67845)
    bpy.utils.register_class(SNA_AddonPreferences_026DE)
    bpy.utils.register_class(SNA_OT_Import_Unity_D209F)
    bpy.utils.register_class(SNA_OT_Delete_Cache_B7Cd7)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_switch_a
    del bpy.types.Scene.sna_branch_a
    bpy.utils.unregister_class(SNA_PT_axis_comparison_67845)
    bpy.utils.unregister_class(SNA_AddonPreferences_026DE)
    bpy.utils.unregister_class(SNA_OT_Import_Unity_D209F)
    bpy.utils.unregister_class(SNA_OT_Delete_Cache_B7Cd7)
