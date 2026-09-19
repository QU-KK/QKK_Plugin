"""
utils.py
Shared utility functions used across Keymapper modules.
"""

import bpy


def get_host_app() -> str:
    """Returns 'bforartists' or 'blender'."""
    try:
        from . import HOST_APP
        return HOST_APP
    except ImportError:
        pass
    try:
        if hasattr(bpy.app, "bforartists"):
            return "bforartists"
        if "bforartists" in bpy.app.version_string.lower():
            return "bforartists"
    except Exception:
        pass
    return "blender"


def redraw_all(context=None):
    """Tag all areas for redraw."""
    ctx = context or bpy.context
    try:
        for area in ctx.screen.areas:
            area.tag_redraw()
    except Exception:
        pass


def is_compatible_entry(entry: dict) -> bool:
    """
    Returns False if an entry was created in Bforartists but we're
    currently running standard Blender (or vice versa for bfa-only ops).
    """
    host = get_host_app()
    source = entry.get("source_app", "blender")
    if source == "bforartists" and host == "blender":
        return False
    return True
