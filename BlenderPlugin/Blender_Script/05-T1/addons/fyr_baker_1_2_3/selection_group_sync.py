"""Find the bake groups a viewport selection belongs to, and optionally follow it.

The hierarchy marks every group that holds a selected mesh. With "Follow
Selection" on, making an object active in the viewport or Outliner also makes
its bake group the active one, so a long group list never has to be searched by
hand.
"""

import bpy

from . import constants, project_structure, properties

_MSGBUS_OWNER = object()
_ROLES = (constants.OBJECT_ROLE_LOW, constants.OBJECT_ROLE_HIGH, constants.OBJECT_ROLE_CAGE)


def group_object_pointers(group) -> set[int]:
    """Pointers of the group's low, high and cage objects."""
    pointers = set()
    for role in _ROLES:
        for obj in project_structure.group_role_targets(group, role):
            if obj is not None:
                pointers.add(obj.as_pointer())
    return pointers


def group_contains_any(group, pointers) -> bool:
    return bool(pointers) and not group_object_pointers(group).isdisjoint(pointers)


def selected_object_pointers(context=None) -> frozenset:
    context = context or bpy.context
    try:
        return frozenset(obj.as_pointer() for obj in (getattr(context, "selected_objects", None) or ()))
    except Exception:
        return frozenset()


def sync_active_group_to_object(context, obj) -> bool:
    """Make the first group holding ``obj`` active. Returns True when it changed.

    Nothing changes while the active group (or any shift-included group) already
    holds the object, so a mesh shared by several groups never flips the focus.
    """
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    project = properties.get_active_project(scene)
    if obj is None or settings is None or project is None:
        return False
    groups = list(getattr(project, "groups", []) or [])
    if not groups:
        return False
    pointer = obj.as_pointer()
    holding = [index for index, group in enumerate(groups) if pointer in group_object_pointers(group)]
    if not holding:
        return False
    focus_is_group = str(getattr(project, "hierarchy_focus", "") or "") == constants.HIERARCHY_FOCUS_GROUP
    active_index = int(getattr(project, "active_group_index", -1))
    if focus_is_group:
        targeted = set(properties.bake_group_target_names(project, settings))
        for index in holding:
            name = str(getattr(groups[index], "name", "") or "").strip()
            if index == active_index or (name and name in targeted):
                return False
    target = holding[0]
    group = groups[target]
    # Open the group so its mesh row is visible next to the highlighted group row.
    if not bool(getattr(group, "cage_menu_expanded", True)):
        group.cage_menu_expanded = True
    properties.set_bake_group_targets(settings, [])
    project.active_group_index = target
    project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP
    return True


def _follow_enabled(settings) -> bool:
    ui_state = properties.scene_ui_state(settings) if settings is not None else None
    return bool(getattr(ui_state, "follow_selection", False))


def _on_active_object_changed(*_args) -> None:
    try:
        context = bpy.context
        scene = getattr(context, "scene", None)
        if not _follow_enabled(getattr(scene, "fyr_baker_settings", None)):
            return
        view_layer = getattr(context, "view_layer", None)
        obj = getattr(getattr(view_layer, "objects", None), "active", None)
        if obj is None or not getattr(obj, "select_get", None) or not obj.select_get():
            return
        if sync_active_group_to_object(context, obj):
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
    except Exception:
        pass


def follow_selection_update(self, context) -> None:
    """Turning the toggle on jumps to the current active object's group right away."""
    if not bool(getattr(self, "follow_selection", False)):
        return
    try:
        obj = getattr(getattr(context, "view_layer", None), "objects", None)
        obj = getattr(obj, "active", None)
        if obj is not None and obj.select_get():
            sync_active_group_to_object(context, obj)
    except Exception:
        pass


def subscribe() -> None:
    msgbus = getattr(bpy, "msgbus", None)
    layer_objects = getattr(getattr(bpy, "types", None), "LayerObjects", None)
    if msgbus is None or layer_objects is None:
        return
    try:
        msgbus.clear_by_owner(_MSGBUS_OWNER)
        msgbus.subscribe_rna(
            key=(layer_objects, "active"),
            owner=_MSGBUS_OWNER,
            args=(),
            notify=_on_active_object_changed,
        )
    except Exception:
        pass


def unsubscribe() -> None:
    msgbus = getattr(bpy, "msgbus", None)
    if msgbus is None:
        return
    try:
        msgbus.clear_by_owner(_MSGBUS_OWNER)
    except Exception:
        pass
