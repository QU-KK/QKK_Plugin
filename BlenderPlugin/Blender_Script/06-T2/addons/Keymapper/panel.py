"""
panel.py — Keymapper N-Panel (multi-operator, inline form, final design)
"""

import bpy
from bpy.types import Panel, UILayout

from . import persistence
from .database.bfa_ops import get_friendly_name
from .database.categories import CATEGORIES, get_category_by_id
from .preferences import get_prefs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Cache of valid icon enum identifiers for the running Blender build. Some
# icons get renamed or removed between versions (e.g. LASTOPERATOR was valid
# in Blender ≤5.1.1 but removed in 5.1.2), and passing a missing icon to
# UILayout.operator()/label() raises a TypeError that crashes the whole panel
# draw. We resolve icons at runtime against this set with a safe fallback.
_VALID_ICONS: set | None = None


def _get_valid_icons() -> set:
    global _VALID_ICONS
    if _VALID_ICONS is None:
        try:
            enum = (
                bpy.types.UILayout.bl_rna.functions["operator"]
                .parameters["icon"]
                .enum_items
            )
            _VALID_ICONS = {item.identifier for item in enum}
        except Exception:
            # If introspection fails for any reason, fall back to an empty set
            # so safe_icon() always returns its fallback (never crashes).
            _VALID_ICONS = set()
    return _VALID_ICONS


def safe_icon(preferred: str, *fallbacks: str) -> str:
    """Return the first icon identifier that exists in the running Blender
    build, trying `preferred` then each fallback. 'BLANK1' is always valid
    (it's Blender's empty-slot placeholder) so it's the final guaranteed
    fallback. This prevents version-specific icon names from crashing the
    panel draw on Blender builds where they don't exist.
    """
    valid = _get_valid_icons()
    if not valid:
        # Introspection unavailable — trust the preferred icon and hope.
        return preferred
    for candidate in (preferred, *fallbacks):
        if candidate in valid:
            return candidate
    return "BLANK1"


_kmi_type_names: dict = {}  # cache: "RIGHTMOUSE" -> "Right Mouse"


def _key_display_name(key: str) -> str:
    """Return Blender's human-readable name for a key type identifier."""
    global _kmi_type_names
    if not _kmi_type_names:
        try:
            import bpy

            items = bpy.types.KeyMapItem.bl_rna.properties["type"].enum_items
            _kmi_type_names = {item.identifier: item.name for item in items}
        except Exception:
            pass
    return _kmi_type_names.get(key, key)


_EVENT_TYPE_DISPLAY = {
    "ANY": "Any",
    "PRESS": "Press",
    "RELEASE": "Release",
    "CLICK": "Click",
    "DOUBLE_CLICK": "Double Click",
    "CLICK_DRAG": "Drag",
    "NOTHING": "Nothing",
}

# Mouse/NDOF/trackpad keys (mirrors operators._mouse_keys). For these map
# types Blender hides Repeat entirely; we gray it out instead.
_MOUSE_KEYS = {
    "LEFTMOUSE", "RIGHTMOUSE", "MIDDLEMOUSE",
    "BUTTON4MOUSE", "BUTTON5MOUSE", "BUTTON6MOUSE", "BUTTON7MOUSE",
    "MOUSEMOVE", "TRACKPADPAN", "TRACKPADZOOM", "MOUSEROTATE",
    "WHEELUPMOUSE", "WHEELDOWNMOUSE", "WHEELINMOUSE", "WHEELOUTMOUSE",
}


def _repeat_available(entry) -> bool:
    """Mirror Blender: Repeat applies only to keyboard keys whose value is
    ANY or PRESS (never for mouse/NDOF, never for release/click/drag)."""
    key = entry.get("key", "") or "NONE"
    if key in _MOUSE_KEYS or "NDOF" in key:
        return False
    return entry.get("event_type", "PRESS") in {"ANY", "PRESS"}


_EVENT_TYPE_SHORT = {
    "ANY": "any",
    "PRESS": "",
    "RELEASE": "rel",
    "CLICK": "clk",
    "DOUBLE_CLICK": "dbl-click",
    "CLICK_DRAG": "drag",
    "NOTHING": "nth",
}


def _key_str_display(event_type: str, key: str) -> str:
    """Build a human-readable shortcut string like 'Right Mouse (drag)'."""
    name = _key_display_name(key)
    ev = _EVENT_TYPE_SHORT.get(event_type, "")
    if ev:
        return f"{name} ({ev})"
    return name


def _combo_label(any_mod, shift, ctrl, alt, oskey, key_mod, key, event_type) -> str:
    """Shared single-binding combo string, e.g. 'Ctrl + Alt + Right Mouse (Drag)'.
    Used by both the card keybind button and the edit-panel header pill so they
    stay identical."""
    parts = []
    if any_mod:
        parts.append("Any")
    else:
        if shift:
            parts.append("Shift")
        if ctrl:
            parts.append("Ctrl")
        if alt:
            parts.append("Alt")
        if oskey:
            parts.append("OS")
    if key_mod and key_mod != "NONE":
        parts.append(_key_display_name(key_mod))
    if key and key != "NONE":
        parts.append(_key_str_display(event_type, key))
    return " + ".join(parts)


def _shortcut_str(entry: dict) -> str:
    """Build shortcut string showing all keybinds separated by /"""

    def _build(any_mod, shift, ctrl, alt, oskey, key_mod, key, event_type):
        parts = []
        if any_mod:
            parts.append("Any")
        else:
            if shift:
                parts.append("Shift")
            if ctrl:
                parts.append("Ctrl")
            if alt:
                parts.append("Alt")
            if oskey:
                parts.append("✦")
        if key_mod and key_mod != "NONE":
            parts.append(_key_display_name(key_mod))
        if key and key != "NONE":
            parts.append(_key_str_display(event_type, key))
        return " ".join(parts) if parts else ""

    # Primary keybind
    primary = _build(
        entry.get("any", False),
        entry.get("shift", False),
        entry.get("ctrl", False),
        entry.get("alt", False),
        entry.get("oskey", False),
        entry.get("key_modifier", ""),
        entry.get("key", ""),
        entry.get("event_type", "PRESS"),
    )
    all_parts = [primary] if primary else []

    # Extra keybinds
    for ex in entry.get("extra_keybinds", []):
        s = _build(
            ex.get("any", False),
            ex.get("shift", False),
            ex.get("ctrl", False),
            ex.get("alt", False),
            ex.get("oskey", False),
            ex.get("key_modifier", ""),
            ex.get("key", ""),
            ex.get("value", "PRESS"),
        )
        if s:
            all_parts.append(s)

    return " / ".join(all_parts) if all_parts else "—"


def _get_op_ids(entry: dict) -> list:
    """Return list of operator IDs from entry (handles both old and new format)."""
    import json

    raw = entry.get("operator_ids", "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            # New format: [{id, props}, ...]
            return [o["id"] if isinstance(o, dict) else o for o in data]
    except Exception:
        pass
    # Old format: comma-separated
    return [o.strip() for o in raw.split(",") if o.strip()]


def _fallback_cat_sub(op_id: str):
    """Two-level (category, subcategory) for ops NOT in the static table —
    mirrors Browse's placement: addon ops under "Addon Operators > <Addon>"
    (or their routed category), dynamic builtins under their module-prefix
    category's "Other" bucket."""
    try:
        from . import operator_discovery as _od
        _od.build_cache()
        info = _od._cache_addon.get(op_id)
        if info:
            rc = info.get("routed_category")
            if rc:
                return rc, "Other"
            return "Addon Operators", info.get("addon_name", "") or ""
    except Exception:
        pass
    try:
        from .database.dynamic_ops import MODULE_TO_CATEGORY_ID
        mod = op_id.split(".", 1)[0]
        cid = MODULE_TO_CATEGORY_ID.get(mod)
        if cid:
            for c in CATEGORIES:
                if c.get("id") == cid:
                    return c["label"], "Other"
    except Exception:
        pass
    return "Other", op_id.split(".", 1)[0].replace("_", " ").title()


def _find_cat_and_sub_for_op(op_id: str):
    """Return (category_label, subcategory_label) for an op_id."""
    for cat in CATEGORIES:
        for sub in cat["subcategories"]:
            if op_id in sub["operators"]:
                return cat["label"], sub["label"]
    return None, None


# Category display order — matches CATEGORIES list order
_CAT_ORDER = [cat["label"] for cat in CATEGORIES]


# ---------------------------------------------------------------------------
# Inline form
# ---------------------------------------------------------------------------


def entry_label_placeholder(sel_ops, sel_ids, use_friendly) -> str:
    """The greyed placeholder shown in an entry's Label field.

    Single source of truth: the main edit form and the right-click quick-add
    popup both call this, so their temporary names always match."""
    first_lbl = get_friendly_name(sel_ids[0]) if sel_ids else ""
    # For menu/pie/panel callers, build a richer live placeholder
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
    _VAL_FROM = {
        "wm.call_menu_pie": "pie_menus",
        "wm.call_menu": "menus",
        "wm.call_panel": "panels",
    }
    if sel_ids and sel_ids[0] in _AUTO_NAMED_OPS:
        first_op = sel_ops[0]
        first_id = sel_ids[0]
        props = first_op.get("props", {})
        menu_id = props.get("name", "")
        op_context = first_op.get("context", "")
        if menu_id:
            # Menu selected — use short prefix
            prefix = _SHORT_PREFIX[first_id]
            menu_label = menu_id
            if use_friendly:
                from .database.op_properties import get_prop_values as _gpv

                try:
                    lmap = {vid: vlbl for vid, vlbl in _gpv(_VAL_FROM[first_id], "")}
                    menu_label = lmap.get(menu_id, menu_id)
                except Exception:
                    pass
            placeholder = f"{prefix}: {menu_label}"
        else:
            # No menu selected yet — use full name
            placeholder = _FULL_NAME[first_id]
        # Always append context if set, regardless of menu selection state
        if op_context:
            placeholder += f" ({op_context})"
    elif sel_ids and (sel_ops[0].get("props") or {}).get("data_path"):
        # wm.context_* operators: the attribute is what the shortcut is
        # really "about", so name the entry after it ("Face Orientation")
        # rather than after the generic operator ("Context Toggle").
        try:
            from .database.op_properties import get_context_path_label
            placeholder = get_context_path_label(
                sel_ops[0]["props"]["data_path"]) or ""
        except Exception:
            placeholder = ""
        if not placeholder:
            _ff = get_friendly_name(sel_ids[0])
            placeholder = (_ff or sel_ids[0]) if use_friendly else sel_ids[0]
    else:
        if sel_ids:
            first_friendly = get_friendly_name(sel_ids[0])
            placeholder = (
                (first_friendly if first_friendly else sel_ids[0])
                if use_friendly
                else sel_ids[0]
            )
        else:
            placeholder = "Enter label..."
    return placeholder


def draw_internal_conflict_rows(container, rows, cur_entry):
    """Internal-conflict rows: other entry (+folder) then its clashing
    bindings. Shared by the main form and the quick-add popup so both
    present internal conflicts identically."""
    from .conflict_detector import internal_conflict_refs
    for c in rows:
        other = persistence.get_entry_by_id(c.get("with", ""))
        other_name = (
            (other.get("custom_label") or other.get("display_name", ""))
            if other else c.get("with", "")
        )
        _fid = other.get("folder_id", "") if other else ""
        _folder = "New Folder"
        if _fid:
            _fobj = persistence.get_folder_by_id(_fid) or {}
            _folder = _fobj.get("label", "Folder")
        hdr = container.row(align=True)
        hdr.separator(factor=3)
        hdr.label(text=f"{other_name} (Folder:{_folder})")
        if not other or not cur_entry:
            continue
        # Rows of the actual conflicting bindings — same format as the
        # shortcut / keybind conflict rows.
        try:
            _refs = internal_conflict_refs(cur_entry, other,
                                           c.get("type", ""))
        except Exception:
            _refs = []
        for _ref in _refs:
            _draw_external_conflict_row(container, _ref, entry_id="",
                                        ref_index=0,
                                        conflict_type="internal",
                                        preview=True)


def _draw_keybind_slot(layout, kmi, wm, slot_index: int = 0,
                       show_detect_ctx: bool = True):
    """Draw the primary keybind slot using the scratch KMI.

    `show_detect_ctx=False` omits the Additional Keybind Detection Context(s)
    row — used by the compact right-click popup, where that row is noise (and
    opens its own sub-UI).

    The key field is always the press-a-key widget, matching the main
    form. NOTE: inside a popup that widget never receives middle-mouse
    clicks, so MMB has to be assigned from the full editor."""
    map_type = kmi.map_type
    key_row = layout.row(align=True)
    if map_type not in {"TWEAK", "TEXTINPUT", "TIMER"}:
        # Four equal columns: map_type | key | value | repeat.
        c = key_row.split(factor=0.25, align=True)
        c.prop(kmi, "map_type", text="")
        c = c.split(factor=1.0 / 3.0, align=True)
        _kc = c.row(align=True)
        # Red until a key is actually assigned.
        _kc.alert = (kmi.type == "NONE")
        _kc.prop(kmi, "type", text="", event=True)
        c = c.split(factor=0.5, align=True)
        c.prop(kmi, "value", text="")
        rep = c.row(align=True)
        rep.active = map_type == "KEYBOARD" and kmi.value in {"ANY", "PRESS"}
        rep.prop(kmi, "repeat", text="Repeat")
    else:
        split = key_row.split(factor=0.30, align=True)
        split.prop(kmi, "map_type", text="")
        _kc = split.row(align=True)
        _kc.alert = (kmi.type == "NONE")
        _kc.prop(kmi, "type", text="", event=True)
    if show_detect_ctx:
        # The detection-contexts row below is hidden by default; this arrow
        # (right of Repeat) folds it in and out.
        import bpy as _bpy0
        _det_row_open = bool(_bpy0.context.window_manager.get(
            f"keymapper_subcat_detrow_{slot_index}", False))
        _dtog = key_row.row(align=True)
        _dtog.ui_units_x = 1.2
        _d = _dtog.operator(
            "keymapper.toggle_extra_options", text="",
            icon="DOWNARROW_HLT" if _det_row_open else "RIGHTARROW",
            emboss=True, depress=_det_row_open,
        )
        _d.key = f"detrow_{slot_index}"
    mod_row = layout.row(align=True)
    import bpy as _bpy

    _wm = _bpy.context.window_manager
    any_val = bool(_wm.get(f"keymapper_kmi_any_{slot_index}", False))
    btn_any = mod_row.operator("keymapper.toggle_kmi_mod", text="Any", depress=any_val)
    btn_any.mod_name = "any"
    btn_any.slot_index = slot_index
    for mod_name, mod_label in (
        ("shift", "Shift"),
        ("ctrl", "Ctrl"),
        ("alt", "Alt"),
        ("oskey", "OS"),
    ):
        # Show highlighted if modifier is on OR if any is on
        val = getattr(kmi, mod_name, 0)
        btn = mod_row.operator(
            "keymapper.toggle_kmi_mod", text=mod_label, depress=(val == 1 or any_val)
        )
        btn.mod_name = mod_name
        btn.slot_index = slot_index
    key_mod_val = getattr(kmi, "key_modifier", "NONE") or "NONE"
    key_mod_row = mod_row.row(align=True)
    if key_mod_val != "NONE":
        inner = key_mod_row.row(align=True)
        km_btn = inner.operator(
            "keymapper.clear_key_modifier", text=key_mod_val, depress=True, emboss=True
        )
        km_btn.slot_index = slot_index
    else:
        key_mod_row.prop(kmi, "key_modifier", text="", event=True)

    # ---- Additional Keybind Detection Context(s) — per keybind ----
    # Only shown when the fold arrow right of Repeat is open.
    if not show_detect_ctx or not _det_row_open:
        return
    from .operators import (get_ops_locked_contexts, subcat_wm_key,
                            view_detect_contexts)
    from .database.keymap_contexts import GROUP_LABELS, get_contexts_by_group

    det = view_detect_contexts(_wm, slot_index)
    det_hdr = layout.row(align=True)
    summary = ", ".join(det) if det else "None"
    d_tog = det_hdr.operator(
        "keymapper.open_detect_ctx_picker",
        text=f"Additional Keybind Detection Context(s): {summary}",
        icon="PLUGIN",
        emboss=True,
    )
    d_tog.slot_index = slot_index


def draw_detect_ctx_body(layout, context, slot_index):
    """Body of the detection-contexts dialog for one keybind slot: the same
    grouped checkbox list the old inline dropdown drew — operator contexts
    pre-checked and locked, extra contexts toggleable. Clicks apply live."""
    from .operators import (get_detect_contexts, get_ops_locked_contexts,
                            subcat_wm_key)
    from .database.keymap_contexts import GROUP_LABELS, get_contexts_by_group

    _wm = context.window_manager
    det = get_detect_contexts(_wm, slot_index)
    det_set = set(det)
    locked = set(get_ops_locked_contexts(_wm))
    _draw_selected_summary(layout, det, "keymapper.reset_detect_ctx",
                           {"slot_index": slot_index})
    box = layout.box()
    body = box.column(align=True)
    if True:
        for group_id, entries in get_contexts_by_group().items():
            grp_wm_key = subcat_wm_key(f"detgrp_{slot_index}_{group_id}")
            grp_open = bool(_wm.get(grp_wm_key, False))
            hdr = body.row(align=True)
            hdr.alignment = "LEFT"
            g_tog = hdr.operator(
                "keymapper.form_toggle_browse_subcat",
                text=GROUP_LABELS.get(group_id, group_id),
                icon="DOWNARROW_HLT" if grp_open else "RIGHTARROW",
                emboss=False,
            )
            g_tog.key = f"detgrp_{slot_index}_{group_id}"
            if grp_open:
                for e in entries:
                    km_name = e[0]
                    r = body.row(align=True)
                    r.alignment = "LEFT"
                    if km_name in locked:
                        rr = r.row(align=True)
                        rr.enabled = False
                        rr.label(text=km_name, icon="CHECKBOX_HLT")
                    else:
                        on = km_name in det_set
                        t = r.operator(
                            "keymapper.toggle_detect_ctx",
                            text=km_name,
                            icon="CHECKBOX_HLT" if on else "CHECKBOX_DEHLT",
                            emboss=False,
                        )
                        t.slot_index = slot_index
                        t.context_name = km_name
            body.separator()
    if hasattr(layout, "template_popup_confirm"):
        layout.template_popup_confirm(
            "keymapper.dialog_commit", text="Confirm",
            cancel_text="Cancel", cancel_default=False)


def _saved_custom_icon(wm) -> str:
    """The custom icon already saved on the entry being edited ("" for new
    entries or entries without one)."""
    try:
        from . import persistence
        eid = wm.get("keymapper_form_edit_id", "")
        if eid:
            e = persistence.get_entry_by_id(eid)
            return (e or {}).get("custom_icon", "") or ""
    except Exception:
        pass
    return ""


def _build_preview_entry(context):
    """Assemble a transient entry dict from the add-form's scratch state so the
    real card renderer can draw an identical-looking preview."""
    from .operators import (get_scratch_kmi, get_extra_scratch_kmi,
                            form_view_ops as _get_sel_ops,
                            get_button_locations as _get_button_locations)
    import json as _j

    wm = context.window_manager
    try:
        sel_ops = _get_sel_ops(wm)
    except Exception:
        sel_ops = []
    label = (getattr(wm, "keymapper_form_label", "") or "").strip()

    kmi = get_scratch_kmi()
    key = getattr(kmi, "type", "NONE") if kmi else "NONE"
    entry = {
        "entry_id": "__preview__",
        # The preview card's checkbox writes this, so a new entry can be
        # created already disabled (see KEYMAPPER_OT_ToggleEnabled).
        "enabled": bool(wm.get("keymapper_form_enabled", True)),
        # Mode fields, so a button-only entry previews the way it will look
        # once confirmed (button pill + locations row instead of a keybind).
        "use_keybind": bool(wm.get("keymapper_form_use_keybind", True)),
        "use_button": bool(wm.get("keymapper_form_use_button", False)),
        "button_locations": _get_button_locations(wm),
        "button_show_label": bool(
            wm.get("keymapper_form_button_show_label", True)),
        "button_show_icon": bool(
            wm.get("keymapper_form_button_show_icon", True)),
        "button_label": (getattr(wm, "keymapper_form_button_label", "")
                         or "").strip(),
        "button_conflict_detection": bool(
            wm.get("keymapper_form_button_conflicts", False)),
        "custom_label": label,
        "display_name": (sel_ops[0]["id"] if sel_ops else "New Shortcut"),
        "operator_ids": _j.dumps(sel_ops),
        # Pending pick, else the edited entry's SAVED custom icon — on edit,
        # picks write the entry directly, so pending alone showed the op's
        # auto icon in the preview pill.
        "custom_icon": (wm.get("keymapper_form_pending_icon", "")
                        or _saved_custom_icon(wm)),
        "key": key,
        "event_type": getattr(kmi, "value", "PRESS") if kmi else "PRESS",
        "shift": bool(getattr(kmi, "shift", 0)) if kmi else False,
        "ctrl": bool(getattr(kmi, "ctrl", 0)) if kmi else False,
        "alt": bool(getattr(kmi, "alt", 0)) if kmi else False,
        "oskey": bool(getattr(kmi, "oskey", 0)) if kmi else False,
        "any": bool(getattr(kmi, "any", False)) if kmi else False,
        "key_modifier": getattr(kmi, "key_modifier", "") if kmi else "",
        "repeat": bool(getattr(kmi, "repeat", False)) if kmi else False,
        "folder_id": "",
        "sort_index": 0,
        "internal_conflicts": [],
        "extra_keybinds": [],
    }
    # Extra keybinds (so the card shows the "+ N other keybindings" form).
    try:
        extras = _j.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]")
    except Exception:
        extras = []
    ex_list = []
    for idx in range(len(extras)):
        ek = get_extra_scratch_kmi(idx + 1)
        if ek is None:
            continue
        # Include slots whose key is not chosen yet: the card renders them as
        # "—", so a freshly added keybind appears immediately.
        ex_list.append({
            "key": getattr(ek, "type", "NONE"), "value": ek.value,
            "shift": bool(ek.shift), "ctrl": bool(ek.ctrl),
            "alt": bool(ek.alt), "oskey": bool(ek.oskey),
            "key_modifier": getattr(ek, "key_modifier", ""),
        })
    entry["extra_keybinds"] = ex_list
    return entry


def _draw_new_entry_preview_card(layout: UILayout, context):
    """Temporary preview of the entry being built — drawn with the exact same
    renderer as a real card, but locked (non-interactive)."""
    entry = _build_preview_entry(context)
    _draw_simplified_card(layout, context, entry, -1, preview=True)



