from __future__ import annotations

import re
import types

import bpy

from . import constants, matching, naming, preferences, preset_store, properties, tagging


def next_available_label(base_name: str, existing_names) -> str:
    used_names = {str(name or "").strip().casefold() for name in existing_names if str(name or "").strip()}
    normalized_base = str(base_name or "").strip() or "Item"
    if normalized_base.casefold() not in used_names:
        return normalized_base

    index = 1
    while True:
        candidate = f"{normalized_base}_{index:02d}"
        if candidate.casefold() not in used_names:
            return candidate
        index += 1


def create_default_project(context):
    settings = context.scene.fyr_baker_settings
    project = settings.projects.add()
    project.name = next_available_label(
        "BakeProject",
        (getattr(item, "name", "") for item in settings.projects if item != project),
    )
    properties.ensure_default_maps(project)
    # No texture set is seeded. Groups start standalone (texture_set_name == ""), which makes
    # the output stem the BAKE GROUP name -- a group called "Pottery" writes Pottery_Normal.tga
    # out of the box. Seeding a project-named set here used to stamp every first group with the
    # project name, so a fresh project wrote BakeProject_*.tga regardless of the group name.
    # Texture sets are created on demand (New Texture Set / assign / merge).
    project.active_texture_set_index = 0
    # Before the scaffold call: a "Use My Collections" default must never create the
    # project's root collection in the first place.
    mode = default_collection_mode()
    if str(getattr(project, "collection_mode", constants.COLLECTION_MODE_FYR) or "") != mode:
        project.collection_mode = mode
    ensure_project_collection_scaffold(context, project)
    settings.active_project_index = len(settings.projects) - 1
    properties.overlay_settings_state(settings).show_cage_overlay = True
    settings.status_message = "Created Bake Project"
    return project


def create_material_project(context, target_objects, enabled_channels, *, include_normal=False, project_name="MaterialBake"):
    """Create a same-object material-flatten project (workflow=MATERIAL).

    V1 semantics (docs/MATERIAL_BAKING_WORKFLOW_PLAN.md sec 3.4): one bake group and one
    texture set per selected object. Each object is a LOW target only -- never assigned to
    both Low and High -- so the shared bake pipeline self-bakes the object's own materials
    (empty high => SELF_MATERIAL) instead of projecting a fabricated high source.

    The project-global map stack holds one enabled MAP_MATERIAL row per enabled PBR channel
    (plus an optional material-space MAP_NORMAL row). No geometry maps and no cage/projection
    concepts are seeded. The project is created but NOT baked.
    """
    project = create_default_project(context)
    project.workflow = constants.WORKFLOW_MATERIAL
    settings = context.scene.fyr_baker_settings
    project.name = next_available_label(
        project_name,
        (getattr(item, "name", "") for item in settings.projects if item != project),
    )

    # Replace the default geometry map stack with the requested material channels.
    # Order the stack by the canonical MATERIAL_CHANNEL_ITEMS order so the result is
    # deterministic regardless of the order the caller passed channels in.
    project.maps.clear()
    requested = set(enabled_channels)
    ordered_channels = [item[0] for item in constants.MATERIAL_CHANNEL_ITEMS if item[0] in requested]
    for channel in ordered_channels:
        item = properties.add_map_setting(project, constants.MAP_MATERIAL)
        item.material_channel = channel
        item.enabled = True
        item.execution_route = constants.EXECUTION_ROUTE_AUTO
        # Every material row stores map_type MAP_MATERIAL, so the shared suffix logic would
        # otherwise disambiguate them with generic "Material_2/3" labels. Give each row a
        # clean per-channel suffix (BaseColor / Roughness / ...) so filenames read per
        # channel and the real path + validation agree on the name.
        effective_type = constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE.get(channel, constants.MAP_MATERIAL_ALBEDO)
        item.output_suffix = naming.resolved_map_file_label(effective_type)
    if include_normal:
        # A MAP_MATERIAL row on the NORMAL channel, not a MAP_NORMAL row. Both bake
        # the object's own material normal, but the exporter sends every MAP_NORMAL
        # row in a material project down the Cycles self-bake branch, while this one
        # takes the native Material IR path. Measured on the same material at 2048²:
        # 45 s through Cycles against 1.1 s native, agreeing to a mean 0.0015 (0.39
        # of a 255 level) inside UV coverage. Nothing was gained by the slow route.
        normal_item = properties.add_map_setting(project, constants.MAP_MATERIAL)
        normal_item.material_channel = constants.MATERIAL_CHANNEL_NORMAL
        normal_item.enabled = True
        normal_item.execution_route = constants.EXECUTION_ROUTE_AUTO
        normal_item.output_suffix = naming.resolved_map_file_label(constants.MAP_MATERIAL_NORMAL)
    project.active_map_index = 0

    # One group + one texture set per target object. Rebuild the seeded texture-set list.
    texture_sets = getattr(project, "texture_sets", None)
    if texture_sets is not None and hasattr(texture_sets, "clear"):
        texture_sets.clear()
    project.groups.clear()

    used_group_names: list[str] = []
    used_set_names: list[str] = []
    for obj in target_objects:
        if getattr(obj, "type", None) != "MESH":
            continue
        base = str(getattr(obj, "name", "") or "Object").strip() or "Object"
        set_name = next_available_label(base, used_set_names)
        used_set_names.append(set_name)
        properties.ensure_texture_set(project, set_name)

        group = project.groups.add()
        group.name = next_available_label(base, used_group_names)
        used_group_names.append(group.name)
        group.texture_set_name = set_name
        # Material projects never project through a cage; pin a passive Distance cage so no
        # auto-cage fit or coverage work is triggered for a role that is unused here.
        group.cage_mode = constants.CAGE_MODE_DISTANCE
        add_unique_role_objects(group, constants.OBJECT_ROLE_LOW, [obj])
        ensure_group_collection_scaffold(context, project, group)
        link_objects_to_group_role_collection(context, project, group, constants.OBJECT_ROLE_LOW, [obj])

    project.active_group_index = 0
    project.active_texture_set_index = 0
    # Cage overlay is meaningless for a material project; keep it off.
    properties.overlay_settings_state(settings).show_cage_overlay = False
    settings.status_message = "Created Material Project"
    project.last_status_message = "Created Material Project"
    return project


