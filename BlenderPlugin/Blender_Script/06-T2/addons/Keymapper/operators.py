"""
operators.py — Phase 2 inline form approach.
No popup dialogs — all UI lives inside the panel itself.
Keyboard events only affect the field the user is actively typing in.
"""

import uuid

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator

from . import persistence
from .database.bfa_ops import get_friendly_name

# ---------------------------------------------------------------------------
# WM scratch key names
# ---------------------------------------------------------------------------

WM_CONTEXTS = "keymapper_popup_contexts"
WM_CATEGORY = "keymapper_browse_category"
WM_OP_ID = "keymapper_picked_op_id"
WM_OP_IDS = "keymapper_selected_op_ids"  # JSON list of {id, props} dicts
WM_OP_PROPS_PREFIX = "keymapper_op_props_"  # prefix for per-op prop scratch keys


# ---------------------------------------------------------------------------
# Operator list helpers — new format: [{id, props}, ...]
# ---------------------------------------------------------------------------


def _safe_icon(preferred: str, fallback: str = "NONE") -> str:
    """Version-safe icon: `preferred` if it exists in this build, else fallback.

    Used for 5.2-only icons (STATUS_*) so labels don't crash on Blender 5.1.
    """
    try:
        from .panel import safe_icon
        return safe_icon(preferred, fallback)
    except Exception:
        return fallback


def get_button_locations(wm) -> list:
    """Form scratch: the button locations picked for the entry being edited."""
    import json as _j
    try:
        return _j.loads(wm.get("keymapper_form_button_locations", "[]") or "[]")
    except Exception:
        return []


def set_button_locations(wm, locs: list):
    import json as _j
    wm["keymapper_form_button_locations"] = _j.dumps(list(locs))



class KEYMAPPER_OT_FormToggleUseKeybind(Operator):
    """Whether this entry has keybind(s). At least one of Keybind/Button must stay on."""

    bl_idname = "keymapper.form_toggle_use_keybind"
    bl_label = "Keybind"
    bl_description = "This entry has keybind(s)"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        cur = bool(wm.get("keymapper_form_use_keybind", True))
        if cur and not bool(wm.get("keymapper_form_use_button", False)):
            self.report(
                {"WARNING"},
                "Keymapper: an entry needs at least a keybind or a button.",
            )
            return {"CANCELLED"}
        wm["keymapper_form_use_keybind"] = not cur
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleUseButton(Operator):
    """Whether this entry shows as UI button(s). At least one of Keybind/Button must stay on."""

    bl_idname = "keymapper.form_toggle_use_button"
    bl_label = "Button"
    bl_description = "This entry shows as button(s) in the UI locations you pick"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        cur = bool(wm.get("keymapper_form_use_button", False))
        if cur and not bool(wm.get("keymapper_form_use_keybind", True)):
            self.report(
                {"WARNING"},
                "Keymapper: an entry needs at least a keybind or a button.",
            )
            return {"CANCELLED"}
        wm["keymapper_form_use_button"] = not cur
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleButtonLabel(Operator):
    """Show the entry's label on the button. Label and icon can't both be hidden."""

    bl_idname = "keymapper.form_toggle_button_label"
    bl_label = "Show Label"
    bl_description = "Show the entry's label on the button"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        cur = bool(wm.get("keymapper_form_button_show_label", True))
        if cur and not bool(wm.get("keymapper_form_button_show_icon", True)):
            self.report(
                {"WARNING"},
                "Keymapper: the button must show at least a label or an icon.",
            )
            return {"CANCELLED"}
        wm["keymapper_form_button_show_label"] = not cur
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleButtonIcon(Operator):
    """Show the entry's icon on the button. Label and icon can't both be hidden."""

    bl_idname = "keymapper.form_toggle_button_icon"
    bl_label = "Show Icon"
    bl_description = "Show the entry's icon on the button"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        cur = bool(wm.get("keymapper_form_button_show_icon", True))
        if cur and not bool(wm.get("keymapper_form_button_show_label", True)):
            self.report(
                {"WARNING"},
                "Keymapper: the button must show at least a label or an icon.",
            )
            return {"CANCELLED"}
        wm["keymapper_form_button_show_icon"] = not cur
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleButtonConflicts(Operator):
    """Conflict detection for a button-only entry (shortcut conflicts only)."""

    bl_idname = "keymapper.form_toggle_button_conflicts"
    bl_label = "Conflict Detection"
    bl_description = (
        "Run conflict detection for this button-only entry (shortcut/operator "
        "conflicts only — a button has no keybind to clash)"
    )
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        wm["keymapper_form_button_conflicts"] = not bool(
            wm.get("keymapper_form_button_conflicts", False))
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleButtonLocation(Operator):
    """Include or exclude a UI location for this entry's button."""

    bl_idname = "keymapper.toggle_button_location"
    bl_label = "Toggle Button Location"
    bl_description = "Show or hide this entry's button in this location"
    bl_options = {"INTERNAL"}

    location: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        locs = get_button_locations(wm)
        if self.location in locs:
            locs.remove(self.location)
        else:
            locs.append(self.location)
        set_button_locations(wm, locs)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleButtonLocDropdown(Operator):
    """Open/close the button-locations dropdown."""

    bl_idname = "keymapper.form_toggle_button_loc_dropdown"
    bl_label = "Button Locations"
    bl_description = "Pick the UI locations where this entry's button shows"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        key = subcat_wm_key("button_locations_dd")
        wm[key] = not wm.get(key, False)
        _redraw(context)
        return {"FINISHED"}


def subcat_wm_key(key: str) -> str:
    """Resolve a subcat toggle key to its WM id-prop name, hashing long keys
    so both the reader (panel) and writer (operator) agree."""
    import hashlib
    raw = f"keymapper_subcat_{key}"
    if len(raw) > 58:
        raw = "keymapper_s_" + hashlib.md5(raw.encode()).hexdigest()[:46]
    return raw


