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

"""Media elements: live viewport preview, before/after slider, carousel, frame scrubber, drop zone."""

import math
import time

from .core import Widget, call, mark_animating
from .theme import alpha, mix


def _val(v):
    return v() if callable(v) else v


class ViewportPreview(Widget):
    """A live picture of the scene inside the panel, rendered with Blender's viewport engine.

        ui.ViewportPreview()                       # through the scene camera
        ui.ViewportPreview(source="view")          # what the 3D viewport currently shows
        ui.ViewportPreview(camera=lambda: bpy.data.objects["Cam_Close"])

    Must live in a surface of a 3D view (sidebar or viewport). fps limits how often it re-renders."""

    def __init__(self, source="camera", camera=None, height=None, aspect=None, fps=6, radius=None, label=True,
                 **kw):
        super().__init__(**kw)
        self.source = source
        self.camera = camera
        self.height_dp = height
        self.aspect = aspect
        self.fps = fps
        self.radius = radius
        self.label = label
        self._off = None
        self._last = 0.0
        self._error = None

    def _aspect(self):
        if self.aspect:
            return self.aspect
        try:
            import bpy
            r = bpy.context.scene.render
            return (r.resolution_x * r.pixel_aspect_x) / max(1, r.resolution_y * r.pixel_aspect_y)
        except Exception:
            return 16 / 9

    def measure(self, ctx, avail_w):
        w = self.resolve_width(ctx, avail_w)
        if self.height_dp:
            return w, ctx.px(self.height_dp)
        return w, w / max(0.2, self._aspect())

    def _render(self, ctx, W, H):
        import bpy
        import gpu
        area = ctx.area
        if area is None or area.type != "VIEW_3D":
            self._error = "Open in a 3D view"
            return None
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        space = area.spaces.active
        scene = bpy.context.scene
        cam = _val(self.camera) if self.camera is not None else scene.camera
        if self.source == "camera" and cam is None:
            self._error = "The scene has no camera"
            return None
        if self._off is None or self._off.width != W or self._off.height != H:
            if self._off is not None:
                self._off.free()
            self._off = gpu.types.GPUOffScreen(W, H)
        if self.source == "camera":
            depsgraph = bpy.context.evaluated_depsgraph_get()
            view = cam.matrix_world.inverted()
            proj = cam.calc_matrix_camera(depsgraph, x=W, y=H)
        else:
            rv3d = space.region_3d
            view, proj = rv3d.view_matrix, rv3d.window_matrix
        vp = gpu.state.viewport_get()
        self._off.draw_view3d(scene, bpy.context.view_layer, space, region, view, proj, do_color_management=True)
        gpu.state.viewport_set(*vp)
        self._error = None
        return self._off.texture_color

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        r = ctx.px(self.radius if self.radius is not None else th.r_md)
        now = time.perf_counter()
        W, H = max(8, int(w)), max(8, int(h))
        tex = self._off.texture_color if self._off is not None and self._off.width == W else None
        if tex is None or now - self._last >= 1.0 / max(0.5, self.fps):
            p.flush()
            try:
                tex = self._render(ctx, W, H)
            except Exception as e:
                self._error = str(e).split("\n")[0]
                tex = None
            self._last = now
        mark_animating(slow=True)
        p.rect(x, y, w, h, fill=th.surface_0, radius=r)
        if tex is not None:
            p.image(tex, x, y, w, h, radius=r, fit="stretch")
        else:
            p.icon("camera", x + w / 2 - ctx.px(12), y + h / 2, ctx.px(24), th.text_muted, 1.4)
            p.text(self._error or "", x + w / 2, y + h / 2 - ctx.px(14), th.fs_sm, th.text_muted, align="center",
                   valign="center", max_w=w - ctx.px(16))
        p.rect(x, y, w, h, radius=r, border=alpha((1, 1, 1, 1), 0.08), border_w=ctx.px(1))
        if self.label and tex is not None:
            lab = "● LIVE  ·  " + ("Camera" if self.source == "camera" else "View")
            lw = ctx.text_w(lab, th.fs_xs, "semibold") + ctx.px(14)
            p.rect(x + ctx.px(8), y + h - ctx.px(26), lw, ctx.px(18), fill=(0.05, 0.06, 0.06, 0.72), radius=ctx.px(9))
            p.text(lab, x + ctx.px(15), y + h - ctx.px(17), th.fs_xs, th.text, "semibold", valign="center")


