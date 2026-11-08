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

# Copyright 2023-2025, Valeriy Yatsenko lightbio@gmail.com


import bmesh
import math

from collections import deque
from dataclasses import dataclass

from typing import List

from mathutils import Vector


@dataclass
class SmartLoopProps:
    stop_on_self_intersect: bool = True
    stop_on_seam: bool = False
    stop_on_sharp: bool = False
    stop_on_selected: bool = False

    stop_on_simple_vertex: bool = True
    simple_detect_obtuse_angle: bool = True

    stop_on_complex_vertex: bool = False
    complex_dir_weight: float = 0.5
    complex_sharp_weight: float = 0.5
    complex_dir_sharp_balance: float = 0.5

    use_edge_sharpness_limit: bool = False
    edge_sharpness_mode: str = 'AUTO'  # in {"BELOW", "ABOVE", "AUTO"}
    edge_sharpness_limit: float = 0.5235988

    use_edge_angle_limit: bool = False
    edge_angle_limit: float = 0.5235988

    def normalize_weights(self):
        """Ensure dir + sharp = 1"""
        self.complex_dir_weight = self.complex_dir_sharp_balance
        total = self.complex_dir_weight + self.complex_sharp_weight
        if abs(total - 1.0) > 1e-6:
            self.complex_sharp_weight = 1.0 - self.complex_dir_weight


