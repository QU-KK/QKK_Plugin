"""Entry Buttons — expose Keymapper entries as clickable UI buttons.

An entry with `use_button` enabled draws a button in each UI location the user
picked (`button_locations`). The button shows the entry's icon and/or label and
runs the entry's operator(s) on click — the first operator whose poll passes,
mirroring how multi-operator keybind entries fall through in a keymap.

Implementation mirrors the classic pattern: one draw callback appended per
supported bpy.types menu/header class; each callback iterates the entries
targeting that location at draw time (cheap — entry count is small).
"""

import json

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

from . import persistence

# (hook class name, human label) — the places a button can be shown.
BUTTON_LOCATIONS = (
    ("TOPBAR_MT_file", "File menu"),
    ("TOPBAR_MT_edit", "Edit menu"),
    ("TOPBAR_MT_render", "Render menu"),
    ("TOPBAR_MT_window", "Window menu"),
    ("TOPBAR_MT_help", "Help menu"),
    ("VIEW3D_HT_header", "3D View header"),
    ("IMAGE_HT_header", "Image Editor header"),
    ("NODE_HT_header", "Node Editor header"),
    ("SEQUENCE_HT_header", "Sequencer header"),
    ("CLIP_HT_header", "Clip Editor header"),
    ("DOPESHEET_HT_header", "Dope Sheet header"),
    ("GRAPH_HT_header", "Graph Editor header"),
    ("NLA_HT_header", "NLA Editor header"),
    ("PROPERTIES_HT_header", "Properties editor header"),
    ("OUTLINER_HT_header", "Outliner header"),
    ("TEXT_HT_header", "Text Editor header"),
    ("CONSOLE_HT_header", "Python Console header"),
    ("INFO_HT_header", "Info header"),
    ("STATUSBAR_HT_header", "Status bar"),
)

LOCATION_LABELS = dict(BUTTON_LOCATIONS)


def entry_button_label(entry: dict) -> str:
    """The label a button shows for this entry.

    A per-button custom label (`button_label`) wins; otherwise the ENTRY's
    label exactly as the card shows it, which is what the field's "blank =
    entry label" hint promises. That resolution lives in the panel (custom
    label > attribute name for wm.context_* > friendly operator name), so
    call it instead of duplicating a weaker version here — duplicating it is
    why a "Face Orientation" entry produced a "Context Toggle" button."""
    lbl = (entry.get("button_label") or "").strip()
    if lbl:
        return lbl
    try:
        from .panel import _resolve_display_name
        name = _resolve_display_name(entry)
        if name:
            return name
    except Exception:
        pass
    return entry.get("custom_label") or entry.get("display_name") or "?"


def entry_button_icon(entry: dict) -> tuple:
    """Return (icon_name, icon_value) for the entry's button.

    Prefers the entry's custom icon, else the first operator's mapped icon.
    Exactly one of the two return values is meaningful; the other is ""/0.
    """
    custom = entry.get("custom_icon", "") or ""
    if custom:
        return custom, 0
    try:
        ops = json.loads(entry.get("operator_ids", "[]"))
        first = ops[0].get("id", "") if ops else ""
    except Exception:
        first = ""
    if first:
        from .database.op_icons import get_op_icon
        return get_op_icon(first), 0
    return "NONE", 0


def _coerce_op_kwargs(op_fn, legacy_props: dict, props_data: dict) -> dict:
    """Build bpy.ops call kwargs from an op-instance's stored props.

    Legacy `props` are strings from the curated pickers — coerced to the RNA
    property's real type. `props_data` (typed, from serialize_kmi_props) is
    applied on top and wins on overlap. Enum-flag lists become sets.
    """
    kwargs = {}
    try:
        rna_props = op_fn.get_rna_type().properties
    except Exception:
        return kwargs
    for name, raw in (legacy_props or {}).items():
        p = rna_props.get(name)
        if p is None:
            continue
        try:
            if p.type == "BOOLEAN":
                kwargs[name] = str(raw) in ("True", "true", "1")
            elif p.type == "INT":
                kwargs[name] = int(float(raw))
            elif p.type == "FLOAT":
                kwargs[name] = float(raw)
            else:  # STRING / ENUM
                kwargs[name] = str(raw)
        except Exception:
            continue
    for name, val in (props_data or {}).items():
        p = rna_props.get(name)
        if p is None:
            continue
        if p.type == "ENUM" and getattr(p, "is_enum_flag", False) \
                and isinstance(val, (list, tuple)):
            kwargs[name] = set(val)
        else:
            kwargs[name] = val
    return kwargs


