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

# Copyright 2023, Valeriy Yatsenko, Alex Zhornyak

import bpy

from ZenUV.utils.generic import (
    ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE,
    ZUV_SPACE_TYPE)
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.ico import icon_get
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.prop.common import get_combo_panel_order


def draw_select(self, context: bpy.types.Context):
    ''' @Draw Select '''
    from .select import (
        ZUV_OT_SelectHalf, ZUV_OT_SelectEdgeByCondition,
        ZUV_OT_SelectLinkedLoops, ZUV_OT_UVSyncSelect,
        ZUV_OT_Select_OpenEdges, ZUV_OT_SelectEdgesByDirection,
        ZUV_OT_Select_UV_Borders, ZUV_OT_SelectFacesLessOnePixel,
        ZUV_OT_SelectByUvArea, ZUV_OT_GrabSelectedArea,
        ZUV_OT_Select_SplitsEdges, ZUV_OT_SelectFacesByNormal)
    from .select_islands import (
        ZUV_OT_FilterIslandsByProperty, ZUV_OP_SelectHoledIslands,
        ZUV_OP_SelectIslandByDirection, ZUV_OT_Select_QuadedIslands,
        ZUV_OT_SelectInTile, ZUV_OT_Select_UV_Island)
    from ZenUV.ops.operators import (
        ZUV_OT_SelectSeams, ZUV_OT_SelectSharp,
        ZUV_OT_Select_Loop, ZUV_OT_SelectFlipped,
        ZUV_OT_Select_UV_Overlap, ZUV_OT_Isolate_Island,
        ZUV_OT_Isolate_Part, ZUV_OT_SelectSelfIntersecting)
    from ZenUV.stacks.stacks import ZUV_OT_Select_Similar
    from ZenUV.zen_checker.stretch_map import ZUV_OT_SelectStretchedFaces

    addon_prefs = get_prefs()

    layout: bpy.types.UILayout = self.layout
    main_col = layout.column(align=True)

    b_is_uv_area = context.area.type == 'IMAGE_EDITOR'

    def fn_create_body(p_layout: bpy.types.UILayout):
        return p_layout.column(align=True)

    box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(
        main_col, "expand_select_sys_islands", fn_create_body=fn_create_body)
    if box:
        col = box.column(align=True)

        col.operator(ZUV_OT_Select_UV_Island.bl_idname, icon_value=icon_get('select'), text=ZUV_OT_Select_UV_Island.bl_zen_short_name)
        grid = col.grid_flow(row_major=True, align=True, columns=2)

        grid.operator(ZUV_OT_Select_UV_Overlap.bl_idname, text=ZUV_OT_Select_UV_Overlap.bl_zen_short_name)
        grid.operator(ZUV_OT_SelectFlipped.bl_idname, text=ZUV_OT_SelectFlipped.bl_zen_short_name)

        grid.operator(ZUV_OT_Select_QuadedIslands.bl_idname, text=ZUV_OT_Select_QuadedIslands.bl_zen_short_name)
        grid.operator(ZUV_OP_SelectHoledIslands.bl_idname, text=ZUV_OP_SelectHoledIslands.bl_zen_short_name)

        grid.operator(ZUV_OT_Select_Similar.bl_idname, text=ZUV_OT_Select_Similar.bl_zen_short_name)
        grid.operator(ZUV_OT_SelectInTile.bl_idname)

        col.operator(ZUV_OP_SelectIslandByDirection.bl_idname, text=ZUV_OP_SelectIslandByDirection.bl_zen_short_name)

        if b_is_uv_area:
            col.operator(ZUV_OT_FilterIslandsByProperty.bl_idname)

    box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(
        main_col, "expand_select_sys_faces", fn_create_body=fn_create_body)
    if box:
        col = box.column(align=True)

        col.operator(ZUV_OT_SelectStretchedFaces.bl_idname, text=ZUV_OT_SelectStretchedFaces.bl_zen_short_name)
        col.operator(ZUV_OT_SelectSelfIntersecting.bl_idname, text=ZUV_OT_SelectSelfIntersecting.bl_label.replace("Select ", ""))

        row = col.row(align=True)
        row.operator(ZUV_OT_SelectByUvArea.bl_idname)
        row.operator(ZUV_OT_GrabSelectedArea.bl_idname, icon='IMPORT', text='')

        # Zero Area
        ot = col.operator(ZUV_OT_SelectByUvArea.bl_idname, text='Zero Area Faces')
        ot.mode = 'FACE'
        ot.clear_selection = True
        ot.condition = 'ZERO'
        ot.treshold = 0.0

        if context.area.type == 'VIEW_3D':
            col.operator(ZUV_OT_SelectFacesByNormal.bl_idname, text=ZUV_OT_SelectFacesByNormal.bl_zen_short_name)

        if b_is_uv_area:
            col.operator(ZUV_OT_SelectFacesLessOnePixel.bl_idname, text=ZUV_OT_SelectFacesLessOnePixel.bl_zen_short_name)

    box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(
        main_col, "expand_select_sys_edges", fn_create_body=fn_create_body)
    if box:
        col = box.column(align=True)
        grid = col.grid_flow(row_major=True, align=True, columns=2)

        grid.operator(ZUV_OT_SelectSeams.bl_idname, text=ZUV_OT_SelectSeams.bl_zen_short_name)
        grid.operator(ZUV_OT_SelectSharp.bl_idname, text=ZUV_OT_SelectSharp.bl_zen_short_name)

        grid.operator(ZUV_OT_Select_UV_Borders.bl_idname, text=ZUV_OT_Select_UV_Borders.bl_zen_short_name)
        grid.operator(ZUV_OT_Select_OpenEdges.bl_idname, text=ZUV_OT_Select_OpenEdges.bl_zen_short_name)

        col.operator(ZUV_OT_Select_SplitsEdges.bl_idname, text=ZUV_OT_Select_SplitsEdges.bl_zen_short_name)
        col.operator(ZUV_OT_SelectEdgeByCondition.bl_idname, text=ZUV_OT_SelectEdgeByCondition.bl_zen_short_name)

        if ZenPolls.version_since_3_2_0:
            col.operator(ZUV_OT_SelectEdgesByDirection.bl_idname, text=ZUV_OT_SelectEdgesByDirection.bl_zen_short_name)

    box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(
        main_col, "expand_select_sys_loops", fn_create_body=fn_create_body)
    if box:
        col = box.column(align=True)
        col.operator(ZUV_OT_UVSyncSelect.bl_idname, depress=context.scene.tool_settings.use_uv_select_sync)

        if b_is_uv_area:
            col.operator(ZUV_OT_SelectLinkedLoops.bl_idname)

    box: bpy.types.UILayout = addon_prefs.op_addon_props.prepare_layout_panel(
        main_col, "expand_select_sys_misc", fn_create_body=fn_create_body)
    if box:
        col = box.column(align=True)

        row = col.row(align=True)
        row.operator(ZUV_OT_Select_Loop.bl_idname, text=ZUV_OT_Select_Loop.bl_zen_short_name)
        row.operator(ZUV_OT_SelectHalf.bl_idname, text='Half')

        col.separator()

        col.operator(ZUV_OT_Isolate_Island.bl_idname)
        col.operator(ZUV_OT_Isolate_Part.bl_idname)


class ZUV_PT_Select(bpy.types.Panel):

    bl_idname = "ZUV_PT_Select"
    bl_label = 'Select'
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_Select')

    zen_icon_value = 'pn_Select'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_select and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit Mode'

    def draw(self, context):
        draw_select(self, context)


class ZUV_PT_UVL_Select(bpy.types.Panel):

    bl_idname = "ZUV_PT_UVL_Select"
    bl_label = 'Select'
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('UV', 'ZUV_PT_UVL_Select')

    get_icon = ZUV_PT_Select.get_icon

    poll = ZUV_PT_Select.poll

    combo_poll = ZUV_PT_Select.combo_poll

    poll_reason = ZUV_PT_Select.poll_reason

    draw = ZUV_PT_Select.draw
