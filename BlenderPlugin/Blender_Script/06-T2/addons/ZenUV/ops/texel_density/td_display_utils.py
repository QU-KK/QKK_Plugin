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

""" Zen UV Texel Density Display utilities"""

import bpy
from dataclasses import dataclass
from mathutils import Color

from .td_utils import TdContext
from .td_islands_storage import TdIslandsStorage, TdPresetsStorage

from ZenUV.utils.vlog import Log


class TdColorManager:


    color_scheme_names = {
        "USER_THREE",
        "FULL_SPEC",
        "REVERSED_SPEC",
        "USER_LINEAR",
        "MONO"
        }

    black = [0.0, 0.0, 0.0]
    white = [1.0, 1.0, 1.0]

    full: list = [
        (0.0, 0.0, 1.0),

        (0.0, 0.5, 1.0),
        (0.0, 1.0, 1.0),

        (0.5, 1.0, 0.5),

        (1.0, 1.0, 0.0),
        (1.0, 0.5, 0.0),

        (1.0, 0.0, 0.0),
    ]
    mono = [
            (0.0, 0.0, 0.0),
            (0.5, 0.5, 0.5),
            (0.9, 0.9, 0.9)]

    three_default = [
            (0.0, 0.0, 1.0),
            (0.0, 1.0, 0.0),
            (1.0, 0.0, 0.0)]

    empty_black = [[0.0, 0.0, 0.0], ] * 3

    alert_purple = (1.0, 0.0, 1.0)
    alert_green = (0.0, 1.0, 0.0)

    area_stretch: list = [
        (1.0, 0.0, 0.0),
        (1.0, 0.5, 0.0),
        (1.0, 1.0, 0.0),
        (0.5, 1.0, 0.5),
        (0.0, 1.0, 1.0),
        (0.0, 0.5, 1.0),
        # (0.0, 0.0, 1.0)

        (0.0, 0.0, 1.0),

        (0.0, 0.5, 1.0),
        (0.0, 1.0, 1.0),

        (0.5, 1.0, 0.5),

        (1.0, 1.0, 0.0),
        (1.0, 0.5, 0.0),

        (1.0, 0.0, 0.0),
    ]

    @property
    def over_under(cls):
        p_colors = cls.full.copy()
        p_colors.insert(cls.black)
        p_colors.append(cls.white)
        return p_colors

    @classmethod
    def get_mid_color(cls, context: bpy.types.Context, color_scheme_name: str) -> list:
        if color_scheme_name == "USER_THREE":
            return cls.get_user_equal(context)
        elif color_scheme_name == "FULL_SPEC":
            return cls.full[3]
        elif color_scheme_name == "REVERSED_SPEC":
            return cls.full[3]
        elif color_scheme_name == "USER_LINEAR":
            return cls.get_user_linear(context)[1]
        elif color_scheme_name == "MONO":
            return cls.mono[1]
        else:
            mes = f'color scheme name not in {cls.color_scheme_names}'
            raise RuntimeError(mes)

    @classmethod
    def get_middle_color(cls, color_01: Color, color_02: Color) -> Color:
        return ((Color(color_01) + Color(color_02)) * 0.5)[:]

    @classmethod
    def get_user_three(cls, context: bpy.types.Context) -> list:
        cl = context.scene.zen_uv.td_props.colors
        return [cl.col_less[:], cl.col_equal[:], cl.col_over[:]]

    @classmethod
    def get_user_equal(cls, context: bpy.types.Context) -> list:
        return context.scene.zen_uv.td_props.colors.col_equal[:]

    @classmethod
    def get_user_linear(cls, context: bpy.types.Context):
        cl = context.scene.zen_uv.td_props.colors
        p_col_sch = cls.get_user_three(context)
        p_col_sch[1] = cls.get_middle_color(cl.col_less.copy(), cl.col_over.copy())
        return p_col_sch


