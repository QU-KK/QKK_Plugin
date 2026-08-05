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
    "name" : "Blender_Max_Maya_v1",
    "author" : "渠奎奎", 
    "description" : "blender  max  maya模型互导",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}


import bpy
import bpy.utils.previews
import os
import time
import atexit




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
node_tree = {'sna_old_mat_name': '', 'sna_new_mat_name': '', }
node_tree_002 = {'sna_mat': [], }
class SNA_PT_V10_BATE_F3595(bpy.types.Panel):
    bl_label = '导入导出 (V1.0_Bate)'
    bl_idname = 'SNA_PT_V10_BATE_F3595'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_context = ''
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
        row_0B863 = layout.row(heading='', align=True)
        row_0B863.alert = False
        row_0B863.enabled = True
        row_0B863.active = True
        row_0B863.use_property_split = False
        row_0B863.use_property_decorate = False
        row_0B863.scale_x = 1.0
        row_0B863.scale_y = 1.2000000476837158
        row_0B863.alignment = 'Expand'.upper()
        row_0B863.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_0B863.prop(bpy.context.scene, 'sna_bridge_port_switch', text='模式', icon_value=0, emboss=True)
        layout.separator(factor=0.0)
        box_82210 = layout.box()
        box_82210.alert = False
        box_82210.enabled = True
        box_82210.active = True
        box_82210.use_property_split = False
        box_82210.use_property_decorate = False
        box_82210.alignment = 'Expand'.upper()
        box_82210.scale_x = 1.0
        box_82210.scale_y = 1.0
        if not True: box_82210.operator_context = "EXEC_DEFAULT"
        if (bpy.context.scene.sna_bridge_port_switch == '插件'):
            layout_function = box_82210
            sna_maya_max_interface_21FDB(layout_function, )
        else:
            col_553AC = box_82210.column(heading='', align=True)
            col_553AC.alert = False
            col_553AC.enabled = True
            col_553AC.active = True
            col_553AC.use_property_split = False
            col_553AC.use_property_decorate = False
            col_553AC.scale_x = 1.0
            col_553AC.scale_y = 1.0
            col_553AC.alignment = 'Expand'.upper()
            col_553AC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            if (bpy.context.scene.sna_bridge_port_switch == 'FBX '):
                layout_function = col_553AC
                sna_output_fbx_interface_3CED5(layout_function, )
            if (bpy.context.scene.sna_bridge_port_switch == 'Maya '):
                layout_function = col_553AC
                sna_blender_to_maya_EA518(layout_function, )
            if (bpy.context.scene.sna_bridge_port_switch == 'Max '):
                layout_function = col_553AC
                sna_blender_to_max_1C16F(layout_function, )
            if (bpy.context.scene.sna_bridge_port_switch != 'FBX '):
                col_8F7EC = col_553AC.column(heading='', align=False)
                col_8F7EC.alert = False
                col_8F7EC.enabled = True
                col_8F7EC.active = True
                col_8F7EC.use_property_split = False
                col_8F7EC.use_property_decorate = False
                col_8F7EC.scale_x = 1.0
                col_8F7EC.scale_y = 1.0
                col_8F7EC.alignment = 'Expand'.upper()
                col_8F7EC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                col_8F7EC.separator(factor=1.0)
                box_5FC45 = col_8F7EC.box()
                box_5FC45.alert = False
                box_5FC45.enabled = True
                box_5FC45.active = True
                box_5FC45.use_property_split = False
                box_5FC45.use_property_decorate = False
                box_5FC45.alignment = 'Expand'.upper()
                box_5FC45.scale_x = 1.0
                box_5FC45.scale_y = 1.0
                if not True: box_5FC45.operator_context = "EXEC_DEFAULT"
                col_99BEC = box_5FC45.column(heading='', align=True)
                col_99BEC.alert = False
                col_99BEC.enabled = True
                col_99BEC.active = True
                col_99BEC.use_property_split = False
                col_99BEC.use_property_decorate = False
                col_99BEC.scale_x = 1.0
                col_99BEC.scale_y = 1.0
                col_99BEC.alignment = 'Expand'.upper()
                col_99BEC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                layout_function = col_99BEC
                sna_clean_normal_interface_8DF6C(layout_function, )
                layout_function = col_99BEC
                sna_img__B5485(layout_function, )