def ensure_active_project(context):
    project = properties.get_active_project(context.scene)
    if project is not None:
        return project, False
    return create_default_project(context), True


def ensure_active_group(project, seed_objects=None, context=None):
    group = properties.get_active_group(project)
    if group is not None:
        return group, False

    group = project.groups.add()
    seed_names = [obj.name for obj in (seed_objects or []) if getattr(obj, "type", None) == "MESH"]
    suggested_name = matching.suggest_group_name(seed_names)
    group.name = suggested_name if suggested_name != "BakeGroup" else f"BakeGroup_{len(project.groups):02d}"
    project.active_group_index = len(project.groups) - 1
    project.last_status_message = "Created bake group"
    if context is not None:
        ensure_group_collection_scaffold(context, project, group)
    return group, True


def uses_fyr_collections(project) -> bool:
    """True when Fyr owns an Outliner scaffold for ``project`` (the default).

    The single gate for "Use My Collections": every scaffold builder and every link
    into a role collection checks this, so no call site can create or link a
    collection for an EXISTING-mode project. A project without the field (saved
    before it existed, or a test stand-in) is FYR, which is what it always was.
    """
    mode = str(getattr(project, "collection_mode", "") or constants.COLLECTION_MODE_FYR)
    return mode != constants.COLLECTION_MODE_EXISTING


def default_collection_mode() -> str:
    """The collection mode a NEW project starts in (Preferences > General > Baking)."""
    prefs = preferences.get_preferences(migrate=False)
    mode = str(getattr(prefs, "default_collection_mode", "") or "")
    valid = {item[0] for item in constants.COLLECTION_MODE_ITEMS}
    return mode if mode in valid else constants.COLLECTION_MODE_FYR


def collection_label(name: str, fallback: str) -> str:
    value = str(name or "").strip()
    return value or fallback


def collection_exists(collection) -> bool:
    if collection is None:
        return False
    try:
        name = collection.name
    except ReferenceError:
        return False
    return getattr(getattr(bpy.data, "collections", None), "get", lambda _name: None)(name) is collection


def has_child_collection(parent_collection, child_collection) -> bool:
    return any(existing == child_collection for existing in getattr(parent_collection, "children", []))


# Outliner color tags for the collections Fyr builds, so its scaffold reads apart from
# the artist's own collections at a glance: the project and group containers share
# one color, each role gets its own. Blender's default theme: COLOR_02 orange,
# COLOR_04 green, COLOR_05 blue, COLOR_03 yellow.
SCAFFOLD_COLOR_CONTAINER = "COLOR_02"
SCAFFOLD_ROLE_COLORS = {
    "low_collection": "COLOR_04",
    "high_collection": "COLOR_05",
    "cage_collection": "COLOR_03",
}
# Stamped on a scaffold collection once Fyr has colored it. The color is applied once
# per collection, so an artist who recolors or clears it keeps their choice; scaffolds
# from files saved before coloring existed pick it up the next time they are ensured.
_SCAFFOLD_COLOR_STAMP = "_fyr_color_applied"


def _apply_scaffold_color(collection, color_tag: str | None) -> None:
    if not color_tag:
        return
    try:
        if collection.get(_SCAFFOLD_COLOR_STAMP):
            return
        if str(getattr(collection, "color_tag", "NONE") or "NONE") == "NONE":
            collection.color_tag = color_tag
        collection[_SCAFFOLD_COLOR_STAMP] = True
    except (AttributeError, ReferenceError, TypeError):
        pass


def ensure_child_collection(parent_collection, owner, attribute_name: str, name: str, color_tag: str | None = None):
    collection = getattr(owner, attribute_name, None)
    if collection_exists(collection):
        collection.name = name
        if not has_child_collection(parent_collection, collection):
            parent_collection.children.link(collection)
        _apply_scaffold_color(collection, color_tag)
        return collection

    collection = bpy.data.collections.new(name)
    parent_collection.children.link(collection)
    setattr(owner, attribute_name, collection)
    _apply_scaffold_color(collection, color_tag)
    return collection


def project_collection_name(project) -> str:
    return collection_label(getattr(project, "name", ""), "BakeProject")


def group_collection_name(group) -> str:
    return collection_label(getattr(group, "name", ""), "BakeGroup")


def role_collection_name(group, suffix: str) -> str:
    return f"{group_collection_name(group)}_{suffix}"


def sync_group_collection_metadata(group) -> None:
    metadata_state = properties.group_metadata_state(group)
    collections_state = properties.group_collections_state(group)
    group_collection = getattr(collections_state, "group_collection", None)
    if group_collection is not None:
        tagging.set_metadata_names(
            group_collection,
            group_name=getattr(metadata_state, "name", ""),
            collection_name=getattr(metadata_state, "id_collection_name", "") or getattr(metadata_state, "name", ""),
        )

    for collection, role in (
        (getattr(collections_state, "low_collection", None), constants.OBJECT_ROLE_LOW),
        (getattr(collections_state, "high_collection", None), constants.OBJECT_ROLE_HIGH),
        (getattr(collections_state, "cage_collection", None), constants.OBJECT_ROLE_CAGE),
    ):
        if collection is not None:
            tagging.apply_collection_tag(collection, role, group_name=getattr(group, "name", ""), source="scaffold")


