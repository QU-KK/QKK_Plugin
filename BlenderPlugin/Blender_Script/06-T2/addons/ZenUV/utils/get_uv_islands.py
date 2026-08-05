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

""" Zen UV Islands Processor """

import bpy
import bmesh

from mathutils import Vector
from ZenUV.utils.generic import verify_uv_layer  # Timer
from ZenUV.utils.blender_zen_utils import ZenPolls
from collections import deque

from ZenUV.utils.vlog import Log

# from ZenUV.utils.progress import ProgressBar


def get_active_component(context: bpy.types.Context, bm: bmesh.types.BMesh, component_type: str = 'ISLAND'):
    if context.tool_settings.mesh_select_mode[:] == (False, False, True):
        a_face = bm.faces.active
        if a_face is not None:
            return [get_islands_by_face_list_indexes(bm, [a_face.index, ]), 'ISLAND'] if component_type == 'ISLAND' else [a_face, 'FACE']

    if len(bm.select_history) > 0:
        active_element = bm.select_history[-1]
        if isinstance(active_element, bmesh.types.BMVert):
            return [get_islands_by_vert_list_indexes(bm, [active_element.index, ]), 'ISLAND'] if component_type == 'ISLAND' else [active_element, 'VERTEX']
        elif isinstance(active_element, bmesh.types.BMEdge):
            return [get_islands_by_edge_list_indexes(bm, [active_element.index, ]), 'ISLAND'] if component_type == 'ISLAND' else [active_element, 'EDGE']
        elif isinstance(active_element, bmesh.types.BMFace):
            return [get_islands_by_face_list_indexes(bm, [active_element.index, ]), 'ISLAND'] if component_type == 'ISLAND' else [active_element, 'FACE']
        else:
            return None, 'NONE'
    else:
        return None, 'NONE'


def sort_island_faces(f):
    return f.index


def get_islands_by_face_list(context, bm, faces, uv_layer, use_seams_as_separator: bool = False):
    ''' Return islands by indexes '''
    # faces = [bm.faces[index] for index in indexes]
    selection = [f for f in faces if not f.hide]

    return zen_get_islands(bm, selection, has_selected_faces=True, use_seams_as_separator=use_seams_as_separator)


def get_islands_by_edge_list_indexes(bm, edge_list):
    ''' Return islands by indexes '''
    # faces = [bm.faces[index] for index in indexes]
    bm.edges.ensure_lookup_table()
    selection = {face for edge in [bm.edges[index] for index in edge_list] for face in edge.link_faces if not face.hide}
    return zen_get_islands(bm, selection, has_selected_faces=True)


def get_islands_by_vert_list_indexes(bm, verts, _sorted=False):
    ''' Return islands by indexes '''
    bm.verts.ensure_lookup_table()
    selection = [face for vert in [bm.verts[index] for index in verts] for face in vert.link_faces if not face.hide]
    return zen_get_islands(bm, selection, has_selected_faces=True, _sorted=_sorted)


def get_islands_by_seams(bm):
    ''' Return islands by seams '''
    return zen_get_islands_by_seams(bm, bm.faces, _sorted=True, by_seams=True)


def get_islands_by_face_list_indexes(bm, face_list):
    ''' Return islands by indexes '''
    # faces = [bm.faces[index] for index in indexes]
    bm.faces.ensure_lookup_table()
    selection = [bm.faces[index] for index in face_list if not bm.faces[index].hide]
    return zen_get_islands(bm, selection, has_selected_faces=True)


