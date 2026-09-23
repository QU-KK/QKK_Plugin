"""
dynamic_ops.py — Unified operator discovery engine.

Single runtime scan of all bpy.ops operators. For each operator:
  - If its module has bl_info → Addon Operators
  - If it's in our static categories.py → placed in that subcategory
  - Otherwise → placed in "Other" under the correct category by module prefix

This replaces the old split between static curation and dynamic augmentation.
"""

import bpy

# ---------------------------------------------------------------------------
# Operators to explicitly exclude (addon operators that hijack built-in IDs)
# ---------------------------------------------------------------------------

OPERATOR_BLOCKLIST = {
    # Operators that hijack built-in IDs but belong to addons
    # (operator_discovery handles routing them to Addon Operators)
    "view3d.modal_operator_raycast",
    # MayaConfigPro operators under object.*, wm.*
    "object.addasset", "object.applytransforms", "object.back_ortho",
    "object.bevel", "object.bottom_ortho", "object.bridgeloops",
    "object.camlockall", "object.camlocklocation", "object.camlocklocationx",
    "object.camlockrotation", "object.camlockscale", "object.campop",
    "object.campopup", "object.camview_lock", "object.delta_transfer",
    "object.edgesnap", "object.extrudeaxis", "object.extrudenormal",
    "object.facesnap", "object.front_ortho", "object.gizmodefault",
    "object.gridsnap", "object.hideorigin", "object.hidetheorigin",
    "object.insetfaces", "object.keycurvesnap", "object.keygridsnap",
    "object.keyvertexsnap", "object.knifetool", "object.left_ortho",
    "object.loopcut", "object.mirrorapply", "object.mirrorx",
    "object.mirrorx2", "object.mirrorz", "object.msm_from_object",
    "object.multi", "object.offsnap", "object.pivotlock",
    "object.right_ortho", "object.safe_area", "object.showguides",
    "object.showorigin", "object.split_view", "object.split_view_h",
    "object.subdivide", "object.themeblenderdark", "object.thememayablue",
    "object.thememayagradient", "object.thememodo", "object.themesketchup",
    "object.themewhitebg", "object.toggle_subsurf1", "object.toggle_subsurf2",
    "object.toggle_subsurf3", "object.top_ortho", "object.unsubdivide",
    "object.vertexsnap", "edit.delete_without_confirm",
    "wm.cone", "wm.cylinder", "wm.cylinderb", "wm.icosphere",
    "wm.meshcube", "wm.myop", "wm.myopinfo", "wm.plane", "wm.uvsphere",
}

# ---------------------------------------------------------------------------
# Module prefix → category ID mapping
# ---------------------------------------------------------------------------

MODULE_TO_CATEGORY_ID = {
    "view3d":       "view3d",
    "view2d":       "view2d",
    "object":       "object",
    "mesh":         "mesh",
    "curve":        "curve",
    "armature":     "armature",
    "pose":         "pose",
    "sculpt":       "sculpt",
    "paint":        "paint",
    "paintcurve":   "paint",
    "palette":      "paint",
    "anim":         "animation",
    "action":       "animation",
    "nla":          "animation",
    "marker":       "animation",
    "time":         "animation",
    "node":         "node_editor",
    "uv":           "uv",
    "image":        "image",
    "sequencer":    "sequencer",
    "outliner":     "outliner",
    "transform":    "transform",
    "render":       "render",
    "cycles":       "render",
    "screen":       "screen",
    "wm":           "screen",
    "workspace":    "screen",
    "particle":     "particle",
    "ptcache":      "particle",
    "font":         "font",
    "gpencil":      "grease_pencil",
    "grease_pencil": "grease_pencil",
    "curves":       "curves",
    "sculpt_curves": "curves",
}

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_cache: dict | None = None  # { category_id: { subcategory_label: [(op_id, label)] } }
_addon_cache: dict | None = None  # { addon_name: [(op_id, label)] }


def _get_op_label(op_id: str) -> str:
    """Best available label: the curated friendly-names table first (Blender's
    own bl_label can be unfindable — outliner.select_all is "Toggle Selected"),
    then the RNA bl_label, then a prettified id."""
    try:
        from .friendly_ops import FRIENDLY_NAMES
        entry = FRIENDLY_NAMES.get(op_id)
        if entry and entry[0]:
            return entry[0]
    except Exception:
        pass
    try:
        module, func = op_id.split(".", 1)
        rna = getattr(getattr(bpy.ops, module), func).get_rna_type()
        label = rna.name
        if label and label != rna.identifier:
            return label
    except Exception:
        pass
    return op_id.split(".")[-1].replace("_", " ").title()


