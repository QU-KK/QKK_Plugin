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

import bmesh
import math
import numpy as np
from mathutils import Vector, Matrix, geometry
from collections import defaultdict

from ZenUV.utils.transform import (
    calculate_fit_scale,
    UvTransformUtils
)
from ZenUV.utils.bounding_box import BoundingBox3d
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.constants import Planes
from ZenUV.utils.projection import Projection, pVector

# Debugging Purposes
from ZenUV.utils.generic import Scope, verify_uv_layer
# from ZenUV.utils.generic import MeshBuilder
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops

from ZenUV.utils.vlog import Log


CAT = 'orient_'


class BaseCluster():
    def __init__(self, context, obj, island, bm=None, index=-1) -> None:
        self.index = index
        self.island = self._island_container(island)
        self.context = context
        self.obj = self._object_container(obj)
        self.bm = self._get_bm() if bm is None else bm
        # self.bm.faces.ensure_lookup_table()
        self.destroy_bm = False
        self.transform_ma = self.obj.matrix_world
        self.loops = {loop.index: loop for face in self.island for loop in face.loops}
        self.uv_layer = verify_uv_layer(self.bm)
        self.init_co = [loop[self.uv_layer].uv.copy().freeze() for loop in self.loops.values()]
        self.uv_layer_name = self.uv_layer.name

        self.bbox: BoundingBox2d = BoundingBox2d(islands=[self.island, ], uv_layer=self.uv_layer)

        self.bound_uv_edges = self._cluster_bound_edges()

    def select(self, context, state=True):
        C = context
        uv_layer = self.uv_layer
        # self.mesh_edge.select = True
        sync_uv = C.scene.tool_settings.use_uv_select_sync
        if C.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
            for loop in self.loops.values():
                loop[uv_layer].select = state
            if ZenPolls.version_since_3_2_0:
                for loop in self.loops.values():
                    loop[uv_layer].select_edge = state
        else:
            for f in self.island:
                f.select = state

    def reset(self):
        for loop, co in zip(self.loops.values(), self.init_co):
            loop[self.uv_layer].uv = co

    def update_bounds(self):
        self.bound_uv_edges = self._cluster_bound_edges()

    def update_mesh(self):
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=False)

    def _object_container(self, obj):
        if isinstance(obj, str):
            return self.context.scene.objects[obj]
        else:
            return obj

    def _check_zeroarea(self):
        zeroarea = [f for f in self.island if f.calc_area() == 0]
        return zeroarea

    def _island_container_worked(self, island):
        if not isinstance(island, list):
            island = list(island)
        if not isinstance(island[0], int):
            return island
        else:
            self.bm.faces.ensure_lookup_table()
            return [self.bm.faces[index] for index in island]

    def _island_container(self, island):
        if not isinstance(island, list):
            island = list(island)
        if not isinstance(island[0], int):
            return island
            # Fixed #371
            # return [f for f in island if f.calc_area() != 0]
        else:
            self.bm.faces.ensure_lookup_table()
            # Fixed #371
            # return [f for f in [self.bm.faces[index] for index in island] if f.calc_area() != 0]
            return [f for f in [self.bm.faces[index] for index in island]]

    def _get_bm(self):
        if self.obj.mode == "EDIT":
            return bmesh.from_edit_mesh(self.obj.data)
        else:
            bm = bmesh.new()
            bm.from_mesh(self.obj.data)
            self.destroy_bm = True
            return bm

    def _cluster_bound_edges(self):
        edge_indexes = island_util.get_uv_bound_edges_indexes(self.island, self.uv_layer)
        edges = [e for f in self.island for e in f.edges if e.index in edge_indexes]
        loops = [loop for edge in edges for loop in edge.link_loops if loop in self.loops.values()]
        ex = []
        for loop in loops:
            ex.append(loop.link_loop_next)
        return loops + ex

    # Deleting (Calling destructor)
    def __del__(self):
        if self.destroy_bm:
            self.bm.free


class ProjectionPlane:
    i = 1
    j = 1
    direction = Vector((-1.0, 0.0, 0.0))
    transform = Matrix.Rotation(math.radians(45.0), 4, 'Z') @ Matrix.Rotation(math.radians(-20.0), 4, 'X')
    # transform = Matrix()
    s = transform @ Vector((0.0, 0.0, 0.0))
    x = transform @ Vector((1.0, 0.0, 0.0)) * i
    y = transform @ Vector((0.0, 0.0, 1.0)) * j
    s_uv = Vector((0.0, 0.0))
    x_uv = Vector((1.0, 0.0))
    y_uv = Vector((0.0, 1.0))