class IslandUtils:

    @classmethod
    def face_indexes_by_sel_elements(cls, context, bm):
        """
            Returns face indices converted from selected elements
            Use only for Island detection !!!
        """
        if context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                return []

            uv_selection_mode = context.scene.tool_settings.uv_select_mode
            if ZenPolls.version_since_3_2_0:
                if uv_selection_mode == 'VERTEX':
                    return list({f.index for f in bm.faces if not f.hide and f.select and True in [loop[uv_layer].select for loop in f.loops]})
                else:
                    return list({f.index for f in bm.faces for loop in f.loops if not f.hide and f.select and loop[uv_layer].select and loop[uv_layer].select_edge})
            else:
                if uv_selection_mode == 'VERTEX':
                    return list({f.index for f in bm.faces if not f.hide and f.select and True in [loop[uv_layer].select for loop in f.loops]})
                else:
                    return list({f.index for f in bm.faces for loop in f.loops if not f.hide and f.select and loop[uv_layer].select})
        else:
            selection_mode = context.tool_settings.mesh_select_mode
            if selection_mode[1]:
                return [face.index for edge in [e for e in bm.edges if e.select] for face in edge.link_faces if not face.hide]
            elif selection_mode[2]:
                return [face.index for face in bm.faces if face.select and not face.hide]
            elif selection_mode[0]:
                return [face.index for vert in [v for v in bm.verts if v.select] for face in vert.link_faces if not face.hide]


def get_island(context, bm, uv_layer, _sorted: bool = False, use_seams_as_separator: bool = False):
    ''' Return island (s) by selected faces, edges or vertices '''
    bm.faces.ensure_lookup_table()
    selection = [bm.faces[index] for index in IslandUtils.face_indexes_by_sel_elements(context, bm)]
    return zen_get_islands(bm, selection, has_selected_faces=True, _sorted=_sorted, use_seams_as_separator=use_seams_as_separator)


def get_selected_faces(context, bm):
    selection = [bm.faces[index] for index in FacesFactory.face_indexes_by_sel_mode(context, bm)]
    if selection:
        return [selection, ]
    return []


def get_islands_legacy(bm, use_seams_as_separator: bool = False):
    ''' Return all islands from mesh '''
    return zen_get_islands(bm, None, has_selected_faces=False, use_seams_as_separator=use_seams_as_separator)


def get_islands(context: bpy.types.Context, bm: bmesh.types.BMesh, is_include_hidden: bool = False, use_seams_as_separator: bool = False):
    ''' Return all islands from mesh '''
    sync_uv = context.scene.tool_settings.use_uv_select_sync
    if is_include_hidden:
        return zen_get_islands(bm, bm.faces, is_include_hidden=True, use_seams_as_separator=use_seams_as_separator)

    if context.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
        faces = {f for f in bm.faces if f.select}
    else:
        faces = {f for f in bm.faces if not f.hide}
    return zen_get_islands(bm, faces, has_selected_faces=True, use_seams_as_separator=use_seams_as_separator)


def get_islands_ignore_context(bm: bmesh.types.BMesh, is_include_hidden: bool = False):
    ''' Return all islands from mesh with UV Editor Sync ignorance'''

    return zen_get_islands(bm, {f for f in bm.faces}, has_selected_faces=True, is_include_hidden=is_include_hidden)


def get_island_by_loops(bm: bmesh.types.BMesh, loops: list):
    ''' Return all islands from given loops '''
    faces = list({loop.face for loop in loops})
    return list(zen_get_islands(bm, faces, has_selected_faces=True))


def get_islands_in_indices(bm, use_seams_as_separator: bool = False):
    ''' Return all islands as indices from mesh '''
    islands_ind = []
    islands = zen_get_islands(bm, None, has_selected_faces=False, use_seams_as_separator=use_seams_as_separator)
    for island in islands:
        islands_ind.append([f.index for f in island])
    return islands_ind


def get_selected_islands_in_indices(context, bm, use_seams_as_separator: bool = False):
    ''' Return selected islands as indices from mesh '''
    islands = zen_get_islands(
        bm,
        [bm.faces[index] for index in IslandUtils.face_indexes_by_sel_elements(context, bm)],
        has_selected_faces=True,
        use_seams_as_separator=use_seams_as_separator)
    return [[f.index for f in island] for island in islands]


def get_islands_selected_only(bm, selection):
    """ Return islands consist from selected faces only """
    return [sorted(island, key=sort_island_faces) for island in zen_get_islands(bm, selection, True, True)]
    # return zen_get_islands(bm, selection, True, True)


