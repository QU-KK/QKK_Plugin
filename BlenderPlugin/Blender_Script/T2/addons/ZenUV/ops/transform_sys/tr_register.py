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

from .tr_uni_transform import register_uni_transform, uregister_uni_transform
from .tr_align import register_tr_align, unregister_tr_align
from .tr_fit import register_tr_fit, unregister_tr_fit
from .tr_distribute import register_tr_distribute, unregister_tr_distribute
from .tr_scale import register_tr_scale, unregister_tr_scale
from .tr_move import register_tr_move, unregister_tr_move
from .tr_rotate import register_tr_rotate, unregister_tr_rotate
from .trim_depend_transform import register_trim_dep, unregister_trim_dep


def register_transform_sys():
    register_uni_transform()
    register_tr_align()
    register_tr_fit()
    register_tr_distribute()
    register_tr_scale()
    register_tr_move()
    register_tr_rotate()
    register_trim_dep()


def unregister_transform_sys():
    uregister_uni_transform()
    unregister_tr_align()
    unregister_tr_fit()
    unregister_tr_distribute()
    unregister_tr_scale()
    unregister_tr_move()
    unregister_tr_rotate()
    unregister_trim_dep()
