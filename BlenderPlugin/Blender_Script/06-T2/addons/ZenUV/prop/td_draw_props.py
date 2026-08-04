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

# Copyright 2023, Alex Zhornyak

import bpy


class ZUV_TexelDensityDrawProps(bpy.types.PropertyGroup):

    width: bpy.props.IntProperty(
        name='TD Gradient Width',
        min=50,
        max=2000,
        default=300
    )

    height: bpy.props.IntProperty(
        name='TD Gradient Height',
        min=10,
        max=500,
        default=15
    )

    alpha: bpy.props.FloatProperty(
        name='TD Color Alpha',
        description='Texel density overlay color alpha',
        default=0.6,
        min=0.01,
        max=1.0,
        subtype='FACTOR'
    )

    def draw(self, layout: bpy.types.UILayout, context: bpy.types.Context):
        for key in self.__annotations__.keys():
            layout.prop(self, key)

        b_is_uv = context.space_data.type == 'IMAGE_EDITOR'
        if b_is_uv:
            layout.prop(context.scene.zen_uv.ui, 'draw_sub_TD_UV')
        else:
            layout.prop(context.scene.zen_uv.ui, 'draw_sub_TD_3D')
