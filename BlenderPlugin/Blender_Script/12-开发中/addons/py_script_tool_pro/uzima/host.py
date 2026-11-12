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

"""Connects Uzima UI to Blender.

    app = uzima.App("my_addon")                    # unique id per add-on
    side = app.sidebar("My Tab", build=make_ui)    # custom N-panel tab
    view = app.viewport()                          # floating windows, dialogs, toasts over the 3D view

    def register():   app.register()
    def unregister(): app.unregister()

How it works: a hidden-header panel reserves the sidebar tab, a POST_PIXEL draw handler paints
the UI over the region, and one lightweight modal operator per window routes mouse and keyboard
events to the widgets (anything the UI doesn't use passes through to Blender).
"""

import time

import bpy

import json

from .actions import ActionsMixin, Hotkey
from .core import Ctx, Event, consume_animating, consume_slow, mark_animating
from .draw import Painter, unload_fonts, clear_textures, ensure_fonts, reload_fonts
from .overlays import Dialog, Overlay, Popover, Toast, Tooltip, Window
from .theme import DEFAULT, alpha

_apps = []

_KEY_MODS = {"LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL", "LEFT_ALT", "RIGHT_ALT", "OSKEY"}
_MOUSE = {"LEFTMOUSE", "RIGHTMOUSE", "MIDDLEMOUSE", "MOUSEMOVE", "WHEELUPMOUSE", "WHEELDOWNMOUSE",
          "TRACKPADPAN", "TRACKPADZOOM", "BUTTON4MOUSE", "BUTTON5MOUSE", "INBETWEEN_MOUSEMOVE"}
_SPACE_TYPES = {
    "VIEW_3D": "SpaceView3D", "IMAGE_EDITOR": "SpaceImageEditor", "NODE_EDITOR": "SpaceNodeEditor",
    "SEQUENCE_EDITOR": "SpaceSequenceEditor", "CLIP_EDITOR": "SpaceClipEditor", "TEXT_EDITOR": "SpaceTextEditor",
    "GRAPH_EDITOR": "SpaceGraphEditor", "DOPESHEET_EDITOR": "SpaceDopeSheetEditor", "PROPERTIES": "SpaceProperties",
}


def ui_scale():
    try:
        s = bpy.context.preferences.system.ui_scale
        return s if s > 0.1 else 1.0
    except Exception:
        return 1.0


@bpy.app.handlers.persistent
def _load_post_handler(*_):
    """Module-level and @persistent so Blender keeps it across file loads."""
    for app in list(_apps):
        try:
            app._on_load()
        except Exception:
            import traceback
            traceback.print_exc()


def request_redraw():
    """Ask every visible Uzima surface to repaint on the next frame."""
    for app in _apps:
        app.tag_redraw()


def _ptr(o):
    try:
        return o.as_pointer()
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Surface
# ---------------------------------------------------------------------------

