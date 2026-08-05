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


@bpy.app.handlers.persistent
def zenuv_user_script_load_scene_handler(_):
    print('LOAD SCENE')
    p_scene = bpy.context.scene
    if p_scene:
        p_scene.zen_uv.ui.draw_mode_UV = 'UV_OBJECT'
        p_scene.zen_uv.ui.draw_mode_3D = 'UV_NO_SYNC'


def register():
    print('Starting Zen UV user script...')

    # this will override settings after scene was loaded
    if zenuv_user_script_load_scene_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(zenuv_user_script_load_scene_handler)

    # this will override settings in the default scene
    zenuv_user_script_load_scene_handler(None)


def unregister():
    print('Finishing Zen UV user script...')

    if zenuv_user_script_load_scene_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(zenuv_user_script_load_scene_handler)
