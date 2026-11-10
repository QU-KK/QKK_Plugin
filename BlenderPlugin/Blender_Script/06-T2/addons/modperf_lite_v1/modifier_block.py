# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""One modifier block: header row (icon, name, toggles, buttons) and body."""

import math

import blf
import bpy

from .constants import (
    BLOCK_RADIUS, COL_APPLY, COL_DELETE, COLOR_OPACITY_REMOVE, COLOR_OPACITY_STRONG, FONT,
    WIDGET_RADIUS,
)
from .state import HUD
from .utils import _col, _is_new_modifier, _setting_props
from .modifier_info import _header_toggles, _mod_is_disabled
from .gpu_draw import _bicon, _red_alert, _TOGGLE_ICON
from .widgets import (
    _build_nodes_body, _build_prop_row, _disc, _icon_arrow, _icon_dots, _icon_down, _icon_up,
    _icon_x_bold, _ICONS, _over, _ring, _row_bg, _seg, _w_button, _w_edit, _w_field,
    _w_icon_button,
)
from .modifier_panels import _build_blender_body


def _build_modifier(b, m, mod, index=0, count=1):
    S, U, pad, g, W, ui = m.S, m.U, m.pad, m.g, m.W, m.ui
    name = mod.name
    # A modifier added since the last update is drawn collapsed right away
    # (its show_expanded is switched off on the next event / depsgraph update).
    expanded = mod.show_expanded and not _is_new_modifier(mod)
    top, bot = b.new_row(U + 2 * g)
    b.add('rect', pad, bot, W - pad, top, _col(ui.panel_header, lift=0.03), BLOCK_RADIUS * S)
    if mod.is_active:
        b.add('outline', pad, bot, W - pad, top, _col(ui.panel_active), BLOCK_RADIUS * S)
    yc = (top + bot) / 2
    by0, by1 = bot + g, top - g
    sw = round(U * 0.85)                      # width of the small square buttons

    x = pad + g
    hov = b.widget(x, bot, x + U, top, 'expand', name,
                   tip="Expand / Collapse\nShow or hide this modifier's settings.\n"
                       "Ctrl+click to show only this modifier.")
    _icon_arrow(b, x + U / 2, yc, S, expanded, m.text if hov else m.dim)
    x += U
    # modifier type icon: Blender's themed modifier colour (Theme > User Interface >
    # Icon Colors > Modifier), drawn at 80 % alpha unless hovered, like Blender.
    hov = b.widget(x, by0, x + round(U * 0.95), by1, 'mod_icon', name,
                   tip="Set Active Modifier\nActivate the modifier to use as the context.")
    # Same as Blender's Properties editor: the header icon is drawn in the
    # text colour, and in red (red alert) when the modifier is disabled
    # (ModifierTypeInfo::is_disabled, e.g. Boolean without an object).
    if _mod_is_disabled(m.scene, mod):
        icol = _red_alert(ui.wcol_regular.text)
    else:
        icol = _col(ui.wcol_regular.text)
    _icon_modifier(b, x + U * 0.45, yc, S, icol, _modifier_icon_type(mod))
    x += round(U * 0.95)

    xr = W - pad - g
    # drag handle (far right, like Blender's panel grip)
    hov = b.widget(xr - sw, by0, xr, by1, 'grip', name,
                   tip="Move Modifier\nDrag up or down to change the modifier order.")
    _w_icon_button(b, m, xr - sw, by0, xr, by1, _icon_dots, hov)
    xr -= sw + g

    hov = b.widget(xr - sw, by0, xr, by1, 'remove', name)
    _w_icon_button(b, m, xr - sw, by0, xr, by1, _icon_x_bold, hov, color=COL_DELETE,
                   opacity=COLOR_OPACITY_REMOVE)
    xr -= sw + g

    xr -= g

    # move down / up (plain, dimmed when the modifier can't move further)
    # always drawn active (at the end of the stack a click simply does nothing)
    hov = b.widget(xr - sw, by0, xr, by1, 'move_down', name)
    _w_icon_button(b, m, xr - sw, by0, xr, by1, _icon_down, hov)
    xr -= sw + g
    hov = b.widget(xr - sw, by0, xr, by1, 'move_up', name)
    _w_icon_button(b, m, xr - sw, by0, xr, by1, _icon_up, hov)
    xr -= sw + 2 * g

    aw = blf.dimensions(FONT, "Apply")[0] + 2 * pad
    hov = b.widget(xr - aw, by0, xr, by1, 'apply', name)
    _w_button(b, m, xr - aw, by0, xr, by1, "Apply", hov, color=COL_APPLY,
              opacity=COLOR_OPACITY_STRONG)
    xr -= aw + 3 * g

    # Display toggles in Blender's order (left -> right): On Cage (mesh only,
    # when the modifier can be the edit cage), Edit Mode, Realtime, Render.
    toggles = _header_toggles(m.scene, mod.id_data, mod, index)
    for flag, icon, tip, active in reversed(toggles):
        on = getattr(mod, flag)
        tw = ui.wcol_toggle
        x0t, x1t = xr - U + g / 2, xr - g / 2
        hov = b.widget(xr - U, by0, xr, by1, 'toggle', name, flag, tip=tip)
        fade = 1.0 if active else 0.5            # Blender: sub-layout active_set(false)
        inner = tw.inner_sel if on else tw.inner
        b.add('rect', x0t, by0, x1t, by1, _col(_over(inner, ui.panel_header, fade),
                                               lift=0.06 if hov else 0), WIDGET_RADIUS * S)
        iname = _TOGGLE_ICON[icon](on)
        # Plain text-coloured icons, like Blender's header toggles (On Cage too).
        icol = _col(tw.text_sel if on else tw.text, alpha=fade)
        if not _bicon(b, iname, xr - U / 2, yc, S, icol):
            _ICONS[icon](b, xr - U / 2, yc, S, icol)
        xr -= U
    xr -= 2 * g

    hov = b.widget(x + g, by0, xr, by1, 'name', name,
                   tip="Modifier Name\nClick to make this the active modifier, double-click "
                       "to rename, drag up or down to reorder.")
    e = HUD.edit
    if e is not None and e['key'] == ('name', name, None, -1):
        _w_edit(b, m, x + g, by0, xr, by1, e)          # renaming in place
    else:
        _w_field(b, m, x + g, by0, xr, by1, name, hov, ui.wcol_text)
    header_bot = bot

    if expanded:
        t2, b2 = b.new_row(2 * g)
        _row_bg(b, m, t2, b2)
        if mod.type == 'NODES':
            _build_nodes_body(b, m, mod)
        elif _build_blender_body(b, m, mod, bpy.context):
            pass                               # Blender's own panel layout (ported)
        else:
            props = list(_setting_props(mod))
            if not props:
                t3, b3 = b.new_row(U)
                _row_bg(b, m, t3, b3)
                b.text(pad * 3, (t3 + b3) / 2, "No settings", m.dim)
            for p in props:
                _build_prop_row(b, m, mod, p)
        t2, b2 = b.new_row(3 * g)
        _row_bg(b, m, t2, b2)
    return top, header_bot, b.y


