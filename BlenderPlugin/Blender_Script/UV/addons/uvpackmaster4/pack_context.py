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
from .spipeline.engine.types import UvpmIslandFlags, UvpmIslandParams, UvpmMapSerializationFlags, UvpmFaceInputFlags
from .spipeline.engine.island_params import IntIParamInfo, StrIParamInfo
from .utils import MeshWrapper, in_debug_mode
from .app_iface import *

import time
import struct


from mathutils import Vector, Matrix # type: ignore


class UvMod:

    def __init__(self, p_island):
        self.p_island = p_island

    def restore_orig_uvs(self):
        if self.p_island._transform_stored is not None:
            tranform_stored_inverted = self.p_island._transform_stored.inverted()
            self.p_island.transform(tranform_stored_inverted)
            self.p_island._transform_stored = None

    def pre_apply(self):
        pass

    def post_apply(self):
        pass


class UvModTransform(UvMod):

    def __init__(self, p_island, transform):
        super().__init__(p_island)

        self.orig_transform = transform
        self.transform = transform

    def restore_orig_uvs(self):
        pass

    def pre_apply(self):
        if self.p_island._transform_stored is not None:
            tranform_stored_inverted = self.p_island._transform_stored.inverted()
            self.transform = self.transform @ tranform_stored_inverted

    def apply(self):
        self.p_island.transform(self.transform)

    def post_apply(self):
        self.p_island._transform_stored = self.orig_transform
    

class UvModVerticesGeneric(UvMod):

    def pre_apply(self):
        self.p_island.orig_vert_map() # Force saving orig vert map before modification

    def post_apply(self):
        self.p_island._vert_modified = True


class UvModVertexMap(UvModVerticesGeneric):

    def __init__(self, p_island, vert_map):
        super().__init__(p_island)

        self.vert_map = vert_map

    def apply(self):
        self.p_island.apply_vert_map(self.vert_map)

        
class UvModOutVertices(UvModVerticesGeneric):

    def __init__(self, p_island, face_order, vertices):
        super().__init__(p_island)

        self.face_order = face_order
        self.vertices = vertices

    def apply(self):
        loc_face_order = self.p_island.to_loc_face_indices(self.face_order)

        v_idx = 0
        for face_idx in loc_face_order:
            face = self.p_island.p_obj.mw.faces[face_idx]

            for loop in face.loops:
                loop[self.p_island.p_obj.uv_layer].uv = (self.vertices[v_idx][0], self.vertices[v_idx][1])
                v_idx += 1

        assert(v_idx == len(self.vertices))


