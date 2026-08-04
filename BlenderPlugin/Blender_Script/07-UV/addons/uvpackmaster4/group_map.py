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

from .group import UVPM4_GroupInfo
from .grouping_scheme_access import GroupByNameAccess, GroupByColorAccess
from .spipeline.engine.types import GroupingMethod


class GroupMap:

    def __init__(self, g_scheme, p_context):
        self.g_scheme = g_scheme
        self.p_context = p_context

        self.group_name_access = GroupByNameAccess(g_scheme)
        self.map = [UVPM4_GroupInfo.DEFAULT_GROUP_NUM] * self.p_context.total_face_count

        self.init()

    def set_map(self, p_obj, loc_face_idx, group_num):
        self.map[p_obj.to_glob_face_idx(loc_face_idx)] = group_num

    def get_map(self, p_obj, loc_face_idx):
        group_num = self.map[p_obj.to_glob_face_idx(loc_face_idx)]
        return group_num

    def iparam_label(self):
        return 'Group'


class GroupMapMaterial(GroupMap):

    SCRIPT_NAME_SUFFIX = 'material'

    def init(self):
        for p_obj in self.p_context.p_objects:
            def raise_error(msg):
                raise RuntimeError("Grouping by material error (object '{}'): {}".format(p_obj.obj.name, msg))

            if len(p_obj.obj.material_slots) == 0:
                raise_error('object does not have a material assigned')

            faces_to_process = p_obj.get_selected_faces_stored()

            for face in faces_to_process:
                mat_idx = face.material_index

                if not (mat_idx >= 0 and mat_idx < len(p_obj.obj.material_slots)):
                    raise_error('invalid material id')

                mat = p_obj.obj.material_slots[mat_idx]

                if mat is None:
                    raise_error('some faces belong to an empty material slot')

                group, new = self.group_name_access.get(mat.name)
                self.set_map(p_obj, face.index, group.num)

    def iparam_label(self):
        return 'Group By Material'


class GroupMapMeshPart(GroupMap):

    SCRIPT_NAME_SUFFIX = 'mesh_part'

    def init(self):
        for p_obj in self.p_context.p_objects:
            faces_to_process = p_obj.get_selected_faces_stored()
            faces_left = set([face.index for face in faces_to_process])

            while len(faces_left) > 0:
                new_group, new = self.group_name_access.get("Mesh part {}".format(self.g_scheme.group_count()))

                face_idx = list(faces_left)[0]
                faces_left.remove(face_idx)

                faces_to_process = []
                faces_to_process.append(face_idx)

                while len(faces_to_process) > 0:
                    new_face_idx = faces_to_process[0]
                    del faces_to_process[0]

                    self.set_map(p_obj, new_face_idx, new_group.num)
                    new_face = p_obj.mw.faces[new_face_idx]

                    for vert in new_face.verts:
                        for face in vert.link_faces:
                            if face.index not in faces_left:
                                continue

                            faces_to_process.append(face.index)
                            faces_left.remove(face.index)

    def iparam_label(self):
        return 'Group By Mesh Part'

    
class GroupMapObject(GroupMap):

    def init(self):
        for p_obj in self.p_context.p_objects:
            group, new = self.group_name_access.get(p_obj.obj.name)

            faces_to_process = p_obj.get_selected_faces_stored()

            for face in faces_to_process:
                self.set_map(p_obj, face.index, group.num)

    def iparam_label(self):
        return 'Group By Object'


class GroupMapTile(GroupMap):

    def init(self):
        for p_obj in self.p_context.p_objects:
            faces_to_process = p_obj.get_selected_faces_stored()

            for face in faces_to_process:
                uvs = face.loops[0][p_obj.uv_layer].uv
                group, new = self.group_name_access.get("Tile {}:{}".format(int(uvs[0]), int(uvs[1])))
                self.set_map(p_obj, face.index, group.num)

    def iparam_label(self):
        return 'Group By Tile'
    

class GroupMapVertexColor(GroupMap):

    def init(self):
        g_metadata = GROUPING_METHOD_METADATA[GroupingMethod.VERTEX_COLOR]
        group_by_color = GroupByColorAccess(self.g_scheme)

        for p_obj in self.p_context.p_objects:
            def raise_error(msg):
                raise RuntimeError("Grouping by vertex color error (object '{}'): {}".format(p_obj.obj.name, msg))
            
            color_layer = p_obj.mw.get_vertex_color_layer()
            if not color_layer:
                raise_error('object has no active vertex color')

            faces_to_process = p_obj.get_selected_faces_stored()

            for face in faces_to_process:
                color = color_layer.get_color(face)
                group, new = group_by_color.get(color)

                if new:
                    g_metadata.group_name_postprocess(group)

                self.set_map(p_obj, face.index, group.num)

    def iparam_label(self):
        return 'Group By Vertex Color'


class GroupMapCollection(GroupMap):

    def init(self):
        for p_obj in self.p_context.p_objects:
            coll_name = p_obj.obj.users_collection[0].name
            group, new = self.group_name_access.get(coll_name)

            faces_to_process = p_obj.get_selected_faces_stored()

            for face in faces_to_process:
                self.set_map(p_obj, face.index, group.num)

    def iparam_label(self):
        return 'Group By Collection'
    

class GroupMapManual(GroupMap):

    def init(self):
        for p_obj in self.p_context.p_objects:
            vcolor_layer = p_obj.get_or_create_vcolor_layer(self.g_scheme.get_iparam_info())

            for face in p_obj.mw.faces:
                group_num = self.g_scheme.get_iparam_value(vcolor_layer, face)  
                self.set_map(p_obj, face.index, group_num)


class GroupingMethodMetadata:

    def __init__(self, group_map_t, apply_prop_id):
        self.group_map_t = group_map_t
        self.apply_prop_id = apply_prop_id

    @staticmethod
    def group_name_postprocess(group):
        pass


class VertexColorGroupingMethodMetadata(GroupingMethodMetadata):

    def __init__(self):
        super().__init__(group_map_t=GroupMapVertexColor, apply_prop_id='color')

    @staticmethod
    def group_name_postprocess(group):
        group.name = 'C' + str(group.num)

    
GROUPING_METHOD_METADATA = {
    GroupingMethod.MATERIAL : GroupingMethodMetadata(group_map_t=GroupMapMaterial, apply_prop_id='name'),
    GroupingMethod.MESH : GroupingMethodMetadata(group_map_t=GroupMapMeshPart, apply_prop_id='name'),
    GroupingMethod.OBJECT : GroupingMethodMetadata(group_map_t=GroupMapObject, apply_prop_id='name'),
    GroupingMethod.TILE : GroupingMethodMetadata(group_map_t=GroupMapTile, apply_prop_id='name'),
    GroupingMethod.VERTEX_COLOR : VertexColorGroupingMethodMetadata(),
    GroupingMethod.COLLECTION : GroupingMethodMetadata(group_map_t=GroupMapCollection, apply_prop_id='name')
}
