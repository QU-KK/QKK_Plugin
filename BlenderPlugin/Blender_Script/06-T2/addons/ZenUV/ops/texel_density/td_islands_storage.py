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

""" Zen UV Texel Density Objects Storage """

import bpy
from mathutils import Color
from dataclasses import dataclass, field, fields
from mathutils import Vector

from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
from ZenUV.utils.vlog import Log


class UnitsProcessor:

    def __init__(self) -> None:
        pass

    def set_values(self, value: Vector):
        self.x = value[0]
        self.y = value[1]


@dataclass
class Pixels(UnitsProcessor):

    x: float = 0.0
    y: float = 0.0


@dataclass
class Units(UnitsProcessor):

    x: float = 0.0
    y: float = 0.0


class IslandSize:

    def __init__(self, texture_x: float, texture_y: float, bbox: BoundingBox2d) -> None:

        self.units: Units = Units(x=bbox.len_x, y=bbox.len_y)

        self.pixels: Pixels = Pixels(x=texture_x * self.units.x, y=texture_y * self.units.y)

    def __str__(self) -> str:
        return f'Island size:\n{self.units.x} u\n{self.units.y} u\n{self.pixels.x} px\n{self.pixels.y} px'

    def set_size(self, context: bpy.types.Context, size: Vector):
        td_props = context.scene.zen_uv.td_props
        if td_props.sz_units == 'PIXELS':
            self.pixels.set_values(size)
        elif td_props.sz_units == 'UNITS':
            self.units.set_values(size)


@dataclass
class TdIsland:


    index: int = -1
    name: str = 'TdIsland'
    indices: list = field(default_factory=list)
    obj_name: str = None
    td: float = 0.0
    color: Color = Color((0.0, 0.0, 0.0))
    is_fake: bool = False
    color_ref_point: bool = False

    size: IslandSize = None

    def __hash__(self):
        return hash(self.td)

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, type(self)):
            return NotImplemented
        return self.td == __o.td

    def __str__(self):
        only_fake = False
        if only_fake:
            if self.is_fake is True:
                s = ', '.join(
                    f'{field.name}={getattr(self, field.name)!r}'
                    for field in fields(self)
                    if field.name not in {'indices', 'index', 'name', 'obj_name'})
                # if getattr(self, field.name) != field.default)
                return f'{type(self).__name__}({s})'
            else:
                return '-'
        else:
            s = ', '.join(
                f'{field.name}={getattr(self, field.name)!r}'
                for field in fields(self)
                if field.name not in {'indices', 'index', 'name', 'obj_name'})
            return f'{type(self).__name__}({s})'


class TdReferencedManager:

    def __init__(self) -> None:

        self.ref_td: list = []
        self.ref_colors: list = []

    def append_color_scheme_reference_values(self, colors: list, td_min: float, td_max: float):
        from ZenUV.utils.generic import generate_range_values

        p_r_td_values = generate_range_values(td_min, td_max, len(colors))

        for td, col in zip(p_r_td_values, colors):
            self.append_reference(td=td, color=col, color_ref_point=True)

    def append_reference(self, td: float, color: Color, color_ref_point: bool = False) -> None:
        self.islands.append(TdIsland(td=td, color=color, is_fake=True, color_ref_point=color_ref_point))
        self.sort()

    def remove_referenced_items(self) -> None:
        self.islands = [i for i in self.islands if i.is_fake is False]

    def get_referenced_values_for_gradient(self, td_inputs) -> tuple[list, list]:

        p_islands = [i for i in self.islands if i.is_fake]

        p_islands = sorted(p_islands, key=lambda island: island.td)

        return [round(i.td, td_inputs.round_value) for i in p_islands], [i.color for i in p_islands]


