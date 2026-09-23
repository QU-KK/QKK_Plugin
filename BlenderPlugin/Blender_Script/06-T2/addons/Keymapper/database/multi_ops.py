"""Multi-operator detection for the simplified Browse Operators view.

A "multi-op" bundles several operators that do the same conceptual thing in
different contexts (mesh.select_all, curve.select_all, object.select_all, ...)
so the user can bind all of them in one go instead of hunting them down
individually.

Detection rules (all must hold):

  1. Same operator SUFFIX — the part after the module prefix
     (mesh.select_all / curve.select_all -> "select_all").
  2. Same DEFAULT KEYBIND. Sharing a name is not enough: the operators must
     actually agree on a binding in the factory keyconfig. Many operators carry
     SEVERAL default keybinds (396 of 960 do), so every binding is considered,
     not just the first.
  3. Same PROPERTIES. select_all is bound three times over — A (action=SELECT),
     Alt+A (action=DESELECT), Ctrl+I (action=INVERT) — and those are three
     DIFFERENT actions that happen to share an operator. Keying on props keeps
     them apart, so each multi-op is one coherent action.
  4. At least MIN_CLUSTER_SIZE operators (2).

Source of truth: `wm.keyconfigs.default` — Blender's FACTORY keyconfig. It is
pristine: Keymapper, addons and the user all write to the `user`/`addon`
keyconfigs instead, so the default layer contains no Keymapper entries, no addon
bindings and no user edits (verified: zero negative-id KMIs, zero operator
overlap with the addon layer). That means no ownership bookkeeping is needed —
scanning a layer we never write to cannot be contaminated by our own KMIs.

Because it reads the factory keyconfig, the multi-op set only changes when the
user switches keyconfig template (Blender / BForArtists / Industry Compatible),
which is exactly when a Re-scan happens.
"""

import bpy

MIN_CLUSTER_SIZE = 2

# Suffixes whose title-cased form reads badly. Everything else is derived
# automatically (select_all -> "Select All").
_LABEL_OVERRIDES = {
    "select_all": "Select All",
    "select_more": "Select More",
    "select_less": "Select Less",
    "select_linked": "Select Linked",
    "select_linked_pick": "Select Linked (Pick)",
    "select_box": "Box Select",
    "select_circle": "Circle Select",
    "select_lasso": "Lasso Select",
    "view_all": "View All",
    "view_selected": "View Selected",
    "clickselect": "Click Select",
    "copy": "Copy",
    "paste": "Paste",
    "delete": "Delete",
}

# Cache: list of multi-op dicts, rebuilt on demand / after a Re-scan.
_multi_ops: list | None = None


def _kmi_props(kmi) -> dict:
    """Explicitly-set properties of a KMI (the ones that define its action).

    Skips POINTER/COLLECTION properties: macro operators (transform.translate
    inside object.duplicate_move, ...) expose their sub-operators as struct
    properties, and str()-ing those yields
    "<bpy struct, TRANSFORM_OT_translate at 0x55...>" — memory addresses that
    are meaningless to the user, unstable across sessions, and were leaking into
    labels.
    """
    out = {}
    try:
        props = kmi.properties
        for p in props.bl_rna.properties:
            pid = p.identifier
            if pid == "rna_type":
                continue
            if p.type in ("POINTER", "COLLECTION"):
                continue
            if props.is_property_set(pid):
                out[pid] = str(getattr(props, pid, ""))
    except Exception:
        pass
    return out



def _friendly_for_op(op_id: str, suffix: str) -> str:
    """Friendly base name for a variant cluster: the operator's real friendly
    name when the database has one (wm.call_menu_pie -> "Call Pie Menu"),
    else the mechanical suffix titling."""
    try:
        from .friendly_ops import get_friendly_name
        # Raw name: cluster labels cover many modules, so per-op module
        # qualification would mislabel the bundle.
        name = get_friendly_name(op_id, qualify=False)
        if name:
            return name
    except Exception:
        pass
    return _friendly_from_suffix(suffix)

def _friendly_from_suffix(suffix: str) -> str:
    """Human-readable name for an operator suffix (the Friendly half of the
    Friendly/Pure naming toggle). Pure naming shows the raw suffix instead."""
    if suffix in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[suffix]
    return suffix.replace("_", " ").title()