class KEYMAPPER_OT_EntryButton(Operator):
    """Run a Keymapper entry from a UI button."""

    bl_idname = "keymapper.entry_button"
    bl_label = "Keymapper Entry"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()

    @classmethod
    def description(cls, context, properties):
        entry = persistence.get_entry_by_id(properties.entry_id)
        if entry:
            return f"Keymapper: {entry_button_label(entry)}"
        return "Keymapper entry button"

    def execute(self, context):
        entry = persistence.get_entry_by_id(self.entry_id)
        if not entry:
            self.report({"WARNING"}, "Keymapper: entry not found.")
            return {"CANCELLED"}
        try:
            ops = json.loads(entry.get("operator_ids", "[]"))
        except Exception:
            ops = []
        unreg = set(entry.get("unregistered_ops", []) or [])
        # Run the FIRST operator whose poll passes — same fall-through order a
        # multi-operator keybind entry has in the keymap.
        for op_inst in ops:
            op_id = op_inst.get("id", "") if isinstance(op_inst, dict) else str(op_inst)
            if not op_id or "." not in op_id or op_id in unreg:
                continue
            module, func = op_id.split(".", 1)
            try:
                op_fn = getattr(getattr(bpy.ops, module), func)
            except Exception:
                continue
            try:
                if not op_fn.poll():
                    continue
            except Exception:
                continue
            kwargs = _coerce_op_kwargs(
                op_fn,
                op_inst.get("props", {}) if isinstance(op_inst, dict) else {},
                op_inst.get("props_data", {}) if isinstance(op_inst, dict) else {},
            )
            try:
                result = op_fn("INVOKE_DEFAULT", **kwargs)
                if "CANCELLED" not in result:
                    return {"FINISHED"}
            except Exception as e:
                print(f"[Keymapper] Button op '{op_id}' failed: {e}")
                continue
        self.report(
            {"INFO"},
            "Keymapper: no operator of this entry can run in this context.",
        )
        return {"CANCELLED"}


def _make_location_draw(hook_name: str):
    """Draw callback for one UI location: a button per entry targeting it."""

    def draw_keymapper_buttons(self, context):
        try:
            entries = persistence.get_entries()
        except Exception:
            return
        layout = self.layout
        for entry in entries:
            if not entry.get("use_button", False):
                continue
            if not entry.get("enabled", True):
                continue
            if not entry.get("button_visible", True):
                continue
            if hook_name not in (entry.get("button_locations", []) or []):
                continue
            show_label = entry.get("button_show_label", True)
            show_icon = entry.get("button_show_icon", True)
            text = entry_button_label(entry) if show_label else ""
            icon, icon_value = ("NONE", 0)
            if show_icon:
                icon, icon_value = entry_button_icon(entry)
                # Version safety: unknown icon names degrade instead of crashing
                try:
                    from .panel import safe_icon
                    icon = safe_icon(icon, "DOT")
                except Exception:
                    pass
            op = layout.operator(
                "keymapper.entry_button",
                text=text,
                icon=icon,
                icon_value=icon_value,
            )
            op.entry_id = entry.get("entry_id", "")

    return draw_keymapper_buttons


_DRAW_CALLBACKS = {}

_classes = (KEYMAPPER_OT_EntryButton,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    for hook_name, _label in BUTTON_LOCATIONS:
        hook = getattr(bpy.types, hook_name, None)
        if hook is None:
            continue
        cb = _make_location_draw(hook_name)
        _DRAW_CALLBACKS[hook_name] = cb
        try:
            hook.append(cb)
        except Exception as e:
            print(f"[Keymapper] Button hook '{hook_name}' failed: {e}")
    print("[Keymapper] Buttons registered.")


def unregister():
    for hook_name, _label in BUTTON_LOCATIONS:
        hook = getattr(bpy.types, hook_name, None)
        cb = _DRAW_CALLBACKS.get(hook_name)
        if hook is not None and cb is not None:
            try:
                hook.remove(cb)
            except Exception:
                pass
    _DRAW_CALLBACKS.clear()
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[Keymapper] Buttons unregistered.")
