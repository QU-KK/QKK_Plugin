# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""A small re-implementation of Blender's UILayout used by the modifier panels."""

import bpy

from .constants import WIDGET_RADIUS
from .state import HUD, _PERSIST
from .utils import _col, _enum_text, _fmt_value
from .gpu_draw import _bicon, _icon_cat_color
from .widgets import (
    _icon_arrow, _ob_icon, _row_bg, _value_columns, _w_button, _w_checkbox, _w_edit, _w_field,
    _w_number, _w_toggle,
)
from .tooltips import _rna_tip, _sentence


# =============================================================================
# Blender-style modifier panels
# =============================================================================
#
# A small re-implementation of the parts of Blender's UILayout used by the
# modifier panels (row / column / headings / property split / active /
# enabled / expanded enums / toggles / sub-panels with header checkboxes /
# operator buttons / prop_search), so each modifier can be drawn with the same
# layout as Blender 5.2's own panel (ported from source/blender/modifiers/
# intern/MOD_*.cc, see _MOD_PANELS below).

_AXIS_ICON_LABEL = "XYZW"


def _fade_items(b, start, factor):
    """Multiply the alpha of the draw items added since `start` (inactive UI)."""
    for i in range(start, len(b.items)):
        row, it = b.items[i]
        k = it[0]
        ci = {'rect': 5, 'outline': 5, 'icon': 5, 'text': 4, 'tris': 2, 'lines': 2}.get(k)
        if ci is None:
            continue
        c = it[ci]
        c = (c[0], c[1], c[2], (c[3] if len(c) > 3 else 1.0) * factor)
        b.items[i] = (row, it[:ci] + (c,) + it[ci + 1:])


class _Cell:
    __slots__ = ('kind', 'lay', 'pid', 'owner', 'text', 'idx', 'expand', 'toggle', 'slider',
                 'icon', 'extra', 'fixed')

    def __init__(self, kind, lay, pid=None, owner=None, text=None, idx=-1, expand=False,
                 toggle=False, slider=False, icon=None, **extra):
        self.kind, self.lay, self.pid, self.owner, self.text = kind, lay, pid, owner, text
        self.idx, self.expand, self.toggle, self.slider, self.icon = idx, expand, toggle, slider, icon
        self.extra = extra
        self.fixed = False


class _UICtx:
    """Shared drawing state for one modifier body."""

    def __init__(self, b, m, mod, ob, context):
        self.b, self.m, self.mod, self.ob, self.context = b, m, mod, ob, context
        self.pending = None          # row being collected
        self.depth = 0               # sub-panel nesting (indent)
        self.path = ""               # sub-panel path for open state


