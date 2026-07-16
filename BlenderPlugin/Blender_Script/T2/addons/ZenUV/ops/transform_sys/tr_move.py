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

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
from ZenUV.ops.transform_sys.tr_labels import TrLabels
from ZenUV.utils.generic import get_mesh_data, verify_uv_layer
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.ops.adv_uv_maps_sys.udim_utils import UdimFactory
from ZenUV.utils.blender_zen_utils import ZenPolls

from .transform_utils.tr_utils import TransformSysOpsProps
from . transform_utils.tr_move_utils import TrMoveProps, MoveFactory, TrMove2dCursor


class ZUV_OT_TrMove(bpy.types.Operator):
    bl_idname = "uv.zenuv_move"
    bl_label = "Move"
    bl_description = "Move selected Islands or Selection"
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode: TransformSysOpsProps.influence_mode
    op_order: TransformSysOpsProps.get_order_prop()
    move_mode: bpy.props.EnumProperty(
        name='Move',
        description="Transform Mode",
        items=[
                ("INCREMENT", "By Increment", ""),
                ("TO_POSITION", "To Position", ""),
                ("TO_CURSOR", "To 2D Cursor", ""),
                ("TO_ACTIVE_TRIM", "To Active Trim Center", ""),
                ("TO_M_CURSOR", "To Mouse Cursor", "")
            ],
        default="INCREMENT"
    )

    # Operator Settings
    direction: TransformSysOpsProps.direction
    increment: bpy.props.FloatProperty(
        name=TrLabels.PROP_MOVE_INCREMENT_LABEL,
        default=1.0,
        min=0,
        step=0.1,
    )
    destination_pos: bpy.props.FloatVectorProperty(
        name="Position",
        size=2,
        default=(0.0, 0.0),
        subtype='COORDINATES',
    )
    mouse_pos: bpy.props.FloatVectorProperty(
        name="Mouse Position",
        size=2,
        default=(0.5, 0.5),
        subtype='XYZ',
        options={'HIDDEN'}
    )

    island_pivot: TransformSysOpsProps.island_pivot

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        self.mouse_pos = context.region.view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "influence_mode")
        layout.prop(self, "op_order")
        layout.prop(self, "move_mode")

        if self.move_mode not in {'TO_CURSOR', 'TO_M_CURSOR', "TO_ACTIVE_TRIM"}:
            layout.separator()
            box = layout.box()
            box.label(text='Settings:')

        if self.move_mode == 'TO_POSITION':
            box.prop(self, "destination_pos")
        elif self.move_mode == 'TO_CURSOR':
            pass
        elif self.move_mode == "INCREMENT":
            box.prop(self, 'direction')
            box.prop(self, "increment")

        if self.move_mode in {'TO_CURSOR', 'TO_POSITION', "TO_M_CURSOR", "TO_ACTIVE_TRIM"}:
            box = layout.box()
            box.label(text='Advanced:')
            box.prop(self, "island_pivot")

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        move_mode = self.move_mode

        if self.move_mode == 'TO_M_CURSOR':
            if context.area.type == 'IMAGE_EDITOR':
                destination_pos = self.mouse_pos
                move_mode = 'TO_POSITION'
            else:
                move_mode = 'HOLD'
                destination_pos = self.destination_pos
                self.report({'WARNING'}, "Move To Mouse Cursor allowed only in the UV Editor")
        else:
            destination_pos = self.destination_pos

        MP = TrMoveProps(context, is_global=False)
        MP.move_mode = move_mode
        MP.direction_str = self.direction
        MP.increment = self.increment
        MP.destination_pos = destination_pos

        MF = MoveFactory(
            context,
            MP,
            self.influence_mode,
            objs,
            self.op_order,
            self.island_pivot
        )
        if not MF.move():
            self.report(MF.message[0], MF.message[1])
            return {'CANCELLED'}

        return {'FINISHED'}


