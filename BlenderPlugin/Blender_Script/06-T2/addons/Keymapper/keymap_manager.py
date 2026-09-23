"""
keymap_manager.py
Phase 5: Full keymap generation implementation.

Responsibilities:
  - Create KMIs in keyconfigs.addon when an entry is saved
  - Enable/disable KMIs when an entry is toggled
  - Remove KMIs when an entry is deleted
  - Rebuild all KMIs on Blender startup
  - Only recreate KMIs on edit if something actually changed
"""

import bpy
import json

# ---------------------------------------------------------------------------
# Internal KMI registry
# { entry_id: [ (keymap, kmi), ... ] }
# ---------------------------------------------------------------------------

_kmi_registry: dict = {}

# { entry_id: set((idname, (key,value,shift,ctrl,alt,oskey)), ...) } — the
# binding specs an entry ACTUALLY registered, captured at registration and
# updated only on (re)registration. Removal matches live addon-owned KMIs
# against these durable specs, so editing an entry's binding still removes the
# OLD KMIs (the live item carries the old binding until re-registered), and an
# inert duplicate — which never registers — has no specs and removes nothing,
# leaving its canonical twin's identical-signature KMIs untouched.
_entry_kmi_specs: dict = {}


def _entry_binding_specs(entry: dict) -> set:
    """Return the set of (idname, signature) this entry's bindings map to."""
    import json
    try:
        op_list = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        op_list = []
    op_ids = [o.get("id") for o in op_list if isinstance(o, dict) and o.get("id")]
    specs = set()
    main_key = entry.get("key", "")
    if main_key and main_key != "NONE":
        main_sig = (main_key, entry.get("event_type", "PRESS"),
                    bool(entry.get("shift", False)), bool(entry.get("ctrl", False)),
                    bool(entry.get("alt", False)), bool(entry.get("oskey", False)))
        for oid in op_ids:
            specs.add((oid, main_sig))
    for extra in entry.get("extra_keybinds", []):
        ek = extra.get("key", "")
        if not ek or ek == "NONE":
            continue
        esig = (ek, extra.get("value", "PRESS"),
                bool(extra.get("shift", False)), bool(extra.get("ctrl", False)),
                bool(extra.get("alt", False)), bool(extra.get("oskey", False)))
        for oid in op_ids:
            specs.add((oid, esig))
    return specs

# ---------------------------------------------------------------------------
# Disabled defaults registry
# { entry_id: [ kmi_ref_dict, ... ] }
# Stores references to default KMIs we've disabled, keyed by entry_id.
# ---------------------------------------------------------------------------

_disabled_defaults: dict = {}
_entry_kmi_keymaps: dict = {}  # entry_id -> {(km_name, idname, sig)} for collapse healing


# ---------------------------------------------------------------------------
# Keymap name lookup
# Scans all of keyconfigs.default to find which keymap an operator lives in.
# ---------------------------------------------------------------------------

_op_keymap_cache: dict = {}   # { op_id: keymap_name } single best (legacy)
_op_keymaps_all: dict = {}    # { op_id: [keymap_name, ...] } all homes
_op_keymaps_by_prop: dict = {}  # { (op_id, prop_value): [keymap_name, ...] } for prop-disambiguated ops
_op_keymap_built = False


# Priority order — higher index = higher priority (preferred)
# When an operator appears in multiple keymaps, we pick the highest priority one
_KEYMAP_PRIORITY = [
    "Outliner",
    "Text",
    "Node Editor",
    "UV Editor",
    "Image",
    "Graph Editor",
    "Dopesheet",
    "NLA Editor",
    "Sequencer",
    "Preview",
    "Lattice",
    "Font",
    "Metaball",
    "Curves",
    "Grease Pencil",
    "Particle",
    "Image Paint",
    "Weight Paint",
    "Vertex Paint",
    "Sculpt",
    "Pose",
    "Armature",
    "Curve",
    "Mesh",
    "Object Mode",
    "3D View",
    "Screen",
    "Window",   # highest priority — fires everywhere
]

_KEYMAP_PRIORITY_MAP = {name: i for i, name in enumerate(_KEYMAP_PRIORITY)}


def _build_op_keymap_cache():
    global _op_keymap_built
    wm = bpy.context.window_manager

    # Scan ALL relevant keyconfigs and union the keymaps each operator appears
    # in. A binding may exist only in keyconfigs.default (factory) and not be
    # materialized in the named active config, or vice versa — scanning just one
    # misses homes (e.g. grease_pencil.select_all in "Grease Pencil Edit Mode").
    keyconfigs = []
    seen_kc = set()
    for name in ("Blender", "BForArtists", "blender"):
        kc = wm.keyconfigs.get(name)
        if kc is not None and id(kc) not in seen_kc:
            keyconfigs.append(kc)
            seen_kc.add(id(kc))
    for kc in (wm.keyconfigs.default, wm.keyconfigs.active, wm.keyconfigs.user):
        if kc is not None and id(kc) not in seen_kc:
            keyconfigs.append(kc)
            seen_kc.add(id(kc))
    if not keyconfigs:
        return

    from .conflict_detector import _PROP_DISAMBIGUATED_OPS as _PROP_DIS
    _op_keymaps_by_prop.clear()
    op_candidates: dict = {}
    # Keymapper-owned KMIs must not contribute to auto-context homes. Negative
    # id marks ours in factory-existing keymaps, but in user-CREATED keymaps our
    # items get positive ids — so in the user/active layers also skip any
    # (keymap, op) recorded in _entry_kmi_keymaps or pending binding fixes.
    # Factory keyconfigs still contribute the true homes for those ops.
    owned_km_op = set()
    for recs in _entry_kmi_keymaps.values():
        for rec in recs:
            owned_km_op.add((rec[0], rec[1]))
    for pf in _pending_binding_fixes:
        owned_km_op.add((pf[0], pf[1]))
    _kc_user = wm.keyconfigs.user
    for kc in keyconfigs:
        is_user_layer = (kc == _kc_user)
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                if is_user_layer and kmi.id < 0:
                    continue
                op_id = kmi.idname
                if not op_id:
                    continue
                if is_user_layer and (km.name, op_id) in owned_km_op:
                    continue
                op_candidates.setdefault(op_id, []).append(km.name)
                # Prop-disambiguated ops (Call Menu/Panel/Pie, tool_set, ...)
                # also get homes keyed by the disambiguating property value.
                key_prop = _PROP_DIS.get(op_id)
                if key_prop:
                    try:
                        val = str(getattr(kmi.properties, key_prop, "") or "")
                    except Exception:
                        val = ""
                    if val:
                        lst = _op_keymaps_by_prop.setdefault((op_id, val), [])
                        if km.name not in lst:
                            lst.append(km.name)

    for op_id, keymap_names in op_candidates.items():
        # De-duplicate while preserving the actual keymaps the operator lives in.
        # We do NOT promote mode keymaps to "3D View": the operator's real home
        # (e.g. "Mesh", "Pose", "Curve") is where its conflicts and binding
        # belong. Promotion caused every mode select_all to collapse to 3D View.
        seen = []
        for n in keymap_names:
            if n not in seen:
                seen.append(n)
        _op_keymaps_all[op_id] = seen
        # Legacy single-best (used only as a last-resort fallback).
        best = max(seen, key=lambda n: _KEYMAP_PRIORITY_MAP.get(n, -1))
        _op_keymap_cache[op_id] = best

    _op_keymap_built = True
    print(f"[Keymapper] Op->keymap cache built: {len(_op_keymap_cache)} operators mapped.")


# Bundled Keymapper operators have a fixed home keymap. We resolve these
# deterministically (NOT by scanning where a KMI currently lives), because once
# Keymapper registers one of these in some keymap, the op->keymap cache would
# otherwise pick that up and make the auto-context depend on prior registration.
_BUNDLED_OP_KEYMAPS = {
    "keymapper.op_marking_menu":            ["3D View"],
    "keymapper.op_quick_view":              ["3D View"],
    "keymapper.op_pivot_transform":         ["3D View"],
    "mesh.keymapper_pie_select_mode":       ["3D View"],  # Set Component Mode
    "keymapper.op_open_assetbrowser_window": ["Window"],
}


# Module prefix → keymap fallback (for operators not in any default keymap)
# Fallback keymap for operators that have NO binding anywhere in the keyconfig
# (443 of the 655 mode-module operators, e.g. mesh.select_similar), so their
# home can't be learned from an existing KMI.
#
# These MUST point at the operator's own MODE keymap, not the shared "3D View"
# parent. 3D View is live in every 3D mode, so registering a mesh-edit operator
# there makes it fire in Object Mode, Pose, Sculpt, ... — both wrong behaviour
# and a source of phantom conflicts (an unbound mesh.* op would "overlap"
# object.* and pose.* ops purely because they all sat in 3D View). Bound
# siblings already resolve this way — curve.select_similar -> "Curve",
# armature.select_similar -> "Armature" — so this just makes the unbound ones
# consistent with them.
_MODULE_KEYMAP_FALLBACK = {
    "object":       "Object Mode",
    "mesh":         "Mesh",
    "curve":        "Curve",
    "armature":     "Armature",
    "pose":         "Pose",
    "sculpt":       "Sculpt",
    "mball":        "Metaball",
    # paint.* has no single home — see _PAINT_PREFIX_KEYMAP below.
    "paint":        "3D View",
    "vertex_paint": "Vertex Paint",
    "image":        "Image",
    "node":         "Node Editor",
    "graph":        "Graph Editor",
    "action":       "Dopesheet",
    "nla":          "NLA Editor",
    "sequencer":    "Sequencer",
    "text":         "Text",
    "outliner":     "Outliner",
    "uv":           "UV Editor",
    "view2d":       "View2D",
    "view3d":       "3D View",
    "screen":       "Screen",
}


# paint.* operators split across several mode keymaps, so a single module-level
# fallback can't be right. Resolve by the operator's name prefix, matching where
# the BOUND paint.* operators actually live.
_PAINT_PREFIX_KEYMAP = {
    "vertex":     "Vertex Paint",
    "weight":     "Weight Paint",
    "image":      "Image Paint",
    "grab":       "Image Paint",
    "mask":       "Sculpt",
    "hide":       "Sculpt",
    "visibility": "Sculpt",
    "face":       "Paint Face Mask (Weight, Vertex, Texture)",
    "vert":       "Paint Vertex Selection (Weight, Vertex)",
}


def _module_fallback_keymap(op_id: str) -> str:
    """Fallback keymap for an operator with no binding to learn from."""
    module = op_id.split(".")[0] if "." in op_id else ""
    if module == "paint":
        name = op_id.split(".", 1)[1] if "." in op_id else ""
        prefix = name.split("_", 1)[0]
        km = _PAINT_PREFIX_KEYMAP.get(prefix)
        if km:
            return km
    return _MODULE_KEYMAP_FALLBACK.get(module, "Window")


def _get_keymap_for_op(op_id: str) -> str:
    """Return the single primary keymap an operator lives in (legacy/fallback)."""
    bundled = _BUNDLED_OP_KEYMAPS.get(op_id)
    if bundled:
        return bundled[0]
    if not _op_keymap_built:
        _build_op_keymap_cache()
    homes = _op_keymaps_all.get(op_id)
    if homes:
        return homes[0]
    if op_id in _op_keymap_cache:
        return _op_keymap_cache[op_id]
    return _module_fallback_keymap(op_id)


def _get_keymaps_for_op(op_id: str, op_item=None) -> list:
    """Return ALL keymaps an operator naturally lives in (no promotion).

    Used for auto-context resolution: an operator that lives in multiple
    keymaps (e.g. curves.select_all in 'Curves' and 'Sculpt Curves') should
    auto-select all of them and use multiple contexts.

    For prop-disambiguated ops (Call Menu/Panel/Pie, tool_set, ...), when the
    op instance carries the disambiguating property, homes are resolved from
    where THAT value is natively bound.
    """
    if not _op_keymap_built:
        _build_op_keymap_cache()
    bundled = _BUNDLED_OP_KEYMAPS.get(op_id)
    if bundled:
        return list(bundled)
    if isinstance(op_item, dict):
        try:
            from .conflict_detector import _PROP_DISAMBIGUATED_OPS as _PD
            key_prop = _PD.get(op_id)
        except Exception:
            key_prop = None
        if key_prop:
            props = op_item.get("props_data") or op_item.get("props") or {}
            if isinstance(props, str):
                import json as _j
                try:
                    props = _j.loads(props)
                except Exception:
                    props = {}
            val = str(props.get(key_prop, "") or "") if isinstance(props, dict) else ""
            if val:
                by_prop = _op_keymaps_by_prop.get((op_id, val))
                if by_prop:
                    return list(by_prop)
    homes = _op_keymaps_all.get(op_id)
    if homes:
        return list(homes)
    return [_module_fallback_keymap(op_id)]


# ---------------------------------------------------------------------------
# Space/region lookup table
# ---------------------------------------------------------------------------

