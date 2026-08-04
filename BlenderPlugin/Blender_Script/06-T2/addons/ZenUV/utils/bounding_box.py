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


import bpy
import bmesh
import numpy as np
from typing import List, Tuple, Union
from dataclasses import dataclass, field, asdict
from math import pi
from mathutils import Vector, Matrix
from mathutils.geometry import convex_hull_2d

from ZenUV.utils.vlog import Log
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.utils.generic import resort_objects_by_selection, verify_uv_layer


# NOTE: 1 symbol is X, 2 symbol is Y
t_SYMBOL_BBOX_2_DIGITS = {
    "br":   "rb",
    "bl":   "lb",
    "tr":   "rt",
    "tl":   "lt",
    "cen":  "cc",
    "rc":   "rc",
    "lc":   "lc",
    "bc":   "cb",
    "tc":   "ct"
}


class UdimBbox:

    @classmethod
    def get_bbox(id: int):
        pass


class BoundingBox3d:

    # Blender BBox mapping order
    # (LoX, LoY, LoZ),
    # (LoX, LoY, HiZ),
    # (LoX, HiY, HiZ),
    # (LoX, HiY, LoZ),
    # (HiX, LoY, LoZ),
    # (HiX, LoY, HiZ),
    # (HiX, HiY, HiZ),
    # (HiX, HiY, LoZ)

    def __init__(self, obj) -> None:
        self.obj = obj
        self.mv = obj.matrix_world
        self.lc = [Vector((i[:])) for i in obj.bound_box[:]]
        self.loX = self.lc[0][0]
        self.loY = self.lc[0][1]
        self.loZ = self.lc[0][2]
        self.hiX = self.lc[6][0]
        self.hiY = self.lc[6][1]
        self.hiZ = self.lc[6][2]
        self.dim_x = self.hiX - self.loX
        self.dim_y = self.hiY - self.loY
        self.max_dim = max(self.dim_x, self.dim_y)
        self.lo_point = self.lc[0]
        self.hi_point = self.lc[6]


class DirMatrixStr:

    all_directions = ['tl', 'tc', 'tr', 'lc', 'cen', 'rc', 'bl', 'bc', 'br']
    all_directions_icons = [
        "tr_control_tl",
        "tr_control_tc",
        "tr_control_tr",
        "tr_control_lc",
        "tr_control_cen",
        "tr_control_rc",
        "tr_control_bl",
        "tr_control_bc",
        "tr_control_br"
    ]

    matrix = [
        ['tl', 'tc', 'tr'],
        ['lc', 'cen', 'rc'],
        ['bl', 'bc', 'br'],
    ]
    matrix_rev = [
        ['br', 'bc', 'bl'],
        ['rc', 'cen', 'lc'],
        ['tr', 'tc', 'tl'],
    ]
    matrix_rotated_ccw = [
        ['tr', 'rc', 'br'],
        ['tc', 'cen', 'bc'],
        ['tl', 'lc', 'bl'],
    ]


class DirectionBboxStr:

    _matrix: DirMatrixStr

    @property
    def matrix(self):
        return DirMatrixStr.matrix

    @matrix.setter
    def matrix(self, value):
        raise RuntimeError('DirectionBboxStr.matrix read only.')

    @classmethod
    def reversed_direction(cls, inp_dir: str) -> str:
        cls._check_appropriate_value(inp_dir)
        row_index, col_index = cls.get_current_indexes(inp_dir)
        return DirMatrixStr.matrix_rev[row_index][col_index]

    @classmethod
    def _check_appropriate_value(cls, inp_dir):
        if inp_dir not in DirMatrixStr.all_directions:
            msg = f'inp_dir not in {DirMatrixStr.all_directions}'
            raise RuntimeError(msg)

    @classmethod
    def get_current_indexes(cls, inp_dir):
        return next((i, row.index(inp_dir)) for i, row in enumerate(DirMatrixStr.matrix) if inp_dir in row)

    @classmethod
    def perpendicular_direction(cls, inp_dir: str) -> str:
        cls._check_appropriate_value(inp_dir)
        row_index, col_index = cls.get_current_indexes(inp_dir)
        return DirMatrixStr.matrix_rotated_ccw[row_index][col_index]


