"""Bake group membership from the Outliner.

A bake group's meshes are its role slots. Fyr's Low / High / Cage collections mirror
those slots, and until this module nothing read them back, so a mesh dragged into
``mod_Low`` left the group showing "No meshes" (customer request 2026-11-08, the
Marmoset / Painter habit of grouping in the Outliner).

Two rules keep this from rewriting projects that were never set up this way:

* **Changes are deltas.** A slot is added or removed only because the collection
  changed while Fyr was watching it. Plenty of existing files have baking groups whose
  meshes the artist later moved to their own collections, and treating the collection
  as the whole truth would empty those groups on open.
* **The first look only fills an empty role.** That covers meshes placed before the
  add-on could see them, and it never adds to a role the artist has already filled.

Only "Fyr Collections" projects take part: in "My Collections" there is no scaffold,
and a material project is one object per group by construction.

The sweep runs on a debounced timer, never inside the depsgraph handler or a panel
draw, and waits while a bake is running.
"""

from __future__ import annotations

import time

from . import constants
from .handler_thread_guard import on_main_thread

try:
    import bpy
except ImportError:  # pragma: no cover - unit tests exercise the bpy-free planner
    bpy = None


_ROLES = (constants.OBJECT_ROLE_LOW, constants.OBJECT_ROLE_HIGH, constants.OBJECT_ROLE_CAGE)
_OPPOSITE_ROLE = {
    constants.OBJECT_ROLE_LOW: constants.OBJECT_ROLE_HIGH,
    constants.OBJECT_ROLE_HIGH: constants.OBJECT_ROLE_LOW,
}

_SYNC_DELAY_SECONDS = 0.2
_BUSY_RETRY_SECONDS = 1.0
# A sweep with nothing to do measured 32 ms on 200 groups under load; only the rare
# excluded collection depends on this path, so it can afford to be slow.
_DRAW_REQUEST_INTERVAL_SECONDS = 3.0

#: (scene, project, group, role, collection) -> mesh names last seen in that collection.
#: Deliberately not reset on undo: the delta against a stale snapshot is the change the
#: undo made to the collection, and the slots it restored already match or get repaired.
_SNAPSHOT: dict[tuple[str, str, str, str, str], frozenset[str]] = {}
_last_draw_request = 0.0

_DEPSGRAPH_HANDLER = None
_LOAD_POST_HANDLER = None


def plan_role_change(
    previous: frozenset[str] | None,
    current: frozenset[str],
    slots: frozenset[str],
    *,
    fill_empty: bool = True,
) -> tuple[list[str], list[str]]:
    """Mesh names to (add to, remove from) a role's slots.

    ``previous`` is None the first time this collection is seen in the session, when
    there is no delta to read: only an empty role may be filled, and nothing is removed.
    """
    if previous is None:
        if fill_empty and not slots:
            return sorted(current), []
        return [], []
    return sorted((current - previous) - slots), sorted((previous - current) & slots)


def request_sync() -> None:
    """Schedule one sweep, coalescing every request made before it runs."""
    if bpy is None:
        return
    if not bpy.app.timers.is_registered(_timer):
        bpy.app.timers.register(_timer, first_interval=_SYNC_DELAY_SECONDS)


def request_sync_from_draw() -> None:
    """Rate-limited request for the panel.

    A collection excluded from the view layer is not in the depsgraph, so moving a mesh
    in or out of one never reaches the handler below. Only schedules: a draw callback
    must not write to the scene.
    """
    global _last_draw_request
    now = time.monotonic()
    if now - _last_draw_request < _DRAW_REQUEST_INTERVAL_SECONDS:
        return
    _last_draw_request = now
    request_sync()


def _busy() -> bool:
    try:
        from . import operators, runtime

        if runtime.active_bake_snapshot() is not None or operators.cycles_async_bake_active():
            return True
        return bool(bpy.app.is_job_running("OBJECT_BAKE"))
    except Exception:  # noqa: BLE001 - unknown means "still busy"
        return True


def _timer():
    if _busy():
        return _BUSY_RETRY_SECONDS
    try:
        sync_now()
    except Exception as exc:  # noqa: BLE001 - a timer callback must never raise
        print(f"[Fyr Baker] Outliner group sync failed: {exc}")
    return None