_KEYMAP_SPACE_REGION = {
    "Window":                   ("EMPTY",              "WINDOW"),
    "Screen":                   ("EMPTY",              "WINDOW"),
    "3D View":                  ("VIEW_3D",            "WINDOW"),
    "Object Mode":              ("VIEW_3D",            "WINDOW"),
    "Mesh":                     ("VIEW_3D",            "WINDOW"),
    "Curve":                    ("VIEW_3D",            "WINDOW"),
    "Armature":                 ("VIEW_3D",            "WINDOW"),
    "Pose":                     ("VIEW_3D",            "WINDOW"),
    "Sculpt":                   ("VIEW_3D",            "WINDOW"),
    "Vertex Paint":             ("VIEW_3D",            "WINDOW"),
    "Weight Paint":             ("VIEW_3D",            "WINDOW"),
    "Image Paint":              ("VIEW_3D",            "WINDOW"),
    "Particle":                 ("VIEW_3D",            "WINDOW"),
    "Grease Pencil":            ("VIEW_3D",            "WINDOW"),
    "Curves":                   ("VIEW_3D",            "WINDOW"),
    "Lattice":                  ("VIEW_3D",            "WINDOW"),
    "Font":                     ("VIEW_3D",            "WINDOW"),
    "Metaball":                 ("VIEW_3D",            "WINDOW"),
    "Graph Editor":             ("GRAPH_EDITOR",       "WINDOW"),
    "Dopesheet":                ("DOPESHEET_EDITOR",   "WINDOW"),
    "NLA Editor":               ("NLA_EDITOR",         "WINDOW"),
    "Node Editor":              ("NODE_EDITOR",        "WINDOW"),
    "UV Editor":                ("IMAGE_EDITOR",       "WINDOW"),
    "Image":                    ("IMAGE_EDITOR",       "WINDOW"),
    "Outliner":                 ("OUTLINER",           "WINDOW"),
    "Sequencer":                ("SEQUENCE_EDITOR",    "WINDOW"),
    "Text":                     ("TEXT_EDITOR",        "WINDOW"),
    "Frames":                   ("EMPTY",              "WINDOW"),
    "File Browser Buttons":     ("FILE_BROWSER",       "WINDOW"),
    "Clip Dopesheet Editor":    ("CLIP_EDITOR",        "WINDOW"),
    "Clip Time Scrub":          ("CLIP_EDITOR",        "PREVIEW"),
}


def _keymap_space_region(keymap_name: str):
    return _KEYMAP_SPACE_REGION.get(keymap_name, ("EMPTY", "WINDOW"))


def _op_target_keymaps(op_item, op_id: str) -> list:
    """Keymaps an operator instance should register into.

    - explicit `contexts` list (multi-select) → one KMI per entry
    - else legacy single `context` → that one
    - else auto-resolve from Blender's keymaps
    """
    if isinstance(op_item, dict):
        ctxs = op_item.get("contexts") or []
        if ctxs:
            # de-dupe, preserve order
            seen = set()
            out = []
            for c in ctxs:
                if c and c not in seen:
                    seen.add(c)
                    out.append(c)
            if out:
                return out
        sc = op_item.get("context", "")
        if sc:
            return [sc]
    # Auto: register into ALL keymaps the operator naturally lives in.
    return _get_keymaps_for_op(op_id, op_item)


def _get_or_create_user_keymap(keymap_name: str):
    """Get or create a keymap in keyconfigs.user.

    Used for entry KMIs that need to coexist with user-layer disabled defaults.
    When we set kmi.active=False in keyconfigs.user, Blender treats that keymap
    as fully user-customized and dispatches only from the user keyconfig version,
    ignoring addon keyconfig additions. Registering there too solves this.
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user
    if kc is None:
        return None
    km = kc.keymaps.get(keymap_name)
    if km is not None:
        return km
    space_type = region_type = None
    for ref_kc in (wm.keyconfigs.default, wm.keyconfigs.active):
        if ref_kc is None:
            continue
        ref_km = ref_kc.keymaps.get(keymap_name)
        if ref_km is not None:
            space_type = ref_km.space_type
            region_type = ref_km.region_type
            break
    if space_type is None:
        # No keymap of this name in default OR active. Creating it anyway makes
        # a PHANTOM user keymap: it never dispatches (nothing routes to a keymap
        # Blender doesn't know), it shows up in Preferences > Keymap, and it is
        # the precondition for the WM_keymap_item_restore_to_default() null
        # deref (see _has_factory_original). Stale names in our own tables were
        # manufacturing these on every install. Refuse.
        print(f"[Keymapper] Skipping keymap '{keymap_name}' — not present in "
              f"this Blender version (no factory counterpart).")
        return None
    try:
        km = kc.keymaps.new(
            name=keymap_name,
            space_type=space_type,
            region_type=region_type,
        )
    except Exception as e:
        print(f"[Keymapper] Could not create user keymap '{keymap_name}': {e}")
        return None
    return km


# ---------------------------------------------------------------------------
# Entry snapshot for change detection
# ---------------------------------------------------------------------------

_entry_snapshots: dict = {}


def _entry_snapshot(entry: dict) -> tuple:
    import json
    return (
        entry.get("key", ""),
        entry.get("shift", False),
        entry.get("ctrl", False),
        entry.get("alt", False),
        entry.get("oskey", False),
        entry.get("key_modifier", ""),
        entry.get("event_type", "PRESS"),
        entry.get("operator_ids", "[]"),
        bool(entry.get("any", False)),
        bool(entry.get("repeat", False)),
        json.dumps(entry.get("extra_keybinds", []), sort_keys=True),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _find_default_kmis(ref: dict) -> list:
    """Find ALL writable keymap items matching a conflict ref.

    Returns a list of (km, kmi, layer_name) tuples. We search keyconfigs.active
    first (disabling there leaves no Restore arrow), then keyconfigs.user for
    bindings only materialized in the user layer. We never create keymaps or
    copy items.

    Returning ALL matches (not just the first) is essential: a single keymap can
    contain multiple KMIs for the same operator+key (e.g. duplicate animation
    bindings), and disabling only one leaves the conflict partially active.
    """
    import bpy
    wm = bpy.context.window_manager
    kc_active  = wm.keyconfigs.active
    kc_user    = wm.keyconfigs.user

    km_name    = ref.get("keymap_name", "")
    op_id      = ref.get("op_id", "")
    key        = ref.get("key", "")
    event_type = ref.get("event_type", "PRESS")
    shift      = bool(ref.get("shift", False))
    ctrl       = bool(ref.get("ctrl", False))
    alt        = bool(ref.get("alt", False))
    oskey      = bool(ref.get("oskey", False))

    def _km_in(kc):
        if kc is None:
            return None
        km = kc.keymaps.get(km_name)
        if km is None:
            kl = km_name.lower()
            for k in kc.keymaps:
                if k.name.lower() == kl:
                    return k
        return km

    results = []
    # Collect (keymap_name, id) pairs of all KMIs Keymapper itself registered, so
    # we never match our own entry KMI as a "default" to disable. CRITICAL: KMI
    # ids are only unique WITHIN a keymap, not globally — so we must qualify by
    # keymap name. A bare-id set wrongly excludes e.g. Object Mode's default
    # object.select_all (id=5) just because some other keymap has a Keymapper KMI
    # with id=5. That collision made entire keymaps' defaults un-disableable.
    # Our KMIs are addon-owned and always carry a NEGATIVE id in the user/active
    # layers; factory defaults (incl. materialized copies) are always POSITIVE.
    # So "don't disable our own" is a property of the live item — robust against
    # the id renumbering that a stored (km,id) set cannot survive.
    def _collect(km, layer):
        if km is None:
            return
        is_user = (layer == "user")
        for kmi in km.keymap_items:
            if kmi.idname != op_id:
                continue
            # Never disable our own KMIs. In active/default layers ours carry a
            # NEGATIVE id and nothing else does. In the USER layer, negative ids
            # also mark real user KMIs we DO want to disable — so there, skip
            # only items matching our registration records.
            if not is_user:
                if kmi.id < 0:
                    continue
            else:
                sig = (kmi.type, kmi.value, bool(kmi.shift), bool(kmi.ctrl),
                       bool(kmi.alt), bool(kmi.oskey))
                # Ours = registration-record (or previous-session leftover)
                # match AND ownership id. The record alone cannot tell OUR KMI
                # from the FACTORY twin it pins against (identical signature,
                # e.g. an entry bound exactly like the default it replaces):
                # skipping by record alone excluded the factory item too, so
                # other entries conflicting with that default never got a
                # user-layer match — no disable, and no claim handle, leaving
                # the default stuck disabled once the pinning entry released.
                _rec_match = (
                    any((km.name, kmi.idname, sig) in recs
                        for recs in _entry_kmi_keymaps.values())
                    or _is_our_previous_kmi(km.name, kmi.idname, sig))
                if _rec_match and _owned_id_ok(km.name, kmi):
                    continue
            if (kmi.type == key and
                    kmi.value == event_type and
                    bool(kmi.shift) == shift and bool(kmi.ctrl) == ctrl and
                    bool(kmi.alt) == alt and bool(kmi.oskey) == oskey):
                results.append((km, kmi, layer, False))

    # Search BOTH the user and active layers and disable the matching default in
    # each. A factory binding (e.g. plain-A select_all) may live only in the
    # active layer while the keymap ALSO exists in the user layer for dispatch.
    # If we disable only the active copy, Blender keeps dispatching from the user
    # layer and the shortcut still fires (the "A still selects all" bug).
    km_user = _km_in(kc_user)
    _collect(km_user, "user")
    if kc_active is not None and (kc_user is None or id(kc_active) != id(kc_user)):
        _collect(_km_in(kc_active), "active")
    # Addon-registered KMIs (e.g. Node Wrangler) live in the addon keyconfig.
    kc_addon = getattr(wm.keyconfigs, "addon", None)
    if kc_addon is not None:
        _collect(_km_in(kc_addon), "addon")

    # If nothing matched in user/active, the binding may live ONLY in the factory
    # (default) keyconfig — e.g. View2D's plain Wheel Up scroll_up. Disabling it
    # in the default layer doesn't suppress dispatch because the user layer
    # shadows it. So materialize a copy into the user keymap (Blender then
    # dispatches the user version) which the caller disables — exactly the state
    # Blender produces when you uncheck a factory binding in the keymap editor.
    if not results:
        # Materializing copies a binding that lives ONLY in the factory
        # `default` keyconfig so it can be disabled in the dispatching layer.
        # That only makes sense when `default` IS the dispatching config. With a
        # CUSTOM active config (BForArtists, Industry Compatible), the default
        # layer is dormant — its bindings never fire, so there is nothing to
        # disable, and a materialized copy is a pure phantom KMI.
        if not _active_is_default():
            return results
        # Never materialize a factory copy for a binding that ANY entry has
        # adopted — the adopted item already provides this binding, and a
        # materialized duplicate becomes a phantom KMI. Checking the adoption
        # records (not just live presence) is race-free: during a deferred
        # keyconfigs.update() on custom configs like BForArtists the live item's
        # id can momentarily change, but the adoption record persists.
        for _recs in _adopted_kmis.values():
            for (a_km, a_op, a_sig) in ((r[0], r[1], r[2]) for r in _recs):
                if (a_km == km_name and a_op == op_id
                        and a_sig == (key, event_type, shift, ctrl, alt, oskey)):
                    return results
        # Also skip if any live KMI with this exact binding already exists in
        # the user or active layer (ours, adopted, or genuine).
        def _binding_live_in(kc_check):
            if kc_check is None:
                return False
            k = _km_in(kc_check)
            if k is None:
                return False
            for it in k.keymap_items:
                if (it.idname == op_id and it.type == key
                        and it.value == event_type
                        and bool(it.shift) == shift and bool(it.ctrl) == ctrl
                        and bool(it.alt) == alt and bool(it.oskey) == oskey):
                    return True
            return False
        if _binding_live_in(kc_user) or _binding_live_in(kc_active):
            return results
        kc_default = getattr(wm.keyconfigs, "default", None)
        dkm = _km_in(kc_default) if kc_default is not None else None
        if dkm is not None:
            for kmi in dkm.keymap_items:
                if kmi.idname != op_id:
                    continue
                if (kmi.type == key and kmi.value == event_type and
                        bool(kmi.shift) == shift and bool(kmi.ctrl) == ctrl and
                        bool(kmi.alt) == alt and bool(kmi.oskey) == oskey):
                    ukm = _get_or_create_user_keymap(km_name)
                    if ukm is None:
                        break
                    try:
                        mat = ukm.keymap_items.new(
                            idname=op_id, type=key, value=event_type,
                            shift=kmi.shift, ctrl=kmi.ctrl, alt=kmi.alt,
                            oskey=kmi.oskey,
                            key_modifier=(kmi.key_modifier or "NONE"),
                        )
                        try:
                            mat.repeat = kmi.repeat
                        except Exception:
                            pass
                        try:
                            if kmi.any:
                                mat.any = True
                        except Exception:
                            pass
                        results.append((ukm, mat, "user", True))
                        print(f"[Keymapper] Materialized factory default into user: "
                              f"{op_id} in {km_name}")
                    except Exception as e:
                        print(f"[Keymapper] Could not materialize default '{op_id}': {e}")
                    break
    return results


def _find_keymap(layer: str, km_name: str):
    """Re-fetch a keymap object by name within a layer (user/addon/active)."""
    import bpy
    wm = bpy.context.window_manager
    if layer == "user":
        kc = wm.keyconfigs.user
    elif layer == "addon":
        kc = getattr(wm.keyconfigs, "addon", None)
    else:
        kc = wm.keyconfigs.active
    if kc is None:
        return None
    km = kc.keymaps.get(km_name)
    if km is None:
        kl = km_name.lower()
        for k in kc.keymaps:
            if k.name.lower() == kl:
                return k
    return km


def _refresh_keyconfigs() -> None:
    """Force Blender to rebuild keymaps after we toggle KMI active flags.

    Programmatic changes to kmi.active in keyconfigs.user/active don't take
    effect (or show in the keymap editor) until the key configuration is
    rebuilt. Without this, a disabled/restored default only "lands" after a
    manual Restore + entry toggle. keyconfigs.update() is Blender's API for
    applying these changes immediately.
    """
    try:
        bpy.context.window_manager.keyconfigs.update()
    except Exception as e:
        print(f"[Keymapper] keyconfigs.update() failed: {e}")


def _has_factory_original(km) -> bool:
    """Mirror of Blender's wm_keymap_preset(): is there a keymap with this
    name + space + region in the active preset, or failing that the default
    config? Matches Blender's own lookup so we can prove a factory original
    exists BEFORE calling preferences.keyitem_restore."""
    wm = bpy.context.window_manager
    for kc in (wm.keyconfigs.active, wm.keyconfigs.default):
        if kc is None:
            continue
        for k in kc.keymaps:
            if (k.name == km.name and k.space_type == km.space_type
                    and k.region_type == km.region_type):
                return True
    return False


def _keyitem_restore_in_layer(layer: str, km_name: str, item_id: int) -> None:
    """Revert a single keymap item to its factory state (clears the Restore
    arrow). Runs preferences.keyitem_restore under a Preferences-area context so
    its poll succeeds. Best-effort: callers wrap in try/except."""
    wm = bpy.context.window_manager
    if layer == "user":
        kc = wm.keyconfigs.user
    elif layer == "addon":
        # Was falling through to keyconfigs.active — a different keyconfig than
        # the id came from, so on an id collision this restored the WRONG item.
        kc = wm.keyconfigs.addon
    else:
        kc = wm.keyconfigs.active
    km = kc.keymaps.get(km_name) if kc else None
    if km is None:
        return
    # HARD GUARD (crash, not an exception). WM_keymap_item_restore_to_default()
    # resolves the factory original with wm_keymap_preset() and feeds the result
    # straight into WM_keymap_item_find_id() with NO null check; that function
    # then iterates keymap->items. A keymap present in neither the active preset
    # nor the default config makes it NULL and Blender dereferences it:
    # EXCEPTION_ACCESS_VIOLATION, which no try/except can catch. Reproduced on
    # Blender 5.2 (segfault) via exactly this bpy.ops call. With no factory
    # original the call could only ever have been a no-op, so bailing here
    # forfeits nothing.
    if not _has_factory_original(km):
        return
    target = None
    for window in wm.windows:
        scr = window.screen
        if scr is None:
            continue
        for area in scr.areas:
            if area.type == 'PREFERENCES':
                target = (window, area)
                break
        if target:
            break
    override = {"keymap": km}
    if target:
        win, area = target
        override["window"] = win
        override["area"] = area
    # Guard: keyitem_restore crashes internally (AttributeError on a None kmi)
    # if item_id no longer resolves — BFA reassigns ids across updates. Only
    # call when the id still maps to a live item in this keymap.
    if not any(it.id == item_id for it in km.keymap_items):
        return
    with bpy.context.temp_override(**override):
        bpy.ops.preferences.keyitem_restore(item_id=item_id)


_pending_binding_fixes = []  # (km_name, idname, type, value, shift, ctrl, alt, oskey, key_modifier)

# The throwaway modifier combo used to keep a freshly-created KMI distinct.
_DUMMY_CTRL = True
_DUMMY_ALT = True
_DUMMY_OSKEY = True
_DUMMY_KEYMOD = "SLASH"

_factory_km_names: set | None = None


def _is_factory_keymap(km_name: str) -> bool:
    """True if the keymap exists in Blender's factory (default) keyconfig.
    In factory keymaps our KMIs get NEGATIVE ids; in user-created keymaps
    (e.g. 'Asset Browser Main') they get POSITIVE ids."""
    global _factory_km_names
    if _factory_km_names is None:
        try:
            kc = bpy.context.window_manager.keyconfigs.default
            _factory_km_names = {km.name for km in kc.keymaps} if kc else set()
        except Exception:
            return True  # safest assumption
        if not _factory_km_names:
            _factory_km_names = None
            return True
    return km_name in _factory_km_names


def _owned_id_ok(km_name: str, item) -> bool:
    """Negative id marks our items in factory keymaps. In user-CREATED keymaps
    (e.g. 'Asset Browser Main') our items get positive ids, so the id sign is
    meaningless there — the caller's spec/signature match decides ownership."""
    return item.id < 0 or not _is_factory_keymap(km_name)


