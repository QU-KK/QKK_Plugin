from __future__ import annotations

from dataclasses import dataclass

try:
    import bpy
except Exception:  # pragma: no cover - fake test environments may not provide bpy
    bpy = None

from . import constants


@dataclass(slots=True)
class ResolvedLowSlotTarget:
    project_index: int
    group_index: int
    group: object
    slot_index: int
    slot: object
    object_ref: object


@dataclass(slots=True)
class ResolvedPreviewTarget:
    project_index: int
    group_index: int
    group: object
    slot_indices: tuple[int, ...]


def _overlay_settings_state(settings):
    try:
        from . import properties as _properties
    except Exception:
        _properties = None
    if _properties is not None and hasattr(_properties, "overlay_settings_state"):
        return _properties.overlay_settings_state(settings)
    nested_state = getattr(settings, "overlay_settings", None) if settings is not None else None
    if nested_state is not None:
        return nested_state
    return settings


def _group_role_assignments_state(group):
    try:
        from . import properties as _properties
    except Exception:
        _properties = None
    if _properties is not None and hasattr(_properties, "group_role_assignments_state"):
        return _properties.group_role_assignments_state(group)
    nested_state = getattr(group, "role_assignments", None) if group is not None else None
    if nested_state is not None:
        return nested_state
    return group


def _group_projection_settings_state(group):
    try:
        from . import properties as _properties
    except Exception:
        _properties = None
    if _properties is not None and hasattr(_properties, "group_projection_settings_state"):
        return _properties.group_projection_settings_state(group)
    nested_state = getattr(group, "projection_settings", None) if group is not None else None
    if nested_state is not None:
        return nested_state
    return group


def _group_metadata_state(group):
    try:
        from . import properties as _properties
    except Exception:
        _properties = None
    if _properties is not None and hasattr(_properties, "group_metadata_state"):
        return _properties.group_metadata_state(group)
    nested_state = getattr(group, "metadata", None) if group is not None else None
    if nested_state is not None:
        return nested_state
    return group


def _resolve_index(index: int, item_count: int) -> int | None:
    if item_count <= 0:
        return None
    return min(max(int(index), 0), item_count - 1)


