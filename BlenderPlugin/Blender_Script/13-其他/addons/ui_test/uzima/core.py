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

"""Widget base class, events, animation and Blender property binding."""

import math
import time

from .theme import DEFAULT


# ---------------------------------------------------------------------------
# Context passed to measure / arrange / paint
# ---------------------------------------------------------------------------

class Ctx:
    def __init__(self, surface, scale, theme, region_w, region_h):
        self.surface = surface
        self.scale = scale
        self.theme = theme
        self.region_w = region_w
        self.region_h = region_h
        self.area = None     # bpy area / region being drawn or handled (when known)
        self.region = None

    def px(self, v):
        return v * self.scale

    def text_w(self, text, size, weight="regular"):
        from .draw import text_size
        return text_size(text, size * self.scale, weight)[0]


class Event:
    """Mouse / keyboard event in region-local pixels."""
    __slots__ = ("type", "value", "x", "y", "shift", "ctrl", "alt", "oskey", "unicode",
                 "dx", "dy", "wheel", "region", "area", "window", "is_repeat")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def mod(self):
        return self.ctrl or self.oskey


# ---------------------------------------------------------------------------
# Animation helpers
# ---------------------------------------------------------------------------

_anim_state = {"active": False, "slow": False}


def mark_animating(slow=False):
    """Ask for another frame soon. slow=True: ~10 fps (live previews, clocks)."""
    if slow:
        _anim_state["slow"] = True
    else:
        _anim_state["active"] = True


def consume_animating():
    a = _anim_state["active"]
    _anim_state["active"] = False
    return a


def consume_slow():
    a = _anim_state["slow"]
    _anim_state["slow"] = False
    return a


def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_out_back(t, s=1.4):
    t = max(0.0, min(1.0, t)) - 1
    return 1 + t * t * ((s + 1) * t + s)


# ---------------------------------------------------------------------------
# Blender property binding
# ---------------------------------------------------------------------------

class Bind:
    """Connect a widget to a Blender property.

        Bind("scene.my_settings.strength")         # path from bpy.context
        Bind(lambda: bpy.context.object, "location", index=2)
        Bind(obj, "name")

    Widgets read the value every redraw, so changes made anywhere in Blender
    show up immediately, and edits from the UI are written back with undo.
    """

    def __init__(self, target, attr=None, index=None, undo=True):
        self.target = target
        self.attr = attr
        self.index = index
        self.undo = undo
        if isinstance(target, str) and attr is None:
            path, _, a = target.rpartition(".")
            self.target = path
            self.attr = a

    def owner(self):
        import bpy
        t = self.target
        try:
            if isinstance(t, str):
                obj = bpy.context
                for part in t.split("."):
                    if part:
                        obj = getattr(obj, part)
                return obj
            if callable(t):
                return t()
            return t
        except Exception:
            return None

    def get(self, default=None):
        o = self.owner()
        if o is None:
            return default
        try:
            v = getattr(o, self.attr)
            if self.index is not None:
                v = v[self.index]
            return v
        except Exception:
            return default

    def set(self, value):
        o = self.owner()
        if o is None:
            return
        try:
            if self.index is not None:
                arr = getattr(o, self.attr)
                arr[self.index] = value
            else:
                setattr(o, self.attr, value)
        except Exception as e:
            print("Uzima UI: could not set", self.attr, e)

    def rna(self):
        o = self.owner()
        try:
            return o.bl_rna.properties[self.attr]
        except Exception:
            return None

    def label(self):
        p = self.rna()
        return p.name if p else (self.attr or "").replace("_", " ").capitalize()

    def description(self):
        p = self.rna()
        return p.description if p else ""

    def enum_items(self):
        p = self.rna()
        out = []
        if p is not None and p.type == "ENUM":
            for it in p.enum_items:
                out.append((it.identifier, it.name, it.description))
        return out

    def range(self):
        p = self.rna()
        if p is None or p.type not in ("INT", "FLOAT"):
            return None
        return (p.soft_min, p.soft_max, getattr(p, "step", 1), getattr(p, "precision", 2), p.subtype)

    def push_undo(self, message="Uzima UI edit"):
        if not self.undo:
            return
        form = getattr(self, "_in_form", None)
        if form is not None and form.buffered:
            return  # the Form pushes one undo step when it applies
        try:
            import bpy
            bpy.ops.ed.undo_push(message=message)
        except Exception:
            pass


