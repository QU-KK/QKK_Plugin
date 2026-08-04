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

# Copyright 2024, Valeriy Yatsenko

"""
Zen UV Quadrify operator based on native Blender Follow Active Quad operator.
"""

import bpy
import bmesh
from dataclasses import dataclass, field
import time
from mathutils import Vector, Matrix

from ZenUV.utils.transform import ZenLocRotScale
from ZenUV.utils.transform import centroid
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import (
    fit_uv_view,
    ensure_facemap, set_face_int_tag)
from ZenUV.utils.get_uv_islands import get_bound_edges_idxs_from_facelist, get_uv_bound_edges_indexes
from ZenUV.utils.hops_integration import show_uv_in_3dview
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.ui.pie import ZsPieFactory
from ZenUV.ops.texel_density.td_utils import TdContext, TexelDensityFactory
from ZenUV.ops.zen_unwrap.finishing import FINISHED_FACEMAP_NAME
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage

from ZenUV.utils.progress import ProgressBar, ProgressCancelException

from ZenUV.utils.annotations_toolbox.math_visualizer import MathVisualizer

from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.generic import Timer

from ZenUV.utils.vlog import Log


class QuadrifyMarkState:

    is_mark_allowed: bool = False
    mark_seam: bool = None
    mark_sharp: bool = None

    @classmethod
    def init(cls, mark_borders: bool, mark_seam: bool, mark_sharp: bool):
        addon_prefs = get_prefs()
        if mark_borders:
            if addon_prefs.useGlobalMarkSettings:
                cls.mark_seam = addon_prefs.markSeamEdges
                cls.mark_sharp = addon_prefs.markSharpEdges
            else:
                cls.mark_seam = mark_seam
                cls.mark_sharp = mark_sharp

            if any((cls.mark_seam, cls.mark_sharp)):
                cls.is_mark_allowed = True
            else:
                cls.is_mark_allowed = False

        else:
            cls.is_mark_allowed = False


@dataclass
class ZenQuadrifyVisualizerData:

    arrows_offset: float = 0.05
    loops_offset = offset = 0.01

    # arrays

    start_point_co_2d: list = field(default_factory=list)
    start_point_co_3d: list = field(default_factory=list)
    start_point_size: float = 0.005
    start_point_rotation: Matrix = Matrix()

    average_edges_3d: list = field(default_factory=list)
    average_edges_2d: list = field(default_factory=list)

    master_edges: list = field(default_factory=list)
    ort_edges: list = field(default_factory=list)

    master_edges_2d: list = field(default_factory=list)
    ort_edges_2d: list = field(default_factory=list)

    distribution_3d: list = field(default_factory=list)
    distribution_2d: list = field(default_factory=list)
    distribution_indexes: list = field(default_factory=list)

    skipped_faces: list = field(default_factory=list)


class Qviz:

    obj_matrix_world: Matrix = Matrix()

    data: ZenQuadrifyVisualizerData = None

    area_type: str = None
    is_show_ops_annotations: bool = False

    @classmethod
    def do_matrix_correction(cls, coords: list):
        return ([cls.obj_matrix_world @ v[0], cls.obj_matrix_world @ v[1]] for v in coords)

    @classmethod
    def show(cls, context, uv_layer):
        vis = MathVisualizer(context, 'ZenUV Quadrify')

        letters_size = 3  # NOTE: non-screen: 0.025
        letters_position = (10, 10, 0)  # NOTE: non-screen: (0, -0.1, 0)
        letters_line_width = 1  # NOTE: non-screen: 3
        letters_screen_mode = True

        vis.add_text(
            'Description', 0, "Zen UV | Quadrify | faces distribution",
            line_width=letters_line_width, letters_size=letters_size, position=letters_position, is_screen_mode=letters_screen_mode)

        if cls.area_type == 'VIEW_3D':
            vis.add_vector('Master', 0, cls.do_matrix_correction(cls.data.master_edges), color=(0.4, 0, 0), clear=True, show_in_front=False, arrow_size=0)
            vis.add_vector('Ort', 0, cls.do_matrix_correction(cls.data.ort_edges), color=(0, 0.5, 0), clear=True, show_in_front=False, arrow_size=0)
            vis.add_vector(
                'Distribution',
                0,
                cls.do_matrix_correction(cls.data.distribution_3d),
                color=(0.3, 0.3, 0.7),
                clear=True,
                is_constant_arrow_size=True,
                arrow_size=cls.data.start_point_size * 3,
                show_in_front=False)

            vis.clear('Averaged', 0)
            vis.add_vector('Averaged', 0, cls.do_matrix_correction(cls.data.average_edges_3d), color=(0.8, 0.5, 0), clear=True, show_in_front=False, arrow_size=0)

            vis.add_dot(
                'Starting Point', 0, color=(1, 0, 0),
                position=cls.obj_matrix_world @ cls.data.start_point_co_3d,
                rotation=cls.data.start_point_rotation,
                clear=True, size=sum(cls.obj_matrix_world.to_scale()[:]) / 3 * cls.data.start_point_size, line_width=6)

            vis.clear('Skipped faces', 0)
            p_size = sum(cls.obj_matrix_world.to_scale()[:]) / 3 * cls.data.start_point_size * 4
            for f in cls.data.skipped_faces:
                vis.add_cross(
                    'Skipped faces', 0, color=(1, 0, 0),
                    position=cls.obj_matrix_world @ f.calc_center_median(),
                    rotation=ZenLocRotScale(None, f.normal.to_track_quat('Z', 'X'), None),
                    clear=False, size=p_size
                )

        elif cls.area_type == 'IMAGE_EDITOR':
            cls.data.start_point_size *= 0.5

            # Faces distribution

            vis.add_vector(
                'Distribution2D',
                0,
                cls.data.distribution_2d,
                color=(0.3, 0.4, 0.6),
                clear=True,
                is_constant_arrow_size=True,
                arrow_size=cls.data.start_point_size)

            # Averaged for average mode only
            vis.clear('Averaged2D', 0)
            vis.add_vector('Averaged2D', 0, cls.data.average_edges_2d, color=(0.8, 0.5, 0), clear=True, show_in_front=False, arrow_size=0)

            # Starting Point

            vis.add_dot('Starting Point2D', 0, color=(1, 0, 0), position=cls.data.start_point_co_2d, clear=True, size=cls.data.start_point_size)

            # Skipped Faces

            vis.clear('Skipped faces2D', 0)
            p_size = cls.data.start_point_size * 2
            for f in cls.data.skipped_faces:
                vis.add_cross(
                    'Skipped faces2D', 0, color=(1, 0, 0),
                    position=centroid([lp[uv_layer].uv for lp in f.loops]),
                    clear=False, size=p_size)

            # Master, Ort
            vis.clear('Master2D', 0)
            vis.clear('Ort2D', 0)
            vis.clear('len', 0)
            for loop in cls.data.master_edges_2d:
                main_diagonal = loop.link_loop_next.link_loop_next[uv_layer].uv - loop[uv_layer].uv
                p_offset = main_diagonal.length * 0.05
                main_offset = main_diagonal.normalized() * p_offset  # Qviz.data.loops_offset
                second_offset = (loop.link_loop_next.link_loop_next.link_loop_next[uv_layer].uv - loop.link_loop_next[uv_layer].uv).normalized() * p_offset  # Qviz.data.loops_offset
                vis.add_vector('Master2D', 0, ([loop[uv_layer].uv + main_offset, loop.link_loop_next[uv_layer].uv + second_offset], ), color=(0.4, 0, 0), clear=False, show_in_front=False, arrow_size=0)
                vis.add_vector('Ort2D', 0, ([loop.link_loop_next[uv_layer].uv + second_offset, loop.link_loop_next.link_loop_next[uv_layer].uv + main_offset * -1], ), color=(0, 0.5, 0), clear=False, show_in_front=False, arrow_size=0)

            # XXX: Only for debug purposes !!!
            # for loop in cls.data.master_edges_2d:
            #     edge_pos = loop[uv_layer].uv + ((loop.link_loop_next[uv_layer].uv - loop[uv_layer].uv) * 0.5)
            #     p_text = str(ZenQuadrify.avg_edges_len[loop.edge.index])
            #     vis.add_text('len', 0, p_text, letters_size=cls.data.start_point_size * 0.6, position=(edge_pos[0], edge_pos[1], 0), clear=False)
            # for loop in cls.data.ort_edges_2d:
            #     edge_pos = loop[uv_layer].uv + ((loop.link_loop_next[uv_layer].uv - loop[uv_layer].uv) * 0.5)
            #     p_text = str(ZenQuadrify.avg_edges_len[loop.edge.index])
            #     vis.add_text('len', 0, p_text, letters_size=cls.data.start_point_size * 0.6, position=(edge_pos[0], edge_pos[1], 0), clear=False)

            # vis.clear('Distr Indexes', 0)
            # for index, f in enumerate(cls.data.distribution_indexes):
            #     p_position = centroid([lp[uv_layer].uv for lp in f.loops])
            #     vis.add_text('Distr Indexes', 0, str(index), letters_size=cls.data.start_point_size, position=(p_position[0], p_position[1], 0), clear=False)
        else:
            print("Annotation Visualizer: Works only in 'VIEW_3D' or 'IMAGE_EDITOR'")