def _apply_pending_binding_fixes():
    """Strip the throwaway modifiers off freshly-created KMIs, one tick later.

    Creating a KMI identical to an existing default collapses it; creating with
    extra modifiers avoids that, but stripping them back in the SAME cycle
    re-collapses. Doing it on a deferred tick (after the keyconfig settles) is
    safe. We locate the KMI by its unique dummy binding (NOT by id, which can be
    reassigned by keyconfigs.update())."""
    global _pending_binding_fixes
    fixes = list(_pending_binding_fixes)
    _pending_binding_fixes = []
    if not fixes:
        return None
    try:
        kc = bpy.context.window_manager.keyconfigs.user
    except Exception:
        kc = None
    if kc is not None:
        for (km_name, idname, type_, value, sh, ct, al, ok, kmod) in fixes:
            km = kc.keymaps.get(km_name)
            if not km:
                continue
            found = False
            for it in km.keymap_items:
                if (it.idname == idname and it.type == type_ and it.value == value
                        and bool(it.ctrl) == _DUMMY_CTRL
                        and bool(it.alt) == _DUMMY_ALT
                        and bool(it.oskey) == _DUMMY_OSKEY
                        and (it.key_modifier or "") == _DUMMY_KEYMOD
                        and bool(it.shift) == bool(sh)):
                    try:
                        it.shift = sh
                        it.ctrl = ct
                        it.alt = al
                        it.oskey = ok
                        it.key_modifier = kmod or "NONE"
                        found = True
                    except Exception as e:
                        print(f"[Keymapper] Deferred binding-fix error for '{idname}' in '{km_name}': {e}")
                    break
            if found:
                print(f"[Keymapper] Deferred binding-fix applied: '{idname}' in '{km_name}' ({type_})")
            else:
                print(f"[Keymapper] Deferred binding-fix: dummy KMI not found for '{idname}' in '{km_name}'")
        try:
            bpy.context.window_manager.keyconfigs.update()
        except Exception:
            pass
    try:
        _heal_collapsed_entry_kmis()
    except Exception:
        pass
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()
    except Exception:
        pass
    return None


def _schedule_binding_fix(km_name, idname, type, value, shift, ctrl, alt, oskey, key_modifier):
    _pending_binding_fixes.append(
        (km_name, idname, type, value, shift, ctrl, alt, oskey, key_modifier)
    )
    try:
        if not bpy.app.timers.is_registered(_apply_pending_binding_fixes):
            bpy.app.timers.register(_apply_pending_binding_fixes, first_interval=0.01)
    except Exception:
        _apply_pending_binding_fixes()


def _new_kmi_no_collapse(km, *, idname, type, value, shift, ctrl, alt,
                         oskey, key_modifier="", repeat=False):
    """Create a KMI without it collapsing onto an identical existing one.

    Blender merges a freshly-created KMI into an existing item in the same
    keymap with the same operator + key + modifiers. Binding an entry to a key
    a default already uses would silently fold our item onto that default. We
    create with extra throwaway modifiers (distinct, so no collapse), then strip
    them to the intended binding on a deferred tick — stripping in the same
    cycle re-collapses, but a later pass (after the keyconfig settles) is safe.
    """
    key_modifier = key_modifier or "NONE"  # "" is an invalid enum value
    def _ref_keymaps():
        # Blender collapses a new user-layer KMI onto an identical one in the
        # resolved keymap — which includes factory/addon defaults that aren't
        # materialised into keyconfigs.user. So we must look beyond `km`.
        kms = [km]
        try:
            wm = bpy.context.window_manager
            for kc in (wm.keyconfigs.default, getattr(wm.keyconfigs, "addon", None)):
                if kc is None:
                    continue
                rkm = kc.keymaps.get(km.name)
                if rkm is not None and rkm is not km:
                    kms.append(rkm)
        except Exception:
            pass
        return kms

    def _identical_exists():
        for rkm in _ref_keymaps():
            for it in rkm.keymap_items:
                if it.idname == idname and it.type == type:
                    if (it.value == value
                            and bool(it.shift) == bool(shift)
                            and bool(it.ctrl) == bool(ctrl)
                            and bool(it.alt) == bool(alt)
                            and bool(it.oskey) == bool(oskey)
                            and (it.key_modifier or "") == (key_modifier or "")):
                        return True
        return False

    # Evaluated BEFORE our own item exists, so a match here is a PRE-EXISTING
    # byte-identical KMI — the only situation the property pin below defends
    # against. (Called after creation it would always match our own item.)
    # Adoption has already claimed the user/addon cases upstream, so what
    # reaches here identical is the factory twin.
    needs_pin = _identical_exists()

    kmi = km.keymap_items.new(
        idname=idname, type=type, value=value,
        shift=shift, ctrl=ctrl, alt=alt, oskey=oskey,
        key_modifier=key_modifier, repeat=repeat,
    )
    if _identical_exists() and kmi.id >= 0 and _is_factory_keymap(km.name):
        # new() merged onto an existing item (legacy behavior) — leave that
        # item untouched and create ours via the dummy-modifier dance.
        kmi = km.keymap_items.new(
            idname=idname, type=type, value=value, shift=shift,
            ctrl=_DUMMY_CTRL, alt=_DUMMY_ALT, oskey=_DUMMY_OSKEY,
            key_modifier=_DUMMY_KEYMOD,
        )
        kmi.repeat = repeat
        _schedule_binding_fix(
            km.name, idname, type, value, shift, ctrl, alt, oskey, key_modifier
        )
    # Pin one operator property (explicitly set to its current/default value)
    # so our item is never field-identical to a factory KMI: identical twins
    # get silently merged away by Blender's user-keymap diff rebuilds.
    # ONLY when such a twin actually exists — pinning unconditionally forces a
    # property to be set on every KMI we make, which makes properties the user
    # deliberately cleared come back on the next activation (e.g. clearing
    # Section on screen.userpref_show to get "last used panel" behaviour).
    try:
        from .conflict_detector import is_operator_registered as _op_reg
        if needs_pin and kmi.properties and _op_reg(kmi.idname):
            for p in kmi.properties.bl_rna.properties:
                if p.identifier == "rna_type" or p.is_readonly:
                    continue
                setattr(kmi.properties, p.identifier,
                        getattr(kmi.properties, p.identifier))
                break
    except Exception:
        pass
    return kmi


def _active_is_default() -> bool:
    """True when the active keyconfig IS Blender's factory default (stock
    Blender). False for custom active configs like BForArtists, which load
    their whole keymap as the active config with positive-id items that behave
    like user KMIs (same-layer, so a duplicate of ours would merge)."""
    try:
        wm = bpy.context.window_manager
        return wm.keyconfigs.active == wm.keyconfigs.default
    except Exception:
        return True


def _kmi_props_identical(kmi, op_props, op_props_data) -> bool:
    """True when the live KMI's operator properties are identical to what the
    entry would set: every property must equal either the entry's specified
    value or, if unspecified by the entry, the property's default. A KMI with a
    deviating property (e.g. BFA's reverse-play with reverse=True) is NOT
    byte-identical and must not be adopted."""
    try:
        # GUARD: a candidate KMI whose operator was unregistered (disabled
        # addon) has a dangling properties RNA pointer — touching .bl_rna
        # segfaults, uncatchably. Such a KMI is never adoptable anyway.
        from .conflict_detector import is_operator_registered as _op_reg2
        if not _op_reg2(kmi.idname):
            return False
        props = kmi.properties
        if props is None:
            return not op_props and not op_props_data
        desired = {}
        if op_props:
            desired.update({str(k): str(v) for k, v in op_props.items()})
        if op_props_data:
            desired.update({str(k): str(v) for k, v in op_props_data.items()})
        for prop in props.bl_rna.properties:
            pid = prop.identifier
            if pid == "rna_type":
                continue
            try:
                cur = getattr(props, pid)
            except Exception:
                return False
            if getattr(prop, "is_array", False) or prop.type in ('COLLECTION', 'POINTER'):
                # Arrays/collections: only compare when explicitly set — a set
                # non-default complex prop makes it non-identical.
                if props.is_property_set(pid) and pid not in desired:
                    return False
                continue
            if pid in desired:
                if str(cur) != desired[pid]:
                    return False
            else:
                # Only explicitly-SET properties can deviate; an unset property
                # sits at its default by definition. Comparing unset values
                # against prop.default false-negatives on dynamic enums (e.g.
                # wm.open_mainfile.sort_method reports default='' but reads
                # 'DEFAULT'), which blocked reuse/adoption for such operators.
                if not props.is_property_set(pid):
                    continue
                try:
                    default = prop.default
                except Exception:
                    default = None
                if default is None or cur != default:
                    return False
        return True
    except Exception:
        return False


