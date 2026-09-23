"""
pivot_transform — bundled into Keymapper.

Adds keymapper.op_pivot_transform, which toggles Maya-style pivot point editing
by flipping the scene's `use_transform_data_origin` tool setting (and enabling
the object-translate gizmo when available).

Originally the standalone "PivotTransform" addon by JFW; bundled here so
Keymapper users get the operator without a separate install. The standalone
addon's optional hotkey system and AddonPreferences are intentionally omitted —
Keymapper manages shortcut binding, so a self-registered keymap would be both
redundant and a source of conflicts.
"""

import bpy
from bpy.types import Operator


OPERATOR_IDNAME = "keymapper.op_pivot_transform"

# Module-level toggle state, mirroring the original addon's behavior.
_pivot_edit_enabled = False


class KEYMAPPER_OT_op_pivot_transform(Operator):
    bl_idname = OPERATOR_IDNAME
    bl_label = "Pivot Transform"
    bl_description = "Toggle Maya-style pivot editing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global _pivot_edit_enabled

        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        ts = context.scene.tool_settings

        if not _pivot_edit_enabled:
            ts.use_transform_data_origin = True
            if hasattr(context.space_data, "show_gizmo_object_translate"):
                context.space_data.show_gizmo_object_translate = True
            _pivot_edit_enabled = True
        else:
            ts.use_transform_data_origin = False
            _pivot_edit_enabled = False

        return {'FINISHED'}


classes = (
    KEYMAPPER_OT_op_pivot_transform,
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
