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

"""Viewport tools drawn in 3D space: object labels, distance ruler, stats HUD and a floating
toolbar next to the selected object. Add them with app.viewport_tool(ui.ObjectLabels(), True)."""

import math
import time

from .core import Widget, call, mark_animating
from .layout import Column, Row
from .overlays import Overlay, Window
from .theme import alpha, mix
from .widgets import IconButton, KeyValue, Label


def _rv3d(ctx):
    area = ctx.area
    if area is None or area.type != "VIEW_3D":
        return None
    return area.spaces.active.region_3d


def project(ctx, co):
    """3D world point -> region pixel (or None if behind the view)."""
    from bpy_extras import view3d_utils
    rv3d = _rv3d(ctx)
    if rv3d is None or ctx.region is None:
        return None
    return view3d_utils.location_3d_to_region_2d(ctx.region, rv3d, co)


def _top_point(obj):
    from mathutils import Vector
    try:
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        cx = sum(c.x for c in corners) / 8
        cy = sum(c.y for c in corners) / 8
        return Vector((cx, cy, max(c.z for c in corners)))
    except Exception:
        return obj.matrix_world.translation


def scene_stats():
    """{"verts": int, "faces": int, "tris": int, "objects": str} parsed from Blender's statistics."""
    import bpy
    out = {}
    try:
        txt = bpy.context.scene.statistics(bpy.context.view_layer)
    except Exception:
        return out
    for part in txt.split("|"):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


class ObjectLabels(Overlay):
    all_areas = True  # shown in every 3D viewport
    """Name tags pinned above objects. which: "selected", "all" or a function(obj) -> bool.
    text(obj) can add a second line (dimensions, material...). Click a tag to select that object."""

    layer = 0

    def __init__(self, which="selected", text=None, max_labels=40):
        super().__init__()
        self.which = which
        self.text = text
        self.max_labels = max_labels
        self._tags = []
        self._hov = None

    def _objects(self):
        import bpy
        scene = bpy.context.scene
        objs = [o for o in scene.objects if o.visible_get()]
        if self.which == "selected":
            objs = [o for o in objs if o.select_get()]
        elif callable(self.which):
            objs = [o for o in objs if self.which(o)]
        return objs[:self.max_labels]

    def place(self, ctx, rx, ry, rw, rh):
        from .inputs import id_icon
        th = ctx.theme
        self.rect = (rx, ry, rw, rh)
        tags = []
        if _rv3d(ctx) is None:
            self._tags = []
            return
        for o in self._objects():
            pt = project(ctx, _top_point(o))
            if pt is None or not (rx <= pt.x <= rx + rw and ry <= pt.y <= ry + rh):
                continue
            name = o.name
            sub = call(self.text, o) if self.text else None
            w = max(ctx.text_w(name, th.fs_sm, "semibold"), ctx.text_w(sub or "", th.fs_xs)) + ctx.px(36)
            h = ctx.px(36 if sub else 24)
            x = pt.x - w / 2
            y = pt.y + ctx.px(18)
            tags.append((o, x, y, w, h, name, sub, id_icon(o, "objects"), pt))
        self._tags = tags

    def hit(self, x, y):
        for t in self._tags:
            o, tx, ty, tw, th_ = t[:5]
            if tx <= x <= tx + tw and ty <= y <= ty + th_:
                return self
        return None

    def interactive(self):
        return True

    def _at(self, ev):
        for t in self._tags:
            o, tx, ty, tw, th_ = t[:5]
            if tx <= ev.x <= tx + tw and ty <= ev.y <= ty + th_:
                return o
        return None

    def on_hover(self, ctx, ev):
        o = self._at(ev)
        if o != self._hov:
            self._hov = o
            self.redraw()

    def on_leave(self, ctx):
        self._hov = None
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        import bpy
        o = self._at(ev)
        if o is None:
            return
        if not ev.shift:
            for other in bpy.context.view_layer.objects:
                other.select_set(False)
        o.select_set(True)
        bpy.context.view_layer.objects.active = o

    def paint(self, ctx, p):
        import bpy
        th = ctx.theme
        active = bpy.context.view_layer.objects.active
        for o, x, y, w, h, name, sub, icon, pt in self._tags:
            act = o == active
            hov = o == self._hov
            p.line(pt.x, pt.y, pt.x, y, ctx.px(1.2), alpha(th.accent if act else th.text, 0.6))
            p.circle(pt.x, pt.y, ctx.px(2.5), fill=th.accent if act else th.text)
            p.shadow(x, y, w, h, h / 2, (0, 0, 0, 0.45), ctx.px(8), dy=-ctx.px(2))
            p.rect(x, y, w, h, fill=th.surface_2 if not hov else th.surface_3, radius=min(h / 2, ctx.px(10)),
                   border=th.accent if act else th.border_strong, border_w=ctx.px(1.2 if act else 1))
            p.icon(icon, x + ctx.px(9), y + h - ctx.px(12) - ctx.px(6), ctx.px(12), th.accent if act else th.text_dim,
                   1.6)
            p.text(name, x + ctx.px(26), y + h - ctx.px(12), th.fs_sm, th.text, "semibold", valign="center",
                   max_w=w - ctx.px(32))
            if sub:
                p.text(sub, x + ctx.px(26), y + ctx.px(10), th.fs_xs, th.text_muted, valign="center",
                       max_w=w - ctx.px(32))


