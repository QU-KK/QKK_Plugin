"""
operator_discovery.py — Live operator discovery for Keymapper.

Queries bpy.ops at runtime to find ALL registered operators.
Separates built-in/static operators from third-party addon operators.
Caches results and supports refresh.
"""

import bpy

from .database.bfa_ops import get_friendly_name
from .database.categories import CATEGORIES

# ---------------------------------------------------------------------------
# Known built-in module prefixes — these belong to Blender/BFA core
# ---------------------------------------------------------------------------

# Operators that exist ONLY in BForArtists builds but register under standard
# Blender prefixes (scene.*, object.*, wm.*, uv.*, mesh.*), so the prefix-based
# addon detection can't spot them. Listed explicitly so they land in
# "Addon Operators > Bforartists" instead of polluting the built-in categories.
# (They previously lived in a hard-coded top-level "Bforartists" category, which
# also wrongly contained a pile of ordinary Blender operators.)
BFA_ONLY_OPERATORS = {
    "scene.cic_create_gameisocam",
    "scene.cic_create_trueisocam",
    "scene.cic_create_groundplane",
    "object.gpencil_modifier_apply",
    "object.gpencil_modifier_copy",
    "object.gpencil_modifier_remove",
    "wm.console_toggle",
    "uv.clear_seam",
    "mesh.dissolve_contextual_bfa",
}

BUILTIN_PREFIXES = {
    "object",
    "mesh",
    "curve",
    "curves",
    "surface",
    "armature",
    "pose",
    "sculpt",
    "paint",
    "vertex_paint",
    "weight_paint",
    "image",
    "uv",
    "node",
    "graph",
    "action",
    "nla",
    "anim",
    "sequencer",
    "scene",
    "screen",
    "wm",
    "window",
    "view3d",
    "view2d",
    "outliner",
    "text",
    "console",
    "file",
    "export_mesh",
    "import_mesh",
    "export_scene",
    "import_scene",
    "render",
    "particle",
    "gpencil",
    "grease_pencil",
    "lattice",
    "font",
    "mball",
    "transform",
    "ed",
    "clip",
    "mask",
    "marker",
    "constraint",
    "object_data",
    "material",
    "geometry",
    "spreadsheet",
    "info",
    "bake",
    "cycles",
    "rigidbody",
    "fluid",
    "cloth",
    "dynamic_paint",
    "ptcache",
    "physics",
    "preferences",
    "buttons",
    "asset",
    "anim",
    "poselib",
    "workspace",
    "collection",
    "world",
    "texture",
    "brush",
    "palette",
    "freestyle",
    "shader",
    "bone",
    "mesh_sequence_cache",
    "nla",
    "sound",
    "speaker",
    "light",
    "lightprobe",
    "camera",
    "empty",
    "force_field",
    "volume",
    # BFA-specific — intentionally NOT in BUILTIN_PREFIXES so they appear under BForArtists in Addon Operators
    # "bfa", "bforartists",
    # Additional built-in prefixes not covered above
    "action",
    "anim",
    "asset",
    "bone",
    "brush",
    "buttons",
    "camera",
    "cachefile",
    "clip",
    "cloth",
    "collection",
    "compositor",
    "console",
    "constraint",
    "curve",
    "curves",
    "dpaint",
    "empty",
    "fluid",
    "force_field",
    "freestyle",
    "lamp",
    "lattice",
    "light",
    "lightprobe",
    "linestyle",
    "marker",
    "mask",
    "material",
    "mesh",
    "mball",
    "nla",
    "object",
    "outliner",
    "paint",
    "palette",
    "particle",
    "pose",
    "poselib",
    "ptcache",
    "render",
    "rigidbody",
    "scene",
    "screen",
    "sculpt",
    "sequencer",
    "shader",
    "sound",
    "speaker",
    "surface",
    "text",
    "texture",
    "transform",
    "uv",
    "view2d",
    "view3d",
    "volume",
    "weight_paint",
    "vertex_paint",
    "workspace",
    "world",
    # Common bundled addon prefixes that are NOT third-party
    "io_",
    "bl_",
    "bpy_extras",

    # BFA/Blender built-ins discovered from live scan
    "asset_shelf",
    "boid",
    "dopesheet",
    "export_anim",
    "extensions",
    "gizmogroup",
    "import_anim",
    "import_curve",
    "mirror",
    "paintcurve",
    "pointcloud",
    "script",
    "sculpt_curves",
    "sequence",
    "text_editor",
    "topbar",
    "ui",
    "uilist",
    "wizard",
    # Mesh tools bundled addon
    "mesh_tools_addon",
    # Remaining built-ins
    "compositor",
    "dpaint",
    # Note: class, edit, popup, theme removed — used by MayaConfigPro
    # Note: keymapper removed — should appear in Addon Operators
}

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_cache_static: dict = {}  # known operators from static DB
_cache_addon: dict = {}  # third-party addon operators
_cache_built = False


