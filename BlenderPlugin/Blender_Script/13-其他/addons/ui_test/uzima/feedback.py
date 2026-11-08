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

"""Overlays and feedback: command palette, pie menu, drawer, guided tour, notification bell,
banner, skeleton loaders, empty state, hold-to-confirm button."""

import math
import time

from .core import Widget, call, mark_animating, ease_out_back, ease_out_cubic
from .layout import Column, Row, ScrollView
from .overlays import MenuItem, Overlay, Popover
from .theme import alpha, mix, lighten
from .widgets import Button, TextInput
from .draw import wrap_text


# ---------------------------------------------------------------------------
# helpers to find where to show things
# ---------------------------------------------------------------------------

def viewport_target(app, info=None):
    """(surface, area, region) of the 3D viewport the user is working in."""
    import bpy
    surf = app.first_viewport()
    if surf is None:
        return None, None, None
    area = (info or {}).get("area") if info else None
    if area is None or area.type != "VIEW_3D":
        area = None
        wm = bpy.context.window_manager
        for win in wm.windows:
            scr = win.screen
            for a in (scr.areas if scr else []):
                if a.type == "VIEW_3D" and (app.last_area_ptr is None or a.as_pointer() == app.last_area_ptr):
                    area = a
                    break
            if area:
                break
        if area is None:
            for win in wm.windows:
                for a in (win.screen.areas if win.screen else []):
                    if a.type == "VIEW_3D":
                        area = a
                        break
    if area is None:
        return surf, None, None
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    return surf, area, region


# ---------------------------------------------------------------------------
# Command palette
# ---------------------------------------------------------------------------

_op_index = None


def _blender_operators():
    global _op_index
    if _op_index is not None:
        return _op_index
    import bpy
    out = []
    for mod in dir(bpy.ops):
        if mod.startswith("_") or mod in ("uzima",):
            continue
        sub = getattr(bpy.ops, mod)
        for name in dir(sub):
            if name.startswith("_"):
                continue
            try:
                rna = getattr(sub, name).get_rna_type()
            except Exception:
                continue
            if "INTERNAL" in rna.bl_rna.properties and False:
                continue
            label = rna.name or name.replace("_", " ").title()
            desc = (rna.description or "").split("\n")[0]
            out.append(("%s.%s" % (mod, name), label, desc))
    _op_index = out
    return out


