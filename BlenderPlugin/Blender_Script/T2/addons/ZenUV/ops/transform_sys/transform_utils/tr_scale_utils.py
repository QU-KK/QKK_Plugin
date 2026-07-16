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
from mathutils import Vector
from .tr_utils import TransformLimitsManager
from .transform_loops import TransformLoops
from .tr_object_data import transform_object_data
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.bounding_box import BoundingBox2d, get_overall_bbox
from . tr_utils import (
    TrConstants,
    Cursor2D,
    TrOrder
    )
from ZenUV.utils.generic import get_mesh_data, verify_uv_layer


class TrScaleProps:

    def __init__(self, context: bpy.types.Context, is_global) -> None:
        prop = context.scene.zen_uv
        self.is_global_settings = is_global

        # GLOBAL Settings
        self.sc_tr_scale = prop.tr_scale
        self.sc_tr_scale_mode = prop.tr_scale_mode
        self.sc_prop_unts_uv_ar = prop.unts_uv_area_size
        self.sc_prop_unts_desired = prop.unts_desired_size
        self.sc_prop_cals_by = prop.unts_calculate_by
        self.sc_tr_flip_always_center = prop.tr_flip_always_center

        self.cursor_2d_as_pivot = False

        # OPERATOR Settings
        self.op_scale = None
        self.op_tr_scale_mode = None
        self.op_prop_unts_uv_ar = None
        self.op_prop_unts_desired = None
        self.op_prop_cals_by = None

        # FLIP Mode settings
        self.flip_direction = 'HORIZONTAL'


class ScaleFactory():

    def __init__(
        self,
        context: bpy.types.Context,
        ScaleProps: TrScaleProps,
        influence_mode: bool,
        objs: list,
        pivot_point: str = "CENTER",
        island_pivot: str = 'cen',
        transform_mode: str = 'SCALE',
        scale_mode: str = "AXIS",
    ) -> None:
        """
        :param context: bpy.types.Context
        :param ScaleProps: class TrScaleProps
        :param influence_mode: {'ISLAND', 'SELECTION'}
        :param objs: list of blender objects
        :param pivot_point: in {
                'BOUNDING_BOX_CENTER',
                'CURSOR',
                'INDIVIDUAL_ORIGINS',
                'MEDIAN_POINT',
                'ACTIVE_ELEMENT',
                }
        :param island_pivot: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
        :param transform_mode: in {'SCALE', 'FLIP'}
        :param scale_mode: {'UNITS', 'AXIS'}
        """

        self.context = context
        self.PROPS = ScaleProps
        self.is_transform_islands = influence_mode == 'ISLAND'
        self.objs = objs
        self.pivot_point = pivot_point
        self.island_pivot = island_pivot
        self.transform_mode = transform_mode
        self.scale_mode = scale_mode
        self.order = TrOrder.from_pivot_point(context, self.pivot_point)
        self.influence_mode = influence_mode

    def _get_anchor(self, loops, uv_layer):
        if self.PROPS.is_global_settings:
            if self.PROPS.sc_tr_flip_always_center:
                return BoundingBox2d(points=[loop[uv_layer].uv for loop in loops]).get_as_dict()['cen']
            else:
                return BoundingBox2d(points=[loop[uv_layer].uv for loop in loops]).get_as_dict()[self.island_pivot]

        if self.pivot_point in ("INDIVIDUAL_ORIGINS", "ACTIVE_ELEMENT"):
            return BoundingBox2d(points=[loop[uv_layer].uv for loop in loops]).get_as_dict()[self.island_pivot]

    def _get_scale(self):

        if self.transform_mode == "SCALE":

            if self.PROPS.is_global_settings:
                if self.PROPS.sc_tr_scale_mode == "AXIS":
                    return self.PROPS.sc_tr_scale
                elif self.PROPS.sc_tr_scale_mode == "UNITS":
                    return self._calc_by_units_scale_overall(_global=True)

            if self.scale_mode == "AXIS":
                return self.PROPS.op_scale
            elif self.scale_mode == "UNITS":
                return self._calc_by_units_scale_overall(_global=False)

        elif self.transform_mode == "FLIP":

            if self.PROPS.is_global_settings:
                return TrConstants.flip_vector[self.island_pivot]

            return {
                'HORIZONTAL': TrConstants.flip_vector['lc'],
                'VERTICAL': TrConstants.flip_vector['tc'],
                'BY_I_PIVOT': TrConstants.flip_vector[self.island_pivot]
            }[self.PROPS.flip_direction]

    def _calc_by_units_scale_overall(self, _global=False):
        bbox = get_overall_bbox(self.context, from_islands=self.is_transform_islands)
        cals_solver = {
            'HORIZONTAL': bbox['len_x'] if bbox['len_x'] != 0.0 else 1.0,
            'VERTICAL': bbox['len_y'] if bbox['len_y'] != 0.0 else 1.0
            }
        if _global:
            return Vector([self.PROPS.sc_prop_unts_desired / self.PROPS.sc_prop_unts_uv_ar / cals_solver.get(self.PROPS.sc_prop_cals_by, 1.0)] * 2)
        else:
            return Vector([self.PROPS.op_prop_unts_desired / self.PROPS.op_prop_unts_uv_ar / cals_solver.get(self.PROPS.op_prop_cals_by, 1.0)] * 2)

    def is_always_center(self) -> bool:
        return self.transform_mode == 'FLIP' and self.PROPS.is_global_settings and self.PROPS.sc_tr_flip_always_center

    def transform_scale_flip(self) -> None:
        island_pivot = 'cen' if self.is_always_center() else self.island_pivot

        if self.PROPS.cursor_2d_as_pivot:
            order = 'OVERALL'
            anchor = Cursor2D(self.context).uv_cursor_pos
        else:
            order = self.order
            if order == 'OVERALL':
                anchor = get_overall_bbox(self.context, from_islands=self.influence_mode == 'ISLAND')[island_pivot]
            else:
                anchor = Vector((0.0, 0.0))

        TrScaleFlipProcessor.transform_scale_flip(
            self.context,
            self.objs,
            self.influence_mode,
            order,
            island_pivot,
            self._get_scale(),
            anchor,
            self.scale_mode,
            self.PROPS
        )


