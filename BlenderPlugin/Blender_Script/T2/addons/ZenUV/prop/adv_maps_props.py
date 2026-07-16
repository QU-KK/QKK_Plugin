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

from ZenUV.utils.blender_zen_utils import _setnameex
from ZenUV.prop.common import update_addon_prop


class ZUV_AdvMapsRenameTemplateGroup(bpy.types.PropertyGroup):

    def set_name_ex(self, value):
        from ZenUV.prop.zuv_preferences import get_prefs

        def _collection_from_element(self):
            addon_prefs = get_prefs()
            return addon_prefs.adv_maps.rename_templates

        _setnameex(self, value, collection_from_element=_collection_from_element)

    name_ex: bpy.props.StringProperty(
        name='Name',
        description='Rename template name',
        get=lambda self: getattr(self, 'name', ''),
        set=set_name_ex,
        options={'HIDDEN', 'SKIP_SAVE'}
    )


class ZUV_AdvMapsProps(bpy.types.PropertyGroup):

    detect_uv_map_display_active: bpy.props.BoolProperty(
        name='Active Display',
        description='Detect synchronization status of active UV map for display and editing',
        default=True,
        update=update_addon_prop
    )

    detect_uv_map_render_active: bpy.props.BoolProperty(
        name='Render',
        description='Detect synchronization status of active UV map for rendering',
        default=True,
        update=update_addon_prop
    )

    detect_uv_map_position: bpy.props.BoolProperty(
        name='Position',
        description='Detect synchronization status of active UV map for rendering',
        default=True,
        update=update_addon_prop
    )

    rename_templates: bpy.props.CollectionProperty(
        name='Rename Templates',
        type=ZUV_AdvMapsRenameTemplateGroup
    )

    rename_templates_index: bpy.props.IntProperty(
        name='Rename Templates Index',
        min=-1,
        default=-1,
        update=update_addon_prop
    )

    def on_eye_dropper_object_enabled_update(self, context: bpy.types.Context):
        if not self.eye_dropper_object_enabled:
            wm = context.window_manager
            wm.zen_uv.obj_uvs.active_uv_object = None
            update_addon_prop(self, context)

    eye_dropper_object_enabled: bpy.props.BoolProperty(
        name='Enable Object Eye Dropper',
        description='Warning! If enabled active object becomes multi-user',
        default=True,
        update=on_eye_dropper_object_enabled_update
    )


class ZUV_AdvMapsSceneProps(bpy.types.PropertyGroup):
    sync_adv_maps: bpy.props.BoolProperty(
        name='Multi UV Maps Mode',
        description='Set active UV map for display, editing and rendering to all selected or active object',
        default=True
    )

    transfer_mode: bpy.props.EnumProperty(
        name='Transfer Mode',
        description='Copy UV maps mode which depends on matching geometry or not',
        items=[
            ('MATCH_GEOMETRY', 'Matching geometry', 'Objects must be of type mesh and must have a matching topology'),
            ('ADVANCED', 'Advanced', 'Transfer UV maps by generating an interpolated mapping between source and target mesh elements'),
            ('LAYOUT', 'Layout', 'Transfer layout of UV maps from active to selected meshes'),
        ],
        default='MATCH_GEOMETRY',
        options=set()
    )

    sync_seams: bpy.props.BoolProperty(
        name='Sync Seams By UV Islands',
        description="Seams are updated by UV islands that are present in UV Map",
        options=set()
    )
