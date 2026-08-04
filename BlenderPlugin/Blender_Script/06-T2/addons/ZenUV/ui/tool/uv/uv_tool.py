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

# Copyright 2023, Alex Zhornyak

import bpy

from ZenUV.ico import zenuv_tool_icon
from ZenUV.prop.zuv_preferences import get_prefs

from ..tool_generic_keymap import get_tool_generic_keymap


def get_keymap():
    km = [
        ("wm.zenuv_update_toggle",
            {"type": 'D', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.display_trims')]}),
        ("wm.zenuv_update_toggle",
            {"type": 'F', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.select_trim_ex')]}),
        ("wm.context_set_enum",
            {"type": 'L', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.mode'), ("value", 'RESIZE')]}),
        ("wm.context_set_enum",
            {"type": 'K', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.mode'), ("value", 'CREATE')]}),

        ("wm.context_set_enum",
            {"type": 'G', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.mode'), ("value", 'MOVE')]}),
        ("wm.context_set_enum",
            {"type": 'R', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.mode'), ("value", 'ROTATE')]}),
        ("wm.context_set_enum",
            {"type": 'S', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.uv_tool.mode'), ("value", 'SCALE')]}),

        ("zenuv.tool_exit_create",
            {"type": 'ESC', "value": 'ANY', "ctrl": False, "shift": False},
            {"properties": []}),

        ("wm.zuv_event_service",
            {"type": 'MOUSEMOVE', "value": 'ANY', "any": True},
            {"properties": []}),

        ("wm.zenuv_trim_scroll_fit_internal",
            {"type": 'WHEELUPMOUSE', "value": 'ANY', "ctrl": True, "shift": True},
            {"properties": [("is_up", True)]}),
        ("wm.zenuv_trim_scroll_fit_internal",
            {"type": 'WHEELDOWNMOUSE', "value": 'ANY', "ctrl": True, "shift": True},
            {"properties": [("is_up", False)]}),

        ("uv.zuv_trim_delete_all",
            {"type": 'X', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("use_dialog", False), ("mode", 'SELECTED')]}),
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

    select_km.append(
        ("wm.zuv_trim_box_select", {"type": 'LEFTMOUSE', "value": 'PRESS', "any": True},
            {"properties": []}),
    )

    return tuple(km + get_tool_generic_keymap() + select_km)


class ZuvUVWorkSpaceTool(bpy.types.WorkSpaceTool):
    bl_space_type = 'IMAGE_EDITOR'
    bl_context_mode = 'UV'

    # The prefix of the idname should be add-on name.
    bl_idname = "zenuv.uv_tool"
    bl_idname_fallback = 'builtin.select_box'
    bl_label = 'Zen UV Transform'
    bl_description = 'ZenUV islands and trims transform tool'
    bl_icon = zenuv_tool_icon()
    bl_keymap = get_keymap()
    bl_widget = '' if bpy.app.version < (3, 3, 0) else 'ZUV_GGT_UVTransformMove'

    def draw_settings(context: bpy.types.Context, layout: bpy.types.UILayout, tool):
        from ZenUV.prop.scene_ui_props import ZUV_UVToolProps

        not_header = context.region.type != 'TOOL_HEADER'

        wm = context.window_manager
        addon_prefs = get_prefs()
        p_scene = context.scene

        p_enum_shorten_text = None if not_header else ''

        p_layout = layout
        b_is_in_property_area = context.area.type == 'PROPERTIES'
        if b_is_in_property_area:
            p_layout = layout.box()

        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        p_layout.prop(tool_props, 'category', text=p_enum_shorten_text)
        if tool_props.category == 'TRANSFORMS':
            p_layout.prop(tool_props, 'transform_mode', text=p_enum_shorten_text)
        else:
            p_layout.prop(tool_props, 'trim_mode', text=p_enum_shorten_text)

        row = layout.row(align=True)
        row.prop(tool_props, "display_trims", text=p_enum_shorten_text, icon='OVERLAY')

        s_tool_mode = tool_props.mode

        b_is_create = s_tool_mode == 'CREATE'
        b_is_resize = s_tool_mode == 'RESIZE'

        if not b_is_create:
            if tool_props.display_trims:
                row.prop(
                    tool_props, 'select_trim', text='',
                    icon='RESTRICT_SELECT_OFF' if tool_props.select_trim else 'RESTRICT_SELECT_ON')

        row.popover(panel='ZUV_PT_TrimOverlayFilter', text='')

        if not b_is_create and not b_is_resize:
            row = layout.row(align=True)
            row.prop(tool_props, 'tr_handles', text=p_enum_shorten_text, icon_only=not not_header)

        def draw_lock_in_trim(op_id):
            op_ptr = wm.operator_properties_last(op_id)

            if op_ptr:
                r_lock = layout.row(align=True)
                r_lock.alert = op_ptr.lock_in_trim and 'out of trim' in op_ptr.info_message.lower()
                r_lock.prop(
                    op_ptr, 'lock_in_trim',
                    icon_only=not not_header,
                    icon='LOCKED' if op_ptr.lock_in_trim else 'UNLOCKED')

        p_act_obj = context.active_object
        if p_act_obj is not None and p_act_obj.type == 'MESH':
            # Scene | Image
            row = p_layout.row(align=True)
            row.prop(addon_prefs.trimsheet, 'mode', expand=True)

            # Islands | Selection
            row = p_layout.row(align=True)
            row.prop(p_scene.zen_uv, 'tr_type', expand=True, text=p_enum_shorten_text)

        if s_tool_mode in {'MOVE', 'SCALE', 'ROTATE'}:
            draw_lock_in_trim(F'uv.zenuv_{s_tool_mode.lower()}_in_trim')

        if b_is_create or b_is_resize:
            row = p_layout.row(align=True)
            if b_is_create:
                row.prop(
                    tool_props,
                    'lock_trim_size',
                    icon_only=True,
                    icon='LINKED' if tool_props.lock_trim_size else 'UNLINKED')
            r_snap = row.row(align=True)
            r_snap.active = tool_props.poll_trim_snap_mode(context)
            r_snap.prop(
                tool_props,
                'use_trim_snap',
                icon_only=True,
                icon='SNAP_ON' if tool_props.use_trim_snap else 'SNAP_OFF')
            r_snap2 = r_snap.row(align=True)
            r_snap2.active = tool_props.use_trim_snap

            snap_items = tool_props.bl_rna.properties["trim_snap_mode"].enum_items

            snap_elements = tool_props.trim_snap_mode

            if len(snap_elements) == 1:
                s_text = ""
                for elem in snap_elements:
                    p_icon = snap_items[elem].icon
                    break
            else:
                s_text = "Mix"
                p_icon = 'NONE'

            r_snap2.popover(panel='ZUV_PT_TrimSnapUV', text=s_text, icon=p_icon)

        if b_is_in_property_area:
            from ZenUV.ui.combo_panel import ZuvComboBase, ZUV_PT_UVL_ComboPanel
            pnl = ZuvComboBase()
            pnl.column_align = 'RIGHT'
            pnl.bl_space_type = ZUV_PT_UVL_ComboPanel.bl_space_type
            pnl.layout = layout
            pnl.draw(context)