class _UL:
    """Mini UILayout. Lines are emitted as they are declared; rows collect their
    cells until the next element is added (then they are drawn as one line)."""

    def __init__(self, ctx, parent=None, heading=None, align=False, is_row=False):
        self.ctx, self.parent, self.heading, self.align = ctx, parent, heading, align
        self.is_row = is_row
        self.active = True
        self.enabled = True
        self.red = False
        self.split = parent.split if parent is not None else False
        self.depth = parent.depth if parent is not None else 0
        self.path = parent.path if parent is not None else ""
        self.rowroot = None
        self.cells = None
        self.heading_used = False

    # -- state -------------------------------------------------------------
    def eff_active(self):
        return self.active and (self.parent.eff_active() if self.parent else True)

    def eff_enabled(self):
        return self.enabled and (self.parent.eff_enabled() if self.parent else True)

    def eff_red(self):
        return self.red or (self.parent.eff_red() if self.parent else False)

    def _heading(self):
        lay = self
        while lay is not None:
            if lay.heading and not lay.heading_used:
                lay.heading_used = True
                return lay.heading
            if not lay.is_row and lay is not self:
                break
            lay = lay.parent
        return None

    # -- structure -----------------------------------------------------------
    def row(self, align=True, heading=None):
        if self.is_row:
            r = _UL(self.ctx, self, heading, align, True)
            r.rowroot = self.rowroot
            return r
        self.ctx_flush()
        r = _UL(self.ctx, self, heading, align, True)
        r.rowroot, r.cells = r, []
        self.ctx.pending = r
        return r

    def column(self, align=False, heading=None):
        self.ctx_flush()
        return _UL(self.ctx, self, heading, align, False)

    def ctx_flush(self):
        p = self.ctx.pending
        if p is not None:
            self.ctx.pending = None
            _ui_draw_line(self.ctx, p, p.cells, p._heading())

    def _add(self, cell):
        if self.is_row:
            self.rowroot.cells.append(cell)
        else:
            self.ctx_flush()
            _ui_draw_line(self.ctx, self, [cell], self._heading())

    # -- items ---------------------------------------------------------------
    def prop(self, pid, text=None, expand=False, toggle=False, slider=False, icon=None,
             index=-1, owner=None, path=None):
        owner = owner if owner is not None else self.ctx.mod
        try:
            p = owner.bl_rna.properties[pid]
        except KeyError:
            return
        if text is None:
            text = p.name
        if (p.type in {'INT', 'FLOAT'} and p.is_array and index < 0 and not self.is_row
                and 1 < p.array_length <= 4 and p.subtype != 'COLOR'):
            # vectors in a column: one line per component ("Offset X", "Y", "Z")
            self.ctx_flush()
            for i in range(p.array_length):
                lab = (f"{text} {_AXIS_ICON_LABEL[i]}".strip() if i == 0
                       else _AXIS_ICON_LABEL[i])
                _ui_draw_line(self.ctx, self, [_Cell('prop', self, pid, owner, lab, i,
                                                    slider=slider)], self._heading())
            return
        cell = _Cell('prop', self, pid, owner, text, index, expand, toggle, slider, icon)
        if path:
            cell.extra['path'] = path
        self._add(cell)

    def vgroup(self, pid="vertex_group", inv="invert_vertex_group", text=None):
        """modifier_vgroup_ui(): vertex group search + invert toggle."""
        r = self.row(True)
        r.prop(pid, text=text if text is not None else None, icon='group_vertex')
        if inv:
            sub = r.row(True)
            sub.active = bool(getattr(self.ctx.mod, pid, ""))
            sub.prop(inv, text="", icon='arrow_leftright')

    def search(self, pid, getter, coll, text=None, icon=None):
        """prop_search() against an arbitrary collection (bones, paths, ...)."""
        mod = self.ctx.mod
        try:
            p = mod.bl_rna.properties[pid]
        except KeyError:
            return
        self._add(_Cell('search', self, pid, mod, text if text is not None else p.name,
                        icon=icon, getter=getter, coll=coll))

    def template(self, tmpl, pid, text=""):
        """Templates Blender draws inline (curve mapping, texture ID, cache file...):
        a field / button that opens the native template in a popup."""
        self._add(_Cell('tmpl', self, pid, self.ctx.mod, text, tmpl=tmpl))

    def label(self, text, icon=None):
        self._add(_Cell('label', self, text=text, icon=icon))

    def separator(self):
        self.ctx_flush()
        self.ctx.b.new_row(round(self.ctx.m.U * 0.3))
        _row_bg(self.ctx.b, self.ctx.m, *self.ctx.b.row)

    def op(self, idname, text, **props):
        self._add(_Cell('op', self, text=text, idname=idname, props=props))

    def panel(self, key, label, header=None, header_text=None, open_prop=None,
              header_active=True):
        """A collapsible sub-panel. Returns its layout, or None when closed."""
        self.ctx_flush()
        ctx = self.ctx
        path = f"{self.path}/{key}"
        mod = ctx.mod
        if open_prop and hasattr(mod, open_prop):
            is_open = bool(getattr(mod, open_prop))
        else:
            is_open = _PERSIST.setdefault('subpanels', {}).get(
                (ctx.ob.name, mod.name, path), False)
        _ui_draw_panel_header(ctx, path, self.depth, label, header, header_text, is_open,
                              open_prop, header_active)
        if not is_open:
            return None
        sub = _UL(ctx, None)
        sub.depth = self.depth + 1
        sub.path = path
        return sub


def _subpanel_open(ctx, path):
    return _PERSIST.setdefault('subpanels', {}).get((ctx.ob.name, ctx.mod.name, path), False)


# ---- drawing -------------------------------------------------------------------

def _ui_x_range(ctx, lay):
    m = ctx.m
    ind = lay.depth * round(m.pad * 0.8)
    lx, vx0, vx1 = _value_columns(m)
    return lx + ind, vx0 + ind * 0.5, vx1


