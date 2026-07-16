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

import os
import json

from .version import UvpmVersionInfo
from .utils import get_prefs, in_debug_mode, print_backtrace, redraw_ui, print_warning
from .box_utils import disable_box_rendering
from .os_iface import os_simulate_esc_event
from .spipeline.engine.types import UvpmAxis, UvpmCoordSpace, UvpmSimilarityMode, UvpmScaleMode
from .operator_generic import UVPM4_OT_Generic
from .operator import OpConfirmationMsgMixin
from .pgroup import StandalonePropertyGroupBase
from .props import PropConstants
from .app_iface import *


PRESET_FILENAME_EXT = "uvpmp"
PRESET_FILENAME_DOT_EXT = '.' + PRESET_FILENAME_EXT


class UVPM4_PT_PresetsBase(PresetPanel):

    show_remove_button = True
    show_save_button = True
    show_reset_button = False
    load_operator_label = "Load"

    DEFAULT_PRESET_NAME = "untitled{}".format(PRESET_FILENAME_DOT_EXT)

    @staticmethod
    def get_load_operator_idname():
        return UVPM4_OT_LoadPreset.bl_idname

    @staticmethod
    def get_save_operator_idname():
        return UVPM4_OT_SavePreset.bl_idname
    
    def init_load_save_operator(self, op):
        pass

    def get_preset_path(self):
        prefs = get_prefs()
        return prefs.get_main_preset_path()

    def get_preset_dot_ext(self):
        return PRESET_FILENAME_DOT_EXT

    def get_default_preset_name(self):
        return self.DEFAULT_PRESET_NAME

    def is_save_button_enabled(self):
        return True

    def draw(self, context):
        preset_path = self.get_preset_path()

        layout = self.layout
        layout.emboss = 'PULLDOWN_MENU'

        layout.label(text=self.bl_label)

        column = layout.column(align=True)
        presets_info = self.get_presets_info(preset_path)
        for preset_file, preset_name in presets_info:
            row = column.row(align=True)
            op = row.operator(self.get_load_operator_idname(), text=preset_name)
            self.init_load_save_operator(op)
            op.invoke_default = False
            op.filepath = preset_file
            if self.show_remove_button:
                row.operator_context = 'INVOKE_DEFAULT'
                op = row.operator('uvpackmaster4.remove_preset', text='', icon="REMOVE")
                op.filepath = preset_file

        column = layout.column(align=True)
        column.operator_context = 'INVOKE_DEFAULT'
        row = column.row(align=True)
        if self.show_save_button:
            sub = row.row()
            sub.enabled = self.is_save_button_enabled()
            op = sub.operator(self.get_save_operator_idname(), text="Save")
            self.init_load_save_operator(op)
            op.filepath = os.path.join(preset_path, self.get_default_preset_name())
        op = row.operator(self.get_load_operator_idname(), text=self.load_operator_label)
        self.init_load_save_operator(op)
        op.filepath = os.path.join(preset_path, "")
        if self.show_reset_button:
            row = column.row(align=True)
            row.operator(UVPM4_OT_ResetToDefaults.bl_idname)

    def get_presets_info(self, preset_path):
        if not os.path.exists(preset_path):
            return []
        presets_info = [(os.path.join(preset_path, f), f[:-len(self.get_preset_dot_ext())]) for f in os.listdir(preset_path)
                        if os.path.isfile(os.path.join(preset_path, f)) and f.endswith(self.get_preset_dot_ext())]
        presets_info.sort(key=lambda x: x[0])
        return presets_info


class UVPM4_PT_Presets(UVPM4_PT_PresetsBase, Panel):

    bl_label = 'Option Presets'
    load_operator_label = "Open"
    show_reset_button = True


class UVPM4_PT_PresetsCustomTargetBox(UVPM4_PT_PresetsBase, Panel):

    bl_label = 'Load Box From Preset'
    show_remove_button = False
    show_save_button = False

    @staticmethod
    def get_load_operator_idname():
        return UVPM4_OT_LoadTargetBox.bl_idname


