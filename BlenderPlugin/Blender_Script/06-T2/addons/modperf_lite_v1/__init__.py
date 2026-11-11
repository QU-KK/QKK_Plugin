# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""
ModPerf Lite
============

The free edition of ModPerf: a draggable modifier panel drawn inside the 3D
Viewport (Object Mode).

* Press the shortcut (default **Y**) over a 3D Viewport to open the panel at
  the mouse cursor; press it again to close it. The panel only works in
  Object Mode and closes when you switch to another mode.
* It always shows the modifier stack of the active object, with Blender's own
  modifier settings.

ModPerf Pro adds the built-in outliner, copy / paste of whole stacks, favourite
modifier stacks and Apply All. When ModPerf
Pro is enabled too, Lite steps aside so the shortcut opens Pro.

Modules
-------
constants, state, utils        shared constants, runtime state and helpers
modifier_info                  modifier facts mirrored from Blender's source
gpu_draw, widgets, tooltips    drawing primitives, widgets and tooltips
ui_layout, modifier_panels     Blender's modifier panels, ported to the panel
modifier_block                 one modifier (header + settings)
hud_layout                     the whole panel and its draw callback
popups, operators, modal       popups, operators and the modal event loop
interaction                    clicks, drags and text editing
keymap, preferences            shortcut and preferences
"""


bl_info = {
    "name" : "modperf_lite_v1",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "category" : "修改器工具" 
}



import bpy
from bpy.app.handlers import persistent

from .constants import PANEL_TITLE
from .state import HUD
from .gpu_draw import _ATLAS, _SHADERS, _unload_brand
from .keymap import PREFERENCES_OT_modperf_lite_key_reset, _register_keymaps, _unregister_keymaps
from .popups import (
    _relink_blender_menus, ADD_CATEGORY_MENUS, OBJECT_OT_modperf_lite_pick,
    VIEW3D_MT_modperf_lite_add, VIEW3D_PT_modperf_lite_popup,
)
from .operators import (
    _close_hud, _pro_enabled, OBJECT_OT_modperf_lite_action, VIEW3D_OT_modperf_lite,
)
from .interaction import _on_depsgraph_update
from .modal import VIEW3D_OT_modperf_lite_modal
from .preferences import MODPERF_LITE_AddonPreferences


def _draw_view_menu(self, context):
    if _pro_enabled():
        return            # ModPerf Pro adds its own entry
    layout = self.layout
    layout.separator()
    layout.operator(VIEW3D_OT_modperf_lite.bl_idname,
                    text=f"Close {PANEL_TITLE}" if HUD.running else PANEL_TITLE,
                    icon='MODIFIER').action = 'TOGGLE'


@persistent
def _on_load_pre(_dummy):
    _close_hud()


classes = (
    # preferences first: other classes read them while registering
    PREFERENCES_OT_modperf_lite_key_reset,
    MODPERF_LITE_AddonPreferences,
    # popups / menus
    VIEW3D_PT_modperf_lite_popup,
    *ADD_CATEGORY_MENUS,
    VIEW3D_MT_modperf_lite_add,
    OBJECT_OT_modperf_lite_pick,
    # panel
    OBJECT_OT_modperf_lite_action,
    VIEW3D_OT_modperf_lite,
    VIEW3D_OT_modperf_lite_modal,
)


def register():
    _relink_blender_menus()
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_view.append(_draw_view_menu)
    if _on_load_pre not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_on_load_pre)
    if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)
    _register_keymaps()


def unregister():
    _close_hud()
    _unregister_keymaps()
    if _on_load_pre in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load_pre)
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
    bpy.types.VIEW3D_MT_view.remove(_draw_view_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    _SHADERS.clear()
    _ATLAS.update(meta_tried=False, icons={}, raw=None, tex=None)
    _unload_brand()
