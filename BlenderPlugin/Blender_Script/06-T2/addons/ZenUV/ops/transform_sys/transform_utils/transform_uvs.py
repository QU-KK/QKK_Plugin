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

import numpy as np
from mathutils import Vector, Matrix


class TransformUVS:

    @classmethod
    def move_uvs(
        cls,
        uvs: list,
        delta: Vector = Vector((0.0, 0.0))
    ) -> list:
        """
        Input: uvs - list of uv coordinates
        Return: uvs - list of offsetted uv coordinates
        """
        if delta.magnitude == 0:
            return uvs
        else:
            return list(np.array(uvs).reshape((-1, 2)) + delta)

    @classmethod
    def clip_uvs(
        cls,
        uvs: list,
        low_lim: float,
        high_lim: float
    ) -> list:
        """
        Input: uvs - list of uv coordinates
        Return: uvs - list of offsetted uv coordinates
        """
        return np.clip(np.array(uvs), low_lim, high_lim)

    @classmethod
    def scale_uvs(
        cls,
        uvs: list,
        scale: Vector = Vector((0.0, 0.0)),
        pivot: Vector = Vector((0.0, 0.0))
    ) -> list:

        S = Matrix.Diagonal(scale)
        return [((uv - pivot) @ S) + pivot for uv in uvs]

    @classmethod
    def rotate_uvs(
        cls,
        uvs: list,
        angle: float,
        pivot: Vector = Vector((0.0, 0.0)),
        image_aspect: float = 1.0
    ) -> list:
        if angle == 0.0:
            return uvs

        R = cls._get_rotation_matrix(angle, image_aspect)
        return [((uv - pivot) @ R) + pivot for uv in uvs]

    @classmethod
    def _get_rotation_matrix(cls, angle, aspect=1):

        return Matrix(
            (
                (np.cos(angle), np.sin(angle) / aspect),
                (-aspect * np.sin(angle), np.cos(angle)),
            )
        )
