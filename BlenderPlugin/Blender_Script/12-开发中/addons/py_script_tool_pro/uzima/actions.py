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

"""Actions, hotkeys, the file browser and viewport picking.

Actions are named commands of your add-on. They run as a real Blender operator
(`<namespace>.uzima_action`), so they get undo, can be bound to keys in Blender's keymap,
and show up in the command palette, menus and buttons:

    @app.action("add_lamp", label="Add lamp", icon="light", hotkey="ctrl+shift+L")
    def add_lamp(context):
        bpy.ops.object.light_add(type="POINT")

    ui.Button("Add lamp", action="add_lamp")
    app.run_action("add_lamp")
    app.set_hotkey("add_lamp", "alt+L")     # updates Blender's keymap live
"""

import os
import time

import bpy

_KEY_NAMES = {
    "ZERO": "0", "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5", "SIX": "6",
    "SEVEN": "7", "EIGHT": "8", "NINE": "9", "SPACE": "Space", "RET": "Enter", "ESC": "Esc",
    "TAB": "Tab", "BACK_SPACE": "Backspace", "DEL": "Delete", "LEFT_ARROW": "←",
    "RIGHT_ARROW": "→", "UP_ARROW": "↑", "DOWN_ARROW": "↓", "HOME": "Home",
    "END": "End", "PAGE_UP": "Page Up", "PAGE_DOWN": "Page Down", "INSERT": "Insert",
    "COMMA": ",", "PERIOD": ".", "SLASH": "/", "MINUS": "-", "EQUAL": "=", "SEMI_COLON": ";",
    "QUOTE": "'", "ACCENT_GRAVE": "`", "LEFT_BRACKET": "[", "RIGHT_BRACKET": "]",
    "BACK_SLASH": "\\", "NUMPAD_ENTER": "Num Enter",
}


class Hotkey:
    """A key combination. Hotkey.parse("ctrl+shift+P") / str(hotkey) -> "Ctrl Shift P"."""

    __slots__ = ("type", "ctrl", "shift", "alt", "oskey")

    def __init__(self, type="NONE", ctrl=False, shift=False, alt=False, oskey=False):
        self.type, self.ctrl, self.shift, self.alt, self.oskey = type, ctrl, shift, alt, oskey

    @classmethod
    def parse(cls, combo):
        if combo is None or isinstance(combo, Hotkey):
            return combo
        parts = [p.strip() for p in combo.replace(" ", "+").split("+") if p.strip()]
        hk = cls()
        for part in parts:
            low = part.lower()
            if low in ("ctrl", "control"):
                hk.ctrl = True
            elif low == "shift":
                hk.shift = True
            elif low in ("alt", "option"):
                hk.alt = True
            elif low in ("cmd", "oskey", "super", "win"):
                hk.oskey = True
            else:
                t = part.upper()
                rev = {v.upper(): k for k, v in _KEY_NAMES.items()}
                hk.type = rev.get(t, t)
        return hk

    def parts(self):
        out = []
        if self.ctrl:
            out.append("Ctrl")
        if self.alt:
            out.append("Alt")
        if self.shift:
            out.append("Shift")
        if self.oskey:
            out.append("Cmd")
        if self.type and self.type != "NONE":
            out.append(_KEY_NAMES.get(self.type, self.type.replace("_", " ").title()
                                      if len(self.type) > 1 else self.type))
        return out

    def __str__(self):
        return " ".join(self.parts())

    def combo(self):
        mods = [m for m, on in (("ctrl", self.ctrl), ("alt", self.alt), ("shift", self.shift),
                                ("oskey", self.oskey)) if on]
        return "+".join(mods + [self.type])

    @property
    def empty(self):
        return not self.type or self.type == "NONE"


class Action:
    def __init__(self, name, fn, label=None, icon=None, description="", hotkey=None, keymap="3D View",
                 space="VIEW_3D", undo=True):
        self.name = name
        self.fn = fn
        self.label = label or name.replace("_", " ").capitalize()
        self.icon = icon
        self.description = description or (fn.__doc__ or "").strip().split("\n")[0]
        self.hotkey = Hotkey.parse(hotkey)
        self.keymap = keymap
        self.space = space
        self.undo = undo
        self.kmi = None


