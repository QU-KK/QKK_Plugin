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

# Copyright 2023, Alex Zhornyak

import bpy
from mathutils import Vector

from ast import literal_eval

from ZenUV.ico import icon_get
from ZenUV.utils.blender_zen_utils import (
    update_areas_in_uv,
    update_areas_in_view3d,
    show_message_box)
from ZenUV.utils.vlog import Log

from ZenUV.ops.transform_sys.transform_utils.tr_utils import (
    TransformSysOpsProps
)

from ZenUV.ops.texel_density.td_props import TdProps

from ZenUV.ui.labels import ZuvLabels


_mode_items = []

# NOTE: by default it must much 2d cursor which is set to 0 coordinates
DEFAULT_TR_GIZMO_PIVOT_HANDLE = (0.0, 0.0)
DEFAULT_TR_GIZMO_ANGLE_HANDLE = (0.5, 0.5)


class TrGizmoSetTransformException(Exception):
    """ Can not set transform mode in 'uv_tool_props.tr_gizmo_mode' """
    pass


class ZuvToolProps:

    space_type = ''

    def update_view(self, context: bpy.types.Context):
        if self.space_type == 'UV':
            update_areas_in_uv(context)
        else:
            update_areas_in_view3d(context)

    display_trims: bpy.props.BoolProperty(
        name='Display Trims',
        description='Display Trimsheet Trims',
        default=False,
        update=update_view,
        options=set()
    )

    display_all: bpy.props.BoolProperty(
        name='Display All Trims',
        description='Display all Trims or only active Trim',
        default=True,
        update=update_view,
        options=set()
    )

    select_trim: bpy.props.BoolProperty(
        name='Trim Select',
        description='Activate Trim Selector',
        default=False,
        update=update_view,
        options=set()
    )

    def get_select_trim_ex(self):
        return self.display_trims and self.select_trim

    def set_select_trim_ex(self, value):
        if value:
            self.display_trims = True
            if hasattr(self, 'trim_select_mode'):
                self.trim_select_mode = 'MESH'

        self.select_trim = value

    select_trim_ex: bpy.props.BoolProperty(
        name='Trim Select',
        description='Activate Trim Selector',
        get=get_select_trim_ex,
        set=set_select_trim_ex,
        update=update_view,
        options={'SKIP_SAVE'}
    )

    tr_handles: bpy.props.EnumProperty(
        name='Transform Handles',
        description='Enable handles for uv transform operations',
        items=[
            ('OFF', 'Off', 'Transform handles are disabled', 'CURSOR', 1),
            ('TRIM', 'Trim', 'Transform handles are placed at the trim corners', 'PIVOT_BOUNDBOX', 2),
            ('GIZMO', 'Gizmo', 'Transform handles are placed around gizmo', 'PIVOT_CURSOR', 3)
        ],
        default='TRIM',
        update=update_view,
        options=set()
    )

    auto_options_expanded: bpy.props.BoolProperty(
        name='Automatic Settings',
        description='Tool automatic settings expanded-collapsed',
        default=False,
        options=set()
    )

    scale_island_pivot: TransformSysOpsProps.island_pivot

    rotate_island_pivot: TransformSysOpsProps.island_pivot

    trim_preview_expanded: bpy.props.BoolProperty(
        name="Trim Preview",
        description="Trim preview expanded",
        options=set(),
        default=False
    )

    trim_list_expanded: bpy.props.BoolProperty(
        name="Trim List",
        description="Trim list expanded",
        options=set(),
        default=True
    )


class ZuvFitToSelectionProps:

    pivot_in_center = bpy.props.BoolProperty(
        name='Pivot in Center',
        description='Set pivot in the selection center',
        default=False,
        options=set()
    )

    direction = bpy.props.EnumProperty(
        name="Direction",
        description="Specifies how to place the gizmo. Along the selection or across it",
        items=[
            ('ALONG', 'Along', 'Along the selection'),
            ('ACROSS', 'Across', 'Across the selection')
        ],
        default='ALONG',
        options=set()
    )


