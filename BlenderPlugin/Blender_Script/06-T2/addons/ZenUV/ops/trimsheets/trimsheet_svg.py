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
import base64
import os
import json
from xml.sax import saxutils
from .svg import import_svg

from bpy_extras.io_utils import ImportHelper, ExportHelper

from .trimsheet_utils import ZuvTrimsheetUtils, TrimImportUtils
from ZenUV.utils.blender_zen_utils import ZenPolls


class ZUV_OT_TrimImportSVG(bpy.types.Operator, ImportHelper):
    """Load a SVG file"""
    bl_idname = "wm.zuv_trim_import_svg"
    bl_label = "Import SVG"
    bl_description = "Load trimsheet from SVG"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".svg"
    filter_glob: bpy.props.StringProperty(default="*.svg", options={'HIDDEN'})

    load_image: bpy.props.BoolProperty(
        name='Load Image Element',
        description=(
            'Load image from the corresponding svg element\n'
            'if mode is SCENE then mode will be automatically switched to IMAGE'),
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    mode: TrimImportUtils.paste_mode

    select: TrimImportUtils.paste_select

    @classmethod
    def poll(self, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        col = layout.column(align=True)
        col.use_property_split = True
        col.prop(self, 'mode', expand=True)
        col.separator()
        col.prop(self, 'select')

    def execute(self, context):
        return import_svg.load(self, context, filepath=self.filepath)


class ZUV_OT_TrimExportSVG(bpy.types.Operator, ExportHelper):
    """Save a SVG file"""
    bl_idname = "wm.zuv_trim_export_svg"
    bl_label = "Export SVG"
    bl_description = 'Save trimsheet to SVG'
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".svg"
    filter_glob: bpy.props.StringProperty(default="*.svg", options={'HIDDEN'})

    save_image: bpy.props.BoolProperty(
        name='Save Image Element',
        description=(
            'Save image to the corresponding svg element\n'),
        default=True
    )

    href_mode: bpy.props.EnumProperty(
        name='Image Mode',
        items=[
            ('BASE64', 'Base64', 'Image encoded as base64'),
            ('URL', 'Url', 'Image as href link')
        ],
        default='BASE64'
    )

    def header(self, width, height):
        yield '<?xml version="1.0" standalone="no"?>\n'
        yield '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" \n'
        yield '  "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
        yield f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"\n'
        yield '     xmlns:xlink="http://www.w3.org/1999/xlink"\n'
        yield f'     xmlns:trim="{ZenPolls.doc_url}"\n'
        yield '     xmlns="http://www.w3.org/2000/svg" version="1.1">\n'
        desc = f"Blender {bpy.app.version_string}"
        yield f'<desc>{saxutils.escape(desc)}</desc>\n'

    def get_color_string(self, color):
        r, g, b = color
        return f"rgb({round(r*255)}, {round(g*255)}, {round(b*255)})"

    def footer(self):
        yield '\n'
        yield '</svg>\n'

    def draw_trimsheet(self, p_image, trimsheet, width, height):
        ''' @Draw Trim Export '''
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()

        p_trimsheet_prefs = addon_prefs.trimsheet

        if p_image is not None and self.save_image:
            i_width, i_height = p_image.size

            was_file_path = p_image.filepath_raw

            yield '  <image x="0" y="0"\n'
            yield f'    width="{i_width}"\n'
            yield f'    height="{i_height}"\n'
            yield f'    id="{p_image.name}"\n'

            if self.href_mode == 'BASE64':
                import tempfile
                with tempfile.TemporaryDirectory() as directory:
                    try:
                        filename = directory + "/zenuv_trim_preview.png"
                        p_image.filepath_raw = filename
                        p_image.save()
                        p_bytes = base64.encodebytes(open(filename, "rb").read()).decode('ascii')
                        yield f'    xlink:href="data:image/png;base64,{p_bytes}"\n'
                    finally:
                        p_image.filepath_raw = was_file_path
            else:
                import pathlib
                p_image_path = bpy.path.abspath(p_image.filepath, library=p_image.library)
                p_image_path = os.path.normpath(p_image_path)
                yield f'    xlink:href="{pathlib.Path(p_image_path).as_uri()}"\n'

            yield '  />\n'

        from .trimsheet import TrimColorSettings

        for p_trim in trimsheet:
            p_color_settings: TrimColorSettings = p_trim.get_draw_color_settings(p_trimsheet_prefs, False, False)

            p_color = p_color_settings.color
            p_border_color = p_color_settings.border

            p_stroke_color = self.get_color_string(p_border_color[:3])
            p_stroke_opacity = 1.0
            p_stroke_width = p_color_settings.border_width

            p_fill_color = self.get_color_string(p_color[:3])
            p_fill_opacity = p_color_settings.color_alpha

            yield f'<g id="Group: {p_trim.name}">'
            yield ' <rect\n'
            yield f'  stroke="{p_stroke_color}" stroke-width="{p_stroke_width}" stroke-opacity="{p_stroke_opacity:.2g}"\n'
            yield f'  fill="{p_fill_color}" fill-opacity="{p_fill_opacity:.2g}"\n'

            i_width = p_trim.width * 100.0
            i_height = p_trim.height * 100.0

            i_x = p_trim.left * 100.0
            i_y = p_trim.bottom * 100.0
            i_y = 100.0 - i_y - i_height

            yield f'  id="Rect: {p_trim.name}"\n'
            yield f'  x="{i_x}%"\n'
            yield f'  y="{i_y}%"\n'
            yield f'  width="{i_width}%"\n'
            yield f'  height="{i_height}%"\n'
            yield ' />\n'

            yield '    <trim:trim>'

            def skip_prop(inst, attr):
                if inst == p_trim and attr in {'name', 'rect', 'color', 'border_color', 'selected'}:
                    return True
                return False

            s_trim_props = json.dumps(p_trim.to_dict(fn_skip_prop=skip_prop), indent=4)

            yield f'{saxutils.escape(s_trim_props)}'

            yield '    </trim:trim>'

            yield f'  <text id="Text: {p_trim.name}" font-size="{max(8, height/100)}" fill="{p_fill_color}" x="{i_x + i_width / 2}%" y="{i_y + i_height / 2}%" dominant-baseline="middle" text-anchor="middle">{saxutils.escape(p_trim.name)}</text>\n'
            yield '</g>\n'

    def get_file_parts(self, p_image, trimsheet, width, height):
        yield from self.header(width, height)
        yield from self.draw_trimsheet(p_image, trimsheet, width, height)
        yield from self.footer()

    def execute(self, context):
        try:

            img_w = 1024
            img_h = 1024

            from ZenUV.prop.zuv_preferences import get_prefs
            addon_prefs = get_prefs()
            p_data = context.scene if addon_prefs.trimsheet.mode == 'SCENE' else ZuvTrimsheetUtils.getActiveImage(context)
            if p_data is None:
                raise RuntimeError(f'No active {addon_prefs.trimsheet.mode.title()} trimsheet data!')

            p_image = None
            if isinstance(p_data, bpy.types.Image):
                p_image = p_data
                img_w, img_h = p_image.size
            if img_h > 0 and img_w > 0:
                p_trimsheet = p_data.zen_uv.trimsheet
                n_trimsheet_count = len(p_trimsheet)
                if n_trimsheet_count > 0:
                    with open(self.filepath, 'w', encoding='utf-8') as file:
                        for text in self.get_file_parts(
                                p_image,
                                p_data.zen_uv.trimsheet,
                                img_w, img_h):
                            file.write(text)
                else:
                    self.report({'WARNING'}, 'Trimsheet is empty!')
            else:
                self.report({'WARNING'}, 'Image size is zero!')

        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'FINISHED'}
