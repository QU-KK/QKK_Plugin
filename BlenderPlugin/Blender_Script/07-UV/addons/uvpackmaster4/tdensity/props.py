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

from ..app_iface import *
from ..pgroup import standalone_property_group
from ..spipeline.engine.labels import Labels
from ..spipeline.engine.tdensity import TDensityValue


@standalone_property_group
class UVPM4_TDensityValue(TDensityValue):

    DEFAULT_VALUE = 0
    MAX_VALUE = 10000

    view_val : FloatProperty(
        name=Labels.TEXEL_DENSITY_VALUE_NAME(),
        default=DEFAULT_VALUE,
        min=float(DEFAULT_VALUE),
        max=float(MAX_VALUE)
    )

    s_val : StringProperty(
        default=str(DEFAULT_VALUE)
    )

    def draw(self, layout, text=None):
        row = layout.row(align=True)
        row.prop(self, 'view_val', **({'text': text} if text is not None else {}))