# KMIs Keymapper created in a PREVIOUS session, restored from prefs at startup.
# Blender persists the user keyconfig, so on launch our own KMIs are already in
# it — and they're indistinguishable from KMIs the user made by hand (both get
# negative ids in factory keymaps). Without this record, every entry would
# "adopt" its own leftover and wrongly claim to be identical to a default.
# Entries are (km_name, idname, sig); consumed (and emptied) as activation
# re-registers each KMI this session.
_prev_session_kmis: set = set()


def _invalidate_owned_specs():
    """Kept for call-site compatibility; the persisted registry needs no cache."""
    return


def load_owned_kmi_registry():
    """Populate _prev_session_kmis from the saved registry. Called once at
    startup BEFORE any activation."""
    global _prev_session_kmis
    _prev_session_kmis = set()
    try:
        import json
        from .preferences import get_prefs
        raw = get_prefs().keymapper_owned_kmis_store or ""
        if not raw:
            return
        for km_name, idname, sig in json.loads(raw):
            _prev_session_kmis.add((km_name, idname, tuple(sig)))
        print(f"[Keymapper] Loaded {len(_prev_session_kmis)} previously-created "
              f"KMI records (adoption self-exclusion).")
    except Exception as e:
        print(f"[Keymapper] Could not load owned-KMI registry: {e}")


def save_owned_kmi_registry():
    """Persist the KMIs we CREATED this session so the next launch can tell them
    apart from the user's own bindings.

    ADOPTED KMIs are deliberately excluded: they are pre-existing bindings we
    merely took ownership of, so on the next launch they must be adoptable again
    (otherwise e.g. BFA's Shift+Space play would stop being recognised).
    """
    try:
        import json
        from .preferences import get_prefs
        adopted = set()
        for recs in _adopted_kmis.values():
            for (km_name, op_id, sig, _orig) in recs:
                adopted.add((km_name, op_id, tuple(sig)))
        recs = []
        for specs in _entry_kmi_keymaps.values():
            for (km_name, idname, sig) in specs:
                if (km_name, idname, tuple(sig)) in adopted:
                    continue  # adopted, not created — must stay adoptable
                recs.append([km_name, idname, list(sig)])
        get_prefs().keymapper_owned_kmis_store = json.dumps(recs)
    except Exception as e:
        print(f"[Keymapper] Could not save owned-KMI registry: {e}")


def _is_our_previous_kmi(km_name, idname, sig) -> bool:
    """True if this exact KMI was created by Keymapper in a previous session."""
    return (km_name, idname, sig) in _prev_session_kmis


# Claims made on previous-session leftovers during the CURRENT activation
# cycle, keyed (km_name, op_id, sig) -> count. Identity comparison against
# stored KMI wrappers is unreliable (keyconfigs.update() reallocates items and
# stale pointers compare true nondeterministically), so instead each reuse
# skips the first N matching candidates — identical items are interchangeable,
# making the count exact.
_leftover_claims: dict = {}


def _reset_leftover_claims():
    _leftover_claims.clear()


def _find_our_leftover(km, op_id, key, value, shift, ctrl, alt, oskey,
                       op_props=None, op_props_data=None):
    """Locate OUR OWN KMI from a previous session (persisted in the saved user
    keyconfig) matching this binding, so activation can REUSE it instead of
    creating a duplicate next to it.

    The registry record is NOT consumed on a hit: it is keyed by (keymap, op,
    signature) WITHOUT props, and several entries can share that key with
    different operator properties (e.g. two wm.context_toggle bindings on Y).

    Multiple entries CAN legitimately share the exact same spec; each reuse
    claims the next unclaimed candidate via _leftover_claims (see above for why
    identity/pointer checks are not usable here).

    If a leftover matches the binding but its operator properties no longer
    match the entry (edited between sessions), it is removed so a fresh KMI
    with correct props gets created."""
    sig = (key, value, bool(shift), bool(ctrl), bool(alt), bool(oskey))
    if not _is_our_previous_kmi(km.name, op_id, sig):
        return None
    ckey = (km.name, op_id, sig)
    skip = _leftover_claims.get(ckey, 0)
    seen = 0
    for it in list(km.keymap_items):
        cur = (it.type, it.value, bool(it.shift), bool(it.ctrl),
               bool(it.alt), bool(it.oskey))
        if it.idname != op_id or cur != sig:
            continue
        if not _owned_id_ok(km.name, it):
            continue
        if not _kmi_props_identical(it, op_props, op_props_data):
            continue  # someone else's variant of this spec — leave it alone
        if seen < skip:
            seen += 1
            continue
        _leftover_claims[ckey] = skip + 1
        return it
    return None


def _find_existing_user_kmi(km, op_id, key, value, shift, ctrl, alt, oskey,
                            op_props=None, op_props_data=None):
    """Return a pre-existing KMI byte-identical to what we'd create, if one
    exists and we can safely ADOPT it (take ownership instead of creating a
    colliding duplicate).

    Adoptable cases:
      - A genuine user/addon KMI (negative id in a factory keymap, or any id in
        a user-created keymap).
      - A positive-id item that belongs to a CUSTOM active keyconfig (e.g.
        BForArtists), because our duplicate would merge onto it in the same
        layer — adoption is the only thing that works.

    NOT adoptable:
      - A pure factory `default` binding in stock Blender (positive id, active
        config == default). Those get their own controllable KMI via the
        property-pin path, so we can disable the factory copy independently.
    """
    factory_km = _is_factory_keymap(km.name)
    active_is_default = _active_is_default()
    for it in km.keymap_items:
        if it.idname != op_id:
            continue
        if (it.type == key and it.value == value
                and bool(it.shift) == bool(shift) and bool(it.ctrl) == bool(ctrl)
                and bool(it.alt) == bool(alt) and bool(it.oskey) == bool(oskey)):
            if factory_km and it.id >= 0 and active_is_default:
                # Pure stock-Blender factory binding — use the pin path instead.
                continue
            if not _kmi_props_identical(it, op_props, op_props_data):
                # Same binding but different operator properties (e.g. BFA's
                # reverse-play). NOT identical — disable + create instead.
                continue
            sig = (it.type, it.value, bool(it.shift), bool(it.ctrl),
                   bool(it.alt), bool(it.oskey))
            rec = (km.name, it.idname, sig)
            if any(rec in recs for recs in _entry_kmi_keymaps.values()):
                continue  # already ours (registered this session)
            if _is_our_previous_kmi(km.name, it.idname, sig):
                # Our own KMI from the LAST session, persisted in the saved user
                # keyconfig. Not a pre-existing default — don't adopt it (it gets
                # re-registered as ours by the normal creation path below).
                continue
            return it
    return None



def _gated_conflict_refs(entry: dict) -> tuple[list, list]:
    """(keybind_refs, shortcut_refs) honoring the master override toggles.

    The "Override Shortcut/Keybind Conflicts" prefs gate the OVERRIDE only:
    with a master off, that class's conflicts stay detected and listed (with
    a warning in the UI) but its default KMIs are NOT disabled. EVERY caller
    that feeds refs into _disable_default_kmis must go through this helper —
    the deferred reapply pass previously bypassed the gate and re-disabled
    everything moments after activation.
    """
    keybind_refs = entry.get("keybind_conflicts_external", []) or []
    shortcut_refs = entry.get("shortcut_conflicts_external", []) or []
    try:
        from .preferences import get_prefs
        p = get_prefs()
        if not bool(getattr(p, "find_shortcut_conflicts", True)):
            shortcut_refs = []
        if not bool(getattr(p, "find_keybind_conflicts", True)):
            keybind_refs = []
    except Exception:
        pass
    return keybind_refs, shortcut_refs


def _disable_default_kmis(entry_id: str, kmi_refs: list) -> set:
    """Disable default KMIs and store exact item handles for later restore.

    For each conflict ref we find ALL matching KMIs and disable each, recording
    a stable (layer, keymap_name, kmi.id) handle. Restore toggles those exact
    items by id — no property re-matching, so we never toggle the wrong item or
    miss duplicates.

    Returns the set of keymap names where disables landed in keyconfigs.user, so
    callers can register their own KMI in the user layer where it dispatches.

    Refs the user manually re-enabled (user_reenabled) are skipped.
    """
    wm = bpy.context.window_manager
    kc_user = wm.keyconfigs.user
    user_disabled_keymaps: set = set()
    existing = _disabled_defaults.get(entry_id, [])
    # existing entries are (layer, km_name, kmi_id, ref) tuples.
    #
    # Dedupe on (layer, keymap, kmi_id). The layer MUST stay in the key: a
    # keymap can resolve to a different physical KMI per layer, and dropping it
    # collapsed distinct defaults into one handle — so one KMI got restored
    # repeatedly while others were never covered at all, leaving hundreds
    # disabled after a Restore. (The double-restore problem this was meant to
    # solve is handled properly by restoring the handle's EXACT kmi_id instead
    # of the first signature match.)
    seen_handles = {(h[0], h[1], h[2]) for h in existing}
    newly = []
    for ref in kmi_refs:
        if ref.get("user_reenabled", False):
            continue
        # Never disable a binding some entry has ADOPTED — that KMI *is* the
        # entry's own binding now. Guards every caller (incl. the deferred
        # reapply pass, which previously re-disabled adopted BFA bindings).
        _ref_sig = (ref.get("key", ""), ref.get("event_type", "PRESS"),
                    bool(ref.get("shift")), bool(ref.get("ctrl")),
                    bool(ref.get("alt")), bool(ref.get("oskey")))
        _ref_kmn = ref.get("keymap_name", "")
        _ref_op = ref.get("op_id", "")
        _is_adopted = any(
            a_km == _ref_kmn and a_op == _ref_op and a_sig == _ref_sig
            for recs in _adopted_kmis.values()
            for (a_km, a_op, a_sig, _o) in recs)
        if _is_adopted:
            continue
        matches = _find_default_kmis(ref)
        for km, kmi, layer, materialized in matches:
            try:
                kmi_id = kmi.id
            except Exception:
                continue
            # NEVER disable one of OUR OWN KMIs. A ref can match our own item
            # because the entry's binding is IDENTICAL to the stock default it
            # replaces (Undo Ctrl+Z, Redo, view2d scroll...): the stock KMI and
            # ours share op + signature, so _find_default_kmis returns BOTH.
            #
            # Ours is either (a) registered this session, or (b) a leftover from
            # the previous session that Blender persisted in the user keyconfig
            # and that this entry is about to re-adopt. Case (b) is the restart
            # bug: the disable pass runs BEFORE the entry re-registers its
            # leftover, so without this check we record a disable handle on our
            # own KMI and the deferred fast replay switches the shortcut off —
            # leaving BOTH the stock KMI and ours disabled (dead shortcut, fixed
            # only by a Re-scan). Whether it triggers depends on pass ordering,
            # which is why it looked intermittent.
            _own_sig = (kmi.type, kmi.value, bool(kmi.shift), bool(kmi.ctrl),
                        bool(kmi.alt), bool(kmi.oskey))
            _rec = (km.name, kmi.idname, _own_sig)
            _is_ours = (
                any(_rec in recs for recs in _entry_kmi_keymaps.values())
                or _is_our_previous_kmi(km.name, kmi.idname, _own_sig)
            )
            if _is_ours and _owned_id_ok(km.name, kmi):
                continue
            handle = (layer, km.name, kmi_id)
            # Decide where our own entry KMI must live. If the disable landed in
            # the user layer, register there. But also: if the disable landed in
            # 'active' yet the same keymap ALSO exists in keyconfigs.user, the
            # user layer shadows active for dispatch — so we must still register
            # our KMI in user, otherwise it goes to the addon layer and silently
            # fails to dispatch (the Ctrl-A-default collision bug: Font, Text,
            # Console, Preview, where the factory binding already matched the
            # entry's key and was only found in the active layer).
            if layer == "user":
                user_disabled_keymaps.add(km.name)
            elif kc_user is not None and kc_user.keymaps.get(km.name) is not None:
                user_disabled_keymaps.add(km.name)
            if kmi.active:
                try:
                    kmi.active = False
                    print(f"[Keymapper] Disabled default: {ref.get('op_id')} in {km.name} ({layer})")
                except Exception as e:
                    print(f"[Keymapper] Could not disable default KMI: {e}")
                    continue
            if handle not in seen_handles:
                seen_handles.add(handle)
                newly.append((layer, km.name, kmi_id, ref, materialized))
    _disabled_defaults[entry_id] = existing + newly
    return user_disabled_keymaps


