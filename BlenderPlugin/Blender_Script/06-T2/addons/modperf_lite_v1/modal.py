# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""The modal operator that runs the panel and routes events."""

import time

import bpy
from bpy.props import IntProperty

from .constants import OPEN_ON_RELEASE, TOOLTIP_DELAY
from .state import HUD
from .utils import (
    _clamp_panel, _edit_lock, _get_modifier, _hit, _region_from_ptrs, _rna_of, _scale,
    _status, _undo_push,
)
from .tooltips import _tooltip_lines
from .keymap import _is_toggle_event
from .hud_layout import _draw_callback
from .operators import _close_hud, _mouse_over_view3d, _pick_view3d
from .interaction import (
    _collapse_new_modifiers, _commit_edit, _drag_cancel, _drag_finish, _drag_update,
    _duplicate_modifier_shortcut, _press, _step_num, _sync_node_inputs,
)



_LAST_PRESS = {'key': None, 't': 0.0, 'x': 0, 'y': 0}


def _is_double_click(context, event, w, mx, my):
    """Detect a double-click ourselves: once the modal handler has taken the
    first press, Blender sends the second one as a plain PRESS, not DOUBLE_CLICK."""
    now = time.monotonic()
    lp = _LAST_PRESS
    limit = context.preferences.inputs.mouse_double_click_time / 1000.0
    double = (event.value == 'DOUBLE_CLICK'
              or (lp['key'] == w['key'] and now - lp['t'] <= limit
                  and abs(mx - lp['x']) <= 6 * _scale() and abs(my - lp['y']) <= 6 * _scale()))
    if double:
        lp['key'] = None                      # a third click starts over
    else:
        lp.update(key=w['key'], t=now, x=mx, y=my)
    return double