def get_uv_bound_edges_indexes(faces, uv_layer):
    """ Return indexes of border edges of given island (faces) from current UV Layer """
    if not faces:
        return []

    edges = {edge for face in faces for edge in face.edges if edge.link_loops}
    return [edge.index for edge in edges
            if edge.link_loops[0][uv_layer].uv
            != edge.link_loops[0].link_loop_radial_next.link_loop_next[uv_layer].uv
            or edge.link_loops[-1][uv_layer].uv
            != edge.link_loops[-1].link_loop_radial_next.link_loop_next[uv_layer].uv]


def get_bound_edges(edges_from_polygons):
    boundary_edges = []
    for edge in edges_from_polygons:
        if False in [f.select for f in edge.link_faces] or edge.is_boundary:
            boundary_edges.append(edge.index)
    return boundary_edges


def get_bound_edges_idxs_from_selected_faces(faces):
    if len(faces) == 1:
        return set()
    return {e.index for e in [e for f in faces for e in f.edges] if False in [f.select for f in e.link_faces] or e.is_boundary}


def get_bound_edges_idxs_from_facelist(facelist, progress=None):
    if len(facelist) == 0:
        return set()
    if len(facelist) == 1:
        return {e.index for e in list(facelist)[0].edges}

    from ZenUV.utils.progress import ProgressBar

    # return {
    #     e.index for e in [
    #         e for f in facelist for e in f.edges]
    #     if ProgressBar.check_update_spinner_progress(progress) and (False in [f in facelist for f in e.link_faces] or e.is_boundary)}

    face_set = {f.index for f in facelist}

    edge_indices = set()

    for face in facelist:
        for edge in face.edges:
            if ProgressBar.check_update_spinner_progress(progress) and any(linked_face.index not in face_set for linked_face in edge.link_faces) or edge.is_boundary:
                edge_indices.add(edge.index)
    return edge_indices


def zen_get_islands(
    bm: bmesh.types.BMesh,
    _selection: list,
    has_selected_faces: bool = False,
    selected_only: bool = False,
    _sorted: bool = False,
    is_include_hidden: bool = False,
    use_seams_as_separator: bool = False
) -> list:
    # print("SELECTION: ", _selection)
    uv_layer = verify_uv_layer(bm)

    if use_seams_as_separator:
        _bounds = {e.index for e in bm.edges if e.seam}
    else:
        if not selected_only:
            _bounds = get_uv_bound_edges_indexes(bm.faces, uv_layer)
        else:
            _bounds = get_bound_edges([e for f in _selection for e in f.edges])

    bm.edges.ensure_lookup_table()
    for edge in bm.edges:
        edge.tag = False
    # Tag all edges in uv borders
    for index in _bounds:
        bm.edges[index].tag = True
        # print(bm.edges[index], bm.edges[index].tag)

    _islands = []
    if has_selected_faces:
        faces = set(_selection)
    # if has_selected_faces:
    #     faces = {f for f in bm.faces if f.select}
        # faces = {f for f in bm.faces for l in f.loops if l[uv_layer].select}
    else:
        faces = set(bm.faces)
    while len(faces) != 0:
        init_face = faces.pop()
        island = {init_face}
        stack = [init_face]
        while len(stack) != 0:
            face = stack.pop()
            for e in face.edges:
                if not e.tag:
                    for f in e.link_faces:
                        if f not in island:
                            stack.append(f)
                            island.add(f)
        for f in island:
            faces.discard(f)
        if not is_include_hidden and True in [f.hide for f in island]:
            continue
        _islands.append(island)
    for index in _bounds:
        bm.edges[index].tag = False

    if _sorted:
        return [sorted(island, key=sort_island_faces) for island in _islands]

    return _islands