@dataclass
class SimpleBbox:

    bot_left: Vector = None
    top_left: Vector = None
    top_right: Vector = None
    bot_right: Vector = None

    center: Vector = None
    center_horizontal: Vector = None
    center_vertical: Vector = None

    len_x: float = None
    len_y: float = None

    top_center: Vector = None
    right_center: Vector = None
    bot_center: Vector = None
    left_center: Vector = None

    aspect: float = None
    aspect_inverted: float = None

    is_vertical: bool = None

    '''
        Is Vertical -->
        self.is_vertical = True - vertical,
        self.is_vertical = False - Horizontal,
        self.is_vertical = None - Square
    '''

    corners: List[Vector] = field(default_factory=list)
    _area: float = None

    @property
    def area(self) -> float:
        return self.len_x * self.len_y if self.len_x and self.len_y else 0.0

    @area.setter
    def area(self):
        raise RuntimeError('SimpleBbox.area read only')


@dataclass
class BoundingBox2d(SimpleBbox):

    transform_safe_zone = 0.000001

    def __init__(
        self,
        islands: list = [],
        points: list = [],
        uv_layer: bmesh.types.BMLayerItem = None,
        full: bool = False,
        safe_mode: bool = True
    ) -> None:

        self.safe_mode = safe_mode
        '''
            Safe Mode -->
            If self.safe_mode = True:
            All parameters will be checked.
            If the input parameters do not match, an error will be Raised.
            If self.safe_mode = False:
            The input parameters will not be checked.
            If they are filled in incorrectly,
            a bbox with one point with coordinates 0,0 will be created.
        '''

        self.uv_layer = uv_layer
        self.points = None
        self.full = full
        self._input_data_preparation(islands, points, uv_layer)

        self._update_bbox()

        # self.show_bbox()
        self._simple = field(default_factory=SimpleBbox)
        self.extras = None

    def __str__(self):
        values = vars(self)
        return "\nBoundingBox2d\n" + "\n".join([f"{key} --> {value}" for key, value in values.items()])

    @property
    def simple(self):
        s_bbox = SimpleBbox()

        for attr_name in asdict(s_bbox).keys():
            value = getattr(self, attr_name)
            print(f'{attr_name = }\t\t --> \t\t{value = }')
            setattr(s_bbox, attr_name, value)
        return s_bbox

    @simple.setter
    def simple(self):
        raise RuntimeError('BoundingBox2d.simple read only.')

    def _input_data_preparation(self, islands, points, uv_layer):

        if islands is not None and sum([len(i) for i in islands]) and uv_layer is not None:
            points = [loop[uv_layer].uv for island in islands for face in island for loop in face.loops]
        else:
            if not len(points):
                if self.safe_mode is False:
                    points = [Vector((0.0, 0.0))]
                else:
                    raise RuntimeError(f'Zen UV class BoundingBox2d input parameters error:\n \
Some parameters are not specified.\n \
The parameters of one of the groups must be specified in full.\n\n \
    Group 01:\n \
        islands state --> {[len(i) for i in islands]}\n \
        uv_layer --> {uv_layer}\n\n \
    Group 02:\n \
        points count--> {len(points)}')

        if len(points):
            if self.full:
                self.points = points
            else:
                self.points = self._convex_hull_2d(list(points))
        else:
            raise RuntimeError(f'self.points is {self.points}')

    def _uv_layer_container(self, uv_layer):
        if isinstance(uv_layer, str):
            uvl = self.bm.loops.layers.uv.get(uv_layer)
            if uvl:
                return uvl
        else:
            return uv_layer

    def _convex_hull_2d(self, points):
        """
        Return convex hull points. Include fix Blender issue with 2 points convex hull.
        """
        from mathutils.geometry import convex_hull_2d

        if len(points) > 2:
            return [points[i] for i in convex_hull_2d(points)]
        return points

    def rotate_by_matrix(self, r_matrix, pivot: Vector = None):
        if pivot is None:
            pivot = self.center
        self.points = [(r_matrix @ (point - pivot)) + pivot for point in self.points]
        self._update_bbox()

    def scale_np(self, scale: Vector, pivot_point: float = None) -> None:
        """
            Scale bbox using numpy by given Vector.
            Using bbox center as pivot.
        """
        if pivot_point is None:
            pivot_point = self.center

        S = Matrix.Diagonal(scale)
        self.points = [Vector(p) for p in (np.dot(np.array(self.points).reshape((-1, 2)) - pivot_point, S) + pivot_point)]
        self._update_bbox()

    def scale(self, scale: Vector, pivot_point: float = None):
        """
            Scale bbox using mathutils by given Vector.
            Using bbox center as pivot.
        """
        if pivot_point is None:
            pivot_point = self.center

        transformed_points = []
        S = Matrix([
            [scale[0], 0],
            [0, scale[1]]])
        for point in self.points:
            vector = Vector(point)
            relative_vector = vector - self.center
            transformed_vector = S @ relative_vector
            final_vector = transformed_vector + self.center
            transformed_points.append(final_vector)
        self.points = transformed_points
        self._update_bbox()

    def scaled(self, scale: Vector):
        """
            Scale bbox by given Vector.
            Using Zero coordinates (0.0, 0.0) as pivot.
        """
        return BoundingBox2d(
            points=[Vector((val)) for val in np.dot(np.array(self.points).reshape((-1, 2)), Matrix.Diagonal(scale))])

    def show_bbox(self, name="Noname"):
        divider_len = 80
        Log.info("\n" + "*" * divider_len + "\n" + f"BoundingBox2d named '{name}' attributes --> ")
        attrs = vars(self)
        Log.info(', '.join("%s: %s\n" % item for item in attrs.items()))
        Log.info(f"BoundingBox2d named '{name}' attributes --> END" + "\n" + "*" * divider_len + "\n")

    def _update_bbox(self):

        uvs = np.array(self.points).reshape((-1, 2))

        m_ax = np.amax(uvs, axis=0)
        m_in = np.amin(uvs, axis=0)

        minX, minY = m_in
        maxX, maxY = m_ax

        self.bot_left = Vector((minX, minY))
        self.top_left = Vector((minX, maxY))
        self.top_right = Vector((maxX, maxY))
        self.bot_right = Vector((maxX, minY))

        self.rect = (
            self.bot_left.x,
            self.top_left.y,
            self.top_right.x,
            self.bot_right.y
        )

        self.center = (self.bot_left + self.top_right) * 0.5

        self.top_center = (self.top_left + self.top_right) * 0.5
        self.right_center = (self.top_right + self.bot_right) * 0.5
        self.bot_center = (self.bot_right + self.bot_left) * 0.5
        self.left_center = (self.bot_left + self.top_left) * 0.5

        self.len_x = (self.top_right - self.top_left).length
        self.len_y = (self.top_left - self.bot_left).length

        self.center_horizontal = self.center * Vector((1.0, 0.0))
        self.center_vertical = self.center * Vector((0.0, 1.0))

        self.max_len = max(self.len_x, self.len_y)
        div = min(self.max_len, 1) if self.max_len != 0 else 1
        self.factor_to_uv_area = max(self.max_len, 1) / div
        _aspect = self.len_x / self.len_y if self.len_y != 0 else self.len_x / 0.0001
        self.aspect = round(_aspect, 4)
        _aspect_inverted = self.len_y / self.len_x if self.len_x != 0 else self.len_y / 0.0001
        self.aspect_inverted = round(_aspect_inverted, 4)

        self.shift_to_uv_area = Vector((0.5, 0.5)) - self.center

        if self.aspect > 1:
            self.is_vertical = False
        elif self.aspect < 1:
            self.is_vertical = True

        self.corners = [self.bot_left, self.top_left, self.top_right, self.bot_right, self.center]

    def get_as_dict(self):
        return {
            "tl": self.top_left,
            "tc": self.top_center,
            "tr": self.top_right,
            "lc": self.left_center,
            "cen": self.center,
            "rc": self.right_center,
            "bl": self.bot_left,
            "bc": self.bot_center,
            "br": self.bot_right,
            "U": self.len_x,
            "V": self.len_y,
            "len_x": self.len_x,
            "len_y": self.len_y,
            "aspect": self.aspect,
            "rect": (
                self.bot_left.x,
                self.top_left.y,
                self.top_right.x,
                self.bot_right.y
                ),
            "cen_h": self.center_horizontal,
            "cen_v": self.center_vertical,
        }

    def get_shortest_axis_len(self) -> float:
        return self.len_x if self.len_x < self.len_y else self.len_y

    def get_longest_axis_len(self) -> float:
        return self.len_x if self.len_x > self.len_y else self.len_y

    def get_other_axis_len(self, axis) -> float:
        return {'U': self.len_y, 'V': self.len_x}[axis]

    def get_shortest_axis_name(self) -> str:
        return 'U' if self.len_x < self.len_y else 'V'

    def get_longest_axis_name(self) -> str:
        return 'U' if self.len_x > self.len_y else 'V'

    def get_longest_axis_vector(self) -> Vector:
        return Vector((1.0, 0.0)) if self.len_x > self.len_y else Vector((0.0, 1.0))

    def get_shortest_axis_vector(self) -> Vector:
        return Vector((1.0, 0.0)) if self.len_x < self.len_y else Vector((0.0, 1.0))

    def _matrix_by_image_aspect(self, image_aspect):
        if image_aspect > 1.0:
            return Matrix.Diagonal((1, 1 / image_aspect))
        elif image_aspect < 1.0:
            return Matrix.Diagonal((image_aspect, 1))
        else:
            return Matrix.Diagonal((1, 1))

    def get_orient_angle(self, image_aspect):
        from ZenUV.utils.transform import zen_box_fit_2d
        if not len(self.points):
            print('Zen UV Warning: BoundingBox2d.points is empty.')
            return 0.0

        S = self._matrix_by_image_aspect(image_aspect)
        angle = zen_box_fit_2d([S @ p for p in self.points])

        if abs(angle) > pi / 2:
            if angle < 0:
                angle += pi / 2
            else:
                angle -= pi / 2
        if abs(angle) > pi / 4:
            if angle < 0:
                angle = pi / 2 + angle
            else:
                angle = - pi / 2 + angle

        return angle

    def get_orient_angle_with_threshold(self, image_aspect, threshold):
        scope = [self.len_x, self.len_y]
        aspect = round(min(scope) / max(scope), 3)
        if aspect > threshold:
            return 0.0
        else:
            return self.get_orient_angle(image_aspect)

    def is_circle(self):
        p_count = len(self.points)
        if p_count <= 4 or abs(self.aspect - self.aspect_inverted) > 0.065:
            return False
        scalar = 10 / (self.len_x + self.len_y)
        vecs = [(self.center - point) * scalar for point in self.points]
        mid_len = sum([vec.magnitude for vec in vecs]) / p_count
        difs = [0.04 > (vec.magnitude - mid_len) for vec in vecs]
        return False not in difs

    def intersect_uv_area(self):
        return not (min(self.top_right) <= 0.0 or max(self.self.bot_left) >= 1.0)

    def inside_of_bbox(self, master_bbox) -> bool:
        p_safe = BoundingBox2d.transform_safe_zone
        return False not in [
            self.rect[0] >= master_bbox.rect[0] - p_safe,
            self.rect[1] <= master_bbox.rect[1] + p_safe,
            self.rect[2] <= master_bbox.rect[2] + p_safe,
            self.rect[3] >= master_bbox.rect[3] - p_safe
            ]

    def inside_of_uv_area(self) -> bool:
        p_safe = BoundingBox2d.transform_safe_zone

        return False not in [
            self.rect[0] >= UV_AREA_BBOX.rect[0] - p_safe,
            self.rect[1] <= UV_AREA_BBOX.rect[1] + p_safe,
            self.rect[2] <= UV_AREA_BBOX.rect[2] + p_safe,
            self.rect[3] >= UV_AREA_BBOX.rect[3] - p_safe
            ]

    def _is_overlap(self, bl1, tr1, bl2, tr2):

        if bl1.x == tr1.x or bl1.y == tr1.y or tr2.x == bl2.x or bl2.y == tr2.y:
            return False
        if bl1.x > tr2.x or bl2.x > tr1.x:
            return False
        if tr1.y < bl2.y or tr2.y < bl1.y:
            return False
        return True

    def overlapped_with_bbox(self, master_bbox):
        return self._is_overlap(self.bot_left, self.top_right, master_bbox.bot_left, master_bbox.top_right)

    def moved(self, offset: Vector):
        if offset.magnitude == 0:
            return self
        return BoundingBox2d(points=np.array(self.points).reshape((-1, 2)) + offset)

    def show_bbox_points(self, bm):
        ''' Developer only '''
        verts = []
        for p in self.points:
            verts.append(bm.verts.new(p.resized(3)))

    def get_diff_scale_vec(self, other, margin: float = 0.0):
        from ZenUV.utils.transform import UvTransformUtils
        from ZenUV.ops.transform_sys.transform_utils.tr_fit_utils import TransformLoops
        return UvTransformUtils._get_scale_vec(
            TransformLoops.get_optimal_axis_name(self, other),
            single_axis=False,
            keep_proportion=True,
            i_bbox=self,
            fit_bbox=other,
            padding=margin
        )


