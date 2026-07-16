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


from ...operator import UVPM4_OT_Engine
from ...app_iface import BoolProperty


class UtilFinishConditionMixin:
    
    def operation_done_hint(self):
        return ''



class UVPM4_OT_OverlapCheck(UtilFinishConditionMixin, UVPM4_OT_Engine):

    bl_idname = 'uvpackmaster4.overlap_check'
    bl_label = 'Overlap Check'
    bl_description = "Check for overlapping UV islands among all selected islands. WARNING: this operation works on a per-island basis (reports whether two distinct UV islands overlap each other) - it will NOT report two overlapping UV faces belonging to the same island"

    SCENARIO_ID = 'util_overlap_check'


class UVPM4_OT_MeasureArea(UtilFinishConditionMixin, UVPM4_OT_Engine):

    bl_idname = 'uvpackmaster4.measure_area'
    bl_label = 'Measure Area'
    bl_description = 'Measure area of selected UV islands'

    SCENARIO_ID = 'util_measure_area'

    merged : BoolProperty(
        name='Merged',
        description='',
        default=False
    )

    @classmethod
    def description(cls, context, properties):
        if properties.merged:
            return "Measure merged area of selected UV islands (area of overlapping UVs will be added to the result only once)"

        return "Measure area of selected UV islands (area of overlapping islands will be added to the result separately per every UV island)"
