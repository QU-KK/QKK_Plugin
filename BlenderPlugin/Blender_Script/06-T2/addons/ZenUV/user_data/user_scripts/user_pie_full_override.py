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

# Copyright 2023, Alex Zhornyak, alexander.zhornyak@gmail.com


from ZenUV.ui.pie.mesh_pie import (
    ZUV_OT_PieCallerRight, ZUV_OT_PieCallerLeft,
    ZUV_OT_PieCallerTop, ZUV_OT_PieCallerBottom,
    ZUV_OT_PieCallerTopLeft, ZUV_OT_PieCallerBottomLeft,
    ZUV_OT_PieCallerBottomRight, ZUV_OT_PieCallerTopRight)


def register():
    print('Starting Zen UV user script...')

    ZUV_OT_PieCallerLeft.template_items = {
        'Default': 'uv.zenuv_mark_seams(True, action="UNMARK")',
        'CTRL': 'uv.zenuv_untag_finished(True)',
        'ALT': 'uv.zenuv_unmark_all(True)'
    }
    ZUV_OT_PieCallerRight.template_items = {
        'Default': 'uv.zenuv_mark_seams(True, action="MARK")',
        'CTRL': 'uv.zenuv_tag_finished(True)'
    }
    ZUV_OT_PieCallerTop.template_items = {
        'Default': "bpy.ops.uv.zenuv_isolate_island('INVOKE_DEFAULT', True)",
    }
    ZUV_OT_PieCallerBottom.template_items = {
        'Default': "bpy.ops.uv.zenuv_unwrap('INVOKE_DEFAULT', True)",
        'ALT': "uv.zenuv_pack(True)",
        'SHIFT': "bpy.ops.uv.zuv_activate_tool(True, mode='ACTIVATE')"
    }
    ZUV_OT_PieCallerTopLeft.template_items = {
        'Default': "uv.zenuv_select_island(True)",
        'ALT': "uv.zenuv_select_uv_overlap(True)",
        'CTRL': "uv.zenuv_select_flipped(True)",
        'SHIFT': "uv.zenuv_select_similar(True)",
    }
    ZUV_OT_PieCallerBottomLeft.template_items = {
        'Default': "uv.zenuv_quadrify(True)",
        'CTRL': "uv.zenuv_relax(True)",
        'SHIFT': "uv.zenuv_fit_to_trim_hotspot(True)"
    }
    ZUV_OT_PieCallerBottomRight.template_items = {
        'Default': "view3d.zenuv_checker_toggle(True, action='TOGGLE')",
        'ALT': "uv.switch_stretch_map(True)",
        'CTRL': "uv.zenuv_display_finished(True)"
    }
    ZUV_OT_PieCallerTopRight.template_items = {
        'Default': "uv.zenuv_auto_mark(True)",
    }


def unregister():
    print('Finishing Zen UV user script...')
