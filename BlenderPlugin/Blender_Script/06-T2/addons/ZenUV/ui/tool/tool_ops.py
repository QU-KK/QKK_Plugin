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
import bmesh
from mathutils import Vector, Matrix

from bl_operators.wm import rna_path_prop

from timeit import default_timer as timer
import re
import math
from dataclasses import dataclass, asdict

from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils.blender_zen_utils import (
    update_areas_in_all_screens, rsetattr,
    get_view_1px_from_region, is_uv_snap_enabled,
    ZenPolls)
from ZenUV.utils.vlog import Log
from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer,
    resort_objects_by_selection,
    calc_uv_editor_image_aspect_ratio)
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.ops.transform_sys.transform_utils.tr_object_data import transform_object_loop_data
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps
from ZenUV.prop.scene_ui_props import ZUV_UVToolProps, ZuvFitToSelectionProps


def zenuv_status_text_transform_draw(
        self, context: bpy.types.Context, snap_enabled: bool,
        precision_mode=False, z_axis='', step_rotation=None):
    layout: bpy.types.UILayout = self.layout

    row = layout.row(align=True)
    row.use_property_split = False

    subrow = row.row(align=True)
    subrow.label(icon='EVENT_RETURN')
    subrow.label(text="Confirm")

    row.separator()

    subrow = row.row(align=False)
    subrow.label(icon="EVENT_ESC")
    subrow.label(text="Cancel")

    row.separator()

    subrow = row.row(align=True)
    subrow.label(icon="EVENT_X")
    subrow.label(icon="EVENT_Y")
    subrow.label(text="Axis")

    if z_axis:
        subrow = row.row(align=True)
        subrow.label(icon="EVENT_Z")
        subrow.label(text=z_axis)

    subrow = row.row(align=False)
    subrow.label(icon="EVENT_CTRL")
    subrow.label(text="Invert Snap" if snap_enabled else "Enable Snap")

    if step_rotation is not None:
        subrow = row.row(align=True)
        subrow.label(icon="EVENT_A")
        subrow.label(text="Angle Step On" if not step_rotation else "Angle Step Off")

    if precision_mode:
        subrow = row.row(align=True)
        subrow.label(icon="EVENT_SHIFT")
        subrow.label(text="Precision Mode")