def _get_static_op_ids() -> set:
    ids = set()
    for cat in CATEGORIES:
        for sub in cat["subcategories"]:
            for op_id in sub["operators"]:
                ids.add(op_id)
    return ids


# Map addon module prefixes to static category labels for auto-routing
# Bundled addons whose operators belong alongside built-ins in existing categories
ADDON_CATEGORY_ROUTES = {
    # node_wrangler has no own bpy.ops prefix — skip
    # Note: MayaConfigPro prefixes (class, edit, popup, theme) intentionally
    # NOT routed — they should appear in Addon Operators under MayaConfigPro
    "mesh_looptools": "Mesh",
    "mesh_f2": "Mesh",
    "mesh_snap_utilities_line": "Mesh",
    "add_curve_extra_objects": "Curve",
    "curve_tools": "Curve",
    "animation_animall": "Animation",
    "rigify": "Armature",
    "paint_palette": "Paint",
    "render_freestyle": "Render",
    "io_scene_gltf2": "Import / Export",
    "io_mesh_stl": "Import / Export",
    "io_mesh_ply": "Import / Export",
    "io_anim_bvh": "Import / Export",
    "io_curve_svg": "Import / Export",
    "io_scene_fbx": "Import / Export",
    "io_scene_x3d": "Import / Export",
    "io_import_images_as_planes": "Import / Export",
    "measureit": "3D View",
    "space_view3d_copy_attributes": "3D View",
}


# Known MayaConfigPro file prefixes (filename based)
_MCP_FILE_PREFIXES = {"fa_", "delete_without", "msm_"}
# Known bpy.ops prefixes that MCP registers operators under
_MCP_OPS_PREFIXES = {"edit", "class", "popup", "theme"}
_MCP_ADDON_NAME = "MayaConfigPro"

# Operators registered under built-in prefixes that actually belong to addons.
# These can't be detected via bl_info/portable scan since their prefix is built-in.
# Format: { op_id: addon_name }
MANUAL_ADDON_OPS = {
    # Keymapper bundled operators — registered by keymapper/bundled_ops/.
    # These always exist when Keymapper is enabled, so the existence check in
    # _discover_addon_operators will always include them. They live under the
    # "keymapper.op_*" namespace so the panel's hide-rule (which hides
    # Keymapper's internal UI operators) lets them through.
    "keymapper.op_open_assetbrowser_window": "Keymapper",
    "keymapper.op_pivot_transform": "Keymapper",
    "keymapper.op_marking_menu": "Keymapper",
    "keymapper.op_quick_view": "Keymapper",
    "keymapper.op_select_tool_pie": "Keymapper",
    # MayaConfigPro — operators registered under object.*, wm.*, view3d.*
    "view3d.modal_operator_raycast": "MayaConfigPro",
    "object.addasset": "MayaConfigPro",
    "object.applytransforms": "MayaConfigPro",
    "object.back_ortho": "MayaConfigPro",
    "object.bevel": "MayaConfigPro",
    "object.bottom_ortho": "MayaConfigPro",
    "object.bridgeloops": "MayaConfigPro",
    "object.camlockall": "MayaConfigPro",
    "object.camlocklocation": "MayaConfigPro",
    "object.camlocklocationx": "MayaConfigPro",
    "object.camlockrotation": "MayaConfigPro",
    "object.camlockscale": "MayaConfigPro",
    "object.campop": "MayaConfigPro",
    "object.campopup": "MayaConfigPro",
    "object.camview_lock": "MayaConfigPro",
    "object.delta_transfer": "MayaConfigPro",
    "object.edgesnap": "MayaConfigPro",
    "object.extrudeaxis": "MayaConfigPro",
    "object.extrudenormal": "MayaConfigPro",
    "object.facesnap": "MayaConfigPro",
    "object.front_ortho": "MayaConfigPro",
    "object.gizmodefault": "MayaConfigPro",
    "object.gridsnap": "MayaConfigPro",
    "object.hideorigin": "MayaConfigPro",
    "object.hidetheorigin": "MayaConfigPro",
    "object.insetfaces": "MayaConfigPro",
    "object.keycurvesnap": "MayaConfigPro",
    "object.keygridsnap": "MayaConfigPro",
    "object.keyvertexsnap": "MayaConfigPro",
    "object.knifetool": "MayaConfigPro",
    "object.left_ortho": "MayaConfigPro",
    "object.loopcut": "MayaConfigPro",
    "object.mirrorapply": "MayaConfigPro",
    "object.mirrorx": "MayaConfigPro",
    "object.mirrorx2": "MayaConfigPro",
    "object.mirrorz": "MayaConfigPro",
    "object.msm_from_object": "MayaConfigPro",
    "object.multi": "MayaConfigPro",
    "object.offsnap": "MayaConfigPro",
    "object.pivotlock": "MayaConfigPro",
    "object.right_ortho": "MayaConfigPro",
    "object.safe_area": "MayaConfigPro",
    "object.showguides": "MayaConfigPro",
    "object.showorigin": "MayaConfigPro",
    "object.split_view": "MayaConfigPro",
    "object.split_view_h": "MayaConfigPro",
    "object.subdivide": "MayaConfigPro",
    "object.themeblenderdark": "MayaConfigPro",
    "object.thememayablue": "MayaConfigPro",
    "object.thememayagradient": "MayaConfigPro",
    "object.thememodo": "MayaConfigPro",
    "object.themesketchup": "MayaConfigPro",
    "object.themewhitebg": "MayaConfigPro",
    "object.toggle_subsurf1": "MayaConfigPro",
    "object.toggle_subsurf2": "MayaConfigPro",
    "object.toggle_subsurf3": "MayaConfigPro",
    "object.top_ortho": "MayaConfigPro",
    "object.unsubdivide": "MayaConfigPro",
    "object.vertexsnap": "MayaConfigPro",
    "edit.delete_without_confirm": "MayaConfigPro",
    "wm.cone": "MayaConfigPro",
    "wm.cylinder": "MayaConfigPro",
    "wm.cylinderb": "MayaConfigPro",
    "wm.icosphere": "MayaConfigPro",
    "wm.meshcube": "MayaConfigPro",
    "wm.myop": "MayaConfigPro",
    "wm.myopinfo": "MayaConfigPro",
    "wm.plane": "MayaConfigPro",
    "wm.uvsphere": "MayaConfigPro",
}


