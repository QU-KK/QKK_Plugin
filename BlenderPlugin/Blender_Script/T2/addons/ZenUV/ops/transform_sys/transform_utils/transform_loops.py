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

# Copyright 2023, Valeriy Yatsenko

import bmesh
from math import radians
from mathutils import Vector, Matrix
from .tr_utils import TrConstants
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils.transform import UvTransformUtils


class TrLoopsAnalyzer:

    @classmethod
    def check_fit_loops_results(cls, fit_bbox, chk_cluster_bbox):
        print('Checking results:\nleft | right | top | bottom')
        print(f'{cls.compare_vectors(chk_cluster_bbox.left_center, fit_bbox.left_center)}   {cls.compare_vectors(chk_cluster_bbox.right_center, fit_bbox.right_center)}   {cls.compare_vectors(chk_cluster_bbox.top_center, fit_bbox.top_center)}   {cls.compare_vectors(chk_cluster_bbox.bot_center, fit_bbox.bot_center)}')
        print(f'Checking results:\nleft {round((chk_cluster_bbox.left_center - fit_bbox.left_center).length, 4)}')
        print(f'right {round((chk_cluster_bbox.right_center - fit_bbox.right_center).length, 4)}')
        print(f'top {round((chk_cluster_bbox.top_center - fit_bbox.top_center).length, 4)}')
        print(f'bottom {round((chk_cluster_bbox.bot_center - fit_bbox.bot_center).length, 4)}')

    @classmethod
    def compare_vectors(cls, vec1: Vector, vec2: Vector, tolerance: float = 1e-6) -> bool:
        """
        Compare two Blender Vectors based on their x and y components.

        Args:
            vec1 (Vector): The first vector.
            vec2 (Vector): The second vector.
            tolerance (float): Tolerance for comparing floating-point numbers. Defaults to 1e-6.

        Returns:
            bool: True if the vectors are considered equal within the specified tolerance, False otherwise.
        """
        return abs(vec1.x - vec2.x) < tolerance and abs(vec1.y - vec2.y) < tolerance


