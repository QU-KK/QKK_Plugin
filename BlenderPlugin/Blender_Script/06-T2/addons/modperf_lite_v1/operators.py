# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Operators: modifier actions and the open / close toggle; panel placement."""

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

from .constants import TOGGLE_OPERATOR
from .state import HUD
from .utils import (
    _active_object, _clean_error, _edit_lock, _mod_lock, _status, _supports_modifiers,
    _tag_all_view3d, _undo_push,
)


# =============================================================================
# Operators
# =============================================================================

class OBJECT_OT_modperf_lite_action(bpy.types.Operator):
    """Run a modifier stack action on the active object"""
    bl_idname = "object.modperf_lite_action"
    bl_label = "ModPerf Lite Action"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=(
            ('APPLY', "Apply", "Apply the modifier"),
            ('DUPLICATE', "Duplicate", "Duplicate the modifier"),
            ('REMOVE', "Delete", "Delete the modifier"),
            ('MOVE_UP', "Move Up", ""),
            ('MOVE_DOWN', "Move Down", ""),
            ('MOVE_FIRST', "Move to First", ""),
            ('MOVE_LAST', "Move to Last", ""),
            ('MOVE_TO', "Move to Index", ""),
        ),
    )
    modifier: StringProperty(name="Modifier")
    index: IntProperty(name="Index", default=0, min=0)

    @classmethod
    def poll(cls, context):
        return _supports_modifiers(_active_object(context))

    def execute(self, context):
        obj = _active_object(context)
        mods = obj.modifiers
        name = self.modifier
        if name not in mods:
            self.report({'ERROR'}, f"Modifier '{name}' not found")
            return {'CANCELLED'}
        lock = (_edit_lock(obj) if self.action == 'DUPLICATE'
                else _mod_lock(obj, mods[name]))
        if lock:
            self.report({'WARNING'}, lock)
            _status(lock)
            return {'CANCELLED'}
        if self.action == 'APPLY' and obj.mode == 'EDIT':
            msg = "Can't apply modifiers in Edit Mode: switch to Object Mode first"
            self.report({'WARNING'}, msg)
            _status(msg)
            return {'CANCELLED'}
        try:
            with context.temp_override(object=obj, active_object=obj):
                self._run(context, obj, mods, name)
        except RuntimeError as ex:
            msg = _clean_error(ex)
            self.report({'ERROR'}, msg)
            _status(msg)
            _tag_all_view3d(context)
            return {'CANCELLED'}
        _tag_all_view3d(context)
        return {'FINISHED'}

    def _run(self, context, obj, mods, name):
        a = self.action
        ops = bpy.ops.object
        if a == 'APPLY':
            ops.modifier_apply(modifier=name)
            _status(f"Applied '{name}'")
        elif a == 'DUPLICATE':
            ops.modifier_copy(modifier=name)
        elif a == 'REMOVE':
            ops.modifier_remove(modifier=name)
            _status(f"Deleted '{name}'")
        else:
            cur = mods.find(name)
            last = len(mods) - 1
            target = {
                'MOVE_UP': cur - 1, 'MOVE_DOWN': cur + 1,
                'MOVE_FIRST': 0, 'MOVE_LAST': last, 'MOVE_TO': self.index,
            }[a]
            target = max(0, min(last, target))
            if target != cur:
                ops.modifier_move_to_index(modifier=name, index=target)


