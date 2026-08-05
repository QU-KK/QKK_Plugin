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

from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils


class ZUV_PT_ImageUIOverlay(bpy.types.Panel):
    bl_label = "Zen UV Overlay"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'
    bl_parent_id = "IMAGE_PT_overlay"

    @classmethod
    def poll(cls, context):
        return ZuvTrimsheetUtils.getActiveImage(context)

    def draw(self, context):
        layout = self.layout

        p_image = ZuvTrimsheetUtils.getActiveImage(context)
        if p_image is not None:
            row = layout.row(align=True)
            row.operator('uv.zuv_darken_image', depress=ZUV_OT_DarkenImage.is_mode_on(context))


class ZUV_OT_DarkenImage(bpy.types.Operator):
    bl_idname = "uv.zuv_darken_image"
    bl_label = 'Darken Image'
    bl_description = 'Darken active image in ImageEditor'
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('NONE', 'None', ''),
            ('ON', 'On', ''),
            ('OFF', 'Off', '')
        ],
        default='NONE'
    )

    darkness: bpy.props.IntProperty(
        name='Darkness',
        min=1,
        max=100,
        default=50
    )

    @classmethod
    def getActiveImage(cls, context):
        if hasattr(context, 'space_data'):
            if context.space_data is not None and hasattr(context.space_data, 'image'):
                return context.space_data.image
        return None

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return cls.getActiveImage(context) is not None

    @classmethod
    def is_mode_on(cls, context: bpy.types.Context):
        p_image = cls.getActiveImage(context)
        if p_image is not None:
            p_scene = context.scene
            if p_image.use_view_as_render and p_scene.view_settings.use_curve_mapping:
                return True
        return False

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.mode = 'NONE'
        p_image = self.getActiveImage(context)
        if p_image is not None:
            if self.is_mode_on(context):
                self.mode = 'OFF'
            else:
                self.mode = 'ON'
            return self.execute(context)

        return {'CANCELLED'}

    def execute(self, context: bpy.types.Context):
        p_image = self.getActiveImage(context)
        if p_image is not None:

            p_scene = context.scene

            if self.mode == 'ON':
                p_image.use_view_as_render = True
                p_scene.view_settings.use_curve_mapping = True

                p_white = max(self.darkness * 1, 0)

                p_scene.view_settings.curve_mapping.white_level = (p_white, p_white, p_white)

                p_scene.view_settings.curve_mapping.update()
            elif self.mode == 'OFF':

                p_scene.view_settings.curve_mapping.white_level = (1.0, 1.0, 1.0)

                p_scene.view_settings.curve_mapping.update()

                p_image.use_view_as_render = False
                p_scene.view_settings.use_curve_mapping = False

            return {'FINISHED'}

        return {'CANCELLED'}