def _count_visible_kmi_props(pk, op_id, skip):
    """Row count the always-open per-row Properties editor will produce —
    used to size the spanning remove-X. 0 when there is nothing to draw.
    Guarded against dangling RNA on unregistered operators."""
    try:
        from .conflict_detector import is_operator_registered
        if pk is None or not is_operator_registered(op_id):
            return 0
        props = getattr(pk, "properties", None)
        if props is None:
            return 0
        n = 0
        for p in props.bl_rna.properties:
            pid = p.identifier
            if pid == "rna_type" or pid in skip:
                continue
            # NOTE: no is_property_hidden() filter — keymap-item editors
            # show hidden props by convention (select_all's "action" is
            # PROP_HIDDEN yet Blender's own keymap editor displays it);
            # skipping them removed the Properties dropdown from every op
            # whose only props are hidden.
            n += 1
        return n
    except Exception:
        return 0


def draw_kmi_properties_locked(layout, kmi, locked=(), skip=(), slot=None,
                               op_id=""):
    """Operator properties drawn one row at a time, so individual ones can be
    locked. Blender's `template_keymap_item_properties` renders them as a
    single block with no way to disable just one — the quick-add popup needs
    the identifying property (data_path / name) locked while Module and the
    rest stay editable.
    """
    props = getattr(kmi, "properties", None)
    if props is None:
        return False
    try:
        rna_props = props.bl_rna.properties
    except Exception:
        return False
    drew = False
    col = layout.column(align=True)
    for p in rna_props:
        pid = p.identifier
        if pid == "rna_type" or pid in skip:
            continue
        # No hidden-prop filter — see _count_visible_kmi_props.
        try:
            is_set = bool(props.is_property_set(pid))
        except Exception:
            is_set = True
        row = col.row(align=True)
        val = row.row(align=True)
        if pid in locked:
            val.enabled = False
        # Mirror Blender's keymap editor: an unset property draws dimmed (still
        # clickable — active=False greys but keeps input, enabled=False would
        # kill the click and the tooltip). Unset means "not stored on the KMI",
        # so the operator uses its own default behaviour.
        val.active = is_set
        try:
            val.prop(props, pid)
            drew = True
        except Exception:
            continue
        # Fixed-width trailing cell so the value widget keeps one width whether
        # or not the X is present (§10b: rows stretch their children).
        cell = row.row(align=True)
        cell.ui_units_x = 1.1
        if is_set and slot is not None and pid not in locked:
            op = cell.operator("keymapper.unset_kmi_property",
                               text="", icon="X")
            op.slot = int(slot)
            op.op_id = op_id
            op.prop_name = pid
        else:
            cell.label(text="")
    return drew



def _draw_selected_summary(layout, items, reset_op, reset_props=None,
                           empty_text="Nothing selected yet", budget=46):
    """Shared "Selected:" block for the picker dialogs. Labels never wrap on
    their own, so the item names are chunked over as many rows as needed
    (the dialog re-layouts each redraw, so it grows with the selection).
    The reset arrow sits right-aligned on the first row and is disabled
    when there is nothing to reset."""
    row0 = layout.row(align=True)
    have = bool(items)
    chunks = []
    if have:
        # Collapse repeats: "Call Menu, Call Menu, …" reads as
        # "Call Menu (x7)" — first-appearance order preserved.
        _counts = {}
        for it in items:
            _k = str(it)
            _counts[_k] = _counts.get(_k, 0) + 1
        items = [(_k if _n == 1 else f"{_k} (x{_n})")
                 for _k, _n in _counts.items()]
        cur = ""
        for it in items:
            add = (", " if cur else "") + str(it)
            if cur and len(cur) + len(add) > budget:
                chunks.append(cur + ",")
                cur = str(it)
            else:
                cur += add
        if cur:
            chunks.append(cur)
        row0.label(text=f"Selected: {chunks[0]}", icon="CHECKMARK")
    else:
        _dim = row0.row(align=True)
        _dim.active = False
        _dim.label(text=empty_text, icon="RADIOBUT_OFF")
    _rst = row0.row(align=True)
    _rst.alignment = "RIGHT"
    _rst.enabled = have
    _op = _rst.operator(reset_op, text="", icon="LOOP_BACK", emboss=False)
    for _k, _v in (reset_props or {}).items():
        setattr(_op, _k, _v)
    for ch in chunks[1:]:
        r = layout.row(align=True)
        r.label(text=ch, icon="BLANK1")
    layout.separator(factor=0.4)


def draw_prop_picker_body(layout, context, i, prop_name):
    """Body of the value-picker dialog for a curated dropdown property
    (menu / pie menu / panel / tool): search field plus the grouped value
    list. Extracted verbatim from the old inline expanding list, so grouping,
    search, and selection behave identically — only the container changed
    (a draggable dialog instead of rows inside the form)."""
    from .database.op_properties import get_op_props, op_derives_context
    from .operators import _get_sel_ops, subcat_wm_key
    from .preferences import is_friendly

    wm = context.window_manager
    ops = _get_sel_ops(wm)
    if i >= len(ops):
        layout.label(text="Operator slot no longer exists.",
                     icon=safe_icon("STATUS_WARNING", "ERROR"))
        return
    op_inst = ops[i]
    op_id = op_inst.get("id", "")
    meta = get_op_props(op_id).get(prop_name, {})
    values_from = meta.get("values_from") or ""
    if not values_from:
        layout.label(text="Nothing to pick for this property.",
                     icon=safe_icon("STATUS_INFO", "INFO"))
        return
    use_friendly = is_friendly()
    derives_ctx = op_derives_context(op_id)
    op_context = op_inst.get("context", "")
    current_val = (op_inst.get("props") or {}).get(prop_name, "")

    # Current selection, shown at the top and updating live as values are
    # clicked (the dialog itself cannot be closed by the click — Blender
    # gives child operators no way to dismiss the parent dialog).
    _items = []
    if current_val:
        shown = current_val
        if use_friendly:
            from .database.op_properties import get_prop_values as _gpv_sel
            try:
                _lm = {vid: vlbl for vid, vlbl in _gpv_sel(values_from, "")
                       if not vid.startswith("__")}
                shown = _lm.get(current_val, current_val)
            except Exception:
                pass
        _items = [shown]
    _draw_selected_summary(layout, _items, "keymapper.reset_op_prop",
                           {"op_index": i, "prop_name": prop_name})

    ctx_for_filter = "" if derives_ctx else op_context
    menu_search = ""
    # Dropdown with search
    while len(wm.keymapper_menu_searches) <= i:
        wm.keymapper_menu_searches.add()
    menu_search_row = layout.row(align=True)
    menu_search_row.prop(
        wm.keymapper_menu_searches[i],
        "value",
        text="",
        icon="VIEWZOOM",
    )
    _fp2 = menu_search_row.row(align=True)
    _fp2.ui_units_x = 1.2
    # Icon-only (keyboard-key glyphs) — dialog popups auto-assign text
    # accelerators and underline the letter, which icons dodge entirely.
    _fp2.operator(
        "keymapper.toggle_naming_mode", text="",
        icon=safe_icon("EVENT_F" if use_friendly else "EVENT_P", "DOT"),
    )
    menu_search = (
        wm.keymapper_menu_searches[i].value.lower().strip()
    )
    from .database.op_properties import get_prop_values

    values = get_prop_values(values_from, ctx_for_filter)
    if not values:
        layout.label(text="No values found.", icon=safe_icon("STATUS_INFO", "INFO"))
    else:
        # Parse sentinels into two-level group structure
        groups = []
        cur_grp = None
        cur_items = []
        cur_subs = []
        cur_sub = None
        cur_sub_items = []
        for vid, vlbl in values:
            if vid == "__GROUP_HEADER__":
                if cur_sub is not None:
                    cur_subs.append(
                        (cur_sub, cur_sub_items)
                    )
                    cur_sub, cur_sub_items = None, []
                if cur_grp is not None:
                    groups.append(
                        (cur_grp, cur_items, cur_subs)
                    )
                cur_grp, cur_items, cur_subs = vlbl, [], []
            elif vid == "__SUBGROUP_HEADER__":
                if cur_sub is not None:
                    cur_subs.append(
                        (cur_sub, cur_sub_items)
                    )
                cur_sub, cur_sub_items = vlbl, []
            else:
                if cur_sub is not None:
                    cur_sub_items.append((vid, vlbl))
                else:
                    cur_items.append((vid, vlbl))
        if cur_sub is not None:
            cur_subs.append((cur_sub, cur_sub_items))
        if cur_grp is not None:
            groups.append((cur_grp, cur_items, cur_subs))
        if not groups:
            groups = [("", values, [])]

        for grp_name, grp_vals, subgroups in groups:
            if menu_search:
                grp_vals = [
                    (vid, vlbl)
                    for vid, vlbl in grp_vals
                    if menu_search in vlbl.lower()
                    or menu_search in vid.lower()
                ]
                subgroups = [
                    (
                        sn,
                        [
                            (vid, vlbl)
                            for vid, vlbl in sv
                            if menu_search in vlbl.lower()
                            or menu_search in vid.lower()
                        ],
                    )
                    for sn, sv in subgroups
                ]
                subgroups = [
                    (sn, sv) for sn, sv in subgroups if sv
                ]
            if not grp_vals and not subgroups:
                continue
            if grp_name:
                safe_key = (
                    grp_name.replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                )
                grp_key = subcat_wm_key(f"grp_{i}_{prop_name}_{safe_key}")
                grp_is_open = bool(wm.get(grp_key, False))
                total = len(grp_vals) + sum(
                    len(s[1]) for s in subgroups
                )
                label_text = (
                    f"{grp_name} ({total})"
                    if menu_search
                    else grp_name
                )
                is_addon = grp_name.startswith("Addon ")
                if is_addon:
                    layout.separator(factor=0.3)
                groups_box = layout.box()
                groups_box.scale_y = 1.0
                grp_hdr = groups_box.row(align=True)
                grp_hdr.alignment = "LEFT"
                grp_tog = grp_hdr.operator(
                    "keymapper.form_toggle_browse_subcat",
                    text=label_text,
                    icon="DOWNARROW_HLT"
                    if grp_is_open
                    else "RIGHTARROW",
                    emboss=False,
                )
                grp_tog.key = (
                    f"grp_{i}_{prop_name}_{safe_key}"
                )
                if not grp_is_open:
                    continue
                item_col = groups_box.column(align=True)
                item_col.scale_y = 1.0
            else:
                item_col = layout

            for vid, vlbl in grp_vals:
                item_row = item_col.row(align=True)
                item_row.alignment = "LEFT"
                menu_text = (
                    vlbl
                    if (
                        use_friendly
                        and vlbl
                        and vlbl != vid
                    )
                    else vid
                )
                set_op = item_row.operator(
                    "keymapper.form_set_op_prop",
                    text=menu_text,
                    emboss=False,
                )
                set_op.op_index = i
                set_op.prop_name = prop_name
                set_op.prop_value = vid

            for idx_sub, (sub_name, sub_vals) in enumerate(
                subgroups
            ):
                safe_sub = (
                    sub_name.replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                )
                sub_key = subcat_wm_key(f"grp_{i}_{prop_name}_{safe_sub}")
                sub_is_open = bool(wm.get(sub_key, False))
                sub_label = (
                    f"{sub_name} ({len(sub_vals)})"
                    if menu_search
                    else sub_name
                )
                sub_box = item_col.box()
                sub_box.scale_y = 1.0
                sub_hdr = sub_box.row(align=True)
                sub_hdr.alignment = "LEFT"
                sub_tog = sub_hdr.operator(
                    "keymapper.form_toggle_browse_subcat",
                    text=sub_label,
                    icon="DOWNARROW_HLT"
                    if sub_is_open
                    else "RIGHTARROW",
                    emboss=False,
                )
                sub_tog.key = (
                    f"grp_{i}_{prop_name}_{safe_sub}"
                )
                if not sub_is_open:
                    continue
                sub_col = sub_box.column(align=True)
                sub_col.scale_y = 1.2
                for vid, vlbl in sub_vals:
                    sub_row = sub_col.row(align=True)
                    sub_row.alignment = "LEFT"
                    menu_text = (
                        vlbl
                        if (
                            use_friendly
                            and vlbl
                            and vlbl != vid
                        )
                        else vid
                    )
                    set_op = sub_row.operator(
                        "keymapper.form_set_op_prop",
                        text=menu_text,
                        emboss=False,
                    )
                    set_op.op_index = i
                    set_op.prop_name = prop_name
                    set_op.prop_value = vid
    if hasattr(layout, "template_popup_confirm"):
        layout.template_popup_confirm(
            "keymapper.dialog_commit", text="Confirm",
            cancel_text="Cancel", cancel_default=False)


def draw_op_context_selector(parent, context, op_inst, i, op_id,
                             op_context=""):
    """Interactive context selector for one operator instance.

    Shared by the main edit form and the quick-add popup so both offer
    the same picker (the popup previously showed a read-only summary).
    """
    from .database.op_properties import op_derives_context
    from .database.op_properties import op_requires_context as _orc2
    from .database.keymap_contexts import GROUP_LABELS, get_contexts_by_group
    wm = context.window_manager
    derives_ctx = op_derives_context(op_id)
    # ── Context selector (unified) — above Properties ───────
    if not derives_ctx:
        from . import keyconfig_store as _kstore
        from .keymap_manager import _get_keymaps_for_op as _gkfos

        requires_ctx = _orc2(op_id)
        use_multi = bool(op_inst.get("use_multi_contexts", False))
        expand = bool(op_inst.get("expand_contexts", False))

        checked = list(op_inst.get("contexts") or [])
        if not checked and op_context:
            checked = [op_context]
        checked_set = set(checked)

        try:
            auto_kms = _gkfos(op_id, op_inst)
        except Exception:
            auto_kms = []
        auto_km = auto_kms[0] if auto_kms else ""
        auto_km_set = set(auto_kms)

        ctx_hdr = parent.row(align=True)
        if checked:
            hdr_text = ", ".join(checked)
        elif auto_kms:
            hdr_text = f"Context: Auto ({', '.join(auto_kms)})"
        elif requires_ctx:
            hdr_text = "⚠ Select context..."
        else:
            hdr_text = "Context: Auto"
        ctx_hdr.alert = requires_ctx and not checked and not auto_kms
        ctx_tog = ctx_hdr.operator(
            "keymapper.open_op_ctx_picker",
            text=hdr_text,
            icon="PLUGIN",
            emboss=True,
        )
        ctx_tog.op_index = i



def draw_op_ctx_body(layout, context, i):
    """Body of the per-operator Context dialog: the options pair (multi /
    expand) plus the grouped context checkboxes — extracted verbatim from the
    old inline dropdown, so auto-detection marks, group auto-open and the
    expand filter behave identically. Clicks apply to the form live."""
    from . import keyconfig_store as _kstore
    from .database.keymap_contexts import GROUP_LABELS, get_contexts_by_group
    from .keymap_manager import _get_keymaps_for_op as _gkfos
    from .operators import _get_sel_ops

    wm = context.window_manager
    ops = _get_sel_ops(wm)
    if i >= len(ops):
        layout.label(text="Operator slot no longer exists.",
                     icon=safe_icon("STATUS_WARNING", "ERROR"))
        return
    op_inst = ops[i]
    op_id = op_inst.get("id", "")
    use_multi = bool(op_inst.get("use_multi_contexts", False))
    expand = bool(op_inst.get("expand_contexts", False))
    checked = list(op_inst.get("contexts") or [])
    if not checked and op_inst.get("context"):
        checked = [op_inst.get("context")]
    checked_set = set(checked)
    try:
        auto_kms = _gkfos(op_id, op_inst)
    except Exception:
        auto_kms = []
    auto_km_set = set(auto_kms)
    _auto = f"Auto ({', '.join(auto_kms)})" if auto_kms else "Auto"
    _draw_selected_summary(layout, checked, "keymapper.reset_op_context",
                           {"op_index": i},
                           empty_text=f"Nothing selected — {_auto}")

    box = layout.box()
    # Options — bordered together (B2)
    opt_box = box.box()
    opt = opt_box.column(align=True)
    # When nothing is manually selected (still auto)
    # and the operator auto-resolves to multiple home
    # keymaps, multi-context is the effective auto
    # state — show a green checkmark to indicate it.
    auto_multi = (not checked) and len(auto_km_set) > 1
    m_row = opt.row(align=True)
    m_op = m_row.operator(
        "keymapper.form_toggle_op_flag",
        text="Use multiple contexts",
        icon="CHECKBOX_HLT" if use_multi else "CHECKBOX_DEHLT",
        emboss=False,
    )
    m_op.op_index = i
    m_op.flag = "use_multi_contexts"
    if auto_multi and not use_multi:
        m_sub = m_row.row(align=True)
        m_sub.alignment = "RIGHT"
        m_sub.label(text="", icon="CHECKMARK")
    e_op = opt.operator(
        "keymapper.form_toggle_op_flag",
        text="Expand Contexts",
        icon="CHECKBOX_HLT" if expand else "CHECKBOX_DEHLT",
        emboss=False,
    )
    e_op.op_index = i
    e_op.flag = "expand_contexts"

    lived = set(_kstore.get_keymap_names_for_op(op_id))
    lived |= auto_km_set
    body = box.column(align=True)
    any_shown = False
    for group_id, entries in get_contexts_by_group().items():
        shown = [
            e[0] for e in entries
            if expand or e[0] in lived
            or e[0] in checked_set or e[0] in auto_km_set
        ]
        if not shown:
            continue
        any_shown = True
        auto_in_group = any(e[0] in auto_km_set for e in entries)
        grp_key = f"keymapper_ctxgrp_{i}_{group_id}"
        grp_open = bool(wm.get(grp_key, auto_in_group))
        hdr = body.row(align=True)
        hdr.alignment = "LEFT"
        g_tog = hdr.operator(
            "keymapper.form_toggle_ctx_group",
            text=GROUP_LABELS.get(group_id, group_id),
            icon="DOWNARROW_HLT" if grp_open else "RIGHTARROW",
            emboss=False,
        )
        g_tog.op_index = i
        g_tog.group_id = group_id
        g_tog.default_open = auto_in_group
        if grp_open:
            for km in shown:
                on = km in checked_set
                is_auto = (km in auto_km_set and not checked)
                r = body.row(align=True)
                r.alignment = "LEFT"
                ic = "CHECKBOX_HLT" if on else "CHECKBOX_DEHLT"
                t = r.operator(
                    "keymapper.form_toggle_op_context",
                    text=km,
                    icon=ic,
                    emboss=False,
                )
                t.op_index = i
                t.context_name = km
                if is_auto:
                    r.label(text="", icon="CHECKMARK")
        body.separator()  # B4: spacing between categories
    if not any_shown:
        body.label(text="Scan keyconfig to list contexts", icon=safe_icon("STATUS_INFO", "INFO"))
    if hasattr(layout, "template_popup_confirm"):
        layout.template_popup_confirm(
            "keymapper.dialog_commit", text="Confirm",
            cancel_text="Cancel", cancel_default=False)


def draw_button_section_body(layout, context, sel_ops, sel_ids, use_kb):
    """The Button section's body — ONE implementation shared by the main
    edit form and the quick-add popup, so they can never drift apart."""
    from . import operators as ops_mod
    from .buttons import LOCATION_LABELS
    from .preferences import is_friendly as _is_friendly

    wm = context.window_manager
    body = layout.column(align=True)
    # Show icon / show label — icon first (can't both be off)
    _b_lbl = bool(wm.get("keymapper_form_button_show_label", True))
    _b_ico = bool(wm.get("keymapper_form_button_show_icon", True))
    ico_row = body.row(align=True)
    ico_row.alignment = "LEFT"
    ico_row.operator(
        "keymapper.form_toggle_button_icon",
        text="Show Icon",
        icon="CHECKBOX_HLT" if _b_ico else "CHECKBOX_DEHLT",
        emboss=False,
    )
    # Show Label + the custom-label field on ONE row; the field is greyed
    # while labels are off, and its placeholder mirrors the entry's own
    # custom label (else the auto label).
    lbl_row = body.row(align=True)
    _lchk = lbl_row.row(align=True)
    _lchk.alignment = "LEFT"
    _lchk.operator(
        "keymapper.form_toggle_button_label",
        text="Show Label",
        icon="CHECKBOX_HLT" if _b_lbl else "CHECKBOX_DEHLT",
        emboss=False,
    )
    _lfield = lbl_row.row(align=True)
    _lfield.enabled = _b_lbl
    _lfield.prop(
        wm, "keymapper_form_button_label", text="",
        placeholder=((getattr(wm, "keymapper_form_label", "") or "")
                     .strip()
                     or entry_label_placeholder(sel_ops, sel_ids,
                                                _is_friendly())))
    body.separator(factor=0.3)
    # Locations — a draggable dialog like the other pickers.
    locs = ops_mod.view_button_locations(wm)
    summary = (", ".join(LOCATION_LABELS.get(l, l) for l in locs)
               if locs else "None")
    body.operator(
        "keymapper.open_button_loc_picker",
        text=f"Locations: {summary}",
        icon="RESTRICT_VIEW_OFF",
        emboss=True,
    )
    # Conflict detection — only meaningful for button-only entries
    # (keybind entries already do full detection).
    if not use_kb:
        _b_cd = bool(wm.get("keymapper_form_button_conflicts", False))
        cd_row = body.row(align=True)
        cd_row.operator(
            "keymapper.form_toggle_button_conflicts",
            text="Conflict Detection (shortcut conflicts only)",
            icon="CHECKBOX_HLT" if _b_cd else "CHECKBOX_DEHLT",
            emboss=False,
        )
    return body


def draw_entry_header_row(layout, context, sel_ops, sel_ids, edit_id=""):
    """Icon picker | Label field | Folder selector.

    ONE implementation shared by the main edit form and the quick-add popup —
    they used to have separate copies, which is how their captions drifted
    apart ("Label" vs "Label:", stray "Folder" caption).
    """
    from .preferences import is_friendly as _is_friendly
    from .database.op_icons import FALLBACK_ICON as _FB_ICON
    from .database.op_icons import get_op_icon as _goi

    wm = context.window_manager
    row = layout.row(align=True)

    _icap = row.row(align=True)
    _icap.alignment = "RIGHT"
    _icap.ui_units_x = 2.0
    _icap.label(text="Icon")
    if edit_id:
        _ent = persistence.get_entry_by_id(edit_id)
        _icons = _entry_op_icons(_ent) if _ent else []
        _icon_now = safe_icon(_icons[0], "DOT") if _icons else "DOT"
    else:
        _pending = wm.get("keymapper_form_pending_icon", "")
        _icon_now = (safe_icon(_pending, _FB_ICON) if _pending
                     else (safe_icon(_goi(sel_ids[0]), _FB_ICON)
                           if sel_ids else _FB_ICON))
    row.operator("keymapper.pick_icon", text="",
                 icon=_icon_now).entry_id = edit_id

    _lcap = row.row(align=True)
    _lcap.alignment = "RIGHT"
    _lcap.ui_units_x = 2.4
    _lcap.label(text="Label")
    row.prop(wm, "keymapper_form_label", text="",
             placeholder=entry_label_placeholder(sel_ops, sel_ids,
                                                 _is_friendly()))

    fid = (wm.get("keymapper_quickadd_folder_id", "")
           if wm.get("keymapper_quickadd_folder_set", False)
           else wm.get("keymapper_new_entry_folder", "")) or ""
    folder = persistence.get_folder_by_id(fid) if fid else None
    _fold = row.row(align=True)
    _fold.ui_units_x = 8.0
    _fold.label(text="", icon="FILE_FOLDER")
    _fold.menu("KEYMAPPER_MT_QuickAddFolder",
               text=folder.get("label", "Folder") if folder else "New Folder")
    return row


