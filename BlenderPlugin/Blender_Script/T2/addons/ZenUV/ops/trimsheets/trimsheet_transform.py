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
import numpy as np
from mathutils import Vector
from ZenUV.ops.transform_sys.transform_utils.transform_uvs import TransformUVS
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.utils.bounding_box import BoundingBox2d, DirectionBboxStr, DirMatrixStr
from . trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.utils.generic import ZenOperatorProperties
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TrConstants
from ZenUV.ico import icon_get

from ZenUV.utils.blender_zen_utils import ZenPolls


class TrimTransformProps:

    message_controlled_ui = 'It is controlled from the addon Panel.'

    # Global Operators (trim transform modes Enum)
    def trim_transform_mode_items(cls, context):
        return [
            ('ALIGN', 'Align', 'Align selected Trims', icon_get("transform-orient"), 0),
            ('CROP', 'Crop', 'Crop selected or all Trims', icon_get("transform-fit"), 1),
            ('ADJUST', 'Adjust', 'Adjust height and width of selected Trims', icon_get("transform-scale"), 2),
            ('DISTRIBUTE', 'Distribute', 'Arrange selected Trims in a row', icon_get("transform-distribute"), 3),
        ]

    @ classmethod
    def get_global_trim_transform_mode(cls) -> bpy.props.EnumProperty:
        return bpy.props.EnumProperty(
                name='Trim Transform',
                description='Transform Types',
                items=cls.trim_transform_mode_items,
                default=1
            )

    def draw_global_mode(self, layout):
        if self.is_panel_controlled:
            layout.label(text=TrimTransformProps.message_controlled_ui)
        col = layout.column()
        col.enabled = not self.is_panel_controlled
        return col

    align_mode_enum_items = [
                ('ACTIVE_TRIM', 'Active Trim', 'Align Trims with Active Trim', 0),
                ('UV_BOUNDS', 'UV Area Bounds', 'Align Trims with UV Area bounds', 1),
                ('EACH_OTHER', 'With each other', 'Align Trims with each other', 2),
            ]

    direction_enum_items = [
                ("br", 'Bottom-Right', '', 0),
                ("bl", 'Bottom-Left', '', 1),
                ("tr", 'Top-Right', '', 2),
                ("tl", 'Top-Left', '', 3),
                ("cen", 'Center', '', 4),
                ("rc", 'Right', '', 5),
                ("lc", 'Left', '', 6),
                ("bc", 'Bottom', '', 7),
                ("tc", 'Top', '', 8),
                ("cen_h", 'Center Horizontal', '', 9),
                ("cen_v", 'Center Vertical', '', 10)
            ]

    is_panel_controlled = bpy.props.BoolProperty(
        name='Use Settings from the UI Panel',
        description='If set to On, the operator will use the values of all properties from the Panel. Leave it Off if you are assigning the operator to a hotkey',
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'})

    align_mode = bpy.props.EnumProperty(
        name='Mode',
        description='Align Mode',
        items=align_mode_enum_items,
        default=2
    )

    @classmethod
    def get_direction(cls) -> bpy.props.EnumProperty:
        return bpy.props.EnumProperty(
                name="UC Direction",
                description='The UC Direction used in Universal Control (UC) to control the operator from the Panel. If you are assigning a hotkey, simply disable this option',
                items=cls.direction_enum_items,
                default=10,
                options={'HIDDEN'}
            )

    # Crop Props
    crop_enum_items = [
            ('SEL_TRIMS', 'Selected Trims', 'Crop Selected Trims', 0),
            ('ALL_TRIMS', 'All Trims', 'Crop all Trims', 1),
        ]
    crop_mode = bpy.props.EnumProperty(
        name='Mode',
        description='Crop Mode',
        items=crop_enum_items,
        default=1
    )

    # Adjust Props
    adjust_mode_enum_items = [
            ('ACTIVE_TRIM', 'Active Trim', 'Adjust Trims size with Active Trim', 0),
            ('UV_BOUNDS', 'UV Area Bounds', 'Adjust Trims size with UV Area bounds', 1),
            ('EACH_OTHER', 'With each other', 'Adjust Trims size with each other', 2),
        ]
    adjust_mode = bpy.props.EnumProperty(
        name='Mode',
        description='Adjust Mode',
        items=adjust_mode_enum_items,
        default=2
    )
    adjust_size_enum_items = [
                ("MAX", 'Maximum', 'Get the maximum size from the selected Trims', 0),
                ("MIN", 'Minimum', 'Get the minimum size from the selected Trims', 1)
            ]
    adjust_size = bpy.props.EnumProperty(
            name="Inherited Value",
            description='Which value of the selected Trims to follow. Maximum or minimum',
            items=adjust_size_enum_items,
            default=0
        )
    adjust_direction_enum_items = [
                ("WIDTH", 'Width', 'Change the Trim width', 0),
                ("HEIGHT", 'Height', 'Change the Trim height', 1)
            ]
    adjust_direction = bpy.props.EnumProperty(
            name="Adjust Direction",
            items=adjust_direction_enum_items,
            description='How to change the size of the Trim. Height or width',
            default=0
        )

    # Distribute Props
    distr_direction_enum_items = [
                ("AUTO", 'Automatic', '', 0),
                ("HORIZONTAL", 'Horizontal', '', 1),
                ("VERTICAL", 'Vertical', '', 2),
            ]
    distr_direction = bpy.props.EnumProperty(
            name="Island Pivot",
            items=distr_direction_enum_items,
            default=0
        )
    distr_and_align = bpy.props.BoolProperty(name='Align', description='Perform Trims Aligning', default=True)
    distr_mode_enum_items = [
            ('ACTIVE_TRIM', 'Active Trim', 'Align Trims with Active Trim', 0),
            ('UV_BOUNDS', 'UV Area Bounds', 'Align Trims with UV Area bounds', 1),
            ('EACH_OTHER', 'With each other', 'Align Trims with each other', 2),
        ]
    distr_mode = bpy.props.EnumProperty(
        name='Mode',
        description='Distribute Mode',
        items=distr_mode_enum_items,
        default=2
    )
    distr_reverse_direction_in_a_trim_mode = bpy.props.BoolProperty(
        name='Reverse Direction',
        description='If the Active Trim mode is set, the direction is reversed. In this case, the direction button shows the direction in which the Trims will be placed instead of the starting point',
        default=True)


class AlignProperties(ZenOperatorProperties):

    align_mode: str = 'EACH_OTHER'
    align_direction: str = 'cen'
    is_panel_controlled: bool = False
    opposite: bool = False


class TrimAlignFactory(AlignProperties):

    def __init__(self, PROPS: bpy.types.OperatorProperties) -> None:
        super().__post_init__(PROPS)

    def align(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is None:
            self.report({'INFO'}, "There are no TrimSheet Data.")
            return {'CANCELLED'}

        p_trimsheet = p_data.trimsheet

        p_selected_indices = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)

        if not len(p_selected_indices):
            self.report({'INFO'}, "There are no selected Trims.")
            return {'CANCELLED'}

        if self.align_mode == 'EACH_OTHER':
            points = [p_trimsheet[i].left_bottom for i in p_selected_indices]
            points.extend([p_trimsheet[i].top_right for i in p_selected_indices])
            master_bbox = BoundingBox2d(points=points).get_as_dict()

        elif self.align_mode == 'ACTIVE_TRIM':
            p_trim_pair = ZuvTrimsheetUtils.getActiveTrimPair(context)
            if p_trim_pair is None:
                self.report({'INFO'}, "There are no Active Trim.")
                return {'FINISHED'}
            idx, a_trim = p_trim_pair
            p_selected_indices = np.delete(p_selected_indices, np.where(p_selected_indices == idx))
            master_bbox = BoundingBox2d(points=(a_trim.left_bottom, a_trim.top_right)).get_as_dict()

        elif self.align_mode == 'UV_BOUNDS':
            master_bbox = UV_AREA_BBOX.get_as_dict()

        else:
            raise RuntimeError('ZUV_OT_TrimAlignTrim.align_mode not in {"EACH_OTHER", "ACTIVE_TRIM", "UV_BOUNDS"}')

        if self.align_direction in ('cen_h', 'cen_v'):
            self.align_direction = TrConstants.opposite_direction[self.align_direction]
            self.opposite = True

        for i in p_selected_indices:
            p_trim = p_trimsheet[i]
            p_trim_uvs = (p_trim.left_bottom, p_trim.top_right)
            p_trim_bbox = BoundingBox2d(points=p_trim_uvs).get_as_dict()

            offset = TransformLoops.mute_axis(
                master_bbox[self.align_direction] - p_trim_bbox[self.align_direction],
                self.align_direction, opposite=self.opposite
            )

            moved = TransformUVS.move_uvs(p_trim_uvs, offset)
            p_trim.rect = BoundingBox2d(points=moved).rect

        p_data.trimsheet_mark_geometry_update()

        return {'FINISHED'}


class ZUV_OT_SetActiveTrimMouseover(bpy.types.Operator):
    bl_idname = "uv.zenuv_set_active_trim_mouseover"
    bl_label = "Set Active Trim"
    bl_description = "Set active trim using mouse position"
    bl_options = {'REGISTER', 'UNDO'}

    def __del__(self):
        self.cancel(bpy.context)

    x: bpy.props.IntProperty(
        default=0,
        options={'HIDDEN', 'SKIP_SAVE'}

    )
    y: bpy.props.IntProperty(
        default=0,
        options={'HIDDEN', 'SKIP_SAVE'}
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

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        if event.type in {'RIGHTMOUSE', 'ESC'} or bpy.app.driver_namespace.get(self.bl_idname, Ellipsis) != ZenPolls.SESSION_UUID:
            self.cancel(context)
            return {'CANCELLED'}

        elif event.type in {'LEFTMOUSE', 'RET'}:
            self.x = event.mouse_region_x
            self.y = event.mouse_region_y
            return self.execute(context)

        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data:
            context.window.cursor_modal_set('EYEDROPPER')
            p_trimsheet = p_data.trimsheet

            idx_trim, _ = self.get_trim_index_by_mouse(context, p_trimsheet, event.mouse_region_x, event.mouse_region_y)

            if idx_trim != -1:
                s_trim_name = p_trimsheet[idx_trim].name
                s_trim = "Trim " if 'trim' not in s_trim_name.lower() else ""  # NOTE: prevent Trim Trim duplication
                context.workspace.status_text_set(f"Set Active{s_trim}: {s_trim_name} - Enter/LMB: Confirm, Esc/RMB: Cancel.")
            else:
                context.workspace.status_text_set("No Trim Detected - Esc/RMB: Cancel.")

            return {'PASS_THROUGH'}

        return {'CANCELLED'}

    def get_trim_index_by_mouse(self, context: bpy.types.Context, p_trimsheet, region_x, region_y):
        l_uv_co = Vector(context.region.view2d.region_to_view(region_x, region_y))

        idx_trim = -1

        for index, trim in enumerate(p_trimsheet):
            if (trim.left_bottom.x <= l_uv_co.x <= trim.top_right.x) and (trim.left_bottom.y <= l_uv_co.y <= trim.top_right.y):
                idx_trim = index
                break

        return idx_trim, l_uv_co

    def execute(self, context):
        self.cancel(context)

        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is None:
            self.report({'INFO'}, "There are no TrimSheet Data.")
            return {'CANCELLED'}

        p_trimsheet = p_data.trimsheet

        if len(p_data.trimsheet) == 0:
            self.report({'WARNING'}, "There are no Trims.")
            return {'CANCELLED'}

        idx_trim, l_uv_co = self.get_trim_index_by_mouse(context, p_trimsheet, self.x, self.y)
        if idx_trim != -1:
            return bpy.ops.wm.zuv_trim_set_index(trimsheet_index=idx_trim)

        self.report({'INFO'}, f"Can not detect trim in UV coordinates: {l_uv_co.x:.4f}, {l_uv_co.y:.4f}")
        return {'CANCELLED'}

    def cancel(self, context: bpy.types.Context):
        # NOTE: check is operator is running
        if self.bl_idname in bpy.app.driver_namespace:
            del bpy.app.driver_namespace[self.bl_idname]

            if context.window:
                context.window.cursor_modal_restore()
            if context.workspace:
                context.workspace.status_text_set(None)


class ZUV_OT_TrimAlignTrim(bpy.types.Operator):
    bl_idname = "uv.zuv_align_trim"
    bl_label = "Align Trims"
    bl_description = "Align selected trims"
    bl_options = {'REGISTER', 'UNDO'}

    def set_align_mode_value(self, value):
        self['align_mode'] = value

    def get_align_mode_value(self):
        if self.is_panel_controlled:
            return next(
                (i for i, item in enumerate(TrimTransformProps.align_mode_enum_items)
                    if item[0] == bpy.context.scene.zen_uv.trimsheet_transform.align_mode), 2)
        else:
            return self.get('align_mode', 2)

    def get_align_mode_items(self, context):
        return TrimTransformProps.align_mode_enum_items

    def get_direction_items(self, context):
        return TrimTransformProps.direction_enum_items

    align_mode: bpy.props.EnumProperty(
            name='Mode',
            description='Align Mode',
            items=get_align_mode_items,
            get=get_align_mode_value,
            set=set_align_mode_value,
            default=2
        )

    align_direction: bpy.props.EnumProperty(
        name='Align Direction',
        items=get_direction_items,
        description='Specifies the side of the bounding box to which the Trim should be aligned.',
        default=10,
    )

    is_panel_controlled: TrimTransformProps.is_panel_controlled

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            s_direction = bpy.types.UILayout.enum_item_name(properties, "align_direction", properties.align_direction)
            if s_direction in {'Center', 'Center Horizontal', 'Center Vertical'}:
                s_insert = ''
            else:
                s_insert = ' side' if '-' not in s_direction else ' corner'

            s_ends = 'selection Bounding Box' if properties.align_mode == 'EACH_OTHER' else bpy.types.UILayout.enum_item_name(properties, "align_mode", properties.align_mode)
            return cls.bl_label + " to the " + s_direction + s_insert + " of the " + s_ends
        else:
            return cls.bl_description

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        return p_data is not None

    def draw(self, context: bpy.types.Context) -> None:
        layout = TrimTransformProps.draw_global_mode(self, self.layout)
        self.draw_op_props(layout)

    def draw_op_props(self, layout):
        layout.prop(self, 'align_mode')
        layout.prop(self, 'align_direction')

    def execute(self, context: bpy.types.Context):
        AlignFactory = TrimAlignFactory(self.properties)
        result = AlignFactory.align(context)
        if result == {'CANCELLED'}:
            self.report(AlignFactory.report_type, AlignFactory.get_report_message())
            return result

        ZuvTrimsheetUtils.fix_undo()
        ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

        return result


class ZUV_OT_TrimCropTrim(bpy.types.Operator):
    bl_idname = "uv.zuv_crop_trim"
    bl_label = "Crop Trims"
    bl_description = "Crop Trims outside the UV Area."
    bl_options = {'REGISTER', 'UNDO'}

    def get_crop_mode_value(self):
        if self.is_panel_controlled:
            return next(
                (i for i, item in enumerate(TrimTransformProps.crop_enum_items)
                    if item[0] == bpy.context.scene.zen_uv.trimsheet_transform.crop_mode), 1)
        else:
            return self.get('crop_mode', 1)

    def set_crop_mode_value(self, value):
        self['crop_mode'] = value

    crop_mode: bpy.props.EnumProperty(
        name='Mode',
        description='Crop Mode',
        items=TrimTransformProps.crop_enum_items,
        get=get_crop_mode_value,
        set=set_crop_mode_value,
        default=1
    )

    is_panel_controlled: TrimTransformProps.is_panel_controlled

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            return cls.bl_label + ": " + bpy.types.UILayout.enum_item_name(properties, "crop_mode", properties.crop_mode)
        else:
            return cls.bl_description

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        return p_data is not None

    def draw(self, context: bpy.types.Context) -> None:
        layout = TrimTransformProps.draw_global_mode(self, self.layout)
        self.draw_op_props(layout)

    def draw_op_props(self, layout):
        layout.prop(self, 'crop_mode', expand=True)

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is None:
            self.report({'INFO'}, "There are no TrimSheet Data.")
            return {'CANCELLED'}

        excluded = []
        p_trimsheet = p_data.trimsheet

        if self.crop_mode == 'SEL_TRIMS':
            p_selected_indices = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)
            if not len(p_selected_indices):
                self.report({'INFO'}, "There are no selected Trims.")
                return {'FINISHED'}
            for idx in p_selected_indices:
                if self.is_trim_intersect_uv_area(p_trimsheet[idx]) is False:
                    excluded.append(p_trimsheet[idx].name)
                    continue
                p_trimsheet[idx].rect = np.clip(np.array(p_trimsheet[idx].rect), 0.0, 1.0)

        elif self.crop_mode == 'ALL_TRIMS':
            for trim in p_trimsheet:
                if self.is_trim_intersect_uv_area(trim) is False:
                    excluded.append(trim.name)
                    continue
                trim.rect = np.clip(np.array(trim.rect), 0.0, 1.0)

        else:
            self.report({'WARNING'}, "The crop mode is incorrect.")
            return {'CANCELLED'}

        p_data.trimsheet_mark_geometry_update()
        ZuvTrimsheetUtils.fix_undo()
        ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

        if len(excluded):
            self.report({'WARNING'}, "Some trims were excluded from processing.")
            print('\nTrims are excluded from cropping:\n' + ''.join(['\t' + n + "\n" for n in excluded]))

        return {'FINISHED'}

    def is_trim_intersect_uv_area(self, trim):
        return not (min(trim.top_right) <= 0.0 or max(trim.left_bottom) >= 1.0)


class ZUV_OT_TrimAdjustSizeTrim(bpy.types.Operator):
    bl_idname = "uv.zuv_adjust_size_trim"
    bl_label = "Adjust Size Trims"
    bl_description = "Adjust the size of the selected Trims"
    bl_options = {'REGISTER', 'UNDO'}

    def set_adjust_mode_value(self, value):
        self['adjust_mode'] = value

    def get_adjust_mode_value(self):
        if self.is_panel_controlled:
            return next(
                (i for i, item in enumerate(TrimTransformProps.adjust_mode_enum_items)
                    if item[0] == bpy.context.scene.zen_uv.trimsheet_transform.adjust_mode), 2)
        else:
            return self.get('adjust_mode', 2)

    adjust_mode: bpy.props.EnumProperty(
        name='Mode',
        description='Adjust Mode',
        items=TrimTransformProps.adjust_mode_enum_items,
        get=get_adjust_mode_value,
        set=set_adjust_mode_value,
        default=2
    )

    def set_adjust_size_value(self, value):
        self['adjust_size'] = value

    def get_adjust_size_value(self):
        if self.is_panel_controlled:
            if self.uc_controls in ['bc', 'lc']:
                return 1  # "MIN"
            elif self.uc_controls in ['tl', 'br']:
                return 0  # "MAX"
            else:
                return 0  # "MAX"
        else:
            return self.get('adjust_size', 0)

    adjust_size: bpy.props.EnumProperty(
            name="Inherited Value",
            items=TrimTransformProps.adjust_size_enum_items,
            get=get_adjust_size_value,
            set=set_adjust_size_value,
            default=0
        )

    def set_adjust_direction_value(self, value):
        self['adjust_direction'] = value

    def get_adjust_direction_value(self):
        if self.is_panel_controlled:
            if self.uc_controls in ['tl', 'lc']:
                return 1  # "HEIGHT"
            elif self.uc_controls in ['bc', 'br']:
                return 0  # "WIDTH"
            else:
                return 0  # "WIDTH"
        else:
            return self.get('adjust_direction', 0)

    adjust_direction: bpy.props.EnumProperty(
            name="Adjust Direction",
            items=TrimTransformProps.adjust_direction_enum_items,
            get=get_adjust_direction_value,
            set=set_adjust_direction_value,
            default=0
        )

    is_panel_controlled: TrimTransformProps.is_panel_controlled
    uc_controls: TrimTransformProps.get_direction()

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            s_dir = bpy.types.UILayout.enum_item_name(properties, "adjust_direction", properties.adjust_direction)
            s_match = bpy.types.UILayout.enum_item_name(properties, "adjust_mode", properties.adjust_mode)
            s_size = bpy.types.UILayout.enum_item_name(properties, "adjust_size", properties.adjust_size) + " size"
            return f"Adjust the {s_dir.lower()} of the Trim to match the {s_match.lower()} by its {s_size.lower()}"
        else:
            return cls.bl_description

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        return p_data is not None

    def draw(self, context: bpy.types.Context) -> None:
        layout = TrimTransformProps.draw_global_mode(self, self.layout)
        self.draw_op_props(layout)

    def draw_op_props(self, layout):
        layout.prop(self, 'adjust_mode')
        row = layout.row()
        row.enabled = self.adjust_mode == 'EACH_OTHER'
        row.prop(self, 'adjust_size', expand=True)
        row = layout.row()
        row.prop(self, 'adjust_direction', expand=True)

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is None:
            self.report({'INFO'}, "There are no TrimSheet Data.")
            return {'CANCELLED'}

        p_trimsheet = p_data.trimsheet

        p_selected_indices = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)
        if not len(p_selected_indices):
            self.report({'INFO'}, "There are no selected Trims.")
            return {'CANCELLED'}

        if self.adjust_mode == 'EACH_OTHER':
            sizes = [[p_trimsheet[i].width, p_trimsheet[i].height] for i in p_selected_indices]
            width = [s[0] for s in sizes]
            height = [s[1] for s in sizes]
            size = {
                'MAX':
                    {'WIDTH': max(width), 'HEIGHT': max(height)},
                'MIN':
                    {'WIDTH': min(width), 'HEIGHT': min(height)}
                }[self.adjust_size][self.adjust_direction]

        elif self.adjust_mode == 'ACTIVE_TRIM':
            p_trim_pair = ZuvTrimsheetUtils.getActiveTrimPair(context)
            if p_trim_pair is None:
                self.report({'INFO'}, "There are no Active Trim.")
                return {'FINISHED'}
            idx, a_trim = p_trim_pair
            p_selected_indices = np.delete(p_selected_indices, np.where(p_selected_indices == idx))
            size = {'WIDTH': a_trim.width, 'HEIGHT': a_trim.height}[self.adjust_direction]
        elif self.adjust_mode == 'UV_BOUNDS':
            size = 1.0

        # Set sizes
        set_s = {'WIDTH': self.set_size_h, 'HEIGHT': self.set_size_v}
        for i in p_selected_indices:
            set_s[self.adjust_direction](p_trimsheet[i], size)

        p_data.trimsheet_mark_geometry_update()
        ZuvTrimsheetUtils.fix_undo()
        ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

        return {'FINISHED'}

    def set_size_v(self, trim, size: float) -> None:
        trim.height = size

    def set_size_h(self, trim, size: float) -> None:
        trim.width = size