def ensure_project_collection_scaffold(context, project):
    if not uses_fyr_collections(project):
        return None
    scene_collection = getattr(context.scene, "collection", None)
    if scene_collection is None:
        return None
    return ensure_child_collection(
        scene_collection, project, "root_collection", project_collection_name(project), SCAFFOLD_COLOR_CONTAINER
    )


def _clear_invalid_collection_pointer(owner, attr_name, expected_parent=None):
    """Clear a collection pointer if it is the same object as expected_parent or not a valid child of it."""
    col = getattr(owner, attr_name, None)
    if col is None:
        return
    if expected_parent is not None and col is expected_parent:
        try:
            setattr(owner, attr_name, None)
        except (ReferenceError, AttributeError):
            pass
        return
    if expected_parent is not None and not has_child_collection(expected_parent, col):
        try:
            setattr(owner, attr_name, None)
        except (ReferenceError, AttributeError):
            pass


def ensure_group_collection_scaffold(context, project, group):
    if not uses_fyr_collections(project):
        return None
    project_collection = ensure_project_collection_scaffold(context, project)
    if project_collection is None:
        return None

    collections_state = properties.group_collections_state(group)

    # Validate: if the stored group_collection IS the project root (self-reference) or is
    # not a direct child of it, clear the pointer so ensure_child_collection creates a fresh one.
    _clear_invalid_collection_pointer(collections_state, "group_collection", expected_parent=project_collection)
    try:
        setattr(group, "group_collection", getattr(collections_state, "group_collection", None))
    except (ReferenceError, AttributeError):
        pass

    # A group named after its own project (auto-build does this whenever a mesh prefix
    # matches the project name, e.g. project "Skull" + Skull_01_LP) collides with the
    # project root collection, so Blender uniquified it to "Skull.001" and the outliner
    # read "Skull > Skull.001 > Skull_Low" while every sibling read "Skull > Jaw >
    # Jaw_Low". Qualify the group's own collection instead of letting the collision
    # happen (RC sweep 2026-08-29, finding 19).
    desired_group_collection_name = group_collection_name(group)
    if desired_group_collection_name == getattr(project_collection, "name", ""):
        desired_group_collection_name = f"{desired_group_collection_name} Group"
    group_collection = ensure_child_collection(
        project_collection, collections_state, "group_collection", desired_group_collection_name, SCAFFOLD_COLOR_CONTAINER
    )

    # Validate role collection pointers: they must be children of group_collection.
    for role_attr in ("low_collection", "high_collection", "cage_collection"):
        _clear_invalid_collection_pointer(collections_state, role_attr, expected_parent=group_collection)
        try:
            setattr(group, role_attr, getattr(collections_state, role_attr, None))
        except (ReferenceError, AttributeError):
            pass

    ensure_child_collection(
        group_collection, collections_state, "low_collection", role_collection_name(group, "Low"), SCAFFOLD_ROLE_COLORS["low_collection"]
    )
    ensure_child_collection(
        group_collection, collections_state, "high_collection", role_collection_name(group, "High"), SCAFFOLD_ROLE_COLORS["high_collection"]
    )
    ensure_child_collection(
        group_collection, collections_state, "cage_collection", role_collection_name(group, "Cage"), SCAFFOLD_ROLE_COLORS["cage_collection"]
    )
    sync_group_collection_metadata(group)
    return group_collection


def copy_slot_collection(source_collection, target_collection):
    target_collection.clear()
    seen_refs = []
    for source in source_collection:
        source_ref = source.object_ref
        # Skip duplicate object references so a drifted source does not propagate
        # the duplication into the copy (e.g. Duplicate Project).
        if source_ref is not None and any(existing == source_ref for existing in seen_refs):
            continue
        seen_refs.append(source_ref)
        item = target_collection.add()
        item.object_ref = source_ref
        item.cage_offset_delta = float(getattr(source, "cage_offset_delta", 0.0))
        if not bool(getattr(source, "casts_ao", True)):
            item.casts_ao = False


def group_role_slot_collections(group, role: str):
    role_state = properties.group_role_assignments_state(group)
    if role == constants.OBJECT_ROLE_HIGH:
        attr_name = "high_meshes"
        index_attr = "high_mesh_index"
    else:
        attr_name = "low_meshes"
        index_attr = "low_mesh_index"
    collections = []
    for collection in (getattr(group, attr_name, None), getattr(role_state, attr_name, None)):
        if collection is None or any(existing is collection for existing in collections):
            continue
        collections.append(collection)
    return collections, index_attr, role_state


def discard_role_objects(group, objects) -> int:
    """Drop ``objects`` from every low/high slot list on ``group``. Returns the count.

    Suffix grouping used to be purely additive: a mesh that moved to another prefix
    kept its slot in the group it came from, so the old group silently baked the new
    group's geometry as well. Both 2026-08-19 tester bundles show exactly that —
    group #1 holding every mesh in the project.
    """
    targets = [obj for obj in (objects or []) if obj is not None]
    if not targets:
        return 0
    # Counted by (role, object), not by slot: a group mirrors each role list across
    # two collections, so counting removals would report every eviction twice.
    removed: list[tuple] = []
    for role in (constants.OBJECT_ROLE_LOW, constants.OBJECT_ROLE_HIGH):
        collections, _index_attr, _role_state = group_role_slot_collections(group, role)
        unlink: list = []
        for collection in collections:
            for index in range(len(collection) - 1, -1, -1):
                slot_object = getattr(collection[index], "object_ref", None)
                if slot_object is None or not any(slot_object is obj for obj in targets):
                    continue
                collection.remove(index)
                key = (role, getattr(slot_object, "name", "") or id(slot_object))
                if key not in removed:
                    removed.append(key)
                    unlink.append(slot_object)
        # The slot list and the role collection are two views of the same membership;
        # dropping only the slot leaves the mesh sitting under the old group in the
        # Outliner, which reads as the eviction not having happened.
        for slot_object in unlink:
            unlink_object_from_group_role_collection(group, role, slot_object)
    return len(removed)


