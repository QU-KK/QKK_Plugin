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

"""Uzima UI controls."""

import math
import time

from .core import Bind, Widget, call
from .draw import ellipsize, text_size, wrap_text
from .theme import alpha, lighten, mix


def _dim(c, enabled, bg=(0.12, 0.13, 0.14, 1.0)):
    return c if enabled else mix(c, bg, 0.55)


# ---------------------------------------------------------------------------
# Value helper
# ---------------------------------------------------------------------------

class ValueMixin:
    """Gives a widget `value` that is either local or bound to a Blender property."""

    def _init_value(self, value, bind, on_change, default=None):
        if isinstance(bind, str):
            bind = Bind(bind)
        self.bind = bind
        self._value = value if value is not None else default
        self.on_change = on_change

    def _form(self):
        w = self.parent
        while w is not None:
            if getattr(w, "_uz_form", False) and w.buffered:
                return w
            w = w.parent
        return None

    @property
    def value(self):
        if self.bind is not None:
            f = self._form()
            if f is not None and id(self.bind) in f._staged:
                return f._staged[id(self.bind)][1]
            v = self.bind.get(None)
            if v is not None:
                return v
        return self._value

    @value.setter
    def value(self, v):
        self.set_value(v)

    def set_value(self, v, notify=True):
        if self.bind is not None:
            f = self._form()
            if f is not None:
                self.bind._in_form = f
                f._stage(self.bind, v)
            else:
                self.bind.set(v)
        self._value = v
        if notify:
            call(self.on_change, v, self)
        self.redraw()


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

class Label(Widget):
    """Text. `wrap=True` wraps to the available width."""

    def __init__(self, text="", size=None, color=None, weight="regular", align="left", wrap=False,
                 muted=False, icon=None, icon_color=None, line_height=1.45, **kw):
        kw.setdefault("width", None)
        super().__init__(**kw)
        self.text = text
        self.size = size
        self.color = color
        self.weight = weight
        self.text_align = align
        self.wrap = wrap
        self.muted = muted
        self.icon = icon
        self.icon_color = icon_color
        self.line_height = line_height
        self._lines = []

    def _size(self, ctx):
        return self.size if self.size is not None else ctx.theme.fs_md

    def _text(self):
        return self.text() if callable(self.text) else str(self.text)

    def natural_width(self, ctx):
        iw = ctx.px(self._size(ctx) + 6) if self.icon else 0.0
        return ctx.text_w(self._text(), self._size(ctx), self.weight) + iw + 1

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        s = self._size(ctx)
        lh = ctx.px(s) * self.line_height
        if self.wrap:
            iw = ctx.px(s + 6) if self.icon else 0.0
            self._lines = wrap_text(self._text(), ctx.px(s), max(10.0, w - iw), self.weight)
            return w, lh * len(self._lines)
        h = ctx.px(self.height) if self.height is not None else lh
        return w, h

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        s = self._size(ctx)
        col = th.color(self.color) or (th.text_muted if self.muted else th.text)
        col = _dim(col, self.is_enabled)
        if self.icon:
            isz = ctx.px(s + 1)
            ly = y + h - ctx.px(s) * self.line_height / 2 if self.wrap else y + h / 2
            p.icon(self.icon, x, ly - isz / 2, isz, self.icon_color or col, 1.5)
            x += isz + ctx.px(5)
            w -= isz + ctx.px(5)
        if self.wrap:
            lh = ctx.px(s) * self.line_height
            top = y + h
            for line, _i in self._lines:
                p.text(line.rstrip(), x, top - lh / 2, s, col, self.weight, valign="center")
                top -= lh
            return
        tx = x
        if self.text_align == "center":
            tx = x + w / 2
        elif self.text_align == "right":
            tx = x + w
        p.text(self._text(), tx, y + h / 2, s, col, self.weight, align=self.text_align,
               valign="center", max_w=w)


class Heading(Widget):
    """Title with optional subtitle and an eyebrow label."""

    def __init__(self, title, subtitle=None, eyebrow=None, size=None, **kw):
        super().__init__(**kw)
        self.title = title
        self.subtitle = subtitle
        self.eyebrow = eyebrow
        self.size = size

    def measure(self, ctx, avail_w):
        th = ctx.theme
        w = self.resolve_width(ctx, avail_w)
        s = self.size or th.fs_xl
        h = ctx.px(s * 1.35)
        if self.subtitle:
            self._sub = wrap_text(self.subtitle, ctx.px(th.fs_sm), w, "regular")
            h += ctx.px(th.fs_sm * 1.5) * len(self._sub) + ctx.px(2)
        if self.eyebrow:
            h += ctx.px(th.fs_xs * 1.8)
        return w, h

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        top = y + h
        s = self.size or th.fs_xl
        if self.eyebrow:
            lh = ctx.px(th.fs_xs * 1.8)
            p.text(self.eyebrow.upper(), x, top - lh / 2, th.fs_xs, th.accent, "semibold", valign="center")
            top -= lh
        lh = ctx.px(s * 1.35)
        p.text(self.title, x, top - lh / 2, s, th.text, "semibold", valign="center", max_w=w)
        top -= lh + ctx.px(2)
        if self.subtitle:
            lh = ctx.px(th.fs_sm * 1.5)
            for line, _i in self._sub:
                p.text(line.rstrip(), x, top - lh / 2, th.fs_sm, th.text_muted, valign="center")
                top -= lh


class Icon(Widget):
    def __init__(self, name, size=16, color=None, stroke=1.6, **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self.name = name
        self.size = size
        self.color = color
        self.stroke = stroke

    def natural_width(self, ctx):
        return ctx.px(self.size)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.size)

    def paint(self, ctx, p):
        x, y, w, h = self.rect
        s = ctx.px(self.size)
        p.icon(self.name, x + (w - s) / 2, y + (h - s) / 2, s, ctx.theme.color(self.color) or ctx.theme.text, self.stroke)


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

_SIZES = {"xs": (22, 10.5, 12), "sm": (26, 11.5, 14), "md": (32, 12.5, 15), "lg": (40, 13.5, 16),
          "xl": (56, 14.5, 17)}


class Button(Widget):
    """Clickable button.

    variant: "hero" (glowing pill; "generate" is an alias), "primary", "secondary", "ghost", "outline",
             "soft", "danger", "success"
    cost:    shows a spark and a number on the right, like "GENERATE ✦ 3"
    """

    cursor = "HAND"

    def __init__(self, text="", on_click=None, icon=None, icon_right=None, variant="secondary",
                 size="md", cost=None, loading=False, uppercase=False, toggle=False, active=False,
                 radius=None, operator=None, props=None, action=None, **kw):
        """operator="mesh.primitive_cube_add", props={...}: run a Blender operator on click.
        action="name": run an app action (see App.action)."""
        self.operator = operator
        self.props = props or {}
        self.action = action
        if text == "" and icon:
            kw.setdefault("width", "auto")
        super().__init__(**kw)
        self.text = text
        self.on_click_cb = on_click
        self.icon = icon
        self.icon_right = icon_right
        self.variant = variant
        self.size = size
        self.cost = cost
        self.loading = loading
        self.uppercase = uppercase
        self.toggle = toggle
        self.active = active
        self.radius = radius

    def interactive(self):
        return True

    def _label(self):
        t = self.text() if callable(self.text) else self.text
        return t.upper() if self.uppercase else t

    def _cost(self):
        return self.cost() if callable(self.cost) else self.cost

    def _metrics(self, ctx):
        h, fs, isz = _SIZES.get(self.size, _SIZES["md"])
        if self.height is not None:
            h = self.height
        return ctx.px(h), fs, ctx.px(isz)

    def natural_width(self, ctx):
        h, fs, isz = self._metrics(ctx)
        pad = h * 0.42
        w = pad * 2
        lab = self._label()
        weight = "semibold" if self.variant in ("generate", "hero", "primary") else "medium"
        if lab:
            w += ctx.text_w(lab, fs, weight)
        if self.icon or self.loading:
            w += isz + (ctx.px(7) if lab else 0)
        if self.icon_right:
            w += isz + ctx.px(6)
        if self.cost is not None:
            w += ctx.px(16) + isz * 0.6 + ctx.px(4) + ctx.text_w(str(self._cost()), fs - 1, "semibold") + ctx.px(6)
        if not lab and (self.icon or self.loading) and not self.icon_right:
            w = h
        return w

    def measure(self, ctx, avail_w):
        h, _fs, _i = self._metrics(ctx)
        return self.resolve_width(ctx, avail_w), h

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        self.redraw()
        return self.is_enabled

    def on_release(self, ctx, ev, inside):
        self.redraw()

    def on_click(self, ctx, ev):
        if self.loading or not self.is_enabled:
            return
        if self.toggle:
            self.active = not self.active
        call(self.on_click_cb, self)
        if self.operator:
            from . import run_operator
            try:
                run_operator(self.operator, **self.props)
            except Exception as e:
                ctx.surface.toast("Couldn't run " + (self._label() or self.operator), str(e).split("\n")[0],
                                  "danger")
        if self.action:
            ctx.surface.app.run_action(self.action)

    def _style(self, th):
        v = self.variant
        on = self.active
        if v in ("generate", "hero"):
            return dict(fill=th.accent, text=th.accent_text)
        if v == "primary":
            return dict(fill=th.accent, text=th.accent_text)
        if v == "soft":
            return dict(fill=th.accent_soft, text=th.accent, border=alpha(th.accent, 0.25))
        if v == "danger":
            return dict(fill=alpha(th.danger, 0.14), text=th.danger, border=alpha(th.danger, 0.35))
        if v == "success":
            return dict(fill=alpha(th.success, 0.14), text=th.success, border=alpha(th.success, 0.35))
        if v == "ghost":
            return dict(fill=alpha(th.surface_3, 0.0) if not on else th.selected,
                        text=th.text_dim if not on else th.text)
        if v == "outline":
            return dict(fill=alpha(th.surface_1, 0.0), text=th.text, border=th.border_strong)
        return dict(fill=th.surface_3 if not on else th.selected, text=th.text,
                    border=th.border_strong if not on else alpha(th.accent, 0.45))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        en = self.is_enabled
        hov = self.anim("hov", 1.0 if (self.hovered and en) else 0.0)
        prs = self.anim("prs", 1.0 if (self.pressed and en) else 0.0, speed=30)
        st = self._style(th)
        v = "hero" if self.variant == "generate" else self.variant
        r = ctx.px(self.radius) if self.radius is not None else (
            h / 2 if v == "hero" else min(h / 2, ctx.px(8 if h < 30 else 9)))

        if v == "hero":
            # soft pill: diagonal gradient, top sheen, accent halo that grows on hover
            k = ctx.px(1.2) * prs
            x, y, w, h = x + k, y + k, w - 2 * k, h - 2 * k
            p.shadow(x, y, w, h, r, alpha(th.accent, (0.10 + 0.22 * hov) * (1 if en else 0.3)),
                     ctx.px(10 + 10 * hov), dy=-ctx.px(3))
            p.rect(x, y, w, h, fill=_dim(mix(th.accent_hi, th.accent, 0.35 - 0.25 * hov), en),
                   fill2=_dim(mix(th.accent_lo, th.accent_edge, 0.25), en), angle=2.2, radius=r,
                   border=alpha(th.accent_hi, 0.55), border_w=ctx.px(1))
            p.rect(x + r * 0.6, y + h - ctx.px(1.6) - h * 0.04, w - r * 1.2, ctx.px(1.2),
                   fill=alpha((1, 1, 1, 1), 0.0), fill2=alpha((1, 1, 1, 1), 0.35), angle=1.5708,
                   radius=ctx.px(0.6))
            y_shift = 0.0
        elif v == "primary":
            p.shadow(x, y, w, h, r, alpha(th.accent, 0.18 * hov), ctx.px(10))
            p.rect(x, y, w, h, fill=_dim(lighten(th.accent, 0.08 * hov), en),
                   fill2=_dim(mix(th.accent, th.accent_lo, 0.4), en), radius=r)
            y_shift = -prs * ctx.px(0.5)
        else:
            fill = st["fill"]
            if hov > 0:
                if v == "ghost":
                    fill = mix(fill, alpha(th.surface_3, 1.0), hov * 0.85)
                elif v == "outline":
                    fill = mix(fill, alpha(th.surface_3, 0.6), hov)
                else:
                    fill = mix(fill, lighten(fill, 0.08), hov)
            if prs > 0:
                fill = mix(fill, lighten(fill, 0.04), prs)
            border = st.get("border")
            if border and v in ("outline", "secondary") and hov > 0:
                border = mix(border, alpha(th.accent, 0.5), hov * 0.5)
            p.rect(x, y, w, h, fill=_dim(fill, en), radius=r, border=border, border_w=ctx.px(1))
            if self.focused:
                p.rect(x - ctx.px(2), y - ctx.px(2), w + ctx.px(4), h + ctx.px(4), radius=r + ctx.px(2),
                       border=th.border_focus, border_w=ctx.px(1.5))
            y_shift = 0.0

        _h, fs, isz = self._metrics(ctx)
        lab = self._label()
        weight = "semibold" if v in ("hero", "primary") else "medium"
        tc = _dim(st["text"], en)
        tw = ctx.text_w(lab, fs, weight) if lab else 0.0
        has_icon = bool(self.icon) or self.loading
        cost_w = 0.0
        if self.cost is not None:
            cost_w = ctx.px(10) + isz * 0.6 + ctx.px(4) + ctx.text_w(str(self._cost()), fs - 1, "semibold") + ctx.px(6)
        content = tw + (isz + (ctx.px(7) if lab else 0) if has_icon else 0) + \
            (isz + ctx.px(6) if self.icon_right else 0) + cost_w
        cx = x + max(ctx.px(6), (w - content) / 2)
        cy = y + h / 2 + y_shift
        if self.loading:
            ang = (time.perf_counter() * 6.0) % math.tau
            p.arc(cx + isz / 2, cy, isz * 0.38, ang, 4.2, ctx.px(1.8), tc)
            self.anim("spin", 0.0)
            from .core import mark_animating
            mark_animating()
            cx += isz + (ctx.px(7) if lab else 0)
        elif self.icon:
            p.icon(self.icon, cx, cy - isz / 2, isz, tc, 1.7 if v == "hero" else 1.6)
            cx += isz + (ctx.px(7) if lab else 0)
        if lab:
            p.text(lab, cx, cy, fs, tc, weight, valign="center", max_w=max(4.0, w - (cx - x) - ctx.px(6)))
            cx += tw
        if self.cost is not None:
            # inset credit tag: ◆ 3
            cx += ctx.px(10)
            ct = str(self._cost())
            tw2 = ctx.text_w(ct, fs - 1, "semibold")
            tag_w = isz * 0.8 + ctx.px(3) + tw2 + ctx.px(12)
            tag_h = min(h - ctx.px(10), ctx.px(22))
            p.rect(cx - ctx.px(6), cy - tag_h / 2, tag_w, tag_h, fill=alpha(tc, 0.12), radius=tag_h / 2,
                   border=alpha(tc, 0.16), border_w=ctx.px(1))
            p.sparkle(cx + isz * 0.3, cy, isz * 0.3, tc, 1.0)
            p.text(ct, cx + isz * 0.6 + ctx.px(4), cy, fs - 1, tc, "semibold", valign="center")
        if self.icon_right:
            p.icon(self.icon_right, x + w - isz - (h - isz) / 2, cy - isz / 2, isz, tc, 1.6)