class TdRangesMapper:

    @classmethod
    def calc_remap(cls, td_values, colors, range_limits=[0.0, 0.0]):

        td_min, td_max = range_limits[0], range_limits[1]

        if td_min == td_max:
            td_max += 1

        if range_limits[-1] > td_values[-1]:
            td_values.append(range_limits[-1])
        if range_limits[0] < td_values[0]:
            td_values.insert(0, range_limits[0])
        indices = []
        alphas = []
        result_colors = []

        for td in td_values:

            td_clamped = max(td_min, min(td_max, td))

            index = int((td_clamped - td_min) / (td_max - td_min) * (len(colors) - 1))
            alpha = (td_clamped - td_min) / (td_max - td_min) * (len(colors) - 1) - index

            indices.append(index)
            alphas.append(alpha)

            if index == len(colors) - 1:
                result_colors.append(colors[-1])
            else:
                color = [(1 - alpha) * c1 + alpha * c2 for c1, c2 in zip(colors[index], colors[index + 1])]
                result_colors.append(color)

        return result_colors

    @classmethod
    def calc_remap_balanced(cls, SCOPE: TdIslandsStorage, base_value: float, mesh_limits: list = [0.0, 0.0]) -> TdIslandsStorage:

        td_min = mesh_limits[0]
        td_max = mesh_limits[1]

        colors = [c for c in SCOPE.get_colors(include_fake=True) if c != TdColorManager.black]

        SCOPE.append_color_scheme_reference_values(colors, td_min, td_max)

        if len(colors) == 1:
            colors *= 2

        for it in SCOPE.get_islands_in_td_range(td_min, base_value):
            it.color = cls._calc_island_color(td_min, base_value, colors[:2], it.td)

        for it in SCOPE.get_islands_in_td_range(base_value, td_max):
            it.color = cls._calc_island_color(base_value, td_max, colors[1:], it.td)

        return SCOPE

    @classmethod
    def calc_remap_scope(cls, td_inputs: TdContext, SCOPE: TdIslandsStorage, colors: list, range_limits=[0.0, 0.0], mesh_limits=[0.0, 0.0]):

        # SCOPE.remove_referenced_items()

        td_min = mesh_limits[0]
        td_max = mesh_limits[1]

        if td_min >= td_max:
            td_max += 1

        SCOPE.append_color_scheme_reference_values(colors, td_min, td_max)

        underrated = False
        overrated = False

        for isl in SCOPE.islands:

            if isl.td < range_limits[0]:
                isl.color = TdColorManager.black
                if not underrated:
                    underrated = True
                    SCOPE.append_reference(td=range_limits[0], color=TdColorManager.black)
                    SCOPE.append_reference(td=range_limits[0] - 0.01, color=TdColorManager.black)

            elif isl.td > range_limits[1]:
                isl.color = TdColorManager.white
                if not overrated:
                    overrated = True
                    SCOPE.append_reference(td=range_limits[1] - 0.01, color=cls._calc_island_color(td_min, td_max, colors, isl.td))
                    SCOPE.append_reference(td=range_limits[1], color=TdColorManager.white)

            else:
                isl.color = cls._calc_island_color(td_min, td_max, colors, isl.td)

        return SCOPE

    @classmethod
    def calc_remap_presets(cls, SCOPE: TdIslandsStorage, colors: list, range_limits: list = [0.0, 0.0]) -> TdIslandsStorage:

        td_min = range_limits[0]
        td_max = range_limits[-1]

        if td_min == td_max:
            td_max += 1

        underrated = False
        overrated = False

        for it in SCOPE.islands:
            if it.td < range_limits[0]:
                it.color = TdColorManager.black
                if not underrated:
                    underrated = True
                    SCOPE.append_reference(td=it.td, color=colors[0], color_ref_point=True)

            elif it.td > range_limits[1]:
                it.color = TdColorManager.white
                if not overrated:
                    overrated = True
                    SCOPE.append_reference(td=it.td, color=TdColorManager.white, color_ref_point=True)
            else:
                it.color = cls._calc_island_color(td_min, td_max, colors, it.td)

        return SCOPE

    @classmethod
    def _calc_island_color(cls, td_min: float, td_max: float, colors: list, island_td: float) -> None:

        td_clamped = max(td_min, min(td_max, island_td))
        p_val = td_max - td_min
        if p_val == 0:
            p_val = 1

        index = int((td_clamped - td_min) / p_val * (len(colors) - 1))
        alpha = (td_clamped - td_min) / p_val * (len(colors) - 1) - index

        if index == len(colors) - 1:
            return colors[-1]
        else:
            return [(1 - alpha) * c1 + alpha * c2 for c1, c2 in zip(colors[index], colors[index + 1])]