class BBoxUtils:

    @classmethod
    def get_width_and_move_vec_from_island(cls, island, uv_layer) -> list:
        """ Returns scalar for set island 1.0 width and Vector to move island in the UV Area """
        return cls.get_width_and_move_vec_from_uvs([lp[uv_layer].uv for f in island for lp in f.loops])

    @classmethod
    def get_width_and_move_vec_from_loops(cls, loops, uv_layer) -> list:
        """ Returns scalar for set loops 1.0 width and Vector to move island in the UV Area """
        return cls.get_width_and_move_vec_from_uvs([lp[uv_layer].uv for lp in loops])

    @classmethod
    def get_width_and_move_vec_from_uvs(cls, uvs: list) -> list:
        from mathutils.geometry import convex_hull_2d

        if len(uvs) > 2:
            uvs = [uvs[i] for i in convex_hull_2d(uvs)]
        try:
            p_scalar = 1.0 / (max(uvs, key=lambda v: v.x).x - min(uvs, key=lambda v: v.x).x)
        except ZeroDivisionError:
            p_scalar = 1

        return p_scalar, Vector((0.0, 0.0)) - uvs[0] * p_scalar


def uv_area_bbox() -> BoundingBox2d:
    return BoundingBox2d(points=[Vector((0.0, 0.0)), Vector((1.0, 1.0))])


