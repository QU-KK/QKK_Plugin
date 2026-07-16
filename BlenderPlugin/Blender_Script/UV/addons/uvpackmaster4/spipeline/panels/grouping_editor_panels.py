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

from ...panel_grouping_editor import UVPM4_PT_GenericGroupingEditor, UVPM4_PT_GroupTargetBoxes, UVPM4_PT_Grouping, UVPM4_PT_SchemeGroups


class UVPM4_PT_GroupingEditor(UVPM4_PT_Grouping, UVPM4_PT_GenericGroupingEditor):

    bl_idname = 'UVPM4_PT_GroupingEditor'
    bl_label = 'Grouping Editor'

    def draw_impl2(self, context):
        from ...prefs import GROUPING_EDITOR_DIS_MSG
        self.prefs.dis_msgs.handle(GROUPING_EDITOR_DIS_MSG, self.layout, add_separator=False)
        super().draw_impl2(context)


class UVPM4_PT_SchemeGroupsGroupingEditor(UVPM4_PT_SchemeGroups, UVPM4_PT_GenericGroupingEditor):

    bl_idname = 'UVPM4_PT_SchemeGroupsGroupingEditor'
    bl_parent_id = UVPM4_PT_GroupingEditor.bl_idname


class UVPM4_PT_GroupTargetBoxesGroupingEditor(UVPM4_PT_GroupTargetBoxes, UVPM4_PT_GenericGroupingEditor):

    bl_idname = 'UVPM4_PT_GroupTargetBoxesGroupingEditor'
    bl_parent_id = UVPM4_PT_GroupingEditor.bl_idname
    