def _draw_inline_form(layout: UILayout, context):
    from . import operators as ops_mod
    from .operators import (
        WM_BROWSE_ON,
        WM_CATEGORY,
        _wm_get,
        get_scratch_kmi,
        subcat_wm_key,
    )
    from .preferences import is_friendly as _is_friendly

    wm = context.window_manager
    if not wm.get("keymapper_form_active", False):
        return

    host = ops_mod._host()
    browse_open = bool(_wm_get(wm, WM_BROWSE_ON, False))
    op_mode = "FRIENDLY" if _is_friendly() else "PURE"
    sel_cat = _wm_get(wm, WM_CATEGORY, "object")
    edit_id = wm.get("keymapper_form_entry_id", "")
    from .operators import form_view_ops as _form_get_ops

    sel_ops = _form_get_ops(wm)
    sel_ids = [o["id"] for o in sel_ops]
    use_friendly = _is_friendly()

    # Confirm/Cancel as a header bar FUSED to the form box: an aligned
    # column merges the row with the box below, so the buttons run
    # edge-to-edge with the border and square off where they meet it.
    # Header section in its OWN box, fused to the form box below (aligned
    # boxes share a squared seam and a continuous outer border — that gives
    # the header rows the left/right border line too). Order: icon/label/
    # folder row on top, Confirm/Cancel beneath it.
    _form_col = layout.column(align=True)
    # Confirm/Cancel OUTSIDE the box, fused to it in the aligned stack —
    # full-width bar attached to the border line, squared where they meet.
    _btn_row = _form_col.row(align=True)
    _btn_row.operator("keymapper.form_confirm", text="Confirm", icon="CHECKMARK")
    _btn_row.operator("keymapper.form_cancel", text="Cancel", icon="X")
    _hdr_box = _form_col.box()
    draw_entry_header_row(_hdr_box, context, sel_ops, sel_ids,
                          edit_id=edit_id)
    # Each section is its own box in the SAME fused stack: where two boxes
    # meet, the shared border renders as the thin seam line (the same line
    # as under the header box) — no extra encapsulating border, no fake
    # rules.
    form = _form_col

    # ---- Entry mode: Keybind and/or Button (at least one must stay on).
    # The Keybind checkbox sits above the Keybind section; the Button checkbox
    # sits below it, above the Button section. Left-aligned rows keep each
    # text right next to its checkbox.
    _use_kb = bool(wm.get("keymapper_form_use_keybind", True))
    _use_btn = bool(wm.get("keymapper_form_use_button", False))
    # ---- 1. Shortcut(s) — collapsible bordered box (only in Keybind mode) ----
    if True:
        sc_open_key = "keymapper_subcat_shortcut_section"
        sc_is_open = bool(wm.get(sc_open_key, True))  # open by default
        try:
            import json as _jsc

            _extra_count = len(_jsc.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]"))
        except Exception:
            _extra_count = 0
        sc_label = "Keybind" if _extra_count == 0 else "Keybinds"
        # Keybinds and Button live in ONE bordered box (shared with 1b).
        _kb_btn_box = _form_col.box()
        sc_box = _kb_btn_box
        # The mode checkbox IS the section header; the arrow and + only make
        # sense while the mode is on.
        # Full-width row: a LEFT group holds the checkbox + arrow, a RIGHT
        # group holds the add button. (Setting the header itself to LEFT
        # shrink-wraps it, leaving the nested RIGHT row nothing to push
        # against, which is why + used to sit beside the arrow.)
        sc_hdr = sc_box.row(align=True)
        sc_hdr_left = sc_hdr.row(align=True)
        sc_hdr_left.alignment = "LEFT"
        sc_hdr_left.operator(
            "keymapper.form_toggle_use_keybind",
            text=sc_label,
            icon="CHECKBOX_HLT" if _use_kb else "CHECKBOX_DEHLT",
            emboss=False,
        )
        if _use_kb:
            sc_tog = sc_hdr_left.operator(
                "keymapper.form_toggle_browse_subcat",
                text="",
                icon="DOWNARROW_HLT" if sc_is_open else "RIGHTARROW",
                emboss=False,
            )
            sc_tog.key = "shortcut_section"
            sc_tog.default_open = True
            _sc_add = sc_hdr.row(align=True)
            _sc_add.alignment = "RIGHT"
            _sc_add.operator("keymapper.add_extra_keybind", text="",
                             icon="ADD")

        if _use_kb and sc_is_open:
            kmi = get_scratch_kmi()
            if kmi is not None:
                # Primary keybind — same structure as the extras below (so
                # the spacing matches), just without the remove button.
                # Plain column (no align): aligned boxes merge their
                # touching corners, which squared the 2nd/3rd slots.
                _kb_stack = sc_box.column()
                primary_box = _kb_stack.box()
                _p_row = primary_box.row(align=True)
                _p_col = _p_row.column(align=True)
                _draw_keybind_slot(_p_col, kmi, wm, slot_index=0)

                # Extra keybinds — each with an X button to remove that specific slot
                try:
                    import json as _j

                    extras = _j.loads(wm.get("keymapper_extra_keybinds", "[]") or "[]")
                except Exception:
                    extras = []
                for idx, extra in enumerate(extras):
                    slot = idx + 1
                    from .operators import get_extra_scratch_kmi

                    extra_kmi = get_extra_scratch_kmi(slot)
                    if extra_kmi is not None:
                        extra_box = _kb_stack.box()
                        slot_row = extra_box.row(align=True)
                        slot_col = slot_row.column(align=True)
                        _draw_keybind_slot(slot_col, extra_kmi, wm, slot_index=slot)
                        x_col = slot_row.column(align=True)
                        # Span the slot height: keybind + modifier rows, plus
                        # the detection-contexts row only while it is open.
                        _dro = bool(wm.get(
                            f"keymapper_subcat_detrow_{slot}", False))
                        x_col.scale_y = 3.0 if _dro else 2.0
                        x_op = x_col.operator(
                            "keymapper.remove_extra_keybind_at", text="", icon="X"
                        )
                        x_op.slot_index = idx
            else:
                sc_box.label(text="Shortcut widget unavailable.", icon=safe_icon("STATUS_WARNING", "ERROR"))


    # ---- 1b. Button — checkbox header + collapsible bordered box ----
    if True:
        from .operators import get_button_locations, subcat_wm_key as _swk
        from .buttons import BUTTON_LOCATIONS, LOCATION_LABELS

        # Bordered only while the Button mode is ON; otherwise just the
        # checkbox row, borderless.
        btn_box = _kb_btn_box.box() if _use_btn else _kb_btn_box.column()
        btn_open = bool(wm.get("keymapper_subcat_button_section", True))
        btn_hdr = btn_box.row(align=True)
        _bh_left = btn_hdr.row(align=True)
        _bh_left.alignment = "LEFT"
        _bh_left.operator(
            "keymapper.form_toggle_use_button",
            text="Button",
            icon="CHECKBOX_HLT" if _use_btn else "CHECKBOX_DEHLT",
            emboss=False,
        )
        if _use_btn:
            b_tog = _bh_left.operator(
                "keymapper.form_toggle_browse_subcat",
                text="",
                icon="DOWNARROW_HLT" if btn_open else "RIGHTARROW",
                emboss=False,
            )
            b_tog.key = "button_section"
            b_tog.default_open = True
            # Live preview of the button itself, right on the header row.
            try:
                _pv_e = _build_preview_entry(context)
                if _pv_e is not None:
                    _bh_pv = btn_hdr.row(align=True)
                    _bh_pv.alignment = "RIGHT"
                    _draw_entry_button_widget(_bh_pv, _pv_e, preview=True,
                                              caption=False)
            except Exception:
                pass

        if _use_btn and btn_open:
            draw_button_section_body(btn_box, context, sel_ops, sel_ids,
                                     _use_kb)


    # ---- 2. Operators box: one dropdown (the selected operators) with a
    #      "Browse Operators" button on its header that opens the browser as
    #      a POPUP instead of an inline collapsible — far less clutter. ----
    sel_open = bool(wm.get("keymapper_sel_panel_open", False))
    ops_box = _form_col.box()

    ops_hdr = ops_box.row(align=True)
    _hdr_split = ops_hdr.split(factor=0.62, align=True)
    _hdr_split.operator(
        "keymapper.form_toggle_sel_panel",
        text=f"Operators ({len(sel_ops)})" if sel_ops else "Operators",
        icon="DOWNARROW_HLT" if sel_open else "RIGHTARROW",
        emboss=True,
        depress=sel_open,
    )
    _hdr_split.operator(
        "keymapper.open_browse_popup",
        text="Browse Operators",
        icon="VIEWZOOM",
    )

    if sel_open:
        sel_ops_box = ops_box

        if sel_ops:
            from .database.keymap_contexts import GROUP_LABELS, get_contexts_by_group
            from .database.op_properties import (
                get_op_props,
                get_prop_values,
            )

            # Group by category > subcategory preserving instance index
            cat_sub_groups: dict = {}
            for i, op_inst in enumerate(sel_ops):
                op_id = op_inst["id"]
                cat_lbl, sub_lbl = _find_cat_and_sub_for_op(op_id)
                if not cat_lbl:
                    cat_lbl, sub_lbl = _fallback_cat_sub(op_id)
                cat_sub_groups.setdefault(cat_lbl, {}).setdefault(sub_lbl, []).append(
                    (i, op_inst)
                )

            # Build icon lookup from static categories
            from .database.categories import CATEGORIES as _CATS

            _cat_icon_map = {cat["label"]: cat.get("icon", "DOT") for cat in _CATS}
            _cat_icon_map.setdefault("Addon Operators", "PLUGIN")

            # Single border wrapping all selected operators
            sel_box = sel_ops_box.box()

            first_cat = True
            for cat_lbl, sub_groups in cat_sub_groups.items():
                # Gap between categories (no divider line) — generous above
                # a category header…
                if not first_cat:
                    sel_box.separator(factor=1.2)
                first_cat = False

                # Category — icon + bold label
                cat_icon = _cat_icon_map.get(cat_lbl, "DOT")
                cat_row = sel_box.row(align=True)
                cat_row.label(text=cat_lbl, icon=cat_icon)

                # Consecutive SINGLE-op subcategories share one grid — each
                # cell carries its own small subcategory label above its op,
                # so lone subcats pack side by side instead of stacking. A
                # subcategory with 2+ ops flushes that grid and starts on a
                # new line with a full-width header, as before.
                def _sg_pad_row(row_layout, nfill):
                    """Blank filler cells completing a partial singles row,
                    so its real cells don't stretch wider than the grid."""
                    for _k in range(nfill):
                        _f = row_layout.column(align=False)
                        _f.ui_units_x = 12.0
                        _f.label(text="")

                def _sg_seg_line(container, ncells):
                    """Line segments under a row — one per occupied cell.
                    The row is ALWAYS padded to the full column count with
                    blank fillers: rows with fewer children than the width
                    allows get their children stretched by Blender, which
                    made partial segment lines grow on resize."""
                    _sl = container.row(align=False)
                    for _k in range(ncells):
                        _sc = _sl.column(align=False)
                        _sc.ui_units_x = 12.0
                        try:
                            _sc.separator(factor=0.7, type="LINE")
                        except TypeError:
                            _sc.separator(factor=0.7)
                    for _k in range(max(0, _sg_ncols - ncells)):
                        # Fillers are PLAIN separators — the same widget
                        # class as the line segments, so every child of this
                        # row measures identically (label fillers measured
                        # differently and skewed the segment widths).
                        _f = _sl.column(align=False)
                        _f.ui_units_x = 12.0
                        _f.separator(factor=0.7)

                _singles_grid = None   # a plain column of manual rows
                _sg_row = None
                _sg_n = 0
                _first_sub = True
                _sg_top = 0.5
                # How many 12-unit cells fit the panel width (grid_flow
                # can't take full-width lines between its rows, so the
                # rows are chunked manually).
                try:
                    _ui_sc = bpy.context.preferences.system.ui_scale
                    _sg_ncols = max(1, int(
                        bpy.context.region.width / (12.0 * 20.0 * _ui_sc)))
                except Exception:
                    _sg_ncols = 2
                for sub_lbl, instances in sub_groups.items():
                    if len(instances) == 1:
                        if _singles_grid is None:
                            _singles_grid = sel_box.column(align=False)
                            _sg_row = None
                            _sg_n = 0
                            _sg_top = 0.15 if _first_sub else 0.5
                        if _sg_n % _sg_ncols == 0:
                            if _sg_n:
                                # segmented line under the completed row
                                _sg_seg_line(_singles_grid, _sg_ncols)
                            _sg_row = _singles_grid.row(align=False)
                        _sg_n += 1
                        _cell = _sg_row.column(align=False)
                        _cell.ui_units_x = 12.0
                        if sub_lbl:
                            _cell.separator(factor=_sg_top)
                            _sr = _cell.row(align=True)
                            _sr.scale_y = 0.7
                            _sr.alignment = "LEFT"
                            _sr.label(text=f"· {sub_lbl}")
                        inst_parent = _cell.column(align=False)
                        inst_parent.scale_y = 0.85
                    else:
                        if _singles_grid is not None:
                            # Close the finished singles block: pad a partial
                            # last row, then a segmented line sized to it.
                            _rem = (-_sg_n) % _sg_ncols
                            if _rem and _sg_row is not None:
                                _sg_pad_row(_sg_row, _rem)
                            _sg_seg_line(_singles_grid,
                                         (_sg_n % _sg_ncols) or _sg_ncols)
                        _singles_grid = None
                        # Subcategory — tight to the category above, small
                        # muted label, with a divider line above it
                        if sub_lbl:
                            sel_box.separator(
                                factor=0.15 if _first_sub else 0.5)
                            sub_r = sel_box.row(align=True)
                            sub_r.scale_y = 0.7
                            sub_r.alignment = "LEFT"
                            sub_r.label(text=f"· {sub_lbl}")

                        # Manual rows (same machinery as the singles): no
                        # grid_flow margins, so the label sits as close to
                        # its ops as the singles' labels do, and the row
                        # lines land at matching heights.
                        _multi_col = sel_box.column(align=False)
                        _m_row = None
                        _m_n = 0
                        inst_parent = None
                    _is_multi = len(instances) > 1
                    for i, op_inst in instances:
                        if _is_multi:
                            if _m_n % _sg_ncols == 0:
                                if _m_n:
                                    _sg_seg_line(_multi_col, _sg_ncols)
                                _m_row = _multi_col.row(align=False)
                            _m_n += 1
                            inst_parent = _m_row.column(align=False)
                            inst_parent.ui_units_x = 12.0
                            inst_parent.scale_y = 0.85
                        op_id = op_inst["id"]
                        op_props = op_inst.get("props", {})
                        op_context = op_inst.get("context", "")
                        friendly = get_friendly_name(op_id)
                        display = (
                            (friendly if friendly else op_id) if use_friendly else op_id
                        )

                        from .database.keymap_contexts import (
                            GROUP_LABELS,
                            get_contexts_by_group,
                        )
                        from .database.op_properties import op_derives_context
                        from .database.op_properties import op_requires_context as _orc2

                        derives_ctx = op_derives_context(op_id)

                        # (A) Small gap + (B) a box per operator, so each one
                        # is visibly bounded in long lists. Everything below
                        # draws into this box.
                        # (spacing handled by the grid — a separator would
                        # occupy a grid cell and break the two-per-row flow)
                        # Left column holds every row; right column is ONE tall
                        # remove button spanning them (same pattern as the
                        # extra-keybind X). Span counts the collapsed rows:
                        # label + curated pickers + context header (if drawn).
                        # Properties sit behind a dropdown on the operator
                        # row (collapsed by default): create the backing KMI
                        # up front, count what the editor would draw, and
                        # size the spanning X from the rows actually shown.
                        from . import operators as _kmops
                        from .database.op_properties import (
                            get_picker_prop_names as _gppn3,
                        )
                        _skip_props = _gppn3(op_id)
                        _n_pick = sum(
                            1 for _m in get_op_props(op_id).values()
                            if _m.get("values_from"))
                        _pk = _kmops.get_props_kmi(
                            i, op_id,
                            op_inst.get("props_data") or None,
                            op_inst.get("props") or None,
                        )
                        _n_props = _count_visible_kmi_props(_pk, op_id,
                                                            _skip_props)
                        _opp_open = bool(
                            wm.get(f"keymapper_subcat_opprops_{i}", False))
                        _n_rows = (1 + (1 if _n_pick else 0)
                                   + (_n_props if _opp_open else 0)
                                   + (0 if derives_ctx else 1))
                        # Two boxes side by side: the op box, and the remove
                        # X in its OWN bordered box on the right (outside the
                        # op border, so the centred name is centred within
                        # the visible box). The X box auto-stretches to the
                        # row height; the button inside fills it.
                        # Each grid cell is a column with air at the BOTTOM
                        # (added after the op below): the subcategory label
                        # stays tight to ITS ops, and the air separates the
                        # op from whatever follows underneath.
                        _ocell = inst_parent.column(align=False)
                        _outer = _ocell.row(align=True)
                        # Fixed cell size — this is what the auto column
                        # count measures against when the panel resizes.
                        _outer.ui_units_x = 12.0
                        inst_col = _outer.box().column(align=True)
                        _xbox = _outer.box()
                        _xcol = _xbox.column(align=True)
                        _xcol.scale_y = max(1, _n_rows)
                        _xcol.ui_units_x = 1.2
                        _rm = _xcol.operator(
                            "keymapper.form_remove_op", text="", icon="X",
                            emboss=True)
                        _rm.op_index = i

                        # Operator label row — sub-row for label prevents it from
                        # consuming all space, so the X button stays visible
                        inst_row = inst_col.row(align=True)
                        # Properties arrow at the FAR LEFT (above the context
                        # icon); a mirrored fixed spacer on the right keeps
                        # the centred name on the true centre. Fixed-width
                        # cells don't grab leftover width, so the CENTER row
                        # stays the sole flexible child.
                        if _n_props:
                            _arr = inst_row.row(align=True)
                            _arr.ui_units_x = 1.6
                            _opp_tog = _arr.operator(
                                "keymapper.toggle_extra_options",
                                text="",
                                icon=("DOWNARROW_HLT" if _opp_open
                                      else "RIGHTARROW"),
                                emboss=True, depress=_opp_open,
                            )
                            _opp_tog.key = f"opprops_{i}"
                        lbl_sub = inst_row.row(align=True)
                        lbl_sub.alignment = "CENTER"
                        if _n_props:
                            _balR = inst_row.row(align=True)
                            _balR.ui_units_x = 1.6
                            _balR.label(text="")
                        # (C) Self-describing header: position within the entry
                        # plus the property that tells same-named operators
                        # apart ("2 · Call Menu (Armature)").
                        lbl_sub.label(text=display)
                        # Flag operators that aren't registered right now (their
                        # add-on is disabled, or the op no longer exists). Probed
                        # live here — only the handful of ops in the open form.
                        from .conflict_detector import (
                            is_operator_registered as _is_reg,
                            op_source_hint as _src_hint,
                        )
                        if not _is_reg(op_id):
                            _ui = lbl_sub.operator(
                                "keymapper.unregistered_ops_info",
                                text="",
                                icon="INFO",
                                emboss=False,
                            )
                            _ui.text = (
                                f"'{op_id}' is not registered "
                                f"(from {_src_hint(op_id)}).\n\n"
                                "No shortcut is created for it. Re-enable the "
                                "add-on it comes from, or remove it from this "
                                "entry."
                            )

                        # Row 2 (only when the op has curated pickers):
                        # attribute / menu / tool pickers share one row.
                        prop_row = (inst_col.row(align=True)
                                    if _n_pick else None)

                        # Property fields — only curated pickers (menu/tool/
                        # panel/context-path) draw inline; all other properties
                        # are shown via the native "Properties" editor below.
                        prop_meta = get_op_props(op_id)
                        for prop_name, meta in prop_meta.items():
                            current_val = op_props.get(prop_name, "")
                            values_from = meta.get("values_from") or ""
                            prop_type = meta.get("type", "STRING")
                            prop_keys = sorted(prop_meta.keys())
                            j = (
                                prop_keys.index(prop_name)
                                if prop_name in prop_keys
                                else 0
                            )

                            if not values_from:
                                # Plain operator properties are shown via the native
                                # "Properties" editor below — keep only curated pickers inline.
                                continue

                            # --- context_path — native Blender search popup ---
                            if values_from == "context_path":
                                txt_idx = i * 20 + j
                                coll = wm.keymapper_context_path_props
                                while len(coll) <= txt_idx:
                                    coll.add()
                                # Seed from saved value on first draw
                                if not coll[txt_idx].value and current_val:
                                    coll[txt_idx].value = current_val
                                ctx_row = prop_row.row(align=True)
                                ctx_row.prop(
                                    coll[txt_idx],
                                    "value",
                                    text=meta.get("label", "Context Attributes"),
                                )
                                continue

                            # Dropdown prop — opens the value picker DIALOG
                            prop_hdr = prop_row.row(align=True)
                            prop_hdr.alert = not current_val
                            if current_val and use_friendly:
                                from .database.op_properties import (
                                    get_prop_values as _gpv,
                                )

                                _all_vals = _gpv(values_from, "")
                                _label_map = {
                                    vid: vlbl
                                    for vid, vlbl in _all_vals
                                    if vid
                                    not in ("__GROUP_HEADER__", "__SUBGROUP_HEADER__")
                                }
                                display_val = _label_map.get(current_val, current_val)
                            else:
                                display_val = current_val
                            prop_tog = prop_hdr.operator(
                                "keymapper.open_prop_picker",
                                text=display_val
                                if display_val
                                else f"⚠ Select {meta['label']}...",
                                icon="VIEWZOOM",
                                emboss=True,
                            )
                            prop_tog.op_index = i
                            prop_tog.prop_name = prop_name
                            # (row-level reset removed — the picker dialog
                            # carries its own Reset Selection button)

                        # Properties — behind the dropdown toggle on the
                        # operator row (collapsed by default); per-row with
                        # picker-managed props skipped. Nothing at all when
                        # the operator has no other properties.
                        if _n_props and _opp_open and _pk is not None:
                            pbox = inst_col.column(align=True)
                            draw_kmi_properties_locked(
                                pbox, _pk, skip=_skip_props,
                                slot=i, op_id=op_id)

                        # ── Context selector (unified) — below Properties ───
                        draw_op_context_selector(
                            inst_col, context, op_inst, i, op_id,
                            op_context=op_context)
                        _ocell.separator(factor=0.7)

                    # Line closing a MULTI subcategory's last row — padded
                    # so its cells keep the standard width, continuous over
                    # the occupied cells, at the same height as the singles'
                    # segment lines.
                    if sub_lbl and _is_multi and _m_n:
                        _rem = (-_m_n) % _sg_ncols
                        if _rem and _m_row is not None:
                            _sg_pad_row(_m_row, _rem)
                        _sg_seg_line(_multi_col,
                                     (_m_n % _sg_ncols) or _sg_ncols)
                    _first_sub = False
                if _singles_grid is not None:
                    _rem = (-_sg_n) % _sg_ncols
                    if _rem and _sg_row is not None:
                        _sg_pad_row(_sg_row, _rem)
                    _sg_seg_line(_singles_grid,
                                 (_sg_n % _sg_ncols) or _sg_ncols)


        else:
            sel_ops_box.label(text="No operators selected yet.", icon=safe_icon("STATUS_INFO", "INFO"))

    # ---- Conflicts — after operators ----
    from .operators import (get_form_conflict_preview,
                            get_form_internal_conflict_preview, subcat_wm_key)

    _saved = persistence.get_entry_by_id(edit_id) if edit_id else None
    saved_int = _saved.get("internal_conflicts", []) if _saved else []
    saved_sc = _saved.get("shortcut_conflicts_external", []) if _saved else []
    saved_kc = _saved.get("keybind_conflicts_external", []) if _saved else []
    saved_total = len(saved_int) + len(saved_sc) + len(saved_kc)

    _preview = get_form_conflict_preview(wm)
    prev_int = get_form_internal_conflict_preview(wm)
    prev_sc = _preview["shortcut"]
    prev_kc = _preview["keybind"]
    prev_total = len(prev_int) + len(prev_sc) + len(prev_kc)

    total_conflicts = saved_total + prev_total

    def _draw_internal_rows(container, rows, cur_entry):
        draw_internal_conflict_rows(container, rows, cur_entry)

    def _conflict_sig(rows, kind):
        """Order-independent signature of a conflict list, for comparing the
        preview against the active set."""
        out = set()
        for r in rows or []:
            if kind == "internal":
                out.add((r.get("type", ""), r.get("with", "")))
            else:
                out.add((
                    r.get("op_id", ""), r.get("keymap_name", ""),
                    r.get("key", ""), r.get("event_type", "PRESS"),
                    bool(r.get("shift")), bool(r.get("ctrl")),
                    bool(r.get("alt")), bool(r.get("oskey")),
                ))
        return out

    def _draw_preview_sub(parent, rows, kind, cur_entry, active_rows=None):
        """Nested 'Preview' box: the conflicts the CURRENT (unconfirmed) form
        state would produce, shown underneath the active ones in the same
        dropdown.

        Only drawn when it actually DIFFERS from the active set — otherwise it
        would just repeat the list directly above it, which is noise. An empty
        preview against a non-empty active set IS a difference (the edit clears
        the conflict), so that still shows.
        """
        if _conflict_sig(rows, kind) == _conflict_sig(active_rows, kind):
            return
        if not rows:
            pv = parent.box()
            pv.label(text="Preview", icon="HIDE_OFF")
            pv.label(text="No conflicts.", icon="CHECKMARK")
            return
        pv = parent.box()
        pv.label(text="Preview", icon="HIDE_OFF")
        if kind == "internal":
            _draw_internal_rows(pv, rows, cur_entry)
        else:
            _rows_col = pv.column(align=True)
            for i, ref in enumerate(rows):
                _draw_external_conflict_row(_rows_col, ref, entry_id=edit_id,
                                            ref_index=i, conflict_type=kind,
                                            preview=True)

    def _draw_conflict_group(parent, key_suffix,
                             int_c, sc_c, kc_c,
                             pv_int, pv_sc, pv_kc):
        """The three conflict dropdowns. Each shows the ACTIVE conflicts, then a
        nested Preview box with what the live form state would produce."""
        try:
            _pv_entry = _build_preview_entry(context)
        except Exception:
            _pv_entry = _saved

        # Addon-layer KMI conflicts get their own dropdown below; keep the
        # Shortcut/Keybind dropdowns to factory/user sources. Saved rows keep
        # their ORIGINAL list index as (i, ref) pairs — the override checkbox
        # toggles by index into the entry's stored ref list, so a filtered
        # enumerate would flip the wrong conflict.
        def _split_addon_pairs(refs):
            kept = [(i, r) for i, r in enumerate(refs)
                    if r.get("source") != "addon"]
            addon = [(i, r) for i, r in enumerate(refs)
                     if r.get("source") == "addon"]
            return kept, addon
        sc_pairs, ad_sc_pairs = _split_addon_pairs(sc_c)
        kc_pairs, ad_kc_pairs = _split_addon_pairs(kc_c)
        sc_c = [r for _, r in sc_pairs]
        kc_c = [r for _, r in kc_pairs]
        ad_sc = [r for _, r in ad_sc_pairs]
        ad_kc = [r for _, r in ad_kc_pairs]
        # Previews draw no checkbox, so plain filtered lists are fine there.
        pv_ad_sc = [r for r in pv_sc if r.get("source") == "addon"]
        pv_ad_kc = [r for r in pv_kc if r.get("source") == "addon"]
        pv_sc = [r for r in pv_sc if r.get("source") != "addon"]
        pv_kc = [r for r in pv_kc if r.get("source") != "addon"]

        def _hdr_count(n_active, n_preview):
            """"— N", plus "(Preview - M)" only when the preview count
            differs from the confirmed one."""
            s = f" — {n_active}"
            if n_preview != n_active:
                s += f" (Preview - {n_preview})"
            return s

        # --- Internal ---
        # All four section boxes live in one aligned column: zero vertical
        # gap between the dropdowns.
        _secs = parent.column(align=True)
        int_section = _secs.box()
        _ik = subcat_wm_key(f"{key_suffix}_internal")
        _int_open = bool(wm.get(_ik, False))
        it = int_section.row(align=True).operator(
            "keymapper.form_toggle_browse_subcat",
            text=f"Internal Conflicts{_hdr_count(len(int_c), len(pv_int))}",
            icon="DOWNARROW_HLT" if _int_open else "RIGHTARROW", emboss=False,
        )
        it.key = f"{key_suffix}_internal"
        if _int_open:
            if int_c:
                _draw_internal_rows(int_section, int_c, _saved)
            _draw_preview_sub(int_section, pv_int, "internal", _pv_entry,
                              active_rows=int_c)

        # --- Shortcut overrides ---
        _sk = subcat_wm_key(f"{key_suffix}_shortcut")
        sc_section = _secs.box()
        _sc_open = bool(wm.get(_sk, False))
        try:
            _sc_master = bool(get_prefs(bpy.context).find_shortcut_conflicts)
        except Exception:
            _sc_master = True
        _sc_title = ("Shortcut Conflict Overrides" if _sc_master
                     else "Shortcut Conflicts (Override disabled)")
        st = sc_section.row(align=True).operator(
            "keymapper.form_toggle_browse_subcat",
            text=f"{_sc_title}{_hdr_count(len(sc_c), len(pv_sc))}",
            icon="DOWNARROW_HLT" if _sc_open else "RIGHTARROW", emboss=False,
        )
        st.key = f"{key_suffix}_shortcut"
        if _sc_open:
            _sc_rows = sc_section.column(align=True)
            for i, ref in sc_pairs:
                _draw_external_conflict_row(_sc_rows, ref, entry_id=edit_id,
                                            ref_index=i, conflict_type="shortcut",
                                            preview=False)
            _draw_preview_sub(sc_section, pv_sc, "shortcut", _pv_entry,
                              active_rows=sc_c)

        # --- Keybind overrides ---
        _kk = subcat_wm_key(f"{key_suffix}_keybind")
        kc_section = _secs.box()
        _kc_open = bool(wm.get(_kk, False))
        try:
            _kc_master = bool(get_prefs(bpy.context).find_keybind_conflicts)
        except Exception:
            _kc_master = True
        _kc_title = ("Keybind Conflict Overrides" if _kc_master
                     else "Keybind Conflicts (Override disabled)")
        kt = kc_section.row(align=True).operator(
            "keymapper.form_toggle_browse_subcat",
            text=f"{_kc_title}{_hdr_count(len(kc_c), len(pv_kc))}",
            icon="DOWNARROW_HLT" if _kc_open else "RIGHTARROW", emboss=False,
        )
        kt.key = f"{key_suffix}_keybind"
        if _kc_open:
            _kc_rows = kc_section.column(align=True)
            for i, ref in kc_pairs:
                _draw_external_conflict_row(_kc_rows, ref, entry_id=edit_id,
                                            ref_index=i, conflict_type="keybind",
                                            preview=False)
            _draw_preview_sub(kc_section, pv_kc, "keybind", _pv_entry,
                              active_rows=kc_c)

        # --- Addon conflicts (shortcut + keybind refs from the addon layer) ---
        _ak = subcat_wm_key(f"{key_suffix}_addonconf")
        ad_section = _secs.box()
        _ad_open = bool(wm.get(_ak, False))
        at = ad_section.row(align=True).operator(
            "keymapper.form_toggle_browse_subcat",
            text=f"Addon Conflicts{_hdr_count(len(ad_sc) + len(ad_kc), len(pv_ad_sc) + len(pv_ad_kc))}",
            icon="DOWNARROW_HLT" if _ad_open else "RIGHTARROW", emboss=False,
        )
        at.key = f"{key_suffix}_addonconf"
        if _ad_open:
            _ad_rows = ad_section.column(align=True)
            for i, ref in ad_sc_pairs:
                _draw_external_conflict_row(_ad_rows, ref, entry_id=edit_id,
                                            ref_index=i, conflict_type="shortcut",
                                            preview=False)
            for i, ref in ad_kc_pairs:
                _draw_external_conflict_row(_ad_rows, ref, entry_id=edit_id,
                                            ref_index=i, conflict_type="keybind",
                                            preview=False)
            _draw_preview_sub(ad_section, pv_ad_sc, "shortcut", _pv_entry,
                              active_rows=ad_sc)
            _draw_preview_sub(ad_section, pv_ad_kc, "keybind", _pv_entry,
                              active_rows=ad_kc)

    # One "Conflicts" section. Active conflicts are listed in each dropdown,
    # with the live Preview nested underneath — no separate Preview section.
    conf_key = subcat_wm_key(f"conflicts_{edit_id}")
    conf_is_open = bool(wm.get(conf_key, False))
    conf_box = _form_col.box()
    conf_tog = conf_box.row(align=True).operator(
        "keymapper.form_toggle_browse_subcat",
        text=f"Conflicts ({saved_total or prev_total})",
        icon="DOWNARROW_HLT" if conf_is_open else "RIGHTARROW",
        emboss=True, depress=conf_is_open,
    )
    conf_tog.key = f"conflicts_{edit_id}"

    if conf_is_open:
        _draw_conflict_group(conf_box, "cf",
                             saved_int, saved_sc, saved_kc,
                             prev_int, prev_sc, prev_kc)