def add_unique_role_objects(group, role: str, selected_objects) -> int:
    collections, _index_attr, _role_state = group_role_slot_collections(group, role)
    if not collections:
        return 0
    primary = collections[0]
    added = 0
    for obj in selected_objects:
        if getattr(obj, "type", None) != "MESH":
            continue
        if any(getattr(slot, "object_ref", None) is obj for slot in primary):
            continue
        for collection in collections:
            if any(getattr(slot, "object_ref", None) is obj for slot in collection):
                continue
            slot = collection.add()
            slot.object_ref = obj
        added += 1
    return added


def sync_role_slot_collections(source_collection, target_collections) -> None:
    unique_targets = []
    for collection in target_collections:
        if collection is None or any(existing is collection for existing in unique_targets):
            continue
        unique_targets.append(collection)
    for target_collection in unique_targets:
        copy_slot_collection(source_collection, target_collection)


def remove_group_role_slot(group, role: str):
    collections, index_attr, role_state = group_role_slot_collections(group, role)
    if not collections:
        return None
    primary = collections[0]
    current_index = getattr(role_state, index_attr, getattr(group, index_attr, 0))
    removed_object = None
    if 0 <= current_index < len(primary):
        removed_object = getattr(primary[current_index], "object_ref", None)
    for collection in collections:
        if hasattr(collection, "remove") and 0 <= current_index < len(collection):
            collection.remove(current_index)
    new_index = min(max(current_index - 1, 0), max(len(primary) - 1, 0))
    setattr(role_state, index_attr, new_index)
    if hasattr(group, index_attr):
        setattr(group, index_attr, new_index)
    return removed_object


def collection_has_object(collection, obj) -> bool:
    return any(existing == obj for existing in getattr(collection, "objects", []))


def link_object_to_collection(collection, obj) -> None:
    if collection is None or obj is None or collection_has_object(collection, obj):
        return
    collection.objects.link(obj)


def unlink_object_from_collection(collection, obj) -> None:
    if collection is None or obj is None or not collection_has_object(collection, obj):
        return
    collection.objects.unlink(obj)


def group_role_collection(group, role: str):
    collections_state = properties.group_collections_state(group)
    if role == constants.OBJECT_ROLE_HIGH:
        return getattr(collections_state, "high_collection", None)
    if role == constants.OBJECT_ROLE_CAGE:
        return getattr(collections_state, "cage_collection", None)
    return getattr(collections_state, "low_collection", None)


def link_objects_to_group_role_collection(context, project, group, role: str, objects) -> None:
    if not objects or not uses_fyr_collections(project):
        return
    ensure_group_collection_scaffold(context, project, group)
    collection = group_role_collection(group, role)
    for obj in objects:
        link_object_to_collection(collection, obj)


def unlink_object_from_group_role_collection(group, role: str, obj) -> None:
    unlink_object_from_collection(group_role_collection(group, role), obj)


def group_low_mesh_objects(group) -> list:
    """The group's low-poly mesh objects, for export / tile detection.

    A group with a Fyr Low collection reads it exactly as before. A group without
    one (a "Use My Collections" project, or a group whose scaffold was never built)
    reads its low slots instead: the slots are the bake membership, the collection
    was only ever a mirror of them.
    """
    collection = group_role_collection(group, constants.OBJECT_ROLE_LOW)
    if collection is not None:
        source = getattr(collection, "objects", []) or ()
    else:
        source = group_role_targets(group, constants.OBJECT_ROLE_LOW)
    objects: list = []
    for obj in source:
        if getattr(obj, "type", "") != "MESH" or any(existing == obj for existing in objects):
            continue
        objects.append(obj)
    return objects


def generated_cage_target_collection(group, source_object=None):
    """Where a cage Fyr generates for ``group`` is linked.

    The group's Fyr Cage collection when it has one; otherwise the collection the
    low mesh the cage was built from lives in, so the cage lands next to the
    artist's own low-poly rather than loose in the scene root. None means "the
    scene collection" to the caller.
    """
    collection = group_role_collection(group, constants.OBJECT_ROLE_CAGE)
    if collection_exists(collection):
        return collection
    if source_object is not None:
        return primary_collection_for_object(source_object)
    return None


# --- Collection mode switching ---------------------------------------------------

# ID-property on the project recording which mode apply_collection_mode last carried
# out. Blender runs a property's update callback on EVERY assignment, including a preset
# load or Duplicate Project writing the value the project already has, so the switch
# keys on this record rather than on "the callback fired". Absent means FYR: every
# project that predates the setting was built with Fyr's collections.
_APPLIED_COLLECTION_MODE_KEY = "_fyr_collection_mode_applied"


def _applied_collection_mode(project) -> str:
    value = None
    getter = getattr(project, "get", None)
    if callable(getter):
        try:
            value = getter(_APPLIED_COLLECTION_MODE_KEY)
        except Exception:
            value = None
    else:
        value = getattr(project, _APPLIED_COLLECTION_MODE_KEY, None)
    return str(value or constants.COLLECTION_MODE_FYR)