def _restore_default_kmis(entry_id: str, releasing: set | None = None,
                          preserve_own_twins: bool = False) -> None:
    """Re-enable the defaults this entry disabled.

    Resolution is ROBUST: we match each disabled default by the conflict ref's
    signature, EXCLUDING the entry's own KMIs (whose ids are stable). We never
    trust a stored default id — a materialized factory copy's id can shift across
    keyconfigs.update(), so an id lookup could grab the wrong item (our own KMI
    or the factory) and toggle/remove it by mistake.

    Materialized factory copies are simply re-enabled (left alive), becoming the
    active factory representative — so deleting/disabling an entry never deletes
    a factory binding. The copy is re-disabled by _disable_default_kmis when the
    entry is re-activated.
    """
    handles = _disabled_defaults.pop(entry_id, [])
    if not handles:
        return
    # The entry's own binding specs (op, sig) — used to gate the identical-twin
    # removal below to bindings the entry actually owns.
    _own_specs = set()
    try:
        from . import persistence as _pers
        _ent = _pers.get_entry_by_id(entry_id)
        if _ent:
            _own_specs = _entry_binding_specs(_ent)
    except Exception:
        pass
    if not _own_specs:
        _own_specs = set(_entry_kmi_specs.get(entry_id) or [])
    for handle in handles:
        layer, km_name, kmi_id, ref = handle[0], handle[1], handle[2], handle[3]
        op_id = ref.get("op_id", "")
        key   = ref.get("key", "")
        val   = ref.get("event_type", "PRESS")
        sh = bool(ref.get("shift", False)); ct = bool(ref.get("ctrl", False))
        al = bool(ref.get("alt", False));   ok = bool(ref.get("oskey", False))
        km = _find_keymap(layer, km_name)
        if km is None and layer not in ("user", "addon"):
            km = _find_keymap("user", km_name)
        if km is None:
            continue
        is_addon_layer = (layer == "addon")
        is_user_layer = (layer == "user")
        # Consensus check: if any OTHER entry still holds a claim on this same
        # default (same keymap + ref signature), leave it disabled. The default
        # is only re-enabled when the LAST claimant releases it. This prevents
        # disabling/deleting/editing one entry from re-enabling a default that
        # another enabled entry still conflicts with (shared shortcut/keybind
        # overrides). Our own claims were popped above, so we never self-block.
        claimant = None
        for other_id, other_handles in _disabled_defaults.items():
            if other_id == entry_id:
                continue
            # `releasing` = entries being restored in the SAME batch (Restore
            # KMIs, master-switch-off). They're all giving up their claims, so
            # a claim held by one of them must not block a default here — the
            # restore loop pops handles one entry at a time, so an entry
            # processed early would otherwise be blocked by entries not yet
            # processed, and nothing ever goes back to re-enable it once they
            # are. That left e.g. view2d.scroll_up dead after a Restore.
            if releasing and other_id in releasing:
                continue
            for oh in other_handles:
                oref = oh[3]
                if (oh[0] == layer and oh[1] == km_name
                        and oref.get("op_id", "") == op_id
                        and oref.get("key", "") == key
                        and oref.get("event_type", "PRESS") == val
                        and bool(oref.get("shift")) == sh and bool(oref.get("ctrl")) == ct
                        and bool(oref.get("alt")) == al and bool(oref.get("oskey")) == ok):
                    claimant = other_id
                    break
            if claimant:
                break
        if claimant:
            print(f"[Keymapper] Kept disabled (claimed by another entry): {op_id} in {km_name}")
            continue
        # Collect every matching default copy. A default we disabled is always a
        # factory/materialized copy with a POSITIVE id; our own KMIs are addon-
        # owned with NEGATIVE ids and must never be matched here. The first match
        # becomes the restored default (re-enabled); extras are leftover
        # materialized copies from prior cycles and are removed so duplicates
        # don't accumulate.
        matches = []
        for it in km.keymap_items:
            if not is_user_layer and not is_addon_layer:
                if it.id < 0:
                    continue  # addon-owned (our KMI); never touch
            elif is_user_layer:
                sig = (it.type, it.value, bool(it.shift), bool(it.ctrl),
                       bool(it.alt), bool(it.oskey))
                # Ours = ownership id AND (registration record match OR a
                # previous-session record). The id check matters for identical
                # bindings: the entry's own KMI and the factory twin share the
                # exact signature, and excluding by signature alone also
                # excluded the factory item — leaving it permanently disabled
                # (e.g. FIX_Delete's DEL defaults after disable / keyconfig
                # switch). The previous-session record matters on restart: the
                # disable pass runs BEFORE this entry re-registers its persisted
                # leftover, and without it a disable handle gets recorded on our
                # own KMI — the deferred fast replay then re-disables it after
                # activation re-enabled it (entry silently dead, e.g. 'Open').
                if _owned_id_ok(km.name, it) and (
                        any((km.name, it.idname, sig) in recs
                            for recs in _entry_kmi_keymaps.values())
                        or _is_our_previous_kmi(km.name, it.idname, sig)):
                    continue  # our own KMI (registered or persisted leftover)
            if (it.idname == op_id and it.type == key and it.value == val
                    and bool(it.shift) == sh and bool(it.ctrl) == ct
                    and bool(it.alt) == al and bool(it.oskey) == ok):
                matches.append(it)
        if not matches:
            continue
        # Phantom cleanup: with a CUSTOM active config, a previously-
        # materialized factory copy (saved by an older version/session) has no
        # dispatching factory source — the binding doesn't exist in the active
        # config. Remove it entirely instead of re-enabling a dead duplicate.
        if (not is_user_layer and not is_addon_layer
                and not _active_is_default()):
            kc_act = bpy.context.window_manager.keyconfigs.active
            act_km = kc_act.keymaps.get(km_name) if kc_act else None
            in_active = False
            if act_km is not None:
                for it in act_km.keymap_items:
                    if (it.idname == op_id and it.type == key
                            and it.value == val and bool(it.shift) == sh
                            and bool(it.ctrl) == ct and bool(it.alt) == al
                            and bool(it.oskey) == ok):
                        in_active = True
                        break
            if not in_active:
                for it in matches:
                    try:
                        km.keymap_items.remove(it)
                        print(f"[Keymapper] Removed stale materialized copy: "
                              f"{op_id} in {km_name}")
                    except Exception:
                        pass
                continue
        # Prefer the EXACT item this handle was recorded against (kmi_id). Several
        # distinct defaults can share a keymap + op + signature and differ only in
        # their PROPERTIES — view3d.view_axis is bound four times on Alt+MMB
        # (TOP/BOTTOM/LEFT/RIGHT). Taking matches[0] re-enabled one and treated
        # the other three as stale duplicates, so they stayed dead.
        target = next((it for it in matches if it.id == kmi_id), matches[0])
        try:
            target.active = True
            orig_repeat = bool(ref.get("repeat", False))
            if bool(target.repeat) != orig_repeat:
                try:
                    target.repeat = orig_repeat
                except Exception:
                    pass
            print(f"[Keymapper] Restored default: {op_id} in {km_name} ({layer})")
        except Exception as e:
            print(f"[Keymapper] Could not restore default KMI: {e}")
        # If one of OUR OWN KMIs (negative id) carries the identical binding in
        # this keymap, it IS the user-layer diff that keeps the factory item
        # suppressed — Blender won't let the factory default fire while our
        # identical override exists, even disabled. Remove ours so the restored
        # factory default actually surfaces (re-created on the next activate).
        # ONLY when the ref binding is the ENTRY'S OWN binding (op + sig match
        # one of its binding specs): otherwise a negative-id identical item is a
        # THIRD-PARTY user-layer KMI we merely disabled (e.g. an addon writing
        # directly to the user keymap) — deleting it would destroy a real
        # binding we don't own.
        # preserve_own_twins: the caller keeps the entry REGISTERED (form-
        # confirm's stale-conflict refresh) — deleting our identical KMI here
        # would kill the live shortcut with nothing re-creating it. Only the
        # deactivate/delete flows (which release the entry) may remove twins.
        _ref_is_own = (not preserve_own_twins
                       and (op_id, (key, val, sh, ct, al, ok)) in _own_specs)
        if not is_user_layer and not is_addon_layer:
            _kill_km = _find_keymap("user", km_name) or km
        else:
            _kill_km = km
        if _ref_is_own and _kill_km is not None:
            _removed_twin = False
            for it in list(_kill_km.keymap_items):
                if (it.id < 0 and it.idname == op_id and it.type == key
                        and it.value == val and bool(it.shift) == sh
                        and bool(it.ctrl) == ct and bool(it.alt) == al
                        and bool(it.oskey) == ok):
                    try:
                        _kill_km.keymap_items.remove(it)
                        _removed_twin = True
                    except Exception:
                        pass
            # After removing our identical override, clear the factory item's
            # user-diff so it re-enables cleanly (active=True alone may be
            # re-suppressed by the lingering diff on the next update()).
            if _removed_twin:
                try:
                    _keyitem_restore_in_layer(layer, km.name, target.id)
                    target.active = True
                except Exception:
                    pass
        # Clear the "user-modified" Restore arrow for factory-layer items only.
        if not is_user_layer and not is_addon_layer:
            # BUT: if one of OUR own KMIs (negative id) with the identical
            # binding still exists in this keymap, keyitem_restore can mis-revert
            # the factory twin back to a disabled state (the diff still sees our
            # override). In that case just leave it active — the explicit
            # active=True above already restored it correctly.
            our_twin_present = any(
                it.id < 0 and it.idname == op_id and it.type == key
                and it.value == val and bool(it.shift) == sh
                and bool(it.ctrl) == ct and bool(it.alt) == al
                and bool(it.oskey) == ok
                for it in km.keymap_items)
            if not our_twin_present:
                try:
                    _keyitem_restore_in_layer(layer, km.name, target.id)
                except Exception:
                    pass
            # NOTE: the old "remove extra materialized factory copies" loop
            # deleted matches[1:] here. It only ever ran for the active/default
            # layer — where materialized copies NEVER live (materialize targets
            # the user layer exclusively) — so every "extra" it removed was a
            # genuine factory item. With signature-sharing prop-variant
            # defaults (view3d.view_axis Alt+MMB x4) it deleted 3 of the 4
            # variants from keyconfigs.default. Removed entirely; each variant
            # has its own handle and is restored by its exact kmi_id.



def _set_legacy_props(kmi, op_props: dict):
    """Apply legacy STRING props onto a KMI, coerced by the RNA prop type.

    Preset/catalog data stores props as strings ({"confirm": "False"}); a raw
    setattr of "False" onto a BOOLEAN either coerces truthy or throws - either
    way the operator default is not overridden (the object.delete confirm
    popup bug). props_data (typed) does not need this.
    """
    if not op_props or not kmi.properties:
        return
    try:
        rna_props = kmi.properties.bl_rna.properties
    except Exception:
        rna_props = None
    for prop_key, prop_val in op_props.items():
        try:
            val = prop_val
            p = rna_props.get(prop_key) if rna_props else None
            if p is not None and isinstance(prop_val, str):
                if p.type == "BOOLEAN":
                    val = prop_val in ("True", "true", "1")
                elif p.type == "INT":
                    val = int(float(prop_val))
                elif p.type == "FLOAT":
                    val = float(prop_val)
            setattr(kmi.properties, prop_key, val)
        except Exception:
            pass