class TrScaleFlipProcessorEx:

    @classmethod
    def transform_scale_flip(
        cls,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
        island_pivot: str,
        scale: Vector,
        anchor: Vector,
        scale_mode: str = 'AXIS',
        PROPS: TrScaleProps = None,
    ) -> None:
        """
        :param context: bpy.types.Context
        :param objs: list of blender objects
        :param influence_mode: {'ISLAND', 'SELECTION'}
        :param order: {'ONE_BY_ONE', 'OVERALL}
        :param island_pivot: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
        :param scale: Vector
        :param anchor: Vector
        :param scale_mode: {'UNITS', 'AXIS'}
        :param PROPS: class TrScaleProps. Used only in 'UNITS' scale mode.
        """
        if scale_mode == 'UNITS':
            if PROPS is None:
                message = 'Current scale_mode is "UNITS". PROPS must be filled in.'
                raise RuntimeError(message)

        if not transform_object_data.is_valid(objs, influence_mode, order):
            transform_object_data.setup(context, objs, influence_mode, order)

        for obj, info in transform_object_data.object_storage.items():
            me = info.me
            uv_layer = info.uv_layer
            loops = info.loops
            info.loops_data.clear()

            if order == 'ONE_BY_ONE':
                for idx, lp_cluster in enumerate(loops):
                    lp_cluster_bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in lp_cluster]).get_as_dict()
                    if scale_mode == 'UNITS':
                        scale = cls._scale_by_units_individual(lp_cluster_bbox, PROPS)

                    TransformLoops.scale_loops(lp_cluster, uv_layer, scale, lp_cluster_bbox[island_pivot])
                    info.loops_data[idx] = lp_cluster_bbox[island_pivot]

            else:  # order == 'OVERALL'
                for idx, lp_cluster in enumerate(loops):
                    TransformLoops.scale_loops(lp_cluster, uv_layer, scale, anchor)
                    info.loops_data[idx] = anchor

            bmesh.update_edit_mesh(me, loop_triangles=False)

    @classmethod
    def scale_in_trim(
        cls,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
        lock: bool,
        island_pivot: str,
        inp_scale: Vector,
        anchor: Vector,
        limits_bbox: BoundingBox2d
    ) -> str:
        """
        :param context: bpy.types.Context
        :param objs: list of blender objects
        :param influence_mode: {'ISLAND', 'SELECTION'}
        :param order: {'ONE_BY_ONE', 'OVERALL}
        :param island_pivot: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
        :param inp_scale: Vector
        :param anchor: Vector
        :param limits_bbox: BoundingBox2d
        """
        TransformLimitsManager.results.clear()

        if not transform_object_data.is_valid(objs, influence_mode, order):
            n_loops = transform_object_data.setup(context, objs, influence_mode, order)
            if n_loops == 0:
                return 'No selected islands!'

        message = 'Finished' if transform_object_data.object_storage else 'No selected islands'

        i_out_trim_element_count = 0

        for obj, info in transform_object_data.object_storage.items():
            me = info.me
            uv_layer = info.uv_layer
            loops = info.loops
            info.loops_data.clear()

            for idx, cluster in enumerate(loops):
                scale = inp_scale.copy()
                cluster_bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in cluster])
                anchor = cluster_bbox.get_as_dict()[island_pivot]

                if lock:
                    if cluster_bbox.inside_of_bbox(limits_bbox):
                        TransformLimitsManager.fill(anchor, cluster_bbox, limits_bbox, scale)
                        scale = TransformLimitsManager.get_scale(scale)
                        TransformLoops.scale_loops(cluster, uv_layer, scale, anchor)
                    else:
                        i_out_trim_element_count += 1
                        message = f'Out of Trim: {i_out_trim_element_count} element(s)'
                else:
                    TransformLoops.scale_loops(cluster, uv_layer, scale, anchor)

                info.loops_data[idx] = anchor

            bmesh.update_edit_mesh(me, loop_triangles=False)

        if False in TransformLimitsManager.results:
            return 'Limit reached'

        return message


