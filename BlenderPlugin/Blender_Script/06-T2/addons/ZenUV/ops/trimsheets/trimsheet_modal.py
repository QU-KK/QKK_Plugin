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

from dataclasses import dataclass

from .trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens
from ZenUV.utils.simple_geometry import Rectangle


class ZUV_OT_TrimCreate(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_create"
    bl_label = "Create Trims"
    bl_description = "Create trims modal operator"
    bl_option = {'REGISTER'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.area_ptr = None
        self.area_right = 0
        self.area_top = 0

        self.is_dragging = False
        self.pressed_x = 0
        self.pressed_y = 0
        self.pressed_region_x = 0
        self.pressed_region_y = 0

        self.was_pressed = False

    def cancel(self, context: bpy.types.Context):
        self.area_ptr = None
        self.area_right = 0
        self.area_top = 0

        self.was_pressed = False
        self.in_mode = ''

        self.pressed_x = 0
        self.pressed_y = 0
        self.pressed_region_x = 0
        self.pressed_region_y = 0

        self.is_dragging = False

        ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):

        # DEBUG:
        # print(event.type, event.value, f'{event.is_repeat=}', f'{event.ctrl=}')

        if context.area is None or self.area_ptr is None or context.area.as_pointer() != self.area_ptr:
            self.cancel(context)
            return {'CANCELLED', 'PASS_THROUGH'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED', 'PASS_THROUGH'}

        b_is_released = event.value == 'RELEASE'

        p_trimsheet_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)

        if event.type == 'MOUSEMOVE':
            if self.was_pressed is True:
                from .trimsheet import ZuvTrimsheetGroup
                p_trim: ZuvTrimsheetGroup = ZuvTrimsheetUtils.getActiveTrim(context)
                if p_trim:
                    p_view_coords = list(context.region.view2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

                    p_trim.set_snapped_rect(
                        context,
                        self.pressed_x, self.pressed_y,
                        p_view_coords[0], p_view_coords[1]
                    )

                    ZuvTrimsheetUtils.update_imageeditor_in_all_screens()
                else:
                    self.cancel(context)
                    return {'CANCELLED', 'PASS_THROUGH'}

        elif event.type == 'LEFTMOUSE':
            if b_is_released:
                if self.was_pressed:
                    self.was_pressed = False
                    b_modified = True

                    p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
                    if p_trim and (p_trim.width == 0 or p_trim.height == 0):
                        if bpy.ops.uv.zuv_trim_remove.poll():
                            bpy.ops.uv.zuv_trim_remove('INVOKE_DEFAULT')
                            b_modified = False

                    if b_modified:
                        if p_trimsheet_owner:
                            p_trimsheet_owner.trimsheet_mark_geometry_update()
                        ZuvTrimsheetUtils.fix_undo()
                        bpy.ops.ed.undo_push(message='Change Trim')

                self.is_dragging = False

                self.cancel(context)
                return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def is_valid_context(self, context: bpy.types.Context):
        if self.area_ptr is not None and hasattr(context, 'area') and context.area is not None:
            return self.area_ptr == context.area.as_pointer()

    @classmethod
    def poll(cls, context: bpy.types.Context):
        scene = context.scene
        return (
            scene.zen_uv.ui.uv_tool.mode == 'CREATE' and
            ZuvTrimsheetUtils.isTrimsheetEditable(context))

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # clean data
        self.cancel(context)

        self.area_ptr = context.area.as_pointer()

        self.was_pressed = False
        self.is_dragging = False

        if bpy.ops.uv.zuv_trim_add.poll():
            bpy.ops.uv.zuv_trim_add('INVOKE_DEFAULT')

            p_trim_pair = ZuvTrimsheetUtils.getActiveTrimPair(context)
            if p_trim_pair:
                from .trimsheet import ZuvTrimsheetGroup
                p_trim: ZuvTrimsheetGroup
                _, p_trim = p_trim_pair
                self.pressed_region_x = event.mouse_region_x
                self.pressed_region_y = event.mouse_region_y
                self.pressed_x, self.pressed_y = context.region.view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)

                p_trim.set_rectangle(self.pressed_x, self.pressed_y, self.pressed_x, self.pressed_y)

                self.was_pressed = True

                update_areas_in_all_screens(context)

                context.window_manager.modal_handler_add(self)

                return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Trimsheet is not editable!")

        return {'CANCELLED'}

    def execute(self, context: bpy.types.Context):
        # NOTE: Do not remove!
        return {'FINISHED'}


@dataclass
class BoxSelectRect(Rectangle):
    trim_index: int = -1

    def __hash__(self):
        return hash((super().__hash__(), self.trim_index))


class ZUV_OT_TrimBoxSelect(bpy.types.Operator):
    bl_idname = "wm.zuv_trim_box_select"
    bl_label = "Trims Box Select"
    bl_description = "Select trims with box selection tool"
    bl_option = {'REGISTER'}

    trimsheet_index: bpy.props.IntProperty(
        name='Trimsheet Index',
        default=-1,
        min=-1,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.area_ptr = None

        self.is_dragging = False
        self.pressed_region_x = 0
        self.pressed_region_y = 0

        self.was_pressed = False

    def cancel(self, context: bpy.types.Context):

        t_data = bpy.app.driver_namespace.get('zenuv_box_select', {})
        t_data[context.area.as_pointer()] = None
        bpy.app.driver_namespace['zenuv_box_select'] = t_data

        self.area_ptr = None
        self.was_pressed = False

        self.pressed_region_x = 0
        self.pressed_region_y = 0

        self.is_dragging = False

        ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):

        # DEBUG:
        # print(event.type, event.value, f'{event.is_repeat=}', f'{event.ctrl=}')

        if context.area is None or self.area_ptr is None or context.area.as_pointer() != self.area_ptr:
            self.cancel(context)
            return {'CANCELLED', 'PASS_THROUGH'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED', 'PASS_THROUGH'}

        b_is_released = event.value == 'RELEASE'

        t_data = bpy.app.driver_namespace.get('zenuv_box_select', {})
        p_box_select = BoxSelectRect(
            self.pressed_region_x,
            self.pressed_region_y,
            event.mouse_region_x,
            event.mouse_region_y,
            self.trimsheet_index)

        t_data[self.area_ptr] = p_box_select
        bpy.app.driver_namespace['zenuv_box_select'] = t_data

        if event.type == 'MOUSEMOVE':
            if self.was_pressed is True:
                context.area.tag_redraw()
        elif event.type == 'LEFTMOUSE':
            if b_is_released:
                if self.was_pressed:
                    self.was_pressed = False
                    b_modified = False

                    p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
                    if p_data is not None:
                        # 1. Click. No Drag
                        if self.trimsheet_index != -1:
                            if p_box_select.width < 2 and p_box_select.height < 2:
                                bpy.ops.wm.zuv_trim_set_index('INVOKE_DEFAULT', True, trimsheet_index=self.trimsheet_index)
                                self.cancel(context)
                                return {'CANCELLED', 'PASS_THROUGH'}

                        # 2. Click and Drag
                        for p_trim in p_data.trimsheet:
                            left, bottom = context.region.view2d.view_to_region(*p_trim.left_bottom, clip=False)
                            right, top = context.region.view2d.view_to_region(*p_trim.top_right, clip=False)
                            trim_rgn_rect = Rectangle(left, top, right, bottom)

                            b_is_selected = p_box_select.intersects(trim_rgn_rect)
                            if event.shift:
                                if b_is_selected:
                                    if not p_trim.selected:
                                        p_trim.selected = True
                                        b_modified = True
                            elif event.ctrl:
                                if b_is_selected:
                                    if p_trim.selected:
                                        p_trim.selected = False
                                        b_modified = True
                            else:
                                if p_trim.selected != b_is_selected:
                                    p_trim.selected = b_is_selected
                                    b_modified = True

                    if b_modified:
                        update_areas_in_all_screens(context)
                        ZuvTrimsheetUtils.fix_undo()
                        bpy.ops.ed.undo_push(message='Select Trim(s)')

                self.is_dragging = False

                self.cancel(context)
                return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def is_valid_context(self, context: bpy.types.Context):
        if self.area_ptr is not None and hasattr(context, 'area') and context.area is not None:
            return self.area_ptr == context.area.as_pointer()

    @classmethod
    def poll(cls, context: bpy.types.Context):

        from ZenUV.ui.tool.uv.uv_base import ZuvUVGizmoBase

        p_scene = context.scene
        return (
            ZuvUVGizmoBase.is_workspace_tool_active(context) and
            p_scene.zen_uv.ui.uv_tool.display_trims and
            p_scene.zen_uv.ui.uv_tool.select_trim and
            p_scene.zen_uv.ui.uv_tool.mode != 'CREATE')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):

        # clean data
        self.cancel(context)

        self.area_ptr = context.area.as_pointer()

        self.was_pressed = False
        self.is_dragging = False

        self.pressed_region_x = event.mouse_region_x
        self.pressed_region_y = event.mouse_region_y

        t_data = bpy.app.driver_namespace.get('zenuv_box_select', {})
        t_data[self.area_ptr] = BoxSelectRect(
            self.pressed_region_x,
            self.pressed_region_y,
            self.pressed_region_x,
            self.pressed_region_y,
            self.trimsheet_index)
        bpy.app.driver_namespace['zenuv_box_select'] = t_data

        self.was_pressed = True

        update_areas_in_all_screens(context)

        context.window_manager.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context: bpy.types.Context):
        return {'FINISHED'}
