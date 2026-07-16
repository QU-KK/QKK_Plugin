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

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
from ZenUV.utils.bounding_box import get_overall_bbox
from ZenUV.utils.constants import GREASE_PEN_LAYER_NAME, GREASE_PEN_DATA_NAME
from ZenUV.ops.transform_sys.tr_labels import TrLabels

from . transform_utils.tr_fit_utils import FitRegion, TrFitFactory
from .transform_utils.tr_utils import (
    TrConstants,
    TransformSysOpsProps,
    TransformOrderSolver
)


class ZUV_OT_TrFit(bpy.types.Operator):
    bl_idname = "uv.zenuv_fit"
    bl_label = "Fit"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Fit into Region"

    influence_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Transform Mode",
        items=[
            ("ISLAND", "Islands", ""),
            ("SELECTION", "Selection", ""),
            ("FACES", "Faces", ""),
        ],
        default="ISLAND"
    )
    op_order: TransformSysOpsProps.get_order_prop()
    fit_mode: bpy.props.EnumProperty(
        name='Fit',
        description="Transform Mode",
        items=[
            ("UV_AREA", "To UV Area", ""),
            ("REGION", "To Region", ""),
            ("ACTIVE_UDIM", "Active UDIM tile", "To active UDIM tile"),
            ("TILE_NUMBER", "Tile Number", "To UDIM tile with the specified number"),
            ("FILL", "Fill Islands", "")
        ],
        default="UV_AREA"
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
        description="The amount by which the islands should be reduced relative to the edges of the region",
        default=0.0,
        step=1
    )
    op_keep_proportion: bpy.props.BoolProperty(
        name="Keep proportion",
        description="Do not change the proportions of the selected island",
        default=True,
    )
    match_rotation: bpy.props.BoolProperty(
        name="Match Rotation",
        description="Match the rotation of the island to the rotation of the region (for rectangular regions)",
        default=False,
    )
    op_region_bl: bpy.props.FloatVectorProperty(
        name="Bottom-Left",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ'
    )
    op_region_tr: bpy.props.FloatVectorProperty(
        name="Top-Right",
        size=2,
        default=(1.0, 1.0),
        subtype='XYZ'
    )
    op_align_to: TransformSysOpsProps.island_pivot

    tile_number: bpy.props.IntProperty(
        name='Tile Number',
        description='Number of UDIM tile',
        default=1001,
        min=1001,
        max=2000
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "influence_mode")

        row = layout.row()
        row.enabled = self.influence_mode != 'FACES'
        row.prop(self, "op_order")

        layout.prop(self, "fit_mode")
        s_box = layout.box()
        s_box.enabled = self.is_activate_settings()
        s_box.label(text="Settings:")
        row = s_box.row()
        row.enabled = self.fit_mode == 'TILE_NUMBER'
        row.prop(self, 'tile_number')
        s_box.prop(self, 'op_fit_axis')

        s_box.prop(self, 'op_padding')

        if self.fit_mode == 'REGION':
            region_box = layout.box()
            region_box.label(text='Region:')
            col = region_box.column(align=True)
            row = col.row(align=True)
            col_v1 = row.column()
            col_v1.prop(self, "op_region_bl")
            col_v2 = row.column()
            col_v2.prop(self, "op_region_tr")

        keep_row = s_box.row()
        keep_row.enabled = not self.fit_mode == 'FILL'

        keep_row.prop(self, "op_keep_proportion")
        s_box.prop(self, 'match_rotation')
        box = layout.box()
        box.enabled = self.is_activate_pivot()
        row = box.row(align=True)
        row.prop(self, "op_align_to", text='Align To')

    def is_activate_pivot(self):
        return self.op_keep_proportion and self.fit_mode != 'FILL'

    def is_activate_settings(self):
        return self.fit_mode != 'FILL'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        order = self.op_order
        if self.fit_mode == 'UV_AREA':
            FR = FitRegion(TrConstants.uv_area_bl, TrConstants.uv_area_tr)
            self.set_region_props_from_operator(FR)

        elif self.fit_mode == 'REGION':
            FR = FitRegion(self.op_region_bl, self.op_region_tr)
            self.set_region_props_from_operator(FR)

        elif self.fit_mode == 'TILE_NUMBER':
            FR = FitRegion(self.op_region_bl, self.op_region_tr)
            FR.from_udim_tile(self.tile_number)
            if FR.report_message[0] is not None:
                self.report(FR.report_message[0], FR.report_message[1])
                return {'CANCELLED'}
            self.set_region_props_from_operator(FR)

        elif self.fit_mode == 'ACTIVE_UDIM':
            FR = FitRegion(self.op_region_bl, self.op_region_tr)
            FR.from_active_udim(context)
            if FR.report_message[0] is not None:
                self.report(FR.report_message[0], FR.report_message[1])
                return {'CANCELLED'}
            self.set_region_props_from_operator(FR)

        elif self.fit_mode == 'FILL':
            FR = FitRegion(TrConstants.uv_area_bl, TrConstants.uv_area_tr)
            FR.padding = 0.0
            FR.keep_proportion = False

        else:
            raise RuntimeError('"fit_mode" value incorrect')

        TF = TrFitFactory(
            context,
            self.influence_mode,
            objs,
            order,
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


class ZUV_OT_FitRegion(bpy.types.Operator):
    bl_idname = "uv.zenuv_fit_region"
    bl_label = "Fit into Region"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Fit into Region"

    fit_keep_proportion: bpy.props.BoolProperty(
        name="Keep proportion",
        description="",
        default=True,
    )
    st_fit_mode: bpy.props.EnumProperty(
        name=TrLabels.PREF_OT_PASTE_MATCH_LABEL,
        description=TrLabels.PREF_OT_PASTE_MATCH_DESC,
        items=[
            (
                "AUTO",
                TrLabels.PREF_OT_FIT_REGION_FULL_LABEL,
                TrLabels.PREF_OT_FIT_REGION_FULL_DESC
            ),
            (
                "U",
                TrLabels.PREF_OT_PASTE_MATCH_HOR_LABEL,
                TrLabels.PREF_OT_PASTE_MATCH_HOR_DESC
            ),
            (
                "V",
                TrLabels.PREF_OT_PASTE_MATCH_VERT_LABEL,
                TrLabels.PREF_OT_PASTE_MATCH_VERT_LABEL
            )
        ],
        default="AUTO"
    )
    align_to: TransformSysOpsProps.island_pivot

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "fit_keep_proportion")
        if self.fit_keep_proportion:
            box = layout.box()
            row = box.row(align=True)

            row.prop(self, "st_fit_mode", expand=True)
            box.prop(self, 'align_to')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            return {'CANCELLED'}
        prop = context.scene.zen_uv
        FR = FitRegion(prop.tr_fit_region_bl, prop.tr_fit_region_tr)
        FR.keep_proportion = self.fit_keep_proportion
        FR.fit_axis = self.st_fit_mode
        FR.align_to = self.align_to

        TF = TrFitFactory(
            context,
            prop.tr_type,
            objs,
            TransformOrderSolver.get(context),
            FR
            )

        TF.fit()

        return {"FINISHED"}