def _set_applied_collection_mode(project, mode: str) -> None:
    try:
        project[_APPLIED_COLLECTION_MODE_KEY] = mode
    except TypeError:
        try:
            setattr(project, _APPLIED_COLLECTION_MODE_KEY, mode)
        except Exception:
            pass
    except Exception:
        pass


def _project_scene_context(context, project):
    """A context whose ``scene`` is the scene that owns ``project``.

    The scaffold helpers only read ``context.scene``. A project's collections belong
    in ITS scene, which is not necessarily the active one when the mode is written
    from a script.
    """
    owner = getattr(project, "id_data", None)
    if owner is not None and getattr(owner, "collection", None) is not None and owner != getattr(context, "scene", None):
        return types.SimpleNamespace(scene=owner)
    return context


def _collection_tree(root) -> list:
    """``root`` and every collection nested under it (each once)."""
    tree: list = []
    pending = [root] if root is not None else []
    while pending:
        collection = pending.pop()
        if any(existing == collection for existing in tree):
            continue
        tree.append(collection)
        pending.extend(child for child in getattr(collection, "children", []) or [] if child is not None)
    return tree


def _project_scaffold_collections(project) -> tuple[list, list, list]:
    """(role collections, group collections, [root]) the project's pointers name.

    Only live pointers count; this is the complete set of collections the mode
    switch is ever allowed to unlink objects from or delete.
    """
    roles: list = []
    groups: list = []
    for group in getattr(project, "groups", []) or []:
        state = properties.group_collections_state(group)
        for attr in ("low_collection", "high_collection", "cage_collection"):
            collection = getattr(state, attr, None)
            if collection_exists(collection) and not any(existing == collection for existing in roles):
                roles.append(collection)
        collection = getattr(state, "group_collection", None)
        if collection_exists(collection) and not any(existing == collection for existing in groups):
            groups.append(collection)
    root = getattr(project, "root_collection", None)
    roots = [root] if collection_exists(root) else []
    return roles, groups, roots


def _clear_project_collection_pointers(project) -> None:
    for group in getattr(project, "groups", []) or []:
        state = properties.group_collections_state(group)
        for attr in ("group_collection", "low_collection", "high_collection", "cage_collection"):
            # Both copies: _sync_group_collections_state promotes a flat pointer back into
            # an empty nested one, so clearing only the nested state would resurrect it.
            for owner in (state, group):
                try:
                    if getattr(owner, attr, None) is not None:
                        setattr(owner, attr, None)
                except (AttributeError, ReferenceError, TypeError):
                    pass
    try:
        if getattr(project, "root_collection", None) is not None:
            project.root_collection = None
    except (AttributeError, ReferenceError, TypeError):
        pass


def release_fyr_collections(context, project) -> dict:
    """FYR -> EXISTING: hand the Outliner back to the artist.

    For every object in the project's scaffold collections:
      * if it is also in a collection of this scene outside the scaffold, it is
        simply unlinked from the scaffold;
      * otherwise it is first linked to the collection that holds the project root
        (normally the scene collection), so no object ever loses its last
        collection or leaves the scene.
    Then scaffold collections left with no objects and no child collections are
    deleted, bottom-up. A scaffold collection the artist put other things into is
    kept. Every scaffold pointer is cleared either way, so Fyr never renames or
    deletes those collections again. No collection that is not one of the
    project's own scaffold pointers is ever unlinked from, renamed or deleted.
    """
    summary = {"unlinked": 0, "relinked": 0, "removed": 0, "kept": []}
    role_collections, group_collections, roots = _project_scaffold_collections(project)
    scaffold = role_collections + group_collections + roots
    if not scaffold:
        _clear_project_collection_pointers(project)
        return summary

    scene = getattr(_project_scene_context(context, project), "scene", None)
    scene_collection = getattr(scene, "collection", None)
    scene_tree = _collection_tree(scene_collection)

    def _is_scaffold(collection) -> bool:
        return any(existing == collection for existing in scaffold)

    fallback = scene_collection
    for root in roots:
        for candidate in scene_tree:
            if not _is_scaffold(candidate) and has_child_collection(candidate, root):
                fallback = candidate
                break

    objects: list = []
    for collection in scaffold:
        for obj in list(getattr(collection, "objects", []) or []):
            if obj is not None and not any(existing == obj for existing in objects):
                objects.append(obj)

    for obj in objects:
        users = [collection for collection in getattr(obj, "users_collection", []) or [] if collection is not None]
        keeps_a_home = any(
            not _is_scaffold(collection) and any(member == collection for member in scene_tree)
            for collection in users
        )
        if not keeps_a_home:
            if fallback is None:
                # No scene collection to fall back to: leave the object exactly where it is
                # rather than risk orphaning it.
                continue
            link_object_to_collection(fallback, obj)
            summary["relinked"] += 1
        for collection in scaffold:
            if collection_has_object(collection, obj):
                unlink_object_from_collection(collection, obj)
                summary["unlinked"] += 1

    # Bottom-up, so a group collection whose role children were just removed can go too.
    # A removed collection's wrapper raises on any access, and it stays in `parents`
    # (it was part of the scaffold), so every later parent scan has to skip it: the
    # first version walked into the freed role collection and aborted the switch
    # halfway, leaving live pointers behind (headless smoke, 2026-09-26).
    parents = scene_tree + scaffold
    removed: set[int] = set()

    def _alive(collection) -> bool:
        try:
            return collection.as_pointer() not in removed
        except ReferenceError:
            return False

    try:
        for collection in role_collections + group_collections + roots:
            if not _alive(collection):
                continue
            if len(getattr(collection, "objects", []) or []) or len(getattr(collection, "children", []) or []):
                summary["kept"].append(str(collection.name))
                continue
            for parent in parents:
                if parent == collection or not _alive(parent):
                    continue
                if has_child_collection(parent, collection):
                    try:
                        parent.children.unlink(collection)
                    except Exception:
                        pass
            pointer = collection.as_pointer()
            remove_collection_from_data(collection)
            removed.add(pointer)
            summary["removed"] += 1
    finally:
        # Even a partial clean-up must not leave pointers that later renames/removals
        # would follow into what are now the artist's collections.
        _clear_project_collection_pointers(project)
    return summary


