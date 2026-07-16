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

""" Zen UV Texel Density utilities"""

import bpy
import math
import bmesh
from mathutils import Vector, Color
import numpy as np

from .td_islands_storage import TdIslandsStorage, TdIsland, IslandSize

from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils import vc_processor as vc
from ZenUV.utils.generic import UnitsConverter, verify_uv_layer
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils.vlog import Log


class TdDrawUI:

    def update_gradient_switch(self, context):
        p_path = context.scene.zen_uv.ui
        if self.enable_gradient_widget is True:
            if context.area.type == 'VIEW_3D':
                p_path.draw_mode_3D = 'TEXEL_DENSITY'
            elif context.area.type == 'IMAGE_EDITOR':
                p_path.draw_mode_UV = 'TEXEL_DENSITY'
        else:
            if context.area.type == 'VIEW_3D':
                p_path.draw_mode_3D = 'NONE'
            elif context.area.type == 'IMAGE_EDITOR':
                p_path.draw_mode_UV = 'NONE'

    enable_gradient_widget = bpy.props.BoolProperty(
        name="Gradient Widget",
        description="Show Gradient Widget",
        default=False,
        update=update_gradient_switch)

    values_filter = bpy.props.FloatProperty(
        name='Values Filter',
        description='Sets how many values to display. This is the value between adjacent marks on the gradient widget',
        default=10,
        min=0)

    def draw_gradient_setup(self, context, layout, PROPS):
        from ZenUV.prop.zuv_preferences import get_prefs

        # from .td_props import ZUV_TdDrawProperties
        # PROPS = PROPS  # type: ZUV_TdDrawProperties

        addon_prefs = get_prefs()
        box = layout.box()
        box.label(text='Gradient widget settings:')
        box.prop(PROPS, 'enable_gradient_widget', icon='HIDE_OFF', expand=True)
        box.prop(PROPS, 'values_filter')
        col = box.column()
        addon_prefs.td_draw.draw(col, context)

    def draw_current_td_limits(context: bpy.types.Context, layout):
        from . td_display_utils import TdDisplayLimits
        is_td_uniform = TdDisplayLimits.lower_limit == TdDisplayLimits.upper_limit
        label = 'TD is uniform' if is_td_uniform else 'TD range'
        layout.label(text=f'{label}:  {TdDisplayLimits.lower_limit} - {TdDisplayLimits.middle} - {TdDisplayLimits.upper_limit} {TdUtils.get_current_units_string(context)}')


class SzContext:


    def __init__(self, context: bpy.types.Context) -> None:
        sz_props = context.scene.zen_uv.td_props

        self.set_mode: str = sz_props.sz_set_mode  # type: str in {'ISLAND', 'OVERALL'}
        self.obj_mode: bool = False  # Always False for blocking object mode in SZ sys

        self.image_size: list = self._get_image_size(context)

        self.sz_reference_size: IslandSize = IslandSize(self.image_size[0], self.image_size[1], bbox=BoundingBox2d(points=((0, 0), (1, 1))))

        self.sz_reference_size.set_size(context, sz_props.sz_current_size)

        self.sz_units = sz_props.sz_units  # in ['PIXELS', 'UNITS']
        self.sz_active_axis_list = [sz_props.sz_active_x, sz_props.sz_active_y]

        self.sz_set_pivot_name = sz_props.sz_set_pivot if sz_props.sz_use_pivot is True else 'cen'

    def _get_image_size(self, context):
        if context.scene.zen_uv.td_props.sz_im_size_presets == 'Custom':
            return [context.scene.zen_uv.td_props.SZ_TextureSizeX, context.scene.zen_uv.td_props.SZ_TextureSizeY]
        else:
            return [context.scene.zen_uv.td_props.SZ_TextureSizeX, context.scene.zen_uv.td_props.SZ_TextureSizeX]


