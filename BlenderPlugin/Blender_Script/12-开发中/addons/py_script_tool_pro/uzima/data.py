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

"""Data elements: curve editor, color ramp, charts, stat tiles, table, tree, steps, ring progress, histogram.

The curve editor and color ramp edit real Blender data when given a CurveMapping or ColorRamp
(for example from a Float Curve / Color Ramp node), and work on plain Python lists otherwise.
"""

import math
import time

from .core import Bind, FuncBind, Widget, call, mark_animating
from .layout import Column, Row
from .theme import alpha, mix, lighten
from .widgets import Dropdown, NumberField, _fmt


def _val(v):
    return v() if callable(v) else v


def _lerp_pts(pts, x):
    """y on a polyline at x (pts sorted by x)."""
    if x <= pts[0][0]:
        return pts[0][1]
    lo, hi = 0, len(pts) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pts[mid][0] <= x:
            lo = mid
        else:
            hi = mid
    (ax, ay), (bx, by) = pts[lo], pts[hi]
    if x >= bx:
        return by
    t = 0.0 if bx - ax < 1e-9 else (x - ax) / (bx - ax)
    return ay + (by - ay) * t


def _palette(th):
    return [th.accent, th.info, th.warning, th.danger, th.success, (0.75, 0.6, 0.95, 1.0)]


# ---------------------------------------------------------------------------
# Curve editor
# ---------------------------------------------------------------------------

def _monotone(points, x):
    """Monotone cubic interpolation (no overshoot) through sorted points."""
    n = len(points)
    if n == 0:
        return 0.0
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    d = []
    for i in range(n - 1):
        dx = xs[i + 1] - xs[i]
        d.append((ys[i + 1] - ys[i]) / dx if dx > 1e-9 else 0.0)
    m = [d[0]] + [0.0 if d[i - 1] * d[i] <= 0 else (d[i - 1] + d[i]) / 2 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0.0
    i = 0
    while i < n - 2 and x > xs[i + 1]:
        i += 1
    h = xs[i + 1] - xs[i]
    if h <= 1e-9:
        return ys[i]
    t = (x - xs[i]) / h
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] +
            (t3 - t2) * h * m[i + 1])


CURVE_PRESETS = {
    "linear": [(0, 0), (1, 1)],
    "smooth": [(0, 0), (0.25, 0.08), (0.75, 0.92), (1, 1)],
    "ease_in": [(0, 0), (0.6, 0.2), (1, 1)],
    "ease_out": [(0, 0), (0.4, 0.8), (1, 1)],
    "bell": [(0, 0), (0.5, 1), (1, 0)],
    "sharp": [(0, 1), (0.2, 0.25), (1, 0)],
}


class CurveEditor(Widget):
    """Draggable curve, for falloffs, easing and profiles.

        ui.CurveEditor(mapping=lambda: node.mapping)          # a Blender CurveMapping (Float Curve node,
                                                              # RGB Curves node, brush falloff...)
        ed = ui.CurveEditor(points=[(0, 0), (1, 1)], on_change=lambda pts, w: ...)
        ed.evaluate(0.5)

    Drag points; double-click to add; right-click a point to delete it."""

    def __init__(self, mapping=None, curve=0, points=None, height=150, on_change=None, label=None, **kw):
        super().__init__(height=height, **kw)
        self.mapping = mapping
        self.curve_index = curve
        self._points = [list(p) for p in (points or CURVE_PRESETS["smooth"])]
        self.on_change = on_change
        self.label = label
        self._sel = -1
        self._drag = False
        self._hover = None

    # ---- data access ------------------------------------------------------------------------
    def _mapping(self):
        return _val(self.mapping) if self.mapping is not None else None

    def _curve(self):
        m = self._mapping()
        return m.curves[self.curve_index] if m is not None else None

    def points(self):
        c = self._curve()
        if c is not None:
            return [tuple(p.location) for p in c.points]
        return [tuple(p) for p in sorted(self._points)]

    def evaluate(self, x):
        m = self._mapping()
        if m is not None:
            c = m.curves[self.curve_index]
            try:
                return m.evaluate(c, x)
            except Exception:
                try:
                    m.initialize()
                    return m.evaluate(c, x)
                except Exception:
                    pass
        return _monotone(self.points(), x)

    def set_points(self, pts):
        """Replace all points (e.g. a preset)."""
        pts = sorted([tuple(p) for p in pts])
        c = self._curve()
        if c is not None:
            while len(c.points) > len(pts):
                c.points.remove(c.points[len(c.points) - 1])
            while len(c.points) < len(pts):
                c.points.new(0.5, 0.5)
            for p, (x, y) in zip(c.points, pts):
                p.location = (x, y)
            self._update()
        else:
            self._points = [list(p) for p in pts]
        self._sel = -1
        call(self.on_change, self.points(), self)
        self.redraw()

    def _update(self):
        m = self._mapping()
        if m is not None:
            try:
                m.update()
            except Exception:
                pass
            idb = getattr(m, "id_data", None)
            try:
                if idb is not None and hasattr(idb, "update_tag"):
                    idb.update_tag()
            except Exception:
                pass

    def _set_point(self, i, x, y):
        c = self._curve()
        if c is not None:
            c.points[i].location = (x, y)
            self._update()
            pts = self.points()
            self._sel = min(range(len(pts)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][1] - y) ** 2)
        else:
            self._points[i] = [x, y]
            order = sorted(range(len(self._points)), key=lambda k: self._points[k][0])
            self._points = [self._points[k] for k in order]
            self._sel = order.index(i)

    def _add(self, x, y):
        c = self._curve()
        if c is not None:
            c.points.new(x, y)
            self._update()
        else:
            self._points.append([x, y])
            self._points.sort()
        pts = self.points()
        self._sel = min(range(len(pts)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][1] - y) ** 2)

    def _remove(self, i):
        c = self._curve()
        if c is not None:
            if len(c.points) > 2:
                c.points.remove(c.points[i])
                self._update()
        elif len(self._points) > 2:
            del self._points[i]
        self._sel = -1

    # ---- geometry -----------------------------------------------------------------------------
    def _box(self, ctx):
        x, y, w, h = self.rect
        top = ctx.px(18) if self.label else 0.0
        pad = ctx.px(8)
        return x + pad, y + pad, w - pad * 2, h - pad * 2 - top

    def _to_px(self, ctx, px_, py_):
        bx, by, bw, bh = self._box(ctx)
        return bx + px_ * bw, by + py_ * bh

    def _from_px(self, ctx, ex, ey):
        bx, by, bw, bh = self._box(ctx)
        return max(0.0, min(1.0, (ex - bx) / max(1.0, bw))), max(0.0, min(1.0, (ey - by) / max(1.0, bh)))

    def _near(self, ctx, ev):
        best, bd = -1, ctx.px(11) ** 2
        for i, (px_, py_) in enumerate(self.points()):
            sx, sy = self._to_px(ctx, px_, py_)
            d = (sx - ev.x) ** 2 + (sy - ev.y) ** 2
            if d < bd:
                best, bd = i, d
        return best

    # ---- events --------------------------------------------------------------------------------
    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height) + (ctx.px(18) if self.label else 0.0)

    def on_hover(self, ctx, ev):
        self._hover = self._from_px(ctx, ev.x, ev.y)
        self.redraw()

    def on_leave(self, ctx):
        self._hover = None
        self.redraw()

    def on_press(self, ctx, ev):
        self._sel = self._near(ctx, ev)
        self._drag = self._sel >= 0
        self.redraw()
        return True

    def on_drag(self, ctx, ev):
        if self._drag and self._sel >= 0:
            x, y = self._from_px(ctx, ev.x, ev.y)
            self._set_point(self._sel, x, y)
            self._hover = (x, y)
            self.redraw()

    def on_release(self, ctx, ev, inside):
        if self._drag:
            call(self.on_change, self.points(), self)
            self._push_undo()
        self._drag = False

    def on_double_click(self, ctx, ev):
        if self._near(ctx, ev) < 0:
            x, _y = self._from_px(ctx, ev.x, ev.y)
            self._add(x, self.evaluate(x))
            call(self.on_change, self.points(), self)
            self._push_undo()
            self.redraw()
        return True

    def on_right_click(self, ctx, ev):
        i = self._near(ctx, ev)
        if i >= 0:
            self._remove(i)
            call(self.on_change, self.points(), self)
            self._push_undo()
            self.redraw()
            return True
        return False

    def _push_undo(self):
        if self._mapping() is not None:
            try:
                import bpy
                bpy.ops.ed.undo_push(message="Edit curve")
            except Exception:
                pass

    # ---- paint ------------------------------------------------------------------------------------
    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
            h -= ctx.px(18)
        r = ctx.px(th.r_md)
        p.rect(x, y, w, h, fill=th.surface_0, radius=r, border=th.border, border_w=ctx.px(1))
        bx, by, bw, bh = self._box(ctx)
        for i in range(1, 4):
            p.rect(bx + bw * i / 4 - 0.5, by, 1, bh, fill=alpha(th.border_strong, 0.5))
            p.rect(bx, by + bh * i / 4 - 0.5, bw, 1, fill=alpha(th.border_strong, 0.5))
        p.line(bx, by, bx + bw, by + bh, ctx.px(1), alpha(th.text_muted, 0.25))
        n = max(24, int(bw / ctx.px(3)))
        samples = [(i / n, max(0.0, min(1.0, self.evaluate(i / n)))) for i in range(n + 1)]
        pts = [self._to_px(ctx, sx, sy) for sx, sy in samples]
        p.area(bx, bx + bw, by, lambda px_: _lerp_pts(pts, px_), alpha(th.accent, 0.20), alpha(th.accent, 0.03),
               flat=alpha(th.accent, 0.10))
        p.polyline(pts, ctx.px(2.2), th.accent)
        for i, (px_, py_) in enumerate(self.points()):
            sx, sy = self._to_px(ctx, px_, py_)
            sel = i == self._sel
            kr = ctx.px(6 if sel else 4.5)
            p.shadow(sx - kr, sy - kr, kr * 2, kr * 2, kr, (0, 0, 0, 0.5), ctx.px(3))
            p.circle(sx, sy, kr, fill=(0.97, 0.97, 0.97, 1) if sel else th.surface_2,
                     border=th.accent, border_w=ctx.px(2))
        if self._hover is not None or self._sel >= 0:
            hx, hy = (self.points()[self._sel] if self._drag and self._sel >= 0 else self._hover) or (0, 0)
            txt = "x %.2f   y %.2f" % (hx, hy if self._drag else self.evaluate(hx))
            p.text(txt, bx + ctx.px(4), by + bh - ctx.px(8), th.fs_xs, th.text_dim, "medium", valign="center")