def _props_suffix(props: dict) -> str:
    """Disambiguating tail for the label, e.g. Select All (Deselect).

    Enum-ish values carry the meaning (action=DESELECT -> "Deselect"), but a
    BOOLEAN value does not: rendering toggle=True as "(True)" tells the user
    nothing and makes several different multi-ops read identically. For booleans
    the KEY is the meaningful part, so use that instead (-> "(Toggle)").
    A False boolean is the operator's default behaviour and adds no meaning, so
    it's dropped entirely.
    """
    if not props:
        return ""
    parts = []
    for k, v in props.items():
        sv = str(v)
        if sv == "True":
            parts.append(k.replace("_", " ").title())
        elif sv == "False":
            # Keep it, but say so explicitly. Dropping False booleans outright
            # collapses a cluster into its sibling: shortest_path_pick is bound
            # with use_fill=True AND use_fill=False, and hiding the False one
            # made it read identically to a third, unrelated cluster.
            parts.append("No " + k.replace("_", " ").title())
        else:
            parts.append(sv.replace("_", " ").title())
    if not parts:
        return ""
    return " (" + ", ".join(parts) + ")"


def _variant_label_suffix(variants: dict, kb_label: str) -> str:
    """Parenthetical for a prop-variant cluster's label.

    Factory keybinds are meaningless in the Simple view (the user is about to
    REBIND the thing), so the parenthetical shows what actually distinguishes
    the row instead, in order of preference:
      1. props SHARED by every variant ("Clear Track Path (Remained)" — the
         action is the identity; only clear_active varies per context);
      2. the common trailing tokens of the VARYING prop's values ("Call Menu
         (Context Menu)" from *_MT_*_context_menu; "Context Toggle (Use Snap)"
         from tool_settings.use_snap*);
      3. the factory keybind, as a last resort when nothing else does.
    """
    import re as _re

    plists = [dict(pt) for pt in variants.keys()]
    # 1) shared props (identical key+value in every variant)
    shared = dict(plists[0])
    for p in plists[1:]:
        shared = {k: v for k, v in shared.items() if p.get(k) == v}
    # drop boolean/empty noise ("clear_active=False" flags never identify)
    shared_show = {k: v for k, v in shared.items()
                   if str(v) not in ("True", "False", "")}
    if shared_show:
        return _props_suffix(shared_show)
    # 2) common tokens of the varying prop's values — trailing first
    #    ("*_context_menu" -> Context Menu), then leading ("use_snap_*" ->
    #    Use Snap; "brush_*" asset shelves -> Brush), with generic data-path
    #    heads stripped.
    _GENERIC = {"tool_settings", "space_data", "scene", "preferences",
                "view_layer", "overlay", "data"}
    varying = sorted({k for p in plists for k in p} - set(shared))
    for key in varying:
        vals = [str(p.get(key, "")) for p in plists]
        if any(not v for v in vals):
            continue
        # strip UI-class prefixes like VIEW3D_MT_ / TOPBAR_PT_
        vals = [_re.sub(r"^[A-Za-z0-9]+_(MT|PT|AST|HT)_", "", v) for v in vals]
        toks = [[t for t in _re.split(r"[._]", v) if t] for v in vals]
        # trailing
        common: list = []
        for group in zip(*(reversed(t) for t in toks)):
            if all(g == group[0] for g in group):
                common.insert(0, group[0])
            else:
                break
        _GENERIC_TAIL = {"pie", "menu", "panel"}
        if common and all(c in _GENERIC_TAIL for c in common):
            # Only generic tail tokens ("pie") survived strict commonality —
            # label by the MAJORITY meaningful token instead (the snap pies:
            # most values contain "snap", one outlier broke strictness).
            from collections import Counter
            freq = Counter(t for tl in toks for t in set(tl)
                           if t not in _GENERIC_TAIL and t not in _GENERIC)
            if freq:
                top, n = freq.most_common(1)[0]
                if n > len(toks) // 2:
                    common = [top]
        if not common:
            # leading
            for group in zip(*toks):
                if all(g == group[0] for g in group):
                    common.append(group[0])
                else:
                    break
            common = [c for c in common if c not in _GENERIC]
        if common:
            pretty = " ".join(w.title() for w in common)
            return f" ({pretty})"
    # 3) nothing distinguishes it in words — signal the caller to drop it
    return None


def combo_label(sig) -> str:
    """'Alt + A' style label for a keybind signature."""
    key, value, shift, ctrl, alt, oskey = sig
    parts = []
    if shift:
        parts.append("Shift")
    if ctrl:
        parts.append("Ctrl")
    if alt:
        parts.append("Alt")
    if oskey:
        parts.append("OS")
    try:
        from ..panel import _key_display_name

        parts.append(_key_display_name(key))
    except Exception:
        parts.append(key)
    label = " + ".join(parts)
    if value and value not in ("PRESS", ""):
        label += f" ({value.replace('_', ' ').title()})"
    return label


