# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later
# The OrientedBounds code was taken and modified from https://github.com/mikedh/trimesh

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy  # noqa: F401
import bmesh
import typing  # noqa: F401
import mathutils
import numpy as np
import numpy.typing as npt

from mathutils import Euler, Matrix, Vector
from bmesh.types import BMVert
from math import atan2, pi
from .. import draw
from .. import utils
from ..utypes import MeshIslands
from bpy.props import *
from ..operators import project
from ..preferences import prefs

TOL_ZERO = np.float32(1e-8)
_IDENTITY = np.eye(4)
_IDENTITY.flags["WRITEABLE"] = False


class OrientBoundConvexData:
    def __init__(self, vertices, face_adjacency, face_adjacency_edges, face_normals):
        # Vertex coords
        self.vertices: np.ndarray = vertices
        # Edge with linked (two) faces (index)
        self.face_adjacency: npt.NDArray[np.int32] = face_adjacency
        # Edge with linked (two) verts (index)
        self.face_adjacency_edges: npt.NDArray[np.int32] = face_adjacency_edges
        self.face_normals: np.ndarray = face_normals

    @classmethod
    def from_points(cls, points) -> 'typing.Self':
        bm: bmesh.types.BMesh = bmesh.new()

        try:
            for co in points:
                bm.verts.new(co)

            convex_ret = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)

            inner_faces = [f for f in bm.faces if not f.select]
            bmesh.ops.delete(bm, geom=inner_faces, context='FACES')

            inner_verts = [v for v in convex_ret['geom_interior'] if isinstance(v, BMVert) and v.is_valid]
            bmesh.ops.delete(bm, geom=inner_verts, context='VERTS')

            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            bm.faces.index_update()
            bm.verts.index_update()
            bm.edges.index_update()

            coords = np.array([v.co.to_tuple() for v in bm.verts], dtype=np.float32)
            normals = np.array([f.normal.to_tuple() for f in bm.faces], dtype=np.float32)

            face_adj = []
            face_adj_edges = []

            for edge in bm.edges:
                # assert len(edge.link_faces) == 2
                f1, f2 = edge.link_faces
                face_adj.append((f1.index, f2.index))
                v1, v2 = edge.verts
                face_adj_edges.append((v1.index, v2.index))

            face_adj_np = np.array(face_adj, dtype=np.int32)
            face_adj_edges_np = np.array(face_adj_edges, dtype=np.int32)
            return cls(coords, face_adj_np, face_adj_edges_np, normals)
        except BaseException as e:
            bm.free()
            raise e


