"""
op_properties.py — Static metadata about operator properties.

Flags which properties are BFA-only, which have known valid value sets,
and which operators require properties at all.
"""

# Operators that REQUIRE at least one property to be meaningful.
# Format: { "op_id": { "prop_name": { "label", "type", "bfa_only", "values_from" } } }
# values_from: None = free text, "menus" = registered menus, "panels" = registered panels,
#              "pie_menus" = pie menus, "operator_types" = operator bl_idnames

OPERATOR_PROPERTIES: dict = {
    "wm.call_menu": {
        "_derives_context": False,
        "name": {
            "label":       "Menu",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": "menus",
        }
    },
    "wm.call_menu_pie": {
        "_derives_context": False,
        "name": {
            "label":       "Pie Menu",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": "pie_menus",
        }
    },
    "wm.call_panel": {
        "_derives_context": False,
        "name": {
            "label":       "Panel",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": "panels",
        }
    },
    "wm.tool_set_by_id": {
        "_derives_context": True,
        "name": {
            "label":       "Tool ID",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": "tool_ids",
        }
    },
    "wm.context_set_enum": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":     {"label": "Value",     "type": "STRING", "bfa_only": False, "values_from": None},
    },
    "wm.context_toggle": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
    },
    "wm.context_toggle_enum": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value_1":   {"label": "Value 1",   "type": "STRING", "bfa_only": False, "values_from": None},
        "value_2":   {"label": "Value 2",   "type": "STRING", "bfa_only": False, "values_from": None},
    },
    "wm.context_set_value": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":     {"label": "Value",     "type": "STRING", "bfa_only": False, "values_from": None},
    },
    "wm.context_set_int": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":     {"label": "Value",     "type": "INT",    "bfa_only": False, "values_from": None},
    },
    "wm.context_set_float": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":     {"label": "Value",     "type": "FLOAT",  "bfa_only": False, "values_from": None},
    },
    "wm.context_set_boolean": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":     {"label": "Value",     "type": "BOOL",   "bfa_only": False, "values_from": None},
    },
    "wm.context_set_string": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":     {"label": "Value",     "type": "STRING", "bfa_only": False, "values_from": None},
    },
    "wm.context_set_id": {
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":     {"label": "Value",     "type": "STRING", "bfa_only": False, "values_from": None},
    },
    "wm.context_scale_float": {
        "_derives_context": True,
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":     {"label": "Factor",    "type": "FLOAT",  "bfa_only": False, "values_from": None},
    },
    "wm.context_scale_int": {
        "_derives_context": True,
        "data_path":   {"label": "Context Attributes",   "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "value":       {"label": "Value",        "type": "INT",    "bfa_only": False, "values_from": None},
        "always_step": {"label": "Always Step",  "type": "BOOL",   "bfa_only": False, "values_from": None},
    },
    "wm.context_cycle_enum": {
        "_derives_context": True,
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "reverse":   {"label": "Reverse",   "type": "BOOL",   "bfa_only": False, "values_from": None},
        "wrap":      {"label": "Wrap",       "type": "BOOL",   "bfa_only": False, "values_from": None},
    },
    "wm.context_cycle_int": {
        "_derives_context": True,
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "reverse":   {"label": "Reverse",   "type": "BOOL",   "bfa_only": False, "values_from": None},
    },
    "wm.context_cycle_array": {
        "_derives_context": True,
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
        "reverse":   {"label": "Reverse",   "type": "BOOL",   "bfa_only": False, "values_from": None},
    },
    "wm.context_menu_enum": {
        "_derives_context": True,
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
    },
    "wm.context_pie_enum": {
        "_derives_context": True,
        "data_path": {"label": "Context Attributes", "type": "STRING", "bfa_only": False, "values_from": "context_path"},
    },
    "wm.context_modal_mouse": {
        "_derives_context": True,
        "data_path_iter": {"label": "Data Path (Iterator)", "type": "STRING", "bfa_only": False, "values_from": None},
        "data_path_item": {"label": "Data Path (Item)",     "type": "STRING", "bfa_only": False, "values_from": None},
        "input_scale":    {"label": "Input Scale",           "type": "FLOAT",  "bfa_only": False, "values_from": None},
    },
    "wm.context_collection_boolean_set": {
        "_derives_context": True,
        "data_path_iter": {
            "label":       "Data Path (Iterator)",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": None,
        },
        "data_path_item": {
            "label":       "Data Path (Item)",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": None,
        },
        "type": {
            "label":       "Type",
            "type":        "ENUM",
            "bfa_only":    False,
            "values_from": None,
        },
    },
    "wm.tool_set_by_id": {
        "name": {
            "label":       "Tool ID",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": "tool_ids",
        },
    },
    "wm.tool_set_by_name": {
        "name": {
            "label":       "Tool Name",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": "tool_ids",
        },
    },
    "script.python_file_run": {
        "_derives_context": True,
        "filepath": {
            "label":       "File Path",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": None,
        },
    },
    "script.execute_preset": {
        "_derives_context": True,
        "filepath": {
            "label":       "File Path",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": None,
        },
        "menu_idname": {
            "label":       "Menu ID",
            "type":        "STRING",
            "bfa_only":    False,
            "values_from": None,
        },
    },
}


