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

import bpy

from ZenUV.ops.mark import ZUV_OT_Auto_Mark


class ZUV_OT_Auto_Mark2(ZUV_OT_Auto_Mark):
    bl_idname = "uv.zenuv_auto_mark"
    bl_options = {'REGISTER', 'UNDO'}

    keep_init: bpy.props.BoolProperty(
        name='Keep init marks',
        description="Keep the state of initial seam and sharp",
        default=True  # this value is overridden !
    )

    respect_selection: bpy.props.BoolProperty(
        name='Selection Respect',
        description="Mark only within current selection",
        default=True  # this value is overridden
    )


def register():
    print('Starting Zen UV user script...')

    # disabling old operator
    bpy.utils.unregister_class(ZUV_OT_Auto_Mark)
    ZUV_OT_Auto_Mark.bl_idname = "uv.zenuv_auto_mark__"
    ZUV_OT_Auto_Mark.bl_options = {'INTERNAL'}
    bpy.utils.register_class(ZUV_OT_Auto_Mark)

    # registering overrided operator
    bpy.utils.register_class(ZUV_OT_Auto_Mark2)


def unregister():
    print('Finishing Zen UV user script...')

    bpy.utils.unregister_class(ZUV_OT_Auto_Mark2)
