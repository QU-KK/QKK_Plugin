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

# Copyright 2024, Valeriy Yatsenko

import bpy

from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.generic import ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE, ZUV_SPACE_TYPE, ZUV_CONTEXT
from ZenUV.prop.common import get_combo_panel_order
from ZenUV.ico import icon_get
from ZenUV.prop.zuv_preferences import get_prefs


def draw_stack_in_favourites(layout):
    from ZenUV.stacks.stacks import ZUV_OT_Stack_Similar, ZUV_OT_Unstack
    row = layout.row(align=True)
    row.operator(ZUV_OT_Stack_Similar.bl_idname, icon_value=icon_get("stack_32"), text="Stack")
    row.operator(ZUV_OT_Unstack.bl_idname, text="Unstack")


def draw_stack(self, context):
    ''' @Draw Stack '''
    from ZenUV.stacks.stacks import ZUV_OT_Stack_Similar, ZUV_OT_Unstack
    from ZenUV.ops.transform_sys.tr_align import ZUV_OT_SimpleStack, ZUV_OT_SimpleUnstack

    layout = self.layout

    col = layout.column(align=True)

    row = col.row(align=True)
    row.operator(ZUV_OT_Stack_Similar.bl_idname, text="Stack All", icon_value=icon_get(ZuvLabels.ZEN_STACK_ICO)).selected = False

    row.popover(panel="STACK_PT_Properties", text="", icon="PREFERENCES")

    row = col.row(align=True)
    row.operator(ZUV_OT_Stack_Similar.bl_idname, text="Selected").selected = True
    row.operator(ZUV_OT_SimpleStack.bl_idname, text="Simple")

    col = layout.column(align=True)

    col.operator(ZUV_OT_Unstack.bl_idname, text="Unstack All").UnstackMode = 'GLOBAL'
    row = col.row(align=True)
    row.operator(ZUV_OT_Unstack.bl_idname, text="Selected").UnstackMode = 'SELECTED'
    row.operator(ZUV_OT_SimpleUnstack.bl_idname, text="Simple")


def draw_stack_tools(self, context):
    ''' @Draw Stack Tools '''
    from ZenUV.zen_checker.check_utils import ZUV_OT_IslandCounter

    layout = self.layout
    box = layout.box()
    box.label(text="Tools:")
    col = box.column(align=False)
    row = col.row(align=True)
    row.operator("uv.zenuv_copy_param", icon="COPYDOWN")
    row.operator("uv.zenuv_paste_param", icon="PASTEDOWN")

    col.operator(ZUV_OT_IslandCounter.bl_idname).show_selected_only = True


def draw_substack(layout: bpy.types.UILayout, context: bpy.types.Context):
    ''' @Draw Stacks Sub Panel '''
    from ZenUV.zen_checker.check_utils import draw_checker_display_items, t_draw_stack_modes

    draw_checker_display_items(layout, context, t_draw_stack_modes)

    col = layout.column(align=True)
    for k in ('PRIMARIES', 'REPLICAS', 'SINGLES'):
        row = col.row(align=True)
        op = row.operator("uv.zenuv_select_stack", text=k.title(), icon="RESTRICT_SELECT_OFF")
        op.mode = k


class ZUV_PT_UVL_Stack(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_idname = "ZUV_PT_UVL_Stack"
    bl_label = ZuvLabels.PANEL_STACK_LABEL
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('UV', 'ZUV_PT_UVL_Stack')

    zen_icon_value = 'pn_Stack'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_UV_panels.enable_pt_stack and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit Mode'

    def draw(self, context):
        draw_stack(self, context)
        draw_stack_tools(self, context)


class ZUV_PT_Stack(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_idname = "ZUV_PT_Stack"
    bl_label = ZuvLabels.PANEL_STACK_LABEL
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_Stack')
    # bl_options = {'DEFAULT_CLOSED'}

    zen_icon_value = 'pn_Stack'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_stack and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context: bpy.types.Context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit Mode'

    def draw(self, context):
        draw_stack(self, context)
        draw_stack_tools(self, context)


class ZUV_PT_3DV_DisplayAndSelect(bpy.types.Panel):
    bl_label = 'Display & Select'
    bl_context = ZUV_CONTEXT
    bl_space_type = "VIEW_3D"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    # bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_Stack"

    def draw_header(self, context: bpy.types.Context):
        layout = self.layout

        layout.popover(panel='STACK_PT_DrawProperties', text='', icon='PREFERENCES')

    def draw(self, context):
        draw_substack(self.layout, context)
        pass


class ZUV_PT_UVL_DisplayAndSelect(bpy.types.Panel):
    bl_label = 'Display & Select'
    bl_context = ZUV_CONTEXT
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    # bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Stack"

    draw_header = ZUV_PT_3DV_DisplayAndSelect.draw_header

    draw = ZUV_PT_3DV_DisplayAndSelect.draw