class TransformLoops:

    @classmethod
    def get_fit_transform_matrix(
        cls,
        uvs: list[Vector],
        fit_bbox: BoundingBox2d,
        fit_axis_name='AUTO',
        single_axis=False,
        keep_proportion=True,
        align_to='cen',
        padding=0.0,
        angle=0.0,
        image_aspect=1.0,
        move=True,
        rotate=True,
        scale=True,
        flip=False
    ) -> Matrix:
        """
        Returns the final transformation matrix for a set of UVs.
        """
        if not uvs:
            return Matrix.Identity(3).to_4x4()

        if not keep_proportion:
            align_to = 'cen'

        fit_bbox_pivot = fit_bbox.get_as_dict()[align_to]

        R = cls._get_rotation_matrix(angle, image_aspect)

        i_bbox = BoundingBox2d(points=[uv.to_2d() for uv in uvs])
        i_bbox.rotate_by_matrix(R, i_bbox.center)
        i_pivot = i_bbox.get_as_dict()[align_to].to_3d()

        fit_axis_name = cls.get_current_axis(fit_axis_name, i_bbox, fit_bbox)

        scale_vec = (
            UvTransformUtils._get_scale_vec(
                fit_axis_name, single_axis, keep_proportion,
                i_bbox, fit_bbox,
                padding=padding + BoundingBox2d.transform_safe_zone
            ) if scale else Vector((1.0, 1.0))
        )

        if flip:
            scale_vec *= TrConstants.flip_vector[align_to]
            align_to = TrConstants.opposite_direction[align_to]

        S = Matrix.Diagonal(scale_vec).to_3x3()
        SR = (S @ R.to_3x3()).to_4x4() if rotate else S.to_4x4()

        if not move:
            fit_bbox_pivot = i_bbox.center

        if angle != 0.0:
            M = Matrix.Translation(-i_pivot) @ R @ Matrix.Translation(i_pivot)
            temp_uvs = [M @ uv for uv in uvs]
            p_new_pivot = BoundingBox2d(points=[Vector((uv.x, uv.y)) for uv in temp_uvs]).get_as_dict()[align_to].to_3d()
            M = Matrix.Translation(-p_new_pivot) @ S @ Matrix.Translation(p_new_pivot) @ M
        else:
            M = Matrix.Translation(-i_pivot) @ SR @ Matrix.Translation(i_pivot)

        p_new_pivot = BoundingBox2d(points=[Vector((M @ uv).to_2d()) for uv in uvs]).get_as_dict()[align_to].to_3d()
        M = Matrix.Translation(fit_bbox_pivot.to_3d() - p_new_pivot) @ M

        return M

    @classmethod
    def mute_axis(self, _offset: Vector, direction: str, opposite: bool = False) -> Vector:
        ''' In this case, opposite_direction is used to introduce a correction
            in cases where we have an alignment by cen_v or cen_h.
            Mathematically, with cen_v alignment, we get horizontally aligned islands.
            This is not what the user expects.
        '''
        if opposite:
            direction = TrConstants.opposite_direction[direction]
        return _offset * TrConstants.mute_axis[direction]

    @classmethod
    def _collect_uvs(
        cls,
        loops: list,
        uv_layer: bmesh.types.BMLayerItem,
    ):
        return [lp[uv_layer].uv for lp in loops]

    @classmethod
    def _set_uvs(
        cls,
        uv_layer: bmesh.types.BMLayerItem,
        loops: list,
        uvs: list
    ):
        for lp, uv in zip(loops, uvs):
            lp[uv_layer].uv = uv

    @classmethod
    def move_loops(
        cls,
        loops: list,
        uv_layer: bmesh.types.BMLayerItem,
        delta: Vector = Vector((0.0, 0.0))
    ) -> None:

        if delta.magnitude == 0:
            return
        for loop in loops:
            loop[uv_layer].uv = loop[uv_layer].uv + delta

    @classmethod
    def scale_loops(
        cls,
        loops: list,
        uv_layer,
        scale: Vector = Vector((0.0, 0.0)),
        pivot: Vector = Vector((0.0, 0.0))
    ) -> None:

        if scale.x == 1.0 and scale.y == 1.0:
            return

        S = Matrix.Diagonal(scale)

        for loop in loops:
            loop[uv_layer].uv = (S @ (loop[uv_layer].uv - pivot)) + pivot

    @classmethod
    def rotate_loops(
        cls,
        loops: list,
        uv_layer,
        angle: float,
        pivot: Vector = Vector((0.0, 0.0)),
        image_aspect: float = 1.0,
        angle_in_radians: bool = False
    ) -> None:

        if angle == 0:
            return

        if not angle_in_radians:
            angle = radians(angle)

        R = cls._get_rotation_matrix(angle, image_aspect)

        for loop in loops:
            loop[uv_layer].uv = (R @ (loop[uv_layer].uv - pivot)) + pivot

    @classmethod
    def _get_rotation_matrix(cls, angle_radians, image_aspect=1):
        rotation_matrix = Matrix.Rotation(angle_radians, 2, 'Z')

        if image_aspect > 1:
            normalization_matrix = Matrix.Diagonal(Vector((1, 1 / image_aspect)))
            rescale_matrix = Matrix.Diagonal(Vector((1, image_aspect)))
        elif image_aspect < 1:
            normalization_matrix = Matrix.Diagonal(Vector((image_aspect, 1)))
            rescale_matrix = Matrix.Diagonal(Vector((1 / image_aspect, 1)))
        else:
            return rotation_matrix

        return (rescale_matrix @ rotation_matrix @ normalization_matrix)

    @classmethod
    def get_current_axis(cls, axis_name: str, i_bbox: BoundingBox2d, fit_bbox: BoundingBox2d):
        return {
            'V': 'V',
            'U': 'U',
            'MIN': i_bbox.get_shortest_axis_name(),
            'MAX': i_bbox.get_longest_axis_name(),
            'AUTO': cls.get_optimal_axis_name(i_bbox, fit_bbox),
            'MAX_FIT': fit_bbox.get_longest_axis_name(),
            'MIN_FIT': fit_bbox.get_shortest_axis_name()
        }[axis_name]

    @classmethod
    def get_optimal_axis_name(cls, i_bbox, fit_bbox) -> str:  # 'U', 'V'

        i_factor = i_bbox.aspect
        fit_factor = fit_bbox.aspect

        if i_factor < 1:
            if fit_factor >= i_factor:
                return i_bbox.get_longest_axis_name()
            else:
                return i_bbox.get_shortest_axis_name()
        elif i_factor == 1:
            return fit_bbox.get_shortest_axis_name()
        else:
            if fit_factor >= i_factor:
                return i_bbox.get_shortest_axis_name()
            else:
                return i_bbox.get_longest_axis_name()

    @classmethod
    def fit_loops(
        cls,
        loops: list,
        uv_layer: bmesh.types.BMLayerItem,
        fit_bbox: BoundingBox2d,
        fit_axis_name: str = 'AUTO',
        single_axis: bool = False,
        keep_proportion: bool = True,
        align_to: str = 'cen',
        padding: float = 0.0,
        angle: radians = 0.0,
        image_aspect: float = 1.0,
        move: bool = True,
        rotate: bool = True,
        scale: bool = True,
        flip: bool = False
    ) -> Vector:
        """
        :param loops: [bmesh.types.BMLoop, ...]
        :param uv_layer: bmesh.types.BMLayerItem
        :param fit_bbox: BoundingBox2d. Fit region Bounding box
        :param fit_axis_name: {'U', 'V', 'MIN', 'MAX', 'AUTO'}
        :param single_axis: bool
        :param keep_proportion: Bool
        :param align_to: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
        :param padding: float. Padding value from Fit region bbox
        :param angle: radians Island rotation
        :param image_aspect: float Current image aspect for rotate correction.
        :param move: is moving allowed?
        :param rotate: is rotation allowed?
        :param scale: is scaling allowed?
        :param flip: is flipping allowed?

        :return: flip pivot
        :rtype: Vector
        """

        if not loops:
            return Vector()

        if keep_proportion is False:
            align_to = 'cen'

        fit_bbox_pivot = fit_bbox.get_as_dict()[align_to]

        R = cls._get_rotation_matrix(angle, image_aspect)

        i_bbox = BoundingBox2d(points=[lp[uv_layer].uv for lp in loops], uv_layer=uv_layer)

        p_cluster_init_pivot = Vector((i_bbox.center.x, i_bbox.center.y))
        i_bbox.rotate_by_matrix(R, i_bbox.center)
        i_pivot = i_bbox.get_as_dict()[align_to]

        fit_axis_name = cls.get_current_axis(fit_axis_name, i_bbox, fit_bbox)

        scale_vec = UvTransformUtils._get_scale_vec(
            fit_axis_name,
            single_axis,
            keep_proportion,
            i_bbox,
            fit_bbox,
            padding=padding + BoundingBox2d.transform_safe_zone
        ) if scale else Vector((1.0, 1.0))
        scale_vec = scale_vec * TrConstants.flip_vector[align_to] if flip else scale_vec
        S = Matrix.Diagonal(scale_vec)

        SR = S @ R if rotate else S

        if flip is True:
            scale_vec *= TrConstants.flip_vector[align_to]
            align_to = TrConstants.opposite_direction[align_to]

        if not move:
            fit_bbox_pivot = p_cluster_init_pivot

        if angle != 0.0:
            # Rotate
            for loop in loops:
                loop[uv_layer].uv = ((R @ (loop[uv_layer].uv - i_pivot)) + i_pivot)
            p_new_pivot = BoundingBox2d(points=[lp[uv_layer].uv for lp in loops], uv_layer=uv_layer).get_as_dict()[align_to]
            # Scale
            for loop in loops:
                loop[uv_layer].uv = ((S @ (loop[uv_layer].uv - p_new_pivot)) + p_new_pivot)
            # Fit
            p_new_pivot = BoundingBox2d(points=[lp[uv_layer].uv for lp in loops], uv_layer=uv_layer).get_as_dict()[align_to]
            for loop in loops:
                loop[uv_layer].uv = ((loop[uv_layer].uv - p_new_pivot) + fit_bbox_pivot)
        else:
            # Rotate & Scale
            for loop in loops:
                loop[uv_layer].uv = ((SR @ (loop[uv_layer].uv - i_pivot)) + i_pivot)
            # Fit
            p_new_pivot = BoundingBox2d(points=[lp[uv_layer].uv for lp in loops], uv_layer=uv_layer).get_as_dict()[align_to]
            for loop in loops:
                loop[uv_layer].uv = ((loop[uv_layer].uv - p_new_pivot) + fit_bbox_pivot)

        # chk_cluster_bbox = BoundingBox2d(points=[lp[uv_layer].uv for lp in loops], uv_layer=uv_layer)

        # TrLoopsAnalyzer.check_fit_loops_results(fit_bbox, chk_cluster_bbox)

        return fit_bbox_pivot