class ZUV_OT_TrimDistributeTrim(bpy.types.Operator):
    bl_idname = "uv.zuv_distribute_trim"
    bl_label = "Distribute Trims"
    bl_description = "Distribute selected trims"
    bl_options = {'REGISTER', 'UNDO'}

    start_position_enum_items = [
            ('TOP_LEFT', 'Top-Left', 'Start from the top or left, depending on the direction of distribution', 0),
            ('BOTTOM_RIGHT', 'Bottom-Right', 'Start from the bottom or right, depending on the direction of distribution', 1)
        ]

    def get_start_pos_value(self):
        if self.is_panel_controlled:
            if self.uc_controls in ('tc', 'lc', 'cen'):
                return 0
            else:
                return 1
        else:
            return self.get('start_position', 0)

    def set_start_pos_value(self, value):
        self['start_position'] = value

    def get_distr_mode_value(self):
        if self.is_panel_controlled:
            return next(
                (i for i, item in enumerate(TrimTransformProps.distr_mode_enum_items)
                    if item[0] == bpy.context.scene.zen_uv.trimsheet_transform.distr_mode), 0)
        else:
            return self.get('distr_mode', 0)

    def set_distr_mode_value(self, value):
        self['distr_mode'] = value

    distr_mode: bpy.props.EnumProperty(
        name='Mode',
        description='Distribute Mode',
        items=TrimTransformProps.distr_mode_enum_items,
        get=get_distr_mode_value,
        set=set_distr_mode_value,
        default=0
    )

    def set_distr_direction_value(self, value):
        self['distr_direction'] = value

    def get_distr_direction_value(self):
        if self.is_panel_controlled:
            if self.uc_controls == 'cen':
                return 0  # "AUTO"
            elif self.uc_controls in ('lc', 'rc'):
                return 1  # "HORIZONTAL"
            elif self.uc_controls in ('tc', 'bc'):
                return 2  # "VERTICAL"
            else:
                return 0
        else:
            return self.get('distr_direction', 0)

    def get_align_state(self):
        if self.is_panel_controlled:
            return bpy.context.scene.zen_uv.trimsheet_transform.distr_and_align
        else:
            return self.get('align', True)

    def set_align_state(self, value):
        self['align'] = value

    def get_distr_reverse(self):
        if self.is_panel_controlled:
            return bpy.context.scene.zen_uv.trimsheet_transform.distr_reverse_direction_in_a_trim_mode
        else:
            return self.get('reverse_direction_in_a_trim_mode', True)

    def set_distr_reverse(self, value):
        self['reverse_direction_in_a_trim_mode'] = value

    def get_margin_value(self):
        if self.is_panel_controlled:
            return 0.0
        else:
            return self.get('margin', 0.0)

    def set_margin_value(self, value):
        self['margin'] = value

    start_position: bpy.props.EnumProperty(
        name='To begin with:',
        description='The position from which the distribution starts. If the division is performed vertically, the position can be either the top or the bottom. If it is horizontal, the position is either left or right',
        items=start_position_enum_items,
        get=get_start_pos_value,
        set=set_start_pos_value,
        default=0)

    distr_direction: bpy.props.EnumProperty(
            name="Direction of distribution",
            description='The direction in which the distribution will be performed',
            items=TrimTransformProps.distr_direction_enum_items,
            get=get_distr_direction_value,
            set=set_distr_direction_value,
            default=0)

    align: bpy.props.BoolProperty(
        name='Align',
        description='Perform Trims Aligning',
        get=get_align_state,
        set=set_align_state,
        default=True)

    margin: bpy.props.FloatProperty(
        name='Margin',
        description='Sets the distance between Trims. The value 0.0 is considered automatic. If you are not sure what distance you need, just leave the value equal to 0.0',
        min=0.0,
        default=0.0,
        precision=3,
        get=get_margin_value,
        set=set_margin_value
    )
    reverse_direction_in_a_trim_mode: bpy.props.BoolProperty(
        name='Reverse Direction',
        description='If the Active Trim mode is set, the direction is reversed. In this case, the direction button shows the direction in which the Trims will be placed instead of the starting point.',
        default=True,
        get=get_distr_reverse,
        set=set_distr_reverse,
        )

    is_panel_controlled: TrimTransformProps.is_panel_controlled
    uc_controls: TrimTransformProps.get_direction()

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            s_dir_mode = bpy.types.UILayout.enum_item_name(properties, "distr_direction", properties.distr_direction)
            s_mode = bpy.types.UILayout.enum_item_name(properties, "distr_mode", properties.distr_mode)
            s_mode = 'each other' if s_mode == 'With each other' else s_mode
            s_start_pos = bpy.types.UILayout.enum_item_name(properties, "start_position", properties.start_position)
            s_align = ' and perform aligning' if context.scene.zen_uv.trimsheet_transform.distr_and_align is True else ''
            if s_dir_mode == 'Vertical' and s_start_pos == 'Top-Left':
                s_start_pos = 'top'
            elif s_dir_mode == 'Horizontal' and s_start_pos == 'Top-Left':
                s_start_pos = 'left'
            elif s_dir_mode == 'Vertical' and s_start_pos == 'Bottom-Right':
                s_start_pos = 'bottom'
            elif s_dir_mode == 'Horizontal' and s_start_pos == 'Bottom-Right':
                s_start_pos = 'right'
            else:
                s_dir_mode = 'top or left'
            return f"Arrange Trims to {s_mode.lower()} in a {s_dir_mode.lower()} row starting from {s_start_pos.lower()}{s_align}"
        else:
            return cls.bl_description

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        return p_data is not None

    def draw(self, context: bpy.types.Context) -> None:
        layout = TrimTransformProps.draw_global_mode(self, self.layout)
        self.draw_op_props(layout)

    def draw_op_props(self, layout) -> None:
        layout.prop(self, 'distr_mode')
        row = layout.row(align=True)
        row.prop(self, 'start_position')
        if self.distr_mode == 'ACTIVE_TRIM':
            row.prop(self, 'reverse_direction_in_a_trim_mode', icon_only=True, icon='ARROW_LEFTRIGHT')
        row = layout.row()
        row.prop(self, 'distr_direction', expand=True)
        layout.prop(self, 'margin')
        col = layout.column()
        col.label(text='Postprocess:')
        box = col.box()
        box.prop(self, 'align')

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is None:
            self.report({'INFO'}, "There are no TrimSheet Data.")
            return {'CANCELLED'}

        p_trimsheet = p_data.trimsheet

        p_selected_indices = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)

        if not len(p_selected_indices):
            self.report({'INFO'}, "There are no selected Trims.")
            return {'CANCELLED'}

        storage = {i: BoundingBox2d(points=([p_trimsheet[i].left_bottom, p_trimsheet[i].top_right])) for i in p_selected_indices}
        alt_base_point = Vector((0.0, 0.0))
        use_alt_offset = False
        direction = self.distr_direction
        if self.distr_direction == 'AUTO':
            t_bbox = BoundingBox2d(points=[p_trimsheet[i].left_bottom for i in p_selected_indices])
            if t_bbox.is_vertical is True:
                direction = 'VERTICAL'
            else:
                direction = 'HORIZONTAL'

        if self.start_position == 'BOTTOM_RIGHT':
            dd_v = 'bc' if self.is_reverse_in_active_not_allowed() else 'tc'
            dd_h = 'rc' if self.is_reverse_in_active_not_allowed() else 'lc'
            sort_rev = True if self.is_reverse_in_active_not_allowed() else False
            direction_mult = -1
        else:
            dd_v = 'tc' if self.is_reverse_in_active_not_allowed() else 'bc'
            dd_h = 'lc' if self.is_reverse_in_active_not_allowed() else 'rc'
            sort_rev = False if self.is_reverse_in_active_not_allowed() else True
            direction_mult = 1

        if direction == 'HORIZONTAL':
            align_direction = dd_h
            sorted_trims = self.sort_trims_horizontal(storage, align_direction, sort_rev)

        elif direction == 'VERTICAL':
            align_direction = dd_v
            sorted_trims = self.sort_trims_vertical(storage, align_direction, sort_rev)
            direction_mult *= -1

        if self.distr_mode == 'EACH_OTHER':
            base_point = storage[sorted_trims[0]].get_as_dict()[align_direction]

        elif self.distr_mode == 'UV_BOUNDS':
            base_point = UV_AREA_BBOX.get_as_dict()[align_direction]

        elif self.distr_mode == 'ACTIVE_TRIM':
            p_trim_pair = ZuvTrimsheetUtils.getActiveTrimPair(context)
            if p_trim_pair is None:
                self.report({'INFO'}, "There are no Active Trim.")
                return {'FINISHED'}
            idx, a_trim = p_trim_pair
            base_point = BoundingBox2d(points=(a_trim.left_bottom, a_trim.top_right)).get_as_dict()[align_direction]

            elm_idx = next((index for index, i in enumerate(sorted_trims) if i == idx), None)

            if elm_idx is not None:
                sorted_trims.insert(0, sorted_trims.pop(elm_idx))
            else:
                _reversed_dir = DirectionBboxStr.reversed_direction(align_direction)
                base_point = BoundingBox2d(points=(a_trim.left_bottom, a_trim.top_right)).get_as_dict()[_reversed_dir]

                if self.align:
                    use_alt_offset = True
                    alt_base_point = TransformLoops.mute_axis(
                        base_point, DirectionBboxStr.perpendicular_direction(align_direction))

        new_base = DirectionBboxStr.reversed_direction(align_direction)
        margin = Vector.Fill(2, self.margin * direction_mult)

        if self.distr_mode == 'UV_BOUNDS' and self.margin == 0.0:
            if direction == 'HORIZONTAL':
                total_size = sum([bb.len_x for bb in storage.values()])
            else:
                total_size = sum([bb.len_y for bb in storage.values()])

            margin = Vector.Fill(2, (1.0 - total_size) / (len(storage) - 1))
            margin *= direction_mult * -1
        else:
            margin = Vector.Fill(2, self.margin * direction_mult)

        for num, i in enumerate(sorted_trims):
            p_trim = p_trimsheet[i]
            p_bbox = storage[i]
            p_mrg = margin if num > 0 else Vector((0.0, 0.0))

            offset = TransformLoops.mute_axis(
                p_mrg + base_point - p_bbox.get_as_dict()[align_direction],
                align_direction)

            if use_alt_offset is True:
                alt_offset = TransformLoops.mute_axis(alt_base_point - p_bbox.get_as_dict()[align_direction], DirectionBboxStr.perpendicular_direction(align_direction))
                offset = offset + alt_offset

            moved = TransformUVS.move_uvs((p_bbox.bot_left, p_bbox.top_right), offset)

            n_bbox = BoundingBox2d(points=moved)
            p_trim.rect = n_bbox.rect

            base_point = n_bbox.get_as_dict()[new_base]

        # Aligning Phase
        if self.align:
            AF = TrimAlignFactory(AlignProperties)
            AF.align_mode = self.distr_mode
            if direction == 'VERTICAL':
                AF.align_direction = 'cen_v'
            else:
                AF.align_direction = 'cen_h'
            result = AF.align(context)
            if result == {'CANCELLED'}:
                self.report(AF.report_type, AF.report)
                return {'CANCELLED'}

        p_data.trimsheet_mark_geometry_update()
        ZuvTrimsheetUtils.fix_undo()
        ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

        return {'FINISHED'}

    def is_reverse_in_active_not_allowed(self):
        if self.distr_mode == 'ACTIVE_TRIM':
            return not self.reverse_direction_in_a_trim_mode or self.distr_direction == 'AUTO'
        return False

    def sort_trims_horizontal(self, storage, align_direction, sort_rev):

        min_value = min([i.get_as_dict()[align_direction].x for i in storage.values()])
        return [k for k, v in sorted(storage.items(), key=lambda item: item[1].get_as_dict()[align_direction].x + min_value, reverse=sort_rev)]

    def sort_trims_vertical(self, storage, align_direction, sort_rev):
        return [k for k, v in sorted(storage.items(), key=lambda item: item[1].get_as_dict()[align_direction].y, reverse=not sort_rev)]


