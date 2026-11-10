# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Mouse / keyboard interaction with the panel: clicks, drags, text editing."""

import math
import re

import bpy
from bpy.app.handlers import persistent

from .state import HUD, _PERSIST, _POPUP
from .utils import (
    _active_object, _clamp_panel, _clean_error, _data_path, _edit_lock, _get_modifier, _hit,
    _key_target, _mod_lock, _mod_uid, _rna_of, _scale, _start_text_edit, _status,
    _supports_modifiers, _tag_all_view3d, _undo_push,
)
from .widgets import _arrow_zone
from .popups import _pickable, VIEW3D_MT_modperf_lite_add, VIEW3D_PT_modperf_lite_popup
from .operators import _close_hud, _run_action


@persistent
def _on_depsgraph_update(scene, depsgraph):
    """Collapse modifiers as soon as they are added (before the next redraw)."""
    if HUD.running:
        HUD.layout_dirty = True
        try:
            if _collapse_new_modifiers(bpy.context):
                _tag_all_view3d()
        except Exception:
            pass


def _collapse_new_modifiers(context):
    """Modifiers added while the panel is open start collapsed.
    The stack of the active object is remembered; anything new is collapsed
    (switching to another object only records its stack)."""
    obj = _active_object(context)
    if not _supports_modifiers(obj) or HUD.no_collapse:
        return False
    try:
        key = obj.name_full
        uids = {_mod_uid(md) for md in obj.modifiers}
    except ReferenceError:
        return False
    known = HUD.known_mods.get(key)
    HUD.known_mods[key] = uids
    if known is None:
        return False
    changed = False
    for md in obj.modifiers:
        if _mod_uid(md) not in known and md.show_expanded:
            md.show_expanded = False
            changed = True
    return changed


_NODE_INPUTS = {}   # object name -> snapshot of its Geometry Nodes modifier inputs


def _node_inputs_snapshot(obj):
    snap = []
    for md in obj.modifiers:
        if md.type != 'NODES':
            continue
        try:
            inputs = md.properties.inputs
        except AttributeError:
            continue
        vals = [md.name, md.node_group.name_full if md.node_group else ""]
        for p in inputs.bl_rna.properties:
            if p.identifier in {"rna_type", "name"}:
                continue
            v = getattr(getattr(inputs, p.identifier, None), "value", None)
            if hasattr(v, "name_full"):
                v = v.name_full
            elif hasattr(v, "__len__") and not isinstance(v, str):
                v = tuple(v)
            vals.append(v)
        snap.append(tuple(vals))
    return tuple(snap)


def _sync_node_inputs(context):
    """Re-evaluate the active object when one of its Geometry Nodes modifier
    inputs changed (e.g. the node-based Array modifier).

    In Blender 5.2, setting modifier.properties.inputs.<socket>.value from
    Python stores the value but doesn't tag the object for re-evaluation, so
    the viewport would keep showing the old result. Comparing a snapshot after
    each event catches every way a value can change: dragging or typing in the
    panel or the native value popups.
    """
    obj = _active_object(context)
    if not _supports_modifiers(obj):
        return False
    try:
        key = obj.name_full
        snap = _node_inputs_snapshot(obj)
    except ReferenceError:
        return False
    old = _NODE_INPUTS.get(key)
    _NODE_INPUTS[key] = snap
    if old is not None and old != snap:
        obj.update_tag()
        return True
    return False


def _duplicate_modifier_shortcut(context, area, region, mx, my):
    obj = _active_object(context)
    if not _supports_modifiers(obj) or not len(obj.modifiers):
        return
    name = None
    for n, top, hb, bb in HUD.headers:            # modifier block under the mouse
        if bb <= my <= top and n in obj.modifiers:
            name = n
            break
    if name is None:
        act = obj.modifiers.active
        name = act.name if act is not None else None
    if name is None:
        _status("No modifier selected")
        return
    src = obj.modifiers[name]
    expanded = src.show_expanded
    before = {_mod_uid(md) for md in obj.modifiers}
    HUD.no_collapse = True
    try:
        _run_action(context, area, region, 'DUPLICATE', name)
        for md in obj.modifiers:
            if _mod_uid(md) not in before:
                md.show_expanded = expanded            # keep the source's open state
                obj.modifiers.active = md
                _status(f"Duplicated '{name}' as '{md.name}'")
    finally:
        HUD.known_mods[obj.name_full] = {_mod_uid(md) for md in obj.modifiers}
        HUD.no_collapse = False


