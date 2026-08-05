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

# Copyright 2022, Alex Zhornyak

import bpy

import json
import shutil
from collections import defaultdict
from functools import partial
import numpy as np
from timeit import default_timer as timer

from .trimsheet_utils import ZuvTrimsheetUtils, TrimImportUtils

from ZenUV.utils.blender_zen_utils import (
    get_tools_region_width, get_ui_region_width,
    update_areas_in_all_screens, ZenPolls, ZenStrUtils, ZuvPresets)
from ZenUV.utils.vlog import Log
from ZenUV.utils.simple_geometry import Rectangle


class ZUV_PT_UVMathVisualizer(bpy.types.Panel):
    bl_label = "Zen UV Math"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_parent_id = "IMAGE_PT_annotation"

    def draw(self, context):
        layout = self.layout

        # NOTE: we need separate operators to have separate options in View3D, UV
        layout.operator('uv.zenuv_math_vis')


class ZUV_PT_3DVMathVisualizer(bpy.types.Panel):
    bl_label = "Zen UV Math"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "VIEW3D_PT_grease_pencil"

    def draw(self, context):
        layout = self.layout

        # NOTE: we need separate operators to have separate options in View3D, UV
        layout.operator('view3d.zenuv_math_vis')


class MathVizBase:
    bl_label = 'Math Vis'
    bl_description = 'Add vector or group of vectors to annotation for debugging math purposes'
    bl_options = {'REGISTER', 'UNDO'}

    co_name: bpy.props.StringProperty(
        name='Vec Name',
        description='Name of the vector or group of vectors',
        default='First Vector'
    )

    co_start: bpy.props.FloatVectorProperty(
        name='Vec Start', size=3, subtype='XYZ', default=(0, 0, 0))
    co_end: bpy.props.FloatVectorProperty(
        name='Vec End', size=3, subtype='XYZ', default=(1, 1, 0))

    frame_id: bpy.props.IntProperty(
        name='Frame ID',
        min=0,
        default=0
    )

    arrow_size: bpy.props.FloatProperty(
        name='Arrow Size',
        min=0,
        precision=3,
        default=0.005
    )

    is_constant_arrow_size:  bpy.props.BoolProperty(
        name='Constant Arrow Size',
        default=False
    )

    def execute(self, context: bpy.types.Context):
        from ZenUV.utils.annotations_toolbox.math_visualizer import MathVisualizer

        debugger = MathVisualizer(context)
        debugger.add_vector(
            self.co_name, self.frame_id, [(self.co_start, self.co_end)],
            clear=True,
            color=(1, 0, 0),
            is_constant_arrow_size=self.is_constant_arrow_size,
            arrow_size=self.arrow_size)

        return {'FINISHED'}


class ZUV_OT_View3DMathVis(bpy.types.Operator, MathVizBase):
    bl_idname = "view3d.zenuv_math_vis"


class ZUV_OT_UVMathVis(bpy.types.Operator, MathVizBase):
    bl_idname = "uv.zenuv_math_vis"


