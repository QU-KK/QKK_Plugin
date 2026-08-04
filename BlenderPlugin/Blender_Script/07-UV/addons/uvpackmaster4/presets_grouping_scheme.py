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

from .utils import get_prefs, PropertyWrapper
from .presets import UVPM4_PT_PresetsBase, UVPM4_OT_SavePresetBase, UVPM4_OT_LoadPresetBase, LoadPresetInvokeHelper, PresetLoader
from .grouping_scheme import UVPM4_GroupingScheme
from .grouping_scheme_access import GroupingSchemeAccess, GSAccessDescIdAttrMixin
from .version import UvpmVersionInfo
from .group import UVPM4_GroupOverrides
from .app_iface import *

GROUPING_SCHEME_PRESET_FILENAME_EXT = "uvpmg"
GROUPING_SCHEME_PRESET_FILENAME_DOT_EXT = '.' + GROUPING_SCHEME_PRESET_FILENAME_EXT


class GroupingSchemePresetFilenameMixin:

    filename_ext = GROUPING_SCHEME_PRESET_FILENAME_DOT_EXT
    filter_glob : StringProperty(
        default="*{}".format(GROUPING_SCHEME_PRESET_FILENAME_DOT_EXT),
        options={'HIDDEN'},
    )


class UVPM4_PT_PresetsGroupingScheme(UVPM4_PT_PresetsBase, Panel):

    bl_label = 'Grouping Scheme Presets'
    show_remove_button = True
    show_save_button = True

    @staticmethod
    def get_load_operator_idname():
        return UVPM4_OT_LoadGroupingSchemePreset.bl_idname

    @staticmethod
    def get_save_operator_idname():
        return UVPM4_OT_SaveGroupingSchemePreset.bl_idname
    
    def init_load_save_operator(self, op):
        op.gs_access_desc_id = self.GS_ACCESS_DESC_ID

    def get_preset_path(self):
        prefs = get_prefs()
        return prefs.get_g_schemes_preset_path()

    def get_preset_dot_ext(self):
        return GROUPING_SCHEME_PRESET_FILENAME_DOT_EXT

    def is_save_button_enabled(self):
        return self.gs_access.active_g_scheme is not None

    def get_default_preset_name(self):
        g_scheme = self.gs_access.active_g_scheme
        return "{}{}".format(g_scheme.name, GROUPING_SCHEME_PRESET_FILENAME_DOT_EXT) if g_scheme is not None else ""

    def draw(self, context):
        self.gs_access = GroupingSchemeAccess(context, ui_drawing=True, desc_id=self.GS_ACCESS_DESC_ID)
        super().draw(context)


class UVPM4_PT_PresetsGroupingSchemePack(UVPM4_PT_PresetsGroupingScheme):

    GS_ACCESS_DESC_ID = 'packing'


class UVPM4_PT_PresetsGroupingSchemeEditor(UVPM4_PT_PresetsGroupingScheme):

    GS_ACCESS_DESC_ID = 'editor'


class UVPM4_OT_SaveGroupingSchemePreset(UVPM4_OT_SavePresetBase, ExportHelper, GroupingSchemePresetFilenameMixin, GSAccessDescIdAttrMixin):

    bl_idname = 'uvpackmaster4.save_grouping_scheme_preset'
    bl_label = 'Save Scheme'
    bl_description = 'Save the active grouping scheme to a file'

    def set_preset_version(self, json_struct):
        json_struct['grouping_scheme_version'] = UvpmVersionInfo.GROUPING_SCHEME_VERSION

    def get_collection_props(self, context):
        return self.gs_access.active_g_scheme

    def execute(self, context):
        self.gs_access = GroupingSchemeAccess(context, desc_id=self.gs_access_desc_id)
        return super().execute(context)


