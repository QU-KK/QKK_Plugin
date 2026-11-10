# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Blender-style tooltips (label, description, value, Python path)."""

import blf
import bpy

from .constants import BLOCK_RADIUS, FONT, PROP_WIDGETS, WIDGET_OPERATORS
from .state import HUD
from .utils import _active_object, _col, _key_target, _scale, _theme


def _rna_tip(struct, prop):
    p = struct.bl_rna.properties[prop]
    return f"{p.name}\n{_sentence(p.description)}"


# =============================================================================
# Tooltips (Blender-style: label, description, current value, Python path)
# =============================================================================

def _sentence(text):
    text = (text or "").strip()
    if text and text[-1] not in ".!?:":
        text += "."
    return text


def _op_tooltip(idname, show_py):
    group, fn = idname.split(".")
    try:
        rna = getattr(getattr(bpy.ops, group), fn).get_rna_type()
        lines = [(rna.name, 'title')]
        if rna.description:
            lines.append((_sentence(rna.description), 'body'))
    except (AttributeError, KeyError):
        lines = [(idname, 'title')]
    if show_py:
        lines.append((f"Python: bpy.ops.{idname}()", 'python'))
    return lines


def _tooltip_lines(context, w):
    """Lines of (text, style) for the widget under the mouse."""
    show_py = context.preferences.view.show_tooltips_python
    kind = w['kind']
    if kind in WIDGET_OPERATORS:
        return _op_tooltip(WIDGET_OPERATORS[kind], show_py)
    if kind == 'op' and w.get('prop'):
        lines = _op_tooltip(w['prop'], show_py)
        if lines and w.get('label'):
            lines[0] = (w['label'], 'title')
        return lines

    if kind in PROP_WIDGETS and w.get('mod') and w.get('prop'):
        tgt = _key_target(context, w['key'])
        if tgt is not None:
            owner, attr, p, idx = tgt
            label = w.get('label') or p.name or attr
            desc = w.get('desc')
            if desc is None:
                desc = p.description
            lines = [(label, 'title')]
            if desc:
                lines.append((_sentence(desc), 'body'))
            if p.type == 'ENUM' and not p.is_enum_flag:
                cur = getattr(owner, attr)
                item = next((i for i in p.enum_items if i.identifier == cur), None)
                if item is not None:
                    lines.append((f"{item.name}: {_sentence(item.description)}"
                                  if item.description else item.name, 'value'))
            if show_py:
                obj = _active_object(context)
                esc = bpy.utils.escape_identifier
                path = (f'bpy.data.objects["{esc(obj.name)}"]'
                        f'.modifiers["{esc(w["mod"])}"]')
                pid = w['prop']
                path += (f".properties.inputs.{pid[3:]}.value" if pid.startswith("in:")
                         else f".{attr}")
                if idx >= 0:
                    path += f"[{idx}]"
                lines.append((f"Python: {owner.bl_rna.identifier}.{attr}", 'python'))
                lines.append((path, 'python'))
            return lines

    tip = w.get('tip') or ""
    if not tip:
        return []
    parts = tip.split("\n")
    return [(parts[0], 'title')] + [(t, 'body') for t in parts[1:] if t]


def _wrap(text, max_w):
    words, out, line = text.split(" "), [], ""
    for word in words:
        trial = f"{line} {word}" if line else word
        if line and blf.dimensions(FONT, trial)[0] > max_w:
            out.append(line)
            line = word
        else:
            line = trial
    if line:
        out.append(line)
    return out


def _build_tooltip(region):
    S = _scale()
    ui = _theme()
    wc = ui.wcol_tooltip
    blf.size(FONT, round(11 * S))
    cap = blf.dimensions(FONT, "X")[1]
    pad = round(7 * S)
    lh = round(17 * S)
    max_w = round(300 * S)
    text = _col(wc.text)
    styles = {'title': text, 'body': _col(wc.text, alpha=0.85),
              'value': _col(wc.text, alpha=0.85), 'python': _col(wc.text, alpha=0.55)}
    rows, prev = [], None
    for txt, style in HUD.tip_lines:
        if prev is not None and style != prev and style in {'value', 'python'}:
            rows.append(("", None))                   # small gap between sections
        for seg in _wrap(txt, max_w):
            rows.append((seg, style))
        prev = style
    if not rows:
        return []
    w = max(blf.dimensions(FONT, t)[0] for t, _s in rows if t) + 2 * pad
    h = len(rows) * lh + 2 * pad - (lh - cap) // 2
    mx, my = HUD.mouse
    x0 = mx + round(14 * S)
    y1 = my - round(20 * S)
    if x0 + w > region.width - 4:
        x0 = max(4, region.width - 4 - w)
    if y1 - h < 4:
        y1 = min(region.height - 4, my + round(28 * S) + h)
    y0 = y1 - h
    items = [('rect', x0 + 2 * S, y0 - 3 * S, x0 + w + 2 * S, y1 - 1 * S, (0, 0, 0, 0.30),
              BLOCK_RADIUS * S),
             ('rect', x0, y0, x0 + w, y1, _col(wc.inner, alpha=0.98), BLOCK_RADIUS * S),
             ('outline', x0, y0, x0 + w, y1, _col(wc.outline), BLOCK_RADIUS * S)]
    y = y1 - pad - cap
    for t, style in rows:
        if t:
            items.append(('text', x0 + pad, y, t, styles.get(style, text)))
        y -= lh
    return items
