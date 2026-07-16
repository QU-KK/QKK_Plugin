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

from .tr_utils import (
    TrConstants,
    TrOrder,
    Cursor2D,
    TrSpaceMode,
    TransformLimitsManager
)
from .tr_object_data import transform_object_data

from ZenUV.utils.bounding_box import BoundingBox2d, get_overall_bbox
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.utils.generic import get_mesh_data, verify_uv_layer
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.ops.adv_uv_maps_sys.udim_utils import UdimFactory


class TrMoveProps:
    """
    :param move_mode: {'TO_CURSOR', 'TO_POSITION', 'INCREMENT'}
    :param direction_str: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
    :param increment: Vector,
    :param destination_pos: Vector
    """

    def __init__(
        self,
        context: bpy.types.Context,
        is_global: bool
    ) -> None:

        self.scene_prop = context.scene.zen_uv
        self.is_global_settings = is_global
        self.is_align_mode = False
        self.disable_tr_space_mode = False

        # Operator MOVE Settings
        self._move_mode: str = None  # In {"INCREMENT", "TO_POSITION", "TO_CURSOR", "TO_ACTIVE_TRIM"}
        self.direction_str: str = None  # In {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
        self.increment: float = None  # float value
        self.destination_pos: Vector = None

        # Operator ALIGN Settings
        self.align_direction = 'cen'
        self.use_trim_settings = False
        self.i_pivot_as_direction = False

        # UDIM Settings
        self.tile_number: int = 1001

    @property
    def move_mode(self):
        return self._move_mode

    @move_mode.setter
    def move_mode(self, value):
        self._move_mode = value