class UVPM4_OT_RemovePreset(Operator):

    bl_idname = 'uvpackmaster4.remove_preset'
    bl_label = 'Remove Preset'
    bl_description = 'Remove the selected preset from the disk'
    bl_options = {'INTERNAL'}
    filepath : StringProperty(name="File Path", description="Filepath used for importing the file", subtype="FILE_PATH")

    def execute(self, context):
        if self.filepath and os.path.exists(self.filepath):
            try:
                os.remove(self.filepath)
            except:
                self.report({'ERROR'}, 'Cannot delete "{}" preset file: '.format(self.filepath))
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text='Are you sure you want to delete "{}"?'.format(os.path.basename(self.filepath)))


class PresetFilenameMixin:

    filename_ext = PRESET_FILENAME_DOT_EXT
    filter_glob : StringProperty(
        default="*{}".format(PRESET_FILENAME_DOT_EXT),
        options={'HIDDEN'},
        )


class UVPM4_OT_SavePresetBase(UVPM4_OT_Generic):

    props_to_filter = None

    def get_props(self, props_collection, props_to_filter):
        props_dict = {}
        
        for prop_name, prop_struct in AppInterface.object_property_data(props_collection).items():
            if not prop_struct.is_runtime:
                continue
            prop_value = getattr(props_collection, prop_name)

            if prop_struct.type in ['BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM']:
                if props_to_filter is not None and props_to_filter.get(prop_name, False):
                    continue
                if getattr(prop_struct, 'is_array', False):
                    prop_value = tuple(prop_value)
                props_dict[prop_name] = prop_value

            elif prop_struct.type == 'POINTER':
                pointer_props_to_filter = props_to_filter.get(prop_name) if props_to_filter is not None else None
                if isinstance(pointer_props_to_filter, bool) and pointer_props_to_filter:
                    continue
                if not isinstance(pointer_props_to_filter, dict):
                    pointer_props_to_filter = None
                props_dict[prop_name] = self.get_props(prop_value, pointer_props_to_filter)

            elif prop_struct.type == 'COLLECTION' and len(prop_value) > 0:
                if props_to_filter is not None and props_to_filter.get(prop_name, False):
                    continue
                props_dict[prop_name] = [self.get_props(v, None) for v in prop_value]

        return props_dict

    def execute(self, context):
        try:
            props = self.get_collection_props(context)
            props_dict = self.get_props(props, self.props_to_filter)

            json_struct = {
                'version_major': UvpmVersionInfo.ADDON_VERSION_MAJOR,
                'version_minor': UvpmVersionInfo.ADDON_VERSION_MINOR,
                'version_patch': UvpmVersionInfo.ADDON_VERSION_PATCH
            }
            self.set_preset_version(json_struct)
            json_struct['properties'] = props_dict

            json_str = json.dumps(json_struct)
            
            with open(self.filepath, "w") as file:
                file.write(json_str)
                
            self.report({'INFO'}, 'Preset saved')

        except RuntimeError as ex:
            if in_debug_mode():
                print_backtrace(ex)

            self.report({'ERROR'}, str(ex))

        except Exception as ex:
            self.handle_unexpected_error(ex)

        return {'FINISHED'}

    def draw(self, context):
        pass

    def post_op(self):
        pass


class UVPM4_OT_SavePreset(UVPM4_OT_SavePresetBase, ExportHelper, PresetFilenameMixin):

    bl_idname = 'uvpackmaster4.save_preset'
    bl_label = 'Save Preset'
    bl_description = 'Save all packer options to a file'

    props_to_filter = {
        'name': True,
        'uuid': True,
        'grouping_schemes': True,
        'grouping_scheme_access_descriptors': True,
        'scripting': {
            'packing': {
                'before_op': True,
                'after_op': True
            }
        },
        'scripted_props': True,
        'saved_m_panel_settings': True,
        'saved_panel_settings': True,
        'numbered_groups_descriptors': {
            'lock_group': {
                'iparam_name': True
            },
            'stack_group': {
                'iparam_name': True
            },
            'track_group': {
                'iparam_name': True
            },
            'norm_group': {
                'iparam_name': True
            }
        }
    }

    def get_collection_props(self, context):
        return get_main_props(context)

    def set_preset_version(self, json_struct):
        json_struct['preset_version'] = UvpmVersionInfo.PRESET_VERSION


