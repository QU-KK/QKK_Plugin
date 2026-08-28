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
    "name" : "Import_Unity_FBX",
    "author" : "渠奎奎", 
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


addon_keymaps = {}
_icons = None


def sna_update_sna_project_a_AAF72(self, context):
    sna_updated_prop = self.sna_project_a
    bpy.ops.wm.save_userpref()


def sna_update_sna_project_b_CEFF9(self, context):
    sna_updated_prop = self.sna_project_b
    bpy.ops.wm.save_userpref()


def sna_update_sna_project_c_E356F(self, context):
    sna_updated_prop = self.sna_project_c
    bpy.ops.wm.save_userpref()


def sna_update_sna_project_d_C341A(self, context):
    sna_updated_prop = self.sna_project_d
    bpy.ops.wm.save_userpref()


class SNA_PT_UNITY_FBX_E5BE0(bpy.types.Panel):
    bl_label = '导入Unity_FBX'
    bl_idname = 'SNA_PT_UNITY_FBX_E5BE0'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = '导入'
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout.prop(bpy.context.scene, 'sna_switch_unity_fbx', text='项目', icon_value=0, emboss=True)
        if bpy.context.scene.sna_switch_unity_fbx:
            box_EF6DB = layout.box()
            box_EF6DB.alert = False
            box_EF6DB.enabled = True
            box_EF6DB.active = True
            box_EF6DB.use_property_split = False
            box_EF6DB.use_property_decorate = False
            box_EF6DB.alignment = 'Expand'.upper()
            box_EF6DB.scale_x = 1.0
            box_EF6DB.scale_y = 1.0
            if not True: box_EF6DB.operator_context = "EXEC_DEFAULT"
            col_52C3C = box_EF6DB.column(heading='', align=False)
            col_52C3C.alert = False
            col_52C3C.enabled = True
            col_52C3C.active = True
            col_52C3C.use_property_split = False
            col_52C3C.use_property_decorate = False
            col_52C3C.scale_x = 1.0
            col_52C3C.scale_y = 1.0
            col_52C3C.alignment = 'Expand'.upper()
            col_52C3C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            col_52C3C.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_project_a', text='', icon_value=0, emboss=True)
            col_52C3C.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_project_b', text='', icon_value=0, emboss=True)
            col_52C3C.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_project_c', text='', icon_value=0, emboss=True)
            col_52C3C.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_project_d', text='', icon_value=0, emboss=True)
        layout.prop(bpy.context.scene, 'sna_branch_unity_fbx', text='', icon_value=0, emboss=True)
        layout.prop(bpy.context.preferences.addons[__package__].preferences, 'sna_mod_name', text='', icon_value=0, emboss=True)
        split_F350F = layout.split(factor=0.5, align=True)
        split_F350F.alert = False
        split_F350F.enabled = True
        split_F350F.active = True
        split_F350F.use_property_split = False
        split_F350F.use_property_decorate = False
        split_F350F.scale_x = 1.0
        split_F350F.scale_y = 1.0
        split_F350F.alignment = 'Expand'.upper()
        if not True: split_F350F.operator_context = "EXEC_DEFAULT"
        col_3850C = split_F350F.column(heading='', align=False)
        col_3850C.alert = False
        col_3850C.enabled = True
        col_3850C.active = True
        col_3850C.use_property_split = False
        col_3850C.use_property_decorate = False
        col_3850C.scale_x = 1.0
        col_3850C.scale_y = 6.0
        col_3850C.alignment = 'Expand'.upper()
        col_3850C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_3850C.operator('sna.import_unity_fbx_d209f', text='导入', icon_value=0, emboss=True, depress=False)
        col_F17FE = split_F350F.column(heading='', align=True)
        col_F17FE.alert = False
        col_F17FE.enabled = True
        col_F17FE.active = True
        col_F17FE.use_property_split = False
        col_F17FE.use_property_decorate = False
        col_F17FE.scale_x = 1.0
        col_F17FE.scale_y = 1.0
        col_F17FE.alignment = 'Expand'.upper()
        col_F17FE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_F17FE.prop(bpy.context.scene, 'sna_suffix_unity_fbx', text=str(list(bpy.context.scene.sna_suffix_unity_fbx)), icon_value=0, emboss=True, expand=True)


