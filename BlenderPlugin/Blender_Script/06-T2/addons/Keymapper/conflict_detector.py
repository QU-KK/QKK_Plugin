"""
conflict_detector.py
Internal Keymapper conflict detection engine.

Detects conflicts between our own shortcut entries.
Phase 7 will extend this with Blender default conflict detection.

Conflict types (internal):
  "duplicate"    — identical key + context + operators + props
  "key_conflict" — same key + context overlap, different operators
  "op_overlap"   — same operators + context overlap, different key
  "event_soft"   — same key+mods+context, different event type (PRESS vs CLICK)

Each entry stores:
  "internal_conflicts": [
      {"type": str, "with": entry_id, "wins": bool},
      ...
  ]

Conflict caching (v0.9.92+):
  Each entry also stores `_conflict_signature` (hash of conflict-relevant
  fields) and `_ks_signature_at_scan` (hash of the keyconfig store at the
  time of last scan). When both match the current state,
  update_entry_external_conflicts() returns early without re-scanning,
  using the cached `*_conflicts_external` lists.
"""

import json
import hashlib

# Bump when conflict-detection logic changes so cached results invalidate.
#   2 — keymap_contexts now included in context resolution for conflict
#       scanning; keyconfigs.user now scanned so user/addon KMIs are visible.
#   3 — Smart Pan conditional operator removed from presets.
#   4 — (prior bump)
#   8 — per-keybind Additional Detection Contexts (keybind-only matching).
#   7 — conflict refs capture all explicitly-set KMI properties.
#   6 — same-op KMIs now always classify as shortcut conflicts (previously
#       same-op+same-key fell into the keybind list).
#   5 — entry-level keymap_contexts no longer treated as a bound context in
#       _km_context_matches_entry (registration never used it; caused false
#       external conflicts + wrong default disables).
_DETECTION_VERSION = "8"

# ---------------------------------------------------------------------------
# Signature helpers (v0.9.92+) — used to skip redundant external scans
# ---------------------------------------------------------------------------

def compute_entry_signature(entry: dict) -> str:
    """Hash of the entry fields that affect external conflict outcomes.

    Whenever any of these change, the entry must be rescanned:
      - operator_ids (string of JSON, contains op IDs + props + per-op context)
      - key, event_type, modifiers (shift/ctrl/alt/oskey/any), key_modifier
      - keymap_contexts (the entry-level context)
      - extra_keybinds (each has its own key + modifiers)

    Note: `enabled` is NOT in the signature — toggling enabled does not
    change WHICH KMIs would conflict, just whether ours are active.
    custom_label is also excluded; it doesn't affect conflicts.
    """
    parts = [
        # Detection-logic version. Bump this whenever conflict-detection rules
        # change (new operator aliases, context-resolution changes, etc.) so
        # that all cached conflict results are invalidated and entries get
        # rescanned with the new logic on next load — without requiring the
        # user to manually press Re-scan.
        _DETECTION_VERSION,
        entry.get("operator_ids", ""),
        entry.get("key", ""),
        entry.get("event_type", ""),
        "S" if entry.get("shift") else "_",
        "C" if entry.get("ctrl") else "_",
        "A" if entry.get("alt") else "_",
        "O" if entry.get("oskey") else "_",
        "Y" if entry.get("any") else "_",
        entry.get("key_modifier", "") or "",
        entry.get("keymap_contexts", "") or "",
    ]
    # Normalize extra_keybinds to a stable string
    extras = entry.get("extra_keybinds", []) or []
    extra_strs = []
    for ex in extras:
        if not isinstance(ex, dict):
            continue
        extra_strs.append("|".join([
            ex.get("key", "") or "",
            ex.get("value", "") or "",
            "S" if ex.get("shift") else "_",
            "C" if ex.get("ctrl") else "_",
            "A" if ex.get("alt") else "_",
            "O" if ex.get("oskey") else "_",
            "Y" if ex.get("any") else "_",
            ex.get("key_modifier", "") or "",
        ]))
    # Sort so order changes don't trigger a rescan if the set is the same
    extra_strs.sort()
    parts.append(";".join(extra_strs))
    raw = "\x1f".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def entry_signatures_match(entry: dict, current_ks_signature: str) -> bool:
    """Return True if the entry's stored conflict signature AND keyconfig
    store signature both match the current state, meaning the cached
    `*_conflicts_external` lists are still valid and a re-scan is unnecessary.
    """
    stored_entry_sig = entry.get("_conflict_signature", "")
    stored_ks_sig    = entry.get("_ks_signature_at_scan", "")
    if not stored_entry_sig or not stored_ks_sig:
        return False
    if stored_ks_sig != current_ks_signature:
        return False
    if compute_entry_signature(entry) != stored_entry_sig:
        return False
    return True


# ---------------------------------------------------------------------------
# Context hierarchy
# Maps each context to the set of broader contexts that "contain" it.
# An entry in "Object Mode" is also active in "3D View" and "Window".
# ---------------------------------------------------------------------------

CONTEXT_ANCESTORS: dict[str, set] = {
    "Window":            set(),
    "Screen":            {"Window"},
    "3D View":           {"Window", "Screen"},
    "Object Mode":       {"Window", "Screen", "3D View"},
    "Mesh":              {"Window", "Screen", "3D View"},
    "Curve":             {"Window", "Screen", "3D View"},
    "Armature":          {"Window", "Screen", "3D View"},
    "Lattice":           {"Window", "Screen", "3D View"},
    "Metaball":          {"Window", "Screen", "3D View"},
    "Font":              {"Window", "Screen", "3D View"},
    "Pose":              {"Window", "Screen", "3D View"},
    "Sculpt":            {"Window", "Screen", "3D View"},
    "Vertex Paint":      {"Window", "Screen", "3D View"},
    "Weight Paint":      {"Window", "Screen", "3D View"},
    "Image Paint":       {"Window", "Screen", "3D View"},
    "Particle":          {"Window", "Screen", "3D View"},
    "Grease Pencil":     {"Window", "Screen", "3D View"},
    "Curves":            {"Window", "Screen", "3D View"},
    "Graph Editor":      {"Window", "Screen"},
    "Dopesheet":         {"Window", "Screen"},
    "NLA Editor":        {"Window", "Screen"},
    "Node Editor":       {"Window", "Screen"},
    "UV Editor":         {"Window", "Screen"},
    "Image":             {"Window", "Screen"},
    "Outliner":          {"Window", "Screen"},
    "Sequencer":         {"Window", "Screen"},
    "Video Sequence Editor": {"Window", "Screen"},
    "Preview":           {"Window", "Screen"},
    "Text":              {"Window", "Screen"},
    "Frames":            {"Window", "Screen"},
}

# Modal contexts never conflict with normal contexts
MODAL_CONTEXTS = {
    "View3D Fly Modal", "View3D Walk Modal", "View3D Rotate Modal",
    "View3D Move Modal", "View3D Zoom Modal", "Knife Tool Modal",
    "Eyedropper Modal", "Transform Modal", "View3D Gesture Circle",
    "Gesture Straight Line", "Gesture Zoom Border",
}

