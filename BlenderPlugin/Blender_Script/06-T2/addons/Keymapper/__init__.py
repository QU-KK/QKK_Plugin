bl_info = {
    "name": "Keymapper",
    "author": "JFW",
    "version": (1, 3, 3),
    "blender": (5, 1, 0),
    "location": "3D Viewport > Sidebar (N) > Keymapper | Edit > Preferences > Addons > Keymapper",
    "description": "A modern, non-destructive shortcut manager for Blender",
    "category": "Interface",
}

import bpy
from bpy.app.handlers import persistent


def _detect_host():
    try:
        if hasattr(bpy.app, "bforartists"):
            return "bforartists"
        if "bforartists" in bpy.app.version_string.lower():
            return "bforartists"
        if "bforartists" in (getattr(bpy.app, "binary_path", "") or "").lower():
            return "bforartists"
        if "bfa" in bpy.app.build_hash.decode("utf-8", errors="ignore").lower():
            return "bforartists"
    except Exception:
        pass
    return "blender"


HOST_APP = _detect_host()


def _import_modules():
    from . import properties
    from . import preferences
    from . import persistence
    from . import bundled_ops
    from . import operators
    from . import panel
    from . import buttons
    return properties, preferences, persistence, bundled_ops, operators, panel, buttons


@persistent
def _keymapper_load_post(dummy=None):
    """Reload entries from prefs whenever a file is opened."""
    try:
        from . import persistence, keyconfig_store as _ks
        persistence.load()
        _ks.invalidate()  # reset cache so it reloads from prefs on next access
        from .operator_discovery import build_cache, deep_scan
        build_cache(force=True)
        deep_scan()
    except Exception as e:
        print(f"[Keymapper] load_post error: {e}")


@persistent
def _keymapper_save_pre(dummy=None):
    """Ensure entries are written to prefs before any save operation."""
    try:
        from . import persistence
        persistence._write_to_prefs()
    except Exception as e:
        print(f"[Keymapper] save_pre error: {e}")


_modules = None


def _deferred_cache_build():
    """Called once via bpy.app.timers, ~1s after register(). Runs the
    operator discovery cache, deep scan, internal conflict scan, and a
    skip-aware external conflict refresh.

    The external scan is skip-aware (v0.9.92+): entries whose stored
    signature matches their current data AND the current keyconfig store
    signature are not re-scanned. On a steady-state startup (nothing
    changed since last run), this typically scans 0 of N entries.
    """
    import time as _t
    _t_start = _t.perf_counter()

    from . import persistence
    from .operator_discovery import build_cache, deep_scan
    from . import keymap_manager

    persistence.load()

    # Internal scan + skip-aware external scan (fast on cache hit) FIRST,
    # then reactivate — so the default-KMI disables land as early as
    # possible. The heavy operator-discovery scans run after.
    try:
        from .conflict_detector import (
            update_entry_conflicts,
            update_all_external_conflicts,
        )
        entries = persistence.get_entries()
        update_entry_conflicts(entries)
        scanned = update_all_external_conflicts(entries, force=False)
        if scanned:
            persistence._write_to_prefs()
    except Exception as e:
        print(f"[Keymapper] Startup conflict scan error: {e}")
        scanned = -1

    # Load the record of KMIs we created last session BEFORE activating, so the
    # adoption logic doesn't mistake our own leftovers (Blender persists the
    # user keyconfig) for pre-existing defaults.
    keymap_manager.load_owned_kmi_registry()

    # Reactivate entries — activate_entry reads the cached
    # keybind_conflicts_external to know which Blender defaults to disable.
    keymap_manager.reactivate_all(fast=True)

    # Refresh the record with what we just created.
    keymap_manager.save_owned_kmi_registry()

    build_cache()
    deep_scan()

    # First-run environment baseline: if the saved snapshot is empty (fresh
    # install OR upgrade from pre-0.9.92), record the current environment
    # as the baseline so future change detection works. We do NOT clear
    # _cached_changes here — get_cached_changes() will compute "first_run"
    # = True and silently suppress the banner on this first session.
    try:
        from . import environment
        if not environment.get_saved_snapshot():
            environment.save_snapshot()
    except Exception as e:
        print(f"[Keymapper] Environment baseline error: {e}")

    # Force panel redraw so conflict icons appear immediately
    try:
        import bpy as _bpy
        for window in _bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:
        pass

    dt_ms = (_t.perf_counter() - _t_start) * 1000.0
    cache_note = "all cached" if scanned == 0 else f"{scanned} re-scanned"
    print(f"[Keymapper] Startup ready in {dt_ms:.0f} ms ({cache_note}).")
    return None  # run once


def register():
    global _modules, HOST_APP
    HOST_APP = _detect_host()
    print(f"[Keymapper] Detected host: {HOST_APP}")

    _modules = _import_modules()
    from . import icons as _icons
    _icons.register()
    for mod in _modules:
        mod.register()

    # Handlers
    if _keymapper_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_keymapper_load_post)

    if _keymapper_save_pre not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(_keymapper_save_pre)

    # Build operator cache after all addons have loaded
    bpy.app.timers.register(_deferred_cache_build, first_interval=0.1)
    print("[Keymapper] Registered successfully.")


def unregister():
    global _modules

    if _keymapper_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_keymapper_load_post)

    if _keymapper_save_pre in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(_keymapper_save_pre)

    if _modules:
        for mod in reversed(_modules):
            try:
                mod.unregister()
            except Exception as e:
                print(f"[Keymapper] Error unregistering {mod.__name__}: {e}")

    try:
        from . import icons as _icons
        _icons.unregister()
    except Exception:
        pass

    print("[Keymapper] Unregistered.")
