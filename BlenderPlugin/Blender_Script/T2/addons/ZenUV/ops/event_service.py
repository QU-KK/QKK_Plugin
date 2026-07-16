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
from timeit import default_timer as timer

from ZenUV.utils.blender_zen_utils import ZenPolls


LITERAL_ZENUV_EVENT = 'zenuv_event'
LITERAL_ZENUV_MOUSE_DRAG = 'zenuv_mouse_drag'


class ZUV_OT_EventService(bpy.types.Operator):
    bl_idname = "wm.zuv_event_service"
    bl_label = "Zen UV Event Detection"
    bl_description = 'Drag event detection for Zen UV internal purposes'
    bl_options = {'INTERNAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):

        t_event_data = {
            'ctrl': event.ctrl,
            'shift': event.shift,
            'alt': event.alt,
            'oskey': event.oskey,

            'mouse_x': event.mouse_x,
            'mouse_y': event.mouse_y,
        }

        bpy.app.driver_namespace[LITERAL_ZENUV_EVENT] = t_event_data

        return {'PASS_THROUGH'}  # Never change this !!!


class ZUV_OT_EventGet(bpy.types.Operator):
    bl_idname = "wm.zuv_event_get"
    bl_label = "Get Blender Event"
    bl_description = 'Get blender event and store'
    bl_options = {'INTERNAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        t_event_data = {
            'ctrl': event.ctrl,
            'shift': event.shift,
            'alt': event.alt,
            'oskey': event.oskey,

            'mouse_x': event.mouse_x,
            'mouse_y': event.mouse_y,
            'mouse_region_x': event.mouse_region_x,
            'mouse_region_y': event.mouse_region_y,

            'type': event.type,
            'value': event.value
        }

        if ZenPolls.version_since_3_0_0:
            t_event_data['mouse_prev_x'] = event.mouse_prev_x
            t_event_data['mouse_prev_y'] = event.mouse_prev_y

        bpy.app.driver_namespace[LITERAL_ZENUV_EVENT] = t_event_data
        return {'FINISHED'}


def get_blender_event(force=False):
    if force:
        bpy.ops.wm.zuv_event_get('INVOKE_DEFAULT')
    return bpy.app.driver_namespace.get(LITERAL_ZENUV_EVENT, {})


# NOTE: WARNING - Do not use in draw !!!
def ensure_continious_drag(context: bpy.types.Context):
    delta_x, delta_y = 0, 0

    v_mouse_prev = Vector((0, 0))
    v_mouse = Vector((0, 0))

    if ZenPolls.version_since_3_0_0 and context.preferences.inputs.use_mouse_continuous:
        p_event = get_blender_event(force=True)

        x, y = p_event.get('mouse_x', 0), p_event.get('mouse_y', 0)

        v_mouse.x = x
        v_mouse.y = y

        x_prev, y_prev = p_event.get('mouse_prev_x', 0), p_event.get('mouse_prev_y', 0)

        v_mouse_prev.x = x_prev
        v_mouse_prev.y = y_prev

        p_area = context.area

        n_left = p_area.x
        n_right = p_area.x + p_area.width
        n_top = p_area.y + p_area.height
        n_bottom = p_area.y

        if x <= n_left:
            wrap_x = n_right - 1
            delta_x = wrap_x - x
            x = wrap_x
        elif x >= n_right:
            wrap_x = n_left + 1
            delta_x = wrap_x - x
            x = wrap_x

        if y <= n_bottom:
            wrap_y = n_top - 1
            delta_y = wrap_y - y
            y = wrap_y
        elif y >= n_top:
            wrap_y = n_bottom + 1
            delta_y = wrap_y - y
            y = wrap_y

        if delta_x or delta_y:
            wnd = context.window
            wnd.cursor_warp(x, y)

    return (delta_x, delta_y, v_mouse, v_mouse_prev)


def is_skipped_by_continious_drag(context: bpy.types.Context):
    delta_x, delta_y, _, _ = ensure_continious_drag(context)

    d_drag_time = bpy.app.driver_namespace.get(LITERAL_ZENUV_MOUSE_DRAG, 0.0)
    if d_drag_time != 0.0:
        # NOTE: we skip drag on the next step, so let's also double check by 1.0 second delay
        d_wrap_interval = timer() - d_drag_time
        bpy.app.driver_namespace[LITERAL_ZENUV_MOUSE_DRAG] = 0.0
        if d_wrap_interval < 1.0:
            return True

    if delta_x or delta_y:
        bpy.app.driver_namespace[LITERAL_ZENUV_MOUSE_DRAG] = timer()

    return False
