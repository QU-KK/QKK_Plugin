# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Small helpers: theme colours, status line, active object, RNA access, undo."""

import math
import re
import time

import blf
import bpy

from .constants import FONT, HIDDEN_PROPS, MODIFIER_OBJECT_TYPES
from .state import HUD


# =============================================================================
# Small helpers
# =============================================================================

def _scale():
    return bpy.context.preferences.system.ui_scale


def _theme():
    return bpy.context.preferences.themes[0].user_interface


def _col(c, alpha=None, lift=0.0):
    t = list(c)[:4]
    if len(t) == 3:
        t.append(1.0)
    if lift:
        t[0], t[1], t[2] = (min(1.0, max(0.0, v + lift)) for v in t[:3])
    if alpha is not None:
        t[3] = alpha
    return tuple(t)


def _status(msg):
    HUD.status = msg
    HUD.status_time = time.monotonic()


def _active_object(context):
    vl = getattr(context, "view_layer", None)
    return vl.objects.active if vl else None


def _supports_modifiers(obj):
    return obj is not None and obj.type in MODIFIER_OBJECT_TYPES


def _edit_lock(obj):
    """Why the object's modifiers can't be edited (linked data), or "" if they can."""
    try:
        if obj is None:
            return ""
        if obj.library is not None:
            return "Linked object: its modifiers can't be edited (make a library override first)"
        ov = obj.override_library
        if ov is not None and ov.is_system_override:
            return "Non-editable override: make it editable to change its modifiers"
    except ReferenceError:
        return "Object no longer exists"
    return ""


def _mod_lock(obj, mod):
    """Why this modifier can't be removed / moved / applied (it comes from a linked file)."""
    lock = _edit_lock(obj)
    if lock:
        return lock
    try:
        if obj.override_library is not None and getattr(mod, "is_override_data", False):
            return "This modifier comes from the linked file and can't be removed, moved or applied"
    except ReferenceError:
        return "Modifier no longer exists"
    return ""


def _clean_error(msg):
    """Turn Blender operator errors into a short, readable message."""
    msg = str(msg).replace("Error: ", "").strip()
    msg = re.sub(r"^Operator bpy\.ops\.[\w.]+\.poll\(\)\s*", "", msg)
    if "failed, context is incorrect" in msg or not msg:
        return "This action isn't available here"
    if "not allowed from Edit mode" in msg or "in edit mode" in msg.lower():
        return "Not available in Edit Mode: switch to Object Mode first"
    return msg.splitlines()[0]


def _get_modifier(context, name):
    obj = _active_object(context)
    if not _supports_modifiers(obj) or not name:
        return obj, None
    return obj, obj.modifiers.get(name)


def _owner_attr(mod, prop):
    """Resolve a widget property path to (owner struct, attribute name).

    'levels'       -> (modifier, 'levels')
    'in:Socket_5'  -> (modifier.properties.inputs.Socket_5, 'value')
                      Geometry Nodes inputs (Blender 5.x stores them as RNA,
                      e.g. the node-based Array modifier).
    """
    if prop.startswith("in:"):
        return getattr(mod.properties.inputs, prop[3:]), "value"
    if "." in prop:                         # e.g. 'projectors[0].object'
        head, attr = prop.rsplit(".", 1)
        return mod.path_resolve(head), attr
    return mod, prop


def _rna_of(mod, prop):
    owner, attr = _owner_attr(mod, prop)
    return owner, attr, owner.bl_rna.properties[attr]


def _data_path(mod, prop):
    base = f'object.modifiers["{bpy.utils.escape_identifier(mod.name)}"]'
    if prop.startswith("in:"):
        return f"{base}.properties.inputs.{prop[3:]}.value"
    return f"{base}.{prop}"


def _setting_props(mod):
    for p in mod.bl_rna.properties:
        pid = p.identifier
        if (pid in HIDDEN_PROPS or pid.startswith("open_") or p.is_readonly
                or p.type == 'COLLECTION' or getattr(p, "is_hidden", False)):
            continue
        # Bevel: "Width" and "Width Percent" are one stored value; like Blender,
        # show only the one that matches the Width Type.
        # Hook: internal matrices Blender doesn't show (set by Reset / Recenter).
        if mod.type == 'HOOK' and pid in {'matrix_inverse', 'center'}:
            continue
        if mod.type == 'BEVEL' and pid in {'width', 'width_pct'}:
            if (pid == 'width_pct') != (mod.offset_type == 'PERCENT'):
                continue
        yield p


def _fit(text, max_w):
    if max_w <= 0:
        return ""
    if blf.dimensions(FONT, text)[0] <= max_w:
        return text
    ell = "…"
    while text and blf.dimensions(FONT, text + ell)[0] > max_w:
        text = text[:-1]
    return text + ell if text else ""


def _enum_text(prop, value):
    items = {i.identifier: i.name for i in prop.enum_items}
    if prop.is_enum_flag:
        return ", ".join(items.get(v, v) for v in sorted(value)) or "None"
    return items.get(value, str(value))