class ZuvTrimsheetTransformProps(bpy.types.PropertyGroup):

    trim_transform_mode: TrimTransformProps.get_global_trim_transform_mode()
    align_mode: TrimTransformProps.align_mode
    crop_mode: TrimTransformProps.crop_mode
    adjust_mode: TrimTransformProps.adjust_mode
    adjust_size: TrimTransformProps.adjust_size
    distr_mode: TrimTransformProps.distr_mode
    distr_and_align: TrimTransformProps.distr_and_align
    distr_reverse_direction_in_a_trim_mode: TrimTransformProps.distr_reverse_direction_in_a_trim_mode
    # panel_extend_mode: bpy.props.BoolProperty(
    #     name='Extend Trim Transform Panel',
    #     description='Show extended Trim Transform Panel',
    #     default=False
    # )


class UcOperator:

    def __init__(self, operator: bpy.types.Operator, s_props: list = []) -> None:
        self.op = operator
        self.uc_controls = 'cen'
        self.s_props = s_props
        self.s_props.append('uc_controls')


class UcEmpty:

    def __init__(self, prop, position_name) -> None:
        idxs = next((i, row.index(position_name)) for i, row in enumerate(DirMatrixStr.matrix) if position_name in row)
        self.icon_value = icon_get(TrimsUnifiedControl.icons_mtx[idxs[0]][idxs[1]])

    def draw(self, layout):
        empty = layout.row(align=True)
        empty.enabled = False
        empty.alignment = 'LEFT'
        empty.label(icon_value=self.icon_value)