# class ProjectCluster(BaseCluster):
class ProjectCluster():

    def set_fit_to_uv(self, fit=False):
        self.fit_to_uv_area = fit

    def set_object(self, obj):
        self.obj = obj

    def set_transform(self, ma):
        self.ma = ma

    def project_hybrid_cluster(self):
        """ Creates a projection based on BaseCluster and ZenCluster data """
        self.project()

        edges = [edge for edge in self.uv_edges if edge.is_border()]
        distortion = (np.random.rand(len(edges), 2) * 0.001).tolist()
        verts = [[edge.vert, edge.other_vert] for edge in edges]
        for v_edge, dist in zip(verts, distortion):
            vec = Vector(dist)
            v_edge[0].move_by(vec)
            v_edge[1].move_by(vec)

    def project_face_loops(self, loops, uv_layer, input_plane=None, s_factor=1.0):
        plane = self.check_input_plane(input_plane, rough_fit=True)

        base_co, base_uv, to_uv = self._project(plane)

        for lp in loops:
            lp[uv_layer].uv = base_uv + (self.ma @ lp.vert.co - base_co) @ to_uv * s_factor

    def project(self, input_plane=None, s_factor=1.0):
        """ plane - Vectors list size 3
        Sample  [Vector((0.0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0))]
        Mapping [zero, x, y]
        """
        if not hasattr(self, "ma"):
            self.ma = Matrix()

        plane = self.check_input_plane(input_plane, rough_fit=True)

        base_co, base_uv, to_uv = self._project(plane)

        for lp in self.loops.values():
            lp[self.uv_layer].uv = base_uv + (self.ma @ lp.vert.co - base_co) @ to_uv * s_factor

        # Fit to UV Area
        if hasattr(self, "fit_to_uv_area") and self.fit_to_uv_area:
            points = [lp[self.uv_layer].uv for lp in self.loops.values()]
            points = np.array(points)
            points = self._fit_to_uv_area(points)
            points *= s_factor

            for lp, co in zip(self.loops.values(), points):
                lp[self.uv_layer].uv = co

    def _project(self, plane):
        base_co = plane.s
        x = plane.x - base_co
        y = plane.y - base_co
        normal = x.cross(y)

        base_uv = plane.s_uv

        u = plane.x_uv - base_uv
        v = plane.y_uv - base_uv

        to_uv = Matrix([x, y, normal]).inverted(Matrix([x, y, normal])) @ Matrix([u, v, [0, 0]])
        return base_co, base_uv, to_uv

    def check_input_plane(self, input_plane, rough_fit=True):
        if not input_plane:
            plane = ProjectionPlane()

            # Try to fit Plane to Object bbox.
            if rough_fit:
                bbox = BoundingBox3d(self.obj)
                plane.s = bbox.lo_point * Vector((1, 0, 1))
                factor = bbox.max_dim
                plane.x = plane.s + plane.x * factor
                plane.y = plane.s + plane.y * factor

        else:
            plane = ProjectionPlane()
            plane.s = input_plane[0]
            plane.x = input_plane[1]
            plane.y = input_plane[2]
        return plane

    def project_zen_cluster(self, input_plane=None, s_factor=1.0):
        """ Create projection only for ZenCluster. """
        plane = self.check_input_plane(input_plane, rough_fit=True)

        base_co, base_uv, to_uv = self._project(plane)

        for edge in self.uv_edges:
            distortion = np.random.rand(1, 2)[0] * 0.001 if edge.is_border() else [0, 0]
            for v in (edge.vert, edge.other_vert):
                v.set_position(Vector(distortion) + base_uv + (v.mesh_vert.co - base_co) @ to_uv * s_factor)

    def preproject(self):
        """ Create simple preprojection in general purposes.
            Main goal is to avoid zero uv coordinates. """
        coo = np.random.rand(len(self.loops), 2)
        for lp, co in zip(self.loops.values(), coo):
            lp[self.uv_layer].uv = co

    def project_obj_mode(self, input_plane=None, s_factor=1.0):
        """ Create projection in OBJECT MODE.
        self.obj need to be specified. self.set_object(obj)."""

        if not hasattr(self, "ma"):
            self.ma = Matrix()

        plane = self.check_input_plane(input_plane, rough_fit=True)
        base_co, base_uv, to_uv = self._project(plane)

        me = self.obj.data
        uv_layer = me.uv_layers.active.data

        for lp in me.loops:
            vertex_co = self.ma @ me.vertices[lp.vertex_index].co
            uv_layer[lp.index].uv = base_uv + (vertex_co - base_co) @ to_uv * s_factor

        # Fit to UV Area
        if hasattr(self, "fit_to_uv_area") and self.fit_to_uv_area:
            loops = {uv_layer[lp.index]: uv_layer[lp.index].uv for lp in me.loops}
            points = np.array(list(loops.values()))

            points = self._fit_to_uv_area(points)
            points *= s_factor

            for loop, coo in zip(loops.keys(), points):
                loop.uv = coo

    def _fit_to_uv_area(self, points):
        factor = self._get_factor(points=points.tolist())
        points *= factor
        shift = self._get_shift(points=points.tolist())
        points += shift
        return points

    def _get_shift(self, points):
        bbox = BoundingBox2d(points=points)
        return bbox.shift_to_uv_area

    def _get_factor(self, points):
        bbox = BoundingBox2d(points=points)
        return bbox.factor_to_uv_area