def _scan_portable_startup() -> dict:
    """
    Scan portable/scripts/startup/ for user-dropped .py files.
    Returns { module_prefix: addon_display_name }
    Groups known MayaConfigPro files under one name.
    """
    import os
    import sys

    found = {}
    try:
        blender_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        for candidate in [
            os.path.join(blender_dir, "portable", "scripts", "startup"),
            os.path.join(
                os.path.dirname(blender_dir), "portable", "scripts", "startup"
            ),
        ]:
            if os.path.isdir(candidate):
                for fname in os.listdir(candidate):
                    if not fname.endswith(".py") or fname.startswith("_"):
                        continue
                    mod = fname[:-3].lower()
                    pfx = mod.split("_")[0]
                    # Check if this is a known MCP file
                    is_mcp = any(mod.startswith(p) for p in _MCP_FILE_PREFIXES)
                    name = _MCP_ADDON_NAME if is_mcp else mod.replace("_", " ").title()
                    found[mod] = name
                    found[pfx] = name
                    # If any MCP file is found, also register MCP ops prefixes
                    if is_mcp:
                        for ops_pfx in _MCP_OPS_PREFIXES:
                            found[ops_pfx] = _MCP_ADDON_NAME
                break
    except Exception as e:
        print(f"[Keymapper] portable scan: {e}")
    return found


def _addon_modules_snapshot() -> list:
    """`addon_utils.modules()` once, cached for this discovery pass.

    addon_utils.modules() defaults to refresh=True, which re-walks every add-on
    directory from disk (getmtime per add-on file/manifest, plus listdir/isfile
    per search path) on EVERY call. Calling it inside a per-operator loop meant
    one full directory walk per discovered add-on operator — tens of thousands
    of stat() calls per startup, and worse with more add-ons installed, since
    more add-ons means both more calls AND more files per call. That is I/O
    bound, so it stalls Blender while barely touching the CPU.

    The add-on set cannot change during one discovery pass, so one snapshot is
    enough. Invalidated by _invalidate_addon_modules() at the start of each
    build_cache()/deep_scan(), so a newly enabled add-on is still picked up.
    """
    global _addon_modules_cache
    if _addon_modules_cache is None:
        try:
            import addon_utils
            _addon_modules_cache = list(addon_utils.modules())
        except Exception:
            _addon_modules_cache = []
    return _addon_modules_cache


