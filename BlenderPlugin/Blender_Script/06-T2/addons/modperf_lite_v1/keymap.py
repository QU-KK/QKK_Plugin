# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""The open / close shortcut: keymap registration and helpers."""

import bpy

from .constants import TOGGLE_OPERATOR


addon_keymaps = []


def _toggle_kmi():
    """The (user-editable) keymap item that opens / closes the panel."""
    wm = bpy.context.window_manager
    for kc in (wm.keyconfigs.user, wm.keyconfigs.addon):
        if kc is None:
            continue
        km = kc.keymaps.get("3D View")
        if km is None:
            continue
        for kmi in km.keymap_items:
            if kmi.idname == TOGGLE_OPERATOR:
                return km, kmi
    return None, None


def _is_toggle_event(event):
    km, kmi = _toggle_kmi()
    if kmi is None:
        return (event.type == 'Y' and not (event.ctrl or event.alt or event.shift
                                            or event.oskey))
    if not kmi.active or event.type != kmi.type:
        return False

    def mod_ok(want, have):
        return True if want == -1 else bool(want) == bool(have)
    return (mod_ok(kmi.ctrl, event.ctrl) and mod_ok(kmi.shift, event.shift)
            and mod_ok(kmi.alt, event.alt) and mod_ok(kmi.oskey, event.oskey))


def _toggle_key_label():
    km, kmi = _toggle_kmi()
    if kmi is None:
        return "Y"
    try:
        return kmi.to_string() or kmi.type.title()
    except Exception:
        return kmi.type.title()


def _register_keymaps():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:  # background mode
        return
    km = kc.keymaps.new(name="3D View", space_type='VIEW_3D')
    kmi = km.keymap_items.new(TOGGLE_OPERATOR, type='Y', value='PRESS')
    kmi.properties.action = 'TOGGLE'
    addon_keymaps.append((km, kmi))


def _unregister_keymaps():
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    addon_keymaps.clear()


class PREFERENCES_OT_modperf_lite_key_reset(bpy.types.Operator):
    """Reset the shortcut to Y"""
    bl_idname = "preferences.modperf_lite_key_reset"
    bl_label = "Reset Shortcut"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        km, kmi = _toggle_kmi()
        if kmi is not None:
            kmi.type = 'Y'
            kmi.value = 'PRESS'
            kmi.ctrl = kmi.shift = kmi.alt = kmi.oskey = False
            kmi.key_modifier = 'NONE'
            context.preferences.is_dirty = True
        return {'FINISHED'}