def get_overall_bbox(context: bpy.types.Context, from_islands: bool = False, as_dict: bool = True):
    objs = resort_objects_by_selection(context, context.objects_in_mode)
    uvs = []
    for obj in objs:
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        if uv_layer is None:
            continue
        if from_islands:
            uvs.extend([lp[uv_layer].uv.copy() for island in island_util.get_island(context, bm, uv_layer) for f in island for lp in f.loops])
        else:
            uvs.extend([lp[uv_layer].uv.copy() for lp in island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer)])
    if not len(uvs):
        if as_dict:
            return UV_AREA_BBOX.get_as_dict()
        else:
            return UV_AREA_BBOX
    if as_dict:
        return BoundingBox2d(points=uvs).get_as_dict()
    else:
        return BoundingBox2d(points=uvs)


def get_bbox_loops(context):
    objs = resort_objects_by_selection(context, context.objects_in_mode)
    bb = []
    for obj in objs:
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = verify_uv_layer(bm)
        loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer)
        points = [loop[uv_layer].uv for loop in loops]
        # islands = island_util.get_island(context, bm, uv_layer)
        if loops:
            cbbox = BoundingBox2d(points=points).get_as_dict()
            bb.extend((cbbox["bl"], cbbox["tr"]))
    gbb = BoundingBox2d(points=bb).get_as_dict()
    res = Vector((0.0, 0.0))
    for value in gbb.values():
        if isinstance(value, Vector):
            res += value
    if res == Vector((0.0, 0.0)):
        gbb = UV_AREA_BBOX.get_as_dict()
    return gbb


