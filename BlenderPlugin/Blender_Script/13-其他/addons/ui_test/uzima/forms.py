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

"""Blender-aware building blocks: automatic property widgets, transactional forms and code blocks.

    ui.Prop("object.location")                 # picks the right widget from the property type
    ui.Props("scene.render", ["engine", "resolution_x", "resolution_y", "film_transparent"])
    ui.Props("object", exclude=["name"])       # every property of a PropertyGroup / data-block
    ui.Form(ui.Prop(...), ui.Prop(...), title="Render settings")   # edits apply together, one undo step
"""

import re

from .core import Bind, Widget, call
from .layout import Card, Column, Row
from .theme import alpha, mix
from .widgets import (Button, Checkbox, Dropdown, IconButton, Label, NumberField, RadioGroup, Segmented, Slider,
                      Switch, TextInput)


def resolve(target):
    """'object.data' -> bpy.context.object.data ; callables are called ; objects returned as is."""
    import bpy
    if isinstance(target, str):
        obj = bpy.context
        for part in target.split("."):
            if not part:
                continue
            obj = getattr(obj, part, None)
            if obj is None:
                return None
        return obj
    if callable(target):
        try:
            return target()
        except Exception:
            return None
    return target


def _owner_fn(target):
    return lambda: resolve(target)


def make_prop_widget(bind, label=None, style=None, **kw):
    """Build a widget for a resolved property. Returns None if the property can't be found."""
    from .inputs import (ColorField, DataPicker, FilePathField, Knob, ToggleGroup, VectorField, POINTER_COLLECTIONS)
    rna = bind.rna()
    if rna is None:
        return None
    name = label if label is not None else rna.name
    t = rna.type
    sub = rna.subtype
    n = getattr(rna, "array_length", 0)
    if t == "BOOLEAN":
        if n:
            names = "XYZW" if n <= 4 else [str(i) for i in range(n)]
            return ToggleGroup([(str(i), names[i]) for i in range(n)], label=name,
                               binds=[Bind(bind.target, bind.attr, index=i) for i in range(n)], **kw)
        if style == "checkbox":
            return Checkbox(name, bind=bind, **kw)
        return Switch(name, bind=bind, **kw)
    if t == "ENUM":
        if rna.is_enum_flag:
            return ToggleGroup(bind=bind, label=name, **kw)
        if style == "radio":
            return Column(Label(name, muted=True, size=11.5, weight="medium"), RadioGroup(bind=bind), gap=4, **kw)
        if style == "segmented":
            return Column(Label(name, muted=True, size=11.5, weight="medium"), Segmented(bind=bind), gap=4, **kw)
        return Dropdown(bind=bind, label=name, **kw)
    if t in ("INT", "FLOAT"):
        if n:
            if sub in ("COLOR", "COLOR_GAMMA"):
                return ColorField(name, bind=bind, **kw)
            return VectorField(name, bind=bind, **kw)
        if style == "knob":
            return Knob(name, bind=bind, **kw)
        lo, hi = rna.soft_min, rna.soft_max
        finite = abs(hi - lo) <= 100000
        if style == "field" or not finite or sub in ("DISTANCE", "TIME", "ANGLE") and style != "slider":
            return NumberField(name, bind=bind, **kw)
        if sub in ("FACTOR", "PERCENTAGE") or style == "slider" or (finite and hi - lo <= 1000):
            return Slider(name, bind=bind, **kw)
        return NumberField(name, bind=bind, **kw)
    if t == "STRING":
        if sub in ("FILE_PATH", "DIR_PATH", "FILE_NAME"):
            return FilePathField(name, bind=bind, mode="DIR" if sub == "DIR_PATH" else "FILE", **kw)
        return TextInput(rna.description or name, label=name, bind=bind, password=sub == "PASSWORD", **kw)
    if t == "POINTER":
        ft = rna.fixed_type.identifier
        if ft in POINTER_COLLECTIONS:
            return DataPicker(name, bind=bind, **kw)
        try:
            import bpy
            if issubclass(type(bind.get()), bpy.types.PropertyGroup):
                return Props(lambda b=bind: b.get(), title=name, card=True)
        except Exception:
            pass
        return Label(name, muted=True)
    if t == "COLLECTION":
        return Label(lambda: "%s: %d items" % (name, len(bind.get() or [])), muted=True)
    return Label(name, muted=True)


