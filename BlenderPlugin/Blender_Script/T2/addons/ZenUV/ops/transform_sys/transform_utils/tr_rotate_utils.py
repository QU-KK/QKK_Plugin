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
from math import radians, pi
from random import choice
from . tr_utils import (
    ActiveUvImage,
    Cursor2D,
    TrOrder,
    TrSpaceMode
    )
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.utils.generic import get_mesh_data, verify_uv_layer
from ZenUV.utils.bounding_box import BoundingBox2d, get_overall_bbox
from ZenUV.utils import get_uv_islands as island_util
from .tr_object_data import transform_object_data


class TrRotateProps:

    def __init__(
        self,
        context: bpy.types.Context,
        is_global: bool
    ) -> None:

        prop = context.scene.zen_uv
        self.is_global_settings = is_global

        # GLOBAL Settings
        self.sc_tr_rotate_inc = prop.tr_rot_inc

        # Operator Settings
        self.op_tr_rotate_inc = 0
        self.op_direction = 'CW'

        self.op_tr_rotate_angle = 0


class RotateFactory:

    def __init__(
        self,
        context: bpy.types.Context,
        RotateProps: TrRotateProps,
        is_transform_islands: bool,
        objs: list,
        pivot_point: str,
        island_pivot: str = 'cen',
        rotation_mode: str = 'DIRECTION'
    ) -> None:

        self.context = context
        self.PROPS = RotateProps
        self.is_transform_islands = is_transform_islands
        self.objs = objs
        self.pivot_point = pivot_point
        self.island_pivot = island_pivot
        self.rotation_mode = rotation_mode

        self.image_aspect = ActiveUvImage(context).aspect

    def get_incremental_angle(self):
        if self.rotation_mode == 'DIRECTION':
            direction = {'CW': -1, 'CCW': 1}[self.PROPS.op_direction]
            if self.PROPS.is_global_settings:
                return direction * radians(self.PROPS.sc_tr_rotate_inc) * TrSpaceMode(self.context).editor_direction
            else:
                return direction * radians(self.PROPS.op_tr_rotate_inc) * TrSpaceMode(self.context).editor_direction
        else:
            return -1 * radians(self.PROPS.op_tr_rotate_angle) * TrSpaceMode(self.context).editor_direction

    def rotate(self) -> None:
        TrRotateProcessor.rotate(
            self.context,
            self.is_transform_islands,
            self.objs,
            self.pivot_point,
            self.island_pivot,
            self.image_aspect,
            angle=self.get_incremental_angle()
        )


class TrRotateProcessorEx:

    def __init__(self) -> None:
        self.is_transform_islands = False
        self.influence_mode = ''
        self.order = None
        self.pivot_point = None
        self.island_pivot = None
        self.global_anchor = None

    def setup(self, context, influence_mode, objs, pivot_point, island_pivot):
        self.is_transform_islands = influence_mode == 'ISLAND'
        self.influence_mode = influence_mode

        self.island_pivot = island_pivot
        self.pivot_point = pivot_point
        self.global_anchor = get_overall_bbox(context, from_islands=self.is_transform_islands)[self.island_pivot]
        self.order = TrOrder.from_pivot_point(context, self.pivot_point)

        transform_object_data.setup(context, objs, influence_mode, self.order)

        for obj, info in transform_object_data.object_storage.items():

            uv_layer = info.uv_layer
            loops = info.loops
            info.loops_data.clear()

            for idx, lp_cluster in enumerate(loops):
                if self.order == 'ONE_BY_ONE':
                    anchor = BoundingBox2d(points=[loop[uv_layer].uv for loop in lp_cluster]).get_as_dict()[self.island_pivot]

                else:
                    if self.pivot_point == 'CURSOR':
                        anchor = Cursor2D(context).uv_cursor_pos
                    else:
                        anchor = self.global_anchor

                info.loops_data[idx] = anchor

    def is_valid(self, influence_mode, objs, pivot_point, island_pivot):
        if (
                self.influence_mode != influence_mode or
                self.pivot_point != pivot_point or
                self.island_pivot != island_pivot or
                not transform_object_data.is_valid(objs, influence_mode, self.order)):
            return False
        return True

    def process(
        self,
        context,
        objs,
        influence_mode,
        pivot_point,
        island_pivot,
        image_aspect,
        angle,
        randomize=False
    ) -> str:

        if not self.is_valid(influence_mode, objs, pivot_point, island_pivot):
            self.setup(
                context,
                influence_mode,
                objs,
                pivot_point,
                island_pivot,
            )

        message = 'Finished' if transform_object_data.object_storage else 'No selected islands'

        for obj, info in transform_object_data.object_storage.items():
            me = info.me
            uv_layer = info.uv_layer
            loops = info.loops

            for idx, lp_cluster in enumerate(loops):
                if randomize:
                    angle += choice(range(0, 360, 5))

                anchor = info.loops_data.get(idx, None)
                if anchor is not None:

                    TransformLoops.rotate_loops(lp_cluster, uv_layer, angle, anchor, image_aspect=image_aspect, angle_in_radians=True)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return message