def get_op_props(op_id: str) -> dict:
    """Return property metadata for an operator.

    Strategy:
    1. Read all props from RNA (bpy.ops.<op>.get_rna_type().properties)
    2. Apply OPERATOR_PROPERTIES overrides on top.
    Skips internal RNA props and collection/pointer props.
    """
    import bpy

    _SKIP_IDS   = {"rna_type"}
    _SKIP_TYPES = {"COLLECTION", "POINTER"}
    _TYPE_MAP   = {
        "BOOLEAN": "BOOL",
        "INT":     "INT",
        "FLOAT":   "FLOAT",
        "STRING":  "STRING",
        "ENUM":    "ENUM",
    }

    # Step 1: RNA scan
    rna_props = {}
    try:
        module, func = op_id.split(".", 1)
        rna_type = getattr(getattr(bpy.ops, module), func).get_rna_type()
        for rna_prop in rna_type.properties:
            pid = rna_prop.identifier
            if pid in _SKIP_IDS or pid.startswith("_"):
                continue
            if rna_prop.type in _SKIP_TYPES:
                continue
            # Skip props not intended for user interaction
            try:
                if rna_prop.is_hidden:
                    continue
                if rna_prop.is_readonly:
                    continue
                if rna_prop.is_skip_save:
                    continue
                if rna_prop.is_output:
                    continue
            except Exception:
                pass
            mapped = _TYPE_MAP.get(rna_prop.type, "STRING")
            entry = {
                "label":       rna_prop.name or pid.replace("_", " ").title(),
                "type":        mapped,
                "bfa_only":    False,
                "values_from": None,
            }
            if mapped == "ENUM":
                try:
                    entry["enum_items"] = [(i.identifier, i.name)
                                           for i in rna_prop.enum_items]
                except Exception:
                    entry["enum_items"] = []
            rna_props[pid] = entry
    except Exception:
        pass

    # Step 2: Apply overrides from OPERATOR_PROPERTIES
    overrides = {k: v for k, v in OPERATOR_PROPERTIES.get(op_id, {}).items()
                 if not k.startswith("_")}
    for pid, override in overrides.items():
        if pid in rna_props:
            rna_props[pid].update(override)
        else:
            rna_props[pid] = override

    return rna_props


def get_picker_prop_names(op_id: str) -> set:
    """Property names that are managed by a curated inline picker (values_from)
    and stored in the entry's legacy string `props`. These are excluded from the
    native props_data blob so the picker stays the single source of truth."""
    meta = OPERATOR_PROPERTIES.get(op_id, {})
    return {
        k
        for k, v in meta.items()
        if not k.startswith("_") and isinstance(v, dict) and v.get("values_from")
    }


def op_derives_context(op_id: str) -> bool:
    """Return True if this operator derives its context from its props (e.g. menu prefix)."""
    return OPERATOR_PROPERTIES.get(op_id, {}).get("_derives_context", False)


