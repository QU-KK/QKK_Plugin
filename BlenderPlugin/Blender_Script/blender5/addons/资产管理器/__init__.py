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
    "name" : "Asset Management Expansion",
    "author" : "Qkk", 
    "description" : "Operational options can be added to images and materials to enhance usability.",
    "blender" : (5, 0, 0),
    "version" : (2, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "https://superhivemarket.com/creators/qkk", 
    "category" : "Asset" 
}


import bpy
import bpy.utils.previews
import os
import subprocess




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
node_tree_003 = {'sna_new_variable': '', }


def property_exists(prop_path, glob, loc):
    try:
        eval(prop_path, glob, loc)
        return True
    except:
        return False


def get_id_preview_id(data):
    if hasattr(data, "preview"):
        if not data.preview:
            data.preview_ensure()
        if hasattr(data.preview, "icon_id"):
            return data.preview.icon_id
    return 0


def sna_add_to_assetbrowser_pt_metadata_85850(self, context):
    if not (False):
        layout = self.layout
        if property_exists("bpy.context.id.id_type", globals(), locals()):
            if ('IMAGE' == bpy.context.id.id_type):
                layout_function = layout
                sna_image_configuration_14D6B(layout_function, )
            if (bpy.context.id.id_type == 'MATERIAL'):
                layout_function = layout
                sna_material_configuration_3E316(layout_function, )