class GroupingSchemePresetLoader(PresetLoader):

    PROPS_TO_LOAD_DEFAULT = True

    def translate_props_1to2(self, props_dict):
        pass

    def translate_props_2to3(self, props_dict):
        pass

    def translate_props_3to4(self, props_dict):
        pass

    def translate_props_4to5(self, props_dict):
        pass

    def translate_props_5to6(self, props_dict):
        for group in props_dict['groups']:
            overrides = group['overrides']

            overrides['override_groups_together'] = False
            overrides['groups_together'] = False

            overrides['override_group_compactness'] = False
            overrides['group_compactness'] = 0.0

    def translate_props_6to7(self, props_dict):
        for group in props_dict['groups']:
            overrides = group['overrides']

            overrides['override_pixel_border_margin'] = overrides['override_pixel_padding']
            del overrides['override_pixel_padding']

            overrides['pixel_border_margin'] = overrides['pixel_padding']
            del overrides['pixel_padding']

    def translate_props_7to8(self, props_dict):
        pass

    def translate_props_8to9(self, props_dict):
        for group in props_dict['groups']:
            overrides = group['overrides']

            overrides['override_tdensity_value'] = False
            overrides['tdensity_value'] = 0

    def translate_props_9to10(self, props_dict):
        for group in props_dict['groups']:
            overrides = group['overrides']

            if overrides['pixel_border_margin'] == 0:
                overrides['override_pixel_border_margin'] = False
                overrides['pixel_border_margin'] = 1

    def translate_props_10to11(self, props_dict):
        tr = self.PropTranslator()
        options = props_dict['options']
        del options['automatic']
        del options['base']['tile_count_per_group']
        options['tile_count_per_group'] = 0

        tr.translate('grouping_compactness', 'group_compactness', target=options['base'], source=options['base'])
        options['base']['dynamic_tiles_all'] = False
        options['base']['atlas_size_x'] = 2
        options['base']['atlas_size_y'] = 2

        for group in props_dict['groups']:
            group['dynamic_tiles'] = False

            overrides = group['overrides']
            tr.translate('override_tdensity_packing', 'override_tdensity_value', target=overrides, source=overrides)
            tr.translate_tdensity('tdensity_packing', 'tdensity_value', target=overrides, source=overrides)

            tr.translate('override_grouping_compactness', 'override_group_compactness', target=overrides, source=overrides)
            tr.translate('grouping_compactness', 'group_compactness', target=overrides, source=overrides)

    def translate_props(self, g_scheme_version, props_dict):
        translate_array = [
            self.translate_props_1to2,
            self.translate_props_2to3,
            self.translate_props_3to4,
            self.translate_props_4to5,
            self.translate_props_5to6,
            self.translate_props_6to7,
            self.translate_props_7to8,
            self.translate_props_8to9,
            self.translate_props_9to10,
            self.translate_props_10to11
        ]

        for i in range(g_scheme_version - UvpmVersionInfo.GROUPING_SCHEME_VERSION_FIRST_SUPPORTED, len(translate_array)):
            translate_array[i](props_dict)

    def get_preset_version(self, json_struct):
        return json_struct['grouping_scheme_version']

    def validate_preset_version(self, preset_version):
        return preset_version in range(UvpmVersionInfo.GROUPING_SCHEME_VERSION_FIRST_SUPPORTED, UvpmVersionInfo.GROUPING_SCHEME_VERSION + 1)


class UVPM4_OT_LoadGroupingSchemePreset(LoadPresetInvokeHelper, GroupingSchemePresetFilenameMixin,
                                        UVPM4_OT_LoadPresetBase, ImportHelper, GSAccessDescIdAttrMixin):

    bl_idname = 'uvpackmaster4.load_grouping_scheme_preset'
    bl_label = 'Load Scheme'
    bl_options = {'UNDO'}
    bl_description = 'Load Grouping Scheme from a file'

    LOADER_TYPE = GroupingSchemePresetLoader

    CREATE_NEW_PROP_NAME = 'Create New'
    create_new : BoolProperty(name=CREATE_NEW_PROP_NAME, default=False, options={'SKIP_SAVE'})

    success_msg = 'Grouping Scheme loaded.'

    g_scheme_to_overwrite = None
    g_scheme_to_overwrite_uuid = ''

    def show_confirm_popup(self, context):
        self.gs_access = GroupingSchemeAccess(context, desc_id=self.gs_access_desc_id)

        preset_uuid = self.loader.props_dict.get('uuid')
        if not UVPM4_GroupingScheme.uuid_is_valid(preset_uuid):
            self.LOADER_TYPE.raise_invalid_format()

        g_schemes = self.gs_access.get_g_schemes()
        for idx, g_scheme in enumerate(g_schemes):
            if g_scheme.uuid == preset_uuid:
                self.g_scheme_to_overwrite = g_scheme
                self.g_scheme_to_overwrite_uuid = preset_uuid
                return True

        return False

    def draw(self, context):
        if not self.should_show_confirm_popup:
            return super().draw(context)

        layout = self.layout
        col = layout.column()
        col.label(text='The operation is going to overwrite a grouping scheme already present in the blend file:')
        col.label(text='  "{}"'.format(self.g_scheme_to_overwrite.name))
        col.label(text='(because the internal IDs of the grouping scheme and the preset are the same). Press OK to continue.')

        col.separator()
        col.label(text="Check '{}' to force creating a new grouping scheme (instead of overwriting):".format(self.CREATE_NEW_PROP_NAME))
        col.prop(self, 'create_new')

    def get_target(self):
        return UVPM4_GroupingScheme.SA()

    def load_properties(self):
        super().load_properties()
        temp_g_scheme = self.loader.target

        if not temp_g_scheme.is_valid():
            self.LOADER_TYPE.raise_invalid_format()

        if self.g_scheme_to_overwrite is not None and not self.create_new:
            self.g_scheme_to_overwrite.copy_from(temp_g_scheme)
            self.gs_access.set_active_g_scheme_uuid(self.g_scheme_to_overwrite_uuid)
        else:
            if self.g_scheme_to_overwrite is not None:
                temp_g_scheme.regenerate_uuid()

            self.gs_access = GroupingSchemeAccess(self.context, desc_id=self.gs_access_desc_id)
            new_g_scheme = self.gs_access.create_g_scheme()
            new_g_scheme.copy_from(temp_g_scheme)
            self.gs_access.set_active_g_scheme_uuid(new_g_scheme.uuid)