class PackIsland:

    p_obj = None
    face_indices = None
    faces = None
    iparam_values = None
    __overlay = None
    __bbox = None

    __orig_vert_map = None
    _vert_modified = False
    _transform_stored = None

    flags = 0

    def refresh_bmesh(self):
        self.faces = [self.p_obj.mw.faces[face_idx] for face_idx in self.face_indices]

    def __init__(self, p_obj, face_indices, selected):
        self.p_obj = p_obj
        self.flags = UvpmIslandFlags.SELECTED if selected else 0

        self.face_indices = self.to_loc_face_indices(face_indices)
        self.refresh_bmesh()

    def to_loc_face_indices(self, face_indices):
        return self.p_obj.to_loc_face_indices(face_indices)

    def calc_bbox(self):
        x_coords = []
        y_coords = []

        for face_idx in self.face_indices:
            face = self.p_obj.mw.faces[face_idx]
            for loop in face.loops:
                uv = loop[self.p_obj.uv_layer].uv
                x_coords.append(uv[0])
                y_coords.append(uv[1])

        return [Vector((min(x_coords), min(y_coords))), Vector((max(x_coords), max(y_coords)))]

    def bbox(self):
        if self.__bbox is None:
            self.__bbox = self.calc_bbox()

        return self.__bbox

    def register_overlay(self, overlay, ov_manager):
        self.__overlay = overlay

        if ov_manager is not None:
            ov_manager.set_dirty()

    def overlay(self):
        if self.__overlay is not None:
            bbox = self.bbox()
            bbox_center = (bbox[0] + bbox[1]) / 2.0
            region_coord = self.p_obj.mw.view_to_region(bbox_center)
            self.__overlay.set_coords(region_coord)
        
        return self.__overlay

    def iparam_value(self, iparam_info):
        return self.iparam_values[iparam_info.PARAM_TYPE][iparam_info.index()]

    def save_iparam(self, iparam_info, save_iparam_handler=None):
        iparam_value = self.iparam_value(iparam_info)

        if save_iparam_handler:
            save_iparam_handler(iparam_info, iparam_value)

        self.p_obj.save_iparam(iparam_info, iparam_value, self.faces)

    def select(self, select):
        self.p_obj.select_faces(self.face_indices, select)

    def transform(self, matrix):
        for face_idx in self.face_indices:
            face = self.p_obj.mw.faces[face_idx]
            for loop in face.loops:
                if self.p_obj.mw.loop_uv_is_self_modified(loop):
                    continue

                uv = loop[self.p_obj.uv_layer].uv
                transformed_uv = matrix @ Vector((uv[0], uv[1], 1.0))
                loop[self.p_obj.uv_layer].uv = (transformed_uv[0] / transformed_uv[2], transformed_uv[1] / transformed_uv[2])

    def apply_vert_map(self, vert_map):
        for face_idx, verts in vert_map.items():
            face = self.p_obj.mw.faces[face_idx]
            assert(len(face.loops) == len(verts))

            for loop_idx, loop in enumerate(face.loops):
                loop[self.p_obj.uv_layer].uv = (verts[loop_idx][0], verts[loop_idx][1])

    def orig_vert_map(self):
        if self.__orig_vert_map is not None:
            return self.__orig_vert_map

        assert(not self._vert_modified)
        assert(self._transform_stored is None)

        __orig_vert_map = dict()
        for face_idx in self.face_indices:
            verts = []

            face = self.p_obj.mw.faces[face_idx]
            for loop in face.loops:
                uv = loop[self.p_obj.uv_layer].uv
                verts.append((uv[0], uv[1]))

            __orig_vert_map[face_idx] = verts

        self.__orig_vert_map = __orig_vert_map
        return self.__orig_vert_map

    def restore_orig_uvs(self, uv_mod):
        if self._vert_modified:
            assert(self._transform_stored is None)
            self.apply_vert_map(self.orig_vert_map())
            self._vert_modified = False
            return

        uv_mod.restore_orig_uvs()

    def modify_uvs(self, uv_mod):
        assert(self is uv_mod.p_island)
        self.restore_orig_uvs(uv_mod)

        uv_mod.pre_apply()
        uv_mod.apply()
        uv_mod.post_apply()

        self.__bbox = None

    def apply_out_island(self, out_island):
        if out_island.transform is not None:
            self.modify_uvs(UvModTransform(self, out_island.transform))

        if out_island.iparam_values is not None:
            self.iparam_values = out_island.iparam_values
            self.iparam_values[StrIParamInfo.PARAM_TYPE] = self.p_obj.p_context.string_id_map.get_str_array(self.iparam_values[StrIParamInfo.PARAM_TYPE])

        if out_island.flags is not None:
            old_flags = self.flags
            new_flags = out_island.flags

            old_selected = (old_flags & UvpmIslandFlags.SELECTED) > 0
            new_selected = (new_flags & UvpmIslandFlags.SELECTED) > 0

            if old_selected != new_selected:
                self.select(new_selected)

            self.flags = new_flags

        if out_island.vertices is not None:
            assert(out_island.face_order is not None)

            self.modify_uvs(UvModOutVertices(self, out_island.face_order, out_island.vertices))


