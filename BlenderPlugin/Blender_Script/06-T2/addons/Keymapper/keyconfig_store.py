"""
keyconfig_store.py
Manages a local snapshot of Blender's default + active keymaps.
Used by conflict_detector.py for fast lookups instead of live keymap iteration.

Data structure stored in preferences (keymapper_keyconfig_store):
{
  "blender_version": "5.1.1",
  "keymap_count": 123,
  "keymaps": {
    "3D View": [
      {
        "op_id":  "view3d.move",
        "key":    "MIDDLEMOUSE",
        "value":  "PRESS",
        "shift":  false,
        "ctrl":   false,
        "alt":    false,
        "oskey":  false,
        "any":    false,
        "active": true
      },
      ...
    ],
    ...
  }
}
"""

import json

# ---------------------------------------------------------------------------
# In-memory cache — populated from prefs on load
# ---------------------------------------------------------------------------

_store: dict | None = None   # { keymap_name: [ kmi_dict, ... ] }
_op_index: dict | None = None  # { op_id: {keymap_name, ...} } — built lazily
_scanned: bool = False
_signature: str | None = None  # cached hash of the store JSON, recomputed on invalidate


# ---------------------------------------------------------------------------
# Prefs access
# ---------------------------------------------------------------------------

def _get_prefs():
    try:
        import bpy
        addons = bpy.context.preferences.addons
        # __package__ is this addon's package name, whatever the install
        # route: "keymapper" (legacy addon) or "bl_ext.<repo>.keymapper"
        # (extension). The repo segment is NOT always "user_default" —
        # installing from an online repository gives a different one, which
        # is why the hardcoded list below failed there (store never saved,
        # so the "Scan Keyconfig" prompt never cleared).
        for key in (__package__, "bl_ext.user_default.keymapper", "keymapper"):
            if key and key in addons:
                return addons[key].preferences
        # Last resort: any enabled addon whose module tail is ours.
        for key in addons.keys():
            if key.rsplit(".", 1)[-1] == "keymapper":
                return addons[key].preferences
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_STORE_SCHEMA = 3  # 3: KMI entries carry their source layer ("source")


def is_scanned() -> bool:
    """Return True if a keyconfig snapshot with the current schema exists."""
    global _scanned
    if _scanned:
        return True
    prefs = _get_prefs()
    if prefs is None:
        return False
    raw = getattr(prefs, "keymapper_keyconfig_store", "")
    if not (raw and raw.strip()):
        return False
    try:
        if json.loads(raw).get("schema", 1) != _STORE_SCHEMA:
            return False  # stale schema -> treat as unscanned, forces rescan
    except Exception:
        return False
    _scanned = True
    return _scanned


def get_store() -> dict:
    """Return the in-memory keymap store, loading from prefs if needed."""
    global _store, _op_index
    if _store is not None:
        return _store
    prefs = _get_prefs()
    if prefs is None:
        return {}
    raw = getattr(prefs, "keymapper_keyconfig_store", "")
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        _store = data.get("keymaps", {})
        _op_index = None
        return _store
    except Exception as e:
        print(f"[Keymapper] keyconfig_store load error: {e}")
        return {}


def get_stored_blender_version() -> str:
    """Return the Blender version string from when the scan was performed."""
    prefs = _get_prefs()
    if prefs is None:
        return ""
    raw = getattr(prefs, "keymapper_keyconfig_store", "")
    if not raw:
        return ""
    try:
        data = json.loads(raw)
        return data.get("blender_version", "")
    except Exception:
        return ""


def current_blender_version() -> str:
    try:
        import bpy
        return ".".join(str(v) for v in bpy.app.version)
    except Exception:
        return ""


def version_changed() -> bool:
    stored = get_stored_blender_version()
    current = current_blender_version()
    return bool(stored and current and stored != current)


def invalidate():
    """Clear the in-memory cache so next get_store() reloads from prefs."""
    global _store, _scanned, _signature
    _store     = None
    _scanned   = False
    _signature = None


def get_signature() -> str:
    """Return a short hex hash of the current keyconfig store contents.

    Used by conflict_detector to decide whether cached external conflict
    results on an entry are still valid. If the store changes (Blender
    version upgrade, new addon enabled, user-edited default keymap, full
    Re-scan pressed), the signature changes and entries get re-scanned.

    Result is cached in `_signature` until invalidate() is called.
    """
    global _signature
    if _signature is not None:
        return _signature
    prefs = _get_prefs()
    if prefs is None:
        _signature = ""
        return _signature
    raw = getattr(prefs, "keymapper_keyconfig_store", "")
    if not raw or not raw.strip():
        _signature = ""
        return _signature
    import hashlib
    _signature = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return _signature


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

MODAL_CONTEXTS = {
    "View3D Fly Modal", "View3D Walk Modal", "View3D Rotate Modal",
    "View3D Move Modal", "View3D Zoom Modal", "View3D Dolly Modal",
    "View3D Gesture Circle", "View3D Placement Modal",
    "Transform Modal Map", "Eyedropper Modal Map",
    "Graph Editor - FPS Keymap",
}