@dataclass
class BoundingBox2dSimple(SimpleBbox):
    points: List[Union[Tuple[float, float], Vector]] = field(default_factory=list)

    def __post_init__(self):

        if not isinstance(self.points, list):
            self.points = list(self.points)

        if len(self.points) > 2:
            self.points = [self.points[i] for i in convex_hull_2d(self.points)]

        min_x = min(p[0] for p in self.points)
        max_x = max(p[0] for p in self.points)
        min_y = min(p[1] for p in self.points)
        max_y = max(p[1] for p in self.points)

        self.bot_left = Vector((min_x, min_y))
        self.top_left = Vector((min_x, max_y))
        self.top_right = Vector((max_x, max_y))
        self.bot_right = Vector((max_x, min_y))

        self.corners = [
            self.bot_left, self.top_left,
            self.top_right, self.bot_right,
            self.center]

        self.center = (self.bot_left + self.top_right) * 0.5
        self.len_x = max_x - min_x
        self.len_y = max_y - min_y

        self.top_center = (self.top_left + self.top_right) * 0.5
        self.right_center = (self.top_right + self.bot_right) * 0.5
        self.bot_center = (self.bot_left + self.bot_right) * 0.5
        self.left_center = (self.bot_left + self.top_left) * 0.5

        self.rect = (
            self.bot_left.x,
            self.top_left.y,
            self.top_right.x,
            self.bot_right.y
        )

        self.aspect = self.len_x / self.len_y if self.len_y != 0 else self.len_x / 0.0001

    def __str__(self):
        values = vars(self)
        return "\nBoundingBox2dSimple\n" + "\n".join([f"{key} --> {value}" for key, value in values.items()])


