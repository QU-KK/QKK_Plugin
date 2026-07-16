# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2022, Alex Zhornyak

import bpy

from functools import partial

from ZenUV.utils.generic import ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE, ZUV_SPACE_TYPE
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.prop.common import get_combo_panel_order

from .trimsheet_utils import ZuvTrimsheetUtils
from .color_palette import ZUV_PT_3DV_ColorPresets, ZUV_PT_UV_ColorPresets

from ZenUV.ops.transform_sys.trim_batch_operators.directional_hotspot import (
    ZUV_PT_3DV_DirectionalHotspot, ZUV_PT_UV_DirectionalHotspot)
from ZenUV.ops.transform_sys.trim_batch_operators.selections import ZUV_OT_TrimSelectIslandsByTrimName
from ZenUV.ops.trimsheets.trimsheet_labels import TrimSheetLabels as TrsLabels
from ZenUV.ops.trimsheets.trimsheet_from_mesh import ZUV_OT_SetTrimWorldSize
from ZenUV.ops.trimsheets.trimsheet_ops import ZUV_OT_TrimsSetProps
from ZenUV.ops.trimsheets.trimsheet_preview import update_preview
from ZenUV.ico import icon_get
from ZenUV.utils.tests.system_operators import ZUV_OT_OpenPresetsFolder
from ZenUV.ui.tool.uv.uv_tool import ZuvUVWorkSpaceTool
from ZenUV.ui.tool.view3d_tool import Zuv3DVWorkSpaceTool
from ZenUV.utils.blender_zen_utils import getattr_for_repr, update_areas_in_all_screens
from ZenUV.utils.vlog import Log


_last_uv_tool = ''
_last_view3d_tool = ''