class FaceFactory:

    init_pivot: Vector = None
    init_angle: float = None

    @classmethod
    def find_nearest_axis(cls, vector: Vector) -> list[Vector, float]:
        """
        Finds the closest primary axis (x or y) to the given vector and returns the
        axis and the angle between them.

        Parameters:
        vector : Vector
            The input vector to analyze, which will be normalized.

        Returns:
        list(Vector, float)
            A list containing:
            - The nearest axis as a Vector.
            - The angle in radians between the vector and the nearest axis.
        """

        if vector[0] < 0:
            x_axis = Vector((-1, 0))
        else:
            x_axis = Vector((1, 0))

        if vector[1] < 0:
            y_axis = Vector((0, -1))
        else:
            y_axis = Vector((0, 1))

        angle_x = x_axis.angle_signed(vector)
        angle_y = y_axis.angle_signed(vector)

        if abs(angle_x) < abs(angle_y):
            return x_axis, angle_x
        else:
            return y_axis, angle_y

    @classmethod
    def calc_len_average_edges(cls, uv_layer, p_loop):
        edge_uv_length: float = 0.0
        edge_mesh_length: float = 0.0
        count: int = 0
        p_edges_indices = []
        for loop in (p_loop, p_loop.link_loop_next.link_loop_next):
            for e in BlFollowUtils.walk_edgeloop(loop):
                p_edges_indices.append(e.index)
                count += 1
                edge_mesh_length += e.calc_length()
                uv_edge = e.link_loops[0][uv_layer].uv, e.link_loops[0].link_loop_next[uv_layer].uv
                edge_uv_length += (uv_edge[1] - uv_edge[0]).length
                if Qviz.is_show_ops_annotations:
                    if Qviz.area_type == 'VIEW_3D':
                        Qviz.data.average_edges_3d.append((e.verts[0].co, e.verts[1].co))
                    elif Qviz.area_type == 'IMAGE_EDITOR':
                        Qviz.data.average_edges_2d.append(uv_edge)
        if count == 0:
            return False, False
        return edge_uv_length / count, edge_mesh_length / count

    @classmethod
    def calc_mesh_len_average_edges(cls, bm, island):

        edge_lengths = [None] * len(bm.edges)

        for face in island:
            for p_loop in (face.loops[0], face.loops[1]):
                if edge_lengths[p_loop.edge.index] is not None:
                    continue
                count: int = 0
                edge_mesh_length: float = 0.0
                e_indexes: list = []
                for loop in (p_loop, p_loop.link_loop_next.link_loop_next):
                    for e in BlFollowUtils.walk_edgeloop(loop):
                        count += 1
                        edge_mesh_length += e.calc_length()
                        e_indexes.append(e.index)

                for i in e_indexes:
                    edge_lengths[i] = edge_mesh_length / count

        return edge_lengths

    @classmethod
    def get_initial_face_edges_lengths_auto_mode(
            cls,
            p_face_quad: bmesh.types.BMFace,
            uv_layer: bmesh.types.BMLayerItem,
            fault_value: float = 0.05,
            is_average_shape: str = 'AVERAGE',
            min_limit_value: float = 0.002
    ) -> tuple[tuple[bmesh.types.BMLoop, bmesh.types.BMLoop, bmesh.types.BMLoop, bmesh.types.BMLoop], float, float]:
        """
        Return loops of the UV face as tuple and UV edge length of the quad
        :p_face: bmesh.types.BMFace
        :uv_layer: bmesh.types.BMLayerItem
        :fault_value: float = 0.05
        :return: tuple[tuple[loop, loop, loop, loop], float (uv edge 01 length), float(uv edge 02 length)]
        :min_limit_value: float = 0.0002 Default calculation: 1 / 256 = 0.003 Less than 1 pixel in the bitmap resolution 256
        """

        if len(p_face_quad.verts) != 4:
            return False

        init_loop = p_face_quad.loops[0]
        second_loop = init_loop.link_loop_next

        p_edge_01_uv_length = (init_loop.link_loop_next[uv_layer].uv - init_loop[uv_layer].uv).length
        p_edge_02_uv_length = (second_loop.link_loop_next[uv_layer].uv - second_loop[uv_layer].uv).length

        if p_edge_01_uv_length <= p_edge_02_uv_length:
            init_loop = init_loop.link_loop_next

        edge_01: bmesh.types.BMEdge = init_loop.edge
        edge_02: bmesh.types.BMEdge = init_loop.link_loop_next.edge

        edge_01_pair: bmesh.types.BMEdge = init_loop.link_loop_next.link_loop_next.edge
        edge_02_pair: bmesh.types.BMEdge = init_loop.link_loop_prev.edge

        if is_average_shape:
            edge_01_uv_length, edge_01_mesh_length = cls.calc_len_average_edges(uv_layer, init_loop)
            edge_02_uv_length, edge_02_mesh_length = cls.calc_len_average_edges(uv_layer, init_loop.link_loop_next)
            if edge_01_uv_length is False:
                Log.debug('Quadrify', 'edge_01_uv_length is False. Use fault value')
                edge_01_uv_length = fault_value

        else:
            edge_01_uv_length = (init_loop.link_loop_next[uv_layer].uv - init_loop[uv_layer].uv).length

            edge_01_pair_uv_length = (
                init_loop.link_loop_next.link_loop_next.link_loop_next[uv_layer].uv -
                init_loop.link_loop_next.link_loop_next[uv_layer].uv).length

            edge_01_uv_length = (edge_01_uv_length + edge_01_pair_uv_length) * 0.5
            edge_01_mesh_length = edge_01.calc_length() + edge_01_pair.calc_length()
            edge_02_mesh_length = edge_02.calc_length() + edge_02_pair.calc_length()

        if edge_01_uv_length < min_limit_value:
            Log.debug('Quadrify', f'edge_01_uv_length is less than min_limit_value. Use min_limit_value = {min_limit_value} instead')
            edge_01_uv_length = min_limit_value

        factor = edge_01_mesh_length / edge_01_uv_length

        edge_02_uv_length = edge_02_mesh_length / factor

        return [init_loop, init_loop.link_loop_next, init_loop.link_loop_next.link_loop_next, init_loop.link_loop_prev], edge_01_uv_length, edge_02_uv_length

    @classmethod
    def align_init_face(
        cls,
        context: bpy.types.Context,
        face: bmesh.types.BMFace,
        uv_layer: bmesh.types.BMLayerItem,
        shape: str = 'PER_FACE',
        is_average_shape: bool = False,
        is_correct_aspect: bool = False
    ):

        from ZenUV.ops.transform_sys.transform_utils.transform_uvs import TransformUVS

        def adjust_edges(edge1_length: float, edge2_length: float, new_value: float):
            if edge1_length < edge2_length:
                ratio = new_value / edge1_length
                edge1_length = new_value
                edge2_length *= ratio
            else:
                ratio = new_value / edge2_length
                edge2_length = new_value
                edge1_length *= ratio

            return edge1_length, edge2_length

        p_active_image = ActiveUvImage(context)
        if p_active_image.image is not None:
            p_limit_value = 1 / p_active_image.len_x
        else:
            p_limit_value = 0.002

        p_face_loops, edge1_length, edge2_length = cls.get_initial_face_edges_lengths_auto_mode(face, uv_layer, is_average_shape=is_average_shape, min_limit_value=p_limit_value)

        if shape == 'EVEN':
            edge1_length = edge2_length = (edge1_length + edge2_length) * 0.5

        cls.init_pivot = centroid([v[uv_layer].uv for v in p_face_loops])

        precision = 7
        is_zero_area_uv_face = False

        p_face_coos = [v[uv_layer].uv - p_face_loops[0][uv_layer].uv for v in p_face_loops]

        c01 = p_face_coos[0].copy()
        c_02_e = p_face_coos[1] - c01

        if c_02_e.length < p_limit_value:
            is_zero_area_uv_face = True
            c02 = c01 + Vector((1.0, 0.0)) * edge1_length
            if edge1_length < p_limit_value or edge2_length < p_limit_value:
                edge1_length, edge2_length = adjust_edges(edge1_length, edge2_length, p_limit_value)
        else:
            c02 = c01 + c_02_e.normalized() * edge1_length

        nearest_axis, cls.init_angle = cls.find_nearest_axis(c02 - c01)

        c02 = c01 + nearest_axis * edge1_length

        ort = (c02 - c01).orthogonal().normalized() * edge2_length

        c03 = c02 + ort
        c04 = c01 + ort

        face_uv_corners = c01, c02, c03, c04

        p_pivot = centroid(face_uv_corners)
        p_offset_vec = cls.init_pivot - p_pivot

        face_uv_corners = [v + p_offset_vec for v in face_uv_corners]

        if is_correct_aspect:
            p_hats_vec = p_active_image._get_hats()
            pivot_offset = c01 - p_pivot if is_zero_area_uv_face else Vector((0.0, 0.0))
            face_uv_corners = [v + pivot_offset for v in TransformUVS.scale_uvs(face_uv_corners, p_hats_vec, p_pivot)]

        for loop, co in zip(p_face_loops, face_uv_corners):
            master_co = loop[uv_layer].uv.to_tuple(precision)
            for lp in loop.vert.link_loops:
                if lp[uv_layer].uv.to_tuple(precision) == master_co:
                    lp[uv_layer].uv = co