# ---------------------------------------------------------------------------
# Color ramp
# ---------------------------------------------------------------------------

def _srgb(c):
    from .inputs import linear_to_srgb
    return tuple(linear_to_srgb(v) for v in c[:3]) + (c[3] if len(c) > 3 else 1.0,)


def _lin(c):
    from .inputs import srgb_to_linear
    return tuple(srgb_to_linear(v) for v in c[:3]) + (c[3] if len(c) > 3 else 1.0,)


class _RampBar(Widget):
    def __init__(self, ed, **kw):
        super().__init__(**kw)
        self.ed = ed
        self._drag = False

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return avail_w, ctx.px(52)

    def _bar(self, ctx):
        x, y, w, h = self.rect
        k = ctx.px(8)
        return x + k, y + ctx.px(20), w - 2 * k, h - ctx.px(22)

    def _near(self, ctx, ev):
        bx, by, bw, bh = self._bar(ctx)
        best, bd = -1, ctx.px(10)
        for i, (pos, _c) in enumerate(self.ed.stops()):
            d = abs(bx + pos * bw - ev.x)
            if d < bd and ev.y < by + ctx.px(4):
                best, bd = i, d
        return best

    def on_press(self, ctx, ev):
        i = self._near(ctx, ev)
        if i >= 0:
            self.ed.select(i)
            self._drag = True
        return True

    def on_drag(self, ctx, ev):
        if self._drag:
            bx, by, bw, bh = self._bar(ctx)
            self.ed.move_selected(max(0.0, min(1.0, (ev.x - bx) / max(1.0, bw))))

    def on_release(self, ctx, ev, inside):
        if self._drag:
            self.ed._changed(undo=True)
        self._drag = False

    def on_double_click(self, ctx, ev):
        bx, by, bw, bh = self._bar(ctx)
        self.ed.add((ev.x - bx) / max(1.0, bw))
        return True

    def on_right_click(self, ctx, ev):
        i = self._near(ctx, ev)
        if i >= 0:
            self.ed.remove(i)
            return True
        return False

    def paint(self, ctx, p):
        from .inputs import _checker
        th = ctx.theme
        bx, by, bw, bh = self._bar(ctx)
        r = ctx.px(7)
        _checker(p, bx, by, bw, bh, ctx.px(6), radius=r)
        stops = self.ed.stops()
        constant = self.ed.interpolation() == "CONSTANT"
        if stops:
            p0 = stops[0][0]
            p.rect(bx, by, max(0.5, bw * p0 + 1), bh, fill=stops[0][1], radius=(r, 0, 0, r), functional=True)
            for (a, ca), (b, cb) in zip(stops, stops[1:]):
                p.rect(bx + bw * a, by, max(0.5, bw * (b - a) + 1), bh, fill=ca, fill2=ca if constant else cb,
                       angle=math.pi / 2, functional=True)
            pl = stops[-1][0]
            p.rect(bx + bw * pl, by, max(0.5, bw * (1 - pl)), bh, fill=stops[-1][1], radius=(0, r, r, 0),
                   functional=True)
        p.rect(bx, by, bw, bh, radius=r, border=alpha((1, 1, 1, 1), 0.12), border_w=ctx.px(1))
        for i, (pos, c) in enumerate(stops):
            sel = i == self.ed.sel
            sx = bx + bw * pos
            s = ctx.px(13 if sel else 11)
            hy = by + bh + ctx.px(3)
            p.line(sx, by, sx, by + bh, ctx.px(1.2), alpha((1, 1, 1, 1), 0.7 if sel else 0.35))
            p.shadow(sx - s / 2, by - s - ctx.px(5), s, s, ctx.px(4), (0, 0, 0, 0.45), ctx.px(3))
            p.rect(sx - s / 2, by - s - ctx.px(4), s, s, fill=c, radius=ctx.px(4),
                   border=th.accent if sel else (0.95, 0.95, 0.95, 1), border_w=ctx.px(2 if sel else 1.5))