def scan_multi_ops() -> list:
    """Build the multi-op list from the FACTORY keyconfig. See module docstring
    for the detection rules."""
    from collections import defaultdict

    try:
        kc = bpy.context.window_manager.keyconfigs.default
    except Exception:
        return []
    if kc is None:
        return []

    # (suffix, keybind_sig, props) -> {op_id: {keymap names}}
    #
    # The keymap each binding was found in is captured as we go. It's stored on
    # the multi-op so its operators can be added with EXPLICIT contexts rather
    # than relying on auto-resolution. That's not just redundancy: auto-context
    # returns every keymap an operator appears in ANYWHERE, whereas this is
    # scoped to the keymap where this exact keybind+props combination is
    # actually bound — so it's strictly narrower and more accurate. (node.select
    # for instance auto-resolves to Node Editor + four tool keymaps, but this
    # cluster's binding only genuinely exists in the tool keymaps.)
    clusters: dict = defaultdict(lambda: defaultdict(set))
    for km in kc.keymaps:
        for kmi in km.keymap_items:
            op_id = kmi.idname
            if not op_id or "." not in op_id:
                continue
            suffix = op_id.split(".", 1)[1]
            sig = (kmi.type, kmi.value, bool(kmi.shift), bool(kmi.ctrl),
                   bool(kmi.alt), bool(kmi.oskey))
            if sig[0] in ("NONE", ""):
                continue
            props = _kmi_props(kmi)
            key = (suffix, sig, tuple(sorted(props.items())))
            clusters[key][op_id].add(km.name)

    out = []
    for (suffix, sig, props_t), members in clusters.items():
        if len(members) < MIN_CLUSTER_SIZE:
            continue
        props = dict(props_t)
        label = _friendly_from_suffix(suffix) + _props_suffix(props)
        contexts = {op: sorted(kms) for op, kms in members.items()}
        out.append({
            "contexts": contexts,
            # Stable id so selection survives a redraw.
            "id": f"multi:{suffix}:{'_'.join(map(str, sig))}:{'_'.join(f'{k}={v}' for k, v in sorted(props.items()))}",
            "suffix": suffix,
            "label": label,             # Friendly
            "raw_label": suffix + _props_suffix(props),  # Pure
            "keybind": sig,
            "keybind_label": combo_label(sig),
            "props": props,
            "operators": sorted(members.keys()),
        })
    # MERGE clusters that differ only in which factory keybind they were found
    # under. A Keymapper entry can hold several keybinds anyway, so two rows
    # bundling the same operators with the same props are one multi-op with two
    # default keybinds — not two multi-ops.
    merged: dict = {}
    for m in out:
        ident = (m["suffix"],
                 tuple(m["operators"]),
                 tuple(sorted(m["props"].items())))
        prev = merged.get(ident)
        if prev is None:
            m["all_keybinds"] = [m["keybind_label"]]
            merged[ident] = m
        else:
            prev["all_keybinds"].append(m["keybind_label"])
    out = list(merged.values())

    # Labels carry NO keybind and NO operator count — those belong in the
    # tooltip only. That means two genuinely different clusters can still end up
    # with the same label (Blender binds e.g. `select` across several editor
    # groups with different operator sets). Rather than pollute the label to
    # tell them apart, keep only the biggest one: it is the most useful
    # (broadest) bundle, and the smaller variants are subsets a user can still
    # assemble by hand.
    by_label: dict = {}
    for m in out:
        prev = by_label.get(m["label"])
        if prev is None or len(m["operators"]) > len(prev["operators"]):
            if prev is not None:
                # fold the discarded variant's keybinds into the kept one
                for kb in prev["all_keybinds"]:
                    if kb not in m["all_keybinds"]:
                        m["all_keybinds"].append(kb)
            by_label[m["label"]] = m
        else:
            for kb in m["all_keybinds"]:
                if kb not in prev["all_keybinds"]:
                    prev["all_keybinds"].append(kb)
    out = list(by_label.values())

    # PROP-VARIANT CLUSTERS: the same operator bound to the same key in many
    # keymaps with per-keymap properties — Call Menu on W (25 mode context
    # menus), Call Asset Shelf Popover on Space (10 mode shelves), Context
    # Toggle on Shift+Tab (snap in 5 editors)... One action from the user's
    # view: "this operator on this key everywhere, properties per context."
    # Selecting one adds one op INSTANCE per variant. Appended AFTER the
    # keep-biggest-label dedupe above: these are distinct actions whose only
    # distinguisher is the keybind, so the keybind goes in the label
    # parenthetical (the one place the no-keybind-in-labels rule yields).
    var_clusters: dict = defaultdict(lambda: defaultdict(set))
    for km in kc.keymaps:
        for kmi in km.keymap_items:
            op_id = kmi.idname
            if not op_id or "." not in op_id:
                continue
            sig = (kmi.type, kmi.value, bool(kmi.shift), bool(kmi.ctrl),
                   bool(kmi.alt), bool(kmi.oskey))
            if sig[0] in ("NONE", ""):
                continue
            props = _kmi_props(kmi)
            var_clusters[(op_id, sig)][tuple(sorted(props.items()))].add(km.name)

    for (op_id, sig), variants in var_clusters.items():
        if len(variants) < 2:
            continue
        # Variants that differ ONLY in boolean props (release_confirm,
        # cursor_transform, wait_for_input...) are tool-keymap mechanics, not
        # distinct user-facing actions — not a meaningful bundle.
        _pl = [dict(pt) for pt in variants.keys()]
        _sh = dict(_pl[0])
        for _p in _pl[1:]:
            _sh = {k: v for k, v in _sh.items() if _p.get(k) == v}
        _vary_keys = {k for p in _pl for k in p} - set(_sh)
        _vary_vals = {str(p.get(k)) for p in _pl for k in _vary_keys}
        if _vary_vals <= {"True", "False", "None"}:
            continue
        suffix = op_id.split(".", 1)[1]
        kb = combo_label(sig)
        _lbl_suffix = _variant_label_suffix(variants, kb)
        if _lbl_suffix is None:
            # Nothing distinguishes this cluster in words; a keybind label is
            # meaningless in the Simple view, so it stays Factory-only.
            continue
        all_ctx = sorted({c for kms in variants.values() for c in kms})
        out.append({
            "id": f"multivar:{op_id}:{'_'.join(map(str, sig))}",
            "suffix": suffix,
            "label": _friendly_for_op(op_id, suffix) + _lbl_suffix,
            "raw_label": suffix + _lbl_suffix,
            "keybind": sig,
            "keybind_label": kb,
            "all_keybinds": [kb],
            "props": {},  # differs per variant — see `variants`
            "operators": [op_id],
            "contexts": {op_id: all_ctx},
            "variants": [
                {"props": dict(pt), "contexts": sorted(kms)}
                for pt, kms in sorted(variants.items())
            ],
        })

    # Variant rows whose CONTENT is identical (same op, same variant set) and
    # which differ only in the factory keybind are one action bound twice —
    # merge them, keeping every keybind for the tooltip (the same rule regular
    # multi-ops follow).
    _vmerged: dict = {}
    _plain = []
    for m in out:
        if not m.get("variants"):
            _plain.append(m)
            continue
        ident = (m["operators"][0],
                 tuple((tuple(sorted(v["props"].items())),
                        tuple(v["contexts"])) for v in m["variants"]))
        prev = _vmerged.get(ident)
        if prev is None:
            _vmerged[ident] = m
        else:
            for kb2 in m["all_keybinds"]:
                if kb2 not in prev["all_keybinds"]:
                    prev["all_keybinds"].append(kb2)
    # Same LABEL from different keybind groups ("Call Menu (Context Menu)" on
    # W, Right Mouse and Application): keep the broadest bundle, fold the
    # others' keybinds into its tooltip — the keep-biggest rule regular
    # multi-ops already follow.
    _by_lbl: dict = {}
    for m in _vmerged.values():
        prev = _by_lbl.get(m["label"])
        if prev is None or len(m["variants"]) > len(prev["variants"]):
            if prev is not None:
                for kb2 in prev["all_keybinds"]:
                    if kb2 not in m["all_keybinds"]:
                        m["all_keybinds"].append(kb2)
            _by_lbl[m["label"]] = m
        else:
            for kb2 in m["all_keybinds"]:
                if kb2 not in prev["all_keybinds"]:
                    prev["all_keybinds"].append(kb2)
    out = _plain + list(_by_lbl.values())

    out.sort(key=lambda m: m["label"].lower())
    return out