class TdDisplayLimits:


    cl_td_limits: list = [0.0, 0.0]

    @classmethod
    @property
    def upper_limit(cls):
        return round(cls.cl_td_limits[1], 2)

    @classmethod
    @property
    def lower_limit(cls):
        return round(cls.cl_td_limits[0], 2)

    @classmethod
    @property
    def middle(cls):
        return round(cls.cl_td_limits[0] + ((cls.cl_td_limits[1] - cls.cl_td_limits[0]) / 2), 2)

    @classmethod
    def is_limits_are_equal(cls) -> bool:
        return cls.cl_td_limits[0] == cls.cl_td_limits[1]


class TdDisplaySpectrumFactory:

    def __init__(self) -> None:

        self.color_scheme: list = []
        self.color_scheme_name: str

        self.mesh_limits: list = []
        self.pr_td_limits: list = [0.0, 0.0]

        self.is_td_uniform: bool = False

    def calc_spectrum(self, context: bpy.types.Context, td_inputs: TdContext, SCOPE: TdIslandsStorage, color_scheme: list, color_scheme_name: str, pr_td_limits: list, mesh_limits: list):

        self.color_scheme = color_scheme.copy()
        self.pr_td_limits = pr_td_limits
        self.mesh_limits = mesh_limits
        self.color_scheme_name = color_scheme_name

        if SCOPE.is_td_uniform():
            self.is_td_uniform = True
            p_color = TdColorManager.get_mid_color(context, color_scheme_name=color_scheme_name)
            SCOPE.set_color(p_color)
            return SCOPE

        TdRangesMapper.calc_remap_scope(
            td_inputs,
            SCOPE,
            self.color_scheme,
            range_limits=self.pr_td_limits,
            mesh_limits=self.mesh_limits)

        self.update_by_user_limits(SCOPE)

        return SCOPE

    def update_by_user_limits(self, SCOPE: TdIslandsStorage):
        p_min_td = self.mesh_limits[0]
        p_max_td = self.mesh_limits[1]

        if self.pr_td_limits[0] < p_min_td:
            if self.color_scheme_name == 'MONO':
                p_color = TdColorManager.alert_green
            else:
                p_color = TdColorManager.black
            SCOPE.append_reference(self.pr_td_limits[0], color=p_color)
            SCOPE.append_reference(p_min_td - 0.01, color=p_color)

        if self.pr_td_limits[1] > p_max_td:
            if self.color_scheme_name == 'MONO':
                p_color = TdColorManager.alert_purple
            else:
                p_color = TdColorManager.black
            SCOPE.append_reference(p_max_td + 0.01, color=p_color)
            SCOPE.append_reference(self.pr_td_limits[1], color=p_color)

        SCOPE.sort()

    def set_gradient_values(self, context: bpy.types.Context, td_inputs: TdContext, SCOPE: TdIslandsStorage, values_filter: float):
        from ZenUV.ui.gizmo_draw import GradientProperties

        if self.is_td_uniform:
            p_td_values, p_colors = TdSysUtils.get_gradient_values_for_uniform_td(context, td_inputs, self.color_scheme_name)
        else:
            p_td_values, p_colors = SCOPE.get_referenced_values_for_gradient(td_inputs)

        GradientProperties.range_values = p_td_values
        GradientProperties.range_colors = p_colors
        GradientProperties.range_labels = TdSysUtils.td_labels_filter(p_td_values, values_filter)