def get_context_from_menu_name(menu_name: str) -> tuple:
    """
    Given a menu ID like VIEW3D_MT_snap_pie, return (keymap_name, space_type, region_type).
    Returns ("Window", "EMPTY", "WINDOW") as fallback.
    """
    if not menu_name:
        return ("Window", "EMPTY", "WINDOW")

    prefix = menu_name.split("_")[0].upper()

    # Map prefix -> (keymap_name, space_type, region_type)
    _PREFIX_TO_CONTEXT = {
        "VIEW3D":      ("3D View",              "VIEW_3D",         "WINDOW"),
        "OBJECT":      ("Object Mode",          "EMPTY",           "WINDOW"),
        "MESH":        ("Mesh",                 "EMPTY",           "WINDOW"),
        "CURVE":       ("Curve",                "EMPTY",           "WINDOW"),
        "ARMATURE":    ("Armature",             "EMPTY",           "WINDOW"),
        "POSE":        ("Pose",                 "EMPTY",           "WINDOW"),
        "SCULPT":      ("Sculpt",               "EMPTY",           "WINDOW"),
        "PAINT":       ("Image Paint",          "EMPTY",           "WINDOW"),
        "GPENCIL":     ("Grease Pencil",        "EMPTY",           "WINDOW"),
        "OUTLINER":    ("Outliner",             "OUTLINER",        "WINDOW"),
        "IMAGE":       ("Image",                "IMAGE_EDITOR",    "WINDOW"),
        "UV":          ("UV Editor",            "EMPTY",           "WINDOW"),
        "NODE":        ("Node Editor",          "NODE_EDITOR",     "WINDOW"),
        "GRAPH":       ("Graph Editor",         "GRAPH_EDITOR",    "WINDOW"),
        "DOPESHEET":   ("Dopesheet",            "DOPESHEET_EDITOR","WINDOW"),
        "ACTION":      ("Dopesheet",            "DOPESHEET_EDITOR","WINDOW"),
        "NLA":         ("NLA Editor",           "NLA_EDITOR",      "WINDOW"),
        "SEQUENCER":   ("Sequencer",            "SEQUENCE_EDITOR", "WINDOW"),
        "SEQ":         ("Sequencer",            "SEQUENCE_EDITOR", "WINDOW"),
        "CLIP":        ("Clip Editor",          "CLIP_EDITOR",     "WINDOW"),
        "TEXT":        ("Text",                 "TEXT_EDITOR",     "WINDOW"),
        "CONSOLE":     ("Console",              "CONSOLE",         "WINDOW"),
        "INFO":        ("Info",                 "INFO",            "WINDOW"),
        "FILE":        ("File Browser",         "FILE_BROWSER",    "WINDOW"),
        "ASSET":       ("Asset Browser Main",   "FILE_BROWSER",    "WINDOW"),
        "SPREADSHEET": ("Spreadsheet Generic",  "SPREADSHEET",     "WINDOW"),
        "PREFERENCES": ("Preferences",          "PREFERENCES",     "WINDOW"),
        "PROPERTIES":  ("Property Editor",      "PROPERTIES",      "WINDOW"),
        "SCREEN":      ("Screen",               "EMPTY",           "WINDOW"),
        "WM":          ("Window",               "EMPTY",           "WINDOW"),
        "TOPBAR":      ("Window",               "EMPTY",           "WINDOW"),
        "STATUSBAR":   ("Screen",               "EMPTY",           "WINDOW"),
        "PARTICLE":    ("Particle",             "EMPTY",           "WINDOW"),
        "LATTICE":     ("Lattice",              "EMPTY",           "WINDOW"),
        "FONT":        ("Font",                 "EMPTY",           "WINDOW"),
        "MBALL":       ("Metaball",             "EMPTY",           "WINDOW"),
        "CURVES":      ("Sculpt Curves",        "EMPTY",           "WINDOW"),
        "PHYSICS":     ("Property Editor",      "PROPERTIES",      "WINDOW"),
        "RENDER":      ("Property Editor",      "PROPERTIES",      "WINDOW"),
        "MATERIAL":    ("Property Editor",      "PROPERTIES",      "WINDOW"),
    }
    return _PREFIX_TO_CONTEXT.get(prefix, ("Window", "EMPTY", "WINDOW"))


def op_requires_context(op_id: str) -> bool:
    """Return True if this operator needs an explicit keymap context."""
    from .keymap_contexts import context_requires_selection
    return context_requires_selection(op_id)


def op_can_repeat(op_id: str) -> bool:
    """Return True if this operator can be added multiple times with different props.
    Only operators with at least one STRING prop make sense to repeat — those
    are the ones where different instances point to different targets
    (e.g. wm.context_toggle with different data_path values).
    """
    props = get_op_props(op_id)
    return any(meta.get("type") == "STRING" for meta in props.values())