class LoadPresetInvokeHelper:

    invoke_default : BoolProperty(options={'HIDDEN', 'SKIP_SAVE'}, default=True)

    def invoke(self, context, event):
        if self.invoke_default:
            return super().invoke(context, event)

        return self.execute(context)


class PresetLoader:

    PROPS_TO_LOAD_DEFAULT = True
    PROPS_TO_LOAD = {}

    class PropTranslator:

        @staticmethod
        def translate_tdensity_s(td):
            td_dict = {}
            val_dict = {}
            val_dict['view_val'] = float(td)
            val_dict['s_val'] = str(td)

            td_dict['val'] = val_dict

            from .tdensity.tier import TDensityTierValueMode
            td_dict['mode'] = TDensityTierValueMode.DIRECT_VALUE.value()
            return td_dict

        def __init__(self, default_target=None, default_source=None):
            self.default_target = default_target
            self.default_source = default_source
  
        def translate(self, new_id, old_id, converter=lambda v: v, target=None, source=None):
            if target is None:
                target = self.default_target

            if source is None:
                source = self.default_source

            target[new_id] = converter(source[old_id])
            del source[old_id]

        def translate_tdensity(self, new_id, old_id, target=None, source=None):
            self.translate(new_id, old_id, source=source, target=target, converter=self.translate_tdensity_s)


    @staticmethod
    def raise_invalid_format():
        raise RuntimeError('Invalid preset format')

    def __init__(self, filepath, target, props_dict=None):
        self.filepath = filepath
        self.target = target
        self.props_to_load = self.PROPS_TO_LOAD
        self.props_to_load_default = self.PROPS_TO_LOAD_DEFAULT

        self.props_dict = props_dict if props_dict is not None else self.read_preset()

    def get_preset_version(self, json_struct):
        return 0

    def validate_preset_version(self, preset_version):
        return True
    
    def translate_props(self, preset_version, props_dict):
        pass

    def read_preset(self):
        with open (os.path.join(self.filepath), "r") as file:
            json_str = file.read()
            
        try:
            json_struct = json.loads(json_str)
        except:
            self.raise_invalid_format()

        if type(json_struct) is not dict:
            self.raise_invalid_format()

        try:
            addon_version_saved = (json_struct['version_major'], json_struct['version_minor'], json_struct['version_patch'])
            preset_version = self.get_preset_version(json_struct)
            props_dict = json_struct['properties']
        except:
            self.raise_invalid_format()

        if not self.validate_preset_version(preset_version):
            raise RuntimeError('Unsupported preset version - upgrade to the latest UVPackmaster addon release')

        self.translate_props(preset_version, props_dict)
        return props_dict
    
    def report_property_problem(self, name, extra=""):
        self.preset_loaded_with_warning = True
        print_warning("Cannot load '{}' from the preset.{} Property restored to default.".format(name, extra))

    def try_setattr(self, collection, name, value):
        try:
            if isinstance(collection, StandalonePropertyGroupBase):
                collection.cast_setattr(name, value)
            else:
                setattr(collection, name, value)
        except:
            self.report_property_problem(name)
            collection.property_unset(name)

    def set_props(self, props_collection, props_dict, props_to_load):
        for prop_name, prop_struct in AppInterface.object_property_data(props_collection).items():
            load_prop = self.props_to_load_default
            if isinstance(props_to_load, dict):
                load_prop = props_to_load.get(prop_name, self.props_to_load_default)
            elif isinstance(props_to_load, bool):
                load_prop = props_to_load
            if not load_prop:
                continue

            if not prop_struct.is_runtime:
                continue
            if prop_name not in props_dict:
                props_collection.property_unset(prop_name)
                continue

            prop_value = props_dict[prop_name]
            if prop_struct.type in ['BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM']:
                self.try_setattr(props_collection, prop_name, prop_value)
            elif prop_struct.type == 'POINTER':
                if isinstance(prop_value, dict):
                    self.set_props(getattr(props_collection, prop_name), prop_value, load_prop)
                else:
                    props_collection.property_unset(prop_name)
                    self.report_property_problem(prop_name)

            elif prop_struct.type == 'COLLECTION':
                props_collection.property_unset(prop_name)
                prop_coll = getattr(props_collection, prop_name)
                if isinstance(prop_value, list):
                    for prop_element_idx, prop_element in enumerate(prop_value):
                        if not isinstance(prop_element, dict):
                            self.report_property_problem(prop_name, " Invalid collection element({}).".format(prop_element_idx))
                            continue
                        new_element = prop_coll.add()
                        self.set_props(new_element, prop_element, load_prop)
                else:
                    self.report_property_problem(prop_name)

        return props_dict
    
    def load(self):
        self.set_props(self.target, self.props_dict, self.props_to_load)