class TdDisplayPresetsFactory:

    def __init__(self) -> None:

        self.color_scheme: list = []
        self.presets_td_values: list = []

        self.is_td_uniform: bool = False

    def calc_presets(self, context: bpy.types.Context, SCOPE: TdIslandsStorage, use_presets_only: bool):

        self.collect_presets(context)


        if self.presets_td_values == [0.0, 0.0]:
            SCOPE.set_color(self.color_scheme[0])
        else:
            SCOPE = TdRangesMapper.calc_remap_presets(
                SCOPE,
                colors=self.color_scheme,
                range_limits=(self.presets_td_values[0], self.presets_td_values[-1]))
            if use_presets_only:
                for island in SCOPE.islands:
                    if round(island.td, 2) not in self.presets_td_values:
                        island.color = TdColorManager.black

        return SCOPE

    def collect_presets(self, context: bpy.types.Context) -> None:
        if len(context.scene.zen_tdpr_list) == 0:
            self.presets_td_values = [0.0, 0.0]
            self.color_scheme = [TdColorManager.alert_purple] * 2
        else:
            TdPresetsStorage.clear()
            TdPresetsStorage.collect_presets(context)

            self.presets_td_values = TdPresetsStorage.get_all_td_values()
            self.color_scheme = TdPresetsStorage.get_colors()


    def set_gradient_values(self, td_inputs: TdContext, SCOPE: TdIslandsStorage, values_filter):
        from ZenUV.ui.gizmo_draw import GradientProperties
        from .td_islands_storage import TdIsland

        for td, col in zip(self.presets_td_values, self.color_scheme):
            SCOPE.append(TdIsland(td=td, color=col, color_ref_point=True, is_fake=True))

        # print(SCOPE.show())

        if SCOPE.is_td_uniform():
            p_td_values = self.presets_td_values
            p_colors = self.color_scheme
        else:
            p_td_values, p_colors = SCOPE.get_referenced_values_for_gradient(td_inputs)


        GradientProperties.range_values = p_td_values
        GradientProperties.range_colors = p_colors
        GradientProperties.range_labels = TdSysUtils.td_labels_filter(p_td_values, values_filter)


class TdDisplayBalancedFactory:

    def __init__(self) -> None:

        self.is_td_uniform: bool = False

    def calc_balanced(self, context: bpy.types.Context, SCOPE: list, mesh_limits: list, is_manual_mode: bool = False) -> TdIslandsStorage:

        if SCOPE.is_td_uniform():
            self.is_td_uniform = True
            SCOPE.set_color(TdColorManager.get_user_equal(context))
            return SCOPE

        base_value = self.get_base_value(context, is_manual_mode)

        return self._remap_balanced(context, SCOPE, base_value, mesh_limits)

    def _remap_balanced(self, context: bpy.types.Context, SCOPE: TdIslandsStorage, base_value: float, mesh_limits):

        # SCOPE.remove_referenced_items()
        # SCOPE.reset_colors()

        user_three = TdColorManager.get_user_three(context)

        td_min = SCOPE.get_min_td_value()
        td_max = SCOPE.get_max_td_value()

        if td_min == td_max:
            pass

        p_equal_color = user_three[1]
        if base_value not in SCOPE.get_all_td_values():
            SCOPE.append_reference(base_value, color=p_equal_color)
        else:
            SCOPE.get_island_by_value(base_value, method='EXACT').color = p_equal_color

        if td_min < base_value < td_max:
            SCOPE.get_island_by_value(td_min, method='EXACT').color = user_three[0]
            SCOPE.get_island_by_value(td_max, method='EXACT').color = user_three[2]
        else:
            if base_value <= td_min:
                SCOPE.get_island_by_value(td_min, method='EXACT').color = user_three[1]
                SCOPE.get_island_by_value(td_max, method='EXACT').color = user_three[2]
            elif base_value >= td_max:
                SCOPE.get_island_by_value(td_min, method='EXACT').color = user_three[0]
                SCOPE.get_island_by_value(td_max, method='EXACT').color = user_three[1]

        TdRangesMapper.calc_remap_balanced(
            SCOPE,
            base_value=base_value,
            mesh_limits=mesh_limits)

        return SCOPE

    def set_gradient_values(self, context: bpy.types.Context, td_inputs: TdContext, SCOPE: TdIslandsStorage, values_filter: float):
        from ZenUV.ui.gizmo_draw import GradientProperties

        if self.is_td_uniform:
            p_td_values, p_colors = TdSysUtils.get_gradient_values_for_uniform_td(context, td_inputs)
        else:
            p_td_values, p_colors = SCOPE.get_referenced_values_for_gradient(td_inputs)

        GradientProperties.range_values = p_td_values
        GradientProperties.range_colors = p_colors
        GradientProperties.range_labels = TdSysUtils.td_labels_filter(p_td_values, values_filter)

    def get_base_value(self, context: bpy.types.Context, is_manual_mode: bool) -> float:

        if is_manual_mode:
            return round(context.window_manager.zen_uv.td_props.balanced_checker, 2)
        else:
            p_base_value = TdDisplayLimits.middle

        return p_base_value