class VIEW3D_OT_modperf_lite(bpy.types.Operator):
    """Toggle the floating Modifier HUD panel at the mouse position"""
    bl_idname = TOGGLE_OPERATOR
    bl_label = "ModPerf Lite"
    # No UNDO: opening / closing the panel changes no data, so it must not add
    # an empty step to the undo history.
    bl_options = {'REGISTER'}

    action: EnumProperty(
        name="Action",
        items=(
            ('TOGGLE', "Toggle", "Open the panel if closed, otherwise close it"),
            ('OPEN', "Open", "Open the panel"),
            ('CLOSE', "Close", "Close the panel"),
        ),
        default='TOGGLE',
        options={'SKIP_SAVE'},
    )

    @classmethod
    def poll(cls, context):
        screen = context.screen
        if screen is None or not any(a.type == 'VIEW_3D' for a in screen.areas):
            return False
        if _pro_enabled() and not HUD.running:
            # ModPerf Pro is enabled too: let its own shortcut (same key) open Pro.
            cls.poll_message_set("ModPerf Pro is enabled: use ModPerf Pro")
            return False
        if context.mode != 'OBJECT' and not HUD.running:
            cls.poll_message_set("ModPerf only works in Object Mode")
            return False
        return True

    def invoke(self, context, event):
        return self._run(context, event)

    def execute(self, context):
        return self._run(context, None)

    def _run(self, context, event):
        if HUD.running:
            if self.action in {'TOGGLE', 'CLOSE'}:
                _close_hud(context)
                return {'FINISHED'}
            return {'CANCELLED'}
        if self.action == 'CLOSE':
            return {'CANCELLED'}

        area, region = _pick_view3d(context, event)
        if region is None:
            self.report({'ERROR'}, "No 3D Viewport found")
            return {'CANCELLED'}
        if event is not None:
            mx, my = event.mouse_x - region.x, event.mouse_y - region.y
        else:
            mx, my = region.width // 2, region.height // 2
        with context.temp_override(window=context.window, area=area, region=region):
            bpy.ops.view3d.modperf_lite_modal('INVOKE_DEFAULT', mouse_x=int(mx), mouse_y=int(my))
        return {'FINISHED'}


def _pro_enabled():
    """True when ModPerf Pro (extension id "modperf") is enabled."""
    try:
        return any(a.module == "modperf" or a.module.endswith(".modperf")
                   for a in bpy.context.preferences.addons)
    except (AttributeError, ReferenceError):
        return False


def _pick_view3d(context, event):
    """Choose the 3D Viewport (area, WINDOW region) to host the panel."""
    screen = context.screen
    area = context.area if context.area and context.area.type == 'VIEW_3D' else None
    if area is None and event is not None:
        for a in screen.areas:
            if (a.type == 'VIEW_3D' and a.x <= event.mouse_x < a.x + a.width
                    and a.y <= event.mouse_y < a.y + a.height):
                area = a
                break
    if area is None:
        views = [a for a in screen.areas if a.type == 'VIEW_3D']
        area = max(views, key=lambda a: a.width * a.height) if views else None
    if area is None:
        return None, None
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    return area, region


def _close_hud(context=None):
    if HUD.draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(HUD.draw_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
    if HUD.timer is not None:
        try:
            (context or bpy.context).window_manager.event_timer_remove(HUD.timer)
        except (ValueError, RuntimeError, ReferenceError, AttributeError):
            pass
    HUD.reset()
    try:
        _tag_all_view3d(context)
    except Exception:
        pass


def _mouse_over_view3d(context, event):
    for a in context.window.screen.areas:
        if (a.type == 'VIEW_3D' and a.x <= event.mouse_x < a.x + a.width
                and a.y <= event.mouse_y < a.y + a.height):
            return True
    return False


_ACTION_UNDO = {
    'APPLY': "Apply Modifier", 'DUPLICATE': "Duplicate Modifier", 'REMOVE': "Delete Modifier",
    'MOVE_UP': "Move Modifier", 'MOVE_DOWN': "Move Modifier",
    'MOVE_FIRST': "Move Modifier", 'MOVE_LAST': "Move Modifier", 'MOVE_TO': "Move Modifier",
}


def _run_action(context, area, region, action, name="", index=0):
    # Operators called from Python never push an undo step on their own, so
    # push one per action: each HUD action is then a separate Ctrl+Z.
    try:
        with context.temp_override(area=area, region=region):
            res = bpy.ops.object.modperf_lite_action(action=action, modifier=name, index=index)
    except RuntimeError as ex:
        _status(_clean_error(ex))
        return
    if 'FINISHED' in res:
        _undo_push(context, area, region, _ACTION_UNDO.get(action, "Modifier"))
