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

# Copyright 2024, Alex Zhornyak, alexander.zhornyak@gmail.com


# NOTE: This example will change Top Right item in Pie menu
#       from 'Mark By Angle' to 'Reshape Island'
#       with demonstration how to change also its label


import bpy
from ZenUV.ui.pie.mesh_pie import ZUV_OT_PieCallerTopRight


def register():
    print('Starting Zen UV user script...')

    ZUV_OT_PieCallerTopRight.bl_label = "Reshape Island"
    ZUV_OT_PieCallerTopRight.template_items = {
        'Default': 'uv.zenuv_reshape_island(True)',
    }

    # NOTE: This is required to reload label
    bpy.utils.unregister_class(ZUV_OT_PieCallerTopRight)
    bpy.utils.register_class(ZUV_OT_PieCallerTopRight)


def unregister():
    print('Finishing Zen UV user script...')
