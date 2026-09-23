"""Custom icon management for Keymapper.

Loads the bundled Keymapper logo into a bpy.utils.previews collection so it can
be used anywhere an ``icon_value=`` is accepted (header labels, buttons, and
— on Blender 5.2+ — the compact sidebar tab via ``bl_icon``).

Works on both Blender 5.1 and 5.2; the previews API is old and stable. The
5.2-only ``bl_icon`` usage is handled defensively at the panel registration
site, not here.
"""

import os

import bpy
import bpy.utils.previews

# Single collection holding all Keymapper custom icons.
_preview_collection = None

# Logical name -> filename inside the icons/ folder.
_ICON_FILES = {
    "logo": "keymapper_logo.png",
}


def register():
    """Create the preview collection and load bundled icons."""
    global _preview_collection
    if _preview_collection is not None:
        return
    try:
        pcoll = bpy.utils.previews.new()
        icons_dir = os.path.join(os.path.dirname(__file__), "icons")
        for name, filename in _ICON_FILES.items():
            path = os.path.join(icons_dir, filename)
            if os.path.isfile(path):
                pcoll.load(name, path, "IMAGE")
        _preview_collection = pcoll
    except Exception as e:
        print(f"[Keymapper] Custom icon load failed: {e}")
        _preview_collection = None


def unregister():
    """Free the preview collection."""
    global _preview_collection
    if _preview_collection is not None:
        try:
            bpy.utils.previews.remove(_preview_collection)
        except Exception:
            pass
        _preview_collection = None


def get_icon_id(name: str = "logo") -> int:
    """Return the icon_id for a loaded custom icon, or 0 if unavailable.

    0 is a safe sentinel: passing ``icon_value=0`` to a UI call draws nothing
    (same as omitting it), so callers can use this unconditionally.
    """
    pcoll = _preview_collection
    if not pcoll:
        return 0
    try:
        return pcoll[name].icon_id
    except Exception:
        return 0