def get_detect_contexts(wm, slot: int) -> list:
    """Per-keybind 'Additional Keybind Detection Context(s)' from WM scratch."""
    import json
    try:
        v = json.loads(wm.get(f"keymapper_detect_ctx_{slot}", "[]") or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def set_detect_contexts(wm, slot: int, ctxs: list):
    import json
    wm[f"keymapper_detect_ctx_{slot}"] = json.dumps(list(ctxs))


def clear_all_detect_contexts(wm):
    for slot in range(17):
        key = f"keymapper_detect_ctx_{slot}"
        if key in wm:
            wm[key] = "[]"


def get_ops_locked_contexts(wm) -> list:
    """Union of all selected operators' effective contexts (manual picks, or
    auto home keymaps when nothing is picked). Used as the locked, always-on
    part of the per-keybind detection context list."""
    out = set()
    for op_inst in _get_sel_ops(wm):
        oid = op_inst.get("id", "")
        ctxs = list(op_inst.get("contexts", []))
        if not ctxs and op_inst.get("context"):
            ctxs = [op_inst["context"]]
        if ctxs:
            out.update(ctxs)
        elif oid:
            try:
                from .keymap_manager import _get_keymaps_for_op
                out.update(_get_keymaps_for_op(oid))
            except Exception:
                pass
    return sorted(out)


def _get_sel_ops(wm) -> list:
    """Return list of {id, props} dicts from WM scratch."""
    import json

    raw = wm.get(WM_OP_IDS, "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _set_sel_ops(wm, ops: list):
    """Store list of {id, props} dicts to WM scratch."""
    import json

    wm[WM_OP_IDS] = json.dumps(ops)


def _saved_custom_icon_op(wm) -> str:
    """Saved custom icon of the entry being edited (preview fallback)."""
    try:
        from . import persistence
        eid = wm.get("keymapper_form_edit_id", "")
        if eid:
            e = persistence.get_entry_by_id(eid)
            return (e or {}).get("custom_icon", "") or ""
    except Exception:
        pass
    return ""


def build_preview_entry_from_form(wm) -> dict | None:
    """Assemble a lightweight entry dict from the live form state for conflict
    preview. Read-only: creates/persists nothing. Returns None if the form has
    no operators or no key set yet."""
    import json as _json

    sel_ops = form_view_ops(wm)
    if not sel_ops:
        return None

    kmi = get_scratch_kmi()
    if kmi is None or kmi.type == "NONE":
        return None

    # Normalize contexts the same way confirm does (single vs multi).
    from .database.keymap_contexts import KEYMAP_CONTEXTS as _ALL_CTX

    _curated = {c[0] for c in _ALL_CTX}
    ops_out = []
    for op_inst in sel_ops:
        oid = op_inst.get("id", "")
        ctxs = list(op_inst.get("contexts", []))
        if not ctxs and op_inst.get("context"):
            ctxs = [op_inst["context"]]
        ctxs = [c for c in ctxs if c in _curated]
        if not op_inst.get("use_multi_contexts", False) and len(ctxs) > 1:
            try:
                from .keymap_manager import _get_keymap_for_op as _gkfo
                auto = _gkfo(oid)
            except Exception:
                auto = ""
            ctxs = [auto] if auto in ctxs else [ctxs[0]]
        ops_out.append({
            "id": oid,
            "props": dict(op_inst.get("props", {})),
            "props_data": op_inst.get("props_data", {}),
            "context": "",
            "contexts": ctxs,
            "use_multi_contexts": op_inst.get("use_multi_contexts", False),
        })

    try:
        extra_slots = _json.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]")
    except Exception:
        extra_slots = []
    extra_keybinds = []
    for idx in range(len(extra_slots)):
        try:
            ex = _ensure_extra_scratch_kmi(idx + 1)
        except Exception:
            ex = None
        if ex and ex.type and ex.type != "NONE":
            extra_keybinds.append({
                "key": ex.type, "value": ex.value,
                "shift": ex.shift == 1, "ctrl": ex.ctrl == 1,
                "alt": ex.alt == 1, "oskey": ex.oskey == 1,
                "any": bool(wm.get(f"keymapper_kmi_any_{idx + 1}", False)),
                "key_modifier": getattr(ex, "key_modifier", "NONE") or "NONE",
                "detect_contexts": get_detect_contexts(wm, idx + 1),
            })

    return {
        "entry_id": "__preview__",
        "display_name": "preview",
        "operator_ids": _json.dumps(ops_out),
        "key": kmi.type,
        "detect_contexts": get_detect_contexts(wm, 0),
        "any": bool(wm.get("keymapper_kmi_any_0", False)),
        "shift": kmi.shift == 1, "ctrl": kmi.ctrl == 1,
        "alt": kmi.alt == 1, "oskey": kmi.oskey == 1,
        "key_modifier": kmi.key_modifier if kmi.key_modifier != "NONE" else "",
        "event_type": kmi.value,
        "keymap_contexts": "",
        "extra_keybinds": extra_keybinds,
        # Entry Buttons: preview respects the form's keybind/button mode so a
        # button-only entry previews shortcut conflicts only (or none).
        "use_keybind": bool(wm.get("keymapper_form_use_keybind", True)),
        "use_button": bool(wm.get("keymapper_form_use_button", False)),
        "button_conflict_detection": bool(
            wm.get("keymapper_form_button_conflicts", False)),
        "button_locations": get_button_locations(wm),
        "button_show_label": bool(
            wm.get("keymapper_form_button_show_label", True)),
        "button_show_icon": bool(
            wm.get("keymapper_form_button_show_icon", True)),
        "button_label": str(getattr(wm, "keymapper_form_button_label", "") or "").strip(),
        "custom_icon": (wm.get("keymapper_form_pending_icon", "")
                        or _saved_custom_icon_op(wm)),
    }


def build_scratch_mirror(wm) -> str:
    """Read the primary + extra scratch KMIs (RNA access — only call OUTSIDE
    draw: from the mirror timer or operator context) into one string."""
    parts = []
    kmi = get_scratch_kmi()
    if kmi is not None:
        parts.append(f"{kmi.type}|{kmi.value}|{kmi.shift}{kmi.ctrl}"
                     f"{kmi.alt}{kmi.oskey}|{kmi.key_modifier}")
    for slot in range(1, 17):
        ex = _peek_extra_scratch_kmi(slot)  # read-only: no create, no writes
        if ex is not None and ex.type and ex.type != "NONE":
            parts.append(f"x{slot}:{ex.type}|{ex.value}|{ex.shift}{ex.ctrl}"
                         f"{ex.alt}{ex.oskey}|"
                         f"{wm.get(f'keymapper_kmi_any_{slot}', False)}")
    return "\x00".join(parts)


def _scratch_mirror_tick():
    """Repeating timer (form-open only): mirror the scratch KMI state into a
    plain WM key so draw code never reads KeyMapItem RNA — reading KMI fields
    during draw on the Preferences->Keymap page breaks the keymap editor's
    expand toggles (found by staged bisection, July 2026). Stops itself when
    the form closes."""
    try:
        wm = bpy.context.window_manager
    except Exception:
        return None
    if not wm.get("keymapper_form_active", False):
        return None  # form closed - stop the timer
    try:
        wm["keymapper_scratch_mirror_pending"] = ""  # reserved
        val = build_scratch_mirror(wm)
        if wm.get("keymapper_scratch_mirror", None) != val:
            wm["keymapper_scratch_mirror"] = val
            _redraw(bpy.context)
    except Exception:
        pass
    return 0.2


def start_scratch_mirror():
    """Start (or restart) the scratch-mirror timer. Call on form open."""
    try:
        if not bpy.app.timers.is_registered(_scratch_mirror_tick):
            bpy.app.timers.register(_scratch_mirror_tick, first_interval=0.05)
    except Exception:
        _scratch_mirror_tick()


def _form_preview_sig(wm) -> str:
    """Cheap signature of everything the conflict preview depends on."""
    parts = [
        str(_dialog_frozen_ops if _dialog_frozen_ops is not None
            else wm.get(WM_OP_IDS, "")),
        str(wm.get("keymapper_extra_keybinds", "[]")),
        str(wm.get("keymapper_form_entry_id", "")),
        str(wm.get("keymapper_kmi_any_0", False)),
        str(wm.get("keymapper_form_use_keybind", True)),
        str(wm.get("keymapper_form_use_button", False)),
        str(wm.get("keymapper_form_button_conflicts", False)),
    ]
    # The scratch KMIs' state (primary + extras) comes from the MIRROR, not
    # live RNA reads (see _scratch_mirror_tick / build_scratch_mirror).
    parts.append(str(wm.get("keymapper_scratch_mirror", "")))
    for slot in range(17):
        if (_dialog_frozen_detect is not None
                and _dialog_frozen_detect[0] == slot):
            v = str(_dialog_frozen_detect[1])
        else:
            v = wm.get(f"keymapper_detect_ctx_{slot}", "")
        if v and v not in ("[]", "[]".replace(" ", "")):
            parts.append(f"d{slot}:{v}")
    try:
        from . import environment, persistence
        parts.append(str(environment.current_conflict_method()))
        parts.append(str(len(persistence.get_entries())))
    except Exception:
        pass
    return "\x00".join(parts)


_preview_cache = {"sig": None, "ext": None, "int": None}


def get_form_conflict_preview(wm) -> dict:
    """Run a read-only external conflict scan on the current form state.
    Cached by form-state signature so redraws don't rescan.
    Returns {'shortcut': [...], 'keybind': [...]} of ref dicts (possibly empty)."""
    sig = _form_preview_sig(wm)
    if _preview_cache["sig"] == sig and _preview_cache["ext"] is not None:
        return _preview_cache["ext"]
    entry = build_preview_entry_from_form(wm)
    if entry is None:
        result = {"shortcut": [], "keybind": []}
        _preview_cache.update(sig=sig, ext=result, int=None)
        return result
    try:
        from . import conflict_detector
        res = conflict_detector.scan_external_conflicts(entry)
        sc = res.get("shortcut_conflicts_external", [])
        kc = res.get("keybind_conflicts_external", [])
        # Also scan each extra keybind (mirrors update_entry_external_conflicts).
        for extra in entry.get("extra_keybinds", []):
            ex_entry = dict(entry)
            ex_entry["key"] = extra.get("key", "")
            ex_entry["event_type"] = extra.get("value", "PRESS")
            for f in ("shift", "ctrl", "alt", "oskey", "any"):
                ex_entry[f] = extra.get(f, False)
            ex_entry["key_modifier"] = extra.get("key_modifier", "")
            ex_entry["detect_contexts"] = extra.get("detect_contexts", [])
            ex_res = conflict_detector.scan_external_conflicts(ex_entry)
            seen_sc = {(r["keymap_name"], r["op_id"], r["key"]) for r in sc}
            for r in ex_res.get("shortcut_conflicts_external", []):
                if (r["keymap_name"], r["op_id"], r["key"]) not in seen_sc:
                    sc.append(r)
            seen_kc = {(r["keymap_name"], r["op_id"], r["key"]) for r in kc}
            for r in ex_res.get("keybind_conflicts_external", []):
                if (r["keymap_name"], r["op_id"], r["key"]) not in seen_kc:
                    kc.append(r)
    except Exception:
        return {"shortcut": [], "keybind": []}
    result = {"shortcut": sc, "keybind": kc}
    # int=None is essential: without it a signature change refreshed the
    # external lists but left the PREVIOUS internal-conflict list in the
    # cache, which the internal getter then served as current (a conflict
    # found at "O" survived adding Ctrl+Alt).
    _preview_cache.update(sig=sig, ext=result, int=None)
    return result


def get_form_internal_conflict_preview(wm) -> list:
    """Preview internal (entry-vs-entry) conflicts for the current form state,
    against all other saved entries. Read-only. Returns a list of
    {type, wins, with} dicts matching internal_conflicts shape."""
    sig = _form_preview_sig(wm)
    if _preview_cache["sig"] == sig and _preview_cache["int"] is not None:
        return _preview_cache["int"]
    entry = build_preview_entry_from_form(wm)
    if entry is None:
        return []
    edit_id = wm.get("keymapper_form_entry_id", "")
    entry["enabled"] = True
    out = []
    try:
        from . import conflict_detector, persistence
        for other in persistence.get_entries():
            if other.get("entry_id") == edit_id:
                continue  # don't conflict with the entry being edited
            ctype = conflict_detector.classify_conflict(entry, other)
            if not ctype:
                continue
            if not other.get("enabled", True) and ctype in (
                "duplicate", "key_conflict", "event_soft"):
                ctype = "op_overlap"
            out.append({"type": ctype, "wins": True,
                        "with": other.get("entry_id", "")})
    except Exception:
        return []
    if _preview_cache["sig"] == sig:
        _preview_cache["int"] = out
    return out


WM_OP_LABEL = "keymapper_picked_label"
WM_OP_MODE = "keymapper_picked_mode"
WM_BROWSE_ON = "keymapper_browse_open"

KEYMAP_CONTEXTS = [
    ("Object Mode", "3D View — Object Mode"),
    ("Mesh", "3D View — Mesh Edit"),
    ("Curve", "3D View — Curve Edit"),
    ("Armature", "3D View — Armature Edit"),
    ("Pose", "3D View — Pose Mode"),
    ("Sculpt", "3D View — Sculpt"),
    ("Vertex Paint", "3D View — Vertex Paint"),
    ("Weight Paint", "3D View — Weight Paint"),
    ("Image Paint", "3D View — Texture Paint"),
    ("Particle", "3D View — Particle Edit"),
    ("Grease Pencil", "3D View — Grease Pencil"),
    ("Curves", "3D View — Curves Sculpt"),
    ("Lattice", "3D View — Lattice Edit"),
    ("Font", "3D View — Text Edit"),
    ("Metaball", "3D View — Metaball Edit"),
    ("Graph Editor", "Graph Editor"),
    ("Dopesheet", "Dopesheet"),
    ("NLA Editor", "NLA Editor"),
    ("Node Editor", "Node Editor"),
    ("UV Editor", "UV Editor"),
    ("Image", "Image Editor"),
    ("Outliner", "Outliner"),
    ("Video Sequence Editor", "Video Sequencer"),
    ("Text", "Text Editor"),
    ("Window", "Window (Global)"),
    ("Screen", "Screen (Global)"),
    ("3D View", "3D View (Generic)"),
]


def _host():
    try:
        from . import HOST_APP

        return HOST_APP
    except ImportError:
        return "blender"


def _redraw(context):
    # Tag areas across every window (not just the active one) so Blender's
    # keymap editor in the Preferences window also refreshes its checkboxes
    # when Keymapper toggles a KMI's active state.
    wm = getattr(context, "window_manager", None)
    if wm:
        for win in wm.windows:
            scr = getattr(win, "screen", None)
            if scr:
                for area in scr.areas:
                    area.tag_redraw()
        return
    if context.screen:
        for area in context.screen.areas:
            area.tag_redraw()


def _wm_get(wm, key, default=""):
    return wm.get(key, default)


def _wm_set(wm, key, value):
    wm[key] = value


# ---------------------------------------------------------------------------
# Unsaved tracker
# ---------------------------------------------------------------------------

_has_unsaved = False


def mark_unsaved():
    global _has_unsaved
    _has_unsaved = True


def mark_saved():
    global _has_unsaved
    _has_unsaved = False


def has_unsaved_changes():
    return _has_unsaved


def _run_reorder_scan():
    """Fast path for MOVE operations: a pure reorder can't change which
    pairs conflict — only the order-derived "wins" flags and (when identical
    twins exist) inert-duplicate canonicality. No pairwise classification."""
    try:
        from . import conflict_detector

        entries = persistence.get_entries()
        conflict_detector.reorder_update_conflicts(entries)
        if conflict_detector.has_potential_duplicates(entries):
            from . import keymap_manager
            keymap_manager.reconcile_inert_duplicates()
    except Exception as e:
        print(f"[Keymapper] Reorder scan error: {e}")


def _run_conflict_scan(entry: dict = None):
    """Run internal conflict detection. External scan is done explicitly per-entry only."""
    try:
        from . import conflict_detector

        entries = persistence.get_entries()
        conflict_detector.update_entry_conflicts(entries)
        # Keep inert-duplicate KMI state in sync (promote/demote as identity
        # relationships change after this add/edit/delete/duplicate).
        from . import keymap_manager
        keymap_manager.reconcile_inert_duplicates()
    except Exception as e:
        print(f"[Keymapper] Conflict scan error: {e}")


# ---------------------------------------------------------------------------
# Scratch KMI — native key-binding widget
# ---------------------------------------------------------------------------

_SCRATCH_KM_NAME = "Keymapper Scratch"
_scratch_kmi = None
_scratch_extra_kmis: list = []  # extra scratch KMIs for additional keybind slots


def _ensure_scratch_kmi():
    global _scratch_kmi
    try:
        kc = bpy.context.window_manager.keyconfigs.addon
        km = kc.keymaps.get(_SCRATCH_KM_NAME)
        if km is None:
            km = kc.keymaps.new(
                name=_SCRATCH_KM_NAME,
                space_type="EMPTY",
                region_type="WINDOW",
            )
        if not km.keymap_items:
            kmi = km.keymap_items.new("none", "NONE", "PRESS")
        else:
            kmi = km.keymap_items[0]
        _scratch_kmi = kmi
    except Exception as e:
        print(f"[Keymapper] Could not create scratch KMI: {e}")
        _scratch_kmi = None


def _ensure_extra_scratch_kmi(slot: int):
    """Ensure extra scratch KMI at given slot index exists. Returns the KMI."""
    global _scratch_extra_kmis
    try:
        kc = bpy.context.window_manager.keyconfigs.addon
        km = kc.keymaps.get(_SCRATCH_KM_NAME)
        if km is None:
            return None
        # Slots 0 = primary, slots 1+ = extras stored at km.keymap_items[slot]
        needed_count = slot + 1  # total items needed (index 0 = primary)
        while len(km.keymap_items) < needed_count:
            km.keymap_items.new("none", "NONE", "PRESS")
        kmi = km.keymap_items[slot]
        kmi.active = False  # keep inactive while editing
        return kmi
    except Exception as e:
        print(f"[Keymapper] Could not create extra scratch KMI slot {slot}: {e}")
        return None


def _peek_extra_scratch_kmi(slot: int):
    """Read-only lookup of an extra scratch KMI: returns the existing item or
    None. NEVER creates and NEVER writes (unlike _ensure_extra_scratch_kmi,
    which creates missing slots and re-writes kmi.active on EVERY call — those
    writes, run per draw/tick, were what kept collapsing the keymap editor's
    expand toggles on the Preferences->Keymap page)."""
    try:
        kc = bpy.context.window_manager.keyconfigs.addon
        km = kc.keymaps.get(_SCRATCH_KM_NAME)
        if km is None or len(km.keymap_items) <= slot:
            return None
        return km.keymap_items[slot]
    except Exception:
        return None


def get_extra_scratch_kmi(slot: int):
    """Get extra scratch KMI at given 1-based slot (slot 1 = first extra)."""
    return _ensure_extra_scratch_kmi(slot)


def _clear_extra_scratch_kmis():
    """Remove all extra scratch KMIs (slots 1+), keeping only the primary."""
    try:
        kc = bpy.context.window_manager.keyconfigs.addon
        km = kc.keymaps.get(_SCRATCH_KM_NAME)
        if km and len(km.keymap_items) > 1:
            # Remove from end to avoid index shifting issues
            while len(km.keymap_items) > 1:
                km.keymap_items.remove(km.keymap_items[-1])
    except Exception:
        pass


def _remove_scratch_kmi():
    global _scratch_kmi
    try:
        kc = bpy.context.window_manager.keyconfigs.addon
        km = kc.keymaps.get(_SCRATCH_KM_NAME)
        if km:
            kc.keymaps.remove(km)
    except Exception:
        pass
    _scratch_kmi = None


def get_scratch_kmi():
    """Return the primary scratch KMI, always re-fetching from keymap to avoid stale refs."""
    global _scratch_kmi
    try:
        kc = bpy.context.window_manager.keyconfigs.addon
        km = kc.keymaps.get(_SCRATCH_KM_NAME)
        if km and km.keymap_items:
            _scratch_kmi = km.keymap_items[0]
            return _scratch_kmi
    except Exception:
        pass
    _ensure_scratch_kmi()
    return _scratch_kmi


def _scratch_kmi_set_active(active: bool):
    """Enable or disable the scratch KMI to prevent it blocking real shortcuts."""
    kmi = get_scratch_kmi()
    if kmi is not None:
        try:
            kmi.active = active
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Full per-operator properties (Task 2)
#
# Reuses Blender's native KMI property editor (layout.template_keymap_item_
# properties) by backing each edited operator with a live, inactive KMI in a
# dedicated scratch keymap. The live KMI exposes the FULL operator property set
# (the same one Blender's keymap editor shows). We serialise the set values to
# a JSON-safe dict (props_data) and restore them on activation.
# ---------------------------------------------------------------------------

_PROPS_KM_NAME = "Keymapper Props Scratch"
_props_kmis: dict = {}  # slot -> live kmi backing that operator's full props
_props_kmi_ids: dict = {}  # slot -> op idname currently backing that slot


def _props_scratch_km():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return None
    km = kc.keymaps.get(_PROPS_KM_NAME)
    if km is None:
        km = kc.keymaps.new(
            name=_PROPS_KM_NAME, space_type="EMPTY", region_type="WINDOW"
        )
    return km


def _kmi_alive(kmi) -> bool:
    if kmi is None:
        return False
    try:
        _ = kmi.idname
        return True
    except Exception:
        return False


def serialize_kmi_props(props, exclude=None) -> dict:
    """Return a JSON-safe {name: value} dict of the explicitly-set properties.

    Arrays become lists, enum-flag sets become lists. Pointer/collection props
    are skipped (operator KMI props effectively never use them). Names in
    `exclude` are skipped (those are managed by a curated picker)."""
    out = {}
    exclude = exclude or set()
    try:
        rna = props.bl_rna
    except Exception:
        return out
    for p in rna.properties:
        name = p.identifier
        if name == "rna_type" or name in exclude:
            continue
        try:
            if p.is_readonly:
                continue
            if not props.is_property_set(name):
                continue
        except Exception:
            continue
        try:
            if p.type in ("POINTER", "COLLECTION"):
                continue
            val = getattr(props, name)
            if p.type == "ENUM" and getattr(p, "is_enum_flag", False):
                val = list(val)
            elif getattr(p, "is_array", False):
                val = list(val)
            out[name] = val
        except Exception:
            continue
    return out


def apply_kmi_props(props, data: dict):
    """Apply a props_data dict (from serialize_kmi_props) onto kmi.properties."""
    if not data:
        return
    try:
        rna = props.bl_rna
    except Exception:
        return
    for name, value in data.items():
        p = rna.properties.get(name)
        if p is None:
            continue
        try:
            if p.type == "ENUM" and getattr(p, "is_enum_flag", False):
                setattr(props, name, set(value))
            else:
                setattr(props, name, value)
        except Exception as ex:
            print(f"[Keymapper] Could not set prop '{name}': {ex}")


def apply_legacy_props(props, legacy: dict):
    """Seed kmi.properties from the entry's legacy string `props` (curated picker
    values), coercing strings to the RNA property's real type. Display-only —
    these are not captured back into props_data."""
    if not legacy:
        return
    try:
        rna = props.bl_rna
    except Exception:
        return
    for name, sval in legacy.items():
        p = rna.properties.get(name)
        if p is None:
            continue
        try:
            t = p.type
            if t == "BOOLEAN":
                if getattr(p, "is_array", False):
                    continue
                setattr(props, name, str(sval).strip().lower() in ("true", "1", "yes", "on"))
            elif t == "INT":
                setattr(props, name, int(float(sval)))
            elif t == "FLOAT":
                setattr(props, name, float(sval))
            elif t == "ENUM" and getattr(p, "is_enum_flag", False):
                continue
            else:  # STRING / ENUM(id) / others
                setattr(props, name, sval)
        except Exception:
            continue


def get_props_kmi(slot: int, op_idname: str, seed_data=None, seed_legacy=None):
    """Return a live inactive KMI for the operator at `slot`, creating it if the
    slot is empty or its operator changed. Seeds from the entry's legacy string
    props (display) and `seed_data` (typed props_data) on creation."""
    km = _props_scratch_km()
    if km is None:
        return None
    kmi = _props_kmis.get(slot)
    if _kmi_alive(kmi) and _props_kmi_ids.get(slot) == op_idname:
        return kmi
    # (Re)create
    if _kmi_alive(kmi):
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    try:
        kmi = km.keymap_items.new(op_idname, "NONE", "PRESS")
        kmi.active = False
    except Exception as e:
        print(f"[Keymapper] Could not back operator '{op_idname}' for props: {e}")
        _props_kmis[slot] = None
        _props_kmi_ids[slot] = op_idname
        return None
    if seed_legacy:
        apply_legacy_props(kmi.properties, seed_legacy)
    if seed_data:
        apply_kmi_props(kmi.properties, seed_data)
    _props_kmis[slot] = kmi
    _props_kmi_ids[slot] = op_idname
    return kmi


def peek_props_kmi(slot: int, op_idname: str):
    """Return the existing backing KMI for slot only if it matches op_idname and
    is alive; never creates one (used at save time to preserve unedited props)."""
    kmi = _props_kmis.get(slot)
    if _kmi_alive(kmi) and _props_kmi_ids.get(slot) == op_idname:
        return kmi
    return None


def clear_props_kmis():
    """Remove the props scratch keymap and reset tracking (called on form open/close)."""
    global _props_kmis, _props_kmi_ids
    try:
        kc = bpy.context.window_manager.keyconfigs.addon
        km = kc.keymaps.get(_PROPS_KM_NAME) if kc else None
        if km:
            kc.keymaps.remove(km)
    except Exception:
        pass
    _props_kmis = {}
    _props_kmi_ids = {}


def reset_scratch_kmi(
    key="NONE",
    value="PRESS",
    shift=False,
    ctrl=False,
    alt=False,
    oskey=False,
    any=False,
    key_modifier="NONE",
    repeat=False,
):
    kmi = get_scratch_kmi()
    if kmi is None:
        return
    try:
        # Hard reset to neutral first to prevent bleed-through from previous entry
        kmi.map_type = "KEYBOARD"
        kmi.type = "NONE"
        kmi.value = "PRESS"
        kmi.shift = 0
        kmi.ctrl = 0
        kmi.alt = 0
        kmi.oskey = 0
        try:
            kmi.key_modifier = "NONE"
        except Exception:
            pass
        # Apply new values — set map_type first, then type, then modifiers
        _mouse_keys = {
            "LEFTMOUSE",
            "RIGHTMOUSE",
            "MIDDLEMOUSE",
            "BUTTON4MOUSE",
            "BUTTON5MOUSE",
            "BUTTON6MOUSE",
            "BUTTON7MOUSE",
            "MOUSEMOVE",
            "TRACKPADPAN",
            "TRACKPADZOOM",
            "MOUSEROTATE",
            "WHEELUPMOUSE",
            "WHEELDOWNMOUSE",
            "WHEELINMOUSE",
            "WHEELOUTMOUSE",
        }
        target_key = key if key else "NONE"
        if target_key in _mouse_keys:
            kmi.map_type = "MOUSE"
        elif "NDOF" in target_key:
            kmi.map_type = "NDOF"
        elif target_key.startswith("EVT_TWEAK"):
            kmi.map_type = "TWEAK"
        elif target_key.startswith("TIMER"):
            kmi.map_type = "TIMER"
        else:
            kmi.map_type = "KEYBOARD"
        kmi.type = target_key
        kmi.value = value
        kmi.shift = 1 if shift else 0
        kmi.ctrl = 1 if ctrl else 0
        kmi.alt = 1 if alt else 0
        kmi.oskey = 1 if oskey else 0
        try:
            kmi.key_modifier = key_modifier if key_modifier else "NONE"
        except Exception:
            pass
        try:
            kmi.repeat = bool(repeat)
        except Exception:
            pass
        # Store any in WM property — kmi.any fights with modifiers internally
        try:
            bpy.context.window_manager["keymapper_kmi_any_0"] = bool(any)
        except Exception:
            pass
    except Exception as e:
        print(f"[Keymapper] reset_scratch_kmi error: {e}")


# ---------------------------------------------------------------------------
# Form state helpers
# ---------------------------------------------------------------------------


def _init_form(wm, entry=None):
    """Initialise WM scratch for the inline form.

    Also clears the quick-add popup's session token: any new form session
    (editing another entry, adding from the panel) means the popup — which
    Blender will not let us close — is no longer editing what it was opened
    for, so it must stop rendering the form.
    """
    wm["keymapper_quickadd_session"] = ""
    wm["keymapper_quickadd_folder_id"] = ""
    wm["keymapper_quickadd_folder_set"] = False
    wm["keymapper_form_enabled"] = bool(entry.get("enabled", True)) if entry \
        else True
    if entry:
        _wm_set(wm, WM_CONTEXTS, entry.get("keymap_contexts", "Object Mode"))
        # Restore operators — handle both old comma-sep and new JSON format
        import json as _json

        raw_ops = entry.get("operator_ids", "")
        try:
            restored = _json.loads(raw_ops)
            if not isinstance(restored, list):
                raise ValueError
        except Exception:
            # Old format: comma-separated string
            restored = [
                {"id": oid.strip(), "props": {}}
                for oid in raw_ops.split(",")
                if oid.strip()
            ]
        _set_sel_ops(wm, restored)
        first_id = restored[0]["id"] if restored else ""
        _wm_set(wm, WM_OP_ID, first_id)
        _wm_set(wm, WM_OP_LABEL, entry.get("display_name", ""))
        _wm_set(
            wm, WM_OP_MODE, "FRIENDLY" if entry.get("is_friendly", True) else "PURE"
        )
        # Always leave label empty here — KEYMAPPER_OT_EditEntry sets it from custom_label after calling _init_form
        wm.keymapper_form_label = ""
    else:
        _wm_set(wm, WM_CONTEXTS, "Object Mode")
        _wm_set(wm, WM_OP_ID, "")
        _wm_set(wm, WM_OP_LABEL, "")
        _wm_set(wm, WM_OP_MODE, "FRIENDLY")
        wm.keymapper_form_label = ""
    from .database.categories import CATEGORIES as _CATS

    _wm_set(wm, WM_CATEGORY, _CATS[0]["id"] if _CATS else "object")
    _wm_set(wm, WM_BROWSE_ON, False)
    _set_sel_ops(wm, [])
    wm.keymapper_search_prop = ""
    clear_props_kmis()
    # Seed the scratch-KMI mirror synchronously (we're in operator context,
    # not draw) and start the mirror timer for live preview updates.
    try:
        wm["keymapper_scratch_mirror"] = build_scratch_mirror(wm)
    except Exception:
        wm["keymapper_scratch_mirror"] = ""
    start_scratch_mirror()
    # Entry Buttons form scratch (loaded from the entry on edit; defaults for new)
    if entry:
        wm["keymapper_form_use_keybind"] = bool(entry.get("use_keybind", True))
        wm["keymapper_form_use_button"] = bool(entry.get("use_button", False))
        set_button_locations(wm, entry.get("button_locations", []) or [])
        wm["keymapper_form_button_show_label"] = bool(
            entry.get("button_show_label", True))
        wm["keymapper_form_button_show_icon"] = bool(
            entry.get("button_show_icon", True))
        wm["keymapper_form_button_conflicts"] = bool(
            entry.get("button_conflict_detection", False))
        wm.keymapper_form_button_label = entry.get("button_label", "")
    else:
        wm["keymapper_form_use_keybind"] = True
        wm["keymapper_form_use_button"] = False
        set_button_locations(wm, [])
        wm["keymapper_form_button_show_label"] = True
        wm["keymapper_form_button_show_icon"] = True
        wm["keymapper_form_button_conflicts"] = False
        wm.keymapper_form_button_label = ""


# ---------------------------------------------------------------------------
# Save Preferences
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_SavePreferences(Operator):
    bl_idname = "keymapper.save_preferences"
    bl_label = "Save Preferences"
    bl_description = "Save Keymapper entries to user preferences"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from . import persistence as pers

        pers.save()
        try:
            bpy.ops.wm.save_userpref()
        except Exception:
            pass
        mark_saved()
        self.report({"INFO"}, "Keymapper: Preferences saved.")
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Open inline form (replaces Add Entry popup)
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_OpenInlineForm(Operator):
    bl_idname = "keymapper.open_inline_form"
    bl_label = "Add Shortcut"
    bl_description = "Add a new shortcut entry"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        # Resolve the folder the panel is DISPLAYING as active BEFORE any form
        # state is set (the resolver returns Unsorted once form_active is on).
        # An unset raw selection falls back to the first folder, which the
        # panel shows highlighted (e.g. right after an import) — the new entry
        # must land there, not silently in Unsorted.
        from .panel import _resolve_active_folder
        _display_fid = _resolve_active_folder(context)
        # Close all open subcategory dropdowns (including hashed keys for long names)
        for key in list(wm.keys()):
            if key.startswith("keymapper_subcat_") or key.startswith("keymapper_s_"):
                del wm[key]
        # Destroy and recreate scratch KMI to guarantee a clean slate
        _remove_scratch_kmi()
        _ensure_scratch_kmi()
        _init_form(wm)
        wm.keymapper_ctx_searches.clear()
        wm.keymapper_menu_searches.clear()
        wm.keymapper_prop_texts.clear()
        wm.keymapper_context_path_props.clear()
        wm.keymapper_int_props.clear()
        wm.keymapper_float_props.clear()
        wm["keymapper_form_active"] = True
        wm["keymapper_form_entry_id"] = ""
        wm["keymapper_extra_keybinds"] = "[]"
        clear_all_detect_contexts(wm)
        wm["keymapper_subcat_shortcut_section"] = True  # open by default
        for _i in range(8):
            wm[f"keymapper_kmi_any_{_i}"] = False
        _clear_extra_scratch_kmis()
        _scratch_kmi_set_active(True)
        entries = persistence.get_entries()
        selected_idx = wm.keymapper.selected_index
        # Use the SAME folder resolution as the panel display: an unset raw
        # selection falls back to the first folder (which the panel shows as
        # active, e.g. right after an import) — the new entry must land in the
        # folder the user actually SEES as selected, not silently in Unsorted.
        sel_fid = _display_fid

        # Inherit folder from selected entry, or from selected folder if expanded
        if entries and 0 <= selected_idx < len(entries):
            new_folder = entries[selected_idx].get("folder_id", "")
            insert_after = selected_idx
            # Preview card + form render right below this card; deselect it so
            # its highlight goes away while the new entry is being built.
            wm["keymapper_form_after_entry"] = entries[selected_idx].get(
                "entry_id", "")
            wm.keymapper.selected_index = -1
        elif sel_fid:
            folder = persistence.get_folder_by_id(sel_fid)
            if folder:
                # Always expand the folder so the form is visible
                if folder.get("collapsed", False):
                    persistence.update_folder(sel_fid, {"collapsed": False})
                new_folder = sel_fid
                folder_entries = [
                    i
                    for i, e in enumerate(entries)
                    if e.get("folder_id", "") == sel_fid
                ]
                insert_after = folder_entries[-1] if folder_entries else -1
                wm["keymapper_form_after_entry"] = (
                    entries[folder_entries[-1]].get("entry_id", "")
                    if folder_entries else "")
            else:
                wm.keymapper_selected_folder_id = ""
                wm.keymapper_renaming_folder_id = ""
                new_folder = ""
                insert_after = -1
                wm["keymapper_form_after_entry"] = ""
        else:
            # Nothing selected — go unsorted, form appears at bottom of unsorted
            new_folder = ""
            insert_after = -1
            wm["keymapper_form_after_entry"] = ""

        wm["keymapper_form_insert_after"] = insert_after
        wm["keymapper_new_entry_folder"] = new_folder
        wm["keymapper_form_goto_unsorted"] = insert_after == -1 and not new_folder
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Edit Entry — opens inline form pre-filled
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_EditEntry(Operator):
    bl_idname = "keymapper.edit_entry"
    bl_label = "Edit Entry"
    bl_description = "Edit this shortcut entry"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        entry = persistence.get_entry_by_id(self.entry_id)
        if not entry:
            return {"CANCELLED"}
        reset_scratch_kmi(
            key=entry.get("key", "NONE"),
            value=entry.get("event_type", "PRESS"),
            shift=entry.get("shift", False),
            ctrl=entry.get("ctrl", False),
            alt=entry.get("alt", False),
            oskey=entry.get("oskey", False),
            any=entry.get("any", False),
            key_modifier=entry.get("key_modifier", "NONE") or "NONE",
            repeat=entry.get("repeat", False),
        )
        _init_form(wm, entry)
        # Pre-fill custom label if entry has one
        wm.keymapper_form_label = entry.get("custom_label", "")
        # Restore operators in new format
        import json as _j

        raw = entry.get("operator_ids", "")
        try:
            restored = _j.loads(raw)
            if not isinstance(restored, list):
                raise ValueError
        except Exception:
            restored = [
                {"id": oid.strip(), "props": {}}
                for oid in raw.split(",")
                if oid.strip()
            ]
        _set_sel_ops(wm, restored)
        wm.keymapper_prop_texts.clear()
        wm.keymapper_context_path_props.clear()
        wm.keymapper_int_props.clear()
        wm.keymapper_float_props.clear()
        wm["keymapper_form_active"] = True
        wm["keymapper_form_entry_id"] = self.entry_id
        wm["keymapper_form_icon_snapshot"] = entry.get("custom_icon", "")
        wm["keymapper_form_icon_snapshot_set"] = True
        wm["keymapper_subcat_shortcut_section"] = True  # open by default
        for _i in range(8):
            wm[f"keymapper_kmi_any_{_i}"] = False
        wm["keymapper_kmi_any_0"] = bool(entry.get("any", False))
        _clear_extra_scratch_kmis()
        clear_all_detect_contexts(wm)
        set_detect_contexts(wm, 0, entry.get("detect_contexts", []))

        # Restore extra keybinds from saved entry into extra scratch KMIs
        import json as _j2

        extra_keybinds = entry.get("extra_keybinds", [])
        extra_slot_list = []
        for idx, ex in enumerate(extra_keybinds):
            slot = idx + 1
            set_detect_contexts(wm, slot, ex.get("detect_contexts", []))
            ex_kmi = _ensure_extra_scratch_kmi(slot)
            if ex_kmi:
                try:
                    # Reset to clean state first
                    # Reset to clean state first
                    ex_kmi.shift = 0
                    ex_kmi.ctrl = 0
                    ex_kmi.alt = 0
                    ex_kmi.oskey = 0
                    ex_kmi.any = False
                    ex_kmi.value = "PRESS"
                    ex_kmi.type = "NONE"
                    # Restore saved values — do NOT set map_type (resets modifiers)
                    ex_kmi.value = ex.get("value", "PRESS")
                    ex_kmi.type = ex.get("key", "NONE") or "NONE"
                    ex_kmi.shift = 1 if ex.get("shift", False) else 0
                    ex_kmi.ctrl = 1 if ex.get("ctrl", False) else 0
                    ex_kmi.alt = 1 if ex.get("alt", False) else 0
                    ex_kmi.oskey = 1 if ex.get("oskey", False) else 0
                    km_val = ex.get("key_modifier", "NONE") or "NONE"
                    try:
                        ex_kmi.key_modifier = km_val
                    except Exception:
                        pass
                    # Store any in WM property per slot
                    try:
                        bpy.context.window_manager[f"keymapper_kmi_any_{slot}"] = bool(
                            ex.get("any", False)
                        )
                    except Exception:
                        pass
                except Exception as e:
                    print(
                        f"[Keymapper] Could not restore extra keybind slot {slot}: {e}"
                    )
                extra_slot_list.append({"slot": slot})
        wm["keymapper_extra_keybinds"] = _j2.dumps(extra_slot_list)

        _scratch_kmi_set_active(True)

        # Re-scan external conflicts so the form shows fresh data
        try:
            from . import conflict_detector

            conflict_detector.update_entry_external_conflicts(entry)
        except Exception:
            pass

        # Select this entry in the main list
        entries = persistence.get_entries()
        for i, e in enumerate(entries):
            if e.get("entry_id") == self.entry_id:
                wm.keymapper.selected_index = i
                break

        # Close all subcats first, then open ones containing selected operators
        for key in list(wm.keys()):
            if key.startswith("keymapper_subcat_") or key.startswith("keymapper_s_"):
                del wm[key]
        # Open subcategories that have selected operators
        from .database.categories import CATEGORIES

        op_ids_set = {o["id"] for o in restored}
        for cat in CATEGORIES:
            for sub in cat.get("subcategories", []):
                if any(op in op_ids_set for op in sub.get("operators", [])):
                    key = f"keymapper_subcat_{cat['id']}_{sub['label']}".replace(
                        " ", "_"
                    )
                    if len(key) <= 63:
                        wm[key] = True

        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Form Confirm (OK button)
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_QuickAddSetFolder(Operator):
    """Choose which folder the new entry is added to"""

    bl_idname = "keymapper.quick_add_set_folder"
    bl_label = "Folder"
    bl_options = {"INTERNAL"}

    folder_id: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        fid = self.folder_id or ""
        entries = persistence.get_entries()
        if fid:
            folder = persistence.get_folder_by_id(fid)
            if folder and folder.get("collapsed", False):
                persistence.update_folder(fid, {"collapsed": False})
            idxs = [i for i, e in enumerate(entries)
                    if e.get("folder_id", "") == fid]
            insert_after = idxs[-1] if idxs else -1
            wm["keymapper_form_after_entry"] = (
                entries[idxs[-1]].get("entry_id", "") if idxs else "")
        else:
            insert_after = -1
            wm["keymapper_form_after_entry"] = ""
        wm["keymapper_new_entry_folder"] = fid
        # Authoritative copy: the shared key is also written by the panel's
        # own form-placement logic, so an explicit choice made in the popup
        # could be silently replaced before the entry was saved.
        wm["keymapper_quickadd_folder_id"] = fid
        wm["keymapper_quickadd_folder_set"] = True
        # Follow the choice in the panel too. _resolve_active_folder falls
        # back to the FIRST folder when nothing valid is selected, so without
        # this the in-progress entry kept showing under that folder while the
        # save went to the chosen one.
        try:
            wm.keymapper_selected_folder_id = fid
        except Exception:
            pass
        wm["keymapper_form_insert_after"] = insert_after
        wm["keymapper_form_goto_unsorted"] = (insert_after == -1 and not fid)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_MT_QuickAddFolder(bpy.types.Menu):
    """Folder picker for the right-click quick-add popup."""

    bl_idname = "KEYMAPPER_MT_QuickAddFolder"
    bl_label = "Folder"

    def draw(self, context):
        layout = self.layout
        # The loose-entries group is called "New Folder" everywhere else in
        # the UI (see panel.py folder tabs), so match it here.
        layout.operator(
            "keymapper.quick_add_set_folder", text="New Folder",
            icon="FILE_FOLDER",
        ).folder_id = ""
        folders = persistence.get_folders()
        if folders:
            layout.separator()
        for f in folders:
            op = layout.operator(
                "keymapper.quick_add_set_folder",
                text=f.get("label", "Folder"),
                icon=_safe_icon(f.get("icon", "FILE_FOLDER"), "FILE_FOLDER"),
            )
            op.folder_id = f.get("folder_id", "")


class KEYMAPPER_OT_OpenFullEditor(Operator):
    """Open the full Keymapper editor in the panel chosen in preferences"""

    bl_idname = "keymapper.open_full_editor"
    bl_label = "Open Full Editor"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from .preferences import get_prefs
        try:
            target = get_prefs(context).open_editor_target
        except Exception:
            target = "KEYMAP"

        if target == "NPANEL":
            # Open the Keymapper tab in a 3D View sidebar. The target is NOT
            # switched based on where the right-click happened; if this screen
            # has no 3D View there is simply nothing to open.
            area = None
            if getattr(context.area, "type", "") == "VIEW_3D":
                area = context.area
            else:
                for a in context.screen.areas:
                    if a.type == "VIEW_3D":
                        area = a
                        break
            if area is None:
                self.report({"WARNING"},
                            "Keymapper: no 3D Viewport in this screen to open "
                            "the sidebar in.")
                return {"CANCELLED"}
            try:
                area.spaces.active.show_region_ui = True
                for region in area.regions:
                    if region.type == "UI":
                        region.active_panel_category = "Keymapper"
                        break
                area.tag_redraw()
            except Exception as e:
                self.report({"WARNING"}, f"Keymapper: {e}")
                return {"CANCELLED"}
            return {"FINISHED"}

        if target == "ADDON_PREFS":
            try:
                bpy.ops.preferences.addon_show(module=__package__)
                return {"FINISHED"}
            except Exception:
                pass  # fall through to the Keymap page

        try:
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
        except Exception:
            pass
        try:
            context.preferences.active_section = "KEYMAP"
        except Exception:
            pass
        return {"FINISHED"}


class KEYMAPPER_OT_FormConfirm(Operator):
    bl_idname = "keymapper.form_confirm"
    bl_label = "Confirm"
    bl_description = "Confirm shortcut entry"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context):
        wm = context.window_manager
        import json as _json

        sel_ops = _get_sel_ops(wm)
        from .preferences import get_naming_mode

        op_mode = get_naming_mode()
        ctx_str = "Object Mode"
        edit_id = wm.get("keymapper_form_entry_id", "")

        typed = wm.keymapper_form_label.strip()

        # Always generate raw display_name regardless of naming mode
        if sel_ops:

            first_op = sel_ops[0]
            first = first_op["id"]

            _AUTO_NAMED_OPS = {"wm.call_menu_pie", "wm.call_menu", "wm.call_panel"}
            _SHORT_PREFIX = {
                "wm.call_menu_pie": "CPM",
                "wm.call_menu": "CM",
                "wm.call_panel": "CP",
            }
            _FULL_NAME = {
                "wm.call_menu_pie": "Call Pie Menu",
                "wm.call_menu": "Call Menu",
                "wm.call_panel": "Call Panel",
            }

            if first in _AUTO_NAMED_OPS:
                props = first_op.get("props", {})
                menu_id = props.get("name", "")
                op_context = first_op.get("context", "")
                if menu_id:
                    prefix = _SHORT_PREFIX[first]
                    label = f"{prefix}: {menu_id}"
                else:
                    label = _FULL_NAME[first]
                if op_context:
                    label += f" ({op_context})"
            else:
                label = first
        else:
            label = ""

        # custom_label: only set if user actually typed something
        custom_label = typed if typed else ""

        # Sync free-text and numeric prop fields into sel_ops props
        from .database.op_properties import get_op_props as _get_op_props

        for i, op_inst in enumerate(sel_ops):
            oid = op_inst.get("id", "")
            op_props = _get_op_props(oid)
            prop_keys = sorted(op_props.keys())
            for j, prop_name in enumerate(prop_keys):
                meta = op_props[prop_name]
                vf = meta.get("values_from") or ""
                # menus/panels/tools are saved immediately via form_set_op_prop — skip them
                # context_path is stored in keymapper_context_path_props — handle below
                if vf and vf != "context_path":
                    continue
                if meta.get("type") == "BOOL":
                    continue
                if meta.get("type") == "ENUM":
                    continue
                txt_idx = i * 20 + j
                prop_type = meta.get("type", "STRING")
                if prop_type == "INT":
                    coll = wm.keymapper_int_props
                    if txt_idx < len(coll):
                        op_inst.setdefault("props", {})[prop_name] = str(
                            coll[txt_idx].int_value
                        )
                elif prop_type == "FLOAT":
                    coll = wm.keymapper_float_props
                    if txt_idx < len(coll):
                        op_inst.setdefault("props", {})[prop_name] = str(
                            coll[txt_idx].float_value
                        )
                else:
                    # Check context_path_props first (has native search), then plain prop_texts
                    if meta.get("values_from") == "context_path":
                        coll = wm.keymapper_context_path_props
                        if txt_idx < len(coll):
                            val = coll[txt_idx].value.strip()
                            if val:
                                op_inst.setdefault("props", {})[prop_name] = val
                    elif txt_idx < len(wm.keymapper_prop_texts):
                        val = wm.keymapper_prop_texts[txt_idx].value.strip()
                        if val:
                            op_inst.setdefault("props", {})[prop_name] = val

        # Validate we have at least a label
        if not label and not custom_label:
            self.report({"WARNING"}, "Keymapper: Please add at least one operator.")
            return {"CANCELLED"}

        # Validate call_menu/pie/panel require both a menu and a context
        _MENU_OPS = {"wm.call_menu_pie", "wm.call_menu", "wm.call_panel"}
        _MENU_LABELS = {
            "wm.call_menu_pie": "Pie Menu",
            "wm.call_menu": "Menu",
            "wm.call_panel": "Panel",
        }
        for op_inst in sel_ops:
            oid = op_inst.get("id", "")
            if oid in _MENU_OPS:
                if not op_inst.get("props", {}).get("name", ""):
                    self.report(
                        {"WARNING"}, f"Keymapper: Please select a {_MENU_LABELS[oid]}."
                    )
                    return {"CANCELLED"}

        _use_keybind = bool(wm.get("keymapper_form_use_keybind", True))
        _use_button = bool(wm.get("keymapper_form_use_button", False))

        kmi = get_scratch_kmi()
        if _use_keybind and (kmi is None or kmi.type == "NONE"):
            self.report({"WARNING"}, "Keymapper: Please set a key.")
            return {"CANCELLED"}

        # Validate call_menu_pie / call_menu / call_panel require both menu and context
        _MENU_OPS = {"wm.call_menu_pie", "wm.call_menu", "wm.call_panel"}
        _MENU_LABEL = {
            "wm.call_menu_pie": "Pie Menu",
            "wm.call_menu": "Menu",
            "wm.call_panel": "Panel",
        }
        for op_inst in sel_ops:
            op_id_check = op_inst.get("id", "")
            if op_id_check in _MENU_OPS:
                props = op_inst.get("props", {})
                menu_id = props.get("name", "")
                if not menu_id:
                    self.report(
                        {"WARNING"},
                        f"Keymapper: Please select a {_MENU_LABEL[op_id_check]}.",
                    )
                    return {"CANCELLED"}

        key_shift = bool(kmi and kmi.shift == 1)
        key_ctrl = bool(kmi and kmi.ctrl == 1)
        key_alt = bool(kmi and kmi.alt == 1)
        key_oskey = bool(kmi and kmi.oskey == 1)

        # Capture full per-operator properties (Task 2) from any live backing
        # KMI. Picker-managed props (stored in legacy `props`) are excluded so
        # they aren't double-saved. If the editor wasn't opened for an op, its
        # existing props_data (loaded from the entry) is preserved untouched.
        from .database.op_properties import get_picker_prop_names as _gppn

        for i, op_inst in enumerate(sel_ops):
            oid = op_inst.get("id", "")
            pk = peek_props_kmi(i, oid)
            if pk is None:
                continue
            _excl = _gppn(oid)
            data = serialize_kmi_props(pk.properties, exclude=_excl)
            if data:
                op_inst["props_data"] = data
            else:
                op_inst.pop("props_data", None)
            # A property the user CLEARED must also leave the legacy `props`
            # string mirror — activation applies that mirror too
            # (_set_legacy_props), so leaving it there would silently put the
            # value back. Picker-managed props live in `props` by design and
            # are never drawn in the editor, so they're left alone.
            _legacy = op_inst.get("props")
            if isinstance(_legacy, dict):
                for _n in [k for k in _legacy if k not in _excl]:
                    try:
                        if not pk.properties.is_property_set(_n):
                            _legacy.pop(_n, None)
                    except Exception:
                        pass
                op_inst["props"] = _legacy

        # Context cleanup (Task: multi-context). Lazy-applied at confirm:
        #   • drop any context that isn't a valid curated option.
        #   • use_multi_contexts OFF → collapse to a single context.
        from .database.keymap_contexts import KEYMAP_CONTEXTS as _ALL_CTX

        _curated = {c[0] for c in _ALL_CTX}
        for op_inst in sel_ops:
            oid = op_inst.get("id", "")
            ctxs = list(op_inst.get("contexts", []))
            if not ctxs and op_inst.get("context"):
                ctxs = [op_inst["context"]]
            if not ctxs:
                op_inst["contexts"] = []
                op_inst["context"] = ""
                continue
            # Drop only contexts that aren't valid curated options (e.g. renamed
            # or removed). Any legitimate curated context the user picked stays.
            ctxs = [c for c in ctxs if c in _curated]
            if not op_inst.get("use_multi_contexts", False) and len(ctxs) > 1:
                try:
                    from .keymap_manager import _get_keymap_for_op as _gkfo2

                    auto = _gkfo2(oid)
                except Exception:
                    auto = ""
                ctxs = [auto] if auto in ctxs else [ctxs[0]]
            op_inst["contexts"] = ctxs
            op_inst["context"] = ""

        op_id = _json.dumps(sel_ops)

        # Collect extra keybinds from scratch KMIs
        try:
            extra_slots = _json.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]")
        except Exception:
            extra_slots = []
        extra_keybinds = []
        for idx in range(len(extra_slots)):
            ex_kmi = None
            try:
                ex_kmi = _ensure_extra_scratch_kmi(idx + 1)
            except Exception:
                pass
            if ex_kmi and ex_kmi.type and ex_kmi.type != "NONE":
                extra_keybinds.append(
                    {
                        "key": ex_kmi.type,
                        "value": ex_kmi.value,
                        "shift": (ex_kmi.shift == 1),
                        "ctrl": (ex_kmi.ctrl == 1),
                        "alt": (ex_kmi.alt == 1),
                        "oskey": (ex_kmi.oskey == 1),
                        "any": bool(wm.get(f"keymapper_kmi_any_{idx + 1}", False)),
                        "key_modifier": getattr(ex_kmi, "key_modifier", "NONE")
                        or "NONE",
                        "detect_contexts": get_detect_contexts(wm, idx + 1),
                    }
                )

        data = {
            "display_name": label,
            "custom_label": custom_label,
            "operator_ids": op_id,
            "key": (kmi.type if (kmi and _use_keybind) else "NONE"),
            "detect_contexts": get_detect_contexts(wm, 0),
            "any": bool(wm.get("keymapper_kmi_any_0", False)),
            "shift": key_shift,
            "ctrl": key_ctrl,
            "alt": key_alt,
            "oskey": key_oskey,
            "key_modifier": (kmi.key_modifier
                             if (kmi and kmi.key_modifier != "NONE") else ""),
            "event_type": (kmi.value if kmi else "PRESS"),
            "repeat": bool(kmi and getattr(kmi, "repeat", False))
            and kmi.map_type == "KEYBOARD"
            and kmi.value in {"ANY", "PRESS"},
            "keymap_contexts": ctx_str,
            "source_app": _host(),
            "extra_keybinds": extra_keybinds if _use_keybind else [],
            # Entry Buttons (buttons.py)
            "use_keybind": _use_keybind,
            "use_button": _use_button,
            "button_locations": get_button_locations(wm) if _use_button else [],
            "button_show_label": bool(
                wm.get("keymapper_form_button_show_label", True)),
            "button_show_icon": bool(
                wm.get("keymapper_form_button_show_icon", True)),
            "button_conflict_detection": bool(
                wm.get("keymapper_form_button_conflicts", False)),
            "button_label": wm.keymapper_form_button_label.strip(),
            "custom_icon": wm.get("keymapper_form_pending_icon", "") if not edit_id else None,
        }
        if data.get("custom_icon") is None:
            data.pop("custom_icon")

        if edit_id:
            old_entry = persistence.get_entry_by_id(edit_id)
            old_snapshot = dict(old_entry) if old_entry else None
            persistence.update_entry(edit_id, data)
            # Only recreate KMIs if something keymap-relevant changed
            if old_snapshot:
                from . import keymap_manager
                keymap_manager.update_entry_if_changed(old_snapshot, data)
            self.report({"INFO"}, f"Keymapper: Updated '{label}'.")
        else:
            data.update(
                {
                    "entry_id": str(uuid.uuid4()),
                    "enabled": bool(wm.get("keymapper_form_enabled", True)),
                    "selected": False,
                    "expanded_entry": False,
                    "expanded_shortcuts": False,
                    "expanded_keybinds": False,
                    "shortcut_conflicts_internal": [],
                    "keybind_conflicts_internal": [],
                    "shortcut_conflicts_external": [],
                    "keybind_conflicts_external": [],
                    "sort_index": len(persistence.get_entries()),
                    "folder_id": (
                        wm.get("keymapper_quickadd_folder_id", "")
                        if wm.get("keymapper_quickadd_folder_set", False)
                        else wm.get("keymapper_new_entry_folder", "")),
                }
            )
            insert_after = wm.get("keymapper_form_insert_after", -1)
            insert_pos = (
                insert_after + 1
                if insert_after >= 0
                else len(persistence.get_entries())
            )
            persistence.insert_entry_at(data, insert_pos)
            # Select the newly created entry
            entries = persistence.get_entries()
            new_idx = next(
                (
                    i
                    for i, e in enumerate(entries)
                    if e.get("entry_id") == data["entry_id"]
                ),
                insert_pos,
            )
            context.window_manager.keymapper.selected_index = new_idx
            # Activate KMIs for the new entry
            from . import keymap_manager

            new_entry = persistence.get_entry_by_id(data["entry_id"])
            if new_entry:
                pass  # activated below after external scan has conflict data
            self.report({"INFO"}, f"Keymapper: Added '{label}'.")

        # Close form — deactivate scratch KMI so it doesn't block real shortcuts
        wm["keymapper_form_active"] = False
        wm["keymapper_form_entry_id"] = ""
        wm["keymapper_form_goto_unsorted"] = False
        wm["keymapper_form_pending_icon"] = ""
        wm["keymapper_form_icon_snapshot_set"] = False
        wm["keymapper_extra_keybinds"] = "[]"
        clear_all_detect_contexts(wm)
        _clear_extra_scratch_kmis()
        # Reset scratch KMI to neutral on close so it doesn't bleed into next edit
        reset_scratch_kmi()
        _scratch_kmi_set_active(False)
        clear_props_kmis()
        _run_conflict_scan()
        # Run external scan for the saved entry specifically
        saved_entry = persistence.get_entry_by_id(edit_id or data.get("entry_id", ""))
        if saved_entry:
            try:
                from . import conflict_detector

                conflict_detector.update_entry_external_conflicts(saved_entry)
                persistence._write_to_prefs()
                if saved_entry.get("enabled", True):
                    if not edit_id:
                        # Creation: activate now that we have conflict data.
                        keymap_manager.activate_entry(saved_entry)
                    else:
                        # Edit: restore old disables, then re-disable with fresh
                        # conflict data so stale conflicts get re-enabled.
                        entry_id = saved_entry.get("entry_id", "")
                        keymap_manager._restore_default_kmis(
                            entry_id, preserve_own_twins=True)
                        all_refs = (
                            saved_entry.get("keybind_conflicts_external", []) +
                            saved_entry.get("shortcut_conflicts_external", [])
                        )
                        if all_refs:
                            keymap_manager._disable_default_kmis(entry_id, all_refs)
                        keymap_manager._refresh_keyconfigs()
                    keymap_manager.schedule_conflict_disable()
            except Exception as e:
                print(f"[Keymapper] External scan error: {e}")
        # Only mark unsaved if something actually changed
        if edit_id:
            if old_snapshot:
                changed_keys = {
                    "display_name",
                    "custom_label",
                    "operator_ids",
                    "key",
                    "shift",
                    "ctrl",
                    "alt",
                    "oskey",
                    "key_modifier",
                    "event_type",
                    "keymap_contexts",
                }
                actually_changed = any(
                    str(data.get(k)) != str(old_snapshot.get(k, ""))
                    for k in changed_keys
                )
                if actually_changed:
                    mark_unsaved()
            else:
                mark_unsaved()
        else:
            mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Form Cancel (X button)
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_FormCancel(Operator):
    bl_idname = "keymapper.form_cancel"
    bl_label = "Cancel"
    bl_description = "Cancel editing this shortcut entry"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        # Revert any icon change made during this edit session.
        eid = wm.get("keymapper_form_entry_id", "")
        if eid and wm.get("keymapper_form_icon_snapshot_set", False):
            entry = persistence.get_entry_by_id(eid)
            if entry is not None:
                persistence.update_entry(
                    eid, {"custom_icon": wm.get("keymapper_form_icon_snapshot", "")}
                )
        wm["keymapper_form_icon_snapshot_set"] = False
        wm["keymapper_form_active"] = False
        wm["keymapper_form_entry_id"] = ""
        wm["keymapper_form_goto_unsorted"] = False
        wm["keymapper_form_pending_icon"] = ""
        _clear_extra_scratch_kmis()
        reset_scratch_kmi()
        _scratch_kmi_set_active(False)
        clear_props_kmis()
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Form inline browse operators
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_FormToggleBrowse(Operator):
    bl_idname = "keymapper.form_toggle_browse"
    bl_label = "Browse Operators"
    bl_description = "Open / close the operator browser"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        _wm_set(wm, WM_BROWSE_ON, not bool(_wm_get(wm, WM_BROWSE_ON, False)))
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleNamingMode(Operator):
    bl_idname = "keymapper.toggle_naming_mode"
    bl_label = "Toggle between Friendly and Pure naming convention."
    bl_options = {"INTERNAL"}

    @classmethod
    def description(cls, context, properties):
        try:
            prefs = context.preferences.addons[__package__].preferences
            if prefs.naming_mode == "FRIENDLY":
                return "Toggle between Friendly and Pure naming convention.\nCurrent: Friendly"
            return "Toggle between Friendly and Pure naming convention.\nCurrent: Pure (Raw IDs)"
        except Exception:
            return "Toggle between Friendly and Pure naming convention."

    def execute(self, context):
        try:
            prefs = context.preferences.addons[__package__].preferences
            prefs.naming_mode = (
                "PURE" if prefs.naming_mode == "FRIENDLY" else "FRIENDLY"
            )
        except Exception:
            pass
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormSetCategory(Operator):
    bl_idname = "keymapper.form_set_category"
    bl_label = "Set Category"
    bl_options = {"INTERNAL"}
    category_id: StringProperty()

    def execute(self, context):
        _wm_set(context.window_manager, WM_CATEGORY, self.category_id)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormAddOp(Operator):
    """Add one instance of a repeatable operator."""

    bl_idname = "keymapper.form_add_op"
    bl_label = "Add Operator Instance"
    bl_options = {"INTERNAL"}
    operator_id: StringProperty()
    use_friendly: BoolProperty(default=True)

    def execute(self, context):
        wm = context.window_manager
        ops = _get_sel_ops(wm)
        op_id = self.operator_id
        ops.append({"id": op_id, "props": {}, "context": ""})
        _set_sel_ops(wm, ops)
        wm.keymapper_prop_texts.clear()
        wm.keymapper_context_path_props.clear()
        wm.keymapper_int_props.clear()
        wm.keymapper_float_props.clear()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormRemoveLastOp(Operator):
    """Remove the last instance of a repeatable operator."""

    bl_idname = "keymapper.form_remove_last_op"
    bl_label = "Remove Last Operator Instance"
    bl_options = {"INTERNAL"}
    operator_id: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        ops = _get_sel_ops(wm)
        op_id = self.operator_id
        # Find last instance and remove it
        for i in range(len(ops) - 1, -1, -1):
            if ops[i]["id"] == op_id:
                ops.pop(i)
                break
        _set_sel_ops(wm, ops)
        wm.keymapper_prop_texts.clear()
        wm.keymapper_context_path_props.clear()
        wm.keymapper_int_props.clear()
        wm.keymapper_float_props.clear()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleSelPanel(Operator):
    """Toggle the Selected Operators panel open/closed."""

    bl_idname = "keymapper.form_toggle_sel_panel"
    bl_label = "Toggle Selected Panel"
    bl_description = "Toggle the Operators panel"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        current = bool(wm.get("keymapper_sel_panel_open", False))
        wm["keymapper_sel_panel_open"] = not current
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ShowUpdate(Operator):
    """A newer version of Keymapper is available — open the extension list"""

    bl_idname = "keymapper.show_update"
    bl_label = "Update Available"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        try:
            bpy.ops.extensions.userpref_show_for_update("INVOKE_DEFAULT")
            return {"FINISHED"}
        except Exception:
            pass
        # Fall back to the add-ons page if that operator is unavailable.
        try:
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
            context.preferences.active_section = "EXTENSIONS"
        except Exception as e:
            self.report({"WARNING"}, f"Keymapper: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class KEYMAPPER_OT_TogglePreviewCard(Operator):
    """Preview how this entry will look in the main Keymapper Panel"""

    bl_idname = "keymapper.toggle_preview_card"
    bl_label = "Preview Keymapper Entry"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        key = subcat_wm_key("quickadd_preview")
        wm[key] = not wm.get(key, False)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleBrowseSubcat(Operator):
    """Toggle a subcategory collapse state in the browse panel."""

    bl_idname = "keymapper.form_toggle_browse_subcat"
    bl_label = "Toggle Subcategory"
    bl_description = "Expand or collapse this section"
    bl_options = {"INTERNAL"}
    key: StringProperty()
    default_open: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        wm = context.window_manager
        raw_key = subcat_wm_key(self.key)
        wm[raw_key] = not wm.get(raw_key, self.default_open)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_TogglePresetFolder(Operator):
    """Expand or collapse a folder's entry list in the presets popup."""

    bl_idname = "keymapper.toggle_preset_folder"
    bl_label = "Toggle Preset Folder"
    bl_description = "Show or hide the individual entries in this preset folder"
    bl_options = {"INTERNAL"}
    preset_id: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        key = f"keymapper_presetfold_{self.preset_id}"
        wm[key] = not wm.get(key, False)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleContextGroup(Operator):
    """Toggle a context group collapse state in the context search popup."""

    bl_idname = "keymapper.form_toggle_context_group"
    bl_label = "Toggle Context Group"
    bl_description = "Expand or collapse this context group"
    bl_options = {"INTERNAL"}
    group_id: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        key = f"keymapper_ctxgrp_{self.group_id}"
        wm[key] = not wm.get(key, False)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleOp(Operator):
    """Toggle an operator in/out of the multi-selection.
    Operators WITH required properties can be added multiple times.
    Operators WITHOUT required properties toggle on/off."""

    bl_idname = "keymapper.form_toggle_op"
    bl_label = "Toggle Operator"
    bl_description = "Add or remove this operator from the selection"
    bl_options = {"INTERNAL"}
    operator_id: StringProperty()
    use_friendly: BoolProperty(default=True)

    @classmethod
    def description(cls, context, properties):
        op_id = properties.operator_id
        if op_id and "." in op_id:
            try:
                module, func = op_id.split(".", 1)
                op_mod = getattr(bpy.ops, module)
                op_fn = getattr(op_mod, func)
                desc = op_fn.get_rna_type().description
                if desc:
                    return desc
            except Exception:
                pass
        return "Add or remove this operator from the selection"

    def execute(self, context):
        from .database.op_properties import op_can_repeat

        wm = context.window_manager
        ops = _get_sel_ops(wm)
        op_id = self.operator_id
        can_repeat = op_can_repeat(op_id)

        if can_repeat:
            # Ops that can repeat: always ADD a new instance
            # Context required ops start with empty context (user must fill it)
            new_inst = {"id": op_id, "props": {}, "context": ""}
            ops.append(new_inst)
        else:
            # Single-instance ops: toggle on/off
            existing = [o for o in ops if o["id"] == op_id]
            if existing:
                ops = [o for o in ops if o["id"] != op_id]
            else:
                ops.append({"id": op_id, "props": {}, "context": ""})

        _set_sel_ops(wm, ops)

        # Update OP_ID/LABEL for backwards compat
        if ops:
            last = ops[-1]["id"]
            _wm_set(wm, WM_OP_ID, last)
            friendly = get_friendly_name(last)
            label = (friendly if friendly else last) if self.use_friendly else last
            _wm_set(wm, WM_OP_LABEL, label)
        else:
            _wm_set(wm, WM_OP_ID, "")
            _wm_set(wm, WM_OP_LABEL, "")

        # Never auto-fill label — placeholder in panel.py drives the live name
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormSetOpProp(Operator):
    """Set a property value on a specific operator instance."""

    bl_idname = "keymapper.form_set_op_prop"
    bl_label = "Set Operator Property"
    bl_description = "Select this menu, pie menu or panel"
    bl_options = {"INTERNAL"}
    op_index: bpy.props.IntProperty()
    prop_name: StringProperty()
    prop_value: StringProperty()

    @classmethod
    def description(cls, context, properties):
        val = properties.prop_value
        if val:
            try:
                t = getattr(bpy.types, val, None)
                if t and hasattr(t, "bl_description") and t.bl_description:
                    return t.bl_description
                if t and hasattr(t, "bl_label") and t.bl_label:
                    return t.bl_label
            except Exception:
                pass
            return val
        return "Select this menu, pie menu or panel"

    def execute(self, context):
        wm = context.window_manager
        ops = _get_sel_ops(wm)
        if 0 <= self.op_index < len(ops):
            ops[self.op_index]["props"][self.prop_name] = self.prop_value
            _set_sel_ops(wm, ops)
            # Live-sync the open Properties editor's backing KMI so its native
            # field (e.g. Identifier) reflects the picker immediately. Safe: runs
            # in an operator (not draw), only when the editor is open, and the
            # prop is display-only (excluded from what gets saved).
            try:
                op_id = ops[self.op_index].get("id", "")
                pk = peek_props_kmi(self.op_index, op_id)
                if pk is not None:
                    apply_legacy_props(
                        pk.properties, {self.prop_name: self.prop_value}
                    )
            except Exception:
                pass
        # Collapse the inline prop selector
        wm[f"keymapper_subcat_prop_{self.op_index}_{self.prop_name}"] = False
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_OpenOpCtxPicker(Operator):
    """Pick the context(s) for one operator instance in a draggable dialog
    (same container as the value picker). Toggles apply live; Close, Cancel
    and Esc all just dismiss the dialog."""

    bl_idname = "keymapper.open_op_ctx_picker"
    bl_label = "Context"
    bl_description = "Choose which context(s) this operator registers in"
    bl_options = {"INTERNAL"}

    op_index: IntProperty(default=-1)

    _CTX_KEYS = ("context", "contexts", "use_multi_contexts",
                 "expand_contexts")

    def invoke(self, context, event):
        import copy as _copy
        wm = context.window_manager
        global _dialog_revert_cb, _dialog_frozen_ops
        _dialog_revert_cb = None
        _dialog_frozen_ops = wm.get(WM_OP_IDS, "")
        try:
            op_inst = _get_sel_ops(wm)[self.op_index]
            _ctx_defaults = {"context": "", "contexts": [],
                             "use_multi_contexts": False,
                             "expand_contexts": False}
            # Missing keys snapshot as their DEFAULTS (not None): the revert
            # writes this dict back verbatim, and a None "contexts" made the
            # selector's list(...) crash on every redraw after Cancel.
            _snap = _copy.deepcopy(
                {k: (op_inst.get(k) if op_inst.get(k) is not None
                     else _ctx_defaults[k])
                 for k in self._CTX_KEYS})
            _i = self.op_index

            def _revert(_ctx, _i=_i, _snap=_snap):
                _w = _ctx.window_manager
                ops = _get_sel_ops(_w)
                if 0 <= _i < len(ops):
                    ops[_i].update(_snap)
                    _set_sel_ops(_w, ops)
                    _redraw(_ctx)
            _dialog_revert_cb = _revert
        except Exception:
            pass
        return wm.invoke_props_dialog(
            self, width=320, title="Context", confirm_text="Close")

    def draw(self, context):
        from .panel import draw_op_ctx_body
        draw_op_ctx_body(self.layout, context, self.op_index)

    def execute(self, context):
        # Confirm path (also reached by Enter): keep the changes.
        _dialog_consume_revert(context, revert=False)
        return {"FINISHED"}

    def cancel(self, context):
        # Cancel button, Esc or clicking away: discard the transaction.
        _dialog_consume_revert(context, revert=True)




class KEYMAPPER_OT_ResetOpContext(Operator):
    """Reset one operator's context selection back to Auto."""

    bl_idname = "keymapper.reset_op_context"
    bl_label = "Reset"
    bl_description = "Reset context selection"
    bl_options = {"INTERNAL"}

    op_index: IntProperty(default=-1)

    def execute(self, context):
        # Same effect as the old header clear: route through the real setter.
        return bpy.ops.keymapper.form_set_op_context(
            op_index=self.op_index, context_name="")


class KEYMAPPER_OT_ResetDetectCtx(Operator):
    """Clear the additional detection contexts of one keybind slot."""

    bl_idname = "keymapper.reset_detect_ctx"
    bl_label = "Reset"
    bl_description = "Reset context selection"
    bl_options = {"INTERNAL"}

    slot_index: IntProperty(default=0)

    def execute(self, context):
        wm = context.window_manager
        set_detect_contexts(wm, self.slot_index, [])
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ResetSelOps(Operator):
    """Clear the form's selected-operators list."""

    bl_idname = "keymapper.reset_sel_ops"
    bl_label = "Reset"
    bl_description = "Reset operator selection"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        _set_sel_ops(wm, [])
        # Same cleanup as removing operators one by one — per-op prop fields
        # are indexed, and every index is stale once the list empties.
        wm.keymapper_prop_texts.clear()
        wm.keymapper_context_path_props.clear()
        wm.keymapper_int_props.clear()
        wm.keymapper_float_props.clear()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ResetOpProp(Operator):
    """Clear one curated picker property (menu / panel / pie / tool)."""

    bl_idname = "keymapper.reset_op_prop"
    bl_label = "Reset"
    bl_description = "Reset Selection"
    bl_options = {"INTERNAL"}

    op_index: IntProperty(default=-1)
    prop_name: StringProperty(default="")

    def execute(self, context):
        return bpy.ops.keymapper.form_set_op_prop(
            op_index=self.op_index, prop_name=self.prop_name, prop_value="")


class KEYMAPPER_OT_OpenDetectCtxPicker(Operator):
    """Pick Additional Keybind Detection Context(s) for one keybind slot in a
    draggable dialog (same container as the value picker). Toggles apply
    live; Close, Cancel and Esc all just dismiss the dialog."""

    bl_idname = "keymapper.open_detect_ctx_picker"
    bl_label = "Additional Keybind Detection Context(s)"
    bl_description = (
        "Contexts where this keybind disables same-key defaults without "
        "creating a shortcut. Operator contexts are pre-checked and locked"
    )
    bl_options = {"INTERNAL"}

    slot_index: IntProperty(default=0)

    def invoke(self, context, event):
        wm = context.window_manager
        global _dialog_revert_cb, _dialog_frozen_detect
        _old = list(get_detect_contexts(wm, self.slot_index))
        _dialog_frozen_detect = (self.slot_index, list(_old))
        _slot = self.slot_index

        def _revert(_ctx, _slot=_slot, _old=_old):
            set_detect_contexts(_ctx.window_manager, _slot, _old)
            _redraw(_ctx)
        _dialog_revert_cb = _revert
        return wm.invoke_props_dialog(
            self, width=320, title="Additional Keybind Detection Context(s)",
            confirm_text="Close")

    def draw(self, context):
        from .panel import draw_detect_ctx_body
        draw_detect_ctx_body(self.layout, context, self.slot_index)

    def execute(self, context):
        # Confirm path (also reached by Enter): keep the changes.
        _dialog_consume_revert(context, revert=False)
        return {"FINISHED"}

    def cancel(self, context):
        # Cancel button, Esc or clicking away: discard the transaction.
        _dialog_consume_revert(context, revert=True)




# Set by each selection dialog's invoke(). The dialogs are transactions:
# picks show live INSIDE the dialog, while the form behind it keeps
# rendering the open-time snapshot (see form_view_ops), so nothing appears
# there mid-pick. Confirm keeps the changes; Cancel, Esc and clicking away
# revert to the snapshot.
_dialog_revert_cb = None
_dialog_frozen_ops = None       # raw WM_OP_IDS string at dialog open
_dialog_frozen_detect = None    # (slot_index, [contexts]) at dialog open
_dialog_frozen_locations = None  # [locations] at dialog open


def form_view_ops(wm) -> list:
    """What the FORM should render: the frozen open-time snapshot while a
    selection dialog is open, the live scratch otherwise."""
    import json
    if _dialog_frozen_ops is not None:
        try:
            data = json.loads(_dialog_frozen_ops or "[]")
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []
    return _get_sel_ops(wm)


def view_detect_contexts(wm, slot: int) -> list:
    """Frozen-aware read of a slot's detection contexts (form display)."""
    if (_dialog_frozen_detect is not None
            and _dialog_frozen_detect[0] == slot):
        return list(_dialog_frozen_detect[1])
    return get_detect_contexts(wm, slot)


def view_button_locations(wm) -> list:
    """Frozen-aware read of the form's button locations (form display)."""
    if _dialog_frozen_locations is not None:
        return list(_dialog_frozen_locations)
    return get_button_locations(wm)


def _dialog_consume_revert(context, revert: bool):
    global _dialog_revert_cb, _dialog_frozen_ops, _dialog_frozen_detect, \
        _dialog_frozen_locations
    cb, _dialog_revert_cb = _dialog_revert_cb, None
    _dialog_frozen_ops = None
    _dialog_frozen_detect = None
    _dialog_frozen_locations = None
    if revert and cb is not None:
        try:
            cb(context)
        except Exception as e:
            print(f"[Keymapper] dialog revert failed: {e}")


class KEYMAPPER_OT_DialogCommit(Operator):
    """The Confirm button of the selection dialogs: keeps everything picked
    while the dialog was open, then the popup closes."""

    bl_idname = "keymapper.dialog_commit"
    bl_label = "Confirm"
    bl_description = "Apply the changes made in this popup and close it"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        _dialog_consume_revert(context, revert=False)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleExtraOptions(Operator):
    """Fold arrow for a keybind slot's extra options (the Additional Keybind
    Detection Context(s) row)."""

    bl_idname = "keymapper.toggle_extra_options"
    bl_label = "Extra Options"
    bl_description = "Expand or collapse extra options"
    bl_options = {"INTERNAL"}

    key: StringProperty(default="")
    default_open: BoolProperty(default=False)

    def execute(self, context):
        wm = context.window_manager
        k = f"keymapper_subcat_{self.key}"
        wm[k] = not bool(wm.get(k, self.default_open))
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_UnsetKmiProperty(Operator):
    """Clear one operator property on the editing scratch KMI, so it isn't
    stored on the entry at all and the operator falls back to its own default
    behaviour (Blender's X in the keymap editor does the same thing)."""

    bl_idname = "keymapper.unset_kmi_property"
    bl_label = "Clear Property"
    bl_description = ("Clear this property so it isn't stored — the operator "
                      "uses its own default behaviour")
    bl_options = {"INTERNAL"}

    slot: IntProperty(default=-1)
    op_id: StringProperty(default="")
    prop_name: StringProperty(default="")

    def execute(self, context):
        if self.slot < 0 or not self.prop_name:
            return {"CANCELLED"}
        pk = peek_props_kmi(self.slot, self.op_id)
        if pk is None or pk.properties is None:
            return {"CANCELLED"}
        try:
            pk.properties.property_unset(self.prop_name)
        except Exception as e:
            print(f"[Keymapper] Could not clear '{self.prop_name}': {e}")
            return {"CANCELLED"}
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ResetButtonLocations(Operator):
    """Clear the button's locations."""

    bl_idname = "keymapper.reset_button_locations"
    bl_label = "Reset"
    bl_description = "Reset location selection"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        set_button_locations(context.window_manager, [])
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleEntryButtonVisibility(Operator):
    """Show or hide this entry's button in all of its locations (the entry
    and its locations are kept — only the visibility flips)."""

    bl_idname = "keymapper.toggle_entry_button_visibility"
    bl_label = "Toggle Button Visibility"
    bl_description = "Toggle button visibility"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty(default="")

    def execute(self, context):
        from . import persistence
        entry = persistence.get_entry_by_id(self.entry_id)
        if entry is None:
            return {"CANCELLED"}
        persistence.update_entry(
            self.entry_id,
            {"button_visible": not entry.get("button_visible", True)})
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleEntryButtonLocation(Operator):
    """Toggle one button location on a SAVED entry (card Locations dialog).
    The location hooks read persistence every draw, so no re-registration is
    needed — the buttons appear/disappear on the next redraw."""

    bl_idname = "keymapper.toggle_entry_button_location"
    bl_label = "Toggle Location"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty(default="")
    location: StringProperty(default="")

    def execute(self, context):
        from . import persistence
        entry = persistence.get_entry_by_id(self.entry_id)
        if entry is None:
            return {"CANCELLED"}
        locs = list(entry.get("button_locations", []) or [])
        if self.location in locs:
            locs.remove(self.location)
        else:
            locs.append(self.location)
        persistence.update_entry(self.entry_id, {"button_locations": locs})
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ResetEntryButtonLocations(Operator):
    """Clear a saved entry's button locations."""

    bl_idname = "keymapper.reset_entry_button_locations"
    bl_label = "Reset"
    bl_description = "Reset location selection"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty(default="")

    def execute(self, context):
        from . import persistence
        if persistence.get_entry_by_id(self.entry_id) is not None:
            persistence.update_entry(self.entry_id,
                                     {"button_locations": []})
            mark_unsaved()
            _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_OpenEntryLocPicker(Operator):
    """The card's Locations dialog: edit where this entry's button appears.
    Confirm keeps the changes; Cancel, Esc and clicking away revert."""

    bl_idname = "keymapper.open_entry_loc_picker"
    bl_label = "Locations"
    bl_description = "Choose where this entry's button appears"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty(default="")

    def invoke(self, context, event):
        from . import persistence
        wm = context.window_manager
        global _dialog_revert_cb
        entry = persistence.get_entry_by_id(self.entry_id)
        _old = list((entry or {}).get("button_locations", []) or [])
        _eid = self.entry_id

        def _revert(_ctx, _eid=_eid, _old=_old):
            from . import persistence as _p
            if _p.get_entry_by_id(_eid) is not None:
                _p.update_entry(_eid, {"button_locations": _old})
                _redraw(_ctx)
        _dialog_revert_cb = _revert
        return wm.invoke_props_dialog(
            self, width=320, title="Locations", confirm_text="Close")

    def draw(self, context):
        from .panel import draw_entry_loc_body
        draw_entry_loc_body(self.layout, context, self.entry_id)

    def execute(self, context):
        _dialog_consume_revert(context, revert=False)
        return {"FINISHED"}

    def cancel(self, context):
        _dialog_consume_revert(context, revert=True)


class KEYMAPPER_OT_OpenButtonLocPicker(Operator):
    """Pick the button's locations in a draggable dialog — same transaction
    pattern as the other pickers: Confirm keeps, Cancel / Esc / click-away
    revert, and the form shows the open-time state until then."""

    bl_idname = "keymapper.open_button_loc_picker"
    bl_label = "Locations"
    bl_description = "Choose where this entry's button appears"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        wm = context.window_manager
        global _dialog_revert_cb, _dialog_frozen_locations
        _old = list(get_button_locations(wm))
        _dialog_frozen_locations = list(_old)

        def _revert(_ctx, _old=_old):
            set_button_locations(_ctx.window_manager, _old)
            _redraw(_ctx)
        _dialog_revert_cb = _revert
        return wm.invoke_props_dialog(
            self, width=320, title="Locations", confirm_text="Close")

    def draw(self, context):
        from .panel import draw_button_loc_body
        draw_button_loc_body(self.layout, context)

    def execute(self, context):
        _dialog_consume_revert(context, revert=False)
        return {"FINISHED"}

    def cancel(self, context):
        _dialog_consume_revert(context, revert=True)


class KEYMAPPER_OT_IconHint(Operator):
    """No-op icon whose tooltip is whatever the draw site sets in `text` —
    used for the card's Button / Location marker icons."""

    bl_idname = "keymapper.icon_hint"
    bl_label = ""
    bl_options = {"INTERNAL"}

    text: StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        return properties.text or ""

    def execute(self, context):
        return {"CANCELLED"}


class KEYMAPPER_OT_OpenPropPicker(Operator):
    """Pick a value for a curated dropdown property (menu / pie menu / panel /
    tool) in a draggable dialog — same container pattern as the Browse
    Operators dialog. Clicking a value applies it to the form live; Close,
    Cancel and Esc all just dismiss the dialog."""

    bl_idname = "keymapper.open_prop_picker"
    bl_label = "Select Value"
    bl_description = "Pick a value for this property in a draggable dialog"
    bl_options = {"INTERNAL"}

    op_index: IntProperty(default=-1)
    prop_name: StringProperty(default="")

    def invoke(self, context, event):
        # Title = the operator's friendly name ("Call Panel"), shown in the
        # dialog's native title strip above the separator line.
        title = "Select Value"
        wm = context.window_manager
        global _dialog_revert_cb, _dialog_frozen_ops
        _dialog_revert_cb = None
        _dialog_frozen_ops = wm.get(WM_OP_IDS, "")
        try:
            op_inst = _get_sel_ops(wm)[self.op_index]
            op_id = op_inst["id"]
            title = get_friendly_name(op_id) or op_id
            _old_val = (op_inst.get("props") or {}).get(self.prop_name, "")
            _i, _pn = self.op_index, self.prop_name

            def _revert(_ctx, _i=_i, _pn=_pn, _old=_old_val):
                bpy.ops.keymapper.form_set_op_prop(
                    op_index=_i, prop_name=_pn, prop_value=_old)
            _dialog_revert_cb = _revert
        except Exception:
            pass
        return wm.invoke_props_dialog(
            self, width=320, title=title, confirm_text="Close")

    def draw(self, context):
        from .panel import draw_prop_picker_body
        draw_prop_picker_body(self.layout, context, self.op_index,
                              self.prop_name)

    def execute(self, context):
        # Confirm path (also reached by Enter): keep the changes.
        _dialog_consume_revert(context, revert=False)
        return {"FINISHED"}

    def cancel(self, context):
        # Cancel button, Esc or clicking away: discard the transaction.
        _dialog_consume_revert(context, revert=True)




class KEYMAPPER_OT_OpenBrowsePopup(Operator):
    """Open the Browse Operators list as a draggable dialog.

    An `invoke_props_dialog` instead of a `wm.call_panel` popup: dialogs can
    be dragged anywhere within the Blender window (popups are anchored to the
    region that spawned them). Every click inside applies to the form live,
    so Close and Cancel are equivalent — both simply dismiss the dialog.
    """

    bl_idname = "keymapper.open_browse_popup"
    bl_label = "Browse Operators"
    bl_description = (
        "Browse and select operators for this entry in a draggable dialog"
    )
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        wm = context.window_manager
        global _dialog_revert_cb, _dialog_frozen_ops
        _old = wm.get(WM_OP_IDS, "")
        _dialog_frozen_ops = _old

        def _revert(_ctx, _old=_old):
            _ctx.window_manager[WM_OP_IDS] = _old
            _redraw(_ctx)
        _dialog_revert_cb = _revert
        return wm.invoke_props_dialog(
            self, width=480, title="Browse Operators", confirm_text="Close")

    def draw(self, context):
        from .panel import draw_browse_popup_body
        draw_browse_popup_body(self.layout, context)

    def execute(self, context):
        # Confirm path (also reached by Enter): keep the changes.
        _dialog_consume_revert(context, revert=False)
        return {"FINISHED"}

    def cancel(self, context):
        # Cancel button, Esc or clicking away: discard the transaction.
        _dialog_consume_revert(context, revert=True)




class KEYMAPPER_OT_FormRemoveOp(Operator):
    """Remove an operator instance by index."""

    bl_idname = "keymapper.form_remove_op"
    bl_label = "Remove Operator"
    bl_description = "Remove this operator from the selected operators list"
    bl_options = {"INTERNAL"}
    op_index: bpy.props.IntProperty(default=-1)
    # Legacy support — remove by ID when index not set
    operator_id: StringProperty(default="")

    def execute(self, context):
        wm = context.window_manager
        ops = _get_sel_ops(wm)
        if self.op_index >= 0 and self.op_index < len(ops):
            ops.pop(self.op_index)
        elif self.operator_id:
            # Legacy: remove first matching ID
            for i, o in enumerate(ops):
                if o["id"] == self.operator_id:
                    ops.pop(i)
                    break
        _set_sel_ops(wm, ops)
        # Clear prop text/numeric fields — indices shift after removal
        wm.keymapper_prop_texts.clear()
        wm.keymapper_context_path_props.clear()
        wm.keymapper_int_props.clear()
        wm.keymapper_float_props.clear()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleContext(Operator):
    bl_idname = "keymapper.form_toggle_context"
    bl_label = "Toggle Context"
    bl_options = {"INTERNAL"}
    context_id: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        current = _wm_get(wm, WM_CONTEXTS, "Object Mode")
        parts = [c.strip() for c in current.split(",") if c.strip()]
        if self.context_id in parts:
            if len(parts) > 1:
                parts.remove(self.context_id)
        else:
            parts.append(self.context_id)
        _wm_set(wm, WM_CONTEXTS, ",".join(parts))
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# KMI modifier toggle
# ---------------------------------------------------------------------------


class KEYMAPPER_SearchItem(bpy.types.PropertyGroup):
    value: bpy.props.StringProperty(default="")


def _context_path_search(self, context, edit_text):
    """Search callback for context path fields — powers Blender's native search popup."""
    from .database.op_properties import get_context_paths

    return get_context_paths(edit_text)


class KEYMAPPER_ContextPathItem(bpy.types.PropertyGroup):
    """PropertyGroup for context path props — has native Blender search popup."""

    value: bpy.props.StringProperty(
        name="Context Attributes",
        default="",
        search=_context_path_search,
        search_options={"SORT"},
    )


class KEYMAPPER_NumericItem(bpy.types.PropertyGroup):
    int_value: bpy.props.IntProperty(default=0)
    float_value: bpy.props.FloatProperty(default=0.0)


class KEYMAPPER_OT_ClearKeyModifier(Operator):
    """Clear the key modifier on the scratch KMI."""

    bl_idname = "keymapper.clear_key_modifier"
    bl_label = "Clear Key Modifier"
    bl_description = "Clear the optional key modifier"
    bl_options = {"INTERNAL"}

    slot_index: IntProperty(default=0)

    def execute(self, context):
        if self.slot_index == 0:
            kmi = get_scratch_kmi()
        else:
            kmi = get_extra_scratch_kmi(self.slot_index)
        if kmi:
            try:
                kmi.key_modifier = "NONE"
            except Exception:
                pass
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleKmiMod(Operator):
    bl_idname = "keymapper.toggle_kmi_mod"
    bl_label = "Toggle Modifier"
    bl_description = "Toggle this modifier key on or off"
    bl_options = {"INTERNAL"}
    mod_name: StringProperty()
    slot_index: IntProperty(default=0)

    def execute(self, context):
        wm = context.window_manager
        if self.slot_index == 0:
            kmi = get_scratch_kmi()
        else:
            kmi = get_extra_scratch_kmi(self.slot_index)

        any_key = f"keymapper_kmi_any_{self.slot_index}"

        if self.mod_name == "any":
            # Toggle all modifiers on/off together
            current = bool(wm.get(any_key, False))
            new_val = not current
            wm[any_key] = new_val
            if kmi:
                val = 1 if new_val else 0
                kmi.shift = val
                kmi.ctrl = val
                kmi.alt = val
                kmi.oskey = val
        else:
            # Toggle individual modifier
            if kmi is None:
                return {"CANCELLED"}
            current = getattr(kmi, self.mod_name, 0)
            setattr(kmi, self.mod_name, 0 if current == 1 else 1)
            # Update any state: True if all modifiers are now on
            all_on = (
                kmi.shift == 1 and kmi.ctrl == 1 and kmi.alt == 1 and kmi.oskey == 1
            )
            wm[any_key] = all_on
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Standard list operators
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_DeleteEntry(Operator):
    bl_idname = "keymapper.delete_entry"
    bl_label = "Delete Selected Entry"
    bl_description = "Delete the currently selected shortcut entry"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        entries = persistence.get_entries()
        idx = context.window_manager.keymapper.selected_index
        if not entries:
            self.report({"WARNING"}, "Keymapper: No entries to delete.")
            return {"CANCELLED"}
        idx = min(idx, len(entries) - 1)
        entry = entries[idx]
        name = entry.get("display_name", "?")
        folder_id = entry.get("folder_id", "")

        # Remove KMIs before deleting from persistence
        from . import keymap_manager

        keymap_manager.delete_entry(entry)
        persistence.remove_entry(entry["entry_id"])

        # Select entry below in same folder, or none if none exists
        remaining = persistence.get_entries()
        # Find next entry in same folder at same or later position
        new_idx = -1
        for i, e in enumerate(remaining):
            if e.get("folder_id", "") == folder_id and i >= idx:
                new_idx = i
                break
        # If nothing below, try entry above in same folder
        if new_idx < 0:
            for i in range(min(idx, len(remaining)) - 1, -1, -1):
                if remaining[i].get("folder_id", "") == folder_id:
                    new_idx = i
                    break

        context.window_manager.keymapper.selected_index = new_idx
        _run_conflict_scan()
        mark_unsaved()
        self.report({"INFO"}, f"Keymapper: Deleted '{name}'.")
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_MoveEntryUp(Operator):
    bl_idname = "keymapper.move_entry_up"
    bl_label = "Move Up"
    bl_description = "Move selected entry or folder up"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        sel_fid = getattr(wm, "keymapper_selected_folder_id", "")
        # Folder selected — move folder
        if sel_fid and wm.keymapper.selected_index < 0:
            persistence.move_folder(sel_fid, -1)
            mark_unsaved()
            _redraw(context)
            return {"FINISHED"}
        # Entry selected
        idx = wm.keymapper.selected_index
        entries = persistence.get_entries()
        if idx <= 0 or not entries:
            return {"CANCELLED"}
        entry = entries[idx]
        folder_id = entry.get("folder_id", "")
        prev_idx = idx - 1
        while prev_idx >= 0 and entries[prev_idx].get("folder_id", "") != folder_id:
            prev_idx -= 1
        if prev_idx < 0:
            return {"CANCELLED"}
        persistence.move_entry(entry["entry_id"], prev_idx - idx)
        wm.keymapper.selected_index = prev_idx
        # Pure reorder: update order-derived state only (wins flags; inert
        # reconcile only when identical twins actually exist).
        _run_reorder_scan()
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_MoveEntryDown(Operator):
    bl_idname = "keymapper.move_entry_down"
    bl_label = "Move Down"
    bl_description = "Move selected entry or folder down"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        sel_fid = getattr(wm, "keymapper_selected_folder_id", "")
        # Folder selected — move folder
        if sel_fid and wm.keymapper.selected_index < 0:
            persistence.move_folder(sel_fid, 1)
            mark_unsaved()
            _redraw(context)
            return {"FINISHED"}
        # Entry selected
        idx = wm.keymapper.selected_index
        entries = persistence.get_entries()
        if idx >= len(entries) - 1 or not entries:
            return {"CANCELLED"}
        entry = entries[idx]
        folder_id = entry.get("folder_id", "")
        next_idx = idx + 1
        while (
            next_idx < len(entries)
            and entries[next_idx].get("folder_id", "") != folder_id
        ):
            next_idx += 1
        if next_idx >= len(entries):
            return {"CANCELLED"}
        persistence.move_entry(entry["entry_id"], next_idx - idx)
        wm.keymapper.selected_index = next_idx
        # Pure reorder — fast path (see MoveEntryUp).
        _run_reorder_scan()
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_DuplicateEntry(Operator):
    bl_idname = "keymapper.duplicate_entry"
    bl_label = "Duplicate Entry"
    bl_description = "Duplicate the selected shortcut entry and insert it below"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        import copy
        import uuid as _uuid

        entries = persistence.get_entries()
        idx = context.window_manager.keymapper.selected_index
        if not entries or idx < 0 or idx >= len(entries):
            self.report({"WARNING"}, "Keymapper: No entry selected.")
            return {"CANCELLED"}
        original = entries[idx]
        # Deep copy and assign new identity
        duplicate = copy.deepcopy(original)
        duplicate["entry_id"] = str(_uuid.uuid4())
        duplicate["selected"] = False
        duplicate["sort_index"] = original["sort_index"] + 1
        # Insert immediately below original
        persistence.insert_entry_at(duplicate, idx + 1)
        # Select the new duplicate
        context.window_manager.keymapper.selected_index = idx + 1
        # Activate KMIs for the duplicate
        from . import keymap_manager

        new_entry = persistence.get_entry_by_id(duplicate["entry_id"])
        if new_entry and new_entry.get("enabled", True):
            keymap_manager.activate_entry(new_entry)
        # Run conflict scan — duplicate will immediately show conflict with original
        _run_conflict_scan()
        mark_unsaved()
        self.report(
            {"INFO"}, f"Keymapper: Duplicated '{original.get('display_name', '')}'."
        )
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ShowConflictInfo(Operator):
    """Show conflict info tooltip."""

    bl_idname = "keymapper.show_conflict_info"
    bl_label = "Conflict"
    bl_description = "This entry has a conflict"
    bl_options = {"INTERNAL"}
    conflict_type: StringProperty(default="")
    wins: bpy.props.BoolProperty(default=True)
    conflict_count: bpy.props.IntProperty(default=1)
    # JSON string: [{"type": str, "count": int, "wins": bool}, ...]
    all_conflicts: StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        # Try to build a full summary from all_conflicts
        import json as _j

        all_raw = properties.all_conflicts
        if all_raw:
            try:
                all_conf = _j.loads(all_raw)
            except Exception:
                all_conf = []
        else:
            all_conf = []

        if not all_conf:
            # Fallback to single conflict
            all_conf = [
                {
                    "type": properties.conflict_type,
                    "count": properties.conflict_count,
                    "wins": properties.wins,
                }
            ]

        lines = []
        for c in all_conf:
            t = c.get("type", "")
            n = c.get("count", 1)
            w = c.get("wins", True)
            others = f"{n} other {'entry' if n == 1 else 'entries'}"
            if t == "duplicate":
                redundant = f"{n} {'entry is' if n == 1 else 'entries are'} redundant"
                lines.append(
                    f"Duplicate — identical keybind, context and operator as {others}. {redundant}"
                )
            elif t == "key_conflict":
                if not w:
                    lines.append(
                        f"Key conflict — same keybind and context as {others}. This entry is registered later and may not fire"
                    )
                else:
                    lines.append(
                        f"Key conflict — same keybind and context as {others}. First registered wins"
                    )
            elif t == "op_overlap":
                lines.append(
                    f"Operator overlap — same operator and context as {others}, mapped under a different keybind"
                )
            elif t == "event_soft":
                lines.append(
                    f"Event overlap — PRESS and CLICK on the same key as {others} can both fire in sequence"
                )

        return (
            " | ".join(lines)
            if lines
            else "This entry has a conflict with another Keymapper entry"
        )

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_InertDuplicateInfo(Operator):
    """Inert-duplicate info tooltip (non-interactive)."""

    bl_idname = "keymapper.inert_duplicate_info"
    bl_label = "Identical Duplicate"
    bl_options = {"INTERNAL"}
    twin_name: StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        tn = properties.twin_name or "another shortcut entry"
        return (
            f"This shortcut entry is identical to \"{tn}\".\n"
            "It stays inactive while identical. Change its keybinding or "
            "operators to make it a normal entry."
        )

    def execute(self, context):
        return {"CANCELLED"}


class KEYMAPPER_OT_AdoptedInfo(Operator):
    """Adopted-KMI info tooltip (non-interactive)."""

    bl_idname = "keymapper.adopted_info"
    bl_label = "Identical to default KMIs"
    bl_options = {"INTERNAL"}
    entry_id: StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        from . import keymap_manager as _km
        from .panel import _combo_label
        recs = _km._adoption_display.get(properties.entry_id) or []
        if not recs:
            return "This entry is identical to a pre-existing KMI."

        # Resolve the layer each adopted binding lives in, preserving first-seen
        # order for a stable, readable sentence.
        layers = []
        for (km_name, op_id, sig) in recs:
            try:
                lyr = _km._adopted_layer_label(km_name, op_id, sig)
            except Exception:
                lyr = "User"
            if lyr not in layers:
                layers.append(lyr)

        def _quoted_list(items):
            q = [f'"{i}"' for i in items]
            if len(q) == 1:
                return q[0]
            if len(q) == 2:
                return f"{q[0]} and {q[1]}"
            return ", ".join(q[:-1]) + f", and {q[-1]}"

        plural = len(recs) > 1
        subject = ("This entry has identical KMIs to pre-existing KMIs in the "
                   if plural
                   else "This entry is identical to a pre-existing KMI in the ")
        layer_phrase = _quoted_list(layers)
        layer_word = "layers" if len(layers) > 1 else "layer"
        lines = [f"{subject}{layer_phrase} {layer_word}."]

        for (km_name, op_id, sig) in recs:
            try:
                combo = _combo_label(False, sig[2], sig[3], sig[4], sig[5],
                                     "", sig[0], sig[1])
            except Exception:
                combo = sig[0]
            lines.append(f"• {op_id}  —  {km_name}  —  {combo}")
        return "\n".join(lines)

    def execute(self, context):
        return {"CANCELLED"}


class KEYMAPPER_OT_AddExtraKeybind(Operator):
    """Add an additional keybind slot to this shortcut entry"""

    bl_idname = "keymapper.add_extra_keybind"
    bl_label = "Add Keybind"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        import json

        wm = context.window_manager
        try:
            extras = json.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]")
        except Exception:
            extras = []
        slot = len(extras) + 1  # slot 1 = first extra
        _ensure_extra_scratch_kmi(slot)
        extras.append({"slot": slot})
        wm["keymapper_extra_keybinds"] = json.dumps(extras)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_RemoveExtraKeybindAt(Operator):
    """Remove a specific extra keybind slot by index"""

    bl_idname = "keymapper.remove_extra_keybind_at"
    bl_label = "Remove Keybind"
    bl_options = {"INTERNAL"}

    slot_index: IntProperty()

    def execute(self, context):
        import json

        wm = context.window_manager
        try:
            extras = json.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]")
        except Exception:
            extras = []
        if self.slot_index >= len(extras):
            return {"CANCELLED"}
        # Remove from list
        extras.pop(self.slot_index)
        # Rebuild scratch KMIs — shift all slots down by re-copying values
        try:
            kc = bpy.context.window_manager.keyconfigs.addon
            km = kc.keymaps.get(_SCRATCH_KM_NAME)
            if km:
                # Remove the last scratch KMI (we'll shift values down)
                if len(km.keymap_items) > 1:
                    km.keymap_items.remove(km.keymap_items[-1])
                # Re-sync remaining slots from their new positions
                for new_idx, _ in enumerate(extras):
                    new_slot = new_idx + 1
                    old_slot = new_idx + 1 if new_idx < self.slot_index else new_idx + 2
                    if (
                        old_slot < len(km.keymap_items) + 1
                        and new_slot < len(km.keymap_items) + 1
                    ):
                        pass  # already in correct position after removal
        except Exception as e:
            print(f"[Keymapper] remove_at error: {e}")
        # Rebuild slot list
        wm["keymapper_extra_keybinds"] = json.dumps(
            [{"slot": i + 1} for i in range(len(extras))]
        )
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_RemoveExtraKeybind(Operator):
    """Remove the last additional keybind slot"""

    bl_idname = "keymapper.remove_extra_keybind"
    bl_label = "Remove Keybind"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        import json

        wm = context.window_manager
        try:
            extras = json.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]")
        except Exception:
            extras = []
        if extras:
            extras.pop()
            # Remove last extra scratch KMI
            try:
                kc = bpy.context.window_manager.keyconfigs.addon
                km = kc.keymaps.get(_SCRATCH_KM_NAME)
                if km and len(km.keymap_items) > 1:
                    km.keymap_items.remove(km.keymap_items[-1])
            except Exception:
                pass
            wm["keymapper_extra_keybinds"] = json.dumps(extras)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_SetExtraKeybindProp(Operator):
    """Set a property on an extra keybind slot"""

    bl_idname = "keymapper.set_extra_keybind_prop"
    bl_label = "Set Keybind Property"
    bl_options = {"INTERNAL"}

    slot_index: IntProperty()
    prop_name: StringProperty()
    prop_value: StringProperty()

    def execute(self, context):
        import json

        wm = context.window_manager
        try:
            extras = json.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]")
        except Exception:
            extras = []
        if self.slot_index >= len(extras):
            return {"CANCELLED"}
        slot = extras[self.slot_index]
        if self.prop_name == "any":
            slot["any"] = not slot.get("any", False)
        elif self.prop_name in ("shift", "ctrl", "alt", "oskey"):
            slot[self.prop_name] = not slot.get(self.prop_name, False)
        else:
            slot[self.prop_name] = self.prop_value
        extras[self.slot_index] = slot
        wm["keymapper_extra_keybinds"] = json.dumps(extras)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ClearSelection(Operator):
    """Deselect all entries and folders"""

    bl_idname = "keymapper.clear_selection"
    bl_label = "Clear Selection"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        wm.keymapper.selected_index = -1
        if getattr(wm, "keymapper_selected_folder_id", ""):
            wm.keymapper_selected_folder_id = ""
        if getattr(wm, "keymapper_renaming_folder_id", ""):
            wm.keymapper_renaming_folder_id = ""
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_SelectEntry(Operator):
    bl_idname = "keymapper.select_entry"
    bl_label = "Select Entry"
    bl_description = "Select this shortcut entry"
    bl_options = {"INTERNAL"}
    index: IntProperty()

    def execute(self, context):
        if self.index >= 0:
            wm = context.window_manager
            wm.keymapper.selected_index = self.index
            # Leave conflict-focus mode when an entry OUTSIDE the focused
            # conflict is selected (selecting one of the conflicting entries
            # keeps the focus, since that's what the user is working on).
            _focus = wm.get("keymapper_conflict_focus", "")
            if _focus:
                try:
                    from .panel import _conflict_focus_set

                    _ids, _ = _conflict_focus_set(context)
                    _ents = persistence.get_entries()
                    _sel_id = (_ents[self.index].get("entry_id", "")
                               if 0 <= self.index < len(_ents) else "")
                    if _ids is None or _sel_id not in _ids:
                        wm["keymapper_conflict_focus"] = ""
                except Exception:
                    wm["keymapper_conflict_focus"] = ""
            # The active folder follows the selected entry's own folder, so the
            # viewed folder doesn't jump (both panels share this property now).
            entries = persistence.get_entries()
            if 0 <= self.index < len(entries):
                wm.keymapper_selected_folder_id = entries[self.index].get("folder_id", "")
            if getattr(wm, "keymapper_renaming_folder_id", ""):
                wm.keymapper_renaming_folder_id = ""
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleExpand(Operator):
    bl_idname = "keymapper.toggle_expand"
    bl_label = "Toggle Expand"
    bl_description = "Expand or collapse this entry"
    bl_options = {"INTERNAL"}
    entry_id: StringProperty()
    field: StringProperty(default="expanded_entry")

    def execute(self, context):
        entry = persistence.get_entry_by_id(self.entry_id)
        if entry:
            entry[self.field] = not entry.get(self.field, False)
            persistence._write_to_prefs()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleEnabled(Operator):
    bl_idname = "keymapper.toggle_enabled"
    bl_label = "Toggle Enabled"
    bl_description = "Enable or disable this shortcut entry"
    bl_options = {"INTERNAL"}
    entry_id: StringProperty()

    def execute(self, context):
        if self.entry_id == "__preview__":
            # Entry not saved yet: flip the form-level flag the preview card
            # reads, so a new entry can be created already disabled.
            wm = context.window_manager
            wm["keymapper_form_enabled"] = not bool(
                wm.get("keymapper_form_enabled", True))
            _redraw(context)
            return {"FINISHED"}
        entry = persistence.get_entry_by_id(self.entry_id)
        if entry:
            new_enabled = not entry.get("enabled", True)
            # Block enabling an inert duplicate (identical to an earlier entry).
            # The greyed checkbox + warning-icon tooltip already explain this, so
            # don't print anything to the console.
            if new_enabled:
                from . import conflict_detector
                if conflict_detector.is_inert_duplicate(entry):
                    return {"CANCELLED"}
            entry["enabled"] = new_enabled
            persistence._write_to_prefs()
            mark_unsaved()
            from . import keymap_manager

            if new_enabled:
                keymap_manager.reactivate_entry(entry)
            else:
                keymap_manager.deactivate_entry(entry)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_IconItem(bpy.types.PropertyGroup):
    icon_id: StringProperty()