def get_multi_ops(force: bool = False) -> list:
    global _multi_ops
    if _multi_ops is None or force:
        _multi_ops = scan_multi_ops()
        print(f"[Keymapper] Detected {len(_multi_ops)} multi-operators "
              f"from the factory keyconfig.")
    return _multi_ops


def invalidate():
    """Drop the caches — called on Re-scan (the factory keyconfig only changes
    when the user switches keyconfig template)."""
    global _multi_ops, _factory_bindings
    _multi_ops = None
    _factory_bindings = None


def get_multi_op(multi_id: str) -> dict | None:
    for m in get_multi_ops():
        if m["id"] == multi_id:
            return m
    return None


# --- Simplified categories -------------------------------------------------
# A multi-op spans many editors by definition, so the normal per-editor
# categories don't fit (a "select_all" multi-op belongs to a dozen of them at
# once). Group by the action instead.

# Category -> {subcategory: [suffix keywords]}. A multi-op spans many editors
# by definition (select_all lives in Mesh, Curve, Object, Node, ...), so the
# per-editor categories of the normal browser can't hold it — these group by
# ACTION instead. Subcategories mirror the normal browser's shape so the
# simplified view reads the same.
# (id, label, icon, [(subcategory, suffix keywords)])
_SIMPLE_CATEGORIES = [
    ("select", "Selection", "RESTRICT_SELECT_OFF", [
        ("Select All",      ("select_all",)),
        ("Grow / Shrink",   ("select_more", "select_less", "select_linked",
                             "select_similar", "select_grouped")),
        ("Region Select",   ("select_box", "select_circle", "select_lasso")),
        ("Pick Select",     ("clickselect", "select_pick", "shortest_path",
                             "move_select", "view_item_select")),
        ("Select Mode",     ("select_mode", "set_selection_mode")),
        ("Walk / Step",     ("select_walk", "select_hierarchy",
                             "select_leftright", "select_column")),
        ("Other Select",    ()),
    ]),
    ("transform", "Transform", "ORIENTATION_GLOBAL", [
        ("Move",            ("translate", "slide", "shift")),
        ("Rotate",          ("rotate", "spin", "roll")),
        ("Scale",           ("resize", "scale", "shrink_fatten")),
        ("Snap / Mirror",   ("snap", "mirror")),
        ("Other Transform", ()),
    ]),
    ("edit", "Edit", "MODIFIER", [
        ("Add / Remove",    ("add", "new", "delete", "remove", "insert")),
        ("Duplicate",       ("duplicate", "copy", "paste", "cut")),
        ("Topology",        ("split", "join", "merge", "dissolve", "extrude",
                             "subdivide", "fill", "bevel", "knife", "inset",
                             "loop", "screw", "solidify")),
        ("Clear / Apply",   ("clear", "apply", "convert", "separate")),
        ("Other Edit",      ()),
    ]),
    ("view", "View", "VIEW3D", [
        ("Framing",         ("view_all", "view_selected", "view_frame",
                             "frame", "view_axis", "view_camera")),
        ("Zoom",            ("zoom", "dolly")),
        ("Pan / Scroll",    ("pan", "scroll")),
        ("Navigation",      ("orbit", "roll", "fly", "walk", "navigate",
                             "ndof")),
        ("Other View",      ()),
    ]),
    ("menus", "Menus & Pies", "MENU_PANEL", [
        ("Pie Menus",       ("call_menu_pie", "pie")),
        ("Menus",           ("call_menu", "menu")),
        ("Panels",          ("call_panel", "panel", "popover")),
        ("Other",           ()),
    ]),
    ("tools", "Tools & Brushes", "BRUSH_DATA", [
        ("Tool Select",     ("tool_set",)),
        ("Brushes",         ("brush", "stroke", "asset")),
        ("Sculpt / Paint",  ("sculpt", "paint", "weight", "smooth", "mask")),
        ("Radial Control",  ("radial_control",)),
        ("Other Tools",     ()),
    ]),
    ("context", "Toggles & Context", "CHECKBOX_HLT", [
        ("Context Set",     ("context_",)),
        ("Toggles",         ("toggle",)),
        ("Cycle",           ("cycle", "space_type")),
        ("Other",           ()),
    ]),
    ("visibility", "Visibility", "HIDE_OFF", [
        ("Hide / Reveal",   ("hide", "reveal", "show")),
        ("Isolate",         ("isolate", "local_view")),
        ("Other",           ()),
    ]),
    ("anim", "Animation", "KEYFRAME", [
        ("Keyframes",       ("keyframe", "keying")),
        ("Playback",        ("play", "frame_jump")),
        ("Channels",        ("channels", "action", "driver")),
        ("Other",           ()),
    ]),
    ("file", "File", "FILE", [
        ("File",            ()),
    ]),
    ("other", "Other", "THREE_DOTS", [
        ("Other",           ()),
    ]),
]


