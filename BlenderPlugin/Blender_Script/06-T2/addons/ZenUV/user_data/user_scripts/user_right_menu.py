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


def zenuv_user_mesh_right_menu(self, context: bpy.types.Context):
    layout = self.layout  # type: bpy.types.UILayout
    layout.separator()
    layout.operator('uv.zenuv_unwrap')


def register():
    print('Starting Zen UV user script...')
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(zenuv_user_mesh_right_menu)


def unregister():
    print('Finishing Zen UV user script...')
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(zenuv_user_mesh_right_menu)
