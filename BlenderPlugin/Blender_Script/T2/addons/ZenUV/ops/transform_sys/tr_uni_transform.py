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

""" Zen UV Transformation module """


import bpy

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.hops_integration import show_uv_in_3dview

from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.generic import resort_objects_by_selection

from . tr_move import MoveFactory, TrMoveProps, TrMove2dCursor
from . tr_fit import FitRegion, TrFitFactory
from . tr_rotate import TrRotateProps, RotateFactory, TrOrientProcessor
from . tr_scale import TrScaleProps, ScaleFactory
from .transform_utils.tr_utils import TransformSysOpsProps, TransformOrderSolver
from . tr_ui import UnifiedControl


class ZUV_OT_UnifiedTransform(bpy.types.Operator):
    bl_idname = "uv.zenuv_unified_transform"
    bl_label = "Zen Transform"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.OT_MOVE_DESC

    transform_mode: bpy.props.StringProperty(
        name='Transform Mode',
        description='Sets Transform Mode',
        default='',
        options={'HIDDEN'}
    )
    orient_island: bpy.props.BoolProperty(
        name="Orient Island",
        description="",
        default=False,
        options={'HIDDEN'}
    )
    pp_pos: TransformSysOpsProps.island_pivot_hidden
    orient_direction: bpy.props.EnumProperty(
        name="Direction",
        description="",
        items=[
            ("HORIZONTAL", "Horizontal", "Horizontal orientation"),
            ("VERTICAL", "Vertical", "Vertical orientation"),
            ("AUTO", "Auto", "Auto detect orientation"),
        ],
        default="AUTO",
        options={'HIDDEN'}
    )
    rotate_direction: bpy.props.EnumProperty(
            name='Rotate Direction',
            description="Direction of rotation",
            items=[
                ("CW", "Clockwise", ""),
                ("CCW", "Counter-clockwise", ""),
            ],
            default="CW",
            options={'HIDDEN'}
        )
    fit_keep_proportion: bpy.props.BoolProperty(
        name="Fit Keep Proportion",
        description="",
        default=True,
        options={'HIDDEN'}
    )

    desc: bpy.props.StringProperty(name="Description", default="Transform", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'  # and properties.active

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_desctiption

    # def draw(self, layout):
    #     pass

    def execute(self, context):

        tr_props = context.scene.zen_uv

        # Type of transformation Islands or Selection
        is_transform_islands = tr_props.tr_type == 'ISLAND'

        if self.transform_mode == "" or self.transform_mode not in UnifiedControl.STATE:
            transform_mode = tr_props.tr_mode
        else:
            transform_mode = self.transform_mode

        # Any transforms blocked (operator CANCELLED) if no selection.
        # Except case 2D Cursor operation.
        # It allows positioning 2D Cursor over UV Area withot Selection.
        objs = resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            if not transform_mode == "2DCURSOR":
                self.report({'WARNING'}, "Zen UV: Select something.")
                return {"CANCELLED"}

        pivot_point = TransformOrderSolver.get(context)
        if pivot_point == '':
            pivot_point = 'CENTER'

        # 2D Cursor Mode
        if transform_mode == "2DCURSOR":
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    p_position = TrMove2dCursor.get_position(
                        context,
                        tr_props.tr_set_cursor_to,
                        self.pp_pos,
                        tr_props.tr_tile_number,
                        tr_props.tr_align_position
                    )
                    if p_position is False:
                        self.report(TrMove2dCursor.report[0], TrMove2dCursor.report[1])
                        return {'CANCELLED'}

                    area.spaces.active.cursor_location = p_position

        # Move Mode
        if transform_mode == "MOVE":
            MP = TrMoveProps(context, is_global=True)
            MP.direction_str = self.pp_pos
            if pivot_point == 'CURSOR':
                MP.move_mode = 'TO_CURSOR'
            else:
                MP.move_mode = 'INCREMENT'
            MF = MoveFactory(
                context,
                MP,
                tr_props.tr_type,
                objs,
                pivot_point,
                island_pivot='cen'
                )
            MF.move()

        # Flip/Scale Mode
        if transform_mode in ("FLIP", "SCALE"):
            SF = ScaleFactory(
                context,
                TrScaleProps(context, is_global=True),
                tr_props.tr_type,
                objs,
                pivot_point,
                self.pp_pos,
                transform_mode
            )
            SF.transform_scale_flip()

        # Fit Mode
        if transform_mode == "FIT":
            FR = FitRegion()
            FR.fill_from_global(context, self.pp_pos)
            FR.keep_proportion = self.fit_keep_proportion
            TF = TrFitFactory(
                context,
                tr_props.tr_type,
                objs,
                pivot_point,
                FR
                )
            TF.fit()

        # Rotate Mode
        if transform_mode == "ROTATE":
            if self.orient_island is True:
                TrOrientProcessor.orient(
                    context,
                    objs,
                    'BBOX',
                    self.orient_direction,
                    self.rotate_direction
                    )
            else:
                RP = TrRotateProps(context, is_global=True)
                RP.op_direction = self.rotate_direction

                RF = RotateFactory(
                    context,
                    RP,
                    is_transform_islands,
                    objs,
                    pivot_point,
                    'cen'
                )
                RF.rotate()

        # Align Mode
        if transform_mode == "ALIGN":
            no_sync_mode = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
            if tr_props.tr_align_to == "TO_ACTIVE_COMPONENT" and no_sync_mode:
                self.report({'WARNING'}, "Active Component mode is not allowed in the UV Sync Selection is Off.")
                return {'CANCELLED'}
            influence_mode = 'VERTICES' if tr_props.tr_type == 'SELECTION' and tr_props.tr_align_vertices else tr_props.tr_type

            MP = TrMoveProps(context, is_global=True)
            MP.move_mode = tr_props.tr_align_to

            MP.is_align_mode = True
            MP.align_direction = self.pp_pos

            MP.tile_number = tr_props.tr_tile_number

            MF = MoveFactory(
                context,
                MP,
                influence_mode,
                objs,
                pivot_point,
                self.pp_pos
            )
            MF.move()

        # Display UV Widget from HOPS addon
        show_uv_in_3dview(context, use_selected_meshes=True, use_selected_faces=False, use_tagged_faces=True)

        return {'FINISHED'}


unified_transform_classes = (
    ZUV_OT_UnifiedTransform,
)


def register_uni_transform():
    RegisterUtils.register(unified_transform_classes)


def uregister_uni_transform():
    RegisterUtils.unregister(unified_transform_classes)


if __name__ == '__main__':
    pass