def _draw_op_entries(container, wm, ops, sel_ids, use_friendly, sel_ops):
    """Shared helper: draw operator entries with consistent scaling.
    Used by both static categories and addon operators."""
    from .database.op_properties import op_can_repeat

    col = container.column(align=True)
    col.scale_y = 0.85
    for op_id, display in ops:
        # In pure mode show raw op_id; in friendly mode use stored label or RNA fallback
        if not use_friendly:
            display = op_id
        else:
            # Use stored display label (already set correctly by operator_discovery)
            # Only fall back to get_friendly_name if display is still a raw ID
            if "." in display and display == op_id:
                display = get_friendly_name(op_id) or display
        is_picked = op_id in sel_ids
        can_repeat = op_can_repeat(op_id)
        if can_repeat:
            count = sum(1 for o in sel_ops if o["id"] == op_id)
            has_any = count > 0
            chip = col.box()
            chip_row = chip.row(align=False)
            pm = chip_row.row(align=True)
            pm.ui_units_x = 2.2
            add_btn = pm.operator(
                "keymapper.form_add_op", text="", icon="ADD", emboss=True
            )
            add_btn.operator_id = op_id
            add_btn.use_friendly = use_friendly
            rm_btn = pm.operator(
                "keymapper.form_remove_last_op", text="", icon="REMOVE", emboss=True
            )
            rm_btn.operator_id = op_id
            # The label doubles as an "add another" button so its area shows
            # the blue depress highlight when count > 0 — matching the visual
            # language of the single-select operators above. No alignment is
            # set on lbl_row so the button expands to fill the remaining width
            # (an explicit alignment would shrink it to its text size).
            lbl_row = chip_row.row(align=True)
            lbl_btn = lbl_row.operator(
                "keymapper.form_add_op",
                text=display,
                emboss=True,
                depress=has_any,
            )
            lbl_btn.operator_id = op_id
            lbl_btn.use_friendly = use_friendly
            # Always reserve the badge column (same fixed width whether or not
            # there's a count) so the label button keeps a constant width and
            # its centered text doesn't shift between the selected and
            # unselected states.
            badge = chip_row.row(align=True)
            badge.alignment = "RIGHT"
            badge.ui_units_x = 1.6
            badge.label(text=f"×{count}" if count > 0 else "")
        else:
            op_row = col.row(align=True)
            from .database.op_icons import get_op_icon
            btn = op_row.operator(
                "keymapper.form_toggle_op",
                text="",
                icon="CHECKBOX_HLT" if is_picked else "CHECKBOX_DEHLT",
                depress=is_picked,
            )
            btn.operator_id = op_id
            btn.use_friendly = use_friendly
            lbl = op_row.operator(
                "keymapper.form_toggle_op",
                text=display,
                icon=safe_icon(get_op_icon(op_id), "DOT"),
                depress=is_picked,
            )
            lbl.operator_id = op_id
            lbl.use_friendly = use_friendly


def _draw_simplified_browse(left, right, wm, sel_cat, sel_ids, search):
    """Simplified Browse Operators view: multi-operators instead of raw ops.

    Same shape as the normal browser — category column on the left, collapsible
    subcategory boxes on the right — but the categories group by ACTION, because
    a multi-op spans a dozen editors at once and can't sit in a per-editor one.

    Labels carry no keybind and no operator count: both live in the tooltip.
    """
    import re as _re

    from .database.multi_ops import simplified_categories
    from .operators import subcat_wm_key as _swk
    from .preferences import is_friendly as _is_friendly

    from .operators import _get_sel_ops as _gso

    friendly = _is_friendly()
    cats = simplified_categories()
    sel_ops_all = _gso(wm)

    def _is_selected(m):
        """Fully selected = every member present WITH this multi-op's props.
        Matching on ids alone would count sibling multi-ops that bundle the same
        operators with different props (Delete (Next Character) vs (Previous))."""
        if m.get("variants"):
            # EVERY variant must be present. Testing only variants[0] marked a
            # cluster selected whenever another cluster's selection happened to
            # contain that one prop set, so picking one lit up its neighbour.
            op_id = m["operators"][0]
            have = [(o.get("props") or {}) for o in sel_ops_all
                    if o.get("id") == op_id]
            return bool(m["variants"]) and all(
                v["props"] in have for v in m["variants"])
        want = m["props"]
        have = {o.get("id") for o in sel_ops_all
                if (o.get("props") or {}) == want}
        return bool(m["operators"]) and set(m["operators"]).issubset(have)

    def _match(m):
        if not search:
            return True
        return (search in m["label"].lower()
                or search in m["suffix"].lower()
                or any(search in o.lower() for o in m["operators"]))

    # --- category column ---
    for cid, clabel, icon, subs in cats:
        n = sum(len([m for m in mops if _match(m)]) for _s, mops in subs)
        if search and not n:
            continue
        row = left.row(align=True)
        op = row.operator(
            "keymapper.form_set_category",
            text=f"{clabel} ({n})" if search else clabel,
            icon=safe_icon(icon, "DOT"),
            depress=(sel_cat == cid),
        )
        op.category_id = cid
        sel_in_cat = sum(1 for _s, mops in subs
                         for m in mops if _is_selected(m))
        if sel_in_cat > 0:
            badge = row.row(align=True)
            badge.scale_x = 0.4
            badge.operator(
                "keymapper.form_set_category",
                text=str(sel_in_cat), depress=True,
            ).category_id = cid

    # --- multi-op list ---
    active = next(((c, s) for c, _l, _i, s in cats if c == sel_cat), None)
    if active is None:
        right.label(text="Select a category.", icon=safe_icon("STATUS_INFO", "INFO"))
        return
    cid, subs = active

    drew = False
    for sub_label, mops in subs:
        shown = [m for m in mops if _match(m)]
        if not shown:
            continue
        drew = True
        raw_key = _re.sub(r"[^a-zA-Z0-9_]", "_", f"multi_{cid}_{sub_label}")
        open_key = _swk(raw_key)
        is_open = bool(wm.get(open_key, False)) or bool(search)

        sub_box = right.box()
        hdr = sub_box.row(align=True)
        tog = hdr.operator(
            "keymapper.form_toggle_browse_subcat",
            text=f"{sub_label} ({len(shown)})" if search else sub_label,
            icon="DOWNARROW_HLT" if is_open else "RIGHTARROW",
            emboss=False,
        )
        tog.key = raw_key
        sub_sel = sum(1 for m in shown if _is_selected(m))
        if sub_sel > 0:
            badge = hdr.row(align=True)
            badge.scale_x = 0.4
            badge.operator(
                "keymapper.form_toggle_browse_subcat",
                text=str(sub_sel), depress=True,
            ).key = raw_key
        if not is_open:
            continue
        # Same row construction as the normal browser's _draw_op_entries:
        # an aligned column at scale_y 0.85, each row a checkbox button plus a
        # labelled button carrying the operator icon.
        from .database.op_icons import get_op_icon

        col = sub_box.column(align=True)
        col.scale_y = 0.85
        for m in shown:
            all_in = _is_selected(m)
            # A multi-op's members are all the same operation in different
            # contexts, so any member's icon represents the bundle. Take the
            # first that actually resolves to one.
            icon = "DOT"
            for _op in m["operators"]:
                _ic = get_op_icon(_op)
                if _ic:
                    icon = _ic
                    break
            op_row = col.row(align=True)
            btn = op_row.operator(
                "keymapper.form_toggle_multi_op",
                text="",
                icon="CHECKBOX_HLT" if all_in else "CHECKBOX_DEHLT",
                depress=all_in,
            )
            btn.multi_id = m["id"]
            lbl = op_row.operator(
                "keymapper.form_toggle_multi_op",
                text=m["label"] if friendly else m["raw_label"],
                icon=safe_icon(icon, "DOT"),
                depress=all_in,
            )
            lbl.multi_id = m["id"]

    if not drew:
        right.label(text="No multi-operators found.", icon=safe_icon("STATUS_INFO", "INFO"))


def _draw_factory_browse(left, right, wm, sel_cat, search):
    """Factory Bindings view: every binding the factory keyconfig actually uses.

    Where Simplified answers "bind this action everywhere at once", this answers
    "how does Blender actually use this operator?" — the normal browser lists
    view3d.view_axis once and never reveals that the factory binds it twelve
    ways, because the difference lives in the PROPERTIES.

    Bindings are grouped into value families (same operator, same property keys,
    differing values). A family is a DISPLAY grouping only — View Axis Front and
    View Axis Top are different actions wanting different keys, so unlike a
    multi-op a family is never selectable as a bundle.
    """
    import re as _re

    from .database.multi_ops import factory_categories
    from .database.op_icons import get_op_icon
    from .operators import _get_sel_ops as _gso
    from .operators import subcat_wm_key as _swk
    from .preferences import is_friendly as _is_friendly

    friendly = _is_friendly()
    cats = factory_categories()
    sel_ops_all = _gso(wm)

    def _picked_binding(b):
        want = b["props"]
        return any(o.get("id") == b["op_id"]
                   and (o.get("props") or {}) == want
                   for o in sel_ops_all)

    def _picked_multi(m):
        if m.get("variants"):
            # EVERY variant must be present. Testing only variants[0] marked a
            # cluster selected whenever another cluster's selection happened to
            # contain that one prop set, so picking one lit up its neighbour.
            op_id = m["operators"][0]
            have = [(o.get("props") or {}) for o in sel_ops_all
                    if o.get("id") == op_id]
            return bool(m["variants"]) and all(
                v["props"] in have for v in m["variants"])
        want = m["props"]
        have = {o.get("id") for o in sel_ops_all
                if (o.get("props") or {}) == want}
        return bool(m["operators"]) and set(m["operators"]).issubset(have)

    def _picked(row):
        if row["kind"] == "multi":
            return _picked_multi(row["multi"])
        return _picked_binding(row["binding"])

    def _match(row):
        if not search:
            return True
        if search in row["label"].lower() or search in row["suffix"].lower():
            return True
        if row["kind"] == "multi":
            return any(search in o.lower() for o in row["multi"]["operators"])
        return search in row["binding"]["op_id"].lower()

    # --- category column ---
    for cid, clabel, icon, subs in cats:
        shown = sum(1 for _s, rows in subs for r in rows if _match(r))
        if search and not shown:
            continue
        crow = left.row(align=True)
        op = crow.operator(
            "keymapper.form_set_category",
            text=f"{clabel} ({shown})" if search else clabel,
            icon=safe_icon(icon, "DOT"),
            depress=(sel_cat == cid),
        )
        op.category_id = cid
        n_sel = sum(1 for _s, rows in subs for r in rows if _picked(r))
        if n_sel:
            badge = crow.row(align=True)
            badge.scale_x = 0.4
            badge.operator(
                "keymapper.form_set_category",
                text=str(n_sel), depress=True,
            ).category_id = cid

    active = next(((c, s) for c, _l, _i, s in cats if c == sel_cat), None)
    if active is None:
        right.label(text="Select a category.", icon=safe_icon("STATUS_INFO", "INFO"))
        return
    cid, subs = active

    drew = False
    for sub_label, rows in subs:
        shown = [r for r in rows if _match(r)]
        if not shown:
            continue
        drew = True
        raw_key = _re.sub(r"[^a-zA-Z0-9_]", "_", f"fb_{cid}_{sub_label}")
        is_open = bool(wm.get(_swk(raw_key), False)) or bool(search)

        sub_box = right.box()
        hdr = sub_box.row(align=True)
        tog = hdr.operator(
            "keymapper.form_toggle_browse_subcat",
            text=f"{sub_label} ({len(shown)})" if search else sub_label,
            icon="DOWNARROW_HLT" if is_open else "RIGHTARROW",
            emboss=False,
        )
        tog.key = raw_key
        n_sel = sum(1 for r in shown if _picked(r))
        if n_sel:
            badge = hdr.row(align=True)
            badge.scale_x = 0.4
            badge.operator(
                "keymapper.form_toggle_browse_subcat",
                text=str(n_sel), depress=True,
            ).key = raw_key
        if not is_open:
            continue

        col = sub_box.column(align=True)
        col.scale_y = 0.85
        for r in shown:
            picked = _picked(r)
            is_multi = r["kind"] == "multi"
            if is_multi:
                m = r["multi"]
                icon_op = next((o for o in m["operators"] if get_op_icon(o)),
                               m["operators"][0] if m["operators"] else "")
                # Multi-ops bundle several operators, so show the count — it's
                # the one thing that distinguishes them from a single row.
                text = (f"{m['label']}  ({len(m['operators'])})" if friendly
                        else f"{m['raw_label']}  ({len(m['operators'])})")
                op_idname = "keymapper.form_toggle_multi_op"
                prop_name, prop_val = "multi_id", m["id"]
            else:
                b = r["binding"]
                icon_op = b["op_id"]
                text = b["label"] if friendly else b["op_id"]
                op_idname = "keymapper.form_toggle_factory_binding"
                prop_name, prop_val = "binding_id", b["id"]

            orow = col.row(align=True)
            btn = orow.operator(
                op_idname, text="",
                icon="CHECKBOX_HLT" if picked else "CHECKBOX_DEHLT",
                depress=picked,
            )
            setattr(btn, prop_name, prop_val)
            lbl = orow.operator(
                op_idname, text=text,
                icon=safe_icon(get_op_icon(icon_op), "DOT"),
                depress=picked,
            )
            setattr(lbl, prop_name, prop_val)

    if not drew:
        right.label(text="No factory bindings found.", icon=safe_icon("STATUS_INFO", "INFO"))


