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
from ZenUV.utils.generic import (
    get_mesh_data,
    resort_by_type_mesh_in_edit_mode_and_sel,
    UnitsConverter
)
from .transform_utils.tr_scale_utils import (
    TrScaleProps,
    ScaleFactory
)
from .transform_utils.tr_utils import TransformSysOpsProps
from ZenUV.ops.transform_sys.tr_labels import TrLabels


class ZUV_OT_TrScale(bpy.types.Operator):
    bl_idname = "uv.zenuv_scale"
    bl_label = "Scale"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Scale selected Islands or Selection"

    influence_mode: TransformSysOpsProps.influence_mode
    op_order: TransformSysOpsProps.get_order_prop()
    scale_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Transform Mode",
        items=[
            ("AXIS", "By Axis", "The mode in which scaling is indicated by the scaling factor for each of the axes"),
            ("UNITS", "By Units", "The mode in which the size is specified relative to the size of the UV Area"),
        ],
        default="AXIS"
    )

    # Operator Settings
    op_tr_scale: bpy.props.FloatVectorProperty(
        name="Scale",
        description="Scaling size",
        size=2,
        default=(1.0, 1.0),
        subtype='XYZ'
    )
    op_unts_uv_area_size: bpy.props.FloatProperty(
        name="UV size",
        description="The estimated width of the UV area",
        min=0.0,
        default=1000.0,
        precision=2
    )
    op_unts_desired_size: bpy.props.FloatProperty(
        name="Desired size",
        description="The size of which should be set for selected elements relative to UV area",
        min=0.0,
        default=250.0,
        precision=4
    )
    op_unts_calculate_by: bpy.props.EnumProperty(
        name="Calcutate",
        description="What mean the Desired Size",
        items=[
            ("HORIZONTAL", "Horizontal", "Horizontal"),
            ("VERTICAL", "Vertical", "Vertical")
        ],
        default="HORIZONTAL"
    )
    island_pivot: TransformSysOpsProps.island_pivot
    cursor_2d_as_pivot: TransformSysOpsProps.cursor_2d_as_pivot

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "influence_mode")
        layout.prop(self, 'op_order')
        layout.prop(self, "scale_mode")
        if self.scale_mode == 'AXIS':
            s_box = layout.box()
            s_box.label(text="Settings:")
            s_box.prop(self, 'op_tr_scale')

        if self.scale_mode == 'UNITS':
            unts_box = layout.box()
            unts_box.label(text='Settings:')
            unts_box.prop(self, "op_unts_uv_area_size")
            unts_box.prop(self, "op_unts_desired_size")
            row = unts_box.row()
            row.prop(self, "op_unts_calculate_by", expand=True)

        box = layout.box()
        col = box.column(align=True)
        col.prop(self, "island_pivot")
        col.prop(self, "cursor_2d_as_pivot")

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        SP = TrScaleProps(context, self.scale_mode == 'GLOBAL')

        SP.op_tr_scale_mode = self.scale_mode
        SP.op_scale = self.op_tr_scale
        SP.op_prop_unts_uv_ar = self.op_unts_uv_area_size
        SP.op_prop_unts_desired = self.op_unts_desired_size
        SP.op_prop_cals_by = self.op_unts_calculate_by
        SP.cursor_2d_as_pivot = self.cursor_2d_as_pivot

        SF = ScaleFactory(
            context,
            SP,
            self.influence_mode,
            objs,
            self.get_order(),
            self.island_pivot,
            transform_mode='SCALE',
            scale_mode=self.scale_mode
        )
        SF.transform_scale_flip()

        return {"FINISHED"}

    def get_order(self):
        if self.op_order == "OVERALL":
            return "CENTER"
        return "INDIVIDUAL_ORIGINS"


class ZUV_OT_TR_ScaleTuner(bpy.types.Operator):
    bl_idname = "uv.zenuv_tr_scale_tuner"
    bl_label = 'Scale Tuner'
    bl_description = "Tune Scale parameters"
    bl_options = {'REGISTER', 'UNDO'}

    desc: bpy.props.StringProperty(
        name="Description",
        default="Increases by two times",
        options={'HIDDEN'}
    )

    mode: bpy.props.EnumProperty(
        name="Tune mode",
        description="Set desired tune mode",
        items=[
            ("DOUBLE", "Double", ""),
            ("HALF", "Half", ""),
            ("RESET", "Reset", "")
        ],
        default="DOUBLE",
        options={'HIDDEN'}
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        description="Axis influence",
        items=[
            ("X", "X", ""),
            ("Y", "Y", ""),
            ("XY", "XY", "")
        ],
        default="XY",
        options={'HIDDEN'}
    )

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_desctiption

    def execute(self, context):
        props = context.scene.zen_uv
        current_scale = props.tr_scale
        if self.mode == "DOUBLE":
            if self.axis == "X":
                props.tr_scale.x = current_scale.x * 2
            elif self.axis == "Y":
                props.tr_scale.y = current_scale.y * 2
            elif self.axis == "XY":
                props.tr_scale = current_scale * 2
            else:
                return {'CANCELLED'}

        elif self.mode == "HALF":
            if self.axis == "X":
                props.tr_scale.x = current_scale.x / 2
            elif self.axis == "Y":
                props.tr_scale.y = current_scale.y / 2
            elif self.axis == "XY":
                props.tr_scale = current_scale / 2
            else:
                return {'CANCELLED'}

        elif self.mode == "RESET":
            if self.axis == "X":
                props.tr_scale.x = 1.0
            elif self.axis == "Y":
                props.tr_scale.y = 1.0
            elif self.axis == "XY":
                props.tr_scale = Vector((1.0, 1.0))
        else:
            return {'CANCELLED'}
        return {'FINISHED'}


