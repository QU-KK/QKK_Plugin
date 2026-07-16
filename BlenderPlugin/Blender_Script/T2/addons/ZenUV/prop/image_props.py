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

import uuid

from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetGroup
from ZenUV.ops.trimsheets.trimsheet_preview import (
    get_enum_previews,
    enum_previews_from_directory_items)
from ZenUV.ops.trimsheets.trimsheet_props import ZuvTrimsheetOwnerProps
from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens
from ZenUV.prop.world_size_props import ZUV_WorldSizeImageProps
from ZenUV.utils.vlog import Log


LITERAL_UV_WORLD_SIZE_TRIMS = 'zenuv_world_size_trims'


class TrimsheetPreviewUtils:
    @classmethod
    def _on_zenuv_trimsheet_previews_update(cls, p_trim_data, context: bpy.types.Context):
        p_trimsheet_names = [p_trim.get_preview_name() for p_trim in p_trim_data.trimsheet]
        p_previews = enum_previews_from_directory_items(p_trim_data, context)

        p_preview_names = [item[0] for item in p_previews]

        if p_preview_names == p_trimsheet_names:
            if p_trim_data.trimsheet_previews in p_trimsheet_names:
                p_index = p_trimsheet_names.index(p_trim_data.trimsheet_previews)
                if p_trim_data.trimsheet_index != p_index:
                    p_trim_data.trimsheet_index = p_index

                try:
                    if p_trim_data.use_fit_to_trim:
                        if bpy.ops.uv.zenuv_fit_to_trim.poll():
                            bpy.ops.uv.zenuv_fit_to_trim('INVOKE_DEFAULT', True)
                except Exception as e:
                    Log.error("Trimsheet Preview Update:", e)

    @classmethod
    def _get_trimsheet_previews(cls, p_trim_data):
        p_trimsheet_names = [p_trim.get_preview_name() for p_trim in p_trim_data.trimsheet]
        p_previews = get_enum_previews(p_trim_data)

        p_preview_names = [item[0] for item in p_previews]

        if p_preview_names == p_trimsheet_names:
            return p_trim_data.trimsheet_index
        else:
            return -1

    @classmethod
    def _set_trimsheet_previews(cls, p_trim_data, value):
        p_trimsheet_names = [p_trim.get_preview_name() for p_trim in p_trim_data.trimsheet]
        p_previews = get_enum_previews(p_trim_data)

        p_preview_names = [item[0] for item in p_previews]

        if p_preview_names == p_trimsheet_names:
            p_trim_data.trimsheet_index = value
            update_areas_in_all_screens(bpy.context)


def on_zenuv_trimsheet_previews_update(self, context: bpy.types.Context):
    TrimsheetPreviewUtils._on_zenuv_trimsheet_previews_update(self, context)


def get_trimsheet_previews(self):
    return TrimsheetPreviewUtils._get_trimsheet_previews(self)


def set_trimsheet_previews(self, value):
    TrimsheetPreviewUtils._set_trimsheet_previews(self, value)


class ZuvImageProperties(bpy.types.PropertyGroup):
    trimsheet: bpy.props.CollectionProperty(name='Trimsheet', type=ZuvTrimsheetGroup)
    trimsheet_index: ZuvTrimsheetOwnerProps.trimsheet_index
    trimsheet_index_ui: ZuvTrimsheetOwnerProps.trimsheet_index_ui
    trimsheet_geometry_uuid: ZuvTrimsheetOwnerProps.trimsheet_geometry_uuid

    # image properties only
    trimsheet_previews: bpy.props.EnumProperty(
        name='Trimsheet Previews', items=enum_previews_from_directory_items,
        get=get_trimsheet_previews,
        set=set_trimsheet_previews,
        update=on_zenuv_trimsheet_previews_update)

    use_fit_to_trim: bpy.props.BoolProperty(
        name="Auto Fit",
        description="Execute fit to trim operation after trim is selected in preview",
        default=False
    )

    def trimsheet_mark_geometry_update(self):
        self.trimsheet_geometry_uuid = str(uuid.uuid4())

    world_size: bpy.props.PointerProperty(name='UW World Size', type=ZUV_WorldSizeImageProps)

    def get_trimsheet_with_size_items(self, context: bpy.types.Context):
        items = {}
        p_trim: ZuvTrimsheetGroup
        for p_trim in self.trimsheet:
            if p_trim.world_size[:] != (0.0, 0.0):
                s_id = p_trim.uuid
                s_name = f'{p_trim.name} - {p_trim.world_size[0]:.2f} x {p_trim.world_size[1]:.2f} {p_trim.world_size_units}'
                items[s_id] = ((s_id, s_name, ''))

        was_items = bpy.app.driver_namespace.get(LITERAL_UV_WORLD_SIZE_TRIMS, {})
        if items != was_items:
            bpy.app.driver_namespace[LITERAL_UV_WORLD_SIZE_TRIMS] = items
        return bpy.app.driver_namespace.get(LITERAL_UV_WORLD_SIZE_TRIMS, {}).values()

    def get_trimsheet_with_size(self):
        p_items: dict = bpy.app.driver_namespace.get(LITERAL_UV_WORLD_SIZE_TRIMS, {})
        if self.trimsheet_index in range(len(self.trimsheet)):
            p_trim = self.trimsheet[self.trimsheet_index]
            if p_trim.uuid in p_items.keys():
                idx = list(p_items.keys()).index(p_trim.uuid)
                return idx
        return -1

    def set_trimsheet_with_size(self, value):
        p_items: dict = bpy.app.driver_namespace.get(LITERAL_UV_WORLD_SIZE_TRIMS, {})
        p_items_list = list(p_items.keys())
        if value in range(len(p_items_list)):
            p_uuid = p_items_list[value]

            for idx, p_trim in enumerate(self.trimsheet):
                if p_trim.uuid == p_uuid:
                    self.trimsheet_index = idx
                    break

    trimsheet_with_size: bpy.props.EnumProperty(
        name="Trims With World Size",
        items=get_trimsheet_with_size_items,
        get=get_trimsheet_with_size,
        set=set_trimsheet_with_size,
        options={'SKIP_SAVE'}
    )