class ZUV_OT_FitGrabRegion(bpy.types.Operator):
    bl_idname = "uv.zenuv_fit_grab_region"
    bl_label = "Grab Region"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Grab Region"

    selected_only: bpy.props.BoolProperty(
        name="Selected",
        description="Grab selection or full island",
        default=True,
    )
    desc: bpy.props.StringProperty(name="Description", default="Grab Region coordinates form Selection", options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_desctiption

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        prop = context.scene.zen_uv
        ovr_bbox = get_overall_bbox(context, not self.selected_only)
        prop.tr_fit_region_bl = ovr_bbox["bl"]
        prop.tr_fit_region_tr = ovr_bbox["tr"]
        return {"FINISHED"}


class ZUV_OT_FitShowRegion(bpy.types.Operator):
    bl_idname = "uv.zenuv_fit_show_region"
    bl_label = "Show Region"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Show region using Annotations"

    color: bpy.props.FloatVectorProperty(
        name="Color",
        description="New tile color",
        subtype='COLOR',
        default=[0.3, 0.2, 0.8],
        size=3,
        min=0,
        max=1)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.annotations_toolbox.math_visualizer import MathVisualizer
        from mathutils import Vector

        prop = context.scene.zen_uv

        bl = prop.tr_fit_region_bl
        tr = prop.tr_fit_region_tr
        MV = MathVisualizer(context, pencil_name=GREASE_PEN_DATA_NAME)
        v1 = bl
        v2 = Vector((tr[0], bl[1]))
        v3 = tr
        v4 = Vector((bl[0], tr[1]))
        try:
            MV.add_vector(
                group=GREASE_PEN_LAYER_NAME,
                frame_idx=0,
                co_list=([v1, v2], [v2, v3], [v3, v4], [v4, v1]),
                color=self.color,
                clear=True,
                is_constant_arrow_size=True,
                arrow_size=0.0
            )

            letters_size = 3  # NOTE: non-screen: 0.025
            letters_position = (30, 10, 0)  # NOTE: non-screen: (v4[0], v4[1] + 0.005, 0)
            letters_line_width = 1  # NOTE: non-screen: 3

            MV.add_text(
                "Description", 0, "Zen UV | Fit | Region",
                line_width=letters_line_width, letters_size=letters_size, position=letters_position,
                clear=True, is_screen_mode=True)
        except Exception as e:
            print(e)
            print('Most likely Grease Pencil Data unavailable')
            return {'CANCELLED'}

        return {"FINISHED"}


class ZUV_OT_FitHideRegion(bpy.types.Operator):
    bl_idname = "uv.zenuv_fit_hide_region"
    bl_label = "Hide Region"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Hide Fit region"

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        try:
            gp_data = bpy.data.grease_pencils.get(GREASE_PEN_DATA_NAME)
            if gp_data is not None:
                bpy.data.grease_pencils.remove(gp_data)

        except Exception as e:
            print(e)
            print('Most likely Grease Pencil Data unavailable')
            return {'CANCELLED'}

        return {"FINISHED"}


uv_tr_fit_classes = (
    ZUV_OT_FitRegion,
    ZUV_OT_FitShowRegion,
    ZUV_OT_FitHideRegion,
    ZUV_OT_TrFit,
    ZUV_OT_FitGrabRegion
)


def register_tr_fit():
    RegisterUtils.register(uv_tr_fit_classes)


def unregister_tr_fit():
    RegisterUtils.unregister(uv_tr_fit_classes)