def zen_get_islands_by_seams(bm, _selection, has_selected_faces=False, selected_only=False, _sorted=False, by_seams=False):
    # print("SELECTION: ", _selection)
    uv_layer = verify_uv_layer(bm)
    if not selected_only:
        _bounds = get_uv_bound_edges_indexes(bm.faces, uv_layer)
    elif selected_only:
        _bounds = get_bound_edges([e for f in _selection for e in f.edges])
    if by_seams:
        _bounds = [e.index for e in bm.edges if e.seam]

    bm.edges.ensure_lookup_table()
    for edge in bm.edges:
        edge.tag = False
    # Tag all edges in uv borders
    for index in _bounds:
        bm.edges[index].tag = True
        # print(bm.edges[index], bm.edges[index].tag)

    _islands = []
    if has_selected_faces:
        faces = set(_selection)
    # if has_selected_faces:
    #     faces = {f for f in bm.faces if f.select}
        # faces = {f for f in bm.faces for l in f.loops if l[uv_layer].select}
    else:
        faces = set(bm.faces)
    while len(faces) != 0:
        init_face = faces.pop()
        island = {init_face}
        stack = [init_face]
        while len(stack) != 0:
            face = stack.pop()
            for e in face.edges:
                if not e.tag:
                    for f in e.link_faces:
                        if f not in island:
                            stack.append(f)
                            island.add(f)
        for f in island:
            faces.discard(f)
        if True in [f.hide for f in island]:
            continue
        _islands.append(island)
    for index in _bounds:
        bm.edges[index].tag = False

    if _sorted:
        return [sorted(island, key=sort_island_faces) for island in _islands]

    return _islands


class FacesFactory:

    @classmethod
    def find_adjacent_faces_bfs(cls, start_face, bound_edges, progress=None):
        from ZenUV.utils.progress import ProgressBar

        processed_faces = set()
        queue = deque([start_face])
        start_face.tag = True
        processed_faces.add(start_face)

        while queue:
            current_face = queue.popleft()
            # yield current_face

            ProgressBar.check_update_spinner_progress(progress)

            for edge in current_face.edges:
                if edge.index in bound_edges or edge.seam:
                    continue
                for linked_face in edge.link_faces:
                    if linked_face != current_face and linked_face not in processed_faces:
                        loop = [lp for lp in edge.link_loops if lp in linked_face.loops][0]
                        yield loop
                        processed_faces.add(linked_face)
                        linked_face.tag = True
                        queue.append(linked_face)

    @classmethod
    def face_indexes_by_sel_mode(cls, context, bm):
        """ Return face indexes converted from selected elements """
        if context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                return []

            mode = context.scene.tool_settings.uv_select_mode
            if ZenPolls.version_since_3_2_0:
                if mode == 'VERTEX':
                    return list({f.index for f in bm.faces if not f.hide and f.select and True in [loop[uv_layer].select for loop in f.loops]})
                else:
                    return list({f.index for f in bm.faces for loop in f.loops if not f.hide and f.select and loop[uv_layer].select and loop[uv_layer].select_edge})
            else:
                if mode == 'VERTEX':
                    return list({f.index for f in bm.faces if not f.hide and f.select and True in [loop[uv_layer].select for loop in f.loops]})
                else:
                    return list({f.index for f in bm.faces for loop in f.loops if not f.hide and f.select and loop[uv_layer].select})
        else:
            mode = context.tool_settings.mesh_select_mode
            if mode[1]:
                return [face.index for edge in [e for e in bm.edges if e.select] for face in edge.link_faces if not face.hide and False not in [vert.select for vert in face.verts]]
            elif mode[2]:
                return [face.index for face in bm.faces if face.select and not face.hide]
            elif mode[0]:
                return [face.index for vert in [v for v in bm.verts if v.select] for face in vert.link_faces if not face.hide and False not in [vert.select for vert in face.verts]]

    @classmethod
    def compound_groups(cls, bm: bmesh.types.BMesh, facelist: list, is_indices: bool = False, is_split_seams: bool = False):
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


