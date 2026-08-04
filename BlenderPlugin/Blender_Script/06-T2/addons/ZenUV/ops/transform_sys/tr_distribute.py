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
import random
from mathutils import Vector, Matrix
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.stacks.utils import Cluster
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import (
    resort_objects_by_selection,
    get_mesh_data,
    verify_uv_layer
)
from ZenUV.utils.transform import zen_convex_hull_2d, bound_box
from ZenUV.utils.vlog import Log
from ZenUV.utils.selection_utils import SelectionProcessor, UniSelectedObject
from ZenUV.ops.transform_sys.tr_labels import TrLabels
from .transform_utils.tr_utils import Cursor2D, TransformOrderSolver


class ZUV_OT_TrArrange(bpy.types.Operator):
    bl_idname = "uv.zenuv_arrange_transform"
    bl_label = TrLabels.OT_ARRANGE_LABEL
    bl_description = TrLabels.OT_ARRANGE_DESC
    bl_options = {'REGISTER', 'UNDO'}

    # def update_uniform(self, context):
    #     if self.uniform_quant:
    #         self.count_v = 0
    #         self.quant_v = 0

    def upd_count_u(self, context):
        if self.count_u != 0:
            self.quant.x = 1 / self.count_u
        else:
            self.quant.x = 0

    def upd_count_v(self, context):
        if self.count_v != 0:
            self.quant.y = 1 / self.count_v
        else:
            self.quant.y = 0

    def upd_quant_u(self, context):
        self.quant.x = self.quant_u

    def upd_quant_v(self, context):
        self.quant.y = self.quant_v

    def update_input_mode(self, context):
        if self.input_mode == "SIMPLIFIED":
            if self.quant.x != 0:
                self.count_u = 1 / self.quant.x
            else:
                self.count_u = 0
            if self.quant.y != 0:
                self.count_v = 1 / self.quant.y
            else:
                self.count_v = 0

        elif self.input_mode == "ADVANCED":
            self.quant_u = self.quant.x
            self.quant_v = self.quant.y

    quant: bpy.props.FloatVectorProperty(
        name="",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ',
        options={"HIDDEN"}
    )
    quant_u: bpy.props.FloatProperty(
        name=TrLabels.PROP_ARRANGE_QUANT_U_LABEL,
        description=TrLabels.PROP_ARRANGE_QUANT_U_DESC,
        precision=3,
        default=0.0,
        step=1,
        min=0.0,
        update=upd_quant_u
    )
    quant_v: bpy.props.FloatProperty(
        name=TrLabels.PROP_ARRANGE_QUANT_V_LABEL,
        description=TrLabels.PROP_ARRANGE_QUANT_V_DESC,
        precision=3,
        default=0.0,
        step=1,
        min=0.0,
        update=upd_quant_v
    )
    count_u: bpy.props.IntProperty(
        name=TrLabels.PROP_ARRANGE_COUNT_U_LABEL,
        description=TrLabels.PROP_ARRANGE_COUNT_U_DESC,
        default=0,
        min=0,
        update=upd_count_u
    )
    count_v: bpy.props.IntProperty(
        name=TrLabels.PROP_ARRANGE_COUNT_V_LABEL,
        description=TrLabels.PROP_ARRANGE_COUNT_V_DESC,
        default=0,
        min=0,
        update=upd_count_v
    )
    reposition: bpy.props.FloatVectorProperty(
        name=TrLabels.PROP_ARRANGE_POSITION_LABEL,
        description=TrLabels.PROP_ARRANGE_POSITION_DESC,
        size=2,
        precision=4,
        step=1,
        default=(0.0, 0.0),
        subtype='XYZ'
    )
    limit: bpy.props.FloatVectorProperty(
        name=TrLabels.PROP_ARRANGE_LIMIT_LABEL,
        description=TrLabels.PROP_ARRANGE_LIMIT_DESC,
        size=2,
        precision=3,
        min=0.0,
        default=(1.0, 1.0),
        subtype='XYZ'
    )
    input_mode: bpy.props.EnumProperty(
        name=TrLabels.PROP_ARRANGE_INP_MODE_LABEL,
        description=TrLabels.PROP_ARRANGE_INP_MODE_DESC,
        items=[
            ("SIMPLIFIED", TrLabels.PROP_ARRANGE_INP_MODE_SIMPL_LABEL, ""),
            ("ADVANCED", TrLabels.PROP_ARRANGE_INP_MODE_ADV_LABEL, ""),
        ],
        default="SIMPLIFIED",
        update=update_input_mode
    )
    start_from: bpy.props.EnumProperty(
        name=TrLabels.PROP_ARRANGE_START_FROM_LABEL,
        description=TrLabels.PROP_ARRANGE_START_FROM_DESC,
        items=[
            ("INPLACE", "In Place", ""),
            ("BOTTOM", "Bottom", ""),
            ("CENTER", "Center", ""),
            ("TOP", "Top", ""),
            ("CURSOR", "Cursor", "")
        ],
        default="INPLACE"
    )
    randomize: bpy.props.BoolProperty(
        name=TrLabels.PROP_ARRANGE_RANDOMIZE_LABEL,
        description=TrLabels.PROP_ARRANGE_RANDOMIZE_DESC,
        default=False
    )
    seed: bpy.props.IntProperty(
        name=TrLabels.PROP_ARRANGE_SEED_LABEL,
        description=TrLabels.PROP_ARRANGE_SEED_DESC,
        default=132,
    )
    scale: bpy.props.FloatProperty(
        name=TrLabels.PROP_ARRANGE_SCALE_LABEL,
        description=TrLabels.PROP_ARRANGE_SCALE_DESC,
        precision=3,
        default=1.0,
        step=1,
        min=0.01
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw_quant(self, context):
        self.layout.separator_spacer()
        col = self.layout.column(align=True)
        row = col.row(align=True)
        if self.input_mode == "SIMPLIFIED":
            mode = "count"
        elif self.input_mode == "ADVANCED":
            mode = "quant"
        row.prop(self, mode + "_u")
        col = row.column(align=True)
        col.prop(self, mode + "_v")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "input_mode")
        row = layout.row(align=True)
        row.prop(self, "start_from")

        self.draw_quant(context)
        if not self.input_mode == "SIMPLIFIED":
            layout.prop(self, "limit")
        layout.label(text="Correction:")
        box = layout.box()
        box.prop(self, "reposition")
        row = box.row(align=True)
        row.prop(self, "randomize")
        if self.randomize:
            row.prop(self, "seed")
        box.prop(self, "scale")

    def invoke(self, context, event):
        objs = resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {"CANCELLED"}
        self.criterion_data = dict()
        counter = 0
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            bm.faces.ensure_lookup_table()
            islands = island_util.get_island(context, bm, uv_layer)
            for island in islands:
                cluster = Cluster(context, obj, island)
                criterion = counter
                self.criterion_data.update(
                    {
                        counter:
                            {
                                "cluster": cluster.geometry["faces_ids"],
                                "bbox": cluster.bbox,
                                "center": cluster.bbox["cen"],
                                "criterion": criterion,
                                "object": obj.name
                            }
                    }
                )
                counter += 1
        self.execute(context)
        return {'FINISHED'}

    def execute(self, context):
        if self.input_mode == "SIMPLIFIED":
            self.limit = Vector((1.0, 1.0))
        reposition = self.reposition
        base_position = Vector((0.0, 0.0))
        criterion_chart = sorted(self.criterion_data.keys())
        position_chart = sorted(criterion_chart, key=lambda x: self.criterion_data[x]["center"].x, reverse=False)

        for _id in position_chart:
            if self.criterion_data[_id]["center"].x > 0:
                break

        if self.start_from == "TOP":
            base_position = Vector((0, 1 - self.criterion_data[_id]["bbox"]["len_y"]))
        elif self.start_from == "BOTTOM":
            base_position = Vector((0.0, 0.0))
        elif self.start_from == "CENTER":
            base_position = Vector((0, 0.5 - self.criterion_data[_id]["bbox"]["len_y"] / 2))
        elif self.start_from == "INPLACE":
            base_position = self.criterion_data[_id]["bbox"]["bl"]
        elif self.start_from == "CURSOR":
            base_position = Cursor2D(context).uv_cursor_pos

        if self.randomize:
            random.shuffle(criterion_chart)

        real_limit = base_position + reposition + self.limit
        current = Vector((0.0, 0.0))
        for _id in criterion_chart:
            cluster = self.criterion_data[_id]
            cl_size = Vector((cluster["bbox"]["len_x"], cluster["bbox"]["len_y"])) * 0.5
            cl_position = base_position + cl_size + reposition

            if self.limit.x != 0:
                if cl_position.x + current.x > real_limit.x:
                    current.x = 0
                    current.y += self.quant.y

            if self.limit.y != 0:
                if cl_position.y + current.y > real_limit.y:
                    current.y = 0

            self.criterion_data[_id].update({"position": cl_position + current})
            current = current + Vector((self.quant.x, 0))

        # Set Cluster to position
        for cluster in self.criterion_data.values():
            cl = Cluster(context, cluster['object'], cluster["cluster"])
            cl.move_to(cluster["position"])
            cl.scale([self.scale, self.scale], cl.bbox["bl"])
            cl.update_mesh()

        return {'FINISHED'}