class BoundingBoxUtils:

    @classmethod
    def show_by_face(cls, bbox, face, uv_layer):
        """ Debug purposes """
        if len(face.loops) != 4:
            raise RuntimeError('Quads accepted only')

        for i, lp in enumerate(face.loops):
            lp[uv_layer].uv = bbox.corners[i]

    @classmethod
    def get_orient_angle(cls, bounding_box: BoundingBox2dSimple, image_aspect: float):
        from ZenUV.utils.transform import zen_box_fit_2d
        from ZenUV.utils.transform import matrix_by_image_aspect
        if not len(bounding_box.points):
            raise RuntimeError('bounding_box.points is empty')

        if image_aspect != 1:
            S = matrix_by_image_aspect(image_aspect)
            angle = zen_box_fit_2d([S @ p for p in bounding_box.points])
        else:
            angle = zen_box_fit_2d([p for p in bounding_box.points])

        if abs(angle) > pi / 2:
            if angle < 0:
                angle += pi / 2
            else:
                angle -= pi / 2
        if abs(angle) > pi / 4:
            if angle < 0:
                angle = pi / 2 + angle
            else:
                angle = - pi / 2 + angle

        return angle

    @classmethod
    def rotate_by_matrix(cls, bounding_box: BoundingBox2dSimple, rotation_matrix: Matrix, pivot: Vector = None, ) -> BoundingBox2dSimple:
        pivot = bounding_box.center if pivot is None else pivot
        translation_to_zero = Matrix.Translation(-pivot.to_3d())
        translation_back = Matrix.Translation(pivot.to_3d())
        M = translation_back @ rotation_matrix.to_4x4() @ translation_to_zero
        return BoundingBox2dSimple(points=[(M @ point.to_3d()).to_2d() for point in bounding_box.points])

    @classmethod
    def rotate_by_angle(cls, bounding_box: BoundingBox2dSimple, angle: float, image_aspect_ratio, pivot: Vector = None, ) -> BoundingBox2dSimple:
        from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
        R = TransformLoops._get_rotation_matrix(angle, image_aspect_ratio)
        return cls.rotate_by_matrix(bounding_box, R, pivot)

    @classmethod
    def get_as_dict(cls, bounding_box: BoundingBox2dSimple):
        return {
            "tl": bounding_box.top_left,
            "tc": bounding_box.top_center,
            "tr": bounding_box.top_right,
            "lc": bounding_box.left_center,
            "cen": bounding_box.center,
            "rc": bounding_box.right_center,
            "bl": bounding_box.bot_left,
            "bc": bounding_box.bot_center,
            "br": bounding_box.bot_right,
            "U": bounding_box.len_x,
            "V": bounding_box.len_y,
            "len_x": bounding_box.len_x,
            "len_y": bounding_box.len_y,
            "aspect": bounding_box.aspect,
            "rect": (
                bounding_box.bot_left.x,
                bounding_box.top_left.y,
                bounding_box.top_right.x,
                bounding_box.bot_right.y
                ),
            "cen_h": bounding_box.center_horizontal,
            "cen_v": bounding_box.center_vertical,
        }
