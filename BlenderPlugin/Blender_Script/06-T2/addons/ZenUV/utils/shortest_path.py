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


import heapq
import math
from mathutils import Vector
from dataclasses import dataclass, field

from ..utils.blender_zen_utils import ZenPolls, get_selection_mode
from ..utils.loops_factory import LoopsFactory
from ..utils.mesh_factory import MeshIslandUtils


@dataclass
class Node:

    index: int = 0
    vert_index: int = None
    uv: Vector = None
    link_loops: list = field(default_factory=list)
    link_loops_indices: set = field(default_factory=set)  # Indices for later selection restore
    pin_states: list = field(default_factory=list)
    neighbours: list = field(default_factory=list)
    select: bool = False
    selected_uv_edges: list = field(default_factory=list)
    in_path: bool = False
    bbox_corner_position: Vector = None

    # Selection restoration
    linked_edges: list = field(default_factory=list)
    linked_faces: list = field(default_factory=list)

    def __hash__(self):
        return hash(self.index)

    # def __repr__(self):
    #     return f"n{self.index}"

    def __repr__(self):
        return f"Node(index={self.index}, uv={tuple(self.uv) if self.uv else None}, select={self.select})"


class GraphProcessor:

    @classmethod
    def compound_graph(cls, context, b_is_loop_based, uv_layer, bm, facelist: list, collect_neighbours: bool = False, skip_unselected: bool = False, store_selection: bool = False):
        node: Node = None
        nodes = dict()
        for f in facelist:
            for loop in f.loops:
                key = loop[uv_layer].uv.to_tuple(5)
                if key not in nodes:
                    p_uv: Vector = loop[uv_layer].uv.copy()
                    p_link_loops = [lp for lp in loop.vert.link_loops if lp[uv_layer].uv == p_uv]
                    p_link_loops_ids = [lp.index for lp in p_link_loops]  # Indices for later selection restore
                    p_select = (
                        any(lp.uv_select_vert for lp in p_link_loops)
                        if ZenPolls.version_since_5_0_0
                        else any(lp[uv_layer].select for lp in p_link_loops)) if b_is_loop_based else loop.vert.select
                    p_selected_uv_edges = (
                        [lp.uv_select_edge for lp in p_link_loops]
                        if ZenPolls.version_since_5_0_0
                        else [lp[uv_layer].select_edge for lp in p_link_loops])

                    nodes[key] = Node(
                                vert_index=loop.vert.index,
                                uv=p_uv,
                                link_loops=p_link_loops,
                                link_loops_indices=p_link_loops_ids,
                                select=p_select,
                                selected_uv_edges=p_selected_uv_edges
                                )
        if collect_neighbours:
            for f in facelist:
                loops = f.loops
                for i, loop in enumerate(loops):
                    key = loop[uv_layer].uv.to_tuple(5)
                    prev_loop = loop.link_loop_prev
                    next_loop = loop.link_loop_next
                    nodes[key].neighbours.extend([nodes[prev_loop[uv_layer].uv.to_tuple(5)], nodes[next_loop[uv_layer].uv.to_tuple(5)]])

            for node in nodes.values():
                node.neighbours = list(set(node.neighbours))

        for i, node in enumerate(nodes.values()):
            node.index = i

        if skip_unselected:
            return [node for node in nodes.values() if node.select]

        if store_selection:
            selection_mode = get_selection_mode(context)
            if selection_mode == 'EDGE':
                cls.store_linked_edges(nodes, bm, facelist)
            if selection_mode == 'FACE':
                cls.store_linked_faces(nodes, bm, facelist)

        return list(nodes.values())

    @staticmethod
    def store_linked_edges(nodes, bm, facelist):
        s_cluster_edges = {e.index for f in facelist for e in f.edges}
        for node in nodes.values():
            node.linked_edges = [[e.index, e.select] for e in bm.verts[node.vert_index].link_edges if e.index in s_cluster_edges]

    @staticmethod
    def store_linked_faces(nodes, bm, facelist):
        s_cluster_faces = {f.index for f in facelist}
        for node in nodes.values():
            node.linked_faces = [[f.index, f.select] for f in bm.verts[node.vert_index].link_faces if f.index in s_cluster_faces]

    @classmethod
    def node_set_position(cls, node, uv_layer, position: Vector = None, percent: float = 100):
        if position is None:
            position = node.bbox_corner_position
        if position is None:
            return
        position = Vector(node.uv).lerp(position, percent / 100.0)
        for loop in node.link_loops:
            loop[uv_layer].uv = position
        node.uv = position

    @classmethod
    def node_recollect_loops(cls, bm, node):
        node.link_loops = [lp for lp in bm.verts[node.vert_index].link_loops if lp.index in node.link_loops_indices]

    @classmethod
    def graph_select(cls, context, b_is_loop_based, bm, uv_layer, graph):
        if b_is_loop_based:
            looplist = []
            for node in graph:
                cls.node_recollect_loops(bm, node)
                looplist.extend(node.link_loops)
            LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)

        else:
            cls._select_by_types(context, bm, graph, select_full_graph=True)

    @classmethod
    def restore_selection_graph(cls, context, b_is_loop_based: bool, bm, uv_layer, graph):
        node: Node = None
        if b_is_loop_based:
            for node in graph:
                cls.node_recollect_loops(bm, node)
            for node in (n for n in graph if n.select):
                if ZenPolls.version_since_5_0_0:
                    for i in range(len(node.link_loops)):
                        loop = node.link_loops[i]
                        loop.uv_select_vert = True
                        loop.uv_select_edge = node.selected_uv_edges[i]
                else:
                    for i in range(len(node.link_loops)):
                        loop = node.link_loops[i]
                        loop[uv_layer].select = True
                        loop[uv_layer].select_edge = node.selected_uv_edges[i]

            if ZenPolls.version_since_5_0_0:
                facelist = {lp.face for n in graph for lp in n.link_loops}
                for face in facelist:
                    if all(lp.uv_select_vert for lp in face.loops) or all(lp.uv_select_edge for lp in face.loops):
                        face.uv_select = True
                MeshIslandUtils.update_uv_select_sync(context, bm)
        else:
            cls._select_by_types(context, bm, graph, select_full_graph=False)

    @classmethod
    def set_pin_graph(cls, b_is_loop_based: bool, bm, uv_layer, graph, pin_state: bool):
        for node in graph:
            cls.node_recollect_loops(bm, node)
            if b_is_loop_based:
                for i in range(len(node.link_loops)):
                    loop = node.link_loops[i]
                    if pin_state is False:
                        loop[uv_layer].pin_uv = node.pin_states[i]
            else:
                if pin_state is False:
                    for i in range(len(node.link_loops)):
                        node.link_loops[i][uv_layer].pin_uv = node.pin_states[i]

    @classmethod
    def _select_by_types(cls, context, bm, graph, select_full_graph: bool = False):
        mesh_selection_mode = get_selection_mode(context)
        if mesh_selection_mode == 'VERT':
            if select_full_graph:
                for node in graph:
                    bm.verts[node.vert_index].select = True
            else:
                for node in graph:
                    if node.select:
                        bm.verts[node.vert_index].select = True
            bm.select_flush_mode()
        elif mesh_selection_mode == 'EDGE':
            if select_full_graph:
                for i in {i for n in graph for i, _ in n.linked_edges}:
                    bm.edges[i].select = True
            else:
                for i in {i for n in graph for i, state in n.linked_edges if state}:
                    bm.edges[i].select = True
            bm.select_flush_mode()
        elif mesh_selection_mode == 'FACE':
            if select_full_graph:
                for i in {i for n in graph for i, _ in n.linked_faces}:
                    bm.faces[i].select = True
            else:
                for i in {i for n in graph for i, state in n.linked_faces if state}:
                    bm.faces[i].select = True

        MeshIslandUtils.update_uv_select_sync(context, bm)

    @classmethod
    def iter_edges_from_verts_path(cls, bm, path: list):
        for i in range(len(path)-1):
            v1 = bm.verts[path[i]]
            v2 = bm.verts[path[i + 1]]
            for e in v1.link_edges:
                if v2 in e.verts:
                    yield e
                    break

    @classmethod
    def iter_edges_from_nodes_path(cls, bm, path: list):
        for i in range(len(path)-1):
            v1 = bm.verts[path[i].vert_index]
            v2 = bm.verts[path[i + 1].vert_index]
            for e in v1.link_edges:
                if v2 in e.verts:
                    yield e
                    break

    @classmethod
    def iter_loops_from_nodes_path_for_vertex(cls, bm, path: list, loop_idxs):
        for edge in GraphProcessor.iter_edges_from_nodes_path(bm, path):
            for vert in edge.verts:
                for loop in vert.link_loops:
                    if loop.index in loop_idxs:
                        yield loop

    @classmethod
    def iter_loops_from_nodes_path_for_edge(cls, bm, path: list, loop_idxs):
        for edge in GraphProcessor.iter_edges_from_nodes_path(bm, path):
            for loop in edge.link_loops:
                if loop.index in loop_idxs:
                    yield loop

    @classmethod
    def get_all_faces_idxs_from_graph(cls, graph):
        return {i for n in graph for i, _ in n.linked_faces}

    @classmethod
    def sort_loops_by_angle(cls, nodes, start_angle: float = 0.0):
        uv_coords = [node.uv.copy() for node in nodes]

        center = sum(uv_coords, Vector((0, 0))) / len(uv_coords)

        def loop_angle(node):
            uv = node.uv
            return (math.atan2(uv.y - center.y, uv.x - center.x) - start_angle) % (2 * math.pi)

        return sorted(nodes, key=loop_angle)