class KEYMAPPER_UL_icons(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_prop, index):
        layout.label(text=item.icon_id, icon=item.icon_id or "BLANK1")

    def draw_filter(self, context, layout):
        pass


def _icon_categories_enum(self, context):
    return KEYMAPPER_OT_PickIcon._enum_cache


class KEYMAPPER_OT_PickIcon(Operator):
    bl_idname = "keymapper.pick_icon"
    bl_label = "Choose Icon"
    bl_description = "Pick a custom icon for this entry"
    bl_options = {"INTERNAL"}
    entry_id: StringProperty()

    _enum_cache = [("ALL", "All", "")]

    def invoke(self, context, event):
        wm = context.window_manager
        if self.entry_id:
            entry = persistence.get_entry_by_id(self.entry_id)
            wm.keymapper_icon_pick = entry.get("custom_icon", "") if entry else ""
        else:
            wm.keymapper_icon_pick = wm.get("keymapper_form_pending_icon", "")
        wm.keymapper_icon_filter = ""
        # Resolve the AUTO icon (operators only, ignoring any custom_icon) for
        # the "Current Icon:" preview so Reset-to-Auto shows the right thing.
        try:
            from .panel import safe_icon
            from .database.op_icons import get_op_icon, FALLBACK_ICON
            import json as _json
            if self.entry_id:
                _e = persistence.get_entry_by_id(self.entry_id)
                _ops = _json.loads(_e.get("operator_ids", "[]")) if _e else []
                _auto = get_op_icon(_ops[0]["id"]) if _ops else FALLBACK_ICON
            else:
                _auto = FALLBACK_ICON
            wm["keymapper_icon_current"] = safe_icon(_auto, "DOT")
        except Exception:
            wm["keymapper_icon_current"] = "DOT"
        self._build_categories(context)
        self._populate(context)
        # Preselect the current icon in the list, if present.
        coll = wm.keymapper_icon_items
        cur = wm.keymapper_icon_pick
        wm.keymapper_icon_index = -1
        if cur:
            for i, it in enumerate(coll):
                if it.icon_id == cur:
                    wm.keymapper_icon_index = i
                    break
        return wm.invoke_props_dialog(self, width=420, confirm_text="Confirm")

    def _build_categories(self, context):
        from .panel import _get_valid_icons
        skip = {"NONE", "BLANK1"}
        icons = [i for i in sorted(_get_valid_icons()) if i not in skip]
        order, buckets = self._categorize(icons)
        cls = KEYMAPPER_OT_PickIcon
        cls._buckets = buckets
        enum = [("ALL", f"All  ({len(icons)})", "")]
        for cat in order:
            enum.append((cat, f"{cat}  ({len(buckets[cat])})", ""))
        cls._enum_cache = enum

    def _populate(self, context):
        KEYMAPPER_OT_PickIcon._populate_static(context)

    @staticmethod
    def _populate_static(context):
        wm = context.window_manager
        coll = wm.keymapper_icon_items
        coll.clear()
        cat = wm.keymapper_icon_category
        flt = (wm.keymapper_icon_filter or "").strip().upper()
        cls = KEYMAPPER_OT_PickIcon
        if cat == "ALL" or not getattr(cls, "_buckets", None):
            from .panel import _get_valid_icons
            src = [i for i in sorted(_get_valid_icons())
                   if i not in {"NONE", "BLANK1"}]
        else:
            src = cls._buckets.get(cat, [])
        for ic in src:
            if flt and flt not in ic:
                continue
            it = coll.add()
            it.icon_id = ic
        # Keep the highlighted row pointing at the current pick (by name),
        # not a stale index position.
        cls._syncing = True
        pick = wm.keymapper_icon_pick
        new_idx = -1
        if pick:
            for i, it in enumerate(coll):
                if it.icon_id == pick:
                    new_idx = i
                    break
        wm.keymapper_icon_index = new_idx
        cls._syncing = False

    # Prefix -> friendly category name.
    _CATEGORIES = [
        ("MESH_", "Mesh"),
        ("MOD_", "Modifiers"),
        ("OUTLINER_OB_", "Object Types"),
        ("OUTLINER_", "Outliner"),
        ("MATERIAL", "Material / Shading"),
        ("SHADING_", "Material / Shading"),
        ("NODE", "Nodes"),
        ("BRUSH_", "Brushes"),
        ("SCULPT", "Brushes"),
        ("PARTICLE", "Physics / Particles"),
        ("PHYSICS", "Physics / Particles"),
        ("FORCE_", "Physics / Particles"),
        ("CONSTRAINT", "Constraints"),
        ("BONE_", "Armature"),
        ("ARMATURE", "Armature"),
        ("POSE_", "Armature"),
        ("ANIM", "Animation"),
        ("KEYFRAME", "Animation"),
        ("ACTION", "Animation"),
        ("DRIVER", "Animation"),
        ("SEQ", "Sequencer / Video"),
        ("IMAGE", "Image / UV"),
        ("UV", "Image / UV"),
        ("RENDER", "Render"),
        ("OUTPUT", "Render"),
        ("CAMERA", "Camera"),
        ("LIGHT", "Light"),
        ("WORLD", "World / Scene"),
        ("SCENE", "World / Scene"),
        ("FILE", "File / Folder"),
        ("EXPORT", "File / Folder"),
        ("IMPORT", "File / Folder"),
        ("CURRENT_FILE", "File / Folder"),
        ("DISK_", "File / Folder"),
        ("SORT", "Arrows / Sort"),
        ("TRIA_", "Arrows / Sort"),
        ("ARROW_", "Arrows / Sort"),
        ("BACK", "Arrows / Sort"),
        ("FORWARD", "Arrows / Sort"),
        ("PLAY", "Playback"),
        ("PAUSE", "Playback"),
        ("REW", "Playback"),
        ("FF_", "Playback"),
        ("FRAME_", "Playback"),
        ("SNAP_", "Snapping"),
        ("PIVOT_", "Pivot / Orientation"),
        ("ORIENTATION_", "Pivot / Orientation"),
        ("CON_", "Constraints"),
        ("GP_", "Grease Pencil"),
        ("GREASEPENCIL", "Grease Pencil"),
        ("STROKE", "Grease Pencil"),
        ("COLOR", "Color"),
        ("BRUSHES_ALL", "Brushes"),
        ("RESTRICT_", "Toggles / Restrict"),
        ("HIDE_", "Toggles / Restrict"),
        ("LOCKED", "Toggles / Restrict"),
        ("UNLOCKED", "Toggles / Restrict"),
        ("CHECKBOX_", "Toggles / Restrict"),
        ("RADIOBUT_", "Toggles / Restrict"),
        ("EVENT_", "Keyboard Events"),
        ("MOUSE_", "Mouse Events"),
        ("MODIFIER", "Modifiers"),
        ("MESH_", "Mesh"),
        ("SURFACE_", "Curve / Surface"),
        ("CURVE_", "Curve / Surface"),
        ("CURVES_", "Curve / Surface"),
        ("HANDLE_", "Curve / Surface"),
        ("PROP_", "Toggles / Restrict"),
        ("PMARKER", "Animation"),
        ("MARKER", "Animation"),
        ("TRACKING", "Motion Tracking"),
        ("CLIP", "Motion Tracking"),
        ("TRACKER", "Motion Tracking"),
        ("SOLO_", "Motion Tracking"),
        ("KEYINGSET", "Animation"),
        ("DECORATE", "Animation"),
        ("GHOST_", "Toggles / Restrict"),
        ("VIS_SEL", "Toggles / Restrict"),
        ("SELECT_", "Selection"),
        ("PIVOT_", "Pivot / Orientation"),
        ("GIZMO", "Pivot / Orientation"),
        ("EMPTY_", "Object Types"),
        ("MESH_DATA", "Object Types"),
        ("FONT_", "Text"),
        ("SMALL_CAPS", "Text"),
        ("SYNTAX_", "Text"),
        ("ALIGN_", "Text"),
        ("BOLD", "Text"),
        ("ITALIC", "Text"),
        ("UNDERLINE", "Text"),
        ("LINENUMBERS", "Text"),
        ("WORDWRAP", "Text"),
        ("SORTALPHA", "Arrows / Sort"),
        ("SORTBYEXT", "Arrows / Sort"),
        ("SORTSIZE", "Arrows / Sort"),
        ("SORTTIME", "Arrows / Sort"),
        ("ZOOM_", "View / Zoom"),
        ("VIEW", "View / Zoom"),
        ("VIEWZOOM", "View / Zoom"),
        ("FULLSCREEN", "View / Zoom"),
        ("SCREEN_BACK", "View / Zoom"),
        ("WINDOW", "Window / Workspace"),
        ("WORKSPACE", "Window / Workspace"),
        ("SPLITSCREEN", "Window / Workspace"),
        ("MENU_", "Menus / UI"),
        ("COLLAPSEMENU", "Menus / UI"),
        ("PANEL_", "Menus / UI"),
        ("TOPBAR", "Menus / UI"),
        ("STATUSBAR", "Menus / UI"),
        ("PLUGIN", "Menus / UI"),
        ("PREFERENCES", "Menus / UI"),
        ("PROPERTIES", "Menus / UI"),
        ("TOOL_SETTINGS", "Tools"),
        ("TOOL_", "Tools"),
        ("SETTINGS", "Tools"),
        ("MODIFIER_", "Modifiers"),
        ("DISCLOSURE", "Arrows / Sort"),
        ("DOT", "Shapes / Symbols"),
        ("KEYFRAME", "Animation"),
        ("HANDLETYPE", "Curve / Surface"),
        ("COLORSET_", "Color"),
        ("COLLECTION_", "Collections"),
        ("COLLECTION", "Collections"),
        ("GROUP_", "Collections"),
        ("GROUP", "Collections"),
        ("LINK", "Collections"),
        ("LIBRARY_", "File / Folder"),
        ("ASSET_", "File / Folder"),
        ("FUND", "Shapes / Symbols"),
        ("HEART", "Shapes / Symbols"),
        ("FAKE_USER", "Shapes / Symbols"),
        ("SOLO_ON", "Shapes / Symbols"),
        ("ERROR", "Status / Info"),
        ("INFO", "Status / Info"),
        ("QUESTION", "Status / Info"),
        ("CANCEL", "Status / Info"),
        ("CHECKMARK", "Status / Info"),
        ("HELP", "Status / Info"),
        ("URL", "Status / Info"),
        ("BLENDER", "Status / Info"),
    ]

    def _categorize(self, icons):
        buckets = {}
        order = []
        for ic in icons:
            cat = None
            for prefix, name in self._CATEGORIES:
                if ic.startswith(prefix):
                    cat = name
                    break
            if cat is None:
                cat = "Misc"
            if cat not in buckets:
                buckets[cat] = []
                order.append(cat)
            buckets[cat].append(ic)
        # Misc last
        order = [c for c in order if c != "Misc"]
        if "Misc" in buckets:
            order.append("Misc")
        return order, buckets

    def draw(self, context):
        wm = context.window_manager
        layout = self.layout

        _coll = wm.keymapper_icon_items
        _cur = wm.get("keymapper_icon_current", "") or "BLANK1"
        _sel = wm.keymapper_icon_pick or _cur

        r1 = layout.row(align=True)
        r1.label(text="Auto Icon:")
        r1.label(text="", icon=_cur)
        r1.separator()
        r1.label(text="Selected:")
        r1.label(text="", icon=_sel or "BLANK1")

        rnames = layout.row(align=True)
        rnames.label(text=_cur)
        rnames.separator()
        rnames.label(text=_sel)

        r2 = layout.row(align=True)
        r2.operator(
            "keymapper.set_icon_pick", text="Reset to Auto", icon="LOOP_BACK"
        ).value = ""

        r3 = layout.row(align=True)
        r3.prop(wm, "keymapper_icon_category", text="")
        r3.prop(wm, "keymapper_icon_filter", text="", icon="VIEWZOOM")

        layout.template_list(
            "KEYMAPPER_UL_icons", "",
            wm, "keymapper_icon_items",
            wm, "keymapper_icon_index",
            rows=16, type="DEFAULT",
            sort_lock=True,
        )

    def execute(self, context):
        wm = context.window_manager
        chosen = wm.keymapper_icon_pick or ""
        if self.entry_id:
            entry = persistence.get_entry_by_id(self.entry_id)
            if entry is not None:
                persistence.update_entry(self.entry_id, {"custom_icon": chosen})
                mark_unsaved()
        else:
            wm["keymapper_form_pending_icon"] = chosen
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleIconCat(Operator):
    bl_idname = "keymapper.toggle_icon_cat"
    bl_label = "Toggle Icon Category"
    bl_options = {"INTERNAL"}
    cat_key: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        wm[self.cat_key] = not wm.get(self.cat_key, False)
        return {"FINISHED"}


