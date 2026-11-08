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

# Copyright 2025, Valeriy Yatsenko - lightbio@gmail.com

""" Zen Mesh Islands Utilities """

# from ..utils.vlog import Log


import bpy
import bmesh

from mathutils import Vector
from ..utils.blender_zen_utils import ZenPolls

from ..utils.vlog import Log


class MeshIslandUtils:

    # @staticmethod
    # def get_mesh_border_edge_indices_from_faces_legacy(facelist):
    #     if len(facelist) == 0:
    #         return set()
    #     if len(facelist) == 1:
    #         return {e.index for e in list(facelist)[0].edges}

    #     bound_edges = set()
    #     for f in facelist:
    #         for e in f.edges:
    #             if e.is_boundary or any(not lf.select for lf in e.link_faces):
    #                 bound_edges.add(e.index)
    #     return bound_edges

    @staticmethod
    def update_uv_select_sync(context: bpy.types.Context, bm: bmesh.types.BMesh, area_type=None):

        if area_type is None:
            p_space = getattr(context, "space_data", None)
            if p_space:
                area_type = p_space.type

        b_is_uv_editor = area_type == 'IMAGE_EDITOR'

        if ZenPolls.version_since_5_0_0:
            if b_is_uv_editor:
                pass
            else:
                bm.uv_select_sync_from_mesh(sticky_select_mode=context.tool_settings.uv_sticky_select_mode)
        else:
            pass

    @staticmethod
    def compound_groups_from_faces(bm: bmesh.types.BMesh, facelist: list, is_indices: bool = False, is_split_seams: bool = False):
        face_set = set(facelist)

        adjacency = {f.index: set() for f in facelist}
        for face in facelist:
            face_idx = face.index
            for edge in face.edges:
                if is_split_seams and edge.seam:
                    continue
                for linked_face in edge.link_faces:
                    if linked_face != face and linked_face in face_set:
                        adjacency[face_idx].add(linked_face.index)

        def dfs(start_idx, visited, component):
            stack = [start_idx]
            while stack:
                current = stack.pop()
                if not visited[current]:
                    visited[current] = True
                    component.append(current)
                    stack.extend(neigh for neigh in adjacency[current] if not visited[neigh])

        visited = {idx: False for idx in adjacency}
        face_groups_indices = []
        for idx in adjacency:
            if not visited[idx]:
                component = []
                dfs(idx, visited, component)
                face_groups_indices.append(component)

        if is_indices:
            return face_groups_indices
        else:
            return [[bm.faces[i] for i in group] for group in face_groups_indices]

    @classmethod
    def get_poly_island_normal(self, p_island: list):
        return sum((face.normal for face in p_island), Vector()).normalized()

    @classmethod
    def get_poly_island_center(self, p_island: list):
        return sum((face.calc_center_median() for face in p_island), Vector()) / len(p_island) if p_island else Vector()

    @staticmethod
    def get_active_component(context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer, component_type: str = 'ISLAND'):
        from . uv_factory import UvIslandUtils
        if context.tool_settings.mesh_select_mode[:] == (False, False, True):
            a_face = bm.faces.active
            if a_face is not None:
                return [UvIslandUtils.get_islands_by_facelist(bm, uv_layer, [a_face, ]), 'ISLAND'] if component_type == 'ISLAND' else [a_face, 'FACE']

        if len(bm.select_history) > 0:
            active_element = bm.select_history[-1]
            if isinstance(active_element, bmesh.types.BMVert):
                return [UvIslandUtils.get_islands_by_vertlist_indexes(bm, uv_layer, [active_element.index, ]), 'ISLAND'] if component_type == 'ISLAND' else [active_element, 'VERTEX']
            elif isinstance(active_element, bmesh.types.BMEdge):
                return [UvIslandUtils.get_islands_by_edgelist_indexes(bm, uv_layer, [active_element.index, ]), 'ISLAND'] if component_type == 'ISLAND' else [active_element, 'EDGE']
            elif isinstance(active_element, bmesh.types.BMFace):
                return [UvIslandUtils.get_islands_by_facelist(bm, uv_layer, [active_element, ]), 'ISLAND'] if component_type == 'ISLAND' else [active_element, 'FACE']
            else:
                return None, 'NONE'
        else:
            return None, 'NONE'

    @staticmethod
    def get_mesh_border_edge_indices_from_faces(facelist, progress=None):

        from ..utils.progress import ProgressBar

        if len(facelist) == 0:
            return set()
        if len(facelist) == 1:
            return {e.index for e in list(facelist)[0].edges}

        face_set = {f.index for f in facelist}

        edge_indices = set()

        for face in facelist:
            for edge in face.edges:
                if ProgressBar.check_update_spinner_progress(progress) and any(linked_face.index not in face_set for linked_face in edge.link_faces) or edge.is_boundary:
                    edge_indices.add(edge.index)
        return edge_indices

    @classmethod
    def _internal_yield_mesh_islands(
        cls,
        bm: bmesh.types.BMesh,
        facelist: list,
        b_include_partially_hidden: bool = False
    ):
        """Finds islands of the mesh divided by edge.seam.
        Returns a generator of lists of edges (islands)."""

        used = [False] * len(bm.faces)
        used_get = used.__getitem__
        used_set = used.__setitem__

        stack_append = list.append
        stack_pop = list.pop

        for seed_face in facelist:
            if used_get(seed_face.index):
                continue

            used_set(seed_face.index, True)
            island = [seed_face]
            stack = [seed_face]

            while stack:
                f = stack_pop(stack)
                for e in f.edges:
                    if e.seam:
                        continue
                    for linked_face in e.link_faces:
                        if used_get(linked_face.index):
                            continue
                        used_set(linked_face.index, True)
                        island.append(linked_face)
                        stack_append(stack, linked_face)

            if not b_include_partially_hidden and any(f.hide for f in island):
                continue

            yield island


if __name__ == "__main__":
    pass