class ZUV_OT_TrimSetIndex(bpy.types.Operator):
    bl_idname = "wm.zuv_trim_set_index"
    bl_label = 'Set Trim Index'
    bl_description = 'Sets trimsheet active index'
    bl_options = {'REGISTER', 'UNDO'}

    trimsheet_index: bpy.props.IntProperty(
        name='Trimsheet Index',
        default=-1,
        min=-1,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    extend: bpy.props.BoolProperty(
        name='Extend Selection',
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    select: bpy.props.BoolProperty(
        name='Select Trim',
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):

        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            n_count = len(p_data.trimsheet)
            if self.trimsheet_index in range(n_count):
                if event.shift:
                    self.extend = True
                    self.select = not p_data.trimsheet[self.trimsheet_index].selected
                elif event.ctrl:
                    self.extend = True
                    self.select = False
                else:
                    self.select = True
                    self.extend = False

                return self.execute(context)
        return {'CANCELLED'}

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            n_count = len(p_data.trimsheet)
            if self.trimsheet_index in range(n_count):

                if not self.extend:
                    arr_selected = [False] * n_count
                    arr_selected[self.trimsheet_index] = self.select

                    # NOTE: foreach does not work if it is linked
                    if p_data.id_data and p_data.id_data.library:
                        for idx in range(n_count):
                            p_data.trimsheet[idx].selected = idx == self.trimsheet_index
                    else:
                        p_data.trimsheet.foreach_set("selected", arr_selected)

                    if p_data.trimsheet_index != self.trimsheet_index:
                        p_data.trimsheet_index = self.trimsheet_index
                else:
                    p_data.trimsheet[self.trimsheet_index].selected = self.select

                ZuvTrimsheetUtils.fix_undo()
                update_areas_in_all_screens(context)

                return {'FINISHED'}

        return {'CANCELLED'}


class ZuvTrimAddItemBase:
    bl_label = 'Add Trim'
    bl_description = 'Adds trim to trimsheet'
    bl_options = {'REGISTER', 'UNDO'}

    color: bpy.props.FloatVectorProperty(
        name="Color",
        description="Trim's color",
        subtype='COLOR',
        default=(0.0, 0.0, 0.0),
        size=3,
        min=0,
        max=1,
        options={'HIDDEN'}

    )

    def get_rectangle(self, context: bpy.types.Context):
        # left, top, right, bottom
        return (0.25, 0.75, 0.75, 0.25)

    def invoke(self, context, event):
        if self.color[:] == (0.0, 0.0, 0.0):
            p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
            if p_data is not None:
                self.color = ZuvTrimsheetUtils.getTrimsheetGeneratedColor(p_data.trimsheet)
        return self.execute(context)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            if self.color[:] == (0.0, 0.0, 0.0):
                self.color = ZuvTrimsheetUtils.getTrimsheetGeneratedColor(p_data.trimsheet)

            p_rect = self.get_rectangle(context)

            p_data.trimsheet.add()
            n_count = len(p_data.trimsheet)
            p_data.trimsheet[-1].create_uuid()
            p_data.trimsheet[-1].name_ex = 'Trim'
            p_data.trimsheet[-1].color = self.color
            p_data.trimsheet[-1].set_rectangle(*p_rect)
            p_data.trimsheet_index = n_count - 1

            p_data.trimsheet_mark_geometry_update()

            ZuvTrimsheetUtils.auto_highlight_trims(context)

            ZuvTrimsheetUtils.fix_undo()
            update_areas_in_all_screens(context)

            return {'FINISHED'}
        else:
            return {'CANCELLED'}


class ZUV_OT_TrimAddItem(bpy.types.Operator, ZuvTrimAddItemBase):
    bl_idname = "uv.zuv_trim_add"


class ZUV_OT_TrimAddSizedItem(bpy.types.Operator, ZuvTrimAddItemBase):
    bl_idname = "uv.zuv_trim_add_sized"

    size: bpy.props.FloatProperty(
        name='Size',
        description='Size of the Trim',
        min=0.0,
        default=0.0
    )

    def get_rectangle(self, context: bpy.types.Context):
        if context.area.type == 'IMAGE_EDITOR':
            region = context.region
            rgn2d = region.view2d
            n_panel_width = get_ui_region_width(context)
            tools_width = get_tools_region_width(context)
            free_zone = region.width - n_panel_width - tools_width

            trim_pos_x = tools_width + free_zone
            t_size = min(trim_pos_x, region.height) * 0.2

            trim_pos_x *= 0.5
            x, y, = rgn2d.region_to_view(trim_pos_x, region.height / 2)

            x_size, y_size, = rgn2d.region_to_view(trim_pos_x + t_size, y)
            if self.size == 0.0:
                t_size = (x - x_size) * 0.8
            else:
                t_size = self.size * 0.5

        else:
            x = y = 0.5
            if self.size == 0.0:
                t_size = 0.1
            else:
                t_size = self.size

        return (x - t_size, y + t_size, x + t_size, y - t_size)


class ZUV_OT_TrimRemoveItem(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_remove"
    bl_label = 'Remove Trim'
    bl_description = 'Remove active Trim from Trimsheet'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context: bpy.types.Context):
        return (
            ZuvTrimsheetUtils.isTrimsheetEditable(context) and
            ZuvTrimsheetUtils.getActiveTrim(context) is not None)

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            n_count = len(p_data.trimsheet)
            idx = p_data.trimsheet_index
            if idx in range(0, n_count):
                p_data.trimsheet.remove(idx)
                p_data.trimsheet_index = max(idx - 1, 0) if n_count > 1 else -1

                p_data.trimsheet_mark_geometry_update()
                ZuvTrimsheetUtils.fix_undo()
                ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

                return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_TrimRemoveItemUI(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_remove_ui"
    bl_label = 'Remove Trim'
    bl_description = (
        'Remove active Trim from Trimsheet\n'
        '* Shift - Remove selected Trims from Trimsheet')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context: bpy.types.Context):
        return (
            ZuvTrimsheetUtils.isTrimsheetEditable(context) and
            ZuvTrimsheetUtils.getTrimsheetSelectedAndActiveCount(context) > 0)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if event.shift:
            return bpy.ops.uv.zuv_trim_delete_all(use_dialog=False, mode='SELECTED')
        else:
            return bpy.ops.uv.zuv_trim_remove()


class ZUV_OT_TrimDuplicate(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_duplicate"
    bl_label = 'Duplicate Trim'
    bl_description = 'Duplicate active or selected Trims in Trimsheet'
    bl_options = {'REGISTER'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('ACTIVE', 'Active', 'Duplicate active trim'),
            ('SELECTED', 'Selected', 'Duplicate selected trims'),
        ],
        default='ACTIVE'
    )

    ignore_color: bpy.props.BoolProperty(
        name='Ignore Color',
        description='Does not copy trim color settings',
        default=True
    )
    clear_selection: bpy.props.BoolProperty(
        name="Clear Selection",
        description='Clears the trimsheet selection before applying the operation',
        default=True
    )

    @classmethod
    def poll(self, context: bpy.types.Context):
        return (
            ZuvTrimsheetUtils.isTrimsheetEditable(context) and
            ZuvTrimsheetUtils.getTrimsheetSelectedAndActiveCount(context) > 0)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):

        ZuvTrimsheetUtils.fix_undo()

        def clone_trim(p_source, p_idx, p_trimsheet):
            p_skipped = {'name', 'uuid'}
            if self.ignore_color:
                p_skipped.add('color')
                p_skipped.add('border_color')

            def fn_skip_prop(inst, attr):
                if inst == p_source and attr in p_skipped:
                    return True
                return False

            p_dict = p_source.to_dict(fn_skip_prop=fn_skip_prop)
            s_was_name = p_source.name

            p_trimsheet.add()
            p_trimsheet[-1].create_uuid()
            p_trimsheet[-1].color = ZuvTrimsheetUtils.getTrimsheetGeneratedColor(p_trimsheet)
            p_trimsheet[-1].from_dict(p_dict)
            p_trimsheet[-1].name_ex = s_was_name if 'copy' in s_was_name else (s_was_name + ' copy')
            p_trimsheet[-1].selected = True

            p_new_index = len(p_trimsheet) - 1
            if p_new_index - p_idx > 1:
                p_trimsheet.move(p_new_index, p_idx + 1)
                return p_trimsheet[p_idx + 1]
            else:
                return p_trimsheet[-1]

        p_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_owner:
            p_trimsheet = p_owner.trimsheet
            idx = p_owner.trimsheet_index
            p_first_uuid = None
            if self.mode == 'ACTIVE':
                p_trim = ZuvTrimsheetUtils.getActiveTrimFromOwner(p_owner)
                if p_trim:
                    p_cloned = clone_trim(p_trim, idx, p_trimsheet)
                    p_first_uuid = p_cloned.uuid
                    if self.clear_selection:
                        p_trim.selected = False
            else:
                p_indices = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)
                if self.clear_selection:
                    for it_idx in p_indices:
                        p_trimsheet[it_idx].selected = False

                for it_idx in reversed(p_indices):
                    p_cloned = clone_trim(p_trimsheet[it_idx], it_idx, p_trimsheet)
                    if p_first_uuid is None:
                        p_first_uuid = p_cloned.uuid

            if p_first_uuid is not None:
                new_idx = ZuvTrimsheetUtils.indexOfTrimByUuid(p_trimsheet, p_first_uuid)
                if p_owner.trimsheet_index != new_idx:
                    p_owner.trimsheet_index = new_idx

                p_owner.trimsheet_mark_geometry_update()

                ZuvTrimsheetUtils.auto_highlight_trims(context)

                ZuvTrimsheetUtils.fix_undo()
                update_areas_in_all_screens(context)
                bpy.ops.ed.undo_push(message='Duplicate Trim(s)')

                return {'FINISHED'}
            else:
                self.report({'INFO'}, 'Nothing selected to duplicate!')
        else:
            self.report({'INFO'}, 'No Trimsheet Data!')

        return {'CANCELLED'}