# ---- modifier type icons (look-alikes of Blender's MOD_* icons) --------------------

def _mod_icon_lines(t, P):
    """Return (lines, filled_tris, discs) in icon space for a modifier type.
    P(x, y) maps icon coordinates (about -6..6) to screen coordinates."""
    L, T, D = [], [], []

    def sq(x0, y0, x1, y1):
        L.extend(_seg([P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)], True))

    def circ(x, y, r, n=14):
        L.extend(_seg([P(px, py) for px, py in _ring(x, y, r, n)], True))

    def wave(y, amp, x0=-6, x1=6, n=12, cycles=1.0):
        L.extend(_seg([P(x0 + (x1 - x0) * i / n,
                         y + amp * math.sin(2 * math.pi * cycles * i / n)) for i in range(n + 1)]))

    if t == 'SUBSURF':
        sq(-5.5, -5.5, 5.5, 5.5); circ(0, 0, 3.4)
    elif t == 'MULTIRES':
        sq(-5.5, -5.5, 5.5, 5.5); L.extend([P(0, -5.5), P(0, 5.5), P(-5.5, 0), P(5.5, 0)])
        circ(0, 0, 2.4)
    elif t == 'BEVEL':
        L.extend(_seg([P(-5.5, -5.5), P(5.5, -5.5), P(5.5, 1.5), P(1.5, 5.5), P(-5.5, 5.5)], True))
        L.extend([P(0.5, -5.5), P(0.5, 0.5), P(0.5, 0.5), P(5.5, 0.5)])
    elif t == 'MIRROR':
        L.extend([P(0, -6), P(0, 6)])
        L.extend(_seg([P(-1.6, -4.5), P(-6, -4.5), P(-1.6, 4.5)], True))
        T.extend([P(1.6, -4.5), P(6, -4.5), P(1.6, 4.5)])
    elif t == 'ARRAY':
        for o in (-3.6, 0.0, 3.6):
            sq(o - 2.1, o - 2.1, o + 2.1, o + 2.1)
    elif t == 'SOLIDIFY':
        L.extend(_seg([P(-6, 1), P(2, 1), P(6, 5), P(-2, 5)], True))
        L.extend([P(-6, 1), P(-6, -4), P(2, 1), P(2, -4), P(6, 5), P(6, 0),
                  P(-6, -4), P(2, -4), P(2, -4), P(6, 0)])
    elif t == 'BOOLEAN':
        circ(-2.1, 0, 3.8); circ(2.1, 0, 3.8)
    elif t == 'DECIMATE':
        L.extend(_seg([P(-5.5, -5), P(5.5, -5), P(0, 5.5)], True))
        L.extend([P(0, -5), P(-2.75, 0.25)])
    elif t == 'REMESH':
        sq(-5.5, -5.5, 5.5, 5.5)
        for v in (-1.8, 1.8):
            L.extend([P(v, -5.5), P(v, 5.5), P(-5.5, v), P(5.5, v)])
    elif t == 'SCREW':
        L.extend(_seg([P(4 * math.sin(i * 0.9), -6 + i * 0.5) for i in range(25)]))
    elif t == 'SKIN':
        circ(0, 3.5, 2.2, 10)
        L.extend([P(0, 1.3), P(0, -2.5), P(0, -2.5), P(-3, -6), P(0, -2.5), P(3, -6),
                  P(-3.5, -0.3), P(3.5, -0.3)])
    elif t == 'TRIANGULATE':
        sq(-5.5, -5.5, 5.5, 5.5); L.extend([P(-5.5, -5.5), P(5.5, 5.5)])
    elif t == 'WELD':
        for x, y in ((-5, -5), (5, -5), (5, 5), (-5, 5)):
            D.append((P(x, y), 1.3)); L.extend([P(x * 0.7, y * 0.7), P(x * 0.25, y * 0.25)])
        D.append((P(0, 0), 1.8))
    elif t == 'WIREFRAME':
        sq(-5.5, -5.5, 5.5, 5.5); sq(-2.5, -2.5, 2.5, 2.5)
        L.extend([P(-5.5, -5.5), P(-2.5, -2.5), P(5.5, 5.5), P(2.5, 2.5),
                  P(5.5, -5.5), P(2.5, -2.5), P(-5.5, 5.5), P(-2.5, 2.5)])
    elif t == 'EDGE_SPLIT':
        sq(-6, -5, -1, 5); sq(1, -5, 6, 5)
    elif t == 'BUILD':
        for i, h in enumerate((2, 5, 8, 11)):
            x = -5.5 + i * 3
            sq(x, -5.5, x + 2, -5.5 + h)
    elif t == 'MASK':
        circ(0, 0, 5)
        T.extend([q for i in range(7) for q in (P(0, 0),
                  P(5 * math.cos(math.pi / 2 + math.pi * i / 7), 5 * math.sin(math.pi / 2 + math.pi * i / 7)),
                  P(5 * math.cos(math.pi / 2 + math.pi * (i + 1) / 7), 5 * math.sin(math.pi / 2 + math.pi * (i + 1) / 7)))])
    elif t == 'DISPLACE':
        wave(-3.5, 1.4, cycles=1.5)
        L.extend([P(0, -1.5), P(0, 5.5), P(0, 5.5), P(-2.2, 3.2), P(0, 5.5), P(2.2, 3.2)])
    elif t in {'SMOOTH', 'CORRECTIVE_SMOOTH', 'LAPLACIANSMOOTH'}:
        L.extend(_seg([P(-6 + 12 * i / 14, -4 + 8 * math.sin(math.pi * i / 14)) for i in range(15)]))
        L.extend([P(-6, -4), P(6, -4)])
    elif t == 'CAST':
        circ(-1, -1, 4.2); sq(-1, -1, 5.5, 5.5)
    elif t == 'CURVE':
        L.extend(_seg([P(-5.5 + 11 * i / 12, 3.5 * math.sin(math.pi * 2 * i / 12)) for i in range(13)]))
        L.extend([P(5.5, 0), P(3.5, 1.6), P(5.5, 0), P(3.8, -1.8)])
    elif t == 'LATTICE':
        sq(-5.5, -5.5, 5.5, 5.5)
        for x in (-5.5, 0, 5.5):
            for y in (-5.5, 0, 5.5):
                D.append((P(x, y), 1.1))
    elif t == 'SHRINKWRAP':
        circ(0, 0, 2.6, 10)
        for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            L.extend([P(6 * x, 6 * y), P(3.4 * x, 3.4 * y), P(3.4 * x, 3.4 * y), P(4.8 * x, 3.4 * y)])
    elif t == 'SIMPLE_DEFORM':
        for off in (-1.6, 1.6):
            L.extend(_seg([P(-5.5 + 11 * i / 10, off + 3.5 * math.cos(math.pi * i / 10))
                           for i in range(11)]))
    elif t in {'WAVE', 'OCEAN'}:
        wave(1.8, 2, cycles=1.5); wave(-2.8, 2, cycles=1.5)
    elif t == 'HOOK':
        L.extend(_seg([P(2.5, 6), P(2.5, -1)] +
                      [P(-0.5 + 3 * math.cos(-math.pi * i / 8), -1 + 3 * math.sin(-math.pi * i / 8))
                       for i in range(9)] + [P(-3.5, 1.5)]))
    elif t == 'ARMATURE':
        L.extend([P(-3.5, -3.5), P(3.5, 3.5)])
        D.extend([(P(-4.2, -4.2), 1.8), (P(4.2, 4.2), 1.8)])
    elif t == 'NODES':
        sq(-6, 1, -1, 5.5); sq(1, -5.5, 6, -1)
        L.extend(_seg([P(-1, 3.2), P(0.5, 3.2), P(0.5, -3.2), P(1, -3.2)]))
    elif t == 'DATA_TRANSFER':
        sq(-6, 1, -1.5, 5.5); sq(1.5, -5.5, 6, -1)
        L.extend([P(-3.8, 1), P(-3.8, -3.2), P(-3.8, -3.2), P(1.5, -3.2),
                  P(1.5, -3.2), P(-0.3, -1.6), P(1.5, -3.2), P(-0.3, -4.8)])
    elif t in {'NORMAL_EDIT', 'WEIGHTED_NORMAL'}:
        L.extend([P(-6, -4.5), P(6, -4.5)])
        for x in (-3.5, 0, 3.5):
            L.extend([P(x, -4.5), P(x, 4), P(x, 4), P(x - 1.6, 2.2), P(x, 4), P(x + 1.6, 2.2)])
    elif t in {'UV_PROJECT', 'UV_WARP'}:
        sq(-5.5, -5.5, 5.5, 5.5)
        T.extend([P(-5.5, -5.5), P(0, -5.5), P(0, 0), P(-5.5, -5.5), P(0, 0), P(-5.5, 0),
                  P(0, 0), P(5.5, 0), P(5.5, 5.5), P(0, 0), P(5.5, 5.5), P(0, 5.5)])
    elif t.startswith('VERTEX_WEIGHT'):
        p = [P(-5.5, -4.5), P(5.5, -4.5), P(0, 5)]
        L.extend(_seg(p, True))
        D.extend([(q, 1.6) for q in p])
    elif t in {'MESH_DEFORM', 'SURFACE_DEFORM', 'LAPLACIANDEFORM', 'WARP'}:
        L.extend(_seg([P(-5.5, -5), P(4.5, -5.5), P(5.5, 4), P(-3.5, 5.5)], True))
        L.extend([P(-1, -5.3), P(1, 4.8), P(-4.5, 0), P(5, -0.8)])
    elif t in {'MESH_CACHE', 'MESH_SEQUENCE_CACHE'}:
        for y in (3.5, 0, -3.5):
            L.extend(_seg([P(px, y + py * 0.35) for px, py in _ring(0, 0, 5, 12)], True))
    elif t in {'PARTICLE_SYSTEM', 'PARTICLE_INSTANCE', 'EXPLODE'}:
        for x, y in ((-4, -3), (0, 4), (4, -1), (-1, -0.5), (3, 4.5), (-4.5, 3), (1.5, -4.5)):
            D.append((P(x, y), 1.2))
    elif t == 'CLOTH':
        L.extend([P(-5.5, -6), P(-5.5, 6)])
        wave(4.5, 1.2, x0=-5.5, x1=5.5); wave(-1, 1.2, x0=-5.5, x1=5.5)
        L.extend([P(5.5, 4.5), P(5.5, -1)])
    elif t in {'FLUID', 'DYNAMIC_PAINT'}:
        L.extend(_seg([P(0, 6)] + [P(4 * math.cos(math.pi * (i / 10) * 1.6 - math.pi * 0.3),
                                     -1.5 + 4 * math.sin(math.pi * (i / 10) * 1.6 - math.pi * 0.3))
                                   for i in range(-1, 12)] + [P(0, 6)]))
    elif t in {'COLLISION', 'SOFT_BODY', 'SURFACE'}:
        circ(0, 0, 3)
        L.extend(_seg([P(px * 1.9, py * 0.7) for px, py in _ring(0, 0, 3.2, 16)], True))
    else:                                               # generic: wrench
        L.extend([P(-5, -5), P(1.4, 1.4)])
        L.extend(_seg([P(3.2 + 2.6 * math.cos(a), 3.2 + 2.6 * math.sin(a))
                       for a in [math.radians(d) for d in range(-150, 151, 30)]]))
    return L, T, D