class ColorRampEditor(Column):
    """Gradient editor with draggable color stops.

        ui.ColorRampEditor(ramp=lambda: node.color_ramp)          # a Blender ColorRamp
        ui.ColorRampEditor(stops=[(0, "#000000"), (1, "#ffffff")], on_change=lambda stops, w: ...)

    Drag stops; double-click the bar to add one; right-click a stop to delete it.
    The selected stop's color and position are edited below the bar."""

    def __init__(self, ramp=None, stops=None, on_change=None, label=None, **kw):
        from .inputs import ColorField
        from .theme import to_color
        self.ramp = ramp
        self._stops = [[p, to_color(c)] for p, c in (stops or [(0.0, "#16181c"), (0.55, "#9fbd97"), (1.0, "#f2f5ef")])]
        self.on_change = on_change
        self.sel = 0
        self.bar = _RampBar(self)
        self.color = ColorField(bind=FuncBind(self._sel_color, self._set_sel_color, "Color"),
                                on_change=lambda v, w: self._changed())
        self.color.linear = False
        self.pos = NumberField("Pos", bind=FuncBind(self._sel_pos, self.move_selected, "Position"), min=0.0, max=1.0,
                               step=0.01, precision=3)
        kids = []
        if label:
            from .widgets import Label
            kids.append(Label(label, muted=True, size=11.5, weight="medium"))
        kids += [self.bar, Row(self.color, self.pos, gap=6)]
        if ramp is not None:
            kids.append(Dropdown(bind=Bind(lambda: _val(self.ramp), "interpolation"), label="Interpolation"))
        super().__init__(*kids, gap=8, **kw)

    def _ramp(self):
        return _val(self.ramp) if self.ramp is not None else None

    def interpolation(self):
        r = self._ramp()
        return r.interpolation if r is not None else "LINEAR"

    def stops(self):
        """[(position, sRGB color)] sorted by position."""
        r = self._ramp()
        if r is not None:
            return [(e.position, _srgb(tuple(e.color))) for e in r.elements]
        return sorted([(p, tuple(c)) for p, c in self._stops], key=lambda s: s[0])

    def evaluate(self, pos):
        r = self._ramp()
        if r is not None:
            return _srgb(tuple(r.evaluate(pos)))
        st = self.stops()
        if pos <= st[0][0]:
            return st[0][1]
        for (a, ca), (b, cb) in zip(st, st[1:]):
            if a <= pos <= b:
                t = 0 if b - a < 1e-6 else (pos - a) / (b - a)
                return mix(ca, cb, t)
        return st[-1][1]

    def select(self, i):
        self.sel = i
        self.redraw()

    def _sel_color(self):
        st = self.stops()
        return st[self.sel][1] if 0 <= self.sel < len(st) else (1, 1, 1, 1)

    def _set_sel_color(self, c):
        c = tuple(c) + (1.0,) * (4 - len(c))
        r = self._ramp()
        if r is not None:
            if 0 <= self.sel < len(r.elements):
                r.elements[self.sel].color = _lin(c)
        else:
            st = sorted(self._stops, key=lambda s: s[0])
            if 0 <= self.sel < len(st):
                st[self.sel][1] = c
                self._stops = st

    def _sel_pos(self):
        st = self.stops()
        return float(st[self.sel][0]) if 0 <= self.sel < len(st) else 0.0

    def move_selected(self, pos):
        pos = max(0.0, min(1.0, float(pos)))
        r = self._ramp()
        if r is not None:
            if 0 <= self.sel < len(r.elements):
                e = r.elements[self.sel]
                e.position = pos
                for i, el in enumerate(r.elements):
                    if el.as_pointer() == e.as_pointer():
                        self.sel = i
        else:
            st = sorted(self._stops, key=lambda s: s[0])
            if 0 <= self.sel < len(st):
                item = st[self.sel]
                item[0] = pos
                st.sort(key=lambda s: s[0])
                self.sel = st.index(item)
                self._stops = st
        self._changed()

    def add(self, pos):
        pos = max(0.0, min(1.0, pos))
        c = self.evaluate(pos)
        r = self._ramp()
        if r is not None:
            e = r.elements.new(pos)
            e.color = _lin(c)
            for i, el in enumerate(r.elements):
                if el.as_pointer() == e.as_pointer():
                    self.sel = i
        else:
            self._stops.append([pos, tuple(c)])
            self._stops.sort(key=lambda s: s[0])
            self.sel = [s[0] for s in self._stops].index(pos)
        self._changed(undo=True)

    def remove(self, i):
        r = self._ramp()
        if r is not None:
            if len(r.elements) > 1:
                r.elements.remove(r.elements[i])
        elif len(self._stops) > 1:
            st = sorted(self._stops, key=lambda s: s[0])
            del st[i]
            self._stops = st
        self.sel = max(0, min(self.sel, len(self.stops()) - 1))
        self._changed(undo=True)

    def _changed(self, undo=False):
        call(self.on_change, self.stops(), self)
        if undo and self._ramp() is not None:
            try:
                import bpy
                bpy.ops.ed.undo_push(message="Edit color ramp")
            except Exception:
                pass
        self.redraw()


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _series(src, th):
    s = _val(src)
    out = []
    pal = _palette(th)
    if isinstance(s, dict):
        s = list(s.items())
    if s and isinstance(s[0], (int, float)):
        s = [("", s)]
    for i, item in enumerate(s or []):
        name, vals = item[0], list(_val(item[1]))
        col = item[2] if len(item) > 2 else pal[i % len(pal)]
        out.append((name, vals, col))
    return out


def _nice(lo, hi):
    if hi - lo < 1e-9:
        hi = lo + 1.0
    span = hi - lo
    step = 10 ** math.floor(math.log10(span / 4))
    for m in (1, 2, 2.5, 5, 10):
        if span / (step * m) <= 5:
            step *= m
            break
    return math.floor(lo / step) * step, math.ceil(hi / step) * step, step