class TdIslandsStorage(TdReferencedManager):

    def __init__(self) -> None:
        super().__init__()

        self.islands: list = []

    def show(self):
        print('\nTdIslandsStorage State:\n')
        for i in self.islands:
            print(i)

    def count(self):
        return len(self.islands)

    def show_colors(self):
        print('\nTdIslandsStorage Colors:\n')
        print([i.color for i in self.islands])

    def update_indexes(self):
        for idx, i in enumerate(self.islands):
            i.index = idx

    def show_td_color_chart(self, include_black=True):
        print('\nTdIslandsStorage TD - Color chart:\n')
        if include_black:
            print(''.join([str(i.td) + str(i.color) + '\n' for i in self.islands]))
        else:
            print(''.join([str(i.td) + str(i.color) + '\n' for i in self.islands if i.color != [0.0, 0.0, 0.0]]))

    def is_empty(self) -> bool:
        return not len(self.islands)

    def clear(self) -> None:
        self.islands.clear()

    def append(self, island: TdIsland) -> None:
        island.td = round(island.td, 2)
        self.islands.append(island)

    def get(self) -> list:
        return self.islands

    def get_colors(self, include_fake=False):
        if include_fake:
            self.sort()
            return [i.color for i in self.islands]
        else:
            self.sort()
            return [i.color for i in self.islands if not i.is_fake]

    def reset_colors(self):
        for i in self.islands:
            i.color = [0.0, 0.0, 0.0]

    def set_color(self, color):
        for i in self.islands:
            i.color = color

    def get_min_td_island(self) -> TdIsland:
        return min(self.islands, key=lambda island: island.td)

    def get_max_td_island(self) -> TdIsland:
        return max(self.islands, key=lambda island: island.td)

    def get_max_td_value(self) -> float:
        return max([i.td for i in self.islands])

    def get_min_td_value(self) -> float:
        return min([i.td for i in self.islands])

    def is_td_uniform(self):
        return self.get_min_td_value() == self.get_max_td_value()

    def get_all_td_values(self, include_fake=False) -> list:
        if include_fake:
            return sorted(round(i.td, 2) for i in self.islands)
        else:
            return sorted(round(i.td, 2) for i in self.islands if not i.is_fake)

    def _remove_doubles(self, _sorted=False):
        if _sorted:
            return sorted(list(set(self.islands)), key=lambda island: island.td)
        else:
            return list(set(self.islands))

    def get_sorted_islands(self) -> list:
        return sorted(self.islands, key=lambda island: island.td)

    def get_sorted_td_values(self, rounded: bool = True) -> list:
        if not len(self.islands):
            self._fill_fake_values()
        if rounded:
            return [round(v, 2) for v in self.get_all_td_values()]
        else:
            return self.get_all_td_values()

    def _fill_fake_values(self):
        for p_td in [0.0, 0.5, 1.0]:
            self.islands.append(TdIsland(td=p_td))

    def get_unique_td_values(self):
        return list(set(self.get_sorted_td_values()))

    def get_islands_by_objects(self) -> dict:
        p_output = dict()
        for p_obj_name in {i.obj_name for i in self.islands}:
            if p_obj_name is None:
                continue
            p_output.update({p_obj_name: [island for island in self.islands if island.obj_name == p_obj_name]})
        return p_output

    def get_mid_td_value(self) -> float:
        p_calc_mid = sum(island.td for island in self.islands) / len(self.islands)
        return min(self.islands, key=lambda island: abs(island.td - p_calc_mid)).td

    def get_mid_td_island(self) -> TdIsland:
        p_calc_mid = self.get_mid_td_value()
        return min(self.islands, key=lambda island: abs(island.td - p_calc_mid))

    def get_island_by_value(self, value, method: str = 'EXACT') -> TdIsland:
        """
        method: in {'EXACT', 'NEAR'}
        return TdIsland or None
        """
        if method == 'EXACT':
            return next((i for i in self.islands if i.td == value), None)
        elif method == 'NEAR':
            return min(self.islands, key=lambda island: abs(island.td - value))

    def sort(self) -> None:
        self.islands = self.get_sorted_islands()

    def set_color_to_islands(self, colors: list):
        self.sort()
        for i, color in zip(self.islands, colors):
            i.color = Color(color)

    def get_islands_in_td_range(self, td_min, td_max) -> list:
        self.sort()
        return [i for i in self.islands if td_min <= i.td <= td_max]

    def get_objs_names(self) -> list:
        return list({i.obj_name for i in self.islands})

    def get_islands_in_size_range(self, size_min, size_max, td_inputs) -> list:
        self.sort()
        size_units = td_inputs.sz_units
        axis = td_inputs.sz_active_axis_list

        if size_units == 'UNITS':
            if axis == [True, False]:
                return [i for i in self.islands if size_min <= i.size.units.x <= size_max]
            elif axis == [False, True]:
                return [i for i in self.islands if size_min <= i.size.units.y <= size_max]
            elif axis == [True, True]:
                return [i for i in self.islands if size_min <= i.size.units.x <= size_max or size_min <= i.size.units.y <= size_max]
            else:
                raise RuntimeError('arg axis not in ["X", "Y", "ANY"]')
        elif size_units == 'PIXELS':
            if axis == [True, False]:
                return [i for i in self.islands if size_min <= i.size.pixels.x <= size_max]
            elif axis == [False, True]:
                return [i for i in self.islands if size_min <= i.size.pixels.y <= size_max]
            elif axis == [True, True]:
                return [i for i in self.islands if size_min <= i.size.pixels.x <= size_max or size_min <= i.size.pixels.y <= size_max]
            else:
                raise RuntimeError('arg axis not in ["X", "Y", "ANY"]')
        else:
            raise RuntimeError('arg influence not in ["UNITS", "PIXELS"]')


