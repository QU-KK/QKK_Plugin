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

"""Advanced inputs: color picker, vector field, range slider, knob, stepper, tag input, search field,
data (ID) picker, file path, hotkey recorder and toggle group.

All of them take bind= (a Blender property path or ui.Bind) like the basic widgets.
"""

import colorsys
import math
import time

from .core import Bind, Widget, call, mark_animating
from .draw import text_size
from .layout import Column, Row
from .theme import alpha, mix, lighten, to_hex, hex_color
from .widgets import (ValueMixin, TextEdit, TextInput, NumberField, IconButton, Label, _dim, _fmt,
                      _norm_items)


# ---------------------------------------------------------------------------
# color helpers
# ---------------------------------------------------------------------------

def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    c = max(0.0, c)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _rgba(c):
    c = tuple(c)
    return c + (1.0,) * (4 - len(c)) if len(c) < 4 else c[:4]


_recent = []


def _remember(c):
    c = tuple(round(v, 3) for v in c[:3]) + (1.0,)
    if c in _recent:
        _recent.remove(c)
    _recent.insert(0, c)
    del _recent[8:]


def _checker(p, x, y, w, h, s, radius=0):
    p.rect(x, y, w, h, fill=(0.85, 0.85, 0.85, 1), radius=radius, functional=True)
    p.push_clip(x, y, w, h)
    n = int(w // s) + 1
    m = int(h // s) + 1
    for i in range(n):
        for j in range(m):
            if (i + j) % 2:
                p.rect(x + i * s, y + j * s, s, s, fill=(0.62, 0.62, 0.62, 1))
    p.pop_clip()


# ---------------------------------------------------------------------------
# Color picker
# ---------------------------------------------------------------------------

class _SVArea(Widget):
    def __init__(self, panel, **kw):
        super().__init__(**kw)
        self.panel = panel

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return avail_w, avail_w * 0.62

    def on_press(self, ctx, ev):
        self.on_drag(ctx, ev)
        return True

    def on_drag(self, ctx, ev):
        x, y, w, h = self.rect
        pn = self.panel
        pn.s = max(0.0, min(1.0, (ev.x - x) / max(1.0, w)))
        pn.v = max(0.0, min(1.0, (ev.y - y) / max(1.0, h)))
        pn._changed()

    def on_release(self, ctx, ev, inside):
        self.panel._commit()

    def paint(self, ctx, p):
        x, y, w, h = self.rect
        pn = self.panel
        r = ctx.px(9)
        hue = colorsys.hsv_to_rgb(pn.h, 1, 1) + (1.0,)
        p.rect(x, y, w, h, fill=(1, 1, 1, 1), fill2=hue, angle=math.pi / 2, radius=r, functional=True)
        p.rect(x, y, w, h, fill=(0, 0, 0, 0), fill2=(0, 0, 0, 1), radius=r, functional=True)
        p.rect(x, y, w, h, radius=r, border=alpha((1, 1, 1, 1), 0.08), border_w=ctx.px(1))
        kx, ky = x + pn.s * w, y + pn.v * h
        kr = ctx.px(7)
        p.shadow(kx - kr, ky - kr, kr * 2, kr * 2, kr, (0, 0, 0, 0.5), ctx.px(4), functional=True)
        p.circle(kx, ky, kr, fill=pn.rgb() + (1.0,), border=(1, 1, 1, 1), border_w=ctx.px(2.2))


class _HueBar(Widget):
    def __init__(self, panel, mode="hue", **kw):
        super().__init__(**kw)
        self.panel = panel
        self.mode = mode

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return avail_w, ctx.px(14)

    def on_press(self, ctx, ev):
        self.on_drag(ctx, ev)
        return True

    def on_drag(self, ctx, ev):
        x, y, w, h = self.rect
        f = max(0.0, min(1.0, (ev.x - x - h / 2) / max(1.0, w - h)))
        if self.mode == "hue":
            self.panel.h = min(f, 0.9999)
        else:
            self.panel.a = f
        self.panel._changed()

    def on_release(self, ctx, ev, inside):
        self.panel._commit()

    def paint(self, ctx, p):
        x, y, w, h = self.rect
        pn = self.panel
        r = h / 2
        if self.mode == "hue":
            n = 6
            sw = w / n
            for i in range(n):
                c0 = colorsys.hsv_to_rgb(i / n, 1, 1) + (1.0,)
                c1 = colorsys.hsv_to_rgb((i + 1) / n % 1.0, 1, 1) + (1.0,)
                rad = (r, 0, 0, r) if i == 0 else ((0, r, r, 0) if i == n - 1 else 0)
                p.rect(x + i * sw - (0.5 if i else 0), y, sw + (1 if 0 < i < n - 1 else 0.5), h, fill=c0, fill2=c1,
                       angle=math.pi / 2, radius=rad, functional=True)
            f = pn.h
            kc = colorsys.hsv_to_rgb(pn.h, 1, 1) + (1.0,)
        else:
            _checker(p, x, y, w, h, h / 2, radius=r)
            c = pn.rgb()
            p.rect(x, y, w, h, fill=c + (0.0,), fill2=c + (1.0,), angle=math.pi / 2, radius=r, functional=True)
            f = pn.a
            kc = c + (1.0,)
        kx = x + r + (w - h) * f
        p.shadow(kx - r, y, r * 2, h, r, (0, 0, 0, 0.5), ctx.px(3), functional=True)
        p.circle(kx, y + h / 2, r - ctx.px(0.5), fill=kc, border=(1, 1, 1, 1), border_w=ctx.px(2.2))


class ColorPickerPanel(Column):
    """Saturation/value square, hue bar, optional alpha bar, hex field, eyedropper and recent colors.
    color is sRGB (r, g, b, a); on_change(color) fires while dragging, on_commit(color) on release."""

    def __init__(self, color=(1, 1, 1, 1), on_change=None, on_commit=None, show_alpha=False, eyedropper=True,
                 **kw):
        c = _rgba(color)
        self.h, self.s, self.v = colorsys.rgb_to_hsv(*c[:3])
        self.a = c[3]
        self.on_change = on_change
        self.on_commit = on_commit
        self.show_alpha = show_alpha
        self.sv = _SVArea(self)
        self.hue = _HueBar(self, "hue")
        self.alpha_bar = _HueBar(self, "alpha") if show_alpha else None
        self.hex = TextInput("#rrggbb", value=to_hex(c), clearable=False, on_submit=self._hex_submit)
        self.hex.height = 28
        tools = [self.hex]
        if eyedropper:
            tools.append(IconButton("target", variant="secondary", size="sm", tooltip="Eyedropper\nPick a color "
                                    "from the 3D viewport.", on_click=self._eyedrop))
        self.preview = _Swatch(lambda: self.rgb() + (self.a,), width=40, height=28)
        from .widgets import ColorSwatches
        self.recent = ColorSwatches(list(_recent) or [hex_color(h) for h in
                                                      ("#ffffff", "#9fbd97", "#6aa8e8", "#e8b25a", "#ec6a6a", "#1b1d20")],
                                    size=18, on_change=lambda v, w: self.set_color(v, commit=True))
        super().__init__(self.sv, self.hue, self.alpha_bar, Row(self.preview, *tools, gap=6), self.recent,
                         gap=10, padding=6, **kw)

    def rgb(self):
        return colorsys.hsv_to_rgb(self.h, self.s, self.v)

    def color(self):
        return self.rgb() + (self.a,)

    def set_color(self, c, commit=False):
        c = _rgba(c)
        h, s, v = colorsys.rgb_to_hsv(*c[:3])
        if s > 0.001 and v > 0.001:
            self.h = h
        if v > 0.001:
            self.s = s
        self.v = v
        self.a = c[3] if self.show_alpha else self.a
        self._changed()
        if commit:
            self._commit()

    def _changed(self):
        if not self.hex.focused:
            self.hex.text = self.hex._value = to_hex(self.rgb())
        call(self.on_change, self.color())
        self.redraw()

    def _commit(self):
        _remember(self.color())
        call(self.on_commit, self.color())

    def _hex_submit(self, text, field):
        try:
            self.set_color(hex_color(text.strip())[:3] + (self.a,), commit=True)
        except Exception:
            pass

    def _eyedrop(self, button):
        surf = self.get_surface()
        if surf is None:
            return
        app = surf.app
        surf.close_popover()
        app.pick_color(lambda c: self.set_color(c[:3] + (self.a,), commit=True))


class _Swatch(Widget):
    def __init__(self, color, **kw):
        super().__init__(**kw)
        self.color = color

    def natural_width(self, ctx):
        return ctx.px(self.width if isinstance(self.width, (int, float)) else 28)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height or 28)

    def paint(self, ctx, p):
        x, y, w, h = self.rect
        c = self.color() if callable(self.color) else self.color
        r = ctx.px(7)
        if c[3] < 1:
            _checker(p, x, y, w, h, ctx.px(5), radius=r)
        p.rect(x, y, w, h, fill=c, radius=r, border=alpha((1, 1, 1, 1), 0.14), border_w=ctx.px(1))


class ColorField(ValueMixin, Widget):
    """A color swatch + hex that opens the color picker.

    Bound to a Blender color property it reads and writes real data. Properties with subtype
    'COLOR' are stored in scene-linear space; they are converted so you see and pick sRGB colors
    just like Blender's own picker (pass linear=False/True to override)."""

    cursor = "HAND"

    def __init__(self, label=None, value=None, bind=None, on_change=None, show_alpha=None, linear=None, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change, (1.0, 1.0, 1.0))
        rna = self.bind.rna() if self.bind is not None else None
        if linear is None:
            linear = bool(rna is not None and rna.subtype == "COLOR")
        self.linear = linear
        size = rna.array_length if rna is not None else len(tuple(self._value))
        self.size = size
        self.show_alpha = (size == 4) if show_alpha is None else show_alpha
        if label is None and self.bind is not None:
            label = self.bind.label()
        self.label = label
        self._open = False

    def interactive(self):
        return True

    def display(self):
        v = tuple(self.value or (1, 1, 1))
        rgb = tuple(linear_to_srgb(c) for c in v[:3]) if self.linear else tuple(v[:3])
        return rgb + ((v[3],) if len(v) > 3 else (1.0,))

    def set_display(self, c):
        rgb = tuple(srgb_to_linear(x) for x in c[:3]) if self.linear else tuple(c[:3])
        v = rgb + ((c[3],) if self.size > 3 else ())
        self.set_value(v)

    def measure(self, ctx, avail_w):
        lab = ctx.px(20) if self.label else 0.0
        return self.resolve_width(ctx, avail_w), ctx.px(self.height or 32) + lab

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        return self.is_enabled

    def on_click(self, ctx, ev):
        if self._open:
            ctx.surface.close_popover()
            return
        panel = ColorPickerPanel(self.display(), on_change=self.set_display, show_alpha=self.show_alpha,
                                 on_commit=lambda c: self.bind.push_undo("Pick color") if self.bind else None)
        self._open = True

        def closed(*_):
            self._open = False
            self.redraw()
        ctx.surface.open_popover(panel, anchor=self, width=max(ctx.px(240), min(self.rect[2], ctx.px(300))),
                                 on_close=closed)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
            h -= ctx.px(20)
        hov = self.anim("hov", 1.0 if (self.hovered or self._open) else 0.0)
        r = ctx.px(9)
        p.rect(x, y, w, h, fill=mix(th.surface_3, th.surface_4, hov * 0.5), radius=r,
               border=mix(th.border_strong, alpha(th.accent, 0.6), 1.0 if self._open else hov * 0.4),
               border_w=ctx.px(1))
        c = self.display()
        sx, sy, ss = x + ctx.px(5), y + ctx.px(5), h - ctx.px(10)
        sw = ss * 1.6
        if c[3] < 1:
            _checker(p, sx, sy, sw, ss, ctx.px(4), radius=ctx.px(6))
        p.rect(sx, sy, sw, ss, fill=c, radius=ctx.px(6), border=alpha((1, 1, 1, 1), 0.15), border_w=ctx.px(1))
        tx = sx + sw + ctx.px(10)
        p.text(to_hex(c).upper(), tx, y + h / 2, th.fs_md, th.text, "medium", valign="center")
        if self.show_alpha:
            p.text("%d%%" % round(c[3] * 100), x + w - ctx.px(30), y + h / 2, th.fs_sm, th.text_muted,
                   align="right", valign="center")
        isz = ctx.px(13)
        p.icon("palette", x + w - ctx.px(10) - isz, y + h / 2 - isz / 2, isz, th.text_dim, 1.5)


# ---------------------------------------------------------------------------
# Vector field
# ---------------------------------------------------------------------------

AXIS_COLORS = ((0.93, 0.36, 0.40, 1.0), (0.55, 0.80, 0.32, 1.0), (0.36, 0.60, 0.95, 1.0), (0.75, 0.75, 0.78, 1.0))


class _AxisField(NumberField):
    def __init__(self, axis_color, **kw):
        super().__init__(**kw)
        self.axis_color = axis_color

    def paint(self, ctx, p):
        NumberField.paint(self, ctx, p)
        x, y, w, h = self.rect
        p.rect(x + ctx.px(1.5), y + h * 0.25, ctx.px(2.5), h * 0.5, fill=self.axis_color, radius=ctx.px(1.25))


class VectorField(Widget):
    """X / Y / Z (/ W) number fields with axis colors, for location, rotation, scale and other vectors.
    Lays out side by side, or stacked when the panel is narrow.

        ui.VectorField(bind="object.location")
        ui.VectorField(bind="object.rotation_euler")     # shown in degrees
        ui.VectorField(value=[0, 0, 1], labels="XYZ", on_change=lambda v, w: ...)
    """

    def __init__(self, label=None, value=None, bind=None, on_change=None, labels=None, precision=None, unit="",
                 step=None, stacked=None, min_field=92, **kw):
        super().__init__(**kw)
        if isinstance(bind, str):
            bind = Bind(bind)
        self.bind = bind
        self.on_change = on_change
        n = None
        rna = bind.rna() if bind is not None else None
        if rna is not None:
            n = rna.array_length
        self._value = list(value) if value is not None else [0.0] * (n or 3)
        n = n or len(self._value)
        labels = labels or ("XYZW" if n <= 4 else [str(i) for i in range(n)])
        if label is None and bind is not None:
            label = bind.label()
        self.label = label
        self.stacked = stacked
        self.min_field = min_field
        self.fields = []
        for i in range(n):
            b = Bind(bind.target, bind.attr, index=i) if bind is not None else None
            f = _AxisField(AXIS_COLORS[i % 4], label=labels[i], bind=b, precision=precision, unit=unit, step=step,
                           value=None if b else float(self._value[i]),
                           on_change=(lambda v, w, i=i: self._changed(i, v)))
            f.parent = self
            self.fields.append(f)
        self.title = Label(label, muted=True, size=11.5, weight="medium") if label else None
        if self.title:
            self.title.parent = self
        self._stack = False

    def _changed(self, i, v):
        self._value[i] = v
        call(self.on_change, tuple(self._value), self)

    @property
    def value(self):
        return tuple(f.value for f in self.fields)

    def children(self):
        return ([self.title] if self.title else []) + self.fields

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        g = ctx.px(6)
        self._stack = self.stacked if self.stacked is not None else \
            (w - g * (len(self.fields) - 1)) / len(self.fields) < ctx.px(self.min_field)
        fh = ctx.px(30)
        lab = ctx.px(20) if self.title else 0.0
        if self._stack:
            return w, lab + fh * len(self.fields) + ctx.px(2) * (len(self.fields) - 1)
        return w, lab + fh

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        top = y + h
        if self.title:
            self.title.measure(ctx, w)
            self.title.arrange(ctx, x, top - ctx.px(18), w, ctx.px(18))
            top -= ctx.px(20)
        fh = ctx.px(30)
        n = len(self.fields)
        if self._stack:
            for f in self.fields:
                f.measure(ctx, w)
                f.arrange(ctx, x, top - fh, w, fh)
                top -= fh + ctx.px(2)
        else:
            g = ctx.px(6)
            fw = (w - g * (n - 1)) / n
            for i, f in enumerate(self.fields):
                f.measure(ctx, fw)
                f.arrange(ctx, x + i * (fw + g), top - fh, fw, fh)

    def paint(self, ctx, p):
        for c in self.children():
            c.paint(ctx, p)


# ---------------------------------------------------------------------------
# Range slider
# ---------------------------------------------------------------------------

class RangeSlider(Widget):
    """Two handles for a min and max.

        ui.RangeSlider("Frames", bind=("scene.frame_start", "scene.frame_end"), min=1, max=250)
        ui.RangeSlider("Distance", value=(2, 8), min=0, max=20, on_change=lambda lo_hi, w: ...)
    """

    def __init__(self, label="", value=(0.25, 0.75), min=0.0, max=1.0, step=None, precision=None, unit="",
                 bind=None, on_change=None, integer=None, **kw):
        super().__init__(**kw)
        if bind is not None:
            if isinstance(bind, (tuple, list)):
                self.binds = [b if isinstance(b, Bind) else Bind(b) for b in bind]
            else:
                b = bind if isinstance(bind, Bind) else Bind(bind)
                self.binds = [Bind(b.target, b.attr, index=0), Bind(b.target, b.attr, index=1)]
        else:
            self.binds = None
        self._value = list(value)
        self.min, self.max = min, max
        self.step = step
        self.unit = unit
        self.label = label
        self.on_change = on_change
        v0 = self.value[0]
        self.integer = integer if integer is not None else isinstance(v0, int)
        self.precision = precision if precision is not None else (0 if self.integer else 2)
        self._drag = None

    @property
    def value(self):
        if self.binds:
            vals = [b.get(None) for b in self.binds]
            if None not in vals:
                return list(vals)
        return list(self._value)

    def _set(self, i, v):
        vals = self.value
        if i == 0:
            v = min(v, vals[1])
        else:
            v = max(v, vals[0])
        if self.integer:
            v = int(round(v))
        if vals[i] == v:
            return
        vals[i] = v
        self._value = vals
        if self.binds:
            # write in an order Blender accepts (e.g. frame_start <= frame_end)
            self.binds[i].set(v)
        call(self.on_change, tuple(vals), self)
        self.redraw()

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(40 if self.label else 22)

    def _track(self, ctx):
        x, y, w, h = self.rect
        kr = ctx.px(8)
        return x + kr, y + ctx.px(8), w - kr * 2, ctx.px(6)

    def _frac(self, v):
        r = self.max - self.min
        return 0.0 if r == 0 else max(0.0, min(1.0, (v - self.min) / r))

    def _val_at(self, ctx, ex):
        tx, ty, tw, th_ = self._track(ctx)
        f = max(0.0, min(1.0, (ex - tx) / max(1.0, tw)))
        v = self.min + (self.max - self.min) * f
        if self.step:
            v = round((v - self.min) / self.step) * self.step + self.min
        return v

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        tx, ty, tw, th_ = self._track(ctx)
        lo, hi = self.value
        x0 = tx + tw * self._frac(lo)
        x1 = tx + tw * self._frac(hi)
        self._drag = 0 if abs(ev.x - x0) <= abs(ev.x - x1) else 1
        if abs(x0 - x1) < 2 and ev.x > x1:
            self._drag = 1
        self._set(self._drag, self._val_at(ctx, ev.x))
        return True

    def on_drag(self, ctx, ev):
        if self._drag is not None:
            self._set(self._drag, self._val_at(ctx, ev.x))

    def on_release(self, ctx, ev, inside):
        self._drag = None
        if self.binds:
            self.binds[0].push_undo("Change " + (self.label or "range"))

    def on_nav(self, ctx, d):
        step = self.step or (self.max - self.min) / 100.0
        lo, hi = self.value
        self._set(1, min(self.max, hi + step * d))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        lo, hi = self.value
        hov = self.anim("hov", 1.0 if (self.hovered or self._drag is not None) else 0.0)
        txt = "%s – %s" % (_fmt(lo, self.precision, self.unit), _fmt(hi, self.precision, self.unit))
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
            vw = ctx.text_w(txt, th.fs_sm, "semibold") + ctx.px(12)
            vh = ctx.px(18)
            p.rect(x + w - vw, y + h - ctx.px(8) - vh / 2, vw, vh, fill=th.surface_3, radius=ctx.px(5),
                   border=th.border, border_w=ctx.px(1))
            p.text(txt, x + w - vw / 2, y + h - ctx.px(8), th.fs_sm, th.text, "semibold", align="center",
                   valign="center")
        tx, ty, tw, tht = self._track(ctx)
        p.rect(tx, ty, tw, tht, fill=th.surface_0, radius=tht / 2, border=th.border, border_w=ctx.px(1))
        f0 = self.anim("f0", self._frac(lo), speed=28)
        f1 = self.anim("f1", self._frac(hi), speed=28)
        x0, x1 = tx + tw * f0, tx + tw * f1
        p.shadow(x0, ty, x1 - x0, tht, tht / 2, alpha(th.accent, 0.25 * (0.5 + 0.5 * hov)), ctx.px(6))
        p.rect(x0, ty, max(tht, x1 - x0), tht, fill=th.accent_lo, fill2=th.accent_hi, angle=math.pi / 2,
               radius=tht / 2)
        for i, kx in enumerate((x0, x1)):
            kr = ctx.px(7) + ctx.px(1.5) * (1.0 if self._drag == i else hov * 0.5)
            ky = ty + tht / 2
            p.shadow(kx - kr, ky - kr, kr * 2, kr * 2, kr, (0, 0, 0, 0.45), ctx.px(4), dy=-ctx.px(1))
            p.circle(kx, ky, kr, fill=(0.96, 0.97, 0.98, 1.0), border=th.accent, border_w=ctx.px(2.5))


# ---------------------------------------------------------------------------
# Knob
# ---------------------------------------------------------------------------

class Knob(ValueMixin, Widget):
    """Round dial. Drag up/down (or left/right) to turn; Shift for fine; double-click resets.
    Angle properties are shown in degrees."""

    def __init__(self, label="", value=None, min=0.0, max=1.0, bind=None, on_change=None, size=58, precision=None,
                 unit="", default=None, **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self._init_value(value, bind, on_change, min)
        r = self.bind.range() if self.bind is not None else None
        self.subtype = None
        if r:
            if min == 0.0 and max == 1.0:
                min, max = r[0], r[1]
            self.subtype = r[4]
        if not label and self.bind is not None:
            label = self.bind.label()
        self.label = label
        self.min, self.max = min, max
        self.size = size
        self.integer = isinstance(self.value, int)
        self.precision = precision if precision is not None else (
            0 if self.integer or self.subtype in ("ANGLE", "EULER") else 2)
        self.unit = unit
        self.default = default if default is not None else self.value
        self._drag = None

    def interactive(self):
        return True

    def natural_width(self, ctx):
        return max(ctx.px(self.size), ctx.text_w(self.label, ctx.theme.fs_xs, "medium") + ctx.px(4))

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.size + 18)

    def _frac(self):
        r = self.max - self.min
        return 0.0 if r == 0 else max(0.0, min(1.0, (float(self.value or 0) - self.min) / r))

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        self._drag = (ev.x, ev.y, self._frac())
        return True

    def on_drag(self, ctx, ev):
        x0, y0, f0 = self._drag
        k = 0.1 if ev.shift else 1.0
        d = ((ev.y - y0) + (ev.x - x0)) / ctx.px(160) * k
        f = max(0.0, min(1.0, f0 + d))
        v = self.min + (self.max - self.min) * f
        self.set_value(int(round(v)) if self.integer else v)

    def on_release(self, ctx, ev, inside):
        self._drag = None
        if self.bind:
            self.bind.push_undo("Turn " + self.label)

    def on_double_click(self, ctx, ev):
        if self.default is not None:
            self.set_value(self.default)
        return True

    def on_nav(self, ctx, d):
        v = float(self.value or 0) + (self.max - self.min) / 100.0 * d
        self.set_value(max(self.min, min(self.max, v)))

    def on_wheel(self, ctx, ev):
        self.on_nav(ctx, ev.wheel)
        return True

    def paint(self, ctx, p):
        if self.subtype is None and self.bind is not None:
            r = self.bind.range()
            if r is not None:
                self.subtype = r[4]
                if self.subtype in ("ANGLE", "EULER"):
                    self.precision = 0
        th = ctx.theme
        x, y, w, h = self.rect
        s = ctx.px(self.size)
        cx, cy = x + w / 2, y + h - s / 2
        hov = self.anim("hov", 1.0 if (self.hovered or self._drag) else 0.0)
        f = self.anim("f", self._frac(), speed=26)
        r = s / 2 - ctx.px(5)
        start = math.radians(225)
        sweep = math.radians(270)
        p.arc(cx, cy, r + ctx.px(1), start - sweep, sweep, ctx.px(4), th.surface_0)
        if f > 0.001:
            p.arc(cx, cy, r + ctx.px(1), start - sweep * f, sweep * f, ctx.px(4), th.accent)
        ir = r - ctx.px(6)
        p.shadow(cx - ir, cy - ir, ir * 2, ir * 2, ir, (0, 0, 0, 0.45), ctx.px(6), dy=-ctx.px(2))
        p.circle(cx, cy, ir, fill=mix(th.surface_4, th.surface_3, 0.3 - 0.2 * hov), fill2=th.surface_2,
                 border=th.border_strong, border_w=ctx.px(1))
        ang = start - sweep * f
        p.line(cx + math.cos(ang) * ir * 0.35, cy + math.sin(ang) * ir * 0.35, cx + math.cos(ang) * ir * 0.78,
               cy + math.sin(ang) * ir * 0.78, ctx.px(2.4), th.accent)
        v = self.value if self.value is not None else 0
        p.text(_fmt(v, self.precision, self.unit, self.subtype), cx, y + ctx.px(18) + ctx.px(1), th.fs_xs, th.text,
               "semibold", align="center", valign="center")
        p.text(self.label, cx, y + ctx.px(5), th.fs_xs, th.text_muted, "medium", align="center", valign="center",
               max_w=w)


# ---------------------------------------------------------------------------
# Stepper
# ---------------------------------------------------------------------------

class Stepper(ValueMixin, Widget):
    """[-] value [+] for small whole numbers."""

    def __init__(self, label=None, value=None, min=0, max=99, step=1, bind=None, on_change=None, unit="", **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change, min)
        r = self.bind.range() if self.bind is not None else None
        if r and min == 0 and max == 99:
            min, max = r[0], r[1]
        if label is None and self.bind is not None:
            label = self.bind.label()
        self.label = label
        self.min, self.max, self.step, self.unit = min, max, step, unit
        self._hot = None

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(30)

    def _zone(self, ctx, ev):
        x, y, w, h = self.rect
        bw, vw = ctx.px(30), ctx.px(46)
        gx = x + w - bw * 2 - vw
        if ev.x >= x + w - bw:
            return "+"
        if gx <= ev.x <= gx + bw:
            return "-"
        return None

    def on_hover(self, ctx, ev):
        z = self._zone(ctx, ev)
        if z != self._hot:
            self._hot = z
            self.redraw()

    def on_leave(self, ctx):
        self._hot = None
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        z = self._zone(ctx, ev)
        if z:
            self.on_nav(ctx, 1 if z == "+" else -1)

    def on_nav(self, ctx, d):
        v = max(self.min, min(self.max, (self.value or 0) + self.step * (1 if d > 0 else -1)))
        if v != self.value:
            self.set_value(v)
            if self.bind:
                self.bind.push_undo("Change " + (self.label or ""))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        bw = ctx.px(30)
        vw = ctx.px(46)
        gx = x + w - bw * 2 - vw
        if self.label:
            p.text(self.label, x, y + h / 2, th.fs_md, th.text, valign="center", max_w=gx - x - ctx.px(6))
        p.rect(gx, y, bw * 2 + vw, h, fill=th.surface_0, radius=h / 2, border=th.border_strong, border_w=ctx.px(1))
        v = self.value or 0
        for sym, bx, ok in (("-", gx, v > self.min), ("+", gx + bw + vw, v < self.max)):
            hot = self._hot == sym
            if hot and ok:
                p.circle(bx + bw / 2, y + h / 2, h / 2 - ctx.px(3), fill=th.surface_4)
            isz = ctx.px(13)
            p.icon("minus" if sym == "-" else "plus", bx + bw / 2 - isz / 2, y + h / 2 - isz / 2, isz,
                   (th.text if hot else th.text_dim) if ok else th.text_disabled, 1.9)
        p.text(_fmt(v, 0, self.unit), gx + bw + vw / 2, y + h / 2, th.fs_md, th.text, "semibold", align="center",
               valign="center")


# ---------------------------------------------------------------------------
# Toggle group (multi-select)
# ---------------------------------------------------------------------------

class ToggleGroup(Widget):
    """Buttons where several can be on at once.

        ui.ToggleGroup([("X", "X"), ("Y", "Y"), ("Z", "Z")],
                       binds=["object.data.use_mirror_x", "object.data.use_mirror_y", "object.data.use_mirror_z"])
        ui.ToggleGroup(bind="scene.my.formats")          # EnumProperty(options={"ENUM_FLAG"})
        ui.ToggleGroup(items, value={"A", "C"}, on_change=lambda ids, w: ...)
    """

    def __init__(self, items=None, value=None, bind=None, binds=None, on_change=None, label=None, **kw):
        super().__init__(**kw)
        if isinstance(bind, str):
            bind = Bind(bind)
        self.bind = bind
        self.binds = [b if isinstance(b, Bind) else Bind(b) for b in binds] if binds else None
        if items is None and bind is not None:
            items = [(i, n, None, d) for i, n, d in bind.enum_items()]
        self.items = _norm_items(items or [])
        self._value = set(value or ())
        self.on_change = on_change
        self.label = label
        self._hov = -1
        self._slots = []

    @property
    def value(self):
        if self.binds:
            return {it[0] for it, b in zip(self.items, self.binds) if b.get(False)}
        if self.bind is not None:
            v = self.bind.get(None)
            if v is not None:
                return set(v)
        return set(self._value)

    def toggle(self, item_id):
        cur = self.value
        on = item_id not in cur
        if self.binds:
            i = [it[0] for it in self.items].index(item_id)
            self.binds[i].set(on)
            self.binds[i].push_undo("Toggle " + self.items[i][1])
        cur = cur | {item_id} if on else cur - {item_id}
        if self.bind is not None and not self.binds:
            self.bind.set(cur)
            self.bind.push_undo("Toggle")
        self._value = cur
        call(self.on_change, cur, self)
        self.redraw()

    def interactive(self):
        return True

    def natural_width(self, ctx):
        th = ctx.theme
        return sum(ctx.px(22) + (ctx.px(16) if it[2] else 0) + (ctx.text_w(it[1], th.fs_sm, "medium") if it[1] else 0)
                   for it in self.items) + ctx.px(4) * len(self.items)

    def measure(self, ctx, avail_w):
        lab = ctx.px(20) if self.label else 0.0
        return self.resolve_width(ctx, avail_w), ctx.px(30) + lab

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        n = max(1, len(self.items))
        g = ctx.px(4)
        bh = ctx.px(30)
        bw = (w - g * (n - 1)) / n
        self._slots = [(x + i * (bw + g), y, bw, bh) for i in range(n)]

    def _at(self, ev):
        for i, (sx, sy, sw, sh) in enumerate(self._slots):
            if sx <= ev.x <= sx + sw and sy <= ev.y <= sy + sh:
                return i
        return -1

    def on_hover(self, ctx, ev):
        i = self._at(ev)
        if i != self._hov:
            self._hov = i
            self.redraw()

    def on_leave(self, ctx):
        self._hov = -1
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        i = self._at(ev)
        if i >= 0:
            self.toggle(self.items[i][0])

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
        val = self.value
        for i, (it, (sx, sy, sw, sh)) in enumerate(zip(self.items, self._slots)):
            on = it[0] in val
            t = self.anim("o%d" % i, 1.0 if on else 0.0)
            hov = 1.0 if i == self._hov else 0.0
            fill = mix(mix(th.surface_3, th.surface_4, hov * 0.6), th.accent_soft, t)
            border = mix(th.border_strong, alpha(th.accent, 0.6), t)
            p.rect(sx, sy, sw, sh, fill=fill, radius=ctx.px(8), border=border, border_w=ctx.px(1))
            col = mix(th.text_dim, th.accent, t)
            iw = ctx.px(14) if it[2] else 0.0
            lw = ctx.text_w(it[1], th.fs_sm, "semibold") if it[1] else 0.0
            gap = ctx.px(5) if (it[2] and it[1]) else 0.0
            cx = sx + (sw - iw - gap - lw) / 2
            if it[2]:
                p.icon(it[2], cx, sy + sh / 2 - iw / 2, iw, col, 1.6)
            if it[1]:
                p.text(it[1], cx + iw + gap, sy + sh / 2, th.fs_sm, col, "semibold", valign="center",
                       max_w=sw - ctx.px(6))


# ---------------------------------------------------------------------------
# Tag input
# ---------------------------------------------------------------------------

class TagInput(ValueMixin, TextEdit, Widget):
    """Type words; Enter or comma turns them into removable chips. Backspace on an empty field
    removes the last tag. Bound to a StringProperty it stores "a, b, c"."""

    focusable = True
    cursor = "TEXT"
    text_entry = True

    def __init__(self, placeholder="Add tag…", value=None, bind=None, on_change=None, label=None, max_tags=None,
                 **kw):
        super().__init__(**kw)
        self._init_value(None, bind, on_change, "")
        if value is not None:
            self._value = ", ".join(value)
        self._te_init("")
        self.placeholder = placeholder
        self.label = label
        self.max_tags = max_tags
        self._chips = []
        self._entry = (0, 0, 0)
        self._hov_x = -1

    @property
    def tags(self):
        raw = self.value
        if isinstance(raw, (list, tuple, set)):
            return [str(t) for t in raw]
        return [t.strip() for t in str(raw or "").split(",") if t.strip()]

    def set_tags(self, tags):
        out = []
        for t in tags:
            if t and t not in out:
                out.append(t)
        self.set_value(", ".join(out))
        if self.bind:
            self.bind.push_undo("Edit tags")

    def interactive(self):
        return True

    def _layout(self, ctx, w):
        th = ctx.theme
        pad = ctx.px(6)
        ch = ctx.px(22)
        g = ctx.px(5)
        x, line = pad, 0
        chips = []
        for t in self.tags:
            cw = ctx.text_w(t, th.fs_sm, "medium") + ctx.px(30)
            cw = min(cw, w - pad * 2)
            if x + cw > w - pad and x > pad:
                x, line = pad, line + 1
            chips.append((t, x, line, cw))
            x += cw + g
        ew = max(ctx.px(60), ctx.text_w(self.text or self.placeholder, th.fs_md) + ctx.px(8))
        if x + ew > w - pad and x > pad:
            x, line = pad, line + 1
        return chips, (x, line, w - pad - x), line + 1

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        _c, _e, lines = self._layout(ctx, w)
        lab = ctx.px(20) if self.label else 0.0
        return w, lab + ctx.px(6) * 2 + lines * ctx.px(22) + (lines - 1) * ctx.px(5)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        chips, entry, lines = self._layout(ctx, w)
        top = y + h - (ctx.px(20) if self.label else 0.0) - ctx.px(6)
        lh = ctx.px(22) + ctx.px(5)
        self._chips = [(t, x + cx, top - (ln + 1) * lh + ctx.px(5), cw, ctx.px(22)) for t, cx, ln, cw in chips]
        ex, eln, ew = entry
        self._entry = (x + ex, top - (eln + 1) * lh + ctx.px(5), ew, ctx.px(22))

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        for t, cx, cy, cw, chh in self._chips:
            if cx + cw - ctx.px(20) <= ev.x <= cx + cw and cy <= ev.y <= cy + chh:
                self.set_tags([x for x in self.tags if x != t])
                return True
        return True

    def _add(self):
        t = self.text.strip().strip(",").strip()
        if t:
            tags = self.tags
            if self.max_tags is None or len(tags) < self.max_tags:
                self.set_tags(tags + [t])
        self.text = ""
        self.caret = self.anchor = 0

    def on_blur(self, ctx):
        self._add()

    def on_key(self, ctx, ev):
        if ev.type in ("RET", "NUMPAD_ENTER") or ev.unicode == ",":
            self._add()
            self.redraw()
            return True
        if ev.type == "BACK_SPACE" and not self.text and self.tags:
            self.set_tags(self.tags[:-1])
            return True
        if ev.type == "ESC":
            ctx.surface.set_focus(None)
            return True
        r = self.te_key(ctx, ev, False)
        self.redraw()
        return r is not None or bool(ev.unicode)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
            h -= ctx.px(20)
        foc = self.anim("foc", 1.0 if self.focused else 0.0)
        p.rect(x, y, w, h, fill=th.surface_0, radius=ctx.px(9),
               border=mix(th.border_strong, th.border_focus, foc), border_w=ctx.px(1))
        for t, cx, cy, cw, chh in self._chips:
            p.rect(cx, cy, cw, chh, fill=th.accent_soft, radius=chh / 2, border=alpha(th.accent, 0.35),
                   border_w=ctx.px(1))
            p.text(t, cx + ctx.px(9), cy + chh / 2, th.fs_sm, th.accent, "medium", valign="center",
                   max_w=cw - ctx.px(28))
            isz = ctx.px(10)
            p.icon("x", cx + cw - ctx.px(15), cy + chh / 2 - isz / 2, isz, th.accent, 1.8)
        ex, ey, ew, eh = self._entry
        fpx = ctx.px(th.fs_md)
        if not self.text and not self.focused:
            p.text(self.placeholder, ex + ctx.px(2), ey + eh / 2, th.fs_md, th.text_muted, valign="center", max_w=ew)
        else:
            p.text(self.text, ex + ctx.px(2), ey + eh / 2, th.fs_md, th.text, valign="center")
            if self.focused and (int((time.perf_counter() - self._blink0) / 0.53) % 2) == 0:
                cw = text_size(self.text[:self.caret], fpx, "regular")[0]
                p.rect(ex + ctx.px(2) + cw, ey + eh / 2 - fpx * 0.62, ctx.px(1.5), fpx * 1.24, fill=th.accent)


# ---------------------------------------------------------------------------
# Search field with suggestions
# ---------------------------------------------------------------------------

class SearchField(TextInput):
    """A text field that suggests matches while you type.

    suggestions: list of strings / (id, label, icon, description), or a function(query) -> list.
    on_pick(id, field) runs when a suggestion is chosen (Enter, click)."""

    def __init__(self, placeholder="Search…", suggestions=(), on_pick=None, max_results=8, min_chars=1,
                 fill_on_pick=True, **kw):
        kw.setdefault("icon", "search")
        super().__init__(placeholder, **kw)
        self.suggestions = suggestions
        self.on_pick = on_pick
        self.max_results = max_results
        self.min_chars = min_chars
        self.fill_on_pick = fill_on_pick
        self._pop = None
        self._menu = None

    def _matches(self):
        q = self.text.strip().lower()
        if len(q) < self.min_chars:
            return []
        src = self.suggestions(q) if callable(self.suggestions) else self.suggestions
        items = _norm_items(src)
        if not callable(self.suggestions):
            starts = [it for it in items if it[1].lower().startswith(q)]
            rest = [it for it in items if q in it[1].lower() and it not in starts]
            items = starts + rest
        return items[:self.max_results]

    def _update_popup(self, ctx):
        from .overlays import Menu
        items = self._matches()
        surf = ctx.surface
        if not items:
            self._close_popup(surf)
            return
        if self._pop is not None and self._pop in surf.overlays:
            self._menu.all_items = self._menu.items = Menu(items).items
            self._menu._kb = 0
            return
        self._menu = Menu(items, on_pick=self._picked)
        surf.close_popover()
        from .overlays import Popover
        pop = Popover(self._menu, anchor=self, width=self.rect[2])
        self._pop = surf.add_overlay(pop)

    def _close_popup(self, surf):
        if self._pop is not None and surf is not None and self._pop in surf.overlays:
            surf.remove_overlay(self._pop)
        self._pop = None

    def _picked(self, item_id):
        label = item_id
        for it in self._menu.items:
            if getattr(it, "id", None) == item_id:
                label = it.label
        if self.fill_on_pick:
            self.text = label
            self.caret = self.anchor = len(label)
            self.set_value(label)
        self._pop = None
        call(self.on_pick, item_id, self)

    def on_key(self, ctx, ev):
        if self._pop is not None and self._pop in ctx.surface.overlays:
            if ev.type in ("DOWN_ARROW", "UP_ARROW"):
                self._menu.on_key(ctx, ev)
                return True
            if ev.type in ("RET", "NUMPAD_ENTER"):
                self._menu._pick(self._menu._kb, ctx)
                return True
            if ev.type == "ESC":
                self._close_popup(ctx.surface)
                return True
        before = self.text
        r = super().on_key(ctx, ev)
        if self.text != before and self.focused:
            self._update_popup(ctx)
        return r

    def on_blur(self, ctx):
        super().on_blur(ctx)


# ---------------------------------------------------------------------------
# Data (ID) picker
# ---------------------------------------------------------------------------

_ID_ICONS = {"MESH": "cube", "CURVE": "brush", "SURFACE": "sphere", "META": "sphere", "FONT": "edit",
             "ARMATURE": "person", "LATTICE": "grid", "EMPTY": "target", "GPENCIL": "brush", "GREASEPENCIL": "brush",
             "CAMERA": "camera", "LIGHT": "light", "SPEAKER": "bell", "LIGHT_PROBE": "sun", "VOLUME": "layers",
             "POINTCLOUD": "dots", "CURVES": "brush"}
_COLL_ICONS = {"materials": "sphere", "images": "image", "collections": "folder", "node_groups": "layers",
               "worlds": "globe", "texts": "edit", "cameras": "camera", "lights": "light", "meshes": "mesh",
               "actions": "play", "scenes": "home", "textures": "palette", "brushes": "brush"}
POINTER_COLLECTIONS = {"Object": "objects", "Material": "materials", "Image": "images", "Collection": "collections",
                       "Mesh": "meshes", "Camera": "cameras", "Light": "lights", "World": "worlds",
                       "Texture": "textures", "NodeTree": "node_groups", "Action": "actions", "Scene": "scenes",
                       "Text": "texts", "Curve": "curves", "Armature": "armatures", "Brush": "brushes"}


def id_icon(idb, collection=None):
    t = getattr(idb, "type", None)
    if collection == "objects" or (t in _ID_ICONS and hasattr(idb, "matrix_world")):
        return _ID_ICONS.get(t, "cube")
    return _COLL_ICONS.get(collection, "cube")


class DataPicker(ValueMixin, Widget):
    """Pick a Blender data-block (object, material, image, collection...) from a searchable list,
    or with the eyedropper (objects: click one in the viewport).

        ui.DataPicker(bind="scene.my_props.target")                 # PointerProperty(type=Object)
        ui.DataPicker(collection="materials", on_change=lambda mat, w: ...)
        ui.DataPicker(collection="objects", filter=lambda o: o.type == "CAMERA", label="Camera")
        ui.DataPicker(bind="scene.camera")                           # Blender's own pointer
    """

    cursor = "HAND"

    def __init__(self, label=None, value=None, bind=None, on_change=None, collection=None, filter=None,
                 placeholder="None", allow_none=True, eyedropper=None, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change)
        rna = self.bind.rna() if self.bind is not None else None
        self.by_name = rna is not None and rna.type == "STRING"
        if collection is None and rna is not None and rna.type == "POINTER":
            collection = POINTER_COLLECTIONS.get(rna.fixed_type.identifier, "objects")
        self.collection = collection or "objects"
        self.filter = filter
        if label is None and self.bind is not None:
            label = self.bind.label()
        self.label = label
        self.placeholder = placeholder
        self.allow_none = allow_none
        self.eyedropper = (self.collection in ("objects",)) if eyedropper is None else eyedropper
        self._open = False
        self._hot = None

    def source(self):
        import bpy
        c = self.collection
        if callable(c):
            items = list(c())
        elif c == "scene_objects":
            items = list(bpy.context.scene.objects)
        else:
            items = list(getattr(bpy.data, c, []))
        if self.filter:
            items = [i for i in items if self.filter(i)]
        return items

    def current(self):
        v = self.value
        if self.by_name or isinstance(v, str):
            for i in self.source():
                if i.name == v:
                    return i
            return None
        return v

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        lab = ctx.px(20) if self.label else 0.0
        return self.resolve_width(ctx, avail_w), ctx.px(32) + lab

    def _field(self, ctx):
        x, y, w, h = self.rect
        return x, y, w, h - (ctx.px(20) if self.label else 0.0)

    def _zone(self, ctx, ev):
        x, y, w, h = self._field(ctx)
        right = x + w
        if self.eyedropper and ev.x > right - ctx.px(30):
            return "pick"
        right -= ctx.px(30) if self.eyedropper else 0
        if self.allow_none and self.current() is not None and ev.x > right - ctx.px(26):
            return "clear"
        return "open"

    def on_hover(self, ctx, ev):
        z = self._zone(ctx, ev)
        if z != self._hot:
            self._hot = z
            self.redraw()

    def on_leave(self, ctx):
        self._hot = None
        self.redraw()

    def on_press(self, ctx, ev):
        return self.is_enabled

    def _assign(self, idb):
        if self.by_name:
            self.set_value(idb.name if idb is not None else "")
        else:
            self.set_value(idb)
        if self.bind:
            self.bind.push_undo("Set " + (self.label or "data"))

    def on_click(self, ctx, ev):
        z = self._zone(ctx, ev)
        if z == "pick":
            ctx.surface.app.pick_object(self._assign, filter=self.filter)
            return
        if z == "clear":
            self._assign(None)
            return
        if self._open:
            ctx.surface.close_popover()
            return
        from .overlays import Menu, MenuItem
        items = []
        lookup = {}
        for idb in self.source():
            key = idb.name_full if hasattr(idb, "name_full") else idb.name
            lookup[key] = idb
            items.append(MenuItem(idb.name, icon=id_icon(idb, self.collection if not callable(self.collection) else None),
                                  id=key, description=getattr(idb, "library", None) and "Linked" or None))
        if self.allow_none:
            items.insert(0, MenuItem("None", icon="x", id="__none__"))
        cur = self.current()

        def pick(key):
            self._assign(None if key == "__none__" else lookup.get(key))
        self._open = True

        def closed(*_):
            self._open = False
            self.redraw()
        menu = Menu(items, value=(cur.name_full if cur is not None and hasattr(cur, "name_full") else None),
                    on_pick=pick, searchable=len(items) > 6)
        ctx.surface.open_popover(menu, anchor=self, width=max(self.rect[2], ctx.px(200)), on_close=closed)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
        x, y, w, h = self._field(ctx)
        hov = self.anim("hov", 1.0 if (self.hovered or self._open) else 0.0)
        p.rect(x, y, w, h, fill=mix(th.surface_3, th.surface_4, hov * 0.5), radius=ctx.px(9),
               border=mix(th.border_strong, alpha(th.accent, 0.55), 1.0 if self._open else hov * 0.4),
               border_w=ctx.px(1))
        cur = self.current()
        cx = x + ctx.px(10)
        cy = y + h / 2
        isz = ctx.px(15)
        right = x + w - ctx.px(8)
        if self.eyedropper:
            hot = self._hot == "pick"
            bx = x + w - ctx.px(30)
            p.rect(bx, y + ctx.px(1), ctx.px(29), h - ctx.px(2), fill=th.surface_4 if hot else alpha(th.surface_4, 0.0),
                   radius=(0, ctx.px(8), ctx.px(8), 0))
            p.rect(bx, y + ctx.px(6), ctx.px(1), h - ctx.px(12), fill=th.border_strong)
            p.icon("target", bx + ctx.px(8), cy - ctx.px(7), ctx.px(14), th.accent if hot else th.text_dim, 1.5)
            right = bx - ctx.px(4)
        if cur is not None:
            p.icon(id_icon(cur, self.collection if not callable(self.collection) else None), cx, cy - isz / 2, isz,
                   th.accent, 1.5)
            if self.allow_none:
                hot = self._hot == "clear"
                p.icon("x", right - ctx.px(16), cy - ctx.px(6), ctx.px(12), th.text if hot else th.text_muted, 1.7)
                right -= ctx.px(22)
            p.text(cur.name, cx + isz + ctx.px(8), cy, th.fs_md, th.text, "medium", valign="center",
                   max_w=right - cx - isz - ctx.px(8))
        else:
            p.icon("search", cx, cy - isz / 2, isz, th.text_muted, 1.5)
            p.text(self.placeholder, cx + isz + ctx.px(8), cy, th.fs_md, th.text_muted, valign="center",
                   max_w=right - cx - isz)


# ---------------------------------------------------------------------------
# File path
# ---------------------------------------------------------------------------

class FilePathField(Column):
    """Text field + folder button that opens Blender's file browser.

        ui.FilePathField(bind="scene.render.filepath", mode="DIR")
        ui.FilePathField(label="Reference", filter="*.png;*.jpg", on_change=lambda path, w: ...)
    mode: "FILE" or "DIR". relative=True stores "//relative/paths" like Blender does."""

    def __init__(self, label=None, value="", bind=None, on_change=None, mode="FILE", filter="*", relative=False,
                 placeholder=None, **kw):
        if isinstance(bind, str):
            bind = Bind(bind)
        if label is None and bind is not None:
            label = bind.label()
        self.mode = mode
        self.filter = filter
        self.relative = relative
        self.field = TextInput(placeholder or ("Choose a folder…" if mode == "DIR" else "Choose a file…"),
                               value=value, bind=bind, on_change=on_change, icon="folder" if mode == "DIR" else "file",
                               clearable=True)
        self.btn = IconButton("folder", variant="secondary", tooltip="Browse\nOpen Blender's file browser.",
                              on_click=self._browse)
        items = []
        if label:
            items.append(Label(label, muted=True, size=11.5, weight="medium"))
        items.append(Row(self.field, self.btn, gap=6))
        super().__init__(*items, gap=4, **kw)

    @property
    def value(self):
        return self.field.value

    def _browse(self, button):
        app = self.app
        if app is None:
            return

        def done(paths):
            import bpy
            path = paths[0] if paths else ""
            if self.relative and path:
                try:
                    path = bpy.path.relpath(path)
                except Exception:
                    pass
            self.field.set_value(path)
            self.field.text = path
            if self.field.bind:
                self.field.bind.push_undo("Set path")
        import bpy
        start = self.field.value or ""
        try:
            start = bpy.path.abspath(start)
        except Exception:
            pass
        app.browse(done, mode=self.mode, filter=self.filter, start=start)


# ---------------------------------------------------------------------------
# Hotkey field
# ---------------------------------------------------------------------------

class HotkeyField(Widget):
    """Shows a key combination as key caps. Click, then press keys to record a new one;
    Backspace clears, Esc cancels.

        ui.HotkeyField(action="command_palette")          # edits the app action's real keymap entry
        ui.HotkeyField(value="ctrl+shift+K", on_change=lambda combo, w: ...)
    """

    focusable = True
    cursor = "HAND"

    def __init__(self, label=None, value=None, action=None, on_change=None, **kw):
        super().__init__(**kw)
        from .actions import Hotkey
        self._value = Hotkey.parse(value) if value else None
        self.action = action
        self.label = label
        self.on_change = on_change

    @property
    def text_entry(self):
        return self.focused

    def _app(self, ctx):
        return ctx.surface.app if ctx is not None else None

    def hotkey(self, ctx=None):
        if self.action and ctx is not None:
            return self._app(ctx).hotkey_of(self.action)
        return self._value

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(32)

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_key(self, ctx, ev):
        from .actions import Hotkey
        t = ev.type
        if t == "ESC":
            ctx.surface.set_focus(None)
            return True
        if t in ("BACK_SPACE", "DEL") and not (ev.ctrl or ev.shift or ev.alt or ev.oskey):
            self._set(ctx, None)
            return True
        if t in ("LEFTMOUSE", "RIGHTMOUSE", "MIDDLEMOUSE"):
            return False
        hk = Hotkey(t, bool(ev.ctrl), bool(ev.shift), bool(ev.alt), bool(ev.oskey))
        self._set(ctx, hk)
        return True

    def _set(self, ctx, hk):
        self._value = hk
        if self.action:
            self._app(ctx).set_hotkey(self.action, hk.combo() if hk else None)
        call(self.on_change, hk.combo() if hk else None, self)
        ctx.surface.set_focus(None)
        self.redraw()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        hov = self.anim("hov", 1.0 if self.hovered else 0.0)
        rec = self.anim("rec", 1.0 if self.focused else 0.0)
        cx = x
        if self.label:
            p.text(self.label, x, y + h / 2, th.fs_md, th.text, valign="center", max_w=w * 0.5)
        hk = self.hotkey(ctx)
        parts = hk.parts() if hk and not hk.empty else []
        fs = th.fs_sm
        if self.focused:
            msg = "Press keys…"
            mw = ctx.text_w(msg, fs, "medium") + ctx.px(20)
            bx = x + w - mw
            p.rect(bx, y + ctx.px(3), mw, h - ctx.px(6), fill=th.accent_soft, radius=ctx.px(7),
                   border=alpha(th.accent, 0.6 + 0.3 * math.sin(time.perf_counter() * 6)), border_w=ctx.px(1.2))
            mark_animating()
            p.text(msg, bx + mw / 2, y + h / 2, fs, th.accent, "medium", align="center", valign="center")
            return
        if not parts:
            p.text("Not set", x + w, y + h / 2, fs, th.text_muted, align="right", valign="center")
            return
        widths = [max(ctx.px(22), ctx.text_w(k, fs, "semibold") + ctx.px(14)) for k in parts]
        total = sum(widths) + ctx.px(4) * (len(widths) - 1)
        kx = x + w - total
        kh = h - ctx.px(8)
        for k, kw_ in zip(parts, widths):
            ky = y + ctx.px(4)
            p.rect(kx, ky, kw_, kh, fill=th.border_strong, radius=ctx.px(6))
            p.rect(kx, ky + ctx.px(2), kw_, kh - ctx.px(2), fill=mix(th.surface_3, th.surface_4, hov), radius=ctx.px(6),
                   border=alpha((1, 1, 1, 1), 0.06), border_w=ctx.px(1))
            p.text(k, kx + kw_ / 2, ky + kh / 2 + ctx.px(1), fs, th.text, "semibold", align="center", valign="center")
            kx += kw_ + ctx.px(4)