class TdSysUtils:

    @classmethod
    def get_gradient_values_for_uniform_td(cls, context: bpy.types.Context, td_inputs: TdContext, color_scheme_name: str = None):
        v = TdDisplayLimits.lower_limit
        if color_scheme_name is None:
            p_colors = [TdColorManager.get_user_equal(context)] * 3
        else:
            p_colors = [TdColorManager.get_mid_color(context, color_scheme_name)] * 3
        return [round(v - 0.01, td_inputs.round_value), v, round(v + 0.01, td_inputs.round_value)], p_colors

    @classmethod
    def show_list(cls, values, inarow: int = 10):
        return ''.join([str(values[i:i+inarow]) + '\n' for i in range(0, len(values), inarow)])

    @classmethod
    def td_labels_filter(cls, p_td_values: list, values_filter: float):
        p_td_labels = p_td_values.copy()

        p_m_label = -1
        for i in range(1, len(p_td_labels)-1):
            if p_m_label - values_filter <= p_td_labels[i] <= p_m_label + values_filter:
                p_td_labels[i] = ''
            else:
                p_m_label = int(p_td_labels[i])
        return p_td_labels

    @classmethod
    def is_gradient_widget_active(cls, context):
        from ZenUV.zen_checker.check_utils import is_draw_mode_active
        return is_draw_mode_active(context, 'TEXEL_DENSITY')

    @classmethod
    def update_view3d_in_all_screens(cls, context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    @classmethod
    def is_td_display_activated(cls, context):
        from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
        from ZenUV.utils.vc_processor import Z_TD_BALANCED_V_MAP_NAME
        for obj in resort_by_type_mesh_in_edit_mode_and_sel(context):
            if obj.data.vertex_colors.get(Z_TD_BALANCED_V_MAP_NAME, False):
                return True
        return False

    @classmethod
    def update_display_presets(cls, context: bpy.types.Context):
        if context.scene.zen_uv.td_draw_props.display_method == 'PRESETS' and TdSysUtils.is_gradient_widget_active(context):
            from .td_props import TdProps
            TdProps.update_td_draw_force(cls, context)


@dataclass
class TdDisplayPropertiesBase:
    """ Texel Density Display Properties Base Class """

    def __post_init__(self, PROPS) -> None:
        self.get_properties_from(PROPS)

    def get_properties_from(self, PROPS: bpy.types.OperatorProperties) -> None:
        """ Get properties from bpy.types.OperatorProperties class """
        for prp in self.__annotations__.keys():
            attr = getattr(PROPS, prp, None)
            if attr is None:
                Log.debug('From class TdDisplayPropertiesBase: ', f'Property "{prp}" not present in the {PROPS} Class')
                continue
            setattr(self, prp, attr)


@dataclass
class TdDisplayProperties(TdDisplayPropertiesBase):

    """ Texel Density Display Properties """

    display_method: str = ''  # in ("BALANCED", "SPECTRUM", "PRESETS")
    color_scheme_name: str = 'USER_THREE'  # in ["FULL", "USER_THREE", "USER_LINEAR", "REVERSED_SPEC", "MONO"]
    is_range_manual: bool = True
    use_presets_only: bool = False
    values_filter: float = 10.0

    def __post_init__(self, PROPS) -> None:
        super().__post_init__(PROPS)


class TdColorProcessor(TdDisplayProperties):


    def __init__(self, context: bpy.types.Context, Scope: TdIslandsStorage, PROPS: bpy.types.OperatorProperties, update_ui_limits: bool = True) -> None:

        super().__post_init__(PROPS)

        self.SCOPE: TdIslandsStorage = Scope

        self.init(context, update_ui_limits)

    def init(self, context: bpy.types.Context, update_ui_limits: bool = True):

        self.td_values = self.SCOPE.get_sorted_td_values()

        wm = context.window_manager

        self.user_limits = wm.zen_uv.td_props.td_limits
        if not len(self.td_values):
            self.mesh_limits = [0.0, 1.0]
        else:
            self.mesh_limits = [min(self.td_values), max(self.td_values)]

        if update_ui_limits:
            TdDisplayLimits.cl_td_limits = self.mesh_limits

        self.pr_td_limits = [0.0, 0.0]

        if self.is_range_manual:
            self.pr_td_limits[0] = round(self.user_limits[0], 2)
            self.pr_td_limits[1] = round(self.user_limits[1], 2)
        else:
            if self._is_all_values_uniform():
                self.pr_td_limits[0] = 0.0
                self.pr_td_limits[-1] = self.td_values[-1] * 2
                wm.zen_uv.td_props.td_limits = self.pr_td_limits
            else:
                self.pr_td_limits = self.mesh_limits
                wm.zen_uv.td_props.td_limits = self.mesh_limits
                wm.zen_uv.td_props.balanced_checker = TdDisplayLimits.middle

        self.color_scheme = self.set_color_scheme(context, self.color_scheme_name)

    def _is_all_values_uniform(self):
        return self.td_values[0] == self.td_values[-1]

    def __str__(self):
        print('\nTdColorProcessor Mapping:\n')
        return ''.join([str(i.obj_name) + ' -->\t' + str(i.td) + '\t-->\t' + str(i.color) + '\n' for i in self.SCOPE.get_sorted_islands()])

    def bake_texel_density_to_vc(self, context, td_inputs):

        from .td_utils import TdUtils
        TdUtils.bake_colors_to_vc(context, td_inputs, self.SCOPE)

    def calc_output_range(self, context: bpy.types.Context, td_inputs: TdContext, method: str) -> TdIslandsStorage:
        """
        method: in {'SPECTRUM', 'BALANCED', 'PRESETS'}
        """
        self.SCOPE.reset_colors()
        self.SCOPE.remove_referenced_items()

        if method == 'SPECTRUM':
            SpectrumFactory = TdDisplaySpectrumFactory()
            self.SCOPE = SpectrumFactory.calc_spectrum(context, td_inputs, self.SCOPE, self.color_scheme, self.color_scheme_name, self.pr_td_limits, self.mesh_limits)

            if TdSysUtils.is_gradient_widget_active(context):
                SpectrumFactory.set_gradient_values(context, td_inputs, self.SCOPE, self.values_filter)

            return self.SCOPE

        elif method == 'BALANCED':
            self.set_color_scheme(context, 'USER_THREE')
            BalancedFactory = TdDisplayBalancedFactory()

            self.SCOPE = BalancedFactory.calc_balanced(context, self.SCOPE, self.mesh_limits, self.is_range_manual)

            if TdSysUtils.is_gradient_widget_active(context):
                BalancedFactory.set_gradient_values(context, td_inputs, self.SCOPE, self.values_filter)

            return self.SCOPE

        elif method == 'PRESETS':
            PresetsFactory = TdDisplayPresetsFactory()

            self.SCOPE = PresetsFactory.calc_presets(context, self.SCOPE, self.use_presets_only)

            if TdSysUtils.is_gradient_widget_active(context):
                PresetsFactory.set_gradient_values(
                    td_inputs,
                    self.SCOPE,
                    self.values_filter)

            return self.SCOPE

    def set_color_scheme(self, context: bpy.types.Context, color_cheme: list) -> list:
        '''
        values in {'FULL_SPEC', 'USER_THREE', 'USER_LINEAR', 'REVERSED_SPEC', 'MONO', 'USER_PRESETS'}
        '''
        if color_cheme == 'FULL_SPEC':
            return TdColorManager.full.copy()

        elif color_cheme == 'REVERSED_SPEC':
            p_cols = TdColorManager.full.copy()
            p_cols.reverse()
            return p_cols

        elif color_cheme == 'USER_THREE':
            return TdColorManager.get_user_three(context)

        elif color_cheme == 'USER_LINEAR':
            return TdColorManager.get_user_linear(context)

        elif color_cheme == 'MONO':
            return TdColorManager.mono.copy()

        elif color_cheme == 'USER_PRESETS':
            pass

        else:
            p_message = f'TdBalancedColorProcessor: set_color_scheme.color_scheme current --> \
                ({color_cheme}) not in ["FULL", "USER_THREE", "USER_LINEAR", "REVERSED_SPEC", "MONO", "USER_PRESETS"]'
            raise RuntimeError(p_message)


if __name__ == '__main__':
    pass
