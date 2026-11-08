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

# Copyright 2025, Valeriy Yatsenko - lightbio@gmail.com, Alex Zhornyak - alexander.zhornyak@gmail.com

""" Zen UV Islands Utilities """

import bpy
import bmesh

from collections import deque

from . uv_factory import UvIslandUtils
from . uvedit_select import uvedit_uv_select_test

from ..utils.blender_zen_utils import ZenPolls, is_loop_domain, is_sync_off

from ..utils.vlog import Log


class LoopsFactory:

    @staticmethod
    def is_loop_selected(loop, uv_layer, select_edge: bool):
        if ZenPolls.version_since_5_0_0:
            if select_edge:
                return loop.uv_select_edge
            else:
                return loop.uv_select_vert
        else:
            if select_edge:
                return loop[uv_layer].select_edge
            else:
                return loop[uv_layer].select

    @staticmethod
    def select_loop(loop, uv_layer: bmesh.types.BMLayerItem, select_edge: bool, state: bool):
        if ZenPolls.version_since_5_0_0:
            if select_edge:
                loop.uv_select_edge = state
            else:
                loop.uv_select_vert = state
        else:
            if select_edge:
                loop[uv_layer].select_edge = state
            else:
                loop[uv_layer].select = state

    @staticmethod
    def yield_loops_from_adjacent_faces_bfs(start_face, bound_edges, progress=None):
        from ..utils.progress import ProgressBar

        if bound_edges is None:
            bound_edges = set()
        elif not isinstance(bound_edges, set):
            bound_edges = set(bound_edges)

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
    def get_loops_by_islands(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        groupped: bool = True
    ) -> list:

        if groupped:
            return [
                [lp for f in island for lp in f.loops]
                for island in UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=True, b_include_hidden=False)]
        else:
            return sum([
                [lp for f in island for lp in f.loops]
                for island in UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=True, b_include_hidden=False)], [])

    @classmethod
    def get_loops_by_sel_mode(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        only_uv_edges: bool = False,
        groupped: bool = False,
        per_face: bool = False
    ) -> list:

        """ Return loops based on selected elements """

        loops = cls._internal_get_loops_by_sel_mode(context, bm, bm.faces, uv_layer, only_uv_edges, per_face)

        if groupped:
            if per_face:
                p_faces = {loop.face for group in loops for loop in group}
                if ZenPolls.version_since_5_0_0:
                    return [f.loops for f in p_faces if any(lp.uv_select_vert for lp in f.loops)]
                else:
                    return [f.loops for f in p_faces if any(lp[uv_layer].select for lp in f.loops)]

            if is_loop_domain(context):
                return cls.compound_groups_from_loops(loops, uv_layer)
            else:
                p_face_idxs_groups = cls.compound_groups_from_loops_in_edit_mode_iterative(bm, loops)
                idxs_groups = [set(i) for i in p_face_idxs_groups]
                return [[lp for lp in loops if lp.edge.index in group] for group in idxs_groups]

        return loops

    @classmethod
    def _loops_by_sel_mode_from_whole_mesh(cls, context, bm, uv_layer, only_uv_edges, per_face):
        return cls._internal_get_loops_by_sel_mode(context, bm, bm.faces, uv_layer, only_uv_edges, per_face)

    @classmethod
    def get_selected_loops_by_island(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        island: list,
        uv_layer: bmesh.types.BMLayerItem,
        only_uv_edges: bool = False,
        per_face: bool = False
    ) -> list:
        return cls._internal_get_loops_by_sel_mode(context, bm, island, uv_layer, only_uv_edges, per_face)

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
            for group in cls.get_loops_by_sel_mode(context, bm, uv_layer, only_uv_edges, groupped, per_face):
                collector = set()
                for loop in group:
                    if all(lp in group for lp in loop.face.loops):
                        collector.add(loop.face.index)
                storage.append(collector)
        else:
            for loop in cls.get_loops_by_sel_mode(context, bm, uv_layer, only_uv_edges, groupped, per_face):
                storage.append(loop.face.index)

        return storage

    @staticmethod
    def select_loops_in_uv_editor_in_sync_off(context, bm, looplist, uv_layer, state: bool = True, area_type=None):
        uv_sticky_select_mode = context.scene.tool_settings.uv_sticky_select_mode
        uv_selection_mode = context.scene.tool_settings.uv_select_mode
        if uv_selection_mode == 'FACE':
            if uv_sticky_select_mode == 'SHARED_LOCATION':
                for lp in looplist:
                    if not lp.face.select:
                        continue
                    lp.uv_select_vert = state
                    lp.uv_select_edge = state

            elif uv_sticky_select_mode == 'SHARED_VERTEX':
                for loop in looplist:
                    for lp in loop.vert.link_loops:
                        lp.uv_select_vert = state

            else:
                for loop in looplist:
                    loop.uv_select_vert = state
                    loop.uv_select_edge = state

        elif uv_selection_mode == 'EDGE':
            if uv_sticky_select_mode == 'SHARED_LOCATION':
                for loop in looplist:
                    next_loop = loop.link_loop_next

                    uv_next = next_loop[uv_layer].uv
                    uv_loop = loop[uv_layer].uv

                    loop.uv_select_vert = state
                    loop.uv_select_edge = state

                    next_loop.uv_select_vert = state

                    for lp in loop.vert.link_loops:
                        if lp[uv_layer].uv == uv_loop:
                            lp.uv_select_vert = state

                    for lp in next_loop.vert.link_loops:
                        if lp[uv_layer].uv == uv_next:
                            lp.uv_select_vert = state

            elif uv_sticky_select_mode == 'SHARED_VERTEX':
                for loop in looplist:
                    loop.uv_select_vert = state
                    loop.uv_select_edge = state
                    for lp in loop.vert.link_loops:
                        lp.uv_select_vert = state
            else:
                for loop in looplist:
                    loop.uv_select_vert = state
                    loop.uv_select_edge = state
        else:
            for loop in looplist:
                loop.uv_select_vert = state

            for loop in looplist:
                if loop.link_loop_next.uv_select_vert is True:
                    loop.uv_select_edge = state

        if uv_selection_mode == 'EDGE' and uv_sticky_select_mode == 'SHARED_LOCATION':
            if state:
                flush_faces = (f for f in bm.faces if f.select and not f.hide and all(lp.uv_select_edge for lp in f.loops))
            else:
                flush_faces = (f for f in bm.faces if f.select and not f.hide and not all(lp.uv_select_edge for lp in f.loops))
        else:
            if state:
                flush_faces = (f for f in bm.faces if f.select and not f.hide and all(lp.uv_select_vert for lp in f.loops))
            else:
                flush_faces = (f for f in bm.faces if f.select and not f.hide and not all(lp.uv_select_vert for lp in f.loops))

        for f in flush_faces:
            f.uv_select = state

        # TODO It may be necessary to replace it with the standard flush.
        # But at the moment it is not correct when flushing from edges to faces.

        # bm.uv_select_flush(True)

        # bm.uv_select_flush_mode(flush_down=True)
        # bm.uv_select_flush_shared(True)

    @classmethod
    def select_loops(cls, context, bm, looplist, uv_layer, state: bool = True, area_type=None):

        if area_type is None:
            p_space = getattr(context, "space_data", None)
            if p_space:
                area_type = p_space.type

        b_is_uv_editor = area_type == 'IMAGE_EDITOR'

        if ZenPolls.version_since_5_0_0:

            if b_is_uv_editor:

                uv_sticky_select_mode = context.scene.tool_settings.uv_sticky_select_mode
                bm.uv_select_sync_valid = True

                # UV Sync Selection is Off
                if is_sync_off(context, area_type=area_type):
                    cls.select_loops_in_uv_editor_in_sync_off(context, bm, looplist, uv_layer, state, area_type)

                # UV Sync Selection is On
                else:
                    mesh_selection_mode = context.tool_settings.mesh_select_mode[:]

                    # FACE MODE
                    if mesh_selection_mode == (False, False, True):
                        if uv_sticky_select_mode == 'SHARED_LOCATION':
                            for lp in looplist:
                                lp.uv_select_vert = state

                        elif uv_sticky_select_mode == 'SHARED_VERTEX':
                            for loop in looplist:
                                for lp in loop.vert.link_loops:
                                    lp.uv_select_vert = state
                                    lp.uv_select_edge = state
                        else:
                            for loop in looplist:
                                loop.uv_select_vert = state
                                loop.uv_select_edge = state

                    # EDGE MODE
                    elif mesh_selection_mode == (False, True, False):
                        if uv_sticky_select_mode == 'SHARED_LOCATION':
                            for loop in looplist:
                                next_loop = loop.link_loop_next
                                radial = loop.link_loop_radial_next

                                uv_loop = loop[uv_layer].uv
                                uv_next = next_loop[uv_layer].uv

                                loop.uv_select_vert = state
                                loop.uv_select_edge = state

                                next_loop.uv_select_vert = state

                                for lp in loop.vert.link_loops:
                                    if lp[uv_layer].uv == uv_loop:
                                        lp.uv_select_vert = state

                                for lp in next_loop.vert.link_loops:
                                    if lp[uv_layer].uv == uv_next:
                                        lp.uv_select_vert = state

                                if (loop.link_loop_next[uv_layer].uv == radial[uv_layer].uv and
                                   radial.link_loop_next[uv_layer].uv == loop[uv_layer].uv):
                                    radial.uv_select_edge = True

                        elif uv_sticky_select_mode == 'SHARED_VERTEX':
                            for loop in looplist:
                                loop.uv_select_vert = state
                                loop.uv_select_edge = state
                                for lp in loop.vert.link_loops:
                                    lp.uv_select_vert = state

                        else:
                            for loop in looplist:
                                loop.uv_select_vert = state
                                loop.link_loop_next.uv_select_vert = state
                                loop.uv_select_edge = state

                    # VERTEX or MIXED MODE
                    else:
                        for lp in looplist:
                            lp.uv_select_vert = state
                            lp.uv_select_edge = state

                    if mesh_selection_mode == (False, True, False) and uv_sticky_select_mode == 'SHARED_LOCATION':
                        if state:
                            flush_faces = (f for f in bm.faces if all(lp.uv_select_edge for lp in f.loops))
                        else:
                            flush_faces = (f for f in bm.faces if not all(lp.uv_select_edge for lp in f.loops))
                    else:
                        if state:
                            flush_faces = (f for f in bm.faces if all(lp.uv_select_vert for lp in f.loops))
                        else:
                            flush_faces = (f for f in bm.faces if not all(lp.uv_select_vert for lp in f.loops))

                    bm.uv_select_foreach_set_from_mesh(
                        state,
                        faces=flush_faces,
                        sticky_select_mode=context.tool_settings.uv_sticky_select_mode)

                    bm.select_flush_mode()
                    bm.uv_select_sync_to_mesh()

            # Other area types
            else:
                mesh_selection_mode = context.tool_settings.mesh_select_mode[:]

                if mesh_selection_mode == (False, True, False):
                    for lp in looplist:
                        lp.edge.select = state

                elif mesh_selection_mode == (False, False, True):
                    for lp in looplist:
                        lp.vert.select = state
                    for f in bm.faces:
                        if all(v.select for v in f.verts):
                            f.select = state

                else:
                    for loop in looplist:
                        loop.vert.select = state

                bm.select_flush_mode()
                if uv_layer:
                    bm.uv_select_sync_from_mesh()

        # Blender below 5.0
        else:
            uv_selection_mode = context.scene.tool_settings.uv_select_mode
            if is_loop_domain(context, area_type=area_type):
                if ZenPolls.version_since_3_2_0:
                    if uv_selection_mode == 'EDGE':
                        for loop in looplist:
                            loop[uv_layer].select = state
                            loop.link_loop_next[uv_layer].select = state
                            loop[uv_layer].select_edge = state

                            for lp in loop.vert.link_loops:
                                if lp[uv_layer].uv == loop[uv_layer].uv:
                                    lp[uv_layer].select = state

                    else:
                        for loop in looplist:
                            loop[uv_layer].select = state

                        for loop in looplist:
                            if loop.link_loop_next[uv_layer].select is True:
                                loop[uv_layer].select_edge = state

                # Below 3.2
                else:
                    for lp in looplist:
                        lp[uv_layer].select = state

            else:
                mesh_selection_mode = context.tool_settings.mesh_select_mode[:]
                if mesh_selection_mode == (False, True, False):
                    for lp in looplist:
                        lp.edge.select = state

                elif mesh_selection_mode == (False, False, True):
                    for lp in looplist:
                        lp.vert.select = state
                    for f in bm.faces:
                        if all(v.select for v in f.verts):
                            f.select = state

                else:
                    for loop in looplist:
                        loop.vert.select = state

                bm.select_flush_mode()

    @staticmethod
    def _loops_by_sel_mode_new(ts, bm, uv_layer):
        return [
            loop
            for face in bm.faces
            for loop in face.loops
            if not face.hide and uvedit_uv_select_test(ts, bm, loop, uv_layer)
        ]

    @staticmethod
    def collect_loops_in_uv_editor_in_sync_off(context, facelist, only_uv_edges, per_face):
        uv_selection_mode = 'FACE' if per_face else context.scene.tool_settings.uv_select_mode

        if uv_selection_mode == 'FACE':
            if per_face:
                return [f.loops for f in facelist if f.select and f.uv_select and not f.hide]
            else:
                return [lp for f in facelist for lp in f.loops if f.select and f.uv_select and not f.hide]
        elif uv_selection_mode == 'EDGE':
            if only_uv_edges:
                return [lp for f in facelist for lp in f.loops if f.select and not f.hide and lp.uv_select_edge]
            else:
                return [lp for f in facelist for lp in f.loops if f.select and not f.hide and lp.uv_select_vert]
        else:
            return [lp for f in facelist for lp in f.loops if f.select and not f.hide and lp.uv_select_vert]

    @classmethod
    def collect_loops_in_uv_editor(cls, context, bm: bmesh.types.BMesh, facelist: list, only_uv_edges: bool, per_face: bool, area_type=None):
        # UV Sync Selection is Off
        if is_sync_off(context, area_type=area_type):
            return cls.collect_loops_in_uv_editor_in_sync_off(context, facelist, only_uv_edges, per_face)
        # UV Sync Selection is On
        else:
            mesh_selection_mode = (False, False, True) if per_face else context.tool_settings.mesh_select_mode[:]
            if not bm.uv_select_sync_valid:
                bm.uv_select_sync_from_mesh()

            if mesh_selection_mode == (False, False, True):
                if per_face:
                    return [f.loops for f in facelist if not f.hide and (f.uv_select or all(lp.uv_select_vert for lp in f.loops))]
                else:
                    return [lp for f in facelist for lp in f.loops if not f.hide and (f.uv_select or all(lp.uv_select_vert for lp in f.loops))]

            elif mesh_selection_mode == (False, True, False):
                if only_uv_edges:
                    return [lp for f in facelist for lp in f.loops if not f.hide and lp.uv_select_edge]
                else:
                    return [lp for f in facelist for lp in f.loops if not f.hide and lp.uv_select_vert]
            else:
                return [lp for f in facelist for lp in f.loops if lp.uv_select_vert and not f.hide]

    @classmethod
    def _internal_get_loops_by_sel_mode(cls, context: bpy.types.Context, bm: bmesh.types.BMesh, facelist: list, uv_layer: bmesh.types.BMLayerItem, only_uv_edges: bool, per_face: bool, area_type=None):
        """ Return loops converted from selected elements """

        if area_type is None:
            p_space = getattr(context, "space_data", None)
            if p_space:
                area_type = p_space.type

        b_is_uv_editor = area_type == 'IMAGE_EDITOR'

        if ZenPolls.version_since_5_0_0:

            # Collect selection in UV EDITOR
            if b_is_uv_editor:
                return cls.collect_loops_in_uv_editor(context, bm, facelist, only_uv_edges, per_face, area_type=area_type)

            else:
                mesh_selection_mode = (False, False, True) if per_face else context.tool_settings.mesh_select_mode[:]
                if mesh_selection_mode == (False, False, True):
                    if per_face:
                        [f.loops for f in facelist if f.select and not f.hide]
                    else:
                        return [lp for f in facelist for lp in f.loops if f.select and not f.hide]
                elif mesh_selection_mode == (False, True, False):
                    if only_uv_edges:
                        return [loop for loop in (lp for f in facelist for lp in f.loops if not f.hide) if loop.edge.select]
                    else:
                        return [loop for loop in (lp for f in facelist for lp in f.loops if not f.hide) if loop.vert.select]
                else:
                    # return [lp for vert in {v for f in facelist for v in f.verts if v.select} for lp in vert.link_loops if lp.face in facelist and not lp.face.hide]
                    return [lp for f in facelist for lp in f.loops if lp.vert.select and not f.hide]
        # Below Blender v5.0
        else:
            if is_loop_domain(context, area_type=area_type):
                mode = 'FACE' if per_face else context.scene.tool_settings.uv_select_mode
                if ZenPolls.version_since_3_2_0:
                    if mode == 'VERTEX':
                        return list({loop for face in facelist for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})
                    elif mode == 'EDGE':
                        if only_uv_edges:
                            return list({loop for face in facelist for loop in face.loops if not face.hide and face.select and loop[uv_layer].select_edge})
                        else:
                            return list({loop for face in facelist for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})
                    else:
                        if per_face:
                            return [face.loops for face in facelist if not face.hide and face.select and False not in [loop[uv_layer].select for loop in face.loops] and all(loop[uv_layer].select_edge for loop in face.loops)]
                        else:
                            return list({loop for face in facelist for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})
                else:  # Blender Ver less than 3.2.0
                    return list({loop for face in facelist for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})

            # Sync On and VIEW_3D
            else:
                mesh_select_mode = context.tool_settings.mesh_select_mode

                if per_face:
                    return [[loop for loop in face.loops] for face in [face for face in facelist if face.select and not face.hide]]

                if only_uv_edges:
                    return list({loop for f in facelist for e in f.edges for loop in e.link_loops if not f.hide and e.select})

                if mesh_select_mode[0]:
                    face_set = set(facelist)
                    return [loop for vertex in [v for v in {v for f in facelist for v in f.verts} if v.select] for loop in vertex.link_loops if not loop.face.hide and loop.face in face_set]
                elif mesh_select_mode[1]:
                    face_set = set(facelist)
                    return [
                                loop
                                for v in {v for f in face_set for v in f.verts if v.select}
                                for loop in v.link_loops
                                if not loop.face.hide and loop.face in face_set
                            ]
                elif mesh_select_mode[2]:
                    return [loop for face in [face for face in facelist if face.select and not face.hide] for loop in face.loops]

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

                if ZenPolls.version_since_5_0_0:
                    adj = [lp.link_loop_next for lp in linked if lp.link_loop_next in loops and lp.link_loop_next not in cluster and lp.uv_select_edge]
                    adj.extend([lp.link_loop_prev for lp in linked if lp.link_loop_prev in loops and lp.link_loop_prev not in cluster and lp.link_loop_prev.uv_select_edge])
                elif ZenPolls.version_since_3_2_0:
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
    def get_condition_in_mesh_domain(cls, uv_layer, start_loop, next_loop, next_edge_in_loop, direction: str):
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
    def get_condition_in_loop_domain(cls, uv_layer, start_loop, next_loop, next_edge_in_loop, direction: str):
        if direction == 'CW':
            return [
                    next_edge_in_loop.seam is True,
                    next_loop.uv_select_edge
                    if ZenPolls.version_since_5_0_0 else
                    next_loop[uv_layer].select_edge
                    if ZenPolls.version_since_3_2_0 else
                    False,
                    next_loop.edge == start_loop.link_loop_next.link_loop_next.edge,
                    next_loop.edge == start_loop.link_loop_radial_next.link_loop_prev.edge,
                    len(start_loop.link_loop_next.vert.link_edges) > 4]
        else:
            return [
                    next_edge_in_loop.seam is True,
                    next_loop.uv_select_edge
                    if ZenPolls.version_since_5_0_0 else
                    next_loop[uv_layer].select_edge
                    if ZenPolls.version_since_3_2_0 else
                    False,
                    next_loop.edge == start_loop.link_loop_next.link_loop_next.edge,
                    next_loop.edge == start_loop.link_loop_radial_next.link_loop_next.edge,
                    len(start_loop.vert.link_edges) > 4]

    @classmethod
    def walk_edgeloop_along(cls, init_loops: list, uv_layer: bmesh.types.BMLayerItem, b_is_loop_domain: bool = False):
        for start_loop in init_loops:
            for lp in init_loops:
                yield lp
            if b_is_loop_domain:
                # CW direction
                p_start_loop = start_loop
                while True:
                    next_edge_in_loop = p_start_loop.link_loop_next.link_loop_radial_next.edge
                    next_loop = p_start_loop.link_loop_next.link_loop_radial_next.link_loop_next

                    if any(cls.get_condition_in_loop_domain(uv_layer, p_start_loop, next_loop, next_edge_in_loop, direction='CW')):
                        break
                    else:
                        yield next_loop
                        p_start_loop = next_loop

                # CCW direction
                p_start_loop = start_loop
                while True:
                    next_edge_in_loop = p_start_loop.link_loop_prev.link_loop_radial_next.edge
                    next_loop = p_start_loop.link_loop_prev.link_loop_radial_next.link_loop_prev

                    if any(cls.get_condition_in_loop_domain(uv_layer, p_start_loop, next_loop, next_edge_in_loop, direction='CCW')):
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

                    if any(cls.get_condition_in_mesh_domain(uv_layer, p_start_loop, next_loop, next_edge_in_loop, direction='CW')):
                        break
                    else:
                        yield next_loop
                        p_start_loop = next_loop

                # CCW direction
                p_start_loop = start_loop
                while True:
                    next_edge_in_loop = p_start_loop.link_loop_prev.link_loop_radial_next.edge
                    next_loop = p_start_loop.link_loop_prev.link_loop_radial_next.link_loop_prev

                    if any(cls.get_condition_in_mesh_domain(uv_layer, p_start_loop, next_loop, next_edge_in_loop, direction='CCW')):
                        break
                    else:
                        yield next_loop
                        p_start_loop = next_loop

    @staticmethod
    def select_linked_loops(looplist, uv_layer):
        if ZenPolls.version_since_5_0_0:
            for loop in looplist:
                for lp in loop.vert.link_loops:
                    lp.uv_select_vert = True
                    if lp.link_loop_next.uv_select_vert is True:
                        lp.uv_select_edge = True
                        lp.link_loop_radial_next.uv_select_edge = True
        else:
            if ZenPolls.version_since_3_2_0:
                for loop in looplist:
                    for lp in loop.vert.link_loops:
                        lp[uv_layer].select = True
                        if lp.link_loop_next[uv_layer].select is True:
                            lp[uv_layer].select_edge = True
                            lp.link_loop_radial_next[uv_layer].select_edge = True

            else:
                for loop in looplist:
                    for lp in loop.vert.link_loops:
                        lp[uv_layer].select = True

    @staticmethod
    def get_uv_border_loops_from_facelist(facelist, uv_layer, include_split_uv_coo: bool):
        """
        Get UV border loops from a given face list.

        A loop is considered a UV border if:
        * Its edge connects to at least one face outside the provided facelist, or
        * The edge is a mesh boundary (``edge.is_boundary``), or
        * ``include_split_uv_coo`` is True and the loop has discontinuous UV coordinates
            compared to its radial neighbor (indicating a UV split).

        :param facelist: List of faces to evaluate.
        :type facelist: list[bmesh.types.BMFace]
        :param uv_layer: UV layer used for reading UV coordinates.
        :type uv_layer: bmesh.types.BMLayerItem
        :param include_split_uv_coo: Include loops that form UV coordinate splits.
        :type include_split_uv_coo: bool
        :return: Set of UV loops located on the UV border of the specified faces.
        :rtype: set[bmesh.types.BMLoop]
        """
        def check_coo(loop):
            return loop.link_loop_radial_next.link_loop_next[uv_layer].uv != loop[uv_layer].uv
        face_set = {f.index for f in facelist}
        loops = set()

        for face in facelist:
            for loop in face.loops:
                if any(linked_face.index not in face_set for linked_face in loop.edge.link_faces) or loop.edge.is_boundary or (check_coo(loop) if include_split_uv_coo else False):
                    loops.add(loop)
        return loops


if __name__ == "__main__":
    pass