class BlFollowUtils:

    @classmethod
    def walk_edgeloop(cls, loop):
        e_first = loop.edge
        e = None
        while True:
            e = loop.edge
            yield e

            # Don't step past non-manifold edges.
            if e.is_manifold:
                if e.seam:
                    break
                # Walk around the quad and then onto the next face.
                loop = loop.link_loop_radial_next
                if len(loop.face.verts) == 4:
                    loop = loop.link_loop_next.link_loop_next
                    if loop.edge is e_first:
                        break
                else:
                    break
            else:
                break


class Bl_FollowActiveQuad:
    """
        Native Blender algorithm Follow Active Quad
    """

    def calc_using_blend_follow_active(
            context, bm,
            uv_act, f_act, faces,
            EXTEND_MODE: str = 'LENGTH_AVERAGE',
            b_is_show_distribution: bool = False,
            progress: ProgressBar = None):

        def walk_face():
            from collections import deque

            for f in bm.faces:
                f.tag = f not in faces

            faces_deque = deque()
            faces_deque.append(f_act)
            f_act.tag = True  # Queued.

            while faces_deque:  # Breadth first search.
                f = faces_deque.popleft()
                for l in f.loops:  # noqa: E741
                    l_edge = l.edge
                    if l_edge.seam:
                        continue  # Don't walk across seams.
                    if not l_edge.is_manifold:
                        continue  # Don't walk across non-manifold.
                    l_other = l.link_loop_radial_next  # Manifold implies uniqueness.
                    f_other = l_other.face
                    if f_other.tag:
                        continue  # Either queued, visited, not selected, or not quad.
                    yield (f, l, f_other)
                    faces_deque.append(f_other)
                    f_other.tag = True  # Queued.

        def walk_edgeloop(l):  # noqa: E741
            """
            Could make this a generic function
            """
            e_first = l.edge
            e = None
            while True:
                e = l.edge
                yield e

                # Don't step past non-manifold edges.
                if e.is_manifold:
                    # Walk around the quad and then onto the next face.
                    l = l.link_loop_radial_next  # noqa: E741
                    if len(l.face.verts) == 4:
                        l = l.link_loop_next.link_loop_next  # noqa: E741
                        if l.edge is e_first:
                            break
                    else:
                        break
                else:
                    break

        uv_updates = []

        def record_and_assign_uv(dest, source):
            from mathutils import Vector
            if dest[uv_act].uv == source:
                return  # Already placed correctly, probably a nearby quad.
            dest_uv_copy = Vector(dest[uv_act].uv)  # Make a copy to prevent aliasing.
            uv_updates.append([dest.vert, dest_uv_copy, source])  # Record changes.
            dest[uv_act].uv = source  # Assign updated UV.

        def extrapolate_uv(fac, l_a_outer, l_a_inner, l_b_outer, l_b_inner):
            l_a_inner_uv = l_a_inner[uv_act].uv
            l_a_outer_uv = l_a_outer[uv_act].uv
            record_and_assign_uv(l_b_inner, l_a_inner_uv)
            record_and_assign_uv(l_b_outer, l_a_inner_uv * (1 + fac) - l_a_outer_uv * fac)

        def apply_uv(_f_prev, l_prev, _f_next):
            l_a = [None, None, None, None]
            l_b = [None, None, None, None]

            l_a[0] = l_prev
            l_a[1] = l_a[0].link_loop_next
            l_a[2] = l_a[1].link_loop_next
            l_a[3] = l_a[2].link_loop_next

            #  l_b
            #  +-----------+
            #  |(3)        |(2)
            #  |           |
            #  |l_next(0)  |(1)
            #  +-----------+
            #        ^
            #  l_a   |
            #  +-----------+
            #  |l_prev(0)  |(1)
            #  |    (f)    |
            #  |(3)        |(2)
            #  +-----------+
            #  Copy from this face to the one above.

            # Get the other loops.
            l_next = l_prev.link_loop_radial_next

            if l_next.vert != l_prev.vert:
                l_b[1] = l_next
                l_b[0] = l_b[1].link_loop_next
                l_b[3] = l_b[0].link_loop_next
                l_b[2] = l_b[3].link_loop_next
            else:
                l_b[0] = l_next
                l_b[1] = l_b[0].link_loop_next
                l_b[2] = l_b[1].link_loop_next
                l_b[3] = l_b[2].link_loop_next

            if EXTEND_MODE == 'LENGTH_AVERAGE':
                d1 = edge_lengths[l_a[1].edge.index][0]
                d2 = edge_lengths[l_b[2].edge.index][0]
                try:
                    fac = d2 / d1
                except ZeroDivisionError:
                    fac = 1.0
            elif EXTEND_MODE == 'LENGTH':
                a0, b0, c0 = l_a[3].vert.co, l_a[0].vert.co, l_b[3].vert.co
                a1, b1, c1 = l_a[2].vert.co, l_a[1].vert.co, l_b[2].vert.co

                d1 = (a0 - b0).length + (a1 - b1).length
                d2 = (b0 - c0).length + (b1 - c1).length
                try:
                    fac = d2 / d1
                except ZeroDivisionError:
                    fac = 1.0
            else:
                fac = 1.0

            extrapolate_uv(fac, l_a[3], l_a[0], l_b[3], l_b[0])
            extrapolate_uv(fac, l_a[2], l_a[1], l_b[2], l_b[1])

        # -------------------------------------------
        # Calculate average length per loop if needed.

        if EXTEND_MODE == 'LENGTH_AVERAGE':
            bm.edges.index_update()
            edge_lengths = [None] * len(bm.edges)
            if progress:
                progress.set_text(prefix='Blen Quadrifying: collect input')
            for f in faces:
                ProgressBar.check_update_spinner_progress(progress)
                # We know it's a quad.
                l_quad = f.loops[:]
                l_pair_a = (l_quad[0], l_quad[2])
                l_pair_b = (l_quad[1], l_quad[3])

                for l_pair in (l_pair_a, l_pair_b):
                    if edge_lengths[l_pair[0].edge.index] is None:

                        edge_length_store = [-1.0]
                        edge_length_accum = 0.0
                        edge_length_total = 0

                        for l in l_pair:  # noqa: E741
                            if edge_lengths[l.edge.index] is None:
                                for e in walk_edgeloop(l):
                                    if edge_lengths[e.index] is None:
                                        edge_lengths[e.index] = edge_length_store
                                        edge_length_accum += e.calc_length()
                                        edge_length_total += 1

                        edge_length_store[0] = edge_length_accum / edge_length_total

        if progress:
            progress.set_text(prefix='Blen Quadrifying: applying UV')
        for f_triple in walk_face():
            ProgressBar.check_update_spinner_progress(progress)
            apply_uv(*f_triple)

        if progress:
            progress.set_text(prefix='Blen Quadrifying: fix boundaries')
        # Propagate UV changes across boundary of selection.
        for (v, original_uv, source) in uv_updates:
            ProgressBar.check_update_spinner_progress(progress)
            # Visit all loops associated with our vertex.
            for loop in v.link_loops:
                # If the loop's UV matches the original, assign the new UV.
                if loop[uv_act].uv == original_uv:
                    loop[uv_act].uv = source


