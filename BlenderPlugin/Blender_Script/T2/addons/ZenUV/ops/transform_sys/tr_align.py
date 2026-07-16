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
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import (
    resort_objects_by_selection,
    get_mesh_data,
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer
)
from .transform_utils.tr_utils import TransformSysOpsProps
from .tr_move import TrMoveProps, MoveFactory
from ZenUV.utils.transform import (
    get_bbox,
    bound_box,
    UvTransformUtils
)
from ZenUV.utils.bounding_box import get_bbox_loops
from . tr_labels import TrLabels
from ZenUV.ops.adv_uv_maps_sys.udim_utils import UdimFactory


class ZUV_OT_TrAlign(bpy.types.Operator):
    bl_idname = "uv.zenuv_align"
    bl_label = "Align"
    bl_description = "Align selected Islands or Selection"
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Transform Mode",
        items=[
            ("ISLAND", "Islands", ""),
            ("SELECTION", "Selection", ""),
            ("VERTICES", "Vertices", ""),
        ],
        default="ISLAND"
    )
    op_order: TransformSysOpsProps.get_order_prop()
    align_to: bpy.props.EnumProperty(
        name='Align',
        description="Transform Mode",
        items=[
                # ("TO_UDIM", "To UDIM", "")
                ("TO_SEL_BBOX", "To Selection Bounding Box", ""),
                ("TO_POSITION", "To Position", ""),
                ("TO_CURSOR", "To 2D Cursor", ""),
                ("TO_UV_AREA", "To UV Area Bounding Box", ""),
                ("TO_ACTIVE_COMPONENT", "To Active Component", ""),
                ("ACTIVE_UDIM", "Active UDIM tile", "To active UDIM tile"),
                ("TILE_NUMBER", "Tile Number", "To UDIM tile with the specified number")
            ],
        default="TO_SEL_BBOX"
    )

    # Operator Settings
    direction: TransformSysOpsProps.direction
    increment: bpy.props.FloatProperty(
        name=TrLabels.PROP_MOVE_INCREMENT_LABEL,
        default=1.0,
        min=0,
        step=0.1,
    )
    destination: bpy.props.FloatVectorProperty(
        name="Position",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ',
    )
    align_direction: TransformSysOpsProps.align_direction
    i_pivot_as_direction: bpy.props.BoolProperty(name='As Direction', default=True, description='Set the island pivot to be the same as the alignment direction')
    island_pivot: TransformSysOpsProps.align_direction
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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "influence_mode")
        row = layout.row()
        row.enabled = not self.influence_mode == 'VERTICES'
        row.prop(self, "op_order")
        layout.prop(self, "align_to")

        layout.separator()
        box = layout.box()
        box.label(text='Settings:')

        if self.align_to == 'TILE_NUMBER':
            box.prop(self, 'tile_number')
        elif self.align_to == 'TO_POSITION':
            box.prop(self, "destination")

        box.prop(self, 'align_direction', text='Align Direction')
        row = box.row()
        if self.i_pivot_as_direction:
            lock_icon = "LOCKED"
        else:
            lock_icon = "UNLOCKED"
        row.prop(self, "i_pivot_as_direction", icon=lock_icon, icon_only=True)
        row = row.row()
        row.enabled = not self.i_pivot_as_direction
        row.prop(self, "island_pivot")

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        if self.influence_mode == 'VERTICES':
            self.op_order = 'ONE_BY_ONE'

        if self.i_pivot_as_direction:
            self.island_pivot = self.align_direction

        MP = TrMoveProps(context, is_global=False)
        MP.move_mode = self.align_to

        MP.is_align_mode = True
        MP.align_direction = self.align_direction
        MP.destination_pos = self.destination

        MP.tile_number = self.tile_number

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