def sna_add_to_assetbrowser_mt_editor_menus_0D928(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('sna.operation_asset_fb945', text=('更新资产' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Update'), icon_value=string_to_icon('PHYSICS'), emboss=True, depress=False)
        op.sna_func_name = 'Update_Assets'
        layout.separator(factor=1.0)
        split_6C593 = layout.split(factor=0.5, align=True)
        split_6C593.alert = False
        split_6C593.enabled = True
        split_6C593.active = True
        split_6C593.use_property_split = False
        split_6C593.use_property_decorate = False
        split_6C593.scale_x = 1.0
        split_6C593.scale_y = 1.0
        split_6C593.alignment = 'Expand'.upper()
        if not True: split_6C593.operator_context = "EXEC_DEFAULT"
        split_6C593.prop(bpy.context.area.spaces[0].params.filter_asset_id, 'filter_material', text='', icon_value=0, emboss=True)
        split_6C593.prop(bpy.context.area.spaces[0].params.filter_asset_id, 'experimental_filter_image', text='', icon_value=0, emboss=True)
        layout_function = layout
        sna_func_5B71E(layout_function, )
        split_1565A = layout.split(factor=0.800000011920929, align=True)
        split_1565A.alert = False
        split_1565A.enabled = True
        split_1565A.active = True
        split_1565A.use_property_split = False
        split_1565A.use_property_decorate = False
        split_1565A.scale_x = 1.0
        split_1565A.scale_y = 1.0
        split_1565A.alignment = 'Expand'.upper()
        if not True: split_1565A.operator_context = "EXEC_DEFAULT"
        op = split_1565A.operator('outliner.orphans_purge', text=('未使用' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Unused'), icon_value=0, emboss=True, depress=False)
        op.do_local_ids = True
        op.do_linked_ids = True
        op.do_recursive = True
        op = split_1565A.operator('outliner.orphans_manage', text='', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)


def sna_refresh_preview_4E81B(layout_function, ):
    op = layout_function.operator('sna.operation_asset_fb945', text=('刷新预览' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Refresh Preview'), icon_value=string_to_icon('MOD_TIME'), emboss=True, depress=False)
    op.sna_func_name = 'Refresh_Preview'
    layout_function.separator(factor=1.0)


def sna_add_to_assetbrowser_mt_context_menu_FEED2(self, context):
    if not (False):
        layout = self.layout
        layout_function = layout
        sna_refresh_preview_4E81B(layout_function, )
        if (len(bpy.context.selected_files) == 1):
            if (bpy.context.id.id_type == 'IMAGE'):
                if ((len(bpy.context.blend_data.images[bpy.context.active_file.name].packed_files) != 0) or os.path.exists(bpy.path.abspath(bpy.context.blend_data.images[bpy.context.id.name].filepath))):
                    if (not (len(bpy.context.blend_data.images[bpy.context.active_file.name].packed_files) != 0)):
                        op = layout.operator('sna.process_img_23ad1', text=('打包' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Pack'), icon_value=string_to_icon('DECORATE_LOCKED'), emboss=True, depress=False)
                        op.sna_func_name = 'pack'
                    else:
                        col_963D8 = layout.column(heading='', align=True)
                        col_963D8.alert = False
                        col_963D8.enabled = True
                        col_963D8.active = True
                        col_963D8.use_property_split = False
                        col_963D8.use_property_decorate = False
                        col_963D8.scale_x = 1.0
                        col_963D8.scale_y = 1.0
                        col_963D8.alignment = 'Expand'.upper()
                        col_963D8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                        op = col_963D8.operator('sna.process_img_23ad1', text=('解包' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Unpack'), icon_value=string_to_icon('DECORATE_UNLOCKED'), emboss=True, depress=False)
                        op.sna_func_name = 'unpack'
                        col_963D8.separator(factor=1.0)
                    col_220AF = layout.column(heading='', align=False)
                    col_220AF.alert = False
                    col_220AF.enabled = True
                    col_220AF.active = True
                    col_220AF.use_property_split = False
                    col_220AF.use_property_decorate = False
                    col_220AF.scale_x = 1.0
                    col_220AF.scale_y = 1.0
                    col_220AF.alignment = 'Expand'.upper()
                    col_220AF.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    col_220AF.separator(factor=1.0)
                    col_9C2BE = col_220AF.column(heading='', align=False)
                    col_9C2BE.alert = False
                    col_9C2BE.enabled = (not (len(bpy.context.blend_data.images[bpy.context.active_file.name].packed_files) != 0))
                    col_9C2BE.active = True
                    col_9C2BE.use_property_split = False
                    col_9C2BE.use_property_decorate = False
                    col_9C2BE.scale_x = 1.0
                    col_9C2BE.scale_y = 1.0
                    col_9C2BE.alignment = 'Expand'.upper()
                    col_9C2BE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    op = col_9C2BE.operator('sna.process_img_23ad1', text=('目录' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Folder'), icon_value=string_to_icon('FOLDER_REDIRECT'), emboss=True, depress=False)
                    op.sna_func_name = 'Open_Directory'
                    op = col_9C2BE.operator('sna.process_img_23ad1', text=('重载' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Reload'), icon_value=string_to_icon('FILE_REFRESH'), emboss=True, depress=False)
                    op.sna_func_name = 'Reload_Img'
                    op = col_9C2BE.operator('sna.rename_img_a8c64', text=('重命名' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Rename'), icon_value=string_to_icon('REMOVE'), emboss=True, depress=False)
                    col_220AF.separator(factor=1.0)
                    op = col_220AF.operator('sna.process_img_23ad1', text=('查看' if (bpy.context.preferences.view.language == 'zh_HANS') else 'View'), icon_value=string_to_icon('IMAGE_BACKGROUND'), emboss=True, depress=False)
                    op.sna_func_name = 'Open_Img'
                    op = col_220AF.operator('sna.process_img_23ad1', text=('删除' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Delete'), icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
                    op.sna_func_name = 'Delete_Img'
                    op = col_220AF.operator('sna.process_img_23ad1', text=('另存' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Save As'), icon_value=string_to_icon('FILE_TICK'), emboss=True, depress=False)
                    op.sna_func_name = 'Save_As_Img'
                    col_220AF.separator(factor=1.0)
                else:
                    col_0D548 = layout.column(heading='', align=False)
                    col_0D548.alert = False
                    col_0D548.enabled = True
                    col_0D548.active = True
                    col_0D548.use_property_split = False
                    col_0D548.use_property_decorate = False
                    col_0D548.scale_x = 1.0
                    col_0D548.scale_y = 1.0
                    col_0D548.alignment = 'Expand'.upper()
                    col_0D548.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                    op = col_0D548.operator('sna.process_img_23ad1', text=('图像已丢失    删除' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Image Missing Delete'), icon_value=string_to_icon('NOT_FOUND'), emboss=True, depress=False)
                    op.sna_func_name = 'Delete_Img'
                    col_0D548.separator(factor=1.0)
            if (bpy.context.id.id_type == 'MATERIAL'):
                col_6265E = layout.column(heading='', align=False)
                col_6265E.alert = False
                col_6265E.enabled = True
                col_6265E.active = True
                col_6265E.use_property_split = False
                col_6265E.use_property_decorate = False
                col_6265E.scale_x = 1.0
                col_6265E.scale_y = 1.0
                col_6265E.alignment = 'Expand'.upper()
                col_6265E.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_6265E.operator('sna.material_process_f7d34', text=('选中模型' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Select mod'), icon_value=string_to_icon('RESTRICT_SELECT_OFF'), emboss=True, depress=False)
                op.sna_func_name = 'Select_Mod'
                op = col_6265E.operator('sna.material_process_f7d34', text=('使用材质' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Apply mat'), icon_value=string_to_icon('CHECKMARK'), emboss=True, depress=False)
                op.sna_func_name = 'Use_Mat'
                col_7F4FE = col_6265E.column(heading='', align=False)
                col_7F4FE.alert = False
                col_7F4FE.enabled = 'EDIT_MESH'==bpy.context.mode
                col_7F4FE.active = True
                col_7F4FE.use_property_split = False
                col_7F4FE.use_property_decorate = False
                col_7F4FE.scale_x = 1.0
                col_7F4FE.scale_y = 1.0
                col_7F4FE.alignment = 'Expand'.upper()
                col_7F4FE.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
                op = col_7F4FE.operator('sna.material_process_f7d34', text=('使用到面' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Apply To Face'), icon_value=string_to_icon('DECORATE_KEYFRAME'), emboss=True, depress=False)
                op.sna_func_name = 'Apply_Face'
                op = col_6265E.operator('sna.material_process_f7d34', text=('删除' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Delete'), icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
                op.sna_func_name = 'Delete_Mat'
                op = col_6265E.operator('sna.rename_mat_2148f', text=('重命名' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Rename'), icon_value=string_to_icon('REMOVE'), emboss=True, depress=False)
                col_6265E.separator(factor=1.0)
        if (len(bpy.context.selected_files) > 1):
            col_BDB96 = layout.column(heading='', align=False)
            col_BDB96.alert = False
            col_BDB96.enabled = True
            col_BDB96.active = True
            col_BDB96.use_property_split = False
            col_BDB96.use_property_decorate = False
            col_BDB96.scale_x = 1.0
            col_BDB96.scale_y = 1.0
            col_BDB96.alignment = 'Expand'.upper()
            col_BDB96.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
            op = col_BDB96.operator('sna.operation_asset_fb945', text=('批量删除' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Bulk Delete'), icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
            op.sna_func_name = 'Delete_Assets'
            col_BDB96.separator(factor=1.0)


class SNA_OT_Rename_Mat_2148F(bpy.types.Operator):
    bl_idname = "sna.rename_mat_2148f"
    bl_label = "Rename_Mat"
    bl_description = "Rename_Mat"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_RENAME_PANEL_MAT_2D4F8", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_RENAME_PANEL_MAT_2D4F8(bpy.types.Panel):
    bl_label = 'Rename_Panel_Mat'
    bl_idname = 'SNA_PT_RENAME_PANEL_MAT_2D4F8'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_context = ''
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        layout.prop(bpy.data.materials[bpy.context.active_file.name], 'name', text='', icon_value=0, emboss=True)


class SNA_OT_Rename_Img_A8C64(bpy.types.Operator):
    bl_idname = "sna.rename_img_a8c64"
    bl_label = "Rename_Img"
    bl_description = "Rename_Img"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        bpy.ops.wm.call_panel(name="SNA_PT_RENAME_PANEL_IMG_51A71", keep_open=True)
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_PT_RENAME_PANEL_IMG_51A71(bpy.types.Panel):
    bl_label = 'Rename_Panel_Img'
    bl_idname = 'SNA_PT_RENAME_PANEL_IMG_51A71'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_context = ''
    bl_order = 0
    bl_ui_units_x=0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout

    def draw(self, context):
        layout = self.layout
        row_7B66C = layout.row(heading='', align=True)
        row_7B66C.alert = (bpy.context.blend_data.images[bpy.context.id.name].name != os.path.basename(bpy.path.abspath(bpy.context.blend_data.images[bpy.context.id.name].filepath)))
        row_7B66C.enabled = True
        row_7B66C.active = True
        row_7B66C.use_property_split = False
        row_7B66C.use_property_decorate = False
        row_7B66C.scale_x = 1.0
        row_7B66C.scale_y = 1.0
        row_7B66C.alignment = 'Expand'.upper()
        row_7B66C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_7B66C.prop(bpy.context.blend_data.images[bpy.context.id.name], 'name', text='', icon_value=0, emboss=True)
        op = row_7B66C.operator('sna.process_img_23ad1', text='', icon_value=string_to_icon('CHECKMARK'), emboss=True, depress=False)
        op.sna_func_name = 'Apply_Img_Name'


def sna_image_configuration_14D6B(layout_function, ):
    box_F3F3D = layout_function.box()
    box_F3F3D.alert = False
    box_F3F3D.enabled = True
    box_F3F3D.active = True
    box_F3F3D.use_property_split = False
    box_F3F3D.use_property_decorate = False
    box_F3F3D.alignment = 'Expand'.upper()
    box_F3F3D.scale_x = 1.0
    box_F3F3D.scale_y = 1.0
    if not True: box_F3F3D.operator_context = "EXEC_DEFAULT"
    col_3FE3A = box_F3F3D.column(heading='', align=True)
    col_3FE3A.alert = False
    col_3FE3A.enabled = True
    col_3FE3A.active = True
    col_3FE3A.use_property_split = False
    col_3FE3A.use_property_decorate = False
    col_3FE3A.scale_x = 1.0
    col_3FE3A.scale_y = 1.0
    col_3FE3A.alignment = 'Expand'.upper()
    col_3FE3A.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_BCE03 = col_3FE3A.row(heading='', align=True)
    row_BCE03.alert = False
    row_BCE03.enabled = True
    row_BCE03.active = True
    row_BCE03.use_property_split = False
    row_BCE03.use_property_decorate = False
    row_BCE03.scale_x = 1.0
    row_BCE03.scale_y = 1.0
    row_BCE03.alignment = 'Expand'.upper()
    row_BCE03.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_BCE03.label(text=('尺寸：' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Size:  ') + str(tuple(bpy.data.images[bpy.context.active_file.name].id_data.size)), icon_value=0)
    row_BCE03.prop(bpy.data.images[bpy.context.active_file.name], 'use_fake_user', text='', icon_value=0, emboss=True)
    op = row_BCE03.operator('sna.process_img_23ad1', text='', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
    op.sna_func_name = 'Delete_Img'
    split_A6D46 = col_3FE3A.split(factor=0.5, align=True)
    split_A6D46.alert = False
    split_A6D46.enabled = True
    split_A6D46.active = True
    split_A6D46.use_property_split = False
    split_A6D46.use_property_decorate = False
    split_A6D46.scale_x = 1.0
    split_A6D46.scale_y = 1.0
    split_A6D46.alignment = 'Expand'.upper()
    if not True: split_A6D46.operator_context = "EXEC_DEFAULT"
    split_A6D46.label(text=('相关：' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Users:  ') + str(bpy.data.images[bpy.context.active_file.name].id_data.users), icon_value=0)
    split_A6D46.prop(bpy.data.images[bpy.context.active_file.name].colorspace_settings, 'name', text='', icon_value=0, emboss=True)
    box_55635 = col_3FE3A.box()
    box_55635.alert = False
    box_55635.enabled = True
    box_55635.active = True
    box_55635.use_property_split = False
    box_55635.use_property_decorate = False
    box_55635.alignment = 'Expand'.upper()
    box_55635.scale_x = 1.0
    box_55635.scale_y = 1.0
    if not True: box_55635.operator_context = "EXEC_DEFAULT"
    box_55635.template_icon(icon_value=get_id_preview_id(bpy.data.images[bpy.context.active_file.name]), scale=6.0)
    row_29D9F = col_3FE3A.row(heading='', align=True)
    row_29D9F.alert = (bpy.data.images[bpy.context.active_file.name].name != os.path.basename(bpy.path.abspath(bpy.data.images[bpy.context.active_file.name].filepath)))
    row_29D9F.enabled = (not (len(bpy.data.images[bpy.context.active_file.name].packed_files) != 0))
    row_29D9F.active = True
    row_29D9F.use_property_split = False
    row_29D9F.use_property_decorate = False
    row_29D9F.scale_x = 1.0
    row_29D9F.scale_y = 1.0
    row_29D9F.alignment = 'Expand'.upper()
    row_29D9F.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_29D9F.prop(bpy.data.images[bpy.context.active_file.name], 'name', text='', icon_value=0, emboss=True)
    op = row_29D9F.operator('sna.process_img_23ad1', text='', icon_value=string_to_icon('CHECKMARK'), emboss=True, depress=False)
    op.sna_func_name = 'Apply_Img_Name'
    row_06849 = col_3FE3A.row(heading='', align=True)
    row_06849.alert = False
    row_06849.enabled = True
    row_06849.active = True
    row_06849.use_property_split = False
    row_06849.use_property_decorate = False
    row_06849.scale_x = 1.0
    row_06849.scale_y = 1.0
    row_06849.alignment = 'Expand'.upper()
    row_06849.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_E6E82 = row_06849.row(heading='', align=True)
    row_E6E82.alert = False
    row_E6E82.enabled = (not (len(bpy.data.images[bpy.context.active_file.name].packed_files) != 0))
    row_E6E82.active = True
    row_E6E82.use_property_split = False
    row_E6E82.use_property_decorate = False
    row_E6E82.scale_x = 1.0
    row_E6E82.scale_y = 1.0
    row_E6E82.alignment = 'Expand'.upper()
    row_E6E82.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = row_E6E82.operator('sna.process_img_23ad1', text=('目录' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Folder'), icon_value=0, emboss=True, depress=False)
    op.sna_func_name = 'Open_Directory'
    op = row_E6E82.operator('sna.process_img_23ad1', text=('重载' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Reload'), icon_value=0, emboss=True, depress=False)
    op.sna_func_name = 'Reload_Img'
    op = row_06849.operator('sna.process_img_23ad1', text=('查看' if (bpy.context.preferences.view.language == 'zh_HANS') else 'View'), icon_value=0, emboss=True, depress=False)
    op.sna_func_name = 'Open_Img'
    op = row_06849.operator('sna.process_img_23ad1', text=('另存' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Save As'), icon_value=0, emboss=True, depress=False)
    op.sna_func_name = 'Save_As_Img'
    if (len(bpy.data.images[bpy.context.active_file.name].packed_files) != 0):
        row_E6CCC = col_3FE3A.row(heading='', align=True)
        row_E6CCC.alert = False
        row_E6CCC.enabled = True
        row_E6CCC.active = True
        row_E6CCC.use_property_split = False
        row_E6CCC.use_property_decorate = False
        row_E6CCC.scale_x = 1.0
        row_E6CCC.scale_y = 1.0
        row_E6CCC.alignment = 'Expand'.upper()
        row_E6CCC.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_E6CCC.label(text=('已打包' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Packaged'), icon_value=string_to_icon('DECORATE_LOCKED'))
        op = row_E6CCC.operator('sna.process_img_23ad1', text='', icon_value=string_to_icon('DECORATE_UNLOCKED'), emboss=True, depress=False)
        op.sna_func_name = 'unpack'
    else:
        col_A321B = col_3FE3A.column(heading='', align=True)
        col_A321B.alert = (not os.path.exists(bpy.path.abspath(bpy.data.images[bpy.context.active_file.name].filepath)))
        col_A321B.enabled = True
        col_A321B.active = True
        col_A321B.use_property_split = False
        col_A321B.use_property_decorate = False
        col_A321B.scale_x = 1.0
        col_A321B.scale_y = 1.0
        col_A321B.alignment = 'Expand'.upper()
        col_A321B.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_A6E17 = col_A321B.row(heading='', align=True)
        row_A6E17.alert = False
        row_A6E17.enabled = True
        row_A6E17.active = True
        row_A6E17.use_property_split = False
        row_A6E17.use_property_decorate = False
        row_A6E17.scale_x = 1.0
        row_A6E17.scale_y = 1.0
        row_A6E17.alignment = 'Expand'.upper()
        row_A6E17.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        row_A6E17.prop(bpy.data.images[bpy.context.active_file.name], 'filepath', text='', icon_value=0, emboss=True)
        op = row_A6E17.operator('sna.process_img_23ad1', text='', icon_value=string_to_icon('DECORATE_LOCKED'), emboss=True, depress=False)
        op.sna_func_name = 'pack'
    layout_function.separator(factor=4.0)


class SNA_OT_Process_Img_23Ad1(bpy.types.Operator):
    bl_idname = "sna.process_img_23ad1"
    bl_label = "Process_Img"
    bl_description = "Process_Img"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        import os
        img_name = bpy.context.id.name
        img = bpy.data.images[img_name]
        img_path = bpy.path.abspath(img.filepath)
        # 打开目录

        def Open_Directory():
            # 指定目录的路径
            directory_path = os.path.dirname(img_path)  # 目录实际路径
            # 选中特定的文件
            file_to_select = os.path.basename(img_path)  # 文件名
            # 在命令行中使用Explorer来选中文件
            subprocess.Popen(f'explorer /select, "{os.path.join(directory_path, file_to_select)}"')
        # 打开图像

        def Open_Img():
            bpy.ops.wm.window_new()    
            bpy.context.area.ui_type = 'IMAGE_EDITOR'
            bpy.context.area.spaces.active.image = img    
            #subprocess.run(['start', '', img_path], shell=True)
        # 重载图像

        def Reload_Img():
            img.reload()
        # 应用图像名称

        def Apply_Img_Name():
            # 源文件改名
            os.rename(img_path, os.path.join(os.path.dirname(img_path), img_name)) 
            # 使用新路径
            img.filepath = os.path.join(os.path.dirname(img_path),img_name)
        # 另存图像

        def Save_As_Img():
            bpy.context.area.ui_type = 'IMAGE_EDITOR'
            # 获取图像编辑器区域
            for area in bpy.context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    # 设置活动图像
                    area.spaces.active.image = img
                    break
            bpy.ops.image.save_as('INVOKE_DEFAULT', )
            bpy.context.area.ui_type = 'ASSETS'
            # 设置当前资产库引用为本地资产库

            def reference():
                area.spaces[0].show_region_tool_props = True    
            bpy.app.timers.register(reference, first_interval=0.1)
        # 删除图像

        def Delete_Img():    
            bpy.data.images.remove(image=img)
        # 打包

        def pack():
            img.pack()
        # 解包

        def unpack():
            img.unpack()
        # 调用函数
        functions = {
            "Open_Directory": Open_Directory,
            "Open_Img": Open_Img,
            "Reload_Img": Reload_Img,
            "Apply_Img_Name": Apply_Img_Name,
            "Save_As_Img": Save_As_Img,
            "Delete_Img": Delete_Img,
            "pack": pack,
            "unpack": unpack,
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Operation_Asset_Fb945(bpy.types.Operator):
    bl_idname = "sna.operation_asset_fb945"
    bl_label = "Operation_Asset"
    bl_description = "Operation_Asset"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        # 更新资产

        def Update_Assets():
            # 开启实验特性
            bpy.context.preferences.experimental.use_extended_asset_browser = True
            # 遍历所有材质
            for mat in bpy.data.materials:
                user = mat.use_fake_user  # 保存当前材质的假用户状态
                mat.asset_mark()          # 标记材质为资产
                mat.use_fake_user = user  # 恢复材质的假用户状态
            # 遍历所有图像
            for img in bpy.data.images:
                user = img.use_fake_user  # 保存当前图像的假用户状态
                img.asset_mark()          # 标记图像为资产
                img.use_fake_user = user  # 恢复图像的假用户状态
            # 设置资产库
            bpy.context.space_data.params.asset_library_reference = 'LOCAL'
        # 刷新预览

        def Refresh_Preview():    
            mat_name_list = []
            img_name_list = []
            for asset in bpy.context.selected_assets:
                name = asset.name
                if asset.id_type == 'MATERIAL':
                    mat_name_list.append(name)
                if asset.id_type == 'IMAGE':
                    img_name_list.append(name)
            for mat_name in mat_name_list:
                mat = bpy.data.materials[mat_name]
                mat.asset_data.id_data.asset_generate_preview()  # 生成材质的预览图
            for img_name in img_name_list:
                img = bpy.data.images[img_name]
                img.asset_data.id_data.asset_generate_preview()  # 生成图像的预览图
            # 遍历所有材质
            #for mat in bpy.data.materials:
                #if mat.asset_data != None:
                    #mat.asset_data.id_data.asset_generate_preview()  # 生成材质的预览图
            # 遍历所有图像
            #for img in bpy.data.images:
                #if img.asset_data != None:
                    #img.asset_data.id_data.asset_generate_preview()  # 生成图像的预览图
            # 设置资产库
            #bpy.context.space_data.params.asset_library_reference = 'LOCAL'
        # 删除资产

        def Delete_Assets():
            mat_name_list = []
            img_name_list = []
            for asset in bpy.context.selected_assets:
                name = asset.name
                if asset.id_type == 'MATERIAL':
                    mat_name_list.append(name)
                if asset.id_type == 'IMAGE':
                    img_name_list.append(name)
            for mat_name in mat_name_list:
                mat = bpy.data.materials[mat_name]
                bpy.context.blend_data.materials.remove(mat)    
            for img_name in img_name_list:
                img = bpy.data.images[img_name]
                bpy.context.blend_data.images.remove(img)
        # 预览资产

        def Browse_Asset():
            if bpy.context.id != None:        
                id_type = bpy.context.id.id_type
                asset_name = bpy.context.id.name             
                if id_type == 'IMAGE':
                    img = bpy.data.images[asset_name]  
                    for window in bpy.context.window_manager.windows:
                        # 查找图像编辑器的区域
                        for area in window.screen.areas:
                            if area.type == 'IMAGE_EDITOR':
                                # 切换到该区域，并设置当前图像
                                for space in area.spaces:
                                    if space.type == 'IMAGE_EDITOR':
                                        space.image = img        
                if id_type == 'MATERIAL':
                    view_layer = bpy.context.view_layer        
                    # 遍历场景中的所有物体
                    for obj in bpy.data.objects:
                        # 确保物体在当前视图层中
                        if obj.name in view_layer.objects and obj.type == 'MESH':
                            for index, mat_slot in enumerate(obj.material_slots):
                                if mat_slot.name == asset_name:
                                    view_layer.objects.active = obj
                                    obj.active_material_index = index  # 设置当前材质索引
                                    break
        # 调用函数
        functions = {
            "Update_Assets": Update_Assets,
            "Refresh_Preview": Refresh_Preview,
            "Delete_Assets": Delete_Assets,
            "Browse_Asset": Browse_Asset,
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_add_to_view3d_pt_tools_active_6D39F(self, context):
    if not (False):
        layout = self.layout
        col_22C4C = layout.column(heading='', align=True)
        col_22C4C.alert = False
        col_22C4C.enabled = True
        col_22C4C.active = True
        col_22C4C.use_property_split = False
        col_22C4C.use_property_decorate = False
        col_22C4C.scale_x = 1.0
        col_22C4C.scale_y = 1.5
        col_22C4C.alignment = 'Expand'.upper()
        col_22C4C.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
        op = col_22C4C.operator('sna.divide_the_area_76314', text='', icon_value=string_to_icon('ASSET_MANAGER'), emboss=True, depress=False)
        op.sna_func_name = 'Divide_Area'


class SNA_OT_Divide_The_Area_76314(bpy.types.Operator):
    bl_idname = "sna.divide_the_area_76314"
    bl_label = "Divide_the_area"
    bl_description = "Divide_the_area"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        # 拆分区域

        def Divide_Area():
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.4)   # VERTICAL
            areas = bpy.context.screen.areas
            area = areas[int(len(areas) - 1.0)]
            area.ui_type = 'ASSETS'
            # 设置当前资产库引用为本地资产库

            def reference():
                area.spaces.active.params.asset_library_reference = 'LOCAL'    
                area.spaces[0].show_region_toolbar = False
                area.spaces[0].show_region_tool_props = True    
            bpy.app.timers.register(reference, first_interval=0.1)
        # 关闭区域

        def Area_Close():
            bpy.ops.screen.area_close()
        # 新建窗口

        def New_Window():
            bpy.ops.wm.window_new()
            bpy.context.area.ui_type = 'OUTLINER'
            bpy.context.space_data.display_mode = 'LIBRARIES'
            bpy.context.space_data.filter_id_type = 'IMAGE'
            bpy.context.space_data.use_filter_id_type = True
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.2)
            bpy.context.area.ui_type = 'OUTLINER'
            bpy.context.space_data.display_mode = 'LIBRARIES'
            bpy.context.space_data.filter_id_type = 'MATERIAL'
            bpy.context.space_data.use_filter_id_type = True
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.75)
            bpy.context.area.ui_type = 'IMAGE_EDITOR'
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.51)   # VERTICAL
            bpy.context.area.ui_type = 'ShaderNodeTree'
            bpy.context.space_data.show_region_ui = False
        # 调用函数
        functions = {
            "Divide_Area": Divide_Area,
            "Area_Close": Area_Close,
            "New_Window": New_Window,
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def sna_add_to_assetbrowser_mt_editor_menus_E5BD5(self, context):
    if not (False):
        layout = self.layout
        op = layout.operator('sna.divide_the_area_76314', text='', icon_value=string_to_icon('QUIT'), emboss=True, depress=False)
        op.sna_func_name = 'Area_Close'
        op = layout.operator('sna.divide_the_area_76314', text=('面板' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Panel'), icon_value=string_to_icon('STATUSBAR'), emboss=True, depress=False)
        op.sna_func_name = 'New_Window'


def sna_material_configuration_3E316(layout_function, ):
    box_06637 = layout_function.box()
    box_06637.alert = False
    box_06637.enabled = True
    box_06637.active = True
    box_06637.use_property_split = False
    box_06637.use_property_decorate = False
    box_06637.alignment = 'Expand'.upper()
    box_06637.scale_x = 1.0
    box_06637.scale_y = 1.0
    if not True: box_06637.operator_context = "EXEC_DEFAULT"
    col_25CB3 = box_06637.column(heading='', align=True)
    col_25CB3.alert = False
    col_25CB3.enabled = True
    col_25CB3.active = True
    col_25CB3.use_property_split = False
    col_25CB3.use_property_decorate = False
    col_25CB3.scale_x = 1.0
    col_25CB3.scale_y = 1.0
    col_25CB3.alignment = 'Expand'.upper()
    col_25CB3.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_8B2C1 = col_25CB3.row(heading='', align=True)
    row_8B2C1.alert = False
    row_8B2C1.enabled = True
    row_8B2C1.active = True
    row_8B2C1.use_property_split = False
    row_8B2C1.use_property_decorate = False
    row_8B2C1.scale_x = 1.0
    row_8B2C1.scale_y = 1.0
    row_8B2C1.alignment = 'Expand'.upper()
    row_8B2C1.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    row_8B2C1.label(text=('相关：' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Users:  ') + str(bpy.context.blend_data.materials[bpy.context.id.name].users), icon_value=0)
    row_8B2C1.prop(bpy.context.blend_data.materials[bpy.context.id.name], 'use_fake_user', text='', icon_value=0, emboss=True)
    op = row_8B2C1.operator('sna.material_process_f7d34', text='', icon_value=string_to_icon('TRASH'), emboss=True, depress=False)
    op.sna_func_name = 'Delete_Mat'
    box_36FB1 = col_25CB3.box()
    box_36FB1.alert = False
    box_36FB1.enabled = True
    box_36FB1.active = True
    box_36FB1.use_property_split = False
    box_36FB1.use_property_decorate = False
    box_36FB1.alignment = 'Expand'.upper()
    box_36FB1.scale_x = 1.0
    box_36FB1.scale_y = 1.0
    if not True: box_36FB1.operator_context = "EXEC_DEFAULT"
    box_36FB1.template_icon(icon_value=get_id_preview_id(bpy.data.materials[bpy.context.id.name]), scale=5.0)
    col_25CB3.prop(bpy.data.materials[bpy.context.id.name], 'name', text='', icon_value=0, emboss=True)
    row_FE408 = col_25CB3.row(heading='', align=True)
    row_FE408.alert = False
    row_FE408.enabled = True
    row_FE408.active = True
    row_FE408.use_property_split = False
    row_FE408.use_property_decorate = False
    row_FE408.scale_x = 1.0
    row_FE408.scale_y = 1.0
    row_FE408.alignment = 'Expand'.upper()
    row_FE408.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = row_FE408.operator('sna.material_process_f7d34', text=('选中模型' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Select mod'), icon_value=0, emboss=True, depress=False)
    op.sna_func_name = 'Select_Mod'
    op = row_FE408.operator('sna.material_process_f7d34', text=('使用材质' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Apply mat'), icon_value=0, emboss=True, depress=False)
    op.sna_func_name = 'Use_Mat'
    col_856D8 = row_FE408.column(heading='', align=True)
    col_856D8.alert = False
    col_856D8.enabled = 'EDIT_MESH'==bpy.context.mode
    col_856D8.active = True
    col_856D8.use_property_split = False
    col_856D8.use_property_decorate = False
    col_856D8.scale_x = 1.0
    col_856D8.scale_y = 1.0
    col_856D8.alignment = 'Expand'.upper()
    col_856D8.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_856D8.operator('sna.material_process_f7d34', text=('使用到面' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Apply To Face'), icon_value=0, emboss=True, depress=False)
    op.sna_func_name = 'Apply_Face'
    layout_function.separator(factor=4.0)


class SNA_OT_Material_Process_F7D34(bpy.types.Operator):
    bl_idname = "sna.material_process_f7d34"
    bl_label = "Material_Process"
    bl_description = "Material_Process"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = self.sna_func_name
        view_layer = bpy.context.view_layer
        mat_name = bpy.context.id.name
        mat = bpy.data.materials[mat_name]
        # 选中模型

        def Select_Mod():
            # 清空当前选择
            bpy.ops.object.select_all(action='DESELECT')
            # 遍历场景中的所有物体
            for obj in bpy.data.objects:
                # 确保物体在当前视图层中
                if obj.name in view_layer.objects and obj.type == 'MESH':
                    for mat in obj.material_slots:
                        if mat.name == mat_name:
                            obj.select_set(True)  # 选择物体            
                            view_layer.objects.active = obj  # 更新最后选择的物体
                            for index, mat_slot in enumerate(obj.material_slots):
                                if mat_slot.name == mat_name:
                                    obj.active_material_index = index  # 设置当前材质索引
                                    break
        # 使用材质

        def Use_Mat():
            # 遍历当前视图层中选中的所有物体
            for obj in bpy.context.view_layer.objects.selected:
                if obj.type == 'MESH':  # 确保物体是网格类型
                    # 确保物体有材质槽
                    if obj.material_slots:
                        # 设置当前激活材质槽的材质
                        obj.active_material = mat  # 将材质赋予当前激活的材质槽
        # 应用到面组

        def Apply_Face():
            mat_name = bpy.context.id.name
            for obj in bpy.context.view_layer.objects.selected:
                bpy.context.view_layer.objects.active = obj
                if any(slot.name == mat_name for slot in obj.material_slots):
                    for index, slot in enumerate(obj.material_slots):
                        if slot.name == mat_name:
                            obj.active_material_index = index                
                    bpy.ops.object.material_slot_assign()
                else:
                    bpy.ops.object.material_slot_add()
                    bpy.ops.object.material_slot_assign()
                    id = obj.active_material_index
                    obj.material_slots[id].material = bpy.data.materials[mat_name]
        # 删除材质

        def Delete_Mat():
            bpy.data.materials.remove(material=mat)
        # 调用函数
        functions = {
            "Select_Mod": Select_Mod,
            "Use_Mat": Use_Mat,
            "Apply_Face": Apply_Face,
            "Delete_Mat": Delete_Mat,
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


class SNA_OT_Citation_Relationship_07564(bpy.types.Operator):
    bl_idname = "sna.citation_relationship_07564"
    bl_label = "Citation_Relationship"
    bl_description = "Citation_Relationship"
    bl_options = {"REGISTER", "UNDO"}
    sna_func_name: bpy.props.StringProperty(name='func_name', description='', options={'HIDDEN'}, default='', subtype='NONE', maxlen=0)

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        return not False

    def execute(self, context):
        func_name = 'Update_Assets'
        # 更新资产

        def Update_Assets():
            # 开启实验特性
            bpy.context.preferences.experimental.use_extended_asset_browser = True
            # 遍历所有材质
            for mat in bpy.data.materials:
                user = mat.use_fake_user  # 保存当前材质的假用户状态
                mat.asset_mark()          # 标记材质为资产
                mat.use_fake_user = user  # 恢复材质的假用户状态
            # 遍历所有图像
            for img in bpy.data.images:
                user = img.use_fake_user  # 保存当前图像的假用户状态
                img.asset_mark()          # 标记图像为资产
                img.use_fake_user = user  # 恢复图像的假用户状态
            # 设置资产库
            bpy.context.space_data.params.asset_library_reference = 'LOCAL'
        # 刷新预览

        def Refresh_Preview():    
            mat_name_list = []
            img_name_list = []
            for asset in bpy.context.selected_assets:
                name = asset.name
                if asset.id_type == 'MATERIAL':
                    mat_name_list.append(name)
                if asset.id_type == 'IMAGE':
                    img_name_list.append(name)
            for mat_name in mat_name_list:
                mat = bpy.data.materials[mat_name]
                mat.asset_data.id_data.asset_generate_preview()  # 生成材质的预览图
            for img_name in img_name_list:
                img = bpy.data.images[img_name]
                img.asset_data.id_data.asset_generate_preview()  # 生成图像的预览图
            # 遍历所有材质
            #for mat in bpy.data.materials:
                #if mat.asset_data != None:
                    #mat.asset_data.id_data.asset_generate_preview()  # 生成材质的预览图
            # 遍历所有图像
            #for img in bpy.data.images:
                #if img.asset_data != None:
                    #img.asset_data.id_data.asset_generate_preview()  # 生成图像的预览图
            # 设置资产库
            #bpy.context.space_data.params.asset_library_reference = 'LOCAL'
        # 删除资产

        def Delete_Assets():
            mat_name_list = []
            img_name_list = []
            for asset in bpy.context.selected_assets:
                name = asset.name
                if asset.id_type == 'MATERIAL':
                    mat_name_list.append(name)
                if asset.id_type == 'IMAGE':
                    img_name_list.append(name)
            for mat_name in mat_name_list:
                mat = bpy.data.materials[mat_name]
                bpy.context.blend_data.materials.remove(mat)    
            for img_name in img_name_list:
                img = bpy.data.images[img_name]
                bpy.context.blend_data.images.remove(img)
        # 预览资产

        def Browse_Asset():
            if bpy.context.id != None:        
                id_type = bpy.context.id.id_type
                asset_name = bpy.context.id.name             
                if id_type == 'IMAGE':
                    img = bpy.data.images[asset_name]  
                    for window in bpy.context.window_manager.windows:
                        # 查找图像编辑器的区域
                        for area in window.screen.areas:
                            if area.type == 'IMAGE_EDITOR':
                                # 切换到该区域，并设置当前图像
                                for space in area.spaces:
                                    if space.type == 'IMAGE_EDITOR':
                                        space.image = img        
                if id_type == 'MATERIAL':
                    view_layer = bpy.context.view_layer        
                    # 遍历场景中的所有物体
                    for obj in bpy.data.objects:
                        # 确保物体在当前视图层中
                        if obj.name in view_layer.objects and obj.type == 'MESH':
                            for index, mat_slot in enumerate(obj.material_slots):
                                if mat_slot.name == asset_name:
                                    view_layer.objects.active = obj
                                    obj.active_material_index = index  # 设置当前材质索引
                                    break
        # 调用函数
        functions = {
            "Update_Assets": Update_Assets,
            "Refresh_Preview": Refresh_Preview,
            "Delete_Assets": Delete_Assets,
            "Browse_Asset": Browse_Asset,
        }
        functions[func_name]()
        func_name = self.sna_func_name
        # 清空标签

        def Clear_Tags():
            # 清空搜索过滤器
            bpy.context.space_data.params.filter_search = ''
            # 遍历所有图像
            for img in bpy.data.images:
                tag_name_list = []  # 用于存储标签名字的列表
                if img.asset_data != None:  # 检查图像是否有资产数据
                    for tga in img.asset_data.tags:  # 遍历图像的所有标签
                        tag_name_list.append(tga.name)  # 将标签名添加到列表中
                for tag_name in tag_name_list:  # 遍历标签名列表
                    img.asset_data.tags.remove(img.asset_data.tags[tag_name])  # 移除标签
            # 遍历所有材质
            for mat in bpy.data.materials:
                tag_name_list = []  # 用于存储标签名字的列表
                if mat.asset_data != None:  # 检查材质是否有资产数据
                    for tga in mat.asset_data.tags:  # 遍历材质的所有标签
                        tag_name_list.append(tga.name)  # 将标签名添加到列表中
                for tag_name in tag_name_list:  # 遍历标签名列表
                    mat.asset_data.tags.remove(mat.asset_data.tags[tag_name])  # 移除标签
        # 设置标签

        def Set_Tags():    
            if bpy.context.id != None:
                Clear_Tags()        
                # 获取当前上下文的资产类型和名称
                ass_type = bpy.context.id.id_type
                ass_name = bpy.context.id.name
                tga_name = ass_name + '_AssetTga'
                # 如果当前资产类型是材质
                if ass_type == 'MATERIAL':
                    mat = bpy.data.materials[ass_name]  # 获取材质            
                    mat.id_data.asset_data.tags.new(name=tga_name)
                    if mat.use_nodes:  # 检查材质是否使用节点
                        for node in mat.node_tree.nodes:  # 遍历材质的所有节点
                            if node.type == 'TEX_IMAGE':  # 如果节点类型是图像纹理
                                img = node.image  # 获取节点中的图像
                                if img and img.asset_data != None:  # 检查图像是否存在且有资产数据
                                    img.id_data.asset_data.tags.new(name=tga_name)  # 为图像创建一个新的标签，名字为材质名称
                # 如果当前资产类型是图像
                if ass_type == 'IMAGE':
                    img = bpy.data.images[ass_name]  # 获取图像
                    img.id_data.asset_data.tags.new(name=tga_name)
                    for mat in bpy.data.materials:  # 遍历所有材质
                        if mat.use_nodes and mat.asset_data != None:  # 检查材质是否使用节点且有资产数据
                            for node in mat.node_tree.nodes:  # 遍历材质的所有节点
                                if node.type == 'TEX_IMAGE' and node.image == img:  # 如果节点是图像纹理且图像匹配
                                    mat.id_data.asset_data.tags.new(name=tga_name)  # 为材质创建一个新的标签，名字为图像名称
                                    break  # 退出循环，避免重复添加标签
                # 设置搜索过滤器为当前资产名称
                bpy.context.space_data.params.filter_search = tga_name
        # 调用函数
        functions = {
            "Clear_Tags": Clear_Tags,
            "Set_Tags": Set_Tags,
        }
        functions[func_name]()
        self.report({'INFO'}, message='OK!')
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


_20C05_running = False
class SNA_OT_Modal_Operator_20C05(bpy.types.Operator):
    bl_idname = "sna.modal_operator_20c05"
    bl_label = "Modal_Operator"
    bl_description = "Modal_Operator"
    bl_options = {"REGISTER", "UNDO"}
    cursor = "EYEDROPPER"
    _handle = None
    _event = {}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set('')
        if not False or context.area.spaces[0].bl_rna.identifier == 'SpaceNodeEditor':
            return not False
        return False

    def save_event(self, event):
        event_options = ["type", "value", "alt", "shift", "ctrl", "oskey", "mouse_region_x", "mouse_region_y", "mouse_x", "mouse_y", "pressure", "tilt"]
        if bpy.app.version >= (3, 2, 1):
            event_options += ["type_prev", "value_prev"]
        for option in event_options: self._event[option] = getattr(event, option)

    def draw_callback_px(self, context):
        event = self._event
        if event.keys():
            event = dotdict(event)
            try:
                pass
            except Exception as error:
                print(error)

    def execute(self, context):
        global _20C05_running
        _20C05_running = False
        context.window.cursor_set("DEFAULT")
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}

    def modal(self, context, event):
        global _20C05_running
        if not context.area or not _20C05_running:
            self.execute(context)
            return {'CANCELLED'}
        self.save_event(event)
        context.window.cursor_set('EYEDROPPER')
        try:
            for mat in bpy.data.materials:
                tag_name_list = []  # 用于存储标签名字的列表
                if mat.asset_data != None:  # 检查材质是否有资产数据
                    for tga in mat.asset_data.tags:  # 遍历材质的所有标签
                        tag_name_list.append(tga.name)  # 将标签名添加到列表中
                for tag_name in tag_name_list:  # 遍历标签名列表
                    mat.asset_data.tags.remove(mat.asset_data.tags[tag_name])  # 移除标签
            obj = bpy.context.active_object
            if obj != None:
                tga_name = obj.name + '_AssetTga'
                bpy.context.area.spaces[0].params.filter_search = tga_name
                for mat_slot in obj.material_slots:
                    if mat_slot.material != None:
                        mat = mat_slot.material
                        if mat.asset_data != None:  # 是否资产数据                
                            if tga_name not in mat.asset_data.tags:
                                mat.id_data.asset_data.tags.new(name=tga_name)
        except Exception as error:
            print(error)
        if event.type in ['RIGHTMOUSE', 'ESC']:
            self.execute(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global _20C05_running
        if _20C05_running:
            _20C05_running = False
            return {'FINISHED'}
        else:
            self.save_event(event)
            self.start_pos = (event.mouse_x, event.mouse_y)
            bpy.context.view_layer.objects.active = None
            func_name = 'Update_Assets'
            # 更新资产

            def Update_Assets():
                # 开启实验特性
                bpy.context.preferences.experimental.use_extended_asset_browser = True
                # 遍历所有材质
                for mat in bpy.data.materials:
                    user = mat.use_fake_user  # 保存当前材质的假用户状态
                    mat.asset_mark()          # 标记材质为资产
                    mat.use_fake_user = user  # 恢复材质的假用户状态
                # 遍历所有图像
                for img in bpy.data.images:
                    user = img.use_fake_user  # 保存当前图像的假用户状态
                    img.asset_mark()          # 标记图像为资产
                    img.use_fake_user = user  # 恢复图像的假用户状态
                # 设置资产库
                bpy.context.space_data.params.asset_library_reference = 'LOCAL'
            # 刷新预览

            def Refresh_Preview():    
                mat_name_list = []
                img_name_list = []
                for asset in bpy.context.selected_assets:
                    name = asset.name
                    if asset.id_type == 'MATERIAL':
                        mat_name_list.append(name)
                    if asset.id_type == 'IMAGE':
                        img_name_list.append(name)
                for mat_name in mat_name_list:
                    mat = bpy.data.materials[mat_name]
                    mat.asset_data.id_data.asset_generate_preview()  # 生成材质的预览图
                for img_name in img_name_list:
                    img = bpy.data.images[img_name]
                    img.asset_data.id_data.asset_generate_preview()  # 生成图像的预览图
                # 遍历所有材质
                #for mat in bpy.data.materials:
                    #if mat.asset_data != None:
                        #mat.asset_data.id_data.asset_generate_preview()  # 生成材质的预览图
                # 遍历所有图像
                #for img in bpy.data.images:
                    #if img.asset_data != None:
                        #img.asset_data.id_data.asset_generate_preview()  # 生成图像的预览图
                # 设置资产库
                #bpy.context.space_data.params.asset_library_reference = 'LOCAL'
            # 删除资产

            def Delete_Assets():
                mat_name_list = []
                img_name_list = []
                for asset in bpy.context.selected_assets:
                    name = asset.name
                    if asset.id_type == 'MATERIAL':
                        mat_name_list.append(name)
                    if asset.id_type == 'IMAGE':
                        img_name_list.append(name)
                for mat_name in mat_name_list:
                    mat = bpy.data.materials[mat_name]
                    bpy.context.blend_data.materials.remove(mat)    
                for img_name in img_name_list:
                    img = bpy.data.images[img_name]
                    bpy.context.blend_data.images.remove(img)
            # 预览资产

            def Browse_Asset():
                if bpy.context.id != None:        
                    id_type = bpy.context.id.id_type
                    asset_name = bpy.context.id.name             
                    if id_type == 'IMAGE':
                        img = bpy.data.images[asset_name]  
                        for window in bpy.context.window_manager.windows:
                            # 查找图像编辑器的区域
                            for area in window.screen.areas:
                                if area.type == 'IMAGE_EDITOR':
                                    # 切换到该区域，并设置当前图像
                                    for space in area.spaces:
                                        if space.type == 'IMAGE_EDITOR':
                                            space.image = img        
                    if id_type == 'MATERIAL':
                        view_layer = bpy.context.view_layer        
                        # 遍历场景中的所有物体
                        for obj in bpy.data.objects:
                            # 确保物体在当前视图层中
                            if obj.name in view_layer.objects and obj.type == 'MESH':
                                for index, mat_slot in enumerate(obj.material_slots):
                                    if mat_slot.name == asset_name:
                                        view_layer.objects.active = obj
                                        obj.active_material_index = index  # 设置当前材质索引
                                        break
            # 调用函数
            functions = {
                "Update_Assets": Update_Assets,
                "Refresh_Preview": Refresh_Preview,
                "Delete_Assets": Delete_Assets,
                "Browse_Asset": Browse_Asset,
            }
            functions[func_name]()
            context.window_manager.modal_handler_add(self)
            _20C05_running = True
            return {'RUNNING_MODAL'}


def sna_func_5B71E(layout_function, ):
    layout_function.separator(factor=1.0)
    col_25A96 = layout_function.column(heading='', align=True)
    col_25A96.alert = False
    col_25A96.enabled = (None != bpy.context.id)
    col_25A96.active = True
    col_25A96.use_property_split = False
    col_25A96.use_property_decorate = False
    col_25A96.scale_x = 1.0
    col_25A96.scale_y = 1.0
    col_25A96.alignment = 'Expand'.upper()
    col_25A96.operator_context = "INVOKE_DEFAULT" if True else "EXEC_DEFAULT"
    op = col_25A96.operator('sna.citation_relationship_07564', text=('相关' if (bpy.context.preferences.view.language == 'zh_HANS') else 'Related'), icon_value=string_to_icon('LONGDISPLAY'), emboss=True, depress=False)
    op.sna_func_name = 'Set_Tags'
    op = layout_function.operator('sna.modal_operator_20c05', text='3D', icon_value=string_to_icon('EYEDROPPER'), emboss=True, depress=False)
    op = layout_function.operator('sna.citation_relationship_07564', text='', icon_value=string_to_icon('PANEL_CLOSE'), emboss=True, depress=False)
    op.sna_func_name = 'Clear_Tags'
    layout_function.separator(factor=1.0)


def register():
    global _icons
    _icons = bpy.utils.previews.new()
    bpy.types.ASSETBROWSER_PT_metadata.prepend(sna_add_to_assetbrowser_pt_metadata_85850)
    bpy.types.ASSETBROWSER_MT_editor_menus.append(sna_add_to_assetbrowser_mt_editor_menus_0D928)
    bpy.types.ASSETBROWSER_MT_context_menu.prepend(sna_add_to_assetbrowser_mt_context_menu_FEED2)
    bpy.utils.register_class(SNA_OT_Rename_Mat_2148F)
    bpy.utils.register_class(SNA_PT_RENAME_PANEL_MAT_2D4F8)
    bpy.utils.register_class(SNA_OT_Rename_Img_A8C64)
    bpy.utils.register_class(SNA_PT_RENAME_PANEL_IMG_51A71)
    bpy.utils.register_class(SNA_OT_Process_Img_23Ad1)
    bpy.utils.register_class(SNA_OT_Operation_Asset_Fb945)
    bpy.types.VIEW3D_PT_tools_active.append(sna_add_to_view3d_pt_tools_active_6D39F)
    bpy.utils.register_class(SNA_OT_Divide_The_Area_76314)
    bpy.types.ASSETBROWSER_MT_editor_menus.prepend(sna_add_to_assetbrowser_mt_editor_menus_E5BD5)
    bpy.utils.register_class(SNA_OT_Material_Process_F7D34)
    bpy.utils.register_class(SNA_OT_Citation_Relationship_07564)
    bpy.utils.register_class(SNA_OT_Modal_Operator_20C05)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='File Browser', space_type='FILE_BROWSER')
    kmi = km.keymap_items.new('sna.operation_asset_fb945', 'SPACE', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.sna_func_name = 'Browse_Asset'
    addon_keymaps['943BF'] = (km, kmi)
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='Outliner', space_type='OUTLINER')
    kmi = km.keymap_items.new('sna.operation_asset_fb945', 'SPACE', 'PRESS',
        ctrl=False, alt=False, shift=False, repeat=False)
    kmi.properties.sna_func_name = 'Browse_Asset'
    addon_keymaps['A276C'] = (km, kmi)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    for km, kmi in addon_keymaps.values():
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.types.ASSETBROWSER_PT_metadata.remove(sna_add_to_assetbrowser_pt_metadata_85850)
    bpy.types.ASSETBROWSER_MT_editor_menus.remove(sna_add_to_assetbrowser_mt_editor_menus_0D928)
    bpy.types.ASSETBROWSER_MT_context_menu.remove(sna_add_to_assetbrowser_mt_context_menu_FEED2)
    bpy.utils.unregister_class(SNA_OT_Rename_Mat_2148F)
    bpy.utils.unregister_class(SNA_PT_RENAME_PANEL_MAT_2D4F8)
    bpy.utils.unregister_class(SNA_OT_Rename_Img_A8C64)
    bpy.utils.unregister_class(SNA_PT_RENAME_PANEL_IMG_51A71)
    bpy.utils.unregister_class(SNA_OT_Process_Img_23Ad1)
    bpy.utils.unregister_class(SNA_OT_Operation_Asset_Fb945)
    bpy.types.VIEW3D_PT_tools_active.remove(sna_add_to_view3d_pt_tools_active_6D39F)
    bpy.utils.unregister_class(SNA_OT_Divide_The_Area_76314)
    bpy.types.ASSETBROWSER_MT_editor_menus.remove(sna_add_to_assetbrowser_mt_editor_menus_E5BD5)
    bpy.utils.unregister_class(SNA_OT_Material_Process_F7D34)
    bpy.utils.unregister_class(SNA_OT_Citation_Relationship_07564)
    bpy.utils.unregister_class(SNA_OT_Modal_Operator_20C05)