class ZUV_OT_MoveToUvArea(bpy.types.Operator):
    bl_idname = "uv.zenuv_move_to_uv_area"
    bl_label = "Move To UV Area"
    bl_description = "Move islands to UV area, active UDIM tile, or UDIM tile defined by number"
    bl_options = {'REGISTER', 'UNDO'}

    move_mode: bpy.props.EnumProperty(
        name='Move to',
        description="Transform Mode",
        items=[
                ("UV_AREA", "UV Area", "Move selection to the UV Area"),
                ("ACTIVE_UDIM", "Active UDIM tile", "Move selection to the active UDIM Tile"),
                ("TILE_NUMBER", "Tile Number", "Move the selection to the tile with the specified number")
            ],
        default="UV_AREA")
    tile_number: bpy.props.IntProperty(
        name='Tile Number',
        description='Number of UDIM tile',
        default=1001,
        min=UdimFactory.min_udim_number,
        max=UdimFactory.max_udim_number)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'move_mode')
        row = layout.row()
        row.enabled = self.move_mode == 'TILE_NUMBER'
        row.prop(self, 'tile_number')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)

            for cluster in loops:
                cp = BoundingBox2d(points=[loop[uv_layer].uv for loop in cluster]).center

                if self.move_mode == 'UV_AREA':
                    offset = Vector((cp.x % 1, cp.y % 1)) - cp
                elif self.move_mode in {'ACTIVE_UDIM', 'TILE_NUMBER'}:
                    if self.move_mode == 'ACTIVE_UDIM':
                        p_active_tile = UdimFactory.get_active_udim_tile(context)
                        if p_active_tile is None:
                            self.report({'WARNING'}, "Zen UV: No Active UDIM tile")
                            return {'CANCELLED'}
                        p_tile_co = UdimFactory.convert_udim_name_to_id(p_active_tile.number)
                    elif self.move_mode == 'TILE_NUMBER':
                        if UdimFactory.is_udim_number_valid(self.tile_number):
                            p_tile_co = UdimFactory.convert_udim_name_to_id(self.tile_number)
                        else:
                            self.report({'WARNING'}, '"Tile Number" value is not valid UDIM number')
                            return {'CANCELLED'}
                    offset = Vector((cp.x % 1, cp.y % 1)) - cp + Vector(p_tile_co)
                else:
                    raise RuntimeError("move_mode not in {'UV_AREA', 'ACTIVE_UDIM', 'TILE_NUMBER'}")

                TransformLoops.move_loops(cluster, uv_layer, offset)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_MoveToUvAreaMouseover(bpy.types.Operator):
    bl_idname = "uv.zenuv_move_to_uv_area_mouseover"
    bl_label = "Move To UV Area"
    bl_description = "Move center of the selected Islands to the UV Area using mouse position"
    bl_options = {'REGISTER', 'UNDO'}

    def __del__(self):
        self.cancel(bpy.context)

    x: bpy.props.IntProperty(
        name='X',
        description='X position',
        default=0
    )
    y: bpy.props.IntProperty(
        name='Y',
        description='Y position',
        default=0
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.area.type == "IMAGE_EDITOR"

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # NOTE: is already running
        if self.bl_idname in bpy.app.driver_namespace:
            return {'CANCELLED'}

        bpy.app.driver_namespace[self.bl_idname] = ZenPolls.SESSION_UUID
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set(f"{self.bl_label} - Enter/LMB: Confirm, Esc/RMB: Cancel")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'} or bpy.app.driver_namespace.get(self.bl_idname, Ellipsis) != ZenPolls.SESSION_UUID:
            self.cancel(context)
            return {'CANCELLED'}

        elif event.type in {'LEFTMOUSE', 'RET'}:
            return self.execute(context)

        context.window.cursor_modal_set('EYEDROPPER')

        return {'PASS_THROUGH'}

    def execute(self, context):
        self.cancel(context)

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        from ZenUV.ops.event_service import get_blender_event

        p_event = get_blender_event(force=True)
        self.x, self.y = p_event.get('mouse_region_x', 0), p_event.get('mouse_region_y', 0)
        l_uv_co = context.region.view2d.region_to_view(self.x, self.y)

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)

            for cluster in loops:
                cp = BoundingBox2d(points=[loop[uv_layer].uv for loop in cluster]).center
                offset = self.cutoff_value(l_uv_co) - self.cutoff_value(cp)

                TransformLoops.move_loops(cluster, uv_layer, offset)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

        return {'FINISHED'}

    def cutoff_value(self, value: list) -> Vector:
        return Vector(value) - Vector((value[0] % 1, value[1] % 1))

    def cancel(self, context: bpy.types.Context):
        # NOTE: check is operator is running
        if self.bl_idname in bpy.app.driver_namespace:
            del bpy.app.driver_namespace[self.bl_idname]

            if context.window:
                context.window.cursor_modal_restore()
            if context.workspace:
                context.workspace.status_text_set(None)


