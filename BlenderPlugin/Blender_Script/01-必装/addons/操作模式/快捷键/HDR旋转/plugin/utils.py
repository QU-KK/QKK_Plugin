"""Helper functions of the add-on."""

import contextlib

import bpy

_keymaps = []


def add_shortcut(
    keymap, space_type, idname, key, value="PRESS", properties=None, **modifiers
):
    """Add a keymap item to Blender's add-on keyconfig (removed when the
    add-on is disabled)."""
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:  # background mode
        return
    keymap = keyconfig.keymaps.new(name=keymap, space_type=space_type)
    item = keymap.keymap_items.new(idname, key, value, **modifiers)
    for name, prop_value in (properties or {}).items():
        if prop_value is not None:  # keymap items can't hold None
            setattr(item.properties, name, prop_value)
    _keymaps.append((keymap, item))


def unregister():
    for keymap, item in _keymaps:
        # gone if Blender removed the keymap already
        with contextlib.suppress(ReferenceError, RuntimeError):
            keymap.keymap_items.remove(item)
    _keymaps.clear()