def _invalidate_addon_modules() -> None:
    global _addon_modules_cache
    _addon_modules_cache = None


def _addon_name_by_suffix(clean_prefix: str) -> str:
    """Name of the first add-on whose module path ends with `clean_prefix`.

    Identical logic to the loop this replaced (same order, same endswith test,
    same first-match-wins break) — the only change is that it walks the cached
    snapshot instead of calling addon_utils.modules(), which re-read the add-on
    directories from disk on every single call.
    """
    try:
        import addon_utils
        for mod in _addon_modules_snapshot():
            if (getattr(mod, "__name__", "") or "").lower().endswith(clean_prefix):
                try:
                    info = addon_utils.module_bl_info(mod)
                except Exception:
                    info = None
                if info and info.get("name"):
                    return info["name"]
                break
    except Exception:
        pass
    return ""


def _get_addon_bl_info() -> dict:
    """
    Return { module_prefix_or_id: addon_name } for all enabled addons.

    Two kinds of addons get mapped here:
      - Legacy addons: module name has no dots, e.g. "node_wrangler".
        Key: "node_wrangler" → name from bl_info["name"].
      - Extensions: module name like "bl_ext.blender_org.icon_viewer".
        We DO NOT key these by their first segment ("bl_ext") because all
        extensions share that prefix and would overwrite each other.
        Instead we key by the LAST segment (the actual addon id), and
        also by the full module path, so callers can look up by either.
    """
    mapping = {}
    try:
        import addon_utils

        for mod in _addon_modules_snapshot():
            try:
                info = addon_utils.module_bl_info(mod)
            except Exception:
                info = {}
            name = mod.__name__
            if name.startswith("bl_ext."):
                # Extension. Use bl_info name if available, otherwise
                # prettify just the last segment (the addon id).
                last_seg = name.rsplit(".", 1)[-1] if "." in name else name
                friendly = (info.get("name") if info else None) or last_seg.replace(
                    "_", " "
                ).title()
                # Key by full module path AND by the last segment so
                # operator-prefix lookups still match.
                mapping[name.lower()] = friendly
                mapping[last_seg.lower()] = friendly
            else:
                # Legacy addon
                prefix = name.split(".")[0].lower()
                friendly = (info.get("name") if info else None) or prefix
                mapping[prefix] = friendly
    except Exception:
        pass
    return mapping


# --- single-pass operator index -------------------------------------------
# bpy's `dir(bpy.ops.<module>)` re-walks and re-splits the FULL global operator
# name list on EVERY call (see bpy/ops.py::_bpy_ops_submodule__dir__), so the
# usual `for m in dir(bpy.ops): for o in dir(getattr(bpy.ops, m))` pattern is
# O(modules x operators) — ~205k string splits per scan on a bare install, and
# it grows quadratically with installed add-ons. One pass over the same source
# list gives byte-identical results.
def _iter_bpy_ops():
    """Yield (module_name, op_name) for every registered operator."""
    try:
        from bpy.ops import _op_dir as _od
        names = _od()
    except Exception:
        names = None
    if names is not None:
        for _id in names:
            _p = _id.split("_OT_", 1)
            if len(_p) != 2:
                continue
            yield _p[0].lower(), _p[1]
        return
    # Fallback: original nested walk.
    for _m in dir(bpy.ops):
        if _m.startswith("_"):
            continue
        try:
            _mod = getattr(bpy.ops, _m)
            _ops = dir(_mod)
        except Exception:
            continue
        for _o in _ops:
            yield _m, _o


def _bpy_ops_map():
    """{module_name: [op_name, ...]} for every registered operator."""
    out = {}
    for _m, _o in _iter_bpy_ops():
        out.setdefault(_m, []).append(_o)
    return out