def _open_popup(context, area, region, **target):
    _POPUP.clear()
    _POPUP.update(target)
    with context.temp_override(area=area, region=region):
        bpy.ops.wm.call_panel(name=VIEW3D_PT_modperf_lite_popup.bl_idname, keep_open=True)


def _get_num(mod, pid, idx):
    v = getattr(mod, pid)
    return v[idx] if idx >= 0 else v


def _set_num(mod, pid, idx, value):
    if idx >= 0:
        getattr(mod, pid)[idx] = value
    else:
        setattr(mod, pid, value)


def _no_modifier_object_message(context, obj, kind, not_selected=None):
    """Short message when the action needs a selected object that supports modifiers."""
    if obj is None or not_selected is not None:
        title, line = "No Object Selected", "Select an object to add a modifier."
    else:
        title, line = "Modifiers Not Supported", "Select a mesh, curve or similar object."
    _status(f"{title}: {line}")

    def draw(self, _context):
        self.layout.label(text=line)
    try:
        context.window_manager.popup_menu(draw, title=title, icon='INFO')
    except Exception:
        pass


def _run_modifier_op(context, area, region, obj, mod, idname, props):
    """Operator button inside a modifier panel (Bind, Apply Base, Refresh...)."""
    cat, opname = idname.split(".", 1)
    try:
        op = getattr(getattr(bpy.ops, cat), opname)
        rna_props = op.get_rna_type().properties
        kw = dict(props)
        if 'modifier' in rna_props and 'modifier' not in kw:
            kw['modifier'] = mod.name
        with context.temp_override(area=area, region=region, object=obj, active_object=obj,
                                   modifier=mod):
            op('INVOKE_DEFAULT', True, **kw)      # True: push an undo step like a UI button
    except (RuntimeError, TypeError, AttributeError) as ex:
        _status(_clean_error(ex))