# class TransformCluster(ZenCluster):
class TransformCluster():

    # def __init__(self, context, obj, island, bm=None) -> None:
    #     super().__init__(context, obj, island, bm)

    def rotate(
        self,
        angle=1.5708,
        anchor: Vector = None
    ) -> None:
        """ angle in radians """
        if anchor is None:
            anchor = self.bbox.center
        UvTransformUtils.rotate_island(self.island, self.uv_layer, angle, anchor, angle_in_radians=True)

    def fit(self, fit_mode="cen", keep_proportion=True, bounds=Vector((1.0, 1.0))):
        scale = calculate_fit_scale(fit_mode, 0.0, self.bbox, keep_proportion, bounds=bounds)
        UvTransformUtils.scale(self.island, self.uv_layer, scale, pivot=self.bbox.center)

    def move_to_pos(self, pos):
        loops = [loop[self.uv_layer] for loop in self.loops.values()]
        # np.array(uvs).reshape((-1, 2)) + delta
        uvs = np.array([loop.uv for loop in loops]).reshape((-1, 2)) + pos
        self._set_uvs(loops, uvs)

    def scale(self, scale: float, pivot: Vector):
        loops = [loop[self.uv_layer] for loop in self.loops.values()]
        uvs = np.array([loop.uv for loop in loops]).reshape((-1, 2))

        S = Matrix.Diagonal(Vector([scale] * 2))
        uvs = np.dot(np.array(uvs).reshape((-1, 2)) - pivot, S) + pivot
        self._set_uvs(loops, uvs)

    def _collect_loops(self):
        data = {lp[self.uv_layer]: lp[self.uv_layer].uv for lp in self.loops.values()}
        return data.keys(), list(data.values())

    def _set_uvs(self, loops, uvs):
        for lp, uv in zip(loops, uvs):
            lp.uv = uv