class BeforeAfter(Widget):
    """Two images with a draggable divider."""

    def __init__(self, before, after, split=0.5, height=170, labels=("Before", "After"), **kw):
        super().__init__(height=height, **kw)
        self.before, self.after = before, after
        self.split = split
        self.labels = labels
        self._drag = False

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height)

    def on_press(self, ctx, ev):
        self._drag = True
        self.on_drag(ctx, ev)
        return True

    def on_drag(self, ctx, ev):
        x, y, w, h = self.rect
        self.split = max(0.0, min(1.0, (ev.x - x) / max(1.0, w)))
        self.redraw()

    def on_release(self, ctx, ev, inside):
        self._drag = False

    def on_nav(self, ctx, d):
        self.split = max(0.0, min(1.0, self.split + 0.02 * d))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        r = ctx.px(th.r_md)
        p.image(_val(self.after), x, y, w, h, radius=r)
        sx = x + w * self.split
        p.push_clip(x, y, sx - x, h)
        p.image(_val(self.before), x, y, w, h, radius=r)
        p.pop_clip()
        for txt, lx, al in ((self.labels[0], x + ctx.px(8), "left"), (self.labels[1], x + w - ctx.px(8), "right")):
            tw = ctx.text_w(txt, th.fs_xs, "semibold") + ctx.px(12)
            bx = lx if al == "left" else lx - tw
            p.rect(bx, y + h - ctx.px(26), tw, ctx.px(18), fill=(0.05, 0.06, 0.06, 0.7), radius=ctx.px(9))
            p.text(txt, bx + tw / 2, y + h - ctx.px(17), th.fs_xs, th.text, "semibold", align="center", valign="center")
        p.rect(sx - ctx.px(1), y, ctx.px(2), h, fill=(1, 1, 1, 0.9))
        kr = ctx.px(13 if self._drag or self.hovered else 12)
        p.shadow(sx - kr, y + h / 2 - kr, kr * 2, kr * 2, kr, (0, 0, 0, 0.5), ctx.px(6))
        p.circle(sx, y + h / 2, kr, fill=(0.97, 0.97, 0.97, 1))
        isz = ctx.px(10)
        p.icon("chevron_left", sx - isz - ctx.px(1), y + h / 2 - isz / 2, isz, (0.15, 0.16, 0.17, 1), 2.0)
        p.icon("chevron_right", sx + ctx.px(1), y + h / 2 - isz / 2, isz, (0.15, 0.16, 0.17, 1), 2.0)