# Map editor prefix to context names
# Maps menu/panel ID prefix -> list of keymap context names where it applies
_EDITOR_PREFIX_MAP = {
    "VIEW3D":      ["3D View", "3D View Generic", "Object Mode", "Mesh", "Curve",
                    "Armature", "Pose", "Sculpt", "Sculpt Curves", "Vertex Paint",
                    "Weight Paint", "Image Paint", "Particle", "Grease Pencil",
                    "Grease Pencil Draw Mode", "Grease Pencil Edit Mode"],
    "OBJECT":      ["3D View", "3D View Generic", "Object Mode"],
    "MESH":        ["3D View", "Mesh"],
    "CURVE":       ["3D View", "Curve"],
    "ARMATURE":    ["3D View", "Armature"],
    "POSE":        ["3D View", "Pose"],
    "SCULPT":      ["3D View", "Sculpt"],
    "PAINT":       ["3D View", "Vertex Paint", "Weight Paint", "Image Paint"],
    "GPENCIL":     ["3D View", "Grease Pencil", "Grease Pencil Draw Mode",
                    "Grease Pencil Edit Mode"],
    "OUTLINER":    ["Outliner"],
    "IMAGE":       ["Image", "Image Generic", "UV Editor"],
    "UV":          ["Image", "UV Editor"],
    "NODE":        ["Node Editor", "Node Generic"],
    "GRAPH":       ["Graph Editor", "Graph Editor Generic"],
    "DOPESHEET":   ["Dopesheet", "Dopesheet Generic"],
    "ACTION":      ["Dopesheet", "Graph Editor"],
    "NLA":         ["NLA Editor", "NLA Generic"],
    "SEQUENCER":   ["Sequencer", "Video Sequence Editor"],
    "SEQ":         ["Sequencer", "Video Sequence Editor"],
    "CLIP":        ["Clip", "Clip Editor"],
    "MASK":        ["Clip", "Image", "UV Editor"],
    "INFO":        ["Info"],
    "TEXT":        ["Text", "Text Generic"],
    "CONSOLE":     ["Console"],
    "PROPERTIES":  ["Property Editor"],
    "FILE":        ["File Browser", "File Browser Main"],
    "ASSET":       ["File Browser", "Asset Browser Main"],
    "SPREADSHEET": ["Spreadsheet Generic"],
    "PREFERENCES": ["Preferences"],
    "SCREEN":      ["Screen", "Window"],
    "WM":          ["Window", "Screen"],
    "TOPBAR":      ["Window", "Screen"],
    "STATUSBAR":   ["Window", "Screen"],
    "PARTICLE":    ["3D View", "Particle"],
    "LATTICE":     ["3D View", "Lattice"],
    "FONT":        ["3D View", "Font"],
    "MBALL":       ["3D View", "Metaball"],
    "CURVES":      ["3D View", "Sculpt Curves"],
    "POINTCLOUD":  ["3D View", "Point Cloud"],
    "PHYSICS":     ["Property Editor"],
    "RENDER":      ["Property Editor"],
    "MATERIAL":    ["Property Editor"],
    "SCENE":       ["Property Editor"],
    "WORLD":       ["Property Editor"],
    "OBJECT_DATA": ["Property Editor"],
}


def _get_menu_editor_prefix(menu_name: str) -> str:
    """Return the editor prefix for a menu name like VIEW3D_MT_snap_pie -> VIEW3D"""
    parts = menu_name.split("_")
    return parts[0] if parts else ""


def _get_addon_name(cls) -> str:
    """Return bl_info name for addon-registered classes, empty string for builtins."""
    import sys
    module_root = (getattr(cls, "__module__", "") or "").split(".")[0]
    # Keymapper's own menu/panel/pie classes live under this package; group
    # them under "Keymapper" regardless of how the addon folder is named.
    pkg_root = (__name__ or "").split(".")[0]
    full_mod = getattr(cls, "__module__", "") or ""
    if pkg_root and (full_mod == pkg_root or full_mod.startswith(pkg_root + ".")):
        return "Keymapper"
    # Skip clearly built-in modules
    if module_root in ("bpy", "bpy_types", "_bpy", "bl_operators",
                       "bl_ui", "bl_app_override", "rna_keymap_ui"):
        return ""
    mod = sys.modules.get(module_root)
    if not mod or not hasattr(mod, "bl_info"):
        return ""
    return mod.bl_info.get("name", "").strip()


# Addon names that are Blender system internals — exclude from addon grouping
_ADDON_NAME_EXCLUSIONS = {
    "Extensions",
}

# Manual display name overrides — map multiple bl_info names to one addon display name.
# Format: { "raw bl_info name": "Display Name" }
_ADDON_NAME_OVERRIDES = {
    "Marking Menu":  "MayaConfigPro",
    "QuadView Menu": "MayaConfigPro",
    "Tab Switcher":  "MayaConfigPro",
}


_module_name_cache: dict = {}


def _get_cached_addon_name(cls) -> str:
    module_root = (getattr(cls, "__module__", "") or "").split(".")[0]
    if module_root not in _module_name_cache:
        raw = _get_addon_name(cls)
        if raw in _ADDON_NAME_EXCLUSIONS:
            _module_name_cache[module_root] = ""
        else:
            _module_name_cache[module_root] = _ADDON_NAME_OVERRIDES.get(raw, raw)
    return _module_name_cache[module_root]


# Derive prefix→display-category from existing _EDITOR_PREFIX_MAP (first entry = display name)
# with a few overrides for cleaner names
_PREFIX_TO_CATEGORY = {p: v[0] for p, v in _EDITOR_PREFIX_MAP.items()}
_PREFIX_TO_CATEGORY.update({
    "USERPREF":    "User Preferences",
    "TOPBAR":      "Topbar",
    "STATUSBAR":   "Status Bar",
    "SCREEN":      "Screen",
    "WM":          "Window Manager",
    "OBJECT":      "Object Mode",
    "NLA":         "NLA Editor",
    "SEQ":         "Sequencer",
})