class LoopsFactory:

    @classmethod
    def loops_by_islands(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        groupped: bool = True
    ) -> list:

        if groupped:
            return [[lp for f in island for lp in f.loops] for island in get_island(context, bm, uv_layer)]
        else:
            return sum([[lp for f in island for lp in f.loops] for island in get_island(context, bm, uv_layer)], [])

    @classmethod
    def loops_by_sel_mode(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        only_uv_edges: bool = False,
        groupped: bool = False,
        per_face: bool = False
    ) -> list:

        """ Return loops based on selected elements """

        loops = cls._loops_by_sel_mode(context, bm.faces, uv_layer, only_uv_edges, per_face)

        if groupped:
            if per_face:
                loops = [lp for cl in loops for lp in cl]

            if context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                return cls.compound_groups_from_loops(loops, uv_layer)
            else:
                p_face_idxs_groups = cls.compound_groups_from_loops_in_edit_mode_iterative(bm, loops)
                return [[lp for lp in loops if lp.edge.index in group] for group in p_face_idxs_groups]

        return loops

    @classmethod
    def _loops_by_sel_mode_from_whole_mesh(cls, context, bm, uv_layer, only_uv_edges, per_face):
        return cls._loops_by_sel_mode(context, bm.faces, uv_layer, only_uv_edges, per_face)

    @classmethod
    def get_selected_loops_by_island(
        cls,
        context: bpy.types.Context,
        island: list,
        uv_layer: bmesh.types.BMLayerItem,
        only_uv_edges: bool = False,
        per_face: bool = False
    ) -> list:
        return cls._loops_by_sel_mode(context, island, uv_layer, only_uv_edges, per_face)

    @classmethod
    def face_indexes_from_loops_selection(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        only_uv_edges: bool = False,
        groupped: bool = False,
        per_face: bool = False
    ) -> list:

        storage = []
        if groupped:
            for group in cls.loops_by_sel_mode(context, bm, uv_layer, only_uv_edges, groupped, per_face):
                collector = set()
                for loop in group:
                    if all(lp in group for lp in loop.face.loops):
                        collector.add(loop.face.index)
                storage.append(collector)
        else:
            for loop in cls.loops_by_sel_mode(context, bm, uv_layer, only_uv_edges, groupped, per_face):
                storage.append(loop.face.index)

        return storage

    @classmethod
    def _loops_by_sel_mode(cls, context: bpy.types.Context, inp_faces: list, uv_layer: bmesh.types.BMLayerItem, only_uv_edges: bool, per_face: bool):
        """ Return loops converted from selected elements """

        sync_uv = context.scene.tool_settings.use_uv_select_sync
        if context.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
            mode = 'FACE' if per_face else context.scene.tool_settings.uv_select_mode
            if ZenPolls.version_since_3_2_0:
                if only_uv_edges:
                    return list({loop for face in inp_faces for loop in face.loops if not face.hide and loop[uv_layer].select_edge})
                else:
                    if mode == 'VERTEX':
                        return list({loop for face in inp_faces for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})
                    elif mode == 'EDGE':
                        return list({loop for face in inp_faces for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})
                    else:
                        if per_face:
                            return [face.loops for face in inp_faces if not face.hide and face.select and False not in [loop[uv_layer].select for loop in face.loops] and False not in [loop[uv_layer].select_edge for loop in face.loops]]
                        else:
                            return list({loop for face in inp_faces for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})  # and loop[uv_layer].select_edge})
            else:  # Blender Ver less than 3.2.0
                return list({loop for face in inp_faces for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})

        else:
            mesh_select_mode = context.tool_settings.mesh_select_mode

            if per_face is True:
                return [[loop for loop in face.loops] for face in [face for face in inp_faces if face.select and not face.hide]]

            if mesh_select_mode[1] or mesh_select_mode[0]:
                # verts = list({v for f in inp_faces for v in f.verts})
                return [loop for vertex in [v for v in {v for f in inp_faces for v in f.verts} if v.select] for loop in vertex.link_loops if not loop.face.hide and loop.face in inp_faces]

            elif mesh_select_mode[2]:
                return [loop for face in [face for face in inp_faces if face.select and not face.hide] for loop in face.loops]

    @classmethod
    def compound_groups_from_loops_in_edit_mode_recursive(cls, bm, loops: list) -> list[list[int]]:
        # Recursive algorithm

        # Create a set of selected edges
        selected_edges_idxs = {lp.edge.index for lp in loops}

        # Build adjacency list (graph representation)
        adjacency_list = {e_index: [] for e_index in selected_edges_idxs}
        for i in selected_edges_idxs:
            edge = bm.edges[i]
            for vert in edge.verts:
                for other_edge in vert.link_edges:
                    if other_edge != edge and other_edge.index in selected_edges_idxs:
                        adjacency_list[edge.index].append(other_edge.index)

        # Depth-first search (DFS) to find connected components
        def dfs(node, visited, component):
            visited[node] = True
            component.append(node)
            for neighbor in adjacency_list[node]:
                if not visited[neighbor]:
                    dfs(neighbor, visited, component)

        # Find connected components (groups of edges with common vertices)
        visited = {node: False for node in adjacency_list}
        edge_groups_indices = []
        for node in visited:
            if not visited[node]:
                component = []
                dfs(node, visited, component)
                edge_groups_indices.append(component)

        # print(f'{len(edge_groups_indices) = }')
        # print(f'{edge_groups_indices}')

        return edge_groups_indices

    @classmethod
    def compound_groups_from_loops_in_edit_mode_iterative(cls, bm, loops: list) -> list[list[int]]:
        # Create a set of selected edges
        selected_edges_idxs = {lp.edge.index for lp in loops}
        bm.edges.ensure_lookup_table()
        # Build adjacency list (graph representation)
        adjacency_list = {e_index: [] for e_index in selected_edges_idxs}
        for i in selected_edges_idxs:
            edge = bm.edges[i]
            for vert in edge.verts:
                for other_edge in vert.link_edges:
                    if other_edge != edge and other_edge.index in selected_edges_idxs:
                        adjacency_list[edge.index].append(other_edge.index)

        # Depth-first search (DFS) to find connected components iteratively
        def dfs_iterative(start_node):
            visited = set()
            stack = [start_node]
            component = []
            while stack:
                node = stack.pop()
                if node not in visited:
                    visited.add(node)
                    component.append(node)
                    stack.extend(neighbor for neighbor in adjacency_list[node] if neighbor not in visited)
            return component

        # Find connected components (groups of edges with common vertices) iteratively
        visited = set()
        edge_groups_indices = []
        for node in adjacency_list:
            if node not in visited:
                component = dfs_iterative(node)
                edge_groups_indices.append(component)
                visited.update(component)

        # print(f'{len(edge_groups_indices) = }')
        # print(f'{edge_groups_indices}')

        return edge_groups_indices

    @classmethod
    def compound_groups_from_loops(
        cls,
        loops: list,
        uv_layer: bmesh.types.BMLayerItem,
        _sorted: bool = True
    ) -> list:

        def sort_by_index(f):
            return f.index

        def update_storages(upd):
            cluster.update(upd)
            stack.update(upd)

        _groups = []
        loops = set(loops)

        while len(loops) != 0:
            init_loop = loops.pop()
            cluster = {init_loop}
            stack = {init_loop}
            while len(stack) != 0:
                loop = stack.pop()

                linked = [lp for lp in loop.vert.link_loops if lp in loops and lp not in cluster and lp[uv_layer].uv == loop[uv_layer].uv]
                update_storages(linked)
                linked.append(loop)

                if ZenPolls.version_since_3_2_0:
                    adj = [lp.link_loop_next for lp in linked if lp.link_loop_next in loops and lp.link_loop_next not in cluster and lp[uv_layer].select_edge]
                    adj.extend([lp.link_loop_prev for lp in linked if lp.link_loop_prev in loops and lp.link_loop_prev not in cluster and lp.link_loop_prev[uv_layer].select_edge])
                else:
                    adj = [lp.link_loop_next for lp in linked if lp.link_loop_next in loops and lp.link_loop_next not in cluster]
                    adj.extend([lp.link_loop_prev for lp in linked if lp.link_loop_prev in loops and lp.link_loop_prev not in cluster])
                update_storages(adj)

            for lp in cluster:
                loops.discard(lp)
            _groups.append(list(cluster))

        if _sorted:
            return [sorted(cluster, key=sort_by_index) for cluster in _groups]

        return _groups

    @classmethod
    def get_condition_in_sync_mode(cls, uv_layer, start_loop, next_loop, next_edge_in_loop, direction: str):
        if direction == 'CW':
            return [
                    next_edge_in_loop.seam is True,
                    next_loop.edge.select,
                    next_loop.edge == start_loop.link_loop_next.link_loop_next.edge,
                    next_loop.edge == start_loop.link_loop_radial_next.link_loop_prev.edge,
                    len(start_loop.link_loop_next.vert.link_edges) > 4]
        else:
            return [
                    next_edge_in_loop.seam is True,
                    next_loop.edge.select,
                    next_loop.edge == start_loop.link_loop_next.link_loop_next.edge,
                    next_loop.edge == start_loop.link_loop_radial_next.link_loop_next.edge,
                    len(start_loop.vert.link_edges) > 4]

    @classmethod
    def get_condition_in_no_sync_mode(cls, uv_layer, start_loop, next_loop, next_edge_in_loop, direction: str):
        if direction == 'CW':
            return [
                    next_edge_in_loop.seam is True,
                    next_loop[uv_layer].select_edge if ZenPolls.version_since_3_2_0 else False,
                    next_loop.edge == start_loop.link_loop_next.link_loop_next.edge,
                    next_loop.edge == start_loop.link_loop_radial_next.link_loop_prev.edge,
                    len(start_loop.link_loop_next.vert.link_edges) > 4]
        else:
            return [
                    next_edge_in_loop.seam is True,
                    next_loop[uv_layer].select_edge if ZenPolls.version_since_3_2_0 else False,
                    next_loop.edge == start_loop.link_loop_next.link_loop_next.edge,
                    next_loop.edge == start_loop.link_loop_radial_next.link_loop_next.edge,
                    len(start_loop.vert.link_edges) > 4]

    @classmethod
    def walk_edgeloop_along(cls, init_loops: list, uv_layer: bmesh.types.BMLayerItem, is_no_sync: bool = False):
        for start_loop in init_loops:
            for lp in init_loops:
                yield lp
            if is_no_sync:
                # CW direction
                p_start_loop = start_loop
                while True:
                    next_edge_in_loop = p_start_loop.link_loop_next.link_loop_radial_next.edge
                    next_loop = p_start_loop.link_loop_next.link_loop_radial_next.link_loop_next

                    if True in cls.get_condition_in_no_sync_mode(uv_layer, p_start_loop, next_loop, next_edge_in_loop, direction='CW'):
                        break
                    else:
                        yield next_loop
                        p_start_loop = next_loop

                # CCW direction
                p_start_loop = start_loop
                while True:
                    next_edge_in_loop = p_start_loop.link_loop_prev.link_loop_radial_next.edge
                    next_loop = p_start_loop.link_loop_prev.link_loop_radial_next.link_loop_prev

                    if True in cls.get_condition_in_no_sync_mode(uv_layer, p_start_loop, next_loop, next_edge_in_loop, direction='CCW'):
                        break
                    else:
                        yield next_loop
                        p_start_loop = next_loop
            else:
                # CW direction
                p_start_loop = start_loop
                while True:
                    next_edge_in_loop = p_start_loop.link_loop_next.link_loop_radial_next.edge
                    next_loop = p_start_loop.link_loop_next.link_loop_radial_next.link_loop_next

                    if True in cls.get_condition_in_sync_mode(uv_layer, p_start_loop, next_loop, next_edge_in_loop, direction='CW'):
                        break
                    else:
                        yield next_loop
                        p_start_loop = next_loop

                # CCW direction
                p_start_loop = start_loop
                while True:
                    next_edge_in_loop = p_start_loop.link_loop_prev.link_loop_radial_next.edge
                    next_loop = p_start_loop.link_loop_prev.link_loop_radial_next.link_loop_prev

                    if True in cls.get_condition_in_sync_mode(uv_layer, p_start_loop, next_loop, next_edge_in_loop, direction='CCW'):
                        break
                    else:
                        yield next_loop
                        p_start_loop = next_loop


if __name__ == "__main__":
    pass