def _discover_addon_operators(static_ids: set) -> dict:
    """
    Walk bpy.ops and return operators that are NOT in the static DB.
    Groups by addon name using bl_info where available, otherwise by prefix.
    Skips core Blender prefixes that are fully covered by the static DB.
    """
    addon_bl_info = _get_addon_bl_info()
    portable_map = _scan_portable_startup()  # { prefix: addon_name }
    portable_modules = set(portable_map.keys())
    discovered = {}

    # First inject manually mapped addon ops (registered under built-in prefixes).
    # IMPORTANT: only inject ops that ACTUALLY EXIST in this Blender session.
    # bpy.ops is lazy — getattr() always succeeds even for non-existent
    # operators — so existence must be verified via get_rna_type(), which
    # raises for an unregistered operator. Without this guard, an op from an
    # uninstalled addon (e.g. EzPivotPoint's view3d.ez_pivot_toggle) would be
    # re-injected on every scan with a fallback label and could never be
    # cleared by the Re-scan button.
    for op_id, addon_name in MANUAL_ADDON_OPS.items():
        if op_id in static_ids:
            continue
        try:
            module_name, op_name = op_id.split(".", 1)
            module = getattr(bpy.ops, module_name)
            op = getattr(module, op_name)
            rna = op.get_rna_type()  # raises if operator is not registered
        except Exception:
            # Operator not present in this session — addon not installed/enabled.
            # Skip entirely rather than injecting a stale entry.
            continue
        if rna is None:
            continue
        label = (rna.name or "").strip() or op_name.replace("_", " ").title()
        discovered[op_id] = {
            "label": label,
            "addon_prefix": op_id.split(".")[0],
            "addon_name": addon_name,
            "routed_category": None,
            "source": "manual",
        }

    try:
        op_map = _bpy_ops_map()
    except Exception:
        return discovered

    for module_name, op_names in op_map.items():
        if module_name.startswith("_"):
            continue

        try:
            module = getattr(bpy.ops, module_name)
        except Exception:
            continue

        prefix_lower = module_name.lower()

        # Strictly exclude ALL known built-in prefixes
        # UNLESS this prefix comes from a portable/startup script (user-dropped)
        if prefix_lower in BUILTIN_PREFIXES and prefix_lower not in portable_modules:
            continue

        for op_name in op_names:
            if op_name.startswith("_"):
                continue
            op_id = f"{module_name}.{op_name}"
            # Hide Keymapper's own internal UI operators. Only bundled
            # user-facing operators (keymapper.op_*) are exposed; the rest of
            # the keymapper.* namespace is Keymapper's machinery and must not
            # appear in Browse Operators. (Bundled ops are injected above via
            # MANUAL_ADDON_OPS, so they're already in `discovered`.)
            if module_name == "keymapper" and not op_name.startswith("op_"):
                continue
            # Don't overwrite operators already injected from MANUAL_ADDON_OPS —
            # those carry curated addon names (e.g. "Keymapper") that the
            # prettified-prefix fallback below would otherwise clobber.
            if op_id in discovered:
                continue
            # Skip if already in static DB
            if op_id in static_ids:
                continue

            try:
                op = getattr(module, op_name)
                rna = op.get_rna_type()
                label = (rna.name or "").strip() if rna else ""
            except Exception:
                label = ""

            # Skip operators with no meaningful label
            if not label:
                label = op_name.replace("_", " ").title().strip()
            if not label:
                continue
            # Skip generic UI class names that are not real operators
            if label.lower() in {
                "layout",
                "panel",
                "menu",
                "header",
                "region",
                "space",
            }:
                continue

            # Get addon name — bl_info first, then portable map, then clean prefix
            # Handle Blender Extensions format: bl_ext.user_default.my_addon
            clean_prefix = prefix_lower
            if prefix_lower.startswith("bl_ext."):
                # Strip "bl_ext.user_default." or similar — use just the addon id part
                parts = prefix_lower.split(".")
                clean_prefix = parts[-1] if len(parts) >= 3 else prefix_lower

            addon_name = (
                addon_bl_info.get(prefix_lower)
                or addon_bl_info.get(clean_prefix)
                or portable_map.get(module_name.lower())
                or portable_map.get(prefix_lower)
                or portable_map.get(clean_prefix)
            )

            if not addon_name:
                # Try resolving by the operator class's __module__. For ops
                # from a Blender Extension the operator's __module__ looks
                # like "bl_ext.blender_org.icon_viewer"; we then look up
                # that exact module path in addon_bl_info (which my fix in
                # _get_addon_bl_info() keys by full path) to get the real name.
                try:
                    parts = op_id.split(".")
                    class_name = f"{parts[0].upper()}_OT_{parts[1]}"
                    cls = getattr(bpy.types, class_name, None)
                    if cls is not None:
                        op_mod = getattr(cls, "__module__", "") or ""
                        op_mod_lower = op_mod.lower()
                        addon_name = addon_bl_info.get(
                            op_mod_lower
                        ) or addon_bl_info.get(op_mod_lower.split(".")[-1])
                except Exception:
                    pass

            if not addon_name:
                # Try getting name from bl_info directly via the clean module id.
                # Cached snapshot — this ran once per operator and each call
                # re-walked the add-on directories from disk.
                addon_name = _addon_name_by_suffix(clean_prefix)

            if not addon_name:
                # Final fallback — prettify the clean prefix
                addon_name = clean_prefix.replace("_", " ").title()

            # BFA operators always group under "Bforartists"
            # Use ID-derived label since RNA names are too generic (e.g. "Animation")
            if prefix_lower in ("bfa", "bforartists"):
                addon_name = "Bforartists"
                label = op_name.replace("_", " ").title()

            # Option C: route to existing category with sub-label
            routed = ADDON_CATEGORY_ROUTES.get(prefix_lower)
            display_group = f"{routed} ({addon_name})" if routed else addon_name

            discovered[op_id] = {
                "label": label,
                "addon_prefix": module_name,
                "addon_name": display_group,
                "routed_category": routed,
                "source": "addon",
            }

    return discovered