class ShortPathUtils:

    @classmethod
    def get_shortest_path_verts(cls, bm, start_index: int, end_index: int):
        queue = [(0.0, start_index)]
        visited = set()
        dist = {start_index: 0.0}
        prev = {}

        while queue:
            current_dist, current = heapq.heappop(queue)
            if current in visited:
                continue
            visited.add(current)

            if current == end_index:
                break

            current_vert = bm.verts[current]
            for edge in current_vert.link_edges:
                neighbor = edge.other_vert(current_vert).index
                if neighbor in visited:
                    continue

                weight = edge.calc_length()
                new_dist = current_dist + weight

                if new_dist < dist.get(neighbor, float('inf')):
                    dist[neighbor] = new_dist
                    prev[neighbor] = current
                    heapq.heappush(queue, (new_dist, neighbor))

        path = []
        v = end_index
        while v in prev or v == start_index:
            path.append(v)
            if v == start_index:
                break
            v = prev[v]
        path.reverse()

        return path

    @classmethod
    def get_shortest_path_uv(cls, graph, start_index: int, end_index: int):
        queue = [(0.0, start_index)]
        visited = set()
        dist = {start_index: 0.0}
        prev = {}

        while queue:
            current_dist, current = heapq.heappop(queue)
            if current in visited:
                continue
            visited.add(current)

            if current == end_index:
                break

            v1_uv = graph[current].uv

            current_node = graph[current]
            for node in current_node.neighbours:
                neighbor = node.index
                if neighbor in visited:
                    continue

                v2_uv = node.uv
                weight = (v2_uv - v1_uv).length
                new_dist = current_dist + weight

                if new_dist < dist.get(neighbor, float('inf')):
                    dist[neighbor] = new_dist
                    prev[neighbor] = current
                    heapq.heappush(queue, (new_dist, neighbor))

        path = []
        v = end_index
        while v in prev or v == start_index:
            path.append(v)
            if v == start_index:
                break
            v = prev[v]
        path.reverse()

        return path