class ZUV_OT_TrimDeleteAll(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_delete_all"
    bl_label = 'Delete Trims'
    bl_description = 'Delete all, selected, duplicated or empty Trims'
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        description='Deletion trims mode',
        items=[
            ('ALL', 'All', 'Delete all trims in trimsheet'),
            ('SELECTED', 'Selected', 'Delete selected trims in trimsheet'),
            ('EMPTY', 'Empty', 'Delete trims with zero width or height'),
            ('DUPLICATES', 'Duplicates', 'Delete trims with duplicated dimensions'),
        ],
        default='ALL'
    )

    use_dialog: bpy.props.BoolProperty(
        name='Use Dialog',
        description='Call dialog to select properties',
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        col = layout.column(align=True)
        col.use_property_split = True
        col.prop(self, 'mode', expand=True)

    @classmethod
    def poll(self, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if self.use_dialog:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        else:
            return self.execute(context)

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            p_trimsheet = p_data.trimsheet
            n_count = len(p_trimsheet)
            if n_count > 0:
                if self.mode == 'ALL':
                    p_trimsheet.clear()
                elif self.mode == 'SELECTED':
                    for idx in reversed(ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)):
                        p_trimsheet.remove(idx)
                elif self.mode == 'EMPTY':
                    for idx in range(n_count - 1, -1, -1):
                        p_trim = p_trimsheet[idx]
                        if p_trim.is_empty():
                            p_trimsheet.remove(idx)
                elif self.mode == 'DUPLICATES':
                    # we use this approach to delete last duplicates
                    p_duplicates = defaultdict(list)
                    for idx, p_trim in enumerate(p_trimsheet):
                        left, top, right, bottom = p_trim.rect
                        p_rounded = (round(left, 3), round(top, 3), round(right, 3), round(bottom, 3))

                        p_duplicates[p_rounded].append(idx)

                    p_del_indices = set()
                    for v in p_duplicates.values():
                        if len(v) > 1:
                            p_del_indices.update(v[1:])

                    for idx in range(n_count - 1, -1, -1):
                        if idx in p_del_indices:
                            p_trimsheet.remove(idx)

                if p_data.trimsheet_index not in range(len(p_trimsheet)):
                    p_data.trimsheet_index = min(0, len(p_trimsheet) - 1)

                p_data.trimsheet_mark_geometry_update()
                ZuvTrimsheetUtils.fix_undo()
                ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

                return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_TrimCopyToClipboard(bpy.types.Operator):
    bl_idname = "uv.zuv_copy_trimsheet"
    bl_label = 'Copy'
    bl_description = 'Copy Trims to clipboard'
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('ACTIVE', 'Active', 'Copy active trim'),
            ('SELECTED', 'Selected', 'Copy selected trims'),
            ('ALL', 'All', 'Copy all trims in the trimsheet')
        ],
        default='ACTIVE'
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, 'mode', expand=True)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):

        p_out = ZuvTrimsheetUtils.export_to_json(context, self)
        if p_out:
            context.window_manager.clipboard = p_out
            return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_TrimPasteFromClipboard(bpy.types.Operator):
    bl_idname = "uv.zuv_paste_trimsheet"
    bl_label = 'Paste'
    bl_description = 'Paste Trims from clipboard'
    bl_options = {'REGISTER', 'UNDO'}

    mode: TrimImportUtils.paste_mode

    @classmethod
    def poll(self, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        col = layout.column(align=True)
        col.use_property_split = True
        col.prop(self, 'mode', expand=True)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        try:
            wm = context.window_manager
            json_data = wm.clipboard
            ZuvTrimsheetUtils.import_from_json(context, self, json_data)

            ZuvTrimsheetUtils.auto_highlight_trims(context)

            ZuvTrimsheetUtils.fix_undo()
            ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

            return {'FINISHED'}
        except json.decoder.JSONDecodeError as e:
            self.report({'ERROR'}, 'Invalid clipboard JSON: ' + str(e))
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_TrimMoveItem(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_move"
    bl_label = 'Move Trims Up | Down'
    bl_description = 'Moves active Trim Up | Down in Trimsheet'
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=(
            ('UP', 'Up', ""),
            ('DOWN', 'Down', "")
        ),
        options={'HIDDEN', 'SKIP_SAVE'},
        default='UP'
    )

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=(
            ('ACTIVE', 'Active', "Moves active trim up | down in the trimsheet"),
            ('SELECTED_UP_DOWN', 'Selected Up | Down', "Moves selected trims up | down in the trimsheet"),
            ('SELECTED_TOP_BOTTOM', 'Selected Top | Bottom', "Moves selected trims to the top | bottom of the trimsheet"),
            ('SELECTED_FIRST_LAST', 'Selected First | Last', "Moves selected trims to the first | last selected")
        ),
        # options={'HIDDEN', 'SKIP_SAVE'},
        default='ACTIVE'
    )

    keep_intervals: bpy.props.BoolProperty(
        name='Keep Intervals',
        description='Keep intervals in list between selected trims',
        default=True
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True

        row = layout.row(align=True)
        row.enabled = False
        row.prop(self, 'mode')

        if self.mode not in {'ACTIVE', 'SELECTED_FIRST_LAST'}:
            layout.prop(self, 'keep_intervals')

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            s_direction = bpy.types.UILayout.enum_item_name(properties, 'direction', properties.direction)
            s_top_bottom = 'top' if properties.direction == 'UP' else 'bottom'
            s_first_last = 'first' if properties.direction == 'UP' else 'last'
            return (
                f'Moves active trim {s_direction.lower()} in the trimsheet\n'
                f'* Shift - Move selected Trims {s_direction.lower()} in Trimsheet\n'
                f'* Ctrl - Move selected Trims to the {s_top_bottom} of Trimsheet\n'
                f'* Shift + Ctrl - Move selected Trims to the {s_first_last} selected Trim in Trimsheet')
        else:
            return cls.bl_description

    @classmethod
    def poll(cls, context):
        return (
            ZuvTrimsheetUtils.isTrimsheetEditable(context) and
            len(ZuvTrimsheetUtils.getTrimsheet(context)) > 1)

    def move_index(self, context):
        """ Move index of an item render queue while clamping it. """
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            index = p_data.trimsheet_index
            list_length = len(p_data.trimsheet) - 1
            # (index starts at 0)
            new_index = index + (-1 if self.direction == 'UP' else 1)
            i_new_index = max(0, min(new_index, list_length))
            if i_new_index != p_data.trimsheet_index:
                p_data.trimsheet_index = i_new_index

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if event.shift and event.ctrl:
            self.mode = 'SELECTED_FIRST_LAST'
        elif event.shift:
            self.mode = 'SELECTED_UP_DOWN'
        elif event.ctrl:
            self.mode = 'SELECTED_TOP_BOTTOM'
        else:
            self.mode = 'ACTIVE'

        return self.execute(context)

    def execute(self, context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            p_trimsheet = p_data.trimsheet
            n_trims_count = len(p_trimsheet)
            p_list = p_data.trimsheet
            index = p_data.trimsheet_index

            if self.mode == 'ACTIVE':
                neighbor = index + (-1 if self.direction == 'UP' else 1)
                p_list.move(neighbor, index)
                self.move_index(context)
            else:
                p_indices = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)
                if len(p_indices) > 0:

                    b_keep_intervals = False if self.mode == 'SELECTED_FIRST_LAST' else self.keep_intervals

                    if self.direction == 'UP':
                        i_min = 0
                        if self.mode == 'SELECTED_UP_DOWN':
                            i_min = max(p_indices[0] - 1, 0)
                        elif self.mode == 'SELECTED_FIRST_LAST':
                            i_min = max(p_indices[0], 0)
                        i_count = i_min
                        for idx in p_indices:
                            i_new_idx = (
                                i_min + (idx - p_indices[0])
                                if b_keep_intervals else i_count)
                            p_list.move(idx, i_new_idx)
                            if p_data.trimsheet_index == idx:
                                p_data.trimsheet_index = i_new_idx
                            i_count += 1
                    else:
                        n_indices_count = len(p_indices)

                        i_last = n_indices_count - 1

                        i_max = n_trims_count - 1
                        if self.mode == 'SELECTED_UP_DOWN':
                            i_max = min(p_indices[i_last] + 1, n_trims_count - 1)
                        elif self.mode == 'SELECTED_FIRST_LAST':
                            i_max = min(p_indices[i_last], n_trims_count - 1)

                        i_count = i_max
                        for idx in reversed(p_indices):
                            i_new_idx = (
                                i_max - (p_indices[i_last] - idx)
                                if b_keep_intervals else i_count)
                            p_list.move(idx, i_new_idx)
                            if p_data.trimsheet_index == idx:
                                p_data.trimsheet_index = i_new_idx
                            i_count -= 1

            p_data.trimsheet_mark_geometry_update()
            ZuvTrimsheetUtils.fix_undo()
            ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

            return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_TrimFrame(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_frame"
    bl_label = 'Frame Trim'
    bl_description = 'Move view to active Trim center in UV Editor'
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('ACTIVE', 'Active', 'View active trim'),
            ('SELECTED', 'Selected', 'View selected trims'),
        ],
        default='ACTIVE'
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, 'mode', expand=True)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isImageEditorSpace(context)

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            s_mode = bpy.types.UILayout.enum_item_name(properties, "mode", properties.mode)
            return f'Move view to {s_mode.lower()} Trim center in UV Editor'
        else:
            return cls.bl_description

    def view_zoom(self, p_override, xmin, xmax, ymin, ymax):
        rgn = p_override['region']

        p_view_coords_1 = list(rgn.view2d.view_to_region(xmin, ymin, clip=False))
        p_view_coords_2 = list(rgn.view2d.view_to_region(xmax, ymax, clip=False))

        p_view_coords_1[0] = round(p_view_coords_1[0])
        p_view_coords_1[1] = round(p_view_coords_1[1])

        p_view_coords_2[0] = round(p_view_coords_2[0])
        p_view_coords_2[1] = round(p_view_coords_2[1])


        if ZenPolls.version_since_3_2_0:
            with bpy.context.temp_override(**p_override):
                bpy.ops.image.view_zoom_border(
                    xmin=p_view_coords_1[0], xmax=p_view_coords_2[0],
                    ymin=p_view_coords_1[1], ymax=p_view_coords_2[1],
                    wait_for_input=False, zoom_out=False)
        else:
            bpy.ops.image.view_zoom_border(
                p_override,
                xmin=p_view_coords_1[0], xmax=p_view_coords_2[0],
                ymin=p_view_coords_1[1], ymax=p_view_coords_2[1],
                wait_for_input=False, zoom_out=False)

        area = p_override['area']

        area.tag_redraw()

    def execute(self, context: bpy.types.Context):
        try:
            if not ZuvTrimsheetUtils.isImageEditorSpace(context):
                raise RuntimeError('Only ImageEditor context is supported!')

            xmin = 0
            xmax = 0
            ymin = 0
            ymax = 0

            if self.mode == 'ACTIVE':
                p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
                if p_trim is None:
                    raise RuntimeError('No active trim!')

                xmin, ymax, xmax, ymin = p_trim.rect
            elif self.mode == 'SELECTED':
                p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
                if p_trimsheet is None:
                    raise RuntimeError('No active trimsheet!')
                p_rects = [p_trimsheet[idx].rect for idx in ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)]
                if len(p_rects) == 0:
                    raise RuntimeError('No selected trims!')
                xmin_arr, ymax_arr, xmax_arr, ymin_arr = zip(*p_rects)
                xmin = min(xmin_arr)
                xmax = max(xmax_arr)
                ymin = min(ymin_arr)
                ymax = max(ymax_arr)

            if xmax - xmin == 0 or ymax - ymin == 0:
                raise RuntimeError('Can not frame empty trim(s)!')

            bpy.ops.image.view_zoom_ratio('INVOKE_DEFAULT', ratio=1.0)
            bpy.ops.image.view_all('INVOKE_DEFAULT', fit_view=True)

            context.area.tag_redraw()

            # this function does not recalculate region dimensions, so we need to put in queue
            bpy.app.timers.register(partial(self.view_zoom, context.copy(), xmin, xmax, ymin, ymax), first_interval=0.016)
            return {'FINISHED'}
        except Exception as e:
            self.report({'WARNING'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_TrimsSetProps(bpy.types.Operator):
    bl_idname = "wm.zenuv_set_props_to_trims"
    bl_label = "Set Props to Trims"
    bl_options = {'REGISTER', 'UNDO'}

    data_path: bpy.props.StringProperty(
        name='Data Path',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    data_value: bpy.props.StringProperty(
        name='Data Value',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('SINGLE_PARAM', 'Single Param', ''),
            ('ADVANCED_PARAMS', 'Advanced Params', ''),
            ('TAGS', 'Tags', '')
        ],
        default='SINGLE_PARAM',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            if properties.mode == 'TAGS':
                return (
                    'Set current trim tags to all selected trims\n'
                    '* Shift - Set all advanced settings')

            if properties.mode == 'ADVANCED_PARAMS':
                return 'Set all Advanced Settings to all selected trims'
        else:
            return cls.bl_description

        p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if p_trim:
            prop: bpy.types.Property = p_trim.bl_rna.properties.get(properties.data_path)
            s_val = properties.data_value
            if isinstance(prop, bpy.types.FloatProperty):
                val = getattr(p_trim, properties.data_path)
                if prop.array_length > 0:
                    s_val = ', '.join(f'{elem:.2f}' for elem in val[:])
                else:
                    s_val = f'{val:.2f}'
            return (
                f"Set '{prop.name}' with value '{s_val}' to all selected trims\n"
                "* Shift - Set all advanced settings")
        return ""

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if event.shift:
            self.mode = 'ADVANCED_PARAMS'
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            p_trim = ZuvTrimsheetUtils.getActiveTrimFromOwner(p_data)
            if p_trim:
                p_trimsheet = p_data.trimsheet
                sel_indices = ZuvTrimsheetUtils.getTrimsheetSelectedAndActiveIndices(p_trimsheet)
                if len(sel_indices) >= 2:

                    t_dict = None
                    fn_skip = None

                    b_TAGS_MODE = self.mode == 'TAGS'
                    b_ADV_PARAMS_MODE = self.mode == 'ADVANCED_PARAMS'

                    if b_TAGS_MODE:
                        def fn_skip_not_tags(it_trim, inst, attr):
                            if inst == it_trim and attr not in {'tags', 'tag_index'}:
                                return True
                            return False

                        fn_skip = fn_skip_not_tags
                        t_dict = p_trim.to_dict(fn_skip_prop=partial(fn_skip, p_trim))
                    elif b_ADV_PARAMS_MODE:
                        t_filtered_props = {
                            'selected',
                            'uuid',
                            'normal'
                        }

                        t_advanced_props = p_trim.get_common_props(skipped=t_filtered_props)
                        t_advanced_props.append('tags')
                        t_advanced_props.append('tag_index')

                        def fn_skip_not_adv(it_trim, inst, attr):
                            if inst == it_trim and attr not in t_advanced_props:
                                return True
                            return False

                        fn_skip = fn_skip_not_adv
                        t_dict = p_trim.to_dict(fn_skip_prop=partial(fn_skip, p_trim))

                    for idx in sel_indices:
                        it_trim = p_trimsheet[idx]
                        if p_trim != it_trim:
                            if b_TAGS_MODE or b_ADV_PARAMS_MODE:
                                it_trim.from_dict(t_dict, fn_skip_prop=partial(fn_skip, it_trim))
                            else:
                                setattr(it_trim, self.data_path, eval(self.data_value))

                    p_data.trimsheet_mark_geometry_update()
                    ZuvTrimsheetUtils.fix_undo()
                    update_areas_in_all_screens(context)

        return {'FINISHED'}


class ZUV_OT_TrimBatchRename(bpy.types.Operator):
    bl_idname = 'wm.zuv_trim_batch_rename'
    bl_label = 'Batch Rename'
    bl_description = "If 'what' is empty, text will be completely replaced with 'replace' value"
    bl_options = {'REGISTER', 'UNDO'}

    group_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Trim batch rename mode",
        items=[
            ('SELECTED', 'Selected', ''),
            ('ALL', 'All', ''),
        ],
        default='ALL')
    find: bpy.props.StringProperty(
        name='Find',
        description='The text to search for in names')
    replace: bpy.props.StringProperty(
        name='Replace',
        description='The text to replace for in matching names found from the Find text')
    match_case: bpy.props.BoolProperty(
        name='Match Case',
        description='Search results must exactly match the case of the Find text',
        default=True)
    use_counter: bpy.props.BoolProperty(
        name='Counter',
        description="Integer value will be added to the end of the name",
        default=False)
    start_from: bpy.props.IntProperty(
        name='Start from',
        description='If Counter property is used, integer value will be started from this value',
        default=1)
    use_regex: bpy.props.BoolProperty(
        name='Use Regex',
        description='Use Replace by Regular Expression',
        default=False
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return (
            ZuvTrimsheetUtils.isTrimsheetEditable(context) and
            len(ZuvTrimsheetUtils.getTrimsheet(context)) > 0)

    def execute(self, context):
        if self.replace == '' and self.find == '':
            self.report({'WARNING'}, 'Nothing was defined to replace!')
            return {'CANCELLED'}

        i_start = self.start_from
        is_modified = False

        try:
            p_data = ZuvTrimsheetUtils.getActiveTrimData(context)
            if p_data is None:
                self.report({'WARNING'}, 'No Active Trim!')
                return {'CANCELLED'}

            act_idx, p_trim, p_trimsheet = p_data

            for it_trim in p_trimsheet:
                if self.group_mode == 'SELECTED':
                    if not it_trim.selected and it_trim != p_trim:
                        continue

                p_old_name = it_trim.name
                new_name, err = ZenStrUtils.smart_replace(p_old_name, self)
                if err:
                    raise RuntimeError(err)

                if self.use_counter:
                    new_name = new_name + str(i_start)
                    i_start += 1

                if p_old_name != new_name:
                    it_trim.name_ex = new_name
                    is_modified = True
        except Exception as e:
            self.report({'ERROR'}, str(e))
            is_modified = True

        if is_modified:
            ZuvTrimsheetUtils.fix_undo()
            update_areas_in_all_screens(context)

            return {'FINISHED'}
        else:
            self.report({'WARNING'}, 'No replace matches found!')

        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "group_mode", expand=True)
        layout.prop(self, "find")
        layout.prop(self, "replace")
        layout.prop(self, "match_case")
        layout.prop(self, 'use_regex')
        row = layout.row()
        row.prop(self, "use_counter")
        row.prop(self, "start_from")

        p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if p_trim:
            box = layout.box()
            box.label(text='Preview')

            p_old_name = p_trim.name
            p_new_name, err = ZenStrUtils.smart_replace(p_old_name, self)

            if self.use_counter:
                p_new_name = p_new_name + str(self.start_from)

            col = box.column(align=True)
            col.alert = err != ''
            col.active = p_old_name != p_new_name
            row = col.row(align=True)
            row = row.split(factor=0.2)
            row.label(text='Old:')
            row.label(text=p_old_name)

            row = col.row(align=True)
            row = row.split(factor=0.2)
            row.label(text='New:')
            row.label(text=p_new_name)

            if err:
                row = box.row(align=True)
                row.alert = True
                row.label(text='ERROR: ' + err, icon='ERROR')


class ZUV_OT_TrimClearPreviewFolder(bpy.types.Operator):
    bl_idname = 'wm.zuv_trim_clear_preview_folder'
    bl_label = 'Clear Trimsheet Preview Folder'
    bl_description = "Clear folder where trimsheet preview icons are stored"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context):
        try:
            trim_preview_dir = ZuvPresets.force_full_preset_path(ZuvTrimsheetUtils.TRIM_PREVIEW_SUBDIR)
            shutil.rmtree(trim_preview_dir)
            self.report({'INFO'}, 'Successfully cleared!')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_TrimCreateFromZenSets(bpy.types.Operator):
    bl_idname = 'wm.zuv_trim_create_from_zen_sets'
    bl_label = 'Add Trims From Zen Sets'
    bl_description = "Create trims from Zen Sets groups mesh elements with keeping its names"
    bl_options = {'REGISTER', 'UNDO'}

    group_mode: bpy.props.EnumProperty(
        name="Group Mode",
        description="Select to create trims from active or all groups",
        items=[
            ('ACTIVE', 'Active', 'Active group'),
            ('ALL', 'All', 'All groups'),
        ],
        default='ALL')

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return (
            ZenPolls.is_zen_sets_present() and context.mode == 'EDIT_MESH' and
            (
                context.area and context.area.type == "VIEW_3D" or
                context.area.type == "IMAGE_EDITOR" and context.scene.tool_settings.use_uv_select_sync) and
            ZuvTrimsheetUtils.isTrimsheetEditable(context)
        )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        try:
            if not ZenPolls.is_zen_sets_present():
                raise RuntimeError("Zen Sets is not installed!")

            p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
            if p_trimsheet is None:
                raise RuntimeError("No Active Trimsheet!")

            from ZenSets.sets.factories import get_sets_mgr  # type: ignore # noqa: F401
            from .trimsheet import ZuvTrimsheetGroup

            p_cls_mgr = get_sets_mgr(context.scene)
            p_group_pairs = p_cls_mgr.get_current_group_pairs(context)

            act_idx = p_cls_mgr.get_current_list_index(context)

            b_modified = False

            for idx, p_group in p_group_pairs:
                if self.group_mode == 'ACTIVE' and idx != act_idx:
                    continue

                bpy.ops.mesh.select_all(action='DESELECT')

                b_has_selection = False
                for p_obj in context.objects_in_mode_unique_data:
                    if p_obj.type == 'MESH':
                        p_cls_mgr.set_group_to_selection(p_obj, p_group.layer_name)
                        me: bpy.types.Mesh = p_obj.data
                        if not b_has_selection:
                            b_has_selection = sum(me.count_selected_items()) > 0

                # NOTE: if there is no selection, then we skip this group
                if not b_has_selection:
                    continue

                b_modified = True

                idx_trim = p_trimsheet.find(p_group.name)
                if idx_trim != -1:
                    p_trimsheet.remove(idx_trim)

                bpy.ops.uv.zenuv_new_trim(creation_mode="SELECTION")

                p_trim: ZuvTrimsheetGroup = ZuvTrimsheetUtils.getActiveTrim(context)
                if p_trim:
                    p_trim.name_ex = p_group.name
                    p_trim.color = p_group.group_color

            if b_modified:
                return {'FINISHED'}
            else:
                self.report({'INFO'}, "There is no valid data to create trims!")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_TrimCreateFromImage(bpy.types.Operator):
    bl_idname = 'wm.zuv_trim_create_from_image'
    bl_label = 'Add Trims From Color Masks'
    bl_description = "Create trims from image color masks"
    bl_options = {'REGISTER', 'UNDO'}

    def get_items(self, context: bpy.types.Context):
        p_items = []
        for k, v in bpy.data.images.items():
            icon_id = 0
            try:
                icon_id = v.preview.icon_id
            except Exception as e:
                pass
            p_items.append((v.name, k, "", icon_id, len(p_items)))

        s_id = "ZUV_OT_TrimCreateFromImage_ITEMS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])

        if p_was_items != p_items:
            bpy.app.driver_namespace[s_id] = p_items

        return bpy.app.driver_namespace.get(s_id, [])

    image_name: bpy.props.EnumProperty(
        name='Image Name',
        description='Source image name, which will be used for texture size',
        items=get_items
    )

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Image masking mode: ",
        items=[
            ("UNIQUE", "Unique Color", "Image contains only one mask with given color"),
            ("MULTI", "Multicolor", "Image contains multiple masks with the same color"),
        ],
        default="UNIQUE"
    )

    color_limit: bpy.props.IntProperty(
        name="Color Masks Limit",
        description="How many unique colors could be processed in image",
        min=1,
        max=1000,
        default=500
    )

    @classmethod
    def poll(self, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager

        p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
        if p_image:
            self.image_name = p_image.name

        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is None:
            self.report({"INFO"}, "No active trimsheet!")
            return {'CANCELLED'}

        p_image = bpy.data.images.get(self.image_name)

        if p_image is None:
            self.report({'INFO'}, "No active image!")
            return {'CANCELLED'}

        width, height = p_image.size
        if not (width > 0 and height > 0):
            self.report({'INFO'}, "Image is empty!")
            return {'CANCELLED'}

        color_rectangles = defaultdict(list)

        from ZenUV.utils.progress import ProgressBar, ProgressCancelException

        progress = ProgressBar(context, width * height, text_only=False)
        progress.current_step = 0
        progress.fps = 5

        try:
            interval = timer()

            # Create a visited pixel map to avoid redundant checks
            visited = [[False for _ in range(width)] for _ in range(height)]

            progress.set_text(prefix="Calculating unique colors:", preposition="")
            progress.update()

            # NOTE: we will use numpy to quickly found unique colors
            pixels = np.array(p_image.pixels).reshape(height, width, p_image.channels)
            pixels = pixels[:, :, :3]  # Retain only RGB channels

            # unique_colors = np.unique(pixels.reshape(-1, p_image.channels), axis=0)

            pixels_reshaped = pixels.reshape(-1, pixels.shape[2])
            unique_colors = np.unique(pixels_reshaped, axis=0)

            if len(unique_colors) > self.color_limit:
                self.report({'WARNING'}, f"Color ID count: {len(unique_colors)} exceeded the limit!")
                raise ProgressCancelException()

            progress.set_text(prefix="Analysing:", preposition=" of")

            # Function to find bounding box for mask
            def find_bounding_box(mask):
                coords = np.argwhere(mask)
                y_min, x_min = coords.min(axis=0)
                y_max, x_max = coords.max(axis=0)
                return x_min, y_min, x_max, y_max

            def get_pixel_color(x, y):
                return tuple(pixels[y, x])

            def mark_visited(x, y):
                if not visited[y][x]:
                    visited[y][x] = True
                    progress.current_step += 1
                    if not progress.update_by_timer():
                        raise ProgressCancelException()

            def flood_fill(x, y, color):
                stack = [(x, y)]
                min_x, max_x, min_y, max_y = x, x, y, y

                while stack:
                    cx, cy = stack.pop()
                    if not (0 <= cx < width and 0 <= cy < height):
                        continue
                    if visited[cy][cx]:
                        continue
                    pixel_color = get_pixel_color(cx, cy)
                    if pixel_color != color:
                        continue

                    mark_visited(cx, cy)

                    min_x, max_x = min(min_x, cx), max(max_x, cx)
                    min_y, max_y = min(min_y, cy), max(max_y, cy)

                    # Add neighboring pixels to the stack
                    stack.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])

                return (min_x, min_y, max_x + 1, max_y + 1)

            if self.mode == 'UNIQUE':
                bounding_boxes = []
                # Iterate through unique colors and find bounding boxes
                progress.iterations = len(unique_colors)
                for color in unique_colors:
                    if not progress.update():
                        raise ProgressCancelException()
                    mask = np.all(pixels == color, axis=-1)
                    bbox = find_bounding_box(mask)
                    bounding_boxes.append(bbox)

                    bbox = list(bbox)
                    bbox[2] += 1
                    bbox[3] += 1
                    color_rectangles[tuple(color)].append(bbox)

                bounding_boxes = np.array(bounding_boxes)

                # Check for intersections using vectorized operations
                x_min, y_min, x_max, y_max = bounding_boxes.T

                # Use broadcasting to compare all boxes
                intersect_x_min = np.maximum(x_min[:, None], x_min)
                intersect_y_min = np.maximum(y_min[:, None], y_min)
                intersect_x_max = np.minimum(x_max[:, None], x_max)
                intersect_y_max = np.minimum(y_max[:, None], y_max)

                # Calculate intersection widths and heights
                intersect_widths = np.maximum(0, intersect_x_max - intersect_x_min)
                intersect_heights = np.maximum(0, intersect_y_max - intersect_y_min)

                # Check if both width and height are greater than zero
                intersections = (intersect_widths > 0) & (intersect_heights > 0)

                # Check are there any intersections between color masks
                if np.any(np.triu(intersections, 1)):
                    self.report({'WARNING'}, "There are ovelapping masks! Try 'Multicolor' mode!")

            elif self.mode == 'MULTI':
                for y in range(height):
                    for x in range(width):
                        if visited[y][x]:
                            continue
                        color = get_pixel_color(x, y)
                        rectangle = flood_fill(x, y, color)
                        if rectangle[2] - rectangle[0] > 0 and rectangle[3] - rectangle[1] > 0:
                            color_rectangles[color].append(rectangle)
            else:
                raise RuntimeError(f"Mode: {self.mode} - is not defined!")


            for color, rects in color_rectangles.items():
                for rect in rects:
                    p_rect = Rectangle(rect[0], rect[1], rect[2], rect[3])

                    p_data.trimsheet.add()
                    n_count = len(p_data.trimsheet)
                    p_data.trimsheet[-1].create_uuid()
                    p_data.trimsheet[-1].name_ex = 'Trim'
                    p_data.trimsheet[-1].color = color
                    p_data.trimsheet[-1].set_rectangle(p_rect.left / width, p_rect.top / height, p_rect.right / width, p_rect.bottom / height)
                    p_data.trimsheet_index = n_count - 1
        except ProgressCancelException:
            pass
        except Exception as e:
            self.report({'WARNING'}, str(e))
        finally:
            progress.finish()

        p_data.trimsheet_mark_geometry_update()

        ZuvTrimsheetUtils.auto_highlight_trims(context)

        ZuvTrimsheetUtils.fix_undo()
        update_areas_in_all_screens(context)

        return {'FINISHED'}
