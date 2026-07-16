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


from .app_iface import *

import struct

from .utils import get_prefs
from .pgroup import standalone_property_group
from .spipeline.engine.geom.box import Box


def mark_boxes_dirty(self, context):
    get_prefs().boxes_dirty = True


def _box_coord_update(self, context, coord_name):
    coord_val = float(getattr(self, coord_name))
    coord_val_rounded = round(coord_val, self.COORD_PRECISION)

    # Cast the value to single precision because Blender internally uses 
    # single precision to store a property value
    coord_val_rounded = struct.unpack('f', struct.pack('f', coord_val_rounded))[0]
    # print('coord_val: {:.100}'.format(coord_val))
    # print('coord_val_rounded: {:.100}'.format(coord_val_rounded))
    if coord_val != coord_val_rounded:
        setattr(self, coord_name, coord_val_rounded)

    mark_boxes_dirty(self, context)


def _p1_x_update(self, context):
    _box_coord_update(self, context, 'p1_x')

def _p1_y_update(self, context):
    _box_coord_update(self, context, 'p1_y')

def _p2_x_update(self, context):
    _box_coord_update(self, context, 'p2_x')

def _p2_y_update(self, context):
    _box_coord_update(self, context, 'p2_y')


UNIT_BOX = Box.unit_box()


@standalone_property_group
class UVPM4_Box(Box):

    DIMENSION_MIN_LIMIT = 0.05
    COORD_PRECISION = 2
    COORD_STEP = 10.0
    COORD_TO_STR_FORMAT = "{:." + str(COORD_PRECISION) + "}"

    p1_x : FloatProperty(name="P1 (X)", default=UNIT_BOX.p1_x, precision=COORD_PRECISION, step=COORD_STEP, update=_p1_x_update)
    p1_y : FloatProperty(name="P1 (Y)", default=UNIT_BOX.p1_y, precision=COORD_PRECISION, step=COORD_STEP, update=_p1_y_update)
    p2_x : FloatProperty(name="P2 (X)", default=UNIT_BOX.p2_x, precision=COORD_PRECISION, step=COORD_STEP, update=_p2_x_update)
    p2_y : FloatProperty(name="P2 (Y)", default=UNIT_BOX.p2_y, precision=COORD_PRECISION, step=COORD_STEP, update=_p2_y_update)

    def __init__(
        self,
        p1_x=UNIT_BOX.p1_x,
        p1_y=UNIT_BOX.p1_y,
        p2_x=UNIT_BOX.p2_x,
        p2_y=UNIT_BOX.p2_y):

        super(type(self), self).__init__(
            p1_x = p1_x,
            p1_y = p1_y,
            p2_x = p2_x,
            p2_y = p2_y
        )

    def validate(self):
        if self.width < self.DIMENSION_MIN_LIMIT:
            raise RuntimeError('UV target box width must be larger than ' + self.DIMENSION_MIN_LIMIT)

        if self.height < self.DIMENSION_MIN_LIMIT:
            raise RuntimeError('UV target box height must be larger than ' + self.DIMENSION_MIN_LIMIT)

    def coord_to_str(self, coord):
        return self.COORD_TO_STR_FORMAT.format(coord)

    def offset(self, offset):
        self.p1_x += offset[0]
        self.p2_x += offset[0]
        self.p1_y += offset[1]
        self.p2_y += offset[1]

    def to_string(self):
        min_corner = self.min_corner
        max_corner = self.max_corner

        return "{}:{}:{}:{}".format(
            self.coord_to_str(min_corner[0]),
            self.coord_to_str(min_corner[1]),
            self.coord_to_str(max_corner[0]),
            self.coord_to_str(max_corner[1]))

    def label(self):
        min_corner = self.min_corner
        max_corner = self.max_corner

        min_corner_i = tuple(int(x) for x in min_corner)
        max_corner_i = tuple(int(x) for x in max_corner)

        if min_corner_i == min_corner and max_corner_i == max_corner:
            min_corner_i_plus1 = tuple(i + 1 for i in min_corner_i)
            if min_corner_i_plus1 == max_corner_i:
                return "Tile {}:{}".format(min_corner_i[0], min_corner_i[1])

        return "[{}, {}]-[{}, {}]".format(
            self.coord_to_str(min_corner[0]),
            self.coord_to_str(min_corner[1]),
            self.coord_to_str(max_corner[0]),
            self.coord_to_str(max_corner[1]))

    def point_inside(self, coords):
        min_corner = self.min_corner
        max_corner = self.max_corner

        return\
            min_corner[0] < coords[0] and\
            min_corner[1] < coords[1] and\
            max_corner[0] > coords[0] and\
            max_corner[1] > coords[1]

    def point_on_edges(self, coords, thickness):
        thickness = thickness / 2

        left = self.p1_x - thickness
        left_prim = self.p1_x + thickness

        top = self.p2_y + thickness
        top_prim = self.p2_y - thickness

        right = self.p2_x + thickness
        right_prim = self.p2_x - thickness

        bottom = self.p1_y - thickness
        bottom_prim = self.p1_y + thickness

        if self.p1_x > self.p2_x:
            left, left_prim, right, right_prim = right_prim, right, left_prim, left
        if self.p1_y > self.p2_y:
            bottom, bottom_prim, top, top_prim = top_prim, top, bottom_prim, bottom

        on_left = min(left, left_prim) < coords[0] < max(left, left_prim) and min(top, bottom) < coords[1] < max(top, bottom)
        on_top = min(top, top_prim) < coords[1] < max(top, top_prim) and min(left, right) < coords[0] < max(left, right)
        on_right = min(right, right_prim) < coords[0] < max(right, right_prim) and min(top, bottom) < coords[1] < max(top, bottom) if not on_left else False
        on_bottom = min(bottom, bottom_prim) < coords[1] < max(bottom, bottom_prim) and min(left, right) < coords[0] < max(left, right) if not on_top else False

        if self.p1_x > self.p2_x:
            on_left, on_right = on_right, on_left
        if self.p1_y > self.p2_y:
            on_top, on_bottom = on_bottom, on_top

        return [on_left, on_top, on_right, on_bottom]

    def copy(self):
        out = UVPM4_Box.SA()
        out.copy_from(self)
        return out
