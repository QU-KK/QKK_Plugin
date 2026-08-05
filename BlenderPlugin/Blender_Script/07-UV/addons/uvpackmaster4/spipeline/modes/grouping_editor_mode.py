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

from ...mode import UVPM4_Mode_Generic
from ...utils import PropertyWrapper


class UVPM4_Mode_GroupingEditor(UVPM4_Mode_Generic):

    MODE_ID = 'grouping_editor'
    MODE_NAME = 'Grouping Editor'
    MODE_HELP_URL_SUFFIX = "40-miscellaneous-functionalities/05-grouping-editor"

    def get_grouping_config(self):
        config = super().get_grouping_config()
        config.grouping_enabled = True
        config.g_scheme_access_desc_id = 'editor'
        config.group_method_prop = PropertyWrapper(self.scene_props, 'group_method_editor')
        config.target_box_editing = not config.auto_grouping_enabled()

        from ...presets_grouping_scheme import UVPM4_PT_PresetsGroupingSchemeEditor
        config.g_scheme_preset_panel_t = UVPM4_PT_PresetsGroupingSchemeEditor
        return config