class _OrientClusterLegacy():

    def __init__(self):
        self.f_orient = False
        self.axis_direction = {
                "x": 0.0,
                "-x": 0.0,
                "y": 0.0,
                "-y": 0.0,
                "z": 0.0,
                "-z": 0.0,
            }
        # self.show_info = False
        self.compensate_transform = False
        self.primary_edges = None
        self.cluster_normal_axis = None

        self.transform_ma = Matrix()
        self.cluster_normal = None

        self._cluster_parametrization()

        self.edge_anchor = None
        self.uv_angle = 0
        self.mesh_angle = 0
        self.master_edge = None
        self.select_master_edge = False
        self.type = 'ORGANIC'

    def set_direction(self, direction):
        rev_values = {True: math.pi, False: 0.0}
        for axis, _dir in direction.items():
            self.axis_direction[axis] = rev_values[_dir]

    def do_orient_to_world(self):
        if self.type == 'ORGANIC':
            self._orient_organic()
        elif self.type == 'HARD':
            self._orient_hard()
        else:
            print("The Cluster TYPE is not defined. Define the TYPE first.(HARD, ORGANIC)")

    def show_data(self):
        # self.show_info = True
        print("\nOrient Cluster Data: ")
        print("Master Edge Index ->", self.master_edge.mesh_edge.index)
        print("UV Angle: ", math.degrees(self.uv_angle))
        print("Mesh Angle: ", math.degrees(self.mesh_angle))

    def _find_min_vertical(self, edge):
        return min([(self.transform_ma @ vert.co).z for vert in edge.mesh_verts])

    def _find_min_horizontal(self, edge):
        return min([(self.transform_ma @ vert.co).y for vert in edge.mesh_verts])

    def _cluster_parametrization(self):

        self.primary_edges = self._find_primary_edges()
        normal = self.get_cluster_overall_normal()
        if normal.magnitude < 1:
            normal = self.get_cluster_simple_normal()

        normal.normalize()

        self.cluster_normal = normal
        self.cluster_normal_axis = self._get_cluster_normal_axis()

        if "z" in self.cluster_normal_axis:
            self.primary_edges = self._find_primary_edges(vertical=False)

    def get_cluster_simple_normal(self):
        edge = self.primary_edges[0]
        normals = [loop.face.normal for loop in edge.loops]
        normal = Vector()
        for n in normals:
            normal += n
        normal = self.transform_ma @ normal
        return normal

    def get_cluster_overall_normal(self):
        normal = Vector()
        for face in self.island:
            normal = normal + face.normal
        normal = self.transform_ma @ normal
        return normal

    # def build_vector(self, normal):
    #     builder = MeshBuilder(self.bm)
    #     coords = (Vector(), normal)
    #     builder.create_edge(coords)

    def _test_for_z(self, normal, axis):

        if round(normal.x, 4) == round(Planes.z3_negative.x, 4) and \
           round(normal.y, 4) == round(Planes.z3_negative.y, 4) and \
           round(normal.z, 4) == round(Planes.z3_negative.z, 4):
            return "-z"

        if round(normal.x, 4) == round(Planes.z3.x, 4) and \
           round(normal.y, 4) == round(Planes.z3.y, 4) and \
           round(normal.z, 4) == round(Planes.z3.z, 4):
            return "z"

        return axis

    def _orient_hard(self):
        image_aspect = ActiveUvImage(self.context).aspect
        axis = self.cluster_normal_axis
        self.master_edge = self.primary_edges[0]

        prj = Projection(self.transform_ma, self.bm, self.master_edge)
        proj = prj.uni_project(axis)
        self.mesh_angle = proj.angle_to_y_2d()
        self.uv_angle = pVector((
            self.master_edge.vert.uv_co,
            self.master_edge.other_vert.uv_co)).angle_to_y_2d() * -1

        if axis == "-x":
            dif_angle = self.uv_angle - self.mesh_angle
        if axis == "x":
            dif_angle = self.uv_angle + self.mesh_angle
        if axis == "y":
            dif_angle = self.uv_angle - self.mesh_angle
        if axis == "-y":
            dif_angle = self.uv_angle + self.mesh_angle
        if axis == "-z":
            dif_angle = self.uv_angle - self.mesh_angle
            dif_angle += math.pi
        if axis == "z":
            dif_angle = self.uv_angle + self.mesh_angle

        dif_angle += self.axis_direction[axis]

        if self.select_master_edge:
            self.master_edge.mesh_edge.select = True

        TransformLoops.rotate_loops(
            loops=[lp for f in self.island for lp in f.loops],
            uv_layer=self.uv_layer,
            angle=dif_angle,
            pivot=self.bbox.center,
            image_aspect=image_aspect,
            angle_in_radians=True)

        for vert in self.uv_verts:
            vert.update_uv_co()

        if self.f_orient:
            dif_angle = 0.0 if self.bbox.is_circle() else self.bbox.get_orient_angle(image_aspect)

            if axis == "-z":
                dif_angle += math.pi

            dif_angle += self.axis_direction[axis]

            TransformLoops.rotate_loops(
                loops=[lp for f in self.island for lp in f.loops],
                uv_layer=self.uv_layer,
                angle=dif_angle,
                pivot=self.bbox.center,
                image_aspect=image_aspect,
                angle_in_radians=True)

    def _get_cluster_normal_axis(self):
        dot = -100
        axis = 0

        for ax, plane in Planes.pool_3d_orient_dict.items():
            current_dot = self.cluster_normal.dot(plane)
            if current_dot > dot:
                dot = current_dot
                axis = ax
        axis = self._test_for_z(self.cluster_normal, axis)
        return axis

    def print_r_points(self, r_points):
        print("r_points -->")
        for p in r_points:
            print(p)
        print("r_points <--")

    def _orient_organic(self):
        image_aspect = ActiveUvImage(self.context).aspect
        edge = self._find_base_vector()

        dot = -100
        axis = 0

        for ax, plane in Planes.pool_3d_orient_dict.items():
            current_dot = self.cluster_normal.dot(plane)
            if current_dot > dot:
                dot = current_dot
                axis = ax
        axis = self._test_for_z(self.cluster_normal, axis)
        self.master_edge = None
        prj = Projection(self.transform_ma, self.bm, edge)
        proj = prj.uni_project(axis)
        self.mesh_angle = proj.angle_to_y_2d()
        self.uv_angle = pVector((
            edge.vert.uv_co,
            edge.other_vert.uv_co)).angle_to_y_2d()

        dif_angle = - self.uv_angle + self.mesh_angle

        if axis == "-x":
            dif_angle = - self.uv_angle - self.mesh_angle
        if axis == "x":
            dif_angle = - self.uv_angle + self.mesh_angle
        if axis == "y":
            dif_angle = - self.uv_angle - self.mesh_angle
        if axis == "-y":
            dif_angle = - self.uv_angle + self.mesh_angle
        if axis == "-z":
            dif_angle += math.pi
        if axis == "-z":
            dif_angle = - self.uv_angle + self.mesh_angle

        dif_angle += self.axis_direction[axis]

        TransformLoops.rotate_loops(
            loops=[lp for f in self.island for lp in f.loops],
            uv_layer=self.uv_layer,
            angle=dif_angle,
            pivot=self.bbox.center,
            image_aspect=image_aspect,
            angle_in_radians=True)

    def _find_base_vector(self):
        fake_edge = self.primary_edges[0]

        scp = Scope()
        for vert in self.uv_verts:
            if "z" not in self.cluster_normal_axis:
                co = (self.transform_ma @ vert.mesh_vert.co).z
            else:
                co = (self.transform_ma @ vert.mesh_vert.co).y
            scp.append(co, vert)

        v01 = scp.get_value_with_min_key()[0]
        v02 = scp.get_value_with_max_key()[0]

        fake_edge.vert = v01
        fake_edge.other_vert = v02
        fake_edge.verts_co = [v01.uv_co, v02.uv_co]
        fake_edge.mesh_verts = [v01.mesh_vert, v02.mesh_vert]

        return fake_edge

    def _find_primary_edges(self, vertical=True):
        sorter = {True: self._find_min_vertical, False: self._find_min_horizontal}
        uv_edges = self.uv_edges
        scp = Scope()
        for edge in uv_edges:
            min_value = sorter[vertical](edge)
            scp.append(min_value, edge)

        axis_sorter = {True: self.ax_sorter_vertical, False: self.ax_sorter_horizontal}
        stored_edges = scp.get_value_with_min_key()

        scp.clear()

        for edge in stored_edges:
            vec_edge = self.transform_ma @ (edge.mesh_verts[0].co - edge.mesh_verts[1].co)
            current_dot = axis_sorter[vertical](vec_edge)
            scp.append(current_dot, edge)

        return scp.get_value_with_max_key()

    def ax_sorter_vertical(self, vec_edge):
        return abs(vec_edge.dot(Planes.z3))

    def ax_sorter_horizontal(self, vec_edge):
        return abs(vec_edge.dot(Planes.y3))


