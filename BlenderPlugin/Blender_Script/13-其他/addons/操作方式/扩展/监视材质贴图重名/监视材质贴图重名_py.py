import bpy
import bpy.utils.previews
from bpy.app.handlers import persistent




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
node_tree_002 = {'sna_lod_matname': '', 'sna_new_matname': '', 'sna_mat_repeat': False, 'sna_img_repeat': False, 'sna_nod_repeat': False, }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def sna_add_to_view3d_mt_editor_menus_C9258(self, context):
    if not (False):
        layout = self.layout
        row_75797 = layout.row(heading='', align=True)
        row_75797.alert = False
        row_75797.enabled = True
        row_75797.active = True
        row_75797.use_property_split = False
        row_75797.use_property_decorate = False
        row_75797.scale_x = 1.0
        row_75797.scale_y = 1.0
        row_75797.alignment = 'Expand'.upper()
        row_75797.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_B867E = row_75797.column(heading='', align=False)
        col_B867E.alert = node_tree_002['sna_mat_repeat']
        col_B867E.enabled = True
        col_B867E.active = True
        col_B867E.use_property_split = False
        col_B867E.use_property_decorate = False
        col_B867E.scale_x = 1.0
        col_B867E.scale_y = 1.0
        col_B867E.alignment = 'Expand'.upper()
        col_B867E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_B867E.operator('sna.my_generic_operator_0f4a7', text='', icon_value=string_to_icon('SHADING_RENDERED'), emboss=False, depress=False)
        col_86665 = row_75797.column(heading='', align=False)
        col_86665.alert = node_tree_002['sna_img_repeat']
        col_86665.enabled = True
        col_86665.active = True
        col_86665.use_property_split = False
        col_86665.use_property_decorate = False
        col_86665.scale_x = 1.0
        col_86665.scale_y = 1.0
        col_86665.alignment = 'Expand'.upper()
        col_86665.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_86665.operator('sna.my_generic_operator_4b25b', text='', icon_value=string_to_icon('SEQ_PREVIEW'), emboss=False, depress=False)
        col_F13CE = row_75797.column(heading='', align=False)
        col_F13CE.alert = node_tree_002['sna_nod_repeat']
        col_F13CE.enabled = True
        col_F13CE.active = True
        col_F13CE.use_property_split = False
        col_F13CE.use_property_decorate = False
        col_F13CE.scale_x = 1.0
        col_F13CE.scale_y = 1.0
        col_F13CE.alignment = 'Expand'.upper()
        col_F13CE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        col_F13CE.label(text='', icon_value=string_to_icon('NODE_INSERT_OFF'))


class SNA_OT_My_Generic_Operator_0F4A7(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_0f4a7"
    bl_label = "清理_材质"
    bl_description = "清理.0材质"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_F9446 in range(len(bpy.context.scene.objects)):
            if property_exists("bpy.context.scene.objects[i_F9446].data", globals(), locals()):
                if (bpy.context.scene.objects[i_F9446].data.id_type == 'MESH'):
                    for i_4214E in range(len(bpy.context.scene.objects[i_F9446].material_slots)):
                        if property_exists("bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material.name", globals(), locals()):
                            if '.0' in bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material.name[-4:]:
                                node_tree_002['sna_lod_matname'] = bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material.name
                                node_tree_002['sna_new_matname'] = bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material.name[:-4]
                                if property_exists("bpy.data.materials[bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material.name[:-4]]", globals(), locals()):
                                    bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material = bpy.data.materials[bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material.name[:-4]]
                                    self.report({'INFO'}, message='材质：' + node_tree_002['sna_lod_matname'] + '替换为' + node_tree_002['sna_new_matname'])
                                else:
                                    bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material.name = bpy.context.scene.objects[i_F9446].material_slots[i_4214E].material.name[:-4]
                                    self.report({'INFO'}, message='材质：' + node_tree_002['sna_lod_matname'] + '重命名' + node_tree_002['sna_new_matname'])
        bpy.ops.outliner.orphans_purge(do_recursive=True)
        node_tree_002['sna_lod_matname'] = ''
        node_tree_002['sna_new_matname'] = ''
        bpy.ops.sna.my_generic_operator_68d09()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_4B25B(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_4b25b"
    bl_label = "清理_贴图"
    bl_description = "清理.0贴图"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        for i_13094 in range(len(bpy.data.images)):
            if '.0' in bpy.data.images[i_13094].name[-4:]:
                old = bpy.data.images[i_13094].name
                new = bpy.data.images[i_13094].name[:-4]
                result = None
                # 要替换的贴图名称
                old_texture_name = old
                # 新的贴图名称
                new_texture_name = new
                # 存储转换结果的列表
                result_list = []
                # 遍历场景中的所有材质
                for material in bpy.data.materials:
                    # 检查材质是否有节点树
                    if material.use_nodes:
                        # 遍历节点树中的所有节点
                        for node in material.node_tree.nodes:
                            # 检查节点是否为图像节点并且图像名称匹配
                            if node.type == 'TEX_IMAGE' and node.image is not None and node.image.name == old_texture_name:
                                # 查找新的贴图
                                new_image = bpy.data.images.get(new_texture_name)
                                if new_image is None:
                                    # 如果没有找到新的贴图，则将旧的贴图重命名为新的贴图名称
                                    node.image.name = new_texture_name
                                    result_list.append(f"贴图：{old_texture_name} 重命名 {new_texture_name}")
                                else:
                                    # 否则将节点的贴图替换为新的贴图
                                    node.image = new_image
                                    result_list.append(f"贴图：{old_texture_name} 替换为 {new_texture_name}")
                # 输出转换结果
                for result in result_list:
                    print(result)
                self.report({'INFO'}, message=result)
        bpy.ops.outliner.orphans_purge(do_recursive=True)
        bpy.ops.sna.my_generic_operator_68d09()
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SNA_OT_My_Generic_Operator_68D09(bpy.types.Operator):
    bl_idname = "sna.my_generic_operator_68d09"
    bl_label = "刷新重复检查"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        node_tree_002['sna_nod_repeat'] = False
        node_tree_002['sna_img_repeat'] = False
        node_tree_002['sna_mat_repeat'] = False
        for i_0CBA4 in range(len(bpy.data.materials)):
            if '.0' in bpy.data.materials[i_0CBA4].name:
                node_tree_002['sna_mat_repeat'] = True
                break
        for i_0B4C3 in range(len(bpy.data.images)):
            if '.0' in bpy.data.images[i_0B4C3].name:
                node_tree_002['sna_img_repeat'] = True
                break
        for i_C05E2 in range(len(bpy.data.node_groups)):
            if '.0' in bpy.data.node_groups[i_C05E2].name:
                node_tree_002['sna_nod_repeat'] = True
                break
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


@persistent
def save_pre_handler_0FCF4(dummy):
    bpy.ops.sna.my_generic_operator_68d09('INVOKE_DEFAULT', )


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.VIEW3D_MT_editor_menus.append(sna_add_to_view3d_mt_editor_menus_C9258)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_0F4A7)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_4B25B)
    bpy.utils.register_class(SNA_OT_My_Generic_Operator_68D09)
    bpy.app.handlers.save_pre.append(save_pre_handler_0FCF4)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.types.VIEW3D_MT_editor_menus.remove(sna_add_to_view3d_mt_editor_menus_C9258)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_0F4A7)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_4B25B)
    bpy.utils.unregister_class(SNA_OT_My_Generic_Operator_68D09)
    bpy.app.handlers.save_pre.remove(save_pre_handler_0FCF4)