def _get_builtin_category(name: str) -> str:
    prefix = name.split("_")[0].upper()
    return _PREFIX_TO_CATEGORY.get(prefix, "Other")


# Cache for get_prop_values(). Enumerating every menu/panel class in Blender is
# expensive (~650 menus, ~45 ms per call) and the class list only changes when
# addons register/unregister. Without this the UI called it once PER OPERATOR
# PER REDRAW: an entry holding 36 wm.call_menu ops (e.g. "Context Menu") cost
# ~440 ms per redraw in friendly-name mode, which froze scrolling. Raw-name mode
# never hit this path, which is why only friendly naming was slow.
_prop_values_cache: dict = {}


def invalidate_prop_values_cache():
    """Drop the cached menu/panel/tool enumerations (call after a rescan or an
    addon enable/disable, which can add or remove classes)."""
    _prop_values_cache.clear()


def get_prop_values(values_from: str, context_name: str = "") -> list:
    """Cached front-end for _get_prop_values_uncached (see cache note above)."""
    if values_from == "tools":  # legacy alias
        values_from = "tool_ids"
    _ck = (values_from, context_name)
    _hit = _prop_values_cache.get(_ck)
    if _hit is None:
        _hit = _get_prop_values_uncached(values_from, context_name)
        _prop_values_cache[_ck] = _hit
    return _hit



def _ident_tail_label(identifier: str) -> str:
    """'VIEW3D_MT_edit_curves' -> 'Edit Curves' — readable fallback for
    menu/panel classes that ship without a bl_label."""
    import re
    m = re.search(r"_(?:MT|PT|HT|OT)_(.+)$", identifier)
    tail = m.group(1) if m else identifier
    return " ".join(t.title() for t in tail.split("_") if t) or identifier


