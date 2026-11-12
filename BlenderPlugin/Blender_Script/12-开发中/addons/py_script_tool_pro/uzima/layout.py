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

"""Layout containers: Column, Row, Flow, Grid, Card, ScrollView, TabView, Spacer, Separator."""

import math

from .core import Widget, call
from .theme import alpha, mix


def _pad(p):
    if isinstance(p, (tuple, list)):
        if len(p) == 2:
            return p[0], p[1], p[0], p[1]
        return tuple(p)
    return p, p, p, p  # left, top, right, bottom


class Container(Widget):
    def __init__(self, *children, gap=None, padding=0, **kw):
        super().__init__(**kw)
        if len(children) == 1 and isinstance(children[0], (list, tuple)):
            children = children[0]
        self.items = self._adopt(children)
        self.gap = gap
        self.padding = padding
        self._sizes = []

    def children(self):
        return self.items

    def add(self, *ws):
        self.items.extend(self._adopt(ws))
        return ws[0] if len(ws) == 1 else ws

    def clear(self):
        self.items = []

    def set_children(self, ws):
        self.items = self._adopt(ws)

    def _visible(self):
        return [c for c in self.items if c.visible]

    def _gap(self, ctx):
        return ctx.px(ctx.theme.gap if self.gap is None else self.gap)


class Column(Container):
    """Stack children top to bottom."""

    def measure(self, ctx, avail_w):
        pl, pt, pr, pb = (ctx.px(v) for v in _pad(self.padding))
        w = self.resolve_width(ctx, avail_w)
        inner = max(0.0, w - pl - pr)
        g = self._gap(ctx)
        h = 0.0
        self._sizes = []
        vis = self._visible()
        for i, c in enumerate(vis):
            cw, ch = c.measure(ctx, inner)
            self._sizes.append((c, cw, ch))
            h += ch + (g if i else 0.0)
        h += pt + pb
        if self.height is not None:
            h = ctx.px(self.height)
        return w, h

    def natural_width(self, ctx):
        pl, _pt, pr, _pb = (ctx.px(v) for v in _pad(self.padding))
        vis = self._visible()
        return max([c.natural_width(ctx) for c in vis] or [0.0]) + pl + pr

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        pl, pt, pr, pb = (ctx.px(v) for v in _pad(self.padding))
        inner = max(0.0, w - pl - pr)
        if not self._sizes:
            self.measure(ctx, w)
        g = self._gap(ctx)
        top = y + h - pt
        for c, cw, ch in self._sizes:
            if c.width is None or c.align == "stretch":
                cw = inner if c.width is None else cw
            cx = x + pl
            if c.align == "center":
                cx += (inner - cw) / 2
            elif c.align == "end":
                cx += inner - cw
            c.arrange(ctx, cx, top - ch, cw, ch)
            top -= ch + g

    def paint(self, ctx, p):
        for c in self._visible():
            if p.clip_visible(*c.rect):
                c.paint(ctx, p)