def _build_static_lookup() -> tuple[dict, dict]:
    """
    Build two lookups from categories.py:
    - op_to_sub: { op_id: (cat_id, sub_label) }
    - cat_subs:  { cat_id: [sub_label, ...] }  — ordered list of subcategory labels
    """
    from .categories import CATEGORIES
    op_to_sub = {}
    cat_subs  = {}
    for cat in CATEGORIES:
        cat_id = cat["id"]
        cat_subs[cat_id] = []
        for sub in cat["subcategories"]:
            sub_label = sub["label"]
            cat_subs[cat_id].append(sub_label)
            for op_id in sub["operators"]:
                op_to_sub[op_id] = (cat_id, sub_label)
    return op_to_sub, cat_subs


def scan(force: bool = False) -> tuple[dict, dict]:
    """
    Unified scan of all bpy.ops.

    Returns:
      builtin_ops: { cat_id: { sub_label: [(op_id, label)] } }
      addon_ops:   { addon_name: [(op_id, label)] }
    """
    global _cache, _addon_cache
    if _cache is not None and _addon_cache is not None and not force:
        return _cache, _addon_cache

    op_to_sub, cat_subs = _build_static_lookup()

    # Get full addon operator set from operator_discovery
    try:
        from ..operator_discovery import (get_addon_operators_by_addon,
                                          get_deep_scan_operators,
                                          has_deep_scan_results)
        # Build { op_id: addon_name } map
        addon_op_map: dict = {}
        for addon_name, ops in get_addon_operators_by_addon().items():
            for oid, lbl in ops:
                addon_op_map[oid] = (addon_name, lbl)
        if has_deep_scan_results():
            for addon_name, ops in get_deep_scan_operators().items():
                for oid, lbl in ops:
                    if oid not in addon_op_map:
                        addon_op_map[oid] = (addon_name, lbl)
    except Exception:
        addon_op_map = {}

    builtin: dict = {}
    addons:  dict = {}

    # First add all known addon ops directly (no blocklist check — these belong in Addon Operators)
    for oid, (addon_name, lbl) in addon_op_map.items():
        addons.setdefault(addon_name, []).append((oid, lbl))

    # Then scan bpy.ops for everything else
    from ..operator_discovery import _bpy_ops_map as _bom
    _map = _bom()
    for mod_name in sorted(_map):
        if mod_name.startswith("_"):
            continue
        mod = getattr(bpy.ops, mod_name)

        for op_name in sorted(_map[mod_name]):
            if op_name.startswith("_"):
                continue
            op_id = f"{mod_name}.{op_name}"

            # Hide Keymapper's own internal UI operators. The user should never
            # bind shortcuts to Keymapper's machinery (form_confirm, add_entry,
            # etc.). Rule: anything under the "keymapper." namespace is hidden
            # UNLESS it's a bundled user-facing operator, which all live under
            # the "keymapper.op_*" prefix. (Bundled ops are also in addon_op_map
            # and handled before this scan, so this is a belt-and-braces guard.)
            if mod_name == "keymapper" and not op_name.startswith("op_"):
                continue

            if op_id in OPERATOR_BLOCKLIST:
                continue
            if op_id in addon_op_map:
                continue  # Already handled above

            label = _get_op_label(op_id)

            if op_id in op_to_sub:
                cat_id, sub_label = op_to_sub[op_id]
            else:
                cat_id = MODULE_TO_CATEGORY_ID.get(mod_name)
                if cat_id is None:
                    cat_id    = "_other"
                    # Use module name as subcategory label for Other
                    sub_label = mod_name.replace("_", " ").title()
                else:
                    sub_label = "Other"

            builtin.setdefault(cat_id, {}).setdefault(sub_label, []).append((op_id, label))

    # Inject static entries that weren't found in bpy.ops scan
    # (e.g. tool_settings.* which are properties, not bpy.ops operators)
    for op_id, (cat_id, sub_label) in op_to_sub.items():
        if op_id in OPERATOR_BLOCKLIST:
            continue
        if op_id in addon_op_map:
            continue
        # Check if already added by bpy.ops scan
        already = any(
            op_id in [oid for oid, _ in builtin.get(cat_id, {}).get(sub_label, [])]
            for _ in [None]
        )
        if not already:
            label = op_id.split(".")[-1].replace("_", " ").title()
            builtin.setdefault(cat_id, {}).setdefault(sub_label, []).append((op_id, label))

    # Sort
    for cat_id in builtin:
        for sub_label in builtin[cat_id]:
            builtin[cat_id][sub_label].sort(key=lambda x: x[1].lower())
    for addon_name in addons:
        addons[addon_name].sort(key=lambda x: x[1].lower())

    _cache       = builtin
    _addon_cache = addons
    return builtin, addons


def get_builtin_ops(force: bool = False) -> dict:
    """Return { cat_id: { sub_label: [(op_id, label)] } }"""
    builtin, _ = scan(force=force)
    return builtin


def get_addon_ops(force: bool = False) -> dict:
    """Return { addon_name: [(op_id, label)] }"""
    _, addons = scan(force=force)
    return addons


def invalidate_cache():
    global _cache, _addon_cache
    _cache       = None
    _addon_cache = None
