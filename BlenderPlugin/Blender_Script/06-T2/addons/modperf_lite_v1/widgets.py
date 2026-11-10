# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Layout builder, vector icons and the basic widgets (buttons, fields, toggles)."""

import math

import blf

from .constants import AXIS_LETTERS, COLOR_OPACITY, FONT, VECTOR_SUBTYPES, WIDGET_RADIUS
from .state import HUD
from .utils import _col, _enum_text, _fit, _fmt_value, _scale, _theme
from .gpu_draw import _bicon


# =============================================================================
# Layout builder
# =============================================================================

class _Metrics:
    def __init__(self, context):
        self.S = S = _scale()
        self.U = round(20 * S)
        self.pad = round(6 * S)
        self.g = max(1, round(2 * S))
        self.fs = round(11 * S)
        blf.size(FONT, self.fs)
        self.cap = blf.dimensions(FONT, "X")[1]
        self.ui = _theme()
        self.scene = context.scene
        self.W = HUD.w
        self.cw = self.W - 2 * self.pad
        ui = self.ui
        self.text = _col(ui.panel_text)
        self.dim = _col(ui.panel_text, alpha=0.55)
        # property labels: a little softer than values, but readable in light themes too
        self.label = _col(ui.panel_text, alpha=0.82)
        self.off = _col(ui.panel_text, alpha=0.30)


class _Builder:
    """Collects draw items and widgets; supports per-row culling."""

    def __init__(self, m):
        self.m = m
        self.items = []
        self.widgets = []
        self.y = 0.0
        self.row = None

    def new_row(self, h):
        top = self.y
        self.y -= h
        self.row = (top, self.y)
        return top, self.y

    def add(self, *item):
        self.items.append((self.row, item))

    def widget(self, x0, y0, x1, y1, kind, mod=None, prop=None, idx=-1, tip="", **extra):
        w = dict(rect=(x0, y0, x1, y1), key=(kind, mod, prop, idx), kind=kind,
                 mod=mod, prop=prop, idx=idx, tip=tip)
        w.update(extra)
        self.widgets.append((self.row, w))
        return HUD.hover == w['key']

    def text(self, x, yc, s, col, max_w=None, align='L'):
        if max_w is not None:
            s = _fit(s, max_w)
        if not s:
            return
        tw = blf.dimensions(FONT, s)[0]
        if align == 'C' and max_w is not None:
            x += (max_w - tw) / 2
        elif align == 'R' and max_w is not None:
            x += max_w - tw
        self.add('text', x, yc - self.m.cap / 2, s, col)


# ---- icons ------------------------------------------------------------------

def _icon_arrow(b, cx, cy, S, down, col):
    if _bicon(b, 'disclosure_tri_down' if down else 'disclosure_tri_right', cx, cy, S, col):
        return
    k = 3.5 * S
    if down:
        pts = [(cx - k, cy + k * 0.5), (cx + k, cy + k * 0.5), (cx, cy - k * 0.7)]
    else:
        pts = [(cx - k * 0.5, cy + k), (cx - k * 0.5, cy - k), (cx + k * 0.7, cy)]
    b.add('tris', pts, col)


def _icon_x_bold(b, cx, cy, S, col):
    """Bold X (remove-modifier button): thick strokes with rounded ends."""
    k = 3.6 * S
    w = max(2.0, 2.3 * S)
    b.add('lines', [(cx - k, cy - k), (cx + k, cy + k), (cx - k, cy + k), (cx + k, cy - k)], col, w)
    r = w * 0.5
    for x, y in ((cx - k, cy - k), (cx + k, cy + k), (cx - k, cy + k), (cx + k, cy - k)):
        _disc(b, x, y, r, col, 8)


def _icon_x(b, cx, cy, S, col):
    if _bicon(b, 'x', cx, cy, S, col):
        return
    k = 3.5 * S
    b.add('lines', [(cx - k, cy - k), (cx + k, cy + k), (cx - k, cy + k), (cx + k, cy - k)], col)


