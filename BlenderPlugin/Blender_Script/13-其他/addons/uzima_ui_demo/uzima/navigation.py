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

"""Layout and navigation: accordion, side navigation rail, breadcrumbs, pagination, split pane,
scaffold (pinned header/footer) and a drag-to-reorder list."""

import math
import time

from .core import Bind, Widget, call
from .layout import Card, Column, Container, Row, ScrollView
from .theme import alpha, mix


def _val(v):
    return v() if callable(v) else v


# ---------------------------------------------------------------------------
# Accordion
# ---------------------------------------------------------------------------

class _AccCard(Card):
    def on_click(self, ctx, ev):
        if self.collapsible:
            self.parent.toggle(self)


class Accordion(Column):
    """Collapsible sections where (by default) only one is open at a time.
    items: [(title, content, icon)]; multiple=True lets several stay open."""

    def __init__(self, items, open=0, multiple=False, gap=8, **kw):
        cards = []
        for i, it in enumerate(items):
            title, content = it[0], it[1]
            icon = it[2] if len(it) > 2 else None
            c = _AccCard(content, title=title, icon=icon, collapsible=True, open=(i == open))
            cards.append(c)
        self.multiple = multiple
        super().__init__(*cards, gap=gap, **kw)

    def toggle(self, card):
        want = not card.open
        if not self.multiple:
            for c in self.items:
                c.open = False
        card.open = want
        self.redraw()

    def get_state(self):
        return [i for i, c in enumerate(self.items) if c.open]

    def set_state(self, st):
        for i, c in enumerate(self.items):
            c.open = i in st
            c.set_anim("open", 1.0 if c.open else 0.0)


# ---------------------------------------------------------------------------
# Side navigation
# ---------------------------------------------------------------------------