class UVPM4_OT_LoadPresetBase(UVPM4_OT_Generic):

    LOADER_TYPE = None

    preset_loaded_with_warning = False
    success_msg = 'Preset loaded.'
    success_msg_type = {'INFO'}

    loader = None
    main_props = None
    should_show_confirm_popup = False

    def show_confirm_popup(self, context):
        return False
    
    def load_properties(self):
        self.loader.load()

    def execute(self, context):
        try:
            self.context = context
            self.main_props = get_main_props(context)

            if self.loader is None:
                self.loader = self.LOADER_TYPE(
                    target=self.get_target(),
                    filepath=self.filepath)

            if not self.should_show_confirm_popup and self.show_confirm_popup(context):
                self.should_show_confirm_popup = True
                return context.window_manager.invoke_props_dialog(self, width=600)

            self.load_properties()
            self.post_op()
            redraw_ui(context)

            if self.preset_loaded_with_warning:
                self.success_msg_type = {'WARNING'}
                self.success_msg = "{} Not all properties have not been loaded, see the console for more information.".format(self.success_msg)
            self.report(self.success_msg_type, self.success_msg)

        except RuntimeError as ex:
            if in_debug_mode():
                print_backtrace(ex)

            self.report({'ERROR'}, str(ex))

        except Exception as ex:
            self.handle_unexpected_error(ex)

        os_simulate_esc_event()
        return {'FINISHED'}

    def post_op(self):
        pass
    
    def draw(self, context):
        pass