def _object_pointer(obj) -> int:
    if obj is None:
        return 0
    as_pointer = getattr(obj, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            return 0
    return id(obj)


def preview_scope(settings) -> str:
    overlay_state = _overlay_settings_state(settings)
    scope = str(
        getattr(
            overlay_state,
            "cage_preview_scope",
            constants.CAGE_PREVIEW_SCOPE_SELECTED_LOW_MESHES,
        )
        or constants.CAGE_PREVIEW_SCOPE_SELECTED_LOW_MESHES
    ).strip()
    if scope not in {
        constants.CAGE_PREVIEW_SCOPE_ACTIVE_GROUP,
        constants.CAGE_PREVIEW_SCOPE_SELECTED_LOW_MESHES,
        constants.CAGE_PREVIEW_SCOPE_ALL,
    }:
        return constants.CAGE_PREVIEW_SCOPE_SELECTED_LOW_MESHES
    return scope


def _same_struct(left, right) -> bool:
    """Identity for RNA wrappers: Blender hands out a fresh wrapper per access, so
    ``is`` never matches two wrappers of one struct. Compare the RNA pointer."""
    if left is None or right is None:
        return False
    return left is right or _object_pointer(left) == _object_pointer(right)


def _project_index_for_project(settings, project) -> int:
    projects = getattr(settings, "projects", []) if settings is not None else []
    for project_index, candidate in enumerate(projects):
        if _same_struct(candidate, project):
            return int(project_index)
    return -1


def valid_low_slot_indices(group) -> tuple[int, ...]:
    if group is None:
        return ()
    role_state = _group_role_assignments_state(group)
    slot_indices: list[int] = []
    for slot_index, slot in enumerate(getattr(role_state, "low_meshes", [])):
        obj = getattr(slot, "object_ref", None)
        if obj is not None and getattr(obj, "type", None) == "MESH":
            slot_indices.append(int(slot_index))
    return tuple(slot_indices)


def selected_low_slot_targets(scene, context=None, *, project=None) -> list[ResolvedLowSlotTarget]:
    resolved_context = context
    if resolved_context is None and bpy is not None:
        resolved_context = getattr(bpy, "context", None)
    settings, resolved_project, _active_group = resolve_project_group(scene)
    if project is not None:
        resolved_project = project
    if settings is None or resolved_project is None:
        return []

    selected_objects = [
        obj
        for obj in getattr(resolved_context, "selected_objects", []) if obj is not None and getattr(obj, "type", None) == "MESH"
    ]
    if not selected_objects:
        return []
    selected_pointers = {_object_pointer(obj) for obj in selected_objects}
    project_index = _project_index_for_project(settings, resolved_project)
    targets: list[ResolvedLowSlotTarget] = []
    for group_index, candidate_group in enumerate(getattr(resolved_project, "groups", [])):
        role_state = _group_role_assignments_state(candidate_group)
        for slot_index, slot in enumerate(getattr(role_state, "low_meshes", [])):
            obj = getattr(slot, "object_ref", None)
            if obj is None or getattr(obj, "type", None) != "MESH":
                continue
            if _object_pointer(obj) not in selected_pointers:
                continue
            targets.append(
                ResolvedLowSlotTarget(
                    project_index=project_index,
                    group_index=int(group_index),
                    group=candidate_group,
                    slot_index=int(slot_index),
                    slot=slot,
                    object_ref=obj,
                )
            )
    return targets


def resolve_selected_low_slot_targets(scene, context=None, *, project=None) -> list[ResolvedLowSlotTarget]:
    return selected_low_slot_targets(scene, context=context, project=project)


def selected_low_target_groups(scene, context=None, *, project=None) -> list[object]:
    groups: list[object] = []
    seen: set[int] = set()
    for target in selected_low_slot_targets(scene, context=context, project=project):
        pointer = _object_pointer(target.group)
        if pointer in seen:
            continue
        seen.add(pointer)
        groups.append(target.group)
    return groups


def selected_low_slot_anchor(scene, context=None) -> ResolvedLowSlotTarget | None:
    resolved_context = context
    if resolved_context is None and bpy is not None:
        resolved_context = getattr(bpy, "context", None)
    settings, _project, active_group = resolve_project_group(scene)
    targets = selected_low_slot_targets(scene, context=resolved_context)
    if not targets:
        return None

    active_object = getattr(resolved_context, "active_object", None)
    if active_object is not None and getattr(active_object, "type", None) == "MESH":
        active_pointer = _object_pointer(active_object)
        active_matches = [target for target in targets if _object_pointer(target.object_ref) == active_pointer]
        if active_matches:
            if settings is not None and active_group is not None:
                for target in active_matches:
                    if _same_struct(target.group, active_group):
                        return target
            return active_matches[0]
    return targets[0]


def selected_low_offset_value(scene, context=None) -> float:
    anchor = selected_low_slot_anchor(scene, context=context)
    if anchor is None:
        return 0.0
    return max(
        0.0,
        float(getattr(anchor.group, "cage_offset", 0.0) or 0.0)
        + float(getattr(anchor.slot, "cage_offset_delta", 0.0) or 0.0),
    )


def selected_low_offset_values(scene, context=None) -> tuple[float, ...]:
    return tuple(
        max(
            0.0,
            float(getattr(target.group, "cage_offset", 0.0) or 0.0)
            + float(getattr(target.slot, "cage_offset_delta", 0.0) or 0.0),
        )
        for target in selected_low_slot_targets(scene, context=context)
    )


def selected_low_offset_mixed(scene, context=None) -> bool:
    rounded_values = {round(value, 6) for value in selected_low_offset_values(scene, context=context)}
    return len(rounded_values) > 1


def selected_group_offset_value(scene, context=None) -> float:
    anchor = selected_low_slot_anchor(scene, context=context)
    if anchor is None:
        return 0.0
    return float(getattr(anchor.group, "cage_offset", 0.0) or 0.0)


def selected_group_offset_values(scene, context=None) -> tuple[float, ...]:
    return tuple(
        float(getattr(group, "cage_offset", 0.0) or 0.0)
        for group in selected_low_target_groups(scene, context=context)
    )


def selected_group_offset_mixed(scene, context=None) -> bool:
    rounded_values = {round(value, 6) for value in selected_group_offset_values(scene, context=context)}
    return len(rounded_values) > 1


def _filter_cage_overlay_hidden(preview_targets: list[ResolvedPreviewTarget]) -> list[ResolvedPreviewTarget]:
    """Drop preview targets whose group has its cage overlay hidden via the cage menu eye."""
    return [
        target
        for target in preview_targets
        if not bool(getattr(target.group, "cage_overlay_hidden", False))
    ]


#: (pass serial, scene pointer, result) of the last full resolve inside a read-only pass.
_PASS_PREVIEW_TARGETS: tuple | None = None


def _active_read_pass_serial() -> int | None:
    try:
        from . import properties
    except Exception:
        return None
    if getattr(properties, "_ROLE_SYNC_PASS", None) is None:
        return None
    return int(getattr(properties, "_ROLE_SYNC_PASS_SERIAL", 0))


def resolve_preview_targets(scene, context=None, *, include_hidden: bool = False) -> tuple[object | None, object | None, object | None, list[ResolvedPreviewTarget]]:
    # One viewport draw resolves the targets for the static key, the display key and
    # (on a rebuild) the static build; inside a properties.role_sync_once_per_pass
    # block nothing can change, so the first full resolve stands for the whole pass.
    global _PASS_PREVIEW_TARGETS
    serial = _active_read_pass_serial()
    scene_key = None
    if serial is not None:
        try:
            scene_key = int(scene.as_pointer()) if scene is not None else 0
        except Exception:
            serial = None
    if serial is not None:
        cached = _PASS_PREVIEW_TARGETS
        if cached is not None and cached[0] == serial and cached[1] == scene_key:
            resolved = cached[2]
        else:
            resolved = _resolve_preview_targets_uncached(scene, context)
            _PASS_PREVIEW_TARGETS = (serial, scene_key, resolved)
    else:
        _PASS_PREVIEW_TARGETS = None
        resolved = _resolve_preview_targets_uncached(scene, context)
    settings, project, group, preview_targets = resolved
    if include_hidden:
        return settings, project, group, list(preview_targets)
    return settings, project, group, _filter_cage_overlay_hidden(preview_targets)


def _resolve_preview_targets_uncached(scene, context=None) -> tuple[object | None, object | None, object | None, list[ResolvedPreviewTarget]]:
    settings, project, group = resolve_project_group(scene)
    if settings is None or project is None or group is None:
        return settings, project, group, []

    # Cage preview is hierarchy-driven: every bake group in the active project is a
    # preview target, and per-group visibility is controlled solely by the cage menu
    # toggles (cage_overlay_hidden). Selection no longer affects which cages are shown.
    # The static overlay cache resolves with include_hidden=True and filters hidden
    # groups at draw time instead, so eye toggles never invalidate built cage batches.
    project_index = _project_index_for_project(settings, project)
    preview_targets = [
        ResolvedPreviewTarget(
            project_index=project_index,
            group_index=int(group_index),
            group=target_group,
            slot_indices=valid_low_slot_indices(target_group),
        )
        for group_index, target_group in enumerate(getattr(project, "groups", []))
    ]
    return settings, project, group, preview_targets


def preview_target_groups(scene, context=None) -> list[object]:
    _settings, _project, active_group, preview_targets = resolve_preview_targets(scene, context=context)
    groups: list[object] = []
    if active_group is not None:
        groups.append(active_group)
    for preview_target in preview_targets:
        if any(existing == preview_target.group for existing in groups):
            continue
        groups.append(preview_target.group)
    return groups


def active_low_slot(group):
    if group is None:
        return None
    role_state = _group_role_assignments_state(group)
    slots = getattr(role_state, "low_meshes", [])
    slot_count = len(slots)
    if slot_count <= 0:
        return None
    slot_index = _resolve_index(getattr(role_state, "low_mesh_index", 0), slot_count)
    if slot_index is None:
        return None
    return slots[slot_index]


def active_low_mesh_object(group):
    slot = active_low_slot(group)
    if slot is None:
        return None
    obj = getattr(slot, "object_ref", None)
    if obj is None or getattr(obj, "type", None) != "MESH":
        return None
    return obj


def preview_suppressed_for_context(context) -> bool:
    return getattr(context, "mode", "") == "EDIT_MESH"


def resolve_project_group(scene):
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if settings is None:
        return None, None, None

    active_project_index = _resolve_index(getattr(settings, "active_project_index", -1), len(getattr(settings, "projects", [])))
    if active_project_index is None:
        return settings, None, None
    project = settings.projects[active_project_index]
    active_group_index = _resolve_index(getattr(project, "active_group_index", -1), len(getattr(project, "groups", [])))
    group = project.groups[active_group_index] if active_group_index is not None else None
    return settings, project, group
