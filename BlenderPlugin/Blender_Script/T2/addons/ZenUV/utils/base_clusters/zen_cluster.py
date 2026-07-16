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

from ZenUV.utils.base_clusters.base_elements import UvEdge, UvFace, UvVertex

from ZenUV.utils.generic import Scope, Distortion, ZenReport
from ZenUV.utils.base_clusters.base_cluster import BaseCluster
from ZenUV.utils.constants import u_axis
from ZenUV.utils.vlog import Log
from ZenUV.utils.bounding_box import BoundingBox2d


class CheckerZcluster:

    def chk_broken_borders_v_01(self):

        safe_loops = range(10)
        for c in safe_loops:
            b_verts = self.get_bound_verts()
            scope = Scope()
            for vert in b_verts:
                scope.append(vert.uv_co, vert)

            ids_scope = []
            for i, ve in scope.data.items():
                if len(ve) > 2:
                    ids_scope.append(list({v.index for v in ve}))

            if ids_scope:
                for ids in ids_scope:
                    if len(ids) == 1:
                        id = ids[0]
                        # Log.debug("here", self.uv_verts[id])
                        vert = self.uv_verts[id]
                        for i in range(len(vert.link_loops) - 1):
                            new_vert = UvVertex(
                                len(self.uv_verts) + 1,
                                vert.mesh_vert,
                                [vert.link_loops.pop(), ],
                                vert.uv_layer
                                )
                            new_vert.move_by(Distortion.get_vector_2d(0.0001))
                            self.uv_verts.append(new_vert)
            else:
                Log.debug("Regular Exit.", "++ " * 10)
                Log.debug("Total Cycles: ", c)
                return True
            self.coo_deps = {}
            self._collect_uv_verts()
            self._collect_uv_edges()
        Log.debug("Emergency Exit.", "-- " * 50)
        return False

    def douplicate_uv_vertex(self, in_vertex):
        new_vert = UvVertex(
            len(self.uv_verts) + 1,
            in_vertex.mesh_vert,
            [in_vertex.link_loops.pop(), ],
            in_vertex.uv_layer
            )
        self.uv_verts.append(new_vert)
        return new_vert

    def chk_broken_borders(self):

        safe_loops = range(10)
        for c in safe_loops:
            b_verts = self.get_bound_verts()
            scope = Scope()
            for vert in b_verts:
                scope.append(vert.uv_co, vert)

            ids_scope = []
            for i, ve in scope.data.items():
                if len(ve) > 2:
                    ids_scope.append(list({v.index for v in ve})[0])
        return ids_scope

    def fix_broken_borders(self):
        bborders = self.chk_broken_borders()
        if not bborders:
            # Log.debug("TEST: No Broken Borders")
            return True
        sorter = {}
        verts = [self.uv_verts[i] for i in bborders]

        for v in verts:
            sorter.update({v: []})
            faces = [f for f in v.link_uv_faces]
            full_set = []
            while faces:
                start_f = faces.pop()
                sub_set = [start_f, ]
                es1 = set(e.index for e in start_f.mesh_face.edges)
                i = len(faces)
                while i:
                    i -= 1
                    es2 = set(e.index for e in faces[i].mesh_face.edges)
                    if es1.intersection(es2):
                        sub_set.append(faces[i])
                        del faces[i]
                sorter[v].append(sub_set)
        counter = 0
        for vert, full_set in sorter.items():
            for i in range(1, len(full_set)):
                n_vert = self.douplicate_uv_vertex(vert)
                n_vert.link_uv_faces = full_set[i]
                n_vert_loops = set([loop for uv_face in n_vert.link_uv_faces for loop in uv_face.mesh_face.loops])
                vert_loops = set(vert.link_loops)
                intersection = vert_loops.intersection(n_vert_loops)
                n_vert.link_loops = list(intersection)
                n_vert.move_by(Distortion.get_vector_2d(0.0001))
                counter += 1

        # Log.debug(f"Created {counter} new uv veritces.")
        # Log.debug("TEST: Broken Borders Fixed")
        return True

    def check_multiple_loops(self):
        return [edge.index for edge in {e for f in self.island for e in f.edges} if len(edge.link_loops) > 2]