class MainPropsPresetLoader(PresetLoader):

    PROPS_TO_LOAD_DEFAULT = True
    PROPS_TO_LOAD = {
        'name': False,
        'uuid': False,
        'grouping_schemes': False,
        'grouping_scheme_access_descriptors': False,
        'scripting': {
            'packing': {
                'before_op': False,
                'after_op': False
            }
        },
        'scripted_props' : False,
        'saved_m_panel_settings' : False,
        'saved_panel_settings' : False
    }

    def translate_props_11to12(self, props_dict):
        props_dict['island_scale_limit_enable'] = False
        props_dict['island_scale_limit'] = 0

    def translate_props_12to13(self, props_dict):
        pass

    def translate_props_13to14(self, props_dict):
        pass

    def translate_props_14to15(self, props_dict):
        props_dict['simi_mode'] = (UvpmSimilarityMode.VERTEX_POSITION if props_dict['simi_check_vertices'] else UvpmSimilarityMode.BORDER_SHAPE).value()
        del props_dict['simi_check_vertices']

    def translate_props_15to16(self, props_dict):
        pass

    def translate_props_16to17(self, props_dict):
        props_dict['flipping_enable'] = False
        props_dict['simi_match_3d_axis'] = UvpmAxis.NONE.value()
        props_dict['simi_match_3d_axis_space'] = UvpmCoordSpace.LOCAL.value()

    def translate_props_17to18(self, props_dict):
        props_dict['orient_prim_3d_axis'] = PropConstants.ORIENT_PRIM_3D_AXIS_DEFAULT
        props_dict['orient_prim_uv_axis'] = PropConstants.ORIENT_PRIM_UV_AXIS_DEFAULT
        props_dict['orient_sec_3d_axis'] = PropConstants.ORIENT_SEC_3D_AXIS_DEFAULT
        props_dict['orient_sec_uv_axis'] = PropConstants.ORIENT_SEC_UV_AXIS_DEFAULT
        props_dict['orient_prim_sec_bias'] = PropConstants.ORIENT_PRIM_SEC_BIAS_DEFAULT
        props_dict['orient_to_3d_axes_space'] = UvpmCoordSpace.LOCAL.value()

    def translate_props_18to19(self, props_dict):
        pass

    def translate_props_19to20(self, props_dict):
        pass

    def translate_props_20to21(self, props_dict):
        def init_desc(name_prefix):
            enable_prop_id = "{}_groups_enable".format(name_prefix)
            num_prop_id = "{}_group_num".format(name_prefix)

            desc = {
                'enable' : props_dict.get(enable_prop_id, False),
                'group_num' : props_dict.get(num_prop_id, 1)
            }

            try:
                del props_dict[enable_prop_id]
                del props_dict[num_prop_id]
            except:
                pass

            return desc     

        numbered_groups_descriptors = {
            'lock_group' : init_desc('lock'),
            'stack_group' : init_desc('stack')
        }

        props_dict['numbered_groups_descriptors'] = numbered_groups_descriptors
        props_dict['split_overlap_detection_mode'] = '0'

    def translate_props_21to22(self, props_dict):
        pass

    def translate_props_22to23(self, props_dict):
        props_dict['normalize_scale'] = props_dict['normalize_islands']
        del props_dict['normalize_islands']

        props_dict['simi_check_holes'] = False

    def translate_props_23to24(self, props_dict):
        pass

    def translate_props_24to25(self, props_dict):
        props_dict['scripting'] = {
            'packing': {}
        }

    def translate_props_25to26(self, props_dict):
        props_dict['split_overlap_max_tile_x'] = 0

    def translate_props_26to27(self, props_dict):
        props_dict['simi_non_uniform_scaling_tolerance'] = 0.0

    def translate_props_27to28(self, props_dict):
        del props_dict['island_scale_limit_enable']
        del props_dict['island_scale_limit']

    def translate_props_28to29(self, props_dict):
        props_dict['pixel_border_margin'] = props_dict['pixel_padding']
        del props_dict['pixel_padding']

    def translate_props_29to30(self, props_dict):
        props_dict['scale_mode'] = (UvpmScaleMode.FIXED_SCALE if props_dict['fixed_scale'] else UvpmScaleMode.MAX_SCALE).value()
        del props_dict['fixed_scale']

    def translate_props_30to31(self, props_dict):
        pass

    def translate_props_31to32(self, props_dict):
        props_dict['split_props'] = {
            'detection_mode': props_dict['split_overlap_detection_mode'],
            'max_tile_x': props_dict['split_overlap_max_tile_x']
        }

        del props_dict['split_overlap_detection_mode']
        del props_dict['split_overlap_max_tile_x']

    def translate_props_32to33(self, props_dict):
        props_dict['tdensity_enable'] = False
        props_dict['tdensity_value'] = 0

    def translate_props_33to34(self, props_dict):
        props_dict['tdensity_set_before_pack'] = props_dict['tdensity_enable']
        del props_dict['tdensity_enable']

    def translate_props_34to35(self, props_dict):
        pass

    def translate_props_35to36(self, props_dict):
        if props_dict['pixel_border_margin'] > 0:
            props_dict['pixel_border_margin_enable'] = True

        else:
            props_dict['pixel_border_margin_enable'] = False
            props_dict['pixel_border_margin'] = 1

    def translate_props_36to37(self, props_dict):
        norm_group_dict = {
            'enable': False,
            'group_num': 1,
            'use_g_scheme': False
        }
        
        props_dict['numbered_groups_descriptors']['norm_group'] = norm_group_dict

    def translate_props_37to38(self, props_dict):  
        tr = self.PropTranslator(default_target=props_dict, default_source=props_dict)
        tr.translate('active_pack_mode_id', 'active_main_mode_id')
        
        tr.translate_tdensity('tdensity_to_set', 'tdensity_value')
        props_dict['tdensity_packing'] = tr.translate_tdensity_s(0)
        props_dict['island_tdensity_packing'] = tr.translate_tdensity_s(0)

        tr.translate('non_square_packing', 'tex_ratio')
        tr.translate('group_method_pack', 'group_method')

        tile_target_props_dict = {}
        from .spipeline.engine.types import TileTargetMode
        tile_target_props_dict['mode'] = TileTargetMode.TILE_GRID.value()
        tr.translate('use_editor_grid', 'use_blender_tile_grid', target=tile_target_props_dict)
        tr.translate('tile_count_x', 'tile_count_x', target=tile_target_props_dict)
        tr.translate('tile_count_y', 'tile_count_y', target=tile_target_props_dict)
        tile_target_props_dict['start_tile_x'] = 0
        tile_target_props_dict['start_tile_y'] = 0
        tile_target_props_dict['tile_count'] = 1
        tile_target_props_dict['tiles_in_row'] = 10

        props_dict['tile_target_props'] = tile_target_props_dict

        simi_props_dict = {}
        tr.translate('simi_mode', 'simi_mode', target=simi_props_dict)
        tr.translate('threshold', 'simi_threshold', target=simi_props_dict)
        tr.translate('check_holes', 'simi_check_holes', target=simi_props_dict)
        tr.translate('adjust_scale', 'simi_adjust_scale', target=simi_props_dict)
        tr.translate('non_uniform_scaling_tolerance', 'simi_non_uniform_scaling_tolerance', target=simi_props_dict)
        tr.translate('match_3d_axis', 'simi_match_3d_axis', target=simi_props_dict)
        tr.translate('match_3d_axis_space', 'simi_match_3d_axis_space', target=simi_props_dict)
        tr.translate('correct_vertices', 'simi_correct_vertices', target=simi_props_dict)
        tr.translate('vertex_threshold', 'simi_vertex_threshold', target=simi_props_dict)

        props_dict['simi_props'] = simi_props_dict

        orient_to3d_props_dict = {}
        tr.translate('prim_3d_axis', 'orient_prim_3d_axis', target=orient_to3d_props_dict)
        tr.translate('prim_uv_axis', 'orient_prim_uv_axis', target=orient_to3d_props_dict)
        tr.translate('sec_3d_axis', 'orient_sec_3d_axis', target=orient_to3d_props_dict)
        tr.translate('sec_uv_axis', 'orient_sec_uv_axis', target=orient_to3d_props_dict)
        tr.translate('axes_space', 'orient_to_3d_axes_space', target=orient_to3d_props_dict)
        tr.translate('prim_sec_bias', 'orient_prim_sec_bias', target=orient_to3d_props_dict)

        props_dict['orient_to3d_props'] = orient_to3d_props_dict

        del props_dict['auto_group_options']['automatic']
        tr.translate('tile_count_per_group', 'tile_count_per_group', target=props_dict['auto_group_options'], source=props_dict['auto_group_options']['base'])
        tr.translate('grouping_compactness', 'group_compactness', target=props_dict['auto_group_options']['base'], source=props_dict['auto_group_options']['base'])
        props_dict['auto_group_options']['base']['dynamic_tiles_all'] = False
        props_dict['auto_group_options']['base']['atlas_size_x'] = 2
        props_dict['auto_group_options']['base']['atlas_size_y'] = 2
        
    def translate_props(self, preset_version, props_dict):
        translate_array = [
            self.translate_props_11to12,
            self.translate_props_12to13,
            self.translate_props_13to14,
            self.translate_props_14to15,
            self.translate_props_15to16,
            self.translate_props_16to17,
            self.translate_props_17to18,
            self.translate_props_18to19,
            self.translate_props_19to20,
            self.translate_props_20to21,
            self.translate_props_21to22,
            self.translate_props_22to23,
            self.translate_props_23to24,
            self.translate_props_24to25,
            self.translate_props_25to26,
            self.translate_props_26to27,
            self.translate_props_27to28,
            self.translate_props_28to29,
            self.translate_props_29to30,
            self.translate_props_30to31,
            self.translate_props_31to32,
            self.translate_props_32to33,
            self.translate_props_33to34,
            self.translate_props_34to35,
            self.translate_props_35to36,
            self.translate_props_36to37,
            self.translate_props_37to38
        ]

        for i in range(preset_version - UvpmVersionInfo.PRESET_VERSION_FIRST_SUPPORTED, len(translate_array)):
            translate_array[i](props_dict)

    def get_preset_version(self, json_struct):
        return json_struct['preset_version']

    def validate_preset_version(self, preset_version):
        return preset_version in range(UvpmVersionInfo.PRESET_VERSION_FIRST_SUPPORTED, UvpmVersionInfo.PRESET_VERSION+1)