def sna_add_to_topbar_mt_editor_menus_DE27C(self, context):
    if not (False):
        layout = self.layout
        layout.popover('SNA_PT_V10_BATE_F3595', text='互导', icon_value=string_to_icon('IMPORT'))


class SNA_OT_Blender_Output_Max_D67C7(bpy.types.Operator):
    bl_idname = "sna.blender_output_max_d67c7"
    bl_label = "blender_output_max"
    bl_description = "导出至Max"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        sna_mat_switch_92BBA(bpy.context.scene.sna_bridge_img_output_switch)
        filepath_Blender_To_Max = bpy.path.abspath(os.path.join(r'C:\Blender_Cache\BlenderToMax','Qkk_BlenderToMax.FBX'))
        bpy.ops.export_scene.fbx(
        #输出路径
        filepath = filepath_Blender_To_Max,
        #包括
        use_selection=True,#选定物体
        use_visible=False,#可见物体
        use_active_collection=False,#活动集合
        #collection='',#集合名称
        object_types={'MESH'},#导出类型
        use_custom_props=True,#自定义属性
        #变换
        global_scale=1,#缩放
        apply_scale_options='FBX_SCALE_NONE',#应用缩放
        axis_forward='Y',
        axis_up='Z',
        apply_unit_scale=True,#应用单位
        use_space_transform=True,#使用空间变换
        bake_space_transform=False,#应用变换
        #几何数据
        mesh_smooth_type='EDGE',#平滑类型
        use_subsurf=False,#导出表面细分
        use_mesh_modifiers=False,#应用修改器
        use_mesh_modifiers_render=False,#应用修改器（渲染）
        use_mesh_edges=False,#松散边
        use_triangles=False,#三角化
        use_tspace=False,#切向空间
        colors_type='SRGB',#顶点色类型
        prioritize_active_color=False,#活动颜色优先
        #骨架
        primary_bone_axis='Y',#主骨骼轴向
        secondary_bone_axis='X',#次骨骼轴向
        armature_nodetype='NULL',#骨架FBXNode类型
        add_leaf_bones=False,#仅形变骨骼
        use_armature_deform_only=False,#添加叶骨
        #动画
        bake_anim=False,
        bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=False,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=1.0,
        #其他
        check_existing=False,#检查是否存在
        filter_glob='',#过滤
        path_mode='AUTO',#路径模式
        embed_textures=False,#内嵌纹理
        batch_mode='OFF',#批量模式
        use_batch_own_dir=False,#批处理路径
        use_metadata=False,#使用元数据
        )
        sna_mat_switch_92BBA(True)
        self.report({'INFO'}, message='导出完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_blender_to_max_1C16F(layout_function, ):
    split_87CC3 = layout_function.split(factor=0.5, align=True)
    split_87CC3.alert = False
    split_87CC3.enabled = True
    split_87CC3.active = True
    split_87CC3.use_property_split = False
    split_87CC3.use_property_decorate = False
    split_87CC3.scale_x = 1.0
    split_87CC3.scale_y = 1.5
    split_87CC3.alignment = 'Expand'.upper()
    if not True: split_87CC3.operator_context = "EXEC_DEFAULT"
    op = split_87CC3.operator('sna.max_input_blender_21992', text='导入', icon_value=string_to_icon('IMPORT'), emboss=True, depress=False)
    op = split_87CC3.operator('sna.blender_output_max_d67c7', text='导出', icon_value=string_to_icon('EXPORT'), emboss=True, depress=False)


class SNA_OT_Max_Input_Blender_21992(bpy.types.Operator):
    bl_idname = "sna.max_input_blender_21992"
    bl_label = "max_input_blender"
    bl_description = "导入至Blender"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        filepath_Max_To_Blender = bpy.path.abspath(os.path.join(r'C:\Blender_Cache\BlenderToMax','Qkk_MaxToBlender.FBX'))
        bpy.ops.wm.fbx_import(
        # 常规
        filepath=filepath_Max_To_Blender,#路径
        global_scale=1.0, #缩放
        use_custom_props=True, #自定义属性
        use_custom_props_enum_as_string=True, #导入枚举为字符串
        # 几何数据
        use_custom_normals=True, #自定义法向
        import_subdivision=False, #细分曲面
        import_colors='SRGB', #顶点色
        validate_meshes=True, #检查网格
        # 材质引用
        mtl_name_collision_mode='REFERENCE_EXISTING',#引用同名材质
        # 动画
        use_anim=False, #动画
        anim_offset=0.0, #动画偏移
        #骨骼
        ignore_leaf_bones=False, #忽略叶骨骼
        # 5.0弃用
        #use_image_search=True, #图像查找
        #比啊变换
        #decal_offset=0.0, #贴花偏移
        #bake_space_transform=True, #应用变换
        #use_prepost_rot=True,#预旋转
        #轴向
        #use_manual_orientation=True, #手动朝向
        #axis_forward='Y', #向前
        #axis_up='Z', #向上
        )

        def delayed_D7226():
            sna_clean_normal_execute_90228()
        bpy.app.timers.register(delayed_D7226, first_interval=0.10000000149011612)
        time.sleep(0.10000000149011612)
        self.report({'INFO'}, message='导入完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_blender_to_maya_EA518(layout_function, ):
    split_040D0 = layout_function.split(factor=0.5, align=True)
    split_040D0.alert = False
    split_040D0.enabled = True
    split_040D0.active = True
    split_040D0.use_property_split = False
    split_040D0.use_property_decorate = False
    split_040D0.scale_x = 1.0
    split_040D0.scale_y = 1.5
    split_040D0.alignment = 'Expand'.upper()
    if not True: split_040D0.operator_context = "EXEC_DEFAULT"
    op = split_040D0.operator('sna.maya_input_blender_192ad', text='导入', icon_value=string_to_icon('IMPORT'), emboss=True, depress=False)
    op = split_040D0.operator('sna.blender_output_maya_74c9a', text='导出', icon_value=string_to_icon('EXPORT'), emboss=True, depress=False)


class SNA_OT_Blender_Output_Maya_74C9A(bpy.types.Operator):
    bl_idname = "sna.blender_output_maya_74c9a"
    bl_label = "blender_output_maya"
    bl_description = "导出至Maya"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        sna_mat_switch_92BBA(bpy.context.scene.sna_bridge_img_output_switch)
        bpy.ops.export_scene.fbx(filepath=bpy.path.abspath(os.path.join(r'C:\Blender_Cache\BlenderToMaya','Qkk_BlenderToMaya.FBX')), use_selection=True, global_scale=1.0, apply_unit_scale=False, apply_scale_options='FBX_SCALE_NONE', use_space_transform=True, bake_space_transform=True, object_types={'MESH'}, use_mesh_modifiers=True, mesh_smooth_type='EDGE', colors_type='SRGB', use_triangles=False, use_custom_props=True, add_leaf_bones=False, bake_anim=False, path_mode='AUTO', embed_textures=False, batch_mode='OFF', use_metadata=False, axis_forward='Y', axis_up='Z')
        sna_mat_switch_92BBA(True)
        self.report({'INFO'}, message='导出完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Maya_Input_Blender_192Ad(bpy.types.Operator):
    bl_idname = "sna.maya_input_blender_192ad"
    bl_label = "maya_input_blender"
    bl_description = "导入至Blender"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.import_scene.fbx(filepath=bpy.path.abspath(os.path.join(r'C:\Blender_Cache\BlenderToMaya','Qkk_MayaToBlender.FBX')), use_manual_orientation=True, global_scale=1.0, bake_space_transform=True, use_custom_normals=True, colors_type='SRGB', decal_offset=0.0, use_anim=False, use_subsurf=False, use_custom_props=True, use_custom_props_enum_as_string=True, ignore_leaf_bones=False, use_prepost_rot=True, axis_forward='Y', axis_up='Z')

        def delayed_F759C():
            sna_clean_normal_execute_90228()
            sna_reuse_material_execute_3069B()
        bpy.app.timers.register(delayed_F759C, first_interval=0.10000000149011612)
        time.sleep(0.10000000149011612)
        self.report({'INFO'}, message='导入完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_maya_max_interface_21FDB(layout_function, ):
    layout_function.label(text='Maya_Max 接口端', icon_value=string_to_icon('FILE_SCRIPT'))
    col_DAA0A = layout_function.column(heading='', align=True)
    col_DAA0A.alert = False
    col_DAA0A.enabled = True
    col_DAA0A.active = True
    col_DAA0A.use_property_split = False
    col_DAA0A.use_property_decorate = False
    col_DAA0A.scale_x = 1.0
    col_DAA0A.scale_y = 1.5
    col_DAA0A.alignment = 'Expand'.upper()
    col_DAA0A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_DAA0A.operator('sna.open_plugin_043a6', text='打开插件目录', icon_value=0, emboss=True, depress=False)


class SNA_OT_Open_Plugin_043A6(bpy.types.Operator):
    bl_idname = "sna.open_plugin_043a6"
    bl_label = "open_plug-in"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        plugin_path = bpy.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'plug-in'))
        # 尝试打开目录
        os.startfile(plugin_path)
        self.report({'INFO'}, message='打开目录完毕！')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_output_fbx_interface_3CED5(layout_function, ):
    split_9B58A = layout_function.split(factor=0.5, align=True)
    split_9B58A.alert = False
    split_9B58A.enabled = True
    split_9B58A.active = True
    split_9B58A.use_property_split = False
    split_9B58A.use_property_decorate = False
    split_9B58A.scale_x = 1.0
    split_9B58A.scale_y = 1.5
    split_9B58A.alignment = 'Expand'.upper()
    if not True: split_9B58A.operator_context = "EXEC_DEFAULT"
    op = split_9B58A.operator('sna.input_fbx_2b992', text='导入', icon_value=string_to_icon('IMPORT'), emboss=True, depress=False)
    op = split_9B58A.operator('sna.output_fbx_995a5', text='导出', icon_value=string_to_icon('EXPORT'), emboss=True, depress=False)


class SNA_OT_Output_Fbx_995A5(bpy.types.Operator):
    bl_idname = "sna.output_fbx_995a5"
    bl_label = "output_fbx"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        bpy.ops.export_scene.fbx('INVOKE_DEFAULT', use_selection=True, use_visible=False, use_active_collection=False, collection='', global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', use_space_transform=True, bake_space_transform=False, object_types={'MESH'}, use_mesh_modifiers=False, use_mesh_modifiers_render=False, mesh_smooth_type='OFF', colors_type='SRGB', prioritize_active_color=True, use_subsurf=False, use_mesh_edges=False, use_tspace=False, use_triangles=False, use_custom_props=False, add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=False, armature_nodetype='NULL', bake_anim=False, bake_anim_use_all_bones=False, bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False, bake_anim_force_startend_keying=False, bake_anim_step=0.0, bake_anim_simplify_factor=0.0, path_mode='AUTO', embed_textures=False, batch_mode='OFF', use_batch_own_dir=False)
        return self.execute(context)


class SNA_OT_Input_Fbx_2B992(bpy.types.Operator):
    bl_idname = "sna.input_fbx_2b992"
    bl_label = "input_fbx"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.fbx_import(
        'INVOKE_DEFAULT',
        # 常规
        use_custom_props=False, #自定义属性
        use_custom_props_enum_as_string=False, #导入枚举为字符串
        # 几何数据
        use_custom_normals=True, #自定义法向
        import_subdivision=False, #细分曲面
        import_colors='SRGB', #顶点色
        validate_meshes=True, #检查网格
        # 材质引用
        mtl_name_collision_mode='REFERENCE_EXISTING',#引用同名材质
        # 动画
        use_anim=False, #动画
        anim_offset=0.0, #动画偏移
        #骨骼
        ignore_leaf_bones=False, #忽略叶骨骼
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def before_exit_handler_C24CA():
    if os.path.exists(r'C:\Blender_Cache'):
        pass
    else:
        if not os.path.exists(os.path.join(r'C:', 'Blender_Cache')):
            os.mkdir(os.path.join(r'C:', 'Blender_Cache'))
        if not os.path.exists(os.path.join(r'C:\Blender_Cache', 'BlenderToMax')):
            os.mkdir(os.path.join(r'C:\Blender_Cache', 'BlenderToMax'))
        if not os.path.exists(os.path.join(r'C:\Blender_Cache', 'BlenderToMaya')):
            os.mkdir(os.path.join(r'C:\Blender_Cache', 'BlenderToMaya'))


def sna_reuse_material_execute_3069B():
    for i_98226 in range(len(bpy.context.view_layer.objects.selected)):
        for i_BA670 in range(len(bpy.context.view_layer.objects.selected[i_98226].material_slots)):
            if '.0' in bpy.context.view_layer.objects.selected[i_98226].material_slots[i_BA670].material.name:
                node_tree['sna_old_mat_name'] = bpy.context.view_layer.objects.selected[i_98226].material_slots[i_BA670].material.name
                node_tree['sna_new_mat_name'] = bpy.context.view_layer.objects.selected[i_98226].material_slots[i_BA670].material.name[:-4]
                bpy.context.view_layer.objects.selected[i_98226].material_slots[i_BA670].material = bpy.data.materials[bpy.context.view_layer.objects.selected[i_98226].material_slots[i_BA670].material.name[:-4]]
                print(node_tree['sna_old_mat_name'] + '    替换成    ' + node_tree['sna_new_mat_name'])
    return


def sna_clean_normal_execute_90228():
    if bpy.context.scene.sna_bridge_clean_normal_switch:
        for i_F751D in range(len(bpy.context.view_layer.objects.selected)):
            bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.selected[i_F751D]
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        print('清理自定义法线成功！')
        return


def sna_clean_normal_interface_8DF6C(layout_function, ):
    layout_function.prop(bpy.context.scene, 'sna_bridge_clean_normal_switch', text='导入清理自定义法线', icon_value=0, emboss=True)


def sna_mat_switch_92BBA(boolean):
    for i_D987B in range(len(bpy.data.materials)):
        bpy.data.materials[i_D987B].use_nodes = boolean
        print('开关材质：', bpy.data.materials[i_D987B].name)
    return


def sna_img__B5485(layout_function, ):
    layout_function.prop(bpy.context.scene, 'sna_bridge_img_output_switch', text='导出关联贴图（bate）', icon_value=0, emboss=True)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.Scene.sna_bridge_clean_normal_switch = bpy.props.BoolProperty(name='bridge_clean_normal_switch', description='默认开启，导入后模型法线效果不一致时尝试开关比较下', default=True)
    bpy.types.Scene.sna_bridge_img_output_switch = bpy.props.BoolProperty(name='bridge_img_output_switch', description='默认关闭，关闭时只导出材质名称', default=False)
    bpy.types.Scene.sna_bridge_port_switch = bpy.props.EnumProperty(name='bridge_port_switch', description='', items=[('FBX ', 'FBX ', '', 0, 0), ('Maya ', 'Maya ', '', 0, 1), ('Max ', 'Max ', '', 0, 2), ('插件', '插件', '', 0, 3)])
    bpy.utils.register_class(SNA_PT_V10_BATE_F3595)
    bpy.types.TOPBAR_MT_editor_menus.append(sna_add_to_topbar_mt_editor_menus_DE27C)
    bpy.utils.register_class(SNA_OT_Blender_Output_Max_D67C7)
    bpy.utils.register_class(SNA_OT_Max_Input_Blender_21992)
    bpy.utils.register_class(SNA_OT_Blender_Output_Maya_74C9A)
    bpy.utils.register_class(SNA_OT_Maya_Input_Blender_192Ad)
    bpy.utils.register_class(SNA_OT_Open_Plugin_043A6)
    bpy.utils.register_class(SNA_OT_Output_Fbx_995A5)
    bpy.utils.register_class(SNA_OT_Input_Fbx_2B992)
    atexit.register(before_exit_handler_C24CA)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Scene.sna_bridge_port_switch
    del bpy.types.Scene.sna_bridge_img_output_switch
    del bpy.types.Scene.sna_bridge_clean_normal_switch
    bpy.utils.unregister_class(SNA_PT_V10_BATE_F3595)
    bpy.types.TOPBAR_MT_editor_menus.remove(sna_add_to_topbar_mt_editor_menus_DE27C)
    bpy.utils.unregister_class(SNA_OT_Blender_Output_Max_D67C7)
    bpy.utils.unregister_class(SNA_OT_Max_Input_Blender_21992)
    bpy.utils.unregister_class(SNA_OT_Blender_Output_Maya_74C9A)
    bpy.utils.unregister_class(SNA_OT_Maya_Input_Blender_192Ad)
    bpy.utils.unregister_class(SNA_OT_Open_Plugin_043A6)
    bpy.utils.unregister_class(SNA_OT_Output_Fbx_995A5)
    bpy.utils.unregister_class(SNA_OT_Input_Fbx_2B992)
    atexit.unregister(before_exit_handler_C24CA)
