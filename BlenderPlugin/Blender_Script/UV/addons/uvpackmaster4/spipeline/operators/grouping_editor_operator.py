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

from ...multi_panel import GroupingEditorMultiPanel
from ...operator_generic import UVPM4_OT_Generic
from ..engine.types import GroupingMethod
from ..modes.grouping_editor_mode import UVPM4_Mode_GroupingEditor
from ...app_iface import *


class UVPM4_OT_EditGroupingSchemeInEditor(UVPM4_OT_Generic):

    bl_options = {'INTERNAL'}
    bl_idname = 'uvpackmaster4.edit_scheme_in_editor'
    bl_label = 'Edit Scheme In Editor'
    bl_description = "Edit the scheme in the Editor"

    g_scheme_uuid : StringProperty(name='', description='', default='')

    CONFIRMATION_MSG = 'The scheme was selected in the editor'

    @staticmethod
    def execute_impl(context, g_scheme_uuid, select_editor_with_shift=False):
        editor_mode = UVPM4_Mode_GroupingEditor(context)
        editor_mode.grouping_config.group_method_prop.set(GroupingMethod.MANUAL.value())
        editor_mode.grouping_config.get_scheme_access().set_active_g_scheme_uuid(g_scheme_uuid)

        bpy.ops.uvpackmaster4.select_multi_panel(panel_id=GroupingEditorMultiPanel.M_PANEL_ID, shift=select_editor_with_shift, force_select=True)

    def execute(self, context):
        self.execute_impl(context, self.g_scheme_uuid)
        self.report({'INFO'}, self.CONFIRMATION_MSG)

        return {'FINISHED'}
