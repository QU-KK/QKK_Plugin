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
from bl_operators.presets import AddPresetOperator
from bl_operators.wm import rna_path_prop, context_path_validate, context_path_to_rna_property
from bpy_extras.io_utils import ImportHelper, ExportHelper

from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens, reset_properties_modified, ZenPolls
from ZenUV.prop.zuv_preferences import get_prefs


class FakeContext:
    def __init__(self, d: dict = None):
        if d is not None:
            for key, value in d.items():
                setattr(self, key, value)

    def copy(self):
        return {k: v for k, v in self.__dict__.items() if k[:1] != '_' and k != 'copy'}


class ZUV_OT_UpdateToggle(bpy.types.Operator):
    bl_idname = 'wm.zenuv_update_toggle'
    bl_label = 'Toggle Value'
    bl_description = 'Toggles value with updating viewports'
    bl_options = {'INTERNAL'}

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def execute(self, context: bpy.types.Context):
        bpy.ops.wm.context_toggle('INVOKE_DEFAULT', data_path=self.data_path)
        update_areas_in_all_screens(context)
        return {'FINISHED'}


class ZUV_OT_ScriptExec(bpy.types.Operator):
    bl_idname = 'wm.zenuv_script_exec'
    bl_label = 'Exec Script'
    bl_description = ''
    bl_options = {'INTERNAL'}

    script: bpy.props.StringProperty(
        name="Script",
        description="Must be valid python script code in 1 line",
        options={"SKIP_SAVE"})
    desc: bpy.props.StringProperty(
        name="Description",
        description="Operator description in UI",
        options={"SKIP_SAVE"})
    return_value: bpy.props.StringProperty(
        name='Return Value',
        description='Operator return value. Use "PASS_THROUGH" if you would like to run other operator',
        default="{'FINISHED'}",
        options={"SKIP_SAVE"}
    )
    redraw_areas: bpy.props.BoolProperty(
        name='Redraw Areas',
        description='Redraw all UV, View3D areas after execution',
        default=True,
        options={"SKIP_SAVE"}
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        return properties.desc if properties else ''

    def execute(self, context: bpy.types.Context):

        # CONVINIENCE IMPORTS
        import mathutils  # noqa
        import math       # noqa

        # CONVINIENCE VARIABLES
        C, D, P = context, bpy.data, get_prefs()  # noqa

        exec(self.script)

        if self.redraw_areas:
            update_areas_in_all_screens(context)

        t_res = eval(self.return_value)

        if 'FINISHED' in t_res:
            bpy.ops.ed.undo_push(message=self.desc if self.desc else self.bl_idname)

        return t_res


class ZUV_OT_TextExec(bpy.types.Operator):
    bl_idname = 'wm.zenuv_text_exec'
    bl_label = 'Exec Text'
    bl_description = ''
    bl_options = {'INTERNAL'}

    script: bpy.props.StringProperty(
        name="Script Text",
        description="Name of the valid script text datablock",
        options={"SKIP_SAVE"})
    desc: bpy.props.StringProperty(
        name="Description",
        description="Operator description in UI",
        options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        return properties.desc if properties else ''

    def execute(self, context: bpy.types.Context):
        try:
            p_text = bpy.data.texts.get(self.script, None)
            if p_text is None:
                raise RuntimeError(f"Can not find - {self.script}")

            ctx_override = context.copy()
            ctx_override['edit_text'] = p_text

            if ZenPolls.version_since_3_2_0:
                with bpy.context.temp_override(**ctx_override):
                    bpy.ops.text.run_script()
            else:
                bpy.ops.text.run_script(ctx_override)

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_Report(bpy.types.Operator):
    bl_idname = 'wm.zenuv_report'
    bl_label = 'Report'
    bl_description = ''
    bl_options = {'INTERNAL'}

    severity: bpy.props.EnumProperty(
        name="Severity",
        description="Message severity",
        items=[
            ("INFO", "Info", "Informataion message"),
            ("WARNING", "Warning", "Warning message"),
            ("ERROR", "Error", "Error message"),
        ],
        default="INFO"
    )

    message: bpy.props.StringProperty(
        name="Message",
        description="Text message that will be displayed",
        default=""
    )

    def execute(self, context: bpy.types.Context):
        self.report({self.severity}, self.message)
        return {'FINISHED'}


class WM_OT_zenuv_operator_defaults(bpy.types.Operator):
    bl_idname = "wm.zenuv_operator_defaults"
    bl_label = "Restore Operator Defaults"
    bl_description = "Set operator to its default values"

    operator: bpy.props.StringProperty(
        name="Operator",
        maxlen=64,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    menu: bpy.props.StringProperty(
        name="Menu",
        maxlen=64,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    def execute(self, context: bpy.types.Context):
        wm = context.window_manager
        op_props = wm.operator_properties_last(self.operator)
        if op_props:
            reset_properties_modified(op_props)
            if self.menu:
                p_menu = getattr(bpy.types, self.menu, None)
                if p_menu:
                    p_menu.bl_label = "Operator Presets"

        return {'FINISHED'}


class WM_MT_zenuv_operator_presets(bpy.types.Menu):
    bl_label = "Operator Presets"

    def draw(self, context):
        # NOTE: require manually created 'context.active_operator_properties'
        self.operator = context.active_operator_properties.bl_rna.identifier

        layout = self.layout
        op = layout.operator(WM_OT_zenuv_operator_defaults.bl_idname)
        op.operator = self.operator
        op.menu = self.bl_idname
        layout.separator()

        bpy.types.Menu.draw_preset(self, context)

    @property
    def preset_subdir(self):
        return AddPresetOperator.operator_path(self.operator)

    preset_operator = "script.execute_preset"


class ZUV_OT_ImportFromJson(bpy.types.Operator, ImportHelper):
    bl_idname = "wm.zenuv_import_from_json"
    bl_label = "Import From Json"
    bl_description = "Import RNA struct from json file"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    data_path: rna_path_prop

    desc: bpy.props.StringProperty(
        name="Description",
        description="String variable for operator description",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        try:
            if properties:
                if properties.desc:
                    return properties.desc

                if properties.data_path:
                    s_suffix = ''
                    rna_prop = context_path_to_rna_property(context, properties.data_path)
                    if rna_prop:
                        if rna_prop.description:
                            s_suffix = rna_prop.description
                        else:
                            p_rna_data = context_path_validate(context, properties.data_path)
                            if p_rna_data:
                                bl_rna = getattr(p_rna_data, 'bl_rna', None)
                                if bl_rna:
                                    s_suffix = bl_rna.name
                    if s_suffix:
                        return f'Import from json: {s_suffix}'
        except Exception:
            pass
        return cls.bl_description

    def execute(self, context):
        try:
            p_rna_data = context_path_validate(context, self.data_path)
            if p_rna_data is Ellipsis:
                return {'CANCELLED'}

            reset_properties_modified(p_rna_data)

            errors_list = []

            from ..utils.group_dict_utils import load_group_from_json
            if load_group_from_json(p_rna_data, self.filepath, errors_list=errors_list) is not None:
                self.report({'INFO'}, "Imported Successfully!")

            for item in errors_list:
                self.report({'WARNING'}, item)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to Import: {e}")
        return {'FINISHED'}


class ZUV_OT_ExportToJson(bpy.types.Operator, ExportHelper):
    bl_idname = "wm.zenuv_export_to_json"
    bl_label = "Export To Json"
    bl_description = "Export RNA struct to json file"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    data_path: rna_path_prop

    desc: bpy.props.StringProperty(
        name="Description",
        description="String variable for operator description",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        try:
            if properties:
                if properties.desc:
                    return properties.desc

                if properties.data_path:
                    s_suffix = ''
                    rna_prop = context_path_to_rna_property(context, properties.data_path)
                    if rna_prop:
                        if rna_prop.description:
                            s_suffix = rna_prop.description
                        else:
                            p_rna_data = context_path_validate(context, properties.data_path)
                            if p_rna_data:
                                bl_rna = getattr(p_rna_data, 'bl_rna', None)
                                if bl_rna:
                                    s_suffix = bl_rna.name
                    if s_suffix:
                        return f'Import from json: {s_suffix}'
        except Exception:
            pass
        return cls.bl_description

    def execute(self, context: bpy.types.Context):
        try:
            p_rna_data = context_path_validate(context, self.data_path)
            if p_rna_data is Ellipsis:
                return {'CANCELLED'}

            from ..utils.group_dict_utils import save_group_to_json
            if save_group_to_json(p_rna_data, self.filepath) is not None:
                self.report({'INFO'}, f"Exported Successfully to: {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to Export: {e}")
        return {'FINISHED'}


context_utils_classes = (
    ZUV_OT_UpdateToggle,
    ZUV_OT_ScriptExec,
    ZUV_OT_TextExec,
    ZUV_OT_Report,

    ZUV_OT_ImportFromJson,
    ZUV_OT_ExportToJson,

    WM_OT_zenuv_operator_defaults,
    WM_MT_zenuv_operator_presets
)