class KEYMAPPER_OT_SetIconPick(Operator):
    bl_idname = "keymapper.set_icon_pick"
    bl_label = "Set Icon"
    bl_description = "Select this icon"
    bl_options = {"INTERNAL"}
    value: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        wm.keymapper_icon_pick = self.value
        if not self.value:
            wm.keymapper_icon_index = -1
        return {"FINISHED"}


class KEYMAPPER_OT_RestorePresetEntry(Operator):
    bl_idname = "keymapper.restore_preset_entry"
    bl_label = "Restore Preset Entry"
    bl_description = (
        "Revert this entry to its original preset definition "
        "(operators and keybind)"
    )
    bl_options = {"INTERNAL"}
    entry_id: StringProperty()

    def execute(self, context):
        from .database.presets import PRESET_STATE_FIELDS, find_preset_template

        entry = persistence.get_entry_by_id(self.entry_id)
        if not entry:
            return {"CANCELLED"}
        tpl = find_preset_template(entry)
        if not tpl:
            return {"CANCELLED"}

        from . import keymap_manager

        keymap_manager.deactivate_entry(entry)
        data = {f: tpl.get(f, "") for f in PRESET_STATE_FIELDS}
        persistence.update_entry(self.entry_id, data)
        entry = persistence.get_entry_by_id(self.entry_id)
        if entry and entry.get("enabled", True):
            keymap_manager.reactivate_entry(entry)
        mark_unsaved()
        _run_conflict_scan()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_AddEntry(Operator):
    """Shim — delegates to open_inline_form. Kept for preferences panel button."""

    bl_idname = "keymapper.add_entry"
    bl_label = "Add Shortcut Entry"
    bl_options = {"INTERNAL"}
    edit_entry_id: StringProperty(default="")

    def execute(self, context):
        if self.edit_entry_id:
            bpy.ops.keymapper.edit_entry(entry_id=self.edit_entry_id)
        else:
            bpy.ops.keymapper.open_inline_form()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


