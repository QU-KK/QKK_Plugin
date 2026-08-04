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

# Copyright 2024, Alex Zhornyak, Valeriy Yatsenko

import bpy

from ZenUV.utils.adv_generic_ui_list import zenuv_draw_ui_list
from ZenUV.ico import zenuv_tool_transform_icon
from ZenUV.utils.vlog import Log


def get_keymap():
    km = [
        ("wm.context_toggle_enum",
            {"type": "SPACE", "value": "PRESS", "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.tr_gizmo_mode'), ("value_1", "TRANSFORM"), ("value_2", "SETUP")]}),

        ("uv.zenuv_tool_transform_enum",
            {"type": "G", "value": "PRESS", "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.tr_gizmo_event_mode'), ("value", "EVENT_MOVE")]}),
        ("uv.zenuv_tool_transform_enum",
            {"type": "G", "value": "RELEASE", "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.tr_gizmo_event_mode'), ("value", "DEFAULT")]}),

        ("uv.zenuv_tool_transform_enum",
            {"type": "R", "value": "PRESS", "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.tr_gizmo_event_mode'), ("value", "EVENT_ROTATE")]}),
        ("uv.zenuv_tool_transform_enum",
            {"type": "R", "value": "RELEASE", "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.tr_gizmo_event_mode'), ("value", "DEFAULT")]}),

        ("uv.zenuv_tool_transform_enum",
            {"type": "S", "value": "PRESS", "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.tr_gizmo_event_mode'), ("value", "EVENT_SCALE")]}),
        ("uv.zenuv_tool_transform_enum",
            {"type": "S", "value": "RELEASE", "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.tr_gizmo_event_mode'), ("value", "DEFAULT")]}),

        ("uv.zenuv_tool_transform_handle_click",
            {"type": "LEFTMOUSE", "value": "DOUBLE_CLICK", "ctrl": False, "shift": False},
            {"properties": [("mode", 'DEFAULT'), ("handle_action", "NONE")]}),
        ("uv.zenuv_tool_transform_handle_click",
            {"type": "LEFTMOUSE", "value": "DOUBLE_CLICK", "ctrl": True, "shift": False},
            {"properties": [("mode", 'COMMAND'), ("handle_action", "NONE")]}),
    ]

    if bpy.app.version < (3, 2, 0):
        select_km = [
            ("uv.select_box", {"type": 'EVT_TWEAK_L', "value": 'ANY', "ctrl": False, "shift": False},
                {"properties": [("wait_for_input", False)]}),
            ("uv.select_box", {"type": 'EVT_TWEAK_L', "value": 'ANY', "ctrl": True, "shift": False},
                {"properties": [("mode", 'SUB'), ("wait_for_input", False)]}),
            ("uv.select_box", {"type": 'EVT_TWEAK_L', "value": 'ANY', "ctrl": False, "shift": True},
                {"properties": [("mode", 'ADD'), ("wait_for_input", False)]}),
        ]
    elif bpy.app.version < (3, 3, 0):
        select_km = [
            ("uv.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": False, "shift": False},
                {"properties": [("wait_for_input", False)]}),
            ("uv.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": True, "shift": False},
                {"properties": [("mode", 'SUB'), ("wait_for_input", False)]}),
            ("uv.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": False, "shift": True},
                {"properties": [("mode", 'ADD'), ("wait_for_input", False)]}),
        ]
    else:
        select_km = []

    return tuple(km + select_km)


class ZuvUVTransformWorkSpaceTool(bpy.types.WorkSpaceTool):
    bl_space_type = 'IMAGE_EDITOR'
    bl_context_mode = 'UV'

    # The prefix of the idname should be add-on name.
    bl_idname = "zenuv.uv_transform_tool"
    bl_idname_fallback = 'builtin.select_box'
    bl_label = 'Zen UV Touch'
    bl_description = 'ZenUV touchable transform tool'
    bl_icon = zenuv_tool_transform_icon()
    bl_keymap = get_keymap()
    bl_widget = '' if bpy.app.version < (3, 3, 0) else 'ZUV_GGT_UVTransformGizmo'

    @classmethod
    def is_workspace_tool_active(cls, context: bpy.types.Context):
        try:
            _id = getattr(context.workspace.tools.from_space_image_mode('UV', create=False), 'idname', None)
            return isinstance(_id, str) and _id == cls.bl_idname
        except Exception as e:
            Log.error("TRANSFORM TOOL:", e)
        return False

    def draw_settings(context: bpy.types.Context, layout: bpy.types.UILayout, tool):
        from ZenUV.prop.scene_ui_props import ZUV_UVToolProps

        wm = context.window_manager

        not_header = context.region.type != 'TOOL_HEADER'

        p_scene = context.scene

        p_enum_shorten_text = None if not_header else ''

        b_need_extra_separator = False

        p_layout = layout
        b_is_in_property_area = context.area.type == 'PROPERTIES'
        if b_is_in_property_area:
            p_layout = layout.box()
        else:
            if not_header:
                b_need_extra_separator = True

        def add_separator():
            if not_header and b_need_extra_separator:
                p_layout.separator()

        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        row = p_layout.row(align=True)
        row.prop(tool_props, 'tr_gizmo_mode', text=p_enum_shorten_text)
        row.prop(tool_props, 'tr_gizmo_auto_setup_by_selection', text="", icon="EVENT_A")
        r1 = row.row(align=True)
        if not_header:
            r1.ui_units_x = 1  # NOTE: we must restrict, because in Tool panel is overrided by Blender
        r1.popover("ZUV_PT_ToolTransformFitToSelection", text="")

        add_separator()


        from ..tool_ops import (
            ZUV_OP_ToolTransformMouseDraw,
            ZUV_OP_ToolTransformFitToSelection,
            ZUV_OP_ToolTransformSwapHandles,
            ZUV_OP_ToolTransformSetPerpendicular)

        row = p_layout.row(align=True)
        if not_header:
            row.use_property_split = False
            row.prop(tool_props, "tr_gizmo_influence", expand=True)
        else:
            row.prop(tool_props, "tr_gizmo_influence", text="", icon_only=True, expand=True)

        add_separator()

        row = p_layout.row(align=True)
        if not_header:
            row.use_property_split = True
            row.prop(tool_props, "tr_gizmo_transform_editing_mode", expand=False)

            if tool_props.tr_gizmo_is_falloff_enabled():
                box = layout.box()
                col = box.column(align=True)
                col.label(text="Falloff Parameters")
                col.prop(tool_props, "tr_gizmo_invert_falloff")
                col.prop(tool_props, "tr_gizmo_falloff_exponent", text="Exponent")
                if tool_props.tr_gizmo_transform_editing_mode == "LINEAR_FALLOFF":
                    row = col.row()
                    row.prop(tool_props, "tr_gizmo_linear_falloff_transformation_type", text="Linear Type")
        else:
            row.prop_with_popover(
                tool_props, "tr_gizmo_transform_editing_mode",
                panel="ZUV_PT_ToolTransformEditingMode",
                icon_only=True,
                text="")

        add_separator()

        row = p_layout.row(align=True)
        # row.use_property_split = True
        # row.alignment = 'RIGHT'
        row.popover(
            panel="ZUV_PT_ToolTransformDisplayState",
            text="Display Settings" if not_header else "", icon="OVERLAY")
        # if not_header:
        #     row.separator()
        #     row.use_property_split = False
        #     r1 = row.row(align=True)
        #     r1.alignment = 'RIGHT'
        #     for enum_item in addon_prefs.uv_transform_tool.bl_rna.properties["tr_gizmo_handles_display_state"].enum_items:
        #         r1.prop_enum(addon_prefs.uv_transform_tool, "tr_gizmo_handles_display_state", enum_item.identifier, text="")

        add_separator()

        row = p_layout.row(align=True)
        row.operator(ZUV_OP_ToolTransformMouseDraw.bl_idname, text="", icon="GREASEPENCIL")
        row.popover(panel="ZUV_PT_ToolTransformDrawSettings", text=p_enum_shorten_text)

        add_separator()

        row = p_layout.row(align=True)
        if not_header:
            row.alignment = 'RIGHT'
        s_orient = 'Orient Gizmo' if not_header else 'Orient:'
        row.label(text=s_orient)
        if not_header:
            row.separator()
        op = row.operator(ZUV_OP_ToolTransformFitToSelection.bl_idname, text="", icon='SORT_DESC')
        op.influence = tool_props.tr_gizmo_influence
        op.pivot_in_center = False
        op.allow_toggle_direction = True
        op = row.operator(ZUV_OP_ToolTransformFitToSelection.bl_idname, text="", icon='TRIA_UP')
        op.influence = tool_props.tr_gizmo_influence
        op.allow_toggle_direction = True
        op.pivot_in_center = True

        row.operator(ZUV_OP_ToolTransformSwapHandles.bl_idname, text="", icon='MOD_LENGTH')
        row.operator(ZUV_OP_ToolTransformSetPerpendicular.bl_idname, text="", icon='LIGHT_AREA')

        add_separator()

        # NOTE: debug purposes, do not remove !!!
        if False and not_header:
            col = p_layout.column(align=True)

            _ = zenuv_draw_ui_list(
                col,
                context,
                list_path="scene.zen_uv.ui.uv_tool.tr_gizmo_undo_list",
                active_index_path="scene.zen_uv.ui.uv_tool.tr_gizmo_undo_list_index",
                unique_id="name",
                new_name_attr="name",
                new_name_val="Item"
            )

        if not_header:
            row = p_layout.row(align=True)
            row.prop(tool_props, "tr_gizmo_dial_snap_step_angle")

            td_props = p_scene.zen_uv.td_props
            row = p_layout.row()
            row.prop(td_props, 'prp_current_td', text="Texel Density")

            add_separator()

            wm.zen_uv.uv_transform_tool.draw(p_layout, context)


class ZUV_PT_ToolTransformDrawSettings(bpy.types.Panel):
    bl_label = "Draw Transform Settings"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context: bpy.types.Context):
        from ZenUV.prop.scene_ui_props import ZUV_UVToolProps

        layout = self.layout
        p_scene = context.scene

        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        layout.prop(tool_props, "tr_gizmo_draw_allow_merge", icon="ACTION_TWEAK")
        layout.prop(tool_props, "tr_gizmo_draw_use_snap_margin", icon="NODE_CORNER")


class ZUV_PT_ToolTransformDisplayState(bpy.types.Panel):
    bl_label = "Display Transform Handles"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs

        addon_prefs = get_prefs()

        layout = self.layout
        layout.props_enum(addon_prefs.uv_transform_tool, "tr_gizmo_handles_display_state")


class ZUV_PT_ToolTransformEditingMode(bpy.types.Panel):
    bl_label = "Transform Editing Mode"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context: bpy.types.Context):
        from ZenUV.prop.scene_ui_props import ZUV_UVToolProps

        layout = self.layout
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        layout.props_enum(tool_props, "tr_gizmo_transform_editing_mode")

        if tool_props.tr_gizmo_is_falloff_enabled():
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Falloff Parameters")
            col.prop(tool_props, "tr_gizmo_invert_falloff")
            col.prop(tool_props, "tr_gizmo_falloff_exponent")
            if tool_props.tr_gizmo_transform_editing_mode == "LINEAR_FALLOFF":
                row = col.row()
                row.prop(tool_props, "tr_gizmo_linear_falloff_transformation_type")


class ZUV_PT_ToolTransformFitToSelection(bpy.types.Panel):
    bl_label = "Fit To Selection Options"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context: bpy.types.Context):
        from ZenUV.prop.scene_ui_props import ZUV_UVToolProps

        layout = self.layout
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        col = layout.column(align=True)
        col.use_property_split = True
        col.prop(tool_props, "tr_gizmo_fit_to_selection_pivot_in_center")
        col.prop(tool_props, "tr_gizmo_fit_to_selection_direction")