def _ui_draw_panel_header(ctx, path, depth, label, header, header_text, is_open, open_prop,
                          header_active=True):
    b, m, mod = ctx.b, ctx.m, ctx.mod
    S, U, pad, g = m.S, m.U, m.pad, m.g
    top, bot = b.new_row(U + g)
    _row_bg(b, m, top, bot)
    x0 = pad + g + depth * round(pad * 0.8)
    x1 = m.W - pad - g
    hov = b.widget(x0, bot + g / 2, x1, top - g / 2, 'subpanel', mod.name, path, -1,
                   tip=f"{label or header_text or ''}\nShow or hide these settings.",
                   open_prop=open_prop)
    yc = (top + bot) / 2                  # no header background, like Blender's node panels
    _icon_arrow(b, x0 + U / 2, yc, S * 0.85, is_open, m.text if hov else m.dim)
    tx = x0 + U
    if header:
        s_ = round(U * 0.7)
        i0 = len(b.items)
        hv = b.widget(tx, bot + g, tx + s_, top - g, 'bool', mod.name, header, -1,
                      tip=_rna_tip(type(mod), header) if header in mod.bl_rna.properties else "")
        _w_checkbox(b, m, tx, yc, bool(getattr(mod, header, False)), hv)
        tx += s_ + round(5 * S)
        if not header_active:
            _fade_items(b, i0, 0.5)
        text = header_text or mod.bl_rna.properties[header].name
        i0 = len(b.items)
        b.text(tx, yc, text, m.text, max_w=x1 - tx - pad)
        if not header_active:
            _fade_items(b, i0, 0.5)
    else:
        b.text(tx, yc, label, m.text, max_w=x1 - tx - pad)


def _cell_rna(cell):
    try:
        return cell.owner.bl_rna.properties[cell.pid]
    except (KeyError, AttributeError):
        return None


def _cell_is_fixed(cell):
    """Cells that take a fixed square width (icon toggles / bare checkboxes)."""
    if cell.kind != 'prop':
        return False
    p = _cell_rna(cell)
    if p is None or p.type != 'BOOLEAN':
        return False
    if cell.text == "" and not cell.toggle:
        return True
    return False


def _cell_labelled(cell, lay_split):
    """Does this cell's text go into the label column (property split)?"""
    if not lay_split or cell.kind not in {'prop', 'search', 'tmpl'}:
        return False
    if cell.kind == 'tmpl':
        return bool(cell.text)
    p = _cell_rna(cell)
    if p is None:
        return False
    if p.type == 'BOOLEAN' and not p.is_array:
        return False
    return bool(cell.text)


def _ui_draw_line(ctx, lay, cells, heading):
    if not cells:
        return
    b, m = ctx.b, ctx.m
    S, U, pad, g = m.S, m.U, m.pad, m.g
    # expand enums / bool arrays into one cell per item
    flat = []
    for c in cells:
        p = _cell_rna(c) if c.kind == 'prop' else None
        if p is not None and p.type == 'ENUM' and (c.expand or p.is_enum_flag):
            items = list(p.enum_items)
            for i, it in enumerate(items):
                flat.append(_Cell('enum_item', c.lay, c.pid, c.owner, it.name, i,
                                  value=it.identifier, flag=p.is_enum_flag,
                                  desc=it.description, group_text=c.text))
            if flat and c.text and c.lay.split and c is cells[0]:
                flat[-len(items)].extra['line_label'] = c.text
            continue
        if p is not None and p.type == 'BOOLEAN' and p.is_array and c.idx < 0:
            for i in range(p.array_length):
                flat.append(_Cell('prop', c.lay, c.pid, c.owner, _AXIS_ICON_LABEL[i]
                                  if p.array_length <= 4 else str(i), i, toggle=True))
            continue
        flat.append(c)
    cells = flat
    split = lay.split
    label = heading
    first = cells[0]
    if label is None and first.extra.get('line_label'):
        label = first.extra['line_label']
    if label is None and _cell_labelled(first, first.lay.split):
        label = first.text
        first.extra['label_used'] = True
    lx, vx0, vx1 = _ui_x_range(ctx, lay)
    full = all(c.kind in {'op', 'label'} or (c.kind == 'tmpl' and not c.text) for c in cells)
    if (not split or full) and label is None:
        x_start = lx
    else:
        x_start = vx0
    top, bot = b.new_row(U + g)
    _row_bg(b, m, top, bot)
    y0, y1, yc = bot + g / 2, top - g / 2, (top + bot) / 2
    if label:
        i0 = len(b.items)
        b.text(lx, yc, label, m.label, max_w=vx0 - lx - pad, align='R')
        if not (lay.eff_active() and lay.eff_enabled()):
            _fade_items(b, i0, 0.5)
    # widths
    gap = max(1, round(g * (0.5 if lay.align else 1.0)))
    fixed_w = round(U * 1.0)
    n_fixed = sum(1 for c in cells if _cell_is_fixed(c))
    n_flex = len(cells) - n_fixed
    avail = vx1 - x_start - gap * (len(cells) - 1) - n_fixed * fixed_w
    flex_w = avail / n_flex if n_flex else 0
    x = x_start
    for c in cells:
        w = fixed_w if _cell_is_fixed(c) else flex_w
        if n_flex == 0 and c is cells[-1]:
            w = fixed_w
        _ui_draw_cell(ctx, c, x, y0, x + w, y1, yc)
        x += w + gap