# ---------------------------------------------------------------------------
# JSON export / import (delegated from persistence)
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_FormBrowseSearch(Operator):
    """Searchable popup for operators with collapsed subcategories."""

    bl_idname = "keymapper.form_browse_search"
    bl_label = "Search Operators"
    bl_options = {"INTERNAL"}
    search_text: StringProperty(name="Search", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        from .database.bfa_ops import get_friendly_name, is_bfa_only
        from .database.categories import CATEGORIES
        from .database.op_properties import op_can_repeat

        wm = context.window_manager
        layout = self.layout
        layout.prop(
            self,
            "search_text",
            text="",
            icon="VIEWZOOM",
            placeholder="Search operators...",
        )
        search = self.search_text.lower().strip()
        op_mode = wm.get("keymapper_picked_mode", "FRIENDLY")
        use_friendly = op_mode == "FRIENDLY"
        host = "blender"
        try:
            from . import HOST_APP

            host = HOST_APP
        except Exception:
            pass

        # Get current selection
        from .operators import _get_sel_ops

        sel_ops = _get_sel_ops(wm)
        sel_ids = [o["id"] for o in sel_ops]

        for cat in CATEGORIES:
            if cat["id"] == "bforartists" and host != "bforartists":
                continue
            cat_has_results = False
            for sub in cat["subcategories"]:
                for op_id in sub["operators"]:
                    if is_bfa_only(op_id) and host != "bforartists":
                        continue
                    friendly = get_friendly_name(op_id)
                    display = (
                        (friendly if friendly else op_id) if use_friendly else op_id
                    )
                    friendly_lower = (friendly or "").lower()
                    if (
                        not search
                        or search in display.lower()
                        or search in op_id.lower()
                        or search in friendly_lower
                    ):
                        cat_has_results = True
                        break
                if cat_has_results:
                    break
            if not cat_has_results:
                continue

            cat_key = f"keymapper_subcat_search_{cat['id']}"
            is_open = bool(wm.get(cat_key, False)) or bool(search)
            cat_hdr = layout.row(align=True)
            tog = cat_hdr.operator(
                "keymapper.form_toggle_browse_subcat",
                text=cat["label"],
                icon="DOWNARROW_HLT" if is_open else "RIGHTARROW",
                emboss=False,
            )
            tog.key = f"search_{cat['id']}"

            if is_open:
                for sub in cat["subcategories"]:
                    sub_ops = []
                    for op_id in sub["operators"]:
                        if is_bfa_only(op_id) and host != "bforartists":
                            continue
                        friendly = get_friendly_name(op_id)
                        display = (
                            (friendly if friendly else op_id) if use_friendly else op_id
                        )
                        friendly_lower = (friendly or "").lower()
                        if (
                            not search
                            or search in display.lower()
                            or search in op_id.lower()
                            or search in friendly_lower
                        ):
                            sub_ops.append((op_id, display))
                    if not sub_ops:
                        continue
                    layout.label(text=f"  {sub['label']}")
                    sub_box = layout.box()
                    sub_box.scale_y = 0.85
                    for op_id, display in sub_ops:
                        is_picked = op_id in sel_ids
                        can_repeat = op_can_repeat(op_id)
                        row = sub_box.row(align=True)
                        if can_repeat:
                            count = sum(1 for o in sel_ops if o["id"] == op_id)
                            chip = sub_box.box()
                            chip_row = chip.row(align=True)
                            add_sub = chip_row.row(align=True)
                            add_sub.ui_units_x = 1
                            add_btn = add_sub.operator(
                                "keymapper.form_add_op", text="+", emboss=True
                            )
                            add_btn.operator_id = op_id
                            add_btn.use_friendly = use_friendly
                            rm_sub = chip_row.row(align=True)
                            rm_sub.ui_units_x = 1
                            rm_sub.enabled = count > 0
                            rm_btn = rm_sub.operator(
                                "keymapper.form_remove_last_op", text="-", emboss=True
                            )
                            rm_btn.operator_id = op_id
                            chip_row.separator(factor=0.5)
                            lbl_row = chip_row.row(align=True)
                            lbl_row.alignment = "CENTER"
                            lbl_row.label(text=display)
                            if count > 0:
                                badge = chip_row.row(align=True)
                                badge.alignment = "RIGHT"
                                badge.label(text=f"×{count}")
                        else:
                            btn = row.operator(
                                "keymapper.form_toggle_op",
                                text=display,
                                icon="CHECKBOX_HLT" if is_picked else "CHECKBOX_DEHLT",
                                depress=is_picked,
                            )
                            btn.operator_id = op_id
                            btn.use_friendly = use_friendly

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_FormSetOpContext(Operator):
    """Set the keymap context for a specific operator instance."""

    bl_idname = "keymapper.form_set_op_context"
    bl_label = "Set Operator Context"
    bl_description = "Set the keymap context for this operator"
    bl_options = {"INTERNAL"}
    op_index: bpy.props.IntProperty()
    context_name: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        ops = _get_sel_ops(wm)
        if 0 <= self.op_index < len(ops):
            if self.context_name:
                ops[self.op_index]["contexts"] = [self.context_name]
            else:
                ops[self.op_index]["contexts"] = []  # revert to Auto
            ops[self.op_index]["context"] = ""
            _set_sel_ops(wm, ops)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleOpContext(Operator):
    """Toggle a keymap context on/off for an operator instance.

    Respects the operator's `use_multi_contexts` flag: in single mode picking a
    context replaces the selection (clicking the active one clears to Auto); in
    multi mode it adds/removes from the list."""

    bl_idname = "keymapper.form_toggle_op_context"
    bl_label = "Toggle Operator Context"
    bl_description = "Add or remove this keymap context for the operator"
    bl_options = {"INTERNAL"}
    op_index: bpy.props.IntProperty()
    context_name: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        ops = _get_sel_ops(wm)
        if 0 <= self.op_index < len(ops):
            op = ops[self.op_index]
            ctxs = list(op.get("contexts", []))
            # migrate legacy single context into the list on first touch
            if not ctxs and op.get("context"):
                ctxs = [op["context"]]
            multi = bool(op.get("use_multi_contexts", False))
            if multi:
                if self.context_name in ctxs:
                    ctxs.remove(self.context_name)
                else:
                    ctxs.append(self.context_name)
            else:
                ctxs = [] if ctxs == [self.context_name] else [self.context_name]
            op["contexts"] = ctxs
            op["context"] = ""  # contexts list is now the source of truth
            _set_sel_ops(wm, ops)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleOpFlag(Operator):
    """Toggle a per-operator boolean flag (use_multi_contexts / expand_contexts).

    When multi-context is turned OFF, the selection is collapsed immediately to a
    single context (the auto-resolved one if present, else the first)."""

    bl_idname = "keymapper.form_toggle_op_flag"
    bl_label = "Toggle Operator Option"
    bl_options = {"INTERNAL"}
    op_index: bpy.props.IntProperty()
    flag: StringProperty()

    @classmethod
    def description(cls, context, props):
        if props.flag == "use_multi_contexts":
            return (
                "Using multiple contexts for an operator means that a keymap "
                "will be generated for each selected context"
            )
        return (
            "Enable operators to be placed outside of their intended contexts. "
            "This can override many key bindings if used in a context that has "
            "authority over others, thereby disabling many default KMIs. "
            "Use at own risk"
        )

    def execute(self, context):
        wm = context.window_manager
        ops = _get_sel_ops(wm)
        if 0 <= self.op_index < len(ops):
            op = ops[self.op_index]
            newval = not bool(op.get(self.flag, False))
            op[self.flag] = newval
            ctxs = list(op.get("contexts", []))
            if not ctxs and op.get("context"):
                ctxs = [op["context"]]
            if self.flag == "expand_contexts" and not newval and ctxs:
                # Drop only contexts that aren't valid curated options; keep any
                # legitimate curated pick (e.g. 3D View) regardless of which
                # keymaps the operator physically lives in.
                from .database.keymap_contexts import KEYMAP_CONTEXTS as _AC

                curated = {c[0] for c in _AC}
                ctxs = [c for c in ctxs if c in curated]
                op["contexts"] = ctxs
                op["context"] = ""
            if self.flag == "use_multi_contexts" and not newval and len(ctxs) > 1:
                auto = ""
                try:
                    from .keymap_manager import _get_keymap_for_op

                    auto = _get_keymap_for_op(op.get("id", ""))
                except Exception:
                    auto = ""
                keep = auto if auto in ctxs else ctxs[0]
                op["contexts"] = [keep]
                op["context"] = ""
            _set_sel_ops(wm, ops)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleCtxGroup(Operator):
    """Collapse/expand a context category in the operator's context dropdown."""

    bl_idname = "keymapper.form_toggle_ctx_group"
    bl_label = "Toggle Context Group"
    bl_description = "Expand or collapse this context category"
    bl_options = {"INTERNAL"}
    op_index: bpy.props.IntProperty()
    group_id: StringProperty()
    default_open: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        wm = context.window_manager
        key = f"keymapper_ctxgrp_{self.op_index}_{self.group_id}"
        wm[key] = not wm.get(key, self.default_open)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormSearchContext(Operator):
    """Open a searchable list of keymap contexts for an operator instance."""

    bl_idname = "keymapper.form_search_context"
    bl_label = "Search Keymap Context"
    bl_options = {"INTERNAL"}
    op_index: bpy.props.IntProperty()
    search_text: StringProperty(name="Search", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=380)

    def draw(self, context):
        from .database.keymap_contexts import GROUP_LABELS, get_contexts_by_group

        wm = context.window_manager
        layout = self.layout
        layout.prop(
            self,
            "search_text",
            text="",
            icon="VIEWZOOM",
            placeholder="Search context...",
        )
        search = self.search_text.lower()
        groups = get_contexts_by_group()
        for group_id, entries in groups.items():
            filtered = [e for e in entries if not search or search in e[0].lower()]
            if not filtered:
                continue
            group_label = GROUP_LABELS.get(group_id, group_id)
            # Collapsed by default — expanded when searching
            open_key = f"keymapper_ctxgrp_{group_id}"
            is_open = bool(wm.get(open_key, False)) or bool(search)
            hdr = layout.row(align=True)
            tog = hdr.operator(
                "keymapper.form_toggle_context_group",
                text=group_label,
                icon="DOWNARROW_HLT" if is_open else "RIGHTARROW",
                emboss=False,
            )
            tog.group_id = group_id
            if is_open:
                col = layout.column(align=True)
                col.scale_y = 0.85
                for km_name, space, region, _ in filtered:
                    op = col.operator(
                        "keymapper.form_set_op_context",
                        text=km_name,
                        emboss=True,
                    )
                    op.op_index = self.op_index
                    op.context_name = km_name

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_FormSearchPropValue(Operator):
    """Open a searchable list of valid values for an operator property."""

    bl_idname = "keymapper.form_search_prop_value"
    bl_label = "Search Property Value"
    bl_options = {"INTERNAL"}
    op_index: bpy.props.IntProperty()
    prop_name: StringProperty()
    values_from: StringProperty()
    # Scratch search text
    search_text: StringProperty(name="Search", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(
            self, "search_text", text="", icon="VIEWZOOM", placeholder="Search..."
        )
        if not self.values_from:
            layout.label(text="Enter value:")
            layout.prop(self, "search_text", text="")
            return
        from .database.op_properties import get_prop_values

        values = get_prop_values(self.values_from)
        search = self.search_text.lower()
        col = layout.column(align=True)
        col.scale_y = 0.85
        shown = 0
        for vid, vlbl in values:
            # Group header sentinel
            if vid == "__GROUP_HEADER__":
                if not search:  # only show headers when not searching
                    col.separator(factor=0.5)
                    hdr = col.row(align=True)
                    hdr.enabled = False
                    hdr.label(text=f"· {vlbl}")
                continue
            if search and search not in vid.lower() and search not in vlbl.lower():
                continue
            if shown >= 50:
                break
            row = col.row(align=True)
            op = row.operator(
                "keymapper.form_set_op_prop", text=f"{vlbl}  ({vid})", emboss=True
            )
            op.op_index = self.op_index
            op.prop_name = self.prop_name
            op.prop_value = vid
            shown += 1

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleSimplifiedBrowse(Operator):
    """Switch the Browse Operators panel between the full list and the
    simplified multi-operator view."""

    bl_idname = "keymapper.toggle_simplified_browse"
    bl_label = "Browse Mode"
    bl_options = {"INTERNAL"}

    @classmethod
    def description(cls, context, properties):
        m = int(getattr(properties, "mode", 0))
        if m == 1:
            return (
                "Simplified view narrowing down multiple operators down to "
                "multi-operators. Multi-operators contain multiple operators "
                "derived from the factory keyconfig currently in use, making it "
                "easier to find shortcuts that often do the same thing but in "
                "other contexts with a logically similar but mechanically "
                "different operator"
            )
        if m == 2:
            return (
                "Browse every binding the factory keyconfig actually uses, "
                "including each operator's properties. Grouped into families "
                "of the same operator that differ only in their property "
                "values, e.g. the twelve ways View Axis is bound"
            )
        return "Browse every available operator"

    mode: IntProperty(default=0)

    def execute(self, context):
        wm = context.window_manager
        # 0 = All operators, 1 = Simplified (multi-ops), 2 = Factory bindings.
        wm["keymapper_browse_mode"] = int(self.mode)
        # Category ids differ between the views, so reset the selection.
        _wm_set(wm, WM_CATEGORY, "")
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleMultiOp(Operator):
    """Add or remove every operator of a multi-operator in one go."""

    bl_idname = "keymapper.form_toggle_multi_op"
    bl_label = "Toggle Multi-Operator"
    bl_options = {"INTERNAL"}
    multi_id: StringProperty()

    @classmethod
    def description(cls, context, properties):
        from .database.multi_ops import get_multi_op

        m = get_multi_op(properties.multi_id)
        if not m:
            return "Add or remove these operators from the selection"
        kbs = m.get("all_keybinds") or [m["keybind_label"]]
        head = ("Factory Keybinds = " + ", ".join(kbs)) if len(kbs) > 1 \
            else f"Factory Keybind = {kbs[0]}"
        if m.get("variants"):
            lines = [head, m["operators"][0],
                     "Properties set per context:"]
            for v in m["variants"]:
                pv = ", ".join(f"{k}={val}" for k, val in v["props"].items())
                lines.append("• " + ", ".join(v["contexts"]) + ": " + pv)
            return "\n".join(lines)
        lines = [head, f"{len(m['operators'])} operators:"]
        lines += [f"• {o}" for o in m["operators"]]
        return "\n".join(lines)

    def execute(self, context):
        from .database.multi_ops import get_multi_op

        wm = context.window_manager
        m = get_multi_op(self.multi_id)
        if not m:
            return {"CANCELLED"}
        # Prop-variant cluster: one op INSTANCE per (props, contexts) variant —
        # the same operator id repeated with per-context props. Toggle the
        # whole set together.
        if m.get("variants"):
            sel = _get_sel_ops(wm)
            op_id = m["operators"][0]
            var_props = [v["props"] for v in m["variants"]]
            # "Already selected" means ALL of this cluster's variants are in
            # the selection — matching the panel's highlight rule. Testing
            # only the first one made an overlapping cluster look selected.
            _have = [(o.get("props") or {}) for o in sel
                     if o.get("id") == op_id]
            present = bool(var_props) and all(vp in _have for vp in var_props)
            if present:
                sel = [o for o in sel
                       if not (o.get("id") == op_id
                               and (o.get("props") or {}) in var_props)]
            else:
                for v in m["variants"]:
                    sel.append({
                        "id": op_id,
                        "props": dict(v["props"]),
                        "contexts": list(v["contexts"]),
                    })
            _set_sel_ops(wm, sel)
            _redraw(context)
            return {"FINISHED"}
        # Membership must match on (id, props), NOT id alone: two multi-ops can
        # bundle the exact same operators and differ only in properties —
        # Delete (Next Character) and Delete (Previous Character) are both
        # {console.delete, text.delete}, distinguished purely by type=. Matching
        # on id alone made selecting one appear to select the other, and
        # removing one would have stripped the other's operators too.
        want = dict(m["props"])

        def _same(o):
            return (o.get("id") in member_ids
                    and (o.get("props") or {}) == want)

        sel = _get_sel_ops(wm)
        member_ids = set(m["operators"])
        present = {o.get("id") for o in sel if _same(o)}
        if member_ids and member_ids.issubset(present):
            # All present with these exact props -> remove just those.
            sel = [o for o in sel if not _same(o)]
        else:
            ctx_map = m.get("contexts") or {}
            for op_id in member_ids:
                if op_id in present:
                    continue
                # Set the operator's contexts EXPLICITLY from the factory
                # keyconfig instead of leaving auto-resolution to figure it out.
                # These come from the keymap where this exact keybind+props
                # binding actually lives, which is narrower (and thus safer)
                # than the auto-context, which returns every keymap the operator
                # appears in anywhere. Falls back to auto ([]) if unknown.
                sel.append({
                    "id": op_id,
                    "props": dict(want),
                    "contexts": list(ctx_map.get(op_id, [])),
                })
        _set_sel_ops(wm, sel)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FormToggleFactoryBinding(Operator):
    """Add or remove a single factory binding (operator + its properties)."""

    bl_idname = "keymapper.form_toggle_factory_binding"
    bl_label = "Toggle Factory Binding"
    bl_options = {"INTERNAL"}
    binding_id: StringProperty()

    @classmethod
    def description(cls, context, properties):
        from .database.multi_ops import get_factory_binding

        b = get_factory_binding(properties.binding_id)
        if not b:
            return "Add or remove this operator from the selection"
        kbs = b.get("all_keybinds") or [b["keybind_label"]]
        head = ("Factory Keybinds = " + ", ".join(kbs)) if len(kbs) > 1 \
            else f"Factory Keybind = {kbs[0]}"
        lines = [head, b["op_id"]]
        if b.get("variants"):
            lines.append("Properties set per context:")
            for v in b["variants"]:
                pv = ", ".join(f"{k}={val}" for k, val in v["props"].items())
                lines.append("• " + ", ".join(v["contexts"]) + ": " + pv)
        elif b["props"]:
            lines += [f"• {k} = {v}" for k, v in b["props"].items()]
        if not b.get("variants") and b["contexts"]:
            lines.append("Contexts: " + ", ".join(b["contexts"]))
        return "\n".join(lines)

    def execute(self, context):
        from .database.multi_ops import get_factory_binding

        wm = context.window_manager
        b = get_factory_binding(self.binding_id)
        if not b:
            return {"CANCELLED"}
        sel = _get_sel_ops(wm)
        # Merged context-variant row: one op INSTANCE per (props, contexts)
        # variant — same operator id repeated with per-context props. Toggling
        # adds or removes the whole set together.
        variants = b.get("variants")
        if variants:
            present = any(
                o.get("id") == b["op_id"]
                and (o.get("props") or {}) == variants[0]["props"]
                for o in sel)
            if present:
                var_props = [v["props"] for v in variants]
                sel = [o for o in sel
                       if not (o.get("id") == b["op_id"]
                               and (o.get("props") or {}) in var_props)]
            else:
                for v in variants:
                    sel.append({
                        "id": b["op_id"],
                        "props": dict(v["props"]),
                        "contexts": list(v["contexts"]),
                    })
            _set_sel_ops(wm, sel)
            _redraw(context)
            return {"FINISHED"}
        want = dict(b["props"])
        # Match on (id, props): the same operator appears many times with
        # different properties, and they are different actions.
        idx = next((i for i, o in enumerate(sel)
                    if o.get("id") == b["op_id"]
                    and (o.get("props") or {}) == want), None)
        if idx is not None:
            sel.pop(idx)
        else:
            sel.append({
                "id": b["op_id"],
                "props": want,
                "contexts": list(b["contexts"]),
            })
        _set_sel_ops(wm, sel)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_RefreshOperators(Operator):
    """Refresh the live operator cache. Run after enabling new addons."""

    bl_idname = "keymapper.refresh_operators"
    bl_label = "Refresh Operators"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from .database.dynamic_ops import invalidate_cache as _inv_dyn
        from .operator_discovery import deep_scan, refresh

        refresh()
        deep_scan()
        _inv_dyn()
        self.report({"INFO"}, "Keymapper: Operator cache refreshed.")
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_DeepScanOperators(Operator):
    """Deep scan ALL operators to find ones from addons that register
    under existing prefixes (e.g. Node Wrangler). Replaces previous results."""

    bl_idname = "keymapper.deep_scan_operators"
    bl_label = "Deep Scan"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from .operator_discovery import deep_scan

        count = deep_scan()
        self.report({"INFO"}, f"Keymapper: Deep scan found {count} unlisted operators.")
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ExportJSON(Operator):
    bl_idname = "keymapper.export_json"
    bl_label = "Export Keymapper JSON"
    bl_description = "Export all shortcut entries to a JSON file"
    filepath: StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        self.filepath = "keymapper_export.json"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        import json

        from . import persistence as pers

        path = bpy.path.abspath(self.filepath)
        try:
            export_data = {
                "folders": pers.get_folders(),
                "entries": pers.get_entries(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            self.report(
                {"INFO"},
                f"Keymapper: Exported {len(pers.get_entries())} entries and {len(pers.get_folders())} folders to {path}",
            )
        except Exception as e:
            self.report({"ERROR"}, f"Keymapper export failed: {e}")
        return {"FINISHED"}


class KEYMAPPER_OT_ImportJSON(Operator):
    bl_idname = "keymapper.import_json"
    bl_label = "Import Keymapper JSON"
    bl_description = "Import shortcut entries from a JSON file"
    filepath: StringProperty(subtype="FILE_PATH")
    mode: EnumProperty(
        name="Import Mode",
        items=[
            ("REPLACE", "Replace Everything",
             "Remove all current entries and folders, then import the file"),
            ("ADD", "Add To Existing",
             "Keep current entries and folders and add the imported ones"),
        ],
        default="REPLACE",
    )

    def invoke(self, context, event):
        from . import persistence as pers

        self.filepath = ""
        # Only ask when there is something to lose; a fresh setup goes
        # straight to the file browser.
        if pers.get_entries() or pers.get_folders():
            return context.window_manager.invoke_props_dialog(
                self, width=340, confirm_text="Choose File..."
            )
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="You already have shortcut entries.")
        col.label(text="What should the import do with them?")
        col.separator()
        col.prop(self, "mode", expand=True)

    def execute(self, context):
        # Stage 2 of the dialog chain: the props dialog confirms with no
        # filepath yet — open the file browser; the browser then re-invokes
        # execute with the chosen path.
        if not self.filepath:
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        import json
        import os

        from . import persistence as pers

        path = bpy.path.abspath(self.filepath)
        if not os.path.isfile(path):
            self.report({"ERROR"}, f"File not found: {path}")
            return {"CANCELLED"}
        try:
            # Try UTF-8 first, fall back to latin-1 which accepts all byte values
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            except UnicodeDecodeError:
                with open(path, "r", encoding="latin-1") as f:
                    content = f.read().strip()
            if not content:
                self.report(
                    {"ERROR"},
                    "Keymapper import failed: file appears empty, please try again.",
                )
                return {"CANCELLED"}
            loaded = json.loads(content)
            if isinstance(loaded, dict) and "entries" in loaded:
                loaded_folders = loaded.get("folders", [])
                loaded_entries = loaded.get("entries", [])
            elif isinstance(loaded, list):
                # Legacy format — entries only
                loaded_folders = []
                loaded_entries = loaded
            else:
                self.report({"WARNING"}, "Keymapper: Invalid JSON format.")
                return {"CANCELLED"}
            migrated = [pers._migrate_entry(e) for e in loaded_entries]
            if self.mode == "ADD" and (pers._entries or pers._folders):
                # Merge: keep everything, append the imported set. Colliding
                # entry ids get fresh ones (importing the same file twice);
                # folders merge by id so re-imported entries land back in
                # their folder instead of a duplicate.
                import uuid as _uuid

                existing_ids = {e.get("entry_id") for e in pers._entries}
                for e in migrated:
                    if e.get("entry_id") in existing_ids:
                        e["entry_id"] = str(_uuid.uuid4())
                    existing_ids.add(e["entry_id"])
                existing_fids = {f.get("folder_id") for f in pers._folders}
                for f in loaded_folders:
                    if f.get("folder_id") not in existing_fids:
                        pers._folders.append(f)
                        existing_fids.add(f.get("folder_id"))
                pers._entries.extend(migrated)
            else:
                # Replace: first release everything the current entries hold
                # (remove our KMIs, restore the defaults they disabled) so no
                # disabled defaults or orphaned KMIs leak past the swap.
                from . import keymap_manager as _km

                _km.release_all_entries()
                pers._folders[:] = loaded_folders
                pers._entries[:] = migrated
            pers._rebuild_folder_sort_indices()
            pers._rebuild_sort_indices()
            pers._write_to_prefs()
            # Select the top folder so the visible selection matches what the
            # panel displays after import.
            try:
                _folders = pers.get_folders()
                context.window_manager.keymapper_selected_folder_id = (
                    _folders[0].get("folder_id", "") if _folders else "")
            except Exception:
                pass
            # Run conflict scans before activating so disable logic has data.
            # force=True because imported JSON may carry stale signatures
            # from a different Blender install or older addon version.
            try:
                from . import conflict_detector
                from . import keyconfig_store as _ks

                # Ensure the keyconfig store is built FIRST — conflict detection
                # reads from it. Without this, importing on a fresh install
                # scans against an empty/absent store, finds no conflicts, and
                # the shortcuts fail to disable the Blender defaults they
                # override (so they appear not to work until a manual Re-scan).
                if not _ks.is_scanned():
                    _ks.do_full_scan()
                imported_entries = pers.get_entries()
                conflict_detector.update_entry_conflicts(imported_entries)
                conflict_detector.update_all_external_conflicts(
                    imported_entries, force=True
                )
                conflict_detector.update_unregistered_ops(imported_entries)
                pers._write_to_prefs()
            except Exception as e:
                print(f"[Keymapper] Post-import conflict scan error: {e}")
            # Activate KMIs for all imported entries
            from . import keymap_manager

            keymap_manager.reactivate_all()
            keymap_manager.schedule_conflict_disable()
            # Imported data lives in the working prefs but isn't persisted to the
            # saved store until the user clicks Save — flag the unsaved state so
            # the Save button highlights (same as creating/preset-adding).
            mark_unsaved()
            _redraw(context)
            entry_count = len(
                loaded.get("entries", loaded) if isinstance(loaded, dict) else loaded
            )
            folder_count = (
                len(loaded.get("folders", [])) if isinstance(loaded, dict) else 0
            )
            _how = "added" if self.mode == "ADD" else "imported"
            self.report(
                {"INFO"},
                f"Keymapper: {_how.capitalize()} {entry_count} entries "
                f"and {folder_count} folders.",
            )
        except Exception as e:
            self.report({"ERROR"}, f"Keymapper import failed: {e}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Add Keymapper Entry from right-click context menu
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_AddFromContext(Operator):
    """Open Keymapper form pre-filled with the right-clicked button's operator or property"""

    bl_idname = "keymapper.add_from_context"
    bl_label = "Add Keymapper Shortcut Entry..."
    bl_description = (
        "Add a new Keymapper shortcut pre-filled with this operator or property"
    )
    bl_options = {"INTERNAL", "REGISTER"}

    def execute(self, context):
        wm = context.window_manager

        # Discard any half-finished entry first. Dismissing the popup (by
        # clicking away) leaves the form open in the panel, and without this
        # the next right-click add would land on top of that stale form.
        if wm.get("keymapper_form_active", False):
            try:
                bpy.ops.keymapper.form_cancel()
            except Exception:
                pass

        # --- Detect what was right-clicked ---
        btn_op = getattr(context, "button_operator", None)
        btn_prop = getattr(context, "button_prop", None)
        btn_ptr = getattr(context, "button_pointer", None)

        sel_ops = []

        if btn_op is not None:
            # Get operator ID safely — bl_idname may not exist in BForArtists
            op_id = getattr(type(btn_op), "bl_idname", None)
            if not op_id:
                # Fall back to bl_rna.identifier: "WM_OT_tool_set_by_id" → "wm.tool_set_by_id"
                try:
                    rna_id = type(btn_op).bl_rna.identifier
                    parts = rna_id.split("_OT_", 1)
                    if len(parts) == 2:
                        op_id = f"{parts[0].lower()}.{parts[1].lower()}"
                    else:
                        op_id = rna_id.lower()
                except Exception:
                    self.report(
                        {"WARNING"},
                        "Keymapper: Could not determine operator ID from context.",
                    )
                    return {"CANCELLED"}
            props = {}
            for rna_prop in type(btn_op).bl_rna.properties:
                pid = rna_prop.identifier
                if pid == "rna_type":
                    continue
                try:
                    val = getattr(btn_op, pid)
                    # Skip default/empty values to keep things clean
                    if val is None:
                        continue
                    if isinstance(val, str) and val == "":
                        continue
                    if isinstance(val, bool) and val == rna_prop.default:
                        continue
                    props[pid] = str(val)
                except Exception:
                    pass
            sel_ops = [{"id": op_id, "props": props, "context": ""}]

        elif btn_prop is not None and btn_ptr is not None:
            # Property button — map to the appropriate wm.context_* operator
            prop_id = btn_prop.identifier
            prop_type = (
                btn_prop.type
            )  # 'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM', 'POINTER', ...

            # Build the data path — we need the full path from bpy.context
            # e.g. "object.display.show_wire" not just "show_wire"
            try:
                # path_from_id() gives the path from the ID owner to this struct
                # e.g. on an ObjectDisplay struct owned by Object: "display"
                ptr_path = btn_ptr.path_from_id()
                full_path = f"{ptr_path}.{prop_id}" if ptr_path else prop_id
            except Exception:
                full_path = prop_id

            # Resolve the full bpy.context data path.
            # Pass 1: match btn_ptr.id_data against top-level context vars (Object, Scene, etc.)
            # Pass 2: match btn_ptr directly against space/area sub-objects (overlay, shading, etc.)
            data_path = full_path
            resolved = False

            # Pass 1 — ID-owned structs (Object, Scene, Material, ...)
            try:
                id_data = btn_ptr.id_data
                if id_data is not None:
                    for ctx_var in (
                        "object",
                        "active_object",
                        "active_bone",
                        "active_pose_bone",
                        "scene",
                        "world",
                        "material",
                        "space_data",
                        "area",
                    ):
                        try:
                            ctx_obj = getattr(context, ctx_var, None)
                            if ctx_obj is not None and ctx_obj == id_data:
                                data_path = f"{ctx_var}.{full_path}"
                                resolved = True
                                break
                        except Exception:
                            pass
            except Exception:
                pass

            # Pass 2 — Space/area sub-structs (View3DOverlay, View3DShading, …)
            if not resolved:
                # (ctx_var, sub_attr) — sub_attr=None means check ctx_var itself
                _direct = [
                    ("space_data", "overlay"),
                    ("space_data", "shading"),
                    ("space_data", "region_3d"),
                    ("space_data", None),
                    ("area", None),
                    ("region", None),
                    ("scene", "render"),
                    ("scene", "eevee"),
                    ("scene", "cycles"),
                    ("scene", "view_settings"),
                    ("scene", "display"),
                ]
                for ctx_var, sub_attr in _direct:
                    try:
                        ctx_obj = getattr(context, ctx_var, None)
                        if ctx_obj is None:
                            continue
                        target = getattr(ctx_obj, sub_attr) if sub_attr else ctx_obj
                        if target == btn_ptr:
                            prefix = f"{ctx_var}.{sub_attr}" if sub_attr else ctx_var
                            data_path = f"{prefix}.{prop_id}"
                            resolved = True
                            break
                    except Exception:
                        pass

            # Warn if still using absolute indexing after both passes
            import re as _re

            if _re.search(r"\[\d+\]", data_path):
                self.report(
                    {"WARNING"},
                    f"Keymapper: Could not resolve a stable path for this property "
                    f"(got '{data_path}'). The shortcut may not work reliably.",
                )

            # Choose the right context operator
            if prop_type == "BOOLEAN":
                op_id = "wm.context_toggle"
                props = {"data_path": data_path}
            elif prop_type == "ENUM":
                # Use cycle if it's a plain enum, set_enum if we know the value
                op_id = "wm.context_cycle_enum"
                props = {"data_path": data_path}
            elif prop_type == "INT":
                op_id = "wm.context_set_int"
                props = {"data_path": data_path}
            elif prop_type == "FLOAT":
                op_id = "wm.context_set_float"
                props = {"data_path": data_path}
            elif prop_type == "STRING":
                op_id = "wm.context_set_string"
                props = {"data_path": data_path}
            else:
                # Fallback — just use context_set_value
                op_id = "wm.context_set_value"
                props = {"data_path": data_path, "value": ""}

            sel_ops = [{"id": op_id, "props": props, "context": ""}]
        else:
            self.report(
                {"WARNING"},
                "Keymapper: Could not detect operator or property from context.",
            )
            return {"CANCELLED"}

        return self._open_form(context, sel_ops)

    def _open_form(self, context, sel_ops):
        wm = context.window_manager

        # --- Open the form pre-filled ---
        # Clear any open subcategory dropdowns
        for key in list(wm.keys()):
            if key.startswith("keymapper_subcat_") or key.startswith("keymapper_s_"):
                del wm[key]

        _remove_scratch_kmi()
        _ensure_scratch_kmi()
        _init_form(wm)
        wm.keymapper_ctx_searches.clear()
        wm.keymapper_menu_searches.clear()
        wm.keymapper_prop_texts.clear()
        wm.keymapper_context_path_props.clear()
        wm.keymapper_int_props.clear()
        wm.keymapper_float_props.clear()

        _set_sel_ops(wm, sel_ops)

        # A right-click add always starts unfiled: the panel's current
        # folder selection is unrelated to what the user just right-clicked,
        # so defaulting to it filed entries in surprising places.
        entries = persistence.get_entries()
        selected_idx = wm.keymapper.selected_index
        if entries and 0 <= selected_idx < len(entries):
            # Deselect so no card stays highlighted behind the popup.
            wm.keymapper.selected_index = -1
        new_folder = ""
        insert_after = -1
        wm["keymapper_form_after_entry"] = ""

        wm["keymapper_form_active"] = True
        wm["keymapper_quickadd_session"] = uuid.uuid4().hex
        wm["keymapper_form_entry_id"] = ""
        wm["keymapper_form_insert_after"] = insert_after
        wm["keymapper_new_entry_folder"] = new_folder
        wm["keymapper_form_goto_unsorted"] = insert_after == -1 and not new_folder
        _scratch_kmi_set_active(True)

        _redraw(context)
        # Show the compact editor as a floating popup right where the user
        # right-clicked. keep_open=True keeps it alive across button clicks
        # (a plain invoke_popup would dismiss on the first one). The form
        # state lives in WM keys, so dismissing the popup loses nothing —
        # the same form is still active in the panels.
        try:
            # keep_open=True keeps the popup alive across clicks. Blender
            # offers no way to have both: without it, ANY click (dropdown,
            # text field commit, folder menu) dismisses the popup.
            bpy.ops.wm.call_panel(name="KEYMAPPER_PT_QuickAdd",
                                  keep_open=True)
        except Exception as e:
            print(f"[Keymapper] quick-add popup unavailable: {e}")
        return {"FINISHED"}


def _draw_keymapper_context_menu(self, context):
    """Appended to UI_MT_button_context_menu to add our shortcut entry button."""
    btn_op = getattr(context, "button_operator", None)
    btn_prop = getattr(context, "button_prop", None)
    if btn_op is not None or btn_prop is not None:
        self.layout.separator()
        self.layout.operator(
            "keymapper.add_from_context",
            text="Add Keymapper Shortcut Entry...",
            icon="HAND",
        )


# ---------------------------------------------------------------------------
# Keyconfig scan operators
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_RestoreAllKMIs(Operator):
    """Restore Blender's keymap to factory state.

    Removes all Keymapper-created KMIs and reverts every keymap Keymapper (or the
    user) modified back to default. This is a hard reset of the keyconfig.
    """

    bl_idname = "keymapper.restore_all_kmis"
    bl_label = "Restore KMIs"
    bl_description = (
        "Remove all Keymapper shortcuts and restore Blender's keymap to factory "
        "defaults. Also removes user-created KMIs"
    )
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        # A props dialog closes when its confirm button is clicked (unlike
        # invoke_popup, which stays open). Label the confirm "Restore KMIs".
        return context.window_manager.invoke_props_dialog(
            self, width=360, confirm_text="Restore KMIs"
        )

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="This will restore Blender's keymap to factory defaults.", icon=_safe_icon("STATUS_WARNING", "ERROR"))
        col.separator()
        col.label(text="• Removes all Keymapper entries and categories")
        col.label(text="• Removes every shortcut Keymapper added")
        col.label(text="• Reverts all keymaps Keymapper modified")
        col.label(text="• Also removes any user-created KMIs")
        col.separator()
        col.label(text="This cannot be undone.")

    def execute(self, context):
        # Runs when the dialog's "Restore KMIs" button is clicked.
        return bpy.ops.keymapper.restore_all_kmis_confirm()


class KEYMAPPER_OT_RestoreAllKMIsConfirm(Operator):
    """Perform the actual keymap restore (invoked from the confirm dialog)."""

    bl_idname = "keymapper.restore_all_kmis_confirm"
    bl_label = "Restore KMIs"
    bl_description = "Confirm restoring Blender's keymap to factory defaults"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        import bpy
        wm = context.window_manager
        kc = wm.keyconfigs.user
        if kc is None:
            self.report({"WARNING"}, "No user keyconfig.")
            return {"CANCELLED"}

        from . import keymap_manager

        # Close the edit/add form if it's open — the entries it references are
        # about to be removed, and a stale open form keeps the topbar disabled.
        if wm.get("keymapper_form_active", False):
            wm["keymapper_form_active"] = False
            wm["keymapper_form_entry_id"] = ""
            wm["keymapper_form_goto_unsorted"] = False
            wm["keymapper_form_pending_icon"] = ""
            wm["keymapper_form_icon_snapshot_set"] = False
            wm["keymapper_extra_keybinds"] = "[]"
            clear_all_detect_contexts(wm)
            try:
                _clear_extra_scratch_kmis()
                reset_scratch_kmi()
            except Exception:
                pass

        # Step 0: deterministically re-enable every default we disabled. Don't
        # rely solely on Blender's is_user_modified flag (Step 2) — it doesn't
        # flag every keymap where we only toggled a default off, so those
        # defaults would stay disabled.
        #
        # TWO PHASES, and the order matters. _restore_default_kmis runs a
        # consensus check: a default stays disabled while ANY OTHER entry still
        # claims it. Restoring entry-by-entry while every entry's KMIs are still
        # registered means the not-yet-processed entries look like live
        # claimants, so any SHARED default is "kept disabled" — and once those
        # entries' handles are popped too, nothing goes back to re-enable it.
        # (view2d.scroll_up is claimed by both the Menu-Scroll and 2D-Scroll
        # entries, which is exactly why scroll stayed dead after a Restore.)
        # So: drop all of our KMIs first, THEN restore, by which point no entry
        # holds a claim.
        keymap_manager.release_all_entries()

        # Step 1: remove Keymapper-created KMIs. Ours are addon-owned and carry
        # a NEGATIVE id in the user layer (bundled keymapper.* ops included);
        # factory/materialized copies are positive and must be left for Step 2.
        removed = 0
        for km in kc.keymaps:
            for kmi in list(km.keymap_items):
                if kmi.idname.startswith("keymapper.") or kmi.id < 0:
                    try:
                        km.keymap_items.remove(kmi)
                        removed += 1
                    except Exception:
                        pass

        # Step 2: restore each keymap that still has user modifications back to
        # factory. This reverts both disabled defaults AND items modified in
        # place (the ← restore arrow).
        #
        # keymap_restore() rebuilds kc.keymaps, which invalidates any live
        # iterator over the collection (Blender then walks freed memory and
        # crashes). So we snapshot the names up front and re-fetch by name.
        #
        # Restoring a keymap can leave another keymap flagged user-modified only
        # after the keyconfig settles, so a single pass can miss one. Repeat
        # until nothing is modified (capped so we never spin forever).
        restored_kms = 0
        for _pass in range(8):
            modified_names = [
                km.name for km in kc.keymaps
                if getattr(km, "is_user_modified", False)
            ]
            if not modified_names:
                break
            for name in modified_names:
                km = kc.keymaps.get(name)
                if km is None or not getattr(km, "is_user_modified", False):
                    continue
                try:
                    with bpy.context.temp_override(keymap=km):
                        bpy.ops.preferences.keymap_restore()
                    restored_kms += 1
                except Exception as e:
                    print(f"[Keymapper] keymap_restore failed for {name}: {e}")
            try:
                wm.keyconfigs.update()
            except Exception:
                pass

        # Clear Keymapper tracking so it won't re-touch removed items.
        keymap_manager._kmi_registry.clear()
        keymap_manager._entry_kmi_specs.clear()
        keymap_manager._disabled_defaults.clear()

        # Remove ALL Keymapper shortcut entries and categories (full reset).
        # Their KMIs were already removed in Step 1; this clears the stored
        # entries and folders themselves.
        # NOTE: no `from . import persistence` here — it is already imported at
        # module level, and a function-local import would make the name local to
        # this ENTIRE function, so the earlier use in Step 0 would raise
        # UnboundLocalError.
        entry_count = len(persistence.get_entries())
        for _e in list(persistence.get_entries()):
            persistence.remove_entry(_e.get("entry_id", ""))
        for _f in list(persistence.get_folders()):
            persistence.delete_folder(_f.get("folder_id", ""), delete_entries=True)
        # Don't persist here: the removal is a working-state change like any
        # other. The Save button turns red; restarting Blender without saving
        # brings the entries back.
        mark_unsaved()

        try:
            wm.keyconfigs.update()
        except Exception:
            pass
        self.report(
            {"INFO"},
            f"Keymapper: removed {entry_count} entries, {removed} KMIs, "
            f"restored {restored_kms} keymaps.",
        )
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ScanKeyconfig(Operator):
    """Scan Blender's keyconfig and build a local snapshot for fast conflict detection"""

    bl_idname = "keymapper.scan_keyconfig"
    bl_label = "Scan Keyconfig"
    bl_description = "Scan Blender's keymaps once to enable fast conflict detection"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from . import conflict_detector, environment, keymap_manager
        from . import keyconfig_store as _ks
        from .database.dynamic_ops import invalidate_cache as _inv_dyn
        from .operator_discovery import deep_scan as _od_deep
        from .operator_discovery import refresh as _od_refresh

        self.report({"INFO"}, "Keymapper: Scanning keymaps...")

        # Run the SAME full scan as the "Re-scan default keybindings" button so
        # the initial scan fully sets things up (operator caches, conflict
        # rescan, and reactivation) rather than only building the store.
        _od_refresh()
        _od_deep()
        _inv_dyn()
        _ks.do_full_scan()
        entries = persistence.get_entries()
        scanned = conflict_detector.update_all_external_conflicts(entries, force=True)
        conflict_detector.update_unregistered_ops(entries)
        persistence._write_to_prefs()
        keymap_manager.reactivate_all()
        environment.clear_cached_changes()

        self.report(
            {"INFO"},
            f"Keymapper: Keyconfig scanned. {len(_ks.get_store())} keymaps stored.",
        )
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_KeyconfigScanPopup(Operator):
    """Open keyconfig rescan options"""

    bl_idname = "keymapper.keyconfig_scan_popup"
    bl_label = "Keyconfig Scan"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=260)

    def draw(self, context):
        from . import keyconfig_store as _ks

        layout = self.layout
        layout.label(text="Keyconfig Scan", icon="FILE_REFRESH")
        layout.separator()

        stored_ver = _ks.get_stored_blender_version()
        current_ver = _ks.current_blender_version()
        if stored_ver:
            layout.label(text=f"Last scanned on Blender {stored_ver}", icon="INFO")
            if _ks.version_changed():
                layout.label(
                    text=f"Current: {current_ver} — rescan recommended", icon=_safe_icon("STATUS_WARNING", "ERROR")
                )
        layout.separator()
        layout.operator(
            "keymapper.keyconfig_scan_incremental", text="Scan for Changes", icon="ADD"
        )
        layout.operator(
            "keymapper.keyconfig_scan_full", text="New Full Scan", icon="FILE_REFRESH"
        )

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_KeyconfigScanIncremental(Operator):
    """Scan for new keymaps not yet in the snapshot"""

    bl_idname = "keymapper.keyconfig_scan_incremental"
    bl_label = "Scan for Changes"
    bl_description = "Add any new keymaps not already in the snapshot"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from . import keyconfig_store as _ks

        _ks.do_incremental_scan()
        self.report(
            {"INFO"},
            f"Keymapper: Incremental scan complete. "
            f"{len(_ks.get_store())} keymaps stored.",
        )
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_KeyconfigScanFull(Operator):
    """Re-scan everything: refreshes the operator list (so operators from newly installed or enabled add-ons appear) and re-scans Blender's keyconfig for conflict detection."""

    bl_idname = "keymapper.keyconfig_scan_full"
    bl_label = "Re-scan default keybindings"
    bl_description = (
        "Re-scan everything. Refreshes the operator list so operators from "
        "newly installed or enabled add-ons appear, and re-scans Blender's "
        "keyconfig file to update conflict detection. Run this after "
        "installing, enabling, or disabling add-ons."
    )
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from . import conflict_detector, environment, keymap_manager
        from . import keyconfig_store as _ks
        from .database.dynamic_ops import invalidate_cache as _inv_dyn
        from .operator_discovery import deep_scan as _od_deep
        from .operator_discovery import refresh as _od_refresh

        # 1) Rebuild the operator-discovery caches so operators from newly
        #    installed/enabled addons appear in Browse Operators. The keyconfig
        #    store scan below only feeds conflict detection — it does NOT
        #    populate the operator list, so without this step a freshly
        #    installed addon's operators would stay hidden until the user
        #    found the separate ↺ Refresh button.
        _od_refresh()  # build_cache(force=True) — static + addon operators
        _od_deep()  # deep_scan — operators under built-in prefixes
        _inv_dyn()  # invalidate the merged dynamic_ops cache

        # 2) Rescan Blender's keyconfig into our store (for conflict detection)
        _ks.do_full_scan()

        # 3) The keyconfig store contents changed, so its signature changes too.
        #    That alone makes every entry's stored `_ks_signature_at_scan`
        #    stale — force a full external rescan and persist fresh results.
        entries = persistence.get_entries()
        scanned = conflict_detector.update_all_external_conflicts(entries, force=True)
        conflict_detector.update_unregistered_ops(entries)
        persistence._write_to_prefs()
        # Re-disable defaults using the freshly-scanned conflict lists
        keymap_manager.reactivate_all()

        # 4) Refresh the environment baseline so the "addon list changed" banner
        #    clears. This is the only place we update the snapshot — pressing
        #    Re-scan is the user's acknowledgement that they want the current
        #    environment to be the new normal.
        environment.clear_cached_changes()

        # 5) Adopted-KMI icon cache: recompute AFTER reactivation so enabled
        #    entries reflect fresh adoption records and disabled entries get a
        #    fresh would-adopt pass against the just-scanned keyconfig.
        keymap_manager.refresh_adoption_display()

        self.report(
            {"INFO"},
            f"Keymapper: Full scan complete. "
            f"{len(_ks.get_store())} keymaps stored, "
            f"{scanned} entries re-scanned.",
        )
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Folder operators
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_AddFolder(Operator):
    """Create a new folder"""

    bl_idname = "keymapper.add_folder"
    bl_label = "New Folder"
    bl_description = "Create a new folder to organize shortcut entries"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    label: StringProperty(default="New Folder")

    def execute(self, context):
        persistence.add_folder(self.label)
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


def _select_neighbor_folder(context, folder_id: str):
    """Before deleting a folder, select the folder BELOW it in the tab order
    (next in the list); if none below, the one ABOVE; else Unsorted."""
    try:
        folders = persistence.get_folders()
        ids = [f.get("folder_id", "") for f in folders]
        idx = ids.index(folder_id)
    except (ValueError, Exception):
        return
    if idx + 1 < len(ids):
        nxt = ids[idx + 1]
    elif idx > 0:
        nxt = ids[idx - 1]
    else:
        nxt = ""
    try:
        context.window_manager.keymapper_selected_folder_id = nxt
    except Exception:
        pass


class KEYMAPPER_OT_DeleteFolder(Operator):
    """Delete a folder — shows confirmation popup only when folder has entries"""

    bl_idname = "keymapper.delete_folder"
    bl_label = "Delete Folder"
    bl_options = {"INTERNAL"}

    folder_id: StringProperty()

    def invoke(self, context, event):
        entries = [
            e
            for e in persistence.get_entries()
            if e.get("folder_id", "") == self.folder_id
        ]
        if not entries:
            return self.execute(context)
        return context.window_manager.invoke_popup(self, width=320)

    def draw(self, context):
        folder = persistence.get_folder_by_id(self.folder_id)
        if not folder:
            return
        label = folder.get("label", "Folder")
        entries = [
            e
            for e in persistence.get_entries()
            if e.get("folder_id", "") == self.folder_id
        ]
        count = len(entries)

        layout = self.layout
        layout.label(text=f'Delete folder "{label}"?', icon="QUESTION")
        layout.label(
            text=f"This folder contains {count} entr{'y' if count == 1 else 'ies'}.",
            icon="INFO",
        )
        layout.separator()

        row = layout.row()
        op = row.operator(
            "keymapper.delete_folder_confirm",
            text="Delete folder, keep entries",
            icon="FOLDER_REDIRECT",
        )
        op.folder_id = self.folder_id
        op.delete_entries = False

        row2 = layout.row()
        row2.alert = True
        op2 = row2.operator(
            "keymapper.delete_folder_confirm",
            text=f"Delete folder and {count} entr{'y' if count == 1 else 'ies'}",
            icon="TRASH",
        )
        op2.folder_id = self.folder_id
        op2.delete_entries = True

        layout.separator()
        layout.label(text="Click outside to cancel", icon="INFO")

    def execute(self, context):
        _select_neighbor_folder(context, self.folder_id)
        persistence.delete_folder(self.folder_id, delete_entries=False)
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_DeleteFolderConfirm(Operator):
    """Actually delete the folder"""

    bl_idname = "keymapper.delete_folder_confirm"
    bl_label = "Confirm Delete Folder"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    folder_id: StringProperty()
    delete_entries: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        if self.delete_entries:
            # Fully remove KMIs for entries being deleted. Must use delete_entry
            # (which removes the KMIs) rather than deactivate_entry (which only
            # sets kmi.active=False) — otherwise the entries vanish from storage
            # but their KMIs linger in Blender's keymaps as orphans.
            from . import keymap_manager

            entries = [
                e
                for e in persistence.get_entries()
                if e.get("folder_id", "") == self.folder_id
            ]
            for entry in entries:
                keymap_manager.delete_entry(entry)
        _select_neighbor_folder(context, self.folder_id)
        persistence.delete_folder(self.folder_id, delete_entries=self.delete_entries)
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_StartFolderRename(Operator):
    """Start inline rename of a folder"""

    bl_idname = "keymapper.start_folder_rename"
    bl_label = "Rename Folder"
    bl_options = {"INTERNAL"}

    folder_id: StringProperty()

    def execute(self, context):
        folder = persistence.get_folder_by_id(self.folder_id)
        if not folder:
            return {"CANCELLED"}
        wm = context.window_manager
        wm.keymapper_renaming_folder_id = self.folder_id
        wm.keymapper_folder_rename_text = folder.get("label", "")
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ConfirmFolderRename(Operator):
    """Confirm inline folder rename"""

    bl_idname = "keymapper.confirm_folder_rename"
    bl_label = "Confirm Rename"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    def execute(self, context):
        wm = context.window_manager
        folder_id = wm.keymapper_renaming_folder_id
        new_label = wm.keymapper_folder_rename_text.strip()
        if folder_id and new_label:
            persistence.update_folder(folder_id, {"label": new_label})
            mark_unsaved()
        wm.keymapper_renaming_folder_id = ""
        wm.keymapper_folder_rename_text = ""
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_SelectFolder(Operator):
    """Make this the active folder (does not rename — use the rename button)"""

    bl_idname = "keymapper.select_folder"
    bl_label = "Select Folder"
    bl_options = {"INTERNAL"}

    folder_id: StringProperty()  # "" = Unsorted

    def execute(self, context):
        wm = context.window_manager
        wm.keymapper_selected_folder_id = self.folder_id
        wm.keymapper.selected_index = -1
        # Selecting a different folder cancels any in-progress rename.
        if getattr(wm, "keymapper_renaming_folder_id", ""):
            wm.keymapper_renaming_folder_id = ""
            wm.keymapper_folder_rename_text = ""
        _redraw(context)
        return {"FINISHED"}


def _apply_live_binding(context, entry_id):
    """Re-apply an entry after an inline keybinding edit.

    The entry's binding fields are already written to persistence by the caller.
    This recomputes conflicts (fast store scan) and re-registers the entry's
    KMIs so the change takes effect immediately. Uses the same safe apply path
    the edit form uses, scoped to a single entry.
    """
    saved = persistence.get_entry_by_id(entry_id)
    if not saved:
        return
    from . import keymap_manager, conflict_detector

    try:
        conflict_detector.update_entry_external_conflicts(saved, force=True)
        # Internal conflicts must refresh too — a card-level binding change can
        # create/clear conflicts with other entries, and the edit panel's
        # active list reads these stored results (only the preview recomputes
        # live). Pairwise across all entries, same as the Confirm path.
        conflict_detector.update_entry_conflicts(persistence.get_entries())
        persistence._write_to_prefs()
    except Exception as e:
        print(f"[Keymapper] live conflict recompute error: {e}")

    saved = persistence.get_entry_by_id(entry_id)
    try:
        if saved.get("enabled", True):
            keymap_manager.activate_entry(saved)
        else:
            keymap_manager.deactivate_entry(saved)
        keymap_manager.schedule_conflict_disable()
    except Exception as e:
        print(f"[Keymapper] live activate error: {e}")

    mark_unsaved()
    _redraw(context)


_REPEAT_MOUSE_KEYS = {
    "LEFTMOUSE", "RIGHTMOUSE", "MIDDLEMOUSE",
    "BUTTON4MOUSE", "BUTTON5MOUSE", "BUTTON6MOUSE", "BUTTON7MOUSE",
    "MOUSEMOVE", "TRACKPADPAN", "TRACKPADZOOM", "MOUSEROTATE",
    "WHEELUPMOUSE", "WHEELDOWNMOUSE", "WHEELINMOUSE", "WHEELOUTMOUSE",
}


def _entry_repeat_available(entry) -> bool:
    """Repeat applies only to keyboard keys whose value is ANY or PRESS."""
    key = entry.get("key", "") or "NONE"
    if key in _REPEAT_MOUSE_KEYS or "NDOF" in key:
        return False
    return entry.get("event_type", "PRESS") in {"ANY", "PRESS"}


def _clear_repeat_if_unavailable(entry_id):
    """Force repeat off when the current binding can't use it."""
    entry = persistence.get_entry_by_id(entry_id)
    if entry and entry.get("repeat") and not _entry_repeat_available(entry):
        persistence.update_entry(entry_id, {"repeat": False})


class KEYMAPPER_OT_SimplifiedToggleMod(Operator):
    """Toggle a modifier on this shortcut's keybinding"""

    bl_idname = "keymapper.simplified_toggle_mod"
    bl_label = "Toggle Modifier"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()
    mod_name: StringProperty()  # any / shift / ctrl / alt / oskey / repeat
    extra_index: IntProperty(default=-1)  # -1 = primary keybind

    _TOOLTIPS = {
        "any": "Any modifier keys pressed",
        "shift": "Shift key pressed",
        "ctrl": "Ctrl key pressed",
        "alt": "Alt key pressed",
        "oskey": "Operating system key pressed",
        "repeat": "Active on key-repeat events (when a key is held)",
    }

    @classmethod
    def description(cls, context, properties):
        return cls._TOOLTIPS.get(properties.mod_name, cls.bl_label)

    def execute(self, context):
        entry = persistence.get_entry_by_id(self.entry_id)
        if not entry:
            return {"CANCELLED"}
        # Repeat only applies to keyboard keys with value ANY/PRESS; ignore
        # clicks when it's grayed out (mirrors Blender hiding the field).
        if self.mod_name == "repeat" and not _entry_repeat_available(entry):
            return {"CANCELLED"}
        if self.extra_index >= 0:
            extras = entry.get("extra_keybinds", []) or []
            if not (0 <= self.extra_index < len(extras)):
                return {"CANCELLED"}
            cur = bool(extras[self.extra_index].get(self.mod_name, False))
            _update_extra_keybind(self.entry_id, self.extra_index,
                                  {self.mod_name: not cur})
        else:
            cur = bool(entry.get(self.mod_name, False))
            persistence.update_entry(self.entry_id, {self.mod_name: not cur})
        _apply_live_binding(context, self.entry_id)
        return {"FINISHED"}


_VALUE_ITEMS = [
    ("ANY", "Any", ""),
    ("PRESS", "Press", ""),
    ("RELEASE", "Release", ""),
    ("CLICK", "Click", ""),
    ("DOUBLE_CLICK", "Double Click", ""),
    ("CLICK_DRAG", "Drag", ""),
    ("NOTHING", "Nothing", ""),
]


class KEYMAPPER_OT_SimplifiedValueMenu(Operator):
    """Choose the press/click/drag value for this shortcut"""

    bl_idname = "keymapper.simplified_value_menu"
    bl_label = "Value"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()
    extra_index: IntProperty(default=-1)  # -1 = primary keybind

    def invoke(self, context, event):
        eid = self.entry_id
        ex_idx = self.extra_index

        def _draw(menu, ctx):
            for val, label, _ in _VALUE_ITEMS:
                op = menu.layout.operator(
                    "keymapper.simplified_set_value", text=label
                )
                op.entry_id = eid
                op.event_type = val
                op.extra_index = ex_idx

        context.window_manager.popup_menu(_draw, title="Value", icon="NONE")
        return {"FINISHED"}


class KEYMAPPER_OT_SimplifiedSetValue(Operator):
    """Apply a press/click/drag value to this shortcut"""

    bl_idname = "keymapper.simplified_set_value"
    bl_label = "Set Value"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()
    event_type: StringProperty()
    extra_index: IntProperty(default=-1)  # -1 = primary keybind

    def execute(self, context):
        if not self.event_type:
            return {"CANCELLED"}
        if self.extra_index >= 0:
            _update_extra_keybind(self.entry_id, self.extra_index,
                                  {"value": self.event_type})
        else:
            persistence.update_entry(self.entry_id,
                                     {"event_type": self.event_type})
        _clear_repeat_if_unavailable(self.entry_id)
        _apply_live_binding(context, self.entry_id)
        return {"FINISHED"}


# Modifier keys are captured via event.shift/ctrl/alt/oskey, not as the key.
_CAPTURE_IGNORE = {
    "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL",
    "LEFT_ALT", "RIGHT_ALT", "OSKEY", "LEFT_OS", "RIGHT_OS",
    "MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "TIMER", "TIMER_REPORT",
    "WINDOW_DEACTIVATE", "NONE",
}
_CAPTURE_WHEEL = {"WHEELUPMOUSE", "WHEELDOWNMOUSE", "WHEELINMOUSE", "WHEELOUTMOUSE"}


def _update_extra_keybind(entry_id: str, index: int, data: dict) -> bool:
    """Patch one of an entry's ADDITIONAL keybinds and re-register it.

    The card now edits every keybind slot, not just the primary, so the
    simplified_* operators take an `extra_index` (-1 = primary) and route
    here for anything else.
    """
    entry = persistence.get_entry_by_id(entry_id)
    if not entry:
        return False
    extras = list(entry.get("extra_keybinds", []) or [])
    if not (0 <= index < len(extras)):
        return False
    ex = dict(extras[index])
    ex.update(data)
    extras[index] = ex
    persistence.update_entry(entry_id, {"extra_keybinds": extras})
    return True


class KEYMAPPER_OT_SimplifiedCaptureKey(Operator):
    """Press a key or mouse button to set this shortcut's binding"""

    bl_idname = "keymapper.simplified_capture_key"
    bl_label = "Press a key"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()
    extra_index: IntProperty(default=-1)  # -1 = primary keybind

    def invoke(self, context, event):
        context.window_manager["keymapper_capturing_entry"] = (
            self.entry_id if self.extra_index < 0
            else f"{self.entry_id}#{self.extra_index}")
        context.window_manager.modal_handler_add(self)
        _redraw(context)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        wm = context.window_manager
        if "keymapper_capturing_entry" in wm:
            del wm["keymapper_capturing_entry"]
        _redraw(context)

    def modal(self, context, event):
        # Cancel on ESC only (RIGHTMOUSE must remain bindable as a key).
        if event.type == "ESC" and event.value == "PRESS":
            self._finish(context)
            return {"CANCELLED"}

        is_wheel = event.type in _CAPTURE_WHEEL
        if not (is_wheel or event.value == "PRESS"):
            return {"RUNNING_MODAL"}
        if event.type in _CAPTURE_IGNORE:
            return {"RUNNING_MODAL"}

        if self.extra_index >= 0:
            _update_extra_keybind(self.entry_id, self.extra_index,
                                  {"key": event.type})
        else:
            persistence.update_entry(self.entry_id, {"key": event.type})
            _clear_repeat_if_unavailable(self.entry_id)
        self._finish(context)
        _apply_live_binding(context, self.entry_id)
        return {"FINISHED"}


class KEYMAPPER_OT_SimplifiedCaptureKeyModifier(Operator):
    """Press a regular key to use it as a modifier, or click again to clear"""

    bl_idname = "keymapper.simplified_capture_key_modifier"
    bl_label = "Key Modifier"
    bl_description = "Regular key pressed as a modifier"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()
    extra_index: IntProperty(default=-1)  # -1 = primary keybind
    clear: BoolProperty(default=False)

    def invoke(self, context, event):
        if self.clear:
            (_update_extra_keybind(self.entry_id, self.extra_index,
                                   {"key_modifier": ""})
             if self.extra_index >= 0 else
             persistence.update_entry(self.entry_id, {"key_modifier": ""}))
            _apply_live_binding(context, self.entry_id)
            _redraw(context)
            return {"FINISHED"}
        context.window_manager["keymapper_capturing_keymod"] = self.entry_id
        context.window_manager.modal_handler_add(self)
        _redraw(context)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        wm = context.window_manager
        if "keymapper_capturing_keymod" in wm:
            del wm["keymapper_capturing_keymod"]
        _redraw(context)

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._finish(context)
            return {"CANCELLED"}
        if event.value != "PRESS":
            return {"RUNNING_MODAL"}
        # Modifier keys and mouse/wheel can't act as a key modifier.
        if event.type in _CAPTURE_IGNORE or event.type in _CAPTURE_WHEEL:
            return {"RUNNING_MODAL"}
        if "MOUSE" in event.type:
            return {"RUNNING_MODAL"}
        (_update_extra_keybind(self.entry_id, self.extra_index,
                                   {"key_modifier": event.type})
             if self.extra_index >= 0 else
             persistence.update_entry(self.entry_id,
                                      {"key_modifier": event.type}))
        self._finish(context)
        _apply_live_binding(context, self.entry_id)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleFolderCollapse(Operator):
    """Expand or collapse a folder"""

    bl_idname = "keymapper.toggle_folder_collapse"
    bl_label = "Toggle Folder"
    bl_options = {"INTERNAL"}

    folder_id: StringProperty()

    def execute(self, context):
        folder = persistence.get_folder_by_id(self.folder_id)
        if folder:
            new_collapsed = not folder.get("collapsed", False)
            persistence.update_folder(self.folder_id, {"collapsed": new_collapsed})
            # If collapsing and a selected entry is inside this folder, deselect it
            if new_collapsed:
                wm = context.window_manager
                idx = wm.keymapper.selected_index
                entries = persistence.get_entries()
                if 0 <= idx < len(entries):
                    if entries[idx].get("folder_id", "") == self.folder_id:
                        wm.keymapper.selected_index = -1
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_SetEntryFolder(Operator):
    """Assign an entry to a folder"""

    bl_idname = "keymapper.set_entry_folder"
    bl_label = "Set Entry Folder"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    entry_id: StringProperty()
    folder_id: StringProperty()  # "" = unsorted

    def execute(self, context):
        persistence.set_entry_folder(self.entry_id, self.folder_id)
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_FolderPicker(Operator):
    """Open folder picker popup for an entry"""

    bl_idname = "keymapper.folder_picker"
    bl_label = "Move to Folder"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=220)

    def draw(self, context):
        layout = self.layout
        folders = persistence.get_folders()
        entry = persistence.get_entry_by_id(self.entry_id)
        cur_fid = entry.get("folder_id", "") if entry else ""

        for folder in folders:
            fid = folder.get("folder_id", "")
            lbl = folder.get("label", "Folder")
            is_cur = fid == cur_fid
            row = layout.row(align=True)
            row.alert = is_cur
            op = row.operator(
                "keymapper.set_entry_folder",
                text=lbl,
                icon="FOLDER_REDIRECT" if is_cur else "FILE_FOLDER",
                emboss=is_cur,
            )
            op.entry_id = self.entry_id
            op.folder_id = fid

        layout.separator()
        row = layout.row()
        row.enabled = cur_fid != ""
        op = row.operator(
            "keymapper.set_entry_folder", text="None (unsorted)", icon="X"
        )
        op.entry_id = self.entry_id
        op.folder_id = ""

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_MoveFolderUp(Operator):
    """Move folder up"""

    bl_idname = "keymapper.move_folder_up"
    bl_label = "Move Folder Up"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    folder_id: StringProperty()

    def execute(self, context):
        persistence.move_folder(self.folder_id, -1)
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_MoveFolderDown(Operator):
    """Move folder down"""

    bl_idname = "keymapper.move_folder_down"
    bl_label = "Move Folder Down"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    folder_id: StringProperty()

    def execute(self, context):
        persistence.move_folder(self.folder_id, 1)
        mark_unsaved()
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleConflictReenabled(Operator):
    """Toggle whether a conflicting default KMI is re-enabled by the user"""

    bl_idname = "keymapper.toggle_conflict_reenabled"
    bl_label = "Toggle Conflict"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()
    conflict_type: StringProperty()  # "shortcut" or "keybind"
    ref_index: IntProperty()

    def execute(self, context):
        from . import keymap_manager as _km
        from . import persistence as _p

        entry = _p.get_entry_by_id(self.entry_id)
        if not entry:
            return {"CANCELLED"}

        key = (
            f"shortcut_conflicts_external"
            if self.conflict_type == "shortcut"
            else "keybind_conflicts_external"
        )
        refs = entry.get(key, [])
        if self.ref_index >= len(refs):
            return {"CANCELLED"}

        ref = refs[self.ref_index]
        currently_reenabled = ref.get("user_reenabled", False)
        ref["user_reenabled"] = not currently_reenabled

        # Apply to actual Blender KMI(s) — toggle all matching items.
        # user_reenabled=True means user wants default back → kmi.active = True
        # user_reenabled=False means override active → kmi.active = False
        new_active = not currently_reenabled
        matches = _km._find_default_kmis(ref)
        if matches:
            for km, kmi, layer, _materialized in matches:
                try:
                    kmi.active = new_active
                except Exception:
                    pass
            _km._refresh_keyconfigs()
        else:
            print(f"[Keymapper] Could not find KMI for toggle: {ref}")

        _p._write_to_prefs()
        from .operators import _redraw

        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ShowExternalConflictInfo(Operator):
    """Show external conflict details"""

    bl_idname = "keymapper.show_external_conflict_info"
    bl_label = "Operator Override"
    bl_description = (
        "This shortcut entry overrides Blender default operators or keybindings"
    )
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()
    conflict_type: StringProperty()

    def execute(self, context):
        from . import persistence as _p

        entry = _p.get_entry_by_id(self.entry_id)
        if not entry:
            return {"FINISHED"}
        ext_sc = entry.get("shortcut_conflicts_external", [])
        ext_kc = entry.get("keybind_conflicts_external", [])
        if self.conflict_type == "shortcut":
            self.report(
                {"INFO"},
                f"Operator Override: This shortcut entry overrides {len(ext_sc)} "
                f"default operator{'s' if len(ext_sc) != 1 else ''}.",
            )
        else:
            self.report(
                {"INFO"},
                f"Keybind Override: This shortcut entry overrides {len(ext_kc)} "
                f"default keybinding{'s' if len(ext_kc) != 1 else ''}.",
            )
        return {"FINISHED"}


class KEYMAPPER_OT_KbcvSetMode(Operator):
    """Set the action-value override mode."""

    bl_idname = "keymapper.kbcv_set_mode"
    bl_label = "Set Action Value Mode"
    bl_description = (
        "All: override every action value. Blender Native: only values that "
        "natively double-fire. Custom: pick freely"
    )
    bl_options = {"INTERNAL"}

    mode: StringProperty(default="NATIVE")

    def execute(self, context):
        from .preferences import (get_prefs, KBCV_VALUES, KBCV_DEFAULTS,
                                  kbcv_prop_name)
        prefs = get_prefs(context)
        prefs.kbcv_mode = self.mode
        if self.mode in ("ALL", "NATIVE"):
            for w in KBCV_VALUES:
                for l in KBCV_VALUES:
                    if w != l:
                        setattr(prefs, kbcv_prop_name(w, l),
                                True if self.mode == "ALL"
                                else (w, l) in KBCV_DEFAULTS)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleDetectCtxSection(Operator):
    """Add contexts for this keybind to find and disable default KMIs with the
    same keybind without creating a KMI in the specified context(s)."""

    bl_idname = "keymapper.toggle_detect_ctx_section"
    bl_label = "Additional Keybind Detection Context(s)"
    bl_description = (
        "Add contexts for this keybind to find and disable default KMIs with "
        "the same keybind without creating a KMI in the specified context(s)"
    )
    bl_options = {"INTERNAL"}

    slot_index: IntProperty(default=0)

    def execute(self, context):
        wm = context.window_manager
        key = subcat_wm_key(f"detectctx_{self.slot_index}")
        wm[key] = not wm.get(key, False)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ToggleDetectCtx(Operator):
    """Toggle a detection context for this keybind."""

    bl_idname = "keymapper.toggle_detect_ctx"
    bl_label = "Toggle Detection Context"
    bl_description = "Include or exclude this context from keybind conflict detection"
    bl_options = {"INTERNAL"}

    slot_index: IntProperty(default=0)
    context_name: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        ctxs = get_detect_contexts(wm, self.slot_index)
        if self.context_name in ctxs:
            ctxs.remove(self.context_name)
        else:
            ctxs.append(self.context_name)
        set_detect_contexts(wm, self.slot_index, ctxs)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_ResetPref(Operator):
    """Reset this setting to its default (on)."""

    bl_idname = "keymapper.reset_pref"
    bl_label = "Restore"
    bl_description = "Restore this setting to its default (enabled)"
    bl_options = {"INTERNAL"}

    prop: StringProperty()

    def execute(self, context):
        from .preferences import get_prefs
        setattr(get_prefs(context), self.prop, True)
        return {"FINISHED"}


class KEYMAPPER_OT_InternalConflictInfo(Operator):
    """Internal conflict info tooltip (non-interactive)."""

    bl_idname = "keymapper.internal_conflict_info"
    # NOTE: bl_label is the tooltip's bold title and is static per class, so it
    # can't pluralize by count. Keep it singular-neutral and let the body's
    # first line carry the "N Conflict(s)" wording.
    bl_label = "Internal Conflict"
    bl_options = {"INTERNAL"}
    text: StringProperty()
    count: IntProperty(default=1)
    entry_id: StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        body = properties.text or ""
        n = max(int(getattr(properties, "count", 1) or 1), 1)
        head = f"{n} Conflict" + ("s" if n != 1 else "")
        tail = ("\n\nClick to isolate this entry and the ones it conflicts "
                "with; click again to show everything.")
        return (f"{head}\n{body}{tail}" if body else head + tail)

    def execute(self, context):
        # Toggle "conflict focus": grey out every entry and folder that isn't
        # part of this conflict, so a catalog with several internal conflicts is
        # actually navigable. Clicking the same icon again clears it.
        wm = context.window_manager
        cur = wm.get("keymapper_conflict_focus", "")
        wm["keymapper_conflict_focus"] = (
            "" if cur == self.entry_id else self.entry_id)
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_UnregisteredOpsInfo(Operator):
    """Info tooltip for entries referencing unregistered operators."""

    bl_idname = "keymapper.unregistered_ops_info"
    bl_label = "Unregistered Operators"
    bl_options = {"INTERNAL"}

    text: StringProperty()

    @classmethod
    def description(cls, context, properties):
        return properties.text or (
            "This entry references operators that are not registered."
        )

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_StatInfo(Operator):
    """Entry stat."""

    bl_idname = "keymapper.stat_info"
    bl_label = "Stat"
    bl_options = {"INTERNAL"}

    text: StringProperty()

    @classmethod
    def description(cls, context, properties):
        return properties.text or "Stat"

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_ConflictWarningInfo(Operator):
    """Conflict warning."""

    bl_idname = "keymapper.conflict_warning_info"
    bl_label = "Conflict"
    bl_options = {"INTERNAL"}

    text: StringProperty()

    @classmethod
    def description(cls, context, properties):
        return properties.text or "Conflict"

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_ConflictOpLabel(Operator):
    """Shows the full operator name on hover."""

    bl_idname = "keymapper.conflict_op_label"
    bl_label = "Operator"
    bl_options = {"INTERNAL"}

    full_text: StringProperty()

    @classmethod
    def description(cls, context, properties):
        return properties.full_text or "Operator"

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_ConflictDisabledInfo(Operator):
    """Conflicting Keymap successfully disabled and overridden."""

    bl_idname = "keymapper.conflict_disabled_info"
    bl_label = "Success"
    bl_description = "Conflicting Keymap successfully disabled and overridden."
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_ConflictReenabledInfo(Operator):
    """Conflicting Keymap re-enabled by user."""

    bl_idname = "keymapper.conflict_reenabled_info"
    bl_label = "Warning"
    bl_description = "Conflicting Keymap re-enabled by user."
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_ShowExternalShortcutInfo(Operator):
    """This shortcut entry overrides Blender default operators"""

    bl_idname = "keymapper.show_external_shortcut_info"
    bl_label = "Operator Override"
    bl_description = "This shortcut entry overrides Blender default operators"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()

    def execute(self, context):
        from . import persistence as _p

        entry = _p.get_entry_by_id(self.entry_id)
        if not entry:
            return {"FINISHED"}
        n = len(entry.get("shortcut_conflicts_external", []))
        self.report(
            {"INFO"},
            f"Operator Override: This shortcut entry overrides {n} "
            f"default operator{'s' if n != 1 else ''}.",
        )
        return {"FINISHED"}


class KEYMAPPER_OT_ShowExternalKeybindInfo(Operator):
    """This shortcut entry overrides Blender default keybindings"""

    bl_idname = "keymapper.show_external_keybind_info"
    bl_label = "Keybind Override"
    bl_description = "This shortcut entry overrides Blender default keybindings"
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()

    def execute(self, context):
        from . import persistence as _p

        entry = _p.get_entry_by_id(self.entry_id)
        if not entry:
            return {"FINISHED"}
        n = len(entry.get("keybind_conflicts_external", []))
        self.report(
            {"INFO"},
            f"Keybind Override: This shortcut entry overrides {n} "
            f"default keybinding{'s' if n != 1 else ''}.",
        )
        return {"FINISHED"}


class KEYMAPPER_OT_ClosePopup(Operator):
    """Close the current popup"""

    bl_idname = "keymapper.close_popup"
    bl_label = "Close"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Copy / Paste entry
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_CopyEntry(Operator):
    """Copy this shortcut entry to clipboard as a shareable string"""

    bl_idname = "keymapper.copy_entry"
    bl_label = "Copy Shortcut Entry"
    bl_description = (
        "Copy this entry to clipboard — paste it to a friend or another session"
    )
    bl_options = {"INTERNAL"}

    entry_id: StringProperty()

    def execute(self, context):
        import base64
        import json as _json

        entry = persistence.get_entry_by_id(self.entry_id) if self.entry_id else None
        if not entry:
            # Toolbar button passes no entry_id — fall back to the selection.
            entries = persistence.get_entries()
            idx = context.window_manager.keymapper.selected_index
            if entries and 0 <= idx < len(entries):
                entry = entries[idx]
        if not entry:
            self.report({"WARNING"}, "Entry not found.")
            return {"CANCELLED"}

        # Include folder name (not UUID) so it works across instances
        folder_name = ""
        fid = entry.get("folder_id", "")
        if fid:
            folder = persistence.get_folder_by_id(fid)
            if folder:
                folder_name = folder.get("label", "")

        export = {
            k: v
            for k, v in entry.items()
            if k
            not in (
                "entry_id",
                "folder_id",
                "sort_index",
                "selected",
                "internal_conflicts",
                "shortcut_conflicts_internal",
                "keybind_conflicts_internal",
                "shortcut_conflicts_external",
                "keybind_conflicts_external",
                "expanded_entry",
                "expanded_shortcuts",
                "expanded_keybinds",
            )
        }
        export["_folder_name"] = folder_name
        export["_keymapper_version"] = 1

        encoded = base64.b64encode(
            _json.dumps(export, ensure_ascii=False).encode()
        ).decode()
        context.window_manager.clipboard = encoded
        self.report({"INFO"}, f"Keymapper: Entry copied to clipboard.")
        _redraw(context)
        return {"FINISHED"}


class KEYMAPPER_OT_PasteEntry(Operator):
    """Paste a shortcut entry from a copied string"""

    bl_idname = "keymapper.paste_entry"
    bl_label = "Paste Shortcut Entry"
    bl_options = {"INTERNAL"}

    paste_text: StringProperty(name="Paste entry string", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Paste a copied shortcut entry string:")
        layout.prop(self, "paste_text", text="")
        layout.label(
            text="If the entry includes a folder, it will be created if needed.",
            icon="INFO",
        )

    def execute(self, context):
        import base64
        import json as _json
        import uuid as _uuid

        raw = self.paste_text.strip()
        if not raw:
            self.report({"WARNING"}, "Nothing to paste.")
            return {"CANCELLED"}
        try:
            decoded = _json.loads(base64.b64decode(raw.encode()).decode())
        except Exception:
            self.report({"ERROR"}, "Keymapper: Invalid paste string.")
            return {"CANCELLED"}

        if decoded.get("_keymapper_version") != 1:
            self.report({"ERROR"}, "Keymapper: Unrecognised entry format.")
            return {"CANCELLED"}

        # Resolve folder — create if name given but not found
        folder_name = decoded.pop("_folder_name", "")
        decoded.pop("_keymapper_version", None)
        folder_id = ""
        if folder_name:
            existing = next(
                (
                    f
                    for f in persistence.get_folders()
                    if f.get("label", "") == folder_name
                ),
                None,
            )
            if existing:
                folder_id = existing["folder_id"]
            else:
                new_folder = persistence.add_folder(folder_name)
                folder_id = new_folder["folder_id"]

        decoded["entry_id"] = str(_uuid.uuid4())
        decoded["folder_id"] = folder_id
        decoded["sort_index"] = len(persistence.get_entries())
        decoded["selected"] = False
        decoded["enabled"] = decoded.get("enabled", True)
        decoded.setdefault("internal_conflicts", [])
        decoded.setdefault("shortcut_conflicts_internal", [])
        decoded.setdefault("keybind_conflicts_internal", [])
        decoded.setdefault("shortcut_conflicts_external", [])
        decoded.setdefault("keybind_conflicts_external", [])
        decoded.setdefault("expanded_entry", False)
        decoded.setdefault("expanded_shortcuts", False)
        decoded.setdefault("expanded_keybinds", False)

        persistence.insert_entry_at(decoded, len(persistence.get_entries()))
        from . import keymap_manager

        keymap_manager.activate_entry(decoded)
        mark_unsaved()
        _redraw(context)
        self.report({"INFO"}, "Keymapper: Entry pasted successfully.")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


class KEYMAPPER_OT_AddPreset(Operator):
    """Add entries from a built-in preset"""

    bl_idname = "keymapper.add_preset"
    bl_label = "Shortcut Entry Presets"
    bl_options = {"INTERNAL"}

    def _preset_is_applied(self, preset: dict) -> bool:
        """Check whether the given preset is already applied.

        Two signals are checked, in order:
          1. Provenance: any existing entry has source_preset_id == preset["id"].
             This is the authoritative signal for presets applied since v0.9.89.
          2. Signature: every preset entry's operator_ids matches some
             existing entry's operator_ids AND the folder exists.
             This is a fallback for entries from older versions (or imported
             JSON) that don't carry provenance fields yet.
        """
        entries = persistence.get_entries()
        # 1) Provenance check
        preset_id = preset.get("id", "")
        if preset_id and any(
            e.get("source_preset_id", "") == preset_id for e in entries
        ):
            return True
        # 2) Signature fallback — requires a non-empty entry list and
        #    matching folder if the preset declares one.
        folders = persistence.get_folders()
        folder_name = preset.get("folder_name", "")
        if folder_name:
            folder_exists = any(f.get("label") == folder_name for f in folders)
            if not folder_exists:
                return False
        preset_entries = preset.get("entries", [])
        if not preset_entries:
            return False
        existing_op_ids = {e.get("operator_ids", "") for e in entries}
        return all(
            pe.get("operator_ids", "") in existing_op_ids for pe in preset_entries
        )

    def _preset_has_edits(self, preset: dict) -> bool:
        from .database.presets import find_preset_template, preset_entry_differs
        pid = preset.get("id")
        for e in persistence.get_entries():
            if e.get("source_preset_id") != pid:
                continue
            tpl = find_preset_template(e)
            if tpl and preset_entry_differs(e, tpl):
                return True
        return False

    def _entry_has_edits(self, preset_id: str, key: str) -> bool:
        from .database.presets import find_preset_template, preset_entry_differs
        for e in persistence.get_entries():
            if e.get("source_preset_id") != preset_id:
                continue
            if e.get("source_preset_key", e.get("custom_label", "")) != key:
                continue
            tpl = find_preset_template(e)
            return bool(tpl and preset_entry_differs(e, tpl))
        return False

    def _preset_apply_state(self, preset: dict) -> str:
        """Return 'none', 'some', or 'all' based on how many of the preset's
        entries currently exist. Counts by operator_ids presence so a single
        mini-button add reads as 'some', not the whole folder as applied."""
        preset_entries = preset.get("entries", [])
        if not preset_entries:
            return "none"
        existing_op_ids = {
            e.get("operator_ids", "") for e in persistence.get_entries()
        }
        present = sum(
            1
            for pe in preset_entries
            if pe.get("operator_ids", "") in existing_op_ids
        )
        if present == 0:
            return "none"
        if present == len(preset_entries):
            return "all"
        return "some"

    def _entry_is_applied(self, preset: dict, entry_tpl: dict) -> bool:
        """True if this specific preset entry already exists (by operator_ids
        + source_preset_id provenance, falling back to operator_ids match)."""
        entries = persistence.get_entries()
        preset_id = preset.get("id", "")
        op_ids = entry_tpl.get("operator_ids", "")
        for e in entries:
            if e.get("operator_ids", "") == op_ids:
                # provenance match is strongest; op_ids match is the fallback
                if not preset_id or e.get("source_preset_id", "") in (preset_id, ""):
                    return True
        return False

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=340)

    def draw(self, context):
        from .database.presets import (
            addon_is_installed,
            find_applied_preset_in_category,
            get_category_label,
            get_presets_by_category,
            is_category_mutually_exclusive,
        )

        layout = self.layout
        host = _host()
        by_cat = get_presets_by_category()
        entries = persistence.get_entries()

        layout.label(text="Shortcut presets", icon="PRESET")

        # ---- Add All button (top) ----
        all_row = layout.row(align=True)
        all_row.scale_y = 1.1
        all_applied = True
        for _cat, _presets in by_cat.items():
            for _p in _presets:
                if self._preset_apply_state(_p) != "all":
                    all_applied = False
                    break
            if not all_applied:
                break
        all_row.enabled = not all_applied
        all_row.operator(
            "keymapper.add_all_presets",
            text="✓ All added" if all_applied else "Add All",
            icon="CHECKMARK" if all_applied else "ADD",
        )
        _any_edits = any(self._preset_has_edits(_p)
                         for _ps in by_cat.values() for _p in _ps)
        _rr = all_row.row(align=True)
        _rr.enabled = _any_edits
        _rr.operator(
            "keymapper.reset_preset", text="", icon="LOOP_BACK"
        ).scope = "all"
        layout.separator()

        for cat_id, presets in by_cat.items():
            visible = []
            for preset in presets:
                # NOTE: an old filter here hid a whole folder when its FIRST
                # entry's `source_app` said "bforartists" — but that field is
                # an export-origin stamp (37 of ~88 entries carry it), not a
                # compatibility flag, so five folders vanished on stock
                # Blender. Removed: presets show on both hosts; a genuinely
                # host-only entry would surface via the unregistered-ops
                # handling. If truly host-exclusive presets ever exist, give
                # the data a real `hosts` field instead.
                req = preset.get("requires_addon", "")
                if req and not addon_is_installed(req):
                    continue
                visible.append(preset)
            if not visible:
                continue

            cat_label = get_category_label(cat_id)
            if cat_label:
                layout.label(text=cat_label, icon="NONE")

            applied_in_cat = ""
            if is_category_mutually_exclusive(cat_id):
                applied_in_cat = find_applied_preset_in_category(entries, cat_id)

            for preset in visible:
                count = len(preset.get("entries", []))
                is_active_in_excl = preset["id"] == applied_in_cat

                # --- Folder button row: caret toggle + apply-all-in-folder ---
                # The caret must stay clickable even when the folder is already
                # applied, so it lives in the outer row (never disabled) while
                # only the apply button sits in an enable-gated sub-row.
                row = layout.row(align=True)

                wm = context.window_manager
                expanded = bool(
                    wm.get(f"keymapper_presetfold_{preset['id']}", False)
                )
                if count:
                    caret = row.operator(
                        "keymapper.toggle_preset_folder",
                        text="",
                        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
                        emboss=False,
                    )
                    caret.preset_id = preset["id"]

                apply_sub = row.row(align=True)
                if is_category_mutually_exclusive(cat_id):
                    apply_sub.enabled = not is_active_in_excl
                    icon_str = "CHECKMARK" if is_active_in_excl else "NONE"
                    prefix = "✓ " if is_active_in_excl else ""
                else:
                    # Three-state: none / some / all. Only disable when ALL of
                    # the folder's entries are present. 'some' stays clickable
                    # (adds the rest) and shows a dash icon.
                    state = self._preset_apply_state(preset)
                    apply_sub.enabled = state != "all"
                    if state == "all":
                        icon_str = "CHECKMARK"
                        prefix = "✓ "
                    elif state == "some":
                        icon_str = "REMOVE"  # dash — partially applied
                        prefix = ""
                    else:
                        icon_str = "NONE"
                        prefix = ""

                count_str = f"  ({count})" if count else "  (clear)"
                op = apply_sub.operator(
                    "keymapper.apply_preset",
                    text=f"{prefix}{preset['label']}{count_str}",
                    icon=icon_str,
                )
                op.preset_id = preset["id"]
                op.entry_index = -1

                _fr = row.row(align=True)
                _fr.enabled = self._preset_has_edits(preset)
                _fre = _fr.operator(
                    "keymapper.reset_preset", text="", icon="LOOP_BACK"
                )
                _fre.scope = "preset"
                _fre.preset_id = preset["id"]

                # --- Per-entry mini buttons (only when folder is expanded) ---
                if expanded:
                    mini_col = layout.column(align=True)
                    mini_col.scale_y = 0.78
                    for idx, entry_tpl in enumerate(preset.get("entries", [])):
                        e_applied = self._entry_is_applied(preset, entry_tpl)
                        mrow = mini_col.row(align=True)
                        label = (
                            entry_tpl.get("custom_label")
                            or entry_tpl.get("display_name")
                            or "?"
                        )
                        _add = mrow.row(align=True)
                        _add.enabled = not e_applied
                        from .panel import _entry_op_icons
                        _icons = _entry_op_icons(entry_tpl)
                        _ic = _icons[0] if _icons else "DOT"
                        mop = _add.operator(
                            "keymapper.apply_preset",
                            text=f"      {'✓ ' if e_applied else ''}{label}",
                            icon=_ic,
                            emboss=True,
                        )
                        mop.preset_id = preset["id"]
                        mop.entry_index = idx
                        _key = entry_tpl.get("custom_label", "")
                        _er = mrow.row(align=True)
                        _er.enabled = self._entry_has_edits(preset["id"], _key)
                        _ere = _er.operator(
                            "keymapper.reset_preset", text="", icon="LOOP_BACK"
                        )
                        _ere.scope = "entry"
                        _ere.preset_id = preset["id"]
                        _ere.preset_key = _key
                layout.separator(factor=0.4)

    def execute(self, context):
        return {"FINISHED"}


class KEYMAPPER_OT_ApplyPreset(Operator):
    """Apply a preset — adds entries and creates folder if needed."""

    bl_idname = "keymapper.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    preset_id: StringProperty()
    # When >= 0, apply only that single entry from the preset (used by the
    # per-entry mini-buttons). Default -1 means apply all entries.
    entry_index: IntProperty(default=-1)

    # Filled by invoke() when a replacement is needed; consumed by draw()
    # and execute(). Stored as a JSON list of entry_ids on the WM so the
    # popup callback can find it (Blender re-instantiates the operator
    # between invoke and execute for invoke_props_dialog).
    _WM_REPLACE_KEY = "keymapper_preset_replace_pending"

    def _find_replacement_target(self) -> tuple[str, list[dict]]:
        """If this preset's category is mutually exclusive and a different
        preset in the same category is currently applied, return
        (old_preset_id, [entries_to_remove]). Otherwise ("", []).
        """
        from .database.presets import (
            find_applied_preset_in_category,
            find_entries_from_preset,
            get_preset_by_id,
            is_category_mutually_exclusive,
        )

        preset = get_preset_by_id(self.preset_id)
        if not preset:
            return ("", [])
        cat_id = preset.get("category", "")
        if not is_category_mutually_exclusive(cat_id):
            return ("", [])
        entries = persistence.get_entries()
        applied_id = find_applied_preset_in_category(entries, cat_id)
        # If nothing applied, or the same preset is already applied, no swap
        if not applied_id or applied_id == self.preset_id:
            return ("", [])
        old_entries = find_entries_from_preset(entries, applied_id)
        return (applied_id, old_entries)

    def invoke(self, context, event):
        import json as _json

        wm = context.window_manager
        # Per-entry adds are always additive — never trigger the exclusive-swap
        # confirm dialog.
        if self.entry_index < 0:
            old_preset_id, old_entries = self._find_replacement_target()
        else:
            old_preset_id, old_entries = ("", [])
        if old_entries:
            # Stash the entry_ids to remove on the WM so execute() can use them
            wm[self._WM_REPLACE_KEY] = _json.dumps(
                {
                    "new_preset_id": self.preset_id,
                    "old_preset_id": old_preset_id,
                    "old_entry_ids": [e.get("entry_id", "") for e in old_entries],
                }
            )
            return wm.invoke_props_dialog(self, width=420)
        # No replacement needed — clear any stale pending state, run normally
        wm.pop(self._WM_REPLACE_KEY, None)
        return self.execute(context)

    def draw(self, context):
        """Option D confirm popup: list the entries that will be removed."""
        import json as _json

        from .database.presets import get_category_label, get_preset_by_id

        layout = self.layout
        wm = context.window_manager
        try:
            pending = _json.loads(wm.get(self._WM_REPLACE_KEY, "{}") or "{}")
        except Exception:
            pending = {}
        new_preset = get_preset_by_id(pending.get("new_preset_id", ""))
        old_preset = get_preset_by_id(pending.get("old_preset_id", ""))
        old_ids = pending.get("old_entry_ids", [])
        if not new_preset:
            layout.label(text="Preset not found.", icon=_safe_icon("STATUS_WARNING", "ERROR"))
            return

        cat_label = get_category_label(new_preset.get("category", ""))
        old_label = old_preset["label"] if old_preset else "Unknown preset"

        # Header explanation
        box = layout.box()
        hdr = box.row(align=True)
        hdr.label(
            text=f"Replace {cat_label} preset?",
            icon=_safe_icon("STATUS_WARNING", "ERROR"),
        )
        info = box.column(align=True)
        info.scale_y = 0.85
        info.label(text=f"'{old_label}' is currently active.")
        new_count = len(new_preset.get("entries", []))
        if new_count:
            info.label(text=f"Applying '{new_preset['label']}' will:")
        else:
            info.label(text=f"Applying '{new_preset['label']}' will:")

        # What will be removed
        rm_box = layout.box()
        rm_box.label(text=f"Remove {len(old_ids)} entries:", icon="TRASH")
        rm_col = rm_box.column(align=True)
        rm_col.scale_y = 0.85
        entries_by_id = {e.get("entry_id", ""): e for e in persistence.get_entries()}
        for eid in old_ids:
            e = entries_by_id.get(eid)
            if not e:
                continue
            display = e.get("custom_label") or e.get("display_name") or "?"
            rm_col.label(text=f"  • {display}")

        # What will be added (skip for the "clear" uninstaller preset)
        if new_count:
            add_box = layout.box()
            add_box.label(text=f"Add {new_count} entries:", icon="ADD")
            add_col = add_box.column(align=True)
            add_col.scale_y = 0.85
            for tpl in new_preset.get("entries", []):
                display = tpl.get("custom_label") or tpl.get("display_name") or "?"
                add_col.label(text=f"  • {display}")

        layout.label(
            text="This cannot be undone via Ctrl+Z. Continue?", icon="QUESTION"
        )

    def _remove_old_preset(self, old_entry_ids: list, context) -> int:
        """Remove the listed entries: KMI cleanup, restore defaults, drop
        from persistence, and remove any folder that becomes empty.

        Returns the number of entries actually removed.
        """
        from . import keymap_manager

        removed = 0
        affected_folder_ids = set()
        for entry_id in old_entry_ids:
            entry = persistence.get_entry_by_id(entry_id)
            if not entry:
                continue
            fid = entry.get("folder_id", "")
            if fid:
                affected_folder_ids.add(fid)
            keymap_manager.delete_entry(entry)
            if persistence.remove_entry(entry_id):
                removed += 1
        # Clean up any folder that's now empty
        remaining = persistence.get_entries()
        for fid in affected_folder_ids:
            still_used = any(e.get("folder_id", "") == fid for e in remaining)
            if not still_used:
                persistence.delete_folder(fid, delete_entries=False)
        return removed

    @staticmethod
    def _insert_preset_entries(preset, preset_id, preset_entries):
        """Build and insert one preset's entries into persistence (no conflict
        scan, no activation — caller does that once). Returns count added."""
        import json as _json
        import uuid as _uuid

        from .database.presets import addon_is_installed

        category_id = preset.get("category", "")
        folder_name = preset.get("folder_name", "")
        folder_id = ""
        if folder_name and preset_entries:
            existing = next(
                (
                    f
                    for f in persistence.get_folders()
                    if f.get("label", "") == folder_name
                ),
                None,
            )
            if existing:
                folder_id = existing["folder_id"]
            else:
                new_folder = persistence.add_folder(folder_name)
                folder_id = new_folder["folder_id"]

        added = 0
        base_idx = len(persistence.get_entries())
        for i, entry_tpl in enumerate(preset_entries):
            entry = dict(entry_tpl)
            entry["entry_id"] = str(_uuid.uuid4())
            entry["folder_id"] = folder_id
            entry["sort_index"] = base_idx + i

            conditional = entry_tpl.get("conditional_operator_ids", [])
            if conditional:
                try:
                    ops = _json.loads(entry.get("operator_ids", "[]"))
                except Exception:
                    ops = []
                for cond in conditional:
                    signal = cond.get("requires_op", cond.get("id", ""))
                    if signal and addon_is_installed(signal):
                        ops.append(
                            {
                                "id": cond["id"],
                                "props": cond.get("props", {}),
                                "context": cond.get("context", ""),
                            }
                        )
                entry["operator_ids"] = _json.dumps(ops)
                entry.pop("conditional_operator_ids", None)

            entry.setdefault("selected", False)
            entry.setdefault("internal_conflicts", [])
            entry.setdefault("shortcut_conflicts_internal", [])
            entry.setdefault("keybind_conflicts_internal", [])
            entry.setdefault("shortcut_conflicts_external", [])
            entry.setdefault("keybind_conflicts_external", [])
            entry.setdefault("expanded_entry", False)
            entry.setdefault("expanded_shortcuts", False)
            entry.setdefault("expanded_keybinds", False)
            entry["source_preset_id"] = preset_id
            entry["source_preset_category"] = category_id
            entry["source_preset_key"] = preset_entries[i].get("custom_label", "")
            # Migrate so preset entries carry the same defaulted fields
            # (button fields etc.) as loaded/imported entries — keeps entry
            # dicts uniform instead of relying on .get() fallbacks.
            persistence.insert_entry_at(persistence._migrate_entry(entry), base_idx + i)
            added += 1
        return added

    @staticmethod
    def _finalize_added(context, base_idx):
        """Run the conflict scan + activation once for all entries inserted at
        or after base_idx. Shared by single-preset apply and Add-All."""
        from . import keymap_manager

        try:
            from . import conflict_detector
            from . import keyconfig_store as _ks

            if not _ks.is_scanned():
                _ks.do_full_scan()
            new_entries = persistence.get_entries()[base_idx:]
            for entry in new_entries:
                conflict_detector.update_entry_external_conflicts(entry, force=True)
            persistence._write_to_prefs()
        except Exception as e:
            print(f"[Keymapper] Preset conflict scan error: {e}")

        for entry in persistence.get_entries()[base_idx:]:
            keymap_manager.activate_entry(entry)
        keymap_manager.schedule_conflict_disable()

        mark_unsaved()
        _run_conflict_scan()
        _redraw(context)

    def execute(self, context):
        import json as _json

        from .database.presets import get_preset_by_id

        wm = context.window_manager
        preset = get_preset_by_id(self.preset_id)
        if not preset:
            self.report({"WARNING"}, f"Preset not found: {self.preset_id}")
            return {"CANCELLED"}

        # Step 1: if this run was preceded by a confirm popup, remove the
        # old preset's entries first.
        removed = 0
        try:
            pending = _json.loads(wm.get(self._WM_REPLACE_KEY, "{}") or "{}")
        except Exception:
            pending = {}
        if pending.get("new_preset_id") == self.preset_id:
            old_ids = pending.get("old_entry_ids", []) or []
            if old_ids:
                removed = self._remove_old_preset(old_ids, context)
            wm.pop(self._WM_REPLACE_KEY, None)

        # Step 2: apply the new preset's entries (may be empty for the
        # "clear navigation" uninstaller).
        preset_entries = preset.get("entries", [])
        # Per-entry mode: when entry_index >= 0, apply only that one entry.
        if self.entry_index >= 0:
            if self.entry_index < len(preset_entries):
                preset_entries = [preset_entries[self.entry_index]]
            else:
                preset_entries = []

        base_idx = len(persistence.get_entries())
        added = self._insert_preset_entries(
            preset, self.preset_id, preset_entries
        )
        self._finalize_added(context, base_idx)

        # Build a status message that reflects what actually happened
        if removed and added:
            msg = (
                f"Keymapper: Replaced {removed} entries with "
                f"{added} from '{preset['label']}'."
            )
        elif removed and not added:
            msg = f"Keymapper: Removed {removed} entries ({preset['label']})."
        elif added:
            msg = f"Keymapper: Added {added} entries from preset '{preset['label']}'."
        else:
            msg = f"Keymapper: Nothing to do for preset '{preset['label']}'."
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class KEYMAPPER_OT_ResetPreset(Operator):
    """Revert edited preset entries to their preset definition.

    scope='all' resets every edited preset entry; scope='preset' resets one
    folder; scope='entry' resets a single entry (by source_preset_key)."""
    bl_idname = "keymapper.reset_preset"
    bl_label = "Reset Preset"
    bl_description = "Revert edited entries back to their preset definition"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}
    scope: StringProperty(default="all")
    preset_id: StringProperty()
    preset_key: StringProperty()

    def execute(self, context):
        from .database.presets import find_preset_template, preset_entry_differs

        n = 0
        for e in list(persistence.get_entries()):
            if not e.get("source_preset_id"):
                continue
            if self.scope == "preset" and e.get("source_preset_id") != self.preset_id:
                continue
            if self.scope == "entry" and (
                e.get("source_preset_id") != self.preset_id
                or e.get("source_preset_key", e.get("custom_label", "")) != self.preset_key
            ):
                continue
            tpl = find_preset_template(e)
            if tpl and preset_entry_differs(e, tpl):
                bpy.ops.keymapper.restore_preset_entry(entry_id=e["entry_id"])
                n += 1
        self.report({"INFO"}, f"Keymapper: Reset {n} entr{'y' if n == 1 else 'ies'}.")
        return {"FINISHED"}