class Ruler(Overlay):
    all_areas = True  # shown in every 3D viewport
    """Live distance between the active object and the other selected object
    (or the 3D cursor when only one object is selected), in the scene's units."""

    layer = 0

    def __init__(self):
        super().__init__()
        self._seg = None

    def hit(self, x, y):
        return None

    def place(self, ctx, rx, ry, rw, rh):
        import bpy
        self.rect = (rx, ry, rw, rh)
        self._seg = None
        if _rv3d(ctx) is None:
            return
        vl = bpy.context.view_layer
        a = vl.objects.active
        if a is None or not a.select_get():
            return
        others = [o for o in bpy.context.selected_objects if o != a]
        pa = a.matrix_world.translation.copy()
        pb = others[0].matrix_world.translation.copy() if others else bpy.context.scene.cursor.location.copy()
        dist = (pb - pa).length
        sa, sb = project(ctx, pa), project(ctx, pb)
        if sa is None or sb is None:
            return
        us = bpy.context.scene.unit_settings
        try:
            txt = bpy.utils.units.to_string(us.system if us.system != "NONE" else "METRIC", "LENGTH",
                                            dist * us.scale_length, precision=3)
        except Exception:
            txt = "%.3f m" % dist
        self._seg = (sa, sb, txt, "cursor" if not others else others[0].name)

    def paint(self, ctx, p):
        if self._seg is None:
            return
        th = ctx.theme
        sa, sb, txt, other = self._seg
        length = math.hypot(sb.x - sa.x, sb.y - sa.y)
        dash, gap = ctx.px(8), ctx.px(5)
        n = int(length // (dash + gap)) + 1
        for i in range(n):
            t0 = i * (dash + gap) / max(1.0, length)
            t1 = min(1.0, t0 + dash / max(1.0, length))
            p.line(sa.x + (sb.x - sa.x) * t0, sa.y + (sb.y - sa.y) * t0, sa.x + (sb.x - sa.x) * t1,
                   sa.y + (sb.y - sa.y) * t1, ctx.px(2), th.accent)
        for pt in (sa, sb):
            p.circle(pt.x, pt.y, ctx.px(5), fill=th.surface_1, border=th.accent, border_w=ctx.px(2))
        mx, my = (sa.x + sb.x) / 2, (sa.y + sb.y) / 2
        w = ctx.text_w(txt, th.fs_md, "semibold") + ctx.px(36)
        h = ctx.px(26)
        p.shadow(mx - w / 2, my - h / 2, w, h, h / 2, (0, 0, 0, 0.45), ctx.px(8))
        p.rect(mx - w / 2, my - h / 2, w, h, fill=th.accent, radius=h / 2)
        p.icon("ruler", mx - w / 2 + ctx.px(9), my - ctx.px(6.5), ctx.px(13), th.accent_text, 1.6)
        p.text(txt, mx - w / 2 + ctx.px(27), my, th.fs_md, th.accent_text, "semibold", valign="center")


class HUD(Window):
    """Small draggable stats panel: viewport FPS (with a sparkline), objects, vertices, triangles."""

    def __init__(self, anchor="top_left", **kw):
        from .data import Sparkline
        self._fps_hist = [0.0] * 40
        self._last = 0.0
        body = Column(
            Row(Label("Viewport", weight="semibold", size=11.5),
                Label(lambda: "%d fps" % round(self._app.viewport_fps()) if self._app else "", size=11.5,
                      color="accent", weight="semibold", align="right"), gap=6),
            Sparkline(lambda: self._fps_hist, height=24),
            KeyValue("Objects", lambda: scene_stats().get("objects", "-"), icon="cube"),
            KeyValue("Vertices", lambda: scene_stats().get("verts", scene_stats().get("vertices", "-")), icon="mesh"),
            KeyValue("Triangles", lambda: scene_stats().get("tris", scene_stats().get("triangles", "-")), icon="layers"),
            gap=4,
        )
        super().__init__(body, chrome=False, width=200, anchor=anchor, scroll=False, padding=10, **kw)
        self._app = None

    def paint(self, ctx, p):
        self._app = ctx.surface.app
        now = time.perf_counter()
        if now - self._last > 0.25:
            self._fps_hist = self._fps_hist[1:] + [self._app.viewport_fps()]
            self._last = now
        mark_animating(slow=True)
        Window.paint(self, ctx, p)


class SelectionToolbar(Overlay):
    all_areas = True  # shown in every 3D viewport
    """Quick actions floating above the active object (object mode).
    items: [(icon, tooltip, operator, props)] — defaults: duplicate, shade smooth, hide, frame, delete."""

    layer = 1

    DEFAULT = [
        ("copy", "Duplicate", "object.duplicate", {}),
        ("sphere", "Shade smooth", "object.shade_smooth", {}),
        ("eye", "Hide", "object.hide_view_set", {}),
        ("target", "Frame selected", "view3d.view_selected", {}),
        ("trash", "Delete", "object.delete", {"confirm": False}),
    ]

    def __init__(self, items=None):
        super().__init__()
        btns = []
        for icon, tip, op, props in (items or self.DEFAULT):
            btns.append(IconButton(icon, variant="danger" if icon == "trash" else "ghost", size="sm",
                                   tooltip=tip, operator=op, props=props))
        self.row = Row(*btns, gap=2)
        self.row.parent = self
        self._shown = False

    def children(self):
        return (self.row,) if self._shown else ()

    def interactive(self):
        return True

    def place(self, ctx, rx, ry, rw, rh):
        import bpy
        self._shown = False
        self.rect = (0, 0, 0, 0)
        if _rv3d(ctx) is None or bpy.context.mode != "OBJECT":
            return
        a = bpy.context.view_layer.objects.active
        if a is None or not a.select_get() or not a.visible_get():
            return
        pt = project(ctx, _top_point(a))
        if pt is None:
            return
        w = self.row.natural_width(ctx) + ctx.px(10)
        h = ctx.px(36)
        x = min(max(rx + ctx.px(6), pt.x - w / 2), rx + rw - w - ctx.px(6))
        y = min(pt.y + ctx.px(56), ry + rh - h - ctx.px(6))
        self.rect = (x, y, w, h)
        self.row.measure(ctx, w - ctx.px(10))
        self.row.arrange(ctx, x + ctx.px(5), y + ctx.px(5), w - ctx.px(10), h - ctx.px(10))
        self._shown = True

    def hit(self, x, y):
        if not self._shown or not self.contains(x, y):
            return None
        return self.row.hit(x, y) or self

    def paint(self, ctx, p):
        if not self._shown:
            return
        th = ctx.theme
        x, y, w, h = self.rect
        p.shadow(x, y, w, h, ctx.px(12), (0, 0, 0, 0.5), ctx.px(14), dy=-ctx.px(4))
        p.rect(x, y, w, h, fill=th.surface_2, radius=ctx.px(12), border=th.border_strong, border_w=ctx.px(1))
        self.row.paint(ctx, p)
