# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Builds the whole panel (title, toolbar, modifiers, footer) and draws it."""

import time
import traceback

import blf
import bpy

from .constants import (
    BLOCK_RADIUS, COL_ADD, DEFAULT_FOOTER, FONT, PANEL_RADIUS, PANEL_TITLE,
)
from .state import HUD
from .utils import (
    _active_object, _clamp_panel, _col, _edit_lock, _scale, _selected_keys,
    _supports_modifiers,
)
from .gpu_draw import _draw_items, _shift, _title_font
from .widgets import _Builder, _icon_collapse, _icon_grip, _icon_x, _Metrics, _over, _w_button
from .tooltips import _build_tooltip
from .modifier_block import _build_modifier
from .keymap import _toggle_key_label


def _build_layout(context, region):
    """Return (draw items, widgets, header rows) in region coordinates."""
    S_now = _scale()
    if HUD.size_scale and abs(HUD.size_scale - S_now) > 1e-4:
        # The Resolution Scale changed while the panel is open: keep its size
        # (and position) proportional instead of squeezing the new-size content.
        f = S_now / HUD.size_scale
        HUD.w = round(HUD.w * f)
        HUD.max_h = round(HUD.max_h * f)
        HUD.x = max(0, min(HUD.x, region.width - HUD.w))   # a larger panel still fits
    HUD.size_scale = S_now
    m = _Metrics(context)
    S, U, pad, g, W, ui = m.S, m.U, m.pad, m.g, m.W, m.ui
    obj = _active_object(context)
    valid = _supports_modifiers(obj)
    if not (HUD.drag and HUD.drag.get('type') in {'move', 'resize'}):
        _clamp_panel(region)      # the viewport may have been resized: keep the panel reachable

    # ---- scrollable content (local coordinates, y going down from 0) ----
    HUD.sel_keys = _selected_keys()
    cb = _Builder(m)
    headers_local = []
    d = HUD.drag
    live = (d if d and d.get('type') == 'reorder' and d.get('active')
            and d.get('target') is not None else None)
    float_range = None
    if not valid:
        cb.new_row(U * 2)
        cb.text(pad * 2, -U, "Select an object that supports modifiers", m.dim, max_w=m.cw)
    elif len(obj.modifiers) == 0:
        cb.new_row(U * 2)
        cb.text(pad * 2, -U, "No modifiers – use Add Modifier", m.dim, max_w=m.cw)
    else:
        cb.new_row(g)
        if _edit_lock(obj):
            t_, b_ = cb.new_row(U)
            cb.text(pad * 2, (t_ + b_) / 2,
                    "Linked data: read-only" if obj.library is not None
                    else "Non-editable override: read-only", m.dim, max_w=m.cw)
        mods = list(obj.modifiers)
        count = len(mods)
        if live is not None and live['mod'] in obj.modifiers:
            # Live reorder: lay the stack out in the order it will have on drop,
            # so the other modifiers slide out of the way while dragging.
            dragged = obj.modifiers[live['mod']]
            others = [md for md in mods if md.name != live['mod']]
            t = max(0, min(len(others), live['target']))
            mods = others[:t] + [dragged] + others[t:]
        for mod in mods:
            top0 = cb.y
            i0, w0 = len(cb.items), len(cb.widgets)
            index = obj.modifiers.find(mod.name)
            try:
                headers_local.append((mod.name,) + _build_modifier(cb, m, mod, index, count))
            except Exception:
                # Never let one modifier hide the whole panel.
                if not HUD.draw_error:
                    HUD.draw_error = True
                    traceback.print_exc()
                t_, b_ = cb.new_row(U)
                cb.text(pad * 3, (t_ + b_) / 2, f"{mod.name}: settings can't be shown here",
                        m.dim, max_w=m.cw - pad * 2)
                headers_local.append((mod.name, top0, b_, cb.y))
            if live is not None and mod.name == live['mod']:
                float_range = (i0, len(cb.items), w0, len(cb.widgets), top0, cb.y)
            cb.new_row(3 * g)
    content_h = -cb.y

    ol_h = 0                              # no outliner in Lite
    title_h = round(U * 1.5)
    tool_h = U + 2 * pad
    foot_h = round(U * 0.95)
    fixed_h = title_h + ol_h + tool_h + foot_h
    # Never let the panel run past the bottom of the viewport: if its top is
    # low, the modifier list gets shorter (and scrolls) so the footer stays visible.
    if HUD.place_pending:
        # Just opened at the mouse: keep the top at the cursor and only move the
        # panel up as far as needed for its natural height to fit on screen.
        HUD.place_pending = False
        natural = fixed_h + min(content_h, max(U * 2, HUD.max_h - fixed_h))
        HUD.y = max(HUD.y, min(region.height, natural + round(4 * S)))
    avail_h = max(fixed_h + U * 2, HUD.y - round(4 * S))
    max_content = max(U * 2, min(HUD.max_h, avail_h) - fixed_h)
    view_h = min(content_h, max_content)
    total = fixed_h + view_h
    HUD.scroll = max(0.0, min(HUD.scroll, content_h - view_h))
    HUD.content_h, HUD.view_h, HUD.h = content_h, view_h, total
    if HUD.y - total < 0 and not (HUD.drag and HUD.drag.get('type') == 'move'):
        HUD.y = min(region.height, total + round(4 * S))   # lift it so the footer stays visible

    x0, ytop = HUD.x, HUD.y
    ybot = ytop - total
    fb = _Builder(m)          # fixed frame (title/outliner/toolbar/footer), absolute coords
    R = PANEL_RADIUS * S

    # soft shadow (two layers) + background
    fb.add('rect', x0 + 1 * S, ybot - 6 * S, x0 + W + 3 * S, ytop - 1 * S, (0, 0, 0, 0.12), R + 3 * S)
    fb.add('rect', x0 + 2 * S, ybot - 4 * S, x0 + W + 2 * S, ytop - 2 * S, (0, 0, 0, 0.26), R)
    fb.add('rect', x0, ybot, x0 + W, ytop, _col(ui.wcol_menu_back.inner, alpha=0.97), R)
    fb.add('outline', x0, ybot, x0 + W, ytop, _col(ui.wcol_menu_back.outline, alpha=0.9), R)

    # title bar
    ty0 = ytop - title_h
    fb.add('rect', x0, ty0, x0 + W, ytop, _col(ui.panel_header, lift=0.02), R)
    fb.add('rect', x0, ty0, x0 + W, ty0 + R, _col(ui.panel_header, lift=0.02), 0)
    hov_close = fb.widget(x0 + W - title_h, ty0, x0 + W, ytop, 'close',
                          tip=f"Close {PANEL_TITLE}\nShortcut: {_toggle_key_label()}")
    fb.widget(x0, ty0, x0 + W - title_h, ytop, 'title',
              tip=f"{PANEL_TITLE}\nDrag the title bar to move the panel.")
    tyc = (ty0 + ytop) / 2
    # logo (original ModPerf icon, multi-coloured)
    lsz = round(U * 0.95)
    lx = x0 + pad * 2
    fb.add('logo', lx, tyc - lsz / 2, lx + lsz, tyc + lsz / 2)
    tx = lx + lsz + round(6 * S)
    # "ModPerf" in the bundled bold font (Poppins Bold), object name in the UI font
    fid, fsz = _title_font(), round(m.fs * 1.18)
    if fid is not None:
        blf.size(fid, fsz)
        tw_ = blf.dimensions(fid, PANEL_TITLE)[0]
        cap = blf.dimensions(fid, "M")[1]
        fb.add('text', tx, tyc - cap / 2, PANEL_TITLE, _col(ui.panel_title), fid, fsz)
    else:
        tw_ = blf.dimensions(FONT, PANEL_TITLE)[0]
        fb.text(tx, tyc, PANEL_TITLE, _col(ui.panel_title))
    if obj:
        fb.text(tx + tw_ + round(8 * S), tyc, f"·  {obj.name}", m.dim,
                max_w=x0 + W - title_h - (tx + tw_ + round(8 * S)) - pad)
    _icon_x(fb, x0 + W - title_h / 2, (ty0 + ytop) / 2, S, m.text if hov_close else m.dim)

    # toolbar
    by1 = ytop - title_h - ol_h - pad
    by0 = by1 - U
    xr = x0 + W - pad
    hov = fb.widget(xr - U, by0, xr, by1, 'collapse_all',
                    tip="Collapse / Expand All\nShow or hide the settings of every modifier.")
    _w_button(fb, m, xr - U, by0, xr, by1, "", hov)
    _icon_collapse(fb, xr - U / 2, (by0 + by1) / 2, S, m.text)
    xr -= U + g
    ax0 = x0 + pad
    hov = fb.widget(ax0, by0, xr, by1, 'add',
                    tip="Add Modifier\nAdd a procedural operation/effect to the active object.\n"
                        "Start typing in the menu to search.")
    _w_button(fb, m, ax0, by0, xr, by1, "Add Modifier", hov, icon='plus', color=COL_ADD,
              bg=_col(ui.wcol_menu_back.inner))

    # content (translated + culled per row)
    ctop = ytop - title_h - ol_h - tool_h
    cbot = ctop - view_h
    off_y = ctop + HUD.scroll
    items = list(it for _r, it in fb.items)
    widgets = list(w for _r, w in fb.widgets)
    eps = 0.5
    fi0, fi1, fw0, fw1 = (float_range[:4] if float_range else (-1, -1, -1, -1))
    for i, ((rt, rb), it) in enumerate(cb.items):
        if fi0 <= i < fi1:
            continue                                   # dragged block: drawn floating below
        if rt + off_y > ctop + eps or rb + off_y < cbot - eps:
            continue
        items.append(_shift(it, x0, off_y))
    for i, ((rt, rb), w) in enumerate(cb.widgets):
        if fw0 <= i < fw1:
            continue
        if rt + off_y > ctop + eps or rb + off_y < cbot - eps:
            continue
        a, b_, c, d_ = w['rect']
        w['rect'] = (a + x0, b_ + off_y, c + x0, d_ + off_y)
        widgets.append(w)
    headers = [(n, t + off_y, hb + off_y, bb + off_y) for n, t, hb, bb in headers_local]

    # live reorder: empty slot + the dragged modifier following the mouse
    if float_range is not None:
        ftop, fbot = float_range[4], float_range[5]
        blk_h = ftop - fbot
        slot_t = min(ctop, ftop + off_y)
        slot_b = max(cbot, fbot + off_y)
        if slot_t > slot_b:
            items.append(('rect', x0 + pad, slot_b, x0 + W - pad, slot_t,
                          _over(ui.panel_active, ui.wcol_menu_back.inner, 0.12), BLOCK_RADIUS * S))
            items.append(('outline', x0 + pad, slot_b, x0 + W - pad, slot_t,
                          _col(ui.panel_active), BLOCK_RADIUS * S))
        float_top = live.get('float_top', ftop + off_y)
        float_top = max(min(float_top, ctop + U), cbot + min(blk_h, U * 2))
        dy = float_top - (ftop + off_y)
        fl = []
        for (rt, rb), it in cb.items[fi0:fi1]:
            if rt + off_y + dy > ctop + U + eps or rb + off_y + dy < cbot - U - eps:
                continue
            fl.append(_shift(it, x0, off_y + dy))
        vis_top = min(float_top, ctop + U)
        vis_bot = max(float_top - blk_h, cbot - U)
        if fl and vis_top > vis_bot:
            items.append(('rect', x0 + pad + 2 * S, vis_bot - 4 * S, x0 + W - pad + 2 * S,
                          vis_top - 2 * S, (0, 0, 0, 0.35), BLOCK_RADIUS * S))
        items += fl

    # scrollbar
    if content_h > view_h + 0.5:
        sx1 = x0 + W - 2 * S
        sx0 = sx1 - 3 * S
        th = max(U, view_h * view_h / content_h)
        ty1_ = ctop - (view_h - th) * (HUD.scroll / (content_h - view_h))
        items.append(('rect', sx0, cbot, sx1, ctop, _col(ui.wcol_scroll.inner, alpha=0.4), 1.5 * S))
        items.append(('rect', sx0, ty1_ - th, sx1, ty1_, _col(ui.wcol_scroll.item), 1.5 * S))

    # footer
    fy1 = ybot + foot_h
    fb2 = _Builder(m)
    if HUD.status and time.monotonic() - HUD.status_time < 5.0:
        msg, col = HUD.status, m.text
    else:
        msg, col = DEFAULT_FOOTER.format(key=_toggle_key_label()), m.dim
    n_sel = len(HUD.sel_keys)
    if HUD.edit is not None:
        if HUD.edit.get('mode') == 'text':
            msg = ("Type To Search   ·   Enter: Confirm   ·   Esc: Cancel"
                   if HUD.edit['key'][0] == 'ol_search' else
                   "Type A Name   ·   Enter: Confirm   ·   Esc: Cancel")
        else:
            msg = ("Type A Value" + (f" ({n_sel} Fields)" if n_sel > 1 else "")
                   + "   ·   Enter: Confirm   ·   Esc: Cancel")
        col = m.text
    elif n_sel > 1:
        msg, col = (f"{n_sel} Values Selected   ·   Drag Or Type: Change All"
                    "   ·   Click Elsewhere: Clear"), m.text
    fb2.text(x0 + pad * 2, (ybot + fy1) / 2, msg, col, max_w=W - foot_h - g - pad * 3)
    fb2.widget(x0 + W - foot_h, ybot, x0 + W, fy1, 'resize', tip="Resize\nDrag to resize the panel.")
    _icon_grip(fb2, x0 + W - 2 * S, ybot + 1 * S, S, m.dim)
    items += [it for _r, it in fb2.items]
    widgets += [w for _r, w in fb2.widgets]
    # Lowest priority: anywhere on the panel that isn't a control moves it.
    widgets.insert(0, dict(rect=(x0, ybot, x0 + W, ytop), key=('move_bg', None, None, -1),
                           kind='move_bg', mod=None, prop=None, idx=-1, tip=""))
    return items, widgets, headers


# =============================================================================
# Draw callback
# =============================================================================

LAYOUT_MAX_AGE = 0.25   # seconds a cached layout may be reused without any event


def _draw_callback():
    if not HUD.running:
        return
    context = bpy.context
    if context.mode != 'OBJECT':
        return          # closing: the modal shuts the panel on its next event
    region = context.region
    if region is None or region.as_pointer() != HUD.region_ptr:
        return
    try:
        now = time.monotonic()
        size = (region.width, region.height, _scale())   # resize / UI scale: rebuild now
        c = HUD.layout_cache
        if HUD.layout_dirty or c is None or c[1] != size or now - c[0] > LAYOUT_MAX_AGE:
            items, widgets, headers = _build_layout(context, region)
            HUD.widgets = widgets
            HUD.headers = headers
            HUD.layout_cache = (now, size, items)
            HUD.layout_dirty = False
        else:
            items = c[2]
        blf.size(FONT, round(11 * _scale()))
        _draw_items(items, region)
        if HUD.tip_visible and HUD.tip_lines:
            _draw_items(_build_tooltip(region), region)
    except Exception:
        if not HUD.draw_error:
            HUD.draw_error = True
            traceback.print_exc()
