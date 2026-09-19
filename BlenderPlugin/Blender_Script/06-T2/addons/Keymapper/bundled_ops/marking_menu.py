"""
marking_menu — bundled into Keymapper.

Adds keymapper.op_marking_menu, a Maya-style "marking menu" pie that switches
mesh component select modes and shading from a single pie.

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


OPERATOR_IDNAME = "keymapper.op_marking_menu"


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


class MESH_OT_keymapper_pie_select_mode(Operator):
    """Enter Edit Mode (if needed) and set the mesh select mode"""
    bl_idname = "mesh.keymapper_pie_select_mode"
    bl_label = "Set Component Mode"
    bl_options = {'REGISTER', 'UNDO'}

    select_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('VERT', "Vertex", ""),
            ('EDGE', "Edge", ""),
            ('FACE', "Face", ""),
            ('MULTI', "Multi", ""),
        ],
        default='VERT',
    )

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH'

    def execute(self, context):
        ob = context.active_object
        if ob.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        ts = context.scene.tool_settings
        if self.select_mode == 'MULTI':
            ts.mesh_select_mode = (True, True, True)
        else:
            idx = {'VERT': 0, 'EDGE': 1, 'FACE': 2}[self.select_mode]
            flags = [False, False, False]
            flags[idx] = True
            ts.mesh_select_mode = tuple(flags)
        return {'FINISHED'}


class VIEW3D_MT_PIE_keymapper_marking_menu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_PIE_keymapper_marking_menu"
    bl_label = "Marking Menu"

    def draw(self, context):
        pie = self.layout.menu_pie()

        # 4  W  - Vertex
        pie.operator("mesh.keymapper_pie_select_mode", text="Vertex",
                     icon=ic('VERTEXSEL')).select_mode = 'VERT'
        # 6  E  - Multi
        pie.operator("mesh.keymapper_pie_select_mode", text="Multi",
                     icon=ic('EDITMODE_HLT')).select_mode = 'MULTI'
        # 2  S  - Smooth
        pie.operator("object.shade_smooth", text="Smooth", icon=ic('SHADING_SMOOTH', 'MOD_SMOOTH'))
        # 8  N  - Edge
        pie.operator("mesh.keymapper_pie_select_mode", text="Edge",
                     icon=ic('EDGESEL')).select_mode = 'EDGE'
        # 7  NW - Isolate (local view toggle)
        pie.operator("view3d.localview", text="Isolate", icon=ic('ZOOM_SELECTED'))
        # 9  NE - Object
        pie.operator("object.mode_set", text="Object",
                     icon=ic('OBJECT_DATAMODE')).mode = 'OBJECT'
        # 1  SW - Shade Flat
        pie.operator("object.shade_flat", text="Shade Flat", icon=ic('SHADING_FLAT', 'MESH_CUBE'))
        # 3  SE - Face
        pie.operator("mesh.keymapper_pie_select_mode", text="Face",
                     icon=ic('FACESEL')).select_mode = 'FACE'


class KEYMAPPER_OT_op_marking_menu(Operator):
    """Open the marking pie menu"""
    bl_idname = OPERATOR_IDNAME
    bl_label = "Marking Menu"
    bl_description = "Open a Maya-style marking pie menu"

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name=VIEW3D_MT_PIE_keymapper_marking_menu.bl_idname)
        return {'FINISHED'}


classes = (
    MESH_OT_keymapper_pie_select_mode,
    VIEW3D_MT_PIE_keymapper_marking_menu,
    KEYMAPPER_OT_op_marking_menu,
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
