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


from .connection import encode_string
from .spipeline.engine.types import UvpmIParamFlags
from .pack_context import PackContext
from .spipeline.engine.island_params import IParamInfo, GroupIParamInfoGeneric
from .utils import get_prefs
from .app_iface import *

import struct


class NumberedGroupIParamInfo(GroupIParamInfoGeneric):

    LABEL = None
    SCRIPT_NAME = None

    MIN_VALUE = 0
    MAX_VALUE = 1000
    DEFAULT_VALUE = MIN_VALUE
    DEFAULT_VALUE_TEXT = 'N'

    VALUE_PROP_ID = 'group_num'


class IParamError(RuntimeError):

    def __init__(self, str):
        super().__init__(str)


class IParamSerializer:

    p_context : PackContext = None
    iparam_info : IParamInfo

    def __init__(self, iparam_info, flags=0):
        self.iparam_info = iparam_info
        self.iparam_values = []
        self.flags = flags

        if get_prefs().allow_inconsistent_islands:
            self.flags |= UvpmIParamFlags.CONSISTENCY_CHECK_DISABLE

    def init_context(self, p_context):
        self.p_context = p_context

    def serialize_iparam_info(self):
        output = encode_string(self.iparam_info.script_name)
        output += encode_string(self.iparam_info.label)
        output += self.iparam_info.serialize_default_value()
        output += struct.pack('i', int(self.iparam_info.INDEX))
        output += struct.pack('i', int(self.flags))
        output += self.iparam_info.serialize_min_value()
        output += self.iparam_info.serialize_max_value()

        return output
    
    def serialize_iparam(self, p_obj_idx, p_obj, face):
        self.iparam_values.append(self.get_iparam_value(p_obj_idx, p_obj, face))

    def get_faces_for_iparam_value(self, p_obj_idx, p_obj, face_indices, iparam_value):
        return [face_idx for face_idx in face_indices if self.get_iparam_value(p_obj_idx, p_obj, p_obj.mw.faces[face_idx]) == iparam_value]
        

class VColorIParamSerializer(IParamSerializer):

    def init_context(self, p_context):
        super().init_context(p_context)
        self.vcolor_layers = []

        for p_obj in p_context.p_objects:
            self.vcolor_layers.append(p_obj.get_or_create_vcolor_layer(self.iparam_info))
    
    def get_iparam_value(self, p_obj_idx, p_obj, face):
        return self.iparam_info.get_iparam_value(self.p_context, self.vcolor_layers[p_obj_idx], face)