class Row(Container):
    """Place children left to right. width=None children share leftover space by `flex`."""

    def __init__(self, *children, valign="center", justify="start", **kw):
        super().__init__(*children, **kw)
        self.valign = valign
        self.justify = justify

    def natural_width(self, ctx):
        pl, _pt, pr, _pb = (ctx.px(v) for v in _pad(self.padding))
        vis = self._visible()
        g = self._gap(ctx)
        tot = 0.0
        for c in vis:
            if isinstance(c.width, (int, float)):
                tot += ctx.px(c.width)
            else:
                tot += c.natural_width(ctx)
        return tot + g * max(0, len(vis) - 1) + pl + pr

    def measure(self, ctx, avail_w):
        pl, pt, pr, pb = (ctx.px(v) for v in _pad(self.padding))
        w = self.resolve_width(ctx, avail_w)
        inner = max(0.0, w - pl - pr)
        vis = self._visible()
        g = self._gap(ctx)
        fixed = 0.0
        flex_total = 0.0
        widths = {}
        for c in vis:
            if isinstance(c.width, (int, float)):
                widths[c] = ctx.px(c.width)
                fixed += widths[c]
            elif c.width == "auto":
                widths[c] = c.natural_width(ctx)
                fixed += widths[c]
            else:
                flex_total += max(c.flex, 0.0001)
        remaining = max(0.0, inner - fixed - g * max(0, len(vis) - 1))
        if fixed + g * max(0, len(vis) - 1) > inner and fixed > 0:
            # shrink auto children proportionally when space is tight
            room = max(0.0, inner - g * max(0, len(vis) - 1))
            k = room / fixed
            for c in list(widths):
                if c.width == "auto":
                    widths[c] *= k
            remaining = 0.0
        self._sizes = []
        hmax = 0.0
        for c in vis:
            cw = widths.get(c)
            if cw is None:
                cw = remaining * max(c.flex, 0.0001) / flex_total if flex_total else 0.0
            mw, mh = c.measure(ctx, cw)
            self._sizes.append((c, cw, mh))
            hmax = max(hmax, mh)
        h = hmax + pt + pb
        if self.height is not None:
            h = ctx.px(self.height)
        return w, h

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        pl, pt, pr, pb = (ctx.px(v) for v in _pad(self.padding))
        if not self._sizes:
            self.measure(ctx, w)
        g = self._gap(ctx)
        inner_h = h - pt - pb
        used = sum(cw for _c, cw, _ch in self._sizes) + g * max(0, len(self._sizes) - 1)
        cx = x + pl
        inner_w = w - pl - pr
        if self.justify == "center":
            cx += max(0.0, (inner_w - used) / 2)
        elif self.justify == "end":
            cx += max(0.0, inner_w - used)
        elif self.justify == "between" and len(self._sizes) > 1:
            g = g + max(0.0, inner_w - used) / (len(self._sizes) - 1)
        for c, cw, ch in self._sizes:
            if c.align == "stretch" and self.valign == "stretch":
                ch = inner_h
            if self.valign in ("center", "stretch"):
                cy = y + pb + (inner_h - ch) / 2
            elif self.valign == "top":
                cy = y + pb + inner_h - ch
            else:
                cy = y + pb
            c.arrange(ctx, cx, cy, cw, ch)
            cx += cw + g

    def paint(self, ctx, p):
        for c in self._visible():
            if p.clip_visible(*c.rect):
                c.paint(ctx, p)


class Flow(Container):
    """Children keep their natural width and wrap onto new lines (great for chips and tags)."""

    def __init__(self, *children, row_gap=None, **kw):
        super().__init__(*children, **kw)
        self.row_gap = row_gap

    def measure(self, ctx, avail_w):
        pl, pt, pr, pb = (ctx.px(v) for v in _pad(self.padding))
        w = self.resolve_width(ctx, avail_w)
        inner = max(1.0, w - pl - pr)
        g = self._gap(ctx)
        rg = ctx.px(self.row_gap) if self.row_gap is not None else g
        lines = [[]]
        lw = 0.0
        for c in self._visible():
            if isinstance(c.width, (int, float)):
                cw = ctx.px(c.width)
            else:
                cw = c.natural_width(ctx)
            cw = min(cw, inner)
            _mw, ch = c.measure(ctx, cw)
            need = cw if not lines[-1] else lw + g + cw
            if lines[-1] and need > inner:
                lines.append([])
                lw = 0.0
            lw = cw if not lines[-1] else lw + g + cw
            lines[-1].append((c, cw, ch))
        self._lines = lines
        h = sum(max([ch for _c, _w, ch in ln] or [0.0]) for ln in lines)
        h += rg * max(0, len(lines) - 1) + pt + pb
        return w, h

    def natural_width(self, ctx):
        g = self._gap(ctx)
        vis = self._visible()
        return sum(c.natural_width(ctx) for c in vis) + g * max(0, len(vis) - 1)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        pl, pt, pr, pb = (ctx.px(v) for v in _pad(self.padding))
        g = self._gap(ctx)
        rg = ctx.px(self.row_gap) if self.row_gap is not None else g
        top = y + h - pt
        for ln in getattr(self, "_lines", []):
            lh = max([ch for _c, _w, ch in ln] or [0.0])
            cx = x + pl
            for c, cw, ch in ln:
                c.arrange(ctx, cx, top - lh + (lh - ch) / 2, cw, ch)
                cx += cw + g
            top -= lh + rg

    def paint(self, ctx, p):
        for c in self._visible():
            if p.clip_visible(*c.rect):
                c.paint(ctx, p)