class Surface:
    """A place where a UI lives: a sidebar tab or the main region of an editor."""

    def __init__(self, app, space="VIEW_3D", region="UI", category=None, build=None, root=None,
                 theme=None, padding=12, background=True, scroll=True, linear_output=None):
        self.app = app
        self.space = space
        self.region_type = region
        self.category = category
        self.build = build
        self._root = root
        self.theme = theme or DEFAULT
        self.padding = padding
        self.background = background
        self.scroll = scroll
        # Editors drawn by Blender's draw manager (3D viewport, image editor) composite add-on
        # overlays from an sRGB framebuffer and expect linear colors. None = pick automatically.
        if linear_output is None:
            linear_output = region == "WINDOW" and space in ("VIEW_3D", "IMAGE_EDITOR")
        self.linear_output = linear_output
        self.overlays = []
        self.focus = None
        self._view = None
        self._ctx = None
        self.area_ptr = None       # last area the mouse was in
        self.kb_nav = False        # focus came from the keyboard (draw a focus ring)
        self._restored = None
        self.content_rect_cached = (0.0, 0.0, 0.0, 0.0)

    # ---- root ----------------------------------------------------------
    @property
    def root(self):
        if self._root is None and self.build is not None:
            built = self.build(self)
            self._root = built
        if self._root is not None:
            self._root._uz_surface = self
        return self._root

    def set_root(self, widget):
        self._root = widget
        if widget is not None:
            widget._uz_surface = self
        self._view = None
        request_redraw()

    def rebuild(self):
        """Call build() again (e.g. after the data it reads changed)."""
        self._root = None
        self._view = None
        request_redraw()

    def view(self):
        r = self.root
        if r is None:
            return None
        if not self.scroll or getattr(r, "fills_region", False):
            return r
        if self._view is None or self._view.child is not r:
            from .layout import ScrollView
            self._view = ScrollView(r, padding=self.padding)
            self._view.fade_color = self.theme.bg
        return self._view

    # ---- region geometry -------------------------------------------------
    def is_active(self, area, region):
        if area is None or region is None:
            return False
        if area.type != self.space or region.type != self.region_type:
            return False
        if region.width <= 2 or region.height <= 2:
            return False
        if self.category:
            cat = getattr(region, "active_panel_category", None)
            if cat not in (None, "", "NONE") and cat != self.category:
                return False
            if cat in (None, "", "NONE") and not self.app.has_panel(self.category):
                return False
        return True

    def content_rect(self, region, scale, area=None):
        w, h = float(region.width), float(region.height)
        if self.region_type == "UI" and self.category:
            strip = self.theme.sidebar_tab_strip * scale
            if getattr(region, "alignment", "RIGHT") == "LEFT":
                return (strip, 0.0, w - strip, h)
            return (0.0, 0.0, w - strip, h)
        if self.region_type == "WINDOW" and area is not None:
            # with region overlap the sidebar, toolbar and headers float over the viewport:
            # keep windows, dialogs and toasts out from under them
            x0, y0, x1, y1 = 0.0, 0.0, w, h
            for r in area.regions:
                if r is region or r.type == "WINDOW" or r.width <= 1 or r.height <= 1:
                    continue
                lx, ly = r.x - region.x, r.y - region.y
                if lx >= w or lx + r.width <= 0 or ly >= h or ly + r.height <= 0:
                    continue  # not overlapping
                if r.type in ("UI", "TOOLS", "TOOL_PROPS", "HUD") and r.height > h * 0.5:
                    if lx + r.width / 2 > w / 2:
                        x1 = min(x1, lx)
                    else:
                        x0 = max(x0, lx + r.width)
                elif r.type in ("HEADER", "TOOL_HEADER", "FOOTER") and r.width > w * 0.5:
                    if ly + r.height / 2 > h / 2:
                        y1 = min(y1, ly)
                    else:
                        y0 = max(y0, ly + r.height)
            if x1 - x0 > 100 and y1 - y0 > 100:
                return (x0, y0, x1 - x0, y1 - y0)
        return (0.0, 0.0, w, h)

    def make_ctx(self, region, area=None):
        s = ui_scale()
        ctx = Ctx(self, s, self.theme, region.width, region.height)
        ctx.region = region
        ctx.area = area
        self._ctx = ctx
        return ctx

    def layout(self, ctx, region, area):
        rx, ry, rw, rh = self.content_rect(region, ctx.scale, area)
        v = self.view()
        if v is not None:
            v.measure(ctx, rw)
            v.arrange(ctx, rx, ry, rw, rh)
        self._place_overlays(ctx, region, area)

    def _area_overlays(self, area):
        ap = _ptr(area)
        out = []
        for o in self.overlays:
            if getattr(o, "all_areas", False):
                out.append(o)
                continue
            if o.area_ptr is None:
                o.area_ptr = ap
            if o.area_ptr == ap:
                out.append(o)
        return out

    def _place_overlays(self, ctx, region, area):
        rx, ry, rw, rh = self.content_rect(region, ctx.scale, area)
        toasts = []
        for o in self._area_overlays(area):
            if isinstance(o, Toast):
                toasts.append(o)
            else:
                o.place(ctx, rx, ry, rw, rh)
        # stack toasts in the bottom-right corner, newest at the bottom
        gap = ctx.px(8)
        yb = ry + ctx.px(16)
        for t in reversed(toasts):
            w, h = t.size(ctx)
            t.place_at(ctx, rx + rw - w - ctx.px(16), yb, w, h)
            yb += h + gap

    # ---- drawing ---------------------------------------------------------
    def draw(self):
        ctx_b = bpy.context
        self.draw_region(ctx_b.area, ctx_b.region)

    def draw_region(self, area, region):
        if not self.is_active(area, region):
            return
        if self.region_type == "WINDOW":
            self.app._frame_times.append(time.perf_counter())
            del self.app._frame_times[:-90]
            if self.app._color_sample is not None:
                self.app._sample_color_now(area, region)
        self._restore_state_once()
        ctx = self.make_ctx(region, area)
        th = self.theme
        try:
            ensure_fonts()
            p = Painter(ctx.scale, th, linear=self.linear_output)
            self.layout(ctx, region, area)
            rx, ry, rw, rh = self.content_rect(region, ctx.scale, area)
            if self.region_type == "UI" and self.background:
                p.rect(rx, ry, rw, rh, fill=alpha(th.bg, th.sidebar_bg_alpha))
            v = self.view()
            if v is not None:
                v.paint(ctx, p)
            ovs = self._area_overlays(area)
            for o in sorted(ovs, key=lambda o: (o.layer, ovs.index(o))):
                o.paint(ctx, p)
            f = self.focus
            if f is not None and self.kb_nav and not getattr(f, "text_entry", False) and f.visible:
                # keyboard focus ring
                fx, fy, fw, fh = f.rect
                k = ctx.px(3)
                p.rect(fx - k, fy - k, fw + 2 * k, fh + 2 * k, radius=ctx.px(10), border=th.border_focus,
                       border_w=ctx.px(1.6), fill=(0, 0, 0, 0))
            p.finish()
        except Exception:
            import traceback
            traceback.print_exc()
        if consume_animating():
            self.app.ensure_ticker(fast=True)
        if consume_slow():
            self.app.ensure_ticker(slow=True)

    # ---- persisted UI state (tabs, open cards...) saved in the .blend ------------------------------
    def _state_id(self):
        return "%s/%s/%s" % (self.app.ns, self.space, self.category or self.region_type)

    def save_state(self):
        """Store get_state() of every keyed widget in a scene custom property (saved with the file)."""
        r = self._root
        if r is None:
            return
        data = {}
        for w in r.walk():
            if w.key:
                st = w.get_state()
                if st is not None:
                    data[w.key] = st
        try:
            scene = bpy.context.scene
            blob = json.loads(scene.get("uzima_ui_state", "{}") or "{}")
            if blob.get(self._state_id()) == data:
                return
            blob[self._state_id()] = data
            scene["uzima_ui_state"] = json.dumps(blob)
        except Exception:
            pass

    def _restore_state_once(self):
        try:
            scene = bpy.context.scene
            token = (scene.as_pointer(), self.app._load_count, id(self._root))
        except Exception:
            return
        if token == self._restored or self.root is None:
            return
        self._restored = (token[0], token[1], id(self._root))
        try:
            data = json.loads(scene.get("uzima_ui_state", "{}") or "{}").get(self._state_id(), {})
        except Exception:
            return
        for w in self._root.walk():
            if w.key and w.key in data:
                try:
                    w.set_state(data[w.key])
                except Exception:
                    pass

    def needs_window_redraw(self):
        return bool(self.overlays) or self._root is not None or self.build is not None

    # ---- hit testing ---------------------------------------------------------
    def hit(self, ctx, area, x, y):
        """Return (widget, overlay) at local point. widget may be None."""
        ovs = self._area_overlays(area)
        for o in sorted(ovs, key=lambda o: (-o.layer, -ovs.index(o))):
            w = o.hit(x, y)
            if w is not None:
                return w, o
            if o.modal:
                return o, o
        v = self.view()
        if v is not None:
            rx, ry, rw, rh = self.content_rect_cached
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return v.hit(x, y), None
        return None, None

    # ---- focus -------------------------------------------------------------
    def set_focus(self, w):
        old = self.focus
        if old is w:
            return
        self.focus = w
        ctx = self._ctx
        if old is not None:
            old.focused = False
            old.on_blur(ctx)
        if w is not None:
            w.focused = True
            w.on_focus(ctx)
            self.app.focus_surface = self
            self.app.ensure_ticker()
        elif self.app.focus_surface is self:
            self.app.focus_surface = None
        request_redraw()

    # ---- overlays --------------------------------------------------------------
    def add_overlay(self, o, area_ptr=None):
        o.surface = self
        o.area_ptr = area_ptr if area_ptr is not None else (self.app.last_area_ptr or self.area_ptr)
        o.opened_at = time.perf_counter()
        o.set_anim("appear", 0.0)
        self.overlays.append(o)
        self.app.ensure_ticker(fast=True)
        request_redraw()
        return o

    def remove_overlay(self, o):
        if o in self.overlays:
            self.overlays.remove(o)
            if self.focus is not None:
                w = self.focus
                while w is not None and w is not o:
                    w = w.parent
                if w is o or self.focus is o:
                    self.set_focus(None)
            if self.app.hover and self.app.hover[1] is not None:
                h = self.app.hover[1]
                while h is not None and h is not o:
                    h = h.parent
                if h is o:
                    self.app.hover = None
            for child in [c for c in self.overlays if getattr(c, "parent_pop", None) is o]:
                self.remove_overlay(child)
            cb = getattr(o, "on_close", None)
            o.on_close = None
            from .core import call
            call(cb, o)
            request_redraw()

    def raise_overlay(self, o):
        if o in self.overlays:
            self.overlays.remove(o)
            self.overlays.append(o)

    def open_popover(self, content, anchor=None, width=None, on_close=None, at=None, parent=None,
                     side="auto", area_ptr=None):
        """Open a popover. parent=<Popover> keeps the parent open (sub-menus)."""
        if parent is None:
            self.close_popover()
        else:
            for o in list(self.overlays):
                if isinstance(o, Popover) and getattr(o, "parent_pop", None) is parent:
                    self.remove_overlay(o)
        pop = Popover(content, anchor=anchor, width=width, at=at, side=side)
        pop.parent_pop = parent
        pop.on_close = on_close
        self.add_overlay(pop, area_ptr=area_ptr)
        if getattr(content, "focusable", False):
            self.set_focus(content)
        return pop

    def close_popover(self):
        for o in list(self.overlays):
            if isinstance(o, Popover):
                self.remove_overlay(o)

    def window(self, content=None, **kw):
        """Open a floating window. See overlays.Window for options."""
        w = content if isinstance(content, Window) else Window(content, **kw)
        return self.add_overlay(w)

    def dialog(self, title, message="", **kw):
        d = Dialog(title, message, **kw)
        self.add_overlay(d)
        self.set_focus(d)
        return d

    def toast(self, title, message="", kind="info", duration=3.5, **kw):
        self.app._record_notification(title, message, kind)
        t = Toast(title, message, kind, duration, **kw)
        return self.add_overlay(t)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App(ActionsMixin):
    def __init__(self, namespace, theme=None, cursors=False):
        """cursors=False keeps Blender's normal arrow pointer over the whole UI.
        cursors=True switches to hand / text cursors over buttons and fields."""
        ns = "".join(ch if ch.isalnum() else "_" for ch in namespace.lower()).strip("_") or "uzima"
        self.ns = ns
        self.theme = theme or DEFAULT
        self.surfaces = []
        self._panels = {}
        self._classes = []
        self._handles = []
        self._pumping = set()
        self.registered = False
        self._init_actions()
        self._frame_times = []
        self._load_count = 0
        self._slow_until = 0.0
        self.use_cursors = cursors
        self.hover = None          # (surface, widget, area_ptr, region_ptr)
        self.capture = None        # (surface, widget, area_ptr, region_ptr, press_xy)
        self.focus_surface = None
        self._tooltip = None       # (widget, since, surface, area_ptr)
        self._ticker = False
        self._fast_until = 0.0
        self._cursor = None
        self._last_click = (0.0, None)
        self.last_area_ptr = None
        # keep one bound-method object each so timers/handlers can be found again on unregister
        self._watchdog_fn = self._watchdog
        self._tick_fn = self._tick
        self._on_load_fn = self._on_load

    # ---- surfaces --------------------------------------------------------------
    def sidebar(self, category, build=None, root=None, space="VIEW_3D", theme=None, padding=12):
        s = Surface(self, space, "UI", category=category, build=build, root=root, theme=theme or self.theme,
                    padding=padding)
        self.surfaces.append(s)
        self._panels[category] = None
        return s

    def viewport(self, space="VIEW_3D", build=None, root=None, theme=None):
        s = Surface(self, space, "WINDOW", build=build, root=root, theme=theme or self.theme,
                    background=False, scroll=False)
        self.surfaces.append(s)
        return s

    def has_panel(self, category):
        return category in self._panels

    def first_viewport(self):
        for s in self.surfaces:
            if s.region_type == "WINDOW":
                return s
        return None

    # ---- palette, pie, drawer, tour, viewport tools ---------------------------------------------------
    def command_palette(self, info=None, include_blender=True, extra=None):
        """Open the command palette over the 3D viewport (searches actions and Blender operators)."""
        from .feedback import CommandPalette, viewport_target
        surf, area, region = viewport_target(self, info or self.invoke_info)
        if surf is None:
            return None
        pal = CommandPalette(self, include_blender=include_blender, extra=extra)
        surf.add_overlay(pal, area_ptr=area.as_pointer() if area else None)
        surf.set_focus(pal)
        return pal

    def pie(self, items, info=None, at=None, title=None):
        """Open a pie menu at the mouse (from a hotkey action pass its info) or at region coords `at`."""
        from .feedback import PieMenu, viewport_target
        info = info or self.invoke_info or {}
        surf, area, region = viewport_target(self, info)
        if surf is None or region is None:
            return None
        if at is None:
            if "x" in info:
                at = (info["x"] - region.x, info["y"] - region.y)
            else:
                at = (region.width / 2, region.height / 2)
        pie = PieMenu(items, at, title=title)
        return surf.add_overlay(pie, area_ptr=area.as_pointer())

    def drawer(self, content, title=None, icon=None, side="right", width=320, backdrop=True):
        """Slide a panel in from the edge of the 3D viewport."""
        from .feedback import Drawer, viewport_target
        surf, area, region = viewport_target(self)
        if surf is None:
            return None
        d = Drawer(content, title=title, icon=icon, side=side, width=width, backdrop=backdrop)
        return surf.add_overlay(d, area_ptr=area.as_pointer() if area else None)

    def tour(self, steps, surface=None, on_finish=None):
        """Guided tour over a surface (default: the first sidebar). steps: [(widget_key, title, text)]."""
        from .feedback import Tour
        surf = surface or next((s for s in self.surfaces if s.region_type == "UI"), self.surfaces[0])
        t = Tour(steps, on_finish=on_finish)
        surf.add_overlay(t)
        t._reveal()
        return t

    def viewport_tool(self, tool, on=True):
        """Show (on=True) or hide a viewport tool instance (ObjectLabels, Ruler, HUD, SelectionToolbar...)."""
        surf = self.first_viewport()
        if surf is None:
            return None
        if on:
            if tool not in surf.overlays:
                surf.add_overlay(tool, area_ptr=None)
                tool.area_ptr = None
        elif tool in surf.overlays:
            surf.remove_overlay(tool)
        self.tag_redraw(force=True)
        return tool

    # convenience: toasts/dialogs/windows go to the viewport surface
    def toast(self, *a, **kw):
        s = self.first_viewport() or self.surfaces[0]
        return s.toast(*a, **kw)

    def dialog(self, *a, **kw):
        s = self.first_viewport() or self.surfaces[0]
        return s.dialog(*a, **kw)

    def window(self, *a, **kw):
        s = self.first_viewport() or self.surfaces[0]
        return s.window(*a, **kw)

    # ---- registration ------------------------------------------------------------
    def register(self):
        if self.registered:
            return
        ns = self.ns
        app = self

        for cat in list(self._panels):
            slug = "".join(ch if ch.isalnum() else "_" for ch in cat.lower())
            space = next(s.space for s in self.surfaces if s.category == cat)

            def draw(panel, context):
                h = context.region.height / max(ui_scale(), 0.01)
                col = panel.layout.column()
                col.scale_y = max(1.0, (h - 60) / 20.0)
                col.label(text="")

            cls = type("UZIMA_PT_%s_%s" % (ns, slug), (bpy.types.Panel,), {
                "bl_idname": "UZIMA_PT_%s_%s" % (ns, slug),
                "bl_space_type": space, "bl_region_type": "UI", "bl_category": cat,
                "bl_label": cat, "bl_options": {"HIDE_HEADER"}, "draw": draw,
            })
            self._panels[cat] = cls
            self._classes.append(cls)

        def modal(op, context, event):
            if not app.registered:
                app._pumping.discard(op._win)
                return {"CANCELLED"}
            try:
                used = app.handle(context, event)
            except Exception:
                import traceback
                traceback.print_exc()
                used = False
            return {"RUNNING_MODAL"} if used else {"PASS_THROUGH"}

        def invoke(op, context, event):
            op._win = _ptr(context.window)
            if op._win in app._pumping:
                return {"CANCELLED"}
            app._pumping.add(op._win)
            context.window_manager.modal_handler_add(op)
            return {"RUNNING_MODAL"}

        def cancel(op, context):
            app._pumping.discard(getattr(op, "_win", 0))

        op_cls = type("UZIMA_OT_%s_pump" % ns, (bpy.types.Operator,), {
            "bl_idname": "%s.uzima_pump" % ns, "bl_label": "Uzima UI events",
            "bl_options": {"INTERNAL"}, "modal": modal, "invoke": invoke, "cancel": cancel,
        })
        self._op_idname = op_cls.bl_idname
        self._classes.append(op_cls)

        self._classes.extend(self._register_actions())
        for c in self._classes:
            bpy.utils.register_class(c)

        for s in self.surfaces:
            st = getattr(bpy.types, _SPACE_TYPES.get(s.space, "SpaceView3D"))
            h = st.draw_handler_add(s.draw, (), s.region_type, "POST_PIXEL")
            self._handles.append((st, h, s.region_type))

        self.registered = True
        _apps.append(self)
        self._register_keymaps()
        if not bpy.app.background:
            bpy.app.timers.register(self._watchdog_fn, first_interval=0.2, persistent=True)
        if _load_post_handler not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_load_post_handler)
        self.tag_redraw()

    def unregister(self):
        if not self.registered:
            return
        self.registered = False
        if self in _apps:
            _apps.remove(self)
        for st, h, rt in self._handles:
            try:
                st.draw_handler_remove(h, rt)
            except Exception:
                pass
        self._handles.clear()
        for t in (self._watchdog_fn, self._tick_fn):
            if bpy.app.timers.is_registered(t):
                bpy.app.timers.unregister(t)
        self._ticker = False
        if not _apps and _load_post_handler in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_load_post_handler)
        self._unregister_keymaps()
        for c in reversed(self._classes):
            try:
                bpy.utils.unregister_class(c)
            except Exception:
                pass
        self._classes.clear()
        self._pumping.clear()
        self._restore_cursor()
        if not _apps:
            unload_fonts()
            clear_textures()
        self.tag_redraw(force=True)

    # ---- event pump lifetime -------------------------------------------------------
    def _on_load(self, *_):
        # a new .blend was opened: the window manager, images and fonts were all replaced
        self._pumping.clear()
        self.hover = self.capture = None
        self.focus_surface = None
        for s in self.surfaces:
            s.focus = None
            s.overlays = [o for o in s.overlays if isinstance(o, Window) and not isinstance(o, Popover)]
        clear_textures()
        reload_fonts()
        self._load_count += 1
        self.pick = None
        self.tag_redraw(force=True)

    def _watchdog(self):
        if not self.registered:
            return None
        wm = bpy.context.window_manager
        if wm is None:
            return 0.5
        mod = getattr(bpy.ops, self.ns)
        for win in wm.windows:
            if _ptr(win) in self._pumping or win.screen is None:
                continue
            try:
                with bpy.context.temp_override(window=win):
                    mod.uzima_pump("INVOKE_DEFAULT")
            except Exception:
                pass
        return 0.5

    # ---- redraw / ticking ----------------------------------------------------------
    def tag_redraw(self, force=False):
        wm = bpy.context.window_manager if hasattr(bpy.context, "window_manager") else None
        if wm is None:
            return
        spaces = {s.space for s in self.surfaces}
        for win in wm.windows:
            scr = win.screen
            if scr is None:
                continue
            for area in scr.areas:
                if area.type not in spaces:
                    continue
                for region in area.regions:
                    for s in self.surfaces:
                        if s.space == area.type and s.region_type == region.type:
                            if force or region.type != "WINDOW" or s.needs_window_redraw():
                                region.tag_redraw()
                            break

    def viewport_fps(self):
        """Frames per second of the 3D viewport over the last second (needs app.viewport())."""
        t = self._frame_times
        now = time.perf_counter()
        recent = [x for x in t if now - x < 1.0]
        if len(recent) < 2:
            return 0.0
        return (len(recent) - 1) / max(1e-3, recent[-1] - recent[0])

    def ensure_ticker(self, fast=False, slow=False):
        if fast:
            self._fast_until = time.perf_counter() + 0.25
        if slow:
            self._slow_until = time.perf_counter() + 0.3
        if not self._ticker and self.registered:
            self._ticker = True
            bpy.app.timers.register(self._tick_fn, first_interval=1 / 60, persistent=True)

    def _tick(self):
        if not self.registered:
            self._ticker = False
            return None
        now = time.perf_counter()
        for s in self.surfaces:
            for o in list(s.overlays):
                if isinstance(o, Toast) and o.expired():
                    s.remove_overlay(o)
        tt = self._tooltip
        if tt and tt[0] is not None and now - tt[1] > tt[2].theme.tooltip_delay:
            w, _since, surf, ap = tt
            if not any(isinstance(o, Tooltip) for o in surf.overlays) and w.hovered:
                surf.add_overlay(Tooltip(w.tooltip, w), area_ptr=ap)
            self._tooltip = (None, now, surf, ap)
        fast = now < self._fast_until
        busy = fast or any(s.overlays for s in self.surfaces) or self.focus_surface is not None or \
            (self._tooltip is not None and self._tooltip[0] is not None) or now < self._slow_until
        self.tag_redraw()
        if fast:
            return 1 / 60
        if busy:
            return 0.1 if self.focus_surface is None else 0.12
        self._ticker = False
        return None

    # ---- cursor ---------------------------------------------------------------------------
    def _set_cursor(self, win, name):
        if not self.use_cursors:
            # cursors off = "keep Blender's arrow". But handle()'s MOUSEMOVE branch consumes
            # moves over the UI region (returns True -> RUNNING_MODAL), which blocks Blender
            # from resetting its own cursor afterwards (e.g. the resize cursor left by
            # region-scale). So enforce the arrow here when we own the event: cursor_set is
            # cheap, and an active region-scale modal cursor overrides this during a drag.
            try:
                win.cursor_set("DEFAULT")
            except Exception:
                pass
            return
        if name == self._cursor:
            return
        try:
            win.cursor_set(name or "DEFAULT")
        except Exception:
            pass
        self._cursor = name

    def _restore_cursor(self):
        if self._cursor:
            try:
                for win in bpy.context.window_manager.windows:
                    win.cursor_set("DEFAULT")
            except Exception:
                pass
        self._cursor = None

    # ---- events ------------------------------------------------------------------------------
    def _locate(self, win, mx, my):
        """Find (surface, area, region) under the window-space mouse position."""
        scr = win.screen
        if scr is None:
            return None
        spaces = {s.space for s in self.surfaces}
        for area in scr.areas:
            if area.type not in spaces:
                continue
            if not (area.x <= mx < area.x + area.width and area.y <= my < area.y + area.height):
                continue
            regs = [r for r in area.regions if r.width > 1 and r.height > 1 and
                    r.x <= mx < r.x + r.width and r.y <= my < r.y + r.height]
            regs.sort(key=lambda r: 1 if r.type == "WINDOW" else 0)
            for region in regs:
                for s in self.surfaces:
                    if s.is_active(area, region):
                        if s.region_type == "UI":
                            cx, cy, cw, ch = s.content_rect(region, ui_scale())
                            lx = mx - region.x
                            if not (cx <= lx <= cx + cw):
                                return None   # category tabs: let Blender handle them
                        return s, area, region
                if region.type != "WINDOW":
                    # some other overlapping region (header, toolbar) is on top
                    for s in self.surfaces:
                        if s.region_type == "WINDOW" and s.overlays:
                            break
                    else:
                        return None
        return None

    def _region_by_ptr(self, win, area_ptr, region_ptr):
        scr = win.screen
        if scr is None:
            return None, None
        for area in scr.areas:
            if _ptr(area) == area_ptr:
                for r in area.regions:
                    if _ptr(r) == region_ptr:
                        return area, r
        return None, None

    def _event(self, event, region, area, win, wheel=0.0):
        return Event(type=event.type, value=event.value, x=event.mouse_x - region.x, y=event.mouse_y - region.y,
                     shift=event.shift, ctrl=event.ctrl, alt=event.alt, oskey=event.oskey,
                     unicode=getattr(event, "unicode", ""), dx=0.0, dy=0.0, wheel=wheel, region=region,
                     area=area, window=win, is_repeat=getattr(event, "is_repeat", False))

    def _prepare(self, s, area, region):
        ctx = s.make_ctx(region, area)
        s.layout(ctx, region, area)
        s.content_rect_cached = s.content_rect(region, ctx.scale, area)
        s.area_ptr = _ptr(area)
        self.last_area_ptr = s.area_ptr
        return ctx

    def _set_hover(self, surf, widget, area, region, ctx, ev):
        old = self.hover
        if old and old[1] is widget:
            if widget is not None:
                widget.on_hover(ctx, ev)
            return
        if old and old[1] is not None:
            ow = old[1]
            ow.hovered = False
            octx = old[0]._ctx or ctx
            ow.on_leave(octx)
            # hide tooltip
            for o in list(old[0].overlays):
                if isinstance(o, Tooltip):
                    old[0].remove_overlay(o)
        self.hover = (surf, widget, _ptr(area), _ptr(region)) if widget is not None else None
        if widget is not None:
            widget.hovered = True
            widget.on_enter(ctx)
            widget.on_hover(ctx, ev)
            if widget.tooltip:
                self._tooltip = (widget, time.perf_counter(), surf, _ptr(area))
                self.ensure_ticker()
            else:
                self._tooltip = None
        else:
            self._tooltip = None
        request_redraw()

    def _cursor_for(self, w):
        while w is not None:
            if w.cursor:
                return w.cursor
            w = w.parent
        return None

    def handle(self, context, event):
        et = event.type
        val = event.value
        if et in ("TIMER", "TIMER_REPORT", "TIMERREGION", "NONE", "INBETWEEN_MOUSEMOVE", "WINDOW_DEACTIVATE",
                  "TIMER0", "TIMER1", "TIMER2", "TIMER_JOBS", "TIMER_AUTOSAVE", "ACTIONZONE_AREA",
                  "ACTIONZONE_REGION", "ACTIONZONE_FULLSCREEN", "XR_ACTION"):
            return False
        win = context.window
        if win is None:
            return False
        is_mouse = et in _MOUSE

        # 0) eyedropper / object picking mode
        if self.pick is not None:
            r = self._handle_pick(win, event)
            if r is not None:
                return r
        wheel = 0.0
        if et == "WHEELUPMOUSE":
            wheel = 1.0
        elif et == "WHEELDOWNMOUSE":
            wheel = -1.0
        elif et == "TRACKPADPAN":
            wheel = (event.mouse_y - event.mouse_prev_y) / (12.0 * ui_scale())
            if getattr(event, "is_direction_inverted", False):
                wheel = -wheel

        # 1) a widget is being dragged: it gets everything until release
        if self.capture is not None and is_mouse:
            surf, w, ap, rp, press = self.capture
            area, region = self._region_by_ptr(win, ap, rp)
            if region is None:
                self.capture = None
                return False
            ctx = surf._ctx or surf.make_ctx(region)
            ev = self._event(event, region, area, win, wheel)
            if et == "MOUSEMOVE":
                w.on_drag(ctx, ev)
                request_redraw()
                return True
            if et == "LEFTMOUSE" and val == "RELEASE":
                self.capture = None
                inside = w.contains(ev.x, ev.y)
                w.pressed = False
                w.on_release(ctx, ev, inside)
                if inside and w.is_enabled:
                    w.on_click(ctx, ev)
                    surf.save_state()
                request_redraw()
                return True
            return True

        # 2) keyboard goes to the focused widget
        if not is_mouse:
            fs = self.focus_surface
            if fs is not None and fs.focus is not None:
                if et in _KEY_MODS:
                    return False
                if val == "PRESS":
                    w = fs.focus
                    area = region = None
                    ctx = fs._ctx
                    if ctx is None:
                        return False
                    ev = Event(type=et, value=val, x=0, y=0, shift=event.shift, ctrl=event.ctrl, alt=event.alt,
                               oskey=event.oskey, unicode=getattr(event, "unicode", ""), dx=0, dy=0, wheel=0,
                               region=None, area=None, window=win, is_repeat=getattr(event, "is_repeat", False))
                    used = w.on_key(ctx, ev)
                    if not used and not getattr(w, "text_entry", False):
                        used = self._nav_key(fs, w, ctx, ev)
                    if not used and et == "ESC":
                        owner = w
                        while owner is not None and not isinstance(owner, Overlay):
                            owner = owner.parent
                        if owner is not None and owner.dismiss_outside:
                            fs.remove_overlay(owner)
                        fs.set_focus(None)
                        used = True
                    request_redraw()
                    if used:
                        return True
                    # text widgets swallow all keys so Blender shortcuts don't fire while typing
                    return bool(getattr(w, "text_entry", False))
                return bool(getattr(fs.focus, "text_entry", False))
            if et == "ESC" and val == "PRESS":
                for s in self.surfaces:
                    for o in reversed(s.overlays):
                        if isinstance(o, (Popover, Dialog)) or getattr(o, "esc_closes", False):
                            s.remove_overlay(o)
                            return True
            if et == "TAB" and val == "PRESS" and not (event.ctrl or event.alt or event.oskey):
                loc = self._locate(win, event.mouse_x, event.mouse_y)
                if loc is not None and loc[0].region_type == "UI":
                    surf = loc[0]
                    self._prepare(surf, loc[1], loc[2])
                    return self._focus_step(surf, -1 if event.shift else 1)
            return False

        # 3) mouse: find what is under the pointer
        loc = self._locate(win, event.mouse_x, event.mouse_y)
        if loc is None:
            if self.hover is not None:
                hs = self.hover[0]
                self._set_hover(None, None, None, None, hs._ctx, None)
            if self._cursor:
                self._set_cursor(win, None)
            if et in ("LEFTMOUSE", "RIGHTMOUSE") and val == "PRESS":
                self._outside_click()
            return False
        surf, area, region = loc
        ctx = self._prepare(surf, area, region)
        ev = self._event(event, region, area, win, wheel)
        widget, overlay = surf.hit(ctx, area, ev.x, ev.y)

        if et == "MOUSEMOVE":
            self._set_hover(surf, widget, area, region, ctx, ev)
            self._set_cursor(win, self._cursor_for(widget))
            return widget is not None or surf.region_type == "UI"

        if et == "LEFTMOUSE" and val in ("PRESS", "DOUBLE_CLICK"):
            # close popovers when clicking elsewhere
            keep = set()
            o2 = overlay
            while o2 is not None:
                keep.add(id(o2))
                o2 = getattr(o2, "parent_pop", None)
            pops = [o for o in surf.overlays if o.dismiss_outside and id(o) not in keep]
            other_pops = [(s, o) for s in self.surfaces if s is not surf for o in s.overlays if o.dismiss_outside]
            for s, o in other_pops:
                s.remove_overlay(o)
            if pops:
                for o in pops:
                    surf.remove_overlay(o)
                return True
            surf.kb_nav = False
            if widget is None:
                if self.focus_surface is not None:
                    self.focus_surface.set_focus(None)
                return surf.region_type == "UI" or (overlay is not None and overlay.modal)
            if val == "DOUBLE_CLICK" and widget.on_double_click(ctx, ev):
                return True
            used = widget.on_press(ctx, ev) if widget.is_enabled else False
            if self._tooltip:
                self._tooltip = (None, 0, self._tooltip[2], self._tooltip[3])
            for o in list(surf.overlays):
                if isinstance(o, Tooltip):
                    surf.remove_overlay(o)
            if widget.focusable:
                surf.set_focus(widget)
            elif self.focus_surface is not None and self.focus_surface.focus is not None:
                f = self.focus_surface.focus
                # keep focus when clicking inside the focused widget's own overlay (e.g. menu search)
                p = widget
                while p is not None and p is not f:
                    p = p.parent
                if p is None:
                    self.focus_surface.set_focus(None)
            if used:
                widget.pressed = True
                self.capture = (surf, widget, _ptr(area), _ptr(region), (ev.x, ev.y))
                request_redraw()
            return True

        if et in ("WHEELUPMOUSE", "WHEELDOWNMOUSE", "TRACKPADPAN"):
            w = widget
            while w is not None:
                if w.on_wheel(ctx, ev):
                    return True
                w = w.parent
            return surf.region_type == "UI" or widget is not None

        if et in ("RIGHTMOUSE", "MIDDLEMOUSE"):
            if widget is not None:
                if et == "RIGHTMOUSE" and val == "PRESS":
                    fn = getattr(widget, "on_right_click", None)
                    if fn and fn(ctx, ev):
                        return True
                    if self._open_context_menu(surf, widget, ctx, ev):
                        return True
                return True
            return surf.region_type == "UI" and et == "RIGHTMOUSE"

        if et == "LEFTMOUSE" and val == "RELEASE":
            return widget is not None
        return widget is not None

    # ---- picking ----------------------------------------------------------------------------------
    def _handle_pick(self, win, event):
        et, val = event.type, event.value
        try:
            win.cursor_modal_set("EYEDROPPER")
        except Exception:
            pass
        done = False
        result = None
        if (et == "ESC" and val == "PRESS") or (et == "RIGHTMOUSE" and val == "PRESS"):
            self.pick = None
            done, result = True, True
        elif et == "LEFTMOUSE" and val == "PRESS":
            target = None
            scr = win.screen
            for area in (scr.areas if scr else []):
                if area.type != "VIEW_3D":
                    continue
                for r in area.regions:
                    if r.type == "WINDOW" and r.x <= event.mouse_x < r.x + r.width and \
                            r.y <= event.mouse_y < r.y + r.height:
                        target = (area, r)
            done, result = True, True
            if target is not None:
                try:
                    self._do_pick(event, target[0], target[1])
                except Exception:
                    import traceback
                    traceback.print_exc()
                    self.pick = None
            else:
                self.pick = None
        elif et == "MOUSEMOVE":
            return False
        if done:
            try:
                win.cursor_modal_restore()
            except Exception:
                pass
            request_redraw()
        return result

    # ---- context menus --------------------------------------------------------------------------------
    def _open_context_menu(self, surf, widget, ctx, ev):
        w = widget
        while w is not None and not w.context_menu:
            w = w.parent
        if w is None:
            return False
        items = w.context_menu(w) if callable(w.context_menu) else w.context_menu
        if not items:
            return False
        from .overlays import Menu
        surf.open_popover(Menu(items, context=w), at=(ev.x, ev.y), width=ctx.px(220))
        return True

    # ---- keyboard navigation ------------------------------------------------------------------------
    def _focusables(self, surf):
        root = None
        modal = [o for o in surf.overlays if o.modal]
        if modal:
            root = modal[-1]
        else:
            root = surf.view()
        out = []

        def visit(w):
            if w is None or not w.visible:
                return
            if w.interactive() and w.keyboard_nav and w.is_enabled:
                out.append(w)
            for c in w.children():
                visit(c)
        visit(root)
        return out

    def _focus_step(self, surf, d):
        items = self._focusables(surf)
        if not items:
            return False
        cur = surf.focus
        i = items.index(cur) if cur in items else (-1 if d > 0 else 0)
        nxt = items[(i + d) % len(items)]
        surf.kb_nav = True
        surf.set_focus(nxt)
        self._reveal(nxt)
        return True

    def _reveal(self, w):
        from .layout import ScrollView
        p = w.parent
        while p is not None and not isinstance(p, ScrollView):
            p = p.parent
        if p is None:
            return
        sx, sy, sw, sh = p.rect
        x, y, ww, hh = w.rect
        if y < sy + 8:
            p.scroll_to(p.offset + (sy + 8 - y))
        elif y + hh > sy + sh - 8:
            p.scroll_to(p.offset - (y + hh - (sy + sh - 8)))

    def _nav_key(self, surf, w, ctx, ev):
        t = ev.type
        if t == "TAB":
            return self._focus_step(surf, -1 if ev.shift else 1)
        if t in ("RET", "NUMPAD_ENTER", "SPACE"):
            x, y, ww, hh = w.rect
            cev = Event(type="LEFTMOUSE", value="PRESS", x=x + ww / 2, y=y + hh / 2, shift=False, ctrl=False,
                        alt=False, oskey=False, unicode="", dx=0, dy=0, wheel=0, region=None, area=None,
                        window=ev.window, is_repeat=False)
            if w.on_press(ctx, cev) is not False:
                w.on_release(ctx, cev, True)
                w.on_click(ctx, cev)
                surf.save_state()
            return True
        d = {"LEFT_ARROW": -1, "DOWN_ARROW": -1, "RIGHT_ARROW": 1, "UP_ARROW": 1}.get(t)
        if d is not None:
            fn = getattr(w, "on_nav", None)
            if fn is not None:
                fn(ctx, d * (10 if ev.shift else 1))
                return True
            return self._focus_step(surf, d if t in ("LEFT_ARROW", "RIGHT_ARROW") else -d)
        return False

    def _outside_click(self):
        for s in self.surfaces:
            for o in list(s.overlays):
                if o.dismiss_outside:
                    s.remove_overlay(o)
        if self.focus_surface is not None:
            self.focus_surface.set_focus(None)