def activate_entry(entry: dict):
    """Create KMIs for all operators in this entry."""
    _invalidate_owned_specs()
    entry_id = entry.get("entry_id")
    if not entry_id:
        return

    _remove_kmis(entry_id, entry)
    # Restore any defaults this entry previously disabled, so removing an
    # operator (or a conflict no longer applying) re-enables its defaults
    # instead of leaving them stuck off. The current conflict set is
    # re-disabled below.
    _restore_default_kmis(entry_id)

    # Master switch OFF: never register KMIs or disable defaults. Record the
    # snapshot so a later edit still diffs correctly, then stop. (Covers the
    # form edit/create, duplicate, and reconcile-promote paths, which all call
    # activate_entry directly and previously bypassed the switch.)
    try:
        from .preferences import get_prefs
        if not get_prefs().global_enabled:
            _entry_snapshots[entry_id] = _entry_snapshot(entry)
            _refresh_keyconfigs()
            return
    except Exception:
        pass

    # Inert duplicate: 100% identical to an earlier entry. It must register no
    # KMIs (its KMIs would be indistinguishable from the twin's, making a later
    # delete ambiguous). We already removed/restored above, so it's now clean.
    try:
        from . import conflict_detector
        if conflict_detector.is_inert_duplicate(entry):
            _refresh_keyconfigs()
            return
    except Exception:
        pass

    # Button-only entry (use_keybind False): no KMIs, no default-disabling —
    # the entry only exists as UI button(s) (see buttons.py). The removal +
    # restore above already cleaned up anything from when it WAS a keybind
    # entry, so just stop here.
    if not entry.get("use_keybind", True):
        _refresh_keyconfigs()
        return

    # Entry binding fields (needed both for the conflict filter below and for
    # KMI creation further down).
    key        = entry.get("key", "")
    shift      = entry.get("shift", False)
    ctrl       = entry.get("ctrl", False)
    alt        = entry.get("alt", False)
    oskey      = entry.get("oskey", False)
    event_type = entry.get("event_type", "PRESS")
    try:
        op_list = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        op_list = []

    # Disable conflicting defaults BEFORE registering our KMI. When defaults
    # are disabled in keyconfigs.user, Blender dispatches only from that layer
    # for the affected keymap. We must know which keymaps needed user-layer
    # disables so we can also register our KMI there.
    user_disabled_keymaps: set = set()
    if entry.get("enabled", True):
        keybind_refs, shortcut_refs = _gated_conflict_refs(entry)
        all_refs = keybind_refs + shortcut_refs
        # Drop refs describing the entry's OWN identical bindings (main binding
        # OR any extra keybind; same op + key + mods) when that binding is a
        # genuine user/addon KMI we'll adopt below. A factory-identical binding
        # is NOT adopted (we make our own controllable KMI), so its ref must
        # stay and be disabled.
        ent_sigs = {(key, event_type,
                     bool(shift), bool(ctrl), bool(alt), bool(oskey))}
        for _ex in entry.get("extra_keybinds", []):
            _ek = _ex.get("key", "")
            if _ek and _ek != "NONE":
                ent_sigs.add((_ek, _ex.get("value", "PRESS"),
                              bool(_ex.get("shift")), bool(_ex.get("ctrl")),
                              bool(_ex.get("alt")), bool(_ex.get("oskey"))))
        ent_ops = {o.get("id") for o in op_list if isinstance(o, dict)}
        filtered_refs = []
        for r in all_refs:
            r_sig = (r.get("key", ""), r.get("event_type", "PRESS"),
                     bool(r.get("shift")), bool(r.get("ctrl")),
                     bool(r.get("alt")), bool(r.get("oskey")))
            if r.get("op_id") in ent_ops and r_sig in ent_sigs:
                km_r = _find_keymap("user", r.get("keymap_name", ""))
                _op_it = next((o for o in op_list if isinstance(o, dict)
                               and o.get("id") == r.get("op_id")), {})
                adoptable = km_r is not None and _find_existing_user_kmi(
                    km_r, r.get("op_id"), r_sig[0], r_sig[1],
                    r_sig[2], r_sig[3], r_sig[4], r_sig[5],
                    op_props=_op_it.get("props") or {},
                    op_props_data=_op_it.get("props_data") or {}) is not None
                if adoptable:
                    continue  # will adopt this user/addon KMI, don't disable it
            filtered_refs.append(r)
        if filtered_refs:
            user_disabled_keymaps = _disable_default_kmis(entry_id, filtered_refs)
            _refresh_keyconfigs()

    if not op_list:
        return

    any_mod    = entry.get("any", False)
    key_mod    = entry.get("key_modifier", "") or "NONE"
    enabled    = entry.get("enabled", True)
    repeat     = bool(entry.get("repeat", False))

    if not key or key == "NONE":
        return

    registered = []

    # Operators whose addon/source is gone: detected on the last re-scan/import
    # and cached on the entry. We still keep them in the entry (conflict
    # detection, editing) but must NOT create dead KMIs for them.
    unreg = set(entry.get("unregistered_ops", []) or [])

    for op_item in op_list:
        if isinstance(op_item, dict):
            op_id    = op_item.get("id", "")
            op_props = op_item.get("props", {})
            op_props_data = op_item.get("props_data", {})
        else:
            op_id    = str(op_item)
            op_props = {}
            op_props_data = {}

        if not op_id:
            continue

        if op_id in unreg:
            continue  # unregistered operator — no KMI

        # One KMI per target keymap (multi-context support).
        for keymap_name in _op_target_keymaps(op_item, op_id):
            # Register all Keymapper KMIs in the user keyconfig. User-layer KMI
            # ids stay stable across keyconfigs.update() (addon-layer ids get
            # reassigned), which keeps activate/deactivate/remove reliable.
            km = _get_or_create_user_keymap(keymap_name)
            if km is None:
                print(f"[Keymapper] Skipping '{op_id}' — could not get keymap '{keymap_name}'")
                continue
            # Adoption: if an identical USER-layer KMI already exists (e.g. the
            # user made the same binding by hand), take ownership of it instead
            # of creating a duplicate — Blender would merge the duplicate onto it
            # anyway, and on delete we'd wrongly remove the user's KMI. Adopted
            # KMIs are restored (never removed) when our claim ends.
            adopted = _find_existing_user_kmi(
                km, op_id, key, event_type, shift, ctrl, alt, oskey,
                op_props=op_props, op_props_data=op_props_data)
            if adopted is not None:
                sig = (adopted.type, adopted.value, bool(adopted.shift),
                       bool(adopted.ctrl), bool(adopted.alt), bool(adopted.oskey))
                _adopted_kmis.setdefault(entry_id, []).append(
                    (km.name, op_id, sig, bool(adopted.active)))
                try:
                    adopted.active = enabled
                except Exception:
                    pass
                registered.append((km, adopted))
                print(f"[Keymapper] Adopted existing user KMI '{op_id}' in "
                      f"'{keymap_name}' ({key})")
                continue
            # Our OWN KMI from a previous session (the saved user keyconfig
            # persists it): reuse it instead of creating a duplicate beside it.
            leftover = _find_our_leftover(
                km, op_id, key, event_type, shift, ctrl, alt, oskey,
                op_props=op_props, op_props_data=op_props_data)
            if leftover is not None:
                try:
                    leftover.active = enabled
                except Exception:
                    pass
                registered.append((km, leftover))
                continue
            try:
                kmi = _new_kmi_no_collapse(
                    km,
                    idname=op_id,
                    type=key,
                    value=event_type,
                    shift=shift,
                    ctrl=ctrl,
                    alt=alt,
                    oskey=oskey,
                    key_modifier=key_mod,
                    repeat=repeat,
                )
                kmi.active = enabled
                if any_mod:
                    kmi.any = True
                _set_legacy_props(kmi, op_props)
                if op_props_data and kmi.properties:
                    from .operators import apply_kmi_props
                    apply_kmi_props(kmi.properties, op_props_data)

                registered.append((km, kmi))
                print(f"[Keymapper] Registered '{op_id}' in '{keymap_name}' ({key})")

            except Exception as e:
                print(f"[Keymapper] Failed to register '{op_id}': {e}")

    _kmi_registry[entry_id] = registered
    _entry_snapshots[entry_id] = _entry_snapshot(entry)

    # Register extra keybinds
    extra_keybinds = entry.get("extra_keybinds", [])
    for extra in extra_keybinds:
        ex_key = extra.get("key", "")
        if not ex_key or ex_key == "NONE":
            continue
        ex_value = extra.get("value", "PRESS")
        ex_shift = extra.get("shift", False)
        ex_ctrl  = extra.get("ctrl",  False)
        ex_alt   = extra.get("alt",   False)
        ex_oskey = extra.get("oskey", False)
        for op_item in op_list:
            op_id    = op_item.get("id", "") if isinstance(op_item, dict) else str(op_item)
            op_props = op_item.get("props", {}) if isinstance(op_item, dict) else {}
            op_props_data = op_item.get("props_data", {}) if isinstance(op_item, dict) else {}
            if not op_id:
                continue
            if op_id in unreg:
                continue  # unregistered operator — no KMI
            for keymap_name in _op_target_keymaps(op_item, op_id):
                km = _get_or_create_user_keymap(keymap_name)
                if km is None:
                    continue
                # Adoption (same rule as the main-binding path): if an identical
                # adoptable KMI already exists, take ownership instead of
                # creating a duplicate — otherwise delete would remove the
                # user's own KMI along with ours (spec-matched, e.g. under
                # Industry Compatible where user diffs are negative-id).
                adopted = _find_existing_user_kmi(
                    km, op_id, ex_key, ex_value, ex_shift, ex_ctrl, ex_alt, ex_oskey,
                    op_props=op_props, op_props_data=op_props_data)
                if adopted is not None:
                    sig = (adopted.type, adopted.value, bool(adopted.shift),
                           bool(adopted.ctrl), bool(adopted.alt), bool(adopted.oskey))
                    _adopted_kmis.setdefault(entry_id, []).append(
                        (km.name, op_id, sig, bool(adopted.active)))
                    try:
                        adopted.active = enabled
                    except Exception:
                        pass
                    registered.append((km, adopted))
                    print(f"[Keymapper] Adopted existing user KMI (extra) "
                          f"'{op_id}' in '{keymap_name}' ({ex_key})")
                    continue
                leftover = _find_our_leftover(
                    km, op_id, ex_key, ex_value, ex_shift, ex_ctrl,
                    ex_alt, ex_oskey)
                if leftover is not None:
                    try:
                        leftover.active = enabled
                    except Exception:
                        pass
                    registered.append((km, leftover))
                    continue
                try:
                    kmi = _new_kmi_no_collapse(
                        km,
                        idname=op_id, type=ex_key, value=ex_value,
                        shift=ex_shift, ctrl=ex_ctrl, alt=ex_alt, oskey=ex_oskey,
                        key_modifier=extra.get("key_modifier", "") or "NONE",
                    )
                    kmi.active = enabled
                    _set_legacy_props(kmi, op_props)
                    if op_props_data and kmi.properties:
                        from .operators import apply_kmi_props
                        apply_kmi_props(kmi.properties, op_props_data)
                    registered.append((km, kmi))
                    print(f"[Keymapper] Registered extra keybind '{op_id}' in '{keymap_name}' ({ex_key})")
                except Exception as e:
                    print(f"[Keymapper] Failed to register extra keybind '{op_id}': {e}")

    # Update registry with extra KMIs
    _kmi_registry[entry_id] = registered
    # Durable binding specs for robust removal (see _entry_kmi_specs docs).
    _entry_kmi_specs[entry_id] = _entry_binding_specs(entry)
    # Keymap-qualified registration set for collapse detection/healing —
    # (km_name, idname, final_sig). Captured now while kmi refs are fresh;
    # dummy-modifier KMIs record their FINAL (post-fix) signature via specs.
    km_set = set()
    spec_sigs = {}
    for oid, sig in _entry_kmi_specs[entry_id]:
        spec_sigs.setdefault(oid, []).append(sig)
    for km, kmi in registered:
        try:
            cur = (kmi.type, kmi.value, bool(kmi.shift), bool(kmi.ctrl),
                   bool(kmi.alt), bool(kmi.oskey))
            sigs = spec_sigs.get(kmi.idname, [])
            final = cur
            if cur not in sigs:
                # dummy-modifier KMI: match back to its spec by type+value
                for s in sigs:
                    if s[0] == cur[0] and s[1] == cur[1]:
                        final = s
                        break
            km_set.add((km.name, kmi.idname, final))
        except Exception:
            pass
    _entry_kmi_keymaps[entry_id] = km_set

    # UI icon cache: which pre-existing KMIs this entry adopted. Kept across
    # deactivate so the icon stays visible on disabled entries.
    _adoption_display[entry_id] = [
        (r[0], r[1], r[2]) for r in _adopted_kmis.get(entry_id, [])]

    # Defensive phantom cleanup: for each adopted binding, remove any OTHER
    # non-owned duplicate KMI of the same op+signature in that keymap. A heal or
    # materialize pass on custom active configs (e.g. BForArtists) can leave an
    # extra copy that duplicates an adopted binding; strip it so only the
    # adopted item remains.
    for (a_km_name, a_op, a_sig, _orig) in _adopted_kmis.get(entry_id, []):
        akm = _find_keymap("user", a_km_name)
        if akm is None:
            continue
        kept = False
        for it in list(akm.keymap_items):
            cur = (it.type, it.value, bool(it.shift), bool(it.ctrl),
                   bool(it.alt), bool(it.oskey))
            if it.idname == a_op and cur == a_sig:
                if not kept:
                    kept = True  # keep the first (the adopted item)
                    continue
                # extra duplicate — remove only if it's not another entry's
                # registered KMI
                rec = (a_km_name, a_op, a_sig)
                claimed = any(rec in recs for eid, recs in _entry_kmi_keymaps.items()
                              if eid != entry_id)
                if not claimed:
                    try:
                        akm.keymap_items.remove(it)
                        print(f"[Keymapper] Removed phantom duplicate: {a_op} in {a_km_name}")
                    except Exception:
                        pass

    # Schedule a deferred keyconfig rebuild so the addon KMI is picked up by
    # Blender's dispatcher and keymap editor without needing a manual Restore.
    def _deferred_rebuild():
        try:
            bpy.context.window_manager.keyconfigs.update()
        except Exception:
            pass
        try:
            _heal_collapsed_entry_kmis()
        except Exception:
            pass
        return None
    try:
        bpy.app.timers.register(_deferred_rebuild, first_interval=0.1)
    except Exception:
        pass