def _icon_plus(b, cx, cy, S, col):
    if _bicon(b, 'add', cx, cy, S, col):
        return
    k = 4 * S
    b.add('lines', [(cx - k, cy), (cx + k, cy), (cx, cy - k), (cx, cy + k)], col)


def _icon_check(b, cx, cy, S, col):
    k = S
    b.add('lines', [(cx - 3.5 * k, cy + 0.2 * k), (cx - 1 * k, cy - 2.6 * k),
                    (cx - 1 * k, cy - 2.6 * k), (cx + 3.8 * k, cy + 3 * k)], col)


def _icon_viewport(b, cx, cy, S, col):
    if _bicon(b, 'restrict_view_off', cx, cy, S, col):
        return
    k = S
    x0, x1, y0, y1 = cx - 5.5 * k, cx + 5.5 * k, cy - 1.5 * k, cy + 5 * k
    b.add('lines', [(x0, y0), (x1, y0), (x1, y0), (x1, y1), (x1, y1), (x0, y1), (x0, y1), (x0, y0),
                    (cx, y0), (cx, cy - 4.5 * k), (cx - 3 * k, cy - 4.5 * k), (cx + 3 * k, cy - 4.5 * k)], col)


def _icon_render(b, cx, cy, S, col, on=True):
    if _bicon(b, 'restrict_render_off' if on else 'restrict_render_on', cx, cy, S, col):
        return
    k = S
    x0, x1, y0, y1 = cx - 6 * k, cx + 2 * k, cy - 3.5 * k, cy + 3.5 * k
    b.add('lines', [(x0, y0), (x1, y0), (x1, y0), (x1, y1), (x1, y1), (x0, y1), (x0, y1), (x0, y0),
                    (x1, cy), (cx + 6 * k, cy + 3.5 * k), (x1, cy), (cx + 6 * k, cy - 3.5 * k),
                    (cx + 6 * k, cy + 3.5 * k), (cx + 6 * k, cy - 3.5 * k)], col)


def _icon_edit(b, cx, cy, S, col):
    if _bicon(b, 'editmode_hlt', cx, cy, S, col):
        return
    k = S
    s = 4.5 * k
    b.add('lines', [(cx - s, cy - s), (cx + s, cy - s), (cx + s, cy - s), (cx + s, cy + s),
                    (cx + s, cy + s), (cx - s, cy + s), (cx - s, cy + s), (cx - s, cy - s)], col)
    d = 1.6 * k
    for vx, vy in ((cx - s, cy - s), (cx + s, cy - s), (cx + s, cy + s), (cx - s, cy + s)):
        b.add('rect', vx - d, vy - d, vx + d, vy + d, col, 0)


def _icon_up(b, cx, cy, S, col):
    k = 3.6 * S
    b.add('tris', [(cx - k, cy - k * 0.55), (cx + k, cy - k * 0.55), (cx, cy + k * 0.75)], col)


def _icon_down(b, cx, cy, S, col):
    k = 3.6 * S
    b.add('tris', [(cx - k, cy + k * 0.55), (cx + k, cy + k * 0.55), (cx, cy - k * 0.75)], col)


def _icon_dots(b, cx, cy, S, col):
    """Drag handle (like the ':::' grip on Blender's panels)."""
    if _bicon(b, 'grip', cx, cy, S, col):
        return
    d = 1.1 * S
    for dx in (-2.2 * S, 2.2 * S):
        for dy in (-4 * S, 0, 4 * S):
            b.add('rect', cx + dx - d, cy + dy - d, cx + dx + d, cy + dy + d, col, 0)


def _icon_grip(b, x1, y0, S, col):
    for i in (3, 6, 9):
        k = i * S
        b.add('lines', [(x1 - k, y0 + 2 * S), (x1 - 2 * S, y0 + k)], col)


def _icon_collapse(b, cx, cy, S, col):
    k = 3 * S
    b.add('tris', [(cx - k, cy + 1 * S), (cx + k, cy + 1 * S), (cx, cy + k + 2 * S)], col)
    b.add('tris', [(cx - k, cy - 1 * S), (cx + k, cy - 1 * S), (cx, cy - k - 2 * S)], col)


