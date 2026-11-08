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
from bl_operators.presets import ExecutePreset

from pathlib import Path

from .trimsheet_utils import ZuvTrimsheetUtils

from ...utils.blender_zen_utils import ZuvPresets, update_areas_in_all_screens
from ...utils.adv_generic_ui_list import ZenAddPresetBase


class ZUV_OT_TrimExecutePreset(bpy.types.Operator):
    bl_idname = "uv.zuv_execute_preset"
    bl_options = {'REGISTER', 'UNDO'}

    bl_label = 'Load Trimsheet Preset'
    bl_description = "Load trimsheet preset from file"

    filepath: bpy.props.StringProperty(
        subtype='FILE_PATH',
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    # we need this to prevent 'getattr()' is None
    menu_idname: bpy.props.StringProperty(
        name="Menu ID Name",
        description="ID name of the menu this was called from",
        options={'SKIP_SAVE', 'HIDDEN'},
        default='ZUV_MT_StoreTrimsheetPresets'
    )

    def get_preset_name(self):
        return Path(self.filepath).stem

    preset_name: bpy.props.StringProperty(
        name='Preset Name',
        get=get_preset_name
    )

    enable_confirmation: bpy.props.BoolProperty(
        name='Enable Confirmation',
        default=True
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if self.enable_confirmation:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        return self.execute(context)

    def execute(self, context):
        # Use this method because if it is inherited, can not change Blender theme !

        ZuvPresets.preset_file_patch(self.filepath)

        res = ExecutePreset.execute(self, context)

        update_areas_in_all_screens(context)

        return res


class ZUV_MT_StoreTrimsheetPresets(bpy.types.Menu):
    bl_label = 'Trimsheet Presets *'

    default_label = 'Trimsheet Presets *'

    preset_subdir = ZuvPresets.get_preset_path(ZuvTrimsheetUtils.TRIM_PRESET_SUBDIR)
    preset_operator = 'uv.zuv_execute_preset'

    draw = bpy.types.Menu.draw_preset


class ZUV_OT_TrimAddPreset(ZenAddPresetBase, bpy.types.Operator):
    bl_idname = 'uv.zuv_add_trimsheet_preset'
    bl_label = 'Add|Remove Preset'
    preset_menu = 'ZUV_MT_StoreTrimsheetPresets'

    @classmethod
    def description(cls, context, properties):
        if properties:
            return ('Remove' if properties.remove_active else 'Add') + ' trimsheet preset'
        else:
            return cls.bl_description

    # Common variable used for all preset values
    preset_defines = [
        'prefs = bpy.context.window_manager.zen_uv.get_trimsheet_data()'
    ]

    # Properties to store in the preset
    preset_values = [
        'prefs.trimsheet',
        'prefs.trimsheet_index',
    ]

    # Directory to store the presets
    preset_subdir = ZuvPresets.get_preset_path(ZuvTrimsheetUtils.TRIM_PRESET_SUBDIR)