def _press(context, w, event, area, region, mx, my, double=False):
    kind, name, pid, idx = w['kind'], w['mod'], w['prop'], w['idx']
    win = context.window

    if kind in {'title', 'move_bg'}:
        HUD.drag = dict(type='move', sx=mx, sy=my, ox=HUD.x, oy=HUD.y)
        win.cursor_modal_set('HAND')
        return
    if kind == 'resize':
        HUD.drag = dict(type='resize', sx=mx, sy=my, ow=HUD.w, oh=HUD.max_h, top=HUD.y)
        win.cursor_modal_set('SCROLL_XY')
        return
    if kind == 'close':
        _close_hud(context)
        return

    obj = _active_object(context)
    if not _supports_modifiers(obj):
        if kind in {'add', 'collapse_all'}:
            _no_modifier_object_message(context, obj, kind)
        return
    # Linked / non-editable override objects: only folding panels is allowed
    # (Blender greys these modifiers out in the Properties editor).
    lock = _edit_lock(obj)
    if lock and kind not in {'expand', 'collapse_all', 'subpanel', 'gn_panel'}:
        _status(lock)
        return
    if kind == 'add':
        # Adding needs an active object that is also selected (highlighted).
        try:
            selected = obj.select_get()
        except RuntimeError:
            selected = False
        if not selected:
            _no_modifier_object_message(context, None, kind, not_selected=obj)
            return

    if kind == 'add':
        with context.temp_override(area=area, region=region):
            bpy.ops.wm.call_menu(name=VIEW3D_MT_modperf_lite_add.bl_idname)
        return
    if kind == 'collapse_all':
        expand = not any(md.show_expanded for md in obj.modifiers)
        for md in obj.modifiers:
            md.show_expanded = expand
        return

    if kind != 'num':
        HUD.multi = []

    obj, mod = _get_modifier(context, name)
    if mod is None:
        return
    if kind in {'remove', 'apply', 'move_up', 'move_down', 'grip'}:
        ml = _mod_lock(obj, mod)
        if ml:
            _status(ml)
            return
    if kind not in {'remove'}:
        obj.modifiers.active = mod

    if kind == 'expand':
        if event.ctrl:
            for md in obj.modifiers:
                md.show_expanded = md == mod
        else:
            mod.show_expanded = not mod.show_expanded
    elif kind == 'toggle':
        value = not getattr(mod, pid)
        setattr(mod, pid, value)
        # Keep the button held and drag over other toggles to set them too.
        HUD.drag = dict(type='booldrag', kind='toggle', prop=pid, value=value,
                        done={w['key']})
    elif kind == 'name':
        if double:
            _start_text_edit(('name', name, None, -1), name)   # rename in place
        else:
            HUD.drag = dict(type='reorder', mod=name, sy=my, active=False, target=None)
    elif kind == 'grip':
        # Drag handle: reorder by dragging up/down (Blender's panel grip).
        HUD.drag = dict(type='reorder', mod=name, sy=my, active=False, target=None)
        win.cursor_modal_set('MOVE_Y')
    elif kind == 'move_up':
        if obj.modifiers.find(name) > 0:
            _run_action(context, area, region, 'MOVE_UP', name)
    elif kind == 'move_down':
        if obj.modifiers.find(name) < len(obj.modifiers) - 1:
            _run_action(context, area, region, 'MOVE_DOWN', name)
    elif kind == 'apply':
        _run_action(context, area, region, 'APPLY', name)
    elif kind == 'remove':
        _run_action(context, area, region, 'REMOVE', name)
    elif kind == 'gn_panel':
        panels = list(getattr(mod, "panels", []))
        if 0 <= idx < len(panels):
            panels[idx].is_open = not panels[idx].is_open
    elif kind == 'bool':
        value = not _get_bool_key(context, w['key'])
        _set_bool_key(context, w['key'], value)
        # Keep the button held and drag over other checkboxes to set them too
        # (Blender's drag-toggle).
        HUD.drag = dict(type='booldrag', kind='bool', value=value, done={w['key']})
    elif kind == 'num':
        key = w['key']
        if event.shift:
            # Shift+click: add/remove this field from the multi-edit selection.
            if key in HUD.multi:
                HUD.multi.remove(key)
            else:
                HUD.multi.append(key)
            return
        group = list(HUD.multi) if key in HUD.multi else [key]
        if key not in HUD.multi:
            HUD.multi = []
        x0, _y0, x1, _y1 = w['rect']
        zone = _arrow_zone(_scale(), x1 - x0)
        if mx <= x0 + zone or mx >= x1 - zone:
            # Arrow ends: step the value(s) directly, no prompt.
            for k in group:
                _step_key(context, k, -1 if mx <= x0 + zone else 1)
            _undo_push(context, area, region, "Modifier value")
        else:
            # Middle: drag sideways to scrub, drag up/down over other fields
            # to gather them (Blender multi-value editing), or click to type.
            HUD.drag = dict(type='num', key=key, mod=name, prop=pid, idx=idx,
                            sx=mx, sy=my, mode='pending', moved=False,
                            group=group, starts=_starts(context, group))
            win.cursor_modal_set('SCROLL_X')
    elif kind == 'enum':
        owner, attr, p = _rna_of(mod, pid)
        if w.get('flag'):
            _open_popup(context, area, region, kind='prop', mod=name, prop=pid)
        else:
            with context.temp_override(area=area, region=region):
                bpy.ops.wm.context_menu_enum(data_path=_data_path(mod, pid))
    elif kind == 'popup':
        if _pickable(obj, mod, pid):
            _open_picker(context, area, region, name, pid)
        else:
            _open_popup(context, area, region, kind='prop', mod=name, prop=pid)
    elif kind == 'subpanel':
        op_ = w.get('open_prop')
        if op_ and hasattr(mod, op_):
            setattr(mod, op_, not getattr(mod, op_))
        else:
            st = _PERSIST.setdefault('subpanels', {})
            k = (obj.name, name, pid)
            if event.ctrl:            # Ctrl+click: open only this one (like Blender)
                for kk in [kk for kk in st if kk[0] == obj.name and kk[1] == name]:
                    st[kk] = False
            st[k] = not st.get(k, False)
    elif kind == 'enum_item':
        owner, attr, p = _rna_of(mod, pid)
        val = w['value']
        if w.get('flag'):
            cur = set(getattr(owner, attr))
            cur ^= {val}
            setattr(owner, attr, cur)
        else:
            setattr(owner, attr, val)
        _undo_push(context, area, region, "Modifier setting")
    elif kind == 'op':
        _run_modifier_op(context, area, region, obj, mod, pid, w.get('props') or {})
    elif kind == 'tmpl':
        _open_popup(context, area, region, kind='tmpl', mod=name, prop=pid, tmpl=w.get('tmpl'))
    elif kind == 'search':
        getter, coll = HUD.search_getters.get((name, pid), (None, None))
        _open_popup(context, area, region, kind='search', mod=name, prop=pid,
                    getter=getter, coll=coll)