class UcUnit:

    def __init__(self, prop, operator: UcOperator) -> None:
        self.prop = prop
        self.operator = operator
        idxs = next((i, row.index(self.operator.uc_controls)) for i, row in enumerate(DirMatrixStr.matrix) if self.operator.uc_controls in row)
        self.icon_value = icon_get(TrimsUnifiedControl.icons_mtx[idxs[0]][idxs[1]])

    def draw(self, layout):
        btn = layout.row(align=True)
        btn.alignment = 'LEFT'
        op = btn.operator(
            self.operator.op,
            icon_value=self.icon_value,
            text='')  # type: bpy.types.Operator
        op.is_panel_controlled = True

        for prp in self.operator.s_props:
            if hasattr(op, prp):
                setattr(op, prp, self.operator.uc_controls)


class TrimsUnifiedControl:

    enabler_mtx = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ]
    icons_mtx = [
        ["tr_control_tl", "tr_control_tc", "tr_control_tr"],
        ["tr_control_lc", "tr_control_cen", "tr_control_rc"],
        ["tr_control_bl", "tr_control_bc", "tr_control_br"],
    ]
    approved_modes = ("DISTRIBUTE", "ADJUST", "CROP", "ALIGN")

    @classmethod
    def poll(cls, props):
        return props.trim_transform_mode in cls.approved_modes

    @classmethod
    def draw(cls, props, layout, operator: UcOperator):
        if cls.poll(props):
            uc_col = layout.column(align=True)
            uc_grid = list()
            for row in [0, 1, 2]:
                uc_grid.append(uc_col.row(align=True))

            cls.draw_uc(props, uc_grid, operator)

    @classmethod
    def draw_uc(cls, props, layouts: list, operator: UcOperator):
        for layout, idx_row in zip(layouts, [0, 1, 2]):
            layout.alignment = 'LEFT'
            for idx in [0, 1, 2]:
                operator.uc_controls = DirMatrixStr.matrix[idx_row][idx]
                op = UcUnit(props, operator) if cls.enabler_mtx[idx_row][idx] == 1 else UcEmpty(props, operator.uc_controls)
                op.draw(layout)