class TdContext:


    def __init__(self, context: bpy.types.Context) -> None:
        td_props = context.scene.zen_uv.td_props
        self.td: float = round(td_props.prp_current_td, 2)

        self.image_size: list = self._get_image_size(context)
        self.units: float = UnitsConverter.converter[td_props.td_unit]
        self.set_mode: str = td_props.td_set_mode  # type: str in {'ISLAND', 'OVERALL'}
        self.obj_mode: bool = False
        self.by_island: bool = False
        self.bl_units_scale: float = context.scene.unit_settings.scale_length

        self.selected_only: bool = False

        self.td_global_preset: float = td_props.td_global_preset

        self.td_set_pivot_name = td_props.td_set_pivot if td_props.td_use_pivot is True else 'cen'

        self.round_value = self.get_td_round_value(context)

        self.td_calc_precision = td_props.td_calc_precision

    def _get_image_size(self, context):
        if context.scene.zen_uv.td_props.td_im_size_presets == 'Custom':
            return [context.scene.zen_uv.td_props.TD_TextureSizeX, context.scene.zen_uv.td_props.TD_TextureSizeY]
        else:
            return [context.scene.zen_uv.td_props.TD_TextureSizeX, context.scene.zen_uv.td_props.TD_TextureSizeX]

    def show_td_context(self):
        print("\nAttributes of the class TdContext -->")
        print("- ".join("%s: %s\n" % item for item in vars(self).items()))

    def get_td_round_value(self, context: bpy.types.Context):
        from .td_utils import TdUtils
        return UnitsConverter.get_count_after_point(TdUtils.get_current_units_string(context, full=False)) + 1


