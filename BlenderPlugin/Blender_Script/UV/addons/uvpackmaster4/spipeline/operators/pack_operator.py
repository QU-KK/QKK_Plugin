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


from ...operator import UVPM4_OT_Engine, ModeIdAttrMixin
from ..engine.types import PackOpType
from ...app_iface import *


class UVPM4_OT_Pack(UVPM4_OT_Engine, ModeIdAttrMixin):

    bl_idname = 'uvpackmaster4.pack'
    bl_label = 'Pack'
    bl_description = 'Pack selected UV islands'

    pack_op_type : EnumProperty(
        name='Pack Operation Type',
        description='',
        items=lambda self, context: PackOpType.to_blend_items())
    
    auto_repack : BoolProperty(default=False)
    
    @classmethod
    def description(cls, context, properties):
        return PackOpType.item_by_value(properties.pack_op_type).desc
    
    def get_active_mode_id(self):
        return self.main_props.active_pack_mode_id
    
    def packing_operation(self):
        return True

    def send_pinned_islands(self):
        return self.prefs.dont_transform_pinned_uvs
    
    def mode_kwargs(self):
        kwargs = super().mode_kwargs().copy()
        kwargs.update({
            'interactive': self.interactive,
            'pack_op_type': self.pack_op_type,
            'auto_repack': self.auto_repack
        })

        return kwargs
    