class LineChart(Widget):
    """Line chart. series: [values], {"name": values}, or [(name, values, color)], or a function
    returning any of those (re-read every redraw, so it can show live data)."""

    def __init__(self, series, labels=None, height=150, fill=True, y_min=None, y_max=None, format=None,
                 legend=True, **kw):
        super().__init__(height=height, **kw)
        self.series = series
        self.labels = labels
        self.fill = fill
        self.y_min, self.y_max = y_min, y_max
        self.format = format or (lambda v: ("%.0f" % v) if abs(v) >= 100 else ("%.2g" % v))
        self.legend = legend
        self._hi = -1

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height)

    def _plot(self, ctx):
        x, y, w, h = self.rect
        top = ctx.px(22) if self.legend else ctx.px(8)
        return x + ctx.px(34), y + ctx.px(20), w - ctx.px(40), h - ctx.px(20) - top

    def on_hover(self, ctx, ev):
        ss = _series(self.series, ctx.theme)
        n = max((len(v) for _n, v, _c in ss), default=0)
        px_, py_, pw, ph = self._plot(ctx)
        i = int(round((ev.x - px_) / max(1.0, pw) * (n - 1))) if n > 1 else 0
        i = max(0, min(n - 1, i))
        if i != self._hi:
            self._hi = i
            self.redraw()

    def on_leave(self, ctx):
        self._hi = -1
        self.redraw()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        ss = _series(self.series, th)
        if not ss or not any(v for _n, v, _c in ss):
            p.text("No data", x + w / 2, y + h / 2, th.fs_sm, th.text_muted, align="center", valign="center")
            return
        allv = [v for _n, vals, _c in ss for v in vals]
        lo = self.y_min if self.y_min is not None else min(allv)
        hi = self.y_max if self.y_max is not None else max(allv)
        lo, hi, step = _nice(lo, hi)
        px_, py_, pw, ph = self._plot(ctx)
        k = 0
        v = lo
        while v <= hi + step * 0.01 and k < 12:
            gy = py_ + (v - lo) / (hi - lo) * ph
            p.rect(px_, gy - 0.5, pw, 1, fill=alpha(th.border_strong, 0.6))
            p.text(self.format(v), px_ - ctx.px(6), gy, th.fs_xs, th.text_muted, align="right", valign="center")
            v += step
            k += 1
        n = max(len(v) for _n, v, _c in ss)
        labels = _val(self.labels)
        if labels:
            every = max(1, int(len(labels) / max(1, pw / ctx.px(48))))
            for i, lab in enumerate(labels):
                if i % every == 0:
                    lx = px_ + (i / max(1, n - 1)) * pw
                    p.text(str(lab), lx, y + ctx.px(8), th.fs_xs, th.text_muted, align="center", valign="center")

        def pt(i, v):
            return px_ + (i / max(1, n - 1)) * pw, py_ + (v - lo) / (hi - lo) * ph

        for name, vals, col in ss:
            pts = [pt(i, v) for i, v in enumerate(vals)]
            if self.fill and len(pts) > 1:
                p.area(pts[0][0], pts[-1][0], py_, lambda px2, pts=pts: _lerp_pts(pts, px2), alpha(col, 0.22),
                       alpha(col, 0.02), flat=alpha(col, 0.10))
            p.polyline(pts, ctx.px(2), col)
        if self.legend and any(nm for nm, _v, _c in ss):
            lx = x + ctx.px(34)
            for name, _v, col in ss:
                p.circle(lx + ctx.px(4), y + h - ctx.px(9), ctx.px(3.5), fill=col)
                lx += ctx.px(12) + p.text(name, lx + ctx.px(11), y + h - ctx.px(9), th.fs_xs, th.text_dim, "medium",
                                          valign="center") + ctx.px(10)
        if 0 <= self._hi < n:
            hx = pt(self._hi, lo)[0]
            p.rect(hx - 0.5, py_, 1, ph, fill=alpha(th.text, 0.25))
            rows = []
            for name, vals, col in ss:
                if self._hi < len(vals):
                    hx2, hy2 = pt(self._hi, vals[self._hi])
                    p.circle(hx2, hy2, ctx.px(4), fill=col, border=th.bg, border_w=ctx.px(1.5))
                    rows.append((name or "Value", self.format(vals[self._hi]), col))
            head = str(labels[self._hi]) if labels and self._hi < len(labels) else "#%d" % (self._hi + 1)
            tw = max([ctx.text_w(head, th.fs_xs, "semibold")] +
                     [ctx.text_w("%s  %s" % (a, b), th.fs_xs) + ctx.px(12) for a, b, _c in rows]) + ctx.px(16)
            th_ = ctx.px(20) + ctx.px(15) * len(rows)
            bx = hx + ctx.px(8) if hx + ctx.px(8) + tw < x + w else hx - ctx.px(8) - tw
            by = py_ + ph - th_
            p.shadow(bx, by, tw, th_, ctx.px(7), (0, 0, 0, 0.4), ctx.px(8))
            p.rect(bx, by, tw, th_, fill=th.surface_2, radius=ctx.px(7), border=th.border_strong, border_w=ctx.px(1))
            p.text(head, bx + ctx.px(8), by + th_ - ctx.px(10), th.fs_xs, th.text, "semibold", valign="center")
            ry = by + th_ - ctx.px(25)
            for a, b, col in rows:
                p.circle(bx + ctx.px(11), ry, ctx.px(3), fill=col)
                p.text(a, bx + ctx.px(19), ry, th.fs_xs, th.text_dim, valign="center")
                p.text(b, bx + tw - ctx.px(8), ry, th.fs_xs, th.text, "semibold", align="right", valign="center")
                ry -= ctx.px(15)


class BarChart(Widget):
    """Bar chart. values: list or function; labels: list or function; colors: one or a list."""

    def __init__(self, values, labels=None, height=140, colors=None, format=None, **kw):
        super().__init__(height=height, **kw)
        self.values = values
        self.labels = labels
        self.colors = colors
        self.format = format or (lambda v: ("%.0f" % v) if float(v).is_integer() or abs(v) >= 100 else "%.2f" % v)
        self._hi = -1
        self._bars = []

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height)

    def on_hover(self, ctx, ev):
        i = -1
        for k, (bx, bw) in enumerate(self._bars):
            if bx <= ev.x <= bx + bw:
                i = k
        if i != self._hi:
            self._hi = i
            self.redraw()

    def on_leave(self, ctx):
        self._hi = -1
        self.redraw()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        vals = list(_val(self.values) or [])
        labels = list(_val(self.labels) or [])
        if not vals:
            p.text("No data", x + w / 2, y + h / 2, th.fs_sm, th.text_muted, align="center", valign="center")
            return
        hi = max(max(vals), 1e-9)
        n = len(vals)
        base = y + ctx.px(18)
        ph = h - ctx.px(18) - ctx.px(16)
        g = ctx.px(8)
        bw = (w - g * (n - 1)) / n
        cols = self.colors
        self._bars = []
        for i, v in enumerate(vals):
            c = (cols[i % len(cols)] if isinstance(cols, (list, tuple)) and cols and isinstance(cols[0], (list, tuple))
                 else (cols or th.accent))
            t = self.anim("b%d" % i, v / hi, speed=10)
            bh = max(ctx.px(2), ph * t)
            bx = x + i * (bw + g)
            self._bars.append((bx, bw))
            hl = i == self._hi
            p.rect(bx, base, bw, bh, fill=lighten(c, 0.12 if hl else 0.0), fill2=mix(c, th.surface_1, 0.35),
                   radius=(min(ctx.px(6), bw / 2), min(ctx.px(6), bw / 2), 0, 0))
            if labels and i < len(labels):
                p.text(str(labels[i]), bx + bw / 2, y + ctx.px(8), th.fs_xs, th.text if hl else th.text_muted,
                       align="center", valign="center", max_w=bw + g)
            if hl or n <= 8:
                p.text(self.format(v), bx + bw / 2, base + bh + ctx.px(8), th.fs_xs, th.text if hl else th.text_dim,
                       "semibold" if hl else "regular", align="center", valign="center")


