"""
quick_view — bundled into Keymapper.

Adds keymapper.op_quick_view, a pie menu for switching the 3D viewport to a
standard axis-aligned view plus persp/ortho and quadview toggles.

Pie slot layout (numpad positions):
        7  8  9
        4  .  6
        1  2  3
Blender fills slots in this fixed order: W, E, S, N, NW, NE, SW, SE
(= numpad 4, 6, 2, 8, 7, 9, 1, 3), so the draw() calls are ordered to land
each item in its labelled position.

Originally from the standalone "Maya Pies" addon; bundled here so Keymapper
users get the operator without a separate install. Keymapper manages shortcut
binding, so no keymap is registered by this module.
"""

import bpy
from bpy.types import Operator


OPERATOR_IDNAME = "keymapper.op_quick_view"


# Returns the first valid icon name from the candidates, falling back to
# 'NONE' so an unknown name can never break a draw call. VIEW_ACTIVE_* icons
# exist in Bforartists; on stock Blender they fall back to the AXIS_* icons.
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


class VIEW3D_MT_PIE_keymapper_quick_view(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_PIE_keymapper_quick_view"
    bl_label = "Quick View"

    def draw(self, context):
        pie = self.layout.menu_pie()

        # 4  W  - Left
        pie.operator("view3d.view_axis", text="Left",
                     icon=ic('VIEW_ACTIVE_LEFT', 'AXIS_SIDE')).type = 'LEFT'
        # 6  E  - Right
        pie.operator("view3d.view_axis", text="Right",
                     icon=ic('VIEW_ACTIVE_RIGHT', 'AXIS_SIDE')).type = 'RIGHT'
        # 2  S  - Bottom
        pie.operator("view3d.view_axis", text="Bottom",
                     icon=ic('VIEW_ACTIVE_BOTTOM', 'AXIS_TOP')).type = 'BOTTOM'
        # 8  N  - Top
        pie.operator("view3d.view_axis", text="Top",
                     icon=ic('VIEW_ACTIVE_TOP', 'AXIS_TOP')).type = 'TOP'
        # 7  NW - Front
        pie.operator("view3d.view_axis", text="Front",
                     icon=ic('VIEW_ACTIVE_FRONT', 'AXIS_FRONT')).type = 'FRONT'
        # 9  NE - Back
        pie.operator("view3d.view_axis", text="Back",
                     icon=ic('VIEW_ACTIVE_BACK', 'AXIS_FRONT')).type = 'BACK'
        # 1  SW - Persp/Ortho toggle
        pie.operator("view3d.view_persportho", text="Persp/Ortho",
                     icon=ic('VIEW_PERSPECTIVE', 'ARROW_LEFTRIGHT'))
        # 3  SE - QuadView toggle
        pie.operator("screen.region_quadview", text="QuadView",
                     icon=ic('QUADVIEW', 'MESH_GRID'))


class KEYMAPPER_OT_op_quick_view(Operator):
    """Open the quick view pie menu"""
    bl_idname = OPERATOR_IDNAME
    bl_label = "Quick View"
    bl_description = "Open a pie menu for standard viewport angles"

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name=VIEW3D_MT_PIE_keymapper_quick_view.bl_idname)
        return {'FINISHED'}


classes = (
    VIEW3D_MT_PIE_keymapper_quick_view,
    KEYMAPPER_OT_op_quick_view,
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