class MoveFactory():
    """
    :param context: bpy.types.Context
    :param move_props: class TrMoveProps
    :param influence_mode: {"ISLAND", "SELECTION", "VERTICES"}
    :param objs: list of blender objects
    :param pivot point: {
        'MEDIAN', 'CENTER', 'OVERALL', 'MEDIAN_POINT', 'ACTIVE_ELEMENT',
        'ONE_BY_ONE', 'CURSOR', 'INDIVIDUAL_ORIGINS', 'BOUNDING_BOX_CENTER'
        }
    :param island_pivot: {"tl","tc","tr","lc","cen","rc","bl","bc","br"}
    """

    def __init__(
        self,
        context: bpy.types.Context,
        MoveProps: TrMoveProps,
        influence_mode: str,
        objs: list,
        pivot_point: str = 'CENTER',
        island_pivot: str = 'cen'
    ) -> None:

        self.move_modes = {
            "INCREMENT",
            "TO_POSITION",
            "TO_CURSOR",
            "TO_SEL_BBOX",
            "TO_UV_AREA",
            'TO_ACTIVE_TRIM',
            'TO_ACTIVE_COMPONENT',
            'ACTIVE_UDIM',
            'TILE_NUMBER'}
        self.message = {'INFO'}, 'Done'

        self.context = context
        self._check_MoveProps(MoveProps)
        self.influence_mode = influence_mode

        self.PROPS = MoveProps
        self.is_transform_islands = self.influence_mode == 'ISLAND'
        self.objs = objs
        self.pivot_point = pivot_point
        self.island_pivot = island_pivot

        self.dir_vector = TrConstants.dir_vector
        self.overall_offset = None
        self.overall_bbox = None

        # used for reverting cen_v and cen_h for more user convenient.
        self.opposite = False

    def move(self) -> bool:

        if self.PROPS.move_mode == 'HOLD':
            return True

        order = TrOrder.from_pivot_point(self.context, self.pivot_point)
        if self.gathering_input_data() is False:
            return False

        return self.proceed_move(self.influence_mode, order, self.island_pivot)

    def proceed_move(self, influence_mode, order, island_pivot) -> bool:

        if order == 'OVERALL':
            overall_offset = self.get_overall_offset(self.context, island_pivot=island_pivot)

        b_was_moved = False

        for obj in self.objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            if influence_mode == 'ISLAND':
                loops = island_util.LoopsFactory.loops_by_islands(self.context, bm, uv_layer)
            elif influence_mode == 'SELECTION':
                from . tr_utils import BlPivotPoint
                is_groupped = order == 'ONE_BY_ONE' or (order == 'SYSTEM_PIVOT' and BlPivotPoint.get(self.context) == 'INDIVIDUAL_ORIGINS')
                if is_groupped:
                    loops = island_util.LoopsFactory.loops_by_sel_mode(self.context, bm, uv_layer, groupped=True)
                else:
                    loops = [island_util.LoopsFactory.loops_by_sel_mode(self.context, bm, uv_layer, groupped=False), ]
            else:  # VERTICES Align mode only
                loops = island_util.LoopsFactory.loops_by_sel_mode(self.context, bm, uv_layer, groupped=False)
                order = 'ONE_BY_ONE'

            if len(loops) > 0:
                if order == 'ONE_BY_ONE':
                    if influence_mode == 'VERTICES':
                        for loop in loops:
                            offset = self.get_personal_offset(island_pivot, BoundingBox2d(points=[loop[uv_layer].uv]).get_as_dict())
                            TransformLoops.move_loops([loop, ], uv_layer, offset)
                    else:
                        for lp_cluster in loops:
                            offset = self.get_personal_offset(island_pivot, BoundingBox2d(points=[loop[uv_layer].uv for loop in lp_cluster]).get_as_dict())
                            TransformLoops.move_loops(lp_cluster, uv_layer, offset)
                else:
                    TransformLoops.move_loops([lp for group in loops for lp in group], uv_layer, overall_offset)

                b_was_moved = True
                bmesh.update_edit_mesh(me, loop_triangles=False)

        if not b_was_moved:
            self.message = {'INFO'}, 'Nothing selected'

        return b_was_moved

    def gathering_input_data(self):
        move_mode = self.PROPS.move_mode
        scene_props = self.context.scene.zen_uv
        if self.PROPS.is_align_mode:
            if self.island_pivot in ('cen_h', 'cen_v'):
                self.island_pivot = TrConstants.opposite_direction[self.island_pivot]
            if self.PROPS.align_direction in ('cen_h', 'cen_v'):
                self.PROPS.align_direction = TrConstants.opposite_direction[self.PROPS.align_direction]
                self.opposite = True
            else:
                self.opposite = False

        if self.PROPS.is_global_settings:
            if self.PROPS.is_align_mode is True:
                if scene_props.tr_type == 'SELECTION' and scene_props.tr_align_vertices:
                    self.influence_mode == 'VERTICES'

        if move_mode in self.move_modes:
            if move_mode == 'TO_SEL_BBOX':
                if self.overall_bbox is None:
                    self.overall_bbox = get_overall_bbox(self.context, from_islands=self.is_transform_islands)
                self.PROPS.destination_pos = self.overall_bbox[self.PROPS.align_direction]
            elif move_mode == 'TO_UV_AREA':
                self.PROPS.destination_pos = UV_AREA_BBOX().get_vector_by_direction(self.PROPS.align_direction)
            elif move_mode == 'ACTIVE_UDIM':
                p_active_tile = UdimFactory.get_active_udim_tile(self.context)
                if p_active_tile is None:
                    self.message = {'WARNING'}, "No Active UDIM tile"
                    return False
                self.PROPS.destination_pos = UdimFactory.get_bbox_of_udim(p_active_tile.number).get_as_dict()[self.PROPS.align_direction]
            elif move_mode == 'TILE_NUMBER':
                if not UdimFactory.is_udim_number_valid(self.PROPS.tile_number):
                    self.message = {'WARNING'}, '"Tile Number" value is not valid UDIM number'
                    return False
                self.PROPS.destination_pos = UdimFactory.get_bbox_of_udim(self.PROPS.tile_number).get_as_dict()[self.PROPS.align_direction]
            elif move_mode == 'TO_POSITION':
                if self.PROPS.is_global_settings:
                    self.PROPS.destination_pos = self.PROPS.scene_prop.tr_align_position
            elif move_mode == 'TO_ACTIVE_TRIM':
                if self._setting_up_to_active_trim_mode() is False:
                    return False
            elif move_mode == 'TO_CURSOR':
                if self.setting_up_to_cursor_mode() is False:
                    return False
            elif move_mode == 'INCREMENT':
                if self.PROPS.is_global_settings:
                    self.PROPS.increment = scene_props.tr_move_inc
            elif move_mode == 'TO_ACTIVE_COMPONENT':
                if self.context.area.type == 'IMAGE_EDITOR' and not self.context.scene.tool_settings.use_uv_select_sync:
                    self.message = {'WARNING'}, "Active Component mode is not allowed in the UV Sync Selection is Off."
                    return False
                obj = self.context.object
                if obj.type == 'MESH':
                    bm = bmesh.from_edit_mesh(obj.data)
                    uv_layer = verify_uv_layer(bm)
                    if self.is_transform_islands:
                        active_island, _ = island_util.get_active_component(self.context, bm)
                        if active_island is not None:
                            self.PROPS.destination_pos = BoundingBox2d(
                                islands=active_island,
                                uv_layer=uv_layer).get_as_dict()[self.PROPS.align_direction]
                        else:
                            self.message = {'WARNING'}, "There is no Active Island."
                            return False
                    else:
                        active_component, comp_type = island_util.get_active_component(self.context, bm, component_type='SELECTION')
                        if comp_type == 'VERTEX':
                            self.PROPS.destination_pos = BoundingBox2d(
                                points=[lp[uv_layer].uv for lp in active_component.link_loops]).get_as_dict()[self.PROPS.align_direction]
                        elif comp_type == 'EDGE':
                            self.PROPS.destination_pos = BoundingBox2d(
                                points=[lp[uv_layer].uv for lp in active_component.link_loops]).get_as_dict()[self.PROPS.align_direction]
                        elif comp_type == 'FACE':
                            self.PROPS.destination_pos = BoundingBox2d(
                                points=[lp[uv_layer].uv for lp in active_component.loops]).get_as_dict()[self.PROPS.align_direction]
                        else:
                            self.message = {'WARNING'}, "There is no Active Component."
                            return False

            if not move_mode == 'INCREMENT':
                self.PROPS.move_mode = 'TO_POSITION'

            return True
        else:
            raise RuntimeError(f"Current move_mode = {self.PROPS.move_mode}. move_mode must be in {self.move_modes}")

    def setting_up_to_cursor_mode(self):
        self.PROPS.disable_tr_space_mode = True
        c_pos = Cursor2D(self.context).uv_cursor_pos
        if c_pos is None:
            self.message = {'WARNING'}, "No UV Editor is open."
            return False
        self.PROPS.destination_pos = Cursor2D(self.context).uv_cursor_pos
        return True

    def _setting_up_to_active_trim_mode(self):
        trim = ZuvTrimsheetUtils.getActiveTrim(self.context)
        if trim is None:
            p_input_bbox = UV_AREA_BBOX().get_as_dict()
            # self.message = {'WARNING'}, "There are no Active Trim."
            # return False
        else:
            p_input_bbox = BoundingBox2d(points=(trim.left_bottom, trim.top_right)).get_as_dict()

        if trim is not None and self.PROPS.use_trim_settings:
            p_align_direction = trim.align_to
            if self.PROPS.i_pivot_as_direction:
                self.island_pivot = trim.align_to
        else:
            p_align_direction = self.PROPS.align_direction

        self.PROPS.destination_pos = p_input_bbox[p_align_direction]

        return True

    def _check_MoveProps(self, PROPS: TrMoveProps):
        if not PROPS.is_global_settings:
            if PROPS.move_mode not in self.move_modes:
                raise RuntimeError(f'TrMoveProps.move = {PROPS.move_mode} not in {self.move_modes}')
            if PROPS.move_mode == 'INCREMENT':
                if None in {PROPS.direction_str, PROPS.increment}:
                    raise RuntimeError('TrMoveProps.move = "INCREMENT". Properties direction_str, increment must be filled in.')
            if PROPS.move_mode == 'TO_POSITION':
                if PROPS.destination_pos is None:
                    raise RuntimeError('TrMoveProps.move = "TO_POSITION". Properties destination_pos must be filled in.')

    def get_personal_offset(self, island_pivot: str, i_bbox: BoundingBox2d) -> Vector:
        return self.align_mode_correction(self._calculate_offset(island_pivot, i_bbox, self.PROPS.move_mode))

    def align_mode_correction(self, _offset: Vector) -> Vector:
        if self.PROPS.is_align_mode:
            return TransformLoops.mute_axis(_offset, self.PROPS.align_direction, opposite=self.opposite)
        return _offset

    def get_overall_offset(self, context, island_pivot: str) -> Vector:
        if self.overall_bbox is None:
            self.overall_bbox = get_overall_bbox(self.context, from_islands=self.is_transform_islands)

        if self.overall_offset is None:
            self.overall_offset = self._calculate_offset(island_pivot, self.overall_bbox, self.PROPS.move_mode)
        return self.align_mode_correction(self.overall_offset)

    def _calculate_offset(self, island_pivot: str, i_bbox: BoundingBox2d, move_mode: str) -> Vector:
        if move_mode == 'INCREMENT':
            return self.dir_vector[self.PROPS.direction_str] * Vector(([self.PROPS.increment] * 2)) * TrSpaceMode(self.context, self.PROPS.disable_tr_space_mode).editor_direction

        elif move_mode == 'TO_POSITION':

            if self.PROPS.is_align_mode:
                return self.PROPS.destination_pos - i_bbox[island_pivot]

            return (self.PROPS.destination_pos - i_bbox[island_pivot]) * TrSpaceMode(self.context, self.PROPS.disable_tr_space_mode).editor_direction

        else:
            message = f"in MoveFactory._calculate_offset() move_mode == {move_mode} incorrect. Must be in ['TO_POSITION', 'INCREMENT']"
            raise RuntimeError(message)