class TrRotateProcessor:

    @classmethod
    def rotate(
        cls,
        context,
        is_transform_islands,
        objs,
        pivot_point,
        island_pivot,
        image_aspect,
        angle,
        randomize=False
    ) -> None:
        global_anchor = get_overall_bbox(context, from_islands=is_transform_islands)[island_pivot]
        order = TrOrder.from_pivot_point(context, pivot_point)

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            if is_transform_islands:
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
            else:
                from . tr_utils import BlPivotPoint
                is_groupped = order == 'ONE_BY_ONE' or (order == 'SYSTEM_PIVOT' and BlPivotPoint.get(context) == 'INDIVIDUAL_ORIGINS')

                if is_groupped:
                    loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)
                else:
                    loops = [island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=False), ]

            for lp_cluster in loops:
                if randomize:
                    angle += choice(range(0, 360, 5))

                if order == 'ONE_BY_ONE':
                    anchor = BoundingBox2d(points=[loop[uv_layer].uv for loop in lp_cluster]).get_as_dict()[island_pivot]
                else:
                    if pivot_point == 'CURSOR':
                        anchor = Cursor2D(context).uv_cursor_pos
                    else:
                        anchor = global_anchor

                TransformLoops.rotate_loops(lp_cluster, uv_layer, angle, anchor, image_aspect=image_aspect, angle_in_radians=True)

            bmesh.update_edit_mesh(me, loop_triangles=False)