class Sparkline(Widget):
    """Tiny line chart (no axes). values: list or function."""

    def __init__(self, values, height=28, color=None, fill=True, **kw):
        super().__init__(height=height, **kw)
        self.values = values
        self.color = color
        self.fill = fill

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        vals = list(_val(self.values) or [])
        if len(vals) < 2:
            return
        c = th.color(self.color) or th.accent
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-9:
            hi = lo + 1
        pad = ctx.px(3)
        pts = [(x + i / (len(vals) - 1) * w, y + pad + (v - lo) / (hi - lo) * (h - pad * 2)) for i, v in enumerate(vals)]
        if self.fill:
            p.area(pts[0][0], pts[-1][0], y, lambda px_: _lerp_pts(pts, px_), alpha(c, 0.2), alpha(c, 0.0),
                   flat=alpha(c, 0.1))
        p.polyline(pts, ctx.px(1.6), c)
        p.circle(pts[-1][0], pts[-1][1], ctx.px(2.6), fill=c)


class StatTile(Widget):
    """Big number, label, change indicator and optional sparkline. Any argument can be a function."""

    def __init__(self, label, value, delta=None, icon=None, spark=None, suffix="", **kw):
        super().__init__(**kw)
        self.label = label
        self.value = value
        self.delta = delta
        self.icon = icon
        self.suffix = suffix
        self.spark = Sparkline(spark, height=24) if spark is not None else None
        if self.spark:
            self.spark.parent = self

    def children(self):
        return (self.spark,) if self.spark else ()

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(84 if self.spark else 70)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        if self.spark:
            self.spark.measure(ctx, w - ctx.px(24))
            self.spark.arrange(ctx, x + ctx.px(12), y + ctx.px(8), w - ctx.px(24), ctx.px(18))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        p.rect(x, y, w, h, fill=th.surface_1, fill2=mix(th.surface_1, th.bg, 0.4), radius=ctx.px(th.r_md),
               border=th.border, border_w=ctx.px(1))
        top = y + h - ctx.px(16)
        lx = x + ctx.px(12)
        if self.icon:
            p.icon(self.icon, lx, top - ctx.px(6), ctx.px(12), th.text_muted, 1.6)
            lx += ctx.px(17)
        p.text(str(_val(self.label)), lx, top, th.fs_xs, th.text_muted, "medium", valign="center",
               max_w=w - (lx - x) - ctx.px(10))
        v = _val(self.value)
        vs = (("{:,}".format(v) if isinstance(v, int) else ("%.1f" % v if isinstance(v, float) else str(v)))
              + self.suffix)
        p.text(vs, x + ctx.px(12), top - ctx.px(24), th.fs_xl + 2, th.text, "semibold", valign="center",
               max_w=w - ctx.px(24))
        d = _val(self.delta)
        if d is not None:
            if isinstance(d, (int, float)):
                good = d >= 0
                ds = ("+" if d > 0 else "") + ("%g" % round(d, 2))
            else:
                ds = str(d)
                good = not ds.startswith("-")
            c = th.success if good else th.danger
            dw = ctx.text_w(ds, th.fs_xs, "semibold") + ctx.px(22)
            dx = x + w - ctx.px(10) - dw
            dy = top - ctx.px(24) - ctx.px(9)
            p.rect(dx, dy, dw, ctx.px(18), fill=alpha(c, 0.14), radius=ctx.px(9))
            p.icon("arrow_up" if good else "arrow_down", dx + ctx.px(4), dy + ctx.px(3), ctx.px(12), c, 1.8)
            p.text(ds, dx + ctx.px(17), dy + ctx.px(9), th.fs_xs, c, "semibold", valign="center")


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

class TableColumn:
    """A table column.

    TableColumn("Name", lambda row: row.name, icon=lambda row: "cube")
    TableColumn("Verts", lambda o: len(o.data.vertices) if o.type == "MESH" else 0, align="right", width=60)
    TableColumn("", toggle=(lambda o: not o.hide_get(), lambda o, v: o.hide_set(not v)), icons=("eye", "x"),
                width=30)
    """

    def __init__(self, title, value=None, width=None, align="left", icon=None, sortable=True, sort_key=None,
                 toggle=None, icons=("eye", "minus"), format=None):
        self.title = title
        self.value = value
        self.width = width
        self.align = align
        self.icon = icon
        self.sortable = sortable and toggle is None
        self.sort_key = sort_key
        self.toggle = toggle
        self.icons = icons
        self.format = format