# Which category a suffix belongs to — first match wins.
_CATEGORY_KEYWORDS = [
    # Menus / pies / panels first: wm.call_menu & friends are ~130 bindings and
    # would otherwise swamp "Other".
    ("menus",      ("call_menu", "call_panel", "call_pie", "menu", "panel",
                    "popover")),
    ("select",     ("select", "deselect", "clickselect", "shortest_path")),
    ("view",       ("view", "zoom", "pan", "frame", "scroll", "orbit", "dolly",
                    "roll", "fly", "walk", "navigate")),
    ("visibility", ("hide", "reveal", "show", "mask", "isolate", "local_view")),
    ("anim",       ("keyframe", "keying", "play", "frame_jump", "bake",
                    "channels", "action", "driver")),
    ("file",       ("save", "open", "export", "import", "read", "file",
                    "link", "append", "recover", "revert", "quit")),
    ("tools",      ("tool_set", "brush", "stroke", "radial_control", "sculpt",
                    "paint", "weight", "smooth", "asset")),
    ("context",    ("context_", "toggle", "cycle", "set_enum", "set_int",
                    "set_boolean", "space_type")),
    ("transform",  ("translate", "rotate", "resize", "scale", "transform",
                    "mirror", "snap", "shear", "warp", "bend", "push_pull",
                    "shrink_fatten", "edge_slide", "vert_slide", "slide")),
    ("edit",       ("delete", "duplicate", "copy", "paste", "cut", "add",
                    "remove", "new", "insert", "split", "join", "merge",
                    "dissolve", "extrude", "rename", "subdivide", "fill",
                    "clear", "apply", "convert", "separate", "bevel", "knife",
                    "loop", "inset", "spin", "screw", "solidify")),
]