class Carousel(Widget):
    """Images you page through with arrows, dots or the mouse wheel.
    images: [(source, caption)] or [source]; autoplay=seconds to advance on its own."""

    def __init__(self, images, index=0, height=160, autoplay=None, on_change=None, **kw):
        super().__init__(height=height, **kw)
        self.images = images
        self.index = index
        self.autoplay = autoplay
        self.on_change = on_change
        self._t = time.perf_counter()
        self._hot = None

    def _items(self):
        out = []
        for it in _val(self.images) or []:
            out.append(tuple(it) if isinstance(it, (tuple, list)) else (it, None))
        return out

    def get_state(self):
        return self.index

    def set_state(self, s):
        self.index = int(s)

    def go(self, i):
        n = len(self._items())
        if not n:
            return
        self.index = i % n
        self._t = time.perf_counter()
        call(self.on_change, self.index, self)
        self.redraw()

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height) + ctx.px(18)

    def _zone(self, ctx, ev):
        x, y, w, h = self.rect
        if ev.y < y + ctx.px(18):
            n = len(self._items())
            cx = x + w / 2 - (n - 1) * ctx.px(7)
            for i in range(n):
                if abs(ev.x - (cx + i * ctx.px(14))) < ctx.px(7):
                    return ("dot", i)
            return None
        if ev.x < x + ctx.px(40):
            return ("prev", None)
        if ev.x > x + w - ctx.px(40):
            return ("next", None)
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
        if z is None:
            return
        if z[0] == "dot":
            self.go(z[1])
        else:
            self.go(self.index + (1 if z[0] == "next" else -1))

    def on_wheel(self, ctx, ev):
        self.go(self.index - int(math.copysign(1, ev.wheel)))
        return True

    def on_nav(self, ctx, d):
        self.go(self.index + (1 if d > 0 else -1))

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        items = self._items()
        if not items:
            return
        if self.autoplay and time.perf_counter() - self._t > self.autoplay and not self.hovered:
            self.index = (self.index + 1) % len(items)
            self._t = time.perf_counter()
        if self.autoplay:
            mark_animating(slow=True)
        ih = h - ctx.px(18)
        iy = y + ctx.px(18)
        r = ctx.px(th.r_md)
        pos = self.anim("pos", float(self.index), speed=12)
        p.push_clip(x, iy, w, ih)
        for i, (src, cap) in enumerate(items):
            off = (i - pos) * w
            if abs(off) >= w:
                continue
            p.image(src, x + off, iy, w, ih, radius=r)
            if cap:
                p.rect(x + off, iy, w, ctx.px(30), fill=(0, 0, 0, 0), fill2=(0, 0, 0, 0.6), radius=(0, 0, r, r),
                       flat=(0, 0, 0, 0.5))
                p.text(cap, x + off + ctx.px(10), iy + ctx.px(12), th.fs_sm, th.text, "medium", valign="center",
                       max_w=w - ctx.px(20))
        p.pop_clip()
        if self.hovered:
            for kind, cx in (("prev", x + ctx.px(20)), ("next", x + w - ctx.px(20))):
                hot = self._hot is not None and self._hot[0] == kind
                p.circle(cx, iy + ih / 2, ctx.px(13), fill=(0.05, 0.06, 0.06, 0.75 if hot else 0.5))
                p.icon("chevron_left" if kind == "prev" else "chevron_right", cx - ctx.px(7), iy + ih / 2 - ctx.px(7),
                       ctx.px(14), (1, 1, 1, 1), 2.0)
        n = len(items)
        cx = x + w / 2 - (n - 1) * ctx.px(7)
        for i in range(n):
            on = i == self.index
            dw = ctx.px(16 if on else 6)
            p.rect(cx + i * ctx.px(14) - dw / 2 + (0 if on else 0), y + ctx.px(5), dw, ctx.px(6),
                   fill=th.accent if on else th.border_strong, radius=ctx.px(3))


def _fcurves(obj):
    ad = getattr(obj, "animation_data", None)
    act = ad.action if ad else None
    if act is None:
        return []
    try:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
        cb = action_get_channelbag_for_slot(act, ad.action_slot)
        if cb is not None:
            return list(cb.fcurves)
    except Exception:
        pass
    return list(getattr(act, "fcurves", []) or [])


def keyframe_frames(obj):
    """Sorted frames that hold keyframes on obj's action."""
    frames = set()
    for fc in _fcurves(obj):
        for kp in fc.keyframe_points:
            frames.add(round(kp.co[0], 2))
    return sorted(frames)


