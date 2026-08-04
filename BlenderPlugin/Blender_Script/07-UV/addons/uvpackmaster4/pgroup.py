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

from .app_iface import *
from .spipeline.engine.utils import ShadowedCollectionProperty


class CopyFromMixin:

    TYPES_MAP = {'BOOLEAN': bool, 'INT': int, 'FLOAT': float, 'STRING': str, 'ENUM': str}
    ENGINE_TYPES_MAP = {'BOOLEAN': bool, 'INT': int, 'FLOAT': float, 'STRING': str, 'ENUM': str}
    IGNORED_PROPS = {'rna_type'}

    def copy_from(self, other):
        for prop_id, prop_struct in AppInterface.object_property_data(self).items():
            if prop_id in self.IGNORED_PROPS:
                continue
    
            if prop_struct.type == 'POINTER':
                getattr(self, prop_id).copy_from(getattr(other, prop_id))

            elif prop_struct.type == 'COLLECTION':
                dst_coll = getattr(self, prop_id)
                src_coll = getattr(other, prop_id)

                dst_coll.clear()
                for src_elem in src_coll:
                    dst_elem = dst_coll.add()
                    dst_elem.copy_from(src_elem)

            else:
                if hasattr(prop_struct, 'is_array') and prop_struct.is_array:
                    setattr(self, prop_id, (getattr(other, prop_id)))

                else:
                    py_type = self.TYPES_MAP[prop_struct.type]
                    setattr(self, prop_id, py_type(getattr(other, prop_id)))

    def __serialize_scalar(self, type, value):
        if self.TYPES_MAP[type] == str:
            return str(value).encode('utf-8')

        if type == 'BOOLEAN':
            fstr = '?'
        elif type ==  'FLOAT':
            fstr = 'f'
        elif type == 'INT':
            fstr = 'i'
        else:
            assert False

        import struct
        return struct.pack(fstr, value)

    def serialize(self):
        output = bytes()

        for prop_id, prop_struct in AppInterface.object_property_data(self).items():
            if prop_id in self.IGNORED_PROPS:
                continue

            if prop_struct.type == 'POINTER':
                output += getattr(self, prop_id).serialize()

            elif prop_struct.type == 'COLLECTION':
                coll = getattr(self, prop_id)
                for elem in coll:
                    output += elem.serialize()

            else:
                value = getattr(self, prop_id)
                is_array = getattr(prop_struct, 'is_array', False)

                if is_array:
                    for idx in range(prop_struct.size):
                        output += self.__serialize_scalar(prop_struct.type, value[idx])

                else:
                    output += self.__serialize_scalar(prop_struct.type, value)

        return output
    
    def calc_hash(self):
        import hashlib
        return hashlib.sha256(self.serialize()).hexdigest()
    
    def to_engine_param(self):
        d = {}

        for prop_id, prop_struct in AppInterface.object_property_data(self).items():
            if prop_id in self.IGNORED_PROPS:
                continue

            if prop_struct.type == 'POINTER':
                val = getattr(self, prop_id).to_engine_param()

            elif prop_struct.type == 'COLLECTION':
                coll = getattr(self, prop_id)
                l = []
                for elem in coll:
                    l.append(elem.to_engine_param())

                val = l

            else:
                py_type = self.ENGINE_TYPES_MAP[prop_struct.type]

                if hasattr(prop_struct, 'is_array') and prop_struct.is_array:
                    val = tuple(py_type(e) for e in getattr(self, prop_id))

                else:
                    val = py_type(getattr(self, prop_id))

            d[prop_id] = val

        return d


class StandalonePropertyGroupBase(CopyFromMixin):

    @property
    def bl_rna(self):
        return self._pg_cls.bl_rna

    def __init__(self, **kwargs):
        for prop_id, prop_struct in AppInterface.object_property_data(self).items():
            if prop_id in self.IGNORED_PROPS:
                continue

            prop_val = None

            if prop_struct.type == 'POINTER':
                prop_val = prop_struct.fixed_type.SA()

            elif prop_struct.type == 'COLLECTION':
                prop_val = ShadowedCollectionProperty(elem_type=prop_struct.fixed_type.SA)

            elif prop_struct.type == 'ENUM':
                prop_val = str(prop_struct.enum_items.keys()[0])

            else:
                if hasattr(prop_struct, 'is_array') and prop_struct.is_array:
                    prop_val = prop_struct.default

                else:
                    py_type = self.TYPES_MAP[prop_struct.type]
                    prop_val = py_type(prop_struct.default)

            assert prop_val is not None
            setattr(self, prop_id, prop_val)

        for prop_id, value in kwargs.items():
            setattr(self, prop_id, value)

    def cast_setattr(self, key, value):
        def _cast_value(_value, _type):
            _cast_func = self.TYPES_MAP.get(_type)
            if _cast_func is None:
                return _value
            return _cast_func(_value)

        prop_struct = AppInterface.object_property_data(self).get(key, None)
        if prop_struct is not None and prop_struct.type in self.TYPES_MAP:
            prop_type = prop_struct.type
            is_array = getattr(prop_struct, 'is_array', False)
            if is_array:
                value = type(value)(_cast_value(v, prop_type) for v in value)
            else:
                value = _cast_value(value, prop_type)
        super().__setattr__(key, value)

    def property_unset(self, prop_name):
        prop_struct = AppInterface.object_property_data(self)[prop_name]
        is_array = getattr(prop_struct, 'is_array', False)
        if is_array and hasattr(prop_struct, 'default_array'):
            setattr(self, prop_name, prop_struct.default_array)
        elif hasattr(prop_struct, 'default'):
            setattr(self, prop_name, prop_struct.default)


def standalone_property_group(new_cls):
    pg_dict = dict()
    pg_exclude = { '__init__' }

    for id, value in new_cls.__dict__.items():
        if id not in pg_exclude:
            pg_dict[id] = value

    bases = tuple(b for b in new_cls.__bases__ if b != object)
    pg_cls = type(new_cls.__name__, (CopyFromMixin,) + bases + (PropertyGroup,), pg_dict)
    sa_cls = type(new_cls.__name__ + '_SA', (StandalonePropertyGroupBase,) + new_cls.__bases__, dict(new_cls.__dict__))
    pg_cls.SA = sa_cls
    sa_cls._pg_cls = pg_cls
    return pg_cls