def scan_keymaps(incremental: bool = False) -> dict:
    """
    Scan Blender's keyconfigs and return a keymap snapshot dict.
    If incremental=True, only add keymaps not already in the store.
    """
    _op_reg_memo = {}
    import bpy
    wm  = bpy.context.window_manager

    try:
        from .preferences import get_prefs
        prefs = get_prefs()
        scan_default = bool(getattr(prefs, "scan_default_keyconfig", True))
        scan_addon   = bool(getattr(prefs, "scan_addon_keyconfig", True))
        scan_user    = bool(getattr(prefs, "scan_user_keyconfig", True))
    except Exception:
        scan_default, scan_addon, scan_user = True, True, True

    kcs = []
    kc_default = wm.keyconfigs.default
    kc_active  = wm.keyconfigs.active
    if scan_default:
        if kc_active and kc_active != kc_default:
            # A CUSTOM keyconfig is active (e.g. BForArtists, Industry
            # Compatible): only its bindings dispatch. The default layer's
            # bindings are dormant — reporting them creates phantom conflicts
            # (and phantom materialized copies, e.g. the plain-SPACE Play/Pause
            # duplicate on BFA). Scan the active config INSTEAD of default.
            kcs.append((kc_active, "factory"))
        elif kc_default:
            kcs.append((kc_default, "factory"))
    if scan_addon and wm.keyconfigs.addon:
        kcs.append((wm.keyconfigs.addon, "addon"))
    if (scan_user and wm.keyconfigs.user
            and wm.keyconfigs.user not in [k for k, _ in kcs]):
        kcs.append((wm.keyconfigs.user, "user"))

    existing = get_store() if incremental else {}
    keymaps: dict = dict(existing)
    seen_kmi: dict[str, set] = {}

    # Keymapper's own registered KMIs must never enter the store — otherwise an
    # entry's own KMI (for a normal Blender op like view2d.scroll_up) looks like
    # a default and conflict detection would disable it. Bundled keymapper.* ops
    # are skipped by idname below; normal ops are addon-owned and identified by a
    # NEGATIVE id in the user/active layers (factory items are positive).

    for kc, kc_source in kcs:
        for km in kc.keymaps:
            if km.name in MODAL_CONTEXTS:
                continue
            if km.name not in seen_kmi:
                seen_kmi[km.name] = set()
            km_list = keymaps.setdefault(km.name, [])
            for kmi in km.keymap_items:
                if not kmi.idname:
                    continue
                # Skip Keymapper's own bundled operators (keymapper.op_*) so an
                # entry using one doesn't conflict with itself. Real Blender /
                # BForArtists operators are never excluded.
                if kmi.idname.startswith("keymapper."):
                    continue
                # Skip Keymapper's own registered KMIs. In the default/active
                # (factory) layers our items carry a NEGATIVE id and nothing
                # else does, so id<0 is sufficient. In the USER layer, negative
                # ids mark ALL user diffs — including real user KMIs we WANT to
                # detect — so there we skip only items matching our own
                # registration records.
                is_user_layer = (kc_source == "user")
                if not is_user_layer:
                    if kmi.id < 0:
                        continue
                else:
                    try:
                        from .keymap_manager import _entry_kmi_keymaps
                        sig = (kmi.type, kmi.value, bool(kmi.shift),
                               bool(kmi.ctrl), bool(kmi.alt), bool(kmi.oskey))
                        rec = (km.name, kmi.idname, sig)
                        if any(rec in recs for recs in _entry_kmi_keymaps.values()):
                            continue
                    except Exception:
                        pass
                uid = (kmi.idname, kmi.type, kmi.value,
                       kmi.shift, kmi.ctrl, kmi.alt, kmi.oskey, kmi.any)
                if uid in seen_kmi[km.name]:
                    continue
                seen_kmi[km.name].add(uid)
                kmi_entry = {
                    "op_id":  kmi.idname,
                    "key":    kmi.type,
                    "value":  kmi.value,
                    "shift":  kmi.shift,
                    "ctrl":   kmi.ctrl,
                    "alt":    kmi.alt,
                    "oskey":  kmi.oskey,
                    "any":    kmi.any,
                    "active": kmi.active,
                    # Which keyconfig layer this KMI came from ("factory" /
                    # "addon" / "user") — drives the Addon Conflicts dropdown.
                    "source": kc_source,
                }
                # Store all explicitly-set properties (shown on conflict rows),
                # plus the disambiguating property for generic operators.
                #
                # GUARD: a KMI whose operator class was just unregistered (its
                # addon was disabled) has a DANGLING properties RNA pointer —
                # touching .bl_rna on it segfaults Blender, and try/except can't
                # catch that. Skip props for unregistered ops (memoized per
                # scan; the KMI row itself is still recorded).
                kmi_props = {}
                _reg = _op_reg_memo.get(kmi.idname)
                if _reg is None:
                    from .conflict_detector import is_operator_registered
                    _reg = is_operator_registered(kmi.idname)
                    _op_reg_memo[kmi.idname] = _reg
                try:
                    if _reg and kmi.properties:
                        for p in kmi.properties.bl_rna.properties:
                            if p.identifier == "rna_type":
                                continue
                            if kmi.properties.is_property_set(p.identifier):
                                kmi_props[p.identifier] = str(
                                    getattr(kmi.properties, p.identifier, ""))
                except Exception:
                    pass
                from .conflict_detector import _PROP_DISAMBIGUATED_OPS
                key_prop = _PROP_DISAMBIGUATED_OPS.get(kmi.idname)
                if _reg and key_prop and key_prop not in kmi_props:
                    try:
                        kmi_props[key_prop] = str(getattr(kmi.properties, key_prop, ""))
                    except Exception:
                        pass
                if kmi_props:
                    kmi_entry["props"] = kmi_props
                km_list.append(kmi_entry)
    return keymaps