class TdUtils:


    generic_color: Color = Color((0.0, 0.0, 0.0))

    @classmethod
    def get_current_units_string(cls, context, full: bool = True) -> str:
        units = context.scene.zen_uv.td_props.bl_rna.properties['td_unit'].enum_items[context.scene.zen_uv.td_props.td_unit].name
        if full:
            return units
        else:
            return units[5:]

    @classmethod
    def bake_colors_to_vc(cls, context, td_inputs: TdContext, Scope):
        for p_obj_name, p_islands in Scope.get_islands_by_objects().items():
            p_obj = context.scene.objects[p_obj_name]
            bm = TdBmeshManager.get_bm(td_inputs, p_obj)
            bm.faces.ensure_lookup_table()
            cls.set_vcolor_to_mesh(p_islands, bm)
            TdBmeshManager.set_bm(td_inputs, p_obj, bm)
            vc_td_layer = p_obj.data.vertex_colors.get(vc.Z_TD_BALANCED_V_MAP_NAME, None)
            if vc_td_layer:
                vc_td_layer.active = True
            p_obj.update_from_editmode()

    @classmethod
    def set_vcolor_to_mesh(cls, islands, bm):
        for island in islands:
            vc.set_v_color(
                [bm.faces[i] for i in island.indices],
                vc.set_color_layer(bm, vc.Z_TD_BALANCED_V_MAP_NAME),
                island.color,
                randomize=False
            )

    @classmethod
    def get_td_data_with_precision(cls, context: bpy.types.Context, objs: list, td_inputs: TdContext, td_influence: str = 'ISLAND'):

        '''
            Take in to account td_calc_precision in any way
        '''

        Scope = TdIslandsStorage()
        Scope.clear()
        for obj in objs:
            bm = TdBmeshManager.get_bm(td_inputs, obj)
            Scope = cls._collect_td_data(context, Scope, td_inputs, td_influence, obj, bm, precision=td_inputs.td_calc_precision)

            # TdBmeshManager.set_bm(td_inputs, obj, bm)

        return Scope

    @classmethod
    def get_td_data(cls, context: bpy.types.Context, objs: list, td_inputs: TdContext, td_influence: str = 'ISLAND', precision: int = 100):

        '''
            Not take in to account td_calc_precision in any way
        '''

        Scope = TdIslandsStorage()
        Scope.clear()
        for obj in objs:
            bm = TdBmeshManager.get_bm(td_inputs, obj)
            Scope = cls._collect_td_data(context, Scope, td_inputs, td_influence, obj, bm, precision=precision)

            # TdBmeshManager.set_bm(td_inputs, obj, bm)

        return Scope

    @classmethod
    def get_sizes_data(cls, context: bpy.types.Context, objs: list, td_inputs: TdContext, td_influence: str = 'ISLAND'):
        Scope = TdIslandsStorage()
        Scope.clear()
        for obj in objs:
            bm = TdBmeshManager.get_bm(td_inputs, obj)
            Scope = cls._collect_sizes_data(context, Scope, td_inputs, td_influence, obj, bm)

            # TdBmeshManager.set_bm(td_inputs, obj, bm)

        return Scope

    @classmethod
    def create_scope_from_presets(cls, context: bpy.types.Context) -> TdIslandsStorage:

        Scope = TdIslandsStorage()
        Scope.clear()

        scene = context.scene

        r_to = UnitsConverter.get_count_after_point(TdUtils.get_current_units_string(context, full=False)) + 1
        p_values = [round(i.value, r_to) for i in scene.zen_tdpr_list]
        for idx, v in enumerate(p_values):
            Scope.append(
                TdIsland(index=idx, td=v)
                    )

        return Scope

    @classmethod
    def _collect_td_data(
        cls,
        context: bpy.types.Context,
        Scope: TdIslandsStorage,
        td_inputs: TdContext,
        td_influence: str,
        obj: bpy.types.Object,
        bm: bmesh.types.BMesh,
        precision: int = 100
    ) -> dict:

        uv_layer = verify_uv_layer(bm)

        if td_influence == 'FACE':
            islands = [[f, ] for f in bm.faces]
        else:
            if td_inputs.selected_only:
                islands = island_util.get_island(context, bm, uv_layer)
            else:
                islands = island_util.get_islands_ignore_context(bm, is_include_hidden=True)


        for idx, island in enumerate(islands):
            Scope.append(
                TdIsland(
                    index=idx,
                    indices=[f.index for f in island],
                    obj_name=obj.name,
                    td=TexelDensityFactory.calc_averaged_td(obj, uv_layer, [island, ], td_inputs)[0]))
        return Scope

    @classmethod
    def _collect_sizes_data(
        cls,
        context: bpy.types.Context,
        Scope: TdIslandsStorage,
        td_inputs: TdContext,
        td_influence: str,
        obj: bpy.types.Object,
        bm: bmesh.types.BMesh
    ) -> dict:

        uv_layer = verify_uv_layer(bm)

        if td_influence == 'FACE':
            islands = [[f, ] for f in bm.faces]
        else:
            islands = island_util.get_islands_ignore_context(bm, is_include_hidden=True)


        for idx, island in enumerate(islands):
            Scope.append(
                TdIsland(
                    index=idx,
                    indices=[f.index for f in island],
                    obj_name=obj.name,
                    # td=TexelDensityFactory.calc_averaged_td(obj, uv_layer, [island, ], td_inputs)[0])
                    size=IslandSize(td_inputs.image_size[0], td_inputs.image_size[1], BoundingBox2d(islands=[island, ], uv_layer=uv_layer))
                    ))
        return Scope

    @classmethod
    def select_by_td(cls, context, Scope: TdIslandsStorage, td_range: list, td_inputs: TdContext):
        from .td_islands_storage import TdDataStorage as TDS
        if td_range[0] > td_range[1]:
            td_range.reverse()
        islands = Scope.get_islands_in_td_range(
                td_range[0],
                td_range[1]
                )

        for obj_name in list({i.obj_name for i in islands}):
            p_o_islands = [i for i in islands if i.obj_name == obj_name]
            TDS.i_count += len(p_o_islands)
            p_face_idxs = sum([i.indices for i in p_o_islands], [])
            p_obj = context.scene.objects[obj_name]
            bm = TdBmeshManager.get_bm(td_inputs, p_obj)
            bm.faces.ensure_lookup_table()
            for idx in p_face_idxs:
                bm.faces[idx].select_set(True)

            bm.select_flush_mode()
            # TdBmeshManager.set_bm(td_inputs, p_obj, bm)

    @classmethod
    def select_by_size(cls, context, Scope: TdIslandsStorage, size_range: list, td_inputs: TdContext):
        from .td_islands_storage import TdDataStorage as TDS
        from ZenUV.utils.generic import select_by_context
        if size_range[0] > size_range[1]:
            size_range.reverse()
        islands = Scope.get_islands_in_size_range(
                size_range[0],
                size_range[1],
                td_inputs
                )

        for obj_name in list({i.obj_name for i in islands}):
            p_o_islands = [i for i in islands if i.obj_name == obj_name]
            TDS.i_count += len(p_o_islands)
            p_face_idxs = sum([i.indices for i in p_o_islands], [])
            p_obj = context.scene.objects[obj_name]
            bm = TdBmeshManager.get_bm(td_inputs, p_obj)
            bm.faces.ensure_lookup_table()

            select_by_context(context, bm, [[bm.faces[i] for i in p_face_idxs], ], state=True)

            bm.select_flush_mode()
            # TdBmeshManager.set_bm(td_inputs, p_obj, bm)

    @classmethod
    def compound_island_size(cls, sz_inputs: SzContext, size: float):
        return IslandSize(
            sz_inputs.image_size[0],
            sz_inputs.image_size[1],
            BoundingBox2d(points=((0.0, 0.0), size))
            )


