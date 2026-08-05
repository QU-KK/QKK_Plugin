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

# Copyright 2023, Alex Zhornyak, Valeriy Yatsenko

import bpy

from .uv_base import ZuvUVGizmoBase


class ZUV_GGT_UVTrimGeneric(bpy.types.GizmoGroup, ZuvUVGizmoBase):
    bl_idname = "ZUV_GGT_UVTrimGeneric"
    bl_label = "Display, Select, Resize Trim(s)"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SHOW_MODAL_ALL',
    } if bpy.app.version < (3, 3, 0) else {
        'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL',
    }

    tool_mode = {'SELECT', 'RESIZE'}


class ZUV_GGT_UVTrimDisplay(bpy.types.GizmoGroup, ZuvUVGizmoBase):
    bl_idname = "ZUV_GGT_UVTrimDisplay"
    bl_label = "Display Trim(s)"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SHOW_MODAL_ALL',
    } if bpy.app.version < (3, 3, 0) else {
        'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL',
    }

    tool_mode = {'DISPLAY'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        if not cls.is_workspace_tool_active(context):
            return context.scene.zen_uv.ui.uv_tool.display_trims
        return False
