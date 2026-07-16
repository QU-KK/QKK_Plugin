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

# Copyright 2025, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy

from .common import update_addon_prop
from ..utils.blender_zen_utils import ZenPolls


class ZUV_AddonOperatorProps(bpy.types.PropertyGroup):

    expand_auto_unwrap_preprocess: bpy.props.BoolProperty(
        name="Preprocess",
        description="Expand auto unwrap preprocess settings",
        default=True,
        update=update_addon_prop
    )

    expand_auto_unwrap_postprocess: bpy.props.BoolProperty(
        name="Postprocess",
        description="Expand auto unwrap postprocess settings",
        default=True,
        update=update_addon_prop
    )

    expand_auto_unwrap_texel_density: bpy.props.BoolProperty(
        name="Texel Density",
        description="Expand auto unwrap texel density settings",
        default=True,
        update=update_addon_prop
    )

    expand_auto_unwrap_unwrap_settings: bpy.props.BoolProperty(
        name="Unwrap Settings",
        description="Expand auto unwrap settings",
        default=False,
        update=update_addon_prop
    )

    expand_auto_unwrap_advanced_settings: bpy.props.BoolProperty(
        name="Advanced Settings",
        description="Expand auto unwrap advanced settings",
        default=False,
        update=update_addon_prop
    )

    expand_select_sys_islands: bpy.props.BoolProperty(
        name="Islands",
        description="Expand select islands panel",
        default=True,
        update=update_addon_prop
    )

    expand_select_sys_faces: bpy.props.BoolProperty(
        name="Faces",
        description="Expand select faces panel",
        default=True,
        update=update_addon_prop
    )

    expand_select_sys_edges: bpy.props.BoolProperty(
        name="Edges",
        description="Expand select edges panel",
        default=True,
        update=update_addon_prop
    )

    expand_select_sys_loops: bpy.props.BoolProperty(
        name="Loops",
        description="Expand select loops panel",
        default=True,
        update=update_addon_prop
    )

    expand_select_sys_misc: bpy.props.BoolProperty(
        name="Misc",
        description="Expand select misc panel",
        default=True,
        update=update_addon_prop
    )

    def prepare_layout_panel(
            self, p_layout: bpy.types.UILayout, s_identifier: str,
            fn_create_body: callable = lambda layout: layout.box(), s_panel_caption: str = None):
        body: bpy.types.UILayout = None

        if not s_panel_caption:
            s_panel_caption = self.bl_rna.properties[s_identifier].name

        if ZenPolls.version_since_4_1_0:
            header: bpy.types.UILayout
            panel: bpy.types.UILayout
            header, panel = p_layout.panel_prop(self, s_identifier)
            header.label(text=s_panel_caption)
            if panel:
                body = fn_create_body(panel)
        else:
            body = fn_create_body(p_layout)
            body.label(text=s_panel_caption)
        return body