class FuncBind(Bind):
    """Bind to anything through two functions: Bind.fn(getter, setter, label="Size")."""

    def __init__(self, getter, setter=None, label="", undo=False):
        super().__init__(None, "value", undo=undo)
        self.getter = getter
        self.setter = setter
        self._label = label

    def owner(self):
        return self

    def get(self, default=None):
        try:
            v = self.getter()
            return default if v is None else v
        except Exception:
            return default

    def set(self, value):
        if self.setter is not None:
            try:
                self.setter(value)
            except Exception as e:
                print("Uzima UI: setter failed", e)

    def rna(self):
        return None

    def label(self):
        return self._label

    def enum_items(self):
        return []

    def range(self):
        return None


Bind.fn = staticmethod(lambda getter, setter=None, label="", undo=False: FuncBind(getter, setter, label, undo))


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class Widget:
    """Base class. Subclasses override measure / arrange / paint and the on_* events.

    Sizing:
      width=None   fill the available width (or share space in a Row)
      width="auto" use the widget's natural width
      width=120    fixed width in dp (scaled by the UI scale)
      flex=2       share weight inside a Row
    """

    focusable = False
    cursor = None  # e.g. "HAND", "TEXT"
    keyboard_nav = True  # reachable with Tab when interactive

    def __init_subclass__(cls, **kw):
        # Per-widget gradient / shadow overrides: wrap paint so the painter flags are
        # switched only while this widget (and its children) paint.
        super().__init_subclass__(**kw)
        fn = cls.__dict__.get("paint")
        if fn is None or getattr(fn, "_uz_wrapped", False):
            return

        def paint(self, ctx, p, _fn=fn):
            g = self.gradient
            sh = self.shadows
            if g is None and sh is None:
                return _fn(self, ctx, p)
            og, osh = p.gradients, p.shadows
            if g is not None:
                p.gradients = g
            if sh is not None:
                p.shadows = sh
            try:
                return _fn(self, ctx, p)
            finally:
                p.gradients, p.shadows = og, osh

        paint._uz_wrapped = True
        paint.__doc__ = fn.__doc__
        cls.paint = paint

    def __init__(self, width=None, height=None, flex=1.0, tooltip=None, visible=True,
                 enabled=True, align="stretch", key=None, margin=0, gradient=None, shadows=None,
                 context_menu=None):
        """visible / enabled can be callables, e.g. visible=lambda: bpy.context.object is not None
        gradient / shadows: None follows the theme, True / False forces it for this widget.
        context_menu: list of MenuItems (or a function returning one) shown on right-click."""
        self.gradient = gradient
        self.shadows = shadows
        self.context_menu = context_menu
        self.width = width
        self.height = height
        self.flex = flex
        self.tooltip = tooltip
        self.visible = visible
        self.enabled = enabled
        self.align = align
        self.key = key
        self.margin = margin
        self.parent = None
        self.rect = (0.0, 0.0, 0.0, 0.0)
        self.hovered = False
        self.pressed = False
        self.focused = False
        self._anims = {}

    # ---- tree ----------------------------------------------------------
    def children(self):
        return ()

    def walk(self):
        yield self
        for c in self.children():
            if c is not None:
                yield from c.walk()

    def find(self, key):
        for w in self.walk():
            if w.key == key:
                return w
        return None

    def _adopt(self, items):
        out = []
        for c in items:
            if c is None:
                continue
            c.parent = self
            out.append(c)
        return out

    @property
    def visible(self):
        v = self._uz_vis
        if callable(v):
            try:
                return bool(v())
            except Exception:
                return False
        return v

    @visible.setter
    def visible(self, v):
        self._uz_vis = v

    @property
    def enabled(self):
        v = self._uz_en
        if callable(v):
            try:
                return bool(v())
            except Exception:
                return False
        return v

    @enabled.setter
    def enabled(self, v):
        self._uz_en = v

    @property
    def is_enabled(self):
        w = self
        while w is not None:
            if not w.enabled:
                return False
            w = w.parent
        return True

    def get_surface(self):
        """The Surface this widget lives in (sidebar, viewport...), or None before first draw."""
        w = self
        while w is not None:
            s = getattr(w, "_uz_surface", None) or getattr(w, "surface", None)
            if s is not None and hasattr(s, "app"):
                return s
            w = w.parent
        return None

    @property
    def app(self):
        a = self.__dict__.get("_app_override")
        if a is not None:
            return a
        s = self.get_surface()
        return s.app if s is not None else None

    @app.setter
    def app(self, value):
        self.__dict__["_app_override"] = value

    # ---- persisted state (widgets with a key) ---------------------------
    def get_state(self):
        """Return JSON-able UI state to save in the .blend (tabs, open cards...)."""
        return None

    def set_state(self, state):
        pass

    # ---- layout --------------------------------------------------------
    def natural_width(self, ctx):
        """Width the widget would like when not stretched (px)."""
        return ctx.px(60)

    def measure(self, ctx, avail_w):
        """Return (w, h) in px for the available width."""
        w = self.resolve_width(ctx, avail_w)
        h = ctx.px(self.height) if self.height is not None else ctx.px(ctx.theme.control_h)
        return w, h

    def resolve_width(self, ctx, avail_w):
        if self.width is None:
            return avail_w
        if self.width == "auto":
            return min(avail_w, self.natural_width(ctx))
        return min(avail_w, ctx.px(self.width))

    def arrange(self, ctx, x, y, w, h):
        """Place the widget; (x, y) is the bottom-left corner in region px."""
        self.rect = (x, y, w, h)

    # ---- painting ------------------------------------------------------
    def paint(self, ctx, p):
        pass

    # ---- hit testing ---------------------------------------------------
    def contains(self, x, y):
        rx, ry, rw, rh = self.rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def hit(self, x, y):
        if not self.visible or not self.contains(x, y):
            return None
        for c in reversed(list(self.children())):
            if c is None or not c.visible:
                continue
            r = c.hit(x, y)
            if r is not None:
                return r
        return self if (self.interactive() or self.context_menu or self.tooltip) else None

    def interactive(self):
        return False

    # ---- events (return True when handled) --------------------------------
    def on_enter(self, ctx): pass
    def on_leave(self, ctx): pass
    def on_hover(self, ctx, ev): pass
    def on_press(self, ctx, ev): return False
    def on_drag(self, ctx, ev): pass
    def on_release(self, ctx, ev, inside): pass
    def on_click(self, ctx, ev): pass
    def on_double_click(self, ctx, ev): return False
    def on_wheel(self, ctx, ev): return False
    def on_key(self, ctx, ev): return False
    def on_focus(self, ctx): pass
    def on_blur(self, ctx): pass

    # ---- animation -----------------------------------------------------
    def anim(self, name, target, speed=None, snap=0.002):
        """Smoothly move a value toward `target`. Call from paint()."""
        now = time.perf_counter()
        st = self._anims.get(name)
        if st is None:
            self._anims[name] = [target, now]
            return target
        cur, last = st
        dt = min(now - last, 0.1)
        k = 1.0 - math.exp(-dt * (speed or DEFAULT.speed))
        cur = cur + (target - cur) * k
        if abs(target - cur) < snap * max(1.0, abs(target)):
            cur = target
        else:
            mark_animating()
        st[0] = cur
        st[1] = now
        return cur

    def set_anim(self, name, value):
        self._anims[name] = [value, time.perf_counter()]

    def redraw(self):
        from .host import request_redraw
        request_redraw()


_arity = {}


def call(fn, *args):
    """Call a user callback with as many of `args` as it accepts."""
    if fn is None:
        return None
    n = _arity.get(fn)
    if n is None:
        import inspect
        try:
            params = inspect.signature(fn).parameters.values()
            if any(p.kind == p.VAR_POSITIONAL for p in params):
                n = len(args)
            else:
                n = sum(1 for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                        and p.default is p.empty)
                n = max(n, sum(1 for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)))
        except (TypeError, ValueError):
            n = len(args)
        try:
            _arity[fn] = n
        except TypeError:
            pass
    try:
        return fn(*args[:n])
    except Exception:
        import traceback
        traceback.print_exc()
        return None