def rebuild_fyr_collections(context, project) -> dict:
    """EXISTING -> FYR: build the scaffold for every group and link its objects.

    Leaves the project in the state Auto-Build produces: each group's low / high
    slot objects linked into its Low / High collection and its custom cage into its
    Cage collection, in addition to wherever the artist already keeps them.
    """
    summary = {"groups": 0, "linked": 0}
    if not uses_fyr_collections(project):
        return summary
    scaffold_context = _project_scene_context(context, project)
    if ensure_project_collection_scaffold(scaffold_context, project) is None:
        return summary
    for group in getattr(project, "groups", []) or []:
        if ensure_group_collection_scaffold(scaffold_context, project, group) is None:
            continue
        summary["groups"] += 1
        for role in (constants.OBJECT_ROLE_LOW, constants.OBJECT_ROLE_HIGH, constants.OBJECT_ROLE_CAGE):
            collection = group_role_collection(group, role)
            if collection is None:
                continue
            for obj in group_role_targets(group, role):
                if not collection_has_object(collection, obj):
                    link_object_to_collection(collection, obj)
                    summary["linked"] += 1
    return summary


def apply_collection_mode(context, project):
    """Bring the project's Outliner organization in line with ``collection_mode``.

    Runs from the property's update callback. Returns the switch summary, or None
    when the mode already matches what was last applied (nothing to do). Role slots
    are never touched, so no membership cascade runs and no map goes dirty: moving
    an object between collections changes no baked pixel.
    """
    target = constants.COLLECTION_MODE_FYR if uses_fyr_collections(project) else constants.COLLECTION_MODE_EXISTING
    if _applied_collection_mode(project) == target:
        return None
    with properties.suspend_group_membership_updates():
        if target == constants.COLLECTION_MODE_EXISTING:
            summary = release_fyr_collections(context, project)
        else:
            summary = rebuild_fyr_collections(context, project)
    _set_applied_collection_mode(project, target)
    return summary


def group_object_set(group):
    role_state = properties.group_role_assignments_state(group)
    objects = {slot.object_ref for slot in getattr(role_state, "low_meshes", []) if slot.object_ref is not None}
    objects.update(slot.object_ref for slot in getattr(role_state, "high_meshes", []) if slot.object_ref is not None)
    if group.custom_cage is not None:
        objects.add(group.custom_cage)
    return objects


def find_group_for_object(project, obj):
    """Find the bake group that contains the given object."""
    if obj is None or project is None:
        return None
    for i, group in enumerate(getattr(project, "groups", [])):
        if obj in group_object_set(group):
            return i, group
    return None


def group_role_targets(group, role):
    role_state = properties.group_role_assignments_state(group)
    if role == constants.OBJECT_ROLE_CAGE:
        return [group.custom_cage] if group.custom_cage is not None else []
    slots = getattr(role_state, "high_meshes" if role == constants.OBJECT_ROLE_HIGH else "low_meshes", [])
    # Dedupe by object so a drifted slot list never bakes/hides the same mesh twice.
    targets = []
    for slot in slots:
        obj = slot.object_ref
        if obj is None or any(existing == obj for existing in targets):
            continue
        targets.append(obj)
    return targets


# Properties the duplicate deliberately does NOT inherit from its source bake group.
# Everything else travels by RNA reflection, so a property added to
# properties.MasterBakerBakeGroup is copied with no change here.
_GROUP_COPY_DENIED_NAMES = frozenset(
    {
        # Assigned by hand: _group_name_update renames the scaffold collection and
        # rewrites the group's metadata mirror, so it must land exactly once.
        "name",
        "rna_type",
        # Assigning this runs _cage_coverage_scope_update, which fits and rasterizes
        # cage coverage for every group in scope. A duplicate must not kick that off
        # for the whole project the moment it is created; the overlay starts off.
        "show_cage_coverage",
        # Assigned by hand below, from the role-assignments state that owns them.
        # Sweeping them too would fire _group_membership_update and
        # _overlay_static_update a second time per group for no change in value.
        "use_low_as_high",
        "low_mesh_index",
        "high_mesh_index",
    }
)


def _copy_texture_sets(source, target) -> None:
    """Rebuild target.texture_sets from the source, including the UDIM configuration.

    Without the entries themselves the duplicate's groups reference set names with no
    matching entry, leaving the copy in a "needs Migrate Texture Sets" state. Without
    udim_mode / udim_tiles a duplicated UDIM project silently baked tile 1001 only.
    """
    target_sets = getattr(target, "texture_sets", None)
    if target_sets is None or not hasattr(target_sets, "add") or not hasattr(target_sets, "clear"):
        return
    target_sets.clear()
    for source_set in getattr(source, "texture_sets", []) or []:
        target_set = target_sets.add()
        preset_store.apply_payload_to_texture_set(target_set, preset_store.texture_set_to_payload(source_set))
        if not str(getattr(target_set, "name", "") or "").strip():
            target_set.name = constants.DEFAULT_TEXTURE_SET_NAME
    if hasattr(target, "active_texture_set_index"):
        target.active_texture_set_index = max(
            0, min(getattr(source, "active_texture_set_index", 0), max(len(target_sets) - 1, 0))
        )