def _collection_meshes(collection) -> dict:
    """Name -> mesh for ``collection`` and its child collections. Generated cages are Fyr's own."""
    return {
        obj.name: obj
        for obj in collection.all_objects
        if obj.type == "MESH" and not obj.get("_master_baker_generated_cage")
    }


def _slot_names(group, role: str) -> frozenset[str]:
    from . import project_structure

    return frozenset(obj.name for obj in project_structure.group_role_targets(group, role))


def _remove_slots(group, role: str, names: list[str]) -> None:
    from . import project_structure

    collections, index_attr, role_state = project_structure.group_role_slot_collections(group, role)
    if not collections:
        return
    doomed = set(names)
    for collection in collections:
        for index in range(len(collection) - 1, -1, -1):
            obj = getattr(collection[index], "object_ref", None)
            if obj is not None and obj.name in doomed:
                collection.remove(index)
    last_index = max(len(collections[0]) - 1, 0)
    for holder in (role_state, group):
        if hasattr(holder, index_attr) and getattr(holder, index_attr) > last_index:
            setattr(holder, index_attr, last_index)


def _apply_cage_change(group, added: list, removed: list[str]) -> bool:
    changed = False
    cage = group.custom_cage
    if cage is not None and cage.name in removed:
        group.custom_cage = None
        # Custom mode with no cage is a validation error; Distance is the group default.
        group.cage_mode = constants.CAGE_MODE_DISTANCE
        changed = True
    if group.custom_cage is None and added:
        # Assigning custom_cage switches the group to Custom cage mode by itself.
        group.custom_cage = added[0]
        changed = True
    return changed


def _sync_group(project, group, scene_name: str, seen: dict) -> tuple[bool, bool]:
    """Apply the Outliner's changes to one group. Returns (touched, low role was filled)."""
    from . import matching, operators, project_structure, tagging

    project_name = str(project.name)
    plans = []
    for role in _ROLES:
        collection = project_structure.group_role_collection(group, role)
        if not project_structure.collection_exists(collection):
            continue
        meshes = _collection_meshes(collection)
        current = frozenset(meshes)
        key = (scene_name, project_name, str(group.name), role, str(collection.name_full))
        # A cage changes how rays leave the low, so a mesh merely left in the Cage
        # collection of an older file must never switch that group's cage on open.
        adds, removes = plan_role_change(
            _SNAPSHOT.get(key),
            current,
            _slot_names(group, role),
            fill_empty=role != constants.OBJECT_ROLE_CAGE,
        )
        plans.append((role, collection, current, meshes, adds, removes))

    touched = False
    # Removals first, so a mesh dragged from Low to High is not refused below for
    # still holding its old slot.
    for role, _collection, _current, _meshes, _adds, removes in plans:
        if removes and role != constants.OBJECT_ROLE_CAGE:
            _remove_slots(group, role, removes)
            touched = True

    low_was_empty = not _slot_names(group, constants.OBJECT_ROLE_LOW)
    added_objects = []
    for role, _collection, _current, meshes, adds, removes in plans:
        if role == constants.OBJECT_ROLE_CAGE:
            cage_objects = [meshes[name] for name in adds]
            if _apply_cage_change(group, cage_objects, removes):
                touched = True
                if group.custom_cage is not None and cage_objects:
                    tagging.apply_role_tag(group.custom_cage, role, group_name=group.name, source="manual")
            continue
        if not adds:
            continue
        # A mesh cannot be its own bake target.
        opposite = _slot_names(group, _OPPOSITE_ROLE[role])
        objects = [meshes[name] for name in adds if name not in opposite]
        if project_structure.add_unique_role_objects(group, role, objects) > 0:
            touched = True
            added_objects.extend(objects)
            for obj in objects:
                tagging.apply_role_tag(obj, role, group_name=group.name, source="manual")

    if added_objects and str(group.name).startswith("BakeGroup_"):
        # The same placeholder rename Add as Low / Add as High does.
        group.name = operators._unique_group_name(
            project, matching.suggest_group_name(added_objects), skip=group
        )

    # Keyed after the rename, which also renames the scaffold collections.
    for role, collection, current, _meshes, _adds, _removes in plans:
        seen[(scene_name, project_name, str(group.name), role, str(collection.name_full))] = current

    filled = low_was_empty and bool(_slot_names(group, constants.OBJECT_ROLE_LOW))
    return touched, filled