def _get_bool_key(context, key):
    t = _key_target(context, key)
    if t is None:
        return False
    owner, attr, _p, idx = t
    v = getattr(owner, attr)
    return bool(v[idx] if idx >= 0 else v)


def _set_bool_key(context, key, value):
    t = _key_target(context, key)
    if t is None:
        return
    owner, attr, _p, idx = t
    if idx >= 0:
        getattr(owner, attr)[idx] = value
    else:
        setattr(owner, attr, value)


def _step_key(context, key, direction):
    t = _key_target(context, key)
    if t is not None:
        owner, attr, p, idx = t
        _step_num(owner, attr, p, idx, direction)


def _starts(context, keys):
    out = {}
    for k in keys:
        t = _key_target(context, k)
        if t is not None:
            owner, attr, _p, idx = t
            out[k] = _get_num(owner, attr, idx)
    return out


def _open_picker(context, area, region, mod_name, prop):
    with context.temp_override(area=area, region=region):
        bpy.ops.object.modperf_lite_pick('INVOKE_DEFAULT', modifier=mod_name, prop=prop)


def _is_angle(p):
    return p.subtype == 'ANGLE' or p.unit == 'ROTATION'


def _step_size(p):
    if p.type == 'INT':
        return max(1, int(p.step) if p.step else 1)
    if _is_angle(p):
        return math.radians(1.0)
    return max(p.step / 100.0, 0.001)


def _clamp_value(p, v):
    v = max(p.hard_min, min(p.hard_max, v))
    return int(round(v)) if p.type == 'INT' else float(v)


def _step_num(owner, attr, p, idx, direction):
    v = _get_num(owner, attr, idx) + direction * _step_size(p)
    _set_num(owner, attr, idx, _clamp_value(p, v))


# ---- inline typing in number fields ---------------------------------------------

def _edit_text(p, v, scene):
    if p.type == 'INT':
        return str(v)
    if _is_angle(p) and scene.unit_settings.system_rotation == 'DEGREES':
        return f"{round(math.degrees(v), 4):g}"
    return f"{round(v, 5):g}"


