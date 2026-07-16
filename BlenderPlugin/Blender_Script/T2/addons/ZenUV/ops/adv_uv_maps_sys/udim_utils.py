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

import bpy
import bmesh
import numpy as np

from ZenUV.utils.vlog import Log
from ZenUV.utils.generic import verify_uv_layer


class UdimFactory:

    result: bool = True
    message: str = ''
    report_style: str = 'FULL'  # In {'FULL', 'SHORT'}
    min_udim_number: int = 1001
    max_udim_number: int = 2000

    @classmethod
    def reset_report(cls):
        cls.result = True
        cls.message = ''

    @classmethod
    def get_active_image(cls, context):
        if context.area.type != 'IMAGE_EDITOR':
            cls.result = False
            cls.message = 'Switch to the UV Editing workspace.'
            return None

        active_image = context.area.spaces.active.image

        if active_image is None:
            cls.result = False
            cls.message = 'No active image in the UV Editor.'
            return None

        return active_image

    @classmethod
    def get_active_udim_tile(cls, context) -> bpy.types.UDIMTile:
        p_active_image = cls.get_active_image(context)
        if p_active_image is None:
            return None

        p_active_tile = p_active_image.tiles.active

        if not p_active_tile:
            cls.result = False
            cls.message = 'No Active UDIM tile'
            return None

        return p_active_tile

    @classmethod
    def remove_active_tile(cls, context: bpy.types.Context):
        p_active_image = cls.get_active_image(context)
        if p_active_image is None:
            cls.result = False
            cls.message = 'No Active Image'
            return None

        p_active_tile = p_active_image.tiles.active
        if p_active_tile is None:
            cls.result = False
            cls.message = 'No Active UDIM tile'
            return None

        p_active_image.tiles.remove(p_active_tile)

        return True

    @classmethod
    def get_active_image_udim_tiles_numbers(cls, context):
        p_active_image = cls.get_active_image(context)
        if p_active_image is None:
            return None

        return [t.number for t in p_active_image.tiles]

    @classmethod
    def get_active_image_udim_tiles(cls, context):
        p_active_image = cls.get_active_image(context)
        if p_active_image is None:
            return None

        return p_active_image.tiles

    @classmethod
    def set_active_udim_by_number(cls, context: bpy.types.Context, tile_number: int, create_if_absent: bool = False):
        p_active_image = cls.get_active_image(context)
        if p_active_image is None:
            return None
        p_tile = p_active_image.tiles.get(tile_number)

        # Fix bug when tile 1001 is absent
        if p_tile is not None:
            if tile_number == 1001 and p_tile.number != 1001:
                p_tile = None

        if p_tile is None:
            if not create_if_absent:
                cls.result = False
                if cls.report_style == 'FULL':
                    cls.message = f"Zen UV: UDIM tile {tile_number} not exist in the image tiles"
                else:
                    cls.message = "Zen UV: UDIM tile not exist"
                return False
            else:
                p_tile = p_active_image.tiles.new(tile_number)
                p_active_image.tiles.active = p_tile
                return True
        p_active_image.tiles.active = p_tile
        return True

    @classmethod
    def create_tile_by_number(cls, context: bpy.types.Context, tile_number: int) -> bpy.types.UDIMTile:
        p_active_image = cls.get_active_image(context)
        if p_active_image is None:
            return None
        if tile_number not in [t.number for t in p_active_image.tiles]:
            return p_active_image.tiles.new(tile_number)
        for t in p_active_image.tiles:
            if t.number == tile_number:
                return t
        return False

    @classmethod
    def get_udims_from_loops(cls, objs: list, groupped: bool = False) -> list:
        p_uv_co = []
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            p_uv_co.extend(cls.get_unique_uvs(bm, uv_layer))
        p_udims = cls.convert_uv_coords_to_udim_number(p_uv_co)

        if groupped:
            return cls.split_udims_by_groups(p_udims)
        return p_udims

    @classmethod
    def get_udims_from_selected_loops(cls, context: bpy.types.Context, objs: list, groupped: bool = False) -> list:
        import ZenUV.utils.get_uv_islands as island_util
        p_uv_co = []
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=False)
            p_uv_co.extend(list({lp[uv_layer].uv.copy().freeze() for lp in loops}))

        p_udims = cls.convert_uv_coords_to_udim_number(cls.filtering_uvs(p_uv_co))

        if groupped:
            return cls.split_udims_by_groups(p_udims)
        return p_udims

    @classmethod
    def get_unique_uvs(cls, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem):
        if uv_layer:
            return cls.filtering_uvs(list({lp[uv_layer].uv.copy().freeze() for f in bm.faces for lp in f.loops if not f.hide}))

    @classmethod
    def filtering_uvs(cls, uvs):
        uv = np.array(uvs)
        uv_ints = np.floor(uv).astype(int)
        uv_unic = np.unique(uv_ints, axis=0)
        return tuple(tuple((i[0]+1, i[1])) for i in uv_unic.tolist())

    @classmethod
    def convert_uv_coords_to_udim_number(cls, uvs: list):
        croped_to_udim_area = []
        for co in uvs:
            if 1 <= co[0] <= 10 and 0 <= co[1] < 99:
                croped_to_udim_area.append(co)
        return sorted([i[0]+(i[1]*10)+1000 for i in croped_to_udim_area])

    @classmethod
    def split_udims_by_groups(cls, udims: list):
        result = []
        sublist = [udims[0]]
        for i in range(1, len(udims)):
            if udims[i] - udims[i-1] == 1:
                sublist.append(udims[i])
            else:
                result.append(sublist)
                sublist = [udims[i]]
        result.append(sublist)
        return result

    @classmethod
    def is_udim_number_valid(cls, udim_number) -> bool:
        return type(udim_number) == int and cls.min_udim_number <= udim_number <= cls.max_udim_number

    @classmethod
    def convert_udim_name_to_id(cls, udim_number: int):
        if cls.is_udim_number_valid(udim_number):
            return [(udim_number - 1001) % 10, (udim_number - 1001) // 10]
        else:
            raise RuntimeError('udim_name is not legal name ot the udim tile')

    @classmethod
    def int_to_udim(cls, tile_index):
        """
        Converts an integer to a UDIM tile number.

        :param tile_index: The tile index (0-based).
        :return: The corresponding UDIM tile number.
        """
        column = tile_index % 10
        row = tile_index // 10
        udim = 1001 + column + (row * 10)
        return udim

    @classmethod
    def udim_to_uv(cls, udim_tile_number):
        """
        Converts a UDIM tile number to the UV coordinates of the left bottom corner.

        :param udim_tile_number: The UDIM tile number (e.g., 1001).
        :return: A tuple representing the UV coordinates of the left bottom corner.
        """
        # Calculate the 0-based tile index
        tile_index = udim_tile_number - 1001

        column = tile_index % 10
        row = tile_index // 10

        uv_u = column
        uv_v = row

        return (uv_u, uv_v)

    @classmethod
    def get_bbox_of_udim(cls, udim_number):
        from ZenUV.utils.bounding_box import BoundingBox2d
        p_start_co = cls.convert_udim_name_to_id(udim_number)
        return BoundingBox2d(
            points=(
                p_start_co,
                (p_start_co[0] + 1, p_start_co[1] + 1)))

    @classmethod
    def split_range_into_sublists(cls, start, end, n):
        result = []
        current_value = start
        while current_value <= end:
            sublist = list(range(current_value, min(current_value + n, end + 1)))
            result.append(sublist)
            current_value += n
        return result


if __name__ == "__main__":
    pass