def _set_kmi_active(entry_id: str, active: bool, entry: dict = None):
    """Set kmi.active on all registered KMIs for this entry.

    The (km, kmi) object references in _kmi_registry go stale after
    keyconfigs.update() — the Python wrapper survives but reports id=0 and
    silently ignores writes. We re-fetch by stored id first; but
    keyconfigs.update() can also REASSIGN ids on the addon keyconfig (where
    KMIs in keymaps without user-disabled defaults live), so the stored id no
    longer matches. We therefore also match by signature against this entry's
    own generated operators (which never collide with Blender defaults).
    """
    wm = bpy.context.window_manager

    # Only act if this entry actually registered KMIs. An inert duplicate has no
    # specs on record; matching by signature would otherwise toggle its canonical
    # twin's identical-signature KMIs.
    if not _entry_kmi_specs.get(entry_id):
        return

    if entry is None:
        try:
            from . import persistence
            entry = persistence.get_entry_by_id(entry_id)
        except Exception:
            entry = None
    if entry is None:
        return
    import json
    try:
        _op_list = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        _op_list = []
    entry_op_ids = {o.get("id") for o in _op_list
                    if isinstance(o, dict) and o.get("id")}
    if not entry_op_ids:
        return


    sig = (
        entry.get("key", ""), entry.get("event_type", "PRESS"),
        bool(entry.get("shift", False)), bool(entry.get("ctrl", False)),
        bool(entry.get("alt", False)), bool(entry.get("oskey", False)),
    )
    extra_sigs = []
    for extra in entry.get("extra_keybinds", []):
        ek = extra.get("key", "")
        if ek and ek != "NONE":
            extra_sigs.append((
                ek, extra.get("value", "PRESS"),
                bool(extra.get("shift", False)), bool(extra.get("ctrl", False)),
                bool(extra.get("alt", False)), bool(extra.get("oskey", False)),
            ))

    def _sig_match(item):
        if item.idname not in entry_op_ids:
            return False
        cand = (item.type, item.value, bool(item.shift), bool(item.ctrl),
                bool(item.alt), bool(item.oskey))
        return cand == sig or cand in extra_sigs

    # Toggle ONLY our own addon-owned KMIs. Ownership is the live item's NEGATIVE
    # id (factory + materialized copies are POSITIVE), so we never wrongly toggle
    # a factory/materialized copy that happens to share this entry's signature —
    # and we don't depend on any stored id, which renumbers on every rebuild.
    # Restricted to the keymaps this entry actually registered into, so another
    # entry's identical-signature KMI in a DIFFERENT keymap is never touched.
    allowed_kms = {rec[0] for rec in (_entry_kmi_keymaps.get(entry_id) or ())}
    for kc in (wm.keyconfigs.user, wm.keyconfigs.addon):
        if kc is None:
            continue
        for km in kc.keymaps:
            if allowed_kms and km.name not in allowed_kms:
                continue
            for item in km.keymap_items:
                if not _owned_id_ok(km.name, item):
                    continue  # factory/materialized copy; never ours
                if _sig_match(item):
                    try:
                        item.active = active
                    except Exception:
                        pass


_healing = False
_bulk_reactivating = False
_heal_attempts: dict = {}  # entry_id -> heal retry count (loop guard)
_adopted_kmis: dict = {}  # entry_id -> [(km_name, op_id, sig, orig_active), ...]
_adoption_display: dict = {}  # entry_id -> [(km_name, op_id, sig)] — UI icon cache;
# kept across deactivate so the adopted icon stays visible on disabled entries.


def _compute_would_adopt(entry) -> list:
    """For a DISABLED entry: which pre-existing identical KMIs WOULD be adopted
    on activation. Read-only — powers the adopted-KMI card icon."""
    import json as _json
    recs = []
    try:
        op_list = _json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        return recs
    bindings = [(entry.get("key", ""), entry.get("event_type", "PRESS"),
                 bool(entry.get("shift")), bool(entry.get("ctrl")),
                 bool(entry.get("alt")), bool(entry.get("oskey")))]
    for ex in entry.get("extra_keybinds", []):
        k = ex.get("key", "")
        if k and k != "NONE":
            bindings.append((k, ex.get("value", "PRESS"),
                             bool(ex.get("shift")), bool(ex.get("ctrl")),
                             bool(ex.get("alt")), bool(ex.get("oskey"))))
    for op_item in op_list:
        if not isinstance(op_item, dict):
            continue
        op_id = op_item.get("id", "")
        if not op_id:
            continue
        for km_name in _op_target_keymaps(op_item, op_id):
            km = _find_keymap("user", km_name)
            if km is None:
                continue
            for (bk, bv, bs, bc, ba, bo) in bindings:
                if not bk or bk == "NONE":
                    continue
                it = _find_existing_user_kmi(
                    km, op_id, bk, bv, bs, bc, ba, bo,
                    op_props=op_item.get("props") or {},
                    op_props_data=op_item.get("props_data") or {})
                if it is not None:
                    recs.append((km.name, op_id, (bk, bv, bs, bc, ba, bo)))
    return recs


def _adopted_layer_label(km_name, op_id, sig) -> str:
    """Human-readable layer name where an adopted binding lives: a custom active
    config's name (BForArtists / Industry Compatible), else "Addon" if the item
    is in the addon keyconfig, else "User"."""
    try:
        wm = bpy.context.window_manager
    except Exception:
        return "User"

    def _has(kc):
        if kc is None:
            return False
        km = kc.keymaps.get(km_name)
        if km is None:
            return False
        for it in km.keymap_items:
            cur = (it.type, it.value, bool(it.shift), bool(it.ctrl),
                   bool(it.alt), bool(it.oskey))
            if it.idname == op_id and cur == sig:
                return True
        return False

    # A custom active config (BFA / Industry) owns the binding directly.
    try:
        if wm.keyconfigs.active != wm.keyconfigs.default and _has(wm.keyconfigs.active):
            return wm.keyconfigs.active.name
    except Exception:
        pass
    # Addon-registered binding.
    try:
        if _has(wm.keyconfigs.addon):
            return "Addon"
    except Exception:
        pass
    return "User"


def _sweep_unclaimed_leftovers():
    """Remove previous-session KMIs that no entry claimed during this
    activation cycle: their entry was deleted or its binding/props edited
    between sessions, so the persisted KMI is an orphan that would otherwise
    stay live forever.

    The allowance per spec is the number of LIVE REGISTRATIONS of that spec
    (one per entry that reused or freshly created it this cycle) — NOT the
    reuse-claims count: freshly created KMIs have no claim, and sweeping
    against claims would delete them right after creation."""
    try:
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.user
    except Exception:
        return
    if kc is None:
        return
    removed = 0
    for (km_name, op_id, sig) in list(_prev_session_kmis):
        km = kc.keymaps.get(km_name)
        if km is None:
            continue
        allowed = sum(1 for recs in _entry_kmi_keymaps.values()
                      if (km_name, op_id, sig) in recs)
        seen = 0
        for it in list(km.keymap_items):
            cur = (it.type, it.value, bool(it.shift), bool(it.ctrl),
                   bool(it.alt), bool(it.oskey))
            if it.idname != op_id or cur != sig:
                continue
            if not _owned_id_ok(km_name, it):
                continue
            seen += 1
            if seen <= allowed:
                continue
            try:
                km.keymap_items.remove(it)
                removed += 1
            except Exception:
                pass
    if removed:
        print(f"[Keymapper] Removed {removed} orphaned previous-session KMIs.")


def refresh_adoption_display():
    """Refresh the adopted-KMI icon cache for every entry: live records for
    active entries, a would-adopt computation for disabled ones. Called after
    rescans / bulk reactivation."""
    try:
        from . import persistence
        entries = persistence.get_entries()
    except Exception:
        return
    for e in entries:
        eid = e.get("entry_id", "")
        if not eid:
            continue
        if eid in _adopted_kmis:
            _adoption_display[eid] = [
                (r[0], r[1], r[2]) for r in _adopted_kmis[eid]]
        elif not e.get("enabled", True):
            try:
                _adoption_display[eid] = _compute_would_adopt(e)
            except Exception:
                pass
        else:
            # Enabled but nothing adopted: clear any stale record (e.g. left
            # over from a previous keyconfig where the entry WAS adopted).
            _adoption_display[eid] = []


def _heal_collapsed_entry_kmis(skip_entry_id: str = ""):
    """Blender's user-keymap diff rebuild (triggered by restores/refreshes) can
    silently collapse an addon KMI that is field-identical to a default — even
    in keymaps the triggering change never touched. Verify every enabled
    entry's registered specs still have live KMIs and re-register any entry
    that lost one."""
    global _healing
    if _healing or _bulk_reactivating:
        return
    from . import persistence

    wm = bpy.context.window_manager
    alive = set()
    # KMIs awaiting the deferred dummy-modifier strip count as alive — their
    # final signature isn't on any live item yet.
    for pf in _pending_binding_fixes:
        alive.add((pf[0], pf[1], (pf[2], pf[3], bool(pf[4]), bool(pf[5]),
                                  bool(pf[6]), bool(pf[7]))))
    for kc in (wm.keyconfigs.user, wm.keyconfigs.addon, wm.keyconfigs.active):
        if kc is None:
            continue
        for km in kc.keymaps:
            for item in km.keymap_items:
                if not _owned_id_ok(km.name, item):
                    continue
                alive.add((km.name, item.idname, (item.type, item.value,
                           bool(item.shift), bool(item.ctrl),
                           bool(item.alt), bool(item.oskey))))
    # Adopted KMIs (we own the user's/config's existing item) count as alive —
    # their signature is on a live item we didn't create, which the ownership
    # filter above may have skipped.
    for _eid, _recs in _adopted_kmis.items():
        for (a_km, a_op, a_sig, _orig) in _recs:
            alive.add((a_km, a_op, a_sig))
    _healing = True
    try:
        for entry in persistence.get_entries():
            eid = entry.get("entry_id")
            if not eid or eid == skip_entry_id:
                continue
            if not entry.get("enabled", True):
                continue
            expected = _entry_kmi_keymaps.get(eid)
            if not expected:
                continue
            missing = set(expected) - alive
            if missing:
                # Guard against infinite heal loops: if an entry keeps
                # "collapsing" (its expected signature never matches what's
                # live), retrying forever freezes Blender. Give up after a few
                # attempts and leave it as-is.
                n = _heal_attempts.get(eid, 0)
                if n >= 3:
                    continue
                _heal_attempts[eid] = n + 1
                print(f"[Keymapper] Healing collapsed KMIs for "
                      f"'{entry.get('display_name')}'")
                activate_entry(entry)
            else:
                _heal_attempts.pop(eid, None)
    finally:
        _healing = False


def deactivate_entry(entry: dict):
    """Disable KMIs for this entry and restore any disabled Blender defaults."""
    entry_id = entry.get("entry_id")
    if not entry_id:
        return
    _set_kmi_active(entry_id, False, entry)
    _restore_default_kmis(entry_id)
    _refresh_keyconfigs()
    _heal_collapsed_entry_kmis(entry_id)
    print(f"[Keymapper] Deactivated '{entry.get('display_name')}'")


def reactivate_entry(entry: dict):
    """Enable all KMIs for this entry, creating them if needed."""
    _invalidate_owned_specs()
    entry_id = entry.get("entry_id")
    if not entry_id:
        return

    # Inert duplicates never register KMIs.
    try:
        from . import conflict_detector
        if conflict_detector.is_inert_duplicate(entry):
            _remove_kmis(entry_id, entry)
            _restore_default_kmis(entry_id)
            _refresh_keyconfigs()
            return
    except Exception:
        pass

    # Verify our KMIs actually still exist. _kmi_registry holds stale object
    # refs, and Blender's user-keymap diff rebuild can silently collapse an
    # addon KMI that became field-identical to a factory item (same binding,
    # both inactive) — e.g. an entry re-binding an operator to its default key.
    # Checked per-keymap so an identical KMI from ANOTHER entry in a different
    # keymap can't mask a loss. Falls through to a full activate_entry() if
    # anything is missing.
    expected = set(_entry_kmi_keymaps.get(entry_id) or ())
    alive = set()
    if expected:
        wm = bpy.context.window_manager
        for kc in (wm.keyconfigs.user, wm.keyconfigs.addon):
            if kc is None:
                continue
            for km in kc.keymaps:
                for item in km.keymap_items:
                    if not _owned_id_ok(km.name, item):
                        continue
                    rec = (km.name, item.idname, (item.type, item.value,
                           bool(item.shift), bool(item.ctrl),
                           bool(item.alt), bool(item.oskey)))
                    if rec in expected:
                        alive.add(rec)

    kmis = _kmi_registry.get(entry_id, [])
    if kmis and expected and alive == expected:
        _set_kmi_active(entry_id, True, entry)
        # Re-disable conflicting defaults
        keybind_refs  = entry.get("keybind_conflicts_external", [])
        shortcut_refs = entry.get("shortcut_conflicts_external", [])
        all_refs = keybind_refs + shortcut_refs
        if all_refs:
            _disable_default_kmis(entry_id, all_refs)
        _refresh_keyconfigs()
        _heal_collapsed_entry_kmis(entry_id)
        print(f"[Keymapper] Reactivated '{entry.get('display_name')}'")
    else:
        activate_entry(entry)