def _category_of(suffix: str) -> str:
    for cid, keys in _CATEGORY_KEYWORDS:
        if any(k in suffix for k in keys):
            return cid
    return "other"


def _subcategory_of(cid: str, suffix: str) -> str:
    subs = next((subs for c, _l, _i, subs in _SIMPLE_CATEGORIES if c == cid), [])
    fallback = subs[-1][0] if subs else "Other"
    for sub_label, keys in subs:
        if keys and any(k in suffix for k in keys):
            return sub_label
    return fallback


def simplified_categories() -> list:
    """[(cat_id, cat_label, icon, [(sub_label, [multi_op, ...]), ...])]

    Every multi-op lands in exactly one category and one subcategory, sorted
    A-Z, so the simplified view has the same shape as the normal browser.
    """
    from collections import defaultdict

    buckets = defaultdict(lambda: defaultdict(list))
    for m in get_multi_ops():
        cid = _category_of(m["suffix"])
        sub = _subcategory_of(cid, m["suffix"])
        buckets[cid][sub].append(m)

    out = []
    for cid, clabel, icon, subs in _SIMPLE_CATEGORIES:
        if cid not in buckets:
            continue
        rows = []
        for sub_label, _keys in subs:
            mops = buckets[cid].get(sub_label)
            if not mops:
                continue
            mops.sort(key=lambda m: m["label"].lower())
            rows.append((sub_label, mops))
        if rows:
            out.append((cid, clabel, icon, rows))
    return out


# ---------------------------------------------------------------------------
# Factory Bindings browser (third mode)
#
# Lists EVERY binding the factory keyconfig actually uses — including the ~1520
# single-operator ones the multi-op view deliberately omits. The point is
# DISCOVERY: the normal browser lists `view3d.view_axis` once and gives no hint
# that the factory binds it twelve different ways (FRONT / RIGHT / TOP / ...),
# because the distinguishing information lives in the PROPERTIES.
#
# Rows are grouped into "value families": same operator + same property KEYS,
# differing only in property VALUES. A family is a DISPLAY grouping only, never
# a selectable bundle — view_axis FRONT and view_axis TOP are different actions
# that want different keys, so bundling them like a multi-op would be wrong
# (they'd all fire on one keypress).
# ---------------------------------------------------------------------------

_factory_bindings: list | None = None