class Grid(Container):
    """Equal-width cells. Give `cols`, or `min_cell` (dp) to pick columns from the width."""

    def __init__(self, *children, cols=2, min_cell=None, **kw):
        super().__init__(*children, **kw)
        self.cols = cols
        self.min_cell = min_cell

    def _ncols(self, ctx, inner):
        if self.min_cell:
            g = self._gap(ctx)
            return max(1, int((inner + g) // (ctx.px(self.min_cell) + g)))
        return max(1, self.cols)

    def measure(self, ctx, avail_w):
        pl, pt, pr, pb = (ctx.px(v) for v in _pad(self.padding))
        w = self.resolve_width(ctx, avail_w)
        inner = max(0.0, w - pl - pr)
        g = self._gap(ctx)
        n = self._ncols(ctx, inner)
        cw = (inner - g * (n - 1)) / n
        vis = self._visible()
        self._rows = []
        h = 0.0
        for i in range(0, len(vis), n):
            row = []
            rh = 0.0
            for c in vis[i:i + n]:
                _w, ch = c.measure(ctx, cw)
                row.append((c, ch))
                rh = max(rh, ch)
            self._rows.append((row, rh))
            h += rh
        h += g * max(0, len(self._rows) - 1) + pt + pb
        self._cw = cw
        return w, h

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        pl, pt, pr, pb = (ctx.px(v) for v in _pad(self.padding))
        g = self._gap(ctx)
        top = y + h - pt
        for row, rh in getattr(self, "_rows", []):
            cx = x + pl
            for c, ch in row:
                c.arrange(ctx, cx, top - rh, self._cw, rh)
                cx += self._cw + g
            top -= rh + g

    def paint(self, ctx, p):
        for c in self._visible():
            if p.clip_visible(*c.rect):
                c.paint(ctx, p)


class Spacer(Widget):
    def __init__(self, size=8, **kw):
        super().__init__(height=size, **kw)

    def natural_width(self, ctx):
        return ctx.px(self.height)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height)


class Separator(Widget):
    """Thin divider line, optionally with a centered label."""

    def __init__(self, label=None, **kw):
        super().__init__(**kw)
        self.label = label

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(18 if self.label else 9)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        cy = y + h / 2
        if self.label:
            tw = p.measure(self.label.upper(), th.fs_xs, "semibold")[0]
            gap = ctx.px(8)
            p.rect(x, cy - 0.5, (w - tw) / 2 - gap, 1, fill=th.border)
            p.rect(x + (w + tw) / 2 + gap, cy - 0.5, (w - tw) / 2 - gap, 1, fill=th.border)
            p.text(self.label.upper(), x + w / 2, cy, th.fs_xs, th.text_muted, "semibold",
                   align="center", valign="center")
        else:
            p.rect(x, cy - 0.5, w, 1, fill=th.border)


class Card(Column):
    """Rounded surface with optional header (icon, title, subtitle, actions) and collapse."""

    def __init__(self, *children, title=None, subtitle=None, icon=None, actions=None,
                 collapsible=False, open=True, variant="default", padding=12, gap=None,
                 accent=None, **kw):
        super().__init__(*children, padding=padding, gap=gap, **kw)
        self.title = title
        self.subtitle = subtitle
        self.icon = icon
        self.actions = self._adopt(actions or [])
        self.collapsible = collapsible
        self.open = open
        self.variant = variant
        self.accent = accent
        self._header_h = 0.0
        self._content_h = 0.0
        self._hdr_hover = False

    def get_state(self):
        return bool(self.open) if self.collapsible else None

    def set_state(self, st):
        self.open = bool(st)
        self.set_anim("open", 1.0 if self.open else 0.0)

    def children(self):
        if self._open_amount() <= 0.001:
            return self.actions
        return self.items + self.actions

    def _open_amount(self):
        st = self._anims.get("open")
        return st[0] if st else (1.0 if self.open else 0.0)

    def measure(self, ctx, avail_w):
        th = ctx.theme
        w = self.resolve_width(ctx, avail_w)
        pad = ctx.px(self.padding)
        self._header_h = 0.0
        if self.title:
            self._header_h = ctx.px(34 if self.subtitle else 26) + (pad * 0.6 if self.open else 0)
        _w, ch = Column.measure(self, ctx, w)
        ch -= ctx.px(self.padding) * 2
        self._content_h = ch
        t = self.anim("open", 1.0 if self.open else 0.0, speed=16)
        if self.title:
            h = pad * 2 + ctx.px(34 if self.subtitle else 26) + (ch + pad * 0.6) * t
        else:
            h = pad * 2 + ch
        return w, h

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        pad = ctx.px(self.padding)
        head = ctx.px(34 if self.subtitle else 26) if self.title else 0.0
        # header actions on the right (left of the collapse arrow)
        ax = x + w - pad - (ctx.px(24) if self.collapsible and self.title else 0.0)
        for a in reversed(self.actions):
            aw = a.natural_width(ctx) if a.width in (None, "auto") else ctx.px(a.width)
            _mw, ah = a.measure(ctx, aw)
            ax -= aw
            a.arrange(ctx, ax, y + h - pad - head / 2 - ah / 2, aw, ah)
            ax -= ctx.px(6)
        # content hangs from below the header; it slides when collapsing
        top = y + h - pad - (head + pad * 0.6 if self.title else 0.0)
        inner = w - pad * 2
        g = self._gap(ctx)
        for c, cw, ch in self._sizes:
            cw = inner if (c.width is None or c.align == "stretch") else cw
            cx = x + pad
            if c.align == "center":
                cx += (inner - cw) / 2
            elif c.align == "end":
                cx += inner - cw
            c.arrange(ctx, cx, top - ch, cw, ch)
            top -= ch + g

    def hit(self, x, y):
        r = super().hit(x, y)
        if r is self or r is None:
            if self.collapsible and self.contains(x, y) and self._in_header(y):
                return self
        return r

    def _in_header(self, y):
        rx, ry, rw, rh = self.rect
        return y >= ry + rh - (self._hdr_px if hasattr(self, "_hdr_px") else 40)

    def interactive(self):
        return False

    def on_enter(self, ctx):
        self._hdr_hover = True
        self.redraw()

    def on_leave(self, ctx):
        self._hdr_hover = False
        self.redraw()

    def on_press(self, ctx, ev):
        return self.collapsible

    def on_click(self, ctx, ev):
        if self.collapsible:
            self.open = not self.open
            self.redraw()

    cursor = None

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        pad = ctx.px(self.padding)
        r = ctx.px(th.r_lg)
        self._hdr_px = pad + ctx.px(34 if self.subtitle else 26) + pad * 0.3
        if self.variant == "composer":
            # the prompt box from the reference: dark outer ring + soft raised surface
            ring = ctx.px(3)
            p.shadow(x, y, w, h, r, (0, 0, 0, 0.45), ctx.px(18), dy=-ctx.px(6))
            p.rect(x - ring, y - ring, w + ring * 2, h + ring * 2, fill=mix(th.bg, (0, 0, 0, 1), 0.15),
                   radius=r + ring)
            p.rect(x, y, w, h, fill=mix(th.surface_2, (1, 1, 1, 1), 0.015), fill2=th.surface_2, radius=r,
                   border=th.surface_1, border_w=ctx.px(1.5))
        elif self.variant != "ghost":
            if self.variant == "raised":
                p.shadow(x, y, w, h, r, (0, 0, 0, 0.35), ctx.px(14), dy=-ctx.px(4))
            fill = th.surface_2 if self.variant == "raised" else th.surface_1
            border = th.border_strong if self.variant == "outline" else th.border
            p.rect(x, y, w, h, fill=mix(fill, (1, 1, 1, 1), 0.012), fill2=fill, radius=r,
                   border=border, border_w=ctx.px(1))
            if self.accent:
                p.rect(x + r, y + h - ctx.px(1.2), w - 2 * r, ctx.px(1.2), fill=alpha(self.accent, 0.8),
                       radius=ctx.px(1))
        if self.title:
            head = ctx.px(34 if self.subtitle else 26)
            hy = y + h - pad - head
            tx = x + pad
            if self.icon:
                isz = ctx.px(26)
                p.rect(tx, hy + (head - isz) / 2, isz, isz, fill=th.surface_3, radius=ctx.px(7),
                       border=th.border_strong, border_w=ctx.px(1))
                p.icon(self.icon, tx + ctx.px(5), hy + (head - isz) / 2 + ctx.px(5), ctx.px(16),
                       self.accent or th.text, 1.5)
                tx += isz + ctx.px(9)
            hov = self.collapsible and self._hdr_hover
            if self.subtitle:
                p.text(self.title, tx, hy + head * 0.62, th.fs_md, th.text, "semibold", valign="center")
                p.text(self.subtitle, tx, hy + head * 0.18, th.fs_sm, th.text_muted, valign="center",
                       max_w=w - (tx - x) - pad)
            else:
                p.text(self.title, tx, hy + head / 2, th.fs_md, th.text if not hov else th.accent,
                       "semibold", valign="center")
            if self.collapsible:
                t = self._open_amount()
                cx = x + w - pad - ctx.px(16)
                p.icon("chevron_down" if t > 0.5 else "chevron_right", cx, hy + (head - ctx.px(16)) / 2,
                       ctx.px(16), th.text_dim, 1.6)
        t = self._open_amount()
        if t > 0.001:
            if t < 0.999 or self.title:
                p.push_clip(x, y + ctx.px(2), w, h - ctx.px(2))
                Column.paint(self, ctx, p)
                p.pop_clip()
            else:
                Column.paint(self, ctx, p)
        for a in self.actions:
            a.paint(ctx, p)


class ScrollView(Widget):
    """Clips its content and scrolls with the mouse wheel or the scrollbar."""

    keyboard_nav = False

    def __init__(self, child, height=None, padding=0, **kw):
        super().__init__(height=height, **kw)
        self.child = child
        child.parent = self
        self.padding = padding
        self.offset = 0.0     # target offset (px, 0 = top)
        self._content_h = 0.0
        self._drag = None
        self._bar_hover = False

    def children(self):
        return (self.child,)

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        h = ctx.px(self.height) if self.height is not None else ctx.px(200)
        return w, h

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        pad = ctx.px(self.padding)
        _cw, ch = self.child.measure(ctx, w - pad * 2)
        self._content_h = ch + pad * 2
        self.offset = max(0.0, min(self.offset, self.max_offset()))
        cur = self.anim("scroll", self.offset, speed=22, snap=0.0005)
        self._cur = cur
        self.child.arrange(ctx, x + pad, y + h - pad - ch + cur, w - pad * 2, ch)

    def max_offset(self):
        return max(0.0, self._content_h - self.rect[3])

    def scroll_to(self, offset):
        self.offset = max(0.0, min(offset, self.max_offset()))
        self.redraw()

    def interactive(self):
        return True

    def _bar(self, ctx):
        x, y, w, h = self.rect
        if self._content_h <= h + 1:
            return None
        frac = h / self._content_h
        bh = max(ctx.px(28), h * frac)
        t = getattr(self, "_cur", self.offset) / max(1.0, self.max_offset())
        by = y + h - bh - (h - bh) * t
        bw = ctx.px(6 if (self._bar_hover or self._drag) else 4)
        return (x + w - bw - ctx.px(3), by, bw, bh)

    def on_wheel(self, ctx, ev):
        if self.max_offset() <= 0:
            return False
        self.offset = max(0.0, min(self.offset - ev.wheel * ctx.px(64), self.max_offset()))
        self.redraw()
        return True

    def on_press(self, ctx, ev):
        bar = self._bar(ctx)
        if bar and ev.x >= bar[0] - ctx.px(6):
            self._drag = (ev.y, self.offset)
            return True
        return False

    def on_drag(self, ctx, ev):
        if self._drag:
            y0, off0 = self._drag
            h = self.rect[3]
            ratio = self._content_h / max(1.0, h)
            self.offset = max(0.0, min(off0 - (ev.y - y0) * ratio, self.max_offset()))
            self.set_anim("scroll", self.offset)
            self.redraw()

    def on_release(self, ctx, ev, inside):
        self._drag = None

    def on_enter(self, ctx):
        self._bar_hover = True
        self.redraw()

    def on_leave(self, ctx):
        self._bar_hover = False
        self.redraw()

    def paint(self, ctx, p):
        x, y, w, h = self.rect
        p.push_clip(x, y, w, h)
        self.child.paint(ctx, p)
        p.pop_clip()
        th = ctx.theme
        bar = self._bar(ctx)
        if bar:
            a = self.anim("bar", 1.0 if (self._bar_hover or self._drag) else 0.45)
            p.rect(*bar, fill=alpha(th.text, 0.22 * a + 0.05), radius=bar[2] / 2)
        # soft fades at the edges when there is more content
        if self.max_offset() > 0:
            fade = ctx.px(14)
            cur = getattr(self, "_cur", 0.0)
            bg = getattr(self, "fade_color", None) or th.bg
            if cur > 1:
                p.rect(x, y + h - fade, w, fade, fill=bg, fill2=alpha(bg, 0.0))
            if cur < self.max_offset() - 1:
                p.rect(x, y, w, fade, fill=alpha(bg, 0.0), fill2=bg)


class Tab:
    def __init__(self, label, content=None, icon=None, key=None):
        self.label = label
        self.content = content
        self.icon = icon
        self.key = key or label


class TabBar(Widget):
    """Pill tab bar from the reference design, with a sliding active indicator.

    Adapts to narrow widths: shows icon-only tabs (active tab keeps its label)."""

    cursor = "HAND"

    def __init__(self, tabs, index=0, on_change=None, size="md", outlined=False, **kw):
        super().__init__(**kw)
        self.tabs = tabs
        self.index = index
        self.on_change = on_change
        self.size = size
        self.outlined = outlined
        self._hover_i = -1
        self._slots = []
        self._mode = "full"

    def interactive(self):
        return True

    def _h(self, ctx):
        return ctx.px(36 if self.size == "md" else 30)

    def _tab_w(self, ctx, tab, mode, active):
        th = ctx.theme
        pad = ctx.px(12)
        iw = ctx.px(15) if tab.icon else 0.0
        show_label = mode == "full" or (mode == "compact" and active)
        tw = ctx.text_w(tab.label, th.fs_md, "medium") if show_label else 0.0
        gap = ctx.px(7) if (tab.icon and show_label) else 0.0
        if not show_label:
            return iw + pad * 1.6
        return pad * 2 + iw + gap + tw

    def natural_width(self, ctx):
        return sum(self._tab_w(ctx, t, "full", False) for t in self.tabs) + ctx.px(8)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), self._h(ctx)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        inner = w - ctx.px(8)
        for mode in ("full", "compact", "icons"):
            ws = [self._tab_w(ctx, t, mode, i == self.index) for i, t in enumerate(self.tabs)]
            if sum(ws) <= inner or mode == "icons":
                break
        self._mode = mode
        extra = max(0.0, inner - sum(ws))
        # distribute the extra space evenly so the bar is filled
        ws = [v + extra / len(ws) for v in ws] if mode != "full" or extra < ctx.px(40) else ws
        if mode == "full" and extra >= ctx.px(40):
            ws = [v + extra / len(ws) for v in ws]
        cx = x + ctx.px(4)
        self._slots = []
        for v in ws:
            self._slots.append((cx, v))
            cx += v

    def _index_at(self, x):
        for i, (sx, sw) in enumerate(self._slots):
            if sx <= x <= sx + sw:
                return i
        return -1

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self._hover_i = -1
        self.redraw()

    def on_hover(self, ctx, ev):
        i = self._index_at(ev.x)
        if i != self._hover_i:
            self._hover_i = i
            self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        i = self._index_at(ev.x)
        if i >= 0 and i != self.index:
            self.index = i
            call(self.on_change, i, self.tabs[i])
            self.redraw()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        r = h / 2
        p.rect(x, y, w, h, fill=th.surface_1, radius=r,
               border=alpha(th.accent, 0.38) if self.outlined else th.border, border_w=ctx.px(1))
        if not self._slots:
            return
        sx, sw = self._slots[self.index]
        ax = self.anim("ix", sx, speed=20)
        aw = self.anim("iw", sw, speed=20)
        ip = ctx.px(4)
        if 0 <= self._hover_i < len(self._slots) and self._hover_i != self.index:
            hx, hw = self._slots[self._hover_i]
            p.rect(hx, y + ip, hw, h - ip * 2, fill=alpha(th.surface_4, 0.55), radius=(h - ip * 2) / 2)
        p.rect(ax, y + ip, aw, h - ip * 2, fill=th.selected, fill2=mix(th.selected, th.surface_1, 0.25),
               radius=(h - ip * 2) / 2, border=alpha((1, 1, 1, 1), 0.05), border_w=ctx.px(1))
        cy = y + h / 2
        for i, (tab, (tx, tw)) in enumerate(zip(self.tabs, self._slots)):
            active = i == self.index
            col = th.text if active else (th.text_dim if i == self._hover_i else th.text_muted)
            show_label = self._mode == "full" or (self._mode == "compact" and active)
            iw = ctx.px(15) if tab.icon else 0.0
            lw = ctx.text_w(tab.label, th.fs_md, "medium") if show_label else 0.0
            gap = ctx.px(7) if (tab.icon and show_label) else 0.0
            cx = tx + (tw - (iw + gap + lw)) / 2
            if tab.icon:
                p.icon(tab.icon, cx, cy - iw / 2, iw, col, 1.5)
            if show_label:
                p.text(tab.label, cx + iw + gap, cy, th.fs_md, col, "medium", valign="center")