class ZenCluster(BaseCluster, CheckerZcluster):

    def __init__(self, context, obj, island, bm=None, index=-1) -> None:
        super().__init__(context, obj, island, bm, index=index)
        self.analyser = ZenReport()
        self.init_cycles = 0
        self.broken_borders_passed = False
        self.same_uv_verts_coords_passed = False
        self.init_zen_cluster()
        self._bounding_box = None

    @property
    def bounding_box(self):
        return BoundingBox2d(islands=[self.island, ], uv_layer=self.uv_layer)

    @bounding_box.setter
    def bounding_box(self):
        raise RuntimeError('ZenCluster.bounding_box read only')

    def init_zen_cluster(self):
        self.coo_deps = dict()
        self.mult = 1000
        self.init_cycles += 1

        self.uv_verts = []
        self.uv_faces = []
        self.uv_edges = []

        self._collect_uv_verts()
        self._collect_uv_faces()
        self._collect_uv_edges()

        self.check_consistency()
        # Log.debug(f"ZenCluster Init Cycles --> {self.init_cycles}")
        self.stripes = list()

        if not self.analyser.is_warning:
            self.analyser.message = 'Finished'

    def deselect_all_edges(self):
        for edge in self.uv_edges:
            edge.select(self.context, state=False)

    def get_edges_by_orientation(self, _dir=u_axis):
        # for edge in self.uv_edges:
        #     Log.debug(edge.get_orientation())
        return [edge for edge in self.uv_edges if edge.get_orientation() == _dir]

    def get_edges_by_angle_to_axis(self, angle, axis=u_axis):
        return [edge for edge in self.uv_edges if edge.get_orientation_by_angle(angle, axis)]

    def check_consistency(self):
        if not self.broken_borders_passed:
            self.broken_borders_passed = self.fix_broken_borders()

    def check_same_uv_coords(self):
        p_uv_verts_count = len(self.uv_verts)
        if p_uv_verts_count:
            return
        if p_uv_verts_count != len({v.uv_co for v in self.uv_verts}):
            self._fix_same_uv_vert_coords()
            self.same_uv_verts_coords_passed = True
            self.create_coo_dependency()
            self.init_zen_cluster()

    def update_uv_verts(self):
        for v in self.uv_verts:
            v.update_uv_co()

    def is_template(self):
        """ Here Cluster is template if all the UVs is Zero. Vector(0,0)"""
        return len(self.uv_verts) <= 1 and len(self.island) > 0

    def _collect_uv_verts(self):
        self.uv_verts.clear()
        self.create_coo_dependency()
        for idx, (key, data) in enumerate(self.coo_deps.items()):
            uv_vertex = UvVertex(idx, data["mesh_vert"], data["link_loops"], self.uv_layer)
            self.coo_deps[key].update({"uv_vert": uv_vertex})
            self.uv_verts.append(uv_vertex)

    def _fix_same_uv_vert_coords(self):
        scope = Scope()
        # result = True
        for v in self.uv_verts:
            scope.append(v.uv_co, v)
        for uv_vert in scope.get_mults_values():
            uv_vert.move_by(Distortion.get_vector_2d(size=0.01))
            # result = True
        return True

    def create_coo_dependency(self):
        from mathutils import Vector
        from collections import defaultdict

        self.coo_deps.clear()
        loops_scope = defaultdict(list)
        for loop in self.loops.values():
            loops_scope[(loop[self.uv_layer].uv.to_tuple(), loop.vert.index)].append(loop)

        for key, loops in loops_scope.items():
            self.coo_deps[key] = {"link_loops": loops, "mesh_vert": loops[0].vert, "uv_co": Vector(key[0])}

    def _collect_uv_faces(self):
        self.uv_faces.clear()
        for idx, face in enumerate(self.island):
            uv_face = UvFace(idx, face)
            for loop in face.loops:
                key = (loop[self.uv_layer].uv.to_tuple(), loop.vert.index)
                uv_face.uv_verts.append(self.coo_deps[key]["uv_vert"])
            for uv_vert in uv_face.uv_verts:
                uv_vert.link_uv_faces.append(uv_face)
            self.uv_faces.append(uv_face)

    def _collect_uv_edges(self):
        ambiguous_edges = []
        self.uv_edges.clear()
        if self.uv_verts:
            index = 0
            loops_scope = list(self.loops.values())
            while loops_scope:
                loop = loops_scope[0]
                prev_loops = [lp for lp in loop.edge.link_loops if lp.index in self.loops.keys() and len(lp.edge.link_faces) != 0]

                l1 = loop[self.uv_layer].uv.to_tuple()
                l1_mv_iindex = loop.vert.index
                key1 = (l1, l1_mv_iindex)
                l2 = loop.link_loop_next[self.uv_layer].uv.to_tuple()
                l2_mv_iindex = loop.link_loop_next.vert.index
                key2 = (l2, l2_mv_iindex)
                loops = []
                for lp in prev_loops:
                    loop_co = lp[self.uv_layer]
                    next_loop_co = lp.link_loop_next[self.uv_layer]
                    try:
                        if loop_co.uv.to_tuple() in [l1, l2] and next_loop_co.uv.to_tuple() in [l1, l2]:
                            loops.append(lp)
                            loops_scope.remove(lp)
                    except ValueError:
                        ambiguous_edges.append(lp.edge.index)

                vert_01 = self.coo_deps[key1]["uv_vert"]
                vert_02 = self.coo_deps[key2]["uv_vert"]

                edge = UvEdge(index, loop.edge, loops, vert_01, vert_02, self.uv_layer)
                vert_01.link_uv_edges.append(edge)
                vert_02.link_uv_edges.append(edge)
                self.uv_edges.append(edge)
                index += 1
        if len(ambiguous_edges):
            self.analyser.message_type = 'WARNING'
            self.analyser.message = 'Ambiguous edges'
            self.analyser.object_name = self.obj.name
            self.analyser.data.update({f'Object: {self.obj.name}. Island {self.index} Ambiguous edges --> ': ambiguous_edges})

    def get_bound_edges(self):
        boundary = [e for e in self.uv_edges if len(e.loops) == 1]
        return boundary

    def get_selected_edges(self):
        return [e for e in self.uv_edges if e.get_select_state(self.context)]

    def get_bound_verts(self):
        return [v for e in self.get_bound_edges() for v in e.verts]

    def append_uv_edge(self, uv_edge):
        uv_edge.index = len(self.uv_edges) + 1
        if isinstance(uv_edge, UvEdge):
            self.uv_edges.append(uv_edge)