class IconButton(Button):
    def __init__(self, icon, on_click=None, variant="ghost", size="md", **kw):
        kw.setdefault("width", "auto")
        super().__init__("", on_click=on_click, icon=icon, variant=variant, size=size, **kw)

    def natural_width(self, ctx):
        h, _fs, _isz = self._metrics(ctx)
        return h


# ---------------------------------------------------------------------------
# Chips, tags, badges
# ---------------------------------------------------------------------------

class Chip(Widget):
    """Small rounded control from the composer row: icon, label and optional dropdown arrow.

    selectable=True turns it into a toggle chip (filter chips)."""

    cursor = "HAND"

    def __init__(self, text, icon=None, dropdown=False, on_click=None, selected=False,
                 selectable=False, removable=False, on_remove=None, **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self.text = text
        self.icon = icon
        self.dropdown = dropdown
        self.on_click_cb = on_click
        self.selected = selected
        self.selectable = selectable
        self.removable = removable
        self.on_remove = on_remove

    def interactive(self):
        return True

    def _label(self):
        return self.text() if callable(self.text) else self.text

    def natural_width(self, ctx):
        th = ctx.theme
        w = ctx.px(9) * 2 + ctx.text_w(self._label(), th.fs_sm, "medium")
        if self.icon:
            w += ctx.px(14 + 6)
        if self.dropdown or self.removable:
            w += ctx.px(12 + 5)
        return w

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height or 27)

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        return self.is_enabled

    def on_click(self, ctx, ev):
        x, y, w, h = self.rect
        if self.removable and ev.x > x + w - ctx.px(22):
            call(self.on_remove, self)
            return
        if self.selectable:
            self.selected = not self.selected
        call(self.on_click_cb, self)
        self.redraw()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        hov = self.anim("hov", 1.0 if self.hovered else 0.0)
        sel = self.anim("sel", 1.0 if self.selected else 0.0)
        fill = mix(th.surface_3, th.surface_4, hov * 0.7)
        fill = mix(fill, th.accent_soft, sel)
        border = mix(alpha(th.border_strong, 0.0), alpha(th.border_strong, 0.9), hov)
        border = mix(border, alpha(th.accent, 0.5), sel)
        r = ctx.px(8)
        p.rect(x, y, w, h, fill=fill, radius=r, border=border, border_w=ctx.px(1))
        col = mix(th.text, th.accent, sel)
        sub = mix(th.text_dim, th.accent, sel)
        cx = x + ctx.px(9)
        cy = y + h / 2
        if self.icon:
            isz = ctx.px(14)
            p.icon(self.icon, cx, cy - isz / 2, isz, sub, 1.5)
            cx += isz + ctx.px(6)
        right = ctx.px(12 + 5 + 9) if (self.dropdown or self.removable) else ctx.px(9)
        p.text(self._label(), cx, cy, th.fs_sm, col, "medium", valign="center",
               max_w=max(4.0, x + w - right - cx))
        if self.dropdown or self.removable:
            isz = ctx.px(12)
            p.icon("chevron_down" if self.dropdown else "x", x + w - ctx.px(9) - isz, cy - isz / 2, isz, sub, 1.7)


class Badge(Widget):
    """Status pill: kind = neutral, accent, success, warning, danger, info."""

    def __init__(self, text, kind="neutral", dot=False, icon=None, **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self.text = text
        self.kind = kind
        self.dot = dot
        self.icon = icon

    def _color(self, th):
        return {"accent": th.accent, "success": th.success, "warning": th.warning, "danger": th.danger,
                "info": th.info}.get(self.kind, th.text_dim)

    def natural_width(self, ctx):
        th = ctx.theme
        w = ctx.px(16) + ctx.text_w(self.text, th.fs_xs, "semibold")
        if self.dot or self.icon:
            w += ctx.px(10)
        return w

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(19)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        c = self._color(th)
        p.rect(x, y, w, h, fill=alpha(c, 0.13), radius=h / 2, border=alpha(c, 0.28), border_w=ctx.px(1))
        cx = x + ctx.px(8)
        if self.dot:
            p.circle(cx + ctx.px(2.5), y + h / 2, ctx.px(3), fill=c)
            p.shadow(cx, y + h / 2 - ctx.px(2.5), ctx.px(5), ctx.px(5), ctx.px(2.5), alpha(c, 0.6), ctx.px(4))
            cx += ctx.px(10)
        elif self.icon:
            p.icon(self.icon, cx - ctx.px(1), y + h / 2 - ctx.px(5.5), ctx.px(11), c, 1.6)
            cx += ctx.px(10)
        p.text(self.text, cx, y + h / 2, th.fs_xs, c, "semibold", valign="center")


# ---------------------------------------------------------------------------
# Toggles
# ---------------------------------------------------------------------------

class Checkbox(ValueMixin, Widget):
    cursor = "HAND"

    def __init__(self, text="", value=False, bind=None, on_change=None, description=None, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change, False)
        self.text = text if text or bind is None else (bind if isinstance(bind, Bind) else Bind(bind)).label()
        self.description = description

    def interactive(self):
        return True

    def natural_width(self, ctx):
        return ctx.px(16 + 9) + ctx.text_w(self.text, ctx.theme.fs_md, "regular")

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.description and 38 or 24)

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        return self.is_enabled

    def on_nav(self, ctx, d):
        self.set_value(d > 0)

    def on_click(self, ctx, ev):
        self.set_value(not bool(self.value))
        if self.bind:
            self.bind.push_undo("Toggle " + self.text)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        on = bool(self.value)
        t = self.anim("on", 1.0 if on else 0.0, speed=20)
        hov = self.anim("hov", 1.0 if self.hovered else 0.0)
        s = ctx.px(16)
        bx = x
        by = y + h - (ctx.px(24) + s) / 2 if self.description else y + (h - s) / 2
        if t > 0.01:
            p.shadow(bx, by, s, s, ctx.px(5), alpha(th.accent, 0.3 * t), ctx.px(6))
        fill = mix(mix(th.surface_0, th.surface_3, hov * 0.5), th.accent, t)
        border = mix(mix(th.border_strong, lighten(th.border_strong, 0.15), hov), th.accent, t)
        p.rect(bx, by, s, s, fill=_dim(fill, self.is_enabled), radius=ctx.px(5), border=border,
               border_w=ctx.px(1.2))
        if t > 0.01:
            k = 0.6 + 0.4 * t
            pts = [(bx + s * 0.24, by + s * 0.52), (bx + s * 0.43, by + s * 0.32), (bx + s * 0.77, by + s * 0.70)]
            cxm, cym = bx + s / 2, by + s / 2
            pts = [(cxm + (px - cxm) * k, cym + (py - cym) * k) for px, py in pts]
            p.polyline(pts, ctx.px(2), alpha(th.accent_text, t))
        tc = th.text if self.is_enabled else th.text_disabled
        ty = by + s / 2
        p.text(self.text, x + s + ctx.px(9), ty, th.fs_md, tc, valign="center", max_w=w - s - ctx.px(9))
        if self.description:
            p.text(self.description, x + s + ctx.px(9), ty - ctx.px(15), th.fs_sm, th.text_muted,
                   valign="center", max_w=w - s - ctx.px(9))