def _draw_browse_inline(layout, wm, host, sel_cat, op_mode, sel_ids):
    from .preferences import is_friendly as _is_friendly

    search = getattr(wm, "keymapper_search_prop", "").lower().strip()
    use_friendly = _is_friendly()

    from .database.dynamic_ops import get_addon_ops, get_builtin_ops

    all_builtin = get_builtin_ops()
    all_addons = get_addon_ops()

    search_row = layout.row(align=True)
    search_row.prop(
        wm,
        "keymapper_search_prop",
        text="",
        icon="VIEWZOOM",
        placeholder="Search operators...",
    )
    from .preferences import is_friendly as _isf_br
    _fp = search_row.row(align=True)
    _fp.ui_units_x = 1.2
    # Icon-only (keyboard-key glyphs) — dialog popups auto-assign text
    # accelerators and underline the letter, which icons dodge entirely.
    _fp.operator(
        "keymapper.toggle_naming_mode", text="",
        icon=safe_icon("EVENT_F" if _isf_br() else "EVENT_P", "DOT"),
    )

    split = layout.split(factor=0.35)
    left = split.column()
    right = split.column()

    # Browse-mode cycle replaces the old Refresh button (the operator cache is
    # refreshed by Re-scan Operators, so Refresh was redundant).
    #   0 = All operators   1 = Simplified (multi-ops)   2 = Factory bindings
    _mode = int(wm.get("keymapper_browse_mode", 0))
    # The Factory mode is opt-in via addon preferences (off by default). When
    # hidden, a lingering Factory mode state falls back to All.
    try:
        _show_factory = bool(get_prefs(bpy.context).show_factory_browse)
    except Exception:
        _show_factory = False
    if _mode == 2 and not _show_factory:
        _mode = 0
    _MODES = [
        ("All", "PRESET"),
        ("Simple", "CHECKBOX_HLT"),
    ]
    if _show_factory:
        _MODES.append(("Factory", "KEYINGSET"))
    _mrow = left.row(align=True)
    for _i, (_txt, _ic) in enumerate(_MODES):
        _b = _mrow.operator(
            "keymapper.toggle_simplified_browse",
            text=_txt,
            icon=safe_icon(_ic, "DOT"),
            depress=(_mode == _i),
        )
        _b.mode = _i
    left.separator(factor=0.3)
    left.label(text="Category")

    if _mode == 1:
        _draw_simplified_browse(left, right, wm, sel_cat, sel_ids, search)
        return
    if _mode == 2:
        _draw_factory_browse(left, right, wm, sel_cat, search)
        return

    for cat in CATEGORIES:
        is_sel = sel_cat == cat["id"]
        cat_ops = all_builtin.get(cat["id"], {})
        selected_in_cat = sum(
            1 for sub_ops in cat_ops.values() for oid, _ in sub_ops if oid in sel_ids
        )
        if search:
            search_count = sum(
                1
                for sub_ops in cat_ops.values()
                for oid, lbl in sub_ops
                if search in lbl.lower() or search in oid.lower()
            )
            if search_count == 0:
                continue
            cat_label = f"{cat['label']} ({search_count})"
        else:
            cat_label = cat["label"]
        cat_row = left.row(align=True)
        op = cat_row.operator(
            "keymapper.form_set_category",
            text=cat_label,
            icon=cat.get("icon", "DOT"),
            depress=is_sel,
        )
        op.category_id = cat["id"]
        if selected_in_cat > 0:
            badge = cat_row.row(align=True)
            badge.scale_x = 0.4
            badge.operator(
                "keymapper.form_set_category", text=str(selected_in_cat), depress=True
            ).category_id = cat["id"]

    # Other
    left.separator(factor=0.3)
    is_other_sel = sel_cat == "_other"
    other_cat_ops = all_builtin.get("_other", {})
    other_ops_flat = [
        (oid, lbl) for sub_ops in other_cat_ops.values() for oid, lbl in sub_ops
    ]
    other_search_cnt = (
        sum(
            1
            for oid, lbl in other_ops_flat
            if search in lbl.lower() or search in oid.lower()
        )
        if search
        else 0
    )
    total_other_sel = sum(1 for oid, _ in other_ops_flat if oid in sel_ids)
    other_label = (
        f"Other ({other_search_cnt})" if search and other_search_cnt > 0 else "Other"
    )
    if not (search and other_search_cnt == 0):
        other_row = left.row(align=True)
        other_op = other_row.operator(
            "keymapper.form_set_category",
            text=other_label,
            icon="COLLAPSEMENU",
            depress=is_other_sel,
        )
        other_op.category_id = "_other"
        if total_other_sel > 0:
            badge = other_row.row(align=True)
            badge.scale_x = 0.4
            badge.operator(
                "keymapper.form_set_category", text=str(total_other_sel), depress=True
            ).category_id = "_other"

    # Addon Operators
    left.separator(factor=0.3)
    is_addon_sel = sel_cat == "_addon"
    addon_search_cnt = (
        sum(
            1
            for ops in all_addons.values()
            for oid, lbl in ops
            if search in lbl.lower() or search in oid.lower()
        )
        if search
        else 0
    )
    total_addon_sel = sum(
        1 for ops in all_addons.values() for oid, _ in ops if oid in sel_ids
    )
    addon_label = (
        f"Addon Operators ({addon_search_cnt})"
        if search and addon_search_cnt > 0
        else "Addon Operators"
    )
    if not (search and addon_search_cnt == 0):
        addon_row = left.row(align=True)
        addon_op = addon_row.operator(
            "keymapper.form_set_category",
            text=addon_label,
            icon="PLUGIN",
            depress=is_addon_sel,
        )
        addon_op.category_id = "_addon"
        if total_addon_sel > 0:
            badge = addon_row.row(align=True)
            badge.scale_x = 0.4
            badge.operator(
                "keymapper.form_set_category", text=str(total_addon_sel), depress=True
            ).category_id = "_addon"

    # Right panel — render subcategories from unified scan
    from .operators import _get_sel_ops as _gso_right

    sel_ops_right = _gso_right(wm)

    def _draw_sub(sub_label, ops_list, key_prefix):
        if search:
            ops_list = [
                (oid, lbl)
                for oid, lbl in ops_list
                if search in lbl.lower() or search in oid.lower()
            ]
        if not ops_list:
            return
        import hashlib as _hl
        import re as _re

        raw_key = f"{key_prefix}_{sub_label}"
        safe_key = _re.sub(r"[^a-zA-Z0-9_]", "_", raw_key)
        # Same key resolution as KEYMAPPER_OT_FormToggleBrowseSubcat
        from .operators import subcat_wm_key as _swk
        open_key = _swk(safe_key)
        is_open = bool(wm.get(open_key, False)) or bool(search)
        sel_count = sum(1 for oid, _ in ops_list if oid in sel_ids)
        sub_box = right.box()
        hdr_row = sub_box.row(align=True)
        label_text = f"{sub_label} ({len(ops_list)})" if search else sub_label
        tog = hdr_row.operator(
            "keymapper.form_toggle_browse_subcat",
            text=label_text,
            icon="DOWNARROW_HLT" if is_open else "RIGHTARROW",
            emboss=False,
        )
        tog.key = safe_key
        if sel_count > 0:
            badge = hdr_row.row(align=True)
            badge.scale_x = 0.4
            badge.operator(
                "keymapper.form_toggle_browse_subcat", text=str(sel_count), depress=True
            ).key = safe_key
        if is_open:
            _draw_op_entries(
                sub_box, wm, ops_list, sel_ids, use_friendly, sel_ops_right
            )

    if sel_cat in all_builtin:
        cat_ops = all_builtin[sel_cat]
        # Draw subcategories in static order first
        cat_data = get_category_by_id(sel_cat)
        drawn_subs = set()
        if cat_data:
            for sub in cat_data["subcategories"]:
                sub_label = sub["label"]
                ops_list = cat_ops.get(sub_label, [])
                _draw_sub(sub_label, ops_list, sel_cat)
                drawn_subs.add(sub_label)
        # Then any extra subcategories from dynamic scan (e.g. "Other")
        for sub_label, ops_list in sorted(cat_ops.items()):
            if sub_label not in drawn_subs:
                _draw_sub(sub_label, ops_list, sel_cat)

    elif sel_cat == "_other":
        other_cat = all_builtin.get("_other", {})
        if not other_cat:
            right.label(text="No uncategorized operators.", icon=safe_icon("STATUS_INFO", "INFO"))
        else:
            for sub_label in sorted(other_cat.keys()):
                _draw_sub(sub_label, other_cat[sub_label], "_other")

    elif sel_cat == "_addon":
        if not all_addons:
            right.label(text="No addon operators found.", icon=safe_icon("STATUS_INFO", "INFO"))
            right.label(text="Install addons and click ↺ Refresh.", icon="BLANK1")
        else:
            shown_any = False
            for addon_name in sorted(all_addons.keys()):
                ops_list = all_addons[addon_name]
                if search:
                    ops_list = [
                        (oid, lbl)
                        for oid, lbl in ops_list
                        if search in lbl.lower() or search in oid.lower()
                    ]
                if not ops_list:
                    continue
                shown_any = True
                _draw_sub(addon_name, ops_list, "_addon")
            if not shown_any:
                right.label(text="No matching operators.", icon=safe_icon("STATUS_INFO", "INFO"))


def _conflict_ref_text(ref: dict) -> str:
    """Plain-text form of a conflict row (for tooltips): 'Operator — Context — Keybind',
    matching what _draw_external_conflict_row renders visually."""
    op_id = ref.get("op_id", "")
    km_name = ref.get("keymap_name", "")
    try:
        from .database.friendly_ops import get_friendly_name as _gfn
        from .preferences import is_friendly as _is_friendly

        op_display = (_gfn(op_id) if _is_friendly() else op_id) or op_id
    except Exception:
        op_display = op_id
    combo = _combo_label(
        False,
        bool(ref.get("shift")),
        bool(ref.get("ctrl")),
        bool(ref.get("alt")),
        bool(ref.get("oskey")),
        ref.get("key_modifier", "") or "",
        ref.get("key", ""),
        ref.get("event_type", "PRESS"),
    )
    line = f"{op_display} — {km_name} — {combo}"
    return line


def _draw_external_conflict_row(
    layout,
    ref: dict,
    entry_id: str = "",
    ref_index: int = 0,
    conflict_type: str = "keybind",
    preview: bool = False,
):
    """Draw a bordered row: [checkbox] [status icon] | op_id | [Context] | Keybind"""
    op_id = ref.get("op_id", "")
    km_name = ref.get("keymap_name", "")
    key = ref.get("key", "")
    user_reenabled = ref.get("user_reenabled", False)
    # Use friendly name if F/P toggle is set to friendly
    try:
        from .database.friendly_ops import get_friendly_name as _gfn
        from .preferences import is_friendly as _is_friendly

        op_display = _gfn(op_id) if _is_friendly() else op_id
        op_display = op_display or op_id
    except Exception:
        op_display = op_id
    # For operators disambiguated by a property (e.g. Call Menu / Call Panel /
    # Call Pie Menu carry the menu/panel idname in their "name" prop), append
    # that value so identical operator labels can be told apart. Any other
    # explicitly-set properties are indicated by name, with values in the
    # tooltip.
    props = ref.get("props") or {}
    prop_tip = ""
    if props:
        try:
            from .conflict_detector import _PROP_DISAMBIGUATED_OPS
            key_prop = _PROP_DISAMBIGUATED_OPS.get(op_id)
        except Exception:
            key_prop = None
        rest = dict(props)
        if key_prop and rest.get(key_prop):
            op_display = f"{op_display} ({rest.pop(key_prop)})"
        if rest:
            op_display = f"{op_display} ({', '.join(sorted(rest))})"
            prop_tip = "\n".join(f"{k}: {v}" for k, v in sorted(rest.items()))
    mods = "".join(
        [
            "Shift+" if ref.get("shift") else "",
            "Ctrl+" if ref.get("ctrl") else "",
            "Alt+" if ref.get("alt") else "",
            "OS+" if ref.get("oskey") else "",
        ]
    )
    _ev_full = _EVENT_TYPE_SHORT.get(ref.get("event_type", "PRESS"), "")
    if not _ev_full:  # PRESS maps to "" for labels; show it here
        _ev_full = "prs"
    key_name = _key_display_name(key) if key and key != "NONE" else "—"
    key_str = f"{mods}{key_name} ({_ev_full})"

    outer = layout.row(align=True)
    outer.separator(factor=1.5)
    if preview:
        sp = outer.split(factor=0.001, align=True)
        sp.separator()
    else:
        sp = outer.split(factor=0.12, align=True)
        cell_chk = sp.box()
        cell_chk.scale_y = 0.55
        chk_row = cell_chk.row(align=True)
        # Master override toggle for this conflict class (addon prefs). Off =
        # this default KMI stays ACTIVE: no checkbox/checkmark, warning only.
        try:
            _master_on = bool(getattr(
                get_prefs(bpy.context),
                "find_shortcut_conflicts" if conflict_type == "shortcut"
                else "find_keybind_conflicts"))
        except Exception:
            _master_on = True
        if not _master_on:
            _cls = ("Shortcut" if conflict_type == "shortcut" else "Keybind")
            _warn = chk_row.row(align=True)
            _warn.alert = True
            _warn.operator(
                "keymapper.conflict_warning_info", text="",
                icon=safe_icon("STATUS_WARNING", "ERROR"), emboss=False,
            ).text = (
                "This default KMI is active and might cause issues with your "
                f"entry. Enable {_cls} Conflict Override in Keymapper addons "
                "preferences to properly disable this conflict."
            )
        else:
            tog = chk_row.operator(
                "keymapper.toggle_conflict_reenabled",
                text="",
                icon="CHECKBOX_DEHLT" if user_reenabled else "CHECKBOX_HLT",
                emboss=False,
            )
            if tog is not None:
                tog.entry_id = entry_id
                tog.conflict_type = conflict_type
                tog.ref_index = ref_index
            if user_reenabled:
                status_row = chk_row.row(align=True)
                status_row.alert = True
                status_row.operator(
                    "keymapper.conflict_reenabled_info", text="",
                    icon="ERROR", emboss=False
                )
            else:
                chk_row.operator(
                    "keymapper.conflict_disabled_info", text="",
                    icon="CHECKMARK", emboss=False
                )

    # Remaining: operator 35%, context 35%, key 30%
    sp3 = sp.split(factor=0.35, align=True)
    cell_op = sp3.box()
    cell_op.scale_y = 0.55
    r_op = cell_op.row(align=True)
    r_op.alignment = "LEFT"
    r_op.operator(
        "keymapper.conflict_op_label",
        text=op_display,
        emboss=False,
    ).full_text = (f"{op_display}\nProperties:\n{prop_tip}" if prop_tip
                   else op_display)

    sp4 = sp3.split(factor=0.54, align=True)
    cell_ctx = sp4.box()
    cell_ctx.scale_y = 0.55
    r_ctx = cell_ctx.row(align=True)
    r_ctx.alignment = "CENTER"
    r_ctx.label(text=f"[{km_name}]")

    cell_key = sp4.box()
    cell_key.scale_y = 0.55
    r_key = cell_key.row(align=True)
    r_key.alignment = "RIGHT"
    r_key.label(text=key_str)


def _draw_settings_body(box, context):
    """Body of the collapsible Settings section (one row):
    Activate checkbox, keyconfig template dropdown, Restore KMIs, Re-scan
    Operators, Save, and the Friendly/Pure naming toggle."""
    wm = context.window_manager
    from . import keyconfig_store as _ks
    from .preferences import get_prefs, is_friendly as _is_friendly
    from .operators import has_unsaved_changes
    prefs = get_prefs(context)
    _kc_scanned = _ks.is_scanned()
    unsaved = has_unsaved_changes()

    row = box.row(align=True)
    row.use_property_split = False

    # Active/Inactive — master enable for all Keymapper shortcuts. Shows a
    # checkmark + "Active" when on, an X + "Inactive" when off.
    _active = prefs.global_enabled
    cb = row.row(align=True)
    cb.prop(
        prefs,
        "global_enabled",
        text="Active" if _active else "Inactive",
        toggle=1,
        icon="CHECKMARK" if _active else "X",
    )

    # Keyconfig template dropdown — Blender's own keyconfig menu, so it looks
    # native (no clear button) and stays bidirectional with the Keymap panel.
    import bpy as _bpy
    kc_active = wm.keyconfigs.active
    kc_name = kc_active.name if kc_active else "Key Config"
    if hasattr(_bpy.types, "USERPREF_MT_keyconfigs"):
        row.menu("USERPREF_MT_keyconfigs", text=kc_name)
    else:
        row.prop_search(wm.keyconfigs, "active", wm, "keyconfigs", text="")

    # Restore KMIs — opens a confirmation dialog before restoring to factory.
    restore = row.row(align=True)
    restore.operator("keymapper.restore_all_kmis", text="Restore KMIs", icon="LOOP_BACK")

    # Re-scan Operators — highlighted when the environment/template changed.
    from . import environment as _env_mod
    _changes = _env_mod.get_cached_changes()
    rescan = row.row(align=True)
    rescan.enabled = _kc_scanned
    rescan.alert = bool(_changes and _changes.get("has_changes"))
    rescan.operator(
        "keymapper.keyconfig_scan_full", text="Re-scan", icon="FILE_REFRESH"
    )

    # Save
    save = row.row(align=True)
    save.enabled = _kc_scanned
    save.alert = unsaved
    save.operator("keymapper.save_preferences", text="Save", icon="FILE_TICK")

    # Friendly / Pure naming toggle
    nm = row.row(align=True)
    nm.enabled = _kc_scanned
    nm.scale_x = 0.5
    nm.operator(
        "keymapper.toggle_naming_mode", text="F" if _is_friendly() else "P"
    )


def _draw_empty_state(layout):
    """The 'no shortcuts yet' baseline, identical across both panels."""
    col = layout.column(align=True)
    col.label(text="No shortcuts yet.", icon=safe_icon("STATUS_INFO", "INFO"))
    col.label(text='Press "+" to add your first shortcut.')


def _resolve_active_folder(context) -> str:
    """The single active folder for both panels. "" = Unsorted / none.

    Mirrors the simplified panel's display fallback so the toolbar always acts
    on the same folder the panel is showing: an explicit valid selection wins;
    while adding a loose entry we force Unsorted; otherwise we fall back to the
    first real folder (or Unsorted)."""
    wm = context.window_manager
    entries = persistence.get_entries()
    folders = persistence.get_folders()
    form_open = bool(wm.get("keymapper_form_active", False))
    editing_id = wm.get("keymapper_form_entry_id", "")
    adding_new = form_open and not editing_id
    new_target = wm.get("keymapper_new_entry_folder", "")
    add_to_unsorted = adding_new and not new_target
    if add_to_unsorted:
        return ""  # new loose entry → Unsorted
    has_unsorted = any(not e.get("folder_id", "") for e in entries)
    folder_ids = [f.get("folder_id", "") for f in folders]
    valid = set(folder_ids)
    if has_unsorted:
        valid.add("")  # Unsorted tab is "" and is selectable
    sel = getattr(wm, "keymapper_selected_folder_id", "")
    if sel in valid:
        return sel
    return folder_ids[0] if folder_ids else ""


def draw_update_banner(layout, context):
    """"Update Available!" row, shown only when the extension repo's cached
    index lists a newer version than the installed one."""
    try:
        from .updates import get_update_status
        status = get_update_status()
    except Exception:
        return
    if not status.get("available"):
        return
    row = layout.row(align=True)
    row.alert = True
    latest = status.get("latest", "")
    row.operator(
        "keymapper.show_update",
        text=(f"Update Available! (v{latest})" if latest
              else "Update Available!"),
        icon=safe_icon("IMPORT", "FILE_REFRESH"),
    )