class ZUV_OT_RandomizeTransform(bpy.types.Operator):
    bl_idname = "uv.zenuv_randomize_transform"
    bl_label = 'Randomize'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Randomize Transformation'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.Storage: list = None
        self.was_invoked: bool = False

    def update_move_limit_u(self, context):
        if self.uniform_move:
            self.move_limit_v = self.move_limit_u

        if self.move_step_u > abs(self.move_limit_u):
            self.move_step_u = self.move_limit_u

    def update_move_limit_v(self, context):
        if self.move_step_v > abs(self.move_limit_v):
            self.move_step_v = self.move_limit_v

    def update_move_step_u(self, context):
        if self.uniform_move:
            self.move_step_v = self.move_step_u
        if self.move_step_u > self.move_limit_u:
            self.move_limit_u = self.move_step_u

    def update_move_step_v(self, context):
        if self.move_step_v > self.move_limit_v:
            self.move_limit_v = self.move_step_v

    ui_mode: bpy.props.EnumProperty(
        name='Randomize Mode',
        description='Sets operator mode',
        items=[
            ("SIMPLE", "Simple", "Only basic functions are enabled"),
            ("ADVANCED", "Advanced", "Full control over the operator. You can specify the step, etc.")
        ],
        default="SIMPLE"
    )

    influence: bpy.props.EnumProperty(
        name='Influence',
        description='Transform Influence. Affect Islands or Elements (vertices, edges, polygons)',
        items=[
            ("ISLAND", "Island", ""),
            ("SELECTION", "Selection", "")
        ],
        default="ISLAND"
    )

    # Position variables
    is_move_enabled: bpy.props.BoolProperty(
        name='Disable',
        description='Disable transformation',
        default=True
    )
    move_as_one: bpy.props.BoolProperty(
        name='As One',
        description='Move the entire selection as a single unit',
        default=False
    )
    move_limit_u: bpy.props.FloatProperty(
        name="Limit U",
        description='The range starts with a negative value U and ends with its positive value',
        default=0.0,
        update=update_move_limit_u
    )
    move_limit_v: bpy.props.FloatProperty(
        name="Limit V",
        description='The range starts with a negative value U and ends with its positive value',
        default=0.0,
        update=update_move_limit_v
    )
    uniform_move: bpy.props.BoolProperty(
        name='Lock Axes',
        description='Lock values for uniform transformation over the axes',
        default=True
    )
    move_step_u: bpy.props.FloatProperty(
        name="Step U",
        description='The step at which the move will be performed',
        default=0.0,
        min=0.0,
        update=update_move_step_u
    )
    move_step_v: bpy.props.FloatProperty(
        name="Step V",
        description='The step at which the move will be performed',
        default=0.0,
        min=0.0,
        update=update_move_step_v
    )
    move_is_one_direction: bpy.props.BoolProperty(
        name='One Direction',
        description='Turns on the mode when the beginning of the range starts from zero. All transformations will occur in the one direction',
        default=False
    )

    # Rotation Variables
    is_rotation_enabled: bpy.props.BoolProperty(
        name='Disable',
        description='Disable transformation',
        default=True
    )
    rotation_as_one: bpy.props.BoolProperty(
        name='As One',
        description='Rotate the entire selection as a single unit',
        default=False
    )

    def update_angle_limit(self, context):
        if abs(self.angle_limit) < self.rotation_step:
            self.rotation_step = self.angle_limit

    angle_limit: bpy.props.FloatProperty(
        name='Angle Limit',
        description='Rotation angle range',
        default=0.0,
        min=-360.0,
        max=360.0,
        step=100,
        update=update_angle_limit
    )

    def update_rotation_step(self, context):
        if self.rotation_step > abs(self.angle_limit):
            self.angle_limit = self.rotation_step

    rotation_step: bpy.props.FloatProperty(
        name='Step',
        description='The step with which the rotation will be performed',
        default=0.0,
        min=0.0,
        max=360.0,
        step=100,
        update=update_rotation_step,
    )

    rotation_is_one_direction: bpy.props.BoolProperty(
        name='Positive Only',
        description='Turns on the mode when the beginning of the range starts from zero. All rotations will occur in the positive direction',
        default=False
    )

    # Scale Variables
    is_scale_enabled: bpy.props.BoolProperty(
        name='Disable',
        description='Disable transformation',
        default=True
    )
    scale_as_one: bpy.props.BoolProperty(
        name='As One',
        description='Scale the entire selection as a single unit',
        default=False
    )

    def update_scale(self, context):
        if self.uniform_scale:
            self.scale_limit_v = self.scale_limit_u

    def update_scale_limit_u(self, context):
        if self.uniform_scale:
            self.scale_limit_v = self.scale_limit_u

        if self.scale_step_u > abs(self.scale_limit_u):
            self.scale_step_u = self.scale_limit_u

    def update_scale_limit_v(self, context):
        if self.scale_step_v > abs(self.scale_limit_v):
            self.scale_step_v = self.scale_limit_v

    def update_scale_step_u(self, context):
        if self.uniform_move:
            self.scale_step_v = self.scale_step_u
        if self.scale_step_u > self.scale_limit_u:
            self.scale_limit_u = self.scale_step_u

    def update_scale_step_v(self, context):
        if self.scale_step_v > self.scale_limit_v:
            self.scale_limit_v = self.scale_step_v

    scale_limit_u: bpy.props.FloatProperty(
        name="Limit U",
        description='Scale Range',
        default=1.0,
        update=update_scale_limit_u
    )
    scale_limit_v: bpy.props.FloatProperty(
        name="Limit V",
        description='Scale Range',
        default=1.0,
        update=update_scale_limit_v
    )

    def update_uniform_scale(self, context):
        if self.uniform_scale:
            self.scale_limit_v = self.scale_limit_u
            self.scale_step_v = self.scale_step_u

    uniform_scale: bpy.props.BoolProperty(
        name='Lock Axes',
        description='Lock values for uniform transformation over the axes',
        default=True,
        update=update_uniform_scale

    )
    scale_step_u: bpy.props.FloatProperty(
        name="Step U",
        description='The step at which the scaling will be performed',
        default=0.0,
        min=0.0,
        update=update_scale_step_u
    )
    scale_step_v: bpy.props.FloatProperty(
        name="Step V",
        description='The step at which the scaling will be performed',
        default=0.0,
        min=0.0,
        update=update_scale_step_v
    )
    scale_is_one_direction: bpy.props.BoolProperty(
        name='Positive Only',
        description='Turns on the mode when the beginning of the range starts from 1.0. All scaling will occur in the positive values. No islands flipping',
        default=False
    )
    seed: bpy.props.IntProperty(
        name='Seed',
        description='Change transformation in the set ranges by random value',
        default=132,
    )

    use_seams_as_separator: bpy.props.BoolProperty(
        name='Use Seams',
        default=False,
        description='Use seams as an island separator to prevent stacked islands from self-welding'
    )

    def invoke(self, context, event):
        Log.debug('Randomize', 'was invoked')
        SelectionProcessor.reset_state()
        self.Storage = SelectionProcessor.collect_selected_objects(
            context,
            b_is_not_sync=False,
            b_in_indices=True,
            b_is_skip_objs_without_selection=True,
            b_skip_uv_layer_fail=True,
            b_skip_store_selected_items=True)

        self.was_invoked = True
        if SelectionProcessor.result is False:
            self.report({'WARNING'}, SelectionProcessor.message)
            return {'CANCELLED'}

        return self.execute(context)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw_simple_mode(self, context, layout):
        layout.prop(self, "influence")
        if self.influence == 'ISLAND':

            # Move
            self.draw_simple_move(layout)

            # Rotate
            self.draw_simple_rotation(layout)

            # Scale
            self.draw_simple_scale(layout)

        else:
            self.draw_simple_move(layout)

        layout.separator()
        layout.prop(self, "seed")

    def draw_simple_move(self, layout):
        layout.label(text='Position:')
        row = layout.row(align=True)

        if self.uniform_move:
            lock_icon = "LOCKED"
            p_enabled = False
        else:
            lock_icon = "UNLOCKED"
            p_enabled = True

        row.prop(self, "move_limit_u")
        row.prop(self, "uniform_move", icon=lock_icon, icon_only=True)
        row = row.row(align=True)
        row.enabled = p_enabled
        row.prop(self, "move_limit_v")

    def draw_simple_rotation(self, layout):
        layout.label(text="Rotation:")
        layout.prop(self, "angle_limit")

    def draw_simple_scale(self, layout):
        layout.label(text="Scale:")

        row = layout.row(align=True)
        row.prop(self, "scale_limit_u")

        if self.uniform_scale:
            lock_icon = "LOCKED"
            enb = False
        else:
            lock_icon = "UNLOCKED"
            enb = True
        row.prop(self, "uniform_scale", icon=lock_icon, icon_only=True)
        row = row.row(align=True)
        row.enabled = enb
        row.prop(self, "scale_limit_v")

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        if self.ui_mode == 'SIMPLE':
            self.draw_simple_mode(context, box)
        else:
            box.prop(self, "influence")
            if self.influence == 'ISLAND':

                # Move
                self.draw_move_scale(context, box, s_mode='move')

                # Rotate
                self.draw_rotation(box)

                # Scale
                self.draw_move_scale(context, box, s_mode='scale')

            else:
                self.draw_move_scale(context, box, s_mode='move')

            box.prop(self, "seed")

        layout.prop(self, 'use_seams_as_separator')
        row = layout.row()
        row.prop(self, 'ui_mode', expand=True)

    def draw_move_scale(
            self,
            context: bpy.types.Context, layout: bpy.types.UILayout,
            s_mode=''):

        if s_mode == 'move':
            s_caption = 'Position'
            d_limit_u = self.move_limit_u
            d_limit_v = self.move_limit_v
            if self.move_is_one_direction:
                r_start_u = r_start_v = 0.0
            else:
                r_start_u = round(d_limit_u, 2) * - 1
                r_start_v = round(d_limit_v, 2) * - 1
        elif s_mode == 'scale':
            s_caption = 'Scale'
            d_limit_u = self.scale_limit_u
            d_limit_v = self.scale_limit_v
            r_start_u = 1.0 if self.scale_is_one_direction else round(- d_limit_u, 2)
            r_start_v = 1.0 if self.scale_is_one_direction else round(- d_limit_v, 2)
        else:
            RuntimeError('Unreachable place! Mode is not defined!')

        # b_is_mode_enabled = getattr(self, f'is_{s_mode}_enabled')
        b_is_mode_enabled = True

        row = layout.row(align=True)
        row.prop(self, f'is_{s_mode}_enabled', text=f'{s_caption}:')
        row = row.row()
        row.enabled = b_is_mode_enabled
        row.alignment = 'RIGHT'
        row.prop(self, f'{s_mode}_as_one')
        row.prop(self, f'{s_mode}_is_one_direction')

        box = layout.box()
        box.enabled = b_is_mode_enabled

        row = box.row(align=True)

        row_01 = row.row(align=True)
        row_02 = row.row(align=True)
        row_03 = row.row(align=True)

        col_01 = row_01.column(align=True)
        col_02 = row_02.column(align=True)
        col_03 = row_03.column(align=True)

        def draw_range(col: bpy.types.UILayout, s_axis: str, r_start, d_limit):
            row_range = col.row(align=True)

            row = row_range.row(align=True)
            row.alignment = 'LEFT'
            row.label(text=f'{s_axis.upper()}:')

            row = row_range.row(align=True)
            row.alignment = 'RIGHT'
            s_val = f"{r_start} — {round(d_limit, 2)}"
            row.label(text=s_val)

        draw_range(col_01, 'U', r_start_u, d_limit_u)
        col_02.label(icon='BLANK1', text='')
        draw_range(col_03, 'V', r_start_v, d_limit_v)

        # Row Limits
        row_limits = col_01.row(align=True)
        row_limits.prop(self, f"{s_mode}_limit_u")

        b_is_uniform = getattr(self, f'uniform_{s_mode}')
        if b_is_uniform:
            lock_icon = "LOCKED"
            p_enabled = False
        else:
            lock_icon = "UNLOCKED"
            p_enabled = True

        col_02.prop(self, f'uniform_{s_mode}', icon=lock_icon, icon_only=True)

        row = col_03.row(align=True)
        row.enabled = p_enabled
        row.prop(self, f'{s_mode}_limit_v')

        # Row Step
        row_step = col_01.row(align=True)
        row_step.prop(self, f'{s_mode}_step_u')

        col_02.label(text='', icon='BLANK1')

        row = col_03.row(align=True)
        row.enabled = p_enabled
        row.prop(self, f'{s_mode}_step_v')

    def draw_rotation(self, layout: bpy.types.UILayout):
        row = layout.row(align=True)
        row.prop(self, 'is_rotation_enabled', text='Rotation:')
        row = row.row()
        # row.enabled = self.is_rotation_enabled
        row.alignment = 'RIGHT'
        row.prop(self, 'rotation_as_one')
        row.prop(self, 'rotation_is_one_direction')

        box = layout.box()
        # box.enabled = self.is_rotation_enabled

        p_range_start = round(self.angle_limit * -1, 2) if not self.rotation_is_one_direction else 0.0
        row = box.row(align=True)
        row_l = row.row(align=True)
        row_l.alignment = 'LEFT'
        row.label(text='Range:')

        row_r = row.row(align=True)
        row_r.alignment = 'RIGHT'
        row_r.label(text=f'{p_range_start} — {round(self.angle_limit, 2)}')

        col = box.column(align=True)
        col.prop(self, "angle_limit")
        col.prop(self, "rotation_step")

    def execute(self, context):
        if not self.was_invoked:
            SelectionProcessor.reset_state()
            self.Storage = SelectionProcessor.collect_selected_objects(
                context,
                b_is_not_sync=False,
                b_in_indices=True,
                b_is_skip_objs_without_selection=True,
                b_skip_uv_layer_fail=True,
                b_skip_store_selected_items=True)

            if SelectionProcessor.result is False:
                self.report({'WARNING'}, SelectionProcessor.message)
                return {'CANCELLED'}

            self.was_invoked = True

        if self.ui_mode == 'SIMPLE':
            p_scale_is_one_direction = True
        else:
            p_scale_is_one_direction = self.scale_is_one_direction

        for s_obj in SelectionProcessor.yield_selected_objects(self.Storage):
            p_islands = island_util.get_island(context, s_obj.bm, s_obj.uv_layer, use_seams_as_separator=self.use_seams_as_separator)
            sorted_inner_lists = [sorted([face.index for face in face_set]) for face_set in p_islands]
            s_obj.attribute_storage['islands'] = sorted(sorted_inner_lists, key=lambda lst: lst[0])

        self.setup_simple_mode()

        if not any((self.is_move_enabled, self.is_rotation_enabled, self.is_scale_enabled)):
            Log.debug('Randomize', 'No active transformations are specified. The operator is FINISHED.')
            return {'FINISHED'}

        from math import radians
        from ZenUV.ops.transform_sys.transform_utils.tr_randomize_utils import TransformRandomizer as rand
        from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
        from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage

        pivot_point = TransformOrderSolver.get(context)
        if pivot_point == '':
            pivot_point = 'CENTER'

        try:
            entropy = self.Storage[0].attribute_storage['islands'][0][0]
        except Exception as e:
            Log.debug('Randomize', f'Attribute storage "islands" is not exist. {e}')
            entropy = 42

        random.seed(self.seed + entropy)

        if self.influence == 'ISLAND':

            # Position precalculations
            p_u_positions = []
            p_v_positions = []
            if self.is_move_enabled:
                if self.is_move_step_allowed():
                    p_u_pos_precalc = rand.calc_positions_list(
                        self.move_limit_u,
                        self.move_step_u,
                        self.move_is_one_direction)
                    p_v_pos_precalc = rand.calc_positions_list(
                        self.move_limit_v,
                        self.move_step_v,
                        self.move_is_one_direction)

                if self.move_as_one:
                    if self.is_move_step_allowed():
                        p_u_positions = [random.choice(p_u_pos_precalc)]
                        p_v_positions = [random.choice(p_v_pos_precalc)]
                    else:
                        p_u_positions = [rand.calc_random_float(self.move_limit_u, self.move_is_one_direction)]
                        p_v_positions = [rand.calc_random_float(self.move_limit_v, self.move_is_one_direction)]

            # Rotation precalculations
            if self.is_rotation_enabled:
                if self.is_rotation_step_allowed():
                    p_angles_list = rand.calc_angles_list(self.angle_limit, self.rotation_step, self.rotation_is_one_direction)
                else:
                    p_angles_list = [rand.calc_random_float(self.angle_limit, self.rotation_is_one_direction)]
                if self.rotation_as_one:
                    p_angles_list = [random.choice(p_angles_list)]

            # Scale precalculation
            p_u_scale_steps = []
            p_v_scale_steps = []
            if self.is_scale_enabled:
                if self.is_scale_step_allowed():
                    p_u_scale_steps_precalc = rand.calc_scale_list(self.scale_limit_u, self.scale_step_u, p_scale_is_one_direction)
                    p_v_scale_steps_precalc = rand.calc_scale_list(self.scale_limit_v, self.scale_step_v, p_scale_is_one_direction)
                    if self.scale_as_one:
                        p_u_scale_steps = [random.choice(p_u_scale_steps_precalc)]
                        p_v_scale_steps = [random.choice(p_v_scale_steps_precalc)]
                    else:
                        p_u_scale_steps = p_u_scale_steps_precalc
                        p_v_scale_steps = p_v_scale_steps_precalc
                else:
                    if self.scale_as_one:
                        p_u_scale_steps = [rand.calc_random_float_scale(self.scale_limit_u, p_scale_is_one_direction)]
                        p_v_scale_steps = [rand.calc_random_float_scale(self.scale_limit_v, p_scale_is_one_direction)]
                    else:
                        p_u_scale_steps = rand.calc_scale_list(self.scale_limit_u, self.scale_step_u, True)
                        p_v_scale_steps = rand.calc_scale_list(self.scale_limit_v, self.scale_step_v, True)

            # Precalculate BoundingBox
            if self.is_rotation_enabled or self.is_scale_enabled:
                if self.rotation_as_one or self.scale_as_one:
                    from ZenUV.utils.bounding_box import get_overall_bbox
                    g_bbox = get_overall_bbox(context, from_islands=True, as_dict=True)

        # Main routine
        s_obj: UniSelectedObject = None

        L = Matrix.Translation(Vector.Fill(3, 0.0))
        R = Matrix.Rotation(0.0, 4, 'Z')
        S = Matrix.Diagonal(Vector.Fill(4, 1.0))

        for s_obj in SelectionProcessor.yield_selected_objects(self.Storage):
            bm = s_obj.bm
            uv_layer = s_obj.uv_layer

            if self.influence == 'ISLAND':
                bm.faces.ensure_lookup_table()
                islands = [[bm.faces[i] for i in island_idxs] for island_idxs in s_obj.attribute_storage['islands']]

                for island in islands:
                    p_loops = [loop for f in island for loop in f.loops]
                    p_points = [loop[uv_layer].uv for loop in p_loops]
                    p_bbox = bound_box(points=zen_convex_hull_2d(p_points), uv_layer=uv_layer)

                    if self.is_rotation_enabled and self.rotation_as_one:
                        bbox = g_bbox
                    else:
                        bbox = p_bbox

                    # Position
                    if self.is_move_enabled:
                        if self.move_as_one:
                            offset = Vector((random.choice(p_u_positions), random.choice(p_v_positions)))
                        else:
                            if self.is_move_step_allowed():
                                offset = Vector((random.choice(p_u_pos_precalc), random.choice(p_v_pos_precalc)))
                            else:
                                offset = Vector((
                                    rand.calc_random_float(self.move_limit_u, self.move_is_one_direction),
                                    rand.calc_random_float(self.move_limit_v, self.move_is_one_direction)))

                        L = Matrix.Translation(offset.to_3d())

                    # Rotation
                    if self.is_rotation_enabled:

                        if self.rotation_as_one:
                            bbox = g_bbox
                        else:
                            bbox = p_bbox

                        if self.rotation_as_one:
                            angle = random.choice(p_angles_list)
                        else:
                            if self.is_rotation_step_allowed():
                                angle = random.choice(p_angles_list)
                            else:
                                angle = rand.calc_random_float(self.angle_limit, self.rotation_is_one_direction)

                        R = TransformLoops._get_rotation_matrix(radians(angle), ActiveUvImage(context).aspect).to_4x4()

                    # Scale
                    if self.is_scale_enabled:
                        if self.scale_as_one:
                            bbox = g_bbox
                        else:
                            bbox = p_bbox

                        if self.scale_as_one:
                            scale = Vector((random.choice(p_u_scale_steps), random.choice(p_v_scale_steps)))
                        else:
                            if self.is_scale_step_allowed():
                                scale = Vector((random.choice(p_u_scale_steps), random.choice(p_v_scale_steps)))
                            else:
                                scale_factor_u = random.uniform(1.0, self.scale_limit_u)
                                scale_factor_v = random.uniform(1.0, self.scale_limit_v)

                                if p_scale_is_one_direction:
                                    scale = Vector((abs(scale_factor_u), abs(scale_factor_v)))
                                else:
                                    scale = Vector((scale_factor_u, scale_factor_v))

                        if self.uniform_scale:
                            scale = Vector.Fill(2, scale.x)

                        S = Matrix.Diagonal(Vector((scale.x, scale.y, 1.0, 1.0)))

                    pivot_translation_matrix = Matrix.Translation(-bbox['cen'].to_3d())
                    reverse_pivot_translation_matrix = Matrix.Translation(bbox['cen'].to_3d())

                    M = (reverse_pivot_translation_matrix @ L @ R @ S @ pivot_translation_matrix)

                    for loop in p_loops:
                        loop[uv_layer].uv = (M @ loop[uv_layer].uv.to_3d())[:2]

            else:
                if not self.is_move_enabled:
                    return {'FINISHED'}

                loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer)
                f_loops = {loop[uv_layer].uv.copy().freeze(): [lp for lp in loop.vert.link_loops if lp[uv_layer].uv == loop[uv_layer].uv] for loop in loops}
                for loops in f_loops.values():

                    if self.move_is_one_direction:
                        direction = Vector((random.uniform(0, self.move_limit_u), random.uniform(0, self.move_limit_v)))
                    else:
                        direction = Vector((random.uniform(-self.move_limit_u, self.move_limit_u), random.uniform(-self.move_limit_v, self.move_limit_v)))

                    for loop in loops:
                        loop[uv_layer].uv += direction

            bmesh.update_edit_mesh(s_obj.obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}

    def setup_simple_mode(self):
        if self.ui_mode == 'SIMPLE':
            self.is_move_enabled = True
            self.is_rotation_enabled = True
            self.is_scale_enabled = True

            self.move_is_one_direction = False
            self.rotation_is_one_direction = False
            self.scale_is_one_direction = False

            self.move_step_u = self.move_step_v = 0.0
            self.rotation_step = 0.0
            self.scale_step_u = self.scale_step_v = 0.0

            self.move_as_one = False
            self.rotation_as_one = False
            self.scale_as_one = False

    def is_move_step_allowed(self):
        return self.move_step_u != 0 or self.move_step_v != 0

    def is_rotation_step_allowed(self):
        return self.rotation_step != 0

    def is_scale_step_allowed(self):
        return self.scale_step_u != 0 or self.scale_step_v != 0


uv_tr_distribute_classes = (
    ZUV_OT_TrArrange,
    ZUV_OT_RandomizeTransform,
)


def register_tr_distribute():
    RegisterUtils.register(uv_tr_distribute_classes)


def unregister_tr_distribute():
    RegisterUtils.unregister(uv_tr_distribute_classes)
