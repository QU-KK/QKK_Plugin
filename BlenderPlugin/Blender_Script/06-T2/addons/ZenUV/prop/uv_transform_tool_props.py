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

# Copyright 2025, Alex Zhornyak - alexander.zhornyak@gmail.com


import bpy


class ZUV_UVTransformToolProps(bpy.types.PropertyGroup):
    tr_gizmo_handles_display_state: bpy.props.EnumProperty(
        name="Display Gizmo State",
        description="Defines what parts of available transform gizmos should be displayed",
        items=[
            ("ALIGN", "Align Handles", "Align handles around pivot", "GROUP_VERTEX", 2**0),
            ("SCALE", "Scale Handle", "Uniform scale handle", "CON_TRACKTO", 2**1),
            ("SCALE_NON_PROP", "Scale Non-Uniform", "Non-uniform scale handle", "CON_STRETCHTO", 2**2),
            ("ROTATION", "Rotation Handle", "Dedicated rotation handle", "CON_SHRINKWRAP", 2**3),
            ("GUIDLINES", "Guidelines", "Enable dynamic guidelines for uv transform operations", "NODE_CORNER", 2**4),
            ("BBOX", "Bounding Box", "Enable bounding box for UV transform operations", "OBJECT_HIDDEN", 2**5),
            ("HANDLE_NAME", "Handle Name", "Display handle name in viewport", "FILE_TEXT", 2**6),
            ("HANDLE_TOOLTIP", "Handle Tooltip", "Display handle tooltip in viewport", "WINDOW", 2**7),
        ],
        options={'ENUM_FLAG'},
        default={"ALIGN", "SCALE", "SCALE_NON_PROP", "ROTATION", "HANDLE_TOOLTIP"}
    )