class SideNav(Container):
    """Vertical icon rail on the left with the active page beside it.
    tabs: [ui.Tab(label, content, icon)]. Labels show as tooltips."""

    def __init__(self, tabs, index=0, on_change=None, rail=40, gap=10, **kw):
        super().__init__(**kw)
        self.tabs = tabs
        self.index = index
        self.on_change = on_change
        self.rail = rail
        self.gap_dp = gap
        self._hov = -1
        for t in tabs:
            if t.content is not None:
                t.content.parent = self

    def get_state(self):
        return self.index

    def set_state(self, st):
        if 0 <= int(st) < len(self.tabs):
            self.index = int(st)

    def children(self):
        page = self.tabs[self.index].content
        return [page] if page is not None else []

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        rail = ctx.px(self.rail)
        page = self.tabs[self.index].content
        ph = 0.0
        if page is not None:
            _pw, ph = page.measure(ctx, w - rail - ctx.px(self.gap_dp))
        return w, max(ph, ctx.px(44) * len(self.tabs) + ctx.px(8))

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        rail = ctx.px(self.rail)
        page = self.tabs[self.index].content
        if page is not None:
            pw = w - rail - ctx.px(self.gap_dp)
            _w, ph = page.measure(ctx, pw)
            page.arrange(ctx, x + rail + ctx.px(self.gap_dp), y + h - ph, pw, ph)

    def _rail_index(self, ctx, ev):
        x, y, w, h = self.rect
        if ev.x > x + ctx.px(self.rail):
            return -1
        i = int((y + h - ctx.px(4) - ev.y) // ctx.px(44))
        return i if 0 <= i < len(self.tabs) else -1

    def hit(self, x, y):
        r = super().hit(x, y)
        if r is None and self.contains(x, y):
            return self
        return r

    def on_hover(self, ctx, ev):
        i = self._rail_index(ctx, ev)
        if i != self._hov:
            self._hov = i
            self.tooltip = self.tabs[i].label if i >= 0 else None
            app = ctx.surface.app
            from .overlays import Tooltip
            for o in list(ctx.surface.overlays):
                if isinstance(o, Tooltip):
                    ctx.surface.remove_overlay(o)
            if i >= 0:
                app._tooltip = (self, time.perf_counter(), ctx.surface, ctx.surface.area_ptr)
                app.ensure_ticker()
            self.redraw()

    def on_leave(self, ctx):
        self._hov = -1
        self.redraw()

    def on_press(self, ctx, ev):
        return self._rail_index(ctx, ev) >= 0

    def on_click(self, ctx, ev):
        i = self._rail_index(ctx, ev)
        if i >= 0 and i != self.index:
            self.select(i)

    def select(self, i):
        self.index = i
        page = self.tabs[i].content
        if page is not None:
            page.set_anim("enter", 0.0)
        call(self.on_change, i, self.tabs[i])
        self.redraw()

    def on_nav(self, ctx, d):
        self.select(max(0, min(len(self.tabs) - 1, self.index - (1 if d > 0 else -1))))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        rail = ctx.px(self.rail)
        top = y + h - ctx.px(4)
        ih = ctx.px(44)
        p.rect(x, top - ih * len(self.tabs) - ctx.px(4), rail, ih * len(self.tabs) + ctx.px(8), fill=th.surface_1,
               radius=ctx.px(12), border=th.border, border_w=ctx.px(1))
        ay = self.anim("ay", top - ih * (self.index + 1), speed=20)
        p.rect(x + ctx.px(5), ay + ctx.px(5), rail - ctx.px(10), ih - ctx.px(10), fill=th.selected, radius=ctx.px(9),
               border=alpha((1, 1, 1, 1), 0.05), border_w=ctx.px(1))
        p.rect(x + ctx.px(1), ay + ih * 0.3, ctx.px(2.5), ih * 0.4, fill=th.accent, radius=ctx.px(1.2))
        for i, t in enumerate(self.tabs):
            iy = top - ih * (i + 1)
            col = th.accent if i == self.index else (th.text if i == self._hov else th.text_muted)
            isz = ctx.px(17)
            p.icon(t.icon or "dot", x + rail / 2 - isz / 2, iy + ih / 2 - isz / 2, isz, col, 1.6)
        page = self.tabs[self.index].content
        if page is not None:
            t = page.anim("enter", 1.0, speed=14)
            if t < 0.999:
                px_, py_, pw, ph = page.rect
                page.arrange(ctx, px_ + (1 - t) * ctx.px(12), py_, pw, ph)
            page.paint(ctx, p)


# ---------------------------------------------------------------------------
# Breadcrumbs
# ---------------------------------------------------------------------------

class Breadcrumbs(Widget):
    """Library › Props › Chairs. path: list or function; on_click(index, label, widget).
    Collapses the middle into … when space is short."""

    def __init__(self, path, on_click=None, icon="home", **kw):
        super().__init__(**kw)
        self.path = path
        self.on_click_cb = on_click
        self.icon = icon
        self._hits = []
        self._hov = -1

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(24)

    def _layout(self, ctx):
        th = ctx.theme
        x, y, w, h = self.rect
        parts = list(_val(self.path) or [])
        idx = list(range(len(parts)))
        sep = ctx.px(18)

        def width(ix):
            return sum(ctx.text_w("…" if i is None else parts[i], th.fs_sm,
                                  "semibold" if i == len(parts) - 1 else "medium") for i in ix) + sep * (len(ix) - 1) + \
                (ctx.px(20) if self.icon else 0)
        while len(idx) > 2 and width(idx) > w:
            mid = [i for i in idx if i is not None]
            if len(mid) <= 2:
                break
            drop = mid[1]
            idx = [i for i in idx if i != drop and i is not None]
            idx.insert(1, None)
            # merge duplicate ellipses
            out = []
            for i in idx:
                if i is None and out and out[-1] is None:
                    continue
                out.append(i)
            idx = out
        return parts, idx

    def on_hover(self, ctx, ev):
        i = -1
        for k, (hx, hw, pi) in enumerate(self._hits):
            if hx <= ev.x <= hx + hw:
                i = pi
        if i != self._hov:
            self._hov = i
            self.redraw()

    def on_leave(self, ctx):
        self._hov = -1
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        parts = list(_val(self.path) or [])
        for hx, hw, pi in self._hits:
            if hx <= ev.x <= hx + hw and pi is not None:
                call(self.on_click_cb, pi, parts[pi], self)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        parts, idx = self._layout(ctx)
        cy = y + h / 2
        cx = x
        self._hits = []
        if self.icon:
            hot = self._hov == 0
            p.icon(self.icon, cx, cy - ctx.px(7), ctx.px(14), th.accent if hot else th.text_muted, 1.6)
            self._hits.append((cx, ctx.px(16), 0 if parts else None))
            cx += ctx.px(20)
        for k, i in enumerate(idx):
            if k:
                p.icon("chevron_right", cx + ctx.px(3), cy - ctx.px(6), ctx.px(12), th.text_disabled, 1.7)
                cx += ctx.px(18)
            if i is None:
                cx += p.text("…", cx, cy, th.fs_sm, th.text_muted, valign="center")
                continue
            last = i == len(parts) - 1
            hot = i == self._hov and not last
            tw = p.text(parts[i], cx, cy, th.fs_sm, th.text if last else (th.accent if hot else th.text_dim),
                        "semibold" if last else "medium", valign="center", max_w=x + w - cx)
            if hot:
                p.rect(cx, cy - ctx.px(9), tw, ctx.px(1), fill=alpha(th.accent, 0.6))
            self._hits.append((cx, tw, None if last else i))
            cx += tw


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class Pagination(Widget):
    """‹ 1 … 4 5 6 … 20 ›. pages: int or function; on_change(page, widget). Pages are 1-based."""

    def __init__(self, pages, page=1, on_change=None, window=1, **kw):
        super().__init__(**kw)
        self.pages = pages
        self.page = page
        self.on_change = on_change
        self.window = window
        self._hits = []
        self._hov = None

    def get_state(self):
        return self.page

    def set_state(self, s):
        self.page = int(s)

    def _n(self):
        return max(1, int(_val(self.pages)))

    def _items(self):
        n, c, k = self._n(), self.page, self.window
        show = {1, n} | set(range(max(1, c - k), min(n, c + k) + 1))
        out, last = [], 0
        for i in sorted(show):
            if i - last > 1:
                out.append(None)
            out.append(i)
            last = i
        return out

    def go(self, page):
        page = max(1, min(self._n(), page))
        if page != self.page:
            self.page = page
            call(self.on_change, page, self)
            self.redraw()

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(28)

    def _slots(self, ctx):
        x, y, w, h = self.rect
        items = ["prev"] + self._items() + ["next"]
        s = ctx.px(28)
        g = ctx.px(4)
        total = len(items) * s + (len(items) - 1) * g
        cx = x + (w - total) / 2
        out = []
        for it in items:
            out.append((cx, s, it))
            cx += s + g
        return out

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        self._hits = [(cx, s, it if it is not None else None) for cx, s, it in self._slots(ctx)]

    def on_hover(self, ctx, ev):
        h = None
        for hx, hw, v in self._hits:
            if hx <= ev.x <= hx + hw:
                h = v
        if h != self._hov:
            self._hov = h
            self.redraw()

    def on_leave(self, ctx):
        self._hov = None
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        for hx, hw, v in self._hits:
            if hx <= ev.x <= hx + hw and v is not None:
                self.go(self.page - 1 if v == "prev" else (self.page + 1 if v == "next" else v))

    def on_nav(self, ctx, d):
        self.go(self.page + (1 if d > 0 else -1))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        items = ["prev"] + self._items() + ["next"]
        s = ctx.px(28)
        g = ctx.px(4)
        total = len(items) * s + (len(items) - 1) * g
        cx = x + (w - total) / 2
        self._hits = []
        for it in items:
            hot = self._hov == it
            if it in ("prev", "next"):
                ok = (self.page > 1) if it == "prev" else (self.page < self._n())
                if hot and ok:
                    p.rect(cx, y, s, s, fill=th.surface_4, radius=ctx.px(8))
                p.icon("chevron_left" if it == "prev" else "chevron_right", cx + s / 2 - ctx.px(7), y + s / 2 - ctx.px(7),
                       ctx.px(14), th.text if ok else th.text_disabled, 1.8)
                self._hits.append((cx, s, it if ok else None))
            elif it is None:
                p.text("…", cx + s / 2, y + s / 2, th.fs_sm, th.text_muted, align="center", valign="center")
            else:
                on = it == self.page
                if on:
                    p.rect(cx, y, s, s, fill=th.accent, radius=ctx.px(8))
                elif hot:
                    p.rect(cx, y, s, s, fill=th.surface_4, radius=ctx.px(8))
                p.text(str(it), cx + s / 2, y + s / 2, th.fs_sm, th.accent_text if on else th.text_dim,
                       "semibold" if on else "medium", align="center", valign="center")
                self._hits.append((cx, s, it))
            cx += s + g


# ---------------------------------------------------------------------------
# Split pane
# ---------------------------------------------------------------------------

class SplitPane(Widget):
    """Two areas with a draggable divider. direction="horizontal" (side by side) or "vertical"
    (stacked; give height=). ratio is the size of the first pane (0..1)."""

    def __init__(self, first, second, ratio=0.5, direction="horizontal", min_ratio=0.15, height=None, **kw):
        super().__init__(height=height, **kw)
        self.first, self.second = first, second
        first.parent = second.parent = self
        self.ratio = ratio
        self.direction = direction
        self.min_ratio = min_ratio
        self._drag = False
        self._hot = False

    def get_state(self):
        return round(self.ratio, 3)

    def set_state(self, s):
        self.ratio = float(s)

    def children(self):
        return (self.first, self.second)

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        if self.direction == "vertical":
            return w, ctx.px(self.height or 260)
        d = ctx.px(10)
        w1 = (w - d) * self.ratio
        _a, h1 = self.first.measure(ctx, w1)
        _b, h2 = self.second.measure(ctx, w - d - w1)
        return w, ctx.px(self.height) if self.height else max(h1, h2)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        d = ctx.px(10)
        if self.direction == "vertical":
            h1 = (h - d) * self.ratio
            self.first.measure(ctx, w)
            self.second.measure(ctx, w)
            self.first.arrange(ctx, x, y + h - h1, w, h1)
            self.second.arrange(ctx, x, y, w, h - d - h1)
        else:
            w1 = (w - d) * self.ratio
            _a, h1 = self.first.measure(ctx, w1)
            _b, h2 = self.second.measure(ctx, w - d - w1)
            self.first.arrange(ctx, x, y + h - h1, w1, h1)
            self.second.arrange(ctx, x + w1 + d, y + h - h2, w - d - w1, h2)

    def _divider(self, ctx):
        x, y, w, h = self.rect
        d = ctx.px(10)
        if self.direction == "vertical":
            h1 = (h - d) * self.ratio
            return (x, y + h - h1 - d, w, d)
        w1 = (w - d) * self.ratio
        return (x + w1, y, d, h)

    def hit(self, x, y):
        dx, dy, dw, dh = self._divider_px if hasattr(self, "_divider_px") else (0, 0, 0, 0)
        if dx <= x <= dx + dw and dy <= y <= dy + dh:
            return self
        return super().hit(x, y)

    def interactive(self):
        return False

    def on_enter(self, ctx):
        self._hot = True
        self.redraw()

    def on_leave(self, ctx):
        self._hot = False
        self.redraw()

    def on_press(self, ctx, ev):
        self._drag = True
        return True

    def on_drag(self, ctx, ev):
        x, y, w, h = self.rect
        d = ctx.px(10)
        if self.direction == "vertical":
            r = (y + h - ev.y - d / 2) / max(1.0, h - d)
        else:
            r = (ev.x - x - d / 2) / max(1.0, w - d)
        self.ratio = max(self.min_ratio, min(1 - self.min_ratio, r))
        self.redraw()

    def on_release(self, ctx, ev, inside):
        self._drag = False

    def paint(self, ctx, p):
        th = ctx.theme
        self.first.paint(ctx, p)
        self.second.paint(ctx, p)
        dx, dy, dw, dh = self._divider(ctx)
        self._divider_px = (dx, dy, dw, dh)
        active = self._drag or self._hot
        c = th.accent if active else th.border_strong
        if self.direction == "vertical":
            p.rect(dx + dw * 0.4, dy + dh / 2 - ctx.px(1.5), dw * 0.2, ctx.px(3), fill=c, radius=ctx.px(1.5))
        else:
            p.rect(dx + dw / 2 - ctx.px(1.5), dy + dh * 0.4, ctx.px(3), dh * 0.2, fill=c, radius=ctx.px(1.5))


# ---------------------------------------------------------------------------
# Scaffold (pinned header / footer)
# ---------------------------------------------------------------------------

class Scaffold(Widget):
    """Fills the whole panel: header and footer stay put, the body scrolls between them.

        app.sidebar("My Tool", build=lambda s: ui.Scaffold(header=..., body=..., footer=...))
    """

    fills_region = True

    def __init__(self, body, header=None, footer=None, padding=12, gap=10, **kw):
        super().__init__(**kw)
        self.header, self.footer = header, footer
        self.scroll = ScrollView(body, padding=0)
        self.body = body
        self.padding = padding
        self.gap_dp = gap
        for c in (header, footer, self.scroll):
            if c is not None:
                c.parent = self

    def children(self):
        return [c for c in (self.header, self.scroll, self.footer) if c is not None]

    def get_state(self):
        return round(self.scroll.offset, 1)

    def set_state(self, s):
        self.scroll.offset = float(s)
        self.scroll.set_anim("scroll", float(s))

    def measure(self, ctx, avail_w):
        return avail_w, ctx.region_h

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        pad = ctx.px(self.padding)
        g = ctx.px(self.gap_dp)
        iw = w - pad * 2
        top = y + h - pad
        bottom = y + pad
        if self.header is not None:
            _w, hh = self.header.measure(ctx, iw)
            self.header.arrange(ctx, x + pad, top - hh, iw, hh)
            top -= hh + g
        if self.footer is not None:
            _w, fh = self.footer.measure(ctx, iw)
            self.footer.arrange(ctx, x + pad, bottom, iw, fh)
            bottom += fh + g
        self._body_rect = (x, bottom, w, max(0.0, top - bottom))
        self.scroll.height = None
        self.scroll.arrange(ctx, x + pad, bottom, iw, max(0.0, top - bottom))

    def paint(self, ctx, p):
        th = ctx.theme
        self.scroll.fade_color = th.bg
        x, y, w, h = self.rect
        self.scroll.paint(ctx, p)
        if self.header is not None:
            self.header.paint(ctx, p)
        if self.footer is not None:
            fx, fy, fw, fh = self.footer.rect
            p.rect(x, y, w, fh + ctx.px(self.padding) + ctx.px(self.gap_dp) / 2, fill=th.bg)
            p.rect(x, fy + fh + ctx.px(self.gap_dp) / 2, w, ctx.px(1), fill=th.border)
            self.footer.paint(ctx, p)


# ---------------------------------------------------------------------------
# Reorder list
# ---------------------------------------------------------------------------

class ReorderList(Widget):
    """Rows you reorder by dragging the handle. Works with a Blender CollectionProperty or a list.

        ui.ReorderList(collection=lambda: scene.render_queue, label=lambda it: it.name,
                       sublabel=lambda it: f"{it.frames} frames",
                       toggle=(lambda it: it.enabled, lambda it, v: setattr(it, "enabled", v)),
                       active=ui.Bind("scene.render_queue_index"), on_add=..., on_remove=...)
        ui.ReorderList(items=["A", "B", "C"], on_reorder=lambda items, w: ...)
    """

    def __init__(self, items=None, collection=None, label=None, sublabel=None, icon=None, toggle=None,
                 active=None, on_reorder=None, on_add=None, on_remove=None, add_label="Add", row_height=36,
                 empty="Nothing here yet", **kw):
        super().__init__(**kw)
        self._items = list(items or [])
        self.collection = collection
        self.label = label or (lambda it: getattr(it, "name", str(it)))
        self.sublabel = sublabel
        self.icon = icon
        self.toggle = toggle
        self.active = Bind(active) if isinstance(active, str) else active
        self._active_local = 0
        self.on_reorder = on_reorder
        self.on_add = on_add
        self.on_remove = on_remove
        self.add_label = add_label
        self.row_height = row_height
        self.empty = empty
        self._drag = None   # (index, grab_dy, current_y)
        self._hov = -1
        self._hot = None

    def items(self):
        c = _val(self.collection) if self.collection is not None else None
        return list(c) if c is not None else self._items

    def active_index(self):
        if self.active is not None:
            return int(self.active.get(0) or 0)
        return self._active_local

    def set_active(self, i):
        if self.active is not None:
            self.active.set(i)
        else:
            self._active_local = i

    def move(self, a, b):
        if a == b:
            return
        c = _val(self.collection) if self.collection is not None else None
        if c is not None:
            c.move(a, b)
            try:
                import bpy
                bpy.ops.ed.undo_push(message="Reorder")
            except Exception:
                pass
        else:
            it = self._items.pop(a)
            self._items.insert(b, it)
        self.set_active(b)
        call(self.on_reorder, self.items(), self)
        self.redraw()

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        n = max(1, len(self.items()))
        add = ctx.px(34) if self.on_add else 0.0
        return self.resolve_width(ctx, avail_w), ctx.px(self.row_height) * n + ctx.px(8) + add

    def _list_top(self, ctx):
        x, y, w, h = self.rect
        return y + h - ctx.px(4)

    def _row_at(self, ctx, ey):
        i = int((self._list_top(ctx) - ey) // ctx.px(self.row_height))
        return i if 0 <= i < len(self.items()) else -1

    def _zone(self, ctx, ev):
        x, y, w, h = self.rect
        if self.on_add and ev.y < y + ctx.px(30):
            return ("add", None)
        i = self._row_at(ctx, ev.y)
        if i < 0:
            return None
        if ev.x < x + ctx.px(30):
            return ("handle", i)
        if self.toggle and ev.x < x + ctx.px(56):
            return ("toggle", i)
        if self.on_remove and ev.x > x + w - ctx.px(32):
            return ("remove", i)
        return ("row", i)

    def on_hover(self, ctx, ev):
        z = self._zone(ctx, ev)
        i = z[1] if z and z[1] is not None else -1
        if z != self._hot or i != self._hov:
            self._hot, self._hov = z, i
            self.redraw()

    def on_leave(self, ctx):
        self._hot, self._hov = None, -1
        self.redraw()

    def on_press(self, ctx, ev):
        z = self._zone(ctx, ev)
        if z and z[0] == "handle":
            i = z[1]
            row_top = self._list_top(ctx) - i * ctx.px(self.row_height)
            self._drag = (i, row_top - ev.y, ev.y)
        return True

    def on_drag(self, ctx, ev):
        if self._drag is not None:
            self._drag = (self._drag[0], self._drag[1], ev.y)
            self.redraw()

    def _drop_index(self, ctx):
        i, grab, cy = self._drag
        top = cy + grab
        rh = ctx.px(self.row_height)
        j = int(round((self._list_top(ctx) - top) / rh))
        return max(0, min(len(self.items()) - 1, j))

    def on_release(self, ctx, ev, inside):
        if self._drag is not None:
            a = self._drag[0]
            b = self._drop_index(ctx)
            self._drag = None
            self.move(a, b)

    def on_click(self, ctx, ev):
        z = self._zone(ctx, ev)
        if not z or self._drag is not None:
            return
        kind, i = z
        items = self.items()
        if kind == "add":
            call(self.on_add, self)
        elif kind == "toggle":
            get, setter = self.toggle
            setter(items[i], not get(items[i]))
        elif kind == "remove":
            call(self.on_remove, i, self)
            self.set_active(max(0, min(self.active_index(), len(self.items()) - 1)))
        elif kind == "row":
            self.set_active(i)
        self.redraw()

    def on_nav(self, ctx, d):
        n = len(self.items())
        if n:
            self.set_active(max(0, min(n - 1, self.active_index() - (1 if d > 0 else -1))))

    def _paint_row(self, ctx, p, it, i, ry, w, x, lifted=False):
        th = ctx.theme
        rh = ctx.px(self.row_height)
        act = i == self.active_index()
        hov = i == self._hov
        if lifted:
            p.shadow(x, ry, w, rh - ctx.px(2), ctx.px(8), (0, 0, 0, 0.55), ctx.px(12), dy=-ctx.px(4))
            p.rect(x, ry + ctx.px(1), w, rh - ctx.px(2), fill=th.surface_3, radius=ctx.px(8),
                   border=alpha(th.accent, 0.6), border_w=ctx.px(1))
        elif act:
            p.rect(x, ry + ctx.px(1), w, rh - ctx.px(2), fill=th.accent_soft, radius=ctx.px(8))
        elif hov:
            p.rect(x, ry + ctx.px(1), w, rh - ctx.px(2), fill=alpha(th.surface_3, 0.7), radius=ctx.px(8))
        cy = ry + rh / 2
        hot_handle = self._hot == ("handle", i)
        p.icon("drag", x + ctx.px(8), cy - ctx.px(7), ctx.px(14), th.text if (hot_handle or lifted) else th.text_muted,
               1.6)
        cx = x + ctx.px(30)
        if self.toggle:
            on = bool(self.toggle[0](it))
            s = ctx.px(15)
            p.rect(cx, cy - s / 2, s, s, fill=th.accent if on else th.surface_0, radius=ctx.px(4),
                   border=th.accent if on else th.border_strong, border_w=ctx.px(1.2))
            if on:
                p.icon("check", cx + ctx.px(1.5), cy - s / 2 + ctx.px(1.5), s - ctx.px(3), th.accent_text, 2.2)
            cx += ctx.px(26)
        if self.icon:
            ic = self.icon(it) if callable(self.icon) else self.icon
            p.icon(ic, cx, cy - ctx.px(7), ctx.px(14), th.accent if act else th.text_dim, 1.5)
            cx += ctx.px(20)
        right = x + w - (ctx.px(34) if self.on_remove else ctx.px(8))
        lab = str(self.label(it))
        sub = str(self.sublabel(it)) if self.sublabel else None
        if sub:
            p.text(lab, cx, cy + ctx.px(6), th.fs_md, th.text, "medium", valign="center", max_w=right - cx)
            p.text(sub, cx, cy - ctx.px(8), th.fs_xs, th.text_muted, valign="center", max_w=right - cx)
        else:
            p.text(lab, cx, cy, th.fs_md, th.text, "medium" if act else "regular", valign="center", max_w=right - cx)
        if self.on_remove and (hov or lifted):
            hot = self._hot == ("remove", i)
            p.icon("trash", x + w - ctx.px(24), cy - ctx.px(7), ctx.px(14), th.danger if hot else th.text_muted, 1.5)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        items = self.items()
        rh = ctx.px(self.row_height)
        add_h = ctx.px(34) if self.on_add else 0.0
        p.rect(x, y + add_h, w, h - add_h, fill=th.surface_0, radius=ctx.px(th.r_md), border=th.border,
               border_w=ctx.px(1))
        top = self._list_top(ctx)
        if not items:
            p.text(self.empty, x + w / 2, top - rh / 2, th.fs_sm, th.text_muted, align="center", valign="center")
        drag_i = self._drag[0] if self._drag is not None else -1
        drop = self._drop_index(ctx) if self._drag is not None else -1
        slot = 0
        for i, it in enumerate(items):
            if i == drag_i:
                continue
            if slot == drop:
                slot += 1
            target = top - rh * (slot + 1)
            ry = self.anim("r%d" % id(it) if not hasattr(it, "as_pointer") else "r%d" % it.as_pointer(), target,
                           speed=22)
            self._paint_row(ctx, p, it, i, ry, w - ctx.px(8), x + ctx.px(4))
            slot += 1
        if self._drag is not None and 0 <= drag_i < len(items):
            i, grab, cy = self._drag
            ry = cy + grab - rh
            self._paint_row(ctx, p, items[i], i, ry, w - ctx.px(8), x + ctx.px(4), lifted=True)
        if self.on_add:
            hot = self._hot == ("add", None)
            p.rect(x, y, w, ctx.px(28), fill=th.surface_4 if hot else th.surface_3, radius=ctx.px(8),
                   border=th.border_strong, border_w=ctx.px(1))
            tw = ctx.text_w(self.add_label, th.fs_sm, "medium")
            p.icon("plus", x + w / 2 - tw / 2 - ctx.px(10), y + ctx.px(14) - ctx.px(6), ctx.px(12), th.text, 1.8)
            p.text(self.add_label, x + w / 2 + ctx.px(8), y + ctx.px(14), th.fs_sm, th.text, "medium", align="center",
                   valign="center")