class MeshAnalyse:

    @staticmethod
    def select_groups(bm, groups):
        for group in groups:
            if bm.select_mode == {'FACE'}:
                for f_idx in group:
                    bm.faces[f_idx].select = True
            elif bm.select_mode == {'EDGE'}:
                for edge in (e for i in group for e in bm.faces[i].edges):
                    edge.select = any(f.index not in group for f in edge.link_faces)
            else:
                for vertex in (v for i in group for v in bm.faces[i].verts):
                    vertex.select = any(f.index not in group for f in vertex.link_faces)

    @staticmethod
    def calc_edges_angle_from_vert(edge1, vertex, edge2):
        vec1 = (edge1.other_vert(vertex).co - vertex.co).normalized()
        vec2 = (edge2.other_vert(vertex).co - vertex.co).normalized()

        return vec1.angle(vec2, math.pi)

    @staticmethod
    def calc_edge_angle_from_their_normals(edge1, vertex, edge2):
        e1vec: Vector = (edge1.other_vert(vertex).co - vertex.co).normalized()
        e2vec: Vector = (edge2.other_vert(vertex).co - vertex.co).normalized()

        ort = e1vec.cross(e2vec)
        if ort.length < 1e-6:
            return math.pi
        else:
            ort.normalize()

        # n1 = e1vec.cross(ort).normalized()
        # n2 = ort.cross(e2vec).normalized()

        # return n1.angle(n2, 0)
        angle = math.atan2(e1vec.cross(e2vec).dot(ort), e1vec.dot(e2vec))
        return angle

    @staticmethod
    def calc_edge_angle_specific(edge1, vertex, edge2):
        e1vec: Vector = (vertex.co - edge1.other_vert(vertex).co).normalized()
        e2vec: Vector = (edge2.other_vert(vertex).co - vertex.co).normalized()

        return e1vec.angle(e2vec, 0)

    @classmethod
    def collect_cylindrical_faces(
        cls,
        bm: bmesh.types.BMesh,
        facelist: list,
        use_area_check: bool = True,
        edges_tolerance: float = 3.0,  # percentage
        area_tolerance: float = 15.0,  # precentage
        angle_tolerance: float = 0.877  # radians
    ):
        if not facelist:
            return []

        if isinstance(facelist[0], bmesh.types.BMFace):
            facelist = [f.index for f in facelist]

        visited = set()
        groups = []

        edge_angle_cache = {}

        def get_edge_angle(e):
            if e.index not in edge_angle_cache:
                edge_angle_cache[e.index] = e.calc_face_angle(math.pi)
            return edge_angle_cache[e.index]

        for i in facelist:
            start_face = bm.faces[i]
            if start_face.hide or start_face.index in visited:
                continue

            reference_area = start_face.calc_area() if use_area_check else None
            queue = deque([start_face])
            group = []

            while queue:
                f = queue.pop()
                if f.index in visited:
                    continue
                visited.add(f.index)

                if not cls.face_is_cylindrical(f, edges_tolerance,
                                               use_area_check,
                                               area_tolerance,
                                               reference_area):
                    continue

                group.append(f.index)

                for e in f.edges:
                    if get_edge_angle(e) > angle_tolerance:
                        continue
                    for lf in e.link_faces:
                        if not lf.hide and lf.index not in visited:
                            queue.append(lf)

            if group:
                groups.append(group)

        return [group for group in groups if MeshAnalyse.get_faceloop_type(bm, group) == 'CLOSED']

    @staticmethod
    def collect_adjacent_faces_simple(bm: bmesh.types.BMesh, facelist: List[int], angle_tolerance: float, min_group_size: int = 4):
        if not facelist:
            return []

        if isinstance(facelist[0], bmesh.types.BMFace):
            facelist = [f.index for f in facelist]

        visited = set()
        groups = []

        for i in facelist:
            start_face = bm.faces[i]
            if start_face.hide:
                continue

            if start_face.index in visited:
                continue

            to_check = [start_face]
            group = []

            while to_check:
                f = to_check.pop()
                if f.index in visited:
                    continue

                group.append(f.index)
                visited.add(f.index)
                for e in f.edges:
                    if e.calc_face_angle(0) > angle_tolerance:
                        continue
                    for lf in e.link_faces:
                        if lf.hide:
                            continue
                        if lf.index not in visited:
                            to_check.append(lf)

            if group:
                groups.append(group)

        if not groups:
            return []

        if min_group_size == 0:
            return groups

        return [g for g in groups if len(g) > min_group_size]

    @classmethod
    def collect_adjacent_faces(
        cls, bm: bmesh.types.BMesh, facelist: List[int],
        b_use_area_check: bool, edges_tolerance: float,
        area_tolerance: float, angle_tolerance: float,
        min_group_size: int = 4, check_faceloop_type: bool = True
    ):
        visited = set()
        groups = []

        if isinstance(facelist[0], bmesh.types.BMFace):
            facelist = [f.index for f in facelist]

        for i in facelist:
            start_face = bm.faces[i]
            if start_face.hide:
                continue

            if start_face.index in visited:
                continue

            to_check = [start_face]
            group = []
            reference_area = start_face.calc_area() if b_use_area_check else None

            while to_check:
                f = to_check.pop()
                if f.index in visited:
                    continue

                if cls.face_is_trapezium(f, edges_tolerance, b_use_area_check, area_tolerance, reference_area):
                    group.append(f.index)
                    visited.add(f.index)
                    for e in f.edges:
                        if e.calc_face_angle(0) > angle_tolerance:
                            continue
                        for lf in e.link_faces:
                            if lf.hide:
                                continue
                            if lf.index not in visited:
                                to_check.append(lf)

            if group:
                groups.append(group)

        if not groups:
            return []

        if min_group_size == 0:
            return groups

        if check_faceloop_type:
            return [g for g in groups if len(g) > min_group_size and not cls.get_faceloop_type(bm, g) in {'OPEN', 'INVALID'}]

        return [g for g in groups if len(g) > min_group_size]

    @staticmethod
    def merge_groups_by_edges(bm: bmesh.types.BMesh, groups: List[list], angle_tolerance: float = 0.611):
        group_edges = [
            {e.index for f_idx in group for e in bm.faces[f_idx].edges}
            for group in groups
        ]

        merged = []
        used = set()
        for i, group in enumerate(groups):
            if i in used:
                continue

            new_group = set(group)
            edges = group_edges[i]

            for j, sub_group in enumerate(groups):
                if j <= i or j in used:
                    continue

                if edges.isdisjoint(group_edges[j]):
                    continue

                if any(bm.edges[e].calc_face_angle(math.pi) > angle_tolerance for e in edges.intersection(group_edges[j])):
                    continue

                new_group.update(sub_group)
                edges.update(group_edges[j])
                used.add(j)

            merged.append(list(new_group))
            used.add(i)

        return merged

    @staticmethod
    def merge_groups_by_normals(bm, groups: List[list], tolerance_degrees=5.0):
        tolerance_cos = math.cos(math.radians(tolerance_degrees))

        def calc_group_normal(group):
            vec = Vector()
            for i in group:
                vec += bm.faces[i].normal
            if vec.length > 1e-6:
                return vec.normalized()
            return Vector((0.0, 0.0, 0.0))  # fallback

        group_normals = [calc_group_normal(group) for group in groups]

        merged = []
        used = set()

        group_edges = [
            {e.index for f_idx in group for e in bm.faces[f_idx].edges}
            for group in groups
        ]

        for i, group in enumerate(groups):
            if i in used:
                continue

            new_group = set(group)
            normal = group_normals[i]
            edges = set(group_edges[i])

            for j, sub_group in enumerate(groups):
                if j <= i or j in used:
                    continue
                sub_normal = group_normals[j]

                if normal.dot(sub_normal) < tolerance_cos:
                    continue

                if edges.isdisjoint(group_edges[j]):
                    continue

                new_group.update(sub_group)
                edges.update(group_edges[j])
                used.add(j)

            merged.append(list(new_group))
            used.add(i)

        return merged

    @staticmethod
    def get_faceloop_type(bm, faces=None):
        """
        Specifies the faceloop type for the set of selected faceloops.

        Args:
            bm (bmesh.types.BMesh): bmesh object.
            faces (list[bmesh.types.BMFace] or None): list of faces.
                If None, the selected ones are taken.

        Returns:
            str: "CLOSED" (closed faceloop),
                 "OPEN",
                 "INVALID" (not faceloop: branches, holes, etc.).
        """

        if not faces:
            return "INVALID"

        neighbors = {f: [] for f in faces}

        for i in faces:
            face = bm.faces[i]
            for e in face.edges:
                linked = [f for f in e.link_faces if f.index in faces and f.index != i]
                if len(linked) == 1:
                    neighbors[i].append(linked[0])

        # degrees of graph vertices (faces)
        degrees = [len(nbs) for nbs in neighbors.values()]

        if all(d == 2 for d in degrees):
            return "CLOSED"
        elif degrees.count(1) == 2 and all(d in {1, 2} for d in degrees):
            return "OPEN"
        else:
            return "INVALID"

    @staticmethod
    def almost_equal_values_percent(a, b, tol_percent=1.0):
        if a == 0 or b == 0:
            return False
        diff = abs(a - b) / max(a, b) * 100.0
        return diff <= tol_percent

    @classmethod
    def face_is_cylindrical(cls, f, edge_tol_percent=1.0, use_area_check=False, area_tol_percent=1.0, reference_area=None):
        """Check: quad with equal opposite edges and (optionally) same area"""

        if len(f.verts) != 4:
            return False

        edges = f.edges

        if not (cls.almost_equal_values_percent(edges[0].calc_length(), edges[2].calc_length(), edge_tol_percent) and
                cls.almost_equal_values_percent(edges[1].calc_length(), edges[3].calc_length(), edge_tol_percent)):
            return False

        if use_area_check:
            if reference_area is None:
                reference_area = f.calc_area()
            if not cls.almost_equal_values_percent(f.calc_area(), reference_area, area_tol_percent):
                return False

        return True

    @classmethod
    def face_is_trapezium(cls, f, edge_tol_percent=1.0, use_area=False, area_tol_percent=1.0, reference_area=None):
        if len(f.verts) != 4:
            return False

        edges = f.edges

        if sum((cls.almost_equal_values_percent(edges[0].calc_length(), edges[2].calc_length(), edge_tol_percent),
               cls.almost_equal_values_percent(edges[1].calc_length(), edges[3].calc_length(), edge_tol_percent))) != 1:
            return False

        if use_area:
            if reference_area is None:
                reference_area = f.calc_area()
            if not cls.almost_equal_values_percent(f.calc_area(), reference_area, area_tol_percent):
                return False

        return True

    @staticmethod
    def faces_same_area(faces: list, tolerance=0.2):

        if not faces:
            return False

        areas = [f.calc_area() for f in faces]
        min_a, max_a = min(areas), max(areas)

        if min_a == 0:
            return False

        return max_a <= min_a * (1 + tolerance)

    @staticmethod
    def find_closed_edge_loops(bm, edge_list: list):
        if not edge_list:
            return []

        vert_to_edges = {}
        for i in edge_list:
            e = bm.edges[i]
            for v in e.verts:
                vert_to_edges.setdefault(v, []).append(e)

        closed_loops = []

        visited = set()
        for i in edge_list:
            if i in visited:
                continue

            e = bm.edges[i]

            loop = [i]
            visited.add(e.index)

            v_start, v_next = e.verts
            v_current = v_next

            while True:
                edges_next = [ed for ed in vert_to_edges[v_current] if ed.index not in visited]
                if not edges_next:
                    break

                e_next = edges_next[0]
                visited.add(e_next.index)
                loop.append(e_next.index)

                v_current = e_next.other_vert(v_current)

                if v_current == v_start:
                    closed_loops.append(loop)
                    break

        return closed_loops

    @staticmethod
    def find_straight_edge(start_loop, vert, complex_dir_weight, complex_sharp_weight):
        start_edge_idx = start_loop.edge.index
        vecs = [[(e.other_vert(vert).co - vert.co).normalized(), e] for e in vert.link_edges]
        if len(vecs) < 2:
            return None

        normal = sum((f.normal for f in vert.link_faces), Vector())
        if normal.length_squared < 1e-6:
            return None
        normal.normalize()

        ref = vecs[0][0]
        tangent = ref.cross(normal)
        if tangent.length_squared < 1e-6:
            tangent = normal.orthogonal()
        tangent.normalize()
        bitangent = normal.cross(tangent).normalized()

        ref_vec = next(vec for vec, e in vecs if e.index == start_edge_idx)
        ref_vec = Vector((ref_vec.dot(tangent), ref_vec.dot(bitangent)))

        candidates = []
        for vec, e in vecs:
            if e.index == start_edge_idx:
                continue
            face_angle = e.calc_face_angle(0)
            edge_angle = ref_vec.angle(Vector((vec.dot(tangent), vec.dot(bitangent))), 0)
            score = complex_dir_weight * edge_angle / math.pi + complex_sharp_weight * (face_angle / math.pi)
            candidates.append((score, e.index, edge_angle, face_angle))

        if not candidates:
            return None

        # for i in candidates:
        #     print(i)

        best = max(candidates, key=lambda c: c[0])

        # if abs(best[3]) < edge_flatnes_tol_rad:
        #     return None

        return {
            "edge_index": best[1],
            "score": best[0],
            "edge_angle": best[2],
            "sharpnes": best[3]
        }

    @classmethod
    def loop_analyse_report(cls, checks):
        if any(checks):
            i = checks.index(True)
            report = [
                'Self Intersection: 00',
                'Hide: 01',
                'Seam: 02',
                'Sharp: 03',
                'Select: 04',
                'Open Edge (mesh border): 05',
                'Complex Vertex: 06'
            ]
            print(f'Report: {report[i]}')

    @classmethod
    def get_condition_in_sync_mode(cls, props: SmartLoopProps, start_loop, next_loop, visited_edges, direction: str) -> bool:
        next_vert_edges = start_loop.link_loop_next.vert.link_edges
        checks = {
            'CW': [
                lambda: any(e.index in visited_edges for e in next_vert_edges if e.index != start_loop.edge.index) if props.stop_on_self_intersect else False,  # Self Intersection
                lambda: next_loop.edge.hide is True,  # Stop on hidden mesh - Not exposed
                lambda: any(e.seam for e in next_vert_edges) if props.stop_on_seam else False,  # Stop on seam
                lambda: any(not e.smooth for e in next_vert_edges) if props.stop_on_sharp else False,  # Stop on sharp
                lambda: any(e.select for e in next_vert_edges if e.index != start_loop.edge.index) if props.stop_on_selected else False,  # Stop on selected edge
                lambda: next_loop.edge == start_loop.link_loop_next.link_loop_next.edge,  # Stop On mesh border - Not exposed
                # lambda: next_loop.edge == start_loop.link_loop_radial_next.link_loop_prev.edge,
                lambda: len(next_vert_edges) > 4 if props.stop_on_complex_vertex else False,  # Stop on complex vertex
            ],
            'CCW': [
                lambda: next_loop.edge.hide is True,
                lambda: next_loop.edge.seam is True,
                lambda: next_loop.edge.select,
                lambda: next_loop.edge == start_loop.link_loop_next.link_loop_next.edge,
                lambda: next_loop.edge == start_loop.link_loop_radial_next.link_loop_next.edge,
                lambda: len(start_loop.vert.link_edges) > 4 if props.stop_on_complex_vertex else False,
            ],
        }
        # test = [check() for check in checks[direction]]
        # if any(test):
        #     print(test)
        cls.loop_analyse_report([check() for check in checks[direction]])
        return any(check() for check in checks[direction])

    @classmethod
    def walk_edgeloop_along(cls, props: SmartLoopProps, bm, init_loops: list, max_steps: int = 10000):

        def walk_direction(bm, start_loop, direction: str, max_steps: int = 10000):
            p_loop = start_loop
            steps = 0
            visited_edges = []
            while steps < max_steps:
                # print(p_loop.edge.index)
                # print(f'{stop_on_complex_vertex = }')
                # ==============================
                # p_loop.edge.select = True
                # ==============================
                if direction == 'CW':
                    vert = p_loop.link_loop_next.vert
                    vert_edges_count = len(vert.link_edges)

                    if vert_edges_count == 3:
                        if not props.stop_on_simple_vertex:
                            candidate = cls.find_straight_edge(p_loop, vert, 1, 0)
                            if candidate is None:
                                break
                            if props.simple_detect_obtuse_angle and candidate["edge_angle"] < 2.79:
                                break
                            next_edge_idx = candidate['edge_index']
                            next_edge = bm.edges[next_edge_idx]

                            try:
                                next_loop = [lp for lp in next_edge.link_loops if lp.vert.index == vert.index][0]
                            except Exception:
                                break
                        else:
                            break
                    elif vert_edges_count > 4:
                        if not props.stop_on_complex_vertex:
                            props.normalize_weights()
                            candidate = cls.find_straight_edge(p_loop, vert, props.complex_dir_weight, props.complex_sharp_weight)
                            if candidate is None:
                                break
                            # if props.use_edge_sharpness_limit and abs(candidate['sharpnes']) < props.edge_sharpness_limit:
                            #     print('Sharpness Limit Break')
                            #     break
                            next_edge_idx = candidate['edge_index']

                            # if next_edge_idx in visited_edges:
                            #     print(f'Edge {next_edge_idx} in visited. --> Break')
                            #     break
                            next_edge = bm.edges[next_edge_idx]

                            try:
                                next_loop = [lp for lp in next_edge.link_loops if lp.vert.index == vert.index][0]
                            except Exception:
                                break
                        else:
                            break
                    else:
                        next_loop = p_loop.link_loop_next.link_loop_radial_next.link_loop_next
                # else:  # CCW
                #     if not stop_on_mult and len(p_loop.vert.link_edges) > 4:
                #         vert = p_loop.vert
                #         next_edge_idx = MeshAnalyse.find_straight_edge(p_loop, vert)
                #         next_edge = bm.edges[next_edge_idx]
                #         next_loop = [lp for lp in next_edge.link_loops if lp.vert.index == vert.index][0]
                #     else:
                #         next_loop = p_loop.link_loop_prev.link_loop_radial_next.link_loop_prev

                if cls.get_condition_in_sync_mode(props, p_loop, next_loop, visited_edges, direction):
                    # print(f'Edge {next_loop.edge.index} breaked by condition. --> Break')
                    break

                if props.use_edge_angle_limit:
                    if cls.calc_edge_angle_specific(p_loop.edge, vert, next_loop.edge) > props.edge_angle_limit:
                        break

                    if props.edge_sharpness_mode == 'BELOW':
                        if next_loop.edge.calc_face_angle(math.pi) > props.edge_sharpness_limit:
                            print(f'Break Edge Sharpest than {math.degrees(props.edge_sharpness_limit)}')
                            break
                    else:
                        if next_loop.edge.calc_face_angle(math.pi) < props.edge_sharpness_limit:
                            print(f'Break Edge Sharpest than {math.degrees(props.edge_sharpness_limit)}')
                            break

                yield next_loop
                visited_edges.append(next_loop.edge.index)
                p_loop = next_loop
                steps += 1
            else:
                print(f"[ZenUV] walk_direction stopped: max steps {max_steps} reached in {direction}.")

        yield from init_loops
        for start_loop in init_loops:
            if props.use_edge_sharpness_limit:
                # TODO Process AUTO BELOW ABOWE modes Not completed.
                auto_sharpness_candidate_value = start_loop.edge.calc_face_angle(math.pi)
                if props.edge_sharpness_mode == 'AUTO':
                    print(f'{math.degrees(auto_sharpness_candidate_value) = }')
                    if auto_sharpness_candidate_value < math.pi / 2:
                        props.edge_sharpness_mode = 'BELOW'
                    else:
                        props.edge_sharpness_mode = 'ABOWE'

                print(f'{props.edge_sharpness_mode = }')

            yield from walk_direction(bm, start_loop, 'CW', max_steps=max_steps)
            # yield from walk_direction(bm, start_loop, 'CCW')