class ZuvBaseTrimsheetPanel():

    zen_icon_value = 'pn_Trimsheet'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    def draw(self, context: bpy.types.Context):
        layout = self.layout  # type: bpy.types.UILayout

        # predefined functions
        def do_draw_preset(layout: bpy.types.UILayout):
            row = layout.row(align=True)

            if ZuvTrimsheetUtils.isTrimsheetEditable(context):
                preset_menu_class = getattr(bpy.types, 'ZUV_MT_StoreTrimsheetPresets')
                row.menu("ZUV_MT_StoreTrimsheetPresets", text=preset_menu_class.bl_label)

                s_preset_name = preset_menu_class.bl_label

                op = row.operator("uv.zuv_add_trimsheet_preset", text="", icon="ADD")
                if s_preset_name and s_preset_name != preset_menu_class.default_label:
                    op.name = s_preset_name
                op = row.operator("uv.zuv_add_trimsheet_preset", text="", icon="REMOVE")
                op.remove_active = True
                row.operator(
                    ZUV_OT_OpenPresetsFolder.bl_idname,
                    icon=ZUV_OT_OpenPresetsFolder.get_icon_name(),
                    text='').preset_folder = ZuvTrimsheetUtils.TRIM_PRESET_SUBDIR
            else:
                row.alert = True
                row.separator()
                row.label(text="Trimsheet is readonly")

        # Prepare draw vars
        addon_prefs = get_prefs()

        p_scene = context.scene

        p_image = None
        p_data = None

        b_is_editmode = False
        b_is_UV = self.bl_space_type == 'IMAGE_EDITOR'
        if b_is_UV:
            b_is_editmode = p_scene.zen_uv.ui.uv_tool.mode in {'CREATE', 'RESIZE'}

        b_is_scenemode = addon_prefs.trimsheet.mode == 'SCENE'

        if b_is_scenemode:
            p_data = p_scene
        else:
            p_image = ZuvTrimsheetUtils.getActiveImage(context)
            p_data = p_image

        # HACK: we use this for linked images
        p_active_data = ZuvTrimsheetUtils.getActiveOverridedData(p_data, context)

        b_is_trimsheet_editable = ZuvTrimsheetUtils.isTrimsheetEditable(context)

        # Draw starts here ==>
        col_header = layout.column(align=True)
        row = col_header.row(align=True)
        row.prop(addon_prefs.trimsheet, 'mode', expand=True)

        p_mat_image = None
        p_act_mat = None
        if not b_is_UV and not b_is_scenemode:
            p_obj = context.active_object
            if p_obj:
                p_act_mat = p_obj.active_material
                if p_act_mat:
                    p_mat_image = p_act_mat.zen_uv.trimsheet_image

        if p_image is not None:
            col_header.separator(factor=0.5)
            row = col_header.row(align=True)
            box = row.box()
            r_line = box.row(align=True)
            r1 = r_line.row(align=True)
            r1.alert = p_mat_image is not None
            r1.label(text=p_image.name, icon='FILE_IMAGE')

            if p_act_mat is not None:
                r2 = r_line.row(align=True)
                r2.alignment = 'RIGHT'
                r2.popover(panel='ZUV_PT_PopupTrimsheetMaterial', text='', icon='PREFERENCES')
        else:
            if p_act_mat is not None:
                col_header.separator(factor=0.5)
                box = col_header.box()
                box.prop(p_act_mat.zen_uv, 'trimsheet_image', text='')

            if not b_is_scenemode:
                col_header.separator(factor=0.5)
                box = col_header.box()
                row = box.row(align=True)
                row.alignment = 'CENTER'
                row.label(text='No active image', icon='ERROR')

        if p_data is not None:
            col_header.separator(factor=0.5)
            do_draw_preset(col_header)

        p_tool_props = p_scene.zen_uv.ui.uv_tool if b_is_UV else p_scene.zen_uv.ui.view3d_tool

        def display_trim_preview(p_layout: bpy.types.UILayout):
            if p_image is not None:
                if not b_is_scenemode:

                    row = p_layout.row(align=True)
                    r1 = row.row(align=True)
                    r1.alignment = 'LEFT'
                    r1.separator(factor=1)
                    r1.prop(
                        p_tool_props, 'trim_preview_expanded',
                        icon='TRIA_DOWN' if p_tool_props.trim_preview_expanded else 'TRIA_RIGHT', emboss=False)

                    if p_tool_props.trim_preview_expanded:
                        r2 = row.row(align=True)
                        r2.alignment = 'RIGHT'
                        r2.prop(p_active_data, "use_fit_to_trim")
                        r2.operator("wm.zuv_trim_preview_update", icon='FILE_REFRESH', text='')

                        row = p_layout.row(align=True)
                        row.template_icon_view(p_active_data, "trimsheet_previews")

                        LITERAL_TRIM_UUIDS = "zenuv_trimsheet_uuds"
                        p_uuids = bpy.app.driver_namespace.get(LITERAL_TRIM_UUIDS, dict())
                        p_uuid = p_uuids.get(p_image.name, "")

                        b_need_update = False

                        if p_uuid != p_image.zen_uv.trimsheet_geometry_uuid:
                            p_uuids[p_image.name] = p_image.zen_uv.trimsheet_geometry_uuid
                            bpy.app.driver_namespace[LITERAL_TRIM_UUIDS] = p_uuids

                            b_need_update = True

                        # NOTE: we will check is it enough to use 'trimsheet_geometry_uuid'
                        # else:
                        #     b_need_update = not is_preview_valid_check(p_image)

                        if b_need_update:

                            def zenuv_update_preview(p_image):
                                try:
                                    update_preview(p_image)
                                    update_areas_in_all_screens(bpy.context)
                                except Exception as e:
                                    Log.error("UPDATE TRIM PREVIEW:", e)

                            bpy.app.timers.register(partial(zenuv_update_preview, p_image))

        if b_is_UV:
            row = layout.row(align=True)
            row.active = p_data is not None
            r1 = row.row(align=True)
            r1.alignment = 'LEFT'
            r1.prop(p_tool_props, 'display_trims', text='', icon='OVERLAY')

            is_tool_active = False
            p_tool_from_space = context.workspace.tools.from_space_image_mode('UV', create=False)
            if p_tool_from_space:
                is_tool_active = p_tool_from_space.idname == ZuvUVWorkSpaceTool.bl_idname

            display_trim_preview(layout)

            r2 = row.row(align=True)
            r2.enabled = p_tool_from_space is not None
            # NOTE: if trimsheet is linked we mark it as inactive but give an option to change tool mode,
            #       because it may written in base file and give artifacts
            r2.active = b_is_trimsheet_editable
            r2.alignment = 'RIGHT'

            b_is_create = is_tool_active and p_tool_props.mode == 'CREATE'
            op = r2.operator(
                'uv.zuv_activate_tool', depress=b_is_create,
                icon=ZuvTrimsheetUtils.icon_edit_mode_create, text='')
            op.mode = 'OFF' if b_is_create else 'CREATE'

            b_is_resize = is_tool_active and p_tool_props.mode == 'RESIZE'
            op = r2.operator(
                'uv.zuv_activate_tool', depress=b_is_resize,
                icon=ZuvTrimsheetUtils.icon_edit_mode_resize, text='')
            op.mode = 'OFF' if b_is_resize else 'RESIZE'

            if is_tool_active and not b_is_create:
                if p_tool_props.display_trims:
                    r1.prop(
                        p_tool_props, 'select_trim', text='',
                        icon='RESTRICT_SELECT_OFF' if p_tool_props.select_trim else 'RESTRICT_SELECT_ON')

            r1.popover(panel='ZUV_PT_TrimOverlayFilter', text='')
        else:
            p_tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
            is_tool_active = p_tool is not None and p_tool.idname == Zuv3DVWorkSpaceTool.bl_idname

            if is_tool_active:
                row = layout.row(align=True)
                row.active = p_data is not None
                r1 = row.row(align=True)
                r1.alignment = 'LEFT'
                r1.prop(p_tool_props, "display_trims_ex", text='', icon='OVERLAY')
                if p_tool_props.display_trims and not p_tool_props.enable_screen_selector:
                    r1.prop(
                        p_tool_props, 'select_trim', text='',
                        icon='RESTRICT_SELECT_OFF' if p_tool_props.select_trim else 'RESTRICT_SELECT_ON')
                r1.popover(panel='ZUV_PT_TrimOverlayFilter', text='')

            display_trim_preview(layout)

        if p_data is not None:

            row = layout.row(align=True)
            r1 = row.row(align=True)
            r1.alignment = 'LEFT'
            r1.separator(factor=1)
            r1.prop(
                p_tool_props, 'trim_list_expanded',
                icon='TRIA_DOWN' if p_tool_props.trim_list_expanded else 'TRIA_RIGHT', emboss=False)

            if p_tool_props.trim_list_expanded:

                row = layout.row()

                if b_is_editmode:
                    pass

                col = row.column()
                col.template_list(
                    "ZUV_UL_TrimsheetList",
                    "name",
                    p_data.zen_uv,
                    "trimsheet",
                    p_active_data,
                    "trimsheet_index_ui",
                    rows=7
                )

                col = row.column(align=True)
                col.operator('uv.zenuv_new_trim', text="", icon='ADD')
                col.operator('uv.zuv_trim_remove_ui', text="", icon='REMOVE')
                col.operator('uv.zuv_trim_duplicate', text="", icon='DUPLICATE')
                col.separator()

                col.menu(menu='ZUV_MT_TrimsheetMenu', text='', icon='DOWNARROW_HLT')
                col.separator()

                col.operator('uv.zuv_trim_move', text="", icon='TRIA_UP').direction = 'UP'
                col.operator('uv.zuv_trim_move', text="", icon='TRIA_DOWN').direction = 'DOWN'

                col.separator()
                col.operator('uv.zuv_trim_delete_all', text="", icon='TRASH')
        else:
            pass


