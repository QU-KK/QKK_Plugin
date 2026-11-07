"""Explicit, collision-checked object naming for a bake group's low/high meshes."""

from uuid import uuid4

from . import constants, project_structure, properties


def group_mesh_name_plan(group):
    """Return (object, name) pairs without changing scene data.

    Include assigned slots and meshes inside the group's role collections. Keep
    slot/collection order so re-running after a manual rename retains numbering.
    Mesh datablocks and cages are deliberately outside this operation's scope.
    """
    base = str(group.name or "").strip()
    if not base:
        raise ValueError("Give the bake group a name first")
    collections = properties.group_collections_state(group)
    plan = []
    seen = set()
    for role, attr, suffix in (
        (constants.OBJECT_ROLE_LOW, "low_collection", "low"),
        (constants.OBJECT_ROLE_HIGH, "high_collection", "high"),
    ):
        objects = list(project_structure.group_role_targets(group, role))
        collection = getattr(collections, attr, None)
        if collection is not None:
            objects.extend(collection.all_objects)
        unique = {}
        for obj in objects:
            if obj.type == "MESH":
                unique[obj.as_pointer()] = obj
        if seen.intersection(unique):
            raise ValueError("A mesh belongs to both Low and High; assign it to one role before renaming")
        seen.update(unique)
        for index, obj in enumerate(unique.values(), 1):
            numbered = len(unique) > 1
            name = f"{base}_{suffix}" + (f"_{index:02d}" if numbered else "")
            # Blender's ID name limit is in UTF-8 bytes. Refuse truncation, which
            # would silently lose the role/index or cause a .001 collision.
            if len(name.encode("utf-8")) > 63:
                raise ValueError("Bake group name is too long for mesh role suffixes; shorten it first")
            plan.append((obj, name))
    if not plan:
        raise ValueError("This bake group has no low or high meshes to rename")
    return plan


def rename_group_meshes(group, all_objects):
    """Apply a complete plan, refusing external collisions before any mutation."""
    plan = group_mesh_name_plan(group)
    targets = {obj.as_pointer() for obj, _name in plan}
    for obj, name in plan:
        if not obj.is_editable or obj.is_property_readonly("name"):
            raise ValueError(f"'{obj.name}' cannot be renamed; make it local and editable first")
        existing = all_objects.get(name)
        if existing is not None and existing.as_pointer() not in targets:
            raise ValueError(f"'{name}' already exists outside this group; rename it or choose another group name")
    changes = [(obj, name, obj.name) for obj, name in plan if obj.name != name]
    # Park all objects before assigning final names, allowing swaps without .001.
    token = uuid4().hex
    try:
        for index, (obj, _name, _old) in enumerate(changes):
            obj.name = f"__fyr_rename_{token}_{index}"
        for obj, name, _old in changes:
            obj.name = name
            if obj.name != name:
                raise ValueError(f"Could not assign mesh name '{name}'")
    except Exception:
        for index, (obj, _name, _old) in enumerate(changes):
            obj.name = f"__fyr_restore_{token}_{index}"
        for obj, _name, old in changes:
            obj.name = old
        raise
    return len(changes)