class UNIV_OT_BoxProject(project.UNIV_OT_BoxProject):
    # noinspection PyTypeHints
    orient: BoolProperty(name='Orient 3D', default=True,
                         description='This option is useful for cube-shaped elements that have different rotations.')

    def draw(self, context):
        if not self.orient:
            self.layout.prop(self, 'scale', slider=True)
        col = self.layout.column(align=True)
        if not self.orient:
            col.prop(self, 'scale_individual', expand=True, slider=True)
            col.prop(self, 'rotation', expand=True, slider=True)
            col.prop(self, 'move', expand=True)
        col.prop(self, 'avoid_flip')
        col.prop(self, 'orient')
        col.separator()
        col.prop(prefs(), 'use_texel')
        col.prop(self, 'use_correct_aspect')

    def box(self):
        all_lines = []
        degenerate_counter = 0
        for umesh in self.umeshes:
            if self.orient:
                if self.is_edit_mode:
                    if self.has_selected:
                        islands = MeshIslands.calc_selected(umesh)
                    else:
                        islands = MeshIslands.calc_visible(umesh)
                else:
                    islands = MeshIslands.calc_with_hidden(umesh)

                for mesh_isl in islands:
                    # TODO: Fix distortion when scale anisotropic (use world matrix)
                    vertices = {v.co.to_tuple() for f in mesh_isl for v in f.verts}
                    if len(vertices) <= 2:
                        degenerate_counter += 1
                        continue

                    matrix_world, dims = OrientedBounds.oriented_bounds(vertices)
                    mtx_x, mtx_y, mtx_z, r = self.get_box_transforms_orient(umesh, matrix_world)
                    self.box_ex(mesh_isl, mtx_x, mtx_y, mtx_z, r, umesh.uv)

                    lines = draw.mesh_extract.extraxt_cube_lines_for_orient_bound(
                        umesh.obj.matrix_world @ matrix_world, dims)
                    all_lines.append(lines)

            else:
                mtx_x, mtx_y, mtx_z, r = self.get_box_transforms(umesh)
                if self.is_edit_mode:
                    if self.has_selected:
                        faces = utils.calc_selected_uv_faces_iter(umesh)
                    else:
                        faces = utils.calc_visible_uv_faces_iter(umesh)
                else:
                    faces = umesh.bm.faces

                self.box_ex(faces, mtx_x, mtx_y, mtx_z, r, umesh.uv)

        if self.orient:
            draw.LinesDrawSimple3D.draw_register(np.concatenate(all_lines))
        if degenerate_counter:
            self.report({'WARNING'}, f'Detected {degenerate_counter} degenerate mesh islands')

    def get_box_transforms_orient(self, umesh, compensate_matrix: Matrix):
        aspect_x_mtx, aspect_y_mtx, aspect_z_mtx = self.get_aspect_matrix(umesh)

        # World orient
        M = umesh.obj.matrix_world @ compensate_matrix
        Z_world = M.to_3x3() @ Vector((0, 0, 1))
        if Z_world.dot(Vector((0, 0, 1))) < 0:
            compensate_matrix = compensate_matrix @ Matrix.Rotation(pi, 4, (1, 1, 0))

        # TODO: The Z axis also needs to be oriented.
        #  If the object is facing strictly vertically, the axis should be oriented to Forward.
        #  If the axis is tilted, the normal should point along the vertical axis.
        # if abs(Z_world.z) < 0.999:
        #     proj = Vector((Z_world.x, Z_world.y, 0.0))
        #     if proj.length > 1e-6:
        #         proj.normalize()
        #         FWD = Vector((1, 0, 0))
        #         angle = proj.angle(FWD, Vector((0, 0, 1)))
        #         angle = utils.round_threshold(angle, pi/2)
        #         compensate_matrix = compensate_matrix @ Matrix.Rotation(angle, 4, 'Z')

        # Align the object by the compensation angle
        _, compensate_r, _ = compensate_matrix.decompose()
        compensate_r.invert()
        compensate_matrix = compensate_r.to_matrix().to_4x4()

        # Set TD and apply scale
        _, _, scale_obj = umesh.obj.matrix_world.decompose()
        scale_obj *= utils.get_scale_from_texel()
        matrix_world_scale_ = Matrix.LocRotScale(None, None, scale_obj)


        orient_mat = compensate_matrix @ matrix_world_scale_
        mtx_x = aspect_x_mtx @ orient_mat
        mtx_y = aspect_y_mtx @ orient_mat
        mtx_z = aspect_z_mtx @ orient_mat


        return mtx_x, mtx_y, mtx_z, compensate_r