class FrameScrubber(Widget):
    """Timeline strip bound to the scene: drag to change the frame, shows the frame range,
    keyframes of the active object and timeline markers, with play / pause."""

    def __init__(self, height=58, show_keys=True, show_markers=True, **kw):
        super().__init__(height=height, **kw)
        self.show_keys = show_keys
        self.show_markers = show_markers
        self._drag = False
        self._hot = None

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        return self.resolve_width(ctx, avail_w), ctx.px(self.height)

    def _scene(self):
        import bpy
        return bpy.context.scene

    def _track(self, ctx):
        x, y, w, h = self.rect
        return x + ctx.px(10), y + ctx.px(6), w - ctx.px(20), ctx.px(26)

    def _frame_at(self, ctx, ex):
        sc = self._scene()
        tx, ty, tw, th_ = self._track(ctx)
        f = (ex - tx) / max(1.0, tw)
        return int(round(sc.frame_start + max(0.0, min(1.0, f)) * (sc.frame_end - sc.frame_start)))

    def _zone(self, ctx, ev):
        x, y, w, h = self.rect
        if ev.y > y + h - ctx.px(26):
            if ev.x < x + ctx.px(34):
                return "play"
            return None
        return "track"

    def on_hover(self, ctx, ev):
        z = self._zone(ctx, ev)
        if z != self._hot:
            self._hot = z
            self.redraw()

    def on_leave(self, ctx):
        self._hot = None
        self.redraw()

    def on_press(self, ctx, ev):
        z = self._zone(ctx, ev)
        if z == "track":
            self._drag = True
            self._scene().frame_current = self._frame_at(ctx, ev.x)
        return True

    def on_drag(self, ctx, ev):
        if self._drag:
            f = self._frame_at(ctx, ev.x)
            sc = self._scene()
            if sc.frame_current != f:
                sc.frame_current = f

    def on_release(self, ctx, ev, inside):
        self._drag = False

    def on_click(self, ctx, ev):
        if self._zone(ctx, ev) == "play":
            from . import run_operator
            try:
                run_operator("screen.animation_play")
            except Exception:
                pass

    def on_nav(self, ctx, d):
        sc = self._scene()
        sc.frame_current = max(sc.frame_start, min(sc.frame_end, sc.frame_current + d))

    def on_wheel(self, ctx, ev):
        if ev.mod:
            self.on_nav(ctx, int(math.copysign(1, ev.wheel)))
            return True
        return False

    def paint(self, ctx, p):
        import bpy
        th = ctx.theme
        x, y, w, h = self.rect
        sc = self._scene()
        playing = bool(getattr(bpy.context.screen, "is_animation_playing", False)) if bpy.context.screen else False
        if playing:
            mark_animating(slow=True)
        top = y + h - ctx.px(13)
        hot = self._hot == "play"
        p.circle(x + ctx.px(14), top, ctx.px(12), fill=th.accent if hot else th.surface_3)
        p.icon("pause" if playing else "play", x + ctx.px(8), top - ctx.px(6), ctx.px(12),
               th.accent_text if hot else th.text, 1.8)
        p.text("Frame %d" % sc.frame_current, x + ctx.px(34), top, th.fs_md, th.text, "semibold", valign="center")
        p.text("%d – %d  ·  %g fps" % (sc.frame_start, sc.frame_end, sc.render.fps / sc.render.fps_base),
               x + w, top, th.fs_xs, th.text_muted, align="right", valign="center")
        tx, ty, tw, tht = self._track(ctx)
        p.rect(tx - ctx.px(4), ty, tw + ctx.px(8), tht, fill=th.surface_0, radius=ctx.px(7), border=th.border,
               border_w=ctx.px(1))
        span = max(1, sc.frame_end - sc.frame_start)
        step = max(1, int(10 ** math.floor(math.log10(span / 4 + 1e-9))))
        for m in (1, 2, 5, 10):
            if span / (step * m) <= 8:
                step *= m
                break
        f = (sc.frame_start // step) * step
        while f <= sc.frame_end:
            if f >= sc.frame_start:
                fx = tx + (f - sc.frame_start) / span * tw
                p.rect(fx, ty + tht - ctx.px(7), ctx.px(1), ctx.px(5), fill=th.border_strong)
                p.text(str(f), fx, ty + tht - ctx.px(13), th.fs_xs - 1, th.text_muted, align="center", valign="center")
            f += step
        if self.show_keys and bpy.context.object is not None:
            for kf in keyframe_frames(bpy.context.object):
                if sc.frame_start <= kf <= sc.frame_end:
                    kx = tx + (kf - sc.frame_start) / span * tw
                    s = ctx.px(4.5)
                    p.sparkle(kx, ty + ctx.px(7), s, (0.95, 0.80, 0.35, 1.0), 1.0)
        if self.show_markers:
            for mk in sc.timeline_markers:
                if sc.frame_start <= mk.frame <= sc.frame_end:
                    mx = tx + (mk.frame - sc.frame_start) / span * tw
                    p.rect(mx - ctx.px(0.5), ty + ctx.px(2), ctx.px(1), tht - ctx.px(4), fill=alpha(th.info, 0.7))
                    p.text(mk.name, mx + ctx.px(3), ty + tht - ctx.px(5), th.fs_xs - 1.5, th.info, valign="center")
        cx = tx + (sc.frame_current - sc.frame_start) / span * tw
        cx = max(tx, min(tx + tw, cx))
        p.rect(cx - ctx.px(1), ty - ctx.px(2), ctx.px(2), tht + ctx.px(4), fill=th.accent, radius=ctx.px(1))
        p.circle(cx, ty + tht + ctx.px(2), ctx.px(4), fill=th.accent)


class DropZone(Widget):
    """Dashed area that opens Blender's file browser; on_files(paths, zone) gets the chosen files.
    (A panel can't receive files dragged from outside Blender, so the zone is click-to-browse.)"""

    def __init__(self, on_files=None, label="Add reference images", hint="PNG, JPG or EXR · click to browse",
                 filter="*.png;*.jpg;*.jpeg;*.exr;*.tif;*.webp", multiple=True, icon="upload", height=96, **kw):
        super().__init__(height=height, **kw)
        self.on_files = on_files
        self.label = label
        self.hint = hint
        self.filter = filter
        self.multiple = multiple
        self.icon = icon
        self.files = []

    def interactive(self):
        return True

    def measure(self, ctx, avail_w):
        extra = ctx.px(22) if self.files else 0.0
        return self.resolve_width(ctx, avail_w), ctx.px(self.height) + extra

    def on_enter(self, ctx):
        self.redraw()

    def on_leave(self, ctx):
        self.redraw()

    def on_press(self, ctx, ev):
        return True

    def on_click(self, ctx, ev):
        def done(paths):
            import os
            self.files = [p for p in paths if p and os.path.isfile(p)]
            call(self.on_files, self.files, self)
            self.redraw()
        ctx.surface.app.browse(done, mode="FILES" if self.multiple else "FILE", filter=self.filter)

    def paint(self, ctx, p):
        import os
        th = ctx.theme
        x, y, w, h = self.rect
        if self.files:
            names = ", ".join(os.path.basename(f) for f in self.files)
            p.icon("check", x, y + ctx.px(4), ctx.px(12), th.success, 2.0)
            p.text("%d file%s: %s" % (len(self.files), "" if len(self.files) == 1 else "s", names), x + ctx.px(18),
                   y + ctx.px(10), th.fs_xs, th.text_dim, valign="center", max_w=w - ctx.px(18))
            y += ctx.px(22)
            h -= ctx.px(22)
        hov = self.anim("hov", 1.0 if self.hovered else 0.0)
        r = ctx.px(th.r_lg)
        p.rect(x, y, w, h, fill=mix(th.surface_0, th.accent_soft, hov), radius=r)
        c = mix(th.border_strong, th.accent, hov)
        dash, gap = ctx.px(7), ctx.px(5)
        lw = ctx.px(1.4)
        inset = r * 0.6
        for (x0, y0, x1, y1) in ((x + inset, y, x + w - inset, y), (x + inset, y + h, x + w - inset, y + h),
                                 (x, y + inset, x, y + h - inset), (x + w, y + inset, x + w, y + h - inset)):
            length = math.hypot(x1 - x0, y1 - y0)
            n = int(length // (dash + gap))
            for i in range(n + 1):
                t0 = i * (dash + gap) / max(1.0, length)
                t1 = min(1.0, t0 + dash / max(1.0, length))
                p.line(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0, x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1, lw, c)
        for cx, cy, a0 in ((x + r, y + r, math.pi), (x + w - r, y + r, 1.5 * math.pi), (x + w - r, y + h - r, 0),
                           (x + r, y + h - r, 0.5 * math.pi)):
            p.arc(cx, cy, r, a0, math.pi / 2, lw, c)
        isz = ctx.px(22)
        p.circle(x + w / 2, y + h / 2 + ctx.px(14), ctx.px(17), fill=mix(th.surface_3, th.accent, hov * 0.25))
        p.icon(self.icon, x + w / 2 - isz / 2 + ctx.px(2), y + h / 2 + ctx.px(14) - isz / 2 + ctx.px(2), isz - ctx.px(4),
               mix(th.text_dim, th.accent, hov), 1.6)
        p.text(self.label, x + w / 2, y + h / 2 - ctx.px(13), th.fs_md, th.text, "medium", align="center",
               valign="center", max_w=w - ctx.px(16))
        p.text(self.hint, x + w / 2, y + h / 2 - ctx.px(29), th.fs_xs, th.text_muted, align="center", valign="center",
               max_w=w - ctx.px(16))
