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

from ...presets import UVPM4_PT_Presets
from ..operators.other_operator import UVPM4_OT_OrientTo3dSpace, UVPM4_OT_RemoveDataFromObjects

from ...multi_panel import OtherToolsMultiPanel
from ...panel import UVPM4_PT_Generic



class UVPM4_PT_GenericOther(UVPM4_PT_Generic):

    PARENT_M_PANEL_ID = OtherToolsMultiPanel.M_PANEL_ID


class UVPM4_PT_OrientTo3dSpace(UVPM4_PT_GenericOther):

    bl_idname = 'UVPM4_PT_OrientTo3dSpace'
    bl_label = 'Orient UVs To 3D Space'

    PRESET_PANEL = UVPM4_PT_Presets
    PANEL_PRIORITY = 10000
    HELP_URL_SUFFIX = '40-miscellaneous-functionalities/20-other-tools/#orient-uvs-to-the-3d-space'


    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)

        self.draw_main_prop_sets(col)

        self.main_props.orient_to3d_props.draw(col)

        col.separator()
        self.operator_with_help(UVPM4_OT_OrientTo3dSpace.bl_idname, col, help_url_suffix=self.HELP_URL_SUFFIX if self.props_with_help else None)


class UVPM4_PT_OtherUtilities(UVPM4_PT_GenericOther):

    bl_idname = 'UVPM4_PT_OtherUtilities'
    bl_label = 'Other Utilities'

    def draw_impl(self, context):
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator(UVPM4_OT_RemoveDataFromObjects.bl_idname)