class PackObject:

    obj = None
    mw = None
    uv_layer = None
    face_idx_offset = None
    vert_idx_offset = None


    def __init__(self, p_context, obj, next_face_idx_offset, next_vert_idx_offset):
        self.p_context = p_context
        self.obj = obj
        self.selection_dirty = False
        self.mw = MeshWrapper(self)

        self.uv_layer = self.mw.get_uv_layer()

        self.face_idx_offset = self.next_face_idx_offset = next_face_idx_offset
        self.vert_idx_offset = self.next_vert_idx_offset = next_vert_idx_offset

        self.next_face_idx_offset += len(self.mw.faces)
        self.next_vert_idx_offset += len(self.mw.verts)

        self.__selected_faces_stored = None
        self.__visible_faces_stored = None

        self.selected_faces_stored_indices = []
        self.visible_faces_stored_indices = []

        for face in self.mw.faces:
            if self.face_is_visible(face):
                self.visible_faces_stored_indices.append(face.index)

                if self.face_is_selected(face):
                    self.selected_faces_stored_indices.append(face.index)

    def refresh_bmesh(self):
        refresh_required = self.mw.refresh_bmesh()

        if not refresh_required:
            return False
        
        self.invalidate_faces_stored()
        return True
            
    def get_selected_faces_stored(self):
        if self.__selected_faces_stored is None:
            self.__selected_faces_stored = [self.mw.faces[face_idx] for face_idx in self.selected_faces_stored_indices]

        return self.__selected_faces_stored
    
    def get_visible_faces_stored(self):
        if self.__visible_faces_stored is None:
            self.__visible_faces_stored = [self.mw.faces[face_idx] for face_idx in self.visible_faces_stored_indices]

        return self.__visible_faces_stored
    
    def invalidate_faces_stored(self):
        self.__selected_faces_stored = None
        self.__visible_faces_stored = None

    def select_faces(self, face_indices, select):
        self.selection_dirty = True

        for face_idx in face_indices:
            face = self.mw.faces[face_idx]
            PackContext.select_face(self.uv_layer, face, self.mw.uv_select_sync(), select)

    def to_loc_face_idx(self, glob_face_idx):
        return glob_face_idx - self.face_idx_offset

    def to_loc_face_indices(self, face_indices):
        return [self.to_loc_face_idx(glob_face_idx) for glob_face_idx in face_indices]

    def to_glob_face_idx(self, loc_face_idx):
        return loc_face_idx + self.face_idx_offset

    def get_selected_faces(self):
        return [f for f in self.mw.faces if PackContext.face_is_selected(self.uv_layer, f, self.mw.uv_select_sync())]

    def get_visible_faces(self):
        return [f for f in self.mw.faces if PackContext.face_is_visible(f, self.mw.uv_select_sync())]

    def face_is_selected(self, f):
        return PackContext.face_is_selected(self.uv_layer, f, self.mw.uv_select_sync())
        
    def face_is_pinned(self, f):
        for loop in f.loops:
            if loop[self.uv_layer].pin_uv:
                return True

        return False

    def face_is_visible(self, f):
        return PackContext.face_is_visible(f, self.mw.uv_select_sync())

    def get_or_create_vcolor_layer(self, iparam_info):
        return self.mw.get_or_create_vcolor_layer(iparam_info)

    def save_iparam(self, iparam_info, iparam_value, faces=None, face_indicies=None):
        vcolor_layer = self.get_or_create_vcolor_layer(iparam_info)
        
        if face_indicies is not None:
            faces = [self.mw.faces[f_idx] for f_idx in face_indicies]
        else:
            if faces is None:
                faces = self.get_selected_faces()

        for face in faces:
            MeshWrapper.set_vcolor(iparam_info, vcolor_layer, face, iparam_value)

    def load_all_iparam_values(self, iparam_info):
        output = set()

        vcolor_layer = self.get_or_create_vcolor_layer(iparam_info)
        faces = self.mw.faces[:]

        for face in faces:
            output.add(MeshWrapper.get_vcolor(iparam_info, vcolor_layer, face))

        return output


class UvSetDescriptor:

    def __init__(self, name):
        self.name = name

    def serialize(self):
        return encode_string(self.name)


class StringIdMap:

    MIN_STRING_ID = 0

    def __init__(self):
        self.__clear()

    def __clear(self):
        self._str_to_id = {}
        self._id_to_str = {}
        self._next_id = self.MIN_STRING_ID

    def __add_str(self, s, id=None):
        if id is None:
            id = self._next_id

        assert id >= self.MIN_STRING_ID
        self._next_id = max(id + 1, self._next_id)

        if s in self._str_to_id or id in self._id_to_str:
            raise RuntimeError('String ID map: valid state')

        self._str_to_id[s] = id
        self._id_to_str[id] = s

        return id
    
    def __print(self):
        print(str(self))

    def __str__(self):
        return 'String ID map: ' + str(self._id_to_str)

    def get_id(self, s):
        id = self._str_to_id.get(s)
        return self.__add_str(s) if id is None else id
        
    def get_str(self, id):
        if id < self.MIN_STRING_ID:
            return ''
        
        s = self._id_to_str.get(id)

        if s is None:
            raise ValueError()
        
        return s
    
    def get_str_array(self, id_array):
        return [self.get_str(id) for id in id_array]
    
    def from_array(self, array):
        self.__clear()

        for id, str in array:
            self.__add_str(str, id)
    
    def serialize(self):
        o = bytes()
        assert len(self._str_to_id) == len(self._id_to_str)

        o += struct.pack('i', len(self._id_to_str))

        for id, s in self._id_to_str.items():
            o += struct.pack('i', id)
            o += encode_string(s)

        return o
        