class ZenQuadrify:

    pivot: Vector = None
    avg_edges_len: list = []

    @classmethod
    def proceed(
            cls,
            context: bpy.types.Context,
            bm: bmesh.types.BMesh,
            island: list,
            uv_layer: bmesh.types.BMLayerItem,
            influence: str = 'ISLAND',
            face_shape: str = 'PER_FACE',
            average_shape: bool = False,
            is_correct_aspect: bool = False,
            b_is_split: bool = False,
            alg_name: str = 'ZEN_UV',
            progress: ProgressBar = None):

        start_time = time.time()


        if uv_layer is None:
            return False
        if not len(island):
            return False

        Qviz.data = ZenQuadrifyVisualizerData()

        Qviz.area_type = context.area.type
        Qviz.is_show_ops_annotations = context.scene.zen_uv.is_show_ops_annotations

        faces = []
        for f in island:
            if len(f.verts) == 4:
                faces.append(f)
            else:
                Qviz.data.skipped_faces.append(f)

        # for f in faces:
        #     f.tag = False

        if average_shape:
            cls.avg_edges_len = FaceFactory.calc_mesh_len_average_edges(bm, faces)

        face_init: bmesh.types.BMFace = None

        face_init = bm.faces.active

        if face_init is None or face_init not in faces:
            p_center = BoundingBox2d(islands=[faces, ], uv_layer=uv_layer).center
            face_init = min([f for f in faces], key=lambda f: (centroid([lp[uv_layer].uv for lp in f.loops]) - p_center).magnitude)

        if alg_name == 'BLEN':
            Qviz.is_show_ops_annotations = False

        FaceFactory.align_init_face(
            context,
            face_init,
            uv_layer,
            shape=face_shape,
            is_average_shape=average_shape,
            is_correct_aspect=False)

        p_starting_point = cls.pivot = centroid([lp[uv_layer].uv for lp in face_init.loops])

        if Qviz.is_show_ops_annotations:
            if Qviz.area_type == 'VIEW_3D':
                Qviz.data.start_point_size = (face_init.calc_center_median() - face_init.verts[0].co).length * 0.1
                Qviz.data.loops_offset = Qviz.data.start_point_size * 0.5
                Qviz.data.arrows_offset = Qviz.data.start_point_size
                q = face_init.normal.to_track_quat('Z', 'X')
                Qviz.data.start_point_rotation = ZenLocRotScale(None, q, None)
            else:
                Qviz.data.start_point_size = (p_starting_point - face_init.loops[0][uv_layer].uv).length * 0.25

            Qviz.data.start_point_co_2d = p_starting_point
            Qviz.data.start_point_co_3d = face_init.calc_center_median()

        alg_report_name = 'ZEN'

        with Timer() as t:
            if alg_name == 'ZEN_UV':
                ZenFollowQuad.follow(
                    context, uv_layer,
                    faces, face_init,
                    shape=face_shape,
                    b_is_split=b_is_split,
                    b_is_show_distribution=Qviz.is_show_ops_annotations,
                    average_shape=average_shape,
                    progress=progress,
                    bm=bm)
                alg_report_name = 'Zen UV'
            elif alg_name == 'BLEN':
                Bl_FollowActiveQuad.calc_using_blend_follow_active(
                    context, bm, uv_layer,
                    face_init, faces,
                    EXTEND_MODE=face_shape,
                    b_is_show_distribution=Qviz.is_show_ops_annotations,
                    progress=progress)
                alg_report_name = 'Blender'
            else:
                raise RuntimeError('Quadrify algorithm name incorrect')

        Log.debug('Quadrify', f' time {alg_report_name}: {t.delta()}')

        if is_correct_aspect:
            from ZenUV.ops.transform_sys.transform_utils.transform_uvs import TransformUVS

            p_active_image = ActiveUvImage(context)
            p_hats_vec = p_active_image._get_hats()
            if influence == 'ISLAND':
                loops = sum([f.loops[:] for f in island], [])
            elif influence == 'SELECTION':
                loops = [lp for f in island for v in f.verts for lp in v.link_loops if lp[uv_layer].select]
            else:
                raise RuntimeError("influence not in {'ISLAND', 'SELECTION'}")

            TransformLoops.scale_loops(
                loops,
                uv_layer,
                Vector((p_hats_vec[1], p_hats_vec[0])),
                pivot=p_starting_point)

            p_dist_2d = []
            for pair in Qviz.data.distribution_2d:
                p_dist_2d.append(Vector(v) for v in TransformUVS.scale_uvs(pair, Vector((p_hats_vec[1], p_hats_vec[0])), pivot=p_starting_point))
            Qviz.data.distribution_2d = p_dist_2d

        if Qviz.is_show_ops_annotations:
            Qviz.show(context, uv_layer)

        if QuadrifyMarkState.is_mark_allowed:
            mark_seam = QuadrifyMarkState.mark_seam
            mark_sharp = QuadrifyMarkState.mark_sharp

            for e in {e for f in island for e in f.edges}:
                if mark_seam:
                    e.seam = False
                if mark_sharp:
                    e.smooth = True

            edges = bm.edges
            for i in get_uv_bound_edges_indexes(island, uv_layer):
                e = edges[i]
                if mark_seam:
                    e.seam = True
                if mark_sharp:
                    e.smooth = False

        Log.debug('Quadrify', f"Total processing time: {time.time() - start_time:.5f} seconds\n")