_ICONS = {'edit': _icon_edit, 'viewport': _icon_viewport, 'render': _icon_render,
          'cage': lambda b, cx, cy, S, col: _icon_cage(b, cx, cy, S, col)}


# ---- widgets ------------------------------------------------------------------

def _w_button(b, m, x0, y0, x1, y1, label, hover, icon=None, color=None, bg=None,
              opacity=None):
    wc = m.ui.wcol_tool
    if color is not None:
        fill = _over(color, bg if bg is not None else _col(m.ui.panel_header, lift=0.03),
                     COLOR_OPACITY if opacity is None else opacity)
        b.add('rect', x0, y0, x1, y1, _col(fill, lift=0.08 if hover else 0), WIDGET_RADIUS * m.S)
        tc = (1.0, 1.0, 1.0, 1.0)
    else:
        b.add('rect', x0, y0, x1, y1, _col(wc.inner, lift=0.06 if hover else 0), WIDGET_RADIUS * m.S)
        tc = _col(wc.text)
    if icon == 'plus':
        tw = blf.dimensions(FONT, label)[0]
        start = x0 + (x1 - x0 - tw - 12 * m.S) / 2
        _icon_plus(b, start + 4 * m.S, (y0 + y1) / 2, m.S, tc)
        b.text(start + 12 * m.S, (y0 + y1) / 2, label, tc)
    else:
        b.text(x0, (y0 + y1) / 2, label, tc, max_w=x1 - x0, align='C')


def _over(color, bg, opacity):
    """`color` at `opacity` composited over `bg`, returned as a solid colour.

    Blender's viewport overlay doesn't show partially transparent fills
    reliably, so the 50 % look is mixed here and drawn opaque."""
    return tuple(c * opacity + g * (1.0 - opacity) for c, g in zip(color[:3], bg[:3])) + (1.0,)


def _w_icon_button(b, m, x0, y0, x1, y1, icon_fn, hover, color=None, enabled=True, bg=None,
                   opacity=None):
    """Small square icon button; `color` gives it a colour-coded background."""
    S = m.S
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if color is not None:
        base = bg if bg is not None else _col(m.ui.panel_header, lift=0.03)
        op = COLOR_OPACITY if opacity is None else opacity
        fill = _over(color, base, op if enabled else op * 0.4)
        b.add('rect', x0, y0, x1, y1, _col(fill, lift=0.08 if hover else 0), WIDGET_RADIUS * S)
        icol = (1.0, 1.0, 1.0, 1.0 if enabled else 0.35)
    else:
        if hover and enabled:
            b.add('rect', x0, y0, x1, y1, _col(m.ui.wcol_tool.inner, lift=0.06), WIDGET_RADIUS * S)
        icol = (m.text if (hover and enabled) else
                (m.dim if enabled else _col(m.text, alpha=0.14)))
    icon_fn(b, cx, cy, S, icol)


def _w_field(b, m, x0, y0, x1, y1, label, hover, wcol, placeholder=False, arrow=False):
    b.add('rect', x0, y0, x1, y1, _col(wcol.inner, lift=0.05 if hover else 0), WIDGET_RADIUS * m.S)
    tc = _col(wcol.text, alpha=0.5 if placeholder else None)
    right = 14 * m.S if arrow else 0
    b.text(x0 + m.pad, (y0 + y1) / 2, label, tc, max_w=x1 - x0 - 2 * m.pad - right)
    if arrow:
        _icon_arrow(b, x1 - 8 * m.S, (y0 + y1) / 2, m.S * 0.8, True, tc)