class ZenClusterAlt():
    """ Zen Cluster with algorythm of alternatively creation """
    def __init__(self):
        self.init_zen_cluster()

    def init_zen_cluster(self):
        self.coo_deps = dict()
        self.mult = 1000

        self.uv_verts = []
        self.uv_faces = []
        self.uv_edges = []

        self._collect_uv_verts_alt()
        self._collect_uv_faces_alt()
        self._collect_uv_edges_alt()

    def _collect_uv_verts_alt(self):
        vcl = list(self.loops.values())
        idx = 0
        while vcl:
            loop = vcl.pop()
            vert = loop.vert
            coo = loop[self.uv_layer].uv
            uv_vert = UvVertex(idx, vert, [loop], self.uv_layer)
            to_remove = []
            for n_loop in vcl:
                n_vert = n_loop.vert
                n_coo = n_loop[self.uv_layer].uv
                if n_vert == vert and n_coo == coo:
                    uv_vert.link_loops.append(n_loop)
                    to_remove.append(n_loop)
            self.uv_verts.append(uv_vert)
            for lp in to_remove:
                vcl.pop(vcl.index(lp))
            idx += 1

    def _collect_uv_faces_alt(self):
        idx = 0
        for face in self.island:
            uv_face = UvFace(idx, face)
            for loop in face.loops:
                vert = loop.vert
                for u_vert in self.uv_verts:
                    if u_vert.mesh_vert == vert and loop in u_vert.link_loops:
                        uv_face.uv_verts.append(u_vert)
            idx += 1
            self.uv_faces.append(uv_face)

    def _collect_uv_edges_alt(self):
        if self.uv_verts:
            index = 0
            loops_scope = list(self.loops.values())
            while loops_scope:
                loop = loops_scope[0]
                prev_loops = [lp for lp in loop.edge.link_loops if lp.index in self.loops.keys()]

                l1 = loop[self.uv_layer].uv
                l2 = loop.link_loop_next[self.uv_layer].uv
                loops = []
                for lp in prev_loops:
                    loop_co = lp[self.uv_layer]
                    next_loop_co = lp.link_loop_next[self.uv_layer]

                    if loop_co.uv in [l1, l2] and next_loop_co.uv in [l1, l2]:
                        loops.append(lp)
                        loops_scope.remove(lp)

                vert_01 = [vert for vert in self.uv_verts if vert.mesh_vert == loop.vert and vert.uv_co == l1][0]
                vert_02 = [vert for vert in self.uv_verts if vert.mesh_vert == loop.link_loop_next.vert and vert.uv_co == l2][0]

                self.uv_edges.append(UvEdge(index, loop.edge, loops, vert_01, vert_02, self.uv_layer))
                index += 1