class ZenFollowQuad:

    @classmethod
    def follow(
                cls,
                context: bpy.types.Context,
                uv_layer: bmesh.types.BMLayerItem,
                faces: list,
                face_init: bmesh.types.BMFace,
                shape: str = 'PER_FACE',
                b_is_split: bool = False,
                b_is_show_distribution: bool = False,
                average_shape: bool = True,
                # is_correct_aspect: bool = False
                progress: ProgressBar = None,
                bm: bmesh.types.BMesh = None
            ) -> bool:

        from ZenUV.utils.get_uv_islands import FacesFactory

        if progress:
            progress.set_text(prefix='Quadrifying: bound edges')

        p_get_bound_edges = get_bound_edges_idxs_from_facelist(faces, progress=progress)

        if progress:
            progress.set_text(prefix='Quadrifying: adjacent edges')

        p_adjacent_faces = FacesFactory.find_adjacent_faces_bfs(face_init, p_get_bound_edges, progress=progress)

        if progress:
            progress.set_text(prefix='Quadrifying: setting up positions')

        for loop in p_adjacent_faces:

            ProgressBar.check_update_spinner_progress(progress)

            master_loop = loop.link_loop_radial_next

            master_edge = loop.edge
            ort_edge = loop.link_loop_next.edge

            if b_is_show_distribution:
                if Qviz.area_type == 'VIEW_3D':
                    main_diagonal = (loop.link_loop_next.link_loop_next.vert.co - loop.vert.co).normalized() * Qviz.data.loops_offset
                    second_diagonal = (loop.link_loop_next.link_loop_next.link_loop_next.vert.co - loop.link_loop_next.vert.co).normalized() * Qviz.data.loops_offset
                    Qviz.data.master_edges.append([loop.vert.co + main_diagonal, loop.link_loop_next.vert.co + second_diagonal])
                    Qviz.data.ort_edges.append([loop.link_loop_next.vert.co + second_diagonal, loop.link_loop_next.link_loop_next.vert.co + main_diagonal * -1])
                elif Qviz.area_type == 'IMAGE_EDITOR':
                    Qviz.data.master_edges_2d.append(loop)
                    Qviz.data.ort_edges_2d.append(loop.link_loop_next)

            lp_01 = [loop, ]
            lp_02 = [loop.link_loop_next, ]
            lp_03 = [loop.link_loop_next.link_loop_next, ]
            lp_04 = [loop.link_loop_prev, ]

            v_ort: Vector = None
            master_vec: Vector = master_loop[uv_layer].uv - master_loop.link_loop_next[uv_layer].uv

            if shape == 'PER_FACE':
                # p_face_index = 86
                if not lp_02[0].edge.seam and lp_02[0].link_loop_radial_next.face.tag:
                    v_ort = (master_vec.orthogonal()).normalized() * \
                                (lp_02[0].link_loop_radial_next[uv_layer].uv - lp_02[0].link_loop_radial_next.link_loop_next[uv_layer].uv).length
                    # if loop.face.index == p_face_index:
                    #     print('Catch 1', loop.face.index)
                    #     print('From Where copy ', lp_02[0].link_loop_radial_next.face.index)

                elif not lp_04[0].edge.seam and lp_04[0].link_loop_radial_next.face.tag:
                    v_ort = master_vec.orthogonal().normalized() * \
                                (lp_04[0].link_loop_radial_next[uv_layer].uv - lp_04[0].link_loop_radial_next.link_loop_next[uv_layer].uv).length
                    # if loop.face.index == p_face_index:
                    #     print('Catch 2', loop.face.index)
                else:
                    # if loop.face.index == p_face_index:
                    #     print('Catch 3', loop.face.index)
                    try:
                        if average_shape:
                            ort_stored_len = ZenQuadrify.avg_edges_len[ort_edge.index]
                            if ZenQuadrify.avg_edges_len[ort_edge.index] is None:
                                ort_stored_len = ort_edge.calc_length()
                            master_edge_len = ZenQuadrify.avg_edges_len[master_edge.index]
                            if master_edge_len is None:
                                master_edge_len = master_edge.calc_length()
                            factor = ort_stored_len / master_edge_len
                        else:
                            factor = ort_edge.calc_length() / master_edge.calc_length()

                    except Exception as e:
                        Log.debug('Quadrify', e)
                        factor = 1.0

                    v_ort = master_vec.orthogonal().normalized() * (master_vec.magnitude * factor)

            else:
                s_uv_len = (master_loop.link_loop_next[uv_layer].uv - master_loop.link_loop_next.link_loop_next[uv_layer].uv).magnitude
                v_ort = master_vec.orthogonal().normalized() * s_uv_len

            uvs = (
                master_loop.link_loop_next[uv_layer].uv,
                master_loop[uv_layer].uv,
                master_loop[uv_layer].uv + v_ort,
                master_loop.link_loop_next[uv_layer].uv + v_ort
            )

            if not b_is_split:
                lp_01.extend((p for p in lp_01[0].vert.link_loops if p[uv_layer].uv == lp_01[0][uv_layer].uv and not p.face.tag))
                lp_02.extend((p for p in lp_02[0].vert.link_loops if p[uv_layer].uv == lp_02[0][uv_layer].uv and not p.face.tag))
                lp_03.extend((p for p in lp_03[0].vert.link_loops if p[uv_layer].uv == lp_03[0][uv_layer].uv and not p.face.tag))
                lp_04.extend((p for p in lp_04[0].vert.link_loops if p[uv_layer].uv == lp_04[0][uv_layer].uv and not p.face.tag))

            if b_is_show_distribution:

                if Qviz.area_type == 'VIEW_3D':
                    v_offset = master_loop.face.normal.normalized() * Qviz.data.arrows_offset
                    Qviz.data.distribution_3d.append((master_loop.face.calc_center_median() + v_offset, loop.face.calc_center_median() + v_offset))

                elif Qviz.area_type == 'IMAGE_EDITOR':
                    Qviz.data.distribution_2d.append((centroid([p[uv_layer].uv for p in master_loop.face.loops]), centroid(uvs)))

                    # Only for debug purposes !!!
                    # Qviz.data.distribution_indexes.append(loop.face)

            for group, uv in zip((lp_01, lp_02, lp_03, lp_04), uvs):
                for master_loop in group:
                    master_loop[uv_layer].uv = uv

        if bm is not None:
            p_get_uv_bound_edges_idxs = {i for i in get_uv_bound_edges_indexes(faces, uv_layer) if not bm.edges[i].is_boundary}
            p_verts = {v for i in p_get_uv_bound_edges_idxs for v in bm.edges[i].verts}
            cls.merge_uv_verts(context, p_verts, uv_layer, progress=progress)
        else:
            cls.merge_uv_verts(context, {v for f in faces for v in f.verts}, uv_layer, progress=progress)

    @classmethod
    def merge_uv_verts(
            cls,
            context: bpy.types.Context,
            bmesh_verts: list,
            uv_layer: bmesh.types.BMLayerItem,
            threshold: float = 0.001,
            b_is_not_sync: bool = False,
            use_pins: bool = False,
            use_seams: bool = False,
            progress: ProgressBar = None):

        from ZenUV.utils.generic import is_pure_edge_mode
        from collections import defaultdict
        from math import isclose

        if progress:
            progress.set_text(prefix='Merging UV vertices')

        distance_dict = dict()
        if b_is_not_sync:
            if is_pure_edge_mode(context):

                for v in bmesh_verts:
                    ProgressBar.check_update_spinner_progress(progress)

                    p_first_collector = set()
                    if use_seams:
                        selected_edges = {p for p in v.link_loops if not any(
                            lp.edge.seam for lp in (p, p.link_loop_next, p.link_loop_prev)) and any(
                                lp[uv_layer].select_edge and not lp.edge.seam for lp in (p, p.link_loop_next, p.link_loop_prev))}
                    else:
                        selected_edges = {p for p in v.link_loops if any(
                            lp[uv_layer].select_edge for lp in (p, p.link_loop_next, p.link_loop_prev))}
                    p_first_collector.update(selected_edges)

                    if not len(p_first_collector):
                        continue

                    scope = defaultdict(list)
                    for loop in p_first_collector:
                        ProgressBar.check_update_spinner_progress(progress)

                        loop_uv = loop[uv_layer].uv
                        for lp in v.link_loops:
                            uv_distance = (lp[uv_layer].uv - loop_uv).length
                            scope[uv_distance].append(lp)

                    if isclose(0.0, min(scope.keys())):
                        p_first_collector.update(scope[min(scope.keys())])

                    for lp1 in p_first_collector:
                        lp1_uv = lp1[uv_layer].uv
                        lp1_distances = []
                        for lp2 in p_first_collector:
                            if lp1 != lp2:
                                uv_distance = (lp1_uv - lp2[uv_layer].uv).magnitude
                                lp1_distances.append((lp2, uv_distance))
                        distance_dict[lp1] = lp1_distances

            else:
                for v in bmesh_verts:
                    ProgressBar.check_update_spinner_progress(progress)

                    p_first_collector = [p for p in v.link_loops if p[uv_layer].select]
                    for lp1 in p_first_collector:
                        lp1_distances = []
                        for lp2 in p_first_collector:
                            if lp1 != lp2:
                                distance = (lp1[uv_layer].uv - lp2[uv_layer].uv).magnitude
                                lp1_distances.append((lp2, distance))
                        distance_dict[lp1] = lp1_distances
        else:
            if use_seams:
                for v in bmesh_verts:
                    ProgressBar.check_update_spinner_progress(progress)

                    p_first_collector = set()
                    seam_loops = {p for p in v.link_loops if not any(
                        lp.edge.seam for lp in (p, p.link_loop_next, p.link_loop_prev))}
                    p_first_collector.update(seam_loops)

                    if not len(p_first_collector):
                        continue

                    scope = defaultdict(list)
                    for loop in p_first_collector:
                        ProgressBar.check_update_spinner_progress(progress)

                        loop_uv = loop[uv_layer].uv
                        for lp in v.link_loops:
                            uv_distance = (lp[uv_layer].uv - loop_uv).length
                            scope[uv_distance].append(lp)

                    if isclose(0.0, min(scope.keys())):
                        p_first_collector.update(scope[min(scope.keys())])

                    for lp1 in p_first_collector:
                        lp1_uv = lp1[uv_layer].uv
                        lp1_distances = []
                        for lp2 in p_first_collector:
                            if lp1 != lp2:
                                uv_distance = (lp1_uv - lp2[uv_layer].uv).magnitude
                                lp1_distances.append((lp2, uv_distance))
                        distance_dict[lp1] = lp1_distances
            else:
                for v in bmesh_verts:
                    ProgressBar.check_update_spinner_progress(progress)

                    for lp1 in v.link_loops:
                        if use_seams and lp1.edge.seam:
                            continue
                        lp1_distances = []
                        for lp2 in v.link_loops:
                            if use_seams and lp1.edge.seam:
                                continue
                            if lp1 != lp2:
                                distance = (lp1[uv_layer].uv - lp2[uv_layer].uv).magnitude
                                lp1_distances.append((lp2, distance))
                        distance_dict[lp1] = lp1_distances

        if use_pins:
            for lp1, lp_matches in {lp1: [lp2 for lp2, distance in distances if distance < threshold] for lp1, distances in distance_dict.items()}.items():
                if not lp_matches:
                    continue

                ProgressBar.check_update_spinner_progress(progress)

                uvs = None
                p_merged_loops = [lp1, ]
                p_merged_loops.extend(lp_matches)
                for lp in p_merged_loops:
                    if lp[uv_layer].pin_uv:
                        uvs = lp[uv_layer].uv
                        break
                if uvs is None:
                    uvs = centroid([lp[uv_layer].uv for lp in p_merged_loops])
                for lp in p_merged_loops:
                    lp[uv_layer].uv = uvs
        else:
            for lp1, lp_matches in {lp1: [lp2 for lp2, distance in distances if distance < threshold] for lp1, distances in distance_dict.items()}.items():
                if not lp_matches:
                    continue

                ProgressBar.check_update_spinner_progress(progress)

                p_merged_loops = [lp1, ]
                p_merged_loops.extend(lp_matches)
                uvs = centroid([lp[uv_layer].uv for lp in p_merged_loops])
                for lp in p_merged_loops:
                    lp[uv_layer].uv = uvs