class KEYMAPPER_OT_AddAllPresets(Operator):
    """Add every catalog preset (all folders, all entries)."""

    bl_idname = "keymapper.add_all_presets"
    bl_label = "Add All Presets"
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    def execute(self, context):
        from .database.presets import PRESETS

        base_idx = len(persistence.get_entries())
        existing_op_ids = {
            e.get("operator_ids", "") for e in persistence.get_entries()
        }

        total_added = 0
        folders_touched = 0
        for preset in PRESETS:
            pid = preset.get("id", "")
            if not pid:
                continue
            # Skip entries already present (by operator_ids) so re-running
            # Add-All doesn't duplicate.
            entries = [
                e
                for e in preset.get("entries", [])
                if e.get("operator_ids", "") not in existing_op_ids
            ]
            if not entries:
                continue
            added = KEYMAPPER_OT_ApplyPreset._insert_preset_entries(
                preset, pid, entries
            )
            if added:
                folders_touched += 1
                total_added += added
                for e in entries:
                    existing_op_ids.add(e.get("operator_ids", ""))

        # One conflict scan + activation pass for everything just inserted.
        if total_added:
            KEYMAPPER_OT_ApplyPreset._finalize_added(context, base_idx)

        self.report(
            {"INFO"},
            f"Keymapper: Added {total_added} entries "
            f"across {folders_touched} folders.",
        )
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