def _draw_toolbar(layout, context):
    """Draw the shared toolbar row.

    Two grouped boxes plus a right-aligned cluster, used by both the
    advanced and the (upcoming) simplified panels:
      Box 1 — folder ops: new-folder | delete-folder | folder-up | folder-down | presets
      Box 2 — entry ops:  add | remove | up | down | duplicate | copy | paste
                          ...right-aligned: move-to-folder | edit | import | export
    """
    from . import keyconfig_store as _ks

    wm = context.window_manager
    entries = persistence.get_entries()
    folders = persistence.get_folders()
    selected_idx = wm.keymapper.selected_index
    form_open = bool(wm.get("keymapper_form_active", False))
    kc_scanned = _ks.is_scanned()

    has_entries = len(entries) > 0
    has_selection = has_entries and 0 <= selected_idx < len(entries)
    sel_entry = entries[selected_idx] if has_selection else None
    sel_entry_id = sel_entry.get("entry_id", "") if sel_entry else ""

    # Act on the folder currently being viewed.
    sel_folder_id = _resolve_active_folder(context)
    folder_selected = bool(sel_folder_id)

    # Entry up/down graying (position within its own folder)
    at_top = at_bottom = False
    if has_selection:
        sel_fid = sel_entry.get("folder_id", "")
        peer_ids = [
            e.get("entry_id") for e in entries if e.get("folder_id", "") == sel_fid
        ]
        eid = sel_entry.get("entry_id")
        if eid in peer_ids:
            at_top = peer_ids.index(eid) == 0
            at_bottom = peer_ids.index(eid) == len(peer_ids) - 1

    # Folder up/down graying
    folder_at_top = folder_at_bottom = False
    if folder_selected and folders:
        fidx = next(
            (i for i, f in enumerate(folders) if f.get("folder_id") == sel_folder_id),
            -1,
        )
        folder_at_top = fidx == 0
        folder_at_bottom = fidx == len(folders) - 1

    base = kc_scanned and not form_open  # nothing usable until scanned / not editing

    toolbar = layout.row(align=True)
    tb_split = toolbar.split(factor=0.22, align=False)

    # ── Box 1 — folder operations (aligns with folder-list column) ────────
    b1 = tb_split.row(align=True)

    # Right side aligns with the entry-card column.
    tb_right = tb_split.row(align=True)

    nf = b1.row(align=True)
    nf.enabled = base
    nf.operator("keymapper.add_folder", text="", icon="NEWFOLDER")
    df = b1.row(align=True)
    df.enabled = base and folder_selected
    df.operator(
        "keymapper.delete_folder", text="", icon="REMOVE"
    ).folder_id = sel_folder_id

    # Rename the active folder (inline field appears in whichever panel is shown).
    rf = b1.row(align=True)
    rf.enabled = base and folder_selected
    rf.operator(
        "keymapper.start_folder_rename", text="", icon="GREASEPENCIL"
    ).folder_id = sel_folder_id

    b1.separator()

    fu = b1.row(align=True)
    fu.enabled = base and folder_selected and not folder_at_top
    fu.operator(
        "keymapper.move_folder_up", text="", icon="TRIA_UP"
    ).folder_id = sel_folder_id
    fd = b1.row(align=True)
    fd.enabled = base and folder_selected and not folder_at_bottom
    fd.operator(
        "keymapper.move_folder_down", text="", icon="TRIA_DOWN"
    ).folder_id = sel_folder_id

    # ── Box 2 — entry operations (in the card-aligned column) ─────────────
    b2 = tb_right.row(align=True)

    ar = b2.row(align=True)
    ar.enabled = base
    ar.operator("keymapper.open_inline_form", text="", icon="ADD")
    rr = b2.row(align=True)
    rr.enabled = base and has_selection
    rr.operator("keymapper.delete_entry", text="", icon="REMOVE")

    b2.separator()

    ur = b2.row(align=True)
    ur.enabled = base and has_selection and not at_top
    ur.operator("keymapper.move_entry_up", text="", icon="TRIA_UP")
    dr = b2.row(align=True)
    dr.enabled = base and has_selection and not at_bottom
    dr.operator("keymapper.move_entry_down", text="", icon="TRIA_DOWN")

    b2.separator()

    dup = b2.row(align=True)
    dup.enabled = base and has_selection
    dup.operator("keymapper.duplicate_entry", text="", icon="DUPLICATE")
    cp = b2.row(align=True)
    cp.enabled = base and has_selection
    cp.operator("keymapper.copy_entry", text="", icon="COPYDOWN")
    pa = b2.row(align=True)
    pa.enabled = base  # paste creates an entry; needs no selection
    pa.operator("keymapper.paste_entry", text="", icon="PASTEDOWN")

    b2.separator()

    # move-to-folder + edit, acting on the selected entry
    fp = b2.row(align=True)
    fp.enabled = base and has_selection
    fp.operator(
        "keymapper.folder_picker", text="", icon="FILE_FOLDER"
    ).entry_id = sel_entry_id
    ed = b2.row(align=True)
    ed.enabled = base and has_selection
    ed.operator(
        "keymapper.edit_entry", text="", icon="GREASEPENCIL"
    ).entry_id = sel_entry_id

    # ── Right-aligned cluster: presets | restore | import | export ────────
    right = tb_right.row(align=True)
    right.alignment = "RIGHT"

    pr = right.row(align=True)
    pr.enabled = base
    pr.operator("keymapper.add_preset", text="", icon="PRESET")

    from .database.presets import find_preset_template, preset_entry_differs
    _can_restore = False
    if sel_entry is not None:
        _tpl = find_preset_template(sel_entry)
        _can_restore = _tpl is not None and preset_entry_differs(sel_entry, _tpl)
    rb = right.row(align=True)
    rb.enabled = base and _can_restore
    rb.operator(
        "keymapper.restore_preset_entry", text="", icon="LOOP_BACK"
    ).entry_id = sel_entry_id

    right.separator()

    im = right.row(align=True)
    im.enabled = base
    im.operator("keymapper.import_json", text="", icon="IMPORT")
    ex = right.row(align=True)
    ex.enabled = base and has_entries
    ex.operator("keymapper.export_json", text="", icon="EXPORT")


def _is_multi_operator(entry: dict) -> bool:
    """True when an entry holds several operators that aren't the same action
    (different friendly names), i.e. it can't be named after one operator."""
    from .database.bfa_ops import get_friendly_name as _gfn

    ops = _get_op_ids(entry)
    if len(ops) <= 1:
        return False
    names = {(_gfn(op_id) or op_id) for op_id in ops}
    return len(names) > 1


def _resolve_display_name(entry: dict) -> str:
    """Resolve an entry's display label: custom_label > friendly > raw name."""
    from .preferences import is_friendly as _is_friendly

    custom_label = entry.get("custom_label", "")
    raw_name = entry.get("display_name", "Unknown")
    if custom_label:
        return custom_label
    if not _is_friendly():
        return raw_name

    # Several different operators -> no single name fits
    if _is_multi_operator(entry):
        return "Multiple operators"

    from .database.bfa_ops import get_friendly_name as _gfn
    from .database.op_properties import get_prop_values as _gpv

    _AUTO_OPS = {"wm.call_menu_pie", "wm.call_menu", "wm.call_panel"}
    _SHORT = {"wm.call_menu_pie": "CPM", "wm.call_menu": "CM", "wm.call_panel": "CP"}
    _VAL_FROM = {
        "wm.call_menu_pie": "pie_menus",
        "wm.call_menu": "menus",
        "wm.call_panel": "panels",
    }
    try:
        import json as _j

        ops = _j.loads(entry.get("operator_ids", "[]"))
        if not ops:
            return raw_name
        first = ops[0]
        op_id = first.get("id", "")
        if op_id in _AUTO_OPS:
            menu_id = first.get("props", {}).get("name", "")
            op_context = first.get("context", "")
            if not menu_id:
                return raw_name
            lmap = {
                vid: vlbl
                for vid, vlbl in _gpv(_VAL_FROM[op_id], "")
                if vid not in ("__GROUP_HEADER__", "__SUBGROUP_HEADER__")
            }
            name = f"{_SHORT[op_id]}: {lmap.get(menu_id, menu_id)}"
            if op_context:
                name += f" ({op_context})"
            return name
        # wm.context_* operators are generic on their own — name them after
        # the attribute they act on ("Face Orientation"), matching the label
        # placeholder the form shows.
        _dp = (first.get("props") or {}).get("data_path", "")
        if _dp:
            from .database.op_properties import get_context_path_label
            _attr = get_context_path_label(_dp)
            if _attr:
                return _attr
        friendly = _gfn(op_id)
        return friendly if friendly else raw_name
    except Exception:
        return raw_name


def _entry_op_icons(entry: dict, limit: int = 8) -> list:
    """Distinct operator icons for an entry, de-duplicated by the mapped icon.

    A user-set ``custom_icon`` overrides and becomes the sole icon.
    """
    ci = entry.get("custom_icon", "")
    if ci:
        return [ci]
    from .database.op_icons import get_op_icon

    out = []
    for op_id in _get_op_ids(entry):
        ic = get_op_icon(op_id)
        if ic not in out:
            out.append(ic)
            if len(out) >= limit:
                break
    return out


def _conflict_focus_set(context):
    """Conflict-focus mode: (focus_entry_ids, focus_folder_ids) or (None, None).

    Clicking an entry's internal-conflict icon isolates that entry plus the ones
    it conflicts with — everything else greys out — so a catalog with several
    internal conflicts stays navigable. Cleared by clicking the icon again, by
    selecting an unrelated entry, or automatically once the conflict is resolved.
    """
    wm = context.window_manager
    focus_id = wm.get("keymapper_conflict_focus", "")
    if not focus_id:
        return None, None

    entries = persistence.get_entries()
    by_id = {e.get("entry_id", ""): e for e in entries}
    root = by_id.get(focus_id)
    conflicts = (root or {}).get("internal_conflicts") or []
    if not root or not conflicts:
        # Conflict resolved (or entry gone) -> drop out of focus mode.
        wm["keymapper_conflict_focus"] = ""
        return None, None

    ids = {focus_id}
    for c in conflicts:
        other = c.get("with", "")
        if other in by_id:
            ids.add(other)
    folders = {by_id[i].get("folder_id", "") for i in ids}
    return ids, folders


def _draw_simplified_card(layout, context, entry, index, preview=False):
    """One shortcut card laid out as two sibling rows that share the same
    column splits, so the modifier row lines up under the keybind column:

      checkbox | icons + label        | key   | value
               | (invisible spacer)   | mods  | Repeat

    preview=True renders a non-interactive clone (used as the live preview of a
    new entry being built in the add form): identical layout, but the whole
    card is disabled so its buttons do nothing.
    """
    entry_id = entry.get("entry_id", "")
    enabled = entry.get("enabled", True)
    # Conflict focus (see _conflict_focus_set): computed up front because both
    # the grey-out branch and the conflict icon below need it.
    _focus_ids, _focus_folders = _conflict_focus_set(context)
    selected = (not preview) and index == context.window_manager.keymapper.selected_index
    display_name = _resolve_display_name(entry)
    icons = _entry_op_icons(entry)
    editable = bool(entry.get("use_keybind", True))

    card = layout.box()
    content = card.column(align=True)

    # Edit-state: the edited card turns red with only its checkbox active;
    # every other card greys out and locks while a form is open.
    form_open = bool(context.window_manager.get("keymapper_form_active", False))
    editing_id = context.window_manager.get("keymapper_form_entry_id", "")
    is_editing = bool(form_open and editing_id and entry_id == editing_id)

    # Inert duplicates (100% identical to an earlier entry) can't be enabled:
    # the warning icon REPLACES the checkbox (its tooltip names the entry this
    # one duplicates) and the whole card is greyed out.
    from .conflict_detector import get_identical_twin as _get_twin
    twin = None
    if not preview:
        try:
            twin = _get_twin(entry, persistence.get_entries())
        except Exception:
            twin = None
    is_inert = twin is not None

    from . import keymap_manager as _km_mod
    _adopt_recs = [] if is_inert else (
        _km_mod._adoption_display.get(entry_id) or [])

    if is_editing:
        card.alert = True
    elif form_open and not preview:
        card.enabled = False  # grey + lock the other cards
    elif _focus_ids is not None and not preview and entry_id not in _focus_ids:
        # Conflict focus: everything outside the conflict greys out.
        card.enabled = False
    # Preview cards stay FULLY colored and live-looking; only the keybind
    # widgets grey out (the keybind is edited in the form, not on the card).
    # The other controls are safe to leave enabled: they all no-op on the
    # "__preview__" entry id.

    # --- Top row: [checkbox] | icons + label | key | value ---
    # Each row carries its OWN left cell (checkbox here, adopted icon below):
    # no column spans both rows, so the two rows always have identical height
    # and icons appearing can never change the card's vertical size.
    r1 = content.row(align=True)
    cb1 = r1.row(align=True)
    if is_inert:
        # Non-clickable disabled checkbox: the internal-conflict icon in the
        # bottom row already flags the duplicate, so no second warning icon.
        cb1.enabled = False
        cb1.operator(
            "keymapper.toggle_enabled",
            text="",
            icon="CHECKBOX_DEHLT",
            emboss=False,
        ).entry_id = entry_id
    else:
        cb1.operator(
            "keymapper.toggle_enabled",
            text="",
            icon="CHECKBOX_HLT" if enabled else "CHECKBOX_DEHLT",
            emboss=False,
        ).entry_id = entry_id
    body1 = r1.row(align=True)
    if is_editing:
        body1.enabled = False  # only the checkbox stays clickable
    if not enabled:
        body1.active = False
    # align=False: split cells never corner-merge, so a truncating label
    # can't square or shift the keybind cell. Uniform on all card rows.
    s1 = body1.split(factor=0.4, align=False)

    # Label with the operator icon directly before the text (centered together)
    left1 = s1.row(align=True)
    left1.alignment = "CENTER"
    icon = safe_icon(icons[0], "DOT") if icons else "NONE"
    left1.operator(
        "keymapper.select_entry",
        text=display_name,
        icon=icon,
        emboss=selected,
        depress=selected,
    ).index = index

    _kb_top = s1.row(align=True)
    if preview:
        _kb_top.enabled = False
    _draw_keybind_top(_kb_top, context, entry, index)

    # --- Bottom row: [adopted icon] | spacer + conflict icon | modifiers ---
    # Always drawn, even for multi-keybind entries (which have no editable
    # modifier controls): the row keeps the mirror + warning icon cells in the
    # same place on every card.
    if True:
        r2 = content.row(align=True)
        cb2 = r2.row(align=True)
        # Adopted-KMI marker is passive status info and appears on a LOT of
        # entries (every one identical to a pre-existing default), so it is kept
        # permanently dimmed to reduce visual noise. `active = False` greys the
        # widget WITHOUT disabling it, so the tooltip still shows on hover
        # (`enabled = False` would suppress it).
        cb2.active = False
        if _adopt_recs:
            cb2.operator(
                "keymapper.adopted_info",
                text="",
                icon="MOD_MIRROR",
                emboss=False,
            ).entry_id = entry_id
        else:
            # Invisible placeholder — must be the SAME KIND of element as the
            # checkbox above (an emboss=False icon operator), because a
            # label() pads differently and would shift the whole bottom row,
            # throwing the conflict icon off the label's centre.
            cb2.operator(
                "keymapper.select_entry", text="", icon="BLANK1", emboss=False
            ).index = index
        body2 = r2.row(align=True)
        if is_editing:
            body2.enabled = False
        if not enabled:
            body2.active = False
        s2 = body2.split(factor=0.4, align=False)
        _b_left = s2.row(align=True)
        # Left cell splits again: a narrow zone aligned under the checkbox
        # column, then the box left of the modifiers where the internal-
        # conflict icon sits CENTERED (flanking invisible select buttons keep
        # the whole strip clickable and equal-width around the icon).
        # The left cell spans the same width as the label above it, so split it
        # 50/50 and let the icon straddle the boundary: right-align the first
        # half, left-align the second. That lands the icon exactly on the
        # label's horizontal centre.
        _int_c = entry.get("internal_conflicts", []) or []
        _unreg = entry.get("unregistered_ops", []) or []
        _bsub = _b_left.split(factor=0.5, align=True)
        _z1 = _bsub.row(align=True)
        _z1.alignment = "RIGHT"
        _z2 = _bsub.row(align=True)
        _z2.alignment = "LEFT"

        # Build the unregistered-ops tooltip once (used whichever zone it lands
        # in). Names the missing ops, where they came from, and what to do.
        def _unreg_tip():
            from .conflict_detector import op_source_hint
            lines = ["This entry uses operators that are not registered:"]
            for _oid in _unreg:
                lines.append(f"    • {_oid}  (from {op_source_hint(_oid)})")
            lines.append("")
            lines.append("No shortcut is created for these operators. Re-enable "
                         "the add-on they come from, or remove them from this "
                         "entry.")
            return "\n".join(lines)

        if _int_c and not preview:
            # Tooltip body: one line per conflicting entry — the entry name +
            # folder only. The concrete conflicting bindings live in the edit
            # panel's Internal Conflicts section. The operator's bl_label
            # already supplies the "Internal Conflict(s)" heading, so it isn't
            # repeated here.
            _tips = []
            for _c in _int_c:
                _other = persistence.get_entry_by_id(_c.get("with", "")) or {}
                _oname = (_other.get("custom_label")
                          or _other.get("display_name") or "?")
                _ofid = _other.get("folder_id", "")
                _ofolder = "New Folder"
                if _ofid:
                    _fobj = persistence.get_folder_by_id(_ofid) or {}
                    _ofolder = _fobj.get("label", "Folder")
                _tips.append(f'"{_oname}" in "{_ofolder}"')
            _n = len(_int_c)
            _focused = (
                _focus_ids is not None
                and entry_id == context.window_manager.get(
                    "keymapper_conflict_focus", ""))
            # CENTERING + CONSTANT WIDTH.
            # The bottom-left cell is split 50/50 (_z1 right-aligned, _z2 left-
            # aligned). We draw EXACTLY ONE element per zone (two total) in
            # every branch, so the cell never overflows its 0.4 share and never
            # steals width from the label above (which would truncate it). The
            # meaningful icon is the element of the left-aligned _z2, so it
            # straddles the boundary — under the label's centre. _z1 carries a
            # secondary marker (focus eye, or the unregistered-ops INFO) to its
            # LEFT. The conflict COUNT is shown in the tooltip, not a separate
            # badge, to keep the width fixed.
            #
            # _z1 (left of centre): INFO if this entry also has unregistered
            # ops, else the focus eye when focused, else an invisible blank.
            if _unreg and not preview:
                _z1.operator(
                    "keymapper.unregistered_ops_info",
                    text="", icon="INFO", emboss=False,
                ).text = _unreg_tip()
            elif _focused:
                _fb = _z1.operator(
                    "keymapper.internal_conflict_info",
                    text="", icon="HIDE_OFF", emboss=False, depress=True,
                )
                _fb.text = "\n".join(_tips)
                _fb.count = _n
                _fb.entry_id = entry_id
            else:
                _z1.operator(
                    "keymapper.select_entry", text="", icon="BLANK1",
                    emboss=False,
                ).index = index
            # _z2 (centred): the conflict ERROR icon.
            _b1 = _z2.operator(
                "keymapper.internal_conflict_info",
                text="", icon="ERROR", emboss=False, depress=_focused,
            )
            _b1.text = "\n".join(_tips)
            _b1.count = _n
            _b1.entry_id = entry_id
        elif _unreg and not preview:
            # Unregistered ops only: INFO takes the centred slot.
            _z1.operator(
                "keymapper.select_entry", text="", icon="BLANK1",
                emboss=False,
            ).index = index
            _z2.operator(
                "keymapper.unregistered_ops_info",
                text="", icon="INFO", emboss=False,
            ).text = _unreg_tip()
        else:
            # No icons. Same two-slot structure so the cell width matches.
            _z1.operator(
                "keymapper.select_entry", text="", icon="BLANK1", emboss=False,
            ).index = index
            _z2.operator(
                "keymapper.select_entry", text="", icon="BLANK1", emboss=False,
            ).index = index
        _mods = s2.row(align=True)
        if preview:
            _mods.enabled = False
        if not entry.get("use_keybind", True) and entry.get("use_button", False):
            # Button-only entry: the modifier row shows WHERE the button lives.
            _draw_button_locations(_mods, entry, index=index)
        elif editable:
            _draw_keybind_bottom(_mods, context, entry)
        else:
            # Multi-keybind entry: no inline modifier controls (they're edited
            # in the form), but keep the cell so the row height matches.
            _mods.operator(
                "keymapper.select_entry", text="", emboss=False
            ).index = index

    # --- Extra rows: entries that use BOTH a keybind and a button get the
    #     button and its locations on two further rows, under the keybind. ---
    # --- One two-row slot per ADDITIONAL keybind, mirroring the primary. ---
    _extras = entry.get("extra_keybinds", []) or []
    if entry.get("use_keybind", True) and _extras:
        for _exi, _ex in enumerate(_extras):
            content.separator(factor=0.35)
            for _part in ("key", "mods"):
                _ex_row = content.row(align=True)
                _ex_cb = _ex_row.row(align=True)
                _ex_cb.operator(
                    "keymapper.select_entry", text="", icon="BLANK1",
                    emboss=False,
                ).index = index
                _ex_body = _ex_row.row(align=True)
                if is_editing:
                    _ex_body.enabled = False  # locked like the rows above
                if not enabled:
                    _ex_body.active = False
                _ex_split = _ex_body.split(factor=0.4, align=False)
                _ex_left = _ex_split.row(align=True)
                # CENTER = same alignment as the primary label cell; it also
                # ends the aligned chain, so the key cell's left corners stay
                # rounded exactly like the first slot's.
                _ex_left.alignment = "CENTER"
                # Empty cell, but clickable — selects the card like the
                # label cell on the rows above it.
                _ex_left.operator(
                    "keymapper.select_entry", text="", emboss=False,
                ).index = index
                _ex_right = _ex_split.row(align=True)
                if preview:
                    _ex_right.enabled = False
                if _part == "key":
                    _draw_extra_keybind_slot(_ex_right, context, entry, _ex,
                                             index, _exi)
                else:
                    _draw_extra_keybind_mods(_ex_right, context, entry, _ex,
                                             index, _exi)

    # Button-only entries already show the button in the first row's cell.
    if entry.get("use_button", False) and entry.get("use_keybind", True):
        content.separator(factor=0.5)   # set the button section apart
        _rx = content.row(align=True)
        _cbx = _rx.row(align=True)
        _cbx.operator(
            "keymapper.select_entry", text="", icon="BLANK1", emboss=False,
        ).index = index
        _bodyx = _rx.row(align=True)
        if is_editing:
            _bodyx.enabled = False
        if not enabled:
            _bodyx.active = False
        _sx = _bodyx.split(factor=0.4, align=False)
        _leftx = _sx.row(align=True)
        _leftx.alignment = "CENTER"  # see the extra-slot rows above
        _leftx.operator(
            "keymapper.select_entry", text="", emboss=False,
        ).index = index
        _rightx = _sx.column(align=True)
        if preview:
            _rightx.enabled = False
        # Button + locations as one aligned block of full-width widgets, so
        # the outline is rounded exactly like the keybind rows above.
        _blk = _rightx.column(align=True)
        _draw_entry_button_widget(_blk.row(align=True), entry,
                                  preview=preview, fill=True)
        _draw_button_locations(_blk.row(align=True), entry, index=index)





def _extra_repeat_available(extra) -> bool:
    """Repeat only applies to keyboard keys on ANY/PRESS."""
    val = extra.get("value", extra.get("event_type", "PRESS"))
    key = extra.get("key", "") or ""
    return (key not in {"NONE", ""} and val in {"ANY", "PRESS"}
            and not key.endswith("MOUSE") and "WHEEL" not in key)