class Table(Widget):
    """Rows and columns from any Python data, for example scene objects.

        ui.Table([ui.TableColumn("Name", lambda o: o.name, icon=ui.id_icon), ...],
                 rows=lambda: list(bpy.context.scene.objects),
                 selected=lambda o: o.select_get(), on_select=select_object, max_rows=8)

    Click a header to sort, click a row to select (on_select(row, table, event)), double-click
    for on_activate(row). Scrolls with the wheel when there are more than max_rows rows."""

    def __init__(self, columns, rows, row_height=30, max_rows=8, selected=None, on_select=None, on_activate=None,
                 empty="Nothing to show", **kw):
        super().__init__(**kw)
        self.columns = columns
        self.rows = rows
        self.row_height = row_height
        self.max_rows = max_rows
        self.selected = selected
        self.on_select = on_select
        self.on_activate = on_activate
        self.empty = empty
        self.sort_col = None
        self.sort_desc = False
        self.scroll = 0
        self._hov = -1
        self._cols = []
        self._cache = []

    def _rows(self):
        rows = list(_val(self.rows) or [])
        if self.sort_col is not None:
            c = self.columns[self.sort_col]
            key = c.sort_key or c.value
            try:
                rows.sort(key=lambda r: (key(r) is None, key(r)), reverse=self.sort_desc)
            except Exception:
                pass
        self._cache = rows
        return rows

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        n = min(len(self._rows()), self.max_rows)
        return self.resolve_width(ctx, avail_w), ctx.px(28) + ctx.px(self.row_height) * max(1, n)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        fixed = sum(ctx.px(c.width) for c in self.columns if c.width)
        flex = [c for c in self.columns if not c.width]
        rest = max(0.0, w - fixed - ctx.px(8))
        cx = x + ctx.px(4)
        self._cols = []
        for c in self.columns:
            cw = ctx.px(c.width) if c.width else rest / max(1, len(flex))
            self._cols.append((cx, cw))
            cx += cw

    def _row_at(self, ctx, ev):
        x, y, w, h = self.rect
        top = y + h - ctx.px(28)
        if ev.y > top:
            return -2
        i = int((top - ev.y) // ctx.px(self.row_height)) + self.scroll
        return i if 0 <= i < len(self._cache) else -1

    def _col_at(self, ev):
        for i, (cx, cw) in enumerate(self._cols):
            if cx <= ev.x <= cx + cw:
                return i
        return -1

    def on_hover(self, ctx, ev):
        i = self._row_at(ctx, ev)
        if i != self._hov:
            self._hov = i
            self.redraw()

    def on_leave(self, ctx):
        self._hov = -1
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        i = self._row_at(ctx, ev)
        ci = self._col_at(ev)
        if i == -2:
            if 0 <= ci < len(self.columns) and self.columns[ci].sortable:
                if self.sort_col == ci:
                    self.sort_desc = not self.sort_desc
                else:
                    self.sort_col, self.sort_desc = ci, False
            self.redraw()
            return
        if i < 0:
            return
        row = self._cache[i]
        col = self.columns[ci] if 0 <= ci < len(self.columns) else None
        if col is not None and col.toggle is not None:
            get, setter = col.toggle
            setter(row, not get(row))
            try:
                import bpy
                bpy.ops.ed.undo_push(message="Toggle " + (col.title or "value"))
            except Exception:
                pass
            self.redraw()
            return
        call(self.on_select, row, self, ev)
        self.redraw()

    def on_double_click(self, ctx, ev):
        i = self._row_at(ctx, ev)
        if i >= 0 and self.on_activate:
            call(self.on_activate, self._cache[i], self)
            return True
        return False

    def on_wheel(self, ctx, ev):
        n = len(self._cache)
        if n <= self.max_rows:
            return False
        self.scroll = max(0, min(n - self.max_rows, self.scroll - int(ev.wheel)))
        self.redraw()
        return True

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        rows = self._rows()
        r = ctx.px(th.r_md)
        p.rect(x, y, w, h, fill=th.surface_0, radius=r, border=th.border, border_w=ctx.px(1))
        hh = ctx.px(28)
        top = y + h
        p.rect(x, top - hh, w, hh, fill=th.surface_1, radius=(r, r, 0, 0))
        p.rect(x, top - hh, w, ctx.px(1), fill=th.border)
        for i, (c, (cx, cw)) in enumerate(zip(self.columns, self._cols)):
            al = c.align
            tx = cx + ctx.px(8) if al == "left" else (cx + cw - ctx.px(8) if al == "right" else cx + cw / 2)
            col = th.text if self.sort_col == i else th.text_muted
            tw = p.text(c.title.upper(), tx, top - hh / 2, th.fs_xs, col, "semibold", align=al, valign="center",
                        max_w=cw - ctx.px(18))
            if self.sort_col == i:
                ax = tx + tw + ctx.px(3) if al == "left" else tx - tw - ctx.px(13)
                p.icon("chevron_down" if self.sort_desc else "chevron_up", ax, top - hh / 2 - ctx.px(5), ctx.px(10),
                       th.accent, 1.8)
        rh = ctx.px(self.row_height)
        if not rows:
            p.text(self.empty, x + w / 2, y + (h - hh) / 2, th.fs_sm, th.text_muted, align="center", valign="center")
            return
        self.scroll = max(0, min(self.scroll, max(0, len(rows) - self.max_rows)))
        ry = top - hh
        for i in range(self.scroll, min(len(rows), self.scroll + self.max_rows)):
            row = rows[i]
            ry -= rh
            sel = False
            if self.selected is not None:
                try:
                    sel = bool(self.selected(row))
                except Exception:
                    sel = False
            if sel:
                p.rect(x + ctx.px(3), ry + ctx.px(1.5), w - ctx.px(6), rh - ctx.px(3), fill=th.accent_soft,
                       radius=ctx.px(6))
                p.rect(x + ctx.px(3), ry + rh * 0.28, ctx.px(2.5), rh * 0.44, fill=th.accent, radius=ctx.px(1.2))
            elif i == self._hov:
                p.rect(x + ctx.px(3), ry + ctx.px(1.5), w - ctx.px(6), rh - ctx.px(3), fill=alpha(th.surface_3, 0.7),
                       radius=ctx.px(6))
            for c, (cx, cw) in zip(self.columns, self._cols):
                cy = ry + rh / 2
                try:
                    if c.toggle is not None:
                        on = bool(c.toggle[0](row))
                        isz = ctx.px(14)
                        p.icon(c.icons[0] if on else c.icons[1], cx + cw / 2 - isz / 2, cy - isz / 2, isz,
                               th.text_dim if on else th.text_disabled, 1.6)
                        continue
                    v = c.value(row) if c.value else ""
                    txt = c.format(v) if c.format else (("%.2f" % v) if isinstance(v, float) else str(v))
                    tx = cx + ctx.px(8)
                    if c.icon is not None:
                        ic = c.icon(row) if callable(c.icon) else c.icon
                        if ic:
                            p.icon(ic, tx, cy - ctx.px(7), ctx.px(14), th.accent if sel else th.text_dim, 1.5)
                            tx += ctx.px(20)
                    al = c.align
                    ax = tx if al == "left" else (cx + cw - ctx.px(8) if al == "right" else cx + cw / 2)
                    p.text(txt, ax, cy, th.fs_sm, th.text if sel else th.text_dim, "medium" if sel else "regular",
                           align=al, valign="center", max_w=cw - (tx - cx) - ctx.px(6))
                except Exception:
                    pass
            if i < len(rows) - 1:
                p.rect(x + ctx.px(10), ry - 0.5, w - ctx.px(20), 1, fill=alpha(th.border, 0.6))
        if len(rows) > self.max_rows:
            body = h - hh
            frac = self.max_rows / len(rows)
            bh = max(ctx.px(18), body * frac)
            by = y + body - bh - (body - bh) * (self.scroll / max(1, len(rows) - self.max_rows))
            p.rect(x + w - ctx.px(5), by, ctx.px(3), bh, fill=alpha(th.text, 0.22), radius=ctx.px(1.5))


# ---------------------------------------------------------------------------
# Tree view
# ---------------------------------------------------------------------------

class TreeNode:
    def __init__(self, id, label, icon=None, children=None, data=None, muted=False):
        self.id = id
        self.label = label
        self.icon = icon
        self.children = children
        self.data = data
        self.muted = muted

    def kids(self):
        c = self.children
        return list(c() if callable(c) else (c or []))


class TreeToggle:
    """An icon switch at the right of each row: TreeToggle(get(node), set(node, value), icons=("eye", "minus"))."""

    def __init__(self, get, set, icons=("eye", "minus"), tooltip=None):
        self.get, self.set, self.icons, self.tooltip = get, set, icons, tooltip


class TreeView(Widget):
    """Expandable hierarchy (collections, folders, bones...).

        ui.TreeView(lambda: build_nodes(), on_select=lambda node, tree, ev: ..., selected=lambda node: ...,
                    toggles=[ui.TreeToggle(get, set)])
    nodes: list of TreeNode or a function returning one (re-read every redraw)."""

    def __init__(self, nodes, on_select=None, selected=None, toggles=None, row_height=26, max_rows=12,
                 expanded=None, **kw):
        super().__init__(**kw)
        self.nodes = nodes
        self.on_select = on_select
        self.selected = selected
        self.toggles = toggles or []
        self.row_height = row_height
        self.max_rows = max_rows
        self.expanded = set(expanded or ())
        self.scroll = 0
        self._flat = []
        self._hov = -1

    def get_state(self):
        return sorted(str(e) for e in self.expanded)

    def set_state(self, st):
        self.expanded = set(st)

    def _flatten(self):
        out = []

        def walk(nodes, depth):
            for n in nodes:
                kids = n.kids()
                out.append((n, depth, bool(kids)))
                if kids and str(n.id) in self.expanded:
                    walk(kids, depth + 1)
        walk(list(_val(self.nodes) or []), 0)
        self._flat = out
        return out

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        n = min(len(self._flatten()), self.max_rows)
        return self.resolve_width(ctx, avail_w), ctx.px(self.row_height) * max(1, n) + ctx.px(8)

    def _at(self, ctx, ev):
        x, y, w, h = self.rect
        i = int((y + h - ctx.px(4) - ev.y) // ctx.px(self.row_height)) + self.scroll
        return i if 0 <= i < len(self._flat) else -1

    def on_hover(self, ctx, ev):
        i = self._at(ctx, ev)
        if i != self._hov:
            self._hov = i
            self.redraw()

    def on_leave(self, ctx):
        self._hov = -1
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        i = self._at(ctx, ev)
        if i < 0:
            return
        node, depth, has_kids = self._flat[i]
        x, y, w, h = self.rect
        ind = ctx.px(16)
        chev_x = x + ctx.px(6) + depth * ind
        # toggles on the right
        tx = x + w - ctx.px(8)
        for tg in reversed(self.toggles):
            tx -= ctx.px(22)
            if tx <= ev.x <= tx + ctx.px(22):
                try:
                    tg.set(node, not tg.get(node))
                    import bpy
                    bpy.ops.ed.undo_push(message="Toggle")
                except Exception:
                    pass
                self.redraw()
                return
        if has_kids and chev_x - ctx.px(2) <= ev.x <= chev_x + ctx.px(16):
            key = str(node.id)
            self.expanded.symmetric_difference_update({key})
            self.redraw()
            return
        call(self.on_select, node, self, ev)
        self.redraw()

    def on_double_click(self, ctx, ev):
        i = self._at(ctx, ev)
        if i >= 0 and self._flat[i][2]:
            self.expanded.symmetric_difference_update({str(self._flat[i][0].id)})
            self.redraw()
            return True
        return False

    def on_wheel(self, ctx, ev):
        n = len(self._flat)
        if n <= self.max_rows:
            return False
        self.scroll = max(0, min(n - self.max_rows, self.scroll - int(ev.wheel)))
        self.redraw()
        return True

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        flat = self._flatten()
        p.rect(x, y, w, h, fill=th.surface_0, radius=ctx.px(th.r_md), border=th.border, border_w=ctx.px(1))
        rh = ctx.px(self.row_height)
        ind = ctx.px(16)
        self.scroll = max(0, min(self.scroll, max(0, len(flat) - self.max_rows)))
        top = y + h - ctx.px(4)
        for i in range(self.scroll, min(len(flat), self.scroll + self.max_rows)):
            node, depth, has_kids = flat[i]
            ry = top - rh * (i - self.scroll + 1)
            sel = False
            if self.selected is not None:
                try:
                    sel = bool(self.selected(node))
                except Exception:
                    pass
            if sel:
                p.rect(x + ctx.px(4), ry + ctx.px(1), w - ctx.px(8), rh - ctx.px(2), fill=th.accent_soft, radius=ctx.px(6))
            elif i == self._hov:
                p.rect(x + ctx.px(4), ry + ctx.px(1), w - ctx.px(8), rh - ctx.px(2), fill=alpha(th.surface_3, 0.7),
                       radius=ctx.px(6))
            for d in range(depth):
                gx = x + ctx.px(13) + d * ind
                p.rect(gx, ry, ctx.px(1), rh, fill=alpha(th.border_strong, 0.7))
            cx = x + ctx.px(6) + depth * ind
            cy = ry + rh / 2
            if has_kids:
                open_ = str(node.id) in self.expanded
                p.icon("chevron_down" if open_ else "chevron_right", cx, cy - ctx.px(7), ctx.px(14), th.text_dim, 1.7)
            cx += ctx.px(17)
            if node.icon:
                p.icon(node.icon, cx, cy - ctx.px(7), ctx.px(14), th.accent if sel else th.text_dim, 1.5)
                cx += ctx.px(20)
            right = x + w - ctx.px(10) - ctx.px(22) * len(self.toggles)
            col = th.text if sel else (th.text_muted if node.muted else th.text_dim)
            p.text(node.label, cx, cy, th.fs_sm, col, "medium" if sel else "regular", valign="center",
                   max_w=right - cx)
            tx = x + w - ctx.px(8)
            for tg in reversed(self.toggles):
                tx -= ctx.px(22)
                try:
                    on = bool(tg.get(node))
                except Exception:
                    continue
                if on is None:
                    continue
                p.icon(tg.icons[0] if on else tg.icons[1], tx + ctx.px(4), cy - ctx.px(7), ctx.px(14),
                       th.text_dim if on else th.text_disabled, 1.5)


# ---------------------------------------------------------------------------
# Steps, ring progress
# ---------------------------------------------------------------------------

class Steps(Widget):
    """Vertical progress steps: [(title, description, state)], state = done | active | todo | error.
    Can be a function for live status."""

    def __init__(self, steps, **kw):
        super().__init__(**kw)
        self.steps = steps

    def _st(self):
        return [tuple(s) + ("todo",) * (3 - len(s)) for s in (_val(self.steps) or [])]

    def measure(self, ctx, avail_w):
        n = len(self._st())
        return self.resolve_width(ctx, avail_w), ctx.px(44) * n

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        steps = self._st()
        rh = ctx.px(44)
        for i, (title, desc, state) in enumerate(steps):
            ry = y + h - rh * (i + 1)
            cx = x + ctx.px(11)
            cy = ry + rh - ctx.px(13)
            c = {"done": th.accent, "active": th.accent, "error": th.danger}.get(state, th.text_disabled)
            if i < len(steps) - 1:
                nxt = steps[i + 1][2]
                p.rect(cx - ctx.px(1), ry - ctx.px(13) + ctx.px(2), ctx.px(2), rh - ctx.px(22),
                       fill=alpha(th.accent, 0.6) if state == "done" else th.border_strong)
            r = ctx.px(10)
            if state == "done":
                p.circle(cx, cy, r, fill=th.accent)
                p.icon("check", cx - ctx.px(6), cy - ctx.px(6), ctx.px(12), th.accent_text, 2.2)
            elif state == "active":
                t = time.perf_counter()
                mark_animating(slow=True)
                p.circle(cx, cy, r + ctx.px(3) + ctx.px(1.5) * math.sin(t * 4), fill=alpha(th.accent, 0.16))
                p.circle(cx, cy, r, fill=th.surface_2, border=th.accent, border_w=ctx.px(2))
                p.circle(cx, cy, ctx.px(3.5), fill=th.accent)
            elif state == "error":
                p.circle(cx, cy, r, fill=alpha(th.danger, 0.18), border=th.danger, border_w=ctx.px(1.5))
                p.icon("x", cx - ctx.px(5), cy - ctx.px(5), ctx.px(10), th.danger, 2.0)
            else:
                p.circle(cx, cy, r, fill=th.surface_1, border=th.border_strong, border_w=ctx.px(1.5))
                p.text(str(i + 1), cx, cy, th.fs_xs, th.text_muted, "semibold", align="center", valign="center")
            tx = cx + ctx.px(20)
            p.text(title, tx, cy, th.fs_md, th.text if state != "todo" else th.text_dim,
                   "semibold" if state == "active" else "medium", valign="center", max_w=x + w - tx)
            if desc:
                p.text(desc, tx, cy - ctx.px(16), th.fs_xs, th.text_muted, valign="center", max_w=x + w - tx)


class RingProgress(Widget):
    """Circular progress. value 0..1 (or a function), label under the percentage."""

    def __init__(self, value, label=None, size=72, thickness=7, kind="accent", **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self.value = value
        self.label = label
        self.size = size
        self.thickness = thickness
        self.kind = kind

    def natural_width(self, ctx):
        return ctx.px(self.size)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.size)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        c = {"success": th.success, "warning": th.warning, "danger": th.danger, "info": th.info}.get(self.kind,
                                                                                                    th.accent)
        v = max(0.0, min(1.0, float(_val(self.value) or 0)))
        f = self.anim("f", v, speed=8)
        s = ctx.px(self.size)
        cx, cy = x + w / 2, y + h / 2
        r = s / 2 - ctx.px(self.thickness) / 2 - ctx.px(1)
        p.arc(cx, cy, r, 0, math.tau, ctx.px(self.thickness), th.surface_3)
        if f > 0.001:
            p.arc(cx, cy, r, math.pi / 2 - math.tau * f, math.tau * f, ctx.px(self.thickness), c)
        p.text("%d%%" % round(v * 100), cx, cy + (ctx.px(5) if self.label else 0), th.fs_lg, th.text, "semibold",
               align="center", valign="center")
        if self.label:
            p.text(str(_val(self.label)), cx, cy - ctx.px(10), th.fs_xs, th.text_muted, align="center",
                   valign="center", max_w=s - ctx.px(16))


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------

_hist_cache = {}


def image_histogram(source, bins=64):
    """Histogram of an image file path or bpy Image: {"r": [...], "g": [...], "b": [...], "l": [...]}."""
    import bpy
    import numpy as np
    img = bpy.data.images.load(source, check_existing=True) if isinstance(source, str) else source
    key = (img.name, tuple(img.size), bins, img.is_dirty)
    hit = _hist_cache.get(key)
    if hit:
        return hit
    w, h = img.size
    if w == 0 or h == 0:
        return {}
    buf = np.empty(w * h * img.channels, dtype=np.float32)
    img.pixels.foreach_get(buf)
    px = buf.reshape(-1, img.channels)
    if len(px) > 200000:
        px = px[:: max(1, len(px) // 200000)]
    out = {}
    for name, ch in (("r", 0), ("g", 1), ("b", 2)):
        if ch < img.channels:
            hist, _e = np.histogram(np.clip(px[:, ch], 0, 1), bins=bins, range=(0, 1))
            out[name] = hist.astype(float).tolist()
    if img.channels >= 3:
        lum = 0.2126 * px[:, 0] + 0.7152 * px[:, 1] + 0.0722 * px[:, 2]
        hist, _e = np.histogram(np.clip(lum, 0, 1), bins=bins, range=(0, 1))
        out["l"] = hist.astype(float).tolist()
    _hist_cache[key] = out
    return out


class Histogram(Widget):
    """Histogram of an image (path or bpy Image) or of your own values.

        ui.Histogram(image="/path/render.png")            # RGB channels
        ui.Histogram(image=lambda: bpy.data.images.get("Render Result"), channels="l")
        ui.Histogram(values=lambda: my_bins)               # pre-binned counts
    """

    def __init__(self, image=None, values=None, channels="rgb", bins=64, height=90, **kw):
        super().__init__(height=height, **kw)
        self.image = image
        self.values = values
        self.channels = channels
        self.bins = bins

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height)

    def _data(self):
        if self.values is not None:
            return {"l": list(_val(self.values) or [])}
        src = _val(self.image)
        if src is None:
            return {}
        try:
            return image_histogram(src, self.bins)
        except Exception:
            return {}

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        p.rect(x, y, w, h, fill=th.surface_0, radius=ctx.px(th.r_md), border=th.border, border_w=ctx.px(1))
        data = self._data()
        chans = [c for c in self.channels if c in data]
        if not chans:
            p.text("No image", x + w / 2, y + h / 2, th.fs_sm, th.text_muted, align="center", valign="center")
            return
        peak = max(max(data[c]) for c in chans) or 1.0
        cols = {"r": (0.93, 0.36, 0.36, 1), "g": (0.40, 0.85, 0.45, 1), "b": (0.38, 0.55, 0.98, 1), "l": th.accent}
        pad = ctx.px(5)
        iw, ih = w - pad * 2, h - pad * 2
        for c in chans:
            vals = data[c]
            n = len(vals)
            bw = iw / n
            col = cols[c]
            for i, v in enumerate(vals):
                bh = (math.sqrt(v / peak)) * ih
                if bh > 0.5:
                    p.rect(x + pad + i * bw, y + pad, bw + 0.4, bh, fill=alpha(col, 0.42 if len(chans) > 1 else 0.6),
                           fill2=alpha(col, 0.18), flat=alpha(col, 0.35))
