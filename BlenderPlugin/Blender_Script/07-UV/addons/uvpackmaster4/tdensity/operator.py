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

from ..island_params import VColorIParamSerializer
from ..spipeline.engine.island_params import TexelDensityShowIParamInfo
from ..operator_islands import UVPM4_OT_ShowIParam
from ..spipeline.engine.types import UvpmIParamFlags
from ..spipeline.engine.labels import Labels


class UVPM4_OT_ShowTexelDensityGeneric(UVPM4_OT_ShowIParam):

    def get_iparam_info(self):
        return TexelDensityShowIParamInfo()

    def get_iparam_value(self):
        return 0

    def send_verts_3d_global(self):
        return True

    def get_iparam_serializers(self):
        return [VColorIParamSerializer(self.iparam_info, flags=UvpmIParamFlags.CONSISTENCY_CHECK_DISABLE)]


class UVPM4_OT_ShowTexelDensity(UVPM4_OT_ShowTexelDensityGeneric):

    bl_idname = 'uvpackmaster4.show_texel_density'
    bl_label = 'Show TD'
    bl_description = 'Show texel density of the selected islands'

    SCENARIO_ID = 'tdensity_show'


class UVPM4_OT_SetTexelDensity(UVPM4_OT_ShowTexelDensityGeneric):

    bl_idname = 'uvpackmaster4.set_texel_density'
    bl_label = 'Set TD'
    bl_description = "Set texel density for the selected islands. Texel density to set is determined by the '{}' option".format(Labels.TDENSITY_TO_SET_NAME)

    SCENARIO_ID = 'tdensity_set'
    

class UVPM4_OT_AdjustTexelDensityToUnselected(UVPM4_OT_ShowTexelDensityGeneric):

    bl_idname = 'uvpackmaster4.adjust_texel_density_to_unselected'
    bl_label = 'Adjust TD To Unselected'
    bl_description = 'Adjust texel density of the selected islands so it is uniform with texel density of the unselected islands'

    SCENARIO_ID = 'tdensity_adjust_to_unselected'


    def send_unselected_islands(self):
        return True