class TrMoveProcessorEx:

    @classmethod
    def move_in_trim(
        cls,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
        lock: bool,
        inp_offset: Vector,
        limits_bbox: BoundingBox2d
    ) -> str:
        TransformLimitsManager.results.clear()

        if not transform_object_data.is_valid(objs, influence_mode, order):
            transform_object_data.setup(context, objs, influence_mode, order)

        message = 'Finished' if transform_object_data.object_storage else 'No selected islands'

        i_out_trim_element_count = 0

        for obj, info in transform_object_data.object_storage.items():
            me = info.me
            uv_layer = info.uv_layer
            loops = info.loops

            for cluster in loops:
                offset = inp_offset.copy() * TrSpaceMode(context).editor_direction
                if lock:
                    cluster_bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in cluster])
                    anchor = cluster_bbox.center
                    if cluster_bbox.inside_of_bbox(limits_bbox):
                        TransformLimitsManager.fill(anchor, cluster_bbox, limits_bbox, Vector((1.0, 1.0)))
                        offset = TransformLimitsManager.get_offset(offset)
                        TransformLoops.move_loops(cluster, uv_layer, offset)
                    else:
                        i_out_trim_element_count += 1
                        message = f'Out of Trim: {i_out_trim_element_count} element(s)'
                else:
                    TransformLoops.move_loops(cluster, uv_layer, offset)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        if False in TransformLimitsManager.results:
            return 'Limit reached'

        return message