class OrientCluster:

    axes = {
            'X': Vector((1, 0, 0)),
            'Y': Vector((0, 1, 0)),
            'Z': Vector((0, 0, 1)),
            '-X': Vector((-1, 0, 0)),
            '-Y': Vector((0, -1, 0)),
            '-Z': Vector((0, 0, -1))
        }

    injected_edges_remapped = {
        'X': Vector((0, 1, 0)),
        'Y': Vector((1, 0, 0)),
        'Z': Vector((1, 0, 0)),
        '-X': Vector((0, 1, 0)),
        '-Y': Vector((1, 0, 0)),
        '-Z': Vector((1, 0, 0))
    }

    ACM: Matrix = None  # Aspect Correct Matrix

    is_cluster_cycled: bool = False
    is_correct_aspect_ratio: bool = True

    plane_position: Vector = None
    plane_direction: Vector = None

    m_vert1: Vector = Vector((0, 0, 0))
    m_vert2: Vector = Vector((1, 1, 1))


    @classmethod
    def get_orient_angle(cls, island, uv_layer, image_aspect: float = 1):
        from ZenUV.utils.transform import matrix_by_image_aspect
        if image_aspect != 1:
            cls.ACM = matrix_by_image_aspect(image_aspect)
        else:
            cls.ACM = Matrix.Identity(2)
        cluster_normal = cls._calculate_cluster_normal(island)
        dominant_axis, dominant_axis_name = cls._find_dominant_axis(cluster_normal)

        return cls._calc_orient_angle(island, uv_layer, dominant_axis, dominant_axis_name)

    @classmethod
    def orient_uv_island(cls, island, uv_layer, pivot: Vector = None, image_aspect: float = 1) -> float:
        pivot = cls._calculate_uv_centroid(island, uv_layer) if pivot is None else pivot
        orient_angle = cls.get_orient_angle(island, uv_layer, image_aspect)
        cls._rotate_uv_island(island, uv_layer, orient_angle, image_aspect, pivot)
        return orient_angle

    @classmethod
    def _get_dominant_face(cls, faces: list, axis_vector_name: str) -> bmesh.types.BMFace:
        orient_vector = cls.axes.get(axis_vector_name, None)

        if orient_vector is None:
            raise ValueError("Invalid axis specified. Use 'X', '-X', 'Y', '-Y', 'Z', '-Z'.")

        max_dot = -float('inf')
        best_face = None

        for face in faces:
            dot = face.normal.dot(orient_vector)
            if dot > max_dot:
                max_dot = dot
                best_face = face

        return best_face

    @classmethod
    def _find_dominant_axis(cls, vector: Vector, threshold=5):  # threshold in degrees
        vector = vector.normalized()

        threshold_rad = math.radians(threshold)
        best_axis_name = None
        best_axis_vec: Vector = None
        min_angle = float('inf')

        for axis_name, axis_vector in cls.axes.items():
            angle = vector.angle(axis_vector, 0)
            if 'Z' in axis_name and angle > threshold_rad:
                continue

            if angle < min_angle:
                min_angle = angle
                best_axis_name = axis_name
                best_axis_vec = axis_vector

        return best_axis_vec, best_axis_name

    @classmethod
    def _calculate_cluster_normal(cls, island: list) -> Vector:
        island = list(island)
        total_normal = Vector((0, 0, 0))
        z_vector = Vector((0, 0, 1))
        scope = defaultdict(list)

        for f in island:
            dominant_axis, dominant_axis_name = cls._find_dominant_axis(f.normal)
            scope[dominant_axis_name].append(f.normal)

        data = [[k, sum(n, Vector())] for k, n in scope.items()]

        if sum([v[1] for v in data], Vector()).magnitude < 0.01:
            num_normals = len(island)
            cls.is_cluster_cycled = True
            for i in range(num_normals):
                normal1 = island[i].normal
                normal2 = island[(i + 1) % num_normals].normal
                cross_product = normal1.cross(normal2)
                total_normal += cross_product

            plane_normal = total_normal.cross(z_vector).normalized()

            if plane_normal.length == 0:
                plane_normal = Vector((1, 0, 0))

            total_normal = total_normal.cross(plane_normal).normalized()
            if total_normal.z < 0:
                total_normal.negate()
        else:
            cls.is_cluster_cycled = False
            max_axis, total_normal = max(data, key=lambda x: x[1].magnitude)


        if total_normal.magnitude == 0:
            total_normal = Vector((0.0, 1.0, 0.0))

        return total_normal.normalized()

    @classmethod
    def _interpolate_uv(cls, point_3d, edge_verts, uv_verts):
        v1 = edge_verts[0]
        v2 = edge_verts[1]

        edge_vector = v2 - v1
        point_vector = point_3d - v1
        t = point_vector.length / edge_vector.length

        UV = Vector(uv_verts[0]).lerp(Vector(uv_verts[1]), t)

        return UV

    @classmethod
    def _is_point_on_segment(cls, a, b, p, epsilon=1e-4):
        ab = b - a
        ap = p - a
        ab_len_sq = ab.length_squared

        if ab_len_sq == 0.0:
            return (p - a).length < epsilon

        t = ab.dot(ap) / ab_len_sq
        if t < -epsilon or t > 1 + epsilon:
            return False

        closest = a + ab * t
        return (p - closest).length < epsilon

    @classmethod
    def _find_lower_vertex_along_axis(cls, edge, axis_name):
        axis_index = {'X': 0, 'Y': 1, 'Z': 2}[axis_name.upper()]
        min_vertex = None
        min_value = float('inf')

        for vert in edge.verts:
            co = vert.co
            coord_value = co[axis_index]

            if coord_value < min_value:
                min_value = coord_value
                min_vertex = vert

        return min_vertex

    @classmethod
    def _find_longest_most_aligned_pair(cls, edges_vectors, axis: Vector):
        axis.normalize()
        max_alignment = -float('inf')
        best_aligned_pairs = []

        for i in range(len(edges_vectors)):
            for j in range(i + 1, len(edges_vectors)):
                edge1, vector1 = edges_vectors[i]
                edge2, vector2 = edges_vectors[j]

                difference_vector = vector2 - vector1
                normalized_difference = difference_vector.normalized()
                alignment = abs(normalized_difference.dot(axis))

                if alignment > max_alignment:
                    max_alignment = alignment
                    best_aligned_pairs = [(edges_vectors[i], edges_vectors[j])]
                elif alignment == max_alignment:
                    best_aligned_pairs.append((edges_vectors[i], edges_vectors[j]))

        longest_pair = max(best_aligned_pairs, key=lambda pair: (pair[1][1] - pair[0][1]).length, default=(None, None))

        return longest_pair

    @classmethod
    def _calc_orient_angle(cls, island, uv_layer, plane_vector, plane_axis_name):
        p_face = cls._get_dominant_face(island, plane_axis_name)
        plane_direction = Vector((0, 0, 1)) if plane_axis_name in {'X', 'Y', '-X', '-Y'} else Vector((0, 1, 0))
        p_face_center = p_face.calc_center_median()
        cls.plane_position = p_face_center
        cls.plane_direction = plane_direction

        def get_dominant_edge_crossection(edges, min_required=2):
            result = []
            epsilon = 1e-6
            max_epsilon = 1e-2
            step_factor = 10.0
            iteration = 1

            while epsilon <= max_epsilon:
                result.clear()

                for e in edges:
                    v1_co = e.verts[0].co
                    v2_co = e.verts[1].co

                    cross_vec = geometry.intersect_line_plane(v1_co, v2_co, p_face_center, plane_direction)

                    if cross_vec is not None and cls._is_point_on_segment(v1_co, v2_co, cross_vec, epsilon):
                        result.append([e, cross_vec])


                if len(result) >= min_required:
                    break
                else:
                    epsilon *= step_factor
                    iteration += 1

            if len(result) < min_required:
                Log.warn(CAT, f'Only {len(result)} intersection(s) found after all attempts. '
                              f'Last epsilon used: {epsilon / step_factor:.1e}. '
                              f'Minimum required: {min_required}. Possibly coplanar or degenerate geometry.')
                Log.warn(CAT, f'Dominant face index: {p_face.index}')

            return result

        p_edges = {e for f in island for e in f.edges}
        dominant_edges = get_dominant_edge_crossection(p_edges)

        if len(dominant_edges) < 2:
            Log.warn(CAT, 'Dominant edges is not detected. Returned zero angle')
            return 0.0

        remapped_axis = cls.injected_edges_remapped[plane_axis_name]
        # if cls.is_cluster_cycled:
        #     most_aligned_pair = cls._find_most_aligned_pair(dominant_edges, remapped_axis)
        # else:
        #     most_aligned_pair = cls._find_most_distant_pair(dominant_edges)

        most_aligned_pair = cls._find_longest_most_aligned_pair(dominant_edges, remapped_axis)


        def get_edge_loops(edge, vert1, vert2):
            lp1 = None
            for lp in vert1.link_loops:
                if lp.edge == edge and lp.face in island:
                    lp1 = lp
                    break
            lp2 = None
            for lp in vert2.link_loops:
                if lp.edge == edge and lp.face in island:
                    lp2 = lp
                    break
            if lp1 is None:
                lp1 = lp2.link_loop_next
            if lp2 is None:
                lp2 = lp1.link_loop_next

            return lp1, lp2

        edge1 = most_aligned_pair[0][0]
        edge2 = most_aligned_pair[1][0]
        v_mid_edge1: Vector = most_aligned_pair[0][1]
        v_mid_edge2: Vector = most_aligned_pair[1][1]

        cls.m_vert1 = most_aligned_pair[0][1]
        cls.m_vert2 = most_aligned_pair[1][1]

        p_axis_name = 'Z' if remapped_axis in (Vector((0.0, 1.0, 0.0)), Vector((1.0, 0.0, 0.0))) else 'Y'

        edge1_vert = cls._find_lower_vertex_along_axis(edge1, p_axis_name)
        v1_1 = edge1_vert.co
        edge1_other_vert = edge1.other_vert(edge1_vert)
        v1_2 = edge1_other_vert.co

        edge2_vert = cls._find_lower_vertex_along_axis(edge2, p_axis_name)
        v2_1 = edge2_vert.co
        edge2_other_vert = edge2.other_vert(edge2_vert)
        v2_2 = edge2_other_vert.co

        lp1_1, lp1_2 = get_edge_loops(edge1, edge1_vert, edge1_other_vert)
        lp2_1, lp2_2 = get_edge_loops(edge2, edge2_vert, edge2_other_vert)

        def correct_aspect(uvs: list):
            return [cls.ACM @ i[uv_layer].uv for i in uvs]

        uvs1 = correct_aspect([lp1_1, lp1_2])
        uvs2 = correct_aspect([lp2_1, lp2_2])

        interpolated1 = cls._interpolate_uv(v_mid_edge1, [v1_1, v1_2], uvs1)
        interpolated2 = cls._interpolate_uv(v_mid_edge2, [v2_1, v2_2], uvs2)

        projected = []
        for v in (v_mid_edge1, v_mid_edge2):
            projected.append(cls._project_vector_to_plane(v, plane_vector))
        v_projected = (Vector(projected[1] - projected[0])).to_3d()

        v_uv = interpolated2 - interpolated1

        return v_projected.to_2d().normalized().angle_signed(v_uv) if v_uv.magnitude != 0 else 0

    @classmethod
    def _rotate_uv_island(cls, island: list, uv_layer: bmesh.types.BMLayerItem, angle: float, image_aspect_ratio: float, pivot: Vector = None):
        pivot = cls._calculate_uv_centroid(island, uv_layer) if pivot is None else pivot
        R = TransformLoops._get_rotation_matrix(angle, image_aspect_ratio)
        M = Matrix.Translation((pivot[0], pivot[1], 0)) @ R.to_4x4() @ Matrix.Translation((-pivot[0], -pivot[1], 0))
        for face in island:
            for loop in face.loops:
                loop[uv_layer].uv = (M @ loop[uv_layer].uv.to_3d()).to_2d()

    @classmethod
    def _calculate_uv_centroid(cls, island, uv_layer):
        np_coords = np.array([loop[uv_layer].uv for f in island for loop in f.loops], dtype=np.double)
        return Vector(np.mean(np_coords, axis=0))

    @classmethod
    def _project_vector_to_plane(cls, projected_vector: Vector, plane_vector: Vector):
        d = projected_vector.dot(plane_vector) / plane_vector.length
        projection = plane_vector * d / plane_vector.length_squared
        v = projected_vector - projection

        if plane_vector == Planes.x3 or plane_vector == Planes.x3_negative:
            projection = Vector((v[1], v[2]))
            if plane_vector == Planes.x3_negative:
                projection = Vector((-projection[0], projection[1]))
        elif plane_vector == Planes.y3 or plane_vector == Planes.y3_negative:
            projection = Vector((v[0], -v[2]))
            if plane_vector == Planes.y3_negative:
                projection = Vector((-projection[0], projection[1]))
            projection.negate()
        elif plane_vector == Planes.z3 or plane_vector == Planes.z3_negative:
            projection = Vector((v[0], v[1]))
            if plane_vector == Planes.z3_negative:
                projection = Vector((projection[0], projection[1]))

        return projection