class IParamRegistry:

    def __init__(self, param_type):
        self.param_type = param_type
        self.iparam_array = [None] * UvpmIslandParams.MAX_COUNT
        self.iparam_name_to_index = dict()

    def register_iparam(self, iparam_info, param_index=None):
        assert iparam_info.PARAM_TYPE == self.param_type
        old_index = self.iparam_name_to_index.get(iparam_info.script_name)

        if old_index is not None:
            if param_index is not None and old_index != param_index:
                raise ValueError()

            iparam_info.INDEX = old_index
            return False

        if param_index is not None:
            if self.iparam_array[param_index] is not None:
                raise ValueError()
        else:
            try:
                param_index = next(idx for idx, entry in enumerate(self.iparam_array) if entry is None)
            except StopIteration:
                raise RuntimeError('Maximum number of island parameters exceeded')

        assert(self.iparam_array[param_index] is None)
        self.iparam_array[param_index] = iparam_info
        self.iparam_name_to_index[iparam_info.script_name] = param_index
        iparam_info.INDEX = param_index
        return True

    def get_iparam_info(self, param_index):
        iparam_info = self.iparam_array[param_index]
        if iparam_info is None:
            raise ValueError()

        assert(iparam_info.index() == param_index)
        return iparam_info


from .prefs_scripted_utils import EngineParams

class PackConfig:

    send_unselected_islands_default = False
    send_pinned_islands_default = False
    send_verts_3d_default = False
    send_verts_3d_global_default = False
    iparam_serializers_default = []
    group_script_param_handler_default = None
    script_params_default = EngineParams()

    def __init__(self):
        self.send_unselected_islands = None
        self.send_pinned_islands = None
        self.send_verts_3d = None
        self.send_verts_3d_global = None
        self.iparam_serializers = None
        self.engine_params = None

    def init_from_mode(self, mode):
        def process_config_attr(attr_name, attr_mode_getter=None):
            if attr_mode_getter is None:
                attr_mode_getter = attr_name

            if getattr(self, attr_name) is None:
                if mode and hasattr(mode, attr_mode_getter):
                    value = getattr(mode, attr_mode_getter)()

                else:
                    import copy
                    value =  copy.deepcopy(getattr(PackConfig, attr_name + '_default'))

                setattr(self, attr_name, value)

        process_config_attr('send_unselected_islands')
        process_config_attr('send_pinned_islands')
        process_config_attr('send_verts_3d')
        process_config_attr('send_verts_3d_global')
        process_config_attr('iparam_serializers', 'get_iparam_serializers')
        process_config_attr('engine_params', 'setup_engine_params')


class IParamTypeMetadata:

    def __init__(self, param_type, param_type_mark, layer_container):
        self.param_type = param_type
        self.layer_container = layer_container
        self.param_type_mark = param_type_mark


# WARNING: the order is important for serialization and deserialization
IPARAM_TYPE_METADATA = {
    IntIParamInfo.PARAM_TYPE: IParamTypeMetadata(
                                param_type=IntIParamInfo.PARAM_TYPE,
                                param_type_mark=IntIParamInfo.PARAM_TYPE_MARK,
                                layer_container='int'),
    StrIParamInfo.PARAM_TYPE: IParamTypeMetadata(
                                param_type=StrIParamInfo.PARAM_TYPE,
                                param_type_mark=StrIParamInfo.PARAM_TYPE_MARK,
                                layer_container='string'),
}