class Prop(Widget):
    """The right widget for any Blender property, chosen from its type (like layout.prop).

        ui.Prop("object.location")                     # vector field
        ui.Prop("scene.render.engine")                 # dropdown
        ui.Prop("object.color")                        # color picker
        ui.Prop("scene.camera")                        # object picker with eyedropper
        ui.Prop("scene.render.filepath")               # path + file browser
        ui.Prop(ui.Bind(lambda: mat, "roughness"), style="knob")

    style: "slider", "field", "knob", "checkbox", "radio", "segmented" to override the choice.
    The widget follows the owner: if the active object changes, it rebinds automatically and
    shows `empty` when there is nothing to edit."""

    def __init__(self, target, attr=None, index=None, label=None, style=None, empty="Nothing to edit", **kw):
        own = {k: kw.pop(k) for k in ("width", "height", "flex", "tooltip", "visible", "enabled", "key",
                                      "gradient", "shadows", "context_menu") if k in kw}
        super().__init__(**own)
        if isinstance(target, Bind):
            self.bind = target
        else:
            if attr is None and isinstance(target, str):
                path, _, attr = target.rpartition(".")
                target = path
            self.bind = Bind(_owner_fn(target), attr, index=index)
        self.label = label
        self.style = style
        self.empty = empty
        self.kw = kw
        self.child = None
        self._sig = None

    def _signature(self):
        o = self.bind.owner()
        if o is None:
            return None
        rna = self.bind.rna()
        return (type(o).__name__, rna.identifier if rna else None)

    def children(self):
        return (self.child,) if self.child is not None else ()

    def _sync(self):
        sig = self._signature()
        if sig != self._sig:
            self._sig = sig
            w = make_prop_widget(self.bind, self.label, self.style, **self.kw) if sig and sig[1] else None
            if w is None:
                w = Label(self.empty, muted=True, size=11.5)
            w.parent = self
            self.child = w

    def interactive(self):
        return False

    def natural_width(self, ctx):
        self._sync()
        return self.child.natural_width(ctx)

    def measure(self, ctx, avail_w):
        self._sync()
        w = self.resolve_width(ctx, avail_w)
        _cw, h = self.child.measure(ctx, w)
        return w, h

    def arrange(self, ctx, x, y, w, h):
        self.rect = (x, y, w, h)
        self.child.arrange(ctx, x, y, w, h)

    def paint(self, ctx, p):
        if self.child is not None:
            self.child.paint(ctx, p)


_SKIP = {"rna_type", "name_full", "original", "users", "session_uid", "is_evaluated", "is_embedded_data",
         "is_library_indirect", "library", "library_weak_reference", "asset_data", "override_library",
         "preview", "is_missing", "is_runtime_data", "use_fake_user", "use_extra_user", "tag", "is_editmode",
         "id_type", "is_linked_packed"}


class Props(Column):
    """A column of Prop widgets for several properties of one owner.

        ui.Props("scene.render", ["engine", "resolution_x", "resolution_y"])
        ui.Props("scene.my_settings")                     # all properties of a PropertyGroup
        ui.Props("object", ["location", "rotation_euler", "scale"], title="Transform", icon="target")
    styles={"roughness": "knob"} and labels={"resolution_x": "Width"} customize single properties."""

    def __init__(self, target, props=None, exclude=(), title=None, subtitle=None, icon=None, card=False,
                 styles=None, labels=None, empty="Nothing to edit", gap=10, **kw):
        self.target = target
        self.prop_names = props
        self.exclude = set(exclude)
        self.styles = styles or {}
        self.labels = labels or {}
        self.empty = empty
        self._sig = None
        self.card = None
        super().__init__(gap=gap, **kw)
        if card or title:
            self.card = Card(title=title, subtitle=subtitle, icon=icon, collapsible=bool(title))
            self.card._prop_body = True

    def _names(self, owner):
        if self.prop_names is not None:
            return list(self.prop_names)
        out = []
        for p in owner.bl_rna.properties:
            if p.identifier in _SKIP or p.identifier in self.exclude or p.is_hidden or p.type == "COLLECTION":
                continue
            if p.type == "POINTER" and p.identifier in ("id_data", "bl_rna"):
                continue
            out.append(p.identifier)
        return out

    def _sync(self):
        owner = resolve(self.target)
        sig = (type(owner).__name__, tuple(self._names(owner))) if owner is not None else None
        if sig == self._sig:
            return
        self._sig = sig
        if owner is None:
            kids = [Label(self.empty, muted=True, size=11.5)]
        else:
            kids = [Prop(Bind(_owner_fn(self.target), n), label=self.labels.get(n), style=self.styles.get(n))
                    for n in sig[1]]
        if self.card is not None:
            self.card.set_children(kids)
            self.set_children([self.card])
        else:
            self.set_children(kids)

    def measure(self, ctx, avail_w):
        self._sync()
        return Column.measure(self, ctx, avail_w)


