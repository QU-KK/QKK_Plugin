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
from math import pi
import numpy as np
from itertools import chain
from mathutils import Vector

from .tr_utils import TrConstants, TrOrder, ActiveUvImage
from .tr_object_data import TrObjectInfo

from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import get_mesh_data, verify_uv_layer
from ZenUV.utils.bounding_box import BoundingBox2d, get_overall_bbox
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.ops.adv_uv_maps_sys.udim_utils import UdimFactory


class FitRegion:
    '''
    Represents Region defined by 2 vectors
    bl - Bottom-Left
    tr - Top-Right
    '''
    def __init__(
        self,
        vec_01: Vector = Vector((0.0, 0.0)),
        vec_02: Vector = Vector((1.0, 1.0))
    ) -> None:

        self.is_global_settings = False
        self.bl = vec_01
        self.tr = vec_02
        self.bbox = BoundingBox2d(islands=None, points=(self.bl, self.tr))
        self.from_where = None

        self.aspect = self.bbox.aspect

        self.padding = 0.0
        self.keep_proportion = True
        self.align_to = 'cen'
        self.fit_axis = 'AUTO'
        self.match_rotation = False

        self.flip = False

        self.report_message = None, None

    def fill_from_global(self, context, island_pivot):
        # props = TrFitProps(context)
        props = context.scene.zen_uv
        self.bl = TrConstants.uv_area_bl
        self.tr = props.tr_fit_bound
        self.bbox = BoundingBox2d(islands=None, points=(self.bl, self.tr))
        self.padding = props.tr_fit_padding
        self.fit_axis = TrConstants.global_fit_axis[island_pivot]
        self.align_to = island_pivot
        self.is_global_settings = True
        self.tr_type = props.tr_type
        self.per_face = props.tr_fit_per_face

    def from_active_trim(self, context):
        trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if trim is None:
            self.from_uv_area(context)
        else:

            self.bl = trim.left_bottom
            self.tr = trim.top_right
            self.bbox = BoundingBox2d(points=(self.bl, self.tr))
            self.padding = trim.inset
            self.keep_proportion = trim.keep_proportion
            self.align_to = trim.align_to
            self.fit_axis = trim.fit_axis
            self.match_rotation = trim.match_rotation if hasattr(trim, 'match_rotation') else False

        return True

    def from_uv_area(self, context):

        a_bbox = BoundingBox2d(points=(UV_AREA_BBOX().corners))
        self.bl = a_bbox.bot_left
        self.tr = a_bbox.top_right
        self.bbox = a_bbox

        return True

    def from_udim_tile(self, tile_number):
        if not UdimFactory.is_udim_number_valid(tile_number):
            self.report_message = {'WARNING'}, '"Tile Number" value is not valid UDIM number'
            return False
        self.bbox = UdimFactory.get_bbox_of_udim(tile_number)
        self.bl = self.bbox.bot_left
        self.tr = self.bbox.top_right

        return True

    def from_active_udim(self, context):
        p_active_tile = UdimFactory.get_active_udim_tile(context)
        if p_active_tile is None:
            self.report_message = {'WARNING'}, "No Active UDIM tile"
            return False
        self.bbox = UdimFactory.get_bbox_of_udim(p_active_tile.number)
        self.bl = self.bbox.bot_left
        self.tr = self.bbox.top_right

        return True


class TrFitFactory:

    def __init__(
        self,
        context: bpy.types.Context,
        influence_mode: str,
        objs: list,
        pivot_point: str,
        fit_region: FitRegion = None,
        auto_rotate: bool = False
    ) -> None:

        self.context = context
        self.influence_mode = influence_mode
        self.objs = objs
        self.pivot_point = pivot_point

        self.auto_rotate = auto_rotate

        self.FR = fit_region

    def fit(self) -> None:
        FR = self.FR
        if FR.is_global_settings:
            if FR.tr_type == 'SELECTION' and FR.per_face:
                influence_mode = 'FACES'
            else:
                influence_mode = self.influence_mode
        else:
            influence_mode = self.influence_mode

        TrFitProcessor.fit(
            context=self.context,
            objs=self.objs,
            influence_mode=influence_mode,
            order=TrOrder.from_pivot_point(self.context, self.pivot_point),
            fr_bbox=FR.bbox,
            padding=FR.padding,
            fit_axis=FR.fit_axis,
            keep_proportion=FR.keep_proportion,
            align_to=FR.align_to,
            auto_rotate=FR.match_rotation,
            flip=FR.flip,
            angle=0.0,
            image_aspect=ActiveUvImage(self.context).aspect
        )


