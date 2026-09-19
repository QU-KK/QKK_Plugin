"""
select_tool_pie — bundled into Keymapper.

Adds keymapper.op_select_tool_pie, a pie menu for switching the active
selection tool in the 3D viewport.

Pie slot layout (numpad positions):
        7  8  9
        4  .  6
        1  2  3
Blender fills slots in this fixed order: W, E, S, N, NW, NE, SW, SE
(= numpad 4, 6, 2, 8, 7, 9, 1, 3), so the draw() calls are ordered to land
each item in its labelled position:

    Left (W)   - Box Select
    Top (N)    - Circle Select
    Right (E)  - Lasso Select
    Bottom (S) - Tweak

Keymapper manages shortcut binding, so no keymap is registered by this module.
"""

import bpy
from bpy.types import Operator


OPERATOR_IDNAME = "keymapper.op_select_tool_pie"


# Returns the first valid icon name from the candidates, falling back to
# 'NONE' so an unknown name can never break a draw call.
_VALID_ICONS = None


def ic(*names):
    global _VALID_ICONS
    if _VALID_ICONS is None:
        try:
            params = bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"]
            _VALID_ICONS = {e.identifier for e in params.enum_items}
        except Exception:
            _VALID_ICONS = set()
    for n in names:
        if not _VALID_ICONS or n in _VALID_ICONS:
            return n
    return 'NONE'


class VIEW3D_MT_PIE_keymapper_select_tool(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_PIE_keymapper_select_tool"
    bl_label = "Tool-Select Menu"

    def draw(self, context):
        pie = self.layout.menu_pie()

        # 4  W - Box Select
        pie.operator("wm.tool_set_by_id", text="Box Select",
                     icon=ic('SELECT_SET', 'MESH_PLANE')).name = "builtin.select_box"
        # 6  E - Lasso Select
        pie.operator("wm.tool_set_by_id", text="Lasso Select",
                     icon=ic('GP_ONLY_SELECTED', 'MOD_CURVE')).name = "builtin.select_lasso"
        # 2  S - Tweak
        pie.operator("wm.tool_set_by_id", text="Tweak",
                     icon=ic('RESTRICT_SELECT_OFF', 'ARROW_LEFTRIGHT')).name = "builtin.select"
        # 8  N - Circle Select
        pie.operator("wm.tool_set_by_id", text="Circle Select",
                     icon=ic('MESH_CIRCLE', 'ANTIALIASED')).name = "builtin.select_circle"


class KEYMAPPER_OT_op_select_tool_pie(Operator):
    """Open the select tool pie menu"""
    bl_idname = OPERATOR_IDNAME
    bl_label = "Tool-Select Menu"
    bl_description = "Open a pie menu for switching the active selection tool"

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name=VIEW3D_MT_PIE_keymapper_select_tool.bl_idname)
        return {'FINISHED'}


classes = (
    VIEW3D_MT_PIE_keymapper_select_tool,
    KEYMAPPER_OT_op_select_tool_pie,
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
