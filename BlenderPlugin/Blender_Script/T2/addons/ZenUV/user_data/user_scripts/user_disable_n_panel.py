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

import bpy

from ZenUV.ui.combo_panel import ZUV_PT_3DV_ComboPanel, ZUV_PT_UVL_ComboPanel


def register():
    print('Starting Zen UV user script...')

    # NOTE: this operation will disable ZenUV N-Panel
    bpy.utils.unregister_class(ZUV_PT_3DV_ComboPanel)
    bpy.utils.unregister_class(ZUV_PT_UVL_ComboPanel)


def unregister():
    print('Finishing Zen UV user script...')

    # NOTE: we need to revert it back to prevent conflict in addon unregister procedure
    bpy.utils.register_class(ZUV_PT_3DV_ComboPanel)
    bpy.utils.register_class(ZUV_PT_UVL_ComboPanel)