# Event type pairs that can softly conflict (can both fire on same button)
_SOFT_EVENT_PAIRS = {
    frozenset({"PRESS", "CLICK"}),
    frozenset({"PRESS", "DOUBLE_CLICK"}),
    frozenset({"CLICK", "DOUBLE_CLICK"}),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

# Keymaps Blender evaluates for every event, whatever the editor or mode.
# A binding in one of these can fire anywhere, so it overlaps every context.
# "Screen Editing" is deliberately NOT here: Blender does evaluate it
# globally, but every one of its items is spatially gated — area_options /
# area_move / actionzone only fire with the mouse ON an area edge or corner,
# and the rest require synthetic ACTIONZONE_* events. They can never collide
# with an in-editor binding, so treating the keymap as global only produced
# false positives (e.g. every RMB entry "conflicting" with Area Options).
GLOBAL_CONTEXTS = {"Window", "Screen", "User Interface"}


def contexts_overlap(ctx_a: str, ctx_b: str) -> bool:
    """Return True if two contexts can fire in the same situation."""
    if not ctx_a:
        ctx_a = "Window"
    if not ctx_b:
        ctx_b = "Window"
    if ctx_a == ctx_b:
        return True
    # Window/Screen-level bindings are active everywhere. CONTEXT_ANCESTORS is
    # a hand-maintained list and does not name every Blender keymap ("Animation",
    # "Grease Pencil Edit Mode", "Sequencer", ...), so relying on it alone made
    # a global entry silently non-conflicting with anything it did not list.
    if ctx_a in GLOBAL_CONTEXTS or ctx_b in GLOBAL_CONTEXTS:
        return True
    ancestors_a = CONTEXT_ANCESTORS.get(ctx_a, set())
    ancestors_b = CONTEXT_ANCESTORS.get(ctx_b, set())
    return ctx_a in ancestors_b or ctx_b in ancestors_a


def _normalize_props(props: dict) -> str:
    """Canonical sorted JSON for props comparison."""
    if not props:
        return "{}"
    return json.dumps(props, sort_keys=True)


def _ops_match(ops_a: list, ops_b: list) -> tuple:
    """
    Compare two operator lists.
    Returns (exact_match, partial_match).
    exact_match  = all operators+props sets are identical
    partial_match = at least one shared operator+props combination
    Empty props {} only treated as wildcard when the OTHER side also has empty props.
    """
    if not ops_a or not ops_b:
        return False, False

    def _effective_props(op):
        # props_data carries the authoritative full property set (correct types
        # and the values that actually distinguish e.g. view3d.zoom delta 0/1/-1),
        # but it can be PARTIAL (e.g. only {'as_fallback': False}) while the
        # distinguishing prop lives in `props` (e.g. {'name': 'builtin.move'}).
        # Replacing props with props_data collapsed such entries into apparent
        # duplicates (Tool - Move vs Tool - Box Select). MERGE them instead:
        # props_data values win for shared keys, props fills the rest.
        base = dict(op.get("props", {}) or {})
        pd = op.get("props_data")
        if isinstance(pd, dict) and pd:
            base.update(pd)
        return base

    def key_exact(op):
        return (op.get("id", ""), _normalize_props(_effective_props(op)))

    keys_a = {key_exact(o) for o in ops_a}
    keys_b = {key_exact(o) for o in ops_b}
    exact_match   = keys_a == keys_b
    partial_match = bool(keys_a & keys_b)

    # Wildcard: only if both sides have empty props for same op ID
    if not partial_match:
        empty_ids_a = {o.get("id", "") for o in ops_a if not _effective_props(o)}
        empty_ids_b = {o.get("id", "") for o in ops_b if not _effective_props(o)}
        partial_match = bool(empty_ids_a & empty_ids_b)

    return exact_match, partial_match


_all_contexts_cache: dict = {}


def _get_all_contexts(entry: dict) -> list:
    """Content-keyed memo over _get_all_contexts_uncached — the pairwise
    scans call this for both sides of every pair (~n² times); the result
    only depends on the entry fields in the key, so identical content is
    computed once per scan generation. Cleared with the op-context memo."""
    key = (entry.get("entry_id", ""),
           entry.get("operator_ids", ""),
           entry.get("keymap_contexts", "") or "",
           entry.get("context") or "")
    hit = _all_contexts_cache.get(key)
    if hit is not None:
        return hit
    if len(_all_contexts_cache) > 4096:
        _all_contexts_cache.clear()
    res = _get_all_contexts_uncached(entry)
    _all_contexts_cache[key] = res
    return res


def _get_all_contexts_uncached(entry: dict) -> list:
    """
    Return all contexts an entry fires in.
    Multi-operator entries may have different contexts per operator.
    Empty per-operator context is resolved to the operator's real keymap
    (matching how activation registers it), so e.g. view2d.* (View2D) does
    not falsely overlap view3d.* (3D View) just because both were "Window".
    """
    try:
        ops = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        ops = []

    contexts = set()
    for op in ops:
        if isinstance(op, dict):
            multi = op.get("contexts") or []
            if multi:
                for c in multi:
                    contexts.add(c or "Window")
                continue
            ctx = op.get("context", "")
            op_id = op.get("id", "")
        else:
            ctx = ""
            op_id = str(op)
        if not ctx and op_id:
            # Auto context: use EVERY keymap activation would register into,
            # not just the first. _get_keymap_for_op returns one name, but
            # activate_entry registers the op in all of them — so a generic
            # operator (wm.context_toggle spans ~38 keymaps incl. 3D View)
            # was compared against a single arbitrary context and missed
            # real collisions.
            try:
                from .keymap_manager import _get_keymaps_for_op
                _kms = _get_keymaps_for_op(op_id, op if isinstance(op, dict)
                                           else {"id": op_id})
            except Exception:
                _kms = []
            if _kms:
                for _km in _kms:
                    contexts.add(_km or "Window")
                continue
            try:
                from .keymap_manager import _get_keymap_for_op
                ctx = _get_keymap_for_op(op_id)
            except Exception:
                ctx = ""
        contexts.add(ctx or "Window")

    return list(contexts) if contexts else ["Window"]


def _entry_binding_sigs(entry: dict) -> list:
    """All binding signatures of an entry (main + extra keybinds):
    (key, event_type, shift, ctrl, alt, oskey)."""
    sigs = []
    k = entry.get("key", "")
    if k and k != "NONE":
        sigs.append((k, entry.get("event_type", "PRESS"),
                     bool(entry.get("shift")), bool(entry.get("ctrl")),
                     bool(entry.get("alt")), bool(entry.get("oskey"))))
    for ex in entry.get("extra_keybinds", []) or []:
        ek = ex.get("key", "")
        if ek and ek != "NONE":
            sigs.append((ek, ex.get("value", "PRESS"),
                         bool(ex.get("shift")), bool(ex.get("ctrl")),
                         bool(ex.get("alt")), bool(ex.get("oskey"))))
    return sigs


def _op_effective_props(op: dict) -> dict:
    """Merged effective props of an operator item (props_data over props)."""
    base = dict(op.get("props", {}) or {})
    pd = op.get("props_data")
    if isinstance(pd, dict) and pd:
        base.update(pd)
    return base


def _op_contexts(op: dict) -> list:
    """Every keymap an operator item actually registers into. Uses the SAME
    resolver as activation (_op_target_keymaps), so both sides of a comparison
    speak the same context vocabulary."""
    ctxs = list(op.get("contexts") or [])
    if ctxs:
        return [c or "Window" for c in ctxs]
    try:
        from .keymap_manager import _op_target_keymaps

        ctxs = list(_op_target_keymaps(op, op.get("id", "")))
    except Exception:
        ctxs = []
    return [c or "Window" for c in ctxs] or ["Window"]


def internal_conflict_refs(cur_entry: dict, other: dict, ctype: str) -> list:
    """Concrete conflicting bindings between cur_entry and OTHER.

    Each returned ref describes one of the OTHER entry's bindings that actually
    collides with cur_entry, plus `own_ops`: which of CUR_ENTRY's own operators
    it collides with, and in which shared context. Only genuinely overlapping
    (operator, context) pairs are reported — an operator of `other` that shares
    no context with any operator of `cur_entry` is NOT a conflict and is
    omitted. (Previously a mismatch between two different context resolvers made
    the overlap test fail and fall back to listing EVERY operator, which is how
    e.g. Duplicate's Markers-only marker.duplicate showed up against Duplicate
    Move.)
    """
    try:
        o_ops = [o for o in json.loads(other.get("operator_ids", "[]"))
                 if isinstance(o, dict) and o.get("id")]
    except Exception:
        o_ops = []
    try:
        e_ops = [o for o in json.loads(cur_entry.get("operator_ids", "[]"))
                 if isinstance(o, dict) and o.get("id")]
    except Exception:
        e_ops = []

    e_sigs = set(_entry_binding_sigs(cur_entry))
    o_sigs = _entry_binding_sigs(other)

    if ctype == "key_conflict":
        # Only the keybinds the two entries actually share can collide.
        use_sigs = [s for s in o_sigs if s in e_sigs]
    else:  # op_overlap — same operator+props, whatever the keybinds
        use_sigs = o_sigs

    # Pre-resolve cur_entry's operators to their contexts.
    e_resolved = [(o.get("id"), _op_effective_props(o), _op_contexts(o))
                  for o in e_ops]

    refs = []
    seen = set()
    for op in o_ops:
        op_id = op.get("id", "")
        op_props = _op_effective_props(op)
        o_ctxs = _op_contexts(op)

        # Which of OUR operators does this one actually collide with?
        # contexts_overlap() is ancestor-aware on purpose (a 3D View binding
        # DOES shadow Mesh/Curve/Armature mode), so it decides IF they collide —
        # but the ref is reported under the OTHER operator's OWN keymap, never
        # under a descendant it merely shadows. Otherwise armature.duplicate
        # (which lives in 3D View) would be listed as living in Curve, Mesh, ...
        own_ops = []
        for (e_id, e_props, e_ctxs) in e_resolved:
            if ctype != "key_conflict":
                # op_overlap: only the SAME operator (id + props) counts.
                if e_id != op_id or e_props != op_props:
                    continue
            if any(contexts_overlap(ec, oc) for ec in e_ctxs for oc in o_ctxs):
                if e_id not in own_ops:
                    own_ops.append(e_id)
        if not own_ops:
            continue  # no shared context with any of our operators — not a conflict

        for ctx in o_ctxs:
            for (k, ev, sh, ct, al, os_) in use_sigs:
                fp = (op_id, ctx, k, ev, sh, ct, al, os_)
                if fp in seen:
                    continue
                seen.add(fp)
                refs.append({
                    "op_id": op_id,
                    "keymap_name": ctx,
                    "key": k,
                    "event_type": ev,
                    "shift": sh, "ctrl": ct, "alt": al, "oskey": os_,
                    "props": op.get("props", {}) or {},
                    # Our own operators that collide with this ref.
                    "own_ops": own_ops,
                })
    return refs


def _norm_key_modifier(v) -> str:
    """"" and "NONE" both mean *no* key modifier.

    Blender's KMI reports "NONE", saved entries store "" — comparing them
    literally made an otherwise-identical binding look different (which hid
    conflicts for keybinds built from live KMI state).
    """
    v = (v or "").strip()
    return "" if v in {"", "NONE"} else v


def _binding_dicts(entry: dict) -> list:
    """Every binding of an entry (primary + extras) as comparable dicts.

    key_matches() compares one binding at a time, so callers that must
    consider ALL of an entry's keybinds iterate over these.
    """
    out = []
    k = entry.get("key", "")
    if k and k != "NONE":
        out.append({
            "key": k,
            "event_type": entry.get("event_type", "PRESS"),
            "key_modifier": _norm_key_modifier(entry.get("key_modifier")),
            "any": bool(entry.get("any")),
            "shift": bool(entry.get("shift")),
            "ctrl": bool(entry.get("ctrl")),
            "alt": bool(entry.get("alt")),
            "oskey": bool(entry.get("oskey")),
        })
    for ex in entry.get("extra_keybinds", []) or []:
        ek = ex.get("key", "")
        if ek and ek != "NONE":
            out.append({
                "key": ek,
                "event_type": ex.get("value", ex.get("event_type", "PRESS")),
                "key_modifier": _norm_key_modifier(ex.get("key_modifier")),
                "any": bool(ex.get("any")),
                "shift": bool(ex.get("shift")),
                "ctrl": bool(ex.get("ctrl")),
                "alt": bool(ex.get("alt")),
                "oskey": bool(ex.get("oskey")),
            })
    return out


def any_key_matches(entry_a: dict, entry_b: dict) -> bool:
    """True if ANY binding of A matches ANY binding of B."""
    b_binds = _binding_dicts(entry_b)
    for a in _binding_dicts(entry_a):
        for b in b_binds:
            if key_matches(a, b):
                return True
    return False


def key_matches(entry_a: dict, entry_b: dict) -> bool:
    """
    Return True if two entries use the same effective keybinding.
    Handles any=True modifier wildcard and key_modifier field.
    """
    if entry_a.get("key") != entry_b.get("key"):
        return False
    if entry_a.get("event_type", "PRESS") != entry_b.get("event_type", "PRESS"):
        return False
    if (_norm_key_modifier(entry_a.get("key_modifier"))
            != _norm_key_modifier(entry_b.get("key_modifier"))):
        return False

    any_a = entry_a.get("any", False)
    any_b = entry_b.get("any", False)
    if any_a or any_b:
        return True

    return (entry_a.get("shift") == entry_b.get("shift") and
            entry_a.get("ctrl")  == entry_b.get("ctrl")  and
            entry_a.get("alt")   == entry_b.get("alt")   and
            entry_a.get("oskey") == entry_b.get("oskey"))


def key_matches_ignoring_event(entry_a: dict, entry_b: dict) -> bool:
    """Same as key_matches but ignores event_type — for soft event detection."""
    if entry_a.get("key") != entry_b.get("key"):
        return False
    if entry_a.get("key_modifier", "") != entry_b.get("key_modifier", ""):
        return False
    any_a = entry_a.get("any", False)
    any_b = entry_b.get("any", False)
    if any_a or any_b:
        return True
    return (entry_a.get("shift") == entry_b.get("shift") and
            entry_a.get("ctrl")  == entry_b.get("ctrl")  and
            entry_a.get("alt")   == entry_b.get("alt")   and
            entry_a.get("oskey") == entry_b.get("oskey"))


def classify_conflict(entry_a: dict, entry_b: dict) -> str | None:
    """
    Compare two Keymapper entries.
    Returns conflict type string or None.
    entry_a is assumed to be registered BEFORE entry_b (wins on key conflict).
    """
    # Skip modal contexts
    ctxs_a = _get_all_contexts(entry_a)
    ctxs_b = _get_all_contexts(entry_b)

    if all(c in MODAL_CONTEXTS for c in ctxs_a):
        return None
    if all(c in MODAL_CONTEXTS for c in ctxs_b):
        return None

    # Check if any context pairs overlap
    ctx_overlap = any(
        contexts_overlap(ca, cb)
        for ca in ctxs_a
        for cb in ctxs_b
    )
    if not ctx_overlap:
        return None

    # Parse operators
    try:
        ops_a = json.loads(entry_a.get("operator_ids", "[]"))
        ops_b = json.loads(entry_b.get("operator_ids", "[]"))
    except Exception:
        return None

    # Compare EVERY binding on both sides: an entry's second keybind can
    # collide just as its first does, and comparing only the primaries meant
    # extra keybinds were silently excluded from conflict detection.
    same_key  = any_key_matches(entry_a, entry_b)
    exact_ops, partial_ops = _ops_match(ops_a, ops_b)

    # Duplicate — everything identical
    if same_key and exact_ops:
        return "duplicate"

    # Key conflict — same key + context overlap, different operators
    if same_key and not exact_ops:
        return "key_conflict"

    # Operator overlap — same operators + context overlap, different key
    if not same_key and partial_ops:
        return "op_overlap"

    # Soft event conflict — same key+mods, same context, different event type
    for _ba in _binding_dicts(entry_a):
        for _bb in _binding_dicts(entry_b):
            _ea = _ba.get("event_type", "PRESS")
            _eb = _bb.get("event_type", "PRESS")
            if (frozenset({_ea, _eb}) in _SOFT_EVENT_PAIRS
                    and key_matches_ignoring_event(_ba, _bb)):
                return "event_soft"

    return None


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------

def _entry_conflict_mode(entry: dict) -> str:
    """How this entry participates in conflict detection.

    'full'          — normal keybind entry: all conflict types.
    'shortcut_only' — button-only entry with detection enabled: same-operator
                      (shortcut) conflicts only, never keybind conflicts (it
                      has no live keybind to clash).
    'none'          — button-only entry with detection off (the default for
                      button-only): excluded from conflict detection entirely.
    """
    if entry.get("use_keybind", True):
        return "full"
    if entry.get("button_conflict_detection", False):
        return "shortcut_only"
    return "none"


# Conflict types that involve the KEYBIND (vs. same-operator overlap).
_KEYBIND_CONFLICT_TYPES = {"duplicate", "key_conflict", "event_soft"}


def scan_internal_conflicts(entries: list) -> dict:
    """
    Scan all entries pairwise.
    Returns { entry_id: [{"type": str, "with": entry_id, "wins": bool}, ...] }
    Skips disabled entries for key_conflict/duplicate but still checks op_overlap.
    Button-only entries participate per _entry_conflict_mode.
    """
    result = {e["entry_id"]: [] for e in entries}

    for i, ea in enumerate(entries):
        for j, eb in enumerate(entries[i + 1:], start=i + 1):

            mode_a = _entry_conflict_mode(ea)
            mode_b = _entry_conflict_mode(eb)
            if mode_a == "none" or mode_b == "none":
                continue

            conflict_type = classify_conflict(ea, eb)
            if not conflict_type:
                continue

            # A button-only participant can only have shortcut (same-op)
            # conflicts — its stored key fields aren't live keybinds.
            if "shortcut_only" in (mode_a, mode_b):
                if conflict_type in _KEYBIND_CONFLICT_TYPES:
                    conflict_type = "op_overlap"

            # Disabled entries: only flag op_overlap (softer), skip hard conflicts
            ea_enabled = ea.get("enabled", True)
            eb_enabled = eb.get("enabled", True)
            if not (ea_enabled and eb_enabled):
                if conflict_type in ("duplicate", "key_conflict", "event_soft"):
                    conflict_type = "op_overlap"  # downgrade to softest

            result[ea["entry_id"]].append({
                "type":  conflict_type,
                "with":  eb["entry_id"],
                "wins":  True,   # ea is registered first
            })
            result[eb["entry_id"]].append({
                "type":  conflict_type,
                "with":  ea["entry_id"],
                "wins":  False,  # eb is registered second — may not fire
            })

    return result


def update_entry_conflicts(entries: list) -> None:
    """
    Run scan and write results back onto each entry in-place.
    Called after any add/edit/delete/duplicate operation.
    """
    # Clear first to prevent stale data from persisting
    for entry in entries:
        entry["internal_conflicts"] = []
    conflict_map = scan_internal_conflicts(entries)
    for entry in entries:
        entry["internal_conflicts"] = conflict_map.get(entry["entry_id"], [])


# Convenience: get the most severe conflict type for an entry
_SEVERITY = {
    "duplicate":    4,
    "key_conflict": 3,
    "event_soft":   2,
    "op_overlap":   1,
}


def get_worst_conflict(entry: dict) -> tuple | None:
    """
    Return (conflict_type, wins) for the most severe conflict on this entry,
    or None if no conflicts.
    """
    conflicts = entry.get("internal_conflicts", [])
    if not conflicts:
        return None
    worst = max(conflicts, key=lambda c: _SEVERITY.get(c["type"], 0))
    return worst["type"], worst["wins"]


# ---------------------------------------------------------------------------
# Inert-duplicate detection
#
# An entry that is 100% identical to an EARLIER entry (same operators+props,
# same binding, overlapping context) is an "inert duplicate": it registers no
# KMIs and cannot be enabled, because its KMIs would be indistinguishable from
# the earlier entry's and a later delete couldn't tell them apart. The earliest
# entry in such a group is the canonical one and stays active. This is computed
# LIVE from the current entry list (no stored flag), so editing an entry so it
# is no longer identical immediately makes it a normal entry again.
# ---------------------------------------------------------------------------

def _dup_cheap_sig(e: dict) -> tuple:
    """Fields a 100%-identical duplicate MUST share verbatim — a fast
    discriminator so the expensive classify_conflict only runs on plausible
    twins."""
    try:
        op_ids = tuple(sorted(
            o.get("id", "") for o in json.loads(
                e.get("operator_ids", "[]"))))
    except Exception:
        op_ids = ("?",)
    return (e.get("key"), e.get("event_type"), bool(e.get("shift")),
            bool(e.get("ctrl")), bool(e.get("alt")), bool(e.get("oskey")),
            bool(e.get("any")), e.get("key_modifier") or "",
            len(e.get("extra_keybinds") or []), op_ids)


def has_potential_duplicates(entries: list) -> bool:
    """True when any two entries share the cheap duplicate signature — the
    only case in which reordering can change inert-duplicate status."""
    seen = set()
    for e in entries:
        s = _dup_cheap_sig(e)
        if s in seen:
            return True
        seen.add(s)
    return False


def reorder_update_conflicts(entries: list) -> None:
    """After a PURE reorder: which pairs conflict is content-based and
    unchanged — only the order-derived "wins" flags can flip. Recompute
    them from the new indices without any classification."""
    idx = {e.get("entry_id"): i for i, e in enumerate(entries)}
    for e in entries:
        my = idx.get(e.get("entry_id"), 0)
        for ref in (e.get("internal_conflicts") or []):
            ref["wins"] = my < idx.get(ref.get("with"), 1 << 30)


def get_identical_twin(entry: dict, entries: list) -> dict | None:
    """Return the earliest entry that `entry` is 100% identical to AND that
    appears before it in the list, or None. If non-None, `entry` is an inert
    duplicate of the returned twin. Independent of enabled state.
    """
    eid = entry.get("entry_id")
    sig = _dup_cheap_sig(entry)
    for other in entries:
        if other.get("entry_id") == eid:
            break  # reached self; only earlier entries count as the canonical twin
        try:
            if _dup_cheap_sig(other) != sig:
                continue
            if classify_conflict(entry, other) == "duplicate":
                return other
        except Exception:
            continue
    return None


def is_inert_duplicate(entry: dict, entries: list = None) -> bool:
    """True if `entry` is a 100%-identical duplicate of an earlier entry."""
    if entries is None:
        try:
            from . import persistence
            entries = persistence.get_entries()
        except Exception:
            return False
    return get_identical_twin(entry, entries) is not None


# ---------------------------------------------------------------------------
# Unregistered-operator detection
#
# An entry can reference an operator that is no longer registered — e.g. the
# addon that provided it was disabled/uninstalled, or the entry was imported
# from a newer/older Blender where the op existed. We must NOT create KMIs for
# those ops (they'd be dead bindings), but everything else about the entry
# (conflict detection, other ops) keeps working. Detection is intentionally
# only run on full re-scan and on import — not every redraw — and the result
# is cached on the entry as `unregistered_ops`.
# ---------------------------------------------------------------------------

def is_operator_registered(op_id: str) -> bool:
    """True if `op_id` (module.func) resolves to a live, registered operator.

    Keymapper's own bundled ops (keymapper.op_*) are always registered by the
    addon itself, so they're treated as valid without probing.
    """
    if not op_id or "." not in op_id:
        return False
    if op_id.startswith("keymapper."):
        return True
    import bpy
    module, func = op_id.split(".", 1)
    try:
        op = getattr(getattr(bpy.ops, module), func)
        op.get_rna_type()  # raises if the operator is not registered
        return True
    except Exception:
        return False


def get_unregistered_ops(entry: dict) -> list:
    """Return the list of op ids in `entry` that are not currently registered."""
    try:
        ops = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        return []
    missing = []
    for op in ops:
        op_id = op.get("id", "") if isinstance(op, dict) else str(op)
        if op_id and not is_operator_registered(op_id):
            missing.append(op_id)
    return missing


def op_source_hint(op_id: str) -> str:
    """Best-effort description of where an op came from, for user messaging.

    If the op's class is still around (rare for a truly-missing op) and belongs
    to an enabled addon, name the addon. Otherwise fall back to the module
    prefix (e.g. "mesh.*"), which is all we can know for an op whose addon is
    disabled or whose op no longer exists in this Blender version.
    """
    module = op_id.split(".")[0] if "." in op_id else op_id
    try:
        import bpy
        from .operator_discovery import _get_op_addon_name, _get_enabled_addon_names

        parts = op_id.split(".")
        if len(parts) >= 2:
            cls = getattr(
                bpy.types, f"{parts[0].upper()}_OT_{parts[1]}", None)
            if cls is not None:
                addon = _get_op_addon_name(
                    op_id, None, _get_enabled_addon_names())
                if addon:
                    return f"the '{addon}' add-on"
    except Exception:
        pass
    return f"the '{module}' module"


def update_unregistered_ops(entries: list = None) -> None:
    """Recompute and cache each entry's `unregistered_ops`.

    Called ONLY from the full re-scan and the import path — never per redraw.
    """
    if entries is None:
        try:
            from . import persistence
            entries = persistence.get_entries()
        except Exception:
            return
    for entry in entries:
        entry["unregistered_ops"] = get_unregistered_ops(entry)


# ---------------------------------------------------------------------------
# External conflict detection — Blender default keymap
# ---------------------------------------------------------------------------

def _get_default_keyconfig():
    """Return the default Blender keyconfig."""
    import bpy
    # .default is always the built-in keymap regardless of active config
    kc = bpy.context.window_manager.keyconfigs.default
    if kc:
        return kc
    for name in ("Blender", "BForArtists", "blender"):
        kc = bpy.context.window_manager.keyconfigs.get(name)
        if kc:
            return kc
    return None


def _event_types_conflict(entry_val: str, kmi_val: str) -> bool:
    """Whether an entry's event type should be treated as conflicting with a
    KMI's event type (for the purpose of disabling that default).

    "ANY" matches everything. Otherwise exact match — EXCEPT a CLICK_DRAG entry
    also suppresses tap-style defaults (PRESS / CLICK) on the same button, since
    a drag binding logically takes over that button and the click/press default
    would otherwise still fire on a plain tap. This is one-directional: a PRESS
    or CLICK entry does NOT conflict with a DRAG default.
    """
    if entry_val == "ANY" or kmi_val == "ANY":
        return True
    if entry_val == kmi_val:
        return True
    # Cross-value matches come from the per-value override matrix in the
    # preferences (e.g. Click Drag over Press/Click, Click over Press),
    # gated by the "different action values" master toggle.
    try:
        from .preferences import get_prefs, kbcv_prop_name
        prefs = get_prefs()
        if not prefs.keybind_conflicts_cross_value:
            return False
        return bool(getattr(prefs, kbcv_prop_name(entry_val, kmi_val), False))
    except Exception:
        pass
    return False


def _kmi_key_matches_entry(kmi, entry: dict) -> bool:
    """Check if a KMI's key binding can conflict with an entry's key binding."""
    if kmi.type != entry.get("key", ""):
        return False
    if not _event_types_conflict(entry.get("event_type", "PRESS"), kmi.value):
        return False
    # kmi.any=True means the KMI fires regardless of modifier state → always a conflict
    if kmi.any:
        return True
    if entry.get("any", False):
        return True
    # Exact modifier match
    return (kmi.shift == bool(entry.get("shift",  False)) and
            kmi.ctrl  == bool(entry.get("ctrl",   False)) and
            kmi.alt   == bool(entry.get("alt",    False)) and
            kmi.oskey == bool(entry.get("oskey",  False)))


# Operator aliases — treat these as equivalent for conflict detection
_OP_ALIASES: dict[str, str] = {
    "view3d.pan":    "view3d.move",
    "view3d.move":   "view3d.move",
}


# Operators that are disambiguated by a specific property — same op_id but
# different prop values mean completely different actions, so we require prop match.
def _norm_data_path(v: str) -> str:
    """wm.context_* data_paths: "scene.tool_settings.X" and
    "tool_settings.X" resolve to the SAME setting (context.tool_settings is
    an alias of context.scene.tool_settings), so the leading "scene." is
    stripped before identity comparison — a preset stored one spelling while
    the factory keymaps use the other, which silently defeated adoption and
    shortcut-conflict matching for those entries."""
    v = str(v)
    return v[6:] if v.startswith("scene.") else v


_PROP_DISAMBIGUATED_OPS: dict[str, str] = {
    "wm.context_toggle":        "data_path",
    "wm.context_set_boolean":   "data_path",
    "wm.context_set_enum":      "data_path",
    "wm.context_set_int":       "data_path",
    "wm.context_set_float":     "data_path",
    "wm.context_set_value":     "data_path",
    "wm.context_toggle_enum":   "data_path",
    "wm.call_menu":             "name",
    "wm.call_menu_pie":         "name",
    "wm.call_panel":            "name",
    "wm.tool_set_by_id":        "name",
}


def _canonical_op(op_id: str) -> str:
    """Return canonical operator ID for alias resolution."""
    return _OP_ALIASES.get(op_id, op_id)


def _kmi_op_matches_entry(kmi, entry: dict) -> bool:
    """Check if a KMI's operator matches any operator in an entry."""
    try:
        ops = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        return False
    kmi_canonical = _canonical_op(kmi.idname)
    for op in ops:
        if _canonical_op(op.get("id", "")) != kmi_canonical:
            continue
        # For disambiguated operators, also compare the key property
        key_prop = _PROP_DISAMBIGUATED_OPS.get(kmi.idname)
        if key_prop:
            entry_props = op.get("props", {})
            if isinstance(entry_props, str):
                try:
                    entry_props = json.loads(entry_props)
                except Exception:
                    entry_props = {}
            entry_val = entry_props.get(key_prop, "")
            try:
                kmi_val = getattr(kmi.properties, key_prop, "")
            except Exception:
                kmi_val = ""
            if (entry_val and kmi_val
                    and _norm_data_path(entry_val)
                    != _norm_data_path(kmi_val)):
                continue  # different target — not a match
        if not _shortcut_cross_props():
            kmi_props = {}
            try:
                # GUARD: dangling props RNA for unregistered ops segfaults.
                if kmi.properties and is_operator_registered(kmi.idname):
                    for p in kmi.properties.bl_rna.properties:
                        if p.identifier == "rna_type":
                            continue
                        if kmi.properties.is_property_set(p.identifier):
                            kmi_props[p.identifier] = str(
                                getattr(kmi.properties, p.identifier, ""))
            except Exception:
                pass
            if _entry_op_props_strict(op) != kmi_props:
                continue  # property values differ — not a match with pref off
        return True
    return False


# Keymap names that are children of "3D View" context
_3D_VIEW_KEYMAPS = {
    "3D View", "3D View Generic", "Object Mode", "Mesh", "Curve", "Armature",
    "Lattice", "Metaball", "Font", "Pose", "Sculpt", "Vertex Paint",
    "Weight Paint", "Image Paint", "Particle", "Grease Pencil", "Curves",
    "Paint Face Mask", "Paint Vertex Selection", "Paint Weight Selection",
    "Curve Pen", "Object Non-modal",
}


_resolve_op_contexts_cache: dict = {}


def _clear_resolve_cache():
    _resolve_op_contexts_cache.clear()
    _all_contexts_cache.clear()


def _resolve_op_contexts(op_id: str) -> set:
    """Find which keymap contexts an operator lives in, using the store if
    available. Memoized per op_id for the duration of a scan pass."""
    cached = _resolve_op_contexts_cache.get(op_id)
    if cached is not None:
        return cached
    from . import keyconfig_store as _ks
    if _ks.is_scanned():
        result = _ks.get_keymap_names_for_op(op_id)
    else:
        import bpy
        result = set()
        wm = bpy.context.window_manager
        for kc in (wm.keyconfigs.default, wm.keyconfigs.active):
            if not kc:
                continue
            for km in kc.keymaps:
                if km.name in MODAL_CONTEXTS:
                    continue
                for kmi in km.keymap_items:
                    if kmi.idname == op_id:
                        result.add(km.name)
                        break
    _resolve_op_contexts_cache[op_id] = result
    return result


def _km_context_matches_entry(km_name: str, entry: dict) -> bool:
    """Check if a keymap should be scanned for conflicts against an entry.

    The rule:
      - A keymap matches if it overlaps any of the entry's bound contexts
        (selected per-operator context, entry-level keymap_contexts, or — when
        nothing is explicitly selected — the operator's natural home keymaps).
      - EXCEPTION: a keymap is suppressed if it is one of the operator's own
        "natural home" keymaps that the user did NOT select. Example: view2d.pan
        naturally lives in both "View2D" and "View2D Buttons List". If the user
        bound it to "View2D" only, we must not flag conflicts in "View2D Buttons
        List" — but we still flag conflicts in unrelated contexts like "Frames".
    """
    try:
        ops = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        ops = []

    # The effective context an operator is bound to: the user's explicit
    # selection if any, otherwise the auto-resolved keymap (what the UI shows as
    # "Context: Auto (X)" and what activation registers into).
    effective_contexts = set()
    for op in ops:
        if not isinstance(op, dict):
            continue
        # Mirror registration priority (_op_target_keymaps): an explicit
        # `contexts` list wins, then the legacy single `context` string, then
        # the operator's auto-resolved home keymaps. Reading only `context`
        # here missed user multi/single selections stored in `contexts`, so a
        # Window selection would fall through to auto (e.g. 3D View) and never
        # flag conflicts in Window-overlapping keymaps like Frames.
        ctxs = op.get("contexts") or []
        if ctxs:
            for c in ctxs:
                if c:
                    effective_contexts.add(c)
            continue
        ctx = op.get("context", "")
        if ctx:
            effective_contexts.add(ctx)
        else:
            op_id = op.get("id", "")
            if op_id:
                try:
                    from .keymap_manager import _get_keymaps_for_op
                    for auto in _get_keymaps_for_op(op_id):
                        if auto:
                            effective_contexts.add(auto)
                except Exception:
                    pass
    # NOTE: entry-level `keymap_contexts` is deliberately NOT included. It is
    # form scratch state; registration (keymap_manager) never reads it, so
    # including it flagged — and disabled — defaults in keymaps the entry never
    # registers into (e.g. a View2D pan entry claiming 3D View MMB defaults
    # via a stale "Object Mode" value).

    # All natural-home keymaps for the entry's operators.
    natural_homes = set()
    for op in ops:
        op_id = op.get("id", "") if isinstance(op, dict) else ""
        if op_id:
            natural_homes.update(_resolve_op_contexts(op_id))

    # Suppress a keymap only if it's one of the operator's OTHER natural homes —
    # a sibling keymap the operator could live in but that isn't the effective
    # (selected or auto-resolved) context. This filters out e.g. "View2D Buttons
    # List" for a pan bound to "View2D", while still allowing conflicts from
    # unrelated contexts like "Frames".
    if km_name in natural_homes and km_name not in effective_contexts:
        return False

    entry_contexts = set(effective_contexts)
    if not entry_contexts:
        entry_contexts.add("Window")

    for entry_ctx in entry_contexts:
        if contexts_overlap(km_name, entry_ctx):
            return True
        if entry_ctx in _3D_VIEW_KEYMAPS and km_name in _3D_VIEW_KEYMAPS:
            return True
    return False


def _make_kmi_ref(km, kmi) -> dict:
    """Build a serialisable reference to a default KMI for later restore."""
    ref = {
        "keymap_name": km.name,
        "op_id":       kmi.idname,
        "key":         kmi.type,
        "event_type":  kmi.value,
        "shift":       kmi.shift,
        "ctrl":        kmi.ctrl,
        "alt":         kmi.alt,
        "oskey":       kmi.oskey,
        "active":      kmi.active,
    }
    props = {}
    try:
        # GUARD: dangling props RNA for unregistered ops segfaults.
        if kmi.properties and is_operator_registered(kmi.idname):
            for p in kmi.properties.bl_rna.properties:
                if p.identifier == "rna_type":
                    continue
                if kmi.properties.is_property_set(p.identifier):
                    props[p.identifier] = str(getattr(kmi.properties, p.identifier, ""))
    except Exception:
        pass
    key_prop = _PROP_DISAMBIGUATED_OPS.get(kmi.idname)
    if key_prop and key_prop not in props:
        try:
            props[key_prop] = str(getattr(kmi.properties, key_prop, ""))
        except Exception:
            pass
    if props:
        ref["props"] = props
    return ref


def _entry_matching_keymaps(entry: dict, store_keys) -> tuple:
    """Compute (matching_km_names, detect_only_km_names) for an entry ONCE,
    instead of re-deriving the entry's context set for every keymap.

    Hoists the JSON parse, auto-context resolution, and natural-home
    computation out of the per-keymap loop — the dominant rescan cost.
    """
    try:
        ops = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        ops = []

    effective_contexts = set()
    natural_homes = set()
    for op in ops:
        if not isinstance(op, dict):
            continue
        op_id = op.get("id", "")
        ctxs = op.get("contexts") or []
        if ctxs:
            effective_contexts.update(c for c in ctxs if c)
        elif op.get("context"):
            effective_contexts.add(op["context"])
        elif op_id:
            try:
                from .keymap_manager import _get_keymaps_for_op
                effective_contexts.update(c for c in _get_keymaps_for_op(op_id) if c)
            except Exception:
                pass
        if op_id:
            natural_homes.update(_resolve_op_contexts(op_id))

    entry_contexts = set(effective_contexts) or {"Window"}
    detect_ctxs = set(entry.get("detect_contexts") or [])

    matching = set()
    detect_only = set()
    for km_name in store_keys:
        if km_name in MODAL_CONTEXTS:
            continue
        # Suppress a sibling natural-home the user didn't select.
        if km_name in natural_homes and km_name not in effective_contexts:
            ctx_match = False
        else:
            ctx_match = False
            for entry_ctx in entry_contexts:
                if contexts_overlap(km_name, entry_ctx):
                    ctx_match = True
                    break
                if (entry_ctx in _3D_VIEW_KEYMAPS
                        and km_name in _3D_VIEW_KEYMAPS):
                    ctx_match = True
                    break
        if ctx_match:
            matching.add(km_name)
        elif km_name in detect_ctxs:
            detect_only.add(km_name)
    return matching, detect_only


def scan_external_conflicts(entry: dict) -> dict:
    """
    Scan for conflicts with a single Keymapper entry using the keyconfig store.
    Falls back to live scan if store is not available.
    Button-only entries: no scan when detection is off; shortcut (same-op)
    conflicts only when detection is on (informational — no defaults are
    disabled since the entry registers no KMIs).
    """
    mode = _entry_conflict_mode(entry)
    if mode == "none":
        return {"shortcut_conflicts_external": [],
                "keybind_conflicts_external": []}

    from . import keyconfig_store as _ks

    if _ks.is_scanned():
        result = _scan_from_store(entry, _ks)
    else:
        result = _scan_live(entry)
    if mode == "shortcut_only":
        result["keybind_conflicts_external"] = []
    return result


def _scan_from_store(entry: dict, ks) -> dict:
    """Fast conflict scan using the pre-built keyconfig store."""
    shortcut_conflicts = []
    keybind_conflicts  = []
    seen_kmis = set()

    store = ks.get_store()
    matching_kms, detect_only_kms = _entry_matching_keymaps(entry, store.keys())
    for km_name in matching_kms | detect_only_kms:
        kmi_list = store.get(km_name)
        if not kmi_list:
            continue
        detect_only = km_name in detect_only_kms and km_name not in matching_kms
        for kmi_dict in kmi_list:
            kmi_uid = (km_name, kmi_dict["op_id"], kmi_dict["key"],
                       kmi_dict["value"], kmi_dict["shift"], kmi_dict["ctrl"],
                       kmi_dict["alt"], kmi_dict["oskey"])
            if kmi_uid in seen_kmis:
                continue
            same_op  = _op_matches_entry_dict(kmi_dict, entry)
            same_key = _key_matches_entry_dict(kmi_dict, entry)
            if detect_only:
                # Detection-only context: same-key defaults only, always
                # classified as keybind conflicts.
                if not same_key:
                    continue
                same_op = False
            elif not same_op and not same_key:
                continue
            seen_kmis.add(kmi_uid)
            ref = {
                "keymap_name": km_name,
                "op_id":       kmi_dict["op_id"],
                "key":         kmi_dict["key"],
                "event_type":  kmi_dict["value"],
                "shift":       kmi_dict["shift"],
                "ctrl":        kmi_dict["ctrl"],
                "alt":         kmi_dict["alt"],
                "oskey":       kmi_dict["oskey"],
                "active":      kmi_dict.get("active", True),
                "props":       kmi_dict.get("props", {}),
                "source":      kmi_dict.get("source", "factory"),
            }
            if same_op:  # same op is a shortcut conflict even when the key also matches
                shortcut_conflicts.append(ref)
            else:
                keybind_conflicts.append(ref)

    return {
        "shortcut_conflicts_external": shortcut_conflicts,
        "keybind_conflicts_external":  keybind_conflicts,
    }


def _entry_op_props_strict(op) -> dict:
    """Entry op's effective props as a str->str dict (props_data authoritative)."""
    pd = op.get("props_data") or {}
    if isinstance(pd, str):
        try:
            pd = json.loads(pd)
        except Exception:
            pd = {}
    if not pd:
        pd = op.get("props") or {}
        if isinstance(pd, str):
            try:
                pd = json.loads(pd)
            except Exception:
                pd = {}
    return ({str(k): str(v) for k, v in pd.items()}
            if isinstance(pd, dict) else {})


def _shortcut_cross_props() -> bool:
    """Pref: also match same-op defaults whose property values differ."""
    try:
        from .preferences import get_prefs
        return bool(get_prefs().shortcut_conflicts_cross_props)
    except Exception:
        return True


def _op_matches_entry_dict(kmi_dict: dict, entry: dict) -> bool:
    """Check if a stored KMI dict's operator matches any operator in an entry."""
    try:
        ops = json.loads(entry.get("operator_ids", "[]"))
    except Exception:
        return False
    kmi_canonical = _canonical_op(kmi_dict["op_id"])
    for op in ops:
        if _canonical_op(op.get("id", "")) != kmi_canonical:
            continue
        key_prop = _PROP_DISAMBIGUATED_OPS.get(kmi_dict["op_id"])
        if key_prop:
            entry_props = op.get("props", {})
            if isinstance(entry_props, str):
                try:
                    entry_props = json.loads(entry_props)
                except Exception:
                    entry_props = {}
            entry_val = str(entry_props.get(key_prop, ""))
            kmi_val   = str((kmi_dict.get("props") or {}).get(key_prop, ""))
            if (entry_val and kmi_val
                    and _norm_data_path(entry_val)
                    != _norm_data_path(kmi_val)):
                continue
        if not _shortcut_cross_props():
            kmi_props = {str(k): str(v)
                         for k, v in (kmi_dict.get("props") or {}).items()}
            if _entry_op_props_strict(op) != kmi_props:
                continue  # property values differ — not a match with pref off
        return True
    return False


def _key_matches_entry_dict(kmi_dict: dict, entry: dict) -> bool:
    """Check if a stored KMI dict's key binding conflicts with an entry."""
    if kmi_dict["key"] != entry.get("key", ""):
        return False
    if not _event_types_conflict(entry.get("event_type", "PRESS"), kmi_dict["value"]):
        return False
    if kmi_dict.get("any", False):
        return True
    if entry.get("any", False):
        return True
    return (kmi_dict["shift"] == bool(entry.get("shift",  False)) and
            kmi_dict["ctrl"]  == bool(entry.get("ctrl",   False)) and
            kmi_dict["alt"]   == bool(entry.get("alt",    False)) and
            kmi_dict["oskey"] == bool(entry.get("oskey",  False)))


def _scan_live(entry: dict) -> dict:
    """Fallback: scan live keymaps when no store is available."""
    import bpy
    wm = bpy.context.window_manager
    kcs = []
    kc_default = wm.keyconfigs.default
    kc_active  = wm.keyconfigs.active
    if kc_default:
        kcs.append(kc_default)
    if kc_active and kc_active != kc_default:
        kcs.append(kc_active)

    shortcut_conflicts = []
    keybind_conflicts  = []
    seen_kmis = set()

    detect_ctxs = set(entry.get("detect_contexts") or [])
    for kc in kcs:
        for km in kc.keymaps:
            if km.name in MODAL_CONTEXTS:
                continue
            ctx_match = _km_context_matches_entry(km.name, entry)
            detect_only = (not ctx_match) and km.name in detect_ctxs
            if not ctx_match and not detect_only:
                continue
            for kmi in km.keymap_items:
                if not kmi.idname:
                    continue
                if kmi.idname.startswith("keymapper."):
                    continue
                kmi_uid = (km.name, kmi.idname, kmi.type, kmi.value,
                           kmi.shift, kmi.ctrl, kmi.alt, kmi.oskey)
                if kmi_uid in seen_kmis:
                    continue
                same_op  = _kmi_op_matches_entry(kmi, entry)
                same_key = _kmi_key_matches_entry(kmi, entry)
                if detect_only:
                    if not same_key:
                        continue
                    same_op = False
                elif not same_op and not same_key:
                    continue
                seen_kmis.add(kmi_uid)
                ref = _make_kmi_ref(km, kmi)
                if same_op:  # same op is a shortcut conflict even when the key also matches
                    shortcut_conflicts.append(ref)
                else:
                    keybind_conflicts.append(ref)

    return {
        "shortcut_conflicts_external": shortcut_conflicts,
        "keybind_conflicts_external":  keybind_conflicts,
    }


def update_entry_external_conflicts(entry: dict, force: bool = False) -> bool:
    """Scan and write external conflicts back onto entry in-place.
    Scans both the primary keybind and all extra keybinds.

    If `force=False` (default) and the entry's stored signature matches its
    current state AND the keyconfig store signature is unchanged, the scan
    is skipped — the existing cached conflict lists remain valid.

    Returns True if a scan was performed, False if skipped due to cache hit.
    """
    # Cache-skip check
    from . import keyconfig_store as _ks
    current_ks_sig = _ks.get_signature()
    if (not force) and entry_signatures_match(entry, current_ks_sig):
        return False

    # Capture any user-set override toggles BEFORE rescanning, so a rescan
    # (import, preset-apply, Re-scan, env change) doesn't wipe the user's
    # manual re-enable choices. Keyed by ref identity.
    def _ref_key(r):
        return (r.get("keymap_name", ""), r.get("op_id", ""), r.get("key", ""),
                r.get("event_type", ""), bool(r.get("shift")), bool(r.get("ctrl")),
                bool(r.get("alt")), bool(r.get("oskey")))
    preserved_reenabled = {}
    for _r in (entry.get("shortcut_conflicts_external", []) +
               entry.get("keybind_conflicts_external", [])):
        if _r.get("user_reenabled", False):
            preserved_reenabled[_ref_key(_r)] = True

    # Scan primary keybind
    result = scan_external_conflicts(entry)
    sc = result["shortcut_conflicts_external"]
    kc = result["keybind_conflicts_external"]

    # Scan each extra keybind slot
    for extra in entry.get("extra_keybinds", []):
        ex_key = extra.get("key", "")
        if not ex_key or ex_key == "NONE":
            continue
        # Build a temporary entry dict for this extra keybind
        ex_entry = dict(entry)
        ex_entry["key"]        = extra.get("key", "")
        ex_entry["event_type"] = extra.get("value", "PRESS")
        ex_entry["shift"]      = extra.get("shift", False)
        ex_entry["ctrl"]       = extra.get("ctrl",  False)
        ex_entry["alt"]        = extra.get("alt",   False)
        ex_entry["oskey"]      = extra.get("oskey", False)
        ex_entry["any"]        = extra.get("any",   False)
        ex_entry["key_modifier"] = extra.get("key_modifier", "")
        ex_entry["detect_contexts"] = extra.get("detect_contexts", [])
        ex_result = scan_external_conflicts(ex_entry)
        # Merge results, avoiding duplicates
        existing_keys = {(r["keymap_name"], r["op_id"], r["key"]) for r in sc}
        for r in ex_result["shortcut_conflicts_external"]:
            k = (r["keymap_name"], r["op_id"], r["key"])
            if k not in existing_keys:
                sc.append(r)
                existing_keys.add(k)
        existing_keys_kc = {(r["keymap_name"], r["op_id"], r["key"]) for r in kc}
        for r in ex_result["keybind_conflicts_external"]:
            k = (r["keymap_name"], r["op_id"], r["key"])
            if k not in existing_keys_kc:
                kc.append(r)
                existing_keys_kc.add(k)

    # Re-apply preserved user override toggles onto the freshly-scanned refs.
    if preserved_reenabled:
        for _r in sc:
            if preserved_reenabled.get(_ref_key(_r)):
                _r["user_reenabled"] = True
        for _r in kc:
            if preserved_reenabled.get(_ref_key(_r)):
                _r["user_reenabled"] = True

    entry["shortcut_conflicts_external"] = sc
    entry["keybind_conflicts_external"]  = kc
    # Stamp fresh signatures so the next call can skip-if-unchanged
    entry["_conflict_signature"]    = compute_entry_signature(entry)
    entry["_ks_signature_at_scan"]  = current_ks_sig
    return True


def update_all_external_conflicts(entries: list, force: bool = False) -> int:
    """Run external conflict scan for all entries.
    Returns the number of entries that actually got scanned (skips counted out).
    """
    _clear_resolve_cache()
    scanned = 0
    for entry in entries:
        if update_entry_external_conflicts(entry, force=force):
            scanned += 1
    return scanned