class OrientedBounds:
    @classmethod
    def oriented_bounds(cls, verts, angle_digits=1) -> tuple[Matrix, np.ndarray]:
        try:
            hull = OrientBoundConvexData.from_points(verts)

            vertices: np.ndarray = hull.vertices
            # edge with linked (two) face index  = Tris indexes (vertices indexes)
            hull_adj: npt.NDArray[np.int32] = hull.face_adjacency.T
            hull_edge = hull.face_adjacency_edges
            hull_normals = hull.face_normals

            # matrices which will rotate each hull normal to [0,0,1]
            # convert face normals to spherical coordinates on the upper hemisphere
            # the vector_hemisphere call effectively merges negative but otherwise
            # identical vectors
            spherical_coords = vector_to_spherical(vector_hemisphere(hull_normals))  # noqa
            # the unique_rows call on merge angles gets unique spherical directions to check
            # we get a substantial speedup in the transformation matrix creation
            # inside the loop by converting to angles ahead of time
            spherical_coords = spherical_coords[UniqueRows.unique_rows(spherical_coords, digits=angle_digits)[0]]
            matrices = [spherical_matrix(*s).T for s in spherical_coords]
            normals = spherical_to_vector(spherical_coords)

            min_2d = None
            min_volume = np.inf

            # we now need to loop through all the possible candidate
            # directions for aligning our oriented bounding box.
            for normal, to_2D in zip(normals, matrices):
                # we could compute the hull in 2D for every direction
                # but since we know we're dealing with a convex blob
                # we can do back-face culling and then take the boundary
                # start by picking the normal direction with fewer edges
                side: npt.NDArray[np.bool] = np.dot(hull_normals, normal) > -1e-10
                # for coplanar points this could be empty
                if not side.any():
                    continue
                # this line is a heavy lift as it is finding the pairs of
                # adjacent faces where *exactly one* out of two of the faces
                # is visible (xor) and then using the index to get the edge
                edges = hull_edge[np.bitwise_xor(*side[hull_adj])]

                # project the 3D convex hull vertices onto the plane
                projected = np.dot(to_2D[:3, :3], vertices.T).T[:, :3]
                # get the line segments of edges in 2D
                edge_vert = projected[:, :2][edges]
                # now get them as unit vectors
                edge_vectors = edge_vert[:, 1, :] - edge_vert[:, 0, :]
                edge_norm = np.sqrt(np.dot(edge_vectors ** 2, [1, 1]))
                edge_nonzero = edge_norm > 1e-10
                edge_vectors = edge_vectors[edge_nonzero] / edge_norm[edge_nonzero].reshape(
                    (-1, 1)
                )
                # create a set of perpendicular vectors
                persp_vectors = np.fliplr(edge_vectors) * [-1.0, 1.0]

                # find the projection of every hull point on every edge vector
                # this does create a potentially gigantic n^2 array in memory
                # and there is the 'rotating calipers' algorithm which avoids this
                # however, we have reduced n with a convex hull and numpy dot products
                # are extremely fast so in practice this usually ends up being fine
                edge_points = edge_vert[:, 0, :2]
                x = np.dot(edge_vectors, edge_points.T)
                y = np.dot(persp_vectors, edge_points.T)
                area: np.float64 = ((x.max(axis=1) - x.min(axis=1)) * (y.max(axis=1) - y.min(axis=1))).min()

                # the volume is 2D area plus the projected height
                size_z: np.float64 = np.ptp(projected[:, 2])
                volume: np.float64 = area * size_z

                # store this transform if it's better than one we've seen
                if volume < min_volume:
                    min_volume = volume
                    min_2d = to_2D

            # we know the minimum volume transform which should be the expensive
            # part so now we need to do the bookkeeping to find the box
            vert_ones = np.column_stack((vertices, np.ones(len(vertices), dtype=np.float32))).T
            projected = np.dot(min_2d, vert_ones).T[:, :3]

            height = np.ptp(projected[:, 2])
            rotation_2d, box = cls.oriented_bounds_2d(projected[:, :2])
            min_dimensions = np.append(box, height)
            rotation_2d[:2, 2] = 0.0
            rotation_z = planar_matrix_to_3d(rotation_2d)

            # combine the 2D OBB transformation with the 2D projection transform
            to_origin = np.dot(rotation_z, min_2d)

            # transform points using our matrix to find the translation
            transformed = transform_points(vertices, to_origin)
            box_center = transformed.min(axis=0) + np.ptp(transformed, axis=0) * 0.5
            to_origin[:3, 3] = -box_center

            # # return ordered 3D extents
            to_origin, min_dimensions = cls.sorted_dims_to_orient_by_longest_axis(to_origin, min_dimensions)

            return Matrix(to_origin).adjugated(), min_dimensions
        except:  # noqa
            to_origin, dimensions = OrientedBounds.oriented_bounds_coplanar(
                np.asanyarray(list(verts), dtype=np.float32))  # noqa
            matrix_world = Matrix(to_origin).inverted()
            return matrix_world, dimensions

    @classmethod
    def sorted_dims_to_orient_by_longest_axis(cls, to_origin, min_dimensions):
        # sort the three extents
        order = min_dimensions.argsort()
        # generate a matrix which will flip transform
        # to match the new ordering
        flip = np.eye(4)
        flip[:3, :3] = -np.eye(3)[order]

        # make sure transform isn't mangling triangles
        # by reversing windings on triangles
        if not np.isclose(np.linalg.det(flip[:3, :3]), 1.0):
            flip[:3, :3] = np.dot(flip[:3, :3], -np.eye(3))

        # apply the flip to the OBB transform
        to_origin = np.dot(flip, to_origin)
        # apply the order to the extents
        min_dimensions = min_dimensions[order]
        return to_origin, min_dimensions

    @staticmethod
    def oriented_bounds_2d(points) -> tuple[np.ndarray, np.ndarray]:
        from collections import Counter
        angles: Counter[float] = Counter()

        convex_indexes = mathutils.geometry.convex_hull_2d(points)
        points = points[convex_indexes]

        for i in range(len(points) - 1):
            edge_vec = Vector(points[i] - points[i+1])
            current_angle = atan2(*edge_vec)
            angle_to_rotate = -utils.find_min_rotate_angle(round(current_angle, 4))
            angles[round(angle_to_rotate, 4)] += edge_vec.length

        if angles:
            angle = max(angles, key=angles.get)
        else:
            angle = 0

        rot_mat = Matrix.Rotation(-angle, 2)

        rotated = points @ np.array(rot_mat, dtype=np.float32).T
        min_pt = rotated.min(axis=0)
        max_pt = rotated.max(axis=0)
        rectangle = max_pt - min_pt
        center = (min_pt + max_pt) / 2.0

        # to center matrix
        trans = Matrix.Translation(Vector((*center, 0.0)))
        transform = np.array((rot_mat.to_3x3() @ trans.to_3x3()), dtype=np.float32)

        return transform, rectangle

    @classmethod
    def oriented_bounds_coplanar(cls, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Find an oriented bounding box for an array of coplanar 3D points.

        Parameters
        ----------
        points : (n, 3) np.ndarray
          Points in 3D that occupy a 2D subspace.

        Returns
        ----------
        to_origin : (4, 4) np.ndarray
          Transformation matrix which will move the center of the
          bounding box of the input mesh to the origin.
        dimensions : (3, ) np.ndarray
          The dimensions of the mesh once transformed with to_origin
        """
        # Shift points about the origin and rotate into the xy plane
        points_mean = np.mean(points, axis=0)
        points_demeaned = points - points_mean
        _, _, vh = np.linalg.svd(points_demeaned, full_matrices=False)
        points_2d = np.matmul(points_demeaned, vh.T)
        # if np.any(np.abs(points_2d[:, 2]) > coplanar_tol):
        #     raise ValueError("Points must be coplanar")

        # Construct a homogeneous matrix representing the transformation above
        to_2d = np.eye(4)
        to_2d[:3, :3] = vh
        to_2d[:3, 3] = -np.matmul(vh, points_mean)

        # Find the 2D bounding box using the polygon
        to_origin_2d, dimensions_2d = cls.oriented_bounds_2d(points_2d[:, :2])
        # Make dimensions 3D
        dimensions = np.append(dimensions_2d, 0.0)
        # convert transformation from 2D to 3D and combine
        to_origin = np.matmul(planar_matrix_to_3d(to_origin_2d), to_2d)
        return to_origin, dimensions


def vector_hemisphere(vectors: np.ndarray) -> np.ndarray:
    """
    For a set of 3D vectors alter the sign so they are all in the
    upper hemisphere.

    If the vector lies on the plane all vectors with negative Y
    will be reversed.

    If the vector has a zero Z and Y value vectors with a
    negative X value will be reversed.

    Parameters
    ------------
    vectors:
      Input vectors  (n, 3)

    Returns
    ----------
    oriented: (n, 3) np.ndarray
      Vectors with same magnitude as source
      but possibly reversed to ensure all vectors
      are in the same hemisphere.
    """
    negative = vectors < -TOL_ZERO
    zero = np.logical_not(np.logical_or(negative, vectors > TOL_ZERO))
    # move all                          negative Z to positive
    # then for zero Z vectors, move all negative Y to positive
    # then for zero Y vectors, move all negative X to positive
    signs = np.ones(len(vectors), dtype=np.float64)
    # all vectors with negative Z values
    signs[negative[:, 2]] = -1.0
    # all on-plane vectors with negative Y values
    signs[np.logical_and(zero[:, 2], negative[:, 1])] = -1.0
    # all on-plane vectors with zero Y values
    # and negative X values
    signs[
        np.logical_and(np.logical_and(zero[:, 2], zero[:, 1]), negative[:, 0])
    ] = -1.0

    # apply the signs to the vectors
    oriented = vectors * signs.reshape((-1, 1))
    return oriented


def vector_to_spherical(cartesian: np.ndarray) -> np.ndarray:
    x, y, z = cartesian.T
    phi = np.arctan2(y, x)
    theta = np.arccos(z)
    return np.column_stack((phi, theta))


def spherical_to_vector(spherical: np.ndarray) -> np.ndarray:
    """
    Convert an array of `(n, 2)` spherical angles to `(n, 3)` unit vectors.
        spherical : (n, 2) - Angles, in radians
        vectors : (n, 3) float - Unit vectors
    """
    theta, phi = spherical.T
    st, ct = np.sin(theta), np.cos(theta)
    sp, cp = np.sin(phi), np.cos(phi)
    return np.column_stack((ct * sp, st * sp, cp))


def planar_matrix_to_3d(matrix_2d: np.ndarray) -> np.ndarray:
    """
    Given a 2D homogeneous rotation matrix convert it to a 3D rotation
    matrix that is rotating around the Z axis

    matrix_2d: (3,3) homogeneous 2D rotation matrix
    matrix_3d: (4,4) homogeneous 3D rotation matrix
    """

    if matrix_2d.shape != (3, 3):
        raise ValueError("Homogeneous 2D transformation matrix required!")

    matrix_3d = np.eye(4, dtype=np.float32)
    # translation
    matrix_3d[:2, 3] = matrix_2d[:2, 2]
    # rotation from 2D to around Z
    matrix_3d[:2, :2] = matrix_2d[:2, :2]

    return matrix_3d


def transform_points(points: np.ndarray,
                     matrix: np.ndarray,
                     translate: bool = True) -> np.ndarray:
    """
    Returns points rotated by a homogeneous
    transformation matrix.

    If points are (n, 2) matrix must be (3, 3)
    If points are (n, 3) matrix must be (4, 4)

    Parameters
    ----------
    points : (n, dim) float
      Points where `dim` is 2 or 3.
    matrix : (3, 3) or (4, 4) float
      Homogeneous rotation matrix.
    translate : bool
      Apply translation from matrix or not.

    Returns
    ----------
    transformed : (n, dim) float
      Transformed points.
    """
    points = np.asanyarray(points, dtype=np.float64)
    if len(points) == 0 or matrix is None:
        return points.copy()

    # check the matrix against the points
    matrix = np.asanyarray(matrix, dtype=np.float64)
    # shorthand the shape
    count, dim = points.shape

    # quickly check to see if we've been passed an identity matrix
    if np.abs(matrix - _IDENTITY[: dim + 1, : dim + 1]).max() < TOL_ZERO:
        return np.ascontiguousarray(points.copy())

    if translate:
        # apply translation and rotation
        stack = np.column_stack((points, np.ones(count)))
        return np.dot(matrix, stack.T).T[:, :dim]

    # only apply the rotation
    return np.dot(matrix[:dim, :dim], points.T).T


def spherical_matrix(theta: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """
    Give a spherical coordinate vector, find the rotation that will
    transform a [0,0,1] vector to those coordinates

    theta: rotation angle in radians
    phi:   rotation angle in radians

    matrix: (4,4) rotation matrix where the following will be a cartesian vector in the direction of the
             input spherical coordinates: np.dot(matrix, [0,0,1,0])

    """
    return np.array(Euler((0.0, phi, theta), 'XYZ').to_matrix().to_4x4(), dtype=np.float32)


class UniqueRows:
    @classmethod
    def unique_rows(cls, data, digits=None):
        """
        Returns indices of unique rows. It will return the
        first occurrence of a row that is duplicated:
        [[1,2], [3,4], [1,2]] will return [0,1]

        Parameters
        ---------
        data : (n, m) array
          Floating point data
        digits : int or None
          How many digits to consider

        Returns
        --------
        unique :  (j, ...) int
          Index in data which is a unique row
        inverse : (n, ...) int
          Array to reconstruct original
          Example: data[unique][inverse] == data
        """
        # get rows hashable so we can run unique function on it
        rows = cls.hashable_rows(data, digits=digits)

        # we are throwing away the first value which is the
        # garbage row-hash and only returning index and inverse

        # returns values sorted by row-hash but since our row-hash
        # were pretty much garbage the sort order isn't meaningful
        return np.unique(rows, return_index=True, return_inverse=True)[1:]

    @classmethod
    def hashable_rows(cls, data: np.ndarray, digits: int) -> np.ndarray:
        """
        We turn our array into integers based on the precision
        given by digits and then put them in a hashable format.

        Parameters
        ---------
        data : (n, m) array
          Input data
        digits : int or None
          How many digits to add to hash if data is floating point
          If None, tol.merge will be used

        Returns
        ---------
        hashable : (n, )
          May return as a `np.void` or a `np.uint64`
        """
        # if there is no data return immediately
        if len(data) == 0:
            return np.array([], dtype=np.uint64)

        # get array as integer to precision we care about
        as_int = cls.float_to_int(data, digits=digits)

        # if it is flat integers already return
        if len(as_int.shape) == 1:
            return as_int

        # if array is 2D and smallish, we can try bitbanging
        # this is significantly faster than the custom dtype
        if len(as_int.shape) == 2 and as_int.shape[1] <= 4:
            # can we pack the whole row into a single 64-bit integer
            precision = int(np.floor(64 / as_int.shape[1]))

            # get the extreme values of the data set
            d_min, d_max = as_int.min(), as_int.max()
            # since we are quantizing the data down we need every value
            # to fit in a partial integer so we have to check against extrema
            threshold = (2 ** (precision - 1)) - 1

            # if the data is within the range of our precision threshold
            if d_max < threshold and d_min > -threshold:
                # the resulting package
                hashable = np.zeros(len(as_int), dtype=np.uint64)
                # offset to the middle of the unsigned integer range
                # this array should contain only positive values
                bitbang = (as_int.T + (threshold + 1)).astype(np.uint64)
                # loop through each column and bitwise xor to combine
                # make sure as_int is int64 otherwise bit offset won't work
                for offset, column in enumerate(bitbang):
                    # will modify hashable in place
                    np.bitwise_xor(hashable, column << (offset * precision), out=hashable)  # noqa
                return hashable

        # reshape array into magical data type that is weird but works with unique
        dtype = np.dtype((np.void, as_int.dtype.itemsize * as_int.shape[1]))
        # make sure result is contiguous and flat
        result = np.ascontiguousarray(as_int).view(dtype).reshape(-1)
        result.flags["WRITEABLE"] = False

        return result

    @staticmethod
    def float_to_int(data, digits: int = 1) -> npt.NDArray[np.int64]:
        """
        Given a numpy array of float/bool/int, return as integers.

        Parameters
        -------------
        data :  (n, d) np.ndarray
          Input data
        digits : float or int
          Precision for float conversion

        Returns
        -------------
        as_int : (n, d) int
          Data as integers
        """
        # convert to any numpy array
        data = np.asanyarray(data)

        # we can early-exit if we've been passed data that is already
        # an integer, unsigned integer, boolean, or empty
        if data.dtype == np.int64:
            return data
        elif data.dtype.kind in "iub" or data.size == 0:
            return data.astype(np.int64)
        elif data.dtype.kind != "f":
            # if it's not a floating point try to make it one
            data = data.astype(np.float64)

        if not isinstance(digits, (int, np.integer)):
            raise TypeError(f"Digits must be `None` or `int`, not `{type(digits)}`")

        # multiply by requested power of ten
        # then subtract small epsilon to avoid "go either way" rounding
        # then do the rounding and convert to integer
        return np.round((data * 10 ** digits) - 1e-6).astype(np.int64)
