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

from ...operator_islands import NumberedGroupsAccess
from ..engine.types import UvpmAxis, UvpmCoordSpace
from ...island_params import VColorIParamSerializer
from ..engine.island_params import AlignPriorityIParamInfo
from ...app_iface import *
from ...mode import UVPM4_Mode_Generic


class UVPM4_Mode_Align(UVPM4_Mode_Generic):

    def __init__(self, context):
        super().__init__(context)
        self.simi_props = self.main_props.simi_props

        self.stack_groups_access = NumberedGroupsAccess(context, desc_id='stack_group')

    def pre_operation(self, op):
        super().pre_operation(op)
        self.stack_groups_access.init_iparam_name()

    def get_iparam_serializers(self):
        output = super().get_iparam_serializers()

        if self.main_props.stack_groups_enabled():
            output.append(self.stack_groups_access.get_iparam_serializer())

        if self.main_props.align_priority_enabled():
            output.append(VColorIParamSerializer(AlignPriorityIParamInfo()))

        return output

    def send_verts_3d(self):
        return self.simi_props.match_3d_axis != UvpmAxis.NONE and self.simi_props.match_3d_axis_space == UvpmCoordSpace.LOCAL

    def send_verts_3d_global(self):
        return self.simi_props.match_3d_axis != UvpmAxis.NONE and self.simi_props.match_3d_axis_space == UvpmCoordSpace.GLOBAL


class UVPM4_Mode_SelectSimilar(UVPM4_Mode_Align):

    MODE_ID = 'align.select_similar'
    MODE_NAME = 'Select Similar'

    SCENARIO_ID = 'align_select_similar'

    def send_unselected_islands(self):
        return True


class UVPM4_Mode_AlignSimilar(UVPM4_Mode_Align):

    MODE_ID = 'align.align_similar'
    MODE_NAME = 'Align Similar'

    SCENARIO_ID = 'align_align_similar'
