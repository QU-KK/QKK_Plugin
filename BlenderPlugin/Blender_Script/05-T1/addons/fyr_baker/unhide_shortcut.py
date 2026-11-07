"""Object Mode Alt+H choices for scenes with bake projects."""

import bpy

from . import constants, operators
from .registration import safe_register_class, safe_unregister_class


_KEYMAP_ITEMS = []


def _scene_projects(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    return getattr(settings, "projects", ()) if settings is not None else ()


def _hidden_high_objects(context):
    """Snapshot eye-hidden high meshes in the current view layer."""
    view_layer = context.view_layer
    hidden = []
    seen = set()
    for project in _scene_projects(context):
        for obj in operators.project_role_reference_targets(project, constants.OBJECT_ROLE_HIGH):
            key = obj.as_pointer()
            if key in seen:
                continue
            seen.add(key)
            if view_layer.objects.get(obj.name) is not obj:
                continue
            if obj.hide_get(view_layer=view_layer):
                hidden.append(obj)
    return hidden


class MASTER_BAKER_OT_unhide_objects(bpy.types.Operator):
    bl_idname = "master_baker.unhide_objects"
    bl_label = "Unhide Objects"
    bl_description = "Unhide objects, optionally preserving hidden high-poly bake sources"
    bl_options = {"REGISTER", "UNDO"}

    keep_high_hidden: bpy.props.BoolProperty(
        name="Keep High Poly Hidden",
        description="Leave previously hidden high-poly bake sources hidden",
        default=False,
    )

    def execute(self, context):
        hidden_high = _hidden_high_objects(context) if self.keep_high_hidden else ()
        result = bpy.ops.object.hide_view_clear()
        if "FINISHED" not in result:
            return result
        for obj in hidden_high:
            obj.hide_set(True, view_layer=context.view_layer)
        return result


def _draw_unhide_choices(menu, _context):
    layout = menu.layout
    layout.operator_context = "EXEC_DEFAULT"
    layout.operator(
        MASTER_BAKER_OT_unhide_objects.bl_idname,
        text="Unhide All",
        icon="HIDE_OFF",
    ).keep_high_hidden = False
    layout.operator(
        MASTER_BAKER_OT_unhide_objects.bl_idname,
        text="Keep High Poly Hidden",
        icon="HIDE_ON",
    ).keep_high_hidden = True


class MASTER_BAKER_OT_unhide_prompt(bpy.types.Operator):
    bl_idname = "master_baker.unhide_prompt"
    bl_label = "Unhide Objects"
    bl_description = "Choose whether Alt+H reveals high-poly bake sources"

    def invoke(self, context, _event):
        if not _scene_projects(context):
            return bpy.ops.object.hide_view_clear()
        context.window_manager.popup_menu(
            _draw_unhide_choices,
            title="Unhide Objects",
            icon="HIDE_OFF",
        )
        return {"FINISHED"}

    def execute(self, context):
        if not _scene_projects(context):
            return bpy.ops.object.hide_view_clear()
        return bpy.ops.master_baker.unhide_objects(keep_high_hidden=True)


_CLASSES = (MASTER_BAKER_OT_unhide_objects, MASTER_BAKER_OT_unhide_prompt)


def register():
    for cls in _CLASSES:
        safe_register_class(cls)
    wm = getattr(bpy.context, "window_manager", None)
    keyconfig = getattr(getattr(wm, "keyconfigs", None), "addon", None)
    if keyconfig is not None:
        keymap = keyconfig.keymaps.new(name="Object Mode", space_type="EMPTY")
        item = keymap.keymap_items.new(MASTER_BAKER_OT_unhide_prompt.bl_idname, "H", "PRESS", alt=True)
        _KEYMAP_ITEMS.append((keymap, item))


def unregister():
    for keymap, item in _KEYMAP_ITEMS:
        keymap.keymap_items.remove(item)
    _KEYMAP_ITEMS.clear()
    for cls in reversed(_CLASSES):
        safe_unregister_class(cls)