def scan_factory_bindings() -> list:
    """[(family_label, op_id, [binding, ...])] — every factory binding, grouped
    by value family and sorted A-Z."""
    from collections import defaultdict

    try:
        kc = bpy.context.window_manager.keyconfigs.default
    except Exception:
        return []
    if kc is None:
        return []

    # (op_id, prop_keys) -> {(sig, props_tuple): {keymaps}}
    fams: dict = defaultdict(lambda: defaultdict(set))
    for km in kc.keymaps:
        for kmi in km.keymap_items:
            op_id = kmi.idname
            if not op_id or "." not in op_id:
                continue
            if kmi.type in ("NONE", ""):
                continue
            props = _kmi_props(kmi)
            sig = (kmi.type, kmi.value, bool(kmi.shift), bool(kmi.ctrl),
                   bool(kmi.alt), bool(kmi.oskey))
            pkeys = tuple(sorted(props.keys()))
            fams[(op_id, pkeys)][(sig, tuple(sorted(props.items())))].add(km.name)

    out = []
    for (op_id, pkeys), variants in fams.items():
        # Same operator + same props + same contexts, differing only in KEYBIND,
        # is ONE selectable thing that the factory happens to bind twice
        # (screen.animation_play on Space AND Media Play/Pause). Merge them and
        # keep every keybind for the tooltip — the same rule the multi-op view
        # uses. Without this the list showed 204 pairs of identical rows.
        by_action: dict = {}
        for (sig, props_t), kms in variants.items():
            props = dict(props_t)
            ctxs = sorted(kms)
            # Key on PROPS only, not contexts: the same operator+props bound in
            # a wider and a narrower scope (view2d.pan in [View2D] and in
            # [View2D, View2D Buttons List]) is one action, so union the
            # contexts rather than emitting two identical-looking rows.
            akey = props_t
            row = by_action.get(akey)
            if row is None:
                by_action[akey] = {
                    "id": f"fb:{op_id}:{'_'.join(map(str, sig))}:"
                          f"{'_'.join(f'{k}={v}' for k, v in sorted(props.items()))}",
                    "op_id": op_id,
                    "props": props,
                    "keybind": sig,
                    "keybind_label": combo_label(sig),
                    "all_keybinds": [combo_label(sig)],
                    "contexts": ctxs,
                    "label": _label_for_binding(op_id, props, ctxs),
                }
            else:
                kb = combo_label(sig)
                if kb not in row["all_keybinds"]:
                    row["all_keybinds"].append(kb)
                merged_ctx = sorted(set(row["contexts"]) | set(ctxs))
                if merged_ctx != row["contexts"]:
                    row["contexts"] = merged_ctx
                    row["label"] = _label_for_binding(op_id, row["props"],
                                                      merged_ctx)
        rows = list(by_action.values())
        # SECOND merge pass: rows with the SAME keybind(s) whose prop-variants
        # live in pairwise-DISJOINT contexts are one action ("this operator on
        # this key everywhere, with per-context properties") — e.g. Call Asset
        # Shelf Popover bound to the same key in 10 modes, each mode passing its
        # own shelf name. They never compete (disjoint contexts), so collapse
        # them into a single row carrying a per-context props `variants` list.
        # Rows sharing a context (genuinely competing bindings) stay separate.
        by_kb: dict = {}
        for row in rows:
            by_kb.setdefault(frozenset(row["all_keybinds"]), []).append(row)
        merged_rows = []
        for kb_key, group in by_kb.items():
            if len(group) < 2:
                merged_rows.extend(group)
                continue
            # No disjoint-context requirement: even when two variants share a
            # keymap (both asset shelves live in "Image Paint"), the FACTORY
            # itself stacks them and lets poll decide — selecting the merged
            # row recreates exactly what the factory does.
            all_ctx = sorted({c for row in group for c in row["contexts"]})
            base = group[0]
            merged_rows.append({
                "id": f"fbm:{op_id}:{'_'.join(map(str, base['keybind']))}",
                "op_id": op_id,
                "props": {},  # differs per variant — see `variants`
                "variants": [
                    {"props": dict(r["props"]), "contexts": list(r["contexts"])}
                    for r in group
                ],
                "keybind": base["keybind"],
                "keybind_label": base["keybind_label"],
                "all_keybinds": list(base["all_keybinds"]),
                "contexts": all_ctx,
                "label": _label_for_binding(op_id, {}, all_ctx),
            })
        rows = merged_rows
        rows.sort(key=lambda r: r["label"].lower())
        out.append({
            "op_id": op_id,
            "family": _friendly_from_suffix(op_id.split(".", 1)[1]),
            "prop_keys": list(pkeys),
            "bindings": rows,
        })
    out.sort(key=lambda f: (f["family"].lower(), f["op_id"]))
    return out


# Module prefix -> the name a user would recognise it by. Only the ones whose
# title-cased form reads wrong need an entry; everything else is derived.
_MODULE_LABELS = {
    "nla": "NLA",
    "uv": "UV",
    "gpencil": "Grease Pencil",
    "grease_pencil": "Grease Pencil",
    "anim": "Animation",
    "wm": "Window",
    "ed": "Edit",
    "info": "Info",
    "clip": "Clip",
    "mball": "Metaball",
    "poselib": "Pose Library",
    "pointcloud": "Point Cloud",
    "lightprobe": "Light Probe",
    "gizmogroup": "Gizmo",
    "ui": "UI",
    "view2d": "2D View",
    "view3d": "3D View",
    "screen": "Screen",
    "buttons": "Properties",
    "console": "Console",
    "text": "Text",
    "font": "Font",
    "node": "Node",
    "mask": "Mask",
    "paint": "Paint",
    "sculpt": "Sculpt",
    "object": "Object",
    "mesh": "Mesh",
    "curve": "Curve",
    "curves": "Curves",
    "armature": "Armature",
    "pose": "Pose",
    "particle": "Particle",
    "lattice": "Lattice",
    "action": "Action",
    "graph": "Graph",
    "sequencer": "Sequencer",
    "outliner": "Outliner",
    "file": "File",
    "image": "Image",
    "brush": "Brush",
    "marker": "Marker",
    "transform": "Transform",
    "render": "Render",
    "scene": "Scene",
    "asset": "Asset",
    "collection": "Collection",
    "constraint": "Constraint",
    "geometry": "Geometry",
    "material": "Material",
    "palette": "Palette",
    "preferences": "Preferences",
    "script": "Script",
    "sound": "Sound",
    "surface": "Surface",
    "texture": "Texture",
    "workspace": "Workspace",
    "world": "World",
}


def _module_label(op_id: str) -> str:
    mod = op_id.split(".", 1)[0]
    return _MODULE_LABELS.get(mod, mod.replace("_", " ").title())


