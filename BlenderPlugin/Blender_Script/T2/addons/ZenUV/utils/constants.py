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


from dataclasses import dataclass, field, asdict
from mathutils import Vector
from ZenUV.ui.labels import ZuvLabels

ADDON_NAME = "ZenUV"

zenuv_update_filename = "ZenUV_*.zip"
zenuv_update_filter = "*ZenUV*.zip"

u_axis = Vector((1.0, 0.0))
u_axis_negative = Vector((-1.0, 0.0))
v_axis = Vector((0.0, 1.0))
v_axis_negative = Vector((0.0, -1.0))

ALL_AXES_SCOPE = (
    u_axis,
    u_axis_negative,
    v_axis,
    v_axis_negative
)

FACE_UV_AREA_MULT = 100000

ADV_UV_MAP_NAME_PATTERN = "UVChannel_"

ZUV_COPIED = "ZUV_Copied_UV"
ZUV_STORED = "ZUV_Stored_UV"

TEST_OBJ_NAME_CUBE = 'ZenUvTestCube'
TEST_OBJ_NAME_CYLINDER = 'ZenUvTestCylinder'

PACK_EXCLUDED_FACEMAP_NAME = "ZenUV_PackExcluded"
PACK_EXCLUDED_V_MAP_NAME = "zen_uv_pack_excluded"

GREASE_PEN_DATA_NAME: str = 'ZenFitRegion'
GREASE_PEN_LAYER_NAME: str = "Current Fit Region"


@dataclass
class UV_AREA_BBOX:

    bbox_type = 'UV Area BBOX'

    bbox_all_handles = ('bl', 'tl', 'tr', 'br', 'cen', 'tc', 'rc', 'bc', 'lc')
    bbox_circle_ordered_handles = ('rc', 'tr', 'tc', 'tl', 'lc', 'bl', 'bc', 'br')
    bbox_middle_handles = ('tc', 'rc', 'bc', 'lc')
    bbox_vertical_handles = ('tc', 'bc')
    bbox_horizontal_handles = ('lc', 'rc')
    bbox_corner_handles = ('bl', 'tl', 'tr', 'br')
    bbox_bottom_left = 'bl'
    bbox_not_bottom_left = ('tl', 'tr', 'br')

    bl: Vector = Vector((0.0, 0.0))
    tl: Vector = Vector((0.0, 1.0))
    tr: Vector = Vector((1.0, 1.0))
    br: Vector = Vector((1.0, 0.0))
    cen: Vector = Vector((0.5, 0.5))
    tc: Vector = Vector((0.5, 1.0))
    rc: Vector = Vector((1.0, 0.5))
    bc: Vector = Vector((0.5, 0.0))
    lc: Vector = Vector((0.0, 0.5))

    rect: tuple = (0.0, 1.0, 1.0, 0.0)

    len_x: int = 1.0
    len_y: int = 1.0

    cen_h: Vector = Vector((0.5, 0.5))
    cen_v: Vector = Vector((0.5, 0.5))

    aspect: float = 1.0

    _corners: list = field(default_factory=list)

    def get_shortest_axis_len(self) -> float:
        return self.len_x

    def get_longest_axis_len(self) -> float:
        return self.len_x

    @classmethod
    def get_vector_by_direction(self, position: str):
        if position in self.__annotations__.keys():
            return getattr(self, position)

    @property
    def corners(self) -> list:
        return (self.bl, self.tl, self.tr, self.br, self.cen)

    @corners.setter
    def corners(self):
        raise RuntimeError('corners read only')

    @classmethod
    def get_as_dict(self):
        bbox = UV_AREA_BBOX()
        _as_dict = asdict(bbox)
        del _as_dict['_corners']
        _as_dict.update({'corners': bbox.corners})
        return _as_dict

    def show_bbox_dict(self):
        print(f"\n{self.bbox_type} state:\n\n", ''.join(f"{key}: {val}\n" for key, val in self.get_as_dict().items()))

    @classmethod
    def is_direction_vertical(cls, direction: str):
        return direction in cls.bbox_vertical_handles

    @classmethod
    def is_direction_horizontal(cls, direction: str):
        return direction in cls.bbox_horizontal_handles

    @classmethod
    def get_bbox_with_center_in(cls, center: Vector = Vector((0.5, 0.5))):
        b = UV_AREA_BBOX()

        if center != b.cen:
            b_dif = center - b.cen

            b.bl = b.bl + b_dif
            b.tl = b.tl + b_dif
            b.tr = b.tr + b_dif
            b.br = b.br + b_dif
            b.cen = b.cen + b_dif
            b.tc = b.tc + b_dif
            b.rc = b.rc + b_dif
            b.bc = b.bc + b_dif
            b.lc = b.lc + b_dif

            b.cen_h = b.cen_h + b_dif
            b.cen_v = b.cen_v + b_dif
        return b


class Planes:

    x3 = Vector((1, 0, 0))
    y3 = Vector((0, 1, 0))
    z3 = Vector((0, 0, 1))

    x3_negative = Vector((-1.0, 0.0, 0.0))
    y3_negative = Vector((0.0, -1.0, 0.0))
    z3_negative = Vector((0.0, 0.0, -1.0))

    axis_x = Vector((1, 0))
    axis_y = Vector((0, 1))

    pool_3d_dict = {
        "x": x3,
        "y": y3,
        "z": z3,
        "-x": x3_negative,
        "-y": y3_negative,
        "-z": z3_negative
    }

    pool_3d_orient_dict = {
        "x": x3,
        "y": y3,
        # "z": z3,
        "-x": x3_negative,
        "-y": y3_negative,
        # "-z": z3_negative
    }

    pool_3d = (
        x3,
        y3,
        z3,
        x3_negative,
        y3_negative,
        z3_negative
    )
    pool_2d = (axis_x, axis_y)


class UiConstants:

    unified_mark_enum = [
            ("SEAM_BY_UV_BORDER", ZuvLabels.MARK_BY_BORDER_LABEL, ZuvLabels.MARK_BY_BORDER_DESC),
            ("SHARP_BY_UV_BORDER", ZuvLabels.MARK_SHARP_BY_BORDER_LABEL, ZuvLabels.MARK_SHARP_BY_BORDER_DESC),
            ("SEAM_BY_SHARP", ZuvLabels.SEAM_BY_SHARP_LABEL, ZuvLabels.SEAM_BY_SHARP_DESC),
            ("SHARP_BY_SEAM", ZuvLabels.SHARP_BY_SEAM_LABEL, ZuvLabels.SHARP_BY_SEAM_DESC),
            ("SEAM_BY_OPEN_EDGES", ZuvLabels.SEAM_BY_OPEN_EDGES_LABEL, ZuvLabels.SEAM_BY_OPEN_EDGES_DESC),
        ]