def _icon_modifier(b, cx, cy, S, col, mod_type):
    if _bicon(b, _mod_icon_name(mod_type), cx, cy, S, col):
        return
    k = S * 0.92

    def P(x, y):
        return (cx + x * k, cy + y * k)
    lines, tris, discs = _mod_icon_lines(mod_type, P)
    if tris:
        b.add('tris', tris, col)
    if lines:
        b.add('lines', lines, col)
    for (x, y), r in discs:
        _disc(b, x, y, r * k, col, 8)


_OB_ICON = {'LIGHT_PROBE': 'lightprobe', 'GPENCIL': 'greasepencil'}


def _mod_icon_name(mod_type):
    """Blender's own icon for a modifier type (taken from Blender's RNA)."""
    if mod_type == 'WRENCH':
        return 'modifier'
    try:
        icon = bpy.types.Modifier.bl_rna.properties['type'].enum_items[mod_type].icon
        if icon and icon != 'NONE':
            return icon.lower()
    except KeyError:
        pass
    return 'mod_' + mod_type.lower()


def _modifier_icon_type(mod):
    """Blender 5.x ships some modifiers (e.g. Array) as Geometry Nodes groups:
    show them with the icon of the classic modifier they replace."""
    if mod.type == 'NODES' and mod.node_group is not None:
        key = mod.node_group.name.split(".")[0].upper().replace(" ", "_")
        if key in _MOD_ICON_NAMES:
            return key
    return mod.type


_MOD_ICON_NAMES = {
    'ARRAY', 'BEVEL', 'MIRROR', 'SUBSURF', 'SOLIDIFY', 'BOOLEAN', 'DECIMATE', 'REMESH',
    'SCREW', 'SKIN', 'TRIANGULATE', 'WELD', 'WIREFRAME', 'BUILD', 'MASK', 'DISPLACE',
    'SMOOTH', 'CAST', 'CURVE', 'LATTICE', 'SHRINKWRAP', 'WAVE', 'HOOK',
}
