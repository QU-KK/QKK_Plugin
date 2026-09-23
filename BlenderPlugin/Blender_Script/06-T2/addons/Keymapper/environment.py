"""
environment.py
Tracks the relevant Blender environment between sessions:
  - Blender version string (catches version upgrades)
  - Set of enabled addon module names (catches install/enable/disable/uninstall)

Stored as JSON on prefs under `keymapper_environment_snapshot`:
    {"blender_version": "5.1.1",
     "addons":          ["node_wrangler", "io_scene_fbx", ...]}

On addon registration, we compare the current environment to the saved
snapshot. If they differ, the Re-scan default keybindings button is
highlighted (alert=True) and a banner explains what changed. The user
clicks Re-scan to update both the keyconfig store AND this snapshot,
which clears the alert state.
"""

import json
import bpy


# ---------------------------------------------------------------------------
# Prefs access (mirrors keyconfig_store._get_prefs)
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
# Current environment snapshot
# ---------------------------------------------------------------------------

def current_blender_version() -> str:
    try:
        return bpy.app.version_string
    except Exception:
        return ""


def current_addon_modules() -> list[str]:
    """Sorted list of enabled addon module names."""
    try:
        return sorted(a.module for a in bpy.context.preferences.addons)
    except Exception:
        return []


def current_keyconfig() -> str:
    """Name of the active keyconfig (e.g. 'Blender', 'Bforartists')."""
    try:
        active = bpy.context.window_manager.keyconfigs.active
        return active.name if active else ""
    except Exception:
        return ""


def current_conflict_method() -> list:
    """The conflict-detection toggles that affect which defaults get disabled.

    Changing any of these means the stored conflict data is stale and a re-scan
    is needed to recompute it.
    """
    prefs = _get_prefs()
    if prefs is None:
        return []
    sig = [
        bool(getattr(prefs, "find_shortcut_conflicts", True)),
        bool(getattr(prefs, "shortcut_conflicts_cross_props", True)),
        bool(getattr(prefs, "find_keybind_conflicts", True)),
        bool(getattr(prefs, "keybind_conflicts_cross_value", True)),
        bool(getattr(prefs, "scan_default_keyconfig", True)),
        bool(getattr(prefs, "scan_addon_keyconfig", True)),
        bool(getattr(prefs, "scan_user_keyconfig", True)),
    ]
    try:
        from .preferences import KBCV_VALUES, KBCV_DEFAULTS, kbcv_prop_name
        for w in KBCV_VALUES:
            for l in KBCV_VALUES:
                if w == l:
                    continue
                sig.append(bool(getattr(prefs, kbcv_prop_name(w, l),
                                        (w, l) in KBCV_DEFAULTS)))
    except Exception:
        pass
    return sig


def current_snapshot() -> dict:
    return {
        "blender_version": current_blender_version(),
        "addons":          current_addon_modules(),
        "keyconfig":       current_keyconfig(),
        "conflict_method": current_conflict_method(),
    }


# ---------------------------------------------------------------------------
# Saved snapshot (in prefs)
# ---------------------------------------------------------------------------

def get_saved_snapshot() -> dict:
    prefs = _get_prefs()
    if prefs is None:
        return {}
    raw = getattr(prefs, "keymapper_environment_snapshot", "") or ""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"[Keymapper] environment snapshot parse error: {e}")
    return {}