class ZUV_UVToolProps(bpy.types.PropertyGroup, ZuvToolProps):

    space_type = 'UV'

    category: bpy.props.EnumProperty(
        name='Tool Category',
        description='Zen UV tool category',
        items=[
            ('TRANSFORMS', 'Transforms', 'Transform uv category: move, rotate, scale', icon_get('pn_Transform'), 1),
            ('TRIMS', 'Trims', 'Trims category: display, select, create and resize', icon_get('pn_Trimsheet'), 2)
        ],
        default=('TRANSFORMS')
    )

    transform_mode: bpy.props.EnumProperty(
        name='Transform Mode',
        description='Zen UV tool transform mode',
        items=[
            ('MOVE', 'Move', 'Moves UV islands or mesh elements', icon_get('transform-move'), 1),
            ('ROTATE', 'Rotate', 'Rotates UV islands or mesh elements', icon_get('transform-rotate'), 2),
            ('SCALE', 'Scale', 'Scales UV islands or mesh elements', icon_get('transform-scale'), 3),
        ],
        default='MOVE',
        update=ZuvToolProps.update_view
    )

    trim_mode: bpy.props.EnumProperty(
        name='Trim Mode',
        description='Zen UV tool trims mode',
        items=[
            ('RESIZE', 'Resize', 'Resize trims', 'CON_SIZELIMIT', 1),
            ('CREATE', 'Create', 'Create trims', 'GREASEPENCIL', 2),
        ],
        default='RESIZE',
        update=ZuvToolProps.update_view
    )

    def mode_items(self, context):
        p_rna = self.bl_rna.properties['transform_mode']
        p_items_1 = [
            # get icons only thgrough function !
            (item.identifier, item.name, item.description, icon_get(f'transform-{item.identifier.lower()}'), idx + 1)
            for idx, item in enumerate(p_rna.enum_items)]

        p_rna = self.bl_rna.properties['trim_mode']
        p_items_2 = [
            (item.identifier, item.name, item.description, item.icon, idx + 1 + len(p_items_1))
            for idx, item in enumerate(p_rna.enum_items)]
        p_items = p_items_1 + p_items_2

        global _mode_items
        if len(_mode_items) == 0:
            _mode_items = p_items.copy()

        return _mode_items

    def get_mode(self):
        p_rna_items = self.bl_rna.properties['transform_mode'].enum_items
        if self.category == 'TRANSFORMS':
            for idx, item in enumerate(p_rna_items):
                if item.identifier == self.transform_mode:
                    return idx + 1
        else:
            p_rna_items_2 = self.bl_rna.properties['trim_mode'].enum_items
            for idx, item in enumerate(p_rna_items_2):
                if item.identifier == self.trim_mode:
                    return len(p_rna_items) + idx + 1
        return 0

    def set_mode(self, value):
        p_rna = self.bl_rna.properties['transform_mode']
        idx = 0
        for item in p_rna.enum_items:
            idx += 1
            if value == idx:
                self.transform_mode = item.identifier
                self.category = 'TRANSFORMS'
                return

        p_rna = self.bl_rna.properties['trim_mode']
        for item in p_rna.enum_items:
            idx += 1
            if value == idx:
                self.trim_mode = item.identifier
                self.category = 'TRIMS'
                return

    mode: bpy.props.EnumProperty(
        name='Tool Mode',
        description='Zen UV tool mode',
        items=mode_items,
        get=get_mode,
        set=set_mode
    )

    lock_trim_size: bpy.props.BoolProperty(
        name='Lock Trim Size',
        description='If enabled then trim width will be equal to its height during resizing',
        default=False
    )

    use_trim_snap: bpy.props.BoolProperty(
        name='Snap',
        description='Snap trim to pixels, grid etc.',
        default=False
    )

    trim_snap_mode: bpy.props.EnumProperty(
        name='Trim Snap Mode',
        description='Mode of trim snapping during moving or resizing',
        items=[
            ('PIXELS', 'Pixels', 'Snap to image pixels', 'SNAP_INCREMENT', 2**0),
            ('GRID', 'Grid', 'Snap to UV grid', 'SNAP_GRID', 2**1),
            ('TRIMS', 'Trims', 'Snap to trim borders', 'NODE_CORNER', 2**2),
        ],
        options={'ENUM_FLAG'},
        default={'GRID'}
    )

    trim_snap_pivot: bpy.props.EnumProperty(
            name='Snap Pivot',
            description='Trim snap pivot point',
            items=[
                ("br", 'Bottom-Right', '', icon_get("tr_control_br"), 0),
                ("bl", 'Bottom-Left', '', icon_get("tr_control_bl"), 1),
                ("tr", 'Top-Right', '', icon_get("tr_control_tr"), 2),
                ("tl", 'Top-Left', '', icon_get("tr_control_tl"), 3),
            ],
            default='bl',
            options=set()
        )

    trim_snap_threshold: bpy.props.IntProperty(
        name='Snap Threshold',
        description='Trim corners snap threshold in pixels',
        default=10,
        subtype='PIXEL',
        min=1,
        max=500,
        options=set()
    )

    def poll_trim_snap_mode(self, context: bpy.types.Context):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        s_snap_mode = self.trim_snap_mode

        t_enabled = set()

        if 'PIXELS' in s_snap_mode:
            b_res = ZuvTrimsheetUtils.getSpaceDataImage(context) is not None
            t_enabled.add(b_res)
        if 'TRIMS' in s_snap_mode:
            p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
            b_res = len(p_trimsheet) > 1
            t_enabled.add(b_res)
        if 'GRID' in s_snap_mode:
            t_enabled.add(True)

        return True in t_enabled

    # NOTE: ######## Transform Gizmo Section ########

    def tr_gizmo_apply_auto_setup_by_selection(self):
        if bpy.ops.uv.zenuv_tool_transform_fit_to_selection.poll():
            bpy.ops.uv.zenuv_tool_transform_fit_to_selection(
                influence=self.tr_gizmo_influence,
                pivot_in_center=self.tr_gizmo_fit_to_selection_pivot_in_center,
                direction=self.tr_gizmo_fit_to_selection_direction,
                allow_toggle_direction=False)

    def on_tr_gizmo_auto_setup_by_selection_update(self, context: bpy.types.Context):
        if True or self.tr_gizmo_mode == 'SETUP':
            if self.tr_gizmo_auto_setup_by_selection:
                try:
                    # NOTE: this will trigger update gizmo action and update gizmo position
                    if isinstance(context.space_data, bpy.types.SpaceImageEditor):
                        self.tr_gizmo_apply_auto_setup_by_selection()
                except Exception as e:
                    Log.error("AUTO SETUP BY SELECTION:", e)

    def on_tr_gizmo_mode_update(self, context: bpy.types.Context):
        try:
            self.tr_gizmo_active = False
            self.tr_gizmo_axes_lock = 'NONE'
            self.tr_gizmo_event_mode = 'DEFAULT'
            self.tr_gizmo_display_xy_guidelines = (False, False)

            wm = context.window_manager
            from ZenUV.prop.wm_props import ZuvWMTransformToolGroup
            wm_tool_props: ZuvWMTransformToolGroup = wm.zen_uv.uv_transform_tool
            wm_tool_props.clear_scale_spinner_event()
            if self.tr_gizmo_mode == 'TRANSFORM':
                from ZenUV.utils.selection_utils import SelectionProcessor
                if not SelectionProcessor.is_uv_selected(context):
                    raise TrGizmoSetTransformException("Select something\nto start transformation!")

                if self.tr_gizmo_distance <= 1e-6:
                    from ZenUV.ui.tool.tool_ops import ZUV_OP_ToolTransform

                    if not wm.operators or not isinstance(wm.operators[-1], ZUV_OP_ToolTransform):
                        raise TrGizmoSetTransformException("Increase distance between handles\nto start transformation")
        except TrGizmoSetTransformException as e:
            self.tr_gizmo_mode = 'SETUP'
            show_message_box(message=str(e), title="WARNING", icon="ERROR")
        update_areas_in_uv(context)

    def on_tr_gizmo_active_update(self, context: bpy.types.Context):
        bpy.app.driver_namespace["zenuv_tr_gizmo_origin_list"] = dict()

    tr_gizmo_active: bpy.props.BoolProperty(
        name="Transforming Active",
        default=False,
        options={'SKIP_SAVE'},
        update=on_tr_gizmo_active_update
    )

    tr_gizmo_influence: bpy.props.EnumProperty(
        name='Influence',
        description='Transform Influence. Affect Islands or Elements (vertices, edges, polygons)',
        items=[
            ("ISLAND", "Island", "Process islands", "UV_ISLANDSEL", 0),
            ("SELECTION", "Selection", "Process selected mesh elements (vertices, edges, faces)", 'UV_FACESEL', 1)
        ],
        default="ISLAND",
        update=on_tr_gizmo_auto_setup_by_selection_update
    )

    tr_gizmo_mode: bpy.props.EnumProperty(
        name="Gizmo Mode",
        description="Defines what type of operation is performed by gizmo",
        items=[
            ("SETUP", "Setup", "Setting up gizmo position", "MODIFIER", 0),
            ("TRANSFORM", "Transform", "Transforming UVs", "TRANSFORM_ORIGINS", 1)
        ],
        options={'SKIP_SAVE'},
        default="SETUP",
        update=on_tr_gizmo_mode_update
    )

    tr_gizmo_transform_editing_mode: bpy.props.EnumProperty(
        name="Editing Mode",
        description="Defines how UV editing behaves in Transform Gizmo mode",
        items=[
            ("DEFAULT", "Default", "", "OBJECT_ORIGIN", 0),
            ("RADIAL_FALLOFF", "Radial Falloff", "", "SPHERECURVE", 1),
            ("LINEAR_FALLOFF", "Linear Falloff", "", "LINCURVE", 2),
        ],
        default="DEFAULT"
    )

    def tr_gizmo_is_falloff_enabled(self):
        return self.tr_gizmo_transform_editing_mode in {"RADIAL_FALLOFF", "LINEAR_FALLOFF"}

    tr_gizmo_invert_falloff: bpy.props.BoolProperty(
        name="Invert Falloff",
        description="Invert the falloff effect",
        default=False
    )

    tr_gizmo_falloff_exponent: bpy.props.FloatProperty(
        name='Falloff Exponent',
        description='Controls the strength of the falloff effect',
        default=1.0,
        min=0.0,
        max=100
    )
    tr_gizmo_linear_falloff_transformation_type: bpy.props.EnumProperty(
        name='Linear falloff type',
        description='Select the transformation used in linear falloff mode for the angle handle',
        items=[
            ('ROTATE', 'Rotation', 'Use rotation transformation'),
            ('MOVE', 'Translation', 'Use translation transformation'),
            ],
        default={'ROTATE', 'MOVE'},
        options={'ENUM_FLAG'}
    )

    _tr_gizmo_axes_lock_items = [
            ("NONE", "None", "Axes are not locked"),
            ("AXIS_LOCK_MOVE_X", "Axis X", "Axis X is locked for move"),
            ("AXIS_LOCK_MOVE_Y", "Axis Y", "Axis Y is locked for move"),
            ("AXIS_LOCK_SCALE_X", "Axis X - Scale", "Axis X is locked for scale"),
            ("AXIS_LOCK_SCALE_Y", "Axis Y - Scale", "Axis Y is locked for scale"),
            ("SCALE_ALONG_AXIS", "Scale Along Axis", "Uniform scale along axis"),
            ("MOVE_ALONG_AXIS", "Move Along Axis", "Axis angle is locked"),
            ("SCALE_ALONG_AXIS_NO_PROPORTION", "Scale Along Axis Non-Uniform", "The axis angle is locked, and uniform scaling is not allowed"),
            ("PURE_ROTATION", "Pure Rotation", "Distance between pivot and a-handle is locked"),
        ]

    tr_gizmo_axes_lock: bpy.props.EnumProperty(
        name="Axis Lock Mode",
        description="Transform gizmo axes lock mode",
        items=_tr_gizmo_axes_lock_items,
        options={'SKIP_SAVE'},
        default="NONE"
    )

    def on_tr_gizmo_event_mode_update(self, context: bpy.types.Context):
        try:
            if self.tr_gizmo_event_mode != 'DEFAULT':
                from ZenUV.utils.selection_utils import SelectionProcessor
                if not SelectionProcessor.is_uv_selected(context):
                    raise TrGizmoSetTransformException("Select something")
        except TrGizmoSetTransformException as e:
            self.tr_gizmo_event_mode = 'DEFAULT'
            show_message_box(message=str(e), title="WARNING", icon="ERROR")

    tr_gizmo_event_mode: bpy.props.EnumProperty(
        name="Transform Gizmo Event Mode",
        description="Defines does user need to click on gizmo handle or on every place in the viewport",
        items=[
            ("DEFAULT", "Default", "User needs to click on gizmo handle"),
            ("EVENT_MOVE", "Move", "UV is moving when user presses mouse button in every place of the viewport"),
            ("EVENT_ROTATE", "Rotate", "UV is rotating when user presses mouse button in every place of the viewport"),
            ("EVENT_SCALE", "Scale", "UV is scaling when user presses mouse button in every place of the viewport"),
        ],
        options={'SKIP_SAVE'},
        default="DEFAULT",
        update=on_tr_gizmo_event_mode_update
    )

    tr_gizmo_type: bpy.props.EnumProperty(
        name="Transform Gizmo Type",
        description="Defines active gizmo part",
        items=[
            (
                'PIVOT_HANDLE',
                'Pivot Handle',
                '-- SETUP --\n'
                'Setup gizmo pivot handle\n'
                ' * Double Click - Fit gizmo to island\n'
                ' * Double Click + Ctrl - Fit gizmo to island pivot in center\n'
                '-- TRANSFORM --\n'
                'Transform gizmo pivot handle\n'
                ' * Double Click - World orient'
            ),
            (
                'ANGLE_HANDLE',
                'Angle Handle',
                '-- SETUP --\n'
                'Setup gizmo angle handle\n'
                ' * Double Click - Fit gizmo to selection\n'
                ' * Double Click + Ctrl - Fit gizmo to selection pivot in center\n'
                '-- TRANSFORM --\n'
                'Transform gizmo angle handle\n'
                ' * Double Click - Set texel density\n'
                ' * Double Click + Ctrl - Get texel density'
            ),

            (
                'LINE',
                'Line',
                '-- SETUP --\n'
                'Setup gizmo line\n'
                ' * Double Click - Toggle move along axis\n'
                '-- TRANSFORM --\n'
                'Transform gizmo line\n'
                ' * Double Click - Toggle move along axis'
            ),
            (
                'ROTATE',
                'Rotate',
                'Transform gizmo rotate\n'
                '-- TRANSFORM --\n'
                ' * Double Click - Increment Rotation\n'
                ' * Double Click + Ctrl - Decrement Rotation'
            ),

            (
                'SCALE',
                'Scale',
                'Transform gizmo uniform scale handle\n'
                '-- TRANSFORM --\n'
                ' * Double Click - Double scale'
            ),
            (
                'SCALE_NON_PROP',
                'Scale Non-Uniform',
                'Transform gizmo non-uniform scale\n'
                '-- TRANSFORM --\n'
                ' * Double Click - Halve scale\n'
                ' * Double Click + Ctrl - Scale to zero'
            )
        ],
        options={'ENUM_FLAG'},
        default={"PIVOT_HANDLE"}
    )

    tr_gizmo_auto_setup_by_selection: bpy.props.BoolProperty(
        name="Auto Setup By Selection",
        description="Gizmo handles automatically set up by selection depending on island or selection influence",
        default=False,
        update=on_tr_gizmo_auto_setup_by_selection_update
    )

    def get_tr_gizmo_pivot_handle_internal(self):
        """ Internal Pivot Handle Coordinates """
        return self.get('_tr_gizmo_pivot_handle', DEFAULT_TR_GIZMO_PIVOT_HANDLE)

    def update_cursor_location_in_uv(self, context: bpy.types.Context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    p_space = area.spaces.active
                    if p_space:
                        if Vector(p_space.cursor_location) != Vector(self.tr_gizmo_origin):
                            p_space.cursor_location = self.tr_gizmo_origin[:]
                            area.tag_redraw()

    tr_gizmo_fit_to_selection_direction: ZuvFitToSelectionProps.direction

    tr_gizmo_fit_to_selection_pivot_in_center: ZuvFitToSelectionProps.pivot_in_center

    tr_gizmo_origin: bpy.props.FloatVectorProperty(
        name="Transform Gizmo Origin",
        size=2,
        default=(0, 0)
    )

    def get_tr_gizmo_pivot_handle(self):
        """ Pivot Handle Coordinates depending on the gizmo type """
        if self.tr_gizmo_is_pivot:
            return self.tr_gizmo_origin
        return self.get_tr_gizmo_pivot_handle_internal()

    def set_tr_gizmo_pivot_handle(self, value):
        self['_tr_gizmo_pivot_handle'] = value

    def tr_gizmo_setup_cursor_2d(self, context: bpy.types.Context):
        if self.tr_gizmo_is_pivot:
            self.tr_gizmo_origin = Vector(self.get(
                '_tr_gizmo_pivot_handle', self.tr_gizmo_origin))
        else:
            self.tr_gizmo_origin = Vector(self.get(
                '_tr_gizmo_angle_handle', self.tr_gizmo_origin))
        self.update_cursor_location_in_uv(context)

    def on_tr_gizmo_making_transform(self, context: bpy.types.Context):
        from ZenUV.ui.tool.tool_ops import ZUV_OP_ToolTransform
        ZUV_OP_ToolTransform.modal_making_transform(context, self)

    def on_tr_gizmo_pivot_handle_update(self, context: bpy.types.Context):
        self.on_tr_gizmo_making_transform(context)

    def on_tr_gizmo_angle_handle_update(self, context: bpy.types.Context):
        self.on_tr_gizmo_making_transform(context)

    tr_gizmo_pivot_handle: bpy.props.FloatVectorProperty(
        name="Transform Gizmo Pivot Location",
        description="UV coordinates of transfrom gizmo pivot",
        size=2,
        get=get_tr_gizmo_pivot_handle,
        set=set_tr_gizmo_pivot_handle,
        update=on_tr_gizmo_pivot_handle_update
    )

    def get_tr_gizmo_angle_handle_internal(self):
        return self.get('_tr_gizmo_angle_handle', DEFAULT_TR_GIZMO_ANGLE_HANDLE)

    def get_tr_gizmo_angle_handle(self):
        if not self.tr_gizmo_is_pivot:
            return self.tr_gizmo_origin
        return self.get_tr_gizmo_angle_handle_internal()

    def set_tr_gizmo_angle_handle(self, value):
        self['_tr_gizmo_angle_handle'] = value

    tr_gizmo_angle_handle: bpy.props.FloatVectorProperty(
        name="Transform Gizmo Handle Location",
        description="UV coordinates of transfrom gizmo handle",
        size=2,
        get=get_tr_gizmo_angle_handle,
        set=set_tr_gizmo_angle_handle,
        update=on_tr_gizmo_angle_handle_update
    )

    def set_gizmo_type_and_synchronize_cursor_2d(self, context: bpy.types.Context, value):
        """ Synchronize internal data if gizmo types changes from Pivot to A-Handle and back"""
        was_cursor = self.tr_gizmo_origin[:]

        b_was_pivot = 'PIVOT_HANDLE' in self.tr_gizmo_type
        b_is_pivot = 'PIVOT_HANDLE' in value

        if b_was_pivot != b_is_pivot:
            # NOTE: this will synchronize internal data
            if b_was_pivot:
                self.set_tr_gizmo_pivot_handle(was_cursor)
            else:
                self.set_tr_gizmo_angle_handle(was_cursor)

        self.tr_gizmo_type = value

    def get_tr_gizmo_line_internal(self):
        return (
            *self.get_tr_gizmo_pivot_handle_internal()[:],
            *self.get_tr_gizmo_angle_handle_internal()[:])

    def get_tr_gizmo_line(self):
        return (*self.tr_gizmo_pivot_handle[:], *self.tr_gizmo_angle_handle[:])

    def set_tr_gizmo_line(self, value):
        d_pivot = value[:2]
        d_handle = value[2:4]
        self.set_tr_gizmo_pivot_handle(d_pivot)
        self.set_tr_gizmo_angle_handle(d_handle)

    tr_gizmo_line: bpy.props.FloatVectorProperty(
        name="Transform Gizmo Line Location",
        description="UV coordinates of transfrom gizmo line",
        size=4,
        get=get_tr_gizmo_line,
        set=set_tr_gizmo_line,
        update=on_tr_gizmo_angle_handle_update
    )

    def get_tr_gizmo_angle(self):
        try:
            v_delta = Vector(self.tr_gizmo_angle_handle) - Vector(self.tr_gizmo_pivot_handle)
            res = v_delta.angle_signed(Vector((1, 0)), 0)
        except Exception as e:
            Log.error("TR GIZMO ANGLE:", e)
            res = 0

        return res

    tr_gizmo_angle: bpy.props.FloatProperty(
        name="Transform Gizmo Angle",
        description="Angle between handle and pivot",
        get=get_tr_gizmo_angle
    )

    def get_tr_gizmo_distance(self):
        v_gizmo: Vector = Vector(self.tr_gizmo_angle_handle) - Vector(self.tr_gizmo_pivot_handle)
        return v_gizmo.length

    tr_gizmo_distance: bpy.props.FloatProperty(
        name="Transform Gizmo Distance",
        description="Distance between handle and pivot",
        get=get_tr_gizmo_distance
    )

    def get_tr_gizmo_is_pivot(self):
        return 'PIVOT_HANDLE' in self.tr_gizmo_type

    tr_gizmo_is_pivot: bpy.props.BoolProperty(
        name="Is Pivot",
        description="Is transform gizmo in pivot handle type",
        get=get_tr_gizmo_is_pivot
    )

    tr_gizmo_init_p_handle: bpy.props.FloatVectorProperty(
        name="Transform Gizmo Initial P-Handle",
        size=2
    )

    tr_gizmo_init_a_handle: bpy.props.FloatVectorProperty(
        name="Transform Gizmo Initial A-Handle",
        size=2
    )

    tr_gizmo_undo_list: bpy.props.CollectionProperty(
        name="Undo List",
        type=bpy.types.PropertyGroup
    )

    tr_gizmo_undo_list_index: bpy.props.IntProperty(
        name="Undo List Index",
        min=-1,
        default=-1
    )

    tr_gizmo_dial_snap_step_angle: bpy.props.EnumProperty(
        name="Dial Step Angle",
        description="Step of dial angle (degrees) step in transformation gizmo",
        items=[
            ("1_DEG", "1°", "Angle step with 1°"),
            ("5_DEG", "5°", "Angle step with 5°"),
            ("10_DEG", "10°", "Angle step with 10°"),
            ("15_DEG", "15°", "Angle step with 15°"),
            ("30_DEG", "30°", "Angle step with 30°"),
            ("45_DEG", "45°", "Angle step with 45°"),
            ("90_DEG", "90°", "Angle step with 90°")
        ],
        default="5_DEG"
    )

    tr_gizmo_line_lock_along_axis: bpy.props.BoolProperty(
        name="Lock Line Along Axis",
        description="Transformation by dragging line will be performed only along axis",
        default=False
    )

    tr_gizmo_draw_allow_merge: bpy.props.BoolProperty(
        name="Allow Merge In Draw",
        description="Snapped UV vertices are welded together during mouse draw",
        default=True
    )

    tr_gizmo_draw_use_snap_margin: bpy.props.BoolProperty(
        name="Snap Margin In Draw",
        description="UV vertices are drawn with an offset relative to snapped points",
        default=False
    )

    tr_gizmo_snap_to_gizmo_flip_point: bpy.props.BoolProperty(
        name="Flip Point",
        description="Gizmo transform flip point is included to snap targets",
        default=True
    )

    tr_gizmo_snap_to_gizmo_origin_points: bpy.props.BoolProperty(
        name="Origin Points",
        description="Gizmo origin points are included to snap targets",
        default=True
    )

    tr_gizmo_display_xy_guidelines: bpy.props.BoolVectorProperty(
        name="Display XY Guidelines",
        description="Show X, Y axis guidelines in the viewport",
        size=2,
        default=(False, False),
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def tr_gizmo_set_location_by_active_type(
            self, context: bpy.types.Context,
            pivot=None, handle=None):
        self.tr_gizmo_set_location(
            context, pivot=pivot, handle=handle,
            is_pivot=self.tr_gizmo_is_pivot)

    def tr_gizmo_set_location_with_transform_by_active_type(
            self, context: bpy.types.Context,
            origin_pivot, origin_head, matched_pivot, matched_head, axes_lock_mode: str = ""):
        self.tr_gizmo_set_location_with_transform(
            context,
            origin_pivot, origin_head, matched_pivot, matched_head,
            is_pivot=self.tr_gizmo_is_pivot,
            axes_lock_mode=axes_lock_mode
        )

    def tr_gizmo_set_location(
            self, context: bpy.types.Context,
            pivot=None, handle=None,
            is_pivot=True):
        self.tr_gizmo_active = False
        self.tr_gizmo_axes_lock = 'NONE'
        self.tr_gizmo_type = {'PIVOT_HANDLE'} if is_pivot else {'ANGLE_HANDLE'}

        if pivot is not None:
            self.set_tr_gizmo_pivot_handle(pivot)
        if handle is not None:
            self.set_tr_gizmo_angle_handle(handle)
        self.tr_gizmo_setup_cursor_2d(context)

    def tr_gizmo_set_location_with_transform(
            self, context: bpy.types.Context,
            origin_pivot, origin_head, matched_pivot, matched_head,
            is_pivot=True, axes_lock_mode: str = ""):

        self.tr_gizmo_set_location(context, matched_pivot, matched_head, is_pivot=is_pivot)

        if self.tr_gizmo_mode == 'TRANSFORM':

            from ZenUV.ui.tool.tool_ops import ZuvTransformGizmoAxisLockPreset
            p_axis_lock = ZuvTransformGizmoAxisLockPreset()
            p_axis_lock.setup_by_gizmo_lock(axes_lock_mode)

            op_mod = bpy.ops.uv.zenuv_tool_transform
            if op_mod.poll():
                return op_mod(
                    'INVOKE_DEFAULT',
                    True,
                    origin_pivot=origin_pivot[:2],
                    origin_head=origin_head[:2],

                    matched_pivot=matched_pivot[:2],
                    matched_head=matched_head[:2],

                    is_pivot=is_pivot,

                    match_pos=p_axis_lock.match_pos,
                    match_rotation=p_axis_lock.match_rotation,
                    match_scale=p_axis_lock.match_scale,
                    lock_scale_axis=p_axis_lock.lock_scale_axis,
                    lock_position_axis=p_axis_lock.lock_position_axis,

                    preprocessing_offset=(0, 0)
                )
            else:
                op_cls = bpy.types.Operator.bl_rna_get_subclass_py(op_mod.idname())
                s_reason = op_cls.poll_reason(context)
                if s_reason:
                    raise RuntimeError(s_reason)

    def tr_gizmo_undo_push(self, commit_in_blender=True):
        self.tr_gizmo_undo_list.add()
        p_undo_item = self.tr_gizmo_undo_list[-1]
        p_undo_item.name = str(
            (*self.tr_gizmo_pivot_handle[:], *self.tr_gizmo_angle_handle[:], self.tr_gizmo_is_pivot))
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        ZuvTrimsheetUtils.fix_undo()

        if commit_in_blender:
            bpy.ops.ed.undo_push(message="Zen UV tool handles")

    def tr_gizmo_redo_last(self):
        if self.tr_gizmo_undo_list:
            p_item = self.tr_gizmo_undo_list[-1]
            if p_item.name:
                try:
                    x1, y1, x2, y2, is_pivot = literal_eval(p_item.name)
                    self.tr_gizmo_set_location(
                        bpy.context, (x1, y1), (x2, y2), is_pivot=is_pivot)
                except Exception as e:
                    Log.error("HANDLER UNDO_REDO:", e)

    def tr_gizmo_set_transform_by_matrix(self, context: bpy.types.Context, fn_before_execute: callable, is_line: bool = True):
        if self.tr_gizmo_mode == 'TRANSFORM':
            self.tr_gizmo_active = False

            from ZenUV.ui.tool.tool_ops import ZUV_OP_ToolTransform
            wm = context.window_manager
            # NOTE: We should call only 'operators[-1]',
            #       'operator_properties_last' are filled only in invoke
            if wm.operators:
                op = wm.operators[-1]
                if isinstance(op, ZUV_OP_ToolTransform):

                    if fn_before_execute:
                        fn_before_execute(op, context)

                    op.influence = self.tr_gizmo_influence
                    op.execute(context)

                    self.tr_gizmo_finalize_cursor_by_tool_op_matrix(context, is_line=is_line)

    def tr_gizmo_finalize_cursor_by_tool_op_matrix(self, context: bpy.types.Context, is_line: bool = True):
        if self.tr_gizmo_mode == 'TRANSFORM':

            from ZenUV.ui.tool.tool_ops import ZUV_OP_ToolTransform
            wm = context.window_manager
            # NOTE: We should call only 'operators[-1]',
            #       'operator_properties_last' are filled only in invoke
            if wm.operators:
                op = wm.operators[-1]
                if isinstance(op, ZUV_OP_ToolTransform):
                    mtx_op = op.transform_matrix

                    b_is_fallof_enabled = self.tr_gizmo_is_falloff_enabled

                    # NOTE: Use only through vector copy procedure !!!
                    #       'resized' is not working as copy !!!
                    if not b_is_fallof_enabled or (self.tr_gizmo_is_pivot or is_line):
                        p_cursor_location: Vector = mtx_op @ Vector(op.origin_pivot).resized(3)
                        p_cursor_location.resize_2d()
                        self.set_tr_gizmo_pivot_handle(p_cursor_location)
                        op.matched_pivot = p_cursor_location[:]

                    if b_is_fallof_enabled or (not self.tr_gizmo_is_pivot or is_line):
                        p_cursor_location: Vector = mtx_op @ Vector(op.origin_head).resized(3)
                        p_cursor_location.resize_2d()
                        self.set_tr_gizmo_angle_handle(p_cursor_location)
                        op.matched_head = p_cursor_location[:]

            self.tr_gizmo_setup_cursor_2d(context)


class ZUV_3DVToolProps(bpy.types.PropertyGroup, ZuvToolProps):
    space_type = 'VIEW_3D'

    trim_select_mode: bpy.props.EnumProperty(
        name='Trim Select Mode',
        description='Trim selector is binded to mesh or center of screen',
        items=[
            (
                'MESH', 'Mesh',
                'Trim selector center is the center of the active object active face center',
                'MESH_DATA', 1
            ),
            (
                'SCREEN', 'Screen',
                'Trim selector center is the center of 3D viewport',
                'SCREEN_BACK', 2
            )
        ],
        default='MESH',
        update=ZuvToolProps.update_view,
        options=set()
    )

    mode: bpy.props.EnumProperty(
        name='Tool Mode',
        items=[
            ('MOVE', 'Move', 'Moves UV islands or mesh elements', icon_get('transform-move'), 1),
            ('ROTATE', 'Rotate', 'Rotates UV islands or mesh elements', icon_get('transform-rotate'), 2),
            ('SCALE', 'Scale', 'Scales UV islands or mesh elements', icon_get('transform-scale'), 3),
        ],
        default='MOVE',
        update=ZuvToolProps.update_view,
        options=set()
    )

    texture_preview: bpy.props.BoolProperty(
        name='Texture Preview',
        default=True,
        options=set()
    )

    screen_position_locked: bpy.props.BoolProperty(
        name='Screen Locked',
        description='Screen position scale and pan locked',
        default=False,
        options=set()
    )

    screen_scale: bpy.props.FloatProperty(
        name='Screen Scale',
        description=ZuvLabels.PROP_TRIMSHEET_WIDGET_MOVE_HOTKEYS,
        min=0.1,
        default=1.0,
        options=set()
    )

    screen_pan_x: bpy.props.FloatProperty(
        name='Screen Pan X',
        description=ZuvLabels.PROP_TRIMSHEET_WIDGET_MOVE_HOTKEYS,
        precision=0,
        default=0.0,
        options=set()
    )

    screen_pan_y: bpy.props.FloatProperty(
        name='Screen Pan Y',
        description=ZuvLabels.PROP_TRIMSHEET_WIDGET_MOVE_HOTKEYS,
        precision=0,
        default=0.0,
        options=set()
    )

    screen_pos: bpy.props.FloatVectorProperty(
        name='Screen Pos',
        description="Fixed widget screen position\n* Unlock selector to be able to move by hotkeys",
        precision=0,
        step=100,
        size=2,
        default=(0, 0),
        options=set()
    )

    screen_size: bpy.props.FloatProperty(
        name='Screen Size',
        description="Fixed widget screen size\n* Unlock selector to be able to scale by hotkeys",
        precision=0,
        step=100,
        min=50,
        default=500,
        options=set()
    )

    def is_texture_visible(self):
        return (self.display_trims and self.texture_preview) or self.is_select_trim_enabled()

    def is_cage_visible(self):
        return self.display_trims or self.enable_screen_selector

    def is_screen_selector_position_enabled(self):
        return not self.screen_position_locked and self.trim_select_mode == 'SCREEN'

    def is_select_trim_enabled(self):
        return (self.display_trims and self.select_trim) or self.trim_select_mode == 'SCREEN'

    def get_select_mode(self):
        return self.trim_select_mode

    def get_display_trims_ex(self):
        return (self.trim_select_mode == 'SCREEN') or self.display_trims

    def set_display_trims_ex(self, value):
        if not value:
            if self.trim_select_mode == 'SCREEN':
                self.trim_select_mode = 'MESH'

        self.display_trims = value

    display_trims_ex: bpy.props.BoolProperty(
        name='Display Trims',
        description='Display Trimsheet Trims',
        get=get_display_trims_ex,
        set=set_display_trims_ex,
        update=ZuvToolProps.update_view,
        options={'SKIP_SAVE'}
    )

    def get_select_trim_ex(self):
        return self.trim_select_mode == 'SCREEN'

    def set_select_trim_ex(self, value):
        if value:
            self.trim_select_mode = 'SCREEN'
        else:
            self.trim_select_mode = 'MESH'

    enable_screen_selector: bpy.props.BoolProperty(
        name='Trim Viewport Selector',
        description='Show trim selector in screen viewport mode',
        get=get_select_trim_ex,
        set=set_select_trim_ex,
        update=ZuvToolProps.update_view,
        options={'SKIP_SAVE'}
    )


class ZUV_SceneUIProps(bpy.types.PropertyGroup):

    def on_update_view3d(self, context: bpy.types.Context):
        if hasattr(context, 'area') and context.area is not None:
            context.area.tag_redraw()

    def on_update_all_uvs(self, context: bpy.types.Context):
        update_areas_in_uv(context)

    def on_update_all_3ds(self, context: bpy.types.Context):
        update_areas_in_view3d(context)

    trim_preview_image: bpy.props.PointerProperty(
        name='Trim Preview Image',
        type=bpy.types.Image,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    tool_mode: bpy.props.EnumProperty(
        name='Tool Mode',
        items=[
            ('MOVE', 'Move', 'Moves UV islands or mesh elements', icon_get('transform-move'), 1),
            ('ROTATE', 'Rotate', 'Rotates UV islands or mesh elements', icon_get('transform-rotate'), 2),
            ('SCALE', 'Scale', 'Scales UV islands or mesh elements', icon_get('transform-scale'), 3),
        ],
        default='MOVE',
        update=on_update_view3d,
        options=set()
    )

    tool_settings_expanded: bpy.props.BoolProperty(
        name='Tool Settings',
        description='Expand-collapse tool settings',
        default=False,
        options=set()
    )

    uv_tool: bpy.props.PointerProperty(name='UV Tool', type=ZUV_UVToolProps)

    view3d_tool: bpy.props.PointerProperty(name='View3D Tool', type=ZUV_3DVToolProps)

    draw_mode_UV: bpy.props.EnumProperty(
        name='Draw Mode',
        description='Zen UV draw mode',
        items=[
            ('NONE', 'None', 'All UV draws disabled'),
            ('FINISHED', 'Finished', 'Display finished islands'),
            ('FLIPPED', 'Flipped', 'Display flipped faces'),
            ('EXCLUDED', 'Excluded', 'Display excluded islands'),

            ('OVERLAPPED', 'Overlapped', 'Display overlapped faces'),

            ('SIMILAR_STATIC', 'Similar', ZuvLabels.PROP_ENUM_STACK_DISPLAY_SIMILAR_DESC),
            ('SIMILAR_SELECTED', 'Similar By Selection', ZuvLabels.PROP_ENUM_STACK_DISPLAY_SELECTED_DESC),
            ('STACKED', ZuvLabels.PROP_AST_STACKED_LABEL, ZuvLabels.PROP_AST_STACKED_DESC),
            ('STACKED_MANUAL', 'Manual Stacks', ZuvLabels.PROP_M_STACKED_DESC),

            ('TEXEL_DENSITY', 'Texel Density', 'Display texel density'),

            ('UV_OBJECT', 'UV Object', 'Display UVs in object mode'),

            ('UV_BORDERS', 'UV Borders', 'Display UV borders'),
            ('SEAMS', 'Seams', 'Display edge seams'),

            ('SELF_INTERSECTING', 'Self-Intersecting', 'Display faces that have intersecting edges'),
        ],
        default='NONE',
        update=on_update_all_uvs,
        options={'SKIP_SAVE'}
    )

    draw_mode_3D: bpy.props.EnumProperty(
        name='Draw Mode',
        description='Zen UV draw mode',
        items=[
            ('NONE', 'None', 'All UV draws disabled'),
            ('FINISHED', 'Finished', 'Display finished islands'),
            ('FLIPPED', 'Flipped', 'Display flipped islands'),
            ('STRETCHED', 'Stretched', 'Display stretched islands'),
            ('EXCLUDED', 'Excluded', 'Display excluded islands'),
            ('OVERLAPPED', 'Overlapped', 'Display overlapped faces'),
            ('UV_NO_SYNC', 'UV No Sync', 'Display faces that are selected in UV no sync mode'),

            ('SIMILAR_STATIC', 'Similar', ZuvLabels.PROP_ENUM_STACK_DISPLAY_SIMILAR_DESC),
            ('SIMILAR_SELECTED', 'Similar By Selection', ZuvLabels.PROP_ENUM_STACK_DISPLAY_SELECTED_DESC),
            ('STACKED', ZuvLabels.PROP_AST_STACKED_LABEL, ZuvLabels.PROP_AST_STACKED_DESC),
            ('STACKED_MANUAL', 'Manual Stacks', ZuvLabels.PROP_M_STACKED_DESC),
            ('TAGGED', 'Tagged', 'Display tagged islands'),

            ('TEXEL_DENSITY', 'Texel Density', 'Display texel density'),
            ('UV_BORDERS', 'UV Borders', 'Display UV borders'),
            ('TRIM_COLORS', 'Trim Colors', 'Trim Colors')
        ],
        default='NONE',
        update=on_update_all_3ds,
        options={'SKIP_SAVE'}
    )

    draw_sub_TD_UV: TdProps.td_draw_submode
    draw_sub_TD_3D: TdProps.td_draw_submode

    def get_draw_mode_pair_by_context(self, context: bpy.types.Context):
        b_is_UV = context.space_data.type == 'IMAGE_EDITOR'
        s_space = 'UV' if b_is_UV else '3D'
        attr_name = 'draw_mode_' + s_space
        p_mode = getattr(context.scene.zen_uv.ui, attr_name)
        return (attr_name, p_mode)

    use_draw_overlay_sync: bpy.props.BoolProperty(
        name='Overlay Sync',
        description='Draw is synchronized with overlay on-off setting',
        default=False,
        options=set()
    )

    draw_stretched_modal: bpy.props.BoolProperty(
        name='Stretched Dynamic',
        description='Display stretched in viewport modal operations: dragging etc.',
        default=False,
        options=set()
    )

    uv_points_draw_zoom_ratio: bpy.props.FloatProperty(
        name='Scale Point Ratio',
        description='Scale ratio when point size is changed in UV area',
        min=0.1,
        max=10.0,
        default=1.0,
        options=set()
    )


class ZUV_PT_TrimSnapUV(bpy.types.Panel):
    bl_label = "Trim Snapping"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context: bpy.types.Context):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils

        layout = self.layout

        layout.label(text='Snap To')

        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        layout.active = tool_props.use_trim_snap

        row = layout.row(align=True)
        col1 = row.column(align=True)
        col1.prop(tool_props, 'trim_snap_mode')

        col2 = row.column(align=True)

        snap_items = tool_props.bl_rna.properties["trim_snap_mode"].enum_items
        for item in snap_items:
            r2 = col2.row(align=True)
            r2.separator()
            b_active = True
            s_text = ''
            if item.identifier == 'PIXELS':
                b_active = ZuvTrimsheetUtils.getSpaceDataImage(context) is not None
                if not b_active:
                    s_text = 'No Image'
            elif item.identifier == 'TRIMS':
                b_active = len(ZuvTrimsheetUtils.getTrimsheet(context)) > 1
                if not b_active:
                    s_text = 'Too Few Trims'

            r2.alert = len(s_text) > 0
            r2.label(text=s_text)

        layout.label(text="Snap Pivot")
        row = layout.row(align=True)
        row.alignment = 'LEFT'
        p_grid = row.grid_flow(columns=2, align=True)
        p_grid.prop_enum(tool_props, 'trim_snap_pivot', "tl", text="")
        p_grid.prop_enum(tool_props, 'trim_snap_pivot', "bl", text="")
        p_grid.prop_enum(tool_props, 'trim_snap_pivot', "tr", text="")
        p_grid.prop_enum(tool_props, 'trim_snap_pivot', "br", text="")

        layout.separator()
        layout.prop(tool_props, 'trim_snap_threshold')
