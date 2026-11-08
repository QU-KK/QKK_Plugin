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

import os


def get_preset_filepath():
    PRESET_NAME = "test"  # NOTE: write your preset name

    s_preset_subdir = os.path.join("operator", "uv.zenuv_auto_uv_unwrap")
    return bpy.utils.preset_find(PRESET_NAME, s_preset_subdir, ext=".py")


def zenuv_execute_auto_unwrap_preset():
    s_preset = get_preset_filepath()
    try:
        if s_preset:
            bpy.utils.execfile(s_preset)
            print("Successfully loaded Auto Unwrap preset:", s_preset)
        else:
            raise RuntimeError("Preset is not found!")
    except Exception as e:
        print("LOAD AUTO UNWRAP PRESET:", s_preset, e)


@bpy.app.handlers.persistent
def zenuv_load_autounwrap_preset(_):
    if not bpy.data.filepath:
        bpy.app.timers.register(zenuv_execute_auto_unwrap_preset, first_interval=0.1)


def register():
    print('Starting Zen UV user script...')

    s_preset = get_preset_filepath()
    if s_preset:
        bpy.app.handlers.load_post.append(zenuv_load_autounwrap_preset)

        bpy.app.timers.register(zenuv_execute_auto_unwrap_preset, first_interval=0.1)
    else:
        print("ERROR: Auto Unwrap preset is not found: ", s_preset)


def unregister():
    print('Finishing Zen UV user script...')

    if zenuv_load_autounwrap_preset in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(zenuv_load_autounwrap_preset)