class UvFaceArea:


    uv_area_calc: float = 0.0
    islands_counter: int = 0

    @classmethod
    def calculate_uv_coverage(cls, uv_layer, faces):
        return cls.get_uv_faces_area(faces, uv_layer) * 100

    @classmethod
    def polygon_area(cls, p):
        return 0.5 * abs(sum(x0 * y1 - x1 * y0 for ((x0, y0), (x1, y1)) in cls.segments(p)))

    @classmethod
    def segments(cls, p):
        return zip(p, p[1:] + [p[0]])

    @classmethod
    def get_uv_faces_area(cls, faces, uv_layer):
        return sum([cls.polygon_area([loop[uv_layer].uv for loop in face.loops]) for face in faces])

    # Numpy calculation v01
    @classmethod
    def calc_uv_coverage_numpy_01(cls, uv_layer, faces):
        return cls.get_uv_faces_area_numpy_01(faces, uv_layer) * 100

    @classmethod
    def get_uv_faces_area_numpy_01(cls, faces, uv_layer):
        return sum([cls.get_poly_area_np([loop[uv_layer].uv for loop in face.loops]) for face in faces])

    @classmethod
    def get_poly_area_np(cls, uv: list):
        x = [i[0] for i in uv]
        y = [i[1] for i in uv]
        return 0.5 * np.abs(np.dot(x, np.roll(y, 1))-np.dot(y, np.roll(x, 1)))