def build_cache(force: bool = False):
    global _cache_static, _cache_addon, _cache_built
    if _cache_built and not force:
        return

    # Fresh add-on snapshot for this pass — the set can change between passes
    # (user enables an add-on), but never during one.
    _invalidate_addon_modules()

    static_ids = _get_static_op_ids()

    # Static cache
    new_static: dict = {}
    for cat in CATEGORIES:
        for sub in cat["subcategories"]:
            for op_id in sub["operators"]:
                friendly = get_friendly_name(op_id)
                new_static[op_id] = {
                    "label": friendly if friendly else op_id,
                    "category": cat["label"],
                    "source": "static",
                }

    # Addon cache — must run deep scan FIRST so that addon operators
    # registered under built-in prefixes (e.g. "view3d.smart_pan" from
    # K-Tools) are discovered before _discover_addon_operators filters
    # them out via the BUILTIN_PREFIXES skip-list.
    deep_scan(force=force)
    new_addon = _discover_addon_operators(static_ids)

    # BForArtists-only operators that hide behind standard prefixes: force them
    # into Addon Operators > Bforartists. They simply don't resolve when running
    # standard Blender, so this adds nothing there.
    for _bfa_id in BFA_ONLY_OPERATORS:
        if _bfa_id in new_addon:
            continue
        try:
            _m, _f = _bfa_id.split(".", 1)
            _rna = getattr(getattr(bpy.ops, _m), _f).get_rna_type()
        except Exception:
            continue  # not this build (standard Blender) — skip
        _friendly = get_friendly_name(_bfa_id)
        new_addon[_bfa_id] = {
            "label": _friendly or _rna.name or _bfa_id,
            "addon_prefix": _bfa_id.split(".", 1)[0],
            "addon_name": "Bforartists",
            "routed_category": None,  # stays in Addon Operators
        }

    # Merge deep-scan results into the addon cache.  Deep scan finds
    # operators from addons that register under built-in module prefixes
    # (e.g. "view3d.*", "object.*") which _discover_addon_operators
    # skips.  Without this merge they would appear in "3D View" → "Other"
    # instead of "Addon Operators" → "K-Tools".
    for op_id, info in _deep_scan_cache.items():
        if op_id not in new_addon:
            new_addon[op_id] = {
                "label": info["label"],
                "addon_prefix": info["prefix"],
                "addon_name": info["addon_name"],
                "routed_category": None,  # stays in Addon Operators
                "source": "deep_scan",
            }

    _cache_static = new_static
    _cache_addon = new_addon
    _cache_built = True

    print(
        f"[Keymapper] Cache: {len(new_static)} static, {len(new_addon)} addon operators "
        f"across {len({v['addon_prefix'] for v in new_addon.values()})} addon prefixes."
    )


def get_addon_operators_by_addon() -> dict:
    """
    Return non-routed addon operators: { addon_name: [(op_id, label), ...] }
    Excludes operators routed to existing static categories.
    """
    build_cache()
    groups: dict[str, list] = {}
    for op_id, info in _cache_addon.items():
        if info.get("routed_category"):
            continue
        name = info["addon_name"]
        groups.setdefault(name, []).append((op_id, info["label"]))
    for name in groups:
        groups[name].sort(key=lambda x: x[1].lower())
    return dict(sorted(groups.items(), key=lambda x: x[0].lower()))


def get_operator_category(op_id: str) -> str:
    build_cache()
    if op_id in _cache_static:
        return _cache_static[op_id]["category"]
    if op_id in _cache_addon:
        return _cache_addon[op_id]["addon_name"]
    return "Other"

# ---------------------------------------------------------------------------
# Deep Scan — finds operators from addons that register under existing prefixes
# ---------------------------------------------------------------------------

_deep_scan_cache: dict = {}  # { op_id: {label, source_prefix, addon_name} }
_deep_scan_built = False
_addon_modules_cache = None   # addon_utils.modules() snapshot, per discovery pass