class TrFitProcessorEx:
    def __init__(self) -> None:
        self.object_storage = {}
        self.influence_mode = ''
        self.order = ''

    def setup(self, context, objs, influence_mode, order):
        self.influence_mode = influence_mode
        self.object_storage.clear()
        self.order = order
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                if influence_mode == 'ISLAND':
                    loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
                elif influence_mode == 'SELECTION':
                    loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)
                elif influence_mode == 'FACES':
                    loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=False, per_face=True)
                    self.order = 'ONE_BY_ONE'
                else:
                    message = f"current influence_mode is '{influence_mode}' not in ['ISLAND', 'SELECTION', 'FACES']"
                    raise RuntimeError(message)

                if len(loops) > 0:
                    if self.order == 'ONE_BY_ONE':
                        self.loops = [[lp for group in loops for lp in group], ]

                    self.object_storage[obj] = TrObjectInfo(bm=bm, me=me, loops=loops, uv_layer=uv_layer)

    def process(
        self,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
        fr_bbox: BoundingBox2d,
        padding: float,
        fit_axis: str,
        keep_proportion: bool,
        align_to: str,
        auto_rotate: bool = False,
        flip: bool = False,
        angle: float = 0.0,
        image_aspect: float = 1.0,
        rnd_angle: bool = False
    ) -> None:

        op_order = order if influence_mode != 'FACES' else 'ONE_BY_ONE'

        res = (
            self.influence_mode == influence_mode and
            self.order == op_order and
            (len(self.object_storage) != 0) == (len(objs) != 0) and
            set(self.object_storage.keys()).issubset(objs)
            )
        if not res:
            try:
                # this operation will check that loops are still actual
                for _, v in self.object_storage.items():
                    for lp_cluster in v.loops:
                        if lp_cluster:
                            _ = lp_cluster[0][v.uv_layer]
                            break
            except Exception:
                res = True

        if res:
            self.setup(context, objs, influence_mode, op_order)

        for obj, info in self.object_storage.items():
            me = info.me
            uv_layer = info.uv_layer

            loops = info.loops

            if rnd_angle:
                angles = np.random.uniform(-abs(angle), abs(angle), len(loops))
            else:
                angles = np.full(len(loops), angle)

            info.loops_data.clear()
            idx = 0

            if self.order == 'ONE_BY_ONE':
                for lp_cluster, angle in zip(loops, angles):
                    angle = self._get_matching_angle(context, fr_bbox, uv_layer, lp_cluster, image_aspect) if auto_rotate else angle

                    fit_pivot = TransformLoops.fit_loops(
                        lp_cluster,
                        uv_layer,
                        fr_bbox,
                        fit_axis_name=fit_axis,
                        keep_proportion=keep_proportion,
                        align_to=align_to,
                        padding=padding,
                        angle=angle,
                        image_aspect=image_aspect,
                        flip=flip
                    )

                    info.loops_data[idx] = fit_pivot.copy()
                    idx += 1
            else:
                for lp_cluster in loops:
                    fit_pivot = TransformLoops.fit_loops(
                        lp_cluster,
                        uv_layer,
                        fr_bbox,
                        fit_axis_name=fit_axis,
                        keep_proportion=keep_proportion,
                        align_to=align_to,
                        padding=padding,
                        angle=self._get_matching_angle(context, fr_bbox, uv_layer, lp_cluster, image_aspect) if auto_rotate else angle,
                        image_aspect=image_aspect,
                        flip=flip
                    )

                    info.loops_data[idx] = fit_pivot.copy()
                    idx += 1

            bmesh.update_edit_mesh(me, loop_triangles=False)

    @classmethod
    def _get_matching_angle(cls, context, fr_bbox, uv_layer, lp_cluster, image_aspect):
        cl_bbox = BoundingBox2d(points=([lp[uv_layer].uv for lp in lp_cluster]))
        angle = cl_bbox.get_orient_angle(ActiveUvImage(context).aspect)

        if fr_bbox.aspect == 1 and image_aspect != 1:
            if fr_bbox.is_vertical != cl_bbox.is_vertical:
                return pi / 2 + angle
            else:
                return angle

        if fr_bbox.aspect != 1 and cl_bbox != 1:
            if fr_bbox.is_vertical != cl_bbox.is_vertical:
                return pi / 2 + angle
            else:
                return angle
        return angle