def _sync_project(context, settings, project, scene_name: str, seen: dict) -> int:
    from . import operators, properties

    touched_groups = []
    filled_groups = []
    with properties.suspend_group_membership_updates():
        for group in project.groups:
            touched, filled = _sync_group(project, group, scene_name, seen)
            if touched:
                touched_groups.append(group)
            if filled and not str(group.texture_set_name or "").strip():
                filled_groups.append(group)
    if not touched_groups:
        return 0

    if filled_groups:
        # A group filled here gets its texture set the way Auto-Build gives one. Per
        # Bake Group is the standalone default, so it has nothing to assign.
        ui_state = properties.scene_ui_state(settings)
        mode = str(getattr(ui_state, "auto_texture_set_mode", constants.AUTO_TEXTURE_SET_PER_GROUP))
        if mode != constants.AUTO_TEXTURE_SET_PER_GROUP:
            operators._apply_auto_texture_set_mode(project, filled_groups, mode)
            properties.reconcile_texture_sets(project)

    properties.bulk_group_membership_refresh(context, touched_groups)
    count = len(touched_groups)
    project.last_status_message = f"Updated {count} bake group(s) from the Outliner"
    return count


def sync_now(context=None) -> int:
    """One sweep of the current scene. Returns how many bake groups changed."""
    from . import constants as _constants, project_structure

    context = context if context is not None else bpy.context
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None:
        return 0

    scene_name = str(scene.name)
    seen: dict = {}
    changed = 0
    for project in settings.projects:
        if not project_structure.uses_fyr_collections(project):
            continue
        if str(getattr(project, "workflow", "")) == _constants.WORKFLOW_MATERIAL:
            continue
        try:
            changed += _sync_project(context, settings, project, scene_name, seen)
        except Exception as exc:  # noqa: BLE001 - one bad project must not stop the rest
            print(f"[Fyr Baker] Outliner group sync skipped '{project.name}': {exc}")

    # Rebuilt each sweep, so removed groups and projects leave no stale baseline, and a
    # project switched away from Fyr Collections starts clean if it ever comes back.
    for key in [key for key in _SNAPSHOT if key[0] == scene_name]:
        del _SNAPSHOT[key]
    _SNAPSHOT.update(seen)
    return changed


def _depsgraph_update_post(_scene, depsgraph):
    # Blender also calls this from a bake/render job thread (handler_thread_guard).
    if not on_main_thread():
        return
    try:
        if depsgraph.id_type_updated("COLLECTION"):
            request_sync()
    except Exception:  # noqa: BLE001 - never let a depsgraph handler raise
        return


def _load_post(*_args):
    # A baseline from the previous file would read as every mesh having been moved.
    _SNAPSHOT.clear()
    request_sync()


def register():
    global _DEPSGRAPH_HANDLER, _LOAD_POST_HANDLER
    if bpy is None:  # pragma: no cover
        return
    handlers = bpy.app.handlers
    if _DEPSGRAPH_HANDLER is None:
        _DEPSGRAPH_HANDLER = handlers.persistent(_depsgraph_update_post)
    if _LOAD_POST_HANDLER is None:
        _LOAD_POST_HANDLER = handlers.persistent(_load_post)
    if _DEPSGRAPH_HANDLER not in handlers.depsgraph_update_post:
        handlers.depsgraph_update_post.append(_DEPSGRAPH_HANDLER)
    if _LOAD_POST_HANDLER not in handlers.load_post:
        handlers.load_post.append(_LOAD_POST_HANDLER)
    request_sync()


def unregister():
    global _DEPSGRAPH_HANDLER, _LOAD_POST_HANDLER
    if bpy is None:  # pragma: no cover
        return
    handlers = bpy.app.handlers
    if _DEPSGRAPH_HANDLER is not None and _DEPSGRAPH_HANDLER in handlers.depsgraph_update_post:
        handlers.depsgraph_update_post.remove(_DEPSGRAPH_HANDLER)
    if _LOAD_POST_HANDLER is not None and _LOAD_POST_HANDLER in handlers.load_post:
        handlers.load_post.remove(_LOAD_POST_HANDLER)
    _DEPSGRAPH_HANDLER = None
    _LOAD_POST_HANDLER = None
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)
    _SNAPSHOT.clear()