_classes = (
    KEYMAPPER_IconItem,
    KEYMAPPER_UL_icons,
    KEYMAPPER_SearchItem,
    KEYMAPPER_ContextPathItem,
    KEYMAPPER_NumericItem,
    KEYMAPPER_OT_SavePreferences,
    KEYMAPPER_OT_OpenInlineForm,
    KEYMAPPER_OT_EditEntry,
    KEYMAPPER_OT_QuickAddSetFolder,
    KEYMAPPER_MT_QuickAddFolder,
    KEYMAPPER_OT_OpenFullEditor,
    KEYMAPPER_OT_FormConfirm,
    KEYMAPPER_OT_FormCancel,
    KEYMAPPER_OT_FormToggleBrowse,
    KEYMAPPER_OT_ToggleNamingMode,
    KEYMAPPER_OT_FormSetCategory,
    KEYMAPPER_OT_FormAddOp,
    KEYMAPPER_OT_FormRemoveLastOp,
    KEYMAPPER_OT_ShowUpdate,
    KEYMAPPER_OT_TogglePreviewCard,
    KEYMAPPER_OT_FormToggleBrowseSubcat,
    KEYMAPPER_OT_FormToggleContextGroup,
    KEYMAPPER_OT_TogglePresetFolder,
    KEYMAPPER_OT_FormToggleOp,
    KEYMAPPER_OT_FormSetOpProp,
    KEYMAPPER_OT_FormRemoveOp,
    KEYMAPPER_OT_OpenBrowsePopup,
    KEYMAPPER_OT_OpenPropPicker,
    KEYMAPPER_OT_IconHint,
    KEYMAPPER_OT_ToggleExtraOptions,
    KEYMAPPER_OT_UnsetKmiProperty,
    KEYMAPPER_OT_ResetButtonLocations,
    KEYMAPPER_OT_OpenButtonLocPicker,
    KEYMAPPER_OT_ToggleEntryButtonLocation,
    KEYMAPPER_OT_ToggleEntryButtonVisibility,
    KEYMAPPER_OT_ResetEntryButtonLocations,
    KEYMAPPER_OT_OpenEntryLocPicker,
    KEYMAPPER_OT_DialogCommit,
    KEYMAPPER_OT_OpenDetectCtxPicker,
    KEYMAPPER_OT_ResetOpContext,
    KEYMAPPER_OT_ResetDetectCtx,
    KEYMAPPER_OT_ResetSelOps,
    KEYMAPPER_OT_ResetOpProp,
    KEYMAPPER_OT_OpenOpCtxPicker,
    KEYMAPPER_OT_FormToggleSelPanel,
    KEYMAPPER_OT_FormToggleContext,
    KEYMAPPER_OT_ClearKeyModifier,
    KEYMAPPER_OT_ToggleKmiMod,
    KEYMAPPER_OT_DeleteEntry,
    KEYMAPPER_OT_MoveEntryUp,
    KEYMAPPER_OT_MoveEntryDown,
    KEYMAPPER_OT_DuplicateEntry,
    KEYMAPPER_OT_InertDuplicateInfo,
    KEYMAPPER_OT_AdoptedInfo,
    KEYMAPPER_OT_ShowConflictInfo,
    KEYMAPPER_OT_ScanKeyconfig,
    KEYMAPPER_OT_RestoreAllKMIs,
    KEYMAPPER_OT_RestoreAllKMIsConfirm,
    KEYMAPPER_OT_KeyconfigScanPopup,
    KEYMAPPER_OT_KeyconfigScanIncremental,
    KEYMAPPER_OT_KeyconfigScanFull,
    KEYMAPPER_OT_AddExtraKeybind,
    KEYMAPPER_OT_RemoveExtraKeybindAt,
    KEYMAPPER_OT_RemoveExtraKeybind,
    KEYMAPPER_OT_SetExtraKeybindProp,
    KEYMAPPER_OT_ClearSelection,
    KEYMAPPER_OT_SelectEntry,
    KEYMAPPER_OT_ToggleExpand,
    KEYMAPPER_OT_ToggleEnabled,
    KEYMAPPER_OT_RestorePresetEntry,
    KEYMAPPER_OT_PickIcon,
    KEYMAPPER_OT_SetIconPick,
    KEYMAPPER_OT_ToggleIconCat,
    KEYMAPPER_OT_AddEntry,
    KEYMAPPER_OT_FormBrowseSearch,
    KEYMAPPER_OT_FormSetOpContext,
    KEYMAPPER_OT_FormToggleOpContext,
    KEYMAPPER_OT_FormToggleOpFlag,
    KEYMAPPER_OT_FormToggleCtxGroup,
    KEYMAPPER_OT_FormSearchContext,
    KEYMAPPER_OT_FormSearchPropValue,
    KEYMAPPER_OT_RefreshOperators,
    KEYMAPPER_OT_ToggleSimplifiedBrowse,
    KEYMAPPER_OT_FormToggleMultiOp,
    KEYMAPPER_OT_FormToggleFactoryBinding,
    KEYMAPPER_OT_DeepScanOperators,
    KEYMAPPER_OT_ExportJSON,
    KEYMAPPER_OT_ImportJSON,
    KEYMAPPER_OT_AddFromContext,
    KEYMAPPER_OT_CopyEntry,
    KEYMAPPER_OT_PasteEntry,
    KEYMAPPER_OT_AddPreset,
    KEYMAPPER_OT_ApplyPreset,
    KEYMAPPER_OT_AddAllPresets,
    KEYMAPPER_OT_ResetPreset,
    KEYMAPPER_OT_AddFolder,
    KEYMAPPER_OT_DeleteFolder,
    KEYMAPPER_OT_DeleteFolderConfirm,
    KEYMAPPER_OT_SelectFolder,
    KEYMAPPER_OT_SimplifiedToggleMod,
    KEYMAPPER_OT_SimplifiedValueMenu,
    KEYMAPPER_OT_SimplifiedSetValue,
    KEYMAPPER_OT_SimplifiedCaptureKey,
    KEYMAPPER_OT_SimplifiedCaptureKeyModifier,
    KEYMAPPER_OT_StartFolderRename,
    KEYMAPPER_OT_ConfirmFolderRename,
    KEYMAPPER_OT_ToggleFolderCollapse,
    KEYMAPPER_OT_SetEntryFolder,
    KEYMAPPER_OT_FolderPicker,
    KEYMAPPER_OT_MoveFolderUp,
    KEYMAPPER_OT_MoveFolderDown,
    KEYMAPPER_OT_ToggleConflictReenabled,
    KEYMAPPER_OT_ShowExternalConflictInfo,
    KEYMAPPER_OT_ResetPref,
    KEYMAPPER_OT_StatInfo,
    KEYMAPPER_OT_ConflictWarningInfo,
    KEYMAPPER_OT_UnregisteredOpsInfo,
    KEYMAPPER_OT_FormToggleUseKeybind,
    KEYMAPPER_OT_FormToggleUseButton,
    KEYMAPPER_OT_FormToggleButtonLabel,
    KEYMAPPER_OT_FormToggleButtonIcon,
    KEYMAPPER_OT_FormToggleButtonConflicts,
    KEYMAPPER_OT_ToggleButtonLocation,
    KEYMAPPER_OT_FormToggleButtonLocDropdown,
    KEYMAPPER_OT_InternalConflictInfo,
    KEYMAPPER_OT_ConflictOpLabel,
    KEYMAPPER_OT_KbcvSetMode,
    KEYMAPPER_OT_ToggleDetectCtxSection,
    KEYMAPPER_OT_ToggleDetectCtx,
    KEYMAPPER_OT_ConflictDisabledInfo,
    KEYMAPPER_OT_ConflictReenabledInfo,
    KEYMAPPER_OT_ShowExternalShortcutInfo,
    KEYMAPPER_OT_ShowExternalKeybindInfo,
    KEYMAPPER_OT_ClosePopup,
)