def _draw_extra_keybind_slot(parent, context, entry, extra, index, ex_index):
    """Top row of one ADDITIONAL keybind — editable exactly like the primary
    (key capture + event value), targeting extra_keybinds[ex_index]."""
    entry_id = entry.get("entry_id", "")
    key = extra.get("key", "")
    val = extra.get("value", extra.get("event_type", "PRESS"))
    capturing = (context.window_manager.get("keymapper_capturing_entry", "")
                 == f"{entry_id}#{ex_index}")
    if key and key != "NONE":
        combo = _combo_label(
            bool(extra.get("any", False)),
            bool(extra.get("shift", False)),
            bool(extra.get("ctrl", False)),
            bool(extra.get("alt", False)),
            bool(extra.get("oskey", False)),
            extra.get("key_modifier", ""),
            key,
            val,
        )
    else:
        combo = "\u2014"

    top = parent.split(factor=0.74, align=True)
    _cap_wrap = top.row(align=True)
    # Red when no key is bound yet (em-dash), matching the card slots.
    _cap_wrap.alert = (not capturing) and combo == "\u2014"
    cap = _cap_wrap.operator(
        "keymapper.simplified_capture_key",
        text="Press a key\u2026" if capturing else combo,
        depress=capturing,
        emboss=True,
    )
    cap.entry_id = entry_id
    cap.extra_index = ex_index
    vm = top.operator(
        "keymapper.simplified_value_menu",
        text=_EVENT_TYPE_DISPLAY.get(val, val),
    )
    vm.entry_id = entry_id
    vm.extra_index = ex_index


def _draw_extra_keybind_mods(parent, context, entry, extra, index, ex_index):
    """Bottom row of one ADDITIONAL keybind: modifier toggles + Repeat."""
    entry_id = entry.get("entry_id", "")
    any_on = bool(extra.get("any", False))
    bot = parent.split(factor=0.74, align=True)
    mods = bot.row(align=True)
    for field, label in (("any", "Any"), ("shift", "Shift"), ("ctrl", "Ctrl"),
                         ("alt", "Alt"), ("oskey", "Win")):
        sub = mods.row(align=True)
        if field != "any" and any_on:
            sub.active = False      # "Any" supersedes the individual mods
        op = sub.operator(
            "keymapper.simplified_toggle_mod",
            text=label,
            depress=bool(extra.get(field, False)),
        )
        op.entry_id = entry_id
        op.mod_name = field
        op.extra_index = ex_index

    km = extra.get("key_modifier", "")
    capturing_km = (context.window_manager.get(
        "keymapper_capturing_keymod", "") == f"{entry_id}#{ex_index}")
    km_op = mods.operator(
        "keymapper.simplified_capture_key_modifier",
        text=("\u2026" if capturing_km
              else (_key_display_name(km) if km and km != "NONE" else "")),
        depress=capturing_km,
    )
    km_op.entry_id = entry_id
    km_op.extra_index = ex_index

    rep = bot.row(align=True)
    rep.active = _extra_repeat_available(extra)
    rop = rep.operator(
        "keymapper.simplified_toggle_mod",
        text="Repeat",
        depress=bool(extra.get("repeat", False)),
    )
    rop.entry_id = entry_id
    rop.mod_name = "repeat"
    rop.extra_index = ex_index



def _draw_entry_button_widget(parent, entry, preview=False, caption=True,
                              fill=False):
    """The actual button an entry creates: same operator, honouring its
    Show Icon / Show Label settings. Inert while previewing an unsaved entry.

    `caption` draws the "Button" label immediately left of it — part of the
    widget so button-only and keybind+button cards label it identically."""
    from .buttons import entry_button_icon, entry_button_label
    if caption:
        _cap = parent.row(align=True)
        _cap.ui_units_x = 1.4
        _cap.operator("keymapper.icon_hint", text="", icon="MOUSE_LMB",
                      emboss=True).text = "Button"
    _b_icon, _b_icon_val = entry_button_icon(entry)
    _show_icon = bool(entry.get("button_show_icon", True))
    _show_label = bool(entry.get("button_show_label", True))
    row = parent.row(align=True)
    if not fill:
        row.alignment = "CENTER"
    if preview or entry.get("entry_id", "") == "__preview__":
        row.enabled = False
    kw = {"text": entry_button_label(entry) if _show_label else ""}
    if _show_icon:
        if _b_icon_val:
            kw["icon_value"] = _b_icon_val
        else:
            kw["icon"] = safe_icon(_b_icon, "DOT")
    elif not kw["text"]:
        kw["text"] = " "
    _eid = entry.get("entry_id", "")
    if fill and not kw["text"]:
        # An icon-only operator renders at icon width; a blank text makes it
        # a normal button that stretches to fill the card row.
        kw["text"] = " "
    row.operator("keymapper.entry_button", **kw).entry_id = _eid


def _draw_button_locations(parent, entry, index=None):
    """Where an entry's button appears, or a hint when nowhere yet.

    With `index` given (the card), the line is a full-width embossed
    widget — rounded like the keybind rows — that selects the card when
    clicked; otherwise a plain centred label (form / popup)."""
    from .buttons import LOCATION_LABELS
    locs = entry.get("button_locations", []) or []
    txt = ", ".join(LOCATION_LABELS.get(l, l) for l in locs) \
        if locs else "No locations set"
    row = parent.row(align=True)
    if index is not None:
        _vis = entry.get("button_visible", True)
        _mk = row.row(align=True)
        _mk.ui_units_x = 1.4
        _mk.operator(
            "keymapper.toggle_entry_button_visibility", text="",
            icon="HIDE_OFF" if _vis else "HIDE_ON",
            emboss=True, depress=not _vis,
        ).entry_id = entry.get("entry_id", "")
        # Clicking the locations line opens the per-entry Locations dialog.
        row.operator("keymapper.open_entry_loc_picker", text=txt,
                     emboss=True).entry_id = entry.get("entry_id", "")
    else:
        row.alignment = "CENTER"
        row.label(text=txt)


def _draw_keybind_top(parent, context, entry, index):
    """Top keybind row: key capture | value (single binding), else read-only."""
    entry_id = entry.get("entry_id", "")

    # Button-only entry: no live keybind — draw the actual button the entry
    # creates, honouring its Show Icon / Show Label settings. On a saved entry
    # it is clickable and runs the entry; on the form's preview it is inert.
    if not entry.get("use_keybind", True):
        # Button-only: the button occupies the keybind cell and its locations
        # the row below, so the card stays exactly as tall as a keybind card.
        # fill=True gives it the same rounded full-width widget outline as a
        # keybind row (it had NO border here before).
        _draw_entry_button_widget(parent, entry, fill=True)
        return

    val = entry.get("event_type", "PRESS")
    key = entry.get("key", "")
    key_name = _key_display_name(key) if key and key != "NONE" else "—"
    capturing = (
        context.window_manager.get("keymapper_capturing_entry", "") == entry_id
    )

    # Build the full combo label, e.g. "Ctrl + Right Mouse (Drag)", shared with
    # the edit-panel header so both show identical info.
    if not capturing and key and key != "NONE":
        combo_label = _combo_label(
            entry.get("any", False),
            entry.get("shift", False),
            entry.get("ctrl", False),
            entry.get("alt", False),
            entry.get("oskey", False),
            entry.get("key_modifier", ""),
            key,
            val,
        )
    else:
        combo_label = key_name

    top = parent.split(factor=0.74, align=True)
    # extra_index MUST be set explicitly: Blender remembers the last value an
    # operator property was given, so leaving it unset made the primary row
    # inherit the extra slot's index and edit that binding instead.
    _cap_wrap = top.row(align=True)
    _cap_wrap.alert = (not capturing) and combo_label == "\u2014"
    _cap = _cap_wrap.operator(
        "keymapper.simplified_capture_key",
        text="Press a key…" if capturing else combo_label,
        depress=capturing,
        emboss=True,
    )
    _cap.entry_id = entry_id
    _cap.extra_index = -1
    _vm = top.operator(
        "keymapper.simplified_value_menu",
        text=_EVENT_TYPE_DISPLAY.get(val, val),
    )
    _vm.entry_id = entry_id
    _vm.extra_index = -1


def _draw_keybind_bottom(parent, context, entry):
    """Bottom keybind row: modifier toggles (filling the key-box width) | Repeat."""
    entry_id = entry.get("entry_id", "")
    any_on = bool(entry.get("any", False))

    bot = parent.split(factor=0.74, align=True)
    items = (
        ("any", "Any"),
        ("shift", "Shift"),
        ("ctrl", "Ctrl"),
        ("alt", "Alt"),
        ("oskey", "Win"),
        ("__keymod__", ""),  # custom key modifier slot
    )
    capturing_km = (
        context.window_manager.get("keymapper_capturing_keymod", "") == entry_id
    )
    key_mod = entry.get("key_modifier", "") or ""
    if key_mod in ("", "NONE"):
        key_mod = ""

    container = bot
    n = len(items)
    for i, (mod, mlabel) in enumerate(items):
        if i < n - 1:
            container = container.split(factor=1.0 / (n - i), align=True)
        if mod == "__keymod__":
            # Custom key modifier: empty box to capture, or the key name
            # (depressed) to clear it.
            if capturing_km:
                km_op = container.operator(
                    "keymapper.simplified_capture_key_modifier",
                    text="…",
                    depress=True,
                )
                km_op.entry_id = entry_id
                km_op.clear = False
                km_op.extra_index = -1
            elif key_mod:
                km_op = container.operator(
                    "keymapper.simplified_capture_key_modifier",
                    text=_key_display_name(key_mod),
                    depress=True,
                )
                km_op.entry_id = entry_id
                km_op.clear = True
                km_op.extra_index = -1
            else:
                km_op = container.operator(
                    "keymapper.simplified_capture_key_modifier", text=""
                )
                km_op.entry_id = entry_id
                km_op.clear = False
                km_op.extra_index = -1
            continue
        active = any_on if mod == "any" else (bool(entry.get(mod, False)) or any_on)
        op = container.operator(
            "keymapper.simplified_toggle_mod", text=mlabel, depress=active
        )
        op.entry_id = entry_id
        op.mod_name = mod
        op.extra_index = -1

    rep = bot.row(align=True)
    rep.active = _repeat_available(entry)
    rop = rep.operator(
        "keymapper.simplified_toggle_mod",
        text="Repeat",
        depress=bool(entry.get("repeat")),
    )
    rop.entry_id = entry_id
    rop.mod_name = "repeat"
    rop.extra_index = -1


def _draw_simplified_body(layout, context):
    """Simplified layout: folder buttons on the left, shortcut cards on the right."""
    wm = context.window_manager
    entries = persistence.get_entries()
    folders = persistence.get_folders()
    form_open = bool(wm.get("keymapper_form_active", False))
    editing_id = wm.get("keymapper_form_entry_id", "")

    # Folder buttons = real folders, plus Unsorted ONLY when there are loose
    # entries, or while adding a brand-new shortcut (which lands in Unsorted).
    has_unsorted = any(not e.get("folder_id", "") for e in entries)
    adding_new = form_open and not editing_id
    new_target_folder = wm.get("keymapper_new_entry_folder", "")
    add_to_unsorted = adding_new and not new_target_folder
    folder_items = [(f.get("folder_id", ""), f.get("label", "Folder")) for f in folders]
    if has_unsorted or add_to_unsorted:
        folder_items.append(("", "New Folder"))  # the loose-entries tab ("" id)

    # Nothing to show at all (no folders, no entries, not adding) → baseline
    # empty state, matching the advanced panel.
    if not folder_items:
        _draw_empty_state(layout)
        return

    # Single active-folder source of truth, shared with the toolbar.
    sel = _resolve_active_folder(context)

    split = layout.split(factor=0.22, align=False)

    # ── Left: vertical folder list ────────────────────────────────────────
    fcol = split.column(align=True)
    fcol.enabled = not form_open  # locked while editing/adding
    renaming_id = getattr(wm, "keymapper_renaming_folder_id", "")
    _fc_ids, _fc_folders = _conflict_focus_set(context)
    for fid, flabel in folder_items:
        b = fcol.row(align=True)
        b.scale_y = 1.3
        if fid == renaming_id and fid != "":
            # Inline rename: editable field + confirm. Text writes live via the
            # property's update callback; confirm clears the rename mode.
            b.prop(wm, "keymapper_folder_rename_text", text="", icon="FILE_FOLDER")
            b.operator("keymapper.confirm_folder_rename", text="", icon="CHECKMARK")
        else:
            # Conflict focus: folders with no entry in the conflict grey out.
            if _fc_folders is not None and fid not in _fc_folders:
                b.enabled = False
            b.operator(
                "keymapper.select_folder",
                text=flabel,
                depress=(fid == sel),
            ).folder_id = fid
            # Internal-conflict marker on the folder: shown when any entry in
            # this folder has an internal conflict (both involved folders get
            # the icon since conflicts are recorded symmetrically).
            _f_conf = [e for e in entries
                       if e.get("folder_id", "") == fid
                       and e.get("internal_conflicts")]
            if _f_conf:
                _names = sorted({(e.get("custom_label")
                                  or e.get("display_name") or "?")
                                 for e in _f_conf})
                _tip = ("Entries in this folder have internal conflicts:\n"
                        + "\n".join(f"• {n}" for n in _names))
                _fb = b.operator(
                    "keymapper.internal_conflict_info", text="", icon="ERROR",
                    emboss=False,
                )
                _fb.text = _tip
                _fb.count = len(_f_conf)
                # Clicking a FOLDER's icon focuses the first conflicting entry
                # it holds — same isolate behaviour as the card icon.
                _fb.entry_id = _f_conf[0].get("entry_id", "")

    # ── Right: cards for the selected folder ──────────────────────────────
    ecol = split.column(align=True)
    if sel == "":
        shown = [(i, e) for i, e in enumerate(entries) if not e.get("folder_id", "")]
    else:
        shown = [(i, e) for i, e in enumerate(entries) if e.get("folder_id", "") == sel]

    if not shown:
        if not form_open:
            if sel == "":
                _draw_empty_state(ecol)
            else:
                ecol.label(text="No shortcuts in this folder.", icon=safe_icon("STATUS_INFO", "INFO"))
        if form_open and not editing_id:
            _draw_new_entry_preview_card(ecol, context)
            _draw_inline_form(ecol, context)
        return

    drew_form = False
    _after_id = wm.get("keymapper_form_after_entry", "") if adding_new else ""
    for i, entry in shown:
        # The card of the entry being edited mirrors the FORM state, so
        # adding/removing keybinds or toggling Button updates it live instead
        # of showing the last saved version until OK.
        _card_entry = entry
        if editing_id and entry.get("entry_id", "") == editing_id:
            try:
                _live = _build_preview_entry(context)
                if _live:
                    _live["entry_id"] = entry.get("entry_id", "")
                    _live["folder_id"] = entry.get("folder_id", "")
                    _live["sort_index"] = entry.get("sort_index", 0)
                    _card_entry = _live
            except Exception:
                pass
        _draw_simplified_card(ecol, context, _card_entry, i)
        if editing_id and entry.get("entry_id", "") == editing_id:
            _draw_inline_form(ecol, context)
            drew_form = True
        elif (adding_new and _after_id
              and entry.get("entry_id", "") == _after_id):
            # New entry started while this card was selected: preview card of
            # the entry being built, with the edit form right under it.
            _draw_new_entry_preview_card(ecol, context)
            _draw_inline_form(ecol, context)
            drew_form = True

    # Add-new form, or an edited entry that isn't in the shown folder
    if form_open and not drew_form:
        if adding_new:
            _draw_new_entry_preview_card(ecol, context)
        _draw_inline_form(ecol, context)


def draw_main_panel(layout, context):
    from . import keyconfig_store as _ks

    wm = context.window_manager
    entries = persistence.get_entries()
    form_open = bool(wm.get("keymapper_form_active", False))

    # Keyconfig scan state — used later for disabling UI
    _kc_scanned = _ks.is_scanned()

    # ── Update banner (only when the repo index lists a newer version) ────
    draw_update_banner(layout, context)

    # ── Settings row (always visible) ─────────────────────────────────────
    # Activate, keyconfig template, Restore KMIs, Re-scan Operators, Save, F.
    # Each control strip gets its OWN border.
    _draw_settings_body(layout.box(), context)

    # The toolbar and the folders/entries body share ONE box, so a single
    # border wraps the lower control strip together with the content it acts on.
    _lower = layout.box()
    _draw_toolbar(_lower, context)

    # Re-scan, Save, and the naming toggle now live in the Settings row.
    # We still compute the cached environment changes here so the banner below
    # can show the version/add-on/template change warning.
    _env_changes = None
    if _kc_scanned:
        from . import environment as _env_mod

        _env_changes = _env_mod.get_cached_changes()


    # Environment-change banner — shown when Blender version changed or the
    # enabled-addon list changed since the last Re-scan. Stays visible
    # until the user clicks Re-scan (which clears the cached changes).
    if _env_changes and _env_changes.get("has_changes"):
        env_box = _lower.box()
        env_box.alert = True
        if _env_changes.get("version_changed"):
            row = env_box.row(align=True)
            row.label(
                text=f"Blender version changed: "
                f"{_env_changes['old_version']} → {_env_changes['new_version']}.",
                icon="ERROR",
            )
            sub = env_box.row(align=True)
            sub.scale_y = 0.85
            sub.label(text="Re-scan to update conflict detection.")
        added = _env_changes.get("addons_added", []) or []
        removed = _env_changes.get("addons_removed", []) or []
        if added or removed:
            row = env_box.row(align=True)
            row.label(
                text=f"Add-on list changed: +{len(added)} / -{len(removed)}.",
                icon="ERROR",
            )
            sub = env_box.row(align=True)
            sub.scale_y = 0.85
            sub.label(text="Re-scan to update operator lists & conflicts.")
        if _env_changes.get("keyconfig_changed"):
            row = env_box.row(align=True)
            row.label(
                text=f"Keymap template changed: "
                f"{_env_changes.get('old_keyconfig','?')} → "
                f"{_env_changes.get('new_keyconfig','?')}.",
                icon="ERROR",
            )
            sub = env_box.row(align=True)
            sub.scale_y = 0.85
            sub.label(text="Re-scan to update auto-contexts & conflicts.")
        if _env_changes.get("conflict_method_changed"):
            row = env_box.row(align=True)
            row.label(
                text="Conflict Detection method changed.",
                icon="ERROR",
            )
            sub = env_box.row(align=True)
            sub.scale_y = 0.85
            sub.label(text="Re-scan to update conflicts.")
        _lower.separator(factor=0.4)

    folders = persistence.get_folders()

    if not _kc_scanned:
        if not entries and not folders and not form_open:
            _draw_empty_state(_lower)
        scan_box = _lower.box()
        scan_box.label(text="Keyconfig not yet scanned.", icon=safe_icon("STATUS_WARNING", "ERROR"))
        scan_box.label(text="Required for conflict detection.")
        scan_box.operator(
            "keymapper.scan_keyconfig", text="Scan Keyconfig", icon="FILE_REFRESH"
        )
        return

    # Simplified layout is the only view — inside the same box as the toolbar.
    _draw_simplified_body(_lower, context)


class KEYMAPPER_PT_MainPanel(Panel):
    bl_label = "Keymapper"
    bl_idname = "KEYMAPPER_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Keymapper"

    @classmethod
    def poll(cls, context):
        try:
            return get_prefs(context).enable_npanel
        except Exception:
            return True

    def draw_header(self, context):
        # Show the Keymapper logo beside the panel title in the header bar.
        from . import icons as _icons
        icon_id = _icons.get_icon_id("logo")
        if icon_id:
            self.layout.label(text="", icon_value=icon_id)

    def draw(self, context):
        draw_main_panel(self.layout, context)


def draw_keymap_prefs_panel(_panel, context):
    """Keymapper at the TOP of Preferences > Keymap.

    PREPENDED into USERPREF_PT_keymap: the whole keymap page IS that one panel
    (it draws the entire keymap tree) and it carries HIDE_HEADER, so a sibling
    Panel is always appended BELOW the tree regardless of bl_order or
    registration order. Prepending is the only way to land above it.

    The cost is that a prepended draw gets no native panel header — the region
    paints that, not draw(). So the header bar is drawn by hand below
    (_draw_fake_panel_header) to match the N-panel's look.
    """
    try:
        if not get_prefs(context).enable_keymap_panel:
            return
    except Exception:
        return
    layout = _panel.layout
    draw_collapsible_main_panel(layout, context, "keymapper_keymap_prefs")
    layout.separator()


def _draw_fake_panel_header(layout, context, key: str, text: str,
                            icon_value: int = 0) -> bool:
    """Hand-drawn stand-in for Blender's native panel header.

    Blender only paints the real dark header bar for a registered Panel, and the
    two places we need it (a prepend into the Keymap prefs page, and the addon
    preferences body) are plain draw() calls. So: a full-width, embossed row
    holding a triangle + label, which reads as the same bar and toggles the
    section open/closed.

    `icon_value` (a custom-preview icon id) optionally draws before the label,
    e.g. the Keymapper logo on the main header bars.

    Returns True when the section is open.
    """
    from .operators import subcat_wm_key

    wm = context.window_manager
    raw_key = subcat_wm_key(key)
    is_open = bool(wm.get(raw_key, True))

    header = layout.row(align=True)
    header.scale_y = 0.9
    left = header.row(align=True)
    left.alignment = "LEFT"
    # Optional logo just left of the collapse arrow. Drawn as a separate label
    # because operator() only takes ONE icon (used for the arrow).
    if icon_value:
        left.label(text="", icon_value=icon_value)
    op = left.operator(
        "keymapper.form_toggle_browse_subcat",
        text=text,
        icon="DOWNARROW_HLT" if is_open else "RIGHTARROW",
        emboss=False,
    )
    op.key = key
    op.default_open = True
    # Fill the rest of the bar so the whole strip is clickable, like the native
    # header (where clicking anywhere on the bar collapses the panel).
    fill = header.row(align=True)
    op2 = fill.operator(
        "keymapper.form_toggle_browse_subcat", text="", emboss=False
    )
    op2.key = key
    op2.default_open = True
    return is_open


def draw_collapsible_main_panel(layout, context, idname: str):
    """Keymapper's main panel: a hand-drawn collapsible header bar with the body
    in a nested box beneath it.

    A prepended draw (Keymap prefs) and the addon-preferences body get no panel
    frame from Blender, so it's drawn here: an outer box holds the header, and
    the body sits in its own box inside it. The nested box's edge IS the divider
    under the header — a squashed empty box used as a rule just rendered as a
    pale gap.
    """
    container = layout.box()
    from . import icons as _icons
    if _draw_fake_panel_header(container, context, idname, "Keymapper",
                               icon_value=_icons.get_icon_id("logo")):
        body = container.box()
        draw_main_panel(body, context)