class TrMoveProcessor:

    @classmethod
    def move_in_trim(
        cls,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
        lock: bool,
        inp_offset: Vector,
        limits_bbox: BoundingBox2d
    ) -> str:
        message = 'Finished'
        TransformLimitsManager.results.clear()
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            if influence_mode == 'ISLAND':
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
            else:
                loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)

            if order == 'OVERALL':
                loops = [[lp for group in loops for lp in group], ]

            for cluster in loops:
                offset = inp_offset.copy() * TrSpaceMode(context).editor_direction
                cluster_bbox = BoundingBox2d(points=[loop[uv_layer].uv for loop in cluster])
                anchor = cluster_bbox.center
                if lock:
                    if cluster_bbox.inside_of_bbox(limits_bbox):
                        TransformLimitsManager.fill(anchor, cluster_bbox, limits_bbox, Vector((1.0, 1.0)))
                        offset = TransformLimitsManager.get_offset(offset)
                        TransformLoops.move_loops(cluster, uv_layer, offset)
                    else:
                        message = 'Out of Trim'
                else:
                    TransformLoops.move_loops(cluster, uv_layer, offset)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        if False in TransformLimitsManager.results:
            return 'Limit reached'

        return message


class TrMove2dCursor:

    report = []

    @classmethod
    def get_position(cls, context: bpy.types.Context, influence: str = 'POSITION', island_pivot: str = 'cen', tile_number: int = 1001, position: Vector = Vector((0.0, 0.0))):

        if influence in {'ISLAND', 'SELECTION'}:
            p_pivot = get_overall_bbox(context, influence == 'ISLAND')[island_pivot]

        elif influence == 'UV_AREA':
            p_pivot = UV_AREA_BBOX.get_as_dict()[island_pivot]

        elif influence == 'ACTIVE_UDIM':
            p_active_tile = UdimFactory.get_active_udim_tile(context)
            if p_active_tile is None:
                cls.report = [{'WARNING'}, "No Active UDIM tile"]
                return False
            p_pivot = UdimFactory.get_bbox_of_udim(p_active_tile.number).get_as_dict()[island_pivot]

        elif influence == 'TILE_NUMBER':
            if not UdimFactory.is_udim_number_valid(tile_number):
                cls.report = {'WARNING'}, '"Tile Number" value is not valid UDIM number'
                return False
            p_pivot = UdimFactory.get_bbox_of_udim(tile_number).get_as_dict()[island_pivot]

        elif influence == 'TO_POSITION':
            p_pivot = position

        else:
            raise RuntimeError('self.influence value is incorrect')

        return p_pivot