def _copy_material_binding_suppressions(source, target) -> None:
    """Carry the auto-detected material bindings the artist deleted.

    A suppression is a "do not recreate this" record. Dropping it means the duplicate
    immediately recreates every binding the artist removed from the original.
    """
    target_rows = getattr(target, "material_binding_suppressions", None)
    if target_rows is None or not hasattr(target_rows, "add") or not hasattr(target_rows, "clear"):
        return
    target_rows.clear()
    for source_row in getattr(source, "material_binding_suppressions", []) or []:
        target_rows.add().binding_key = str(getattr(source_row, "binding_key", "") or "")


def _copy_group(source_group, group_item, source_ignore_backface: bool) -> None:
    source_roles = properties.group_role_assignments_state(source_group)
    target_roles = properties.group_role_assignments_state(group_item)
    target_collections = properties.group_collections_state(group_item)

    group_item.name = getattr(properties.group_metadata_state(source_group), "name", "")
    # The cage pointer's update callback forces cage_mode to CUSTOM whenever it is set,
    # so it has to land BEFORE the swept cage_mode -- otherwise a group with a cage
    # object still assigned but Cage Mode back on Distance/Automatic duplicates as
    # Custom (the same ordering apply_payload_to_group documents).
    group_item.custom_cage = getattr(source_group, "custom_cage", None)
    preset_store.copy_serializable_properties(source_group, group_item, denied_names=_GROUP_COPY_DENIED_NAMES)
    # The project-wide flag outranks the per-group copy: the field moved to the
    # project and the group value is a legacy mirror.
    group_item.ignore_backface = source_ignore_backface
    # Paint Offset & Skew are image datablocks, so the property sweep cannot see them.
    # They CHANGE BAKED PIXELS: a duplicate that dropped them baked differently from
    # the project it was duplicated from, with no way for the artist to tell why.
    for attribute in ("paint_offset_image", "paint_skew_image"):
        if hasattr(source_group, attribute):
            setattr(group_item, attribute, getattr(source_group, attribute, None))

    # The duplicate builds its own scaffold (the operator calls
    # ensure_group_collection_scaffold); adopting the source's collections would make
    # both projects drive the same Outliner hierarchy.
    target_collections.group_collection = None
    target_collections.low_collection = None
    target_collections.high_collection = None
    target_collections.cage_collection = None

    sync_role_slot_collections(
        getattr(source_roles, "low_meshes", []),
        [getattr(group_item, "low_meshes", None), getattr(target_roles, "low_meshes", None)],
    )
    sync_role_slot_collections(
        getattr(source_roles, "high_meshes", []),
        [getattr(group_item, "high_meshes", None), getattr(target_roles, "high_meshes", None)],
    )
    group_item.use_low_as_high = bool(getattr(source_roles, "use_low_as_high", False))
    target_roles.use_low_as_high = group_item.use_low_as_high
    group_item.low_mesh_index = getattr(source_roles, "low_mesh_index", getattr(source_group, "low_mesh_index", 0))
    group_item.high_mesh_index = getattr(source_roles, "high_mesh_index", getattr(source_group, "high_mesh_index", 0))
    target_roles.low_mesh_index = group_item.low_mesh_index
    target_roles.high_mesh_index = group_item.high_mesh_index


def copy_project(source, target):
    """Duplicate every user-facing setting of ``source`` onto a fresh ``target``.

    This was a hand-maintained list of roughly fifty assignments and it had silently
    fallen about fifteen fields behind properties.py. Duplicate a MATERIAL-workflow
    project and the copy came back as HIGH_TO_LOW, so every bake group in it failed
    with "no high meshes"; duplicate a UDIM project and the copy baked tile 1001 only;
    the per-group Paint Offset / Paint Skew fields were dropped, which changes the
    baked pixels; and image_format, material_profile, live_reproject, denoise_*, the
    per-map material_channel / material_detail_* / execution_route block and the
    export settings all reverted to defaults.

    The copy now runs through the SAME serializer the project presets use, so a new
    property in properties.py travels with no change here (and
    tests/test_project_structure_copy.py fails if one stops travelling). Unlike a
    preset load this is an in-file duplicate: object pointers are assigned directly
    instead of being resolved by name, map rows get FRESH uuids, and the scaffold
    collection pointers are cleared so the copy builds its own hierarchy.
    """
    source_ignore_backface = bool(
        getattr(
            source,
            "ignore_backface",
            any(bool(getattr(group, "ignore_backface", False)) for group in getattr(source, "groups", [])),
        )
    )
    payload = preset_store.project_to_payload(source)
    # apply_name=False: the copy names itself below. The schema stamp travels inside
    # the payload, so the copy is not re-migrated -- without it a deliberately dialed
    # Cavity Black/White Point (set AFTER the legacy neutralization) would be reset.
    preset_store.apply_payload_to_project_scalars(target, payload, apply_name=False)
    target.name = f"{source.name}_Copy"
    # root_collection is a pointer the sweep skips; the duplicate must build its own.
    target.root_collection = None

    target.maps.clear()
    for source_map in source.maps:
        if getattr(source_map, "is_add_phantom", False):
            continue
        map_item = target.maps.add()
        preset_store.apply_payload_to_map(map_item, preset_store.map_row_to_payload(source_map))
        # A duplicated row is a NEW identity. Sharing the source row's uuid would make
        # the copy's tracked outputs, dirty state and export channel aliases resolve
        # back to rows in the project it was copied from.
        map_item.uuid = ""
        properties.ensure_map_setting_uuid(map_item)

    target.groups.clear()
    for source_group in source.groups:
        _copy_group(source_group, target.groups.add(), source_ignore_backface)

    _copy_texture_sets(source, target)
    _copy_material_binding_suppressions(source, target)
    preset_store.apply_export_settings_payload(
        getattr(target, "export_settings", None), payload.get("export_settings")
    )

    # Clamped, not copied straight: phantom "+" rows are skipped above, so the copy's
    # map stack can be shorter than the source's.
    if hasattr(target, "active_map_index"):
        target.active_map_index = max(0, min(int(payload.get("active_map_index", 0)), max(len(target.maps) - 1, 0)))
    if hasattr(target, "active_group_index"):
        target.active_group_index = max(0, min(int(payload.get("active_group_index", 0)), max(len(target.groups) - 1, 0)))