class TexelDensityFactory():


    @classmethod
    def _get_bm_for_td(cls, obj: bpy.types.Object):
        me = obj.data
        if not me.is_editmode:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            return bm
        return bmesh.from_edit_mesh(me).copy()

    @classmethod
    def _destroy_bm_for_td(cls, obj: bpy.types.Object, bm: bmesh.types.BMesh):
        """ Return True if me is in edit mode """
        me = obj.data
        if not me.is_editmode:
            bm.free()
            return True
        bm.free()
        return False

    @classmethod
    def get_texel_density(cls, context: bpy.types.Context, objs: list, td_inputs: TdContext):
        if objs:
            overall_td = []
            for obj in objs:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = verify_uv_layer(bm)
                bm.faces.ensure_lookup_table()
                islands = island_util.get_island(context, bm, uv_layer)

                overall_td.append(
                    cls.calc_averaged_td(
                        obj,
                        uv_layer,
                        islands,
                        td_inputs))

            return cls._prepare_output(sum([val[0] for val in overall_td]) / len([i for i in overall_td if i[0] != 0.0]), sum([val[1] for val in overall_td]))

        return [0.0001, 0.0001]

    @classmethod
    def calc_averaged_td(cls, obj: bpy.types.Object, uv_layer: bmesh.types.BMLayerItem, islands: list, td_inputs: TdContext):

        """
            Calculate averaged texel desity for all islands within islands list.
            Take into account the object transformation matrix.
        """

        if not len(islands):
            return [0.0, 0.0]

        ob_scale = obj.matrix_world.inverted().median_scale
        p_islands = cls.reduce_islands_polycount(islands, precision=td_inputs.td_calc_precision)
        p_td_data = [cls._calculate_texel_density(uv_layer, island, td_inputs) for island in p_islands]
        return sum(val[0] for val in p_td_data) * ob_scale / len(p_islands), sum(val[1] for val in p_td_data)

    @classmethod
    def reduce_islands_polycount(cls, islands, precision: int = 100):
        if precision != 100:
            return [list(island)[::max(round(len(island) / precision), 1)] for island in islands]
        else:
            return islands

    @classmethod
    def _calculate_texel_density(cls, uv_layer: bmesh.types.BMLayerItem, faces: list, td_inputs: TdContext):

        """
            Calculates Texel Density for particular faces.
            Does not take into account the object transformation matrix.
        """

        image_size = td_inputs.image_size
        max_side = max(image_size)
        image_aspect = max(image_size) / min(image_size)
        # Calculating GEOMETRY AREA
        geometry_area = sum(f.calc_area() for f in faces)
        # Calculating UV AREA
        # with Timer() as t:
        uv_area = UvFaceArea.get_uv_faces_area(faces, uv_layer)  # type float
        # UvFaceArea.uv_area_calc += t.delta(as_float=True)

        if geometry_area > 0 and uv_area > 0:
            return (((max_side / math.sqrt(image_aspect)) * math.sqrt(uv_area)) / (math.sqrt(geometry_area) * 100) / td_inputs.bl_units_scale) * td_inputs.units, uv_area * 100.0
        else:
            return 0.0001, uv_area * 100.0

    @classmethod
    def _prepare_output(cls, _input_0: list, _input_1: list):
        return round(_input_0, 2), round(_input_1, 2)

    @classmethod
    def get_texel_density_in_obj_mode(cls, context: bpy.types.Context, objs: list, td_inputs: TdContext):
        if objs:
            p_td_data = []
            for obj in objs:
                bm = cls._get_bm_for_td(obj)
                uv_layer = verify_uv_layer(bm)
                bm.faces.ensure_lookup_table()
                islands = island_util.get_islands(context, bm)
                p_td_data.append(TexelDensityFactory.calc_averaged_td(obj, uv_layer, islands, td_inputs))
                # Destroy bm
                cls._destroy_bm_for_td(obj, bm)
            return cls._prepare_output(sum(val[0] for val in p_td_data) / len(p_td_data), sum(val[1] for val in p_td_data))

        return [0.0001, 0.0001]

    @classmethod
    def get_object_averaged_td(cls, uobj: bpy.types.Object, uv_layer, bm, precision: int = 20) -> float:
        idxs = [f.index for f in bm.faces]
        p_faces = [bm.faces[i] for i in idxs[::max(round(len(bm.faces) / precision), 1)]]
        return TexelDensityFactory.calc_averaged_td(uobj.obj, uv_layer, [p_faces, ], uobj.td_inputs)[0]

    @classmethod
    def _calc_referenced_td_world_size(cls, image_size: list, td_inputs: TdContext):
        max_side = max(image_size)
        image_aspect = max(image_size) / min(image_size)
        return ((max_side / math.sqrt(image_aspect)) / (math.sqrt(image_aspect) * 100) / td_inputs.bl_units_scale) * td_inputs.units, 100.0


class TdBmeshManager:


    @classmethod
    def _bm_from_object(cls, obj: bpy.types.Object):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        return bm

    @classmethod
    def _bm_from_edit(cls, obj: bpy.types.Object):
        return bmesh.from_edit_mesh(obj.data)

    @classmethod
    def _set_to_obj(cls, obj: bpy.types.Object, bm: bmesh.types.BMesh):
        bm.to_mesh(obj.data)
        bm.free()

    @classmethod
    def _set_to_edit(cls, obj: bpy.types.Object):
        bmesh.update_edit_mesh(obj.data, loop_triangles=False)

    @classmethod
    def get_bm(cls, td_inputs: TdContext, obj):
        if td_inputs.obj_mode:
            return cls._bm_from_object(obj)
        else:
            return cls._bm_from_edit(obj)

    @classmethod
    def set_bm(cls, td_inputs: TdContext, obj: bpy.types.Object, bm: bmesh.types.BMesh):
        if td_inputs.obj_mode:
            cls._set_to_obj(obj, bm)
        else:
            cls._set_to_edit(obj)