def draw_entry_loc_body(layout, context, entry_id):
    """Per-entry Locations dialog (opened from the card): edits the SAVED
    entry's button locations. Confirm keeps, Cancel/Esc/click-away revert."""
    from . import persistence
    from .buttons import BUTTON_LOCATIONS, LOCATION_LABELS

    entry = persistence.get_entry_by_id(entry_id)
    if entry is None:
        layout.label(text="Entry no longer exists.",
                     icon=safe_icon("STATUS_WARNING", "ERROR"))
        return
    locs = entry.get("button_locations", []) or []
    _draw_selected_summary(
        layout, [LOCATION_LABELS.get(l, l) for l in locs],
        "keymapper.reset_entry_button_locations",
        {"entry_id": entry_id})
    box = layout.box()
    col = box.column(align=True)
    loc_set = set(locs)
    for hook_name, loc_label in BUTTON_LOCATIONS:
        on = hook_name in loc_set
        r = col.row(align=True)
        r.alignment = "LEFT"
        t = r.operator(
            "keymapper.toggle_entry_button_location",
            text=loc_label,
            icon="CHECKBOX_HLT" if on else "CHECKBOX_DEHLT",
            emboss=False,
        )
        t.entry_id = entry_id
        t.location = hook_name
    if hasattr(layout, "template_popup_confirm"):
        layout.template_popup_confirm(
            "keymapper.dialog_commit", text="Confirm",
            cancel_text="Cancel", cancel_default=False)


def draw_button_loc_body(layout, context):
    """Body of the button Locations dialog: Selected summary + one checkbox
    per hook. Same transaction pattern as the other pickers."""
    from .buttons import BUTTON_LOCATIONS, LOCATION_LABELS
    from .operators import get_button_locations

    wm = context.window_manager
    locs = get_button_locations(wm)
    _draw_selected_summary(
        layout, [LOCATION_LABELS.get(l, l) for l in locs],
        "keymapper.reset_button_locations")
    box = layout.box()
    col = box.column(align=True)
    loc_set = set(locs)
    for hook_name, loc_label in BUTTON_LOCATIONS:
        on = hook_name in loc_set
        r = col.row(align=True)
        r.alignment = "LEFT"
        t = r.operator(
            "keymapper.toggle_button_location",
            text=loc_label,
            icon="CHECKBOX_HLT" if on else "CHECKBOX_DEHLT",
            emboss=False,
        )
        t.location = hook_name
    if hasattr(layout, "template_popup_confirm"):
        layout.template_popup_confirm(
            "keymapper.dialog_commit", text="Confirm",
            cancel_text="Cancel", cancel_default=False)


def draw_browse_popup_body(layout, context):
    """The Browse Operators list, drawn inside the draggable dialog opened by
    the edit form's "Browse Operators" button. Same body as the old inline
    browser — `_draw_browse_inline` — so all three modes (All / Simple /
    Factory), categories and selection behave identically; only the container
    changed. Every click applies to the form live, so the dialog's Close and
    Cancel buttons are equivalent: both just dismiss it."""
    from . import operators as ops_mod
    from .operators import (WM_CATEGORY, _get_sel_ops as _form_get_ops,
                            _wm_get)
    from .preferences import is_friendly as _is_friendly

    wm = context.window_manager
    host = ops_mod._host()
    op_mode = "FRIENDLY" if _is_friendly() else "PURE"
    sel_cat = _wm_get(wm, WM_CATEGORY, "object")
    sel_ops = _form_get_ops(wm)
    sel_ids = [o["id"] for o in sel_ops]

    from .database.bfa_ops import get_friendly_name as _gfn_bp
    if op_mode == "FRIENDLY":
        _names = [(_gfn_bp(o["id"]) or o["id"]) for o in sel_ops]
    else:
        _names = [o["id"] for o in sel_ops]
    _draw_selected_summary(layout, _names, "keymapper.reset_sel_ops",
                           budget=70)
    try:
        _draw_browse_inline(layout, wm, host, sel_cat, op_mode, sel_ids)
    except Exception as _e:
        layout.label(text=f"Browser unavailable: {_e}",
                     icon=safe_icon("STATUS_WARNING", "ERROR"))
    if hasattr(layout, "template_popup_confirm"):
        layout.template_popup_confirm(
            "keymapper.dialog_commit", text="Confirm",
            cancel_text="Cancel", cancel_default=False)


class KEYMAPPER_PT_QuickAdd(bpy.types.Panel):
    """Compact entry editor shown as a popup by the right-click "Add
    Keymapper Shortcut Entry" item.

    Deliberately trimmed: the operator is already captured by the right-click
    and its context resolves automatically, so the browse-operators list and
    context pickers (the widgets that open their own nested popups) are left
    out. Everything drawn here is a plain widget or a simple menu, which
    survives inside a `wm.call_panel(keep_open=True)` popup.
    """

    bl_idname = "KEYMAPPER_PT_QuickAdd"
    bl_space_type = "TOPBAR"
    bl_region_type = "HEADER"
    bl_label = "Add Keymapper Shortcut Entry"
    # Popup width (UI units). call_panel has no width argument, so the panel
    # itself has to ask for one.
    bl_ui_units_x = 21

    def draw(self, context):
        from .operators import (get_scratch_kmi, get_form_conflict_preview,
                                _get_sel_ops, subcat_wm_key)
        from .database.op_icons import get_op_icon
        from .conflict_detector import _PROP_DISAMBIGUATED_OPS
        from .preferences import is_friendly as _is_friendly
        layout = self.layout
        wm = context.window_manager

        # This popup owns one quick-add session. If the form has since been
        # re-initialised (another entry opened for editing, or a new add
        # started), stop drawing it — otherwise the popup would silently
        # adopt whatever entry is now in the form.
        if not wm.get("keymapper_quickadd_session", ""):
            layout.label(text="No longer editing this entry — press Esc to "
                              "close.", icon="INFO")
            return

        if not wm.get("keymapper_form_active", False):
            # keep_open popups cannot be closed from Python, so say something
            # useful instead of looking broken.
            layout.label(text="Done — press Esc or click away to close.",
                         icon="CHECKMARK")
            return

        # The keyconfig store must be scanned before entries can be created
        # (conflict detection and keymap routing both read it).
        from . import keyconfig_store as _ks
        if not _ks.is_scanned():
            warn = layout.box()
            warn.alert = True
            warn.label(text="Keyconfig has not been scanned yet.",
                       icon=safe_icon("STATUS_WARNING", "ERROR"))
            warn.label(text="Keymapper needs to scan your keymaps before "
                            "shortcut entries can be created.")
            layout.operator("keymapper.scan_keyconfig",
                            text="Scan Keyconfig", icon="FILE_REFRESH")
            layout.row().operator("keymapper.form_cancel",
                                  text="Cancel", icon="X")
            return

        sel_ops = _get_sel_ops(wm)
        sel_ids = [o.get("id", "") for o in sel_ops]


        def _op_display(o):
            """"Friendly Name (identifying prop)".

            The disambiguation table only covers the ops conflict detection
            needs; others (wm.context_cycle_enum, ...) still carry a
            data_path/name that the user needs to see, so fall back to the
            usual identifying props and finally to the first set prop.
            """
            oid = o.get("id", "")
            label = get_friendly_name(oid) or oid
            props = o.get("props") or {}
            key = _PROP_DISAMBIGUATED_OPS.get(oid)
            if not key or not props.get(key):
                for _cand in ("data_path", "name", "type", "mode"):
                    if props.get(_cand):
                        key = _cand
                        break
                else:
                    key = next((k for k, v in props.items() if v), None)
            if key:
                val = str(props.get(key, "") or "")
                if val:
                    if key == "data_path":
                        try:
                            from .database.op_properties import (
                                get_context_path_label)
                            val = get_context_path_label(val) or val
                        except Exception:
                            pass
                    return f"{label} ({val})"
            return label

        body = layout.column()

        draw_entry_header_row(body, context, sel_ops, sel_ids)

        # --- Keybind / Button: the mode checkbox IS the section header, with
        #     its own collapse arrow (and, for keybinds, the add button). ---
        _use_kb = bool(wm.get("keymapper_form_use_keybind", True))
        _use_btn = bool(wm.get("keymapper_form_use_button", False))

        body.separator(factor=0.6)
        kb_box = body.box()
        _kb_open = bool(wm.get(subcat_wm_key("quickadd_keybind"), True))
        try:
            import json as _kbc
            _kb_count = len(_kbc.loads(
                wm.get("keymapper_extra_keybinds", "[]") or "[]"))
        except Exception:
            _kb_count = 0
        _kb_hdr = kb_box.row(align=True)
        _kb_hdr_left = _kb_hdr.row(align=True)
        _kb_hdr_left.alignment = "LEFT"
        _kb_hdr_left.operator(
            "keymapper.form_toggle_use_keybind",
            text="Keybind" if _kb_count == 0 else "Keybinds",
            icon="CHECKBOX_HLT" if _use_kb else "CHECKBOX_DEHLT",
            emboss=False,
        )
        if _use_kb:
            _kbt = _kb_hdr_left.operator(
                "keymapper.form_toggle_browse_subcat", text="",
                icon="DOWNARROW_HLT" if _kb_open else "RIGHTARROW",
                emboss=False,
            )
            _kbt.key = "quickadd_keybind"
            _kbt.default_open = True
            _kb_add = _kb_hdr.row(align=True)
            _kb_add.alignment = "RIGHT"
            _kb_add.operator("keymapper.add_extra_keybind", text="",
                             icon="ADD")

        if _use_kb and _kb_open:
            _kb_stack = kb_box.column(align=True)   # tight between slots

            def _kb_slot(slot, kmi_obj, remove_index=None):
                """One keybind in its own box; extras also get an X."""
                _sbox = _kb_stack.box()
                _srow = _sbox.row(align=True)
                _scol = _srow.column(align=True)
                _draw_keybind_slot(_scol, kmi_obj, wm, slot_index=slot,
                                   show_detect_ctx=True)
                if remove_index is not None:
                    _xcol = _srow.column(align=True)
                    _xcol.scale_y = 2.0
                    _xcol.operator(
                        "keymapper.remove_extra_keybind_at", text="", icon="X"
                    ).slot_index = remove_index

            kmi = get_scratch_kmi()
            if kmi is not None:
                _kb_slot(0, kmi)
            else:
                kb_box.label(text="Shortcut widget unavailable.",
                             icon=safe_icon("STATUS_WARNING", "ERROR"))
            try:
                import json as _kbj
                _extras = _kbj.loads(
                    wm.get("keymapper_extra_keybinds", "[]") or "[]")
            except Exception:
                _extras = []
            from .operators import get_extra_scratch_kmi as _gek
            for _ei in range(len(_extras)):
                _ekmi = _gek(_ei + 1)
                if _ekmi is not None:
                    _kb_slot(_ei + 1, _ekmi, remove_index=_ei)

        b_box = body.box()
        _btn_open = bool(wm.get(subcat_wm_key("quickadd_button"), True))
        _btn_hdr = b_box.row(align=True)
        _bh_left = _btn_hdr.row(align=True)
        _bh_left.alignment = "LEFT"
        _bh_left.operator(
            "keymapper.form_toggle_use_button",
            text="Button",
            icon="CHECKBOX_HLT" if _use_btn else "CHECKBOX_DEHLT",
            emboss=False,
        )
        if _use_btn:
            _bt = _bh_left.operator(
                "keymapper.form_toggle_browse_subcat", text="",
                icon="DOWNARROW_HLT" if _btn_open else "RIGHTARROW",
                emboss=False,
            )
            _bt.key = "quickadd_button"
            _bt.default_open = True
            # Live preview of the button itself — same as the main form.
            try:
                _pv_e = _build_preview_entry(context)
                if _pv_e is not None:
                    _bh_pv = _btn_hdr.row(align=True)
                    _bh_pv.alignment = "RIGHT"
                    _draw_entry_button_widget(_bh_pv, _pv_e, preview=True,
                                              caption=False)
            except Exception:
                pass

        if _use_btn and _btn_open:
            from .operators import (get_button_locations,
                                    subcat_wm_key as _swk)
            from .buttons import BUTTON_LOCATIONS, LOCATION_LABELS

            _qa_ids = [o.get("id", "") for o in sel_ops]
            draw_button_section_body(b_box, context, sel_ops, _qa_ids,
                                     _use_kb)

        # --- Operator(s), read-only ---
        op_box = body.box()
        _opkey = "quickadd_operator"
        _op_open = bool(wm.get(subcat_wm_key(_opkey), False))

        def _op_parts(o):
            """(friendly name, attribute/menu value) for the header text."""
            oid = o.get("id", "")
            name = get_friendly_name(oid) or oid
            props = o.get("props") or {}
            key = _PROP_DISAMBIGUATED_OPS.get(oid)
            if not key or not props.get(key):
                for _c in ("data_path", "name", "type", "mode"):
                    if props.get(_c):
                        key = _c
                        break
                else:
                    key = next((k for k, v in props.items() if v), None)
            val = str(props.get(key, "") or "") if key else ""
            if key == "data_path" and val:
                try:
                    from .database.op_properties import get_context_path_label
                    val = get_context_path_label(val) or val
                except Exception:
                    pass
            return name, val

        if len(sel_ops) == 1:
            _nm, _val = _op_parts(sel_ops[0])
            _otext = f"Operator ({_nm} - {_val})" if _val else f"Operator ({_nm})"
            _oicon = safe_icon(get_op_icon(sel_ops[0].get("id", "")), "DOT")
        else:
            _otext = f"Operators ({len(sel_ops)})"
            _oicon = "DOT"
        _ohdr = op_box.row(align=True)
        _ohdr.alignment = "LEFT"
        # Operator icon sits left of the disclosure arrow.
        _ohdr.label(text="", icon=_oicon)
        _otog = _ohdr.operator(
            "keymapper.form_toggle_browse_subcat",
            text=_otext,
            icon=("DOWNARROW_HLT" if _op_open else "RIGHTARROW"),
            emboss=False,
        )
        _otog.key = _opkey
        _otog.default_open = False

        if _op_open:
            # Expanding shows the properties themselves — no second dropdown.
            from . import operators as _kmops
            for _i, o in enumerate(sel_ops):
                if len(sel_ops) > 1:
                    _nm, _val = _op_parts(o)
                    op_box.row(align=True).label(
                        text=f"{_nm} - {_val}" if _val else _nm,
                        icon=safe_icon(get_op_icon(o.get("id", "")), "DOT"))
                _pk = _kmops.get_props_kmi(
                    _i, o.get("id", ""),
                    o.get("props_data") or None,
                    o.get("props") or None,
                )
                _pbox = op_box.column(align=True)
                # Only the IDENTIFYING property is locked (the attribute or
                # menu name fixed by what was right-clicked); everything else
                # — Module and friends — stays editable.
                _oid = o.get("id", "")
                _lock = set()
                _kp = _PROP_DISAMBIGUATED_OPS.get(_oid)
                if not _kp:
                    for _c in ("data_path", "name"):
                        if (o.get("props") or {}).get(_c):
                            _kp = _c
                            break
                if _kp:
                    _lock.add(_kp)
                if _pk is None or not draw_kmi_properties_locked(
                        _pbox, _pk, locked=_lock,
                        slot=_i, op_id=_oid):
                    _pbox.label(text="No editable properties.",
                                icon=safe_icon("STATUS_INFO", "INFO"))

                # Context — same picker as the main form (opens its dialog
                # on top of the popup).
                _cbox = op_box.column(align=True)
                draw_op_context_selector(
                    _cbox, context, o, _i, o.get("id", ""),
                    op_context=o.get("context", ""))
        if not sel_ops:
            op_box.label(text="No operator captured.",
                         icon=safe_icon("STATUS_WARNING", "ERROR"))

        # --- Conflicts (collapsible; live preview rows) ---
        # Refresh the scratch-KMI mirror first: the preview cache is keyed on
        # it and the 0.2s timer would otherwise leave a stale count right
        # after a key change. build_scratch_mirror is READ-ONLY (peek-based).
        try:
            from .operators import build_scratch_mirror
            wm["keymapper_scratch_mirror"] = build_scratch_mirror(wm)
        except Exception:
            pass
        try:
            prev = get_form_conflict_preview(wm)
            prev_sc = prev.get("shortcut", [])
            prev_kc = prev.get("keybind", [])
        except Exception:
            prev_sc, prev_kc = [], []
        try:
            from .operators import get_form_internal_conflict_preview
            prev_int = get_form_internal_conflict_preview(wm)
        except Exception:
            prev_int = []
        n = len(prev_sc) + len(prev_kc) + len(prev_int)

        c_box = body.box()
        # Expanders are BoolProperties, not operators — see the folder note.
        _ckey = "quickadd_conflicts"
        _copen = bool(wm.get(subcat_wm_key(_ckey), False))
        c_hdr = c_box.row(align=True)
        c_hdr.alignment = "LEFT"
        # Shortcut/keybind conflicts are OVERRIDES — expected and handled —
        # so they stay informational. Only an INTERNAL conflict (against
        # another Keymapper entry) is a real problem, and only that turns the
        # header red with a warning icon.
        _has_internal = bool(prev_int)
        if _has_internal:
            c_hdr.alert = True
        # Status icon sits to the LEFT of the dropdown button.
        c_hdr.label(text="", icon=(
            safe_icon("STATUS_WARNING", "ERROR") if _has_internal
            else (safe_icon("STATUS_INFO", "INFO") if n else "CHECKMARK")))
        _ct = c_hdr.operator(
            "keymapper.form_toggle_browse_subcat",
            text=(f"Conflict Overrides: {n}" if n else "No conflicts"),
            icon=("DOWNARROW_HLT" if _copen else "RIGHTARROW"),
            emboss=False,
        )
        _ct.key = _ckey
        _ct.default_open = False

        if _copen:
            # All classes are always listed, even at zero, so the popup
            # shows what was checked rather than only what failed. Addon-layer
            # refs get their own dropdown, mirroring the main editor.
            _p_sc = [r for r in prev_sc if r.get("source") != "addon"]
            _p_kc = [r for r in prev_kc if r.get("source") != "addon"]
            _p_ad = ([(r, "shortcut") for r in prev_sc
                      if r.get("source") == "addon"]
                     + [(r, "keybind") for r in prev_kc
                        if r.get("source") == "addon"])
            for _title, _rows, _kind in (
                ("Internal Conflicts", prev_int, "internal"),
                ("Shortcut Conflicts", _p_sc, "shortcut"),
                ("Keybind Conflicts", _p_kc, "keybind"),
                ("Addon Conflicts", _p_ad, "addon"),
            ):
                _skey = "quickadd_cf_" + _kind
                _sopen = bool(wm.get(subcat_wm_key(_skey), False))
                _shdr = c_box.row(align=True)
                _shdr.alignment = "LEFT"
                if _kind == "internal" and _rows:
                    _shdr.alert = True
                _st = _shdr.operator(
                    "keymapper.form_toggle_browse_subcat",
                    text=f"{_title} — {len(_rows)}",
                    icon=("DOWNARROW_HLT" if _sopen else "RIGHTARROW"),
                    emboss=False,
                )
                _st.key = _skey
                _st.default_open = False
                if not _sopen:
                    continue
                if not _rows:
                    _e = c_box.row()
                    _e.separator(factor=1.5)
                    _e.label(text="None")
                    continue
                _col = c_box.column(align=True)
                if _kind == "internal":
                    # Same renderer as the main editor, in an aligned column
                    # so the rows sit as tight as the other conflict lists.
                    try:
                        _cur = _build_preview_entry(context)
                    except Exception:
                        _cur = None
                    draw_internal_conflict_rows(_col, _rows, _cur)
                elif _kind == "addon":
                    for _i, (_ref, _rk) in enumerate(_rows):
                        _draw_external_conflict_row(
                            _col, _ref, entry_id="", ref_index=_i,
                            conflict_type=_rk, preview=True)
                else:
                    for _i, _ref in enumerate(_rows):
                        _draw_external_conflict_row(
                            _col, _ref, entry_id="", ref_index=_i,
                            conflict_type=_kind, preview=True)

        # --- Buttons: OK / Cancel with Open Full Editor beside them ---
        layout.separator(factor=0.6)
        btns = layout.row(align=True)
        btns.operator("keymapper.form_confirm", text="Confirm", icon="CHECKMARK")
        btns.operator("keymapper.form_cancel", text="Cancel", icon="X")
        btns.operator("keymapper.open_full_editor",
                      text="Open Full Editor", icon="WINDOW")

        # --- Optional live card: opt-in, off by default, at the very bottom
        #     so toggling it never shifts the controls above. ---
        _pv_on = bool(wm.get(subcat_wm_key("quickadd_preview"), False))
        _pv_row = layout.row(align=True)
        _pv_row.alignment = "LEFT"
        _pv_row.operator(
            "keymapper.toggle_preview_card",
            text="Preview Keymapper Entry",
            icon="CHECKBOX_HLT" if _pv_on else "CHECKBOX_DEHLT",
            emboss=False,
        )
        if _pv_on:
            try:
                _draw_new_entry_preview_card(layout, context)
            except Exception as _e:
                layout.label(text=f"Card unavailable: {_e}",
                             icon=safe_icon("STATUS_WARNING", "ERROR"))



_classes = (KEYMAPPER_PT_MainPanel, KEYMAPPER_PT_QuickAdd)


def _apply_compact_sidebar_icon():
    """On Blender 5.2+, give the sidebar category an icon for compact mode.

    5.2's compact sidebar exposes TWO panel attributes (PR #154985):
      • ``bl_icon``       — a built-in icon NAME (string), e.g. "KEYINGSET".
      • ``bl_icon_value`` — a custom icon id (int), e.g. a bpy.utils.previews
                            icon_id. This is how add-ons show their OWN icon.

    We use ``bl_icon_value`` with the Keymapper logo when the custom icon loaded,
    and fall back to the built-in ``bl_icon`` = "KEYINGSET" otherwise. Wrapped
    defensively: on failure the tab still works (compact mode shows "Ke").
    5.1 never reaches the assignment.
    """
    if bpy.app.version < (5, 2, 0):
        return
    try:
        from . import icons as _icons
        icon_id = _icons.get_icon_id("logo")
        if icon_id:
            KEYMAPPER_PT_MainPanel.bl_icon_value = icon_id
        else:
            KEYMAPPER_PT_MainPanel.bl_icon = "KEYINGSET"
    except Exception as e:
        print(f"[Keymapper] Compact sidebar icon not applied: {e}")


def register():
    _apply_compact_sidebar_icon()
    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            # If bl_icon (or anything else) made the class unregisterable,
            # drop the custom icon and try once more so the panel still shows.
            print(f"[Keymapper] Panel register retry (dropping bl_icon): {e}")
            for _attr in ("bl_icon", "bl_icon_value"):
                if hasattr(cls, _attr):
                    try:
                        delattr(cls, _attr)
                    except Exception:
                        pass
            bpy.utils.register_class(cls)
    try:
        bpy.types.USERPREF_PT_keymap.prepend(draw_keymap_prefs_panel)
    except Exception as e:
        print(f"[Keymapper] Could not attach Keymap-preferences panel: {e}")
    print("[Keymapper] Panel registered.")


def unregister():
    try:
        bpy.types.USERPREF_PT_keymap.remove(draw_keymap_prefs_panel)
    except Exception:
        pass
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[Keymapper] Panel unregistered.")