def _parse_value(p, text, scene):
    us = scene.unit_settings
    s = text.strip().replace(",", ".")
    if not s:
        return None
    if p.unit == 'LENGTH' and us.system != 'NONE' and any(c.isalpha() for c in s.replace("pi", "")):
        try:
            return bpy.utils.units.to_value(us.system, 'LENGTH', s) / (us.scale_length or 1.0)
        except ValueError:
            return None
    if not re.fullmatch(r"[0-9eE.+\-*/()% pi]*", s):
        return None
    try:
        v = float(eval(s, {"__builtins__": {}}, {"pi": math.pi}))
    except Exception:
        return None
    if _is_angle(p) and us.system_rotation == 'DEGREES':
        v = math.radians(v)
    return v


def _commit_text_edit(context, e, area, region):
    text = e['text'].strip()
    if not text:
        return
    kind, name = e['key'][0], e['key'][1]
    if kind == 'name':
        obj, mod = _get_modifier(context, name)
        if mod is not None and mod.name != text:
            mod.name = text
            _undo_push(context, area, region, "Rename Modifier")


def _start_edit(context, mod_name, pid, idx, group=None):
    obj, mod = _get_modifier(context, mod_name)
    if mod is None:
        return
    owner, attr, p = _rna_of(mod, pid)
    key = ('num', mod_name, pid, idx)
    HUD.edit = dict(key=key, mod=mod_name, prop=pid, idx=idx, group=list(group or [key]),
                    text=_edit_text(p, _get_num(owner, attr, idx), context.scene), sel=True)


def _commit_edit(context, area, region):
    """Apply the typed value to the field (and every field of a multi-edit)."""
    e, HUD.edit = HUD.edit, None
    HUD.multi = []
    if e is None:
        return
    if e.get('mode') == 'text':
        _commit_text_edit(context, e, area, region)
        return
    changed = bad = False
    for key in e.get('group') or [e['key']]:
        t = _key_target(context, key)
        if t is None:
            continue
        owner, attr, p, idx = t
        v = _parse_value(p, e['text'], context.scene)
        if v is None:
            bad = True
            continue
        _set_num(owner, attr, idx, _clamp_value(p, v))
        changed = True
    if bad and e['text'].strip():
        _status(f"Invalid value: {e['text']}")
    if changed:
        _undo_push(context, area, region, "Modifier value")


def _num_drag_value(p, start, dx, event):
    S = _scale()
    fine = 0.1 if event.shift else 1.0
    if p.type == 'INT':
        val = start + int(round(dx * fine / (8 * S)))
        val = max(p.hard_min, min(p.hard_max, val))
        return val
    rng = p.soft_max - p.soft_min
    if p.subtype in {'FACTOR', 'PERCENTAGE'} and 0 < rng <= 1000:
        per_px = rng / (300 * S)                       # slider: full range ~300 pt
    elif p.subtype == 'ANGLE' or p.unit == 'ROTATION':
        per_px = math.radians(0.5) / S                 # 0.5 degree per point
    else:
        # one RNA step per point, at least 1/10000 of the soft range
        span = rng / 10000.0 if 0 < rng <= 1e5 else 0.0
        per_px = max(p.step / 100.0, span, 0.001) / S
    val = start + dx * per_px * fine
    if event.ctrl:
        if p.subtype == 'ANGLE' or p.unit == 'ROTATION':
            val = math.radians(round(math.degrees(val)))
        else:
            snap = 10 ** math.floor(math.log10(max(per_px * 20 * S, 1e-6)))
            val = round(val / snap) * snap
    return max(p.hard_min, min(p.hard_max, val))