def _search_update(self, context):
    for area in context.screen.areas:
        area.tag_redraw()


def register():
    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            # Already registered — unregister and re-register cleanly
            try:
                bpy.utils.unregister_class(cls)
                bpy.utils.register_class(cls)
            except Exception as e:
                print(f"[Keymapper] Could not register {cls}: {e}")

    bpy.types.WindowManager.keymapper_ctx_searches = bpy.props.CollectionProperty(
        type=KEYMAPPER_SearchItem
    )
    bpy.types.WindowManager.keymapper_menu_searches = bpy.props.CollectionProperty(
        type=KEYMAPPER_SearchItem
    )
    bpy.types.WindowManager.keymapper_prop_texts = bpy.props.CollectionProperty(
        type=KEYMAPPER_SearchItem
    )
    bpy.types.WindowManager.keymapper_context_path_props = bpy.props.CollectionProperty(
        type=KEYMAPPER_ContextPathItem
    )
    bpy.types.WindowManager.keymapper_int_props = bpy.props.CollectionProperty(
        type=KEYMAPPER_NumericItem
    )
    bpy.types.WindowManager.keymapper_float_props = bpy.props.CollectionProperty(
        type=KEYMAPPER_NumericItem
    )
    bpy.types.WindowManager.keymapper_extra_keybinds = bpy.props.StringProperty(
        name="Extra Keybinds",
        description="JSON list of additional keybind slots",
        default="[]",
    )
    # Per-slot any state (can't trust kmi.any due to Blender's internal resets)
    for _slot_i in range(8):
        setattr(
            bpy.types.WindowManager,
            f"keymapper_kmi_any_{_slot_i}",
            bpy.props.BoolProperty(name="Any", default=False),
        )
    bpy.types.WindowManager.keymapper_search_prop = bpy.props.StringProperty(
        name="Search",
        default="",
        update=_search_update,
    )
    bpy.types.WindowManager.keymapper_form_label = bpy.props.StringProperty(
        name="Enter label...",
        description="Label for this shortcut entry",
        default="",
    )
    bpy.types.WindowManager.keymapper_form_button_label = bpy.props.StringProperty(
        name="Button label...",
        description=(
            "Custom text for this entry's button. Leave blank to use the "
            "entry's own label"
        ),
        default="",
    )
    # Hint prop — name is updated dynamically to show operator name as placeholder
    # Active folder — single source of truth for both panels.
    # "" = Unsorted / none selected; a real folder id = that folder.
    bpy.types.WindowManager.keymapper_selected_folder_id = bpy.props.StringProperty(
        default=""
    )
    bpy.types.WindowManager.keymapper_renaming_folder_id = bpy.props.StringProperty(
        default=""
    )

    def _folder_rename_update(self, context):
        folder_id = getattr(self, "keymapper_renaming_folder_id", "")
        new_label = getattr(self, "keymapper_folder_rename_text", "").strip()
        if folder_id and new_label:
            from . import persistence as _p

            _p.update_folder(folder_id, {"label": new_label})

    bpy.types.WindowManager.keymapper_folder_rename_text = bpy.props.StringProperty(
        name="Folder Name",
        default="",
        update=_folder_rename_update,
    )
    bpy.types.WindowManager.keymapper_form_label_hint = bpy.props.StringProperty(
        name="Add Duplicate",
        description="Label placeholder",
        default="",
    )
    bpy.types.WindowManager.keymapper_icon_pick = bpy.props.StringProperty(
        name="Icon",
        description="Selected icon in the picker",
        default="",
    )

    def _icon_repopulate(self, context):
        try:
            KEYMAPPER_OT_PickIcon._populate_static(context)
        except Exception:
            pass

    bpy.types.WindowManager.keymapper_icon_filter = bpy.props.StringProperty(
        name="Filter",
        description="Filter icons by name",
        default="",
        options={"TEXTEDIT_UPDATE"},
        update=_icon_repopulate,
    )
    bpy.types.WindowManager.keymapper_icon_category = bpy.props.EnumProperty(
        name="Category",
        items=_icon_categories_enum,
        update=_icon_repopulate,
    )
    bpy.types.WindowManager.keymapper_icon_items = bpy.props.CollectionProperty(
        type=KEYMAPPER_IconItem,
    )
    def _icon_index_update(self, context):
        if getattr(KEYMAPPER_OT_PickIcon, "_syncing", False):
            return
        wm = context.window_manager
        coll = wm.keymapper_icon_items
        idx = wm.keymapper_icon_index
        if 0 <= idx < len(coll):
            wm.keymapper_icon_pick = coll[idx].icon_id

    bpy.types.WindowManager.keymapper_icon_index = bpy.props.IntProperty(
        default=0, update=_icon_index_update
    )
    _ensure_scratch_kmi()
    _scratch_kmi_set_active(False)  # inactive until form opens
    bpy.types.UI_MT_button_context_menu.append(_draw_keymapper_context_menu)
    print("[Keymapper] Operators registered.")


def unregister():
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    try:
        del bpy.types.WindowManager.keymapper_ctx_searches
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.keymapper_menu_searches
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.keymapper_prop_texts
        del bpy.types.WindowManager.keymapper_context_path_props
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.keymapper_int_props
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.keymapper_float_props
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.keymapper_search_prop
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.keymapper_form_label
        del bpy.types.WindowManager.keymapper_form_button_label
    except Exception:
        pass
    try:
        del bpy.types.WindowManager.keymapper_selected_folder_id
        del bpy.types.WindowManager.keymapper_renaming_folder_id
        del bpy.types.WindowManager.keymapper_folder_rename_text
        del bpy.types.WindowManager.keymapper_form_label_hint
        del bpy.types.WindowManager.keymapper_icon_pick
        del bpy.types.WindowManager.keymapper_icon_filter
        del bpy.types.WindowManager.keymapper_icon_category
        del bpy.types.WindowManager.keymapper_icon_items
        del bpy.types.WindowManager.keymapper_icon_index
    except Exception:
        pass
    _remove_scratch_kmi()
    try:
        clear_props_kmis()
    except Exception:
        pass
    try:
        bpy.types.UI_MT_button_context_menu.remove(_draw_keymapper_context_menu)
    except Exception:
        pass
    print("[Keymapper] Operators unregistered.")