def _ui_draw_cell(ctx, c, x0, y0, x1, y1, yc):
    b, m, mod = ctx.b, ctx.m, ctx.mod
    S, U, pad = m.S, m.U, m.pad
    active = c.lay.eff_active()
    enabled = c.lay.eff_enabled()
    i0, w0 = len(b.items), len(b.widgets)
    name = mod.name
    if c.kind == 'label':
        tx = x0
        if c.icon and _bicon(b, c.icon, x0 + 8 * S, yc, S, m.text):
            tx += 18 * S
        b.text(tx, yc, c.text, m.text, max_w=x1 - tx)
    elif c.kind == 'op':
        hov = b.widget(x0, y0, x1, y1, 'op', name, c.extra['idname'], -1,
                       props=c.extra.get('props', {}), label=c.text)
        _w_button(b, m, x0, y0, x1, y1, c.text, hov)
    elif c.kind == 'tmpl':
        tm = c.extra['tmpl']
        tip = {'curve_mapping': "Edit the falloff curve",
               'curve_profile': "Edit the custom profile",
               'texture': "Texture to use",
               'cache_file': "Cache file"}.get(tm, "")
        hov = b.widget(x0, y0, x1, y1, 'tmpl', name, c.pid, -1, tmpl=tm,
                       tip=f"{c.text or tm.replace('_', ' ').title()}\n{tip}")
        if tm in {'texture', 'cache_file'}:
            v = getattr(mod, c.pid, None)
            txt = v.name if v is not None else "New"
            _w_field(b, m, x0, y0, x1, y1, txt, hov, m.ui.wcol_text, placeholder=v is None)
        else:
            _w_button(b, m, x0, y0, x1, y1, "Edit Curve…" if 'curve' in tm else tm, hov)
    elif c.kind == 'search':
        v = getattr(mod, c.pid, "")
        txt = (v.name if hasattr(v, 'name') else v) if v else ""
        hov = b.widget(x0, y0, x1, y1, 'search', name, c.pid, -1,
                       tip=_rna_tip(type(mod), c.pid), label=c.text)
        ix = x0 + (14 * S if c.icon else 0)
        _w_field(b, m, x0, y0, x1, y1, "", hov, m.ui.wcol_text)
        b.text(ix + m.pad, yc, txt or "", _col(m.ui.wcol_text.text), max_w=x1 - ix - 2 * m.pad)
        if c.icon:
            _bicon(b, c.icon, x0 + 9 * S, yc, S, m.dim)
        ctx.search_getters[(name, c.pid)] = (c.extra['getter'], c.extra['coll'])
    elif c.kind == 'enum_item':
        on_val = getattr(c.owner, c.pid)
        on = (c.extra['value'] in on_val) if c.extra['flag'] else (on_val == c.extra['value'])
        hov = b.widget(x0, y0, x1, y1, 'enum_item', name, c.pid, c.idx,
                       value=c.extra['value'], flag=c.extra['flag'],
                       tip=f"{c.text}\n{_sentence(c.extra.get('desc') or '')}")
        _w_toggle(b, m, x0, y0, x1, y1, c.text, on, hov)
    else:
        _ui_draw_prop(ctx, c, x0, y0, x1, y1, yc)
    if not (active and enabled):
        _fade_items(b, i0, 0.5)
    if not enabled:
        del b.widgets[w0:]