class PackContext:

    UV_SETS = [
        UvSetDescriptor('selected_islands'),
        UvSetDescriptor('unselected_islands'),
        UvSetDescriptor('pinned_islands')
    ]

    SELECTED_UV_SET_IDX = 0
    UNSELECTED_UV_SET_IDX = 1
    PINNED_UV_SET_IDX = 2

    SELECTING_EDGES = AppInterface.APP_VERSION >= (3, 2, 0)
    NEW_SELECT_API = AppInterface.APP_VERSION >= (5, 0, 0)

    if NEW_SELECT_API:
        @classmethod
        def select_face(cls, uv_layer, face, uv_select_sync, select):
            face.uv_select_set(select)

    else:
        @staticmethod
        def _select_face_sync(face, select):
            for v in face.verts:
                v.select = select

            face.select = select

        @classmethod
        def _select_face_no_sync(cls, uv_layer, face, select):
            for loop in face.loops:
                uv_loop = loop[uv_layer]
                uv_loop.select = select
                if cls.SELECTING_EDGES:
                    uv_loop.select_edge = select

        @classmethod
        def select_face(cls, uv_layer, face, uv_select_sync, select):
            if uv_select_sync:
                cls._select_face_sync(face, select)

            else:
                cls._select_face_no_sync(uv_layer, face, select)
      
    if NEW_SELECT_API:
        @classmethod
        def face_is_selected(cls, uv_layer, face, uv_select_sync):
            return cls.face_is_visible(face, uv_select_sync) and face.uv_select
        
    else:
        @staticmethod
        def face_is_selected(uv_layer, face, uv_select_sync):
            if uv_select_sync:
                return face.select
            else:
                if not face.select:
                    return False

                for loop in face.loops:
                    if not loop[uv_layer].select:
                        return False

                return True

    @staticmethod
    def face_is_visible(face, uv_select_sync):
        if uv_select_sync:
            return not face.hide
        else:
            return face.select

    def refresh_bmesh(self):
        refresh_required = False

        for p_obj in self.p_objects:
            refresh_required |= p_obj.refresh_bmesh()

        if not refresh_required:
            return

        if self.p_islands:
            for island in self.p_islands:
                island.refresh_bmesh()
        

    def __init__(self, _context, _mode=None, _only_with_selected_faces=False):
        self.iparam_registry = {
            metadata.param_type: IParamRegistry(param_type=metadata.param_type) for metadata in IPARAM_TYPE_METADATA.values()
        }

        self.string_id_map = StringIdMap()
        self.context = _context
        self.context_w = ContextWrapper(self.context)
        self.topo_analysis_config = MeshWrapper.get_topo_analysis_config(self.context)

        objs = []

        for obj in self.context_w.get_edit_objects():
            if not MeshWrapper.obj_is_mesh(obj):
                continue

            already_added = False
            for obj2 in objs:
                if MeshWrapper.objs_equal(obj, obj2):
                    already_added = True
                    break

            if not already_added:
                objs.append(obj)

        next_face_idx_offset = 0
        next_vert_idx_offset = 0

        self.total_selected_faces_stored_count = 0
        self.total_visible_faces_stored_count = 0
        self.p_objects = []

        for obj in objs:
            p_obj = PackObject(self, obj, next_face_idx_offset, next_vert_idx_offset)

            if len(p_obj.visible_faces_stored_indices) == 0:
                continue

            if _only_with_selected_faces and (len(p_obj.selected_faces_stored_indices) == 0):
                continue
            
            next_face_idx_offset = p_obj.next_face_idx_offset
            next_vert_idx_offset = p_obj.next_vert_idx_offset

            self.total_selected_faces_stored_count += len(p_obj.selected_faces_stored_indices)
            self.total_visible_faces_stored_count += len(p_obj.visible_faces_stored_indices)

            self.p_objects.append(p_obj)

        self.total_face_count = next_face_idx_offset
        self.p_islands = None

        self.config = None
        self.mode = _mode

    def init_config(self, _config=None):
        if _config is None:
            _config = PackConfig()

        self.config = _config
        self.config.init_from_mode(self.mode)

    def invalidate_faces_stored(self):
        for p_obj in self.p_objects:
            p_obj.invalidate_faces_stored()

    def register_iparam(self, iparam_info, param_index=None):
        return self.iparam_registry[iparam_info.PARAM_TYPE].register_iparam(iparam_info, param_index=param_index)

    def get_iparam_info(self, param_type, param_index):
        return self.iparam_registry[param_type].get_iparam_info(param_index)

    def serialize_uv_maps(self):
        send_unselected = self.config.send_unselected_islands
        send_pinned = self.config.send_pinned_islands
        send_verts_3d = self.config.send_verts_3d
        send_verts_3d_global = self.config.send_verts_3d_global
        iparam_serializers_in = self.config.iparam_serializers

        serialize_start = time.time()
        serialized_maps = bytes()

        face_id_len_array = []
        uv_coord_array = []
        vert_idx_array = []
    
        selected_count = 0
        serialization_flags = 0

        serialization_flags |= UvpmMapSerializationFlags.CONTAINS_FLAGS
        face_flags_array = []

        if send_verts_3d:
            serialization_flags |= UvpmMapSerializationFlags.CONTAINS_VERTS_3D
            verts_3d_array = []

        if send_verts_3d_global:
            serialization_flags |= UvpmMapSerializationFlags.CONTAINS_VERTS_3D_GLOBAL
            verts_3d_global_array = []

        # WARNING: dict element order is important
        iparam_serializers = {
            metadata.param_type: [] for metadata in IPARAM_TYPE_METADATA.values()
        }

        for ip_serializer in iparam_serializers_in:
            if not self.register_iparam(ip_serializer.iparam_info):
                continue

            ip_serializer.init_context(self)
            iparam_serializers[ip_serializer.iparam_info.PARAM_TYPE].append(ip_serializer)

        for p_obj_idx, p_obj in enumerate(self.p_objects):
            faces = p_obj.get_visible_faces_stored() if send_unselected else p_obj.get_selected_faces_stored()
            
            for face in faces:
                face_id_len_array.append(face.index + p_obj.face_idx_offset)
                face_id_len_array.append(len(face.verts))

                face_flags = 0
                uv_set_idx = self.SELECTED_UV_SET_IDX

                if send_unselected:
                    if p_obj.face_is_selected(face):
                        face_flags |= UvpmFaceInputFlags.SELECTED
                    else:
                        uv_set_idx = self.UNSELECTED_UV_SET_IDX

                else:
                    face_flags |= UvpmFaceInputFlags.SELECTED

                if send_pinned and p_obj.face_is_pinned(face):
                    uv_set_idx = self.PINNED_UV_SET_IDX

                if uv_set_idx == self.SELECTED_UV_SET_IDX:
                    selected_count += 1

                face_flags |= uv_set_idx * UvpmFaceInputFlags.UV_SET_IDX_OFFSET
                face_flags_array.append(face_flags)

                for ip_serializers in iparam_serializers.values():
                    for ip_serializer in ip_serializers:
                        ip_serializer.serialize_iparam(p_obj_idx, p_obj, face)

                for loop in face.loops:
                    uv = loop[p_obj.uv_layer].uv
                    if self.topo_analysis_config.uv_coord_prec is not None:
                        uv = uv.to_tuple(self.topo_analysis_config.uv_coord_prec)

                    uv_coord_array.append(uv[0])
                    uv_coord_array.append(uv[1])
                    vert_idx_array.append(p_obj.mw.loop_vertex_index(loop) + p_obj.vert_idx_offset)

                    if send_verts_3d:
                        vert_3d = loop.vert.co
                        verts_3d_array.append(vert_3d.x)
                        verts_3d_array.append(vert_3d.y)
                        verts_3d_array.append(vert_3d.z)

                    if send_verts_3d_global:
                        vert_3d = p_obj.obj.matrix_world @ loop.vert.co
                        verts_3d_global_array.append(vert_3d.x)
                        verts_3d_global_array.append(vert_3d.y)
                        verts_3d_global_array.append(vert_3d.z)

        serialized_maps += struct.pack('i', serialization_flags)
        serialized_maps += struct.pack('i', int(len(face_id_len_array) / 2))
        serialized_maps += struct.pack('i' * len(face_id_len_array), *face_id_len_array)
        serialized_maps += struct.pack('i', len(vert_idx_array))
        serialized_maps += struct.pack('f' * len(uv_coord_array), *uv_coord_array)
        serialized_maps += struct.pack('i' * len(vert_idx_array), *vert_idx_array)

        if (serialization_flags & UvpmMapSerializationFlags.CONTAINS_VERTS_3D) > 0:
            serialized_maps += struct.pack('f' * len(verts_3d_array), *verts_3d_array)

        if (serialization_flags & UvpmMapSerializationFlags.CONTAINS_VERTS_3D_GLOBAL) > 0:
            serialized_maps += struct.pack('f' * len(verts_3d_global_array), *verts_3d_global_array)

        if (serialization_flags & UvpmMapSerializationFlags.CONTAINS_FLAGS) > 0:
            serialized_maps += struct.pack('i' * len(face_flags_array), *face_flags_array)

        uv_set_count = len(self.UV_SETS)
        serialized_maps += struct.pack('i', uv_set_count)

        for uv_set in self.UV_SETS[0:uv_set_count]:
            serialized_maps += uv_set.serialize()

        serialized_maps += self.string_id_map.serialize()

        for ip_serializers in iparam_serializers.values():
            serialized_maps += struct.pack('i', len(ip_serializers))

            for ip_serializer in ip_serializers:
                serialized_maps += ip_serializer.serialize_iparam_info()
                iparam_values = ip_serializer.iparam_values
                serialized_maps += struct.pack(ip_serializer.iparam_info.PARAM_TYPE_MARK * len(iparam_values), *iparam_values)

        if in_debug_mode():
            print('UVPM serialization time: ' + str(time.time() - serialize_start))

        return serialized_maps, selected_count

    def islands_received(self):
        return self.p_islands is not None
    
    def get_mesh_wrappers(self):
        return [p_obj.mw for p_obj in self.p_objects]

    def set_islands(self, set_sizes, islands, flags):
        p_islands = []
        island_idx = 0

        for set_size in set_sizes:
            curr_obj_idx = 0

            for i in range(set_size):
                island_faces = islands[island_idx]
                island_flags = flags[island_idx]
                island_idx += 1
                
                next_obj_idx = curr_obj_idx + 1
                while next_obj_idx < len(self.p_objects) and self.p_objects[next_obj_idx].face_idx_offset <= island_faces[0]:
                    curr_obj_idx = next_obj_idx
                    next_obj_idx += 1

                selected = (island_flags & UvpmFaceInputFlags.SELECTED) > 0
                p_islands.append(PackIsland(self.p_objects[curr_obj_idx], island_faces, selected=selected))

        self.p_islands = p_islands

    def update_meshes(self):
        if self.context.mode != 'EDIT_MESH':
            return

        MeshWrapper.update_meshes(self)

    def scale_selected_faces(self, scale_factors):
        sx = scale_factors[0]
        sy = scale_factors[1]

        if sx == 1.0 and sy == 1.0:
            return
        
        self.pre_uv_self_modification()

        for p_obj in self.p_objects:

            selected_faces = p_obj.get_selected_faces()
            for face in selected_faces:
                for loop in face.loops:
                    if p_obj.mw.loop_uv_is_self_modified(loop):
                        continue

                    uv = loop[p_obj.uv_layer].uv
                    loop[p_obj.uv_layer].uv = (uv[0] * sx, uv[1] * sy)

    def pre_uv_self_modification(self):
        for p_obj in self.p_objects:
            p_obj.mw.pre_uv_self_modification()

    def pre_apply_out_islands(self):
        self.pre_uv_self_modification()

    def apply_out_islands(self, out_islands, save_iparam_handler):
        self.pre_apply_out_islands()

        if out_islands.string_id_map_array is not None:
            self.string_id_map.from_array(out_islands.string_id_map_array)

        dirty_iparams = [self.get_iparam_info(IntIParamInfo.PARAM_TYPE, param_index) for param_index in out_islands.dirty_iparam_indices]

        for out_island in out_islands.islands:
            p_island = self.p_islands[out_island.idx]
            p_island.apply_out_island(out_island)

            for iparam_info in dirty_iparams:
                p_island.save_iparam(iparam_info, save_iparam_handler)

    def save_iparam(self, iparam_info, iparam_value):
        for p_obj in self.p_objects:
            p_obj.save_iparam(iparam_info, iparam_value)

    def load_all_iparam_values(self, iparam_info):
        output = set()

        for p_obj in self.p_objects:
            output = output.union(p_obj.load_all_iparam_values(iparam_info))

        return list(output)
