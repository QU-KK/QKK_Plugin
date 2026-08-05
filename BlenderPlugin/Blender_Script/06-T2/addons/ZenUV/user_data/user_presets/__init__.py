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

# Copyright 2024, Alex Zhornyak

import bpy
import os
import shutil
import json

from ZenUV.utils.blender_zen_utils import ZuvPresets, ZenPolls
from ZenUV.utils.vlog import Log


LITERAL_OPERATOR_DEFAULTS_CONFIG = "defaults.json"


class ZUV_OT_PresetsSaveOperatorDefault(bpy.types.Operator):
    bl_idname = 'wm.zenuv_presets_save_operator_default'
    bl_label = 'Save As Default'
    bl_description = 'Save default operator properties values'
    bl_options = {'REGISTER'}

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Defines what to save",
        items=[
            ("PROPERTY", "Property", "Save only active property"),
            ("OPERATOR", "Active Operator", "Save all properties of the active operator"),
            ("ALL", "All Operators", "Save default values of all available operators")
        ],
        default="ALL"
    )

    revert: bpy.props.BoolProperty(
        name="Revert",
        description="Revert to the initial state as it was deployed with the addon",
        default=False
    )

    op_id: bpy.props.StringProperty(
        name='Operator Identifier',
        description="Unique identifier of the active operator",
        default=""
    )

    op_property: bpy.props.StringProperty(
        name="Property Identifier",
        description="Unique identifier of the active operator's property",
        default=""
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        col = layout.column(align=False)
        col.use_property_split = True
        col.prop(self, "mode")
        col.prop(self, "revert")

        box = layout.box()

        wm = context.window_manager

        if self.mode == "ALL":
            box.label(text="Stored Operators:")
            for idx, op_id in enumerate(ZenPolls.map_operator_defaults.keys()):
                s_caption = op_id
                op_last = wm.operator_properties_last(op_id)
                if op_last:
                    s_caption = op_last.bl_rna.name
                box.label(text=f"  {idx + 1}) {s_caption}")
        else:
            op_last = wm.operator_properties_last(self.op_id)
            if op_last:
                box.label(text=f"Operator: {op_last.bl_rna.name}")
                if self.mode == "OPERATOR":
                    box.label(text="All properties will be saved!")
                elif self.mode == 'PROPERTY':
                    box.label(text=f"Property: {op_last.bl_rna.properties[self.op_property].name}")
                    if not self.revert:
                        box.label(text=f"Default: {repr(getattr(op_last, self.op_property))}")

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        try:
            if not self.op_id and self.mode in {"OPERATOR", "PROPERTY"}:
                raise RuntimeError("Operator identifier is not defined!")

            if not self.op_property and self.mode in {"PROPERTY"}:
                raise RuntimeError("Operator property is not defined!")

            wm = context.window_manager

            s_dir = ZuvPresets.force_full_preset_path(ZuvPresets.LITERAL_OPERATOR_DEFAULTS)
            if not os.path.exists(s_dir):
                raise RuntimeError(f"Directory: {s_dir} - does not exist!")

            s_op_config = os.path.join(s_dir, LITERAL_OPERATOR_DEFAULTS_CONFIG)

            def save_operator_defaults(op_id, p_props):
                op_last = wm.operator_properties_last(op_id)
                if not op_last:
                    raise RuntimeError(f"Can not retrieve {op_id} properties!")

                # NOTE: Do not use 'defaultdict' !
                if op_id not in ZenPolls.operator_defaults:
                    ZenPolls.operator_defaults[op_id] = dict()

                for prop in p_props:
                    if not hasattr(op_last, prop):
                        raise RuntimeError(f"Can not find property - {prop}!")

                    if self.revert:
                        if prop in ZenPolls.operator_defaults[op_id]:
                            del ZenPolls.operator_defaults[op_id][prop]
                    else:
                        ZenPolls.operator_defaults[op_id][prop] = getattr(
                            op_last, prop)

            if self.mode == "ALL":
                for op_id, op_props in ZenPolls.map_operator_defaults.items():
                    save_operator_defaults(op_id, op_props)
            elif self.mode == "OPERATOR":
                save_operator_defaults(self.op_id, ZenPolls.map_operator_defaults[self.op_id])
            else:
                save_operator_defaults(self.op_id, {self.op_property})

            with open(s_op_config, "w") as fout:
                fout.write(json.dumps(ZenPolls.operator_defaults, indent=4))

            self.report({'INFO'}, 'Restart Blender to apply updates!')

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_PresetsLoadDefault(bpy.types.Operator):
    bl_idname = 'wm.zenuv_presets_load_default'
    bl_label = 'Load Default Presets'
    bl_description = 'Copy default presets that are shipped with the addon'
    bl_options = {'REGISTER'}

    preset_folder: bpy.props.StringProperty(
        name='Preset Folder Name',
        default=''
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context: bpy.types.Context):
        try:
            if not self.preset_folder:
                raise RuntimeError('Preset folder name is not specified!')

            s_dir = os.path.dirname(__file__)
            s_source_path = os.path.join(s_dir, self.preset_folder)
            if not os.path.exists(s_source_path):
                raise RuntimeError(f'Preset folder - {self.preset_folder} does not exist!')

            s_target_path = os.path.join("presets", ZuvPresets.get_preset_path(self.preset_folder))
            s_target_path = bpy.utils.user_resource('SCRIPTS', path=s_target_path, create=True)

            shutil.copytree(s_source_path, s_target_path, dirs_exist_ok=True)

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


classes = (
    ZUV_OT_PresetsSaveOperatorDefault,
    ZUV_OT_PresetsLoadDefault,
)


def register():
    try:
        s_operator_defaults_dir = ZuvPresets.get_full_preset_path(ZuvPresets.LITERAL_OPERATOR_DEFAULTS)
        s_config = os.path.join(s_operator_defaults_dir, LITERAL_OPERATOR_DEFAULTS_CONFIG)
        if os.path.exists(s_config):
            with open(s_config) as json_cfg:
                ZenPolls.operator_defaults = json.load(json_cfg)

    except Exception as e:
        Log.error("LOAD OPERATOR DEFAULTS:", e)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