def _ui_draw_prop(ctx, c, x0, y0, x1, y1, yc):
    b, m, mod = ctx.b, ctx.m, ctx.mod
    S = m.S
    owner, p = c.owner, _cell_rna(c)
    if p is None:
        return
    name = mod.name
    pid = c.pid if owner is mod else c.extra.get('path', c.pid)
    desc = p.description
    tip = f"{p.name}: {desc}" if desc else p.name
    inline = c.text if (c.text and not c.extra.get('label_used')) else ""
    t = p.type
    if t == 'BOOLEAN':
        idx = c.idx
        v = getattr(owner, c.pid)
        v = v[idx] if idx >= 0 else v
        if c.icon and c.text == "":
            # icon-only toggle (invert vertex group, object transform, lock...)
            hov = b.widget(x0, y0, x1, y1, 'bool', name, pid, idx, tip=tip, label=p.name,
                           desc=desc)
            tw = m.ui.wcol_toggle
            b.add('rect', x0, y0, x1, y1, _col(tw.inner_sel if v else tw.inner,
                                               lift=0.05 if hov else 0), WIDGET_RADIUS * S)
            icon = c.icon(v) if callable(c.icon) else c.icon
            ic = _col(tw.text_sel if v else tw.text)
            if not _bicon(b, icon, (x0 + x1) / 2, yc, S, ic):
                b.text(x0, yc, "⇄" if 'arrow' in icon else "•", ic, max_w=x1 - x0, align='C')
            return
        if c.toggle:
            hov = b.widget(x0, y0, x1, y1, 'bool', name, pid, idx, tip=tip, label=p.name,
                           desc=desc)
            _w_toggle(b, m, x0, y0, x1, y1, c.text, bool(v), hov)
            return
        hov = b.widget(x0, y0, x1 if c.text else x0 + round(m.U * 0.8), y1, 'bool', name, pid,
                       idx, tip=tip, label=p.name, desc=desc)
        s_ = _w_checkbox(b, m, x0, yc, bool(v), hov)
        if c.text:
            b.text(x0 + s_ + m.pad, yc, c.text, m.text, max_w=x1 - x0 - s_ - m.pad)
        return
    if t in {'INT', 'FLOAT'}:
        idx = c.idx if p.is_array else -1
        if p.is_array and idx < 0:
            return
        v = getattr(owner, c.pid)
        v = v[idx] if idx >= 0 else v
        e = HUD.edit
        key = ('num', name, pid, idx)
        hov = b.widget(x0, y0, x1, y1, 'num', name, pid, idx, tip=tip, label=p.name, desc=desc)
        if e is not None and e['key'] == key:
            _w_edit(b, m, x0, y0, x1, y1, e)
            return
        slider = (c.slider or (p.subtype in {'FACTOR', 'PERCENTAGE'})) and \
            abs(p.hard_max - p.hard_min) < 1e6 and not p.is_array
        frac = ((v - p.hard_min) / (p.hard_max - p.hard_min)) if slider and \
            p.hard_max > p.hard_min else None
        txt = _fmt_value(p, v, m.scene)
        if inline:
            _w_number(b, m, x0, y0, x1, y1, "", hov, frac, selected=key in HUD.sel_keys)
            tc = _col(m.ui.wcol_num.text)
            b.text(x0 + m.pad, yc, inline, tc, max_w=(x1 - x0) * 0.6)
            b.text(x0, yc, txt, tc, max_w=x1 - x0 - m.pad, align='R')
        else:
            _w_number(b, m, x0, y0, x1, y1, txt, hov, frac, selected=key in HUD.sel_keys)
        if ctx.lay_red(c):
            pass
        return
    if t == 'ENUM':
        hov = b.widget(x0, y0, x1, y1, 'enum', name, pid, tip=tip, flag=p.is_enum_flag,
                       label=p.name, desc=desc)
        _w_field(b, m, x0, y0, x1, y1, _enum_text(p, getattr(owner, c.pid)), hov,
                 m.ui.wcol_menu, arrow=True)
        return
    # POINTER / STRING
    v = getattr(owner, c.pid)
    txt = (v.name if v else "") if t == 'POINTER' else (v or "")
    hov = b.widget(x0, y0, x1, y1, 'popup', name, pid, tip=tip, label=p.name, desc=desc)
    _w_field(b, m, x0, y0, x1, y1, "", hov, m.ui.wcol_text)
    ix = x0
    icon = c.icon
    if t == 'POINTER' and v is not None and isinstance(v, bpy.types.Object):
        icon = _ob_icon(v)
    elif t == 'POINTER' and icon is None:
        icon = {'Object': 'object_data', 'Collection': 'outliner_collection',
                'Texture': 'texture', 'NodeTree': 'nodetree'}.get(p.fixed_type.identifier)
    if icon:
        cc = _icon_cat_color(m.ui, icon) if icon.startswith('outliner_ob') else None
        if _bicon(b, icon, x0 + 10 * S, yc, S, cc or m.dim):
            ix += 16 * S
    if txt:
        b.text(ix + m.pad, yc, txt, _col(m.ui.wcol_text.text), max_w=x1 - ix - 2 * m.pad)
    elif t == 'POINTER':
        # empty ID field shows its type as a dimmed placeholder, like Blender
        b.text(ix + m.pad, yc, p.fixed_type.name, _col(m.ui.wcol_text.text, alpha=0.4),
               max_w=x1 - ix - 2 * m.pad)