class Switch(Checkbox):
    """iOS-style switch with a glowing on state."""

    def natural_width(self, ctx):
        return ctx.px(34 + 10) + ctx.text_w(self.text, ctx.theme.fs_md, "regular")

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        on = bool(self.value)
        t = self.anim("on", 1.0 if on else 0.0, speed=16)
        hov = self.anim("hov", 1.0 if self.hovered else 0.0)
        tw, tht = ctx.px(34), ctx.px(19)
        tx = x + w - tw
        ty = y + h - (ctx.px(24) + tht) / 2 if self.description else y + (h - tht) / 2
        if t > 0.01:
            p.shadow(tx, ty, tw, tht, tht / 2, alpha(th.accent, 0.28 * t), ctx.px(8))
        track = mix(mix(th.surface_0, th.surface_3, hov * 0.6), th.accent, t)
        p.rect(tx, ty, tw, tht, fill=_dim(track, self.is_enabled), radius=tht / 2,
               border=mix(th.border_strong, th.accent, t), border_w=ctx.px(1))
        kr = tht / 2 - ctx.px(2.5)
        kx = tx + tht / 2 + (tw - tht) * t
        p.shadow(kx - kr, ty + tht / 2 - kr, kr * 2, kr * 2, kr, (0, 0, 0, 0.35), ctx.px(3), dy=-ctx.px(1))
        knob = mix(th.text_dim, th.accent_text, t)
        p.circle(kx, ty + tht / 2, kr + (ctx.px(0.6) * hov), fill=knob)
        tc = th.text if self.is_enabled else th.text_disabled
        p.text(self.text, x, ty + tht / 2, th.fs_md, tc, valign="center", max_w=w - tw - ctx.px(8))
        if self.description:
            p.text(self.description, x, ty + tht / 2 - ctx.px(15), th.fs_sm, th.text_muted,
                   valign="center", max_w=w - tw - ctx.px(8))


def _norm_items(items):
    out = []
    for it in items:
        if isinstance(it, str):
            out.append((it, it, None, None))
        else:
            it = tuple(it) + (None,) * (4 - len(it))
            out.append(it[:4])
    return out


class RadioGroup(ValueMixin, Widget):
    """items: ["A", "B"] or [(id, label, icon, description), ...]; bind to an EnumProperty."""

    cursor = "HAND"

    def __init__(self, items=None, value=None, bind=None, on_change=None, horizontal=False, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change)
        if items is None and self.bind is not None:
            items = [(i, n, None, d) for i, n, d in self.bind.enum_items()]
        self.items = _norm_items(items or [])
        if self._value is None and self.items:
            self._value = self.items[0][0]
        self.horizontal = horizontal
        self._hov = -1
        self._slots = []

    def interactive(self):
        return True

    def _row_h(self, ctx, it):
        return ctx.px(38 if it[3] else 26)

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        if self.horizontal:
            return w, ctx.px(26)
        return w, sum(self._row_h(ctx, it) for it in self.items)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        self._slots = []
        if self.horizontal:
            cx = x
            for it in self.items:
                iw = ctx.px(16 + 8 + 16) + ctx.text_w(it[1], ctx.theme.fs_md)
                self._slots.append((cx, y, iw, h))
                cx += iw
        else:
            top = y + h
            for it in self.items:
                rh = self._row_h(ctx, it)
                self._slots.append((x, top - rh, w, rh))
                top -= rh

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
        return self.is_enabled

    def on_click(self, ctx, ev):
        i = self._at(ev)
        if i >= 0:
            self.set_value(self.items[i][0])
            if self.bind:
                self.bind.push_undo("Set " + self.items[i][1])

    def on_nav(self, ctx, d):
        ids = [it[0] for it in self.items]
        i = ids.index(self.value) if self.value in ids else 0
        d = 1 if d > 0 else -1
        if not self.horizontal:
            d = -d
        self.set_value(ids[max(0, min(len(ids) - 1, i + d))])

    def paint(self, ctx, p):
        th = ctx.theme
        val = self.value
        for i, (it, (sx, sy, sw, sh)) in enumerate(zip(self.items, self._slots)):
            on = it[0] == val
            t = self.anim("o%d" % i, 1.0 if on else 0.0, speed=18)
            hov = 1.0 if i == self._hov else 0.0
            r = ctx.px(8)
            cy = sy + sh - ctx.px(13) if it[3] else sy + sh / 2
            cx = sx + r
            if t > 0.01:
                p.shadow(cx - r, cy - r, r * 2, r * 2, r, alpha(th.accent, 0.25 * t), ctx.px(6))
            p.circle(cx, cy, r, fill=mix(th.surface_0, th.surface_3, hov * 0.5),
                     border=mix(th.border_strong, th.accent, t), border_w=ctx.px(1.3))
            if t > 0.01:
                p.circle(cx, cy, ctx.px(4.2) * (0.4 + 0.6 * t), fill=alpha(th.accent, t))
            tx = cx + r + ctx.px(9)
            p.text(it[1], tx, cy, th.fs_md, th.text if on else th.text_dim, valign="center",
                   max_w=sx + sw - tx)
            if it[3]:
                p.text(it[3], tx, cy - ctx.px(15), th.fs_sm, th.text_muted, valign="center",
                       max_w=sx + sw - tx)


class Segmented(RadioGroup):
    """Compact segmented control with a sliding highlight."""

    def __init__(self, items=None, value=None, bind=None, on_change=None, **kw):
        super().__init__(items, value, bind, on_change, horizontal=True, **kw)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height or 30)

    def natural_width(self, ctx):
        th = ctx.theme
        return sum(ctx.px(24) + ctx.text_w(it[1], th.fs_sm, "medium") + (ctx.px(18) if it[2] else 0)
                   for it in self.items) + ctx.px(6)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        n = max(1, len(self.items))
        sw = (w - ctx.px(6)) / n
        self._slots = [(x + ctx.px(3) + i * sw, y, sw, h) for i in range(n)]

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        p.rect(x, y, w, h, fill=th.surface_0, radius=ctx.px(9), border=th.border, border_w=ctx.px(1))
        ids = [it[0] for it in self.items]
        val = self.value
        idx = ids.index(val) if val in ids else 0
        sx, sy, sw, sh = self._slots[idx]
        ax = self.anim("ax", sx, speed=20)
        ip = ctx.px(3)
        if 0 <= self._hov < len(self._slots) and self._hov != idx:
            hx = self._slots[self._hov][0]
            p.rect(hx, y + ip, sw, h - ip * 2, fill=alpha(th.surface_3, 0.5), radius=ctx.px(7))
        p.rect(ax, y + ip, sw, h - ip * 2, fill=th.surface_4, fill2=th.selected, radius=ctx.px(7),
               border=alpha((1, 1, 1, 1), 0.06), border_w=ctx.px(1))
        for i, (it, (tx, ty, tw, tht)) in enumerate(zip(self.items, self._slots)):
            on = i == idx
            col = th.text if on else th.text_muted
            iw = ctx.px(13) if it[2] else 0.0
            lw = ctx.text_w(it[1], th.fs_sm, "medium")
            g = ctx.px(5) if it[2] else 0.0
            cx = tx + (tw - iw - g - lw) / 2
            if it[2]:
                p.icon(it[2], cx, y + h / 2 - iw / 2, iw, col, 1.5)
            p.text(it[1], cx + iw + g, y + h / 2, th.fs_sm, col, "medium", valign="center",
                   max_w=tw - ctx.px(6))


# ---------------------------------------------------------------------------
# Slider and number field
# ---------------------------------------------------------------------------

def _fmt(v, precision, unit, subtype=None):
    if subtype in ("ANGLE", "EULER"):
        return "%.*f\u00b0" % (min(precision, 1), math.degrees(v))
    if subtype == "PERCENTAGE":
        return "%.*f%%" % (precision, v)
    if isinstance(v, int) and precision == 0:
        s = str(v)
    else:
        s = "%.*f" % (precision, v)
    return s + (unit or "")