def _w_number(b, m, x0, y0, x1, y1, label, hover, frac=None, selected=False):
    wc = m.ui.wcol_numslider if frac is not None else m.ui.wcol_num
    inner = wc.inner_sel if selected else wc.inner
    b.add('rect', x0, y0, x1, y1, _col(inner, lift=0.05 if hover else 0), WIDGET_RADIUS * m.S)
    if frac is not None:
        fx = x0 + (x1 - x0) * max(0.0, min(1.0, frac))
        if fx - x0 > 1:
            b.add('rect', x0, y0, fx, y1, _col(wc.item), WIDGET_RADIUS * m.S)
    if selected:
        b.add('outline', x0, y0, x1, y1, _col(m.ui.panel_active), WIDGET_RADIUS * m.S)
    tc = _col(wc.text_sel if selected else wc.text)
    if hover and not selected:
        # Step arrows on hover, like Blender's own number fields.
        a = _arrow_zone(m.S, x1 - x0)
        yc = (y0 + y1) / 2
        k = 3 * m.S
        ac = _col(wc.text, alpha=0.75)
        b.add('tris', [(x0 + a * 0.35, yc), (x0 + a * 0.35 + k, yc + k), (x0 + a * 0.35 + k, yc - k)], ac)
        b.add('tris', [(x1 - a * 0.35, yc), (x1 - a * 0.35 - k, yc + k), (x1 - a * 0.35 - k, yc - k)], ac)
    b.text(x0 + m.pad, (y0 + y1) / 2, label, tc, max_w=x1 - x0 - 2 * m.pad, align='C')


def _arrow_zone(S, width):
    return min(round(16 * S), width / 4)


def _w_edit(b, m, x0, y0, x1, y1, e):
    """Number field in text-edit mode (typing directly in the panel)."""
    S, ui = m.S, m.ui
    wc = ui.wcol_text
    b.add('rect', x0, y0, x1, y1, _col(wc.inner_sel), WIDGET_RADIUS * S)
    b.add('outline', x0, y0, x1, y1, _col(ui.panel_active), WIDGET_RADIUS * S)
    shown = e['text']
    max_w = x1 - x0 - 2 * m.pad - 3 * S
    while shown and blf.dimensions(FONT, shown)[0] > max_w:
        shown = shown[1:]
    tw = blf.dimensions(FONT, shown)[0] if shown else 0
    tx = x0 + m.pad
    yc = (y0 + y1) / 2
    if e['sel'] and shown:
        b.add('rect', tx - S, y0 + 3 * S, tx + tw + S, y1 - 3 * S,
              _col(ui.panel_active, alpha=0.85), 2 * S)
    if shown:
        b.text(tx, yc, shown, _col(wc.text_sel))
    cx = tx + tw + S
    b.add('rect', cx, y0 + 3 * S, cx + max(1.0, 1.5 * S), y1 - 3 * S,
          _col(ui.widget_text_cursor), 0)


def _w_checkbox(b, m, x, yc, on, hover):
    wc = m.ui.wcol_option
    s = round(m.U * 0.7)
    y0, y1 = yc - s / 2, yc + s / 2
    inner = wc.inner_sel if on else wc.inner
    b.add('rect', x, y0, x + s, y1, _col(inner, lift=0.06 if hover else 0), WIDGET_RADIUS * m.S)
    if on:
        _icon_check(b, x + s / 2, yc, m.S, _col(wc.item))
    return s


def _w_toggle(b, m, x0, y0, x1, y1, label, on, hover):
    wc = m.ui.wcol_toggle
    inner = wc.inner_sel if on else wc.inner
    b.add('rect', x0, y0, x1, y1, _col(inner, lift=0.05 if hover else 0), WIDGET_RADIUS * m.S)
    b.text(x0, (y0 + y1) / 2, label, _col(wc.text_sel if on else wc.text),
           max_w=x1 - x0, align='C')


# ---- rows -------------------------------------------------------------------

def _row_bg(b, m, top, bot):
    b.add('rect', m.pad, bot, m.W - m.pad, top, _col(m.ui.panel_back, lift=-0.035), 0)


def _value_columns(m):
    lx = m.pad * 3
    vx0 = m.pad + round(m.cw * 0.42)
    vx1 = m.W - m.pad * 3
    return lx, vx0, vx1