class ZUV_OT_ScaleGrabSize(bpy.types.Operator):
    bl_idname = "uv.zenuv_scale_grab_size"
    bl_label = "Grab Size"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Grab size from the selection"

    multiplier: bpy.props.FloatProperty(
        name="Multiplier",
        min=0,
        default=1,
    )

    units: bpy.props.EnumProperty(
        name=TrLabels.PREF_UNITS_LABEL,
        description=TrLabels.PREF_UNITS_DESC,
        items=[
            ('km', 'km', 'KILOMETERS'),
            ('m', 'm', 'METERS'),
            ('cm', 'cm', 'CENTIMETERS'),
            ('mm', 'mm', 'MILLIMETERS'),
            ('um', 'um', 'MICROMETERS'),
            ('mil', 'mil', 'MILES'),
            ('ft', 'ft', 'FEET'),
            ('in', 'in', 'INCHES'),
            ('th', 'th', 'THOU'),
            ('ad', 'Adaptive', 'ADAPTIVE')
        ],
        default="m",
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "units")
        if self.units == 'ad':
            layout.prop(self, "multiplier")

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects.")
            return {'CANCELLED'}
        props = context.scene.zen_uv
        sel = []
        for obj in objs:
            me, bm = get_mesh_data(obj)
            sel.extend([obj.matrix_world @ v.co for v in bm.verts if v.select])
            bmesh.update_edit_mesh(me, loop_triangles=False)
        if not len(sel) == 2:
            self.report({'WARNING'}, "Zen UV: Select only two vertices or one edge.")
            return {'CANCELLED'}
        distance = abs((sel[0] - sel[1]).magnitude)
        val = UnitsConverter.convert_raw_world_distance(
            distance=distance,
            units=self.units
        ) or distance * self.multiplier
        props.unts_desired_size = val

        return {"FINISHED"}


class ZUV_OT_TrFlip(bpy.types.Operator):
    bl_idname = "uv.zenuv_flip"
    bl_label = "Flip"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Flip selected Islands or Selection"

    influence_mode: TransformSysOpsProps.influence_mode
    op_order: TransformSysOpsProps.get_order_prop()
    flip_direction: bpy.props.EnumProperty(
        name="Direction",
        description="Direction of flipping",
        items=[
            ("HORIZONTAL", "Horizontal", "Horizontal"),
            ("VERTICAL", "Vertical", "Vertical"),
            ("BY_I_PIVOT", "Island Pivot", "By Pivot of the Island"),
        ],
        default="HORIZONTAL"
    )
    island_pivot: TransformSysOpsProps.island_pivot

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "influence_mode")
        layout.prop(self, 'op_order')
        layout.prop(self, 'flip_direction')
        s_box = layout.box()
        s_box.label(text="Settings:")
        s_box.prop(self, 'island_pivot')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        SP = TrScaleProps(context, is_global=False)

        SP.op_tr_scale_mode = "AXIS"
        SP.flip_direction = self.flip_direction

        SF = ScaleFactory(
            context,
            SP,
            self.influence_mode,
            objs,
            self.get_order(),
            self.island_pivot,
            transform_mode='FLIP'
        )
        SF.transform_scale_flip()

        return {"FINISHED"}

    def get_order(self):
        if self.op_order == "OVERALL":
            return "CENTER"
        return "INDIVIDUAL_ORIGINS"


uv_tr_scale_classes = (
    ZUV_OT_TrScale,
    ZUV_OT_TR_ScaleTuner,
    ZUV_OT_ScaleGrabSize,
    ZUV_OT_TrFlip
)


def register_tr_scale():
    RegisterUtils.register(uv_tr_scale_classes)


def unregister_tr_scale():
    RegisterUtils.unregister(uv_tr_scale_classes)