class Form(Column):
    """Edits made by bound widgets inside a Form are staged, not written to Blender, until Apply.
    Apply writes them all and makes one undo step; Revert throws them away.

        ui.Form(ui.Prop("scene.render.resolution_x"), ui.Prop("scene.render.resolution_y"),
                title="Output", on_apply=lambda form: app.toast("Saved"))

    form.dirty, form.apply(), form.reset(). actions=False hides the built-in Revert / Apply row."""

    _uz_form = True

    def __init__(self, *children, title=None, on_apply=None, on_reset=None, buffered=True, actions=True,
                 apply_label="Apply", gap=10, **kw):
        self._staged = {}
        self.buffered = buffered
        self.title = title
        self.on_apply = on_apply
        self.on_reset = on_reset
        if len(children) == 1 and isinstance(children[0], (list, tuple)):
            children = children[0]
        kids = list(children)
        if actions:
            self.status = Label(lambda: ("%d unsaved change%s" % (len(self._staged), "" if len(self._staged) == 1
                                                                  else "s")) if self._staged else "No changes",
                                muted=True, size=11)
            self.actions_row = Row(self.status,
                                   Button("Revert", variant="ghost", width="auto", icon="refresh",
                                          enabled=lambda: self.dirty, on_click=lambda b: self.reset()),
                                   Button(apply_label, variant="primary", width="auto", icon="check",
                                          enabled=lambda: self.dirty, on_click=lambda b: self.apply()),
                                   gap=6)
            kids.append(self.actions_row)
        super().__init__(*kids, gap=gap, **kw)

    @property
    def dirty(self):
        return bool(self._staged)

    def _stage(self, bind, value):
        self._staged[id(bind)] = (bind, value)

    def apply(self):
        staged = list(self._staged.values())
        self._staged.clear()
        for bind, value in staged:
            bind.set(value)
        if staged:
            try:
                import bpy
                bpy.ops.ed.undo_push(message="Apply " + (self.title or "changes"))
            except Exception:
                pass
        call(self.on_apply, self)
        self.redraw()

    def reset(self):
        self._staged.clear()
        for w in self.walk():
            if hasattr(w, "text") and hasattr(w, "_te_init") and not w.focused and hasattr(w, "bind") and w.bind:
                v = w.bind.get("")
                w.text = str(v)
        call(self.on_reset, self)
        self.redraw()


_PY_KEYWORDS = set("""False None True and as assert async await break class continue def del elif else except
finally for from global if import in is lambda nonlocal not or pass raise return try while with yield""".split())
_TOKEN = re.compile(r"(#.*$)|(\"[^\"]*\"|'[^']*')|(\b\d+(?:\.\d+)?\b)|(\b[A-Za-z_][A-Za-z0-9_]*\b)|(\s+)|(.)")


class Code(Widget):
    """A code block with simple Python highlighting and a copy button (copies to the clipboard)."""

    cursor = "HAND"

    def __init__(self, text, language="python", title=None, copy=True, size=11, **kw):
        super().__init__(**kw)
        self.text = text.strip("\n")
        self.language = language
        self.title = title
        self.copy = copy
        self.size = size
        self._copied = 0.0

    def interactive(self):
        return self.copy

    def _lines(self):
        return self.text.split("\n")

    def measure(self, ctx, avail_w):
        lh = ctx.px(self.size * 1.55)
        head = ctx.px(28) if (self.title or self.copy) else ctx.px(6)
        return self.resolve_width(ctx, avail_w), head + lh * len(self._lines()) + ctx.px(10)

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        import bpy, time
        try:
            bpy.context.window_manager.clipboard = self.text
        except Exception:
            pass
        self._copied = time.perf_counter()
        ctx.surface.toast("Copied", "Code copied to the clipboard.", "success", duration=1.6)

    def paint(self, ctx, p):
        import time
        th = ctx.theme
        x, y, w, h = self.rect
        r = ctx.px(th.r_md)
        p.rect(x, y, w, h, fill=mix(th.surface_0, (0, 0, 0, 1), 0.25), radius=r, border=th.border, border_w=ctx.px(1))
        top = y + h
        if self.title or self.copy:
            hh = ctx.px(28)
            p.rect(x, top - hh, w, ctx.px(1), fill=th.border)
            if self.title:
                p.text(self.title, x + ctx.px(10), top - hh / 2, th.fs_xs, th.text_muted, "semibold",
                       valign="center")
            if self.copy:
                done = time.perf_counter() - self._copied < 1.5
                lab = "Copied" if done else "Copy"
                hov = self.hovered
                col = th.success if done else (th.text if hov else th.text_dim)
                tw = ctx.text_w(lab, th.fs_xs, "medium")
                p.text(lab, x + w - ctx.px(10), top - hh / 2, th.fs_xs, col, "medium", align="right", valign="center")
                p.icon("check" if done else "copy", x + w - ctx.px(14) - tw - ctx.px(12), top - hh / 2 - ctx.px(6),
                       ctx.px(12), col, 1.6)
            top -= hh
        top -= ctx.px(5)
        lh = ctx.px(self.size * 1.55)
        kw_c, str_c, num_c, com_c, txt_c = th.accent, (0.85, 0.72, 0.52, 1), (0.62, 0.78, 0.95, 1), th.text_muted, th.text
        p.push_clip(x, y, w, h)
        for line in self._lines():
            cx = x + ctx.px(12)
            cy = top - lh / 2
            if self.language == "python":
                for m in _TOKEN.finditer(line):
                    tok = m.group(0)
                    if m.group(1):
                        col = com_c
                    elif m.group(2):
                        col = str_c
                    elif m.group(3):
                        col = num_c
                    elif m.group(4):
                        col = kw_c if tok in _PY_KEYWORDS else (
                            (0.83, 0.70, 0.95, 1) if tok in ("ui", "bpy", "app") else txt_c)
                    else:
                        col = txt_c
                    cx += p.text(tok, cx, cy, self.size, col, "mono", valign="center")
            else:
                p.text(line, cx, cy, self.size, txt_c, "mono", valign="center")
            top -= lh
        p.pop_clip()