def _build_prop_row(b, m, mod, p, pid=None, owner=None, label=None, desc=None):
    """One settings row. `owner`/`p` is the RNA struct/property holding the
    value, `pid` the path used by widgets (see _owner_attr)."""
    top, bot = b.new_row(m.U + m.g)
    _row_bg(b, m, top, bot)
    y0, y1, yc = bot + m.g / 2, top - m.g / 2, (top + bot) / 2
    lx, vx0, vx1 = _value_columns(m)
    owner = owner if owner is not None else mod
    attr = p.identifier
    pid = pid or attr
    name, t = mod.name, p.type
    label = label or p.name or attr
    desc = p.description if desc is None else desc
    tip = f"{label}: {desc}" if desc else label

    if t == 'BOOLEAN' and not p.is_array:
        hov = b.widget(vx0, y0, vx1, y1, 'bool', name, pid, tip=tip, label=label, desc=desc)
        s = _w_checkbox(b, m, vx0, yc, getattr(owner, attr), hov)
        b.text(vx0 + s + m.pad, yc, label, m.text, max_w=vx1 - vx0 - s - m.pad)
        return

    b.text(lx, yc, label, m.label, max_w=vx0 - lx - m.pad, align='R')

    if t == 'BOOLEAN':
        vals = list(getattr(owner, attr))
        n = len(vals)
        seg = (vx1 - vx0) / n
        for i, v in enumerate(vals):
            x0 = vx0 + i * seg
            x1 = x0 + seg - (m.g if i < n - 1 else 0)
            hov = b.widget(x0, y0, x1, y1, 'bool', name, pid, i, tip=tip, label=label, desc=desc)
            _w_toggle(b, m, x0, y0, x1, y1, AXIS_LETTERS[i] if n <= 4 else str(i), v, hov)

    elif t in ('INT', 'FLOAT'):
        n = p.array_length if p.is_array else 1
        if n > 4:
            hov = b.widget(vx0, y0, vx1, y1, 'popup', name, pid, tip=tip, label=label, desc=desc)
            _w_field(b, m, vx0, y0, vx1, y1, f"{n} values…", hov, m.ui.wcol_text)
            return
        vals = list(getattr(owner, attr)) if p.is_array else [getattr(owner, attr)]
        seg = (vx1 - vx0) / n
        slider = (not p.is_array and p.subtype in {'FACTOR', 'PERCENTAGE'}
                  and abs(p.hard_max - p.hard_min) < 1e6)
        for i, v in enumerate(vals):
            x0 = vx0 + i * seg
            x1 = x0 + seg - (m.g if i < n - 1 else 0)
            idx = i if p.is_array else -1
            e = HUD.edit
            if e is not None and e['key'] == ('num', name, pid, idx):
                b.widget(x0, y0, x1, y1, 'num', name, pid, idx,
                         tip=tip, label=label, desc=desc)
                _w_edit(b, m, x0, y0, x1, y1, e)
                continue
            txt = _fmt_value(p, v, m.scene)
            if p.is_array and p.subtype in VECTOR_SUBTYPES and n <= 4:
                txt = f"{AXIS_LETTERS[i]}  {txt}"
            frac = (v - p.hard_min) / (p.hard_max - p.hard_min) if slider else None
            hov = b.widget(x0, y0, x1, y1, 'num', name, pid, idx,
                           tip=tip, label=label, desc=desc)
            _w_number(b, m, x0, y0, x1, y1, txt, hov, frac,
                      selected=('num', name, pid, idx) in HUD.sel_keys)

    elif t == 'ENUM':
        hov = b.widget(vx0, y0, vx1, y1, 'enum', name, pid, tip=tip, flag=p.is_enum_flag, label=label, desc=desc)
        _w_field(b, m, vx0, y0, vx1, y1, _enum_text(p, getattr(owner, attr)), hov,
                 m.ui.wcol_menu, arrow=True)

    else:  # POINTER / STRING
        v = getattr(owner, attr)
        txt = (v.name if v else "") if t == 'POINTER' else (v or "")
        hov = b.widget(vx0, y0, vx1, y1, 'popup', name, pid, tip=tip, label=label, desc=desc)
        _w_field(b, m, vx0, y0, vx1, y1, txt or "—", hov, m.ui.wcol_text,
                 placeholder=not txt)


def _ancestor_closed(item, closed):
    par = getattr(item, "parent", None)
    depth = 0
    while par is not None and depth < 64:
        if par.as_pointer() in closed:
            return True
        par = getattr(par, "parent", None)
        depth += 1
    return False