class SNA_OT_Import_Unity_Fbx_D209F(bpy.types.Operator):
    bl_idname = "sna.import_unity_fbx_d209f"
    bl_label = "import_unity_fbx"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_9B484 in range(len(list(bpy.context.scene.sna_suffix_unity_fbx))):
            Mod_Name = bpy.context.preferences.addons[__package__].preferences.sna_mod_name
            Project = bpy.context.scene.sna_branch_unity_fbx
            Suffix = list(bpy.context.scene.sna_suffix_unity_fbx)[i_9B484]
            Print = None
            import os
            # 项目路径
            #Project = r'E:\v2d0\qukuikui_DM42.Beyond_Beyond_v2d0_project'
            # Mod名称
            #Mod_Name = 'S_prop_base02_signal+1_001_01'
            # 资产文件夹名称
            Folder_Name = Mod_Name.replace('S_', '').replace('P_', '').replace('_1_', '+1_').replace('_lod0', '').replace('_lod1', '').replace('_lod2', '').replace('_lod3', '')
            Ass_Name = 'S_'+Folder_Name+Suffix+'.fbx'
            Data = Folder_Name.split('_')
            Folder_Name = Folder_Name[:-len(Data[4])][:-1].capitalize()
            # 场景名称
            Scene_Name = Data[1].capitalize()
            # 资产类别
            Type_Name = Data[0].capitalize()
            # 路径拼接
            Project_Path = os.path.join(Project,'Assets','Beyond','Arts','Environment','SceneAssets')
            # 资产最终路径
            Ass_Path = os.path.join(Project_Path,Scene_Name,Type_Name,Folder_Name,'Models',Ass_Name)
            if os.path.isfile(Ass_Path):
                bpy.ops.wm.fbx_import(filepath=Ass_Path, mtl_name_collision_mode='REFERENCE_EXISTING', use_anim=False)
                print(Ass_Name,'导入')
                print('路径:',Ass_Path)
                # 应用旋转缩放
                bpy.ops.object.transform_apply(rotation=True, scale=True)
                Print = '导入完成!  ' + Ass_Name
            else:
                print('不存在:',Ass_Path)
                Print = '不存在!  ' + Ass_Name
            self.report({'INFO'}, message=Print)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_branch_unity_fbx_enum_items(self, context):
    return [("No Items", "No Items", "No generate enum items node found to create items!", "ERROR", 0)]


class SNA_AddonPreferences_026DE(bpy.types.AddonPreferences):
    bl_idname = __package__
    sna_project_a: bpy.props.StringProperty(name='Project_A', description='', options={'HIDDEN'}, default='无', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_project_a_AAF72)
    sna_project_b: bpy.props.StringProperty(name='Project_B', description='', options={'HIDDEN'}, default='无', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_project_b_CEFF9)
    sna_project_c: bpy.props.StringProperty(name='Project_C', description='', options={'HIDDEN'}, default='无', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_project_c_E356F)
    sna_project_d: bpy.props.StringProperty(name='Project_D', description='', options={'HIDDEN'}, default='无', subtype='DIR_PATH', maxlen=0, update=sna_update_sna_project_d_C341A)
    sna_mod_name: bpy.props.StringProperty(name='Mod_Name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    def draw(self, context):
        if not (False):
            layout = self.layout 


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_suffix_unity_fbx = bpy.props.EnumProperty(name='Suffix_Unity_Fbx', description='', items=[('_lod0', '_lod0', '', 0, 1), ('_lod1', '_lod1', '', 0, 2), ('_lod2', '_lod2', '', 0, 4), ('_lod3', '_lod3', '', 0, 8), ('_COL1_UM01', '_COL1_UM01', '', 0, 16), ('_shadowProxy', '_shadowProxy', '', 0, 32)], options={'ENUM_FLAG'})
    bpy.types.Scene.sna_branch_unity_fbx = bpy.props.EnumProperty(name='Branch_Unity_Fbx', description='', items=sna_branch_unity_fbx_enum_items)
    bpy.types.Scene.sna_switch_unity_fbx = bpy.props.BoolProperty(name='Switch_Unity_Fbx', description='', default=False)
    bpy.utils.register_class(SNA_PT_UNITY_FBX_E5BE0)
    bpy.utils.register_class(SNA_AddonPreferences_026DE)
    bpy.utils.register_class(SNA_OT_Import_Unity_Fbx_D209F)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_switch_unity_fbx
    del bpy.types.Scene.sna_branch_unity_fbx
    del bpy.types.Scene.sna_suffix_unity_fbx
    bpy.utils.unregister_class(SNA_PT_UNITY_FBX_E5BE0)
    bpy.utils.unregister_class(SNA_AddonPreferences_026DE)
    bpy.utils.unregister_class(SNA_OT_Import_Unity_Fbx_D209F)