class CommandPalette(Overlay):
    """Search box that runs anything: your app actions, and (optionally) every Blender operator.

        app.command_palette()                  # or bind the built-in "command_palette" action to a key
    Up/Down to move, Enter to run, Esc to close."""

    modal = True
    dismiss_outside = True
    esc_closes = True
    layer = 7
    focusable = True

    def __init__(self, app, include_blender=True, extra=None, placeholder="Type a command…"):
        super().__init__()
        self.app = app
        self.include_blender = include_blender
        self.extra = extra or []
        self.search = TextInput(placeholder, icon="command", clearable=False, variant="bare",
                                on_change=lambda v, w: self._refresh())
        self.search.parent = self
        self.results = []
        self.sel = 0
        self.scroll = 0
        self._refresh()

    def children(self):
        return (self.search,)

    def _score(self, text, q):
        t = text.lower()
        words = q.split()
        if not all(w in t for w in words):
            return None
        return (0 if t.startswith(q) else 1, len(t))

    def _refresh(self):
        q = self.search.text.strip().lower()
        res = []
        for a in self.app.actions.values():
            if a.name.startswith("_"):
                continue
            hay = "%s %s %s" % (a.label, a.name, a.description)
            sc = self._score(hay, q) if q else (0, 0)
            if sc is not None:
                res.append((sc, ("action", a.name, a.label, a.icon or "sparkle", a.description,
                                 str(a.hotkey) if a.hotkey else "")))
        for it in self.extra:
            hay = "%s %s" % (it.label, it.description or "")
            sc = self._score(hay, q) if q else (0, 0)
            if sc is not None:
                res.append((sc, ("item", it, it.label, it.icon or "dot", it.description or "", it.shortcut or "")))
        res.sort(key=lambda r: r[0])
        out = [r[1] for r in res]
        if self.include_blender and len(q) >= 2:
            ops = []
            for idname, label, desc in _blender_operators():
                sc = self._score("%s %s" % (label, idname), q)
                if sc is not None:
                    ops.append((sc, ("operator", idname, label, "bolt", idname, "")))
            ops.sort(key=lambda r: r[0])
            out += [r[1] for r in ops[:40]]
        self.results = out
        self.sel = 0
        self.scroll = 0
        self.redraw()

    def _run(self, i):
        if not (0 <= i < len(self.results)):
            return
        kind, ref, label, *_ = self.results[i]
        self.close()
        if kind == "action":
            self.app.run_action(ref)
        elif kind == "item":
            ref.run(self.app)
        else:
            from . import run_operator
            try:
                run_operator(ref, invoke=True)
            except Exception as e:
                self.app.toast("Couldn't run " + label, str(e).split("\n")[0], "danger")

    def interactive(self):
        return True

    def place(self, ctx, rx, ry, rw, rh):
        self._region = (rx, ry, rw, rh)
        w = min(ctx.px(520), rw - ctx.px(32))
        rows = min(9, max(1, len(self.results)))
        self._rh = ctx.px(40)
        h = ctx.px(52) + self._rh * rows + ctx.px(28)
        x = rx + (rw - w) / 2
        y = ry + rh - ctx.px(70) - h
        self.rect = (x, y, w, h)
        self.search.measure(ctx, w - ctx.px(28))
        self.search.arrange(ctx, x + ctx.px(16), y + h - ctx.px(44), w - ctx.px(32), ctx.px(36))

    def hit(self, x, y):
        if self.contains(x, y):
            return self
        return self  # modal: swallow

    def _row_at(self, ctx, ev):
        x, y, w, h = self.rect
        top = y + h - ctx.px(52)
        if not (x <= ev.x <= x + w) or ev.y > top or ev.y < y + ctx.px(28):
            return -1
        i = int((top - ev.y) // self._rh) + self.scroll
        return i if i < len(self.results) else -1

    def on_hover(self, ctx, ev):
        i = self._row_at(ctx, ev)
        if i >= 0 and i != self.sel:
            self.sel = i
            self.redraw()

    def on_press(self, ctx, ev):
        if not self.contains(ev.x, ev.y):
            self.close()
            return False
        return True

    def on_click(self, ctx, ev):
        i = self._row_at(ctx, ev)
        if i >= 0:
            self._run(i)

    def on_wheel(self, ctx, ev):
        self.scroll = max(0, min(max(0, len(self.results) - 9), self.scroll - int(ev.wheel)))
        self.redraw()
        return True

    def on_key(self, ctx, ev):
        if ev.type == "ESC":
            self.close()
            return True
        if ev.type in ("DOWN_ARROW", "UP_ARROW"):
            self.sel = max(0, min(len(self.results) - 1, self.sel + (1 if ev.type == "DOWN_ARROW" else -1)))
            if self.sel < self.scroll:
                self.scroll = self.sel
            elif self.sel >= self.scroll + 9:
                self.scroll = self.sel - 8
            self.redraw()
            return True
        if ev.type in ("RET", "NUMPAD_ENTER"):
            self._run(self.sel)
            return True
        self.search.focused = True
        before = self.search.text
        self.search.on_key(ctx, ev)
        if self.search.text != before:
            self._refresh()
        return True

    @property
    def text_entry(self):
        return True

    def paint(self, ctx, p):
        th = ctx.theme
        rx, ry, rw, rh = self._region
        t = ease_out_cubic(self.appear(16))
        p.rect(rx, ry, rw, rh, fill=alpha(th.overlay, th.overlay[3] * 0.6 * t))
        x, y, w, h = self.rect
        y += (1 - t) * ctx.px(12)
        r = ctx.px(16)
        p.shadow(x, y, w, h, r, (0, 0, 0, 0.6 * t), ctx.px(30), dy=-ctx.px(10))
        p.rect(x, y, w, h, fill=th.surface_2, fill2=th.surface_1, radius=r, border=th.border_strong, border_w=ctx.px(1))
        self.search.focused = True
        self.search.paint(ctx, p)
        top = y + h - ctx.px(52)
        p.rect(x, top, w, ctx.px(1), fill=th.border)
        if not self.results:
            p.text("No matches", x + w / 2, top - self._rh / 2, th.fs_sm, th.text_muted, align="center",
                   valign="center")
        last_kind = None
        for k, i in enumerate(range(self.scroll, min(len(self.results), self.scroll + 9))):
            kind, ref, label, icon, desc, short = self.results[i]
            ry_ = top - self._rh * (k + 1)
            if i == self.sel:
                p.rect(x + ctx.px(6), ry_ + ctx.px(2), w - ctx.px(12), self._rh - ctx.px(4), fill=th.surface_4,
                       radius=ctx.px(9))
                p.rect(x + ctx.px(6), ry_ + self._rh * 0.3, ctx.px(2.5), self._rh * 0.4, fill=th.accent,
                       radius=ctx.px(1.2))
            ix = x + ctx.px(18)
            cy = ry_ + self._rh / 2
            p.rect(ix, cy - ctx.px(13), ctx.px(26), ctx.px(26), fill=th.surface_3 if kind != "operator" else
                   alpha(th.info, 0.15), radius=ctx.px(7))
            p.icon(icon, ix + ctx.px(6), cy - ctx.px(7), ctx.px(14), th.accent if kind != "operator" else th.info, 1.5)
            tx = ix + ctx.px(36)
            right = x + w - ctx.px(16)
            if short:
                sw = ctx.text_w(short, th.fs_xs, "semibold") + ctx.px(12)
                p.rect(right - sw, cy - ctx.px(9), sw, ctx.px(18), fill=th.surface_3, radius=ctx.px(5),
                       border=th.border_strong, border_w=ctx.px(1))
                p.text(short, right - sw / 2, cy, th.fs_xs, th.text_dim, "semibold", align="center", valign="center")
                right -= sw + ctx.px(8)
            elif kind == "operator":
                p.text("Blender", right, cy, th.fs_xs, th.text_muted, align="right", valign="center")
                right -= ctx.px(52)
            p.text(label, tx, cy + ctx.px(6) if desc else cy, th.fs_md, th.text, "medium", valign="center",
                   max_w=right - tx)
            if desc:
                p.text(desc, tx, cy - ctx.px(8), th.fs_xs, th.text_muted, valign="center", max_w=right - tx)
        hint = "↑↓ to move  ·  Enter to run  ·  Esc to close"
        p.text(hint, x + w / 2, y + ctx.px(14), th.fs_xs, th.text_muted, align="center", valign="center")


# ---------------------------------------------------------------------------
# Pie menu
# ---------------------------------------------------------------------------

_PIE_ANGLES = [180, 0, 270, 90, 135, 45, 225, 315]   # W, E, S, N, NW, NE, SW, SE (like Blender)


class PieMenu(Overlay):
    """Radial menu around a point in the viewport. items: up to 8 MenuItems
    (order: left, right, bottom, top, top-left, top-right, bottom-left, bottom-right)."""

    modal = True
    esc_closes = True
    layer = 8

    def __init__(self, items, at, title=None, radius=100):
        super().__init__()
        self.items = [it for it in items if isinstance(it, MenuItem)][:8]
        self.at = at
        self.title = title
        self.radius = radius
        self.sel = -1
        self._mouse = at

    def place(self, ctx, rx, ry, rw, rh):
        self._region = (rx, ry, rw, rh)
        self.rect = (rx, ry, rw, rh)
        r = ctx.px(self.radius)
        m = r + ctx.px(70)
        cx = min(max(rx + m, self.at[0]), rx + rw - m)
        cy = min(max(ry + r + ctx.px(30), self.at[1]), ry + rh - r - ctx.px(30))
        self.center = (cx, cy)

    def hit(self, x, y):
        return self

    def interactive(self):
        return True

    def _slot(self, ctx, x, y):
        cx, cy = self.center
        dx, dy = x - cx, y - cy
        if math.hypot(dx, dy) < ctx.px(22):
            return -1
        ang = math.degrees(math.atan2(dy, dx)) % 360
        best, bd = -1, 999
        for i in range(len(self.items)):
            d = abs((ang - _PIE_ANGLES[i] + 180) % 360 - 180)
            if d < bd:
                best, bd = i, d
        return best

    def on_hover(self, ctx, ev):
        self._mouse = (ev.x, ev.y)
        s = self._slot(ctx, ev.x, ev.y)
        if s != self.sel:
            self.sel = s
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        s = self._slot(ctx, ev.x, ev.y)
        self.close()
        if s >= 0 and self.items[s].is_enabled():
            self.items[s].run(self.surface.app)

    def paint(self, ctx, p):
        th = ctx.theme
        t = ease_out_back(self.appear(14), 1.3)
        cx, cy = self.center
        r = ctx.px(self.radius) * (0.6 + 0.4 * t)
        p.circle(cx, cy, ctx.px(26), fill=alpha(th.surface_1, 0.9), border=th.border_strong, border_w=ctx.px(1))
        if self.sel >= 0:
            a = math.radians(_PIE_ANGLES[self.sel])
            p.arc(cx, cy, ctx.px(21), a - 0.45, 0.9, ctx.px(4), th.accent)
        mx, my = self._mouse
        if math.hypot(mx - cx, my - cy) > ctx.px(4):
            a = math.atan2(my - cy, mx - cx)
            p.circle(cx + math.cos(a) * ctx.px(12), cy + math.sin(a) * ctx.px(12), ctx.px(3), fill=th.text_dim)
        if self.title:
            p.text(self.title, cx, cy + ctx.px(40), th.fs_sm, th.text_dim, "semibold", align="center", valign="center")
        for i, it in enumerate(self.items):
            a = math.radians(_PIE_ANGLES[i])
            ix, iy = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.82
            on = i == self.sel
            tw = ctx.text_w(it.label, th.fs_md, "medium")
            bw = tw + ctx.px(46 if it.icon else 26)
            bh = ctx.px(32)
            bx = ix - bw / 2
            if abs(math.cos(a)) > 0.6:
                bx = ix - bw if math.cos(a) < 0 else ix
                bx += ctx.px(16) * (-1 if math.cos(a) < 0 else 1) * 0
            p.shadow(bx, iy - bh / 2, bw, bh, bh / 2, (0, 0, 0, 0.45 * t), ctx.px(10), dy=-ctx.px(3))
            p.rect(bx, iy - bh / 2, bw, bh, fill=th.accent if on else th.surface_2, radius=bh / 2,
                   border=th.border_strong if not on else alpha(th.accent_hi, 0.8), border_w=ctx.px(1))
            col = th.accent_text if on else th.text
            tx = bx + ctx.px(13)
            if it.icon:
                p.icon(it.icon, tx, iy - ctx.px(7.5), ctx.px(15), col, 1.6)
                tx += ctx.px(21)
            p.text(it.label, tx, iy, th.fs_md, col, "medium", valign="center")


# ---------------------------------------------------------------------------
# Drawer
# ---------------------------------------------------------------------------

class Drawer(Overlay):
    """Panel that slides in from the left or right edge of the viewport. Click outside or Esc closes it."""

    dismiss_outside = True
    esc_closes = True
    layer = 4

    def __init__(self, content, title=None, icon=None, side="right", width=320, backdrop=True):
        super().__init__()
        self.title = title
        self.icon = icon
        self.side = side
        self.w_dp = width
        self.backdrop = backdrop
        self.body = ScrollView(content, padding=14)
        self.body.parent = self
        self.close_btn = Button("", icon="x", variant="ghost", size="sm", width="auto", on_click=lambda b: self.close())
        self.close_btn.parent = self

    def children(self):
        return (self.body, self.close_btn)

    def interactive(self):
        return True

    def place(self, ctx, rx, ry, rw, rh):
        self._region = (rx, ry, rw, rh)
        w = min(ctx.px(self.w_dp), rw - ctx.px(40))
        x = rx + rw - w if self.side == "right" else rx
        self.rect = (x, ry, w, rh)
        head = ctx.px(52) if self.title else ctx.px(10)
        self.body.measure(ctx, w)
        self.body.arrange(ctx, x, ry, w, rh - head)
        self.close_btn.measure(ctx, w)
        self.close_btn.arrange(ctx, x + w - ctx.px(40), ry + rh - ctx.px(40), ctx.px(28), ctx.px(28))

    def hit(self, x, y):
        if not self.contains(x, y):
            return None
        return self.close_btn.hit(x, y) or self.body.hit(x, y) or self

    def paint(self, ctx, p):
        th = ctx.theme
        rx, ry, rw, rh = self._region
        t = ease_out_cubic(self.appear(12))
        if self.backdrop:
            p.rect(rx, ry, rw, rh, fill=alpha(th.overlay, th.overlay[3] * 0.7 * t))
        x, y, w, h = self.rect
        off = (1 - t) * w * (1 if self.side == "right" else -1)
        if off:
            self.body.arrange(ctx, x + off, y, w, self.body.rect[3])
        p.shadow(x + off, y, w, h, 0, (0, 0, 0, 0.5 * t), ctx.px(24))
        p.rect(x + off, y, w, h, fill=th.surface_1, radius=(ctx.px(16), 0, 0, ctx.px(16)) if self.side == "right" else
               (0, ctx.px(16), ctx.px(16), 0), border=th.border_strong, border_w=ctx.px(1))
        if self.title:
            tx = x + off + ctx.px(16)
            ty = y + h - ctx.px(26)
            if self.icon:
                p.icon(self.icon, tx, ty - ctx.px(8), ctx.px(16), th.accent, 1.6)
                tx += ctx.px(24)
            p.text(self.title, tx, ty, th.fs_lg, th.text, "semibold", valign="center")
            p.rect(x + off, y + h - ctx.px(52), w, ctx.px(1), fill=th.border)
        self.body.fade_color = th.surface_1
        self.body.paint(ctx, p)
        if not off:
            self.close_btn.paint(ctx, p)


# ---------------------------------------------------------------------------
# Tour
# ---------------------------------------------------------------------------

class Tour(Overlay):
    """Step-by-step walkthrough that points at widgets.

        surface.tour([("create_btn", "Create", "Press here to make your first mesh."), ...])
    Targets are widget keys (key="create_btn") or widget objects."""

    modal = True
    esc_closes = True
    layer = 9

    def __init__(self, steps, on_finish=None):
        super().__init__()
        self.steps = steps
        self.i = 0
        self.on_finish = on_finish
        self.btn_skip = Button("Skip", variant="ghost", size="sm", width="auto", on_click=lambda b: self.finish())
        self.btn_back = Button("Back", variant="secondary", size="sm", width="auto", on_click=lambda b: self.go(-1))
        self.btn_next = Button("Next", variant="primary", size="sm", width="auto", icon_right="chevron_right",
                               on_click=lambda b: self.go(1))
        self.row = Row(self.btn_skip, self.btn_back, self.btn_next, gap=6, justify="end")
        self.row.parent = self
        self._target = None

    def children(self):
        return (self.row,)

    def go(self, d):
        self.i += d
        if self.i >= len(self.steps):
            self.finish()
            return
        self.i = max(0, self.i)
        self.set_anim("ring", 0.0)
        self._reveal()
        self.redraw()

    def finish(self):
        self.close()
        call(self.on_finish, self)

    def _target_widget(self):
        key = self.steps[self.i][0]
        if isinstance(key, Widget):
            return key
        root = self.surface.root if self.surface is not None else None
        return root.find(key) if root is not None else None

    def _reveal(self):
        w = self._target_widget()
        if w is not None and self.surface is not None:
            self.surface.app._reveal(w)

    def interactive(self):
        return True

    def hit(self, x, y):
        r = self.row.hit(x, y)
        return r or self

    def place(self, ctx, rx, ry, rw, rh):
        th = ctx.theme
        self._region = (rx, ry, rw, rh)
        self.btn_back.visible = self.i > 0
        self.btn_next.text = "Done" if self.i == len(self.steps) - 1 else "Next"
        tw = self._target_widget()
        self._target = tw.rect if tw is not None and tw.visible else None
        w = min(ctx.px(270), rw - ctx.px(20))
        _key, title, text = self.steps[self.i][:3]
        self._lines = wrap_text(text, ctx.px(th.fs_sm), w - ctx.px(28))
        h = ctx.px(38) + ctx.px(th.fs_sm * 1.5) * len(self._lines) + ctx.px(52)
        if self._target:
            x0, y0, w0, h0 = self._target
            x = min(max(rx + ctx.px(10), x0 + w0 / 2 - w / 2), rx + rw - w - ctx.px(10))
            y = y0 - ctx.px(14) - h
            if y < ry + ctx.px(10):
                y = y0 + h0 + ctx.px(14)
        else:
            x, y = rx + (rw - w) / 2, ry + (rh - h) / 2
        self.rect = (x, y, w, h)
        self.row.measure(ctx, w - ctx.px(24))
        self.row.arrange(ctx, x + ctx.px(12), y + ctx.px(12), w - ctx.px(24), ctx.px(26))

    def contains(self, x, y):
        return True

    def paint(self, ctx, p):
        th = ctx.theme
        rx, ry, rw, rh = self._region
        t = self.appear(10)
        dim = alpha(th.overlay, th.overlay[3] * 0.9 * t)
        if self._target:
            x0, y0, w0, h0 = self._target
            k = ctx.px(6)
            x0, y0, w0, h0 = x0 - k, y0 - k, w0 + 2 * k, h0 + 2 * k
            p.rect(rx, ry, rw, y0 - ry, fill=dim)
            p.rect(rx, y0 + h0, rw, ry + rh - y0 - h0, fill=dim)
            p.rect(rx, y0, x0 - rx, h0, fill=dim)
            p.rect(x0 + w0, y0, rx + rw - x0 - w0, h0, fill=dim)
            ring = self.anim("ring", 1.0, speed=6)
            pulse = 0.5 + 0.5 * math.sin(time.perf_counter() * 3)
            mark_animating(slow=True)
            p.rect(x0, y0, w0, h0, radius=ctx.px(12), border=alpha(th.accent, 0.6 + 0.4 * pulse), border_w=ctx.px(2))
            e = ctx.px(4) * (1 - ring) + ctx.px(3) * pulse
            p.rect(x0 - e, y0 - e, w0 + 2 * e, h0 + 2 * e, radius=ctx.px(12) + e,
                   border=alpha(th.accent, 0.25 * (1 - ring) + 0.15 * pulse), border_w=ctx.px(1))
        else:
            p.rect(rx, ry, rw, rh, fill=dim)
        x, y, w, h = self.rect
        p.shadow(x, y, w, h, ctx.px(14), (0, 0, 0, 0.55), ctx.px(20), dy=-ctx.px(6))
        p.rect(x, y, w, h, fill=th.surface_2, radius=ctx.px(14), border=th.border_strong, border_w=ctx.px(1))
        _key, title, _text = self.steps[self.i][:3]
        top = y + h - ctx.px(18)
        p.text("%d / %d" % (self.i + 1, len(self.steps)), x + w - ctx.px(14), top, th.fs_xs, th.text_muted, "semibold",
               align="right", valign="center")
        p.text(title, x + ctx.px(14), top, th.fs_md, th.text, "semibold", valign="center", max_w=w - ctx.px(60))
        lh = ctx.px(th.fs_sm * 1.5)
        ly = top - ctx.px(18) - lh / 2
        for line, _i in self._lines:
            p.text(line.rstrip(), x + ctx.px(14), ly, th.fs_sm, th.text_dim, valign="center")
            ly -= lh
        for k in range(len(self.steps)):
            on = k == self.i
            p.rect(x + ctx.px(14) + k * ctx.px(10), y + ctx.px(22), ctx.px(14 if on else 5), ctx.px(5),
                   fill=th.accent if on else th.border_strong, radius=ctx.px(2.5))
        self.row.paint(ctx, p)


# ---------------------------------------------------------------------------
# Notification bell + list
# ---------------------------------------------------------------------------

def _ago(t):
    d = time.time() - t
    if d < 60:
        return "now"
    if d < 3600:
        return "%d min" % (d // 60)
    if d < 86400:
        return "%d h" % (d // 3600)
    return "%d d" % (d // 86400)


class _NotificationList(Widget):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app

    def measure(self, ctx, avail_w):
        n = len(self.app.notifications)
        return avail_w, ctx.px(40) + (ctx.px(52) * min(6, n) if n else ctx.px(70))

    def interactive(self):
        return True

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        x, y, w, h = self.rect
        if ev.y > y + h - ctx.px(34) and ev.x > x + w - ctx.px(80):
            self.app.clear_notifications()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        top = y + h - ctx.px(18)
        p.text("Notifications", x + ctx.px(10), top, th.fs_md, th.text, "semibold", valign="center")
        if self.app.notifications:
            p.text("Clear all", x + w - ctx.px(10), top, th.fs_xs, th.accent, "semibold", align="right", valign="center")
        top -= ctx.px(22)
        if not self.app.notifications:
            p.icon("inbox", x + w / 2 - ctx.px(12), top - ctx.px(34), ctx.px(24), th.text_muted, 1.5)
            p.text("You're all caught up", x + w / 2, top - ctx.px(50), th.fs_sm, th.text_muted, align="center",
                   valign="center")
            return
        icons = {"success": ("success", th.success), "warning": ("warning", th.warning), "danger": ("error", th.danger),
                 "error": ("error", th.danger), "accent": ("sparkles", th.accent)}
        for n in self.app.notifications[:6]:
            ic, c = icons.get(n["kind"], ("info", th.info))
            p.rect(x + ctx.px(4), top - ctx.px(48), w - ctx.px(8), ctx.px(46), fill=alpha(th.surface_3, 0.45),
                   radius=ctx.px(8))
            p.circle(x + ctx.px(22), top - ctx.px(25), ctx.px(11), fill=alpha(c, 0.16))
            p.icon(ic, x + ctx.px(15), top - ctx.px(32), ctx.px(14), c, 1.6)
            p.text(n["title"], x + ctx.px(40), top - ctx.px(17), th.fs_sm, th.text, "semibold", valign="center",
                   max_w=w - ctx.px(90))
            p.text(n["message"], x + ctx.px(40), top - ctx.px(33), th.fs_xs, th.text_muted, valign="center",
                   max_w=w - ctx.px(50))
            p.text(_ago(n["time"]), x + w - ctx.px(12), top - ctx.px(17), th.fs_xs, th.text_muted, align="right",
                   valign="center")
            top -= ctx.px(52)


class NotificationBell(Widget):
    """Bell with an unread count. Click to see the history of toasts (app.notifications)."""

    def __init__(self, **kw):
        kw.setdefault("width", "auto")
        super().__init__(**kw)
        self._open = False

    def interactive(self):
        return True

    def natural_width(self, ctx):
        return ctx.px(32)

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(32)

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        app = ctx.surface.app
        app.unread = 0
        if self._open:
            ctx.surface.close_popover()
            return
        self._open = True

        def closed(*_):
            self._open = False
        ctx.surface.open_popover(Column(_NotificationList(app), padding=4), anchor=self, width=ctx.px(300),
                                 on_close=closed)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        hov = self.anim("hov", 1.0 if (self.hovered or self._open) else 0.0)
        if hov > 0.01:
            p.rect(x, y, w, h, fill=alpha(th.surface_3, hov), radius=ctx.px(9))
        isz = ctx.px(17)
        p.icon("bell", x + w / 2 - isz / 2, y + h / 2 - isz / 2, isz, th.text, 1.6)
        app = self.app
        n = app.unread if app is not None else 0
        if n:
            s = "9+" if n > 9 else str(n)
            bw = max(ctx.px(15), ctx.text_w(s, th.fs_xs - 1, "bold") + ctx.px(8))
            bx, by = x + w - bw + ctx.px(2), y + h - ctx.px(13)
            p.rect(bx, by, bw, ctx.px(15), fill=th.danger, radius=ctx.px(7.5), border=th.bg, border_w=ctx.px(1.5))
            p.text(s, bx + bw / 2, by + ctx.px(7.5), th.fs_xs - 1, (1, 1, 1, 1), "bold", align="center", valign="center")


# ---------------------------------------------------------------------------
# Inline feedback widgets
# ---------------------------------------------------------------------------

class Banner(Widget):
    """Full-width message strip with an optional action and a close button."""

    def __init__(self, text, title=None, kind="accent", action=None, on_action=None, dismissible=True, icon=None,
                 **kw):
        super().__init__(**kw)
        self.text, self.title, self.kind = text, title, kind
        self.action, self.on_action = action, on_action
        self.dismissible = dismissible
        self.icon = icon
        self._hot = None

    def _c(self, th):
        return {"success": th.success, "warning": th.warning, "danger": th.danger, "info": th.info}.get(self.kind,
                                                                                                        th.accent)

    def interactive(self):
        return bool(self.action or self.dismissible)

    def measure(self, ctx, avail_w):
        th = ctx.theme
        w = self.resolve_width(ctx, avail_w)
        aw = ctx.text_w(self.action, th.fs_sm, "semibold") + ctx.px(26) if self.action else 0
        self._lines = wrap_text(self.text, ctx.px(th.fs_sm), w - ctx.px(64) - aw)
        return w, ctx.px(20) + ctx.px(th.fs_sm * 1.45) * len(self._lines) + (ctx.px(17) if self.title else 0)

    def _zone(self, ctx, ev):
        x, y, w, h = self.rect
        if self.dismissible and ev.x > x + w - ctx.px(30):
            return "close"
        if self.action and ev.x > x + w - ctx.px(30) - ctx.text_w(self.action, ctx.theme.fs_sm, "semibold") - ctx.px(26):
            return "action"
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
        return self._zone(ctx, ev) is not None

    def on_click(self, ctx, ev):
        z = self._zone(ctx, ev)
        if z == "close":
            self.visible = False
        elif z == "action":
            call(self.on_action, self)
        self.redraw()

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        c = self._c(th)
        r = ctx.px(th.r_md)
        p.rect(x, y, w, h, fill=alpha(c, 0.16), fill2=alpha(c, 0.07), angle=math.pi / 2, radius=r,
               border=alpha(c, 0.35), border_w=ctx.px(1))
        p.icon(self.icon or {"success": "success", "warning": "warning", "danger": "error", "info": "info"}.get(
            self.kind, "sparkles"), x + ctx.px(12), y + h - ctx.px(12) - ctx.px(16), ctx.px(16), c, 1.6)
        tx = x + ctx.px(38)
        top = y + h - ctx.px(10)
        if self.title:
            p.text(self.title, tx, top - ctx.px(7), th.fs_md, th.text, "semibold", valign="center")
            top -= ctx.px(17)
        lh = ctx.px(th.fs_sm * 1.45)
        for line, _i in self._lines:
            p.text(line.rstrip(), tx, top - lh / 2, th.fs_sm, th.text_dim, valign="center")
            top -= lh
        right = x + w - ctx.px(10)
        if self.dismissible:
            p.icon("x", right - ctx.px(14), y + h / 2 - ctx.px(6), ctx.px(12),
                   th.text if self._hot == "close" else th.text_muted, 1.8)
            right -= ctx.px(26)
        if self.action:
            aw = ctx.text_w(self.action, th.fs_sm, "semibold") + ctx.px(20)
            hot = self._hot == "action"
            p.rect(right - aw, y + h / 2 - ctx.px(13), aw, ctx.px(26), fill=c if hot else alpha(c, 0.2),
                   radius=ctx.px(7))
            p.text(self.action, right - aw / 2, y + h / 2, th.fs_sm, th.accent_text if hot else c, "semibold",
                   align="center", valign="center")


class Skeleton(Widget):
    """Shimmering placeholder while content loads. lines: text lines; avatar / image: extra blocks."""

    def __init__(self, lines=3, avatar=False, image=False, image_height=110, **kw):
        super().__init__(**kw)
        self.lines, self.avatar, self.image, self.image_height = lines, avatar, image, image_height

    def measure(self, ctx, avail_w):
        h = ctx.px(14) * self.lines + ctx.px(8) * (self.lines - 1)
        if self.avatar:
            h = max(h, ctx.px(36))
        if self.image:
            h += ctx.px(self.image_height) + ctx.px(10)
        return self.resolve_width(ctx, avail_w), h

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        mark_animating()
        t = (time.perf_counter() * 0.7) % 1.0
        base = th.surface_3
        hi = lighten(th.surface_3, 0.07)

        def block(bx, by, bw, bh, r):
            p.rect(bx, by, bw, bh, fill=base, radius=r)
            sx = bx - bw * 0.4 + (bw * 1.4) * t
            p.push_clip(bx, by, bw, bh)
            p.rect(sx, by, bw * 0.4, bh, fill=alpha(hi, 0.0), fill2=hi, angle=math.pi / 2, radius=r,
                   flat=alpha(hi, 0.0))
            p.rect(sx + bw * 0.4, by, bw * 0.4, bh, fill=hi, fill2=alpha(hi, 0.0), angle=math.pi / 2, radius=r,
                   flat=alpha(hi, 0.0))
            p.pop_clip()
        top = y + h
        if self.image:
            ih = ctx.px(self.image_height)
            block(x, top - ih, w, ih, ctx.px(th.r_md))
            top -= ih + ctx.px(10)
        lx = x
        if self.avatar:
            block(x, top - ctx.px(36), ctx.px(36), ctx.px(36), ctx.px(18))
            lx += ctx.px(46)
        for i in range(self.lines):
            lw = (x + w - lx) * (0.6 if i == self.lines - 1 and self.lines > 1 else (0.9 if i else 1.0))
            block(lx, top - ctx.px(14), lw, ctx.px(12), ctx.px(6))
            top -= ctx.px(22)


class EmptyState(Widget):
    """Icon, title, text and an optional button for pages with nothing in them yet."""

    def __init__(self, title, text="", icon="inbox", action=None, on_action=None, **kw):
        super().__init__(**kw)
        self.title, self.text, self.icon = title, text, icon
        self.button = Button(action, variant="primary", width="auto", icon="plus",
                             on_click=lambda b: call(on_action, b)) if action else None
        if self.button:
            self.button.parent = self
            self.button.align = "center"

    def children(self):
        return (self.button,) if self.button else ()

    def measure(self, ctx, avail_w):
        th = ctx.theme
        w = self.resolve_width(ctx, avail_w)
        self._lines = wrap_text(self.text, ctx.px(th.fs_sm), w - ctx.px(40)) if self.text else []
        return w, ctx.px(100) + ctx.px(th.fs_sm * 1.5) * len(self._lines) + (ctx.px(44) if self.button else 0)

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        if self.button:
            bw = self.button.natural_width(ctx)
            self.button.arrange(ctx, x + (w - bw) / 2, y + ctx.px(8), bw, ctx.px(32))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        top = y + h - ctx.px(10)
        cx = x + w / 2
        p.circle(cx, top - ctx.px(26), ctx.px(26), fill=th.accent_soft, border=alpha(th.accent, 0.25), border_w=ctx.px(1))
        p.icon(self.icon, cx - ctx.px(12), top - ctx.px(38), ctx.px(24), th.accent, 1.5)
        top -= ctx.px(66)
        p.text(self.title, cx, top, th.fs_lg, th.text, "semibold", align="center", valign="center", max_w=w)
        top -= ctx.px(20)
        lh = ctx.px(th.fs_sm * 1.5)
        for line, _i in self._lines:
            p.text(line.rstrip(), cx, top, th.fs_sm, th.text_muted, align="center", valign="center")
            top -= lh
        if self.button:
            self.button.paint(ctx, p)


class HoldButton(Button):
    """Press and hold to confirm (for destructive actions). on_confirm(button) runs when the bar fills."""

    def __init__(self, text, on_confirm=None, duration=1.0, variant="danger", icon="trash", **kw):
        super().__init__(text, icon=icon, variant=variant, **kw)
        self.on_confirm = on_confirm
        self.duration = duration
        self._held = None
        self._done = False

    def on_press(self, ctx, ev):
        self._held = time.perf_counter()
        self._done = False
        return True

    def on_release(self, ctx, ev, inside):
        self._held = None

    def on_click(self, ctx, ev):
        pass

    def paint(self, ctx, p):
        th = ctx.theme
        Button.paint(self, ctx, p)
        x, y, w, h = self.rect
        if self._held is not None:
            f = min(1.0, (time.perf_counter() - self._held) / self.duration)
            mark_animating()
            r = min(h / 2, ctx.px(9))
            p.push_clip(x, y, w * f, h)
            p.rect(x, y, w, h, fill=alpha(th.danger if self.variant == "danger" else th.accent, 0.35), radius=r)
            p.pop_clip()
            if f >= 1.0 and not self._done:
                self._done = True
                self._held = None
                import bpy
                bpy.app.timers.register(lambda: (call(self.on_confirm, self), None)[1], first_interval=0.0)
        elif self.hovered and not self._done:
            p.text("Hold", x + w - ctx.px(10), y + h / 2, th.fs_xs, th.text_muted, align="right", valign="center")