def _pretty_ident_prefix(identifier: str, label: str) -> str:
    """'VIEW3D_MT_edit_curves_add' + label 'Add' -> 'View3D_MT_Edit_Curves'.

    Strips the label-derived tail from the identifier and title-cases the
    remaining tokens (keeping type tags like MT/PT and re-capitalising
    digit-adjacent letters so VIEW3D reads View3D)."""
    import re
    tail = "_" + label.strip().lower().replace(" ", "_")
    base = identifier
    # Generic trailing type-words ("..._pie", "..._menu", "..._panel") don't
    # help distinguish anything — drop them before the label-tail strip so
    # the qualifier stays short.
    for _suf in ("_pie", "_menu", "_panel"):
        if base.lower().endswith(_suf):
            base = base[: -len(_suf)]
    if base.lower().endswith(tail) and len(base) > len(tail):
        base = base[: -len(tail)]
    parts = []
    for tok in base.split("_"):
        if not tok:
            continue
        if tok.upper() in ("MT", "PT", "HT", "OT") and len(tok) == 2:
            parts.append(tok.upper())
        else:
            t = tok.capitalize()
            t = re.sub(r"(\d)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
            parts.append(t)
    return "_".join(parts)


def _disambiguate_labels(final: list) -> list:
    """Append an identifier-derived qualifier to labels that appear more than
    once, so e.g. three menus all called 'Add' become 'Add (Mask_MT)',
    'Add (View3D_MT)', 'Add (View3D_MT_Edit_Curves)'. Header sentinels pass
    through untouched."""
    counts = {}
    for ident, label in final:
        if ident in ("__GROUP_HEADER__", "__SUBGROUP_HEADER__"):
            continue
        counts[label] = counts.get(label, 0) + 1
    out = []
    for ident, label in final:
        if (ident not in ("__GROUP_HEADER__", "__SUBGROUP_HEADER__")
                and counts.get(label, 0) > 1):
            out.append((ident, f"{label} ({_pretty_ident_prefix(ident, label)})"))
        else:
            out.append((ident, label))
    return out


def _get_prop_values_uncached(values_from: str, context_name: str = "") -> list:
    """
    Return (id, label) pairs. Builtins grouped by editor category (alpha),
    addon menus at the bottom under a single Addon parent.
    """
    import bpy
    builtin_cats = {}   # { category: [(id, label)] }
    addon_groups = {}   # { addon_name: [(id, label)] }

    valid_prefixes: set = set()
    if context_name:
        for prefix, contexts in _EDITOR_PREFIX_MAP.items():
            if context_name in contexts:
                valid_prefixes.add(prefix)
        valid_prefixes.update({"WM", "SCREEN", "TOPBAR", "STATUSBAR"})

    if values_from == "python_files":
        import os
        results = []
        try:
            for base in bpy.utils.script_paths():
                for root, dirs, files in os.walk(base):
                    for f in sorted(files):
                        if f.endswith(".py"):
                            full = os.path.join(root, f)
                            results.append((full, f))
        except Exception:
            pass
        results.sort(key=lambda x: x[1].lower())
        return results

    if values_from == "tool_ids":
        results = []
        try:
            import bpy
            # Scan keyconfig for all wm.tool_set_by_id entries — most reliable method
            seen = {}
            kc = bpy.context.window_manager.keyconfigs.active
            if kc is None:
                kc = bpy.context.window_manager.keyconfigs.default
            if kc:
                for km in kc.keymaps:
                    for kmi in km.keymap_items:
                        if kmi.idname == "wm.tool_set_by_id":
                            try:
                                tid = kmi.properties.name
                                if tid and tid not in seen:
                                    # Convert "builtin.select_box" → "Box Select"
                                    label = tid.split(".")[-1].replace("_", " ").title()
                                    seen[tid] = label
                            except Exception:
                                pass
            # The keymap scan only finds tools that HAVE a keybinding —
            # enumerate the real tool system too, so unbound tools (e.g.
            # builtin.select_circle) appear, with their REAL labels.
            try:
                from bl_ui.space_toolsystem_common import (
                    ToolSelectPanelHelper as _TSPH,
                )
                for _tn in dir(bpy.types):
                    _cls = getattr(bpy.types, _tn, None)
                    try:
                        if not (isinstance(_cls, type)
                                and issubclass(_cls, _TSPH)
                                and _cls is not _TSPH):
                            continue
                    except Exception:
                        continue
                    try:
                        for _mode, _tools in _cls.tools_all():
                            for _item in _TSPH._tools_flatten(_tools):
                                if _item is None:
                                    continue
                                _tid = getattr(_item, "idname", None)
                                _tlb = getattr(_item, "label", None)
                                if not _tid:
                                    continue
                                # ToolDef labels are authoritative;
                                # they override keymap-derived guesses.
                                if _tlb:
                                    seen[_tid] = str(_tlb)
                                elif _tid not in seen:
                                    seen[_tid] = (_tid.split(".")[-1]
                                                  .replace("_", " ").title())
                    except Exception:
                        continue
            except Exception:
                pass
            # --- PURE-ID-based naming ---
            # Brush family: builtin_brush.* reads "Brush (Func)".
            _TOKP = {"uv": "UV", "gp": "Grease Pencil", "vert": "Vertex"}

            def _tokpretty(toks):
                return " ".join(_TOKP.get(t, t.title()) for t in toks)

            try:
                # Family rename with a collision guard: brush ids that
                # differ only in case (builtin_brush.fill vs .Fill) keep
                # their RAW function spelling instead of double-qualifying.
                _brush = {t: t.split(".", 1)[1] for t in seen
                          if t.startswith("builtin_brush.")}
                from collections import Counter as _Ctr
                _bcount = _Ctr(_tokpretty(f.split("_"))
                               for f in _brush.values())
                for _tid, _fn in _brush.items():
                    _p = _tokpretty(_fn.split("_"))
                    if _bcount[_p] > 1:
                        _p = _fn.replace("_", " ")
                    seen[_tid] = f"Brush ({_p})"
                # Remaining duplicate labels: qualify from the PURE id — the
                # canonical builtin whose function name IS the label keeps
                # the bare name; the rest add their distinguishing id tokens
                # ("Relax (UV Sculpt)"), else their module ("(Sequencer)"),
                # else their function name; raw function as tie-breaker.
                import re as _re
                _by_lbl = {}
                for _tid, _lbl in seen.items():
                    _by_lbl.setdefault(_lbl, []).append(_tid)
                _final_used = set(
                    l for l, ids in _by_lbl.items() if len(ids) == 1)
                for _lbl, _ids in sorted(_by_lbl.items()):
                    if len(_ids) < 2:
                        continue
                    _lt = set(_re.findall(r"[a-z0-9]+", _lbl.lower()))
                    for _tid in sorted(_ids):
                        _mod, _fn = _tid.split(".", 1)
                        _ft = [t for t in _fn.lower().split("_") if t]
                        _left = [t for t in _ft if t not in _lt]
                        if (_mod == "builtin" and not _left
                                and set(_ft) == _lt
                                and _lbl not in _final_used):
                            _final_used.add(_lbl)   # canonical stays bare
                            continue
                        if _left:
                            _q = _tokpretty(_left)
                        elif _mod not in ("builtin", "builtin_brush"):
                            _q = _tokpretty(_mod.split("_"))
                        else:
                            _q = _tokpretty(_fn.split("_"))
                        _cand = f"{_lbl} ({_q})"
                        if _cand in _final_used:
                            _cand = f"{_lbl} ({_fn})"
                        _final_used.add(_cand)
                        seen[_tid] = _cand
            except Exception:
                pass
            # Name-family groups ("Brush", "Annotate", "Box", …): tools whose
            # labels share a first word (3+ of them) fold into a collapsible
            # group; the rest stay as flat top-level rows.
            _items = sorted(seen.items(), key=lambda x: x[1].lower())
            _fams = {}
            for _tid, _lbl in _items:
                _w = _lbl.split(" ", 1)[0].strip("()")
                _fams.setdefault(_w, []).append((_tid, _lbl))
            _grp_names = sorted(
                w for w, lst in _fams.items() if len(lst) >= 3)
            _grouped = set()
            for _w in _grp_names:
                _grouped.update(t for t, _l in _fams[_w])
            results = [it for it in _items if it[0] not in _grouped]
            for _w in _grp_names:
                results.append(("__GROUP_HEADER__", _w))
                results.extend(_fams[_w])
        except Exception:
            pass
        return results if results else [
            ("builtin.select",        "Select"),
            ("builtin.select_box",    "Box Select"),
            ("builtin.select_circle", "Circle Select"),
            ("builtin.move",          "Move"),
            ("builtin.rotate",        "Rotate"),
            ("builtin.scale",         "Scale"),
            ("builtin.transform",     "Transform"),
            ("builtin.cursor",        "Cursor"),
        ]

    elif values_from in ("menus", "pie_menus"):
        for name in dir(bpy.types):
            t = getattr(bpy.types, name, None)
            if not t or not hasattr(t, "bl_label"):
                continue
            try:
                if not issubclass(t, bpy.types.Menu):
                    continue
            except Exception:
                continue

            is_pie = ("PIE" in name.upper() or
                      name.upper().endswith("_PIE") or
                      "_MT_PIE" in name.upper())
            if values_from == "pie_menus" and not is_pie:
                continue
            if values_from == "menus" and is_pie:
                continue

            label = (getattr(t, "bl_label", "") or ""
                     ) or _ident_tail_label(name)
            addon_name = _get_cached_addon_name(t)
            if addon_name:
                addon_groups.setdefault(addon_name, []).append((name, label))
            else:
                cat = _get_builtin_category(name)
                builtin_cats.setdefault(cat, []).append((name, label))

    elif values_from == "panels":
        for name in dir(bpy.types):
            t = getattr(bpy.types, name, None)
            if not t or not hasattr(t, "bl_label"):
                continue
            try:
                if not issubclass(t, bpy.types.Panel):
                    continue
            except Exception:
                continue
            prefix = _get_menu_editor_prefix(name)
            if valid_prefixes and prefix not in valid_prefixes:
                continue
            label = (getattr(t, "bl_label", "") or ""
                     ) or _ident_tail_label(name)
            addon_name = _get_cached_addon_name(t)
            if addon_name:
                addon_groups.setdefault(addon_name, []).append((name, label))
            else:
                cat = _get_builtin_category(name)
                builtin_cats.setdefault(cat, []).append((name, label))

    addon_label = {
        "menus":     "Addon Menus",
        "pie_menus": "Addon Pie Menus",
        "panels":    "Addon Panels",
    }.get(values_from, "Addon")

    final = []
    # Builtin categories alphabetically
    for cat_name in sorted(builtin_cats.keys()):
        entries = sorted(builtin_cats[cat_name], key=lambda x: x[1].lower())
        final.append(("__GROUP_HEADER__", cat_name))
        final.extend(entries)
    # Addon group at the bottom
    if addon_groups:
        final.append(("__GROUP_HEADER__", addon_label))
        for addon_name in sorted(addon_groups.keys()):
            entries = sorted(addon_groups[addon_name], key=lambda x: x[1].lower())
            final.append(("__SUBGROUP_HEADER__", addon_name))
            final.extend(entries)
    return _disambiguate_labels(final)


# ---------------------------------------------------------------------------
# Context path scanner — for "context_path" values_from
# ---------------------------------------------------------------------------

_context_paths_cache: list | None = None

def _scan_context_paths() -> list[str]:
    """Collect context attribute paths by walking RNA TYPES, not the live
    context. The live context depends on which editor invokes the form — from
    the Preferences window `space_data` is SpacePreferences, so 3D-view paths
    like `space_data.overlay.show_face_orientation` never made the list and
    Blender rendered the search field red (value not among suggestions).
    Type-walking is deterministic: `space_data` is the UNION of every Space
    subclass, regardless of where the form is drawn."""
    import bpy

    paths: set = set()
    SKIP_PREFIXES = ("bl_", "rna_")

    def _type_props(struct_rna):
        try:
            return list(struct_rna.properties)
        except Exception:
            return []

    def _walk_type(struct_rna, prefix, depth):
        for prop in _type_props(struct_rna):
            pid = prop.identifier
            if pid == "rna_type" or any(pid.startswith(p) for p in SKIP_PREFIXES):
                continue
            full = f"{prefix}.{pid}"
            paths.add(full)
            if depth == 0 and prop.type == "POINTER":
                try:
                    _walk_type(prop.fixed_type, full, depth + 1)
                except Exception:
                    pass

    def _rna(type_name):
        t = getattr(bpy.types, type_name, None)
        return getattr(t, "bl_rna", None) if t else None

    # space_data: union across every registered Space subclass. NOTE:
    # Space.__subclasses__() is unreliable (bpy.types attributes are created
    # lazily), so enumerate by name and force creation via getattr.
    try:
        _space_base = bpy.types.Space
        for _name in dir(bpy.types):
            if not _name.startswith("Space") or _name == "Space":
                continue
            _cls = getattr(bpy.types, _name, None)
            try:
                if _cls is None or not issubclass(_cls, _space_base):
                    continue
            except TypeError:
                continue
            rna = getattr(_cls, "bl_rna", None)
            if rna is not None:
                _walk_type(rna, "space_data", 0)
    except Exception:
        pass

    for prefix, type_name in (
        ("object",        "Object"),
        ("active_object", "Object"),
        ("scene",         "Scene"),
        ("area",          "Area"),
        ("region",        "Region"),
        ("tool_settings", "ToolSettings"),
        ("preferences",   "Preferences"),
    ):
        rna = _rna(type_name)
        if rna is not None:
            _walk_type(rna, prefix, 0)

    return sorted(paths)



# ---------------------------------------------------------------------------
# Friendly names for context attribute paths
# ---------------------------------------------------------------------------

_context_label_cache: dict = {}

# Roots used by context paths, mapped to the RNA type(s) they can resolve to.
# "space_data" is a union: which Space subclass applies depends on the editor.
_CONTEXT_ROOTS = {
    "object":        ("Object",),
    "active_object": ("Object",),
    "scene":         ("Scene",),
    "area":          ("Area",),
    "region":        ("Region",),
    "tool_settings": ("ToolSettings",),
    "preferences":   ("Preferences",),
}


def _root_rna_list(root: str) -> list:
    import bpy
    if root == "space_data":
        out = []
        try:
            base = bpy.types.Space
            # SpaceView3D first: several editors share attribute names under
            # `overlay`/`shading`, and the 3D view is what these paths almost
            # always mean (otherwise `overlay.show_cursor` resolved against
            # whichever Space came first alphabetically).
            _ordered = ["SpaceView3D"] + [
                n for n in dir(bpy.types) if n != "SpaceView3D"]
            for name in _ordered:
                if not name.startswith("Space") or name == "Space":
                    continue
                cls = getattr(bpy.types, name, None)
                try:
                    if cls is None or not issubclass(cls, base):
                        continue
                except TypeError:
                    continue
                rna = getattr(cls, "bl_rna", None)
                if rna is not None:
                    out.append(rna)
        except Exception:
            pass
        return out
    names = _CONTEXT_ROOTS.get(root, ())
    out = []
    for n in names:
        t = getattr(bpy.types, n, None)
        rna = getattr(t, "bl_rna", None) if t else None
        if rna is not None:
            out.append(rna)
    return out


def get_context_path_label(path: str) -> str:
    """Blender's own UI name for a context attribute path.

    "space_data.overlay.show_face_orientation" -> "Face Orientation".
    Resolved from RNA rather than a hand-kept table, so it stays correct as
    Blender changes. Returns "" when the path cannot be resolved.
    """
    if not path:
        return ""
    if path in _context_label_cache:
        return _context_label_cache[path]
    parts = [p for p in path.split(".") if p]
    label = ""
    if len(parts) >= 2:
        for rna in _root_rna_list(parts[0]):
            cur = rna
            ok = True
            for i, attr in enumerate(parts[1:], start=1):
                try:
                    prop = cur.properties.get(attr)
                except Exception:
                    prop = None
                if prop is None:
                    ok = False
                    break
                if i == len(parts) - 1:
                    label = getattr(prop, "name", "") or ""
                    break
                if prop.type == "POINTER":
                    cur = prop.fixed_type
                else:
                    ok = False
                    break
            if ok and label:
                break
            label = ""
    if not label:
        label = parts[-1].replace("_", " ").title() if parts else ""
    _context_label_cache[path] = label
    return label


def get_context_paths(search: str = "") -> list[str]:
    """Return all bpy.context paths, optionally filtered by search string."""
    global _context_paths_cache
    if _context_paths_cache is None:
        _context_paths_cache = _scan_context_paths()
    if not search:
        return _context_paths_cache
    sl = search.lower()
    return [p for p in _context_paths_cache if sl in p.lower()]