class ActionsMixin:
    """Mixed into App."""

    def _init_actions(self):
        self.actions = {}
        self.notifications = []
        self.unread = 0
        self.pick = None            # {"kind": "object" | "color", "callback": fn}
        self._browse_callbacks = {}
        self._keymaps = []
        self.invoke_info = None     # where the last action was invoked from (area, x, y)
        self._color_sample = None

    # ---- actions ---------------------------------------------------------------------------------
    def action(self, name, fn=None, label=None, icon=None, description="", hotkey=None, keymap="3D View",
               space="VIEW_3D"):
        """Register an action. Use as a decorator or call with fn=.
        The function is called as fn(context) or fn(context, info) where info has the area and
        mouse position of the hotkey press (for opening pies and popups at the cursor)."""
        def deco(f):
            act = Action(name, f, label, icon, description, hotkey, keymap, space)
            self.actions[name] = act
            if self.registered and act.hotkey and not act.hotkey.empty:
                self._add_kmi(act)
            return f
        return deco(fn) if fn is not None else deco

    def run_action(self, name, info=None):
        act = self.actions.get(name)
        if act is None:
            print("Uzima UI: no action named", name)
            return
        from .core import call
        r = call(act.fn, bpy.context, info or {})
        from .host import request_redraw
        request_redraw()
        return r

    def action_items(self):
        return list(self.actions.values())

    # ---- hotkeys / keymap ---------------------------------------------------------------------
    def set_hotkey(self, name, combo):
        """Change (or clear with None) the key of an action. Updates Blender's keymap live."""
        act = self.actions[name]
        act.hotkey = Hotkey.parse(combo) if combo else None
        if act.kmi is not None:
            km, kmi = act.kmi
            try:
                km.keymap_items.remove(kmi)
            except Exception:
                pass
            act.kmi = None
        if self.registered and act.hotkey and not act.hotkey.empty:
            self._add_kmi(act)

    def hotkey_of(self, name):
        act = self.actions.get(name)
        return act.hotkey if act else None

    def _add_kmi(self, act):
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.addon if wm else None
        if kc is None:
            return
        km = kc.keymaps.new(name=act.keymap, space_type=act.space)
        hk = act.hotkey
        kmi = km.keymap_items.new(self._action_idname, hk.type, "PRESS", ctrl=hk.ctrl, shift=hk.shift,
                                  alt=hk.alt, oskey=hk.oskey)
        kmi.properties.name = act.name
        act.kmi = (km, kmi)
        self._keymaps.append((km, kmi))

    def _register_actions(self):
        app = self
        ns = self.ns

        def execute(op, context):
            act = app.actions.get(op.name)
            if act is None:
                return {"CANCELLED"}
            app.run_action(op.name, getattr(op, "_info", None))
            return {"FINISHED"}

        def invoke(op, context, event):
            op._info = {"area": context.area, "region": context.region, "window": context.window,
                        "x": event.mouse_x, "y": event.mouse_y}
            app.invoke_info = op._info
            return execute(op, context)

        @classmethod
        def description(cls, context, props):
            act = app.actions.get(props.name)
            return act.description or act.label if act else ""

        op_cls = type("UZIMA_OT_%s_action" % ns, (bpy.types.Operator,), {
            "bl_idname": "%s.uzima_action" % ns, "bl_label": "Run action",
            "bl_options": {"REGISTER", "UNDO"},
            "__annotations__": {"name": bpy.props.StringProperty(name="Action", options={"HIDDEN"})},
            "execute": execute, "invoke": invoke, "description": description,
        })

        def b_invoke(op, context, event):
            context.window_manager.fileselect_add(op)
            return {"RUNNING_MODAL"}

        def b_execute(op, context):
            cb = app._browse_callbacks.pop(op.token, None)
            if op.mode == "DIR":
                paths = [op.directory]
            elif op.mode == "FILES" and len(op.files) and op.files[0].name:
                paths = [os.path.join(op.directory, f.name) for f in op.files]
            else:
                paths = [op.filepath]
            if cb:
                from .core import call
                bpy.app.timers.register(lambda: (call(cb, paths), None)[1], first_interval=0.0)
            return {"FINISHED"}

        def b_cancel(op, context):
            app._browse_callbacks.pop(op.token, None)

        browse_cls = type("UZIMA_OT_%s_browse" % ns, (bpy.types.Operator,), {
            "bl_idname": "%s.uzima_browse" % ns, "bl_label": "Accept", "bl_options": {"INTERNAL"},
            "__annotations__": {
                "token": bpy.props.StringProperty(options={"HIDDEN"}),
                "mode": bpy.props.EnumProperty(items=[("FILE", "File", ""), ("FILES", "Files", ""),
                                                      ("DIR", "Folder", "")], options={"HIDDEN"}),
                "filepath": bpy.props.StringProperty(subtype="FILE_PATH"),
                "directory": bpy.props.StringProperty(subtype="DIR_PATH"),
                "files": bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement),
                "filter_glob": bpy.props.StringProperty(default="*", options={"HIDDEN"}),
            },
            "invoke": b_invoke, "execute": b_execute, "cancel": b_cancel,
        })
        self._action_idname = op_cls.bl_idname
        self._browse_idname = browse_cls.bl_idname
        return [op_cls, browse_cls]

    def _register_keymaps(self):
        for act in self.actions.values():
            if act.hotkey and not act.hotkey.empty:
                self._add_kmi(act)

    def _unregister_keymaps(self):
        for km, kmi in self._keymaps:
            try:
                km.keymap_items.remove(kmi)
            except Exception:
                pass
        self._keymaps.clear()
        for act in self.actions.values():
            act.kmi = None

    # ---- file browser ---------------------------------------------------------------------------
    def browse(self, callback, mode="FILE", filter="*", start=""):
        """Open Blender's file browser. callback(paths) gets a list of chosen paths.
        mode: "FILE", "FILES" (several) or "DIR". filter: e.g. "*.png;*.jpg"."""
        token = "%x" % int(time.perf_counter() * 1e6)
        self._browse_callbacks[token] = callback
        mod, name = self._browse_idname.split(".")
        op = getattr(getattr(bpy.ops, mod), name)
        kw = dict(token=token, mode=mode, filter_glob=filter)
        if start:
            kw["filepath"] = start
        try:
            op("INVOKE_DEFAULT", **kw)
        except Exception as e:
            self._browse_callbacks.pop(token, None)
            print("Uzima UI: file browser failed", e)

    # ---- viewport picking --------------------------------------------------------------------------
    def pick_object(self, callback, filter=None):
        """Next click in a 3D viewport picks the object under the mouse: callback(obj).
        Esc or right-click cancels."""
        self.pick = {"kind": "object", "callback": callback, "filter": filter}
        self.toast("Pick an object", "Click it in the viewport. Esc cancels.", "accent", duration=2.5)

    def pick_color(self, callback):
        """Next click in a 3D viewport samples the color under the mouse: callback((r, g, b, a))."""
        self.pick = {"kind": "color", "callback": callback}
        self.toast("Pick a color", "Click anywhere in the viewport. Esc cancels.", "accent", duration=2.5)

    def _do_pick(self, event, area, region):
        pk = self.pick
        self.pick = None
        try:
            region.tag_redraw()
        except Exception:
            pass
        mx, my = event.mouse_x - region.x, event.mouse_y - region.y
        if pk["kind"] == "object":
            from bpy_extras import view3d_utils
            rv3d = area.spaces.active.region_3d
            ctx = bpy.context
            depsgraph = ctx.evaluated_depsgraph_get()
            coord = (mx, my)
            origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
            direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
            hit, _loc, _n, _i, obj, _m = ctx.scene.ray_cast(depsgraph, origin, direction)
            if hit and obj is not None:
                obj = getattr(obj, "original", obj)
                flt = pk.get("filter")
                if flt is None or flt(obj):
                    from .core import call
                    call(pk["callback"], obj)
                    return
            self.toast("Nothing picked", "No object under the mouse.", "warning", duration=2)
        else:
            # sampled in the viewport's next draw (needs a GPU context), delivered by a timer
            self._color_sample = (id(area), area.as_pointer(), region.as_pointer(), mx, my, pk["callback"])
            region.tag_redraw()

    def _sample_color_now(self, area, region):
        """Called from the viewport draw callback."""
        smp = self._color_sample
        if smp is None or smp[1] != area.as_pointer() or smp[2] != region.as_pointer():
            return
        self._color_sample = None
        _, _, _, mx, my, cb = smp
        try:
            import gpu
            ctx = bpy.context
            space = ctx.space_data
            rv3d = ctx.region_data
            w, h = region.width, region.height
            off = gpu.types.GPUOffScreen(w, h)
            off.draw_view3d(ctx.scene, ctx.view_layer, space, region, rv3d.view_matrix,
                            rv3d.window_matrix, do_color_management=True)
            with off.bind():
                fb = gpu.state.active_framebuffer_get()
                buf = fb.read_color(int(mx), int(my), 1, 1, 4, 0, "FLOAT")
            off.free()
            buf.dimensions = 4
            col = tuple(max(0.0, min(1.0, v)) for v in buf.to_list())
            col = (col[0], col[1], col[2], 1.0)
        except Exception as e:
            print("Uzima UI: color sample failed", e)
            return
        from .core import call
        bpy.app.timers.register(lambda: (call(cb, col), None)[1], first_interval=0.0)

    # ---- notification history ---------------------------------------------------------------------
    def _record_notification(self, title, message, kind):
        self.notifications.insert(0, {"title": title, "message": message, "kind": kind, "time": time.time()})
        del self.notifications[60:]
        self.unread += 1

    def clear_notifications(self):
        self.notifications.clear()
        self.unread = 0
        from .host import request_redraw
        request_redraw()