@dataclass
class TdPreset:


    index: int = -1
    td: float = 0.0
    color: Color = Color((0.0, 0.0, 0.0))
    is_fake: bool = False

    def __str__(self):
        return '\nTdPreset\n' + "\n".join([f"{key} --> {value}" for key, value in self.__annotations__.items()])


class TdPresetsStorage:


    presets: list = []

    @classmethod
    def show(cls):
        print('\nTdPresetsStorage State:\n')
        for i in cls.presets:
            print(i)

    @classmethod
    def is_empty(cls):
        return len(cls.presets) == 0

    @classmethod
    def clear(cls) -> None:
        cls.presets.clear()

    @classmethod
    def append(cls, preset: TdPreset) -> None:
        cls.presets.append(preset)

    @classmethod
    def get_all_td_values(cls) -> list:
        cls.sort()
        return sorted(i.td for i in cls.presets)

    @classmethod
    def sort(cls) -> None:
        cls.presets = cls.get_sorted_presets()

    @classmethod
    def get_sorted_presets(cls) -> list:
        return sorted(cls.presets, key=lambda preset: preset.td)

    @classmethod
    def get_colors(cls):
        cls.sort()
        return [i.color for i in cls.presets]

    @classmethod
    def append_reference(cls, td: float):
        cls.presets.append(TdPreset(td=td, is_fake=True))
        cls.sort()

    @classmethod
    def remove_referenced_items(cls):
        cls.presets = [pr for pr in cls.presets if pr.is_fake is False]

    @classmethod
    def collect_presets(cls, context: bpy.types.Context) -> bool:
        if len(context.scene.zen_tdpr_list) == 0:
            return False
        else:
            cls.clear()
            for pr in context.scene.zen_tdpr_list:
                cls.append(
                    TdPreset(
                        index=-1,
                        td=round(pr.value, 2),
                        color=pr.display_color))
            return True

    @classmethod
    def get_presets_td_range(cls):
        p_full = [p.td for p in cls.presets]
        return min(p_full), max(p_full)


class TdDataStorage:

    """ Global Texel Density data Storage """

    Scope: TdIslandsStorage = None
    objs: list = []
    td_inputs = None
    sz_inputs = None
    min_range: float = 0.0
    max_range: float = 0.0
    i_count: int = 0

    @classmethod
    def clear(cls):
        cls.Scope = None
        cls.objs = []
        cls.td_inputs = None
        cls.sz_inputs = None
        cls.min_range = 0.0
        cls.max_range = 0.0
        cls.i_count = 0

    @classmethod
    def is_empty(cls):
        return cls.Scope is None or cls.Scope.is_empty()

    @classmethod
    def check_inputs(cls, context: bpy.types.Context):
        p_objects = resort_by_type_mesh_in_edit_mode_and_sel(context)

        b_is_obj_mode = context.object.mode == 'OBJECT'
        if ((cls.td_inputs is None) or
                (cls.td_inputs.obj_mode == b_is_obj_mode) or
                (set(p_objects) == set(cls.objs))):

            from .td_utils import TdContext
            cls.objs = p_objects
            cls.td_inputs = TdContext(context)
            cls.td_inputs.obj_mode = b_is_obj_mode

    @classmethod
    def calc_td_scope(cls, context: bpy.types.Context, td_influence):
        from .td_utils import TdUtils

        cls.check_inputs(context)

        cls.Scope = TdUtils.get_td_data_with_precision(context, cls.objs, cls.td_inputs, td_influence)

    @classmethod
    def calc_size_scope(cls, context: bpy.types.Context, influence):
        from .td_utils import TdUtils

        cls.check_inputs(context)

        cls.Scope = TdUtils.get_sizes_data(context, cls.objs, cls.td_inputs, influence)


if __name__ == '__main__':
    pass