def ensure_texture_sets_for_legacy_groups(project) -> int:
    """Create the texture_sets entries a project's groups already reference.

    A project whose groups carry a ``texture_set_name`` with no matching entry in
    ``project.texture_sets`` is internally inconsistent. That used to be surfaced to the
    artist as a "Migrate Texture Sets" button whose tooltip named an internal collection
    (RC sweep 2026-08-29, finding 4). Reaching the state is our bug -- preset loads did it
    on brand-new projects -- so callers heal it instead of asking.

    Returns the number of sets created. No-op when the collection is already populated.
    """
    sets = getattr(project, "texture_sets", None)
    if sets is None or not hasattr(sets, "add"):
        return 0
    try:
        if len(sets) > 0:
            return 0
    except TypeError:
        return 0
    names: list[str] = []
    for group in getattr(project, "groups", []) or []:
        name = str(getattr(group, "texture_set_name", "") or "").strip()
        if name and name not in names:
            names.append(name)
    created = 0
    for name in names:
        try:
            item = sets.add()
            item.name = name
            created += 1
        except Exception:
            continue
    return created


def get_or_create_group(project, group_name: str):
    for existing_group in project.groups:
        if existing_group.name == group_name:
            return existing_group

    group = project.groups.add()
    group.name = group_name
    return group


def get_or_create_group_with_flag(project, group_name: str):
    for existing_group in project.groups:
        if existing_group.name == group_name:
            return existing_group, False

    group = project.groups.add()
    group.name = group_name
    return group, True


def group_index(project, target_group) -> int:
    for index, group in enumerate(getattr(project, "groups", [])):
        if group == target_group:
            return index
    return max(0, min(getattr(project, "active_group_index", 0), max(len(getattr(project, "groups", [])) - 1, 0)))


def normalize_group_name(name: str) -> str:
    base_name = matching.normalize_group_name(name)
    base_name = re.sub(r"(?:[._-]?\d+)$", "", base_name)
    return base_name or "BakeGroup"


def primary_collection_for_object(obj):
    collections = [collection for collection in getattr(obj, "users_collection", []) if collection is not None]
    if not collections:
        return None
    return sorted(collections, key=lambda collection: (collection.name.lower(), collection.name))[0]


def role_from_object_and_collection(obj, collection=None):
    for tagged_target in (obj, collection):
        if tagged_target is None:
            continue
        role = tagging.get_tag_role(tagged_target)
        if role is not None:
            return role

    for user_collection in getattr(obj, "users_collection", []):
        if user_collection is None:
            continue
        role = tagging.get_tag_role(user_collection)
        if role is not None:
            return role

    candidates = [getattr(obj, "name", "")]
    if collection is not None:
        candidates.append(getattr(collection, "name", ""))
    for user_collection in getattr(obj, "users_collection", []):
        if user_collection is not None:
            candidates.append(user_collection.name)
    for candidate in candidates:
        role = matching.detect_role(candidate)
        if role is not None:
            return role
    return constants.OBJECT_ROLE_LOW


def ensure_group_slot(group, role, obj):
    if role == constants.OBJECT_ROLE_CAGE:
        group.cage_mode = constants.CAGE_MODE_CUSTOM
        group.custom_cage = obj
        tagging.apply_role_tag(obj, constants.OBJECT_ROLE_CAGE, group_name=group.name, source="grouping")
        return

    if add_unique_role_objects(group, role, [obj]) <= 0:
        return
    tagging.apply_role_tag(obj, role, group_name=group.name, source="grouping")


def remove_collection_from_data(collection) -> None:
    if not collection_exists(collection):
        return
    try:
        bpy.data.collections.remove(collection)
    except Exception:
        pass


def remove_group_collections(group) -> None:
    """Delete the scaffold collections a group created (Low/High/Cage + the group parent).

    Mirrors remove_project_collections: Blender keeps the contained objects alive as long as
    they remain linked in another collection (e.g. the scene), so this removes only the
    plugin-owned scaffold, never the user's meshes. Called on group removal so add->remove
    cycles don't leak empty collections into the Outliner.
    """
    collections_state = properties.group_collections_state(group)
    for attr in ("low_collection", "high_collection", "cage_collection"):
        remove_collection_from_data(getattr(collections_state, attr, None))
    remove_collection_from_data(getattr(collections_state, "group_collection", None))


def remove_project_collections(context, project) -> None:
    scene_collection = getattr(context.scene, "collection", None)
    for group in getattr(project, "groups", []):
        remove_group_collections(group)
    root = getattr(project, "root_collection", None)
    if collection_exists(root) and scene_collection is not None and has_child_collection(scene_collection, root):
        scene_collection.children.unlink(root)
    remove_collection_from_data(root)