class TrOrientProcessor:

    @classmethod
    def orient(
        cls,
        context: bpy.types.Context,
        objs: list,
        mode: str,
        orient_direction: str,
        rotate_direction: str,
        processing_order: str = 'ONE_BY_ONE'
    ) -> None:
        """
        :param context: bpy.types.Context
        :param objs: list of blender objects
        :param mode: enum in {'BBOX', 'BY_SELECTION}
        :param orient_direction: enum in {'HORIZONTAL', 'VERTICAL'}
        :param rotate_direction: enum in {'CW', 'CWW'}
        """
        if mode == 'BBOX':
            cls.orient_island(
                context,
                objs,
                orient_direction,
                rotate_direction,
                ActiveUvImage(context).aspect,
                processing_order
            )
        elif mode == 'BY_SELECTION':
            cls.orient_by_selection(
                context,
                objs,
                orient_direction,
                rotate_direction,
                ActiveUvImage(context).aspect,
                processing_order
            )
        else:
            raise RuntimeError("mode not in {'BBOX', 'BY_SELECTION}")

    @classmethod
    def orient_island(
        cls,
        context: bpy.types.Context,
        objs: list,
        orient_direction: str,
        rotate_direction: str,
        image_aspect: float,
        processing_order: str = 'ONE_BY_ONE'
    ) -> None:
        """
        :param context: bpy.types.Context
        :param objs: list of blender objects
        :param mode: enum in {'BBOX', 'BY_SELECTION}
        :param orient_direction: enum in {'HORIZONTAL', 'VERTICAL'}
        :param rotate_direction: enum in {'CW', 'CWW'}
        :param image_aspect: float
        """
        if processing_order == 'ONE_BY_ONE':
            for obj in objs:
                me, bm = get_mesh_data(obj)
                uv_layer = verify_uv_layer(bm)
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)

                for cl in loops:
                    bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in cl])

                    cls._orient_loops(cl, uv_layer, bbox, image_aspect, orient_direction, rotate_direction)

                bmesh.update_edit_mesh(me)

        elif processing_order == 'OVERALL':
            g_bbox = get_overall_bbox(context, from_islands=True, as_dict=False)
            image_aspect = ActiveUvImage(context).aspect
            angle = cls.get_orient_angle_by_props(g_bbox, image_aspect, orient_direction, rotate_direction)

            for obj in objs:
                me, bm = get_mesh_data(obj)
                uv_layer = verify_uv_layer(bm)
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)

                for cluster in loops:
                    TransformLoops.rotate_loops(
                        cluster,
                        uv_layer,
                        angle,
                        g_bbox.center,
                        image_aspect=image_aspect,
                        angle_in_radians=True
                    )

                bmesh.update_edit_mesh(me)

    @classmethod
    def orient_by_selection(
        cls,
        context: bpy.types.Context,
        objs: list,
        orient_direction: str,
        rotate_direction: str,
        image_aspect: float,
        processing_order: str
    ) -> None:
        """
        :param context: bpy.types.Context
        :param objs: list of blender objects
        :param orient_direction: enum in {'HORIZONTAL', 'VERTICAL'}
        :param rotate_direction: enum in {'CW', 'CWW'}
        :param image_aspect: float
        :param processing_order: enum in {'OVERALL', 'ONE_BY_ONE'}
        """
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            islands = island_util.get_island(context, bm, uv_layer)

            if not len(islands):
                continue

            if processing_order == 'ONE_BY_ONE':
                for island in islands:
                    s_loops = island_util.LoopsFactory.get_selected_loops_by_island(context, island, uv_layer)
                    bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in s_loops])
                    cl = [lp for f in island for lp in f.loops]

                    cls._orient_loops(cl, uv_layer, bbox, image_aspect, orient_direction, rotate_direction)

            elif processing_order == 'OVERALL':
                cluster = []
                for i in islands:
                    cluster.extend(i)

                s_loops = island_util.LoopsFactory.get_selected_loops_by_island(context, cluster, uv_layer)
                bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in s_loops])

                cls._orient_loops(
                    [lp for f in cluster for lp in f.loops],
                    uv_layer,
                    bbox,
                    image_aspect,
                    orient_direction,
                    rotate_direction)

            else:
                raise RuntimeError("processing_order not in {'OVERALL', 'ONE_BY_ONE'}")

            bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

    @classmethod
    def get_orient_angle_auto(cls, bbox: BoundingBox2d, image_aspect: float = 1.0) -> radians:
        """
        :param mode: enum in {'BBOX', 'BY_SELECTION}
        :param image_aspect: float
        """
        return cls.by_props_correction(bbox, bbox.get_orient_angle(image_aspect))

    @classmethod
    def get_orient_angle_by_props(
        cls,
        bbox: BoundingBox2d,
        image_aspect: float = 1.0,
        orient_direction: str = 'AUTO',
        rotate_direction: str = 'CW'

    ) -> radians:
        """
        :param image_aspect: float
        :param orient_direction: enum in {'HORIZONTAL', 'VERTICAL'}
        :param rotate_direction: enum in {'CW', 'CWW'}
        """
        return cls.by_props_correction(bbox, bbox.get_orient_angle(image_aspect), orient_direction, rotate_direction)

    @classmethod
    def _orient_loops(
        cls,
        cluster: list,
        uv_layer: bmesh.types.BMLayerItem,
        bbox: BoundingBox2d,
        image_aspect: float,
        orient_direction: str,
        rotate_direction: str
    ) -> None:

        angle = bbox.get_orient_angle(image_aspect)

        angle = cls.by_props_correction(bbox, angle, orient_direction, rotate_direction)

        TransformLoops.rotate_loops(
                    cluster,
                    uv_layer,
                    angle,
                    bbox.center,
                    image_aspect=image_aspect,
                    angle_in_radians=True
                )

    @classmethod
    def by_props_correction(
        cls,
        bbox: BoundingBox2d,
        angle: radians,
        orient_direction: str = 'AUTO',
        rotate_direction: str = 'CW'
    ) -> None:
        """
        :param mode: enum in {'BBOX', 'BY_SELECTION}
        :param image_aspect: float
        :param orient_direction: enum in {'HORIZONTAL', 'VERTICAL'}
        :param rotate_direction: enum in {'CW', 'CWW'}
        """

        if not orient_direction == 'AUTO':
            if orient_direction == 'VERTICAL':
                if bbox.is_vertical is False:
                    angle = cls.fix_near_angle(angle)
            elif orient_direction == 'HORIZONTAL':
                if bbox.is_vertical is True:
                    angle = cls.fix_near_angle(angle)

            if not abs(angle) < 0.000001:
                if rotate_direction == 'CCW':
                    if angle <= 0:
                        angle += pi
                else:
                    if angle >= 0:
                        angle -= pi

        return angle

    @classmethod
    def fix_near_angle(cls, angle: radians) -> radians:
        if angle < 0:
            return angle + pi / 2
        else:
            return angle - pi / 2