def _get_enabled_addon_names() -> dict:
    """
    Returns {module_name: friendly_name} for all currently enabled addons.
    Only includes addons the user has explicitly enabled.

    For Blender Extensions (modules under "bl_ext.<repo>.<id>"):
      - The full module path is keyed (e.g. "bl_ext.blender_org.icon_viewer").
      - We do NOT add a parent fallback for "bl_ext" — that key would
        collide across all extensions and overwrite the real names.
      - bl_info is read via addon_utils.module_bl_info() when sys.modules
        doesn't expose bl_info directly (extensions store their metadata
        in blender_manifest.toml, surfaced through addon_utils).
      - As a last resort the LAST module segment (the addon id) is
        prettified — e.g. "icon_viewer" → "Icon Viewer". This avoids
        the "Bl Ext.Blender Org.Icon Viewer" bug from prettifying the
        full module path.
    """
    import sys

    result = {}
    try:
        import addon_utils
    except Exception:
        addon_utils = None
    try:
        for addon in bpy.context.preferences.addons:
            mod_name = addon.module
            name = None
            # Try sys.modules bl_info first (legacy addons)
            mod = sys.modules.get(mod_name) or sys.modules.get(mod_name.split(".")[0])
            if mod:
                bl_info = getattr(mod, "bl_info", None)
                if bl_info:
                    name = bl_info.get("name")
            # Try addon_utils path (works for extensions too)
            if not name and addon_utils is not None:
                try:
                    for amod in _addon_modules_snapshot():
                        if getattr(amod, "__name__", "") == mod_name:
                            info = addon_utils.module_bl_info(amod)
                            if info:
                                name = info.get("name")
                            break
                except Exception:
                    pass
            # Final fallback: prettify just the last segment for extensions,
            # or the whole module name for legacy addons.
            if not name:
                if mod_name.startswith("bl_ext."):
                    last_seg = mod_name.rsplit(".", 1)[-1]
                    name = last_seg.replace("_", " ").title()
                else:
                    name = mod_name.replace("_", " ").title()
            result[mod_name] = name
            # Also map the parent for legacy addons (e.g. node_wrangler.utils
            # -> node_wrangler).
            # For Blender Extensions: map the full extension path minus the
            # last segment (e.g. "bl_ext.user_default.k_tools" for a module
            # "bl_ext.user_default.k_tools.smart_tools").  This is needed so
            # that operator classes registered from a submodule still resolve
            # to their parent extension's display name.  We do NOT map just
            # "bl_ext" because that would collide across every extension
            # installed from the same repo — but we DO map the full
            # bl_ext.<repo>.<addon_id> prefix because each extension keys
            # itself by that exact path.
            if mod_name.startswith("bl_ext."):
                # Strip the last segment to get the extension id path
                # e.g. "bl_ext.user_default.k_tools.smart_tools"
                #      → "bl_ext.user_default.k_tools"
                parts = mod_name.rsplit(".", 1)
                if len(parts) >= 2:
                    ext_parent = parts[0]
                    if ext_parent not in result:
                        result[ext_parent] = name
            else:
                parent = mod_name.split(".")[0]
                if parent not in result:
                    result[parent] = name
    except Exception as e:
        print(f"[Keymapper] addon name lookup error: {e}")
    return result


def _get_op_addon_name(op_id: str, rna, enabled_addons: dict) -> str | None:
    """
    Find which enabled addon registered this operator via __module__.
    Returns (addon_name) if found in enabled addons, or None if it is a Blender built-in.

    For Blender Extensions, the operator's ``__module__`` may be a submodule
    of the extension (e.g. ``bl_ext.user_default.k_tools.smart_tools``).
    We walk up the module path checking each parent prefix until we find a
    match in ``enabled_addons``.
    """
    try:
        parts = op_id.split(".")
        class_name = f"{parts[0].upper()}_OT_{parts[1]}"
        cls = getattr(bpy.types, class_name, None)
        if cls is None:
            return None
        mod_name = getattr(cls, "__module__", None)
        if not mod_name:
            return None
        # Check if this module belongs to an enabled addon
        if mod_name in enabled_addons:
            return enabled_addons[mod_name]
        # Walk up the module path checking parent prefixes.
        # For extensions: "bl_ext.user_default.k_tools.smart_tools" →
        #   check "bl_ext.user_default.k_tools", then "bl_ext.user_default",
        #   then "bl_ext" (which we intentionally skip).
        parts_mod = mod_name.split(".")
        for i in range(len(parts_mod) - 1, 0, -1):
            parent = ".".join(parts_mod[:i])
            if parent in enabled_addons:
                return enabled_addons[parent]
        # Not from any enabled addon — skip
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# deep_scan() — finds operators from addons that register under existing
# built-in module prefixes (e.g. "view3d.*", "object.*").
# ---------------------------------------------------------------------------