def _drag_update(context, d, event, region, mx, my):
    t = d['type']
    if t == 'move':
        HUD.x = d['ox'] + (mx - d['sx'])
        HUD.y = d['oy'] + (my - d['sy'])
        _clamp_panel(region)
    elif t == 'resize':
        S = _scale()
        HUD.w = max(round(240 * S), d['ow'] + (mx - d['sx']))
        HUD.max_h = max(round(150 * S), d['oh'] + (d['sy'] - my))
    elif t == 'num':
        S = _scale()
        dx, dy = mx - d['sx'], my - d['sy']
        if d['mode'] == 'pending':
            if abs(dy) > 6 * S and abs(dy) > abs(dx):
                d['mode'] = 'select'               # gather fields by dragging up/down
                context.window.cursor_modal_set('MOVE_Y')
            elif abs(dx) > 3 * S:
                d['mode'] = 'value'
        if d['mode'] == 'select':
            w = _hit(d['sx'], my)
            if w is not None and w['kind'] == 'num' and w['key'] not in d['group']:
                d['group'].append(w['key'])
                d['starts'].update(_starts(context, [w['key']]))
            if abs(dx) > 10 * S:                   # now drag sideways to change them all
                d['mode'] = 'value'
                d['sx'] = mx
                context.window.cursor_modal_set('SCROLL_X')
            return
        if d['mode'] != 'value':
            return
        d['moved'] = True
        dx = mx - d['sx']
        for key in d['group']:
            tgt = _key_target(context, key)
            if tgt is None or key not in d['starts']:
                continue
            owner, attr, p, idx = tgt
            _set_num(owner, attr, idx, _num_drag_value(p, d['starts'][key], dx, event))
    elif t == 'booldrag':
        w = _hit(mx, my)
        if w is not None and w['kind'] == d['kind'] and w['key'] not in d['done']:
            d['done'].add(w['key'])
            if d['kind'] == 'toggle':
                obj, mod = _get_modifier(context, w['mod'])
                if mod is not None:
                    setattr(mod, w['prop'], d['value'])
            else:
                _set_bool_key(context, w['key'], d['value'])
    elif t == 'reorder':
        S = _scale()
        if not d['active']:
            if abs(my - d['sy']) <= 5 * S:
                return
            blk = next((h for h in HUD.headers if h[0] == d['mod']), None)
            if blk is None or len(HUD.headers) < 2:
                return
            # Snapshot the stack as it was when the drag began.
            d['active'] = True
            d['blocks'] = list(HUD.headers)        # (name, top, header_bottom, bottom)
            d['orig'] = [h[0] for h in HUD.headers].index(d['mod'])
            d['grab'] = d['sy'] - blk[1]           # mouse offset from the block's top
            context.window.cursor_modal_set('MOVE_Y')
        # The dragged modifier follows the mouse; work out where it would land
        # among the others. A neighbour changes places with the dragged block
        # once the block covers more than half of it: the block's leading edge
        # (bottom when dragging down, top when dragging up) passes the
        # neighbour's centre, measured in the layout as it was when the drag
        # began. The same travel is needed in both directions.
        d['float_top'] = my - d['grab']
        blocks = d['blocks']
        height = blocks[d['orig']][1] - blocks[d['orig']][3]
        float_bottom = d['float_top'] - height
        target = 0
        for i, b in enumerate(blocks):
            if i == d['orig']:
                continue
            center = (b[1] + b[3]) / 2
            edge = float_bottom if i > d['orig'] else d['float_top']
            if center > edge:
                target += 1
        d['target'] = target


def _drag_finish(context, d, area, region, event=None):
    t = d['type']
    if t == 'num':
        if d['moved']:
            HUD.multi = []
            _undo_push(context, area, region, "Modifier value")
        else:
            # Click (or gather without changing): type in place for all of them.
            _start_edit(context, d['mod'], d['prop'], d['idx'], group=d['group'])
    elif t == 'booldrag':
        _undo_push(context, area, region, "Modifier setting")
    elif (t == 'reorder' and d['active'] and d['target'] is not None
          and d['target'] != d.get('orig')):
        _run_action(context, area, region, 'MOVE_TO', d['mod'], d['target'])


def _drag_cancel(context, d):
    obj, mod = _get_modifier(context, d.get('mod'))
    if mod is None:
        if d['type'] == 'move':
            HUD.x, HUD.y = d['ox'], d['oy']
        return
    if d['type'] == 'num':
        for key, start in d['starts'].items():
            tgt = _key_target(context, key)
            if tgt is not None:
                owner, attr, _p, idx = tgt
                _set_num(owner, attr, idx, start)
        HUD.multi = []