class Slider(ValueMixin, Widget):
    """Track bar.

    style="track": label + value above a glowing track (default)
    style="box":   Blender-like field where the fill shows the value
    Hold Shift for fine control, double-click to reset to `default`.
    """

    cursor = "HAND"

    def __init__(self, label=None, value=None, min=0.0, max=1.0, step=None, precision=None, unit="",
                 bind=None, on_change=None, style="track", default=None, show_value=True,
                 integer=None, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change, min)
        r = self.bind.range() if self.bind is not None else None
        if r:
            min, max = r[0], r[1]
            if precision is None:
                precision = 0 if isinstance(self.bind.get(0), int) else (r[3] if r[3] < 3 else 3)
            self.subtype = r[4]
        else:
            self.subtype = None
        if label is None and self.bind is not None:
            label = self.bind.label()
        self.label = label or ""
        self.min = min
        self.max = max
        self.step = step
        self.integer = integer if integer is not None else isinstance(self.value, int)
        self.precision = precision if precision is not None else (0 if self.integer else 2)
        self.unit = unit
        self.style = style
        self.default = default if default is not None else self.value
        self.show_value = show_value
        self._drag = None

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        h = 30 if self.style == "box" else (40 if self.label else 22)
        return self.resolve_width(ctx, avail_w), ctx.px(self.height or h)

    def _track(self, ctx):
        x, y, w, h = self.rect
        if self.style == "box":
            return x, y, w, h
        th = ctx.px(6)
        kr = ctx.px(8)
        return x + kr, y + ctx.px(8), w - kr * 2, th

    def _frac(self):
        v = float(self.value or 0)
        rng = self.max - self.min
        return 0.0 if rng == 0 else max(0.0, min(1.0, (v - self.min) / rng))

    def _set_from_x(self, ctx, ex, fine=False):
        tx, ty, tw, th_ = self._track(ctx)
        if fine and self._drag:
            x0, f0 = self._drag
            f = f0 + (ex - x0) / max(1.0, tw) * 0.1
        else:
            f = (ex - tx) / max(1.0, tw)
        f = max(0.0, min(1.0, f))
        v = self.min + (self.max - self.min) * f
        if self.step:
            v = round((v - self.min) / self.step) * self.step + self.min
        if self.integer:
            v = int(round(v))
        else:
            v = round(v, max(self.precision, 3))
        if v != self.value:
            self.set_value(v)

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        if not self.is_enabled:
            return False
        self._drag = (ev.x, self._frac())
        if self.style == "box":
            self._box_start = (ev.x, self._frac())
            return True
        self._set_from_x(ctx, ev.x)
        return True

    def on_drag(self, ctx, ev):
        if self.style == "box":
            x0, f0 = self._box_start
            tw = self.rect[2]
            k = 0.1 if ev.shift else 1.0
            f = max(0.0, min(1.0, f0 + (ev.x - x0) / max(1.0, tw) * k))
            v = self.min + (self.max - self.min) * f
            if self.step:
                v = round((v - self.min) / self.step) * self.step + self.min
            v = int(round(v)) if self.integer else round(v, max(self.precision, 3))
            if v != self.value:
                self.set_value(v)
            return
        self._set_from_x(ctx, ev.x, fine=ev.shift)

    def on_release(self, ctx, ev, inside):
        if self.style == "box" and abs(ev.x - self._box_start[0]) < ctx.px(3):
            self._set_from_x(ctx, ev.x)
        self._drag = None
        if self.bind:
            self.bind.push_undo("Change " + self.label)
        self.redraw()

    def on_double_click(self, ctx, ev):
        if self.default is not None:
            self.set_value(self.default)
        return True

    def on_nav(self, ctx, d):
        step = self.step or ((self.max - self.min) / 100.0)
        v = max(self.min, min(self.max, float(self.value or 0) + step * d))
        self.set_value(int(round(v)) if self.integer else v)

    def on_wheel(self, ctx, ev):
        if not ev.mod:
            return False
        step = self.step or ((self.max - self.min) / 100.0)
        v = self.value + step * ev.wheel
        v = max(self.min, min(self.max, v))
        self.set_value(int(round(v)) if self.integer else v)
        return True

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        en = self.is_enabled
        f = self.anim("f", self._frac(), speed=28)
        hov = self.anim("hov", 1.0 if (self.hovered or self._drag) else 0.0)
        val_txt = _fmt(self.value if self.value is not None else 0, self.precision, self.unit, self.subtype)
        if self.style == "box":
            r = ctx.px(8)
            p.rect(x, y, w, h, fill=mix(th.surface_3, th.surface_4, hov * 0.5), radius=r,
                   border=mix(th.border_strong, alpha(th.accent, 0.5), hov * 0.6), border_w=ctx.px(1))
            if f > 0:
                p.push_clip(x, y, w * f, h)
                p.rect(x, y, w, h, fill=alpha(th.accent, 0.22), fill2=alpha(th.accent, 0.12), angle=math.pi / 2,
                       radius=r)
                p.pop_clip()
                p.rect(x + w * f - ctx.px(1), y + ctx.px(5), ctx.px(2), h - ctx.px(10), fill=alpha(th.accent, 0.9),
                       radius=ctx.px(1))
            p.text(self.label, x + ctx.px(10), y + h / 2, th.fs_sm, _dim(th.text_dim, en), "medium",
                   valign="center", max_w=w * 0.6)
            p.text(val_txt, x + w - ctx.px(10), y + h / 2, th.fs_sm, _dim(th.text, en), "semibold",
                   align="right", valign="center")
            return
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, _dim(th.text_dim, en), "medium", valign="center",
                   max_w=w * 0.65)
        if self.label and self.show_value:
            vw = ctx.text_w(val_txt, th.fs_sm, "semibold") + ctx.px(12)
            vh = ctx.px(18)
            vx = x + w - vw
            vy = y + h - ctx.px(8) - vh / 2
            p.rect(vx, vy, vw, vh, fill=th.surface_3, radius=ctx.px(5), border=th.border, border_w=ctx.px(1))
            p.text(val_txt, vx + vw / 2, vy + vh / 2, th.fs_sm, _dim(th.text, en), "semibold", align="center",
                   valign="center")
        tx, ty, tw, tht = self._track(ctx)
        p.rect(tx, ty, tw, tht, fill=th.surface_0, radius=tht / 2, border=th.border, border_w=ctx.px(1))
        fw = tw * f
        if fw > 0.5:
            p.shadow(tx, ty, fw, tht, tht / 2, alpha(th.accent, 0.25 * (0.5 + hov * 0.5)), ctx.px(6))
            p.rect(tx, ty, fw, tht, fill=_dim(th.accent_lo, en), fill2=_dim(th.accent_hi, en),
                   angle=math.pi / 2, radius=tht / 2)
        kr = ctx.px(7) + ctx.px(1.5) * hov
        kx = tx + fw
        ky = ty + tht / 2
        p.shadow(kx - kr, ky - kr, kr * 2, kr * 2, kr, (0, 0, 0, 0.45), ctx.px(4), dy=-ctx.px(1))
        if self._drag:
            p.circle(kx, ky, kr + ctx.px(5), fill=alpha(th.accent, 0.16))
        p.circle(kx, ky, kr, fill=_dim((0.96, 0.97, 0.98, 1.0), en), border=_dim(th.accent, en),
                 border_w=ctx.px(2.5))


class TextEdit:
    """Editable text state shared by TextInput and NumberField."""

    def _te_init(self, text=""):
        self.text = text
        self.caret = len(text)
        self.anchor = len(text)
        self._blink0 = time.perf_counter()
        self._undo = []

    def _sel(self):
        return (min(self.caret, self.anchor), max(self.caret, self.anchor))

    def _has_sel(self):
        return self.caret != self.anchor

    def _insert(self, s):
        a, b = self._sel()
        self._undo.append((self.text, self.caret, self.anchor))
        self.text = self.text[:a] + s + self.text[b:]
        self.caret = self.anchor = a + len(s)

    def _delete(self, forward=False, word=False):
        if self._has_sel():
            self._insert("")
            return
        c = self.caret
        if forward:
            e = self._word_right(c) if word else min(len(self.text), c + 1)
            self._undo.append((self.text, self.caret, self.anchor))
            self.text = self.text[:c] + self.text[e:]
        else:
            s = self._word_left(c) if word else max(0, c - 1)
            self._undo.append((self.text, self.caret, self.anchor))
            self.text = self.text[:s] + self.text[c:]
            self.caret = self.anchor = s

    def _word_left(self, i):
        t = self.text
        while i > 0 and t[i - 1] == " ":
            i -= 1
        while i > 0 and t[i - 1] not in " \n":
            i -= 1
        return i

    def _word_right(self, i):
        t = self.text
        n = len(t)
        while i < n and t[i] == " ":
            i += 1
        while i < n and t[i] not in " \n":
            i += 1
        return i

    def _move(self, to, select):
        self.caret = max(0, min(len(self.text), to))
        if not select:
            self.anchor = self.caret
        self._blink0 = time.perf_counter()

    def te_key(self, ctx, ev, multiline=False):
        """Handle an editing key. Returns 'submit', 'cancel', 'changed', 'moved' or None."""
        import bpy
        t = ev.type
        sel = bool(ev.shift)
        if ev.mod:
            if t == "A":
                self.anchor, self.caret = 0, len(self.text)
                return "moved"
            if t in ("C", "X") and self._has_sel():
                a, b = self._sel()
                bpy.context.window_manager.clipboard = self.text[a:b]
                if t == "X":
                    self._insert("")
                    return "changed"
                return "moved"
            if t == "V":
                clip = bpy.context.window_manager.clipboard or ""
                if not multiline:
                    clip = clip.replace("\n", " ")
                self._insert(clip)
                return "changed"
            if t == "Z":
                if self._undo:
                    self.text, self.caret, self.anchor = self._undo.pop()
                    return "changed"
                return "moved"
            if t == "LEFT_ARROW":
                self._move(self._word_left(self.caret), sel)
                return "moved"
            if t == "RIGHT_ARROW":
                self._move(self._word_right(self.caret), sel)
                return "moved"
            if t == "BACK_SPACE":
                self._delete(word=True)
                return "changed"
            if t == "DEL":
                self._delete(forward=True, word=True)
                return "changed"
            return None
        if t == "LEFT_ARROW":
            if self._has_sel() and not sel:
                self._move(self._sel()[0], False)
            else:
                self._move(self.caret - 1, sel)
            return "moved"
        if t == "RIGHT_ARROW":
            if self._has_sel() and not sel:
                self._move(self._sel()[1], False)
            else:
                self._move(self.caret + 1, sel)
            return "moved"
        if t == "HOME":
            ls = self.text.rfind("\n", 0, self.caret) + 1 if multiline else 0
            self._move(ls, sel)
            return "moved"
        if t == "END":
            le = self.text.find("\n", self.caret) if multiline else -1
            self._move(len(self.text) if le < 0 else le, sel)
            return "moved"
        if t == "BACK_SPACE":
            self._delete()
            return "changed"
        if t == "DEL":
            self._delete(forward=True)
            return "changed"
        if t in ("RET", "NUMPAD_ENTER"):
            if multiline and ev.shift:
                self._insert("\n")
                return "changed"
            return "submit"
        if t == "ESC":
            return "cancel"
        if t == "TAB":
            return "submit" if not multiline else None
        if ev.unicode and ev.unicode.isprintable():
            self._insert(ev.unicode)
            return "changed"
        return None