def save_store(keymaps: dict) -> None:
    """Persist the keymap snapshot to addon preferences or file fallback."""
    global _store, _scanned, _op_index
    prefs = _get_prefs()
    if prefs is None:
        print("[Keymapper] save_store: prefs not available")
        return
    data = {
        "schema":          _STORE_SCHEMA,
        "blender_version": current_blender_version(),
        "keymap_count":    sum(len(v) for v in keymaps.values()),
        "keymaps":         keymaps,
    }
    try:
        raw = json.dumps(data, ensure_ascii=False)
        prefs.keymapper_keyconfig_store = raw
        stored_len = len(getattr(prefs, "keymapper_keyconfig_store", ""))
        if stored_len < 10:
            print("[Keymapper] save_store: StringProperty too small, using file fallback")
            _save_to_file(raw)
            return
    except Exception as e:
        print(f"[Keymapper] save_store error: {e}")
        return
    try:
        import bpy
        bpy.context.preferences.is_dirty = True
    except Exception:
        pass
    _store   = keymaps
    _scanned = True
    _op_index = None
    # New store contents — force signature recompute on next get_signature()
    global _signature
    _signature = None
    print(f"[Keymapper] Keyconfig store saved: {len(keymaps)} keymaps, {data['keymap_count']} KMIs")


def _get_store_file_path() -> str:
    """Get path for file-based keyconfig store."""
    import bpy, os
    user_dir = bpy.utils.resource_path("USER")
    config_dir = os.path.join(user_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "keymapper_keyconfig.json")


def _save_to_file(raw: str) -> None:
    """Save keyconfig JSON to a file (fallback when prefs StringProperty is too small)."""
    global _store, _scanned, _op_index
    try:
        path = _get_store_file_path()
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw)
        data = json.loads(raw)
        _store   = data.get("keymaps", {})
        _scanned = True
        global _signature
        _signature = None
        print(f"[Keymapper] Keyconfig saved to file: {path}")
        print(f"[Keymapper] {len(_store)} keymaps stored")
    except Exception as e:
        print(f"[Keymapper] _save_to_file error: {e}")


def do_full_scan() -> None:
    # Flush pending keyconfig changes first. After an addon is enabled or
    # disabled, KMIs can still hold a properties pointer into the previous
    # registration of an operator with the same idname — the registration
    # check then passes while the RNA is dangling, and reading it segfaults
    # (uncatchable). keyconfigs.update() rebinds them before we read.
    try:
        import bpy as _b
        _b.context.window_manager.keyconfigs.update()
    except Exception:
        pass
    keymaps = scan_keymaps(incremental=False)
    save_store(keymaps)
    # Menu/panel class lists can change when addons are enabled/disabled, so
    # drop the cached enumerations used for friendly names.
    try:
        from .database.op_properties import invalidate_prop_values_cache
        invalidate_prop_values_cache()
    except Exception:
        pass
    # The multi-op list is derived from the FACTORY keyconfig, so it only
    # changes when the user switches keyconfig template — which is exactly when
    # a Re-scan runs.
    try:
        from .database.multi_ops import invalidate as _inv_multi
        _inv_multi()
    except Exception:
        pass
    try:
        from . import keymap_manager
        keymap_manager.refresh_adoption_display()
    except Exception:
        pass


def do_incremental_scan() -> None:
    keymaps = scan_keymaps(incremental=True)
    save_store(keymaps)


# ---------------------------------------------------------------------------
# Fast lookup helpers (used by conflict_detector)
# ---------------------------------------------------------------------------

def get_kmis_for_keymap(km_name: str) -> list:
    """Return list of KMI dicts for a given keymap name."""
    return get_store().get(km_name, [])


def get_all_keymap_names() -> list:
    """Return all scanned keymap names."""
    return list(get_store().keys())


def get_keymap_names_for_op(op_id: str) -> set:
    """Return all keymap names that contain a given operator.

    Backed by a lazily-built {op_id: {km_name}} index so repeated lookups
    during a rescan don't each walk the entire store.
    """
    global _op_index
    if _op_index is None:
        idx: dict = {}
        for km_name, kmis in get_store().items():
            for kmi in kmis:
                oid = kmi.get("op_id")
                if oid:
                    idx.setdefault(oid, set()).add(km_name)
        _op_index = idx
    return set(_op_index.get(op_id, ()))
