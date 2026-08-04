
from ..param import EngineParamTarget
from . import PACK_RATIO

from ..uc_entry import uc



class Point:

    __slots__ = ("_x", "_y")

    def __init__(self, x, y):
        self._x = float(x)
        self._y = float(y)

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = float(value)

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        self._y = float(value)

    def __len__(self):
        return 2

    def __iter__(self):
        yield self._x
        yield self._y

    def __getitem__(self, index):
        if index == 0:
            return self._x
        elif index == 1:
            return self._y
        raise IndexError("Point index out of range (expected 0 or 1)")

    def __repr__(self):
        return f"Point({self._x:.3f}, {self._y:.3f})"

    def __add__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(self._x + other._x, self._y + other._y)

    def __sub__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(self._x - other._x, self._y - other._y)

    def __mul__(self, scalar):
        return Point(self._x * scalar, self._y * scalar)

    def __truediv__(self, scalar):
        return Point(self._x / scalar, self._y / scalar)

    def __rmul__(self, scalar):
        return self.__mul__(scalar)

    def __eq__(self, other):
        if isinstance(other, Point):
            return self._x == other._x and self._y == other._y
        if isinstance(other, (tuple, list)) and len(other) == 2:
            return self._x == other[0] and self._y == other[1]
        return False

    def to_tuple(self):
        return (self._x, self._y)


class Box(EngineParamTarget):

    name : str
    p1_x : float
    p1_y : float
    p2_x : float
    p2_y : float

    @classmethod
    def unit_box(cls, pack_ratio=True):
        unit = cls(
            p1_x = 0.0,
            p1_y = 0.0,
            p2_x = 1.0,
            p2_y = 1.0
        )

        if pack_ratio:
            unit.apply_pack_ratio()

        return unit
    
    @classmethod
    def flipped_box(cls):
        import sys
        return cls(
            p1_x = float('inf'),
            p1_y = float('inf'),
            p2_x = float('-inf'),
            p2_y = float('-inf')
        )

    @classmethod
    def from_engine_param(cls, param):
        box = super().from_engine_param(param)
        box.apply_pack_ratio()
        return box
    
    def to_engine_param(self):
        param = super().to_engine_param()

        param['p1_x'] /= PACK_RATIO.get()
        param['p2_x'] /= PACK_RATIO.get()

        return param
    
    def apply_pack_ratio(self):
        self.p1_x *= PACK_RATIO.get()
        self.p2_x *= PACK_RATIO.get()

    def unapply_pack_ratio(self):
        self.p1_x /= PACK_RATIO.get()
        self.p2_x /= PACK_RATIO.get()

    @property
    def p1(self):
        return Point(self.p1_x, self.p1_y)
    
    @property
    def p2(self):
        return Point(self.p2_x, self.p2_y)

    @property
    def min_corner(self):
        return Point(min(self.p1_x, self.p2_x), min(self.p1_y, self.p2_y))

    @property
    def max_corner(self):
        return Point(max(self.p1_x, self.p2_x), max(self.p1_y, self.p2_y))

    @property
    def width_interval(self):
        return min(self.p1_x, self.p2_x), max(self.p1_x, self.p2_x)

    @property
    def height_interval(self):
        return min(self.p1_y, self.p2_y), max(self.p1_y, self.p2_y)

    @property
    def width(self):
        return abs(self.p1_x - self.p2_x)

    @property
    def height(self):
        return abs(self.p1_y - self.p2_y)
    
    def coords_tuple(self):
        min_corner = self.min_corner
        max_corner = self.max_corner
        return (min_corner[0], min_corner[1], max_corner[0], max_corner[1])

    def __hash__(self):
        return hash(self.coords_tuple())

    def __eq__(self, other):
        if isinstance(other, Box):
            return self.coords_tuple() == other.coords_tuple()
        
        return super().__eq__(other)
    
    def combine(self, other):
        min_corner = self.p1
        max_corner = self.p2
        o_min_corner = other.min_corner
        o_max_corner = other.max_corner

        self.p1_x = min(min_corner.x, o_min_corner.x)
        self.p1_y = min(min_corner.y, o_min_corner.y)
        self.p2_x = max(max_corner.x, o_max_corner.x)
        self.p2_y = max(max_corner.y, o_max_corner.y)
	
    @staticmethod
    def _interval_intersects(interval1, interval2):
        return not (interval1[0] >= interval2[1] or interval1[1] <= interval2[0])
    
    def intersects(self, other_box):
        return self._interval_intersects(self.width_interval, other_box.width_interval) \
               and self._interval_intersects(self.height_interval, other_box.height_interval)
    
    def tile(self, tile_x, tile_y):
        min_corner = self.min_corner
        max_corner = self.max_corner

        width = self.width
        height = self.height

        tile_max = (max_corner[0] + width * tile_x, max_corner[1] + height * tile_y)
        tile_min = (min_corner[0] + width * tile_x, min_corner[1] + height * tile_y)

        return Box(
            p1_x = tile_min[0],
            p1_y = tile_min[1],
            p2_x = tile_max[0],
            p2_y = tile_max[1]
        )

    def tile_from_number(self, tile_num, tiles_in_row):
        assert(tiles_in_row > 0)
        tile_x = tile_num % tiles_in_row
        tile_y = tile_num // tiles_in_row

        return self.tile(tile_x, tile_y)
    
    def tile_coords(self):
        eps = 1.0e-5
        return int((self.min_corner.x + eps) / PACK_RATIO.get()), int(self.min_corner.y + eps)
    
    @staticmethod
    def tile_grid_boxes(main_box, tile_count_x, tile_count_y):
        tile_count_total = tile_count_x * tile_count_y
        tiles_in_row = tile_count_x

        output = []
        
        for i in range(tile_count_total):
            output.append(main_box.tile_from_number(i, tiles_in_row))

        return output

    def to_uc_box(self):
        min = self.min_corner
        max = self.max_corner
        return uc.Box(uc.Point(min[0], min[1]), uc.Point(max[0], max[1]))
    
    @classmethod
    def from_uc_box(cls, box):
        return cls(
                p1_x = box.min_corner.x,
                p1_y = box.min_corner.y,
                p2_x = box.max_corner.x,
                p2_y = box.max_corner.y
        )
    
    @classmethod
    def from_uc_boxes(cls, boxes):
        return [cls.from_uc_box(box) for box in boxes]
    
    @staticmethod
    def boxes_to_target(boxes):
        target = uc.StdStageTarget()

        for box in boxes:
            target.append(box.to_uc_box())

        return target