class ZUV_OT_ToolTrimHandle(bpy.types.Operator):
    bl_idname = 'zenuv.tool_trim_handle'
    bl_label = 'Align|Fit|Flip Trims'
    bl_options = {'INTERNAL'}

    direction: bpy.props.StringProperty(
        name='Handle Direction',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('ALIGN', 'Align', ''),
            ('FIT', 'Fit', ''),
            ('FLIP', 'Flip', ''),
            ('ROTATE', 'Rotate', ''),
            ('ORIENT', 'Orient', ''),

            ('PIVOT_HANDLE', 'Island Pivot', ''),
            ('UNWRAP', 'Unwrap', ''),
            ('WORLD_ORIENT', 'World Orient', ''),
            ('SELECT_BY_FACE', 'Trim By Face', 'Trim select by active face'),
        ],
        default='ALIGN',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    pivot_prop: bpy.props.StringProperty(
        name='Pivot Property',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._timer = None
        self._last_click = 0

    def cancel(self, context: bpy.types.Context):
        if hasattr(self, "_timer") and self._timer is not None:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self._timer = None
        self._last_click = 0

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        if properties:
            from ZenUV.ops.transform_sys.trim_depend_transform import (
                ZUV_OT_TrAlignToTrim,
                ZUV_OT_TrFlipInTrim,
                ZUV_OT_TrFitToTrim
            )

            from ZenUV.ops.transform_sys.tr_rotate import (
                ZUV_OT_TrRotate3DV
            )

            s_out = [
                ZUV_OT_TrAlignToTrim.bl_description,
                ' * Ctrl - ' + ZUV_OT_TrRotate3DV.bl_description,
                ' * Shift - ' + ZUV_OT_TrFitToTrim.bl_description,
                ' * Ctrl+Shift - ' + ZUV_OT_TrFlipInTrim.bl_description
            ]

            s_double = ['-----------------------']
            if properties.pivot_prop:
                s_double.append(
                    ' * Double Click - Set Transform Pivot'
                )
            if properties.direction == 'cen':
                s_double.append(
                    ' * Double Click+Shift - Unwrap'
                )
                s_double.append(
                    ' * Double Click+Ctrl - World Orient'
                )
                s_double.append(
                    ' * Double Click+Ctrl+Shift - Trim by Face'
                )

            if len(s_double) > 1:
                s_out += s_double

            return '\n'.join(s_out)
        else:
            return cls.bl_description

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        if self._timer is None:
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.cancel(context)

            if self.mode == 'FIT':
                self.mode = 'UNWRAP'
                return self.execute(context)
            elif self.mode in {'ROTATE', 'ORIENT'}:
                self.mode = 'WORLD_ORIENT'
                return self.execute(context)
            elif self.mode == 'FLIP':
                self.mode = 'SELECT_BY_FACE'
                return self.execute(context)
            elif self.pivot_prop:
                self.mode = 'PIVOT_HANDLE'
                return self.execute(context)

            return {'CANCELLED'}

        if timer() - self._last_click > 0.3:
            self.cancel(context)
            return self.execute(context)

        return {'RUNNING_MODAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if self._timer is not None:
            return {'CANCELLED'}

        self.mode = 'ALIGN'
        if event.ctrl and event.shift:
            self.mode = 'FLIP'
        elif event.ctrl:
            self.mode = (
                'ROTATE' if self.direction in UV_AREA_BBOX.bbox_corner_handles else
                'ORIENT')
        elif event.shift:
            self.mode = 'FIT'

        if self.pivot_prop or ((event.ctrl or event.shift) and self.direction == 'cen'):
            wm = context.window_manager
            wm.modal_handler_add(self)

            self._timer = wm.event_timer_add(0.1, window=context.window)
            self._last_click = timer()

            return {'RUNNING_MODAL'}
        else:
            return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            def handle_failed_poll(op_mod):
                op_cls = bpy.types.Operator.bl_rna_get_subclass_py(op_mod.idname())
                s_reason = op_cls.poll_reason(context)
                if s_reason:
                    raise RuntimeError(s_reason)

            if self.mode == 'ALIGN':
                op_mod = bpy.ops.uv.zenuv_align_to_trim
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True,
                        align_direction=self.direction,
                        island_pivot=self.direction,
                        i_pivot_as_direction=True,
                        )
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'ROTATE':
                if self.direction in UV_AREA_BBOX.bbox_not_bottom_left:
                    angle = 90
                if self.direction == UV_AREA_BBOX.bbox_bottom_left:
                    angle = -90
                op_mod = bpy.ops.view3d.zenuv_rotate
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True,
                        rotation_mode='ANGLE',
                        tr_rot_inc_full_range=angle)
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'ORIENT':
                if self.direction in UV_AREA_BBOX.bbox_horizontal_handles:
                    orient_dir = 'HORIZONTAL'
                elif self.direction in UV_AREA_BBOX.bbox_vertical_handles:
                    orient_dir = "VERTICAL"
                elif self.direction == 'cen':
                    orient_dir = "AUTO"
                op_mod = bpy.ops.uv.zenuv_orient_island
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT',
                        mode='BBOX',
                        orient_direction=orient_dir,
                        rotate_direction='CW')
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'FIT':
                op_mod = bpy.ops.uv.zenuv_fit_to_trim
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True,
                        op_align_to=self.direction,
                        )
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'FLIP':
                op_mod = bpy.ops.uv.zenuv_flip_in_trim
                if op_mod.poll():
                    return bpy.ops.uv.zenuv_flip_in_trim(
                        'INVOKE_DEFAULT', True,
                        direction=self.direction)
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'PIVOT_HANDLE':
                if self.pivot_prop:
                    p_scene = context.scene
                    rsetattr(p_scene, self.pivot_prop, self.direction)
                    context.area.tag_redraw()
            elif self.mode == 'UNWRAP':
                op_mod = bpy.ops.uv.zenuv_unwrap_for_tool
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True)
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'WORLD_ORIENT':
                op_mod = bpy.ops.uv.zenuv_world_orient
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True)
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'SELECT_BY_FACE':
                op_mod = bpy.ops.uv.zenuv_trim_select_by_face
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True)
                else:
                    handle_failed_poll(op_mod)
            return {'FINISHED'}

        except Exception as e:
            self.report({'WARNING'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_ToolAreaUpdate(bpy.types.Operator):
    bl_idname = 'zenuv.tool_area_update'
    bl_label = 'Update UV and 3D Areas'
    bl_description = 'Internal Zen UV tool operator to update UV and 3D areas by hotkeys'
    bl_options = {'INTERNAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        bpy.ops.wm.zuv_event_service('INVOKE_DEFAULT')
        update_areas_in_all_screens(context)
        return {'PASS_THROUGH'}  # NEVER CHANGE THIS !


class ZUV_OT_ToolExitCreate(bpy.types.Operator):
    bl_idname = 'zenuv.tool_exit_create'
    bl_label = 'Exit Create Mode'
    bl_description = 'Exit Zen Uv tool create trims mode'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        return p_scene.zen_uv.ui.uv_tool.trim_mode == 'CREATE'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_scene = context.scene
        p_scene.zen_uv.ui.uv_tool.trim_mode = 'RESIZE'
        return {'PASS_THROUGH'}  # NEVER CHANGE THIS !


class ZUV_OT_TrimScrollFit(bpy.types.Operator):
    bl_idname = 'wm.zenuv_trim_scroll_fit'
    bl_label = 'Scroll Fit To Trim'
    bl_description = 'Scroll active trim forward-backward and fit island(s) to it'
    bl_options = {'REGISTER', 'UNDO'}

    is_up: bpy.props.BoolProperty(
        name="Scroll Up",
        description="Scroll to beginning of the trimsheet",
        default=False
    )

    filter: bpy.props.StringProperty(
        name="Filter",
        description="Comma separeted list of partial or full filter by trim name",
        default=""
    )

    # NOTE: this property is required to fight bug:
    # https://projects.blender.org/blender/blender/issues/125901
    influence_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Transform Mode",
        items=[
            ("ISLAND", "Islands", "Transform islands mode", 'UV_ISLANDSEL', 0),
            ("SELECTION", "Selection", "Transform selection (uv, mesh) mode", 'UV_FACESEL', 1),
        ],
    )

    LITERAL_CATEGORIES = "_trimsheet_categories"
    LITERAL_CATEGORIES_SET = "_trimsheet_categories_set"
    LITERAL_TRIM_NOT_CHANGED = "Active trim not changed!"

    def get_categories_items(self, context: bpy.types.Context):
        items = {}

        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if p_trimsheet:
            pattern = r'[^_\.\d\s]+'
            i_count = 0
            for trim in p_trimsheet:
                match = re.search(pattern, trim.name)
                if match:
                    s_category = match.group()
                    if s_category not in items:
                        items[s_category] = ((s_category, s_category, "", "NONE", 2**len(items)))
                        i_count += 1
                        if i_count >= 31:
                            # NOTE: 32 is limitation of set
                            break

        were_items = bpy.app.driver_namespace.get(ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES, [])
        p_list = list(items.values())
        if were_items != p_list:
            bpy.app.driver_namespace[ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES] = p_list
            return bpy.app.driver_namespace[ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES]
        else:
            return were_items

    def get_trimsheet_categories(self):
        were_items = bpy.app.driver_namespace.get(ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES, [])
        t_items = {item[0].lower(): idx for idx, item in enumerate(were_items)}
        t_cats = self.filter.split(",")
        value = 0
        for cat in t_cats:
            cat = cat.strip().lower()
            if cat in t_items:
                value = value | (1 << t_items[cat])
        return value

    def set_trimsheet_categories(self, value):
        t_items = []
        were_items = bpy.app.driver_namespace.get(ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES, [])
        for idx, item in enumerate(were_items):
            if value & (1 << idx):
                t_items.append(item[0])
        self.filter = ", ".join(t_items)

    trimsheet_categories: bpy.props.EnumProperty(
        name="Categories",
        description="Categories that are created from trim names",
        items=get_categories_items,
        get=get_trimsheet_categories,
        set=set_trimsheet_categories,
        options={'ENUM_FLAG', 'HIDDEN', 'SKIP_SAVE'},
    )

    warning_message: bpy.props.StringProperty(
        name="Warning",
        description="Warning message",
        default=""
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        # NOTE: Do not change poll to be able to change scroll increment
        return True

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        if self.warning_message:
            box = layout.box()
            box.alert = True
            box.label(text=self.warning_message, icon='ERROR')

        row = layout.row(align=True)
        row.alert = self.warning_message == self.LITERAL_TRIM_NOT_CHANGED
        row.prop(self, "filter")
        row.prop_menu_enum(self, "trimsheet_categories", text="", icon="TRIA_DOWN")

        from ZenUV.ops.transform_sys.trim_depend_transform import ZUV_OT_TrFitToTrim
        wm = context.window_manager
        op_props = wm.operator_properties_last(ZUV_OT_TrFitToTrim.bl_idname)
        if op_props:
            p_influence_instance = self
            p_instance = op_props
            ZUV_OT_TrFitToTrim.do_draw(p_influence_instance, p_instance, self.layout, context)

    def is_interrupted(self, p_trim, context: bpy.types.Context):
        if self.filter:
            t_cats = self.filter.split(",")
            return any(cat.strip().lower() in p_trim.name.lower() for cat in t_cats)

        return True

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.warning_message = ""
        p_trim_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_trim_owner:
            idx = p_trim_owner.trimsheet_index
            p_trimsheet = p_trim_owner.trimsheet

            n_count = len(p_trimsheet)
            if n_count > 1:
                new_idx = idx

                if self.is_up:
                    for _ in range(n_count):
                        new_idx = new_idx + 1
                        if new_idx >= n_count:
                            new_idx = 0

                        if self.is_interrupted(p_trimsheet[new_idx], context):
                            break
                else:
                    for _ in range(n_count):
                        new_idx = new_idx - 1
                        if new_idx < 0:
                            new_idx = n_count - 1

                        if self.is_interrupted(p_trimsheet[new_idx], context):
                            break

                if new_idx != idx:
                    bpy.ops.wm.zuv_trim_set_index(trimsheet_index=new_idx)
                    self.influence_mode = context.scene.zen_uv.tr_type
                    return self.execute(context)
                else:
                    self.warning_message = self.LITERAL_TRIM_NOT_CHANGED
                    self.report({'INFO'}, self.warning_message)
                    return {'FINISHED'}  # NOTE: Do not change return value !!!
        return {'CANCELLED'}

    def execute(self, context: bpy.types.Context):
        if bpy.ops.uv.zenuv_fit_to_trim.poll():
            wm = context.window_manager
            op_props = wm.operator_properties_last("uv.zenuv_fit_to_trim")
            if op_props:
                props = op_props.bl_rna.properties
                keys = set(props.keys()) - {'rna_type'}
                t_kwargs = dict()
                for k in keys:
                    t_kwargs[k] = getattr(op_props, k)
                    if k == 'influence_mode':
                        t_kwargs[k] = self.influence_mode

                res = bpy.ops.uv.zenuv_fit_to_trim('INVOKE_DEFAULT', True, **t_kwargs)
                context.area.tag_redraw()
                return res

        return {'CANCELLED'}


# NOTE: we create this internal class to avoid this issue:
# https://projects.blender.org/blender/blender/issues/125901
class ZUV_OT_TrimScrollFitInternal(bpy.types.Operator):
    bl_idname = 'wm.zenuv_trim_scroll_fit_internal'
    bl_label = ZUV_OT_TrimScrollFit.bl_label
    bl_description = ZUV_OT_TrimScrollFit.bl_description
    bl_options = {'INTERNAL'}

    is_up: bpy.props.BoolProperty(
        name="Scroll Up",
        description="Scroll to beginning of the trimsheet",
        default=False
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        bpy.ops.wm.zenuv_trim_scroll_fit('INVOKE_DEFAULT', True, is_up=self.is_up)
        return {'PASS_THROUGH'}


class ZUV_OT_ToolScreenZoom(bpy.types.Operator):
    bl_idname = 'view3d.tool_screen_zoom'
    bl_label = 'Screen Select Scale'
    bl_description = 'Scale view3d tool in screen select mode'
    bl_options = {'INTERNAL'}

    is_up: bpy.props.BoolProperty(
        default=False
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        return p_scene.zen_uv.ui.view3d_tool.is_screen_selector_position_enabled()

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_scene = context.scene
        p_scene.zen_uv.ui.view3d_tool.screen_scale += (0.1 if self.is_up else -0.1)
        context.area.tag_redraw()
        return {'FINISHED'}


class ZUV_OT_ToolScreenPan(bpy.types.Operator):
    bl_idname = 'view3d.tool_screen_pan'
    bl_label = 'Screen Select Pan'
    bl_description = 'Pan view3d tool in screen select mode'
    bl_options = {'INTERNAL'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.init_mouse = Vector((0, 0))
        self.init_value = Vector((0, 0))

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        return p_scene.zen_uv.ui.view3d_tool.is_screen_selector_position_enabled()

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        if event.value == 'RELEASE' or event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}

        delta = self.init_mouse - Vector((event.mouse_x, event.mouse_y))

        p_scene = context.scene

        value = self.init_value - delta

        p_scene.zen_uv.ui.view3d_tool.screen_pan_x = value.x
        p_scene.zen_uv.ui.view3d_tool.screen_pan_y = value.y

        context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.init_mouse = Vector((event.mouse_x, event.mouse_y))

        wm = context.window_manager
        p_scene = context.scene

        self.init_value = Vector((
            p_scene.zen_uv.ui.view3d_tool.screen_pan_x,
            p_scene.zen_uv.ui.view3d_tool.screen_pan_y
        ))

        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}


class ZUV_OT_ToolScreenReset(bpy.types.Operator):
    bl_idname = 'view3d.tool_screen_reset'
    bl_label = 'Screen Select Reset'
    bl_description = 'Reset scale and pan view3d tool in screen select mode'
    bl_options = {'INTERNAL'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('RESET', 'Reset', ''),
            ('CENTER', 'Center in view', '')
        ],
        default='RESET'
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        tool_props = p_scene.zen_uv.ui.view3d_tool
        return tool_props.is_screen_selector_position_enabled()

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_scene = context.scene
        p_tool_props = p_scene.zen_uv.ui.view3d_tool

        p_trim_data = ZuvTrimsheetUtils.getActiveTrimData(context)

        if self.mode == 'RESET' or p_trim_data is None:
            p_tool_props.screen_scale = 1.0
            p_tool_props.screen_pan_x = 0.0
            p_tool_props.screen_pan_y = 0.0
        else:
            v_scr_cen = Vector(p_tool_props.screen_pos)
            v_scr_pan = Vector((p_tool_props.screen_pan_x, p_tool_props.screen_pan_y))
            d_rect_length = p_tool_props.screen_size

            v_scr = v_scr_cen - v_scr_pan
            v_start = v_scr - Vector((d_rect_length / 2, d_rect_length / 2))

            _, p_trim, p_trimsheet = p_trim_data
            bounds = ZuvTrimsheetUtils.getTrimsheetBounds(p_trimsheet)

            v_cen = Vector(p_trim.get_center()).to_3d()

            d_trimsheet_size = max(max(bounds.width, bounds.height), 1.0)
            d_trimsheet_size_ratio = 1.0 / d_trimsheet_size

            d_size = max(p_trim.width, p_trim.height) * 2.0 * d_trimsheet_size_ratio
            was_scale = p_tool_props.screen_scale

            if d_size != 0 and was_scale != 0:
                p_tool_props.screen_scale = 1 / d_size
                sca_diff = p_tool_props.screen_scale / was_scale
            else:
                sca_diff = 1.0

            mtx_pos = Matrix.Translation(v_start.resized(3))
            mtx_sca = Matrix.Diagonal((d_rect_length, d_rect_length, 1.0)).to_4x4()
            mtx = mtx_pos @ mtx_sca
            v_cen = mtx @ v_cen

            p_tool_props.screen_pan_x = (v_scr.x - v_cen.x) * sca_diff
            p_tool_props.screen_pan_y = (v_scr.y - v_cen.y) * sca_diff

        context.area.tag_redraw()
        return {'FINISHED'}


class ZUV_OT_ToolScreenSelector(bpy.types.Operator):
    bl_idname = 'view3d.tool_screen_selector'
    bl_label = 'Trim Screen Selector'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            p_scene = context.scene
            t_out = ['Show screen viewport trim selector']
            if p_scene.zen_uv.ui.view3d_tool.enable_screen_selector:
                s_locked = "Unlock" if p_scene.zen_uv.ui.view3d_tool.screen_position_locked else "Lock"
                t_out.append(f'* Shift+Click - {s_locked} screen selector position')
                if p_scene.zen_uv.ui.view3d_tool.screen_position_locked:
                    t_out.append("   to be able to move widget by hotkeys")
            return '\n'.join(t_out)
        else:
            return cls.bl_description

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('DEFAULT', 'Default', ''),
            ('LOCK', 'Lock', '')
        ],
        default='DEFAULT',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return True

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.mode = 'DEFAULT'
        p_scene = context.scene
        if p_scene.zen_uv.ui.view3d_tool.enable_screen_selector:
            if event.shift:
                self.mode = 'LOCK'
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        p_scene = context.scene
        if self.mode == 'DEFAULT':
            p_scene.zen_uv.ui.view3d_tool.enable_screen_selector = not p_scene.zen_uv.ui.view3d_tool.enable_screen_selector
        elif self.mode == 'LOCK':
            p_scene.zen_uv.ui.view3d_tool.screen_position_locked = not p_scene.zen_uv.ui.view3d_tool.screen_position_locked

        context.area.tag_redraw()

        return {'FINISHED'}


class ZUV_OT_TrimActivateTool(bpy.types.Operator):
    bl_idname = "uv.zuv_activate_tool"
    bl_label = "Zen UV Tool"
    bl_description = 'Activate Zen UV tool'  # Is used for Pie
    bl_option = {'REGISTER'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        description='Trim sheets data mode',
        items=[
            ('OFF', 'Off', ''),
            ('RESIZE', 'Resize', ''),
            ('CREATE', 'Create', ''),
            ('ACTIVATE', 'Activate', '')
        ],
        default='OFF'
    )

    prev_tool: bpy.props.StringProperty(
        name='Previous Tool',
        default=''
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            if properties.mode == 'RESIZE':
                return "Activate Tool in Resize Trims mode"
            if properties.mode == 'CREATE':
                return "Activate Tool in Create Trims mode"
            if properties.mode == 'ACTIVATE':
                return "Activate Tool"

            return "Deactivate Tool"
        else:
            return cls.bl_description

    def set_uv_prev_tool(self, context: bpy.types.Context):
        _id_UV = getattr(context.workspace.tools.from_space_image_mode('UV', create=False), 'idname', None)
        if isinstance(_id_UV, str):
            self.prev_tool = _id_UV

    def execute(self, context: bpy.types.Context):
        if self.mode == 'CREATE':
            self.set_uv_prev_tool(context)

            bpy.context.scene.zen_uv.ui.uv_tool.category = 'TRIMS'
            bpy.context.scene.zen_uv.ui.uv_tool.trim_mode = 'CREATE'
            bpy.ops.wm.tool_set_by_id(name="zenuv.uv_tool")

        elif self.mode == 'RESIZE':
            self.set_uv_prev_tool(context)

            bpy.context.scene.zen_uv.ui.uv_tool.category = 'TRIMS'
            bpy.context.scene.zen_uv.ui.uv_tool.trim_mode = 'RESIZE'
            bpy.ops.wm.tool_set_by_id(name="zenuv.uv_tool")
        elif self.mode == 'ACTIVATE':
            self.prev_tool = ''
            if context.area.type == 'IMAGE_EDITOR':
                bpy.ops.wm.tool_set_by_id(name="zenuv.uv_tool")
            elif context.area.type == 'VIEW_3D':
                bpy.ops.wm.tool_set_by_id(name="zenuv.view3d_tool")
        else:
            bpy.context.scene.zen_uv.ui.uv_tool.category = 'TRANSFORMS'

            if self.prev_tool:
                try:
                    bpy.ops.wm.tool_set_by_id(name=self.prev_tool)
                except Exception as e:
                    Log.error('DEACTIVATE TOOL:', str(e))

        return {'FINISHED'}


class ZUV_OT_ToolSnapHandle(bpy.types.Operator):
    bl_idname = 'zenuv.tool_snap_handle'
    bl_label = 'Snap Pivot'
    bl_description = 'Click to change snap pivot'
    bl_options = {'INTERNAL'}

    direction: bpy.props.StringProperty(
        name='Handle Direction',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def execute(self, context: bpy.types.Context):
        p_scene = context.scene
        p_tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        p_tool_props.trim_snap_pivot = self.direction
        context.area.tag_redraw()
        return {'FINISHED'}


@dataclass
class ZuvTransformGizmoAxisLockPreset:
    match_pos: bool = True
    match_rotation: bool = True
    match_scale: bool = True
    lock_scale_axis: str = 'SKIP'
    lock_position_axis: str = 'SKIP'

    @classmethod
    def is_non_proptional_scale(cls, p_operator_instance):
        return (
            p_operator_instance.match_pos and
            not p_operator_instance.match_rotation and
            p_operator_instance.match_scale and
            p_operator_instance.lock_scale_axis == 'LOCAL' and
            p_operator_instance.lock_position_axis == 'LOCAL')

    def setup_by_gizmo_lock(self, gizmo_axes_lock: str):
        if gizmo_axes_lock == "SCALE_ALONG_AXIS":
            self.match_pos = True
            self.match_rotation = False
            self.match_scale = True
            self.lock_scale_axis = 'SKIP'
            self.lock_position_axis = 'LOCAL'
        elif gizmo_axes_lock == "SCALE_ALONG_AXIS_NO_PROPORTION":
            self.match_pos = True
            self.match_rotation = False
            self.match_scale = True
            self.lock_scale_axis = 'LOCAL'
            self.lock_position_axis = 'LOCAL'
        elif gizmo_axes_lock == "PURE_ROTATION":
            self.match_pos = False
            self.match_rotation = True
            self.match_scale = False
        elif gizmo_axes_lock == "MOVE_ALONG_AXIS":
            self.match_pos = True
            self.match_rotation = False
            self.match_scale = False
            self.lock_position_axis = 'LOCAL'
        elif gizmo_axes_lock == "AXIS_LOCK_MOVE_X":
            self.match_pos = True
            self.match_rotation = False
            self.match_scale = False
            self.lock_position_axis = 'X'
        elif gizmo_axes_lock == "AXIS_LOCK_MOVE_Y":
            self.match_pos = True
            self.match_rotation = False
            self.match_scale = False
            self.lock_position_axis = 'Y'
        elif gizmo_axes_lock == "AXIS_LOCK_SCALE_X":
            self.match_pos = False
            self.match_rotation = True
            self.match_scale = True
            self.lock_scale_axis = 'X'
        elif gizmo_axes_lock == "AXIS_LOCK_SCALE_Y":
            self.match_pos = False
            self.match_rotation = True
            self.match_scale = True
            self.lock_scale_axis = 'Y'

    def save_to_operator(self, p_operator_instance):
        for k, v in asdict(self).items():
            setattr(p_operator_instance, k, v)


class ZUV_OP_ToolTransform(bpy.types.Operator):
    bl_idname = 'uv.zenuv_tool_transform'
    bl_label = 'Tool Transform'
    bl_description = 'Transform UVs using Zen UV gizmo tool'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        """ Validate context """
        active_object = context.active_object
        return (
            active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and
            isinstance(context.space_data, bpy.types.SpaceImageEditor))

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        active_object = context.active_object
        if active_object is None:
            return "No Active Object"
        if active_object.type != 'MESH':
            return "No Active Mesh Object"
        if context.mode != 'EDIT_MESH':
            return "Available in Edit Mode"
        if not isinstance(context.space_data, bpy.types.SpaceImageEditor):
            return "Available only in UV Editor"

        return ""

    def get_origin_head(self):
        scene = bpy.context.scene
        tool_props: ZUV_UVToolProps = scene.zen_uv.ui.uv_tool
        return tool_props.tr_gizmo_init_a_handle[:]

    def set_origin_head(self, value):
        scene = bpy.context.scene
        tool_props: ZUV_UVToolProps = scene.zen_uv.ui.uv_tool
        tool_props.tr_gizmo_init_a_handle = value

    def get_origin_pivot(self):
        scene = bpy.context.scene
        tool_props: ZUV_UVToolProps = scene.zen_uv.ui.uv_tool
        return tool_props.tr_gizmo_init_p_handle[:]

    def set_origin_pivot(self, value):
        scene = bpy.context.scene
        tool_props: ZUV_UVToolProps = scene.zen_uv.ui.uv_tool
        tool_props.tr_gizmo_init_p_handle = value

    origin_head: bpy.props.FloatVectorProperty(
        name="Origin Head",
        size=2,
        get=get_origin_head,
        set=set_origin_head,
        options={'HIDDEN', 'SKIP_SAVE'},
        default=(0.5, 0.5),
        subtype='XYZ'
    )

    origin_pivot: bpy.props.FloatVectorProperty(
        name="Origin Pivot",
        size=2,
        get=get_origin_pivot,
        set=set_origin_pivot,
        options={'HIDDEN', 'SKIP_SAVE'},
        default=(0.5, 0.0),
        subtype='XYZ'
    )

    matched_pivot: bpy.props.FloatVectorProperty(
        name="Matched Pivot",
        size=2,
        default=(0.5, 0.0),
        subtype='XYZ'
    )
    matched_head: bpy.props.FloatVectorProperty(
        name="Matched Head",
        size=2,
        default=(0.5, 0.5),
        subtype='XYZ'
    )

    influence: bpy.props.EnumProperty(
        name='Influence',
        description='Transform Influence. Affect Islands or Elements (vertices, edges, polygons)',
        items=[
            ("ISLAND", "Island", "Process islands", "UV_ISLANDSEL", 0),
            ("SELECTION", "Selection", "Process selected mesh elements (vertices, edges, faces)", 'UV_FACESEL', 1)
        ],
        default="ISLAND"
    )

    is_pivot: bpy.props.BoolProperty(
        name="Is Pivot Handle",
        description="Defines transform for pivot or angle handle",
        default=True
    )

    match_pos: bpy.props.BoolProperty(
        name='Position',
        description='Match Island position',
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    lock_position_axis: bpy.props.EnumProperty(
        name='Lock Position Axis',
        description='Blocks one of the axes. Thus, the transformation occurs only in one of the axes.',
        items=[
            ('SKIP', 'Skip', 'Do not use axes lock'),
            ('X', 'X', 'Lock axis X'),
            ('Y', 'Y', 'Lock axis Y'),
            ('LOCAL', 'Local', 'Move along gixmo axis')],
        default='SKIP',
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    match_rotation: bpy.props.BoolProperty(
        name='Rotation',
        description='Match Island rotation',
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    snap_angle: bpy.props.FloatProperty(
        name='Rotation Increment',
        default=0.0,
        min=0.0,
        max=math.pi / 2,
        subtype='ANGLE'  # RADIANS
    )
    match_scale: bpy.props.BoolProperty(
        name='Scale',
        description='Match Island size',
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    lock_scale_axis: bpy.props.EnumProperty(
        name='Lock Scale Axis',
        description='Blocks one of the axes. Thus, the transformation occurs only in one of the axes.',
        items=[
            ('SKIP', 'Skip', 'Do not use axes lock'),
            ('X', 'X', 'Lock axis X'),
            ('Y', 'Y', 'Lock axis Y'),
            ('LOCAL', 'Local', 'Move along gixmo axis')],
        default='SKIP',
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    allow_negative_scale: bpy.props.BoolProperty(
        name="Allow Negative Scale",
        description="Allows negative scale",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    correct_aspect: bpy.props.BoolProperty(
        name="Correct Aspect",
        description="Taking image aspect ratio into accaunt",
        default=True
    )
    use_falloff: bpy.props.BoolProperty(
        name="Use Falloff",
        description="Use transformation falloff",
        default=False
    )
    invert_falloff: bpy.props.BoolProperty(
        name="Invert Falloff",
        description="Invert the falloff effect",
        default=False
    )

    falloff_type: bpy.props.EnumProperty(
        name='Falloff type',
        description='Use tranfsormation falloff',
        items=[
            ('LINEAR', 'Linear', 'Use Linear falloff'),
            ('RADIAL', 'Radial', 'Use Radial falloff'),
            ],
        default='RADIAL'
    )
    falloff_exponent: bpy.props.FloatProperty(
        name='Falloff Exponent',
        default=1.0,
        min=0.0,
        max=10
    )
    linear_falloff_transformation_type: bpy.props.EnumProperty(
        name='Linear falloff transformation type',
        description='Select the transformation used in linear falloff mode for the angle handle',
        items=[
            ('ROTATE', 'Rotation', 'Use Linear falloff'),
            ('MOVE', 'Translation', 'Use Radial falloff'),
            ],
        default={'ROTATE', 'MOVE'},
        options={'ENUM_FLAG'}
    )

    is_gizmo_initialization: bpy.props.BoolProperty(
        name="Is Gizmo Initialization",
        description="Defines only gizmo initialization without any transformation",
        options={'HIDDEN', 'SKIP_SAVE'},
        default=False
    )

    transform_pos_matrix: bpy.props.FloatVectorProperty(
        name="Position Matrix",
        description="Transformation position matrix that is used to modify UV",
        size=(4, 4),
        options={'HIDDEN', 'SKIP_SAVE'},
        subtype='MATRIX',
        default=(
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0))
    )

    transform_rot_matrix: bpy.props.FloatVectorProperty(
        name="Rotation Matrix",
        description="Transformation rotation matrix that is used to modify UV",
        size=(4, 4),
        options={'HIDDEN', 'SKIP_SAVE'},
        subtype='MATRIX',
        default=(
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0))
    )

    transform_sca_matrix: bpy.props.FloatVectorProperty(
        name="Scale Matrix",
        description="Transformation scale matrix that is used to modify UV",
        size=(4, 4),
        options={'HIDDEN', 'SKIP_SAVE'},
        subtype='MATRIX',
        default=(
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0))
    )

    def get_prop_get_transform_matrix(self):
        return self.transform_pos_matrix @ self.transform_rot_matrix @ self.transform_sca_matrix

    transform_matrix: bpy.props.FloatVectorProperty(
        name="Transform Matrix",
        description="Transformation matrix that is used to modify UV",
        size=(4, 4),
        options={'HIDDEN', 'SKIP_SAVE'},
        subtype='MATRIX',
        get=get_prop_get_transform_matrix
    )

    preprocessing_offset: bpy.props.FloatVectorProperty(
        name='Preprocessing Offset',
        description='The offset is used during preprocessing',
        size=2,
        options={'HIDDEN', 'SKIP_SAVE'},
        default=(0, 0)
    )

    image_aspect_ratio: bpy.props.FloatProperty(
        name="Aspect Ratio",
        default=1.0
    )

    info_message: TransformSysOpsProps.info_message
    op_order: TransformSysOpsProps.get_order_prop(default='OVERALL')

    @classmethod
    def get_transform_matrix(cls, context: bpy.types.Context) -> Matrix:
        op = cls.get_active_operator(context)
        return op.transform_matrix if op is not None else None

    @classmethod
    def get_active_operator(cls, context: bpy.types.Context):
        wm = context.window_manager
        # NOTE: We should call only 'operators[-1]',
        #       'operator_properties_last' are filled only in invoke
        if wm.operators:
            op = wm.operators[-1]
            if isinstance(op, ZUV_OP_ToolTransform):
                return op
        return None

    @classmethod
    def modal_making_transform(cls, context: bpy.types.Context, tool_props: ZUV_UVToolProps):
        if tool_props.tr_gizmo_mode == 'SETUP' or not tool_props.tr_gizmo_active:
            return

        wm = context.window_manager
        if wm.operators:
            op = wm.operators[-1]
            if isinstance(op, ZUV_OP_ToolTransform):

                from .uv.uv_transform_gizmo import LITERAL_TR_GIZMO_OPERATORS

                t_operators = bpy.app.driver_namespace.get(LITERAL_TR_GIZMO_OPERATORS, dict())

                t_context = t_operators.get(
                    str(op.as_pointer()),
                    None
                )

                if t_context:

                    p_axis_lock = ZuvTransformGizmoAxisLockPreset()
                    p_axis_lock.setup_by_gizmo_lock(tool_props.tr_gizmo_axes_lock)
                    p_axis_lock.save_to_operator(op)

                    op.matched_pivot = tool_props.tr_gizmo_pivot_handle[:]
                    op.matched_head = tool_props.tr_gizmo_angle_handle[:]
                    op.is_pivot = tool_props.tr_gizmo_is_pivot

                    op.influence = tool_props.tr_gizmo_influence

                    from ZenUV.ops.context_utils import FakeContext
                    overrided_dict = context.copy()
                    overrided_dict["space_data"] = t_context["space_data"]
                    overrided_context = FakeContext(overrided_dict)
                    ZUV_OP_ToolTransform.calculate_transform_matrix(op, overrided_context)
                    op.execute(overrided_context)

    @classmethod
    def revert_transform(cls, context: bpy.types.Context, tool_props: ZUV_UVToolProps, t_init_values: dict):
        wm = context.window_manager
        if wm.operators:
            op = wm.operators[-1]
            if isinstance(op, ZUV_OP_ToolTransform):

                from .uv.uv_transform_gizmo import LITERAL_TR_GIZMO_OPERATORS

                t_operators = bpy.app.driver_namespace.get(LITERAL_TR_GIZMO_OPERATORS, dict())

                t_context = t_operators.get(
                    str(op.as_pointer()),
                    None
                )

                if t_context:
                    # NOTE: revert operator values
                    for k, v in t_init_values.items():
                        setattr(op, k, v)

                    op.execute(context)

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'is_pivot')
        layout.prop(self, 'influence')
        box = layout.box()
        box.prop(self, 'origin_pivot')
        box.prop(self, 'origin_head')
        box.prop(self, 'matched_pivot')
        box.prop(self, 'matched_head')

        box = layout.box()
        box.prop(self, 'match_pos')
        row = box.row(align=True)
        row.prop(self, 'lock_position_axis', expand=True)

        box = layout.box()
        box.prop(self, 'match_rotation')
        box.prop(self, 'snap_angle')

        box = layout.box()
        box.prop(self, 'match_scale')
        row = box.row(align=True)
        row.prop(self, 'lock_scale_axis', expand=True)
        row = box.row(align=True)
        box.prop(self, 'allow_negative_scale')

        box = layout.box()
        box.prop(self, 'correct_aspect')

        box = layout.box()
        box.prop(self, 'use_falloff')
        box.prop(self, 'falloff_type')
        box.prop(self, 'invert_falloff')
        row = box.row()
        row.enabled = self.falloff_type == 'LINEAR'
        row.prop(self, 'linear_falloff_transformation_type')
        row = box.row()
        row.prop(self, 'falloff_exponent')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.info_message = ''
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if len(objs) > 0:

            interval = timer()

            n_loops = transform_object_loop_data.setup_uvs(
                context, objs, self.influence
            )


            if n_loops == 0:
                self.info_message = "No selected islands"
                self.report({'INFO'}, self.info_message)
                return {'FINISHED'}
            else:
                res = {'FINISHED'}

                # NOTE: we consider that at initialization moment we do not need any transformations,
                #       because user just pressed on gizmo without any movement
                if not self.is_gizmo_initialization:
                    ZUV_OP_ToolTransform.calculate_transform_matrix(self, context)
                    res = self.execute(context)

                self.is_gizmo_initialization = False


                return res
        else:
            self.info_message = "There are no selected objects"
            self.report({'INFO'}, self.info_message)

        return {'CANCELLED'}

    @classmethod
    def calc_image_aspect_ratio(cls, op_props, context: bpy.types.Context):
        if isinstance(context.space_data, bpy.types.SpaceImageEditor):
            op_props.image_aspect_ratio = 1.0
            if op_props.correct_aspect:
                p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
                if p_image and p_image.size[0] > 0 and p_image.size[1] > 0:
                    op_props.image_aspect_ratio = p_image.size[0] / p_image.size[1]
        else:
            raise RuntimeError("Method 'calc_image_aspect_ratio' requires SpaceImageEditor!")

    @classmethod
    def calculate_transform_matrix(cls, op_props, context: bpy.types.Context):
        from ZenUV.utils.transform import UvTransformUtils

        tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool

        cls.calc_image_aspect_ratio(op_props, context)

        op_props.influence = tool_props.tr_gizmo_influence
        op_props.use_falloff = tool_props.tr_gizmo_transform_editing_mode in {'RADIAL_FALLOFF', 'LINEAR_FALLOFF'}

        match_pos = op_props.match_pos
        match_rot = op_props.match_rotation
        match_sca = op_props.match_scale
        lock_scale_axis = op_props.lock_scale_axis
        move_along_axis = 'LOCAL' == op_props.lock_position_axis
        action_scale_along_axis_non_uniform = False

        if op_props.is_pivot:
            p_origin_pivot, p_origin_head = op_props.origin_head, op_props.origin_pivot
            p_matched_pivot, p_matched_head = op_props.matched_head, op_props.matched_pivot
        else:
            p_origin_pivot, p_origin_head = op_props.origin_pivot, op_props.origin_head
            p_matched_pivot, p_matched_head = op_props.matched_pivot, op_props.matched_head

        allow_negative_scale = op_props.allow_negative_scale

        # NOTE: PURE_ROTATION
        if not match_pos and match_rot and not match_sca:
            pass

        # NOTE: SCALE_ALONG_AXIS_NO_PROPORTION
        elif match_pos and not match_rot and match_sca and lock_scale_axis == 'LOCAL' and move_along_axis:
            allow_negative_scale = True
            action_scale_along_axis_non_uniform = True

        # NOTE: MOVE_ALONG_AXIS
        elif match_pos and not match_rot and not match_sca and move_along_axis:
            pass

        # NOTE: SCALE_ALONG_AXIS
        elif match_pos and not match_rot and match_sca and lock_scale_axis in {'SKIP', 'X', 'Y'} and move_along_axis:
            allow_negative_scale = True

        # NOTE: Handle falloff
        is_use_linear_falloff = op_props.falloff_type == "LINEAR"
        if op_props.use_falloff:
            if op_props.falloff_type == "LINEAR":
                if tool_props.tr_gizmo_type == {'ANGLE_HANDLE'}:
                    op_props.linear_falloff_transformation_type = tool_props.tr_gizmo_linear_falloff_transformation_type
                    match_pos = "MOVE" in op_props.linear_falloff_transformation_type
                    match_rot = "ROTATE" in op_props.linear_falloff_transformation_type
                    match_sca = False
                elif 'SCALE' in tool_props.tr_gizmo_type:
                    match_pos = False
                    match_rot = False
                    match_sca = True
                elif 'SCALE_NON_PROP' in tool_props.tr_gizmo_type:
                    match_pos = False
                    match_rot = False
                    match_sca = True
                if not any((match_pos, match_rot, match_sca)):
                    tool_props.tr_gizmo_linear_falloff_transformation_type = {'MOVE'}
                    match_pos = True

            op_props.falloff_type = tool_props.tr_gizmo_transform_editing_mode.replace("_FALLOFF", "")
            op_props.falloff_exponent = tool_props.tr_gizmo_falloff_exponent
            op_props.invert_falloff = tool_props.tr_gizmo_invert_falloff

        L, R, S = UvTransformUtils.get_transformation_matrix_from_vectors_dev(
            p_origin_pivot,
            p_origin_head,

            p_matched_pivot,
            p_matched_head,

            apply_translation=match_pos,
            lock_translation_axis=['X' == op_props.lock_position_axis, 'Y' == op_props.lock_position_axis],
            is_move_along_axis=move_along_axis,

            apply_rotation=match_rot,
            snap_angle=op_props.snap_angle,

            apply_scale=match_sca,
            is_scale_along_axis=lock_scale_axis == 'LOCAL',
            allow_negative_scale=allow_negative_scale,

            apply_aspect_ratio=op_props.correct_aspect,
            image_aspect_ratio=op_props.image_aspect_ratio,
            is_use_linear_falloff=is_use_linear_falloff,
            mode_scale_along_axis_non_uniform=action_scale_along_axis_non_uniform
        )

        if op_props.preprocessing_offset[:] != (0.0, 0.0):
            S = S @ Matrix.Translation(
                (op_props.preprocessing_offset[0], op_props.preprocessing_offset[1], 0))

        op_props.transform_pos_matrix = L.copy()
        op_props.transform_rot_matrix = R.copy()
        op_props.transform_sca_matrix = S.copy()

    def execute(self, context):
        from ZenUV.utils.transform import UvTransformUtils

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.info_message = "There are no selected objects"
            self.report({'INFO'}, self.info_message)
            return {'CANCELLED'}

        if not transform_object_loop_data.is_valid(objs, self.influence, self.op_order):
            transform_object_loop_data.setup_uvs(context, objs, self.influence)

        # message = 'Finished' if transform_object_data.object_storage else 'No selected islands'

        for obj, info in transform_object_loop_data.object_storage.items():
            me = info.me
            uv_layer = info.uv_layer

            if self.use_falloff:
                UvTransformUtils.transform_loops_by_matrix_and_stored_uvs_with_falloff(
                    uv_layer=uv_layer,
                    transformed_loops=list(info.selected_loops_uvs.keys()),
                    stored_uvs=list(info.selected_loops_uvs.values()),
                    transform_matrix=self.transform_matrix,
                    falloff_vector_pivot=self.origin_pivot,
                    falloff_vector_head=self.origin_head,
                    falloff_type=self.falloff_type,
                    falloff_exponent=self.falloff_exponent,
                    is_invert_falloff=self.invert_falloff,
                    image_aspect_ratio=self.image_aspect_ratio
                )

            else:
                UvTransformUtils.transform_loops_by_matrix_and_stored_uvs(
                    uv_layer, list(info.selected_loops_uvs.keys()), list(info.selected_loops_uvs.values()), self.transform_matrix)

            bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        from .uv.uv_transform_gizmo import update_transform_gizmo_selection_center
        update_transform_gizmo_selection_center(context)

        return {'FINISHED'}


class ZUV_OP_ToolSnapTransformGizmo(bpy.types.Operator):
    bl_idname = 'uv.zenuv_tool_snap_transform_gizmo'
    bl_label = 'Snap Gizmo'
    bl_description = 'Snap Zen UV tool transform gizmo to selected'
    bl_options = {'REGISTER', 'UNDO'}

    gizmo_type: bpy.props.EnumProperty(
        name="Transform Gizmo Type",
        description="Defines active gizmo part",
        items=[
            ('PIVOT_HANDLE', 'Pivot', 'Transform gizmo pivot'),
            ('ANGLE_HANDLE', 'Handle', 'Transform gizmo handle'),
        ],
        default="PIVOT_HANDLE"
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        return bpy.ops.uv.snap_cursor.poll() and ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context)

    def execute(self, context: bpy.types.Context):
        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        if bpy.ops.uv.snap_cursor.poll():
            tool_props.tr_gizmo_type = {self.gizmo_type}
            bpy.ops.uv.snap_cursor(target="SELECTED")
            # NOTE: do not call through 'setattr' !
            tool_props[f'tr_gizmo_{self.gizmo_type.lower()}'] = context.space_data.cursor_location[:2]
            return {'FINISHED'}

        return {'CANCELLED'}


class TransformClickError(Exception):
    pass


class ZUV_OT_ToolTransformHandleClick(bpy.types.Operator):
    bl_idname = 'uv.zenuv_tool_transform_handle_click'
    bl_label = 'Transform Handle Click'
    bl_description = "Defines an action when when transform handle is clicked"
    bl_options = {'INTERNAL'}  # NOTE: Do not change options !!!

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('DEFAULT', 'Default', ''),
            ('COMMAND', 'Command', ''),
        ],
        default='DEFAULT',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    handle_action: bpy.props.EnumProperty(
        name="Handle Action",
        description="Defines what action will be executed when handle is clicked",
        items=[
            ("NONE", "None", ""),

            ("FIT_TO_SELECTION", "Fit To Selection", ""),
            ("FIT_TO_SELECTION_PIVOT_CENTER", "Fit To Selection Pivot In Center", ""),
            ("FIT_TO_ISLAND", "Fit To Island", ""),
            ("FIT_TO_ISLAND_PIVOT_CENTER", "Fit To Island Pivot In Center", ""),
            ("GET_TD", "Get Texel Density", ""),
            ("SET_TRANSFORM", "Set Transform", ""),
            ("SET_LINE_LOCK_ALONG_AXIS", "Set Line Lock Along Axis", ""),
            ("SET_SETUP", "Set Setup", ""),
        ],
        options={'HIDDEN', 'SKIP_SAVE'},
        default="NONE"
    )

    transform_data: bpy.props.FloatVectorProperty(
        name="Transform Data",
        description="Origin and matched pivot and head data",
        size=9,
        default=(0, 0, 0, 0, 0, 0, 0, 0, 0)
    )

    transform_axis_lock_mode: bpy.props.EnumProperty(
        name="Axis Lock Mode",
        items=ZUV_UVToolProps._tr_gizmo_axes_lock_items,
        default="NONE"
    )

    line_lock_along_axis: bpy.props.BoolProperty(
        name="Line Lock Along Axis",
        default=False
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        return context.space_data.type == 'IMAGE_EDITOR' and ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context)

    def scale_by_td(self, context: bpy.types.Context, tool_props: ZUV_UVToolProps):
        from ZenUV.ops.texel_density.td_utils import TexelDensityFactory, TdContext

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            raise TransformClickError("No editable objects")

        objs = resort_objects_by_selection(context, objs)
        if not objs:
            raise TransformClickError("Nothing selected")

        td_inputs = TdContext(context)
        island_td, _ = TexelDensityFactory.get_texel_density(context, objs, td_inputs)

        if island_td == 0:
            raise TransformClickError("Texel density is not defined")

        target_td = context.scene.zen_uv.td_props.prp_current_td
        mult = target_td / island_td

        init_p_handle_position = Vector(tool_props.tr_gizmo_pivot_handle)
        init_a_handle_position = Vector(tool_props.tr_gizmo_angle_handle)
        v_gizmo_vec = Vector(tool_props.tr_gizmo_angle_handle) - init_p_handle_position
        a_handle_position = init_p_handle_position + v_gizmo_vec * mult

        self.transform_data = (
            *init_p_handle_position[:],
            *init_a_handle_position[:],
            *init_p_handle_position[:],
            *a_handle_position[:],
            float(tool_props.tr_gizmo_is_pivot)
        )

        self.transform_axis_lock_mode = "NONE"

        self.handle_action = "SET_TRANSFORM"

    def scale_by_action(self, context: bpy.types.Context, tool_props: ZUV_UVToolProps, s_axis_lock_mode: str):
        init_p_handle_position = Vector(tool_props.tr_gizmo_pivot_handle)
        init_a_handle_position = Vector(tool_props.tr_gizmo_angle_handle)
        v_gizmo_vec = Vector(tool_props.tr_gizmo_angle_handle) - init_p_handle_position

        lock_mode = 'NONE'
        if s_axis_lock_mode == 'SCALE_ALONG_AXIS_NO_PROPORTION':
            if self.mode == 'COMMAND':
                lock_mode = s_axis_lock_mode
                a_handle_position = init_p_handle_position
            else:
                a_handle_position = init_p_handle_position + v_gizmo_vec * 0.5
        else:
            a_handle_position = init_p_handle_position + v_gizmo_vec * 2

        self.transform_data = (
            *init_p_handle_position[:],
            *init_a_handle_position[:],
            *init_p_handle_position[:],
            *a_handle_position[:],
            float(tool_props.tr_gizmo_is_pivot)
        )

        self.transform_axis_lock_mode = lock_mode

        self.handle_action = "SET_TRANSFORM"

    def rotate_by_action(self, context: bpy.types.Context, tool_props: ZUV_UVToolProps, angle_increment_rad: float):
        from ZenUV.utils.transform import matrix_by_image_aspect

        init_p_handle_position = Vector(tool_props.tr_gizmo_pivot_handle)
        init_a_handle_position = Vector(tool_props.tr_gizmo_angle_handle)
        v_gizmo_vec = Vector(tool_props.tr_gizmo_angle_handle) - init_p_handle_position

        aspect_ratio = calc_uv_editor_image_aspect_ratio(context)
        AM = matrix_by_image_aspect(aspect_ratio)

        dynamic_gizmo_vector = AM @ v_gizmo_vec
        current_angle = dynamic_gizmo_vector.normalized().angle_signed(Vector((1, 0)), 0.0)
        current_angle += angle_increment_rad
        new_direction = AM.inverted() @ Vector((math.cos(current_angle), math.sin(current_angle)))
        a_handle_position = init_p_handle_position + new_direction * dynamic_gizmo_vector.length

        self.transform_data = (
            *init_p_handle_position[:],
            *init_a_handle_position[:],
            *init_p_handle_position[:],
            *a_handle_position[:],
            float(tool_props.tr_gizmo_is_pivot)
        )

        self.transform_axis_lock_mode = 'PURE_ROTATION'

        self.handle_action = "SET_TRANSFORM"

    def rotate_by_world_orient_angle(self, context: bpy.types.Context, tool_props: ZUV_UVToolProps):
        from ZenUV.utils.base_clusters.base_cluster import OrientCluster
        from ZenUV.utils import get_uv_islands as island_util
        from ZenUV.utils.transform import matrix_by_image_aspect

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            raise TransformClickError("No editable objects")

        objs = resort_objects_by_selection(context, objs)
        if not objs:
            raise TransformClickError("Nothing selected")

        aspect_ratio = 1.0
        p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
        if p_image and p_image.size[0] > 0 and p_image.size[1] > 0:
            aspect_ratio = p_image.size[0] / p_image.size[1]

        AM = matrix_by_image_aspect(aspect_ratio)

        init_p_handle_position = AM @ Vector(tool_props.tr_gizmo_pivot_handle)
        init_a_handle_position = AM @ Vector(tool_props.tr_gizmo_angle_handle)

        storage = dict()
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            bm.faces.ensure_lookup_table()
            storage[obj.name] = island_util.get_selected_islands_in_indices(context, bm)

        islands_count = sum([len(k) for k in storage.values()])

        pivot = None if islands_count > 1 else init_p_handle_position @ AM.inverted()

        islands_angles = []
        for obj_name, islands in storage.items():
            obj = context.scene.objects[obj_name]
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            for island in islands:
                islands_angles.append(
                    OrientCluster.orient_uv_island([bm.faces[i] for i in island], uv_layer, pivot, image_aspect=aspect_ratio))
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        if islands_count > 1:
            v_gizmo_vec = Vector(tool_props.tr_gizmo_angle_handle) - init_p_handle_position
            a_handle_position = init_p_handle_position + Vector((0, 1)) * v_gizmo_vec.magnitude
        else:
            angle = islands_angles[0]
            back = Matrix.Translation((-init_p_handle_position[0], -init_p_handle_position[1], 0))
            to_position = Matrix.Translation((init_p_handle_position[0], init_p_handle_position[1], 0))
            M = to_position @ Matrix.Rotation(angle, 4, 'Z') @ back
            a_handle_position = (M @ init_a_handle_position.to_3d()).to_2d()

            init_a_handle_position = init_a_handle_position @ AM.inverted()
            init_p_handle_position = init_p_handle_position @ AM.inverted()
            a_handle_position = a_handle_position @ AM.inverted()

        self.transform_data = (
            *init_p_handle_position[:],
            *init_a_handle_position[:],
            *init_p_handle_position[:],
            *a_handle_position[:],
            float(True)
        )

        self.transform_axis_lock_mode = "NONE"

        self.handle_action = "SET_SETUP"

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        try:
            if self.handle_action == "NONE":
                from ZenUV.ui.tool.uv.uv_transform_gizmo import (
                    ZUV_GGT_UVTransformGizmo,
                    UV_GT_zenuv_transform_pivot, UV_GT_zenuv_transform_a_handle,
                    UV_GT_zenuv_draggable_line, UV_GT_zenuv_scale_handle, UV_GT_zenuv_rotate_handle)

                p_gizmo_group: ZUV_GGT_UVTransformGizmo = ZUV_GGT_UVTransformGizmo.get_gizmo_group_by_context(context)
                if p_gizmo_group:
                    p_scene = context.scene
                    tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

                    b_is_command = self.mode == "COMMAND"
                    b_is_setup = tool_props.tr_gizmo_mode == 'SETUP'
                    b_is_transform = tool_props.tr_gizmo_mode == 'TRANSFORM'

                    for gizmo in p_gizmo_group.gizmos:
                        if not gizmo.hide and hasattr(gizmo, "test_select_internal") and gizmo.test_select_internal(context, (event.mouse_region_x, event.mouse_region_y)) != -1:
                            if isinstance(gizmo, UV_GT_zenuv_transform_a_handle):
                                if b_is_setup:
                                    self.handle_action = "FIT_TO_SELECTION_PIVOT_CENTER" if b_is_command else "FIT_TO_SELECTION"
                                elif b_is_transform:
                                    if b_is_command:
                                        self.handle_action = "GET_TD"
                                    else:
                                        self.scale_by_td(context, tool_props)
                            elif isinstance(gizmo, UV_GT_zenuv_transform_pivot):
                                if b_is_setup:
                                    self.handle_action = "FIT_TO_ISLAND_PIVOT_CENTER" if b_is_command else "FIT_TO_ISLAND"
                                elif b_is_transform:
                                    if b_is_command:
                                        pass
                                    else:
                                        self.rotate_by_world_orient_angle(context, tool_props)
                            elif isinstance(gizmo, UV_GT_zenuv_draggable_line):
                                self.line_lock_along_axis = not tool_props.tr_gizmo_line_lock_along_axis
                                self.handle_action = "SET_LINE_LOCK_ALONG_AXIS"
                            elif isinstance(gizmo, UV_GT_zenuv_scale_handle):
                                self.scale_by_action(context, tool_props, gizmo.gizmo_axes_lock)
                            elif isinstance(gizmo, UV_GT_zenuv_rotate_handle):
                                angle_rad = math.radians(ZUV_GGT_UVTransformGizmo.get_gizmo_dial_step_angle(tool_props))
                                self.rotate_by_action(context, tool_props, angle_rad if b_is_command else -angle_rad)
                            break
            return self.execute(context)
        except TransformClickError as e:
            self.report({"INFO"}, str(e))
        except Exception as e:
            self.report({"ERROR"}, f"Transform Click: {str(e)}")
        return {'CANCELLED'}

    def execute(self, context: bpy.types.Context):
        try:

            def handle_fit_to_selection(res):
                if 'FINISHED' not in res:
                    if ZUV_OP_ToolTransformFitToSelection.info_message:
                        self.report({"WARNING"}, f"Zen UV: {ZUV_OP_ToolTransformFitToSelection.info_message}.")

            p_scene = context.scene
            tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

            if self.handle_action == "FIT_TO_SELECTION":
                if bpy.ops.uv.zenuv_tool_transform_fit_to_selection.poll():
                    tool_props.tr_gizmo_auto_setup_by_selection = False
                    res = bpy.ops.uv.zenuv_tool_transform_fit_to_selection(
                        'INVOKE_DEFAULT',
                        True,
                        influence='SELECTION', pivot_in_center=False, allow_toggle_direction=True)
                    handle_fit_to_selection(res)
                    return res
            elif self.handle_action == "FIT_TO_SELECTION_PIVOT_CENTER":
                if bpy.ops.uv.zenuv_tool_transform_fit_to_selection.poll():
                    tool_props.tr_gizmo_auto_setup_by_selection = False
                    res = bpy.ops.uv.zenuv_tool_transform_fit_to_selection(
                        'INVOKE_DEFAULT',
                        True,
                        influence='SELECTION', pivot_in_center=True, allow_toggle_direction=True)
                    handle_fit_to_selection(res)
                    return res
            elif self.handle_action == "FIT_TO_ISLAND":
                if bpy.ops.uv.zenuv_tool_transform_fit_to_selection.poll():
                    tool_props.tr_gizmo_auto_setup_by_selection = False
                    res = bpy.ops.uv.zenuv_tool_transform_fit_to_selection(
                        'INVOKE_DEFAULT',
                        True,
                        influence='ISLAND', pivot_in_center=False, allow_toggle_direction=True)
                    handle_fit_to_selection(res)
                    return res
            elif self.handle_action == "FIT_TO_ISLAND_PIVOT_CENTER":
                if bpy.ops.uv.zenuv_tool_transform_fit_to_selection.poll():
                    tool_props.tr_gizmo_auto_setup_by_selection = False
                    res = bpy.ops.uv.zenuv_tool_transform_fit_to_selection(
                        'INVOKE_DEFAULT',
                        True,
                        influence='ISLAND', pivot_in_center=True, allow_toggle_direction=True)
                    handle_fit_to_selection(res)
                    return res
            elif self.handle_action == "GET_TD":
                if bpy.ops.uv.zenuv_get_texel_density.poll():
                    return bpy.ops.uv.zenuv_get_texel_density(True)
            elif self.handle_action == "SET_TRANSFORM":
                x0, y0, x1, y1, x2, y2, x3, y3, is_pivot = self.transform_data

                tool_props.tr_gizmo_set_location_with_transform(
                    context,
                    origin_pivot=(x0, y0),
                    origin_head=(x1, y1),
                    matched_pivot=(x2, y2),
                    matched_head=(x3, y3),
                    is_pivot=bool(is_pivot),
                    axes_lock_mode=self.transform_axis_lock_mode)

                return {'FINISHED'}
            elif self.handle_action == "SET_LINE_LOCK_ALONG_AXIS":
                tool_props.tr_gizmo_line_lock_along_axis = self.line_lock_along_axis
                tool_props.tr_gizmo_active = False

                return {'FINISHED'}
            elif self.handle_action == "SET_SETUP":
                tool_props.tr_gizmo_auto_setup_by_selection = False
                x0, y0, x1, y1, x2, y2, x3, y3, is_pivot = self.transform_data

                tool_props.tr_gizmo_set_location(
                    context,
                    pivot=(x2, y2),
                    handle=(x3, y3),
                    is_pivot=bool(is_pivot))

                return {'FINISHED'}
        except Exception as e:
            self.report({"ERROR"}, str(e))

        return {'CANCELLED'}


class ZUV_OT_ToolTransformHandle(bpy.types.Operator):
    bl_idname = 'zenuv.tool_transform_handle'
    bl_label = 'Transform Handle'
    bl_description = "Rotate selected islands or selection by handle direction"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.StringProperty(
        name='Handle Direction',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    transform_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("DEFAULT", "Default", ""),
            ("FLIP", "Flip", ""),
        ],
        default="DEFAULT",
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        return context.space_data.type == 'IMAGE_EDITOR' and ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context)

    @classmethod
    def description(cls, context: bpy.types.Context, properties):
        if properties:
            from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps
            p_scene = context.scene
            p_tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
            s_influence = bpy.types.UILayout.enum_item_name(p_tool_props, "tr_gizmo_influence", p_tool_props.tr_gizmo_influence).lower()
            s_direction = TransformSysOpsProps.get_align_direction_description(properties.direction).lower()
            if p_tool_props.tr_gizmo_mode == "SETUP":
                return f"Rotate angle handle by {s_direction} direction"
            else:
                return (
                    f"Rotate {s_influence} by {s_direction} direction\n"
                    f"* Ctrl - Flip {s_influence} by {s_direction} direction"
                )
        return ""

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool
        p_tool_props.tr_gizmo_undo_push(commit_in_blender=True)

        self.transform_mode = "DEFAULT"
        if p_tool_props.tr_gizmo_mode == 'TRANSFORM':
            if event.ctrl:
                self.transform_mode = "FLIP"

        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        from ZenUV.utils.transform import matrix_by_image_aspect
        try:
            p_scene = context.scene
            p_tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

            if self.transform_mode == "FLIP":
                from ZenUV.ops.transform_sys.transform_utils.tr_utils import TrConstants
                p_handle = Vector(p_tool_props.tr_gizmo_pivot_handle)
                a_handle = Vector(p_tool_props.tr_gizmo_angle_handle)

                center = p_handle.to_3d()

                p_scale_vec = TrConstants.flip_vector[self.direction]
                S = Matrix.Diagonal(p_scale_vec)
                translation_to_zero = Matrix.Translation(-center)
                translation_back = Matrix.Translation(center)
                M = translation_back @ S.to_4x4() @ translation_to_zero

                # NOTE: we need to clear storage to update loops
                transform_object_loop_data.object_storage.clear()

                # NOTE: do not use 'INVOKE'
                res = bpy.ops.uv.zenuv_tool_transform(
                    influence=p_tool_props.tr_gizmo_influence,
                    use_falloff=False,
                    transform_sca_matrix=M
                )

                if 'FINISHED' in res:
                    p_tool_props.tr_gizmo_set_location_by_active_type(
                        context,
                        p_handle,
                        (M @ a_handle.to_3d()).to_2d()
                    )

                return {'FINISHED'}

            image_aspect_ratio = 1.0
            p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
            if p_image and p_image.size[0] > 0 and p_image.size[1] > 0:
                image_aspect_ratio = p_image.size[0] / p_image.size[1]
            AM = matrix_by_image_aspect(image_aspect_ratio)
            AM_inv = AM.inverted()

            p_handle = Vector(p_tool_props.tr_gizmo_pivot_handle)
            a_handle = Vector(p_tool_props.tr_gizmo_angle_handle)

            handled_vec = AM @ (a_handle - p_handle)

            direction: Vector = (getattr(UV_AREA_BBOX, self.direction) - UV_AREA_BBOX.cen).normalized()
            p_new_location = p_handle + AM_inv @ (direction * handled_vec.magnitude)

            p_tool_props.tr_gizmo_set_location_with_transform(
                context,
                p_handle,
                a_handle,
                p_handle,
                p_new_location,
                is_pivot=False
            )

            from .uv.uv_transform_gizmo import update_transform_gizmo_selection_center
            update_transform_gizmo_selection_center(context)

            return {'FINISHED'}

        except Exception as e:
            self.report({'WARNING'}, str(e))

        return {'CANCELLED'}


class ZUV_OP_ToolTransformMouseDraw(bpy.types.Operator):
    bl_description = 'Draw UV transform gizmo using mouse'
    bl_idname = "uv.zenuv_tool_transform_mouse_draw"
    bl_label = "Draw Transform Gizmo"
    bl_options = {'INTERNAL', 'UNDO'}  # NOTE: do not remove 'UNDO' !!!

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        return context.space_data.type == 'IMAGE_EDITOR' and ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context)

    def __del__(self):
        self.cancel(bpy.context)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.area_ptr = None
        self.is_transforming = False
        self.init_cursor_location = Vector((0, 0))
        self.last_update = 0
        self.init_mouse = Vector((0, 0))
        self.init_origin = Vector((0, 0))
        self.lock_axis = ""
        self.margin = 0

    def is_valid_context(self, context: bpy.types.Context):
        if self.area_ptr is not None and hasattr(context, 'area') and context.area is not None:
            return self.area_ptr == context.area.as_pointer()

    def modal(self, context, event: bpy.types.Event):

        from .uv.uv_transform_gizmo import ZUV_GGT_UVTransformGizmo

        b_is_cancelled = (
            event.type in {'RIGHTMOUSE', 'ESC'} or
            bpy.app.driver_namespace.get(ZUV_OP_ToolTransformMouseDraw.bl_idname, Ellipsis) != ZenPolls.SESSION_UUID
            or not self.is_valid_context(context)
        )

        if b_is_cancelled:
            self.cancel(context)
            return {'CANCELLED'}

        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        b_is_transform = tool_props.tr_gizmo_mode == 'TRANSFORM'

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                v_mouse_rgn = Vector((event.mouse_region_x, event.mouse_region_y))
                v_mouse = Vector(context.region.view2d.region_to_view(v_mouse_rgn.x, v_mouse_rgn.y))

                v_view_1px = get_view_1px_from_region(context, v_mouse_rgn)
                b_tweak_snap = event.ctrl
                v_mouse = transform_object_loop_data.get_snap_point_view(
                    context, v_mouse, v_view_1px, b_tweak_snap, snap_threshold_px=15
                )

                self.is_transforming = False

                if b_is_transform:
                    wm = context.window_manager
                    op_transform: ZUV_OP_ToolTransform = wm.operator_properties_last(ZUV_OP_ToolTransform.bl_idname)
                    if op_transform:
                        res_fit = bpy.ops.uv.zenuv_tool_transform_fit_to_selection(
                            influence=tool_props.tr_gizmo_influence,
                            direction='ALONG',
                            pivot_in_center=False
                        )
                        if 'FINISHED' in res_fit:
                            # NOTE: at this moment we can grab A-Handle and Pivot after setting to selection
                            v_angle_delta = Vector(tool_props.tr_gizmo_angle_handle) - Vector(tool_props.tr_gizmo_pivot_handle)

                            # NOTE: we are moving our transform line to cursor position
                            #       Pivot is moved to mouse position and A-Handle by previous delta
                            v_origin_pivot = v_mouse
                            v_origin_handle = v_mouse + v_angle_delta

                            self.init_origin = Vector(tool_props.tr_gizmo_pivot_handle)

                            op_transform.origin_pivot = v_origin_pivot.to_tuple()
                            op_transform.origin_head = v_origin_handle.to_tuple()

                            objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
                            if len(objs) > 0:
                                n_loops = transform_object_loop_data.setup_uvs(context, objs, tool_props.tr_gizmo_influence, use_kdtree=True)
                                if n_loops > 0:
                                    self.is_transforming = True
                                else:
                                    self.report({'WARNING'}, "Nothing is selected!")
                            else:
                                self.report({'WARNING'}, 'There are no selected objects!')
                        else:
                            self.report({'WARNING'}, "Can not calculate selection for transformation!")
                else:
                    # NOTE: SETUP
                    self.is_transforming = True
            elif event.value == 'RELEASE':
                if self.is_transforming:
                    self.cancel(context)
                    return {'FINISHED'}

            # NOTE: at this moment we are starting to draw from 1 mouse point
            tool_props.tr_gizmo_set_location(
                context,
                pivot=v_mouse.to_tuple(),
                handle=v_mouse.to_tuple(),
                is_pivot=False)

            context.area.tag_redraw()

            # NOTE: in this case we just working as in setup mode
            if not self.is_transforming:
                if b_is_transform:
                    b_is_transform = False
                    tool_props.tr_gizmo_mode = 'SETUP'

            self.init_cursor_location = v_mouse.copy()
            self.last_update = timer()
            self.init_mouse = v_mouse_rgn.copy()

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        elif event.type == 'X' and event.value == 'PRESS':
            self.lock_axis = 'AXIS_LOCK_SCALE_X' if self.lock_axis != 'AXIS_LOCK_SCALE_X' else ''
            tool_props.tr_gizmo_display_xy_guidelines = (False, True) if self.lock_axis else (False, False)

        elif event.type == 'Y' and event.value == 'PRESS':
            self.lock_axis = 'AXIS_LOCK_SCALE_Y' if self.lock_axis != 'AXIS_LOCK_SCALE_Y' else ''
            tool_props.tr_gizmo_display_xy_guidelines = (True, False) if self.lock_axis else (False, True)

        elif event.type == 'RET' and event.value == 'PRESS':
            if self.is_transforming:
                self.cancel(context)
                return {'FINISHED'}

        elif event.type == 'MOUSEMOVE':
            if self.is_transforming:
                if timer() - self.last_update >= 1/60:
                    rgn2d = context.region.view2d

                    # NOTE: region data is not used for calculations,
                    #       just to display in area header pixel offset
                    v_mouse_rgn = Vector((event.mouse_region_x, event.mouse_region_y))
                    v_mouse = Vector(rgn2d.region_to_view(x=v_mouse_rgn.x, y=v_mouse_rgn.y))
                    v_view_1px = get_view_1px_from_region(context, v_mouse_rgn)

                    b_tweak_snap = event.ctrl

                    v_snapped_view = transform_object_loop_data.get_snap_point_view(
                        context, v_mouse, v_view_1px, b_tweak_snap, snap_threshold_px=ZUV_GGT_UVTransformGizmo.gizmo_snap_threshold_px
                    )

                    if v_snapped_view != v_mouse:
                        if tool_props.tr_gizmo_draw_use_snap_margin and self.margin:
                            pass
                        else:
                            if not tool_props.tr_gizmo_draw_allow_merge:
                                v_snapped_view += Vector((0.000001, 0.000001))

                    v_mouse = v_snapped_view

                    if self.lock_axis == 'AXIS_LOCK_SCALE_X':
                        v_mouse.y = self.init_cursor_location.y
                    elif self.lock_axis == 'AXIS_LOCK_SCALE_Y':
                        v_mouse.x = self.init_cursor_location.x

                    tool_props.tr_gizmo_set_location(
                        context,
                        pivot=self.init_cursor_location.to_tuple(),
                        handle=v_mouse.to_tuple(),
                        is_pivot=False)

                    if b_is_transform:
                        wm = context.window_manager
                        op_transform = wm.operator_properties_last(ZUV_OP_ToolTransform.bl_idname)
                        if op_transform:

                            p_origin = Vector(op_transform.origin_pivot)
                            a_origin = Vector(op_transform.origin_head)

                            p_matched = Vector(op_transform.origin_pivot)
                            a_matched = Vector(v_mouse)

                            if tool_props.tr_gizmo_draw_use_snap_margin and self.margin:
                                v_margin_vec = (a_matched - p_matched).normalized() * self.margin
                                p_matched += v_margin_vec
                                a_matched -= v_margin_vec

                            p_axis_lock = ZuvTransformGizmoAxisLockPreset()
                            p_axis_lock.setup_by_gizmo_lock(self.lock_axis)
                            p_axis_lock.save_to_operator(op_transform)

                            op_transform.origin_pivot = p_origin
                            op_transform.origin_head = a_origin
                            op_transform.matched_pivot = p_matched
                            op_transform.matched_head = a_matched

                            op_transform.is_pivot = False

                            op_transform.preprocessing_offset = (op_transform.origin_pivot - self.init_origin)[:]

                            ZUV_OP_ToolTransform.calculate_transform_matrix(op_transform, context)

                            bpy.ops.uv.zenuv_tool_transform(
                                influence=tool_props.tr_gizmo_influence,

                                transform_pos_matrix=op_transform.transform_pos_matrix,
                                transform_rot_matrix=op_transform.transform_rot_matrix,
                                transform_sca_matrix=op_transform.transform_sca_matrix,
                            )

                            from ZenUV.prop.wm_props import ZuvWMTransformToolGroup
                            rotation_angle = ZuvWMTransformToolGroup.get_rotation_angle_by_operator(op_transform)
                            scale_value = ZuvWMTransformToolGroup.get_scale_value_by_operator(op_transform)
                            s_header_text = f"Rotation: {math.degrees(rotation_angle):.1f}°, Scale: {scale_value:.2f}"

                            if self.lock_axis == 'AXIS_LOCK_SCALE_X':
                                s_header_text += " along X"
                            elif self.lock_axis == 'AXIS_LOCK_SCALE_Y':
                                s_header_text += " along Y"

                            b_is_snap_enabled = is_uv_snap_enabled(p_scene, b_tweak_snap)

                            if b_is_snap_enabled:
                                s_header_text += " with snap"

                            context.area.header_text_set(s_header_text)

                            context.workspace.status_text_set(
                                lambda self, context: zenuv_status_text_transform_draw(self, context, b_is_snap_enabled)
                            )
                        else:
                            # NOTE: this must not occur !
                            Log.error("RETRIEVE TRANSFORM OPERATOR FAILED!")

                            context.area.header_text_set("Transform operator error!")
                            context.workspace.status_text_set("Transform operator error!")
                    else:
                        rotation_angle = tool_props.tr_gizmo_angle
                        scale_value = tool_props.tr_gizmo_distance

                        s_header_text = f"Rotation: {math.degrees(rotation_angle):.1f}°, Scale: {scale_value:.2f}"

                        if self.lock_axis == 'AXIS_LOCK_SCALE_X':
                            s_header_text += " along X"
                        elif self.lock_axis == 'AXIS_LOCK_SCALE_Y':
                            s_header_text += " along Y"

                        b_is_snap_enabled = is_uv_snap_enabled(p_scene, b_tweak_snap)

                        if b_is_snap_enabled:
                            s_header_text += " with snap"

                        context.area.header_text_set(s_header_text)

                        context.workspace.status_text_set(
                            lambda self, context: zenuv_status_text_transform_draw(self, context, b_is_snap_enabled)
                        )

                    self.last_update = timer()

        context.window.cursor_modal_set('PAINT_BRUSH')

        return {'RUNNING_MODAL'}

    @classmethod
    def is_modal_draw_active(cls):
        return cls.bl_idname in bpy.app.driver_namespace

    def invoke(self, context, event):
        # NOTE: is already running
        if ZUV_OP_ToolTransformMouseDraw.is_modal_draw_active():
            return {'CANCELLED'}

        if context.area.type == 'IMAGE_EDITOR':
            p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool

            if p_tool_props.tr_gizmo_mode == 'TRANSFORM':
                from ZenUV.utils.selection_utils import SelectionProcessor
                if not SelectionProcessor.is_uv_selected(context):
                    self.report({'WARNING'}, "Select something to draw with transformation!")
                    return {'CANCELLED'}

            self.is_transforming = False
            self.lock_axis = ""

            self.margin = 0

            if p_tool_props.tr_gizmo_draw_use_snap_margin:
                from ZenUV.prop.zuv_preferences import get_prefs
                addon_prefs = get_prefs()
                if addon_prefs.uv_borders_draw.mode == 'PACK_MARGIN':
                    from ZenUV.utils.generic import get_padding_in_pct
                    self.margin = (
                        get_padding_in_pct(context, addon_prefs.margin_px)
                        if addon_prefs.margin_show_in_px else addon_prefs.margin)
                elif addon_prefs.uv_borders_draw.mode == 'USER_MARGIN':
                    self.margin = addon_prefs.uv_borders_draw.user_margin * 0.01

            # NOTE: we must force disable gizmo transformations
            p_tool_props.tr_gizmo_active = False

            p_tool_props.tr_gizmo_undo_push(commit_in_blender=True)

            objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
            if len(objs) > 0:
                transform_object_loop_data.setup_full_kdtree(context, objs)

            bpy.app.driver_namespace[ZUV_OP_ToolTransformMouseDraw.bl_idname] = ZenPolls.SESSION_UUID
            self.area_ptr = context.area.as_pointer()
            # Ensure the operator is started in the UV editor
            context.window_manager.modal_handler_add(self)

            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "This operator works only in the UV Editor")
            return {'CANCELLED'}

    def cancel(self, context: bpy.types.Context):
        # NOTE: check is operator is running
        if ZUV_OP_ToolTransformMouseDraw.is_modal_draw_active():
            del bpy.app.driver_namespace[ZUV_OP_ToolTransformMouseDraw.bl_idname]

            p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool
            p_tool_props.tr_gizmo_display_xy_guidelines = (False, False)

            self.is_transforming = False

            if context.window:
                context.window.cursor_modal_restore()
            if context.workspace:
                context.workspace.status_text_set(None)
            if hasattr(context, "area") and context.area:
                context.area.header_text_set(None)
                context.area.tag_redraw()


class ZUV_OP_ToolTransformFitToSelection(bpy.types.Operator):
    bl_idname = "uv.zenuv_tool_transform_fit_to_selection"
    bl_label = "Fit Transform Gizmo"
    bl_description = 'Fit UV transform gizmo to islands or selection'
    bl_options = {'REGISTER', 'UNDO'}

    influence: bpy.props.EnumProperty(
        name='Influence',
        description='Transform Influence. Affect Islands or Selection',
        items=[
            ("ISLAND", "Island", ""),
            ("SELECTION", "Selection", "")
        ],
        default='ISLAND'
    )

    direction: ZuvFitToSelectionProps.direction

    pivot_in_center: ZuvFitToSelectionProps.pivot_in_center

    allow_toggle_direction: bpy.props.BoolProperty(
        name="Toggle Direction",
        description="Enable toggling the gizmo direction between along and across the island",
        default=False
    )

    # NOTE: this must be a class property, because 'StringProperty' is not saved if cancelled
    info_message: str = ""

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        return context.space_data.type == 'IMAGE_EDITOR' and ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context)

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        if properties:
            return cls.bl_description + f' {properties.direction.lower()} the {properties.influence.lower()}{f" with pivot in {properties.influence.lower()} center" if properties.pivot_in_center else ""}'
        return cls.bl_description + ' to selection'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool
        p_tool_props.tr_gizmo_undo_push(commit_in_blender=True)
        p_tool_props.tr_gizmo_auto_setup_by_selection = False
        return self.execute(context)

    def execute(self, context):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        from ZenUV.prop.scene_ui_props import ZUV_UVToolProps
        from ZenUV.ops.transform_sys.transform_utils.tr_object_data import get_uv_islands_loops, get_selection_loops
        from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
        from ZenUV.utils.bounding_box import BoundingBox2dSimple, BoundingBoxUtils

        ZUV_OP_ToolTransformFitToSelection.info_message = ""

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)

        if not len(objs):
            ZUV_OP_ToolTransformFitToSelection.info_message = "There are no selected objects"
            self.report({'INFO'}, f"Zen UV: {ZUV_OP_ToolTransformFitToSelection.info_message}.")
            return {'CANCELLED'}

        p_active_space = None
        if context.area and context.area.type == 'IMAGE_EDITOR':
            p_active_space = context.area.spaces.active

        if p_active_space is None:
            ZUV_OP_ToolTransformFitToSelection.info_message = "Current area is not UV Editor type"
            self.report({'INFO'}, f"Zen UV: {ZUV_OP_ToolTransformFitToSelection.info_message}.")
            return {'CANCELLED'}

        p_scene = context.scene
        tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

        image_aspect_ratio = 1.0
        p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
        if p_image and p_image.size[0] > 0 and p_image.size[1] > 0:
            image_aspect_ratio = p_image.size[0] / p_image.size[1]

        p_chain_loops = []

        for obj in objs:
            me: bpy.types.Mesh = obj.data
            bm = bmesh.from_edit_mesh(me)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            p_loops = (
                get_uv_islands_loops(context, me, bm, uv_layer, return_unselected=False)[0].values()
                if self.influence == 'ISLAND' else
                get_selection_loops(context, me, bm, uv_layer, return_unselected=False)[0].values()
            )
            if p_loops:
                p_chain_loops.extend(p_loops)

        if not p_chain_loops:
            ZUV_OP_ToolTransformFitToSelection.info_message = "Select something"
            self.report({'WARNING'}, f"Zen UV: {ZUV_OP_ToolTransformFitToSelection.info_message}.")
            return {'CANCELLED'}

        bbox = BoundingBox2dSimple(points=p_chain_loops)
        if bbox.len_x == 0.0 and bbox.len_y == 0.0:
            ZUV_OP_ToolTransformFitToSelection.info_message = "Select more than 1 vertex"
            self.report({'WARNING'}, f"Zen UV: {ZUV_OP_ToolTransformFitToSelection.info_message}.")
            return {'CANCELLED'}

        translation_to_zero = Matrix.Translation(-bbox.center.to_3d())
        translation_back = Matrix.Translation(bbox.center.to_3d())
        angle = BoundingBoxUtils.get_orient_angle(bbox, image_aspect_ratio)
        R = TransformLoops._get_rotation_matrix(angle, image_aspect_ratio)
        bbox = BoundingBoxUtils.rotate_by_matrix(bbox, R)
        transformation_matrix = translation_back @ R.to_4x4() @ translation_to_zero

        align_direction = 'ALONG' if bbox.len_x > bbox.len_y else 'ACROSS'

        v1, v2 = self.get_coordinates(bbox, align_direction)

        if v1 == v2:
            v1, v2 = self.get_coordinates(bbox, s_direction='ACROSS' if align_direction == 'ALONG' else 'ALONG')
            self.report({'WARNING'}, f"Zen UV: It is not possible to set the direction {align_direction.lower()}")

        if self.allow_toggle_direction:
            p_key = align_direction == 'ALONG'
            a_handle_position, p_handle_position = [(transformation_matrix.inverted() @ v).to_2d() for v in [v1.to_3d(), v2.to_3d()]]
            ph_pos, ah_pos = tool_props.tr_gizmo_pivot_handle, tool_props.tr_gizmo_angle_handle
            if self.pivot_in_center:
                p_handle_position = (transformation_matrix.inverted() @ bbox.center.to_3d()).to_2d()
                if ph_pos[:] == p_handle_position[:] and ah_pos[:] == a_handle_position[:]:
                    align_direction = 'ALONG' if not p_key else 'ACROSS'
                    v1, v2 = self.get_coordinates(bbox, align_direction)
                    a_handle_position = (transformation_matrix.inverted() @ v1.to_3d()).to_2d()
            else:
                if ph_pos[:] == p_handle_position[:] and ah_pos[:] == a_handle_position[:]:
                    align_direction = 'ALONG' if not p_key else 'ACROSS'
                    v1, v2 = self.get_coordinates(bbox, align_direction)
                    a_handle_position, p_handle_position = [(transformation_matrix.inverted() @ v).to_2d() for v in [v1.to_3d(), v2.to_3d()]]
        else:
            v1, v2 = self.get_coordinates(bbox, align_direction)
            a_handle_position, p_handle_position = [(transformation_matrix.inverted() @ v).to_2d() for v in [v1.to_3d(), v2.to_3d()]]

            if self.pivot_in_center:
                p_handle_position = (transformation_matrix.inverted() @ bbox.center.to_3d()).to_2d()

        tool_props.tr_gizmo_set_location(
            context, pivot=p_handle_position, handle=a_handle_position, is_pivot=True)

        context.area.tag_redraw()

        return {'FINISHED'}

    def get_coordinates(self, bbox: BoundingBox2d, s_direction: str = ''):
        if s_direction == 'ALONG':
            return (bbox.right_center, bbox.left_center) if self.direction == 'ALONG' else (bbox.top_center, bbox.bot_center)
        elif s_direction == 'ACROSS':
            return (bbox.top_center, bbox.bot_center) if self.direction == 'ALONG' else (bbox.right_center, bbox.left_center)


class ZUV_OP_ToolTransformSwapHandles(bpy.types.Operator):
    bl_idname = "uv.zenuv_tool_transform_swap_handles"
    bl_label = "Swap Handles"
    bl_description = 'Swap transform gizmo pivot and angle handles'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        return context.space_data.type == 'IMAGE_EDITOR' and ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool
        p_tool_props.tr_gizmo_undo_push(commit_in_blender=True)
        return self.execute(context)

    def execute(self, context):
        p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool
        x0, y0, x1, y1 = p_tool_props.tr_gizmo_line
        p_tool_props.tr_gizmo_active = False
        p_tool_props.tr_gizmo_auto_setup_by_selection = False
        p_tool_props.tr_gizmo_set_location_by_active_type(context, (x1, y1), (x0, y0))

        return {'FINISHED'}


class ZUV_OP_ToolTransformSetPerpendicular(bpy.types.Operator):
    bl_idname = "uv.zenuv_tool_transform_set_perpendicular"
    bl_label = "Set Perpendicular"
    bl_description = 'Set the gizmo perpendicular to its current orientation while preserving its length'
    bl_options = {'REGISTER', 'UNDO'}

    gizmo_length: bpy.props.FloatProperty(
        name="Gizmo Length",
        description="Adjusts the gizmo length as a percentage, where 1 represents the original gizmo length",
        default=0.5
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        return context.space_data.type == 'IMAGE_EDITOR' and ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool
        p_tool_props.tr_gizmo_undo_push(commit_in_blender=True)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        from ZenUV.utils.transform import matrix_by_image_aspect

        image_aspect_ratio = calc_uv_editor_image_aspect_ratio(context)

        AM = matrix_by_image_aspect(image_aspect_ratio)

        p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool
        p_tool_props.tr_gizmo_auto_setup_by_selection = False
        x0, y0, x1, y1 = p_tool_props.tr_gizmo_line
        pivot = AM @ Vector((x0, y0))
        gizmo_vec = AM @ Vector((x1, y1)) - pivot
        position = pivot + gizmo_vec * 0.5
        new_vec = position + gizmo_vec.normalized().orthogonal() * (gizmo_vec.length * self.gizmo_length)
        p_tool_props.tr_gizmo_active = False
        p_tool_props.tr_gizmo_set_location_by_active_type(context, AM.inverted() @ position, AM.inverted() @ new_vec)

        return {'FINISHED'}


class ZUV_OP_ToolTransformSetEnum(bpy.types.Operator):
    bl_idname = "uv.zenuv_tool_transform_enum"
    bl_label = "Set Transform Enum"
    bl_description = 'Set enum value in transform mode'
    bl_options = {'INTERNAL'}

    data_path: rna_path_prop
    value: bpy.props.StringProperty(
        name="Value",
        description="Assignment value (as a string)",
        maxlen=1024,
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            from bl_operators.wm import WM_OT_context_set_enum
            return WM_OT_context_set_enum.description(properties)
        return ""

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool
        return (
            p_tool_props.tr_gizmo_mode == 'TRANSFORM' and
            context.space_data.type == 'IMAGE_EDITOR' and
            ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context))

    def execute(self, context):
        p_tool_props: ZUV_UVToolProps = context.scene.zen_uv.ui.uv_tool

        bpy.ops.wm.context_set_enum(
            data_path=self.data_path,
            value=self.value
        )

        if self.data_path.endswith('tr_gizmo_event_mode'):
            if p_tool_props.tr_gizmo_event_mode != 'DEFAULT':
                p_layout_cls = bpy.types.UILayout
                s_operation = p_layout_cls.enum_item_name(
                    p_tool_props, "tr_gizmo_event_mode", p_tool_props.tr_gizmo_event_mode)
                s_influence = p_layout_cls.enum_item_name(
                    p_tool_props, "tr_gizmo_influence", p_tool_props.tr_gizmo_influence
                )
                context.area.header_text_set(f"Press Left Mouse to {s_operation} UV {s_influence} ...")

                def zenuv_transform_event_mode_draw(self, context: bpy.types.Context):
                    layout: bpy.types.UILayout = self.layout
                    layout.label(icon="MOUSE_LMB")
                    layout.label(text=f"{s_operation} {s_influence}")

                context.workspace.status_text_set(zenuv_transform_event_mode_draw)
            else:
                context.workspace.status_text_set(None)
                context.area.header_text_set(None)

        update_areas_in_all_screens(context)

        return {'FINISHED'}


class ZUV_OP_ToolTransformSetupModal(bpy.types.Operator):
    bl_idname = "uv.zenuv_tool_transform_setup_modal"
    bl_label = 'Setup UV Transform Gizmo Modal'
    bl_description = 'Setup UV Transform Gizmo Modal'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        from ZenUV.ui.tool.uv.uv_transform_tool import ZuvUVTransformWorkSpaceTool
        return context.space_data.type == 'IMAGE_EDITOR' and ZuvUVTransformWorkSpaceTool.is_workspace_tool_active(context)

    def __del__(self):
        self.cancel(bpy.context)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.space: bpy.types.SpaceImageEditor = None
        self.cursor_location = Vector((0, 0))
        self._timer = None
        self.gizmo_type = ''

    def is_valid_context(self, context: bpy.types.Context):
        if self.area_ptr is not None and hasattr(context, 'area') and context.area is not None:
            return self.area_ptr == context.area.as_pointer()

    def modal(self, context, event: bpy.types.Event):

        b_is_cancelled = (
            event.type in {'RIGHTMOUSE', 'ESC'} or
            (event.type == 'LEFTMOUSE' and event.value == 'RELEASE') or
            bpy.app.driver_namespace.get(ZUV_OP_ToolTransformSetupModal.bl_idname, Ellipsis) != ZenPolls.SESSION_UUID
        )

        p_cursor_location = Vector(self.space.cursor_location)
        p_cursor_offset = p_cursor_location - self.cursor_location
        if p_cursor_offset.length != 0.0:
            self.cursor_location = p_cursor_location

            from .uv.uv_transform_gizmo import ZUV_GGT_UVTransformGizmo

            p_scene = context.scene
            tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
            if 'LINE' in self.gizmo_type:
                ZUV_GGT_UVTransformGizmo.zenuv_setup_transform_gizmo_line(
                    tool_props, p_cursor_location, p_cursor_offset
                )
            else:
                s_gizmo_id = 'tr_gizmo_pivot_handle' if tool_props.tr_gizmo_is_pivot else 'tr_gizmo_angle_handle'
                ZUV_GGT_UVTransformGizmo.zenuv_setup_transform_gizmo(tool_props, s_gizmo_id, p_cursor_location)

            tool_props.update_cursor_location_in_uv(context)
            context.area.tag_redraw()

        if b_is_cancelled:
            self.cancel(context)
            return {'CANCELLED', 'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    @classmethod
    def is_modal_active(cls):
        return cls.bl_idname in bpy.app.driver_namespace

    def invoke(self, context, event):
        # NOTE: is already running
        if ZUV_OP_ToolTransformSetupModal.is_modal_active():
            return {'CANCELLED'}

        if context.area.type == 'IMAGE_EDITOR':
            p_scene = context.scene
            tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool

            bpy.app.driver_namespace[ZUV_OP_ToolTransformSetupModal.bl_idname] = ZenPolls.SESSION_UUID
            self.space = context.space_data
            self.cursor_location = Vector(context.space_data.cursor_location[:])
            self.gizmo_type = tool_props.tr_gizmo_type

            # Ensure the operator is started in the UV editor
            wm = context.window_manager
            wm.modal_handler_add(self)

            self._timer = wm.event_timer_add(0.2, window=context.window)

            return {'RUNNING_MODAL', 'PASS_THROUGH'}
        else:
            self.report({'WARNING'}, "This operator works only in the UV Editor")
            return {'CANCELLED'}

    def cancel(self, context: bpy.types.Context):
        # NOTE: check is operator is running
        if ZUV_OP_ToolTransformSetupModal.is_modal_active():
            del bpy.app.driver_namespace[ZUV_OP_ToolTransformSetupModal.bl_idname]
        if hasattr(self, "_timer") and self._timer is not None:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self._timer = None