_in_build = False  # recursion guard for build_cache() ↔ deep_scan()


def deep_scan(force: bool = False) -> int:
    """
    Scan ALL bpy.ops operators and find ones not in static DB or normal addon cache.
    Uses ``__module__`` on operator classes to group by addon name.
    Returns count of newly found operators.
    """
    global _deep_scan_cache, _deep_scan_built, _in_build
    # Standalone deep_scan() (load_post, Re-scan) runs outside build_cache, so
    # it needs its own fresh snapshot.
    if not _in_build:
        _invalidate_addon_modules()
    _in_build = True
    try:
        result = _deep_scan_impl(force)
    finally:
        _in_build = False
    return result


def _deep_scan_impl(force: bool = False) -> int:
    """Internal implementation of deep_scan.  Must be called with _in_build=True."""
    global _deep_scan_cache, _deep_scan_built

    # When called standalone (not via build_cache) before any cache was built,
    # the caches are empty so there's nothing to compare against.
    if not _in_build and not _cache_built:
        _deep_scan_built = True
        return 0

    all_known = set(_cache_static.keys()) | set(_cache_addon.keys())
    enabled_addons = _get_enabled_addon_names()
    found = {}

    try:
        for module_name, op_names in _bpy_ops_map().items():
            if module_name.startswith("_"):
                continue
            try:
                module = getattr(bpy.ops, module_name)
            except Exception:
                continue
            for op_name in op_names:
                if op_name.startswith("_"):
                    continue
                op_id = f"{module_name}.{op_name}"
                # Hide Keymapper's internal UI operators from discovery. Only
                # bundled user-facing ops (keymapper.op_*) are allowed through;
                # those are already in _cache_addon via MANUAL_ADDON_OPS, so
                # they'd be skipped below anyway — this guard keeps Keymapper's
                # own machinery (form_confirm, add_entry, …) out of results.
                if module_name == "keymapper" and not op_name.startswith("op_"):
                    continue

                if op_id in all_known:
                    continue
                try:
                    op = getattr(module, op_name)
                    rna = op.get_rna_type()
                    label = (rna.name or "").strip() if rna else ""
                except Exception:
                    continue
                if not label:
                    label = op_name.replace("_", " ").title().strip()
                if not label:
                    continue
                if label.lower() in {
                    "layout",
                    "panel",
                    "menu",
                    "header",
                    "region",
                    "space",
                }:
                    continue
                # Deep scan does NOT filter by BUILTIN_PREFIXES —
                # instead rely purely on __module__ -> enabled addon check.
                # This catches addons like smartdelete_bfa (mesh.*) and
                # io_scene_fbx (export_scene.*) that use built-in prefixes.
                addon_name = _get_op_addon_name(op_id, rna, enabled_addons)
                if addon_name is None:
                    continue
                # Skip if already found via normal addon discovery
                if op_id in _cache_addon:
                    continue
                found[op_id] = {
                    "label": label,
                    "prefix": module_name,
                    "addon_name": addon_name,
                }
    except Exception as e:
        print(f"[Keymapper] deep scan error: {e}")

    _deep_scan_cache = found
    _deep_scan_built = True
    # Log breakdown by addon
    by_addon = {}
    for info in found.values():
        by_addon[info["addon_name"]] = by_addon.get(info["addon_name"], 0) + 1
    print(
        f"[Keymapper] Deep scan: {len(found)} unlisted operators across {len(by_addon)} addons:"
    )
    for name, count in sorted(by_addon.items()):
        print(f"  {name}: {count}")
    return len(found)


def get_deep_scan_operators() -> dict:
    """Return deep scan results grouped by addon name: {addon_name: [(op_id, label), ...]}"""
    groups: dict[str, list] = {}
    for op_id, info in _deep_scan_cache.items():
        name = info["addon_name"]
        groups.setdefault(name, []).append((op_id, info["label"]))
    for name in groups:
        groups[name].sort(key=lambda x: x[1].lower())
    return dict(sorted(groups.items()))


def has_deep_scan_results() -> bool:
    return _deep_scan_built and bool(_deep_scan_cache)


def refresh():
    build_cache(force=True)


def invalidate():
    global _cache_built
    _cache_built = False