class TabView(Column):
    """Tab bar plus the page of the active tab."""

    def __init__(self, tabs, index=0, on_change=None, gap=10, outlined=False, **kw):
        self.tabs = tabs
        self.bar = TabBar(tabs, index=index, on_change=self._changed, outlined=outlined)
        self._user_change = on_change
        super().__init__(self.bar, gap=gap, **kw)
        self._sync()

    def get_state(self):
        return self.bar.index

    def set_state(self, st):
        if 0 <= int(st) < len(self.tabs):
            self.index = int(st)

    @property
    def index(self):
        return self.bar.index

    @index.setter
    def index(self, i):
        self.bar.index = i
        self._sync()

    def _changed(self, i, tab):
        self._sync()
        page = self.tabs[i].content
        if page is not None:
            page.set_anim("enter", 0.0)
        call(self._user_change, i, tab)

    def _sync(self):
        page = self.tabs[self.bar.index].content
        self.items = self._adopt([self.bar] + ([page] if page is not None else []))

    def paint(self, ctx, p):
        self.bar.paint(ctx, p)
        page = self.tabs[self.bar.index].content
        if page is not None and page.visible:
            # slide the new page in
            t = page.anim("enter", 1.0, speed=14)
            if t < 0.999:
                off = (1.0 - t) * ctx.px(14)
                x, y, w, h = page.rect
                page.arrange(ctx, x, y - off, w, h)
            page.paint(ctx, p)