class ZuvQuadrifyBase:

    algorithm: bpy.props.EnumProperty(
        name="Algorithm",
        description="Calculation algorithm",
        items=(
            ('ZEN_UV', "Zen UV", "Zen UV calculation algorithm"),
            ('BLEN', "Blender", "Native Blender follow active quad algorithm")),
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "algorithm", "ZEN_UV")
    )

    influence: bpy.props.EnumProperty(
        name='Influence',
        description='Transform Influence. Affect Islands or Selection',
        items=[
            ("ISLAND", "Island", ""),
            ("SELECTION", "Selection", "")
        ],
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "influence", "ISLAND")
    )

    edge_length_mode: bpy.props.EnumProperty(
        name="Edge Length Mode",
        description="Method to space UV edge loops for native Blender algorithm",
        items=(
                ('LENGTH_AVERAGE', "Length Average", "Average space UVs edge length of each loop", 0),
                ('LENGTH', "Length", "Average space UVs edge length of each loop", 1),
                ('EVEN', "Even", "Space all UVs evenly", 2)),
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "edge_length_mode", 0),
    )

    shape: bpy.props.EnumProperty(
        name="Shape",
        description="The face shape for Zen UV algorithm",
        items=(
                ("PER_FACE", "Per Face", "The shape is taken from the every original face shape", 0),
                ("FACE", "Face", "The shape is taken from single (active) face and copied to the other faces", 1),
                ("EVEN", "Even", "Square shape", 2)),
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "shape", 0),
    )

    average_shape: bpy.props.BoolProperty(
        name='Average',
        description='Averages the shape depending on the shape of the faces in the faceloop',
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "average_shape", True))

    use_selected_edges: bpy.props.BoolProperty(
        name='Use selected Edges',
        description='''Selected Edges will be used
as Seams during Quadrify Islands operation.
Works only in edge selection mode''',
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "use_selected_edges", False))

    quadrify_edge_detection_limit: bpy.props.IntProperty(
        name='Limit',
        description='The maximum number of edges used to create the seam. If the number of selected edges is greater than this number, the seams will not be created',
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "quadrify_edge_detection_limit", 4),
        min=0,
        max=100)

    skip_non_quads: bpy.props.BoolProperty(
        name='Skip Non Quads',
        description='Skip islands that contain faces other than quads',
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "skip_non_quads", False))

    mark_borders: bpy.props.BoolProperty(
        name='Mark Borders',
        description='Mark Island boundaries after Quadrify Islands operation',
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "mark_borders", True))

    mark_seams: bpy.props.BoolProperty(
        name="Mark Seams",
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "mark_seams", True),
        description="Mark seam in case Mark Borders is on")
    mark_sharp: bpy.props.BoolProperty(
        name="Mark Sharp",
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "mark_sharp", False),
        description="Mark sharp in case Mark Borders is on")

    # quadrifyOrientToWorld: bpy.props.BoolProperty(
    #     name=ZuvLabels.PREF_ORIENT_TO_WORLD_QUADRIFY_LABEL,
    #     description=ZuvLabels.PREF_ORIENT_TO_WORLD_QUADRIFY_DESC,
    #     default=False,
    #     options={'HIDDEN'}
    #     )

    orient: bpy.props.EnumProperty(
        name="Orient to",
        description="Orient Quadrified Islands",
        items=[
            ("SKIP", "Skip", "Do not change the original orientation", 0),
            ("ALIGN_TO_AXIS", "Align to Axis", "Align to the nearest axis", 1),
            ("VERTICAL", "Vertical", "Set orientation vertical", 2),
            ("HORIZONTAL", "Horizontal", "Set orientation horizontal", 3)],
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "orient", "ALIGN_TO_AXIS"),
    )

    post_td_mode: bpy.props.EnumProperty(
        name="Texel Density",
        description="Set texel density. Not available if Pack Quadrified is On",
        items=[
            ("AVERAGED", "Averaged", "Set averaged Texel Density"),
            ("GLOBAL_PRESET", "Global Preset", "Set value described in the Texel Density panel as Global TD Preset"),
            ("SKIP", "Skip", "Do not make any texel density corrections")],
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "post_td_mode", "SKIP"),
    )

    use_pack_islands: bpy.props.BoolProperty(
        name='Pack Quadrified',
        description='Pack Islands after Quadrify Islands operation',
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "use_pack_islands", False))

    auto_pin: bpy.props.EnumProperty(
        name="Pin",
        description="Auto Pin",
        items=[
            ("QUADS", "Quads", "Perform pinning only faces that have been quadrified"),
            ("ISLAND", "Island", "Pin the entire island or a selection, depending on the Influence mode"),
            ("SKIP", "Skip", "Do not perform Pinning")
        ],
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "auto_pin", "SKIP")
    )

    tag_finished: bpy.props.BoolProperty(
        name='Tag as Finished',
        description='Tag Quadrified island as finished',
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "tag_finished", False))
    is_correct_aspect: bpy.props.BoolProperty(
        name='Correct Aspect',
        description='Map UVs taking image aspect ratio into account',
        default=ZenPolls.get_operator_defaults(
            "UV_OT_zenuv_quadrify", "is_correct_aspect", False))

    def draw(self, context):
        self.draw_properties(self, self.layout, context)

    @classmethod
    def draw_properties(cls, instance, layout: bpy.types.UILayout, context: bpy.types.Context):
        from ZenUV.utils.blender_zen_utils import ZenPolls

        addon_prefs = get_prefs()

        self: ZuvQuadrifyBase = instance

        col = layout.column(align=False)
        col.use_property_split = True

        col.prop(self, 'influence')

        row = col.row(align=True)
        row = row.row(align=True)

        if self.algorithm == 'ZEN_UV':
            row.prop(self, "shape")
            if self.shape != 'EVEN':
                row = row.row(align=True)
                row.prop(self, "average_shape", icon_only=True, icon='EVENT_A')
        else:
            row.prop(self, "edge_length_mode")

        col.prop(self, "orient")
        row = col.row()
        row.enabled = self.use_pack_islands is False
        row.prop(self, "post_td_mode")

        # Post Process
        layout.label(text="Post Process:")
        p_box = layout.box()
        p_box.prop(self, "auto_pin")
        pack_row = p_box.row()
        pack_row.enabled = not ZenPolls.version_equal_3_6_0
        pack_row.prop(self, "use_pack_islands")
        if ZenPolls.version_equal_3_6_0:
            pack_row.label(text='Disabled in 3.6.0')
        p_box.prop(self, "tag_finished")

        layout.label(text='Advanced:')

        # Mark Section
        row = layout.row(align=False)
        row.prop(self, 'algorithm')
        row = layout.row()
        row.prop(self, "use_selected_edges")
        row = row.row()
        row.enabled = self.use_selected_edges
        row.prop(self, 'quadrify_edge_detection_limit')

        mark_box = layout.box()
        ZuvQuadrifyBase.draw_mark_section(self, mark_box, addon_prefs)

        box = layout.box()
        box.prop(self, 'skip_non_quads')
        box.prop(self, 'is_correct_aspect')

    def draw_mark_section(self, layout: bpy.types.UILayout, addon_prefs):
        s_mark_settings = 'Mark Settings'
        s_mark_settings += ' (Global Mode)' if addon_prefs.useGlobalMarkSettings else ' (Local Mode)'
        layout.label(text=s_mark_settings)

        row = layout.row(align=True)
        row.prop(self, "mark_borders")
        sub_row = row.row(align=True)
        sub_row.enabled = self.mark_borders
        if not addon_prefs.useGlobalMarkSettings:
            sub_row.prop(self, "mark_seams")
            sub_row.prop(self, "mark_sharp")
        else:
            sub_row.enabled = False
            sub_row.prop(addon_prefs, "markSeamEdges")
            sub_row.prop(addon_prefs, "markSharpEdges")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def detect_edge_selection_mode(self, context):
        if context.space_data.type == 'IMAGE_EDITOR':
            if context.scene.tool_settings.use_uv_select_sync:
                return context.tool_settings.mesh_select_mode[1]
            else:
                return context.scene.tool_settings.uv_select_mode == "EDGE"

        if context.space_data.type == 'VIEW_3D':
            return context.tool_settings.mesh_select_mode[1]

    def is_pack_allowed(self, context):
        from ZenUV.utils.blender_zen_utils import ZenPolls
        if ZenPolls.version_equal_3_6_0:
            return False
        return self.use_pack_islands

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()
        from collections import Counter
        from ZenUV.ops.texel_density.td_utils import TexelDensityProcessor
        from ZenUV.utils.selection_utils import SelectionProcessor, UniSelectedObject
        from ZenUV.utils.get_uv_islands import LoopsFactory, FacesFactory

        SelectionProcessor.reset_state()

        is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

        Storage = SelectionProcessor.collect_selected_objects(
            context,
            is_not_sync,
            b_in_indices=True,
            b_is_skip_objs_without_selection=True,
            b_skip_uv_layer_fail=False)

        if SelectionProcessor.result is False:
            self.report({'WARNING'}, SelectionProcessor.message)
            return {'CANCELLED'}

        addon_prefs = get_prefs()

        QuadrifyMarkState.init(self.mark_borders, self.mark_seams, self.mark_sharp)

        is_edge_selection_mode = self.detect_edge_selection_mode(context)

        s_obj: UniSelectedObject = None

        td_context: TdContext = None

        if self.influence == 'ISLAND':
            for s_obj in SelectionProcessor.yield_selected_objects(Storage):
                s_obj.attribute_storage['islands'] = [
                    [f.index for f in island]
                    for island in island_util.get_island(context, s_obj.bm, s_obj.uv_layer)]

            total_processing_faces = sum([len(k) for o in Storage for k in o.attribute_storage['islands']])
        else:
            total_processing_faces = sum([len(k) for o in Storage for k in o.selected_items.get_elements()])

        progress = ProgressBar(context, 10, text_only=True) if total_processing_faces > 1000 else None

        try:

            if self.post_td_mode == 'AVERAGED':
                td_context = TdContext(context)

                # Get Init TD
                init_td = 0.0
                for s_obj in SelectionProcessor.yield_selected_objects(Storage):
                    bm = s_obj.bm
                    uv_layer = s_obj.uv_layer
                    if uv_layer is None:
                        continue
                    init_td += TexelDensityFactory.calc_averaged_td(s_obj.obj, uv_layer, [bm.faces, ], TdContext(context))[0]
                td_context.td = init_td / len(Storage)
            elif self.post_td_mode == 'GLOBAL_PRESET':
                td_context = TdContext(context)
                td_context.td = context.scene.zen_uv.td_props.td_global_preset

            # Determining the total number of selected edges.
            if is_edge_selection_mode:
                if is_not_sync:
                    if ZenPolls.version_since_3_2_0:
                        p_total_sel_edges = len([k[1] for o in Storage for k in o.selected_items.selected_loops if k[1] is True]) // 2
                    else:
                        p_total_sel_edges = sum([len(o.selected_items.selected_loops) for o in Storage]) // 4
                    if p_total_sel_edges == 0:
                        p_total_sel_edges = 1
                else:
                    p_total_sel_edges = sum([len(o.selected_items.selected_edges) for o in Storage])


            for s_obj in SelectionProcessor.yield_selected_objects(Storage):
                bm = s_obj.bm
                uv_layer = s_obj.uv_layer

                for f in bm.faces:
                    f.tag = False

                Qviz.obj_matrix_world = s_obj.obj.matrix_world

                if self.tag_finished:
                    fin_fmap = ensure_facemap(bm, FINISHED_FACEMAP_NAME)

                new_seam_edge_idxs = []
                new_seam_loops = []
                if self.use_selected_edges and is_edge_selection_mode:
                    from ZenUV.ops.stitch import UvSplitProcessor
                    if p_total_sel_edges <= self.quadrify_edge_detection_limit:
                        is_pure_uv_edge_mode: bool = context.space_data.type == 'IMAGE_EDITOR' and is_not_sync and ZenPolls.version_since_3_2_0 and context.scene.tool_settings.uv_select_mode == "EDGE"

                        new_seam_edge_idxs, new_seam_loops = self.assign_seams_in_edge_selection_mode(is_not_sync, bm, uv_layer)

                        if is_pure_uv_edge_mode:
                            for loop in new_seam_loops[0]:
                                loop[uv_layer].select_edge = True
                            for loop in new_seam_loops[1]:
                                loop[uv_layer].select = True
                        else:
                            for i in new_seam_edge_idxs:
                                bm.edges[i].select = True

                        SP = UvSplitProcessor(context)

                        node_groups = SP.compound_nodes(uv_layer, [new_seam_loops[0].union(new_seam_loops[1]), ])

                        # SP.show_nodes(node_groups)

                        SP.calculate_loops_positions(
                            uv_layer=uv_layer,
                            node_groups=node_groups,
                            distance=1e-4,
                            is_split_ends=False,
                            is_per_vertex=False)

                        SP.set_uv_coordinates(node_groups, uv_layer)

                        if is_pure_uv_edge_mode:
                            p_stored_loops = {k[0] for k in s_obj.selected_items.selected_loops if k[1] is True}
                            for lp in new_seam_loops[0]:
                                if lp.index not in p_stored_loops:
                                    lp[uv_layer].select_edge = False
                            for lp in new_seam_loops[1]:
                                if lp.index not in p_stored_loops:
                                    lp[uv_layer].select = False
                        else:
                            for i in new_seam_edge_idxs:
                                if i not in s_obj.selected_items.selected_edges:
                                    bm.edges[i].select = False

                bm.faces.ensure_lookup_table()
                if self.influence == 'ISLAND':
                    if self.use_selected_edges and is_edge_selection_mode:
                        storage = [[f.index for f in island] for island in island_util.get_island(context, bm, uv_layer)]
                    else:
                        storage = s_obj.attribute_storage['islands']
                else:
                    if is_not_sync:
                        storage = LoopsFactory.face_indexes_from_loops_selection(context, bm, uv_layer, groupped=True)
                    else:
                        p_selected_faces = FacesFactory.face_indexes_by_sel_mode(context, bm)
                        storage = FacesFactory.compound_groups(
                            bm, [bm.faces[i] for i in p_selected_faces],
                            is_indices=True, is_split_seams=True)
                for island_idxs in storage:
                    island = [bm.faces[i] for i in island_idxs]

                    p_counter = Counter([len(f.verts) == 4 for f in island])

                    # Anyway skip islands without quads
                    if p_counter[True] == 0:
                        continue

                    b_is_non_quads_exist = p_counter[False] > 0
                    if self.skip_non_quads is True and b_is_non_quads_exist:
                        continue

                    ZenQuadrify.proceed(
                        context,
                        bm,
                        island,
                        uv_layer,
                        influence=self.influence,
                        face_shape=self.shape if self.algorithm == 'ZEN_UV' else self.edge_length_mode,
                        average_shape=True if self.shape != 'EVEN' and self.average_shape else False,
                        is_correct_aspect=self.is_correct_aspect,
                        b_is_split=True if self.influence == 'SELECTION' and self.post_td_mode != 'SKIP' else False,
                        alg_name=self.algorithm,
                        progress=progress)

                    ProgressBar.check_update_spinner_progress(progress)

                    if is_edge_selection_mode:
                        if self.mark_borders:
                            Log.debug('Quadrify', 'Mark borders is ON')
                            if len(new_seam_edge_idxs) != 0 and not QuadrifyMarkState.mark_seam:
                                for i in new_seam_edge_idxs:
                                    bm.edges[i].seam = False
                        else:
                            for i in new_seam_edge_idxs:
                                bm.edges[i].seam = False

                    if not self.use_pack_islands and td_context is not None:
                        TexelDensityProcessor.set_td_to_faces(context, s_obj.obj, island, td_inputs=td_context)

                    if self.orient in ("VERTICAL", "HORIZONTAL"):
                        from ZenUV.ops.transform_sys.transform_utils.tr_rotate_utils import TrOrientProcessor

                        p_active_image = ActiveUvImage(context)
                        angle = TrOrientProcessor.get_orient_angle_by_props(BoundingBox2d(points=([lp[uv_layer].uv for f in island for lp in f.loops])), p_active_image.aspect, orient_direction=self.orient)
                        if angle != 0.0:
                            TransformLoops.rotate_loops(self.collect_loops_for_rotation(uv_layer, island), uv_layer, angle, ZenQuadrify.pivot, p_active_image.aspect, angle)

                    elif self.orient == 'SKIP':
                        init_angle = FaceFactory.init_angle
                        init_pivot = FaceFactory.init_pivot

                        if init_angle is not None and init_angle != 0.0 and init_pivot is not None:
                            p_active_image = ActiveUvImage(context)
                            TransformLoops.rotate_loops(
                                self.collect_loops_for_rotation(uv_layer, island),
                                uv_layer=uv_layer,
                                angle=- init_angle,
                                pivot=init_pivot,
                                image_aspect=p_active_image.aspect,
                                angle_in_radians=True)

                    # Pin Island
                    if self.auto_pin == 'QUADS':
                        for face in (f for f in island if len(f.verts) == 4):
                            for lp in face.loops:
                                lp[uv_layer].pin_uv = True

                    elif self.auto_pin == 'ISLAND':
                        for face in island:
                            for lp in face.loops:
                                lp[uv_layer].pin_uv = True

                    if self.tag_finished:
                        set_face_int_tag([island, ], fin_fmap, int_tag=1)

                    bmesh.update_edit_mesh(s_obj.obj.data)

            # Zen Pack if needed
            if self.is_pack_allowed(context):
                if progress:
                    progress.set_text(prefix="Packing islands")
                    progress.updateSpinner()
                bpy.ops.uv.zenuv_pack('INVOKE_DEFAULT', display_uv=False, disable_overlay=True, fast_mode=True)
            else:
                pass

            # If Count of objects more than 1 - Fit UV view in mode checker
            if addon_prefs.autoFitUV and self.use_pack_islands:
                fit_uv_view(context, mode="all")

        except ProgressCancelException:
            self.report({'INFO'}, "Cancelled by user!")
            return {'CANCELLED'}
        finally:
            if progress is not None:
                progress.finish()

        # Display UV Widget from HOPS addon
        show_uv_in_3dview(context, use_selected_meshes=True, use_selected_faces=False, use_tagged_faces=True)

        return {'FINISHED'}

    def collect_loops_for_rotation(self, uv_layer, island):
        if self.influence == 'SELECTION':
            p_loops = set()
            for f in island:
                for loop in f.loops:
                    p_loops.add(loop)
                    p_uv = loop[uv_layer].uv
                    p_loops.update(lp for lp in loop.vert.link_loops if lp[uv_layer].uv == p_uv)
            return p_loops
        else:
            return [lp for f in island for lp in f.loops]

    def assign_seams_in_edge_selection_mode(self, b_is_not_sync, bm, uv_layer):
        from ZenUV.utils.get_uv_islands import LoopsFactory as LF
        p_new_seams: set = set()
        p_loops: list = [set(), set()]
        i_counter = 0
        if b_is_not_sync:
            if ZenPolls.version_since_3_2_0:
                for lp in LF.walk_edgeloop_along(
                            [lp for edge in bm.edges for lp in edge.link_loops if lp[uv_layer].select and lp[uv_layer].select_edge],
                            uv_layer, b_is_not_sync):
                    lp.edge.seam = True
                    p_new_seams.add(lp.edge.index)
                    p_loops[0].update({lp, lp.link_loop_radial_next})
                    p_loops[1].update({lp.link_loop_next, lp.link_loop_radial_next.link_loop_next})
                    i_counter += 1

            else:
                for lp in LF.walk_edgeloop_along(
                            [lp for edge in bm.edges for lp in edge.link_loops if lp[uv_layer].select],
                            uv_layer, b_is_not_sync):
                    lp.edge.seam = True
                    p_new_seams.add(lp.edge.index)
                    p_loops[0].update({lp, lp.link_loop_next, lp.link_loop_radial_next, lp.link_loop_radial_next.link_loop_next})
                    i_counter += 1
        else:
            for lp in LF.walk_edgeloop_along(
                        [lp for edge in bm.edges for lp in edge.link_loops if edge.select],
                        uv_layer, b_is_not_sync):
                lp.edge.seam = True
                p_new_seams.add(lp.edge.index)
                p_loops[0].update({lp, lp.link_loop_next, lp.link_loop_radial_next, lp.link_loop_radial_next.link_loop_next})
                i_counter += 1

        Log.debug('Quadrify', f'Total Loops in assign seam: {i_counter}')
        return p_new_seams, p_loops


class ZUV_OT_Quadrify(bpy.types.Operator, ZuvQuadrifyBase):
    bl_idname = "uv.zenuv_quadrify"
    bl_label = 'Quadrify'
    bl_description = 'Straighten rectangular shaped Island'
    bl_options = {'REGISTER', 'UNDO'}


class QUADRIFY_PT_Properties(bpy.types.Panel):
    """ Internal Popover Zen UV Quadrify Properties"""
    bl_idname = "QUADRIFY_PT_Properties"
    bl_label = "Quadrify Properties"
    bl_context = "mesh_edit"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 14

    def draw(self, context):
        wm = context.window_manager
        layout = self.layout
        op_quad = wm.operator_properties_last(ZUV_OT_Quadrify.bl_idname)
        if op_quad:
            ZUV_OT_Quadrify.draw_properties(op_quad, layout, context)


classes = [
    QUADRIFY_PT_Properties,
    ZUV_OT_Quadrify
]


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)


if __name__ == '__main__':
    pass