def _label_for_binding(op_id: str, props: dict, contexts=None) -> str:
    """Label for ONE factory binding: "Node - Select All", "NLA - Select All
    (Invert)".

    Qualified by the operator's MODULE, not by the keymap it happens to live in.
    The module is what the user actually thinks in ("that's the Node one"),
    whereas a keymap name is an implementation detail and often unwieldy
    ("Grease Pencil Selection", "3D View Tool: Select Box").

    The name comes from the operator SUFFIX rather than the curated friendly
    name: friendly names are written to stand alone in a list of every operator,
    so they pack in disambiguation the module prefix now supplies —
    "Select / Deselect All" instead of plain "Select All", "Select Less UV"
    instead of "Select Less". With the module in front, the short form is both
    clearer and shorter.
    """
    suffix = op_id.split(".", 1)[1]
    base = _friendly_from_suffix(suffix)
    rest = dict(props)

    # Fold the action= property into the verb: "Select All (Deselect)" is just
    # a clumsy way of writing "Deselect All", and (Select) adds nothing at all.
    if suffix.endswith("select_all") and "action" in rest:
        act = str(rest.pop("action")).upper()
        stem = base[:-len("Select All")].strip() if base.endswith("Select All") else ""
        verb = {
            "SELECT": "Select All",
            "DESELECT": "Deselect All",
            "INVERT": "Invert Selection",
            "TOGGLE": "Toggle Selection",
        }.get(act)
        if verb:
            base = f"{stem} {verb}".strip()

    return f"{_module_label(op_id)} - {base}{_props_suffix(rest)}"


def get_factory_bindings(force: bool = False) -> list:
    global _factory_bindings
    if _factory_bindings is None or force:
        _factory_bindings = scan_factory_bindings()
        n = sum(len(f["bindings"]) for f in _factory_bindings)
        print(f"[Keymapper] Factory bindings: {n} in "
              f"{len(_factory_bindings)} families.")
    return _factory_bindings


def get_factory_binding(bid: str) -> dict | None:
    for fam in get_factory_bindings():
        for b in fam["bindings"]:
            if b["id"] == bid:
                return b
    return None


def factory_rows() -> list:
    """Factory browse rows: MULTI-OPS + the single ops that aren't in one.

    The Simplified view is multi-ops ONLY. This list is the combination: every
    binding the factory keyconfig uses, but with the ops that CAN be narrowed to
    a multi-op presented as that multi-op instead of as N separate rows. So
    "Select All" appears once (bundling 23 operators) rather than 23 times, while
    everything with no multi-op sibling still shows individually.

    A row is either {"kind": "multi", "multi": <multi_op>} or
    {"kind": "single", "binding": <factory binding>}.
    """
    # Which (op_id, props) pairs are already covered by a multi-op?
    covered = set()
    covered_variant_groups = set()
    for m in get_multi_ops():
        if m.get("variants"):
            op_id = m["operators"][0]
            vprops = frozenset(tuple(sorted(v["props"].items()))
                               for v in m["variants"])
            covered_variant_groups.add((op_id, vprops))
            for v in m["variants"]:
                covered.add((op_id, tuple(sorted(v["props"].items()))))
            continue
        for op_id in m["operators"]:
            covered.add((op_id, tuple(sorted(m["props"].items()))))

    rows = []
    for m in get_multi_ops():
        rows.append({"kind": "multi", "multi": m,
                     "label": m["label"], "suffix": m["suffix"]})
    for fam in get_factory_bindings():
        for b in fam["bindings"]:
            if b.get("variants"):
                vkey = (b["op_id"],
                        frozenset(tuple(sorted(v["props"].items()))
                                  for v in b["variants"]))
                if vkey in covered_variant_groups:
                    continue  # represented by a prop-variant multi-op
                rows.append({"kind": "single", "binding": b,
                             "label": b["label"],
                             "suffix": b["op_id"].split(".", 1)[1]})
                continue
            key = (b["op_id"], tuple(sorted(b["props"].items())))
            if key in covered:
                continue  # already represented by a multi-op
            rows.append({"kind": "single", "binding": b,
                         "label": b["label"],
                         "suffix": b["op_id"].split(".", 1)[1]})
    return rows


def factory_categories() -> list:
    """[(cat_id, cat_label, icon, [(sub_label, [binding, ...]), ...])]

    FLAT list of rows per subcategory — multi-ops plus the singles they don't
    cover. No family headers: nesting them inside subcategories produced
    subcategories-within-subcategories, and now that every label is
    self-identifying the extra level earned nothing.
    """
    from collections import defaultdict

    buckets = defaultdict(lambda: defaultdict(list))
    for row in factory_rows():
        cid = _category_of(row["suffix"])
        sub = _subcategory_of(cid, row["suffix"])
        buckets[cid][sub].append(row)

    out = []
    for cid, clabel, icon, subs in _SIMPLE_CATEGORIES:
        if cid not in buckets:
            continue
        rows = []
        for sub_label, _keys in subs:
            items = buckets[cid].get(sub_label)
            if not items:
                continue
            items.sort(key=lambda r: r["label"].lower())
            rows.append((sub_label, items))
        if rows:
            out.append((cid, clabel, icon, rows))
    return out