class TexelDensityProcessor(TdBmeshManager):


    @classmethod
    def _get_clusters_obj(cls, context: bpy.types.Context, bm: bmesh.types.BMesh):
        return island_util.get_islands(context, bm)

    @classmethod
    def _get_clusters_bmesh(cls, context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem):
        return island_util.get_island(context, bm, uv_layer)

    @classmethod
    def set_td(cls, context: bpy.types.Context, objs: list, td_inputs: TdContext):
        from ZenUV.ops.transform_sys.transform_utils.tr_scale_utils import TransformLoops

        if objs:
            if td_inputs.set_mode == 'OVERALL':
                overall_td, overall_pivot = cls._calc_overall_params(context, objs, td_inputs)

            for obj in objs:
                bm = cls.get_bm(td_inputs, obj)
                uv_layer = verify_uv_layer(bm)

                clusters = cls._get_clusters_obj(context, bm) if td_inputs.obj_mode else cls._get_clusters_bmesh(context, bm, uv_layer)

                if td_inputs.set_mode == 'ISLAND':
                    for island in clusters:
                        pivot = BoundingBox2d(islands=[island, ], uv_layer=uv_layer).get_as_dict()[td_inputs.td_set_pivot_name]
                        current_td = TexelDensityFactory.calc_averaged_td(obj, uv_layer, [island, ], td_inputs)[0]
                        scale = (td_inputs.td / current_td) if current_td != 0 else td_inputs.td

                        if scale != 1:
                            TransformLoops.scale_loops([loop for face in island for loop in face.loops], uv_layer, Vector.Fill(2, scale), pivot)

                elif td_inputs.set_mode == 'OVERALL' and overall_td is not None:
                    scale = (td_inputs.td / overall_td) if overall_td != 0 else td_inputs.td
                    if scale != 1:
                        TransformLoops.scale_loops(
                            [loop for island in clusters for face in island for loop in face.loops],
                            uv_layer,
                            Vector.Fill(2, scale),
                            overall_pivot)

                cls.set_bm(td_inputs, obj, bm)

            return True
        else:
            return False

    @classmethod
    def _calc_overall_params(cls, context: bpy.types.Context, objs: list, td_inputs: TdContext):
        per_obj_scale_pivots = []
        per_object_td = 0
        overall_islands_count = 0

        for obj in objs:
            bm = cls.get_bm(td_inputs, obj)
            uv_layer = verify_uv_layer(bm)

            clusters = cls._get_clusters_obj(context, bm) if td_inputs.obj_mode else cls._get_clusters_bmesh(context, bm, uv_layer)

            if not len(clusters):
                continue

            per_object_td += TexelDensityFactory.calc_averaged_td(obj, uv_layer, clusters, td_inputs)[0]
            per_obj_scale_pivots.append(BoundingBox2d(islands=clusters, uv_layer=uv_layer).get_as_dict()[td_inputs.td_set_pivot_name])
            overall_islands_count += 1

        if overall_islands_count == 0:
            return None, None

        return per_object_td / overall_islands_count, BoundingBox2d(points=per_obj_scale_pivots).get_as_dict()[td_inputs.td_set_pivot_name]

    @classmethod
    def set_td_to_faces(cls, context: bpy.types.Context, obj: bpy.types.Object, island: list, td_inputs: TdContext):
        from ZenUV.ops.transform_sys.transform_utils.tr_scale_utils import TransformLoops

        def island_container(bm, island):
            if not isinstance(island, list):
                island = list(island)
            if not isinstance(island[0], int):
                return island
            else:
                bm.faces.ensure_lookup_table()
                return [bm.faces[index] for index in island]

        bm = cls._bm_from_edit(obj)
        uv_layer = verify_uv_layer(bm)

        if td_inputs.by_island:
            islands = island_util.get_islands(context, bm)
        else:
            islands = [island_container(bm, island), ]

        for island in islands:

            current_td = TexelDensityFactory.calc_averaged_td(obj, uv_layer, [island, ], td_inputs)[0]
            pivot = BoundingBox2d(islands=[island, ], uv_layer=uv_layer).center
            try:
                scale = td_inputs.td / current_td
            except ZeroDivisionError:
                scale = 1
            if scale != 1:
                TransformLoops.scale_loops([loop for face in island for loop in face.loops], uv_layer, Vector.Fill(2, scale), pivot)

        cls._set_to_edit(obj)