def _fmt_float(prop, v, scene):
    prec = max(prop.precision, 1) if prop.precision else 3
    us = scene.unit_settings
    if prop.subtype == 'ANGLE' or prop.unit == 'ROTATION':
        if us.system_rotation == 'DEGREES':
            return f"{round(math.degrees(v), 2):g}°"
        return f"{v:.{prec}f}"
    if prop.subtype == 'PERCENTAGE':
        return f"{v:.{min(prec, 1)}f} %"
    if prop.unit == 'LENGTH' and us.system != 'NONE':
        try:
            return bpy.utils.units.to_string(us.system, 'LENGTH',
                                             v * us.scale_length, precision=prec)
        except Exception:
            pass
    return f"{v:.{prec}f}"


def _fmt_value(prop, v, scene):
    if prop.type == 'INT':
        return f"{v}%" if prop.subtype == 'PERCENTAGE' else str(v)
    return _fmt_float(prop, v, scene)


def _region_from_ptrs(context):
    """Return (window, area, region) of the HUD or (None, None, None)."""
    wm = context.window_manager
    for win in wm.windows:
        if win.as_pointer() != HUD.window_ptr:
            continue
        for area in win.screen.areas:
            if area.as_pointer() != HUD.area_ptr:
                continue
            for region in area.regions:
                if region.as_pointer() == HUD.region_ptr:
                    return win, area, region
    return None, None, None


def _tag_all_view3d(context=None):
    wm = (context or bpy.context).window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _undo_push(context, area, region, message):
    try:
        with context.temp_override(area=area, region=region):
            bpy.ops.ed.undo_push(message=message)
    except Exception:
        pass


def _data_collection_for(fixed_type):
    """bpy.data collection name holding IDs of the given RNA struct type."""
    if fixed_type is None:
        return None
    for p in bpy.data.bl_rna.properties:
        if p.type == 'COLLECTION' and p.fixed_type and p.fixed_type.identifier == fixed_type.identifier:
            return p.identifier
    return None


def _free_rect(area, region):
    """Part of the viewport not covered by overlapping toolbar / sidebar / header."""
    x0, y0, x1, y1 = 0, 0, region.width, region.height
    for r in area.regions:
        if r == region or r.width <= 1 or r.height <= 1:
            continue
        rx0, ry0 = r.x - region.x, r.y - region.y
        rx1, ry1 = rx0 + r.width, ry0 + r.height
        if ry1 <= y0 or ry0 >= y1 or rx1 <= x0 or rx0 >= x1:
            continue  # does not overlap
        if r.type in {'UI', 'TOOL_PROPS'} and rx0 > region.width / 2:
            x1 = min(x1, rx0)
        elif r.type == 'TOOLS' and rx1 < region.width / 2:
            x0 = max(x0, rx1)
        elif r.type in {'HEADER', 'TOOL_HEADER'} and ry0 > region.height / 2:
            y1 = min(y1, ry0)
        elif r.type in {'HEADER', 'TOOL_HEADER'} and ry1 < region.height / 2:
            y0 = max(y0, ry1)
    return x0, y0, x1, y1


def _clamp_panel(region, fit=False, area=None):
    """Keep the panel reachable. fit=True keeps it inside the free viewport area."""
    S = _scale()
    if fit:
        x0, y0, x1, y1 = _free_rect(area, region) if area else (0, 0, region.width, region.height)
        HUD.max_h = max(round(150 * S), min(HUD.max_h, y1 - y0))
        h = HUD.h        # 0 while opening: the first build nudges it up if needed
        HUD.x = max(x0, min(x1 - HUD.w, HUD.x))
        HUD.y = max(y0 + h, min(y1, HUD.y))
        return
    keep = 60 * S
    HUD.x = max(keep - HUD.w, min(region.width - keep, HUD.x))
    HUD.y = max(round(25 * S), min(region.height, HUD.y))


# =============================================================================
# Interaction
# =============================================================================

def _mod_uid(md):
    return getattr(md, "persistent_uid", None) or md.name


def _is_new_modifier(mod):
    if HUD.no_collapse:
        return False
    try:
        known = HUD.known_mods.get(mod.id_data.name_full)
    except ReferenceError:
        return False
    return known is not None and _mod_uid(mod) not in known


def _hit(mx, my):
    for w in reversed(HUD.widgets):
        x0, y0, x1, y1 = w['rect']
        if x0 <= mx <= x1 and y0 <= my <= y1:
            return w
    return None


# ---- multi-value helpers ---------------------------------------------------------
# A widget key is (kind, modifier name, property path, array index).

def _key_target(context, key):
    """Return (owner, attr, rna_prop, idx) for a widget key, or None."""
    _kind, mod_name, pid, idx = key
    obj, mod = _get_modifier(context, mod_name)
    if mod is None or pid is None:
        return None
    try:
        owner, attr, p = _rna_of(mod, pid)
    except (AttributeError, KeyError):
        return None
    return owner, attr, p, idx


def _selected_keys():
    """Number fields drawn as selected (multi-value editing)."""
    keys = set(HUD.multi)
    d = HUD.drag
    if d and d.get('type') == 'num' and (len(d['group']) > 1 or d['mode'] == 'select'):
        keys.update(d['group'])
    e = HUD.edit
    if e and len(e.get('group', ())) > 1:
        keys.update(e['group'])
    return keys


def _start_text_edit(key, text):
    """Rename in place (modifier name or object name in the outliner)."""
    HUD.edit = dict(key=key, mode='text', mod=key[1], prop=None, idx=-1, group=[key],
                    text=text, sel=True)