class UVPM4_OT_LoadMainPropsPreset(UVPM4_OT_LoadPresetBase):

    LOADER_TYPE = MainPropsPresetLoader

    def get_target(self):
        return self.main_props


class UVPM4_OT_LoadPreset(LoadPresetInvokeHelper, UVPM4_OT_LoadMainPropsPreset, ImportHelper, PresetFilenameMixin):

    bl_idname = 'uvpackmaster4.load_preset'
    bl_label = 'Open Preset'
    bl_options = {'UNDO'}
    bl_description = 'Load all packer options from a file'

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text='Are you sure you want to continue?')


class TargetBoxPresetLoader(MainPropsPresetLoader):

    PROPS_TO_LOAD_DEFAULT = False
    PROPS_TO_LOAD = {
        'custom_target_box': True
    }


class UVPM4_OT_LoadTargetBox(LoadPresetInvokeHelper, UVPM4_OT_LoadMainPropsPreset, ImportHelper, PresetFilenameMixin):

    bl_idname = 'uvpackmaster4.load_target_box'
    bl_label = 'Load Box From Preset'
    bl_options = {'UNDO'}
    bl_description = 'Load target box coordinates from a preset file'

    LOADER_TYPE = TargetBoxPresetLoader

    success_msg = 'Box loaded.'


