"""
asset_browser_window — bundled into Keymapper.

Adds keymapper.op_open_assetbrowser_window, which opens a brand-new Blender
window and switches it to the Asset Browser. It never modifies an existing
window — a new window is always created.

Originally the standalone "Asset Browser Window" addon by JFW; bundled here so
Keymapper users get the operator without a separate install. The standalone
addon's AddonPreferences class is intentionally omitted — Keymapper manages its
own preferences and shortcut binding.
"""

import bpy
from bpy.types import Operator


OPERATOR_IDNAME = "keymapper.op_open_assetbrowser_window"


class KEYMAPPER_OT_op_open_assetbrowser_window(Operator):
    """Open a new window and set it to the Asset Browser"""

    bl_idname = OPERATOR_IDNAME
    bl_label = "Open Asset Browser Window"
    bl_options = {'REGISTER'}

    def execute(self, context):
        wm = context.window_manager

        # Remember the windows that exist *before* we open a new one, so we can
        # reliably identify the new window afterwards and never touch an
        # existing one.
        windows_before = set(wm.windows)

        # Use Blender's built-in operator to spawn a fresh window. It clones the
        # currently active window's screen layout into a new window.
        result = bpy.ops.wm.window_new()
        if 'FINISHED' not in result:
            self.report({'ERROR'}, "Could not open a new window")
            return {'CANCELLED'}

        # Find the window that was just created (the one not present before).
        new_windows = [w for w in wm.windows if w not in windows_before]
        if not new_windows:
            self.report({'ERROR'}, "New window could not be located")
            return {'CANCELLED'}

        new_window = new_windows[-1]

        # Pick the largest area in the new window's screen to convert. The
        # largest area is almost always the main editor, which gives the Asset
        # Browser a sensible amount of room.
        screen = new_window.screen
        if not screen or not screen.areas:
            self.report({'ERROR'}, "New window has no editable area")
            return {'CANCELLED'}

        target_area = max(screen.areas, key=lambda a: a.width * a.height)

        # Switch the area to the File Browser editor, then put it into Asset
        # Browser mode.
        try:
            target_area.type = 'FILE_BROWSER'
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Could not set area type: %s" % ex)
            return {'CANCELLED'}

        space = target_area.spaces.active
        if space is not None and hasattr(space, "browse_mode"):
            try:
                space.browse_mode = 'ASSETS'
            except Exception as ex:  # noqa: BLE001
                self.report({'WARNING'},
                            "Window opened but Asset mode failed: %s" % ex)

        target_area.tag_redraw()
        return {'FINISHED'}


classes = (
    KEYMAPPER_OT_op_open_assetbrowser_window,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