class ZUV_PT_3DV_SubTransformInTrim(bpy.types.Panel):
    """  Zen Transform Islands in Trim 3dv Subpanel """
    bl_label = "Trim Operators"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    # bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_Trimsheet"

    @classmethod
    def poll(self, context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mode'
        return ''

    def draw(self, context):
        from ZenUV.ops.transform_sys.trim_batch_operators.system import draw_trim_batch_ops
        from ZenUV.ops.transform_sys.tr_ui import draw_trim_transform_panel
        draw_trim_transform_panel(self, is_uv=False)
        draw_trim_batch_ops(self, context, self.layout)


class ZUV_PT_UVL_SubTransformInTrim(bpy.types.Panel):
    """  Zen Transform Islands in Trim UVL Subpanel """
    bl_label = "Trim Operators"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    # bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Trimsheet"

    poll = ZUV_PT_3DV_SubTransformInTrim.poll

    poll_reason = ZUV_PT_3DV_SubTransformInTrim.poll_reason

    def draw(self, context):
        from ZenUV.ops.transform_sys.trim_batch_operators.system import draw_trim_batch_ops
        from ZenUV.ops.transform_sys.tr_ui import draw_trim_transform_panel
        draw_trim_transform_panel(self, is_uv=True)
        draw_trim_batch_ops(self, context, self.layout)


class ZUV_PT_UVL_Trimsheet(ZuvBaseTrimsheetPanel, bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_label = TrsLabels.PANEL_TRSH_LABEL
    bl_context = ''
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('UV', 'ZUV_PT_UVL_Trimsheet')

    @classmethod
    def poll(cls, context: bpy.types.Context):
        addon_prefs = get_prefs()
        return addon_prefs.float_UV_panels.enable_pt_trimsheet

    def draw_header(self, context: bpy.types.Context):
        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if p_trimsheet:
            n_count = len(p_trimsheet)
            if n_count > 0:
                p_sel_indices = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)
                n_sel_count = len(p_sel_indices)
                layout = self.layout
                layout.label(text=f'{n_sel_count} of {n_count}')


class ZUV_PT_3DV_Trimsheet(ZuvBaseTrimsheetPanel, bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = TrsLabels.PANEL_TRSH_LABEL
    bl_context = ''
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_3DV_Trimsheet')

    @classmethod
    def poll(cls, context: bpy.types.Context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_trimsheet

    draw_header = ZUV_PT_UVL_Trimsheet.draw_header


class ZUV_PT_3DV_SubTrimsheetTransform(bpy.types.Panel):
    """  Zen Trimsheet Transform Subpanel """
    bl_label = "Transform Trims"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_Trimsheet"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == 'OBJECT' and ZuvTrimsheetUtils.getTrimsheetSelectedCount(context) > 0

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'OBJECT':
            return 'Available in Object Mode'
        if ZuvTrimsheetUtils.getTrimsheetSelectedCount(context) == 0:
            return 'No Selected Trims'
        return ''

    def draw(self, context):
        from ZenUV.ops.trimsheets.trimsheet_transform import draw_trims_transform_ui_tools
        draw_trims_transform_ui_tools(context, self.layout)


class ZUV_PT_UVL_SubTrimsheetTransform(bpy.types.Panel):
    """  Zen Trimsheet UV Transform Subpanel """
    bl_label = ZUV_PT_3DV_SubTrimsheetTransform.bl_label
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Trimsheet"

    poll = ZUV_PT_3DV_SubTrimsheetTransform.poll

    draw = ZUV_PT_3DV_SubTrimsheetTransform.draw

    poll_reason = ZUV_PT_3DV_SubTrimsheetTransform.poll_reason


class ZUV_PT_3DV_SubTrimSettings(bpy.types.Panel):
    """  Zen Trimsheet Transform Subpanel """
    bl_label = "Trim Settings"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_Trimsheet"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
        return p_trim is not None

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if not cls.poll(context):
            return 'No Active Trim'
        return ''

    def draw_header(self, context):
        layout = self.layout

        addon_prefs = get_prefs()

        t_expanded_panels = {}
        if addon_prefs.combo_panel.expanded:
            t_expanded_panels = eval(addon_prefs.combo_panel.expanded)

        panel_id = self.bl_rna.identifier

        b_is_floating = isinstance(self, (ZUV_PT_3DV_SubTrimSettings, ZUV_PT_UVL_SubTrimSettings))
        if b_is_floating or t_expanded_panels.get(panel_id, False):

            b_is_imagemode = addon_prefs.trimsheet.mode == 'IMAGE'
            if b_is_imagemode:
                row = layout.row(align=False)
                row.ui_units_x = 1

                b_is_pixels = addon_prefs.trimsheet.size_mode == 'PIXEL'
                op = row.operator('wm.context_set_enum', text='px', depress=b_is_pixels)
                op.data_path = 'preferences.addons["ZenUV"].preferences.trimsheet.size_mode'
                op.value = 'PERCENT' if b_is_pixels else 'PIXEL'

    def draw(self, context):
        p_trim_data = ZuvTrimsheetUtils.getActiveTrimData(context)
        if p_trim_data is not None:

            act_idx, p_trim, p_trimsheet = p_trim_data
            addon_prefs = get_prefs()

            layout = self.layout

            b_is_scenemode = addon_prefs.trimsheet.mode == 'SCENE'

            sel_indices = ZuvTrimsheetUtils.getTrimsheetSelectedAndActiveIndices(p_trimsheet)
            b_is_multiselection = len(sel_indices) >= 2

            grid = layout.grid_flow(align=True, columns=2)
            grid.alert = p_trim.width == 0 or p_trim.height == 0

            p_props = (
                {
                    'left': 'X',
                    'bottom': 'Y',
                    'width': 'W',
                    'height': 'H',
                }
                if b_is_scenemode or addon_prefs.trimsheet.size_mode == 'PERCENT'
                else
                {
                    'left_px': 'X',
                    'bottom_px': 'Y',
                    'width_px': 'W',
                    'height_px': 'H',
                }
                )

            for s_prop, s_text in p_props.items():
                if b_is_multiselection:
                    p_act_prop_val = getattr_for_repr(p_trim, s_prop)

                    b_all_equal = all(
                        getattr_for_repr(p_trimsheet[idx], s_prop) == p_act_prop_val
                        for idx in sel_indices
                        if idx != act_idx)

                    r = grid.row(align=True)
                    r.active = b_all_equal
                    r.prop(p_trim, s_prop, text=s_text)
                    op = r.operator(
                        ZUV_OT_TrimsSetProps.bl_idname, text='',
                        icon='KEYFRAME_HLT' if b_all_equal else 'KEYFRAME')
                    op.data_path = s_prop
                    op.data_value = repr(getattr_for_repr(p_trim, s_prop))
                    op.mode = 'SINGLE_PARAM'
                else:
                    grid.prop(p_trim, s_prop, text=s_text)


class ZUV_PT_UVL_SubTrimSettings(bpy.types.Panel):
    """  Zen Trimsheet UV Transform Subpanel """
    bl_label = ZUV_PT_3DV_SubTrimSettings.bl_label
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Trimsheet"

    poll = ZUV_PT_3DV_SubTrimSettings.poll

    poll_reason = ZUV_PT_3DV_SubTrimSettings.poll_reason

    draw = ZUV_PT_3DV_SubTrimSettings.draw

    draw_header = ZUV_PT_3DV_SubTrimSettings.draw_header


# Do not delete. It is required for debugging.
class ZUV_PT_3DV_SubTrimsheetTransformAdvanced(bpy.types.Panel):
    """  Zen Trimsheet Transform Subpanel 3DV """
    bl_label = "Advanced"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_SubTrimsheetTransform"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.getTrimsheetOwner(context) is not None

    def draw(self, context):
        from .trimsheet_transform import draw_trims_transform_operators
        draw_trims_transform_operators(context, self.layout)


# Do not delete. It is required for debugging.
class ZUV_PT_UVL_SubTrimsheetTransformAdvanced(bpy.types.Panel):
    """  Zen Trimsheet Transform Subpanel UV """
    bl_label = ZUV_PT_3DV_SubTrimsheetTransformAdvanced.bl_label
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_SubTrimsheetTransform"

    poll = ZUV_PT_3DV_SubTrimsheetTransformAdvanced.poll

    draw = ZUV_PT_3DV_SubTrimsheetTransformAdvanced.draw


class ZUV_PT_3DV_SubTrimsheetAdvanced(bpy.types.Panel):
    """  Zen Trimsheet Transform Subpanel """
    bl_label = "Advanced Settings"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_SubTrimSettings"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.getTrimsheetOwner(context) is not None

    def draw(self, context: bpy.types.Context):

        p_trim_data = ZuvTrimsheetUtils.getActiveTrimData(context)
        if p_trim_data is not None:

            from .trimsheet import ZuvTrimsheetGroup
            p_trim: ZuvTrimsheetGroup
            act_idx, p_trim, p_trimsheet = p_trim_data

            t_filtered_props = {
                'selected',
                'uuid',
                'world_position'
            }

            layout = self.layout

            row_multi_adv = None

            # DEBUG #
            # layout.label(text=f'ID: {p_trim.get_int32_id()}')
            # layout.label(text=f'UUID: {p_trim.uuid}')

            sel_indices = ZuvTrimsheetUtils.getTrimsheetSelectedAndActiveIndices(p_trimsheet)
            b_is_multiselection = len(sel_indices) >= 2
            b_all_tags_equal = False
            if b_is_multiselection:
                # ??? TODO: maybe better to see in header, but how to pass data ???
                # row_multi_adv = layout.row(align=True)
                # row_multi_adv.alignment = 'RIGHT'

                def fn_skip_not_tags(it_trim, inst, attr):
                    if inst == it_trim and attr not in {'tags', 'tag_index'}:
                        return True
                    return False

                p_dict = p_trim.to_dict(fn_skip_prop=partial(fn_skip_not_tags, p_trim))

                b_all_tags_equal = all(
                    p_dict == p_trimsheet[idx].to_dict(fn_skip_prop=partial(fn_skip_not_tags, p_trimsheet[idx]))
                    for idx in sel_indices if idx != act_idx)

            col = layout.column(align=False)
            col.use_property_split = True

            b_all_single_equal = True

            addon_prefs = get_prefs()

            t_group = {
                "text_align_expanded": (
                    [
                        'text_align',
                        'text_offset',
                        'text_offset_mode'
                    ],
                    lambda: addon_prefs.trimsheet.text_align_style == 'USER'
                )
            }

            for s_prop in p_trim.get_common_props(skipped=t_filtered_props):
                b_skip_property = False
                for s_group, group_data in t_group.items():
                    if s_prop in group_data[0]:
                        group_idx = group_data[0].index(s_prop)

                        # NOTE: check by disable-enable property
                        b_skip_property = not group_data[1]()

                        if not b_skip_property:
                            # NOTE: check by expanded-collapsed
                            b_expanded = getattr(addon_prefs.trimsheet, s_group)
                            b_skip_property = not b_expanded

                            if group_idx == 0:
                                r = layout.row(align=True)
                                r.alignment = 'LEFT'

                                r.separator()
                                r.separator()
                                r.separator()

                                r.prop(
                                    addon_prefs.trimsheet, s_group,
                                    icon='TRIA_DOWN' if b_expanded else 'TRIA_RIGHT',
                                    emboss=False)
                                col = layout.column(align=False)
                                col.use_property_split = True

                        break

                if b_skip_property:
                    continue

                if b_is_multiselection:
                    p_act_prop_val = getattr_for_repr(p_trim, s_prop)
                    b_all_equal = all(
                        getattr_for_repr(p_trimsheet[idx], s_prop) == p_act_prop_val
                        for idx in sel_indices
                        if idx != act_idx)
                    if not b_all_equal:
                        b_all_single_equal = False
                    r = col.row(align=True)
                    r.active = b_all_equal
                    r.prop(p_trim, s_prop)
                    r.separator()
                    op = r.operator(
                        ZUV_OT_TrimsSetProps.bl_idname, text='',
                        icon='KEYFRAME_HLT' if b_all_equal else 'KEYFRAME')
                    op.data_path = s_prop
                    op.data_value = repr(getattr_for_repr(p_trim, s_prop))
                    op.mode = 'SINGLE_PARAM'
                else:
                    col.prop(p_trim, s_prop)

            if row_multi_adv:  # TODO: NOT USED NOW, maybe later will be moved to header
                b_all_advanced_equal = b_all_single_equal and b_all_tags_equal
                op = row_multi_adv.operator(
                    ZUV_OT_TrimsSetProps.bl_idname, text='',
                    icon='KEYFRAME_HLT' if b_all_advanced_equal else 'KEYFRAME')
                op.mode = 'ADVANCED_PARAMS'

            row = layout.row()
            col = row.column()
            col.template_list(
                "ZUV_UL_TrimTagsList",
                "name",
                p_trim,
                "tags",
                p_trim,
                "tag_index",
                rows=5
            )

            col = row.column(align=True)

            if b_is_multiselection:
                op = col.operator(
                    ZUV_OT_TrimsSetProps.bl_idname, text='',
                    emboss=True,
                    icon='KEYFRAME_HLT' if b_all_tags_equal else 'KEYFRAME')
                op.mode = 'TAGS'
                col.separator()

            col.operator('uv.zuv_trim_tag_add', text="", icon='ADD')
            col.operator('uv.zuv_trim_tag_remove', text="", icon='REMOVE')
            col.separator()

            r = col.row(align=True)
            r.enabled = p_trim.get_active_tag() is not None
            r.menu(menu='ZUV_MT_TrimTagMenu', text='', icon='DOWNARROW_HLT')
            col.separator()

            col.operator('uv.zuv_trim_tag_move', text="", icon='TRIA_UP').direction = 'UP'
            col.operator('uv.zuv_trim_tag_move', text="", icon='TRIA_DOWN').direction = 'DOWN'

            col.separator()
            col.operator('uv.zuv_trim_tag_delete_all', text="", icon='TRASH')


class ZUV_PT_UVL_SubTrimsheetAdvanced(bpy.types.Panel):
    """  Zen Trimsheet UV Transform Subpanel """
    bl_label = ZUV_PT_3DV_SubTrimsheetAdvanced.bl_label
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_SubTrimSettings"

    poll = ZUV_PT_3DV_SubTrimsheetAdvanced.poll

    draw = ZUV_PT_3DV_SubTrimsheetAdvanced.draw


class ZUV_PT_3DV_SubTrimsheetImport(bpy.types.Panel):
    """  Zen Trimsheet Import Subpanel """
    bl_label = "Import-Export"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_Trimsheet"

    def draw(self, context):
        layout = self.layout
        p_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_owner:
            from ZenUV.ops.trimsheets.trimsheet import ZUV_MT_TrimsheetMenu
            from ZenUV.ops.transform_sys.trim_batch_operators.trim_to_mesh import ZUV_OT_TrimToMesh

            b_is_menu = isinstance(self, ZUV_MT_TrimsheetMenu)
            if b_is_menu:
                grid = layout.column(align=True)
            else:
                grid = layout.grid_flow(align=True, columns=2)

            grid.operator('uv.zuv_copy_trimsheet')
            grid.operator('uv.zuv_paste_trimsheet')

            if b_is_menu:
                layout.separator()

            col = layout.column(align=True)

            col.operator('wm.zuv_trim_batch_rename')
            col.separator()

            if context.area.type == 'VIEW_3D':
                col.operator(ZUV_OT_TrimToMesh.bl_idname)
                col.separator()

            col.operator(ZUV_OT_SetTrimWorldSize.bl_idname)
            col.operator(ZUV_OT_TrimSelectIslandsByTrimName.bl_idname)
            col.separator()

            col.menu(menu="ZUV_MT_TrimAdd")
            col.separator()

            col.menu(menu='ZUV_MT_TrimImport', icon='IMPORT')
            col.menu(menu='ZUV_MT_TrimExport', icon='EXPORT')
        else:
            if ZuvTrimsheetUtils.isImageEditorSpace(context):
                op = layout.operator('wm.zuv_trim_import_svg', text='Import SVG with Image')
                op.load_image = True


class ZUV_PT_UVL_SubTrimsheetImport(bpy.types.Panel):
    """  Zen Trimsheet UV Import Subpanel """
    bl_label = ZUV_PT_3DV_SubTrimsheetImport.bl_label
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Trimsheet"

    draw = ZUV_PT_3DV_SubTrimsheetImport.draw


class ZUV_PT_PopupTrimsheetMaterial(bpy.types.Panel):
    bl_idname = "ZUV_PT_PopupTrimsheetMaterial"
    bl_label = 'Trimsheet Material'
    bl_context = "material"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        layout = self.layout

        p_obj = context.active_object
        if p_obj:
            p_act_mat = p_obj.active_material
            if p_act_mat:
                col = layout.column(align=True)
                col.label(text=p_act_mat.zen_uv.bl_rna.properties['trimsheet_image'].name)
                col.prop(p_act_mat.zen_uv, 'trimsheet_image', text='')


trimsheet_parented_panels = [
    ZUV_PT_3DV_SubTransformInTrim,
    ZUV_PT_UVL_SubTransformInTrim,

    ZUV_PT_3DV_SubTrimSettings,
    ZUV_PT_UVL_SubTrimSettings,

    # Disabled: present in Menu
    # ZUV_PT_3DV_SubTrimsheetImport,
    # ZUV_PT_UVL_SubTrimsheetImport,

    ZUV_PT_3DV_SubTrimsheetAdvanced,
    ZUV_PT_UVL_SubTrimsheetAdvanced,

    ZUV_PT_3DV_SubTrimsheetTransform,
    ZUV_PT_UVL_SubTrimsheetTransform,

    ZUV_PT_3DV_ColorPresets,
    ZUV_PT_UV_ColorPresets,

    ZUV_PT_3DV_DirectionalHotspot,
    ZUV_PT_UV_DirectionalHotspot

    # Do not delete. It is required for debugging.
    # ZUV_PT_3DV_SubTrimsheetTransformAdvanced,
    # ZUV_PT_UVL_SubTrimsheetTransformAdvanced
]
