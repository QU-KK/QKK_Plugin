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
from bpy_extras.io_utils import ImportHelper

import os
import uuid
import json

from .trimsheet_utils import ZuvTrimsheetUtils, TrimImportUtils

from ZenUV.utils.vlog import Log
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens


class ZUV_OT_TrimImportDecal(bpy.types.Operator, ImportHelper):
    bl_idname = "wm.zuv_trim_import_decal"
    bl_label = "Import DECALmachine Trims"
    bl_description = "Import trims from Decalmachine trim sheet"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    mode: TrimImportUtils.paste_mode

    select: TrimImportUtils.paste_select

    LITERAL_ENUM_IMAGES = 'zenuv_import_decal_images'

    @classmethod
    def poll(self, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def get_images(self, context):

        items = []

        if self.filepath:
            try:
                idx = 0
                if os.path.exists(self.filepath):
                    with open(self.filepath) as trim_json:
                        json_data = json.load(trim_json)
                        t_maps = json_data.get('maps', None)
                        for k, v in t_maps.items():
                            s_key_img_path = v.get('texture', k)
                            items.append((s_key_img_path, k, s_key_img_path, 0, 2**idx))
                            idx += 1

            except Exception as e:
                pass

        was_items = bpy.app.driver_namespace.get(ZUV_OT_TrimImportDecal.LITERAL_ENUM_IMAGES, [])
        if items != was_items:
            bpy.app.driver_namespace[ZUV_OT_TrimImportDecal.LITERAL_ENUM_IMAGES] = items

        return bpy.app.driver_namespace.get(ZUV_OT_TrimImportDecal.LITERAL_ENUM_IMAGES, [])

    images: bpy.props.EnumProperty(
        name='Images',
        description=(
            'Load image\n'
            'if mode is SCENE then mode will be automatically switched to IMAGE'),
        items=get_images,
        options={'ENUM_FLAG'}
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        layout.prop(self, 'select')

        col = layout.column(align=True)
        col.prop(self, 'mode', expand=True)

        col = layout.column(align=True)
        col.prop(self, 'images', expand=True)

    def execute(self, context: bpy.types.Context):
        try:

            trim_dict = {}

            with open(self.filepath) as trim_json:
                json_data = json.load(trim_json)

                t_trims = json_data.get('trims', None)

                resolution = json_data.get('resolution', (1, 1))

                for item in t_trims:
                    pos = item.get('coords', (0, 0))
                    size = item.get('dimensions', (0, 0))

                    pos[0] /= resolution[0]
                    pos[1] = (resolution[1] - pos[1]) / resolution[1]

                    size[0] /= resolution[0]
                    size[1] /= resolution[1]

                    left = pos[0]
                    bottom = pos[1] - size[1]
                    right = left + size[0]
                    top = pos[1]

                    trim_dict[item.get('name', 'Unknown')] = {
                        'uuid': item.get('uuid', str(uuid.uuid4())),
                        'rect': (left, top, right, bottom),
                        'color': ZuvTrimsheetUtils.getTrimsheetRandomColor()
                    }

            if trim_dict:
                if self.images:

                    p_first_image = None

                    s_dir = os.path.dirname(self.filepath)

                    t_images = self.get_images(context)
                    for id, name, desc, icon, flag in t_images:
                        if id in self.images:
                            s_json_path = os.path.join(s_dir, id)
                            s_img_path = s_json_path
                            if not os.path.exists(s_img_path):
                                s_img_path = os.path.join(s_dir, name.lower() + '.png')

                            if os.path.exists(s_img_path):
                                p_image = bpy.data.images.load(s_img_path, check_existing=True)
                                if p_image:
                                    ZuvTrimsheetUtils.import_from_trim_dict(p_image.zen_uv, self, trim_dict)
                                    if p_first_image is None:
                                        p_first_image = p_image
                            else:
                                self.report({'WARNING'}, f'Image files:[{id}], [{name.lower()}]  do not exist!')

                    if p_first_image:
                        if ZuvTrimsheetUtils.isImageEditorSpace(context):
                            if context.space_data.image != p_first_image:
                                context.space_data.image = p_first_image

                            addon_prefs = get_prefs()
                            if addon_prefs.trimsheet.mode != 'IMAGE':
                                addon_prefs.trimsheet.mode = 'IMAGE'
                        else:
                            self.report({'WARNING'}, f'Open image: {p_first_image.name} to see imported trims!')
                else:
                    p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
                    if p_data is None:
                        if addon_prefs.trimsheet.mode == 'IMAGE':
                            addon_prefs.trimsheet.mode = 'SCENE'

                    p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
                    if p_data:
                        ZuvTrimsheetUtils.import_from_trim_dict(p_data, self, trim_dict)
                    else:
                        self.report('WARNING', 'No Active Trim Sheet!')

                ZuvTrimsheetUtils.auto_highlight_trims(context)

                ZuvTrimsheetUtils.fix_undo()
                update_areas_in_all_screens(context)
            else:
                self.report({'WARNING'}, 'No trims were detected!')

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_MT_TrimImport(bpy.types.Menu):
    bl_label = "Import"
    bl_description = "Import trim sheet from external resource"

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        op = layout.operator('wm.zuv_trim_import_svg')
        op.load_image = False

        if ZuvTrimsheetUtils.isImageEditorSpace(context):
            op = layout.operator('wm.zuv_trim_import_svg', text='Import SVG with Image')
            op.load_image = True

        layout.separator()

        layout.operator(ZUV_OT_TrimImportDecal.bl_idname)