class ZUV_OT_MoveToUvPositionMouseover(bpy.types.Operator):
    bl_idname = "uv.zenuv_move_to_uv_position_mouseover"
    bl_label = "Move To UV Position"
    bl_description = "Move center of the selected Islands to the UV coordinates defined by mouse"
    bl_options = {'REGISTER', 'UNDO'}

    def __del__(self):
        self.cancel(bpy.context)

    x: bpy.props.IntProperty(
        name='X',
        description='X position',
        default=0
    )
    y: bpy.props.IntProperty(
        name='Y',
        description='Y position',
        default=0
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.area.type == "IMAGE_EDITOR"

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # NOTE: is already running
        if self.bl_idname in bpy.app.driver_namespace:
            return {'CANCELLED'}

        bpy.app.driver_namespace[self.bl_idname] = ZenPolls.SESSION_UUID
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set(f"{self.bl_label} - Enter/LMB: Confirm, Esc/RMB: Cancel")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'} or bpy.app.driver_namespace.get(self.bl_idname, Ellipsis) != ZenPolls.SESSION_UUID:
            self.cancel(context)
            return {'CANCELLED'}

        elif event.type in {'LEFTMOUSE', 'RET'}:
            return self.execute(context)

        context.window.cursor_modal_set('EYEDROPPER')

        return {'PASS_THROUGH'}

    def execute(self, context):
        self.cancel(context)

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        from ZenUV.ops.event_service import get_blender_event

        p_event = get_blender_event(force=True)
        self.x, self.y = p_event.get('mouse_region_x', 0), p_event.get('mouse_region_y', 0)
        l_uv_co = context.region.view2d.region_to_view(self.x, self.y)

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.verify()

            loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)

            for cluster in loops:
                cp = BoundingBox2d(points=[loop[uv_layer].uv for loop in cluster]).center
                offset = Vector(l_uv_co) - cp

                TransformLoops.move_loops(cluster, uv_layer, offset)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

        return {'FINISHED'}

    def cutoff_value(self, value: list) -> Vector:
        return Vector(value) - Vector((value[0] % 1, value[1] % 1))

    def cancel(self, context: bpy.types.Context):
        # NOTE: check is operator is running
        if self.bl_idname in bpy.app.driver_namespace:
            del bpy.app.driver_namespace[self.bl_idname]

            if context.window:
                context.window.cursor_modal_restore()
            if context.workspace:
                context.workspace.status_text_set(None)


class ZUV_OT_MoveGrabIncrement(bpy.types.Operator):
    bl_idname = "uv.zenuv_grab_offset"
    bl_label = "Grab Increment"
    bl_description = "Get the distance between two vertices or edge lendth and use it as the offset value for the move"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects.")
            return {'CANCELLED'}
        props = context.scene.zen_uv
        p_selection = set()
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            p_selection.update(lp[uv_layer].uv.copy().freeze() for lp in island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer))
        if not len(p_selection) == 2:
            self.report({'WARNING'}, "Zen UV: Select only two vertices or one edge.")
            return {'CANCELLED'}
        p_selection = list(p_selection)
        props.tr_move_inc = abs((p_selection[0] - p_selection[1]).magnitude)

        return {'FINISHED'}


class ZUV_OT_Move2dCursorTo(bpy.types.Operator):
    bl_idname = "uv.zenuv_move_cursor_to"
    bl_label = "Move 2D Cursor To"
    bl_description = "Move 2D Cursor To"
    bl_options = {'REGISTER', 'UNDO'}

    influence: bpy.props.EnumProperty(
        name='Influence',
        description="How to set the 2D Cursor",
        items=[
            ("ISLAND", "Islands", "To islands", 'UV_ISLANDSEL', 0),
            ("SELECTION", "Selection", "To selection", 'UV_FACESEL', 1),
            ("UV_AREA", "UV Area", "To UV Area", 'VIEW_ORTHO', 2),
            ("TO_POSITION", "To Position", "To the defined position", 3),
            ("ACTIVE_UDIM", "Active UDIM tile", "To active UDIM tile", 4),
            ("TILE_NUMBER", "Tile Number", "To UDIM tile with the specified number", 5)
        ],
        default="ISLAND"
    )

    island_pivot: TransformSysOpsProps.island_pivot

    tile_number: bpy.props.IntProperty(
        name='Tile Number',
        description='Number of UDIM tile',
        default=1001,
        min=UdimFactory.min_udim_number,
        max=UdimFactory.max_udim_number)

    position: bpy.props.FloatVectorProperty(
        name="Position",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ',
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'influence')

        row = layout.row()
        row.enabled = self.influence != 'TO_POSITION'
        row.prop(self, 'island_pivot')

        row = layout.row()
        row.enabled = self.influence == 'TILE_NUMBER'
        row.prop(self, 'tile_number')

        row = layout.row()
        row.enabled = self.influence == 'TO_POSITION'
        row.prop(self, 'position')

    def execute(self, context):

        p_pivot = TrMove2dCursor.get_position(
            context,
            self.influence,
            self.island_pivot,
            self.tile_number,
            self.position
        )

        if p_pivot is False:
            self.report(TrMove2dCursor.report[0], TrMove2dCursor.report[1])
            return {'CANCELLED'}

        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.cursor_location = p_pivot

        return {'FINISHED'}


uv_tr_move_classes = (
    ZUV_OT_TrMove,
    ZUV_OT_MoveToUvArea,
    ZUV_OT_MoveGrabIncrement,
    ZUV_OT_Move2dCursorTo,
    ZUV_OT_MoveToUvAreaMouseover,
    ZUV_OT_MoveToUvPositionMouseover
)


def register_tr_move():
    RegisterUtils.register(uv_tr_move_classes)


def unregister_tr_move():
    RegisterUtils.unregister(uv_tr_move_classes)
