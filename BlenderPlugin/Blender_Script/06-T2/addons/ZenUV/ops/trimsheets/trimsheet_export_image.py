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
from bpy_extras.io_utils import ExportHelper

import uuid
import numpy as np

from .trimsheet_utils import ZuvTrimsheetUtils


class TrimExportImageBase(ExportHelper):

    image_file_format = ''  # BMP, TGA, PNG

    image_width: bpy.props.IntProperty(
        name='Image Width',
        description='Width of target image in pixels',
        default=1024,
        subtype='PIXEL'
    )

    image_height: bpy.props.IntProperty(
        name='Image Height',
        description='Height of target image in pixels',
        default=1024,
        subtype='PIXEL'
    )

    background_color: bpy.props.FloatVectorProperty(
        name='Back Color',
        description='Background color for image area that is not covered with trims',
        subtype='COLOR',
        default=(0, 0, 0, 1.0),
        size=4,
        min=0,
        max=1)

    trim_alpha: bpy.props.FloatProperty(
        name='Trim Alpha',
        description='Alpha value for exported trim color',
        default=1.0,
        min=0.0,
        max=1.0
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_image = ZuvTrimsheetUtils.getActiveImage(context)
        if p_image:
            self.image_width = p_image.size[0]
            self.image_height = p_image.size[1]

        return super().invoke(context, event)

    def execute(self, context: bpy.types.Context):
        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if p_trimsheet is None:
            self.report({'INFO'}, 'No active Trim Sheet!')
            return {'CANCELLED'}

        if len(p_trimsheet) == 0:
            self.report({'INFO'}, 'Trim Sheet is empty!')
            return {'CANCELLED'}

        if self.image_width == 0 or self.image_height == 0:
            self.report({'INFO'}, 'Width and Height can not be zero!')
            return {'CANCELLED'}

        p_image = bpy.data.images.new(str(uuid.uuid4()), self.image_width, self.image_height)
        p_image.file_format = self.image_file_format
        try:
            back = np.array(self.background_color[:] * self.image_height * self.image_width, dtype=np.float32)
            arr = back.reshape((self.image_height, self.image_width, p_image.channels))

            from .trimsheet import ZuvTrimsheetGroup

            p_trim: ZuvTrimsheetGroup
            for p_trim in p_trimsheet:
                left, top, right, bottom = p_trim.rect

                left_px = round(np.clip(left * self.image_width, 0, self.image_width))
                bottom_px = round(np.clip(bottom * self.image_height, 0, self.image_height))
                right_px = round(np.clip(right * self.image_width, 0, self.image_width))
                top_px = round(np.clip(top * self.image_height, 0, self.image_height))

                width_px = right_px - left_px
                height_px = top_px - bottom_px

                if width_px > 0 and height_px > 0:
                    trim_arr = np.array((*p_trim.color, self.trim_alpha) * height_px * width_px, dtype=np.float32)
                    trim_arr = trim_arr.reshape((height_px, width_px, p_image.channels))
                    arr[bottom_px:top_px, left_px:right_px, :] = trim_arr

            p_image.pixels.foreach_set(arr.ravel())

            if bpy.app.version < (3, 4, 1):
                p_image.filepath_raw = self.filepath
                p_image.save()
            else:
                p_image.save(filepath=self.filepath)

        finally:
            bpy.data.images.remove(p_image)

        return {'FINISHED'}


class ZUV_OT_TrimExportPNG(bpy.types.Operator, TrimExportImageBase):
    """Save a PNG file"""
    bl_idname = "wm.zuv_trim_export_png"
    bl_label = "Export PNG"
    bl_description = 'Save trimsheet to PNG'
    bl_options = {'REGISTER', 'UNDO'}

    image_file_format = 'PNG'
    filename_ext = ".png"
    filter_glob: bpy.props.StringProperty(default="*.png", options={'HIDDEN'})


class ZUV_OT_TrimExportBMP(bpy.types.Operator, TrimExportImageBase):
    """Save a BMP file"""
    bl_idname = "wm.zuv_trim_export_bmp"
    bl_label = "Export BMP"
    bl_description = 'Save trimsheet to BMP'
    bl_options = {'REGISTER', 'UNDO'}

    image_file_format = 'BMP'
    filename_ext = ".bmp"
    filter_glob: bpy.props.StringProperty(default="*.bmp", options={'HIDDEN'})


class ZUV_OT_TrimExportTGA(bpy.types.Operator, TrimExportImageBase):
    """Save a TGA file"""
    bl_idname = "wm.zuv_trim_export_tga"
    bl_label = "Export TGA"
    bl_description = 'Save trimsheet to TGA'
    bl_options = {'REGISTER', 'UNDO'}

    image_file_format = 'TARGA'
    filename_ext = ".tga"
    filter_glob: bpy.props.StringProperty(default="*.tga", options={'HIDDEN'})


class ZUV_MT_TrimExport(bpy.types.Menu):
    bl_label = "Export"
    bl_description = "Export trim sheet as image"

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        op = layout.operator('wm.zuv_trim_export_svg')
        op.save_image = False
        op = layout.operator('wm.zuv_trim_export_svg', text='Export SVG with Image')
        op.save_image = True

        layout.separator()

        layout.operator(ZUV_OT_TrimExportPNG.bl_idname)
        layout.operator(ZUV_OT_TrimExportTGA.bl_idname)
        layout.operator(ZUV_OT_TrimExportBMP.bl_idname)
