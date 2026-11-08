# Copyright (C) 2026 Raisy Clutch
# raisycltch@gmail.com
#
# Created by Raisy Clutch
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Overlays: popover menus, tooltips, toasts, dialogs and floating windows."""

import math
import time

from .core import Widget, call, mark_animating, ease_out_back, ease_out_cubic
from .draw import wrap_text
from .layout import Column, Row, ScrollView
from .theme import alpha, mix, lighten
from .widgets import Button, TextInput, _norm_items


class Overlay(Widget):
    """Something drawn above the main UI. Subclasses set rect in place()."""

    keyboard_nav = False

    modal = False            # block everything below while open
    dismiss_outside = False  # close when clicking elsewhere
    layer = 1

    def __init__(self, **kw):
        super().__init__(**kw)
        self.surface = None
        self.area_ptr = None
        self.closing = False
        self.on_close = None
        self.opened_at = time.perf_counter()

    def place(self, ctx, rx, ry, rw, rh):
        """Compute and arrange inside the region rect."""

    def close(self):
        if self.surface:
            self.surface.remove_overlay(self)

    def appear(self, speed=14):
        return self.anim("appear", 1.0, speed=speed)


# ---------------------------------------------------------------------------
# Menu + popover
# ---------------------------------------------------------------------------

class MenuItem:
    """A menu entry.

    MenuItem("Duplicate", icon="copy", shortcut="Shift D", action="duplicate")     # app action
    MenuItem("Add cube", operator="mesh.primitive_cube_add", props={"size": 2})   # Blender operator
    MenuItem("Hello", on_click=lambda: print("hi"))                               # any function
    MenuItem("More", submenu=[MenuItem(...), ...])
    MenuItem("Wireframe", checked=lambda: ..., on_click=...)                      # check mark
    """

    def __init__(self, label, on_click=None, icon=None, shortcut=None, description=None, action=None,
                 operator=None, props=None, submenu=None, checked=None, enabled=True, danger=False, id=None):
        self.label = label
        self.on_click = on_click
        self.icon = icon
        self.shortcut = shortcut
        self.description = description
        self.action = action
        self.operator = operator
        self.props = props or {}
        self.submenu = submenu
        self.checked = checked
        self.enabled = enabled
        self.danger = danger
        self.id = id if id is not None else label

    def is_checked(self):
        c = self.checked
        return bool(c()) if callable(c) else bool(c)

    def is_enabled(self):
        e = self.enabled
        try:
            return bool(e()) if callable(e) else bool(e)
        except Exception:
            return False

    def run(self, app=None, context_widget=None):
        if self.on_click is not None:
            call(self.on_click, context_widget)
        if self.action is not None and app is not None:
            app.run_action(self.action)
        if self.operator:
            from . import run_operator
            try:
                run_operator(self.operator, **self.props)
            except Exception as e:
                if app is not None:
                    app.toast("Couldn't run " + self.label, str(e).split("\n")[0], "danger")


class MenuSeparator:
    def __init__(self, label=None):
        self.label = label


SEPARATOR = MenuSeparator()


def _norm_menu(items):
    out = []
    for it in items:
        if it is None or it == "-" or isinstance(it, MenuSeparator):
            out.append(it if isinstance(it, MenuSeparator) else SEPARATOR)
        elif isinstance(it, MenuItem):
            out.append(it)
        else:
            iid, label, icon, desc = _norm_items([it])[0]
            out.append(MenuItem(label, icon=icon, description=desc, id=iid))
    return out


class Menu(Widget):
    """List of selectable items: icons, descriptions, shortcuts, check marks, separators, sub-menus,
    hover and keyboard navigation, optional search.

    items: MenuItem / MenuSeparator / "-" or plain (id, label, icon, description) tuples.
    on_pick(id) is called for tuple items (and every item); MenuItems also run their own action."""

    focusable = True
    cursor = "HAND"
    keyboard_nav = False

    def __init__(self, items, value=None, on_pick=None, searchable=False, max_rows=9, context=None, **kw):
        super().__init__(**kw)
        self.all_items = _norm_menu(items)
        self.value = value
        self.on_pick = on_pick
        self.searchable = searchable
        self.max_rows = max_rows
        self.context = context
        self.query = ""
        self.search = TextInput("Search", icon="search", on_change=self._filter, clearable=True) if searchable else None
        if self.search:
            self.search.parent = self
        self.items = list(self.all_items)
        self._hov = -1
        ids = [getattr(it, "id", None) for it in self.items]
        self._kb = ids.index(value) if value in ids else self._first_selectable()
        self.scroll = 0.0
        self._rows = []
        self._sub_for = None

    def children(self):
        return (self.search,) if self.search else ()

    def interactive(self):
        return True

    def _first_selectable(self):
        for i, it in enumerate(self.items):
            if isinstance(it, MenuItem):
                return i
        return 0

    def _filter(self, q):
        self.query = q.lower()
        self.items = [it for it in self.all_items if isinstance(it, MenuItem) and (
            self.query in it.label.lower() or (it.description and self.query in it.description.lower()))]
        self._kb = 0
        self.scroll = 0.0
        self.redraw()

    def _has_desc(self):
        return any(isinstance(it, MenuItem) and it.description for it in self.all_items)

    def _row_h(self, ctx, it):
        if isinstance(it, MenuSeparator):
            return ctx.px(18 if it.label else 9)
        return ctx.px(42 if (self._has_desc() and it.description) else 30)

    def measure(self, ctx, avail_w):
        hs = [self._row_h(ctx, it) for it in self.all_items[:self.max_rows]] or [ctx.px(30)]
        h = sum(hs) + ctx.px(8)
        if self.search:
            h += ctx.px(40)
        return avail_w, h

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        if self.search:
            self.search.measure(ctx, w - ctx.px(12))
            self.search.arrange(ctx, x + ctx.px(6), y + h - ctx.px(6) - ctx.px(30), w - ctx.px(12), ctx.px(30))

    def _list_rect(self, ctx):
        x, y, w, h = self.rect
        top = y + h - ctx.px(4) - (ctx.px(40) if self.search else 0)
        return x, y + ctx.px(4), w, top - y - ctx.px(4)

    def _layout_rows(self, ctx):
        lx, ly, lw, lh = self._list_rect(ctx)
        top = ly + lh + self.scroll
        rows = []
        for it in self.items:
            rh = self._row_h(ctx, it)
            rows.append((top - rh, rh))
            top -= rh
        self._rows = rows
        return rows

    def _row_h_total(self, ctx):
        return sum(self._row_h(ctx, it) for it in self.items)

    def _at(self, ctx, ev):
        lx, ly, lw, lh = self._list_rect(ctx)
        if not (ly <= ev.y <= ly + lh):
            return -1
        for i, (ry, rh) in enumerate(self._layout_rows(ctx)):
            if ry <= ev.y <= ry + rh:
                return i if isinstance(self.items[i], MenuItem) else -1
        return -1

    def _row(self, i):
        return self._rows[i] if 0 <= i < len(self._rows) else None

    def on_hover(self, ctx, ev):
        i = self._at(ctx, ev)
        if i != self._hov:
            self._hov = i
            if i >= 0:
                self._kb = i
                self._open_sub(ctx, i)
            self.redraw()

    def _popover(self):
        p = self.parent
        while p is not None and not isinstance(p, Overlay):
            p = p.parent
        return p

    def _open_sub(self, ctx, i):
        it = self.items[i]
        pop = self._popover()
        surf = ctx.surface
        if pop is None or surf is None:
            return
        if not (isinstance(it, MenuItem) and it.submenu):
            if self._sub_for is not None:
                for o in list(surf.overlays):
                    if getattr(o, "parent_pop", None) is pop:
                        surf.remove_overlay(o)
                self._sub_for = None
            return
        if self._sub_for == i:
            return
        self._sub_for = i
        sub = it.submenu() if callable(it.submenu) else it.submenu
        ry, rh = self._layout_rows(ctx)[i]
        x, y, w, h = self.rect

        class _Anchor:
            rect = (x, ry, w, rh)
        child = Menu(sub, on_pick=self.on_pick, context=self.context)
        surf.open_popover(child, anchor=_Anchor, width=ctx.px(210), parent=pop, side="right",
                          area_ptr=pop.area_ptr)

    def on_leave(self, ctx):
        self._hov = -1
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        i = self._at(ctx, ev)
        if i >= 0:
            self._pick(i, ctx)

    def _pick(self, i, ctx=None):
        it = self.items[i]
        if not isinstance(it, MenuItem) or not it.is_enabled():
            return
        if it.submenu:
            if ctx is not None:
                self._open_sub(ctx, i)
            return
        self.value = it.id
        pop = self._popover()
        root = pop
        while root is not None and getattr(root, "parent_pop", None) is not None:
            root = root.parent_pop
        surf = pop.surface if pop is not None else None
        if root is not None:
            root.close()
        elif pop is not None:
            pop.close()
        app = surf.app if surf is not None else None
        call(self.on_pick, it.id)
        it.run(app, self.context)

    def on_wheel(self, ctx, ev):
        lx, ly, lw, lh = self._list_rect(ctx)
        total = self._row_h_total(ctx)
        self.scroll = max(0.0, min(total - lh, self.scroll - ev.wheel * ctx.px(30)))
        self.redraw()
        return True

    def _move(self, d):
        n = len(self.items)
        i = self._kb
        for _ in range(n):
            i = (i + d) % n
            if isinstance(self.items[i], MenuItem):
                self._kb = i
                return

    def on_key(self, ctx, ev):
        if ev.type == "DOWN_ARROW":
            self._move(1)
        elif ev.type == "UP_ARROW":
            self._move(-1)
        elif ev.type == "RIGHT_ARROW":
            if 0 <= self._kb < len(self.items):
                self._open_sub(ctx, self._kb)
            return True
        elif ev.type in ("RET", "NUMPAD_ENTER"):
            if 0 <= self._kb < len(self.items):
                self._pick(self._kb, ctx)
            return True
        elif self.search is not None and ev.type not in ("ESC",):
            self.search.focused = True
            self.search.on_key(ctx, ev)
            return True
        else:
            return False
        lx, ly, lw, lh = self._list_rect(ctx)
        rows = self._layout_rows(ctx)
        if 0 <= self._kb < len(rows):
            ry, rh = rows[self._kb]
            if ry < ly:
                self.scroll += ly - ry
            elif ry + rh > ly + lh:
                self.scroll -= (ry + rh) - (ly + lh)
            self.scroll = max(0.0, self.scroll)
        self.redraw()
        return True

    def paint(self, ctx, p):
        th = ctx.theme
        if self.search:
            self.search.focused = True
            self.search.paint(ctx, p)
        lx, ly, lw, lh = self._list_rect(ctx)
        p.push_clip(lx, ly, lw, lh)
        if not self.items:
            p.text("No matches", lx + lw / 2, ly + lh / 2, th.fs_sm, th.text_muted, align="center", valign="center")
        for i, (it, (ry, rh)) in enumerate(zip(self.items, self._layout_rows(ctx))):
            if ry > ly + lh or ry + rh < ly:
                continue
            if isinstance(it, MenuSeparator):
                cy = ry + rh / 2
                if it.label:
                    p.text(it.label.upper(), lx + ctx.px(13), cy, th.fs_xs, th.text_muted, "semibold",
                           valign="center")
                else:
                    p.rect(lx + ctx.px(10), cy - 0.5, lw - ctx.px(20), 1, fill=th.border)
                continue
            en = it.is_enabled()
            on = it.id == self.value or it.is_checked()
            hl = i == self._kb and en
            if hl:
                p.rect(lx + ctx.px(5), ry + ctx.px(1.5), lw - ctx.px(10), rh - ctx.px(3),
                       fill=alpha(th.danger, 0.18) if it.danger else th.surface_4, radius=ctx.px(7))
            base = th.danger if it.danger else (th.text if (on or hl) else th.text_dim)
            if not en:
                base = th.text_disabled
            cx = lx + ctx.px(13)
            if it.icon:
                isz = ctx.px(15)
                p.icon(it.icon, cx, ry + rh / 2 - isz / 2, isz,
                       th.accent if (on and not it.danger) else (th.danger if it.danger else
                                                                  (th.text_dim if en else th.text_disabled)), 1.5)
                cx += isz + ctx.px(9)
            right = lx + lw - ctx.px(14)
            if on:
                isz = ctx.px(14)
                p.icon("check", right - isz, ry + rh / 2 - isz / 2, isz, th.accent, 2.0)
                right -= isz + ctx.px(6)
            if it.submenu:
                isz = ctx.px(13)
                p.icon("chevron_right", right - isz, ry + rh / 2 - isz / 2, isz, th.text_muted, 1.7)
                right -= isz + ctx.px(6)
            elif it.shortcut:
                sw = p.measure(it.shortcut, th.fs_xs, "medium")[0]
                p.text(it.shortcut, right, ry + rh / 2, th.fs_xs, th.text_muted, "medium", align="right",
                       valign="center")
                right -= sw + ctx.px(10)
            if it.description and self._has_desc():
                p.text(it.label, cx, ry + rh * 0.64, th.fs_md, base, "medium", valign="center", max_w=right - cx)
                p.text(it.description, cx, ry + rh * 0.3, th.fs_xs, th.text_muted, valign="center",
                       max_w=right - cx)
            else:
                p.text(it.label, cx, ry + rh / 2, th.fs_md, base, "medium" if on else "regular",
                       valign="center", max_w=right - cx)
        p.pop_clip()
        total = self._row_h_total(ctx)
        if total > lh:
            frac = lh / total
            bh = max(ctx.px(20), lh * frac)
            by = ly + lh - bh - (lh - bh) * (self.scroll / max(1.0, total - lh))
            p.rect(lx + lw - ctx.px(5), by, ctx.px(3), bh, fill=alpha(th.text, 0.2), radius=ctx.px(1.5))


class Popover(Overlay):
    """Floating card anchored to a widget (dropdowns, context menus, pickers)."""

    dismiss_outside = True
    layer = 3

    def __init__(self, content, anchor=None, width=None, at=None, side="auto", **kw):
        super().__init__(**kw)
        self.content = content
        content.parent = self
        self.anchor = anchor
        self.width_px = width
        self.at = at
        self.side = side
        self._below = True

    def children(self):
        return (self.content,)

    def interactive(self):
        return True

    def place(self, ctx, rx, ry, rw, rh):
        w = self.width_px or ctx.px(220)
        pad = ctx.px(4)
        _cw, ch = self.content.measure(ctx, w - pad * 2)
        h = ch + pad * 2
        if self.anchor is not None:
            ax, ay, aw, ah = self.anchor.rect
        else:
            ax, ay = self.at or (rx + rw / 2, ry + rh / 2)
            aw = ah = 0
        gap = ctx.px(6)
        if self.side == "right":
            x = ax + aw + ctx.px(2)
            if x + w > rx + rw - ctx.px(6):
                x = ax - w - ctx.px(2)
            if x < rx + ctx.px(6):
                # no room on either side (narrow sidebar): overlap the parent, shifted in
                x = min(rx + rw - w - ctx.px(6), max(rx + ctx.px(6), ax + ctx.px(24)))
            y = min(ay + ah + ctx.px(4), ry + rh - ctx.px(6)) - h
            y = max(ry + ctx.px(6), y)
            self._below = True
            self.rect = (x, y, w, h)
            self.content.arrange(ctx, x + pad, y + pad, w - pad * 2, h - pad * 2)
            return
        below_y = ay - gap - h
        above_y = ay + ah + gap
        if self.side == "above" or (self.side == "auto" and below_y < ry + ctx.px(6) and above_y + h < ry + rh):
            y = above_y
            self._below = False
        else:
            y = max(ry + ctx.px(6), below_y)
            self._below = True
            if y + h > ay:
                h = max(ctx.px(60), ay - gap - (ry + ctx.px(6)))
                y = ay - gap - h
        x = min(max(rx + ctx.px(6), ax), rx + rw - w - ctx.px(6))
        self.rect = (x, y, w, h)
        self.content.arrange(ctx, x + pad, y + pad, w - pad * 2, h - pad * 2)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        t = ease_out_cubic(self.appear(18))
        r = ctx.px(12)
        vis_h = h * (0.6 + 0.4 * t)
        vy = y + h - vis_h if self._below else y
        p.shadow(x, vy, w, vis_h, r, (0, 0, 0, 0.5 * t), ctx.px(18), dy=-ctx.px(6))
        p.rect(x, vy, w, vis_h, fill=th.surface_2, fill2=mix(th.surface_2, th.surface_1, 0.5), radius=r,
               border=th.border_strong, border_w=ctx.px(1))
        p.push_clip(x, vy, w, vis_h)
        self.content.paint(ctx, p)
        p.pop_clip()


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------

class Tooltip(Overlay):
    layer = 5

    def __init__(self, text, target):
        super().__init__()
        self.text = text
        self.target = target

    def hit(self, x, y):
        return None

    def place(self, ctx, rx, ry, rw, rh):
        th = ctx.theme
        title, _, body = self.text.partition("\n")
        maxw = ctx.px(240)
        self._title = title
        self._body = wrap_text(body, ctx.px(th.fs_xs), maxw - ctx.px(20)) if body else []
        tw = max([ctx.text_w(title, th.fs_sm, "semibold")] +
                 [ctx.text_w(l.rstrip(), th.fs_xs) for l, _ in self._body]) + ctx.px(20)
        w = min(maxw, tw)
        h = ctx.px(26) + ctx.px(th.fs_xs * 1.45) * len(self._body) + (ctx.px(2) if self._body else 0)
        ax, ay, aw, ah = self.target.rect
        x = min(max(rx + ctx.px(4), ax + aw / 2 - w / 2), rx + rw - w - ctx.px(4))
        y = ay - h - ctx.px(6)
        if y < ry + ctx.px(4):
            y = ay + ah + ctx.px(6)
        self.rect = (x, y, w, h)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        t = self.appear(20)
        p.shadow(x, y, w, h, ctx.px(8), (0, 0, 0, 0.45 * t), ctx.px(10), dy=-ctx.px(3))
        p.rect(x, y, w, h, fill=mix(th.surface_0, (0, 0, 0, 1), 0.3), radius=ctx.px(8),
               border=th.border_strong, border_w=ctx.px(1))
        top = y + h - ctx.px(13)
        p.text(self._title, x + ctx.px(10), top, th.fs_sm, th.text, "semibold", valign="center", max_w=w - ctx.px(20))
        lh = ctx.px(th.fs_xs * 1.45)
        top -= ctx.px(10) + lh / 2
        for line, _i in self._body:
            p.text(line.rstrip(), x + ctx.px(10), top, th.fs_xs, th.text_dim, valign="center")
            top -= lh


# ---------------------------------------------------------------------------
# Toasts
# ---------------------------------------------------------------------------

class Toast(Overlay):
    layer = 4
    cursor = "HAND"

    def __init__(self, title, message="", kind="info", duration=3.5, action=None, on_action=None):
        super().__init__()
        self.title = title
        self.message = message
        self.kind = kind
        self.duration = duration
        self.action = action
        self.on_action = on_action
        self.index = 0
        self._leaving = None

    def interactive(self):
        return True

    def _c(self, th):
        return {"success": th.success, "warning": th.warning, "danger": th.danger, "error": th.danger,
                "accent": th.accent}.get(self.kind, th.info)

    def size(self, ctx):
        th = ctx.theme
        w = min(ctx.px(300), ctx.region_w - ctx.px(24))
        self._lines = wrap_text(self.message, ctx.px(th.fs_sm), w - ctx.px(64)) if self.message else []
        h = ctx.px(44) + ctx.px(th.fs_sm * 1.45) * max(0, len(self._lines)) + (ctx.px(4) if self._lines else 0)
        return w, h

    def place_at(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)

    def expired(self):
        return self.duration and time.perf_counter() - self.opened_at > self.duration

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        if self.action and self.on_action:
            call(self.on_action, self)
        self.close()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        t = ease_out_back(self.appear(10), 1.2)
        off = (1 - t) * (w * 0.4)
        x += off
        c = self._c(th)
        r = ctx.px(12)
        p.shadow(x, y, w, h, r, (0, 0, 0, 0.5), ctx.px(16), dy=-ctx.px(5))
        p.rect(x, y, w, h, fill=th.surface_2, fill2=th.surface_1, radius=r, border=th.border_strong,
               border_w=ctx.px(1))
        p.rect(x, y, w, h, fill=alpha(c, 0.07), fill2=alpha(c, 0.0), angle=math.pi / 2, radius=r)
        icon = {"success": "success", "warning": "warning", "danger": "error", "error": "error",
                "accent": "sparkles"}.get(self.kind, "info")
        isz = ctx.px(18)
        top = y + h - ctx.px(22)
        p.circle(x + ctx.px(24), top, ctx.px(14), fill=alpha(c, 0.16))
        p.icon(icon, x + ctx.px(24) - isz / 2, top - isz / 2, isz, c, 1.7)
        tx = x + ctx.px(48)
        p.text(self.title, tx, top, th.fs_md, th.text, "semibold", valign="center", max_w=w - ctx.px(80))
        lh = ctx.px(th.fs_sm * 1.45)
        ly = top - ctx.px(18)
        for line, _i in self._lines:
            p.text(line.rstrip(), tx, ly, th.fs_sm, th.text_dim, valign="center")
            ly -= lh
        if self.action:
            p.text(self.action, x + w - ctx.px(14), top, th.fs_sm, th.accent, "semibold", align="right",
                   valign="center")
        else:
            p.icon("x", x + w - ctx.px(26), top - ctx.px(6), ctx.px(12), th.text_muted, 1.6)
        if self.duration:
            frac = 1.0 - min(1.0, (time.perf_counter() - self.opened_at) / self.duration)
            mark_animating()
            p.rect(x + r, y + ctx.px(1), (w - 2 * r) * frac, ctx.px(2), fill=alpha(c, 0.7), radius=ctx.px(1))


# ---------------------------------------------------------------------------
# Window (floating, draggable, resizable) and Dialog
# ---------------------------------------------------------------------------

class Window(Overlay):
    """Floating window over the viewport.

    chrome=True  title bar with icon, title, collapse and close buttons; drag by the title bar;
                 resize from the bottom-right corner.
    chrome=False a bare floating surface (toolbars, HUDs) that you can drag by its edge padding.
    anchor:      "free" or "bottom", "top", "center", "top_right"... (re-placed when the region resizes
                 until the user drags it)
    """

    layer = 2
    cursor = None

    def __init__(self, content=None, title="Window", icon=None, width=340, height=None, chrome=True,
                 resizable=True, closable=True, anchor="center", offset=(0, 0), scroll=True,
                 min_size=(220, 120), padding=12, transparent=False, on_close=None, **kw):
        super().__init__(**kw)
        self.title = title
        self.icon = icon
        self.w_dp = width
        self.h_dp = height
        self.chrome = chrome
        self.resizable = resizable and chrome
        self.closable = closable
        self.anchor = anchor
        self.offset = offset
        self.min_size = min_size
        self.padding = padding
        self.transparent = transparent
        self.on_close = on_close
        self.collapsed = False
        self.pos = None          # (x, top) in region px, set when the user drags
        self._drag = None
        self._hot = None         # "close", "collapse", "resize", "title"
        self.body = None
        self.set_content(content or Column(), scroll)

    def set_content(self, content, scroll=True):
        self.content = content
        self.body = ScrollView(content, padding=self.padding) if scroll else content
        self.body.parent = self
        self.scroll = scroll

    def children(self):
        return () if self.collapsed else (self.body,)

    def interactive(self):
        return True

    def _title_h(self, ctx):
        return ctx.px(38) if self.chrome else 0.0

    def place(self, ctx, rx, ry, rw, rh):
        w = ctx.px(self.w_dp)
        w = min(w, rw - ctx.px(16))
        th_ = self._title_h(ctx)
        if self.h_dp is not None:
            body_h = ctx.px(self.h_dp) - th_
        else:
            pad = ctx.px(self.padding)
            _cw, ch = self.content.measure(ctx, w - pad * 2)
            body_h = ch + pad * 2
        h = th_ + (0 if self.collapsed else body_h)
        h = min(h, rh - ctx.px(16))
        if self.pos is None:
            ox, oy = ctx.px(self.offset[0]), ctx.px(self.offset[1])
            a = self.anchor
            cx = rx + (rw - w) / 2
            top = ry + (rh + h) / 2
            if "bottom" in a:
                top = ry + h + ctx.px(24)
            if "top" in a:
                top = ry + rh - ctx.px(24)
            if "left" in a:
                cx = rx + ctx.px(24)
            if "right" in a:
                cx = rx + rw - w - ctx.px(24)
            x, top = cx + ox, top + oy
        else:
            x, top = self.pos
        x = min(max(rx + ctx.px(4), x), rx + rw - w - ctx.px(4))
        top = min(max(ry + h + ctx.px(4), top), ry + rh - ctx.px(4))
        self.rect = (x, top - h, w, h)
        if not self.collapsed:
            if self.scroll:
                self.body.measure(ctx, w)
                self.body.arrange(ctx, x, top - h, w, h - th_)
            else:
                pad = ctx.px(self.padding)
                self.body.measure(ctx, w - pad * 2)
                self.body.arrange(ctx, x + pad, top - h + pad, w - pad * 2, h - th_ - pad * 2)

    def _zones(self, ctx):
        x, y, w, h = self.rect
        top = y + h
        s = ctx.px(26)
        z = {}
        if self.chrome:
            bx = x + w - ctx.px(8) - s
            if self.closable:
                z["close"] = (bx, top - ctx.px(6) - s, s, s)
                bx -= s + ctx.px(2)
            z["collapse"] = (bx, top - ctx.px(6) - s, s, s)
            z["title"] = (x, top - self._title_h(ctx), w, self._title_h(ctx))
            if self.resizable and not self.collapsed:
                z["resize"] = (x + w - ctx.px(16), y, ctx.px(16), ctx.px(16))
        else:
            z["title"] = (x, y, w, h)
        return z

    def _zone_at(self, ctx, ev):
        for k in ("close", "collapse", "resize", "title"):
            r = self._zones(ctx).get(k)
            if r and r[0] <= ev.x <= r[0] + r[2] and r[1] <= ev.y <= r[1] + r[3]:
                return k
        return None

    def hit(self, x, y):
        if not self.contains(x, y):
            return None
        ctx = self.surface._ctx if self.surface is not None else None
        if ctx is not None and self.chrome:
            for k in ("close", "collapse", "resize"):
                z = self._zones(ctx).get(k)
                if z and z[0] <= x <= z[0] + z[2] and z[1] <= y <= z[1] + z[3]:
                    return self
        r = None
        if not self.collapsed:
            r = self.body.hit(x, y)
            if r is self.body and self.chrome is False:
                r = None
        return r or self

    def on_hover(self, ctx, ev):
        z = self._zone_at(ctx, ev)
        if z != self._hot:
            self._hot = z
            self.redraw()

    def on_leave(self, ctx):
        self._hot = None
        self.redraw()

    def on_press(self, ctx, ev):
        if self.surface:
            self.surface.raise_overlay(self)
        z = self._zone_at(ctx, ev)
        x, y, w, h = self.rect
        if z == "resize":
            self._drag = ("resize", ev.x, ev.y, w, h, x, y + h)
        elif z in ("title",):
            self._drag = ("move", ev.x, ev.y, x, y + h)
        else:
            self._drag = ("btn", z)
        return True

    def on_drag(self, ctx, ev):
        d = self._drag
        if not d:
            return
        if d[0] == "move":
            self.pos = (d[3] + ev.x - d[1], d[4] + ev.y - d[2])
            self.anchor = "free"
            self.redraw()
        elif d[0] == "resize":
            nw = max(ctx.px(self.min_size[0]), d[3] + ev.x - d[1])
            nh = max(ctx.px(self.min_size[1]), d[4] - (ev.y - d[2]))
            self.w_dp = nw / ctx.scale
            self.h_dp = nh / ctx.scale
            self.pos = (d[5], d[6])
            self.redraw()

    def on_release(self, ctx, ev, inside):
        d = self._drag
        self._drag = None
        if d and d[0] == "btn" and d[1] == self._zone_at(ctx, ev):
            if d[1] == "close":
                self.close()
            elif d[1] == "collapse":
                self.collapsed = not self.collapsed
                self.redraw()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        t = ease_out_cubic(self.appear(14))
        r = ctx.px(16)
        lift = (1 - t) * ctx.px(10)
        y -= lift
        drag = self._drag is not None and self._drag[0] == "move"
        if not self.transparent:
            p.shadow(x, y, w, h, r, (0, 0, 0, 0.55 if not drag else 0.7), ctx.px(22 if not drag else 30),
                     dy=-ctx.px(8))
            p.rect(x, y, w, h, fill=th.surface_1, fill2=mix(th.surface_1, th.bg, 0.4), radius=r,
                   border=th.border_strong if not drag else alpha(th.accent, 0.5), border_w=ctx.px(1))
        if self.chrome:
            th_h = self._title_h(ctx)
            top = y + h
            p.rect(x + ctx.px(1), top - th_h, w - ctx.px(2), th_h - ctx.px(1), fill=alpha(th.surface_2, 0.7),
                   radius=(r - 1, r - 1, 0 if not self.collapsed else r - 1, 0 if not self.collapsed else r - 1))
            if not self.collapsed:
                p.rect(x, top - th_h, w, ctx.px(1), fill=th.border)
            tx = x + ctx.px(14)
            if self.icon:
                isz = ctx.px(16)
                p.icon(self.icon, tx, top - th_h / 2 - isz / 2, isz, th.accent, 1.6)
                tx += isz + ctx.px(8)
            p.text(self.title, tx, top - th_h / 2, th.fs_md, th.text, "semibold", valign="center",
                   max_w=w - (tx - x) - ctx.px(70))
            z = self._zones(ctx)
            for k, ic in (("collapse", "chevron_down" if not self.collapsed else "chevron_up"), ("close", "x")):
                if k not in z:
                    continue
                bx, by, bw, bh = z[k]
                by -= lift
                hot = self._hot == k
                if hot:
                    p.rect(bx, by, bw, bh, fill=alpha(th.danger, 0.85) if k == "close" else th.surface_4,
                           radius=ctx.px(7))
                isz = ctx.px(14)
                p.icon(ic, bx + (bw - isz) / 2, by + (bh - isz) / 2, isz,
                       th.text if hot else th.text_dim, 1.8)
            if "resize" in z:
                gx, gy = x + w - ctx.px(6), y + ctx.px(6)
                col = th.accent if self._hot == "resize" else th.text_muted
                for i in range(3):
                    d = ctx.px(4) * (i + 1)
                    p.line(gx - d, gy, gx, gy + d, ctx.px(1.2), alpha(col, 0.7))
        if not self.collapsed:
            if lift:
                bx, by, bw, bh = self.body.rect
                self.body.arrange(ctx, bx, by - lift, bw, bh)
            if self.scroll:
                self.body.fade_color = th.surface_1
            p.push_clip(x, y + ctx.px(1), w, h - self._title_h(ctx) - ctx.px(1))
            self.body.paint(ctx, p)
            p.pop_clip()


class Dialog(Overlay):
    """Modal dialog with a dimmed backdrop. Enter confirms, Esc cancels."""

    modal = True
    layer = 6
    focusable = True

    def __init__(self, title, message="", content=None, confirm="Confirm", cancel="Cancel",
                 on_confirm=None, on_cancel=None, kind="accent", icon=None, width=360, danger=False):
        super().__init__()
        self.title = title
        self.message = message
        self.kind = "danger" if danger else kind
        self.icon = icon or {"danger": "warning", "success": "success", "info": "info"}.get(self.kind, "sparkles")
        self.w_dp = width
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        btns = []
        if cancel:
            btns.append(Button(cancel, on_click=lambda b: self._finish(False), variant="secondary"))
        if confirm:
            btns.append(Button(confirm, on_click=lambda b: self._finish(True),
                               variant="danger" if danger else "primary"))
        self.buttons = Row(btns, gap=8)
        self.buttons.parent = self
        self.content = content
        if content:
            content.parent = self
        self._lines = []

    def children(self):
        return tuple(c for c in (self.content, self.buttons) if c is not None)

    def interactive(self):
        return True

    def _finish(self, ok):
        self.close()
        call(self.on_confirm if ok else self.on_cancel, self)

    def on_key(self, ctx, ev):
        if ev.type in ("RET", "NUMPAD_ENTER"):
            self._finish(True)
            return True
        if ev.type == "ESC":
            self._finish(False)
            return True
        return False

    def place(self, ctx, rx, ry, rw, rh):
        th = ctx.theme
        self._region = (rx, ry, rw, rh)
        w = min(ctx.px(self.w_dp), rw - ctx.px(24))
        pad = ctx.px(20)
        inner = w - pad * 2
        self._lines = wrap_text(self.message, ctx.px(th.fs_md), inner) if self.message else []
        h = pad + ctx.px(44) + ctx.px(th.fs_xl * 1.4)
        h += ctx.px(th.fs_md * 1.5) * len(self._lines) + (ctx.px(8) if self._lines else 0)
        ch = 0.0
        if self.content:
            _cw, ch = self.content.measure(ctx, inner)
            h += ch + ctx.px(14)
        _bw, bh = self.buttons.measure(ctx, inner)
        h += bh + ctx.px(18) + pad
        x = rx + (rw - w) / 2
        y = ry + (rh - h) / 2 + ctx.px(20)
        self.rect = (x, y, w, h)
        self.buttons.arrange(ctx, x + pad, y + pad, inner, bh)
        if self.content:
            self.content.arrange(ctx, x + pad, y + pad + bh + ctx.px(18), inner, ch)

    def hit(self, x, y):
        r = super().hit(x, y)
        return r if r is not None else self  # modal: swallow clicks

    def paint(self, ctx, p):
        th = ctx.theme
        t = self.appear(12)
        rx, ry, rw, rh = self._region
        p.rect(rx, ry, rw, rh, fill=alpha(th.overlay, th.overlay[3] * t))
        x, y, w, h = self.rect
        s = 0.92 + 0.08 * ease_out_back(t, 1.6)
        cx, cy = x + w / 2, y + h / 2
        sw, sh = w * s, h * s
        r = ctx.px(18)
        c = {"danger": th.danger, "success": th.success, "info": th.info}.get(self.kind, th.accent)
        p.shadow(cx - sw / 2, cy - sh / 2, sw, sh, r, (0, 0, 0, 0.6 * t), ctx.px(30), dy=-ctx.px(10))
        p.rect(cx - sw / 2, cy - sh / 2, sw, sh, fill=th.surface_2, fill2=th.surface_1, radius=r,
               border=th.border_strong, border_w=ctx.px(1))
        p.rect(cx - sw * 0.22, cy + sh / 2 - ctx.px(1.5), sw * 0.44, ctx.px(1.5), fill=alpha(c, 0.0),
               fill2=alpha(c, 0.7 * t), angle=math.pi / 2, radius=ctx.px(1),
               flat=alpha(c, 0.45 * t))
        p.rect(cx, cy + sh / 2 - ctx.px(1.5), sw * 0.22, ctx.px(1.5), fill=alpha(c, 0.7 * t),
               fill2=alpha(c, 0.0), angle=math.pi / 2, radius=ctx.px(1), flat=alpha(c, 0.45 * t))
        if t < 0.98:
            return
        pad = ctx.px(20)
        top = y + h - pad
        isz = ctx.px(38)
        p.rect(x + pad, top - isz, isz, isz, fill=alpha(c, 0.14), radius=ctx.px(11), border=alpha(c, 0.3),
               border_w=ctx.px(1))
        p.icon(self.icon, x + pad + ctx.px(9), top - isz + ctx.px(9), ctx.px(20), c, 1.7)
        top -= isz + ctx.px(6)
        lh = ctx.px(th.fs_xl * 1.4)
        p.text(self.title, x + pad, top - lh / 2, th.fs_xl, th.text, "semibold", valign="center",
               max_w=w - pad * 2)
        top -= lh + ctx.px(4)
        lh = ctx.px(th.fs_md * 1.5)
        for line, _i in self._lines:
            p.text(line.rstrip(), x + pad, top - lh / 2, th.fs_md, th.text_dim, valign="center")
            top -= lh
        if self.content:
            self.content.paint(ctx, p)
        self.buttons.paint(ctx, p)
