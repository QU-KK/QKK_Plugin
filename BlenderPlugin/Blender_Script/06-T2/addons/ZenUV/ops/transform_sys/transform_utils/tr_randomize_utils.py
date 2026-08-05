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


import random


class TransformRandomizer:

    seed: int = 0

    @classmethod
    def calc_angles_list(cls, limit: float, step: float = 0.0, is_positive_only: bool = False) -> list:
        if step != 0.0:
            count = round(abs(limit) / step)
            p_mult = - 1 if limit < 0.0 else 1
            p_angles = [p_mult * step * i for i in range(count + 1)]

            if not is_positive_only:
                p_angles.extend([i * - 1 for i in p_angles][1:])

            return p_angles

        return []

    @classmethod
    def calc_random_float(cls, limit: float, is_positive_only: bool = False) -> float:
        if is_positive_only:
            return random.uniform(0.0, limit)
        else:
            return random.uniform(-limit, limit)

    @classmethod
    def calc_random_float_scale(cls, limit: float, is_positive_only: bool = False) -> float:
        if is_positive_only:
            return random.uniform(1.0, limit)
        else:
            return random.uniform(0.0, limit)

    @classmethod
    def _calc_positions(cls, limit, step):
        count = int(limit // step) if step != 0.0 else 1
        if count == 1:
            return [0, step]
        return [step * i for i in range(count)]

    @classmethod
    def calc_positions_list(cls, limit: float, step: float, is_one_direction: bool = False):
        if step != 0.0 and step <= limit:
            p_positions = cls._calc_positions(limit, step)
            if not is_one_direction:
                p_positions.extend([i * -1 for i in p_positions][1:])
            return p_positions
        if limit == 0.0:
            return [0.0]
        else:
            return [cls.calc_random_float(limit, is_one_direction)]

    @classmethod
    def calc_scale_list(cls, limit: float, step: float, is_one_direction: bool = False) -> list:
        if step != 0.0 and step <= limit:
            count = round(abs(limit) / step)
            p_values = [step * i for i in range(count + 1)][1:]
            if not is_one_direction:
                p_values.extend([i * -1 for i in p_values])
            return sorted(p_values)
        if limit == 1.0:
            return [random.uniform(1.0, limit)]
        else:
            if is_one_direction:
                return [random.uniform(1.0, limit)]
            else:
                return [random.uniform(0.0, limit)]