class VIEW3D_OT_modperf_lite_modal(bpy.types.Operator):
    """Internal: runs the Modifier HUD (event handling)"""
    bl_idname = "view3d.modperf_lite_modal"
    bl_label = "ModPerf Lite (Modal)"
    # No UNDO here on purpose: every action inside the HUD pushes its own
    # undo step, which would be swallowed by an UNDO-flagged modal operator.
    bl_options = {'INTERNAL'}

    mouse_x: IntProperty(options={'HIDDEN', 'SKIP_SAVE'})
    mouse_y: IntProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        area, region = context.area, context.region
        if area is None or area.type != 'VIEW_3D' or region is None or region.type != 'WINDOW':
            area, region = _pick_view3d(context, event)
        if region is None or context.mode != 'OBJECT':
            return {'CANCELLED'}
        _close_hud(context)
        S = _scale()
        HUD.running = True
        HUD.window_ptr = context.window.as_pointer()
        HUD.area_ptr = area.as_pointer()
        HUD.region_ptr = region.as_pointer()
        HUD.w = round(385 * S)
        HUD.size_scale = S
        HUD.max_h = max(round(200 * S), min(round(720 * S), region.height - round(30 * S)))
        # Open with the title bar under the mouse cursor.
        HUD.x = self.mouse_x - round(40 * S)
        HUD.y = self.mouse_y + round(12 * S)
        _clamp_panel(region, fit=True, area=area)
        HUD.place_pending = True
        HUD.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback, (), 'WINDOW', 'POST_PIXEL')
        # Light timer that lets tooltips appear after a short hover pause.
        HUD.timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        area.tag_redraw()
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        _close_hud(context)

    # ------------------------------------------------------------------ modal
    def modal(self, context, event):
        if not HUD.running:
            return {'CANCELLED'}
        if event.type != 'TIMER':
            HUD.layout_dirty = True      # anything may have changed: rebuild on next draw
        win, area, region = _region_from_ptrs(context)
        if region is None:
            _close_hud(context)
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            # The panel only works in Object Mode: entering any other mode closes
            # it, and the key press goes on to Blender (e.g. Y = Split).
            _close_hud(context)
            return {'CANCELLED', 'PASS_THROUGH'}
        if _collapse_new_modifiers(context):
            area.tag_redraw()
        if event.type != 'INBETWEEN_MOUSEMOVE' and _sync_node_inputs(context):
            area.tag_redraw()

        mx = event.mouse_x - region.x
        my = event.mouse_y - region.y

        # Tooltip timer: show the tooltip once the mouse rests on a widget.
        if event.type == 'TIMER':
            if (HUD.hover is not None and not HUD.tip_visible and HUD.drag is None
                    and HUD.edit is None and HUD.hover != HUD.tip_block
                    and time.monotonic() - HUD.tip_since >= TOOLTIP_DELAY
                    and context.preferences.view.show_tooltips):
                w = next((w for w in HUD.widgets if w['key'] == HUD.hover), None)
                if w is not None:
                    HUD.tip_lines = _tooltip_lines(context, w)
                    HUD.tip_visible = bool(HUD.tip_lines)
                    if HUD.tip_visible:
                        area.tag_redraw()
            return {'PASS_THROUGH'}

        # Any click or key press hides the tooltip and keeps it from coming
        # back until the mouse moves to another widget, like Blender. Blocking
        # it even when it wasn't showing yet matters for buttons that open a
        # menu (Add Modifier): the menu takes the mouse events, so
        # the tooltip timer would otherwise pop the tooltip up behind the menu.
        if event.value in {'PRESS', 'DOUBLE_CLICK'} and \
                event.type not in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            HUD.tip_block = HUD.hover
            if HUD.tip_visible:
                HUD.tip_visible = False
                area.tag_redraw()

        # Typing a value into a number field takes the keyboard first.
        if HUD.edit is not None:
            result = self._handle_edit(context, event, area, region, mx, my)
            if result is not None:
                return result

        # Toggle off with Y (only when the mouse is over a 3D Viewport so we
        # never steal Y from text editors etc.)
        if (event.value == 'PRESS' and not HUD.drag and _is_toggle_event(event)
                and _mouse_over_view3d(context, event)):
            _close_hud(context)
            return {'FINISHED'}

        if HUD.drag:
            return self._handle_drag(context, event, area, region, mx, my)

        inside = (HUD.x <= mx <= HUD.x + HUD.w and HUD.y - HUD.h <= my <= HUD.y
                  and 0 <= mx <= region.width and 0 <= my <= region.height)

        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            HUD.mouse = (mx, my)
            w = _hit(mx, my) if inside else None
            key = w['key'] if w else None
            if key != HUD.hover:
                HUD.hover = key
                HUD.hover_tip = w['tip'] if w else ""
                HUD.tip_visible = False
                HUD.tip_block = None
                HUD.tip_since = time.monotonic()
                area.tag_redraw()
            return {'PASS_THROUGH'}

        # Shift+D over the panel: duplicate the modifier under the mouse (or the
        # active one), like Blender's modifier panel shortcut.
        if (inside and event.type == 'D' and event.value == 'PRESS'
                and event.shift and not (event.ctrl or event.alt or event.oskey)):
            _duplicate_modifier_shortcut(context, area, region, mx, my)
            area.tag_redraw()
            return {'RUNNING_MODAL'}

        if not inside:
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                HUD.pending = None
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and HUD.multi:
                HUD.multi = []                       # click in the viewport clears it
                area.tag_redraw()
            return {'PASS_THROUGH'}

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.ctrl:
            w = _hit(mx, my)
            if w is not None and w['kind'] == 'num':
                obj, mod = _get_modifier(context, w['mod'])
                if mod is not None and _edit_lock(obj):
                    _status(_edit_lock(obj))
                elif mod is not None:
                    owner, attr, p = _rna_of(mod, w['prop'])
                    _step_num(owner, attr, p, w['idx'],
                              1 if event.type == 'WHEELUPMOUSE' else -1)
                    _undo_push(context, area, region, "Modifier value")
                    area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'TRACKPADPAN':
            # two-finger trackpad scrolling (macOS): pixels, follows the fingers
            dy = event.mouse_y - event.mouse_prev_y
            HUD.scroll = max(0.0, min(HUD.scroll + dy, HUD.content_h - HUD.view_h))
            area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            step = 40 * _scale()
            HUD.scroll += -step if event.type == 'WHEELUPMOUSE' else step
            HUD.scroll = max(0.0, min(HUD.scroll, HUD.content_h - HUD.view_h))
            area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value in {'PRESS', 'DOUBLE_CLICK'}:
            w = _hit(mx, my)
            if w is not None:
                if w['kind'] in OPEN_ON_RELEASE:
                    # Menus/dropdowns open on release (a normal click). Opening on
                    # press lets the release pick the item under the cursor and
                    # close the menu at once.
                    HUD.pending = w['key']
                    HUD.multi = []
                else:
                    _press(context, w, event, area, region, mx, my,
                           double=_is_double_click(context, event, w, mx, my))
                area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and HUD.pending:
            w = _hit(mx, my)
            pending, HUD.pending = HUD.pending, None
            if w is not None and w['key'] == pending:
                _press(context, w, event, area, region, mx, my)
                area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE'}:
            return {'RUNNING_MODAL'}   # never let clicks on the panel reach the viewport
        return {'PASS_THROUGH'}

    # ------------------------------------------------------------ inline edit
    def _handle_edit(self, context, event, area, region, mx, my):
        """Keyboard input while typing into a number field.

        Returns a modal result, or None to continue normal event handling.
        """
        e = HUD.edit
        t, v = event.type, event.value
        if t in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                 'TIMER', 'TIMER_REPORT', 'WINDOW_DEACTIVATE'}:
            return None
        if t in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE'}:
            if v in {'PRESS', 'DOUBLE_CLICK'}:
                w = _hit(mx, my)
                if w is not None and w['key'] == e['key']:
                    e['sel'] = False          # click inside the field: keep typing
                    area.tag_redraw()
                    return {'RUNNING_MODAL'}
                _commit_edit(context, area, region)   # click elsewhere: confirm
                area.tag_redraw()
            return None
        if v != 'PRESS':
            return {'RUNNING_MODAL'}
        if t in {'RET', 'NUMPAD_ENTER', 'TAB'}:
            _commit_edit(context, area, region)
        elif t == 'ESC':
            HUD.edit = None
        elif t == 'BACK_SPACE':
            e['text'] = "" if (e['sel'] or event.ctrl or event.alt) else e['text'][:-1]
            e['sel'] = False
        elif t == 'DEL':
            if e['sel']:
                e['text'] = ""
            e['sel'] = False
        elif t == 'A' and (event.ctrl or event.oskey):
            e['sel'] = True
        elif t == 'V' and (event.ctrl or event.oskey):
            clip = context.window_manager.clipboard.strip()
            e['text'] = clip if e['sel'] else e['text'] + clip
            e['sel'] = False
        elif event.unicode and event.unicode.isprintable() and not (event.ctrl or event.oskey):
            e['text'] = event.unicode if e['sel'] else e['text'] + event.unicode
            e['sel'] = False
        area.tag_redraw()
        return {'RUNNING_MODAL'}   # never let typed keys trigger shortcuts (Y, G, ...)

    # ------------------------------------------------------------------- drag
    def _handle_drag(self, context, event, area, region, mx, my):
        d = HUD.drag
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            HUD.mouse = (mx, my)
            _drag_update(context, d, event, region, mx, my)
            area.tag_redraw()
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            HUD.drag = None
            # the layout may have moved under the mouse: re-hit-test on next move
            HUD.hover = None
            context.window.cursor_modal_restore()
            _drag_finish(context, d, area, region, event)
            area.tag_redraw()
        elif event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            HUD.drag = None
            context.window.cursor_modal_restore()
            _drag_cancel(context, d)
            area.tag_redraw()
        return {'RUNNING_MODAL'}