class TrFitProcessor:

    @classmethod
    def fit(
        cls,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
        fr_bbox: BoundingBox2d,
        padding: float,
        fit_axis: str,
        keep_proportion: bool,
        align_to: str,
        auto_rotate: bool = False,
        flip: bool = False,
        angle: float = 0.0,
        image_aspect: float = 1.0,
        rnd_angle: bool = False
    ) -> None:
        """
        :param context: bpy.types.Context
        :param objs: list of blender objects
        :param influence_mode: {'ISLAND', 'SELECTION', 'FACES'}
        :param order: {'ONE_BY_ONE', 'OVERALL}
        :param fr_bbox: BoundingBox2d. Fit region Bounding box
        :param padding: float. Padding value from Fit region bbox
        :param fit_axis: {'U', 'V', 'MIN', 'MAX', 'AUTO'}
        :param keep_proportion: Bool
        :param align_to: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
        :param auto_rotate: bool
        :param flip: bool
        :param image_aspect: float
        :param rnd_angle: bool randomize angle in one by one mode
        """

        obj_loops = []
        obj_count = len(objs)
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            if influence_mode == 'ISLAND':
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
            elif influence_mode == 'SELECTION':
                loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)
            elif influence_mode == 'FACES':
                loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=False, per_face=True)
                order = 'ONE_BY_ONE'
            else:
                message = f"current influence_mode is '{influence_mode}' not in {'ISLAND', 'SELECTION', 'FACES'}"
                raise RuntimeError(message)

            if rnd_angle:
                angles = np.random.uniform(-abs(angle), abs(angle), len(loops))
            else:
                angles = np.full(len(loops), angle)

            if order == 'ONE_BY_ONE':
                for lp_cluster, angle in zip(loops, angles):
                    angle = cls._get_matching_angle(context, fr_bbox, uv_layer, lp_cluster, image_aspect) if auto_rotate else angle

                    TransformLoops.fit_loops(
                        lp_cluster,
                        uv_layer,
                        fr_bbox,
                        fit_axis_name=fit_axis,
                        keep_proportion=keep_proportion,
                        align_to=align_to,
                        padding=padding,
                        angle=angle,
                        image_aspect=image_aspect,
                        flip=flip
                    )
                bmesh.update_edit_mesh(obj.data, loop_triangles=False)

            elif order == 'OVERALL' and obj_count == 1:
                lp_cluster = [lp for group in loops for lp in group]

                if not lp_cluster:
                    return

                TransformLoops.fit_loops(
                    lp_cluster,
                    uv_layer,
                    fr_bbox,
                    fit_axis_name=fit_axis,
                    keep_proportion=keep_proportion,
                    align_to=align_to,
                    angle=cls._get_matching_angle(context, fr_bbox, uv_layer, lp_cluster, image_aspect) if auto_rotate else angle,
                    image_aspect=image_aspect,
                    flip=flip
                )
                bmesh.update_edit_mesh(obj.data, loop_triangles=False)

            elif order == 'OVERALL' and obj_count > 1:
                loops = chain.from_iterable(loops) if loops and isinstance(loops[0], list) else loops
                obj_loops.append((obj, [[lp.index, lp[uv_layer].uv.copy()] for lp in loops]))

        if order == 'OVERALL' and obj_count > 1:
            uvs = [Vector((uv.x, uv.y, 1.0)) for obj, data in obj_loops for _, uv in data]

            M = TransformLoops.get_fit_transform_matrix(
                uvs=uvs,
                fit_bbox=fr_bbox,
                fit_axis_name=fit_axis,
                keep_proportion=keep_proportion,
                align_to=align_to,
                angle=cls._get_matching_angle(context, fr_bbox, uv_layer, uvs, image_aspect) if auto_rotate else angle,
                image_aspect=image_aspect,
                flip=flip
            )

            for obj, data in obj_loops:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.verify()

                loop_map = {loop.index: loop for face in bm.faces for loop in face.loops}

                for loop_index, uv in data:
                    loop = loop_map.get(loop_index)
                    if loop is not None:
                        uv = loop[uv_layer].uv
                        uv3d = Vector((uv.x, uv.y, 1.0))
                        loop[uv_layer].uv = (M @ uv3d).xy

                bmesh.update_edit_mesh(obj.data, loop_triangles=False)

    @classmethod
    def _get_matching_angle(cls, context, fr_bbox, uv_layer, lp_cluster, image_aspect):
        cl_bbox = BoundingBox2d(points=([lp[uv_layer].uv for lp in lp_cluster]))
        angle = cl_bbox.get_orient_angle(ActiveUvImage(context).aspect)

        if fr_bbox.aspect == 1 and image_aspect != 1:
            if fr_bbox.is_vertical != cl_bbox.is_vertical:
                return pi / 2 + angle
            else:
                return angle

        if fr_bbox.aspect != 1 and cl_bbox != 1:
            if fr_bbox.aspect > 1 and image_aspect < 1:
                angle -= pi / 2
            if fr_bbox.is_vertical != cl_bbox.is_vertical:
                return pi / 2 + angle
            else:
                return angle
        return angle