def draw_trims_transform_ui_tools(context: bpy.types.Context, layout):
    ''' @Draw Trim Transform UI Tools '''
    main_col = layout.column(align=True)
    prp = context.scene.zen_uv.trimsheet_transform
    if context.object.mode == 'EDIT':
        row = main_col.row()
        row.alignment = 'RIGHT'
        row.label(text='Available only in Object mode')
    else:
        grid = main_col.grid_flow(align=True, columns=2)
        grid.prop(prp, 'trim_transform_mode', expand=True)
        main_col.separator()
        m_row = main_col.row()
        uc_col = m_row.column(align=True)
        prp_col = m_row.column(align=True)
        if prp.trim_transform_mode == 'ADJUST':
            UC = TrimsUnifiedControl
            UC.enabler_mtx = (
                [1, 0, 0],
                [1, 0, 0],
                [0, 1, 1],
            )
            UC.draw(prp, uc_col, UcOperator(ZUV_OT_TrimAdjustSizeTrim.bl_idname))
            prp_col.prop(prp, 'adjust_mode')
        elif prp.trim_transform_mode == 'CROP':
            UC = TrimsUnifiedControl
            UC.enabler_mtx = (
                [0, 0, 0],
                [0, 1, 0],
                [0, 0, 0],
            )
            UC.draw(prp, uc_col, UcOperator(ZUV_OT_TrimCropTrim.bl_idname))
            prp_col.prop(prp, 'crop_mode', text='Crop Mode')

        elif prp.trim_transform_mode == 'ALIGN':
            UC = TrimsUnifiedControl
            UC.enabler_mtx = (
                [1, 1, 1],
                [1, 1, 1],
                [1, 1, 1],
            )
            UC.draw(prp, uc_col, UcOperator(ZUV_OT_TrimAlignTrim.bl_idname, s_props=['align_direction', ]))
            prp_col.prop(prp, 'align_mode')
            add_row = prp_col.row(align=True)
            add_row.label(text='Center by Axis:')

            ot = add_row.operator(
                ZUV_OT_TrimAlignTrim.bl_idname,
                icon_value=icon_get("tr_rotate_lc"), text='')
            ot.align_direction = 'cen_h'
            ot.is_panel_controlled = True

            ot = add_row.operator(
                ZUV_OT_TrimAlignTrim.bl_idname,
                icon_value=icon_get("tr_rotate_tc"), text='')
            ot.align_direction = 'cen_v'
            ot.is_panel_controlled = True

        elif prp.trim_transform_mode == 'DISTRIBUTE':
            UC = TrimsUnifiedControl
            UC.enabler_mtx = (
                [0, 1, 0],
                [1, 1, 1],
                [0, 1, 0],
            )
            UC.draw(prp, uc_col, UcOperator(ZUV_OT_TrimDistributeTrim.bl_idname))
            prp_col.prop(prp, 'distr_mode')
            prp_col.prop(prp, 'distr_and_align')
            if prp.distr_mode == 'ACTIVE_TRIM':
                prp_col.prop(prp, 'distr_reverse_direction_in_a_trim_mode')


def draw_trims_transform_operators(context: bpy.types.Context, layout):
    ''' @Draw Trim Transform Operators '''
    layout.separator()
    grid = layout.grid_flow(align=True, columns=2)
    grid.operator(ZUV_OT_TrimAlignTrim.bl_idname)
    grid.operator(ZUV_OT_TrimCropTrim.bl_idname)
    grid.operator(ZUV_OT_TrimAdjustSizeTrim.bl_idname)
    grid.operator(ZUV_OT_TrimDistributeTrim.bl_idname)


classes = (
    ZUV_OT_TrimAlignTrim,
    ZUV_OT_TrimCropTrim,
    ZUV_OT_TrimAdjustSizeTrim,
    ZUV_OT_TrimDistributeTrim,
    ZuvTrimsheetTransformProps,
    ZUV_OT_SetActiveTrimMouseover
)


def register():
    from bpy.utils import register_class
    for cl in classes:
        register_class(cl)


def unregister():
    from bpy.utils import unregister_class
    for cl in classes:
        unregister_class(cl)