class TrScaleFlipProcessor:

    message: str = 'Finished'

    @classmethod
    def transform_scale_flip(
        cls,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
        island_pivot: str,
        scale: Vector,
        anchor: Vector,
        scale_mode: str = 'AXIS',
        PROPS: TrScaleProps = None,
    ) -> None:
        """
        :param context: bpy.types.Context
        :param objs: list of blender objects
        :param influence_mode: {'ISLAND', 'SELECTION'}
        :param order: {'ONE_BY_ONE', 'OVERALL}
        :param island_pivot: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
        :param scale: Vector
        :param anchor: Vector
        :param scale_mode: {'UNITS', 'AXIS'}
        :param PROPS: class TrScaleProps. Used only in 'UNITS' scale mode.
        """
        message = cls.message
        if scale_mode == 'UNITS':
            if PROPS is None:
                message = 'Current scale_mode is "UNITS". PROPS must be filled in.'
                raise RuntimeError(message)

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            if influence_mode == 'ISLAND':
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
            else:  # influence_mode != 'ISLAND'
                from . tr_utils import BlPivotPoint
                is_groupped = order == 'ONE_BY_ONE' or (order == 'SYSTEM_PIVOT' and BlPivotPoint.get(context) == 'INDIVIDUAL_ORIGINS')

                if is_groupped:
                    loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)
                else:
                    loops = [island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=False), ]

            if not len(loops):
                message = 'Select something.'

            if order == 'ONE_BY_ONE':
                for lp_cluster in loops:
                    lp_cluster_bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in lp_cluster]).get_as_dict()
                    if scale_mode == 'UNITS':
                        scale = cls._scale_by_units_individual(lp_cluster_bbox, PROPS)
                    anchor = lp_cluster_bbox[island_pivot] if anchor is None else anchor
                    TransformLoops.scale_loops(lp_cluster, uv_layer, scale, lp_cluster_bbox[island_pivot])

            else:  # order == 'OVERALL'
                if len(loops):
                    lp_cluster = [lp for group in loops for lp in group]
                    anchor = BoundingBox2d(points=[loop[uv_layer].uv for loop in lp_cluster]).center if anchor is None else anchor
                    TransformLoops.scale_loops(lp_cluster, uv_layer, scale, anchor)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return message

    @classmethod
    def scale_in_trim(
        cls,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
        lock: bool,
        island_pivot: str,
        inp_scale: Vector,
        anchor: Vector,
        limits_bbox: BoundingBox2d
    ) -> None:
        """
        :param context: bpy.types.Context
        :param objs: list of blender objects
        :param influence_mode: {'ISLAND', 'SELECTION'}
        :param order: {'ONE_BY_ONE', 'OVERALL}
        :param island_pivot: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
        :param inp_scale: Vector
        :param anchor: Vector
        :param limits_bbox: BoundingBox2d
        """
        message = cls.message
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            if influence_mode == 'ISLAND':
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
            else:  # influence_mode != 'ISLAND'
                loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)

            if order == 'OVERALL':
                loops = [[lp for group in loops for lp in group], ]

            for cluster in loops:
                scale = inp_scale.copy()
                cluster_bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in cluster])
                anchor = cluster_bbox.get_as_dict()[island_pivot]

                if lock:
                    if cluster_bbox.inside_of_bbox(limits_bbox):
                        TransformLimitsManager.fill(anchor, cluster_bbox, limits_bbox, scale)
                        scale = TransformLimitsManager.get_scale(scale)
                        TransformLoops.scale_loops(cluster, uv_layer, scale, anchor)
                    else:
                        message = 'Out of Trim'
                else:
                    TransformLoops.scale_loops(cluster, uv_layer, scale, anchor)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        if False in TransformLimitsManager.results:
            return 'Limit reached'

        return message

    @classmethod
    def _scale_by_units_individual(cls, i_bbox, PROPS):
        cals_solver = {
            'HORIZONTAL': i_bbox['len_x'] if i_bbox['len_x'] != 0.0 else 1.0,
            'VERTICAL': i_bbox['len_y'] if i_bbox['len_y'] != 0.0 else 1.0
            }
        if PROPS.is_global_settings:
            return Vector([PROPS.sc_prop_unts_desired / PROPS.sc_prop_unts_uv_ar / cals_solver.get(PROPS.sc_prop_cals_by, 1.0)] * 2)
        else:
            return Vector([PROPS.op_prop_unts_desired / PROPS.op_prop_unts_uv_ar / cals_solver.get(PROPS.op_prop_cals_by, 1.0)] * 2)