def save_snapshot(snapshot: dict | None = None) -> None:
    """Persist the snapshot. Pass None to save the current environment."""
    prefs = _get_prefs()
    if prefs is None:
        return
    if snapshot is None:
        snapshot = current_snapshot()
    try:
        prefs.keymapper_environment_snapshot = json.dumps(snapshot,
                                                          ensure_ascii=False)
    except Exception as e:
        print(f"[Keymapper] environment snapshot save error: {e}")


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def detect_changes() -> dict:
    """Compare current environment to the saved snapshot.

    Returns a dict describing what changed:
        {
          "has_changes":      bool,
          "version_changed":  bool,
          "old_version":      str,
          "new_version":      str,
          "addons_added":     [str, ...],
          "addons_removed":   [str, ...],
          "first_run":        bool,  # no saved snapshot yet
        }

    If no saved snapshot exists yet, returns first_run=True and
    has_changes=False (no spurious warnings on a fresh install).
    """
    saved   = get_saved_snapshot()
    current = current_snapshot()

    if not saved:
        return {
            "has_changes":     False,
            "version_changed": False,
            "old_version":     "",
            "new_version":     current["blender_version"],
            "addons_added":    [],
            "addons_removed":  [],
            "keyconfig_changed": False,
            "old_keyconfig":   "",
            "new_keyconfig":   current.get("keyconfig", ""),
            "conflict_method_changed": False,
            "new_conflict_method": current.get("conflict_method", []),
            "first_run":       True,
        }

    old_v = saved.get("blender_version", "")
    new_v = current.get("blender_version", "")
    old_addons = set(saved.get("addons", []) or [])
    new_addons = set(current.get("addons", []) or [])
    old_kc = saved.get("keyconfig", "")
    new_kc = current.get("keyconfig", "")
    old_cm = saved.get("conflict_method")
    new_cm = current.get("conflict_method", [])

    version_changed = bool(old_v and new_v and old_v != new_v)
    added   = sorted(new_addons - old_addons)
    removed = sorted(old_addons - new_addons)
    # Only flag a keyconfig change if we actually have a saved baseline for it
    # (older snapshots predate this field — don't warn spuriously).
    keyconfig_changed = bool("keyconfig" in saved and old_kc != new_kc)
    conflict_method_changed = bool("conflict_method" in saved and old_cm != new_cm)

    return {
        "has_changes":     version_changed or bool(added) or bool(removed) or keyconfig_changed or conflict_method_changed,
        "version_changed": version_changed,
        "old_version":     old_v,
        "new_version":     new_v,
        "addons_added":    added,
        "addons_removed":  removed,
        "keyconfig_changed": keyconfig_changed,
        "old_keyconfig":   old_kc,
        "new_keyconfig":   new_kc,
        "conflict_method_changed": conflict_method_changed,
        "new_conflict_method": new_cm,
        "first_run":       False,
    }


# ---------------------------------------------------------------------------
# Module-level cache — computed once at startup, refreshed when
# clear_cached_changes() is called (after the user re-scans).
# ---------------------------------------------------------------------------

_cached_changes: dict | None = None


def get_cached_changes() -> dict:
    """Return the changes detected at startup, computed lazily on first call.
    Avoids re-computing on every panel draw.

    Exception: the active keyconfig can change live (the user switches the
    template in our Settings dropdown or Blender's Keymap panel), so we cheaply
    re-detect when the current keyconfig no longer matches what the cache saw.
    """
    global _cached_changes
    if _cached_changes is None:
        _cached_changes = detect_changes()
        return _cached_changes
    # Live re-check (cheap attribute reads): the active keyconfig or the
    # conflict-detection toggles can change without a restart.
    cached_kc = _cached_changes.get("new_keyconfig", "")
    cached_cm = _cached_changes.get("new_conflict_method")
    if current_keyconfig() != cached_kc or current_conflict_method() != cached_cm:
        _cached_changes = detect_changes()
    return _cached_changes


def clear_cached_changes() -> None:
    """Called when the user clicks Re-scan default keybindings. We save the
    current environment as the new baseline and clear the cache so any
    future change detection starts fresh."""
    global _cached_changes
    save_snapshot()
    _cached_changes = {
        "has_changes":     False,
        "version_changed": False,
        "old_version":     current_blender_version(),
        "new_version":     current_blender_version(),
        "addons_added":    [],
        "addons_removed":  [],
        "conflict_method_changed": False,
        "new_conflict_method": current_conflict_method(),
        "new_keyconfig":   current_keyconfig(),
        "first_run":       False,
    }