class IslandSizeProcessor(TdBmeshManager):

    @classmethod
    def get_island_size(cls, context: bpy.types.Context) -> IslandSize:
        from ZenUV.utils.bounding_box import get_overall_bbox
        td_props = context.scene.zen_uv.td_props

        return IslandSize(td_props.SZ_TextureSizeX, td_props.SZ_TextureSizeY, get_overall_bbox(context, from_islands=True, as_dict=False))

    @classmethod
    def set_island_size(cls, context: bpy.types.Context, objs: list, sz_inputs: TdContext):
        from ZenUV.ops.transform_sys.transform_utils.tr_scale_utils import TransformLoops
        from ZenUV.utils.bounding_box import get_overall_bbox

        if objs:
            if sz_inputs.set_mode == 'OVERALL':
                overall_size = cls.get_island_size(context)
                overall_pivot = get_overall_bbox(context, True)[sz_inputs.sz_set_pivot_name]

            for obj in objs:
                bm = cls.get_bm(sz_inputs, obj)
                uv_layer = verify_uv_layer(bm)

                clusters = TexelDensityProcessor._get_clusters_obj(context, bm) if sz_inputs.obj_mode else TexelDensityProcessor._get_clusters_bmesh(context, bm, uv_layer)

                if sz_inputs.set_mode == 'ISLAND':
                    for island in clusters:
                        p_i_bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)
                        pivot = p_i_bbox.get_as_dict()[sz_inputs.sz_set_pivot_name]
                        current_sz = IslandSize(
                            sz_inputs.image_size[0],
                            sz_inputs.image_size[1],
                            p_i_bbox
                            )  # type: IslandSize
                        scale = cls.calc_scale(current_sz, sz_inputs)
                        if scale != 1:
                            TransformLoops.scale_loops([loop for face in island for loop in face.loops], uv_layer, scale, pivot)

                elif sz_inputs.set_mode == 'OVERALL':
                    scale = cls.calc_scale(overall_size, sz_inputs)
                    if scale != 1:
                        TransformLoops.scale_loops(
                            [loop for island in clusters for face in island for loop in face.loops],
                            uv_layer,
                            scale,
                            overall_pivot)

                cls.set_bm(sz_inputs, obj, bm)

            return True
        else:
            return False

    @classmethod
    def calc_scale(cls, current_sz: IslandSize, sz_inputs: TdContext) -> Vector:

        if sz_inputs.sz_units == 'PIXELS':
            x_scale = (sz_inputs.sz_reference_size.pixels.x / current_sz.pixels.x) if current_sz.pixels.x != 0 else sz_inputs.sz_reference_size.pixels.x
            y_scale = (sz_inputs.sz_reference_size.pixels.y / current_sz.pixels.y) if current_sz.pixels.y != 0 else sz_inputs.sz_reference_size.pixels.y

        elif sz_inputs.sz_units == 'UNITS':
            x_scale = (sz_inputs.sz_reference_size.units.x / current_sz.units.x) if current_sz.units.x != 0 else sz_inputs.sz_reference_size.units.x
            y_scale = (sz_inputs.sz_reference_size.units.y / current_sz.units.y) if current_sz.units.y != 0 else sz_inputs.sz_reference_size.units.y

        if sz_inputs.sz_active_axis_list == [True, False]:
            return Vector.Fill(2, x_scale)
        elif sz_inputs.sz_active_axis_list == [False, True]:
            return Vector.Fill(2, y_scale)
        else:
            return Vector((x_scale, y_scale))


class CoverageReport:

    coverage: float = 0.0
    empty_space: str = '~'

    @classmethod
    def clear(cls):
        cls.coverage = 0.0
        cls.empty_space = '~'


if __name__ == '__main__':
    pass
