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

from .tool_generic_keymap import get_tool_generic_keymap


def get_keymap():
    km = [
        ("wm.zenuv_update_toggle",
            {"type": 'D', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.view3d_tool.display_trims_ex')]}),
        ("wm.zenuv_update_toggle",
            {"type": 'F', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.view3d_tool.select_trim_ex')]}),
        ("wm.zenuv_update_toggle",
            {"type": 'F', "value": 'PRESS', "ctrl": False, "shift": True},
            {"properties": [("data_path", 'scene.zen_uv.ui.view3d_tool.enable_screen_selector')]}),

        ("wm.context_set_enum",
            {"type": 'G', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.view3d_tool.mode'), ("value", 'MOVE')]}),
        ("wm.context_set_enum",
            {"type": 'R', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.view3d_tool.mode'), ("value", 'ROTATE')]}),
        ("wm.context_set_enum",
            {"type": 'S', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("data_path", 'scene.zen_uv.ui.view3d_tool.mode'), ("value", 'SCALE')]}),

        ("view3d.tool_screen_zoom",
            {"type": 'WHEELUPMOUSE', "value": 'ANY', "ctrl": False, "shift": False},
            {"properties": [("is_up", True)]}),
        ("view3d.tool_screen_zoom",
            {"type": 'WHEELDOWNMOUSE', "value": 'ANY', "ctrl": False, "shift": False},
            {"properties": [("is_up", False)]}),
        ("view3d.tool_screen_pan",
            {"type": 'MIDDLEMOUSE', "value": 'PRESS', "ctrl": False, "shift": True},
            {"properties": []}),
        ("view3d.tool_screen_reset",
            {"type": 'NUMPAD_PERIOD', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("mode", "CENTER")]}),
        ("view3d.tool_screen_reset",
            {"type": 'HOME', "value": 'PRESS', "ctrl": False, "shift": False},
            {"properties": [("mode", "RESET")]}),

        ("wm.zuv_event_service",
            {"type": 'MOUSEMOVE', "value": 'ANY', "any": True},
            {"properties": []}),

        ("wm.zenuv_trim_scroll_fit_internal",
            {"type": 'WHEELUPMOUSE', "value": 'ANY', "ctrl": True, "shift": True},
            {"properties": [("is_up", True)]}),
        ("wm.zenuv_trim_scroll_fit_internal",
            {"type": 'WHEELDOWNMOUSE', "value": 'ANY', "ctrl": True, "shift": True},
            {"properties": [("is_up", False)]}),
    ]

    if bpy.app.version < (3, 2, 0):
        select_km = [
            ("view3d.select_box", {"type": 'EVT_TWEAK_L', "value": 'ANY', "ctrl": False, "shift": False},
                {"properties": [("wait_for_input", False)]}),
            ("view3d.select_box", {"type": 'EVT_TWEAK_L', "value": 'ANY', "ctrl": True, "shift": False},
                {"properties": [("mode", 'SUB'), ("wait_for_input", False)]}),
            ("view3d.select_box", {"type": 'EVT_TWEAK_L', "value": 'ANY', "ctrl": False, "shift": True},
                {"properties": [("mode", 'ADD'), ("wait_for_input", False)]}),
        ]
    elif bpy.app.version < (3, 3, 0):
        select_km = [
            ("view3d.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": False, "shift": False},
                {"properties": [("wait_for_input", False)]}),
            ("view3d.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": True, "shift": False},
                {"properties": [("mode", 'SUB'), ("wait_for_input", False)]}),
            ("view3d.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": False, "shift": True},
                {"properties": [("mode", 'ADD'), ("wait_for_input", False)]}),
        ]
    else:
        select_km = []

    return tuple(km + get_tool_generic_keymap() + select_km)


class Zuv3DVWorkSpaceTool(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'

    # The prefix of the idname should be add-on name.
    bl_idname = "zenuv.view3d_tool"
    bl_idname_fallback = 'builtin.select_box'
    bl_label = 'Zen UV Transform'
    bl_description = 'ZenUV islands and trims transform tool'
    bl_icon = zenuv_tool_icon()
    bl_keymap = get_keymap()
    bl_widget = '' if bpy.app.version < (3, 3, 0) else 'ZUV_GGT_3DVTransformMove'

    def draw_settings(context: bpy.types.Context, layout: bpy.types.UILayout, tool):

        not_header = context.region.type != 'TOOL_HEADER'

        wm = context.window_manager
        addon_prefs = get_prefs()
        p_scene = context.scene

        p_enum_shorten_text = None if not_header else ''

        p_layout = layout
        b_is_in_property_area = context.area.type == 'PROPERTIES'
        b_props_expanded = True
        if b_is_in_property_area:
            b_props_expanded = p_scene.zen_uv.ui.tool_settings_expanded

            p_layout = layout.box()

            row = p_layout.row(align=True)
            row.use_property_split = False
            r_1 = row.row(align=True)
            r_1.alignment = 'LEFT'
            r_1.prop(
                p_scene.zen_uv.ui, 'tool_settings_expanded',
                emboss=False,
                icon_only=True,
                icon='DISCLOSURE_TRI_DOWN' if b_props_expanded else 'DISCLOSURE_TRI_RIGHT')
            r_2 = row.row(align=True)
            r_2.alignment = 'LEFT'
            r_2.prop(
                p_scene.zen_uv.ui, 'tool_settings_expanded',
                emboss=False)

            if b_props_expanded:
                p_layout.separator(factor=0.5)

        tool_props = p_scene.zen_uv.ui.view3d_tool

        if b_props_expanded:
            p_layout.prop(tool_props, 'mode', text=p_enum_shorten_text)

            s_tool_mode = tool_props.mode

            p_act_obj = context.active_object
            if p_act_obj is not None and p_act_obj.type == 'MESH':
                row = p_layout.row(align=True)
                row.prop(tool_props, "display_trims_ex", text=p_enum_shorten_text, icon='OVERLAY')
                if tool_props.display_trims and not tool_props.enable_screen_selector:
                    row.prop(
                        tool_props, 'select_trim', text='',
                        icon='RESTRICT_SELECT_OFF' if tool_props.select_trim else 'RESTRICT_SELECT_ON')
                row.popover(panel='ZUV_PT_TrimOverlayFilter', text='')

                row = p_layout.row(align=True)
                row.prop(tool_props, 'tr_handles', text=p_enum_shorten_text, icon_only=not not_header)

                def draw_lock_in_trim(op_id):
                    op_ptr = wm.operator_properties_last(op_id)

                    if op_ptr:
                        r_lock = p_layout.row(align=True)
                        r_lock.alert = op_ptr.lock_in_trim and 'out of trim' in op_ptr.info_message.lower()
                        r_lock.prop(
                            op_ptr, 'lock_in_trim',
                            icon_only=not not_header,
                            icon='LOCKED' if op_ptr.lock_in_trim else 'UNLOCKED')

            if s_tool_mode in {'MOVE', 'SCALE', 'ROTATE'}:
                # Scene | Image
                row = p_layout.row(align=True)
                row.prop(addon_prefs.trimsheet, 'mode', expand=True)

                # Islands | Selection
                row = p_layout.row(align=True)
                row.prop(p_scene.zen_uv, 'tr_type', expand=True, text=p_enum_shorten_text)

                draw_lock_in_trim(F'view3d.zenuv_{s_tool_mode.lower()}_in_trim')

        if b_is_in_property_area:
            from ZenUV.ui.combo_panel import ZuvComboBase, ZUV_PT_3DV_ComboPanel
            pnl = ZuvComboBase()
            pnl.column_align = 'RIGHT'
            pnl.bl_space_type = ZUV_PT_3DV_ComboPanel.bl_space_type
            pnl.layout = layout
            pnl.draw(context)