class ZUV_OT_AlignGrabPosition(bpy.types.Operator):
    bl_idname = "uv.zenuv_align_grab_position"
    bl_label = "Grab Position"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Grab Position"

    desc: bpy.props.StringProperty(name="Description", default="Grab Selection coordinates (center) into Position field", options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_desctiption

    def execute(self, context):
        prop = context.scene.zen_uv
        prop.tr_align_position = get_bbox_loops(context)['cen']
        return {"FINISHED"}


class ZUV_OT_SimpleStack(bpy.types.Operator):
    bl_idname = "uv.zenuv_simple_stack"
    bl_label = "Simple Stack"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Places the islands in the stack, with no respect for their topology"

    def position_items(self, context):
        if context and 'IMAGE_EDITOR' in [area.type for area in context.screen.areas]:
            return [
                ("AVERAGE", "Average", "Averaged islands positions", 0),
                ("UVCENTER", "UV Area Center", "The center of the UV Area", 1),
                ("CUSTOM", "Custom Position", "Custom user defined position", 2),
                # ("ACTIVE", "Active", "", 3),
                ('CURSOR', '2D Cursor', 'The 2D Cursor location', '', 3)
            ]
        else:
            return [
                ("AVERAGE", "Average", "Averaged islands positions", 0),
                ("UVCENTER", "UV Area Center", "The center of the UV Area", 1),
                ("CUSTOM", "Custom Position", "Custom user defined position", 2)
                # ("ACTIVE", "Active", "", 3),
            ]

    position: bpy.props.EnumProperty(
        name="Position Type",
        description="The position type where the islands will be placed",
        items=position_items,
        default=1
    )
    custom_position: bpy.props.FloatVectorProperty(
        name="Position",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ'
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "position")

        is_enabled = False
        if self.position == 'CUSTOM':
            is_enabled = True
        elif self.position == 'AVERAGE':
            p_position = (0, 0)
        elif self.position == 'UVCENTER':
            p_position = (0.5, 0.5)
        elif self.position == 'CURSOR':
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    p_position = area.spaces.active.cursor_location[:]
                else:
                    p_position = (0, 0)
        else:
            p_position = (0, 0)

        col = layout.column(align=True)
        col.enabled = is_enabled
        col.prop(self, "custom_position")
        if not is_enabled:
            self.custom_position = p_position

    def execute(self, context):
        objs = resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        position = Vector((0.5, 0.5))
        if self.position == "AVERAGE":
            position = get_bbox(context)['cen']
        elif self.position == "CUSTOM":
            position = self.custom_position
        elif self.position == "CURSOR":
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    position = area.spaces.active.cursor_location

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            for island in island_util.get_island(context, bm, uv_layer):
                UvTransformUtils.move_island_to_position(island, uv_layer, position)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {"FINISHED"}


class ZUV_OT_SimpleUnstack(bpy.types.Operator):
    bl_idname = "uv.zenuv_simple_unstack"
    bl_label = "Simple Unstack"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Shifting the islands in a given direction"

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="The position where the islands will be placed",
        items=[
                ("EXPAND", "Expand", "Expand selected stack using margin", 0),
                ("OFFSET", "Offset", "Offset selected stack to the right side", 1)
            ],
        default="OFFSET"
    )
    offset_value: bpy.props.FloatVectorProperty(
        name="Offset",
        description='The amount by which all islands except the first one will be shifted',
        size=2,
        default=(1.0, 0.0),
        subtype='XYZ'
    )
    expand_margin: bpy.props.FloatProperty(
        name='Margin',
        description='Distance between the islands',
        min=0.0,
        default=0.005,
        precision=3,
        step=0.1
    )
    use_seams_as_separator: bpy.props.BoolProperty(
        name='Use Seams',
        default=False,
        description='Use seams as an island separator to prevent stacked islands from self-welding'
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'mode')
        if self.mode == 'OFFSET':
            layout.prop(self, 'offset_value')
        else:
            layout.prop(self, 'expand_margin')
        layout.prop(self, 'use_seams_as_separator')

    def execute(self, context):
        objs = resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            p_islands = sorted(
                [
                    list(cluster) for cluster in island_util.get_island(
                        context, bm, uv_layer,
                        use_seams_as_separator=self.use_seams_as_separator)
                ], key=lambda x: x[0].index)

            if self.mode == 'EXPAND':
                init_bbox = bound_box(islands=[p_islands[0], ], uv_layer=uv_layer)
                delta = Vector((0, 0))
                for i in range(1, len(p_islands)):
                    current_bbox = bound_box(islands=[p_islands[i], ], uv_layer=uv_layer)
                    offset = (Vector((init_bbox['len_x'] / 2, init_bbox['len_y'] / 2)) + Vector((current_bbox['len_x'] / 2, current_bbox['len_y'] / 2)) + Vector.Fill(2, self.expand_margin))
                    delta = UvTransformUtils.move_island_to_position(p_islands[i], uv_layer, position=current_bbox["cen"], offset=offset + delta, pivot=current_bbox["cen"], axis=Vector((1, 0)))
                    init_bbox = bound_box(islands=[p_islands[i], ], uv_layer=uv_layer)

            elif self.mode == 'OFFSET':
                init_bbox = bound_box(islands=[p_islands[0], ], uv_layer=uv_layer)
                for i in range(1, len(p_islands)):
                    UvTransformUtils.move_island_to_position(p_islands[i], uv_layer, init_bbox['cen'] + self.offset_value)
            else:
                self.report({'WARNING', 'mode incorrect'})
                return {'FINISHED'}

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {"FINISHED"}


uv_tr_align_classes = (
    ZUV_OT_AlignGrabPosition,
    ZUV_OT_SimpleStack,
    ZUV_OT_SimpleUnstack,
    ZUV_OT_TrAlign
)


def register_tr_align():
    RegisterUtils.register(uv_tr_align_classes)


def unregister_tr_align():
    RegisterUtils.unregister(uv_tr_align_classes)