def reconcile_inert_duplicates():
    """Bring KMI state in line with current inert-duplicate status.

    Inert duplicates (100% identical to an earlier entry) must hold no KMIs;
    canonical entries that are enabled must hold KMIs. Editing/deleting one
    entry can flip another's status (e.g. deleting the canonical entry promotes
    its twin), so this runs after any add/edit/delete/duplicate/reorder.
    """
    from . import persistence, conflict_detector
    entries = persistence.get_entries()
    changed = False
    # PHASE 1 — demote newly-inert entries FIRST, while their KMIs are still
    # the unambiguous owners of their signatures. If a newly-canonical twin
    # were promoted first, its freshly registered identical KMIs would match
    # the demoted twin's stored specs and get deleted by _remove_kmis.
    for entry in entries:
        entry_id = entry.get("entry_id")
        if not entry_id:
            continue
        if (conflict_detector.is_inert_duplicate(entry, entries)
                and bool(_kmi_registry.get(entry_id))):
            _remove_kmis(entry_id, entry)
            _restore_default_kmis(entry_id)
            changed = True
    # PHASE 2 — promote newly-canonical entries.
    for entry in entries:
        entry_id = entry.get("entry_id")
        if not entry_id:
            continue
        if (not conflict_detector.is_inert_duplicate(entry, entries)
                and entry.get("enabled", True)
                and not _kmi_registry.get(entry_id)):
            activate_entry(entry)
            changed = True
    if changed:
        _refresh_keyconfigs()


def delete_entry(entry: dict):
    """Fully remove KMIs for a deleted entry and restore Blender defaults."""
    _invalidate_owned_specs()
    entry_id = entry.get("entry_id")
    if not entry_id:
        return
    _remove_kmis(entry_id, entry)
    _restore_default_kmis(entry_id)
    _refresh_keyconfigs()
    _heal_collapsed_entry_kmis(entry_id)
    _entry_snapshots.pop(entry_id, None)
    _adoption_display.pop(entry_id, None)
    print(f"[Keymapper] Deleted KMIs for '{entry.get('display_name')}'")


def update_entry_if_changed(old_entry: dict, new_data: dict) -> bool:
    """
    Compare old vs new state. Only recreate KMIs if something changed.
    Returns True if KMIs were updated.
    """
    entry_id = old_entry.get("entry_id")
    if not entry_id:
        return False

    old_snap = _entry_snapshots.get(entry_id)
    merged = dict(old_entry)
    merged.update(new_data)
    new_snap = _entry_snapshot(merged)

    if old_snap == new_snap:
        print(f"[Keymapper] No keymap changes for '{old_entry.get('display_name')}' — skipping KMI update")
        return False

    activate_entry(merged)
    print(f"[Keymapper] Updated KMIs for '{old_entry.get('display_name')}'")
    return True


def release_all_entries():
    """Two-phase full release: remove every entry's registered KMIs, then
    restore all disabled defaults with batch release (a per-entry loop
    deadlocks on the consensus check — see Restore-All). Entry DATA is left
    untouched; used before a replace-import and by Restore-All Step 0."""
    from . import persistence

    for _e in persistence.get_entries():
        _eid = _e.get("entry_id")
        if not _eid:
            continue
        try:
            _remove_kmis(_eid, _e)
        except Exception as ex:
            print(f"[Keymapper] remove KMIs failed for {_eid}: {ex}")
    _releasing = set(_disabled_defaults.keys())
    for _eid in list(_disabled_defaults.keys()):
        try:
            _restore_default_kmis(_eid, releasing=_releasing)
        except Exception as ex:
            print(f"[Keymapper] restore defaults failed for {_eid}: {ex}")
    try:
        _refresh_keyconfigs()
    except Exception:
        pass


def reactivate_all(fast: bool = False):
    """Rebuild all KMIs. fast=True only on startup (reuse stored handles)."""
    _invalidate_owned_specs()
    global _bulk_reactivating
    _build_op_keymap_cache()

    # Respect the global master switch: if the user turned all shortcuts off,
    # don't activate anything on startup.
    try:
        from .preferences import get_prefs
        if not get_prefs().global_enabled:
            print("[Keymapper] Startup: global shortcuts disabled — nothing activated.")
            from . import persistence as _p
            for entry in _p.get_entries():
                _entry_snapshots[entry.get("entry_id", "")] = _entry_snapshot(entry)
            return
    except Exception:
        pass

    from . import persistence
    entries = persistence.get_entries()
    count = 0
    _reset_leftover_claims()
    _bulk_reactivating = True
    try:
        for entry in entries:
            if entry.get("enabled", True):
                activate_entry(entry)
                count += 1
            else:
                _entry_snapshots[entry.get("entry_id", "")] = _entry_snapshot(entry)
    finally:
        _bulk_reactivating = False
    # Previous-session KMIs nobody claimed (entry deleted / binding edited
    # between sessions) are orphans — drop them before healing.
    _sweep_unclaimed_leftovers()
    # One heal pass for the whole batch instead of per-entry (which is O(n²)).
    _heal_collapsed_entry_kmis()
    print(f"[Keymapper] Startup: activated {count} of {len(entries)} entries.")
    try:
        refresh_adoption_display()
    except Exception:
        pass
    # Keymap changes made during startup/load don't reliably take effect until
    # Blender's event loop settles. Re-apply the conflict-disables on a deferred
    # timer so default KMIs (e.g. Space → Play/Pause) actually get disabled.
    schedule_conflict_disable(fast=fast)


def set_global_enabled(enabled: bool):
    """Master switch for all Keymapper shortcuts.

    When `enabled` is False: deactivate every entry's KMIs and restore all the
    Blender defaults they were disabling. When True: reactivate every entry
    whose own `enabled` flag is True (so per-entry state is preserved across a
    global off→on cycle).
    """
    from . import persistence
    entries = persistence.get_entries()
    if enabled:
        for entry in entries:
            if entry.get("enabled", True):
                reactivate_entry(entry)
    else:
        # Deactivating one entry at a time does NOT work here. _restore_default_kmis
        # runs a consensus check: a default stays disabled while ANY OTHER entry
        # still claims it. Turning the master switch off means every entry is
        # releasing at once, but a sequential loop still sees the not-yet-processed
        # entries as live claimants — so their shared defaults were "kept disabled"
        # and, once those entries' handles were popped too, nothing ever went back
        # to re-enable them (e.g. all 29 DEL defaults stayed dead until a Re-scan).
        #
        # So: remove OUR KMIs for every entry first, then restore the defaults in a
        # second pass, by which point no entry holds a claim and the consensus check
        # correctly sees the default as fully released.
        for entry in entries:
            entry_id = entry.get("entry_id")
            if not entry_id:
                continue
            _remove_kmis(entry_id, entry)
            _entry_snapshots[entry_id] = _entry_snapshot(entry)
        _releasing = {e.get("entry_id") for e in entries if e.get("entry_id")}
        for entry in entries:
            entry_id = entry.get("entry_id")
            if entry_id:
                _restore_default_kmis(entry_id, releasing=_releasing)
    _refresh_keyconfigs()
    print(f"[Keymapper] Global shortcuts {'enabled' if enabled else 'disabled'}.")


def reapply_all_conflict_disables(fast: bool = False):
    """Re-run the default-KMI disable for every enabled, registered entry.

    Disable-only (never touches keyconfigs.user scanning). Safe to call
    repeatedly: _disable_default_kmis skips KMIs already inactive and skips
    refs the user manually re-enabled.

    Fast path: entries whose disable-handles were already recorded this
    session are re-disabled directly by handle (layer, keymap, kmi.id) —
    no property re-search, no re-materialization.
    """
    from . import persistence
    wm = bpy.context.window_manager
    for entry in persistence.get_entries():
        if not entry.get("enabled", True):
            continue
        entry_id = entry.get("entry_id")
        if not entry_id or not _kmi_registry.get(entry_id):
            continue
        handles = _disabled_defaults.get(entry_id) if fast else None
        if handles:
            # Re-disable by exact stored handles — cheap, idempotent.
            for layer, km_name, kmi_id, _ref, _mat in handles:
                if _ref.get("user_reenabled", False):
                    continue
                km = _find_keymap(layer, km_name)
                if km is None:
                    continue
                for kmi in km.keymap_items:
                    if kmi.id == kmi_id:
                        if kmi.active:
                            kmi.active = False
                        break
            continue
        _kb, _sc = _gated_conflict_refs(entry)
        refs = _kb + _sc
        if refs:
            _disable_default_kmis(entry_id, refs)
    _refresh_keyconfigs()


def schedule_conflict_disable(delay: float = 0.05, fast: bool = False):
    """Defer reapply_all_conflict_disables to after the event loop settles.

    This mirrors the timing of a manual edit+confirm, which is the only path
    that reliably disabled conflicting defaults before this was added.
    """
    import bpy

    def _cb():
        try:
            reapply_all_conflict_disables(fast=fast)
        except Exception as e:
            print(f"[Keymapper] Deferred conflict-disable error: {e}")
        return None  # one-shot

    try:
        bpy.app.timers.register(_cb, first_interval=delay)
    except Exception:
        # Timers unavailable — fall back to a synchronous pass.
        reapply_all_conflict_disables(fast=fast)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _remove_kmis(entry_id: str, entry: dict = None):
    _kmi_registry.pop(entry_id, [])
    wm = bpy.context.window_manager

    # Release any ADOPTED user KMIs first: these are the user's own bindings we
    # took ownership of (identical-signature case). We must NEVER remove them —
    # restore each to the active state it had before adoption, then drop the
    # claim. This runs before spec-based removal so the following removal never
    # deletes an adopted item.
    adopted = _adopted_kmis.pop(entry_id, [])
    adopted_sigs = set()
    for km_name, op_id, sig, orig_active in adopted:
        adopted_sigs.add((km_name, op_id, sig))
        km = _find_keymap("user", km_name)
        if km is None:
            continue
        for it in km.keymap_items:
            cur = (it.type, it.value, bool(it.shift), bool(it.ctrl),
                   bool(it.alt), bool(it.oskey))
            if it.idname == op_id and cur == sig:
                try:
                    it.active = orig_active
                except Exception:
                    pass
                break

    if entry is None:
        try:
            from . import persistence
            entry = persistence.get_entry_by_id(entry_id)
        except Exception:
            entry = None

    # Use the specs ACTUALLY registered (durable, captured at registration). On
    # an edit these still reflect the OLD binding the live KMIs carry, so we
    # remove the right items; after this we re-register with new specs.
    specs = _entry_kmi_specs.pop(entry_id, None)
    _removed_km_set = _entry_kmi_keymaps.pop(entry_id, None) or set()
    _allowed_kms = {rec[0] for rec in _removed_km_set}
    if specs is None:
        # No registration on record. Either an inert duplicate (never
        # registered — owns nothing) or a pre-upgrade entry. We only fall back
        # to signature-based removal when we have PROOF we registered before
        # (a recorded keymap set). Without that proof, removing by the entry's
        # binding would delete a user's identical hand-made KMI we never owned
        # (the adoption case on first activate). So: no proof → remove nothing.
        if not _removed_km_set:
            return
        if entry is not None:
            try:
                from . import conflict_detector
                if conflict_detector.is_inert_duplicate(entry):
                    return
            except Exception:
                pass
            specs = _entry_binding_specs(entry)  # legacy fallback
        else:
            specs = set()
    if not specs:
        return

    def _spec_match(item):
        cand = (item.type, item.value, bool(item.shift), bool(item.ctrl),
                bool(item.alt), bool(item.oskey))
        # Adopted user KMIs are the user's own — restored above, never removed.
        for (a_km, a_op, a_sig) in adopted_sigs:
            if item.idname == a_op and cand == a_sig:
                return False
        if (item.idname, cand) in specs:
            return True
        # Stale dummy-modifier variant (anti-collapse combo that never got
        # stripped, e.g. persisted mid-fix in a previous session).
        if (item.ctrl and item.alt and item.oskey
                and getattr(item, "key_modifier", "NONE") == _DUMMY_KEYMOD):
            for oid, sig in specs:
                if oid == item.idname and sig[0] == item.type and sig[1] == item.value:
                    return True
        return False

    # Remove ONLY our own KMIs, and only in the USER layer: addon-owned items
    # have NEGATIVE ids in factory keymaps; in user-created keymaps ours are
    # POSITIVE, where the spec match decides (see _owned_id_ok). Restricted to
    # this entry's registered keymaps when known.
    #
    # NOTE: no removal pass over keyconfigs.addon. Entry KMIs are created
    # exclusively in keyconfigs.user (_get_or_create_user_keymap); the addon
    # layer belongs to third-party addons, and a spec match there is THEIR
    # binding that happens to be identical to ours (e.g. an addon registering
    # outliner.item_rename on F2) — removing it would destroy their keymap
    # entry instead of just leaving it disabled/restorable.
    kc_user = wm.keyconfigs.user
    if kc_user is not None:
        for km in kc_user.keymaps:
            if _allowed_kms and km.name not in _allowed_kms:
                continue
            for item in list(km.keymap_items):
                if not _owned_id_ok(km.name, item):
                    continue
                if _spec_match(item):
                    try:
                        km.keymap_items.remove(item)
                    except Exception as e:
                        print(f"[Keymapper] Could not remove KMI in {km.name}: {e}")


# ---------------------------------------------------------------------------
# Register / Unregister
# ---------------------------------------------------------------------------

def register():
    print("[Keymapper] Keymap manager ready (Phase 5).")


def unregister():
    global _kmi_registry, _entry_snapshots
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        for entry_id, kmis in _kmi_registry.items():
            for km, kmi in kmis:
                try:
                    km.keymap_items.remove(kmi)
                except Exception:
                    pass
    _kmi_registry = {}
    _entry_snapshots = {}
    print("[Keymapper] Keymap manager: all KMIs removed.")