class ResetToDefaultsPresetLoader(MainPropsPresetLoader):

    PROPS_TO_LOAD_DEFAULT = True
    PROPS_TO_LOAD = {
        'name': False,
        'uuid': False,
        'grouping_schemes': False,
        'grouping_scheme_access_descriptors': False,
        'scripting': {
            'packing': {
                'before_op': False,
                'after_op': False
            }
        },
        'saved_m_panel_settings' : False,
        'saved_panel_settings' : False
    }


class UVPM4_OT_ResetToDefaults(OpConfirmationMsgMixin, UVPM4_OT_LoadMainPropsPreset):

    bl_idname = 'uvpackmaster4.reset_to_defaults'
    bl_label = 'Reset To Defaults'
    bl_description = 'Reset all UVPM parameters to default values'

    CONFIRMATION_MSG = 'Are you sure you want to reset all UVPM parameters to default values?'

    LOADER_TYPE = ResetToDefaultsPresetLoader
    
    def execute(self, context):
        self.context = context
        self.main_props = get_main_props(context)

        props_dict = {
            'scripting': {
                'packing': {}
            }
        }

        self.loader = self.LOADER_TYPE(
                    target=self.get_target(),
                    filepath=None,
                    props_dict=props_dict)
        self.loader.load()

        prefs = get_prefs()
        prefs.property_unset('thread_count')
        disable_box_rendering(None, context)

        redraw_ui(context)

        self.report({'INFO'}, 'Parameters reset')
        return {'FINISHED'}


class PreferencesPresetFilenameMixin:

    @property
    def filepath(self):
        from .prefs import UVPM4_Preferences
        return UVPM4_Preferences.get_preferences_filepath()


class UVPM4_OT_SavePreferencesPreset(UVPM4_OT_SavePresetBase, PreferencesPresetFilenameMixin):

    bl_idname = 'uvpackmaster4.save_preferences_preset'
    bl_label = 'Save Preferences'
    bl_description = 'Save all packer preferences to a file'

    props_to_filter = {}

    def get_collection_props(self, context):
        return get_prefs()

    def set_preset_version(self, json_struct):
        json_struct['preset_version'] = UvpmVersionInfo.PREFERENCES_PRESET_VERSION


class PreferencesPresetLoader(PresetLoader):

    def translate_props(self, preset_version, props_dict):
        pass

    def get_preset_version(self, json_struct):
        return json_struct['preset_version']

    def validate_preset_version(self, preset_version):
        return preset_version in range(UvpmVersionInfo.PREFERENCES_PRESET_VERSION_FIRST_SUPPORTED, UvpmVersionInfo.PREFERENCES_PRESET_VERSION+1)
    

class UVPM4_OT_LoadPreferencesPreset(UVPM4_OT_LoadPresetBase, PreferencesPresetFilenameMixin):

    bl_idname = 'uvpackmaster4.load_preferences_preset'
    bl_label = 'Open Preset'
    bl_options = {'UNDO'}
    bl_description = 'Load all packer preferences from a file'

    LOADER_TYPE = PreferencesPresetLoader

    def get_target(self):
        return get_prefs()