def _gn_socket_shown(mod, inputs, item):
    """A Geometry Nodes input that Blender draws (has a value, not hidden)."""
    if item.item_type != 'SOCKET' or item.in_out != 'INPUT':
        return False
    if item.socket_type == 'NodeSocketGeometry':
        return False
    sock = getattr(inputs, item.identifier, None)
    if sock is None or sock.bl_rna.properties.get('value') is None:
        return False
    try:
        return bool(mod.is_input_visible(item.identifier))
    except (AttributeError, TypeError, RuntimeError):
        return True


def _gn_panel_toggle(panel):
    """The boolean input drawn as the panel header's checkbox, if any."""
    for it in getattr(panel, "interface_items", ()):
        if it.item_type == 'SOCKET' and getattr(it, "is_panel_toggle", False):
            return it
    return None


def _gn_panel_has_content(mod, inputs, panel):
    """Blender only draws a node-group panel when something inside it is shown."""
    for it in getattr(panel, "interface_items", ()):
        if it.item_type == 'PANEL':
            if _gn_panel_has_content(mod, inputs, it):
                return True
        elif _gn_socket_shown(mod, inputs, it):
            return True
    return False


def _build_nodes_body(b, m, mod):
    """Geometry Nodes modifier (incl. Blender 5.x node-based Array etc.).
    Like Blender: panels with nothing visible inside are not drawn, and a
    panel's toggle input is drawn as a checkbox in the panel header."""
    _build_prop_row(b, m, mod, mod.bl_rna.properties['node_group'])
    ng = mod.node_group
    inputs = getattr(getattr(mod, "properties", None), "inputs", None)
    if ng is None or inputs is None:
        return
    lx, vx0, vx1 = _value_columns(m)
    panel_states = list(getattr(mod, "panels", []))
    closed = set()          # panels hidden or collapsed: their contents are skipped
    toggles = set()         # sockets drawn in a panel header
    panel_i = 0
    for item in ng.interface.items_tree:
        hidden = _ancestor_closed(item, closed)
        if item.item_type == 'PANEL':
            i = panel_i
            panel_i += 1
            is_open = panel_states[i].is_open if i < len(panel_states) else True
            empty = not _gn_panel_has_content(mod, inputs, item)
            if not is_open or empty:
                closed.add(item.as_pointer())
            if hidden or empty:
                continue
            top, bot = b.new_row(m.U)
            _row_bg(b, m, top, bot)
            yc = (top + bot) / 2
            hov = b.widget(m.pad, bot, m.W - m.pad, top, 'gn_panel', mod.name, None, i,
                           tip=f"Show / hide '{item.name}' settings")
            _icon_arrow(b, lx + 4 * m.S, yc, m.S * 0.85, is_open, m.text if hov else m.dim)
            tx = lx + 12 * m.S
            tog = _gn_panel_toggle(item)
            if tog is not None:
                toggles.add(tog.identifier)
                if _gn_socket_shown(mod, inputs, tog):
                    pid = "in:" + tog.identifier
                    sock = getattr(inputs, tog.identifier)
                    s_ = round(m.U * 0.7)
                    hv = b.widget(tx, bot + m.g, tx + s_, top - m.g, 'bool', mod.name, pid,
                                  tip=f"{tog.name}: {tog.description}" if tog.description
                                  else tog.name, label=tog.name, desc=tog.description)
                    _w_checkbox(b, m, tx, yc, bool(sock.value), hv)
                    tx += s_ + m.pad
            b.text(tx, yc, item.name, m.text, max_w=m.W - m.pad - tx)
            continue
        if hidden or item.identifier in toggles or getattr(item, "is_panel_toggle", False):
            continue
        if not _gn_socket_shown(mod, inputs, item):
            continue
        sid = item.identifier
        sock = getattr(inputs, sid)
        vp = sock.bl_rna.properties.get('value')
        _build_prop_row(b, m, mod, vp, pid="in:" + sid, owner=sock,
                        label=item.name, desc=item.description)


# ---- small vector-icon helpers ----------------------------------------------------

