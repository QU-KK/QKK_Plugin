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

""" Zen UV The transformation is dependent on the Trim module """

# Copyright 2023, Valeriy Yatsenko, Alex Zhornyak

import bpy
import math

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.ops.zen_unwrap.unwrap_processor import UnwrapProcessor, UnwrapProcessorProps
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage

from .transform_utils.tr_utils import (
    TrConstants,
    TransformSysOpsProps
)
from .transform_utils.tr_scale_utils import TrScaleFlipProcessor, TrScaleFlipProcessorEx
from .transform_utils.tr_fit_utils import FitRegion, TrFitFactory, TrFitProcessorEx
from .transform_utils.tr_move_utils import TrMoveProcessorEx
from .transform_utils.tr_object_data import transform_object_data
from .tr_move import TrMoveProps, MoveFactory
from .transform_utils.tr_utils import TrSpaceMode
from .transform_utils.tr_rotate_utils import TrRotateProcessorEx
from .tr_labels import TrLabels


class ZuvTrMoveInTrimBase:
    bl_label = "Move in Trim"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Move Islands inside active Trim. Islands outside active Trim will be ignored"

    influence_mode: TransformSysOpsProps.influence_scene_mode
    op_order: TransformSysOpsProps.get_order_prop()
    lock_in_trim: TransformSysOpsProps.get_lock_in_trim_sync('UV_OT_zenuv_move_in_trim')

    is_offset_mode: TransformSysOpsProps.is_offset_mode

    # Operator Settings
    op_tr_increment: bpy.props.FloatVectorProperty(
        name="Move",
        description="Move",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ',
    )

    move_offset: bpy.props.FloatVectorProperty(
        name="Move",
        description="Move",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def get_move_value(self):
        if self.is_offset_mode:
            return self.move_offset
        else:
            return self.op_tr_increment

    def set_move_value(self, value):
        if self.is_offset_mode:
            self.is_offset_mode = False
        self.op_tr_increment = value

    move_value: bpy.props.FloatVectorProperty(
        name="Move",
        description="Move",
        size=2,

        step=1,

        subtype='XYZ',

        get=get_move_value,
        set=set_move_value,

        options={'HIDDEN', 'SKIP_SAVE'}
    )

    info_message: TransformSysOpsProps.info_message

    # island_pivot: TransformSysOpsProps.island_pivot
    # cursor_2d_as_pivot: TransformSysOpsProps.cursor_2d_as_pivot

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout

        if self.info_message:
            box = layout.box()
            box.alert = True
            box.label(text=self.info_message, icon='ERROR')

        layout.prop(self, "influence_mode")
        layout.prop(self, 'op_order')

        s_box = layout.box()
        s_box.label(text="Settings:")
        s_box.prop(self, 'lock_in_trim')

        s_box.prop(self, 'move_value')

    def invoke(self: bpy.types.Operator, context: bpy.types.Context, event: bpy.types.Event):
        self.info_message = ''
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if len(objs) > 0:
            n_loops = transform_object_data.setup(
                context, objs, self.influence_mode, self.op_order
            )

            if n_loops == 0:
                self.info_message = "No selected islands"
                self.report({'INFO'}, self.info_message)
                return {'FINISHED'}
            else:
                return self.execute(context)
        else:
            self.info_message = "There are no selected objects"
            self.report({'INFO'}, self.info_message)

        return {'CANCELLED'}

    def execute(self: bpy.types.Operator, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.info_message = "There are no selected objects"
            self.report({'INFO'}, self.info_message)
            return {'CANCELLED'}

        trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if trim is not None:
            tr_bbox = BoundingBox2d(points=(trim.left_bottom, trim.top_right))
        else:
            tr_bbox = BoundingBox2d(points=(UV_AREA_BBOX().corners))

        result = TrMoveProcessorEx.move_in_trim(
            context,
            objs,
            self.influence_mode,
            self.op_order,
            self.lock_in_trim,
            self.op_tr_increment,
            tr_bbox
        )
        if result != 'Finished':
            self.info_message = result
            self.report({'INFO'}, result)
        else:
            self.info_message = ''

        return {"FINISHED"}


class ZUV_OT_TrUVMoveInTrim(ZuvTrMoveInTrimBase, bpy.types.Operator):
    bl_idname = "uv.zenuv_move_in_trim"


class ZUV_OT_Tr3DVMoveInTrim(ZuvTrMoveInTrimBase, bpy.types.Operator):
    bl_idname = "view3d.zenuv_move_in_trim"


class ZUV_OT_TrFitToTrim(bpy.types.Operator):
    bl_idname = "uv.zenuv_fit_to_trim"
    bl_label = "Fit to Trim"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Fit Islands into active Trim"

    auto_unwrap: bpy.props.BoolProperty(
        name="Automatic Unwrap",
        description="Perform Unwrap Island before Fit to Active Trim",
        default=False,
    )

    influence_mode_faces: bpy.props.BoolProperty(
        name='Transform Faces',
        default=False
    )

    influence_mode: TransformSysOpsProps.influence_scene_mode
    op_order: TransformSysOpsProps.get_order_prop()
    fit_mode: bpy.props.EnumProperty(
        name='Fit',
        description="Transform Mode",
        items=[
            ("TO_TRIM_E", "To Active Trim (Exact)", ""),
            ("TO_TRIM_T", "To Active Trim (Tweak)", ""),
        ],
        default="TO_TRIM_T"
    )

    # Operator Settings
    op_fit_axis: bpy.props.EnumProperty(
        name='Fit Axis',
        description='Active Axis',
        items=[
            ('U', 'U', 'U axis'),
            ('V', 'V', 'V axis'),
            ('MIN', 'Min', 'The minimum length axis is automatically determined'),
            ('MAX', 'Max', 'The maximum length axis is automatically determined'),
            ('AUTO', 'Automatic', 'Automatically detected axis for full dimensional compliance'),
        ],
        default='AUTO'
    )
    op_padding: bpy.props.FloatProperty(
        name="Inset",
        description="Inset",
        default=0.0,
        step=1
    )
    match_rotation: bpy.props.BoolProperty(
        name="Match Rotation",
        description="",
        default=False,
    )
    op_keep_proportion: bpy.props.BoolProperty(
        name="Keep proportion",
        description="",
        default=True,
    )
    op_align_to: TransformSysOpsProps.island_pivot

    info_message: TransformSysOpsProps.info_message

    poll = TransformSysOpsProps.poll_edit_mesh_and_active_object

    poll_reason = TransformSysOpsProps.poll_reason_edit_mesh_and_active_object

    def draw(self, context: bpy.types.Context):
        p_influence_instance = self
        p_instance = self
        self.do_draw(p_influence_instance, p_instance, self.layout, context)

    @classmethod
    def do_draw(cls, p_influence_instance, p_instance, layout: bpy.types.UILayout, context: bpy.types.Context):
        layout.prop(p_instance, 'influence_mode_faces')

        col = layout.column(align=True)
        col.enabled = not p_instance.influence_mode_faces
        col.prop(p_influence_instance, "influence_mode")
        col.prop(p_instance, "op_order")

        layout.prop(p_instance, "fit_mode")
        layout.prop(p_instance, "auto_unwrap")
        s_box = layout.box()
        s_box.enabled = cls.is_activate_settings(p_instance)

        # Settings box
        s_box.label(text="Settings:")
        s_box.prop(p_instance, 'op_fit_axis')

        s_box.prop(p_instance, 'op_padding')

        keep_row = s_box.row()

        keep_row.prop(p_instance, "op_keep_proportion")
        s_box.prop(p_instance, 'match_rotation')
        box = layout.box()
        box.enabled = cls.is_activate_pivot(p_instance)
        row = box.row(align=True)
        row.prop(p_instance, "op_align_to", text='Align To')

    def is_activate_pivot(self):
        return self.op_keep_proportion and self.fit_mode not in {'TO_TRIM_E', }

    def is_activate_settings(self):
        return self.fit_mode not in {'TO_TRIM_E', }

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        if self.fit_mode == 'TO_TRIM_E':
            FR = FitRegion()
            if not FR.from_active_trim(context):
                self.report({'WARNING'}, "There are no Active Trim.")
                return {'CANCELLED'}

        elif self.fit_mode == 'TO_TRIM_T':
            FR = FitRegion()
            if not FR.from_active_trim(context):
                self.report({'WARNING'}, "There are no Active Trim.")
                return {'CANCELLED'}
            self.set_region_props_from_operator(FR)

        if self.influence_mode_faces:
            s_influence_mode = 'FACES'
        else:
            s_influence_mode = self.influence_mode

        if self.auto_unwrap:
            props = UnwrapProcessorProps()
            props.influence_mode = s_influence_mode
            UP = UnwrapProcessor(context, props)
            UP.preset_unwrap_and_orient_to_world(context)

        TF = TrFitFactory(
            context,
            s_influence_mode,
            objs,
            self.op_order,
            FR
            )

        TF.fit()

        return {"FINISHED"}

    def set_region_props_from_operator(self, FR):
        FR.padding = self.op_padding
        FR.keep_proportion = self.op_keep_proportion
        FR.align_to = self.op_align_to
        FR.fit_axis = self.op_fit_axis
        FR.match_rotation = self.match_rotation


class ZuvTrRotateInTrimBase():
    bl_idname = "uv.zenuv_rotate_in_trim"
    bl_label = "Rotate in Trim"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Rotate Islands inside active Trim"

    influence_mode: TransformSysOpsProps.influence_scene_mode
    op_order: TransformSysOpsProps.get_order_prop()
    lock_in_trim: TransformSysOpsProps.get_lock_in_trim_sync('UV_OT_zenuv_rotate_in_trim')
    tr_rot_inc_full_range: bpy.props.FloatProperty(
        name=TrLabels.PROP_ROTATE_INCREMENT_LABEL,
        description=TrLabels.PROP_ROTATE_INCREMENT_DESC,
        # min=-360,
        # max=360,
        default=90
    )

    is_offset_mode: TransformSysOpsProps.is_offset_mode

    rotate_offset_rad: bpy.props.FloatProperty(
        name='Rotate',
        description=TrLabels.PROP_ROTATE_INCREMENT_DESC,
        subtype='ANGLE',  # RADIANS
        default=0,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    rnd_angle: bpy.props.BoolProperty(
        name="Randomize",
        description="Randomize rotation angle",
        default=False,
    )

    def _post_init(self):
        self.rotate_processor = None
        self.fit_processor = None

    def get_rotate_angle(self):
        if self.is_offset_mode:
            return self.rotate_offset_rad
        else:
            return math.radians(self.tr_rot_inc_full_range)

    def set_rotate_angle(self, value):
        if self.is_offset_mode:
            self.is_offset_mode = False
        self.tr_rot_inc_full_range = math.degrees(value)

    rotate_angle: bpy.props.FloatProperty(
        name='Rotate',
        description=TrLabels.PROP_ROTATE_INCREMENT_DESC,
        subtype='ANGLE',  # RADIANS,
        precision=2,
        step=100,
        get=get_rotate_angle,
        set=set_rotate_angle,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    island_pivot: TransformSysOpsProps.island_pivot

    info_message: TransformSysOpsProps.info_message

    poll = TransformSysOpsProps.poll_edit_mesh_and_active_object

    poll_reason = TransformSysOpsProps.poll_reason_edit_mesh_and_active_object

    def draw_rotate_angle(self, layout: bpy.types.UILayout):
        layout.prop(self, 'tr_rot_inc_full_range')

    def draw_rotate_offset(self, layout: bpy.types.UILayout):
        row = layout.row(align=True)
        row.enabled = False
        row.prop(self, 'rotate_offset_rad')

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        if self.info_message:
            box = layout.box()
            box.alert = True
            box.label(text=self.info_message, icon='ERROR')

        layout.prop(self, "influence_mode")
        layout.prop(self, 'op_order')
        layout.separator()
        box = layout.box()
        box.label(text='Settings:')
        box.prop(self, 'lock_in_trim')

        box.prop(self, 'rnd_angle')

        box.prop(self, 'rotate_angle')

        if not self.lock_in_trim:
            box = layout.box()
            row = box.row(align=True)
            row.prop(self, "island_pivot")

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.rotate_processor = None
        self.fit_processor = None

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if len(objs) > 0:

            FR = FitRegion()
            if self.lock_in_trim and not FR.from_active_trim(context):
                self.report({'WARNING'}, "There are no Active Trim.")
                return {'CANCELLED'}

            if self.lock_in_trim:
                self.fit_processor = TrFitProcessorEx()
                self.fit_processor.setup(
                    context,
                    objs,
                    self.influence_mode,
                    self.op_order
                )
            else:
                self.rotate_processor = TrRotateProcessorEx()
                self.rotate_processor.setup(
                    context,
                    self.influence_mode,
                    objs,
                    self.op_order,
                    self.island_pivot,
                )

            return self.execute(context)
        else:
            self.report({'INFO'}, "There are no selected objects.")

        return {'CANCELLED'}

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        FR = FitRegion()
        if self.lock_in_trim and not FR.from_active_trim(context):
            self.report({'WARNING'}, "There are no Active Trim.")
            return {'CANCELLED'}

        if self.lock_in_trim:
            if self.fit_processor is None:
                self.fit_processor = TrFitProcessorEx()

            self.fit_processor.process(
                context,
                objs,
                self.influence_mode,
                self.op_order,
                FR.bbox,
                padding=0,
                fit_axis='AUTO',
                keep_proportion=True,
                align_to=self.island_pivot,
                auto_rotate=False,
                angle=-1 * math.radians(self.tr_rot_inc_full_range) * TrSpaceMode(context).editor_direction,
                rnd_angle=self.rnd_angle,
                image_aspect=ActiveUvImage(context).aspect
            )
        else:
            if self.rotate_processor is None:
                self.rotate_processor = TrRotateProcessorEx()

            self.rotate_processor.process(
                context,
                objs,
                self.influence_mode,
                self.op_order, self.island_pivot,
                ActiveUvImage(context).aspect,
                -1 * math.radians(self.tr_rot_inc_full_range) * TrSpaceMode(context).editor_direction,
                self.rnd_angle
            )

        return {'FINISHED'}


class ZUV_OT_TrUVRotateInTrim(bpy.types.Operator, ZuvTrRotateInTrimBase):
    bl_idname = "uv.zenuv_rotate_in_trim"

    island_pivot: TransformSysOpsProps.get_island_pivot_dynamic('zen_uv.ui.uv_tool.rotate_island_pivot')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._post_init()


class ZUV_OT_Tr3DVRotateInTrim(bpy.types.Operator, ZuvTrRotateInTrimBase):
    bl_idname = "view3d.zenuv_rotate_in_trim"

    island_pivot: TransformSysOpsProps.get_island_pivot_dynamic('zen_uv.ui.view3d_tool.rotate_island_pivot')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._post_init()


class ZuvTrScaleInTrimBase:

    bl_label = "Scale in Trim"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Scale Islands inside active Trim. Islands outside active Trim will be ignored"

    influence_mode: TransformSysOpsProps.influence_scene_mode
    op_order: TransformSysOpsProps.get_order_prop()

    # Operator Settings
    allow_negative: bpy.props.BoolProperty(
        name='Allow negative Scale',
        description='Allow negative scale',
        default=False
    )

    op_tr_scale_infinite: bpy.props.FloatVectorProperty(
        name="Scale",
        description="Scaling size",
        size=2,
        default=(1.0, 1.0),
        subtype='XYZ'
    )

    op_tr_scale_positive_only: bpy.props.FloatVectorProperty(
        name="Scale",
        description="Scaling size",
        size=2,
        default=(1.0, 1.0),
        min=0.0,
        subtype='XYZ'
    )

    scale_offset: bpy.props.FloatVectorProperty(
        name="Scale Offset",
        description="Scaling size",
        size=2,
        default=(0.0, 0.0),
        min=0.0,
        subtype='XYZ',
        options={'SKIP_SAVE'}
    )

    is_offset_mode: bpy.props.BoolProperty(
        name='Offset Mode',
        description="Scaling is performed by chain of small offsets",
        default=False,
        options={'SKIP_SAVE'}
    )

    def get_scale_value(self):
        if self.is_offset_mode:
            return self.scale_offset
        else:
            if self.allow_negative:
                return self.op_tr_scale_infinite
            else:
                return self.op_tr_scale_positive_only

    def set_scale_value(self, value):
        if self.is_offset_mode:
            self.is_offset_mode = False
        if self.allow_negative:
            self.op_tr_scale_infinite = value
        else:
            self.op_tr_scale_positive_only = value

    scale_value: bpy.props.FloatVectorProperty(
        name="Scale",
        description="Scaling size",
        size=2,
        min=0.0,
        step=1,
        subtype='XYZ',
        get=get_scale_value,
        set=set_scale_value,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    info_message: TransformSysOpsProps.info_message

    # cursor_2d_as_pivot: TransformSysOpsProps.cursor_2d_as_pivot

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout  # type: bpy.types.UILayout

        if self.info_message:
            box = layout.box()
            box.alert = True
            box.label(text=self.info_message, icon='ERROR')

        layout.prop(self, "influence_mode")
        layout.prop(self, 'op_order')

        s_box = layout.box()
        s_box.label(text="Settings:")
        s_box.prop(self, 'lock_in_trim')

        s_box.prop(self, 'scale_value')

        box = layout.box()
        col = box.column(align=True)
        col.prop(self, "island_pivot")

    invoke = ZuvTrMoveInTrimBase.invoke

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.info_message = "There are no selected objects"
            self.report({'WARNING'}, self.info_message)
            return {'CANCELLED'}

        trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if trim is not None:
            tr_bbox = BoundingBox2d(points=(trim.left_bottom, trim.top_right))
        else:
            tr_bbox = BoundingBox2d(points=(UV_AREA_BBOX().corners))

        scale = self._get_scale()

        result = TrScaleFlipProcessorEx.scale_in_trim(
                    context,
                    objs,
                    self.influence_mode,
                    self.op_order,
                    self.lock_in_trim,
                    self.island_pivot,
                    scale,
                    tr_bbox.get_as_dict()[self.island_pivot],
                    tr_bbox
                )
        if result != 'Finished':
            self.info_message = result
            self.report({'INFO'}, result)
        else:
            self.info_message = ''

        return {"FINISHED"}

    def _get_scale(self):
        return self.op_tr_scale_infinite if self.allow_negative else self.op_tr_scale_positive_only


class ZUV_OT_TrUVScaleInTrim(bpy.types.Operator, ZuvTrScaleInTrimBase):

    bl_idname = "uv.zenuv_scale_in_trim"

    island_pivot: TransformSysOpsProps.get_island_pivot_dynamic('zen_uv.ui.uv_tool.scale_island_pivot')

    lock_in_trim: TransformSysOpsProps.get_lock_in_trim_sync('UV_OT_zenuv_scale_in_trim')


class ZUV_OT_Tr3DVScaleInTrim(bpy.types.Operator, ZuvTrScaleInTrimBase):

    bl_idname = "view3d.zenuv_scale_in_trim"

    island_pivot: TransformSysOpsProps.get_island_pivot_dynamic('zen_uv.ui.view3d_tool.scale_island_pivot')

    lock_in_trim: TransformSysOpsProps.get_lock_in_trim_sync('VIEW3D_OT_zenuv_scale_in_trim')


class ZUV_OT_TrFlipInTrim(bpy.types.Operator):
    bl_idname = "uv.zenuv_flip_in_trim"
    bl_label = "Flip in Trim"
    bl_description = "Flip Islands relative to the center of active Trim"
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode: TransformSysOpsProps.influence_scene_mode
    op_order: TransformSysOpsProps.get_order_prop()

    info_message: TransformSysOpsProps.info_message

    def get_flip_direction(self):
        if self.direction in UV_AREA_BBOX.bbox_horizontal_handles:
            return 0b01
        elif self.direction in UV_AREA_BBOX.bbox_vertical_handles:
            return 0b10
        else:
            return 0b11

    def set_flip_directon(self, value):
        if value == 0b01:
            self.direction = UV_AREA_BBOX.bbox_horizontal_handles[0]
        elif value == 0b10:
            self.direction = UV_AREA_BBOX.bbox_vertical_handles[0]
        else:
            self.direction = UV_AREA_BBOX.bbox_corner_handles[0]

    in_trim: bpy.props.BoolProperty(
        name='Trim Center as Pivot',
        description='Use center of Trim as transformation Pivot',
        default=True
    )

    flip_direction: bpy.props.EnumProperty(
        name="Direction",
        description="",
        items=[
            ("HORIZONTAL", "Horizontal", "Horizontal", 0, 0b01),
            ("VERTICAL", "Vertical", "Vertical", 0, 0b10)
        ],
        options={'ENUM_FLAG', 'SKIP_SAVE'},
        get=get_flip_direction,
        set=set_flip_directon
    )

    direction: bpy.props.EnumProperty(
            name="Direction",
            items=TransformSysOpsProps._bbox_names_with_center,
            default=4
        )

    poll = TransformSysOpsProps.poll_edit_mesh_and_active_object

    poll_reason = TransformSysOpsProps.poll_reason_edit_mesh_and_active_object

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "influence_mode")
        layout.prop(self, "op_order")
        layout.prop(self, 'direction')
        layout.prop(self, 'in_trim')
        row = layout.row()
        row.prop(self, 'flip_direction', expand=True)

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.info_message = "There are no selected objects."
            self.report({'INFO'}, self.info_message)
            return {'CANCELLED'}
        if self.in_trim:
            self.op_order = 'OVERALL'
            trim = ZuvTrimsheetUtils.getActiveTrim(context)
            if trim is not None:
                pivot = BoundingBox2d(points=(trim.left_bottom, trim.top_right)).center
            else:
                pivot = BoundingBox2d(points=(UV_AREA_BBOX().corners)).center
        else:
            pivot = None

        result = TrScaleFlipProcessor.transform_scale_flip(
            context,
            objs,
            self.influence_mode,
            self.op_order,
            'cen',
            TrConstants.flip_vector[self.direction],
            pivot
        )

        if result != 'Finished':
            self.info_message = result
            self.report({'INFO'}, result)
        else:
            self.info_message = ''

        return {'FINISHED'}


class ZUV_OT_TrAlignToTrim(bpy.types.Operator):
    bl_idname = "uv.zenuv_align_to_trim"
    bl_label = "Align to Trim"
    bl_description = "Align Islands to active Trim"
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode_vertices: bpy.props.BoolProperty(
        name='Transform Vertices',
        default=False
    )
    influence_mode: TransformSysOpsProps.influence_scene_mode
    op_order: TransformSysOpsProps.get_order_prop()

    # Operator Settings
    align_direction: TransformSysOpsProps.align_direction
    i_pivot_as_direction: bpy.props.BoolProperty(
        name='As Direction',
        default=True,
        description='Set the island pivot to be the same as the alignment direction'
    )
    island_pivot: TransformSysOpsProps.align_direction
    use_single_axis: bpy.props.BoolProperty(
        name='Single Axis',
        description='Align only along one axis. Works only for Top, Bottom, Left, Right',
        default=True)
    use_trim_settings: bpy.props.BoolProperty(
        name='Use Trim Settings',
        description='Use Active Trim settings "Align to" instead of operator settings',
        default=False)

    info_message: TransformSysOpsProps.info_message

    poll = TransformSysOpsProps.poll_edit_mesh_and_active_object

    poll_reason = TransformSysOpsProps.poll_reason_edit_mesh_and_active_object

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'influence_mode_vertices')

        col = layout.column(align=True)
        col.enabled = not self.influence_mode_vertices
        col.prop(self, "influence_mode")
        col.prop(self, "op_order")

        box = layout.box()
        box.label(text='Settings:')
        box.prop(self, 'use_single_axis')

        row = box.row(align=True)
        sub_row = row.row(align=True)
        sub_row.enabled = not self.use_trim_settings
        sub_row.prop(self, 'align_direction', text='Align Direction')
        row.prop(self, 'use_trim_settings', toggle=True, icon='EVENT_T', text='')

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

        s_influence_mode = self.influence_mode
        if self.influence_mode_vertices:
            self.op_order = 'ONE_BY_ONE'
            s_influence_mode = 'VERTICES'

        if self.i_pivot_as_direction:
            self.island_pivot = self.align_direction

        trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if trim is None:
            input_bbox = UV_AREA_BBOX()
        else:
            input_bbox = BoundingBox2d(points=(trim.left_bottom, trim.top_right))

        if self.align_direction not in UV_AREA_BBOX.bbox_middle_handles:
            align_mode = False
        else:
            align_mode = self.use_single_axis

        MP = TrMoveProps(context, is_global=False)
        MP.move_mode = 'TO_ACTIVE_TRIM'

        MP.disable_tr_space_mode = True
        MP.is_align_mode = align_mode
        MP.align_direction = self.align_direction
        MP.destination_pos = input_bbox.get_as_dict()[self.align_direction]
        MP.use_trim_settings = self.use_trim_settings
        MP.i_pivot_as_direction = self.i_pivot_as_direction

        MF = MoveFactory(
            context,
            MP,
            s_influence_mode,
            objs,
            self.op_order,
            self.island_pivot
        )
        if not MF.move():
            self.report(MF.message[0], MF.message[1])
            return {'CANCELLED'}

        return {'FINISHED'}


class ZUV_OT_TrMoveToTrim(bpy.types.Operator):
    bl_idname = "uv.zenuv_move_to_trim"
    bl_label = "Move"
    bl_description = "Move selected Islands to Active Trim"
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode: TransformSysOpsProps.influence_scene_mode
    op_order: TransformSysOpsProps.get_order_prop()
    island_pivot: TransformSysOpsProps.island_pivot

    info_message: TransformSysOpsProps.info_message

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "influence_mode")
        layout.prop(self, "op_order")
        box = layout.box()
        box.prop(self, "island_pivot")

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        MP = TrMoveProps(context, is_global=False)
        MP.move_mode = 'TO_ACTIVE_TRIM'

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


trim_dep_tr_classes = (
    ZUV_OT_TrFitToTrim,
    ZUV_OT_TrFlipInTrim,
    ZUV_OT_TrAlignToTrim,
    ZUV_OT_TrMoveToTrim,

    ZUV_OT_Tr3DVRotateInTrim,
    ZUV_OT_Tr3DVMoveInTrim,
    ZUV_OT_Tr3DVScaleInTrim,

    ZUV_OT_TrUVRotateInTrim,
    ZUV_OT_TrUVMoveInTrim,
    ZUV_OT_TrUVScaleInTrim,
)


def register_trim_dep():
    RegisterUtils.register(trim_dep_tr_classes)


def unregister_trim_dep():
    RegisterUtils.unregister(trim_dep_tr_classes)
