"""Edit Mode operators for floater faces (see floater_faces.py): Mark, Clear, Select."""

from __future__ import annotations

import bpy

from . import floater_faces
from .registration import safe_register_class, safe_unregister_class


def _edit_mesh_objects(context):
    objects = list(getattr(context, "objects_in_mode_unique_data", None) or [])
    if not objects and getattr(context, "edit_object", None) is not None:
        objects = [context.edit_object]
    return [obj for obj in objects if getattr(obj, "type", None) == "MESH"]


def _poll_edit_mesh(context) -> bool:
    return getattr(context, "mode", "") == "EDIT_MESH" and bool(_edit_mesh_objects(context))


def _set_selected(context, value: bool) -> tuple[int, int]:
    import bmesh

    changed_total = 0
    marked_total = 0
    for obj in _edit_mesh_objects(context):
        bm = bmesh.from_edit_mesh(obj.data)
        changed, total = floater_faces.set_marked(obj, bm, value)
        if changed or not value:
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        changed_total += changed
        marked_total += total
        if changed:
            obj.data.update_tag()
    return changed_total, marked_total


class MASTER_BAKER_OT_mark_floater_faces(bpy.types.Operator):
    bl_idname = "master_baker.mark_floater_faces"
    bl_label = "Mark Floater"
    bl_description = (
        "Mark the selected faces of a High mesh as floaters: they still bake into Normal and "
        "the other maps but cast no AO onto anything else"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _poll_edit_mesh(context)

    def execute(self, context):
        changed, total = _set_selected(context, True)
        if changed == 0:
            self.report({"WARNING"}, "Select the floater faces first (L picks a whole piece)")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Marked {changed} faces as floaters ({total} in total)")
        return {"FINISHED"}


class MASTER_BAKER_OT_clear_floater_faces(bpy.types.Operator):
    bl_idname = "master_baker.clear_floater_faces"
    bl_label = "Clear Floater"
    bl_description = "Clear the floater mark from the selected faces"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _poll_edit_mesh(context)

    def execute(self, context):
        changed, total = _set_selected(context, False)
        if changed == 0:
            self.report({"INFO"}, "None of the selected faces were marked as floaters")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Cleared {changed} floater faces ({total} still marked)")
        return {"FINISHED"}


class MASTER_BAKER_OT_select_floater_faces(bpy.types.Operator):
    bl_idname = "master_baker.select_floater_faces"
    bl_label = "Select Floaters"
    bl_description = "Select the faces marked as floaters"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _poll_edit_mesh(context)

    def execute(self, context):
        import bmesh

        # Face select mode: in vertex mode an unmarked face whose vertices all belong to
        # marked faces would read as selected too.
        tool_settings = getattr(context, "tool_settings", None)
        if tool_settings is not None:
            tool_settings.mesh_select_mode = (False, False, True)
        selected = 0
        for obj in _edit_mesh_objects(context):
            bm = bmesh.from_edit_mesh(obj.data)
            layer = bm.faces.layers.bool.get(floater_faces.ATTRIBUTE_NAME)
            if layer is None:
                continue
            for face in bm.faces:
                if face[layer] and not face.select:
                    face.select_set(True)
                    selected += 1
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        if selected == 0:
            self.report({"INFO"}, "No further floater faces to select")
        return {"FINISHED"}


#: Tint of marked faces in Edit Mode (premultiplied by the draw's alpha blend).
_TINT = (1.0, 0.55, 0.1, 0.35)
#: object pointer -> (key, batch). Rebuilt when the marks or the face/vertex counts change.
_BATCHES: dict[int, tuple] = {}
_DRAW_HANDLE = None


def _tint_batch(obj):
    import bmesh
    import gpu
    from gpu_extras.batch import batch_for_shader

    data = obj.data
    bm = bmesh.from_edit_mesh(data)
    layer = bm.faces.layers.bool.get(floater_faces.ATTRIBUTE_NAME)
    key = (
        floater_faces.signature(obj),
        len(bm.verts),
        len(bm.faces),
        tuple(round(value, 5) for row in obj.matrix_world for value in row),
    )
    cached = _BATCHES.get(obj.as_pointer())
    if cached is not None and cached[0] == key:
        return cached[1]
    batch = None
    if layer is not None:
        matrix = obj.matrix_world
        positions = []
        for triangle in bm.calc_loop_triangles():
            if triangle[0].face[layer]:
                positions.extend(tuple(matrix @ loop.vert.co) for loop in triangle)
        if positions:
            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            batch = batch_for_shader(shader, "TRIS", {"pos": positions})
    _BATCHES[obj.as_pointer()] = (key, batch)
    return batch


def _draw_tint():
    context = bpy.context
    if getattr(context, "mode", "") != "EDIT_MESH":
        return
    try:
        import gpu
    except Exception:
        return
    # The count property is set by the operators at once; a mesh attribute added during the
    # edit session only reaches obj.data.attributes when Edit Mode exits.
    objects = [
        obj
        for obj in _edit_mesh_objects(context)
        if floater_faces.marked_face_count(obj) or floater_faces.ATTRIBUTE_NAME in obj.data.attributes
    ]
    if not objects:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.depth_mask_set(False)
    try:
        shader.bind()
        shader.uniform_float("color", _TINT)
        for obj in objects:
            try:
                batch = _tint_batch(obj)
            except Exception:
                batch = None
            if batch is not None:
                batch.draw(shader)
    finally:
        gpu.state.depth_mask_set(True)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")


def draw_face_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator(MASTER_BAKER_OT_mark_floater_faces.bl_idname, text="Mark Floater (Fyr)")
    layout.operator(MASTER_BAKER_OT_clear_floater_faces.bl_idname, text="Clear Floater (Fyr)")
    layout.operator(MASTER_BAKER_OT_select_floater_faces.bl_idname, text="Select Floaters (Fyr)")


CLASSES = (
    MASTER_BAKER_OT_mark_floater_faces,
    MASTER_BAKER_OT_clear_floater_faces,
    MASTER_BAKER_OT_select_floater_faces,
)

_MENUS = ("VIEW3D_MT_edit_mesh_faces", "VIEW3D_MT_edit_mesh_context_menu")


def register():
    global _DRAW_HANDLE
    for cls in CLASSES:
        safe_register_class(cls)
    if _DRAW_HANDLE is None:
        try:
            _DRAW_HANDLE = bpy.types.SpaceView3D.draw_handler_add(_draw_tint, (), "WINDOW", "POST_VIEW")
        except Exception:
            _DRAW_HANDLE = None
    for name in _MENUS:
        menu = getattr(bpy.types, name, None)
        if menu is not None:
            try:
                menu.append(draw_face_menu)
            except Exception:
                pass


def unregister():
    global _DRAW_HANDLE
    if _DRAW_HANDLE is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW_HANDLE, "WINDOW")
        except Exception:
            pass
        _DRAW_HANDLE = None
    _BATCHES.clear()
    for name in _MENUS:
        menu = getattr(bpy.types, name, None)
        if menu is not None:
            try:
                menu.remove(draw_face_menu)
            except Exception:
                pass
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