def _seg(pts, closed=False):
    """Point list -> line-segment pairs for a 'lines' item."""
    seq = list(pts) + ([pts[0]] if closed and pts else [])
    out = []
    for a, b_ in zip(seq, seq[1:]):
        out += [a, b_]
    return out


def _ring(cx, cy, r, n=14):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def _disc(b, cx, cy, r, col, n=10):
    fan = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        fan += [(cx, cy), (cx + r * math.cos(a0), cy + r * math.sin(a0)),
                (cx + r * math.cos(a1), cy + r * math.sin(a1))]
    b.add('tris', fan, col)


def _icon_cage(b, cx, cy, S, col):
    """On Cage (Blender uses the mesh-data triangle with vertices)."""
    if _bicon(b, 'mesh_data', cx, cy, S, col):
        return
    k = S
    p = [(cx - 5 * k, cy - 4 * k), (cx + 5 * k, cy - 4 * k), (cx, cy + 4.6 * k)]
    b.add('lines', _seg(p, True), col)
    for x, y in p:
        _disc(b, x, y, 1.5 * k, col, 8)

_OB_ICON_NAMES = {
    'MESH': 'mesh', 'CURVE': 'curve', 'SURFACE': 'surface', 'META': 'meta', 'FONT': 'font',
    'ARMATURE': 'armature', 'LATTICE': 'lattice', 'EMPTY': 'empty', 'LIGHT': 'light',
    'CAMERA': 'camera', 'SPEAKER': 'speaker', 'LIGHT_PROBE': 'lightprobe',
    'GREASEPENCIL': 'greasepencil', 'CURVES': 'curves', 'POINTCLOUD': 'pointcloud',
    'VOLUME': 'volume',
}


def _ob_icon(ob):
    if ob.type == 'EMPTY':
        if ob.field is not None and ob.field.type != 'NONE':
            return 'outliner_ob_force_field'
        if ob.instance_type == 'COLLECTION' and ob.instance_collection is not None:
            return 'outliner_ob_group_instance'
        if ob.empty_display_type == 'IMAGE':
            return 'outliner_ob_image'
    return 'outliner_ob_' + _OB_ICON_NAMES.get(ob.type, 'empty')


def _icon_heart(b, cx, cy, S, col):
    """Heart shape (Add Favorite button)."""
    k = 0.36 * S
    pts = []
    for i in range(64):
        t = 2 * math.pi * i / 64
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * k, cy + 0.9 * S + y * k))
    tris = []
    for i in range(len(pts)):
        tris += [(cx, cy), pts[i], pts[(i + 1) % len(pts)]]
    b.add('tris', tris, col)


def _icon_heart_plus(b, cx, cy, S):
    """Add Favorite icon: red heart with a white plus."""
    k = 0.47 * S
    pts = []
    for i in range(64):
        t = 2 * math.pi * i / 64
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * k, cy + 1.2 * S + y * k))
    ccx, ccy = cx, cy
    tris = []
    for i in range(len(pts)):
        tris += [(ccx, ccy), pts[i], pts[(i + 1) % len(pts)]]
    b.add('tris', tris, (0.93, 0.18, 0.24, 1.0))
    a = 3.0 * S
    w = max(1.6, 1.8 * S)
    py = cy + 1.6 * S
    b.add('lines', [(cx - a, py), (cx + a, py), (cx, py - a), (cx, py + a)], (1, 1, 1, 1), w)


def _icon_copy(b, cx, cy, S, col):
    k = S
    b.add('outline', cx - 4 * k, cy - 3 * k, cx + 2 * k, cy + 4 * k, col, 1.5 * k)
    b.add('outline', cx - 2 * k, cy - 5 * k, cx + 4 * k, cy + 2 * k, col, 1.5 * k)


def _icon_paste(b, cx, cy, S, col):
    k = S
    b.add('outline', cx - 4 * k, cy - 5 * k, cx + 4 * k, cy + 4 * k, col, 1.5 * k)
    b.add('rect', cx - 2 * k, cy + 3 * k, cx + 2 * k, cy + 5.5 * k, col, 1 * k)