class TextInput(ValueMixin, TextEdit, Widget):
    """Text field. multiline=True wraps text and grows between min_lines and max_lines
    (Enter submits, Shift+Enter adds a new line)."""

    focusable = True
    cursor = "TEXT"
    text_entry = True  # swallow Blender shortcuts while focused

    def __init__(self, placeholder="", value="", bind=None, on_change=None, on_submit=None, icon=None,
                 multiline=False, min_lines=1, max_lines=6, password=False, clearable=True, label=None,
                 variant="field", **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change, "")
        self._te_init(str(self.value or ""))
        self.placeholder = placeholder
        self.on_submit = on_submit
        self.icon = icon
        self.multiline = multiline
        self.min_lines = min_lines
        self.max_lines = max_lines
        self.password = password
        self.clearable = clearable
        self.label = label
        self.variant = variant  # "field" or "bare" (no box, for composers)
        self._scroll_x = 0.0
        self._lines = [("", 0)]
        self._dragging = False

    def interactive(self):
        return True

    def _shown(self):
        return "•" * len(self.text) if self.password else self.text

    def _fs(self, ctx):
        return ctx.theme.fs_md

    def _pad(self, ctx):
        return ctx.px(0 if self.variant == "bare" else 10)

    def _text_left(self, ctx):
        x = self.rect[0] + self._pad(ctx)
        if self.icon:
            x += ctx.px(16 + 7)
        return x

    def _text_right(self, ctx):
        x, y, w, h = self.rect
        r = x + w - self._pad(ctx)
        if self.clearable and self.text and not self.multiline:
            r -= ctx.px(20)
        return r

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        lab = ctx.px(20) if self.label else 0.0
        if not self.multiline:
            return w, ctx.px(self.height or 32) + lab
        fs = ctx.px(self._fs(ctx))
        lh = fs * 1.5
        inner = w - self._pad(ctx) * 2 - (ctx.px(23) if self.icon else 0)
        if not self.focused:
            self.text = str(self.value or "")
        self._lines = wrap_text(self._shown(), fs, max(20.0, inner), "regular")
        n = max(self.min_lines, min(self.max_lines, len(self._lines)))
        pad_v = ctx.px(0 if self.variant == "bare" else 9)
        return w, lh * n + pad_v * 2 + lab

    def _box(self, ctx):
        x, y, w, h = self.rect
        if self.label:
            return x, y, w, h - ctx.px(20)
        return x, y, w, h

    # -- caret geometry ------------------------------------------------------
    def _caret_line(self, idx):
        li = 0
        for i, (_ln, start) in enumerate(self._lines):
            if start <= idx:
                li = i
        return li

    def _index_at(self, ctx, ex, ey):
        fs = ctx.px(self._fs(ctx))
        shown = self._shown()
        bx, by, bw, bh = self._box(ctx)
        if self.multiline:
            lh = fs * 1.5
            top = by + bh - ctx.px(0 if self.variant == "bare" else 9) + self._vscroll
            li = int(max(0, (top - ey) // lh))
            li = min(li, len(self._lines) - 1)
            line, start = self._lines[li]
            line = line.rstrip("\n")
            rel = ex - self._text_left(ctx)
        else:
            line, start = shown, 0
            rel = ex - self._text_left(ctx) + self._scroll_x
        best, bd = 0, 1e9
        for i in range(len(line) + 1):
            d = abs(text_size(line[:i], fs, "regular")[0] - rel)
            if d < bd:
                best, bd = i, d
        idx = start + best
        if self.multiline and li < len(self._lines) - 1 and best == len(line) and line.endswith(" "):
            idx -= 1
        return idx

    # -- events --------------------------------------------------------------
    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_focus(self, ctx):
        self.text = str(self.value or "")
        self._move(len(self.text), False)
        self.anchor = 0 if not self.multiline else self.caret
        self.redraw()

    def on_blur(self, ctx):
        self._commit()
        self.anchor = self.caret
        self.redraw()

    def _commit(self):
        if self.text != (self.value or ""):
            self.set_value(self.text)
            if self.bind:
                self.bind.push_undo("Edit text")

    def on_press(self, ctx, ev):
        if not self.is_enabled:
            return False
        bx, by, bw, bh = self._box(ctx)
        if self.clearable and self.text and not self.multiline and ev.x > bx + bw - ctx.px(26):
            self._insert_all("")
            return True
        if self.focused:
            self._move(self._index_at(ctx, ev.x, ev.y), ev.shift)
        self._dragging = True
        return True

    def _insert_all(self, s):
        self.text = s
        self.caret = self.anchor = len(s)
        self.set_value(s)

    def on_drag(self, ctx, ev):
        if self.focused and self._dragging:
            self.caret = self._index_at(ctx, ev.x, ev.y)
            self.redraw()

    def on_release(self, ctx, ev, inside):
        self._dragging = False

    def on_double_click(self, ctx, ev):
        i = self._index_at(ctx, ev.x, ev.y)
        self.anchor = self._word_left(i)
        self.caret = self._word_right(i)
        self.redraw()
        return True

    def on_key(self, ctx, ev):
        r = self.te_key(ctx, ev, self.multiline)
        if r == "submit":
            self._commit()
            call(self.on_submit, self.text, self)
            if not self.multiline:
                ctx.surface.set_focus(None)
            return True
        if r == "cancel":
            ctx.surface.set_focus(None)
            return True
        if r == "changed":
            self._value = self.text
            if self.bind is None:
                call(self.on_change, self.text, self)
        self._blink0 = time.perf_counter()
        self.redraw()
        return r is not None or bool(ev.unicode)

    # -- paint ---------------------------------------------------------------
    def paint(self, ctx, p):
        th = ctx.theme
        if not self.focused:
            self.text = str(self.value or "")
        bx, by, bw, bh = self._box(ctx)
        x, y, w, h = self.rect
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
        hov = self.anim("hov", 1.0 if self.hovered else 0.0)
        foc = self.anim("foc", 1.0 if self.focused else 0.0)
        r = ctx.px(9)
        if self.variant != "bare":
            if foc > 0.01:
                p.shadow(bx, by, bw, bh, r, alpha(th.accent, 0.16 * foc), ctx.px(8))
            p.rect(bx, by, bw, bh, fill=mix(th.surface_0, th.surface_1, hov * 0.6), radius=r,
                   border=mix(mix(th.border_strong, lighten(th.border_strong, 0.12), hov), th.border_focus, foc),
                   border_w=ctx.px(1))
        fs = self._fs(ctx)
        fpx = ctx.px(fs)
        left = self._text_left(ctx)
        right = self._text_right(ctx)
        shown = self._shown()
        if self.icon:
            isz = ctx.px(16)
            iy = by + bh - ctx.px(9) - fpx * 0.75 - isz / 2 if self.multiline else by + bh / 2 - isz / 2
            p.icon(self.icon, bx + self._pad(ctx), iy, isz, mix(th.text_muted, th.accent, foc), 1.6)
        blink = (int((time.perf_counter() - self._blink0) / 0.53) % 2) == 0
        if self.multiline:
            lh = fpx * 1.5
            pad_v = ctx.px(0 if self.variant == "bare" else 9)
            top = by + bh - pad_v
            self._lines = wrap_text(shown, fpx, max(20.0, right - left), "regular")
            # keep the caret line visible
            n_vis = max(1, int((bh - pad_v * 2 + 1) // lh))
            cl = self._caret_line(self.caret) if self.focused else 0
            first = max(0, cl - n_vis + 1)
            self._vscroll = first * lh
            p.push_clip(bx, by + pad_v * 0.5, bw, bh - pad_v)
            if not shown and not self.focused or (not shown and self.focused):
                if not shown:
                    p.text(self.placeholder, left, top - lh / 2, fs, th.text_muted, valign="center",
                           max_w=right - left)
            a, b = self._sel()
            for i, (line, start) in enumerate(self._lines):
                ly = top - lh * (i + 1) + self._vscroll
                if self.focused and a != b:
                    s0 = max(a, start)
                    s1 = min(b, start + len(line))
                    if s0 < s1:
                        x0 = left + text_size(line[:s0 - start], fpx, "regular")[0]
                        x1 = left + text_size(line[:s1 - start], fpx, "regular")[0]
                        p.rect(x0, ly + lh * 0.12, x1 - x0, lh * 0.76, fill=alpha(th.accent, 0.28), radius=ctx.px(2))
                p.text(line.rstrip("\n"), left, ly + lh / 2, fs, th.text, valign="center")
            if self.focused and blink:
                li = self._caret_line(self.caret)
                line, start = self._lines[li]
                cx = left + text_size(line[:self.caret - start], fpx, "regular")[0]
                ly = top - lh * (li + 1) + self._vscroll
                p.rect(cx, ly + lh * 0.18, ctx.px(1.5), lh * 0.64, fill=th.accent, radius=ctx.px(0.75))
            p.pop_clip()
            return
        cy = by + bh / 2
        cw = text_size(shown[:self.caret], fpx, "regular")[0]
        avail = right - left
        if self.focused:
            if cw - self._scroll_x > avail - ctx.px(2):
                self._scroll_x = cw - avail + ctx.px(2)
            elif cw - self._scroll_x < 0:
                self._scroll_x = max(0.0, cw - ctx.px(20))
        else:
            self._scroll_x = 0.0
        p.push_clip(left - ctx.px(1), by, avail + ctx.px(3), bh)
        if not shown:
            p.text(self.placeholder, left, cy, fs, th.text_muted, valign="center", max_w=avail)
        else:
            if self.focused and self._has_sel():
                a, b = self._sel()
                x0 = left + text_size(shown[:a], fpx, "regular")[0] - self._scroll_x
                x1 = left + text_size(shown[:b], fpx, "regular")[0] - self._scroll_x
                p.rect(x0, cy - fpx * 0.75, x1 - x0, fpx * 1.5, fill=alpha(th.accent, 0.28), radius=ctx.px(2))
            p.text(shown, left - self._scroll_x, cy, fs, th.text, valign="center",
                   max_w=None if self.focused else avail)
        if self.focused and blink:
            p.rect(left + cw - self._scroll_x, cy - fpx * 0.62, ctx.px(1.5), fpx * 1.24, fill=th.accent,
                   radius=ctx.px(0.75))
        p.pop_clip()
        if self.clearable and self.text and not self.multiline:
            isz = ctx.px(13)
            p.circle(bx + bw - ctx.px(17), cy, ctx.px(8), fill=alpha(th.surface_4, 0.6 + 0.4 * hov))
            p.icon("x", bx + bw - ctx.px(17) - isz / 2, cy - isz / 2, isz, th.text_dim, 1.8)


class NumberField(ValueMixin, TextEdit, Widget):
    """Drag left/right to change, click to type a value, arrows to step."""

    focusable = True
    cursor = "SCROLL_X"

    @property
    def text_entry(self):
        return self._editing

    def __init__(self, label=None, value=None, min=-1e9, max=1e9, step=None, precision=None, unit="",
                 bind=None, on_change=None, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change, 0.0)
        r = self.bind.range() if self.bind is not None else None
        self.subtype = None
        if r:
            if min == -1e9:
                min = r[0]
            if max == 1e9:
                max = r[1]
            if precision is None:
                precision = 0 if isinstance(self.bind.get(0), int) else (r[3] if r[3] < 3 else 3)
            self.subtype = r[4]
        if label is None and self.bind is not None:
            label = self.bind.label()
        self.label = label or ""
        self.min, self.max = min, max
        self.integer = isinstance(self.value, int)
        self.precision = precision if precision is not None else (0 if self.integer else 2)
        self.step = step if step is not None else (
            math.radians(1) if self.subtype in ("ANGLE", "EULER") else (1 if self.integer else 10 ** -self.precision * 10))
        self.unit = unit
        self._te_init("")
        self._press = None
        self._moved = False
        self._editing = False
        self._side = None

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height or 30)

    def _apply(self, v):
        v = max(self.min, min(self.max, v))
        v = int(round(v)) if self.integer else round(v, self.precision + 2)
        if v != self.value:
            self.set_value(v)

    def on_hover(self, ctx, ev):
        x, y, w, h = self.rect
        side = "l" if ev.x < x + ctx.px(22) else ("r" if ev.x > x + w - ctx.px(22) else None)
        if side != self._side:
            self._side = side
            self.redraw()

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self._side = None
        self.redraw()

    def on_press(self, ctx, ev):
        if not self.is_enabled:
            return False
        if self._editing:
            return True
        self._press = (ev.x, float(self.value or 0))
        self._moved = False
        return True

    def on_drag(self, ctx, ev):
        if self._editing or not self._press:
            return
        x0, v0 = self._press
        dx = ev.x - x0
        if abs(dx) > ctx.px(3):
            self._moved = True
        if self._moved:
            k = 0.1 if ev.shift else 1.0
            self._apply(v0 + dx / ctx.px(8) * self.step * k)

    def on_release(self, ctx, ev, inside):
        if self._editing:
            return
        if not self._moved and inside:
            x, y, w, h = self.rect
            if ev.x < x + ctx.px(22):
                self._apply(float(self.value) - self.step)
            elif ev.x > x + w - ctx.px(22):
                self._apply(float(self.value) + self.step)
            else:
                self._editing = True
                self._te_init(_fmt(self.value, self.precision, "", self.subtype).replace("\u00b0", "")
                              .replace("%", ""))
                self.anchor = 0
                ctx.surface.set_focus(self)
        if self.bind and self._moved:
            self.bind.push_undo("Change " + self.label)
        self._press = None

    def on_blur(self, ctx):
        if self._editing:
            self._finish(True)

    def on_nav(self, ctx, d):
        if not self._editing:
            self._apply(float(self.value) + self.step * d)

    def _finish(self, apply):
        self._editing = False
        if apply:
            try:
                expr = self.text.replace(self.unit, "") if self.unit else self.text
                expr = expr.replace("\u00b0", "")
                v = float(eval(expr, {"__builtins__": {}}, {"pi": math.pi, "sqrt": math.sqrt}))
                if self.subtype in ("ANGLE", "EULER"):
                    v = math.radians(v)
                self._apply(v)
                if self.bind:
                    self.bind.push_undo("Set " + self.label)
            except Exception:
                pass
        self.redraw()

    def on_key(self, ctx, ev):
        if not self._editing:
            return False
        r = self.te_key(ctx, ev)
        if r == "submit":
            self._finish(True)
            ctx.surface.set_focus(None)
        elif r == "cancel":
            self._finish(False)
            ctx.surface.set_focus(None)
        self.redraw()
        return True

    def _refresh_rna(self):
        if self.bind is not None and not getattr(self, "_rna_ok", False):
            r = self.bind.range()
            if r is not None:
                self._rna_ok = True
                if self.subtype != r[4]:
                    self.subtype = r[4]
                    if self.subtype in ("ANGLE", "EULER"):
                        self.step = math.radians(1)

    def paint(self, ctx, p):
        self._refresh_rna()
        th = ctx.theme
        x, y, w, h = self.rect
        hov = self.anim("hov", 1.0 if (self.hovered or self._editing) else 0.0)
        r = ctx.px(8)
        p.rect(x, y, w, h, fill=mix(th.surface_3, th.surface_4, hov * 0.4) if not self._editing else th.surface_0,
               radius=r, border=th.border_focus if self._editing else mix(th.border_strong, alpha(th.accent, 0.4), hov * 0.5),
               border_w=ctx.px(1))
        cy = y + h / 2
        fs = th.fs_sm
        if self._editing:
            fpx = ctx.px(fs)
            left = x + ctx.px(10)
            if self._has_sel():
                a, b = self._sel()
                x0 = left + text_size(self.text[:a], fpx, "regular")[0]
                x1 = left + text_size(self.text[:b], fpx, "regular")[0]
                p.rect(x0, cy - fpx * 0.75, x1 - x0, fpx * 1.5, fill=alpha(th.accent, 0.28), radius=ctx.px(2))
            p.text(self.text, left, cy, fs, th.text, valign="center")
            if (int((time.perf_counter() - self._blink0) / 0.53) % 2) == 0:
                cw = text_size(self.text[:self.caret], fpx, "regular")[0]
                p.rect(left + cw, cy - fpx * 0.62, ctx.px(1.5), fpx * 1.24, fill=th.accent)
            return
        isz = ctx.px(13)
        if hov > 0.01:
            for side, ic, ix in (("l", "chevron_left", x + ctx.px(5)), ("r", "chevron_right", x + w - ctx.px(5) - isz)):
                col = th.accent if self._side == side else alpha(th.text_dim, hov)
                p.icon(ic, ix, cy - isz / 2, isz, col, 1.8)
        val = _fmt(self.value if self.value is not None else 0, self.precision, self.unit, self.subtype)
        if self.label:
            p.text(self.label, x + ctx.px(10) + ctx.px(12) * hov, cy, fs, th.text_dim, "medium", valign="center",
                   max_w=w * 0.55)
            p.text(val, x + w - ctx.px(10) - ctx.px(12) * hov, cy, fs, th.text, "semibold", align="right",
                   valign="center")
        else:
            p.text(val, x + w / 2, cy, fs, th.text, "semibold", align="center", valign="center")


# ---------------------------------------------------------------------------
# Dropdown / enum popover
# ---------------------------------------------------------------------------

class Dropdown(ValueMixin, Widget):
    """Select one item from a list in a popover menu.

    items: ["A", "B"] or [(id, label, icon, description), ...]
    bind an EnumProperty and the items come from Blender automatically.
    style: "field" (full-width box) or "chip" (compact chip like "Mode: Full ⌄")
    """

    cursor = "HAND"

    def __init__(self, items=None, value=None, bind=None, on_change=None, label=None, icon=None,
                 style="field", prefix="", placeholder="Select", searchable=None, menu_width=None, **kw):
        if style == "chip":
            kw.setdefault("width", "auto")
        super().__init__(**kw)
        self._init_value(value, bind, on_change)
        self._items_src = items
        self.label = label
        self.icon = icon
        self.style = style
        self.prefix = prefix
        self.placeholder = placeholder
        self.searchable = searchable
        self.menu_width = menu_width
        self._open = False

    @property
    def items(self):
        src = self._items_src
        if src is None and self.bind is not None:
            return [(i, n, None, d) for i, n, d in self.bind.enum_items()]
        if callable(src):
            src = src()
        return _norm_items(src or [])

    def _current(self):
        v = self.value
        for it in self.items:
            if it[0] == v:
                return it
        return None

    def interactive(self):
        return True

    def _text(self):
        cur = self._current()
        return self.prefix + (cur[1] if cur else self.placeholder)

    def natural_width(self, ctx):
        th = ctx.theme
        cur = self._current()
        ic = (cur and cur[2]) or self.icon
        w = ctx.px(9) * 2 + ctx.text_w(self._text(), th.fs_sm, "medium") + ctx.px(17)
        if ic:
            w += ctx.px(20)
        return w

    def measure(self, ctx, avail_w):
        lab = ctx.px(20) if self.label and self.style == "field" else 0.0
        h = 27 if self.style == "chip" else 32
        return self.resolve_width(ctx, avail_w), ctx.px(self.height or h) + lab

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
        from .overlays import Menu
        items = self.items
        cur = self.value

        def pick(item_id):
            self.set_value(item_id)
            if self.bind:
                self.bind.push_undo("Select")

        search = self.searchable if self.searchable is not None else len(items) > 8
        menu = Menu(items, value=cur, on_pick=pick, searchable=search)
        self._open = True

        def closed():
            self._open = False
            self.redraw()

        x, y, w, h = self.rect
        mw = ctx.px(self.menu_width) if self.menu_width else max(w, ctx.px(190))
        ctx.surface.open_popover(menu, anchor=self, width=mw, on_close=closed)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        if self.label and self.style == "field":
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
            h -= ctx.px(20)
        hov = self.anim("hov", 1.0 if (self.hovered or self._open) else 0.0)
        cur = self._current()
        ic = (cur and cur[2]) or self.icon
        if self.style == "chip":
            fill = mix(th.surface_3, th.surface_4, hov * 0.7)
            border = mix(alpha(th.border_strong, 0.0), th.border_strong, hov)
            r = ctx.px(8)
        else:
            fill = mix(th.surface_3, th.surface_4, hov * 0.5)
            border = mix(th.border_strong, alpha(th.accent, 0.55), 1.0 if self._open else hov * 0.4)
            r = ctx.px(9)
        p.rect(x, y, w, h, fill=fill, radius=r, border=border, border_w=ctx.px(1))
        cx = x + ctx.px(9 if self.style == "chip" else 11)
        cy = y + h / 2
        if ic:
            isz = ctx.px(14)
            p.icon(ic, cx, cy - isz / 2, isz, th.text_dim, 1.5)
            cx += isz + ctx.px(6)
        isz = ctx.px(12)
        right = x + w - ctx.px(9) - isz
        p.text(self._text(), cx, cy, th.fs_sm if self.style == "chip" else th.fs_md,
               th.text if cur else th.text_muted, "medium" if self.style == "chip" else "regular",
               valign="center", max_w=max(4.0, right - cx - ctx.px(4)))
        rot = self.anim("rot", 1.0 if self._open else 0.0, speed=20)
        p.icon("chevron_up" if rot > 0.5 else "chevron_down", right, cy - isz / 2, isz,
               mix(th.text_dim, th.accent, rot), 1.7)


# ---------------------------------------------------------------------------
# Progress, spinner
# ---------------------------------------------------------------------------

class ProgressBar(Widget):
    """value 0..1, or None for an indeterminate shimmer."""

    def __init__(self, value=0.0, label=None, show_percent=True, kind="accent", **kw):
        super().__init__(**kw)
        self.value = value
        self.label = label
        self.show_percent = show_percent
        self.kind = kind

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(28 if self.label else 8)

    def _val(self):
        v = self.value() if callable(self.value) else self.value
        return v

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        v = self._val()
        c = {"success": th.success, "warning": th.warning, "danger": th.danger, "info": th.info}.get(self.kind, th.accent)
        if self.label:
            p.text(self.label, x, y + h - ctx.px(7), th.fs_sm, th.text_dim, "medium", valign="center")
            if self.show_percent and v is not None:
                p.text("%d%%" % round(v * 100), x + w, y + h - ctx.px(7), th.fs_sm, th.text, "semibold",
                       align="right", valign="center")
        bh = ctx.px(6)
        p.rect(x, y, w, bh, fill=th.surface_0, radius=bh / 2, border=th.border, border_w=ctx.px(1))
        if v is None:
            from .core import mark_animating
            mark_animating()
            t = (time.perf_counter() * 0.8) % 1.0
            seg = w * 0.35
            sx = x - seg + (w + seg) * t
            p.push_clip(x, y, w, bh)
            p.rect(sx, y, seg, bh, fill=alpha(c, 0.0), fill2=c, angle=math.pi / 2, radius=bh / 2, flat=c)
            p.pop_clip()
            return
        f = self.anim("f", max(0.0, min(1.0, v)), speed=8)
        if f > 0:
            p.shadow(x, y, w * f, bh, bh / 2, alpha(c, 0.3), ctx.px(5))
            p.rect(x, y, max(bh, w * f), bh, fill=mix(c, (0, 0, 0, 1), 0.15), fill2=lighten(c, 0.2),
                   angle=math.pi / 2, radius=bh / 2)


class Spinner(Widget):
    def __init__(self, size=18, color=None, **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self.size = size
        self.color = color

    def natural_width(self, ctx):
        return ctx.px(self.size)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.size)

    def paint(self, ctx, p):
        from .core import mark_animating
        mark_animating()
        th = ctx.theme
        x, y, w, h = self.rect
        r = min(w, h) / 2 - ctx.px(2)
        cx, cy = x + w / 2, y + h / 2
        t = time.perf_counter()
        p.arc(cx, cy, r, 0, math.tau, ctx.px(2.2), alpha(th.text, 0.1))
        span = 1.2 + 1.0 * (0.5 + 0.5 * math.sin(t * 2.5))
        p.arc(cx, cy, r, -t * 5.0, span, ctx.px(2.2), th.color(self.color) or th.accent)


# ---------------------------------------------------------------------------
# Images and media
# ---------------------------------------------------------------------------

class ImageBox(Widget):
    """Image from a file path or bpy Image, rounded, with optional caption overlay and badge."""

    cursor = None

    def __init__(self, source=None, height=140, radius=None, fit="cover", caption=None, badge=None,
                 on_click=None, overlay_icon=None, aspect=None, **kw):
        super().__init__(height=height, **kw)
        self.source = source
        self.radius = radius
        self.fit = fit
        self.caption = caption
        self.badge = badge
        self.on_click_cb = on_click
        self.overlay_icon = overlay_icon
        self.aspect = aspect
        if on_click:
            self.cursor = "HAND"

    def interactive(self):
        return self.on_click_cb is not None

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        if self.aspect:
            return w, w / self.aspect
        return w, ctx.px(self.height)

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        return self.on_click_cb is not None

    def on_click(self, ctx, ev):
        call(self.on_click_cb, self)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        r = ctx.px(self.radius if self.radius is not None else th.r_md)
        hov = self.anim("hov", 1.0 if (self.hovered and self.on_click_cb) else 0.0)
        src = self.source() if callable(self.source) else self.source
        if src:
            p.image(src, x, y, w, h, radius=r, fit=self.fit)
        else:
            p.rect(x, y, w, h, fill=th.surface_3, fill2=th.surface_1, radius=r)
            isz = min(ctx.px(28), h * 0.4)
            p.icon("image", x + w / 2 - isz / 2, y + h / 2 - isz / 2, isz, th.text_muted, 1.4)
        if self.caption:
            ch = ctx.px(34)
            p.rect(x, y, w, ch, fill=(0, 0, 0, 0.0), fill2=(0, 0, 0, 0.0), radius=(0, 0, r, r))
            p.rect(x, y, w, ch * 1.6 if p.gradients else ch, fill=(0, 0, 0, 0.0), fill2=(0, 0, 0, 0.62),
                   radius=(0, 0, r, r), flat=(0, 0, 0, 0.55))
            p.text(self.caption, x + ctx.px(10), y + ctx.px(13), th.fs_sm, th.text, "medium", valign="center",
                   max_w=w - ctx.px(20))
        if self.badge:
            bw = ctx.text_w(self.badge, th.fs_xs, "semibold") + ctx.px(14)
            bh = ctx.px(19)
            bx, by = x + ctx.px(8), y + h - ctx.px(8) - bh
            p.rect(bx, by, bw, bh, fill=(0.06, 0.07, 0.07, 0.72), radius=bh / 2,
                   border=alpha((1, 1, 1, 1), 0.12), border_w=ctx.px(1))
            p.text(self.badge, bx + bw / 2, by + bh / 2, th.fs_xs, th.text, "semibold", align="center",
                   valign="center")
        if hov > 0.01:
            p.rect(x, y, w, h, fill=(0, 0, 0, 0.28 * hov), radius=r, border=alpha(th.accent, 0.7 * hov),
                   border_w=ctx.px(1.5))
            if self.overlay_icon:
                s = ctx.px(34)
                p.circle(x + w / 2, y + h / 2, s / 2, fill=alpha(th.accent, hov))
                p.icon(self.overlay_icon, x + w / 2 - s * 0.3, y + h / 2 - s * 0.3, s * 0.6, th.accent_text, 1.8)


class AssetCard(Widget):
    """Thumbnail card for galleries (image, title, meta line, model badge)."""

    cursor = "HAND"

    def __init__(self, source=None, title="", meta="", badge=None, on_click=None, selected=False,
                 thumb_aspect=1.0, **kw):
        super().__init__(**kw)
        self.source = source
        self.title = title
        self.meta = meta
        self.badge = badge
        self.on_click_cb = on_click
        self.selected = selected
        self.thumb_aspect = thumb_aspect

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        return w, w / self.thumb_aspect + ctx.px(46)

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        call(self.on_click_cb, self)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        hov = self.anim("hov", 1.0 if self.hovered else 0.0)
        sel = self.anim("sel", 1.0 if self.selected else 0.0)
        r = ctx.px(th.r_md)
        lift = ctx.px(2) * hov
        y += lift
        p.shadow(x, y, w, h, r, (0, 0, 0, 0.25 + 0.2 * hov), ctx.px(8 + 6 * hov), dy=-ctx.px(3))
        p.rect(x, y, w, h, fill=th.surface_2, radius=r,
               border=mix(mix(th.border, th.border_strong, hov), th.accent, sel), border_w=ctx.px(1 + 0.5 * sel))
        ip = ctx.px(5)
        tw = w - ip * 2
        thh = tw / self.thumb_aspect
        src = self.source() if callable(self.source) else self.source
        if src:
            p.image(src, x + ip, y + h - ip - thh, tw, thh, radius=r - ip * 0.6)
        else:
            p.rect(x + ip, y + h - ip - thh, tw, thh, fill=th.surface_3, radius=r - ip * 0.6)
        if self.badge:
            bw = ctx.text_w(self.badge, th.fs_xs, "semibold") + ctx.px(12)
            bh = ctx.px(18)
            bx, by = x + ip + ctx.px(6), y + h - ip - ctx.px(6) - bh
            p.rect(bx, by, bw, bh, fill=(0.05, 0.06, 0.06, 0.75), radius=bh / 2,
                   border=alpha((1, 1, 1, 1), 0.12), border_w=ctx.px(1))
            p.text(self.badge, bx + bw / 2, by + bh / 2, th.fs_xs, th.text, "semibold", align="center",
                   valign="center")
        ty = y + ctx.px(28)
        p.text(self.title, x + ctx.px(9), ty, th.fs_sm, th.text, "semibold", valign="center", max_w=w - ctx.px(18))
        p.text(self.meta, x + ctx.px(9), ty - ctx.px(15), th.fs_xs, th.text_muted, valign="center",
               max_w=w - ctx.px(18))


class ListView(ValueMixin, Widget):
    """Selectable rows: items = [(id, title, subtitle, icon), ...]."""

    cursor = "HAND"

    def __init__(self, items, value=None, bind=None, on_change=None, row_height=40, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change)
        self.items = _norm_items(items)
        self.row_height = row_height
        self._hov = -1

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.row_height) * len(self.items)

    def _at(self, ctx, ev):
        x, y, w, h = self.rect
        i = int((y + h - ev.y) // ctx.px(self.row_height))
        return i if 0 <= i < len(self.items) else -1

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
        if i >= 0:
            self.set_value(self.items[i][0])

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        rh = ctx.px(self.row_height)
        val = self.value
        for i, (iid, title, icon, sub) in enumerate(self.items):
            ry = y + h - rh * (i + 1)
            on = iid == val
            if on:
                p.rect(x, ry + ctx.px(2), w, rh - ctx.px(4), fill=th.selected, radius=ctx.px(8),
                       border=alpha((1, 1, 1, 1), 0.05), border_w=ctx.px(1))
                p.rect(x + ctx.px(1), ry + rh * 0.3, ctx.px(3), rh * 0.4, fill=th.accent, radius=ctx.px(1.5))
            elif i == self._hov:
                p.rect(x, ry + ctx.px(2), w, rh - ctx.px(4), fill=alpha(th.surface_3, 0.6), radius=ctx.px(8))
            cx = x + ctx.px(12)
            if icon:
                s = ctx.px(26)
                p.rect(cx, ry + (rh - s) / 2, s, s, fill=th.surface_3, radius=ctx.px(7),
                       border=th.border_strong, border_w=ctx.px(1))
                p.icon(icon, cx + ctx.px(5.5), ry + (rh - s) / 2 + ctx.px(5.5), ctx.px(15),
                       th.accent if on else th.text_dim, 1.5)
                cx += s + ctx.px(10)
            if sub:
                p.text(title, cx, ry + rh * 0.64, th.fs_md, th.text, "medium", valign="center", max_w=x + w - cx - 6)
                p.text(sub, cx, ry + rh * 0.3, th.fs_xs, th.text_muted, valign="center", max_w=x + w - cx - 6)
            else:
                p.text(title, cx, ry + rh / 2, th.fs_md, th.text if on else th.text_dim, "medium",
                       valign="center", max_w=x + w - cx - 6)


class ColorSwatches(ValueMixin, Widget):
    """Pick a color from swatches. Bind to a FloatVectorProperty(subtype='COLOR')."""

    cursor = "HAND"

    def __init__(self, colors, value=None, bind=None, on_change=None, size=22, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change)
        self.colors = [c if len(c) == 4 else (c[0], c[1], c[2], 1.0) for c in colors]
        self.size = size
        self._hov = -1
        self._pos = []

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        s = ctx.px(self.size)
        g = ctx.px(8)
        per = max(1, int((w + g) // (s + g)))
        rows = (len(self.colors) + per - 1) // per
        self._per = per
        return w, rows * s + (rows - 1) * g + ctx.px(4)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        s = ctx.px(self.size)
        g = ctx.px(8)
        self._pos = []
        for i in range(len(self.colors)):
            r, c = divmod(i, self._per)
            self._pos.append((x + ctx.px(2) + c * (s + g) + s / 2, y + h - ctx.px(2) - r * (s + g) - s / 2))

    def _at(self, ctx, ev):
        s = ctx.px(self.size) / 2 + ctx.px(2)
        for i, (cx, cy) in enumerate(self._pos):
            if (ev.x - cx) ** 2 + (ev.y - cy) ** 2 <= s * s:
                return i
        return -1

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
        c = self.colors[i]
        cur = self.value
        n = len(cur) if cur is not None and hasattr(cur, "__len__") else 4
        self.set_value(tuple(c[:n]))
        if self.bind:
            self.bind.push_undo("Pick color")

    def _is_sel(self, c):
        v = self.value
        if v is None:
            return False
        return all(abs(a - b) < 0.01 for a, b in zip(v, c))

    def paint(self, ctx, p):
        th = ctx.theme
        s = ctx.px(self.size) / 2
        for i, (c, (cx, cy)) in enumerate(zip(self.colors, self._pos)):
            sel = self._is_sel(c)
            t = self.anim("s%d" % i, 1.0 if sel else 0.0)
            hov = 1.0 if i == self._hov else 0.0
            if t > 0.01:
                p.circle(cx, cy, s + ctx.px(3), fill=alpha(th.bg, 0), border=alpha(th.text, t), border_w=ctx.px(1.6))
            r = s - ctx.px(1) * (1 - hov) + ctx.px(1) * hov
            p.shadow(cx - r, cy - r, r * 2, r * 2, r, alpha(c, 0.35 * hov), ctx.px(6))
            p.circle(cx, cy, r, fill=lighten(c, 0.08), fill2=c, border=alpha((1, 1, 1, 1), 0.15), border_w=ctx.px(1))


class Avatar(Widget):
    def __init__(self, initials="", image=None, size=30, color=None, status=None, **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self.initials = initials
        self.image = image
        self.size = size
        self.color = color
        self.status = status

    def natural_width(self, ctx):
        return ctx.px(self.size)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.size)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        s = ctx.px(self.size)
        cx, cy = x + w / 2, y + h / 2
        if self.image:
            p.image(self.image, cx - s / 2, cy - s / 2, s, s, radius=s / 2)
        else:
            c = th.color(self.color) or th.accent
            p.circle(cx, cy, s / 2, fill=alpha(c, 0.22), border=alpha(c, 0.45), border_w=ctx.px(1))
            p.text(self.initials, cx, cy, self.size * 0.34, c, "semibold", align="center", valign="center")
        if self.status:
            sc = {"online": th.success, "busy": th.danger, "away": th.warning}.get(self.status, th.text_muted)
            r = s * 0.16
            p.circle(cx + s * 0.34, cy - s * 0.34, r + ctx.px(2), fill=th.bg)
            p.circle(cx + s * 0.34, cy - s * 0.34, r, fill=sc)


class Alert(Widget):
    """Callout box: kind = info, success, warning, danger, accent."""

    def __init__(self, text, title=None, kind="info", icon=None, **kw):
        super().__init__(**kw)
        self.text = text
        self.title = title
        self.kind = kind
        self.icon = icon

    def _c(self, th):
        return {"success": th.success, "warning": th.warning, "danger": th.danger,
                "accent": th.accent}.get(self.kind, th.info)

    def measure(self, ctx, avail_w):
        th = ctx.theme
        w = self.resolve_width(ctx, avail_w)
        inner = w - ctx.px(12 + 18 + 10 + 12)
        self._lines = wrap_text(self.text, ctx.px(th.fs_sm), max(20.0, inner))
        h = ctx.px(th.fs_sm) * 1.5 * len(self._lines) + ctx.px(20)
        if self.title:
            h += ctx.px(18)
        return w, h

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        c = self._c(th)
        r = ctx.px(10)
        p.rect(x, y, w, h, fill=alpha(c, 0.10), radius=r, border=alpha(c, 0.28), border_w=ctx.px(1))
        icon = self.icon or {"success": "success", "warning": "warning", "danger": "error",
                             "accent": "sparkles"}.get(self.kind, "info")
        isz = ctx.px(17)
        top = y + h - ctx.px(10)
        p.icon(icon, x + ctx.px(12), top - isz, isz, c, 1.6)
        tx = x + ctx.px(12 + 18 + 10)
        if self.title:
            p.text(self.title, tx, top - ctx.px(8), th.fs_md, th.text, "semibold", valign="center")
            top -= ctx.px(18)
        lh = ctx.px(th.fs_sm) * 1.5
        for line, _i in self._lines:
            p.text(line.rstrip(), tx, top - lh / 2, th.fs_sm, th.text_dim, valign="center")
            top -= lh


class KeyValue(Widget):
    def __init__(self, key, value, icon=None, **kw):
        super().__init__(**kw)
        self.key_text = key
        self.val = value
        self.icon = icon

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(24)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        cx = x
        if self.icon:
            p.icon(self.icon, x, y + h / 2 - ctx.px(7), ctx.px(14), th.text_muted, 1.5)
            cx += ctx.px(20)
        p.text(self.key_text, cx, y + h / 2, th.fs_sm, th.text_muted, valign="center")
        v = self.val() if callable(self.val) else self.val
        p.text(str(v), x + w, y + h / 2, th.fs_sm, th.text, "medium", align="right", valign="center",
               max_w=w * 0.6)


class Rating(ValueMixin, Widget):
    cursor = "HAND"

    def __init__(self, value=3, count=5, bind=None, on_change=None, size=18, **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self._init_value(value, bind, on_change, 0)
        self.count = count
        self.size = size
        self._hov = -1

    def interactive(self):
        return True

    def natural_width(self, ctx):
        return ctx.px(self.size + 4) * self.count

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.size + 4)

    def _at(self, ctx, ev):
        i = int((ev.x - self.rect[0]) // ctx.px(self.size + 4))
        return i if 0 <= i < self.count else -1

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
        if i >= 0:
            self.set_value(i + 1)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        s = ctx.px(self.size)
        shown = (self._hov + 1) if self._hov >= 0 else int(self.value or 0)
        for i in range(self.count):
            on = i < shown
            sx = x + i * ctx.px(self.size + 4)
            c = th.accent if on else th.text_disabled
            if on:
                p.sparkle(sx + s / 2, y + h / 2, s * 0.48, c, 0.75)
            else:
                p.icon("sparkle", sx, y + (h - s) / 2, s, c, 1.3)


# ---------------------------------------------------------------------------
# Preview enums (thumbnail pickers)
# ---------------------------------------------------------------------------

def _preview_items(widget):
    """[(id, label, image, description)] from explicit items or a bound EnumProperty + images."""
    src = widget._items_src
    if callable(src):
        src = src()
    if src is None and widget.bind is not None:
        src = [(i, n, None, d) for i, n, d in widget.bind.enum_items()]
    items = _norm_items(src or [])
    imgs = widget.images
    if imgs is not None:
        out = []
        for iid, label, img, desc in items:
            if img is None:
                img = imgs(iid) if callable(imgs) else imgs.get(iid)
            out.append((iid, label, img, desc))
        items = out
    return items


class PreviewGrid(ValueMixin, Widget):
    """Pick an enum value from image tiles.

        PreviewGrid([("NEON", "Neon", "/path/neon.png", "Glowing signs"), ...], value="NEON")
        PreviewGrid(bind="scene.my.style", images={"NEON": path, ...})   # enum from Blender
        PreviewGrid(bind=..., images=lambda item_id: pcoll[item_id])     # bpy.utils.previews

    Images can be file paths, bpy Images or ImagePreview objects from bpy.utils.previews.
    """

    cursor = "HAND"

    def __init__(self, items=None, value=None, bind=None, on_change=None, images=None, min_cell=84,
                 cols=None, aspect=1.0, show_labels=True, on_pick=None, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change)
        self._items_src = items
        self.images = images
        self.min_cell = min_cell
        self.cols = cols
        self.aspect = aspect
        self.show_labels = show_labels
        self.on_pick = on_pick
        self._hov = -1
        self._cells = []

    @property
    def items(self):
        return _preview_items(self)

    def interactive(self):
        return True

    def _layout(self, ctx, w):
        g = ctx.px(8)
        n = self.cols or max(1, int((w + g) // (ctx.px(self.min_cell) + g)))
        cw = (w - g * (n - 1)) / n
        lab = ctx.px(22) if self.show_labels else 0.0
        ch = cw / self.aspect + lab
        return n, cw, ch, g

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        n, cw, ch, g = self._layout(ctx, w)
        rows = max(1, (len(self.items) + n - 1) // n)
        return w, rows * ch + (rows - 1) * g

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        n, cw, ch, g = self._layout(ctx, w)
        self._cells = []
        for i in range(len(self.items)):
            r, c = divmod(i, n)
            self._cells.append((x + c * (cw + g), y + h - (r + 1) * ch - r * g, cw, ch))

    def _at(self, ev):
        for i, (cx, cy, cw, ch) in enumerate(self._cells):
            if cx <= ev.x <= cx + cw and cy <= ev.y <= cy + ch:
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
        return self.is_enabled

    def on_click(self, ctx, ev):
        i = self._at(ev)
        items = self.items
        if 0 <= i < len(items):
            self.set_value(items[i][0])
            if self.bind:
                self.bind.push_undo("Pick " + items[i][1])
            call(self.on_pick, items[i][0], self)

    def paint(self, ctx, p):
        th = ctx.theme
        val = self.value
        lab = ctx.px(22) if self.show_labels else 0.0
        r = ctx.px(th.r_md)
        for i, ((iid, label, img, desc), (x, y, w, h)) in enumerate(zip(self.items, self._cells)):
            if not p.clip_visible(x, y, w, h):
                continue
            on = iid == val
            t = self.anim("s%d" % i, 1.0 if on else 0.0)
            hov = self.anim("h%d" % i, 1.0 if i == self._hov else 0.0)
            ty = y + lab
            th_h = h - lab
            if t > 0.01:
                p.shadow(x, ty, w, th_h, r, alpha(th.accent, 0.28 * t), ctx.px(10))
            p.rect(x - ctx.px(2), ty - ctx.px(2), w + ctx.px(4), th_h + ctx.px(4), radius=r + ctx.px(2),
                   fill=alpha(th.surface_0, 0.0), border=mix(alpha(th.border_strong, 0.0), th.accent, t),
                   border_w=ctx.px(1.6))
            if img is not None:
                p.image(img, x, ty, w, th_h, radius=r)
            else:
                p.rect(x, ty, w, th_h, fill=th.surface_3, fill2=th.surface_1, radius=r)
                p.text(label[:1].upper(), x + w / 2, ty + th_h / 2, th.fs_xl, th.text_muted, "semibold",
                       align="center", valign="center")
            if hov > 0.01 and t < 0.99:
                p.rect(x, ty, w, th_h, fill=alpha((1, 1, 1, 1), 0.07 * hov), radius=r)
            if t > 0.01:
                cr = ctx.px(8)
                ccx, ccy = x + w - cr - ctx.px(5), ty + th_h - cr - ctx.px(5)
                p.circle(ccx, ccy, cr * (0.6 + 0.4 * t), fill=alpha(th.accent, t))
                p.icon("check", ccx - cr * 0.6, ccy - cr * 0.6, cr * 1.2, alpha(th.accent_text, t), 2.2)
            if self.show_labels:
                p.text(label, x + w / 2, y + lab * 0.45, th.fs_sm, mix(th.text_dim, th.text, max(t, hov)),
                       "medium" if on else "regular", align="center", valign="center", max_w=w)


class PreviewDropdown(ValueMixin, Widget):
    """A field showing the current preview; click to open a popover grid of previews.
    Same items / bind / images options as PreviewGrid."""

    cursor = "HAND"

    def __init__(self, items=None, value=None, bind=None, on_change=None, images=None, label=None,
                 thumb=44, grid_cell=84, grid_cols=None, menu_width=None, aspect=1.0, **kw):
        super().__init__(**kw)
        self._init_value(value, bind, on_change)
        self._items_src = items
        self.images = images
        self.label = label
        self.thumb = thumb
        self.grid_cell = grid_cell
        self.grid_cols = grid_cols
        self.menu_width = menu_width
        self.aspect = aspect
        self._open = False

    @property
    def items(self):
        return _preview_items(self)

    def _current(self):
        v = self.value
        for it in self.items:
            if it[0] == v:
                return it
        return None

    def interactive(self):
        return True

    def natural_width(self, ctx):
        cur = self._current()
        return ctx.px(self.thumb + 50) + ctx.text_w(cur[1] if cur else "Select", ctx.theme.fs_md, "medium")

    def measure(self, ctx, avail_w):
        lab = ctx.px(20) if self.label else 0.0
        return self.resolve_width(ctx, avail_w), ctx.px(self.thumb + 12) + lab

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
        dd = self

        def picked(item_id, grid):
            p = grid.parent
            while p is not None and not hasattr(p, "close"):
                p = p.parent
            if p is not None:
                p.close()

        grid = PreviewGrid(self._items_src, value=self.value, images=self.images, min_cell=self.grid_cell,
                           cols=self.grid_cols, aspect=self.aspect, on_pick=picked,
                           on_change=lambda v, g: dd.set_value(v))
        if self.bind is not None:
            grid.bind = self.bind
            grid._items_src = self._items_src
        from .layout import Column
        content = Column(grid, padding=8)
        self._open = True

        def closed(*_):
            self._open = False
            self.redraw()

        x, y, w, h = self.rect
        mw = ctx.px(self.menu_width) if self.menu_width else max(w, ctx.px(260))
        ctx.surface.open_popover(content, anchor=self, width=mw, on_close=closed)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        if self.label:
            p.text(self.label, x, y + h - ctx.px(8), th.fs_sm, th.text_dim, "medium", valign="center")
            h -= ctx.px(20)
        hov = self.anim("hov", 1.0 if (self.hovered or self._open) else 0.0)
        r = ctx.px(th.r_md + 1)
        p.rect(x, y, w, h, fill=mix(th.surface_3, th.surface_4, hov * 0.5), radius=r,
               border=mix(th.border_strong, alpha(th.accent, 0.6), 1.0 if self._open else hov * 0.45),
               border_w=ctx.px(1))
        cur = self._current()
        ts = ctx.px(self.thumb)
        tx, ty = x + ctx.px(6), y + (h - ts) / 2
        if cur and cur[2] is not None:
            p.image(cur[2], tx, ty, ts * self.aspect if self.aspect < 1 else ts, ts, radius=ctx.px(th.r_sm))
        else:
            p.rect(tx, ty, ts, ts, fill=th.surface_1, radius=ctx.px(th.r_sm))
        cx = tx + ts + ctx.px(10)
        right = x + w - ctx.px(30)
        if cur:
            if cur[3] and self.thumb >= 30:
                p.text(cur[1], cx, y + h * 0.62, th.fs_md, th.text, "medium", valign="center", max_w=right - cx)
                p.text(cur[3], cx, y + h * 0.34, th.fs_xs, th.text_muted, valign="center", max_w=right - cx)
            else:
                p.text(cur[1], cx, y + h / 2, th.fs_md, th.text, "medium", valign="center", max_w=right - cx)
        else:
            p.text("Select", cx, y + h / 2, th.fs_md, th.text_muted, valign="center")
        isz = ctx.px(14)
        p.icon("chevron_up" if self._open else "chevron_down", x + w - ctx.px(12) - isz, y + h / 2 - isz / 2,
               isz, mix(th.text_dim, th.accent, 1.0 if self._open else 0.0), 1.7)
