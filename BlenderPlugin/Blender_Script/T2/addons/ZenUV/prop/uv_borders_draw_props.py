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


LITERAL_USER_MARGIN = 'Margin value in percents defined by user'


class ZUV_UVBordersDrawProps(bpy.types.PropertyGroup):

    def on_mode_update(self, context):
        p_scene = context.scene
        if p_scene.zen_uv.ui.draw_mode_UV == 'UV_BORDERS':
            from ZenUV.ui.gizmo_draw import update_all_gizmos_UV
            update_all_gizmos_UV(context, force=True)

    mode: bpy.props.EnumProperty(
        name='UV Borders Mode',
        description='Display mode of island uv borders',
        items=[
            ('PACK_MARGIN', 'Pack Margin', 'Margin value taken from the Zen UV Pack system margin'),
            ('USER_MARGIN', 'User Margin', LITERAL_USER_MARGIN),
            ('LINE', 'Line', 'UV Borders as single line'),
        ],
        default='PACK_MARGIN',
        update=on_mode_update
    )

    user_margin: bpy.props.FloatProperty(
        name='UV Borders Margin',
        description=LITERAL_USER_MARGIN,
        min=0,
        max=10,
        subtype='PERCENTAGE',
        default=1,
        update=on_mode_update
    )

    color: bpy.props.FloatVectorProperty(
        name='UV Borders Color',
        description='Island uv borders display color',
        subtype='COLOR',
        default=[0.198, 0.082, 1.0, 0.85],
        size=4,
        min=0,
        max=1)

    line_width: bpy.props.IntProperty(
        name='UV Borders Width',
        description='UV Borders line width in pixels',
        min=1,
        max=10,
        subtype='PIXEL',
        default=2
    )

    def draw(self, layout: bpy.types.UILayout, context: bpy.types.Context):
        layout.prop(self, 'color')

        b_is_uv = context.space_data.type == 'IMAGE_EDITOR'
        if b_is_uv:
            layout.prop(self, 'mode')
            if self.mode == 'USER_MARGIN':
                layout.prop(self, 'user_margin')
            elif self.mode == 'LINE':
                layout.prop(self, 'line_width')
        else:
            layout.prop(self, 'line_width')
