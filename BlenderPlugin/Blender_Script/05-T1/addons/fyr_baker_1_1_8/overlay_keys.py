from __future__ import annotations

from . import floater_faces, mesh_read
from . import cage_session, constants, preferences as preferences_module, properties


def overlay_settings_state(settings):
    overlay_settings_state_fn = getattr(properties, "overlay_settings_state", None)
    if callable(overlay_settings_state_fn):
        return overlay_settings_state_fn(settings)
    nested_state = getattr(settings, "overlay_settings", None) if settings is not None else None
    if nested_state is not None:
        return nested_state
    return settings


def group_role_assignments_state(group):
    role_state_fn = getattr(properties, "group_role_assignments_state", None)
    if callable(role_state_fn):
        return role_state_fn(group)
    nested_state = getattr(group, "role_assignments", None) if group is not None else None
    if nested_state is not None:
        return nested_state
    return group


def effective_high_mesh_slots(group):
    resolver = getattr(properties, "effective_high_mesh_slots", None)
    if callable(resolver):
        return resolver(group)
    role_state = group_role_assignments_state(group)
    use_low_as_high = bool(getattr(role_state, "use_low_as_high", getattr(group, "use_low_as_high", False)))
    return getattr(role_state, "low_meshes" if use_low_as_high else "high_meshes", [])


def iter_valid_meshes(slot_collection):
    for slot in slot_collection:
        obj = getattr(slot, "object_ref", None)
        if obj is not None and obj.type == "MESH":
            yield obj


def iter_unique_role_slots(group, attr_name: str):
    seen: set[int] = set()
    if attr_name == "high_meshes":
        for slot in effective_high_mesh_slots(group):
            obj = getattr(slot, "object_ref", None)
            if obj is None:
                continue
            obj_key = int(obj.as_pointer()) if hasattr(obj, "as_pointer") else id(obj)
            if obj_key not in seen:
                seen.add(obj_key)
                yield slot
        return
    for owner in (group, group_role_assignments_state(group)):
        for slot in getattr(owner, attr_name, []) or []:
            obj = getattr(slot, "object_ref", None)
            if obj is None:
                continue
            obj_key = int(obj.as_pointer()) if hasattr(obj, "as_pointer") else id(obj)
            if obj_key in seen:
                continue
            seen.add(obj_key)
            yield slot


def iter_valid_role_slots(group, attr_name: str):
    for slot in iter_unique_role_slots(group, attr_name):
        obj = getattr(slot, "object_ref", None)
        if obj is not None and getattr(obj, "type", None) == "MESH":
            yield slot


def iter_valid_role_meshes(group, attr_name: str):
    for slot in iter_valid_role_slots(group, attr_name):
        yield slot.object_ref


def object_visible_in_viewport(obj, context) -> bool:
    if obj is None:
        return False
    view_layer = getattr(context, "view_layer", None)
    viewport = getattr(context, "space_data", None)
    if hasattr(obj, "visible_get"):
        try:
            return bool(obj.visible_get(view_layer=view_layer, viewport=viewport))
        except TypeError:
            try:
                return bool(obj.visible_get(view_layer=view_layer))
            except TypeError:
                try:
                    return bool(obj.visible_get())
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass
    hidden = False
    try:
        hidden = bool(obj.hide_get())
    except Exception:
        hidden = bool(getattr(obj, "hide_viewport", False))
    return not hidden


def all_low_meshes_visible_in_viewport(group, context) -> bool:
    low_meshes = list(iter_valid_role_meshes(group, "low_meshes"))
    if not low_meshes:
        return False
    return all(object_visible_in_viewport(obj, context) for obj in low_meshes)


#: session_uid -> monotonic revision stamp.
#:
#: The viewport draw callback computes the static overlay key once per 3D region per
#: frame, so every term in that key is on the hot path. The old key hashed 16 rounded
#: matrix floats plus 24 rounded ``bound_box`` floats for every low/high mesh of every
#: tracked group; ``bound_box`` alone can force an unevaluated modifier stack (subdiv,
#: geometry nodes) to evaluate just to answer a cache question. Both are replaced by an
#: integer revision that the depsgraph handler stamps whenever Blender says the ID was
#: re-evaluated (see :func:`bump_depsgraph_id_revisions`).
#:
#: Revisions come from a single monotonic counter rather than a per-ID one, so a stamp
#: is never reused: if the table is ever dropped, a missing entry reads 0, which cannot
#: collide with a stamp already baked into a cached key. A dropped table therefore costs
#: one extra rebuild, never a stale overlay.
_ID_REVISIONS: dict[int, int] = {}
_REVISION_COUNTER = 0

#: Every depsgraph tick writes one entry per updated ID, unfiltered (filtering by the
#: tracked set would risk a missed bump, and a missed bump is a stale overlay). Cap the
#: table so a long session with churning temporary datablocks cannot grow it without
#: bound; clearing is safe in the direction described above.
_ID_REVISION_TABLE_LIMIT = 100_000

#: >0 while high_poly_park swaps high-poly meshes out and back. The swap is lossless, so
#: its depsgraph updates must not stamp (or invalidate) anything: every stamp changes the
#: static key, and the key covers every group's highs, so each swap rebuilt the cage
#: overlay of all 73 groups of the Uzi (3-5 s per rebuild, one per restore slice).
_REVISION_FREEZE = 0

#: object uid -> (key term, object stamp, mesh uid, mesh stamp). A pinned object keeps
#: answering the key term it had before a lossless swap for as long as neither the object
#: nor the mesh now on it is stamped again; the first real edit drops the pin.
_SIGNATURE_PINS: dict[int, tuple] = {}


class freeze_revisions:
    """Ignore depsgraph updates for the overlay revision table (a lossless mesh swap)."""

    def __enter__(self):
        global _REVISION_FREEZE
        _REVISION_FREEZE += 1
        return self

    def __exit__(self, *_exc):
        global _REVISION_FREEZE
        _REVISION_FREEZE = max(0, _REVISION_FREEZE - 1)
        return False


def revisions_frozen() -> bool:
    return _REVISION_FREEZE > 0


def pin_object_signature(obj, signature) -> None:
    """Hold ``obj``'s key term at ``signature`` (taken before a lossless swap)."""
    obj_uid = id_session_uid(obj)
    if obj_uid is None or signature is None:
        return
    data = getattr(obj, "data", None)
    data_uid = id_session_uid(data) if data is not None else None
    _SIGNATURE_PINS[obj_uid] = (
        signature,
        _ID_REVISIONS.get(obj_uid, 0),
        data_uid,
        _ID_REVISIONS.get(data_uid, 0) if data_uid is not None else 0,
    )


def id_session_uid(id_data) -> int | None:
    """Undo-stable identity for an ID, or ``None`` when the host cannot supply one.

    ``session_uid`` survives undo (which reloads the whole main database and moves every
    pointer), so a key built on it does not spuriously rebuild after every ctrl-Z.
    """
    if id_data is None:
        return None
    uid = getattr(id_data, "session_uid", None)
    if uid is None:
        uid = getattr(id_data, "session_uuid", None)
    try:
        uid = int(uid) if uid is not None else 0
    except Exception:
        uid = 0
    if uid:
        return uid
    # ``DepsgraphUpdate.id`` hands back the evaluated copy, whose session_uid is 0.
    # Stamping that would file every update under one shared key and the overlay would
    # never notice a change. Walk back to the original datablock, which carries the
    # real, undo-stable uid. ``original`` on an original returns itself.
    original = getattr(id_data, "original", None)
    if original is None or original is id_data:
        return None
    uid = getattr(original, "session_uid", None)
    if uid is None:
        uid = getattr(original, "session_uuid", None)
    try:
        uid = int(uid) if uid is not None else 0
    except Exception:
        return None
    return uid or None


def bump_id_revision(id_data) -> None:
    global _REVISION_COUNTER
    uid = id_session_uid(id_data)
    if uid is None:
        return
    if len(_ID_REVISIONS) >= _ID_REVISION_TABLE_LIMIT and uid not in _ID_REVISIONS:
        _ID_REVISIONS.clear()
    _REVISION_COUNTER += 1
    _ID_REVISIONS[uid] = _REVISION_COUNTER


def _shading_only_update(update) -> bool:
    """An update Blender flags as shading and nothing else (a material or preview image
    swap) cannot move a captured vertex. Parking and restoring the highs around a bake
    sends one for every low, and stamping those re-captured every group's cage preview
    twice per bake (Uzi, 73 groups: 13.5 s of frozen UI). Unflagged updates still stamp."""
    return (
        getattr(update, "is_updated_shading", None) is True
        and getattr(update, "is_updated_geometry", None) is False
        and getattr(update, "is_updated_transform", None) is False
    )


def bump_depsgraph_id_revisions(depsgraph, skip=None) -> None:
    if _REVISION_FREEZE:
        return
    """Stamp every ID the depsgraph just re-evaluated.

    Deliberately unfiltered: a child object moved by its parent, an object whose
    evaluated mesh changed under a modifier, and the mesh datablock itself all arrive
    here, and any of them can invalidate captured overlay geometry. Skipping an ID
    because it is not currently tracked would leave the overlay showing stale geometry
    the moment it becomes tracked. The exceptions are shading-only updates (see
    _shading_only_update) and *skip*: a paint-brush stroke's layer write, which the live
    brush draws itself and paint_brush.end_session stamps.
    """
    try:
        updates = getattr(depsgraph, "updates", None)
        if updates is None:
            return
        for update in updates:
            if skip is not None and skip(update):
                continue
            if _shading_only_update(update):
                continue
            bump_id_revision(getattr(update, "id", None))
    except Exception:
        # An unreadable update list must not take down the depsgraph handler; the
        # existing invalidation path in overlay_events still clears the static cache.
        pass


def reset_id_revisions() -> None:
    """Drop every stamp (file load / addon unregister)."""
    _ID_REVISIONS.clear()
    _SIGNATURE_PINS.clear()


def id_revision(id_data) -> int:
    uid = id_session_uid(id_data)
    if uid is None:
        return 0
    return _ID_REVISIONS.get(uid, 0)


def object_bounds_signature(obj) -> tuple:
    bound_box = getattr(obj, "bound_box", None)
    if bound_box is None:
        return ()
    corners: list[tuple[float, float, float]] = []
    for corner in bound_box:
        try:
            x_value, y_value, z_value = corner[:3]
        except Exception:
            continue
        corners.append(
            (
                round(float(x_value), 6),
                round(float(y_value), 6),
                round(float(z_value), 6),
            )
        )
    return tuple(corners)


def id_update_signature(id_data) -> tuple[bool, bool]:
    if id_data is None:
        return (False, False)
    return (
        bool(getattr(id_data, "is_updated", False)),
        bool(getattr(id_data, "is_updated_data", False)),
    )


def object_signature(obj):
    data = getattr(obj, "data", None)
    matrix = tuple(round(float(value), 6) for row in obj.matrix_world for value in row)
    topology_signature = ()
    if data is not None:
        topology_signature = (
            mesh_read.element_count(data, "vertices"),
            mesh_read.element_count(data, "edges"),
            mesh_read.element_count(data, "polygons"),
            bool(getattr(data, "is_editmode", False)),
        )
    return (
        obj.as_pointer(),
        data.as_pointer() if data is not None and hasattr(data, "as_pointer") else 0,
        matrix,
        topology_signature,
        object_bounds_signature(obj),
        id_update_signature(obj),
        id_update_signature(data),
    )


def object_cache_signature(obj):
    data = getattr(obj, "data", None)
    matrix = tuple(round(float(value), 6) for row in obj.matrix_world for value in row)
    topology_signature = ()
    if data is not None:
        topology_signature = (
            mesh_read.element_count(data, "vertices"),
            mesh_read.element_count(data, "edges"),
            mesh_read.element_count(data, "polygons"),
            bool(getattr(data, "is_editmode", False)),
        )
    return (
        obj.as_pointer(),
        data.as_pointer() if data is not None and hasattr(data, "as_pointer") else 0,
        matrix,
        topology_signature,
        object_bounds_signature(obj),
    ) + ((floater_faces.signature(obj),) if floater_faces.has_floater_faces(obj) else ())


def _topology_signature(data) -> tuple:
    if data is None:
        return ()
    # len() on an RNA collection is a size read, not an evaluation, so unlike
    # bound_box this never triggers a modifier-stack evaluation. Kept as a cheap
    # backstop for any edit that lands without a depsgraph update reaching us.
    return (
        mesh_read.element_count(data, "vertices"),
        mesh_read.element_count(data, "edges"),
        mesh_read.element_count(data, "polygons"),
        bool(getattr(data, "is_editmode", False)),
    )


def object_revision_signature(obj):
    """Per-frame key term for one tracked object.

    Identity plus a depsgraph revision stamp: no matrix floats, no ``bound_box``. A
    transform edit, a mesh edit and a modifier-stack change all produce a depsgraph
    update for this object (or its data), which bumps the stamp — so the static cache
    still rebuilds exactly when the captured world-space geometry went stale.

    Falls back to the full :func:`object_signature` when the host cannot supply a
    ``session_uid`` (test doubles, hypothetical pre-4.0 hosts), so the key stays correct
    rather than degrading to identity alone.
    """
    obj_uid = id_session_uid(obj)
    if obj_uid is None:
        return object_signature(obj)
    data = getattr(obj, "data", None)
    data_uid = id_session_uid(data) if data is not None else None
    if data is not None and data_uid is None:
        return object_signature(obj)
    pin = _SIGNATURE_PINS.get(obj_uid) if _SIGNATURE_PINS else None
    if pin is not None:
        if (
            pin[1] == _ID_REVISIONS.get(obj_uid, 0)
            and pin[2] == data_uid
            and pin[3] == (_ID_REVISIONS.get(data_uid, 0) if data_uid is not None else 0)
        ):
            return pin[0]
        _SIGNATURE_PINS.pop(obj_uid, None)
    return (
        obj_uid,
        data_uid if data_uid is not None else 0,
        _ID_REVISIONS.get(obj_uid, 0),
        _ID_REVISIONS.get(data_uid, 0) if data_uid is not None else 0,
        _topology_signature(data),
    )


def effective_static_debug_flags(settings):
    overlay_state = overlay_settings_state(settings)
    return {
        "show_error_heatmap": False,
        "show_ray_miss_debug": False,
        "show_low_reference": False,
        "show_high_reference": False,
        "show_skew_debug": bool(getattr(overlay_state, "show_skew_debug", False)),
    }


def low_mesh_slot_collection(group):
    """The raw slot collection that a preview target's ``slot_indices`` index into.

    ``cage_session.valid_low_slot_indices`` enumerates ``role_state.low_meshes`` and
    returns positions in THAT collection, and ``overlay_cache`` indexes the same
    collection when it builds and draws the preview batches. Anything that resolves a
    slot index has to use the same collection: the filtered, deduped
    ``iter_valid_role_slots`` view drops empty and non-mesh slots, so its positions
    stop lining up as soon as one slot is empty.
    """
    role_state = group_role_assignments_state(group)
    return getattr(role_state, "low_meshes", None) or []


def _mesh_object_for_slot_in(slots, slot_index: int):
    if slot_index < 0 or slot_index >= len(slots):
        return None
    obj = getattr(slots[slot_index], "object_ref", None)
    if obj is None or getattr(obj, "type", None) != "MESH":
        return None
    return obj


def _preview_target_low_mesh_signatures(preview_target) -> tuple:
    group = preview_target.group
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    if cage_mode == constants.CAGE_MODE_DISTANCE:
        # One slot walk for the whole target. Resolving each slot index independently
        # re-walked the role collections per index, and every walk pays the read-side
        # role-assignment state sync in properties.py.
        slots = low_mesh_slot_collection(group)
        return tuple(
            object_revision_signature(obj)
            for slot_index in getattr(preview_target, "slot_indices", ())
            for obj in (_mesh_object_for_slot_in(slots, int(slot_index)),)
            if obj is not None
        )
    return tuple(
        object_revision_signature(slot.object_ref)
        for slot in iter_valid_role_slots(group, "low_meshes")
    )


def group_bake_uv_layer_name(group) -> str | None:
    """The group's bake UV Set, or None to mean "the mesh's active layer".

    The cage overlays carry each captured corner's UV into the paint-offset and skew
    shaders, which sample the paint canvas through it, and the bake resolves that UV
    from the group's UV Set (see export._build_cage_meshes). Reading ``uv_layers.active``
    instead previewed the paint map through a different unwrap than the bake would use
    on any group whose UV Set is not the active layer, so the captures pass this name
    and the overlay keys below fold it in — changing the UV Set has to rebuild the
    batches, because the captured UVs move with it.
    """
    try:
        projection_state = properties.group_projection_settings_state(group)
    except Exception:
        projection_state = group
    return (getattr(projection_state, "uv_layer_name", "") or "").strip() or None


def _preview_target_static_signature(preview_target) -> tuple:
    group = preview_target.group
    high_meshes = tuple(object_revision_signature(obj) for obj in iter_valid_role_meshes(group, "high_meshes"))
    custom_cage = None
    if getattr(group, "custom_cage", None) is not None and getattr(group.custom_cage, "type", None) == "MESH":
        custom_cage = object_revision_signature(group.custom_cage)
    return (
        int(getattr(preview_target, "project_index", -1)),
        int(getattr(preview_target, "group_index", -1)),
        str(getattr(group, "cage_mode", "") or ""),
        bool(getattr(group, "average_normals", True)),
        str(group_bake_uv_layer_name(group) or ""),
        tuple(int(slot_index) for slot_index in getattr(preview_target, "slot_indices", ())),
        custom_cage,
        _preview_target_low_mesh_signatures(preview_target),
        high_meshes,
    )


def _preview_target_offset_signature(preview_target) -> tuple:
    group = preview_target.group
    low_slots = low_mesh_slot_collection(group)
    slot_offsets: list[tuple[int, float]] = []
    for slot_index in getattr(preview_target, "slot_indices", ()):
        obj = _mesh_object_for_slot_in(low_slots, int(slot_index))
        if obj is None:
            continue
        slot = low_slots[int(slot_index)]
        try:
            # Hiding or unhiding a low (H / Alt+H) hides or shows its cage, and a group
            # skipped while hidden is fitted once it shows (overlay_cache._group_cage_hidden).
            visible = bool(obj.visible_get())
        except Exception:
            visible = True
        slot_offsets.append((int(slot_index), round(float(getattr(slot, "cage_offset_delta", 0.0)), 4), visible))
    return (
        int(getattr(preview_target, "group_index", -1)),
        tuple(slot_offsets),
    )


def distance_average_normals_preview_slot_key(
    context,
    obj,
    *,
    cage_mode: str,
    smooth_normals: bool,
    uv_layer_name: str | None,
    lines_enabled: bool,
) -> tuple:
    """Key of ONE Distance + Average Normals preview slot (the subdivided cage).

    Exactly what the worker's input depends on -- the slot's evaluated world-space
    corners (``capture_cage_source_triangles`` / ``capture_object_edge_lines``) --
    and nothing else:

    * the object's revision signature (transform, mesh data, modifier stack) and the
      scene it is evaluated in;
    * cage mode and the smooth/average-normals flag the capture uses;
    * the UV layer the capture resolves (conservative: UVs are not subdivided);
    * whether wireframe lines were captured at all, since a slot built without them
      cannot serve a build that draws them.

    Deliberately NOT here: cage offset / per-slot offset deltas (applied in the offset
    shader at draw time), high meshes, colours, and which group or preview slot index
    the object came from -- none of them change a vertex, and each used to force a
    multi-GB re-subdivision through the whole static overlay key.
    """
    scene = getattr(context, "scene", None)
    scene_pointer = 0
    if scene is not None and hasattr(scene, "as_pointer"):
        try:
            scene_pointer = int(scene.as_pointer())
        except Exception:
            scene_pointer = 0
    return (
        "distance_average_normals_preview_v1",
        scene_pointer,
        object_revision_signature(obj),
        str(cage_mode or ""),
        bool(smooth_normals),
        str(uv_layer_name or ""),
        bool(lines_enabled),
    )


def static_overlay_key(context, settings, project, group):
    # Deliberately visibility-free: show/hide toggles (per-group cage eye, skew/ray
    # debug, coverage gate) must never change this key — a changed key rebuilds every
    # cage batch, which is what made those toggles pause. Hidden groups are included
    # in the build and filtered at draw assembly; debug geometry fills in lazily
    # (ensure_static_debug_geometry) the first time a debug toggle turns on.
    overlay_state = overlay_settings_state(settings)
    active_project_index = properties.resolve_active_index(settings.active_project_index, len(settings.projects))
    active_group_index = properties.resolve_active_index(project.active_group_index, len(project.groups))
    low_meshes = tuple(object_revision_signature(obj) for obj in iter_valid_role_meshes(group, "low_meshes"))
    high_meshes = tuple(object_revision_signature(obj) for obj in iter_valid_role_meshes(group, "high_meshes"))
    custom_cage = None
    if group.custom_cage is not None and getattr(group.custom_cage, "type", None) == "MESH":
        custom_cage = object_revision_signature(group.custom_cage)
    preview_targets = cage_session.resolve_preview_targets(
        getattr(context, "scene", None), context=context, include_hidden=True
    )[3]
    preview_target_signature = tuple(_preview_target_static_signature(preview_target) for preview_target in preview_targets)
    return (
        context.scene.as_pointer(),
        active_project_index,
        active_group_index,
        preview_target_signature,
        group.cage_mode,
        bool(getattr(group, "average_normals", True)),
        str(group_bake_uv_layer_name(group) or ""),
        tuple(round(float(component), 4) for component in getattr(overlay_state, "low_reference_color", (0.72, 0.80, 0.88))),
        tuple(round(float(component), 4) for component in getattr(overlay_state, "heatmap_inside_color", (0.12, 0.46, 1.0))),
        custom_cage,
        low_meshes,
        high_meshes,
    )


def display_overlay_key(
    context,
    settings,
    project,
    group,
    static_key,
    *,
    interaction_active: bool,
    skew_paint_version: int,
    paint_session_version: int = 0,
    skew_debug_length_scale: float = constants.VIEWPORT_SKEW_LINE_LENGTH_SCALE,
):
    del project
    overlay_state = overlay_settings_state(settings)
    low_local_offsets = tuple(
        round(float(getattr(slot, "cage_offset_delta", 0.0)), 4)
        for slot in iter_valid_role_slots(group, "low_meshes")
    )
    current_preview_scope = cage_session.preview_scope(settings)
    # Visible (non-hidden) targets only: an eye toggle changes this tuple, which
    # re-assembles the cheap display cache from the intact static batches.
    preview_target_offsets = tuple(
        _preview_target_offset_signature(preview_target)
        for preview_target in cage_session.resolve_preview_targets(getattr(context, "scene", None), context=context)[3]
    )
    return (
        static_key,
        low_local_offsets,
        current_preview_scope,
        preview_target_offsets,
        bool(getattr(overlay_state, "show_skew_debug", False)),
        bool(getattr(overlay_state, "show_ray_miss_debug", False)),
        bool(getattr(overlay_state, "show_error_heatmap", False)),
        round(float(getattr(overlay_state, "cage_opacity", 1.0)), 3),
        bool(getattr(overlay_state, "show_cage_surface", True)),
        bool(getattr(overlay_state, "show_cage_wireframe", True)),
        round(float(getattr(overlay_state, "cage_surface_opacity", 0.42)), 3),
        round(float(getattr(overlay_state, "cage_wireframe_opacity", 0.38)), 3),
        tuple(round(float(component), 4) for component in getattr(overlay_state, "cage_surface_color", (0.18, 0.88, 0.46))),
        tuple(round(float(component), 4) for component in getattr(overlay_state, "cage_wireframe_color", (0.32, 1.0, 0.62))),
        tuple(round(float(component), 4) for component in getattr(overlay_state, "heatmap_inside_color", (0.12, 0.46, 1.0))),
        tuple(round(float(component), 4) for component in getattr(overlay_state, "heatmap_outside_color", (1.0, 0.08, 0.08))),
        interaction_active,
        skew_paint_version,
        # Advances per redraw while a paint session is live on one of this group's
        # canvases, and is a constant 0 otherwise. Painting changes only image
        # pixels -- no depsgraph update, no key term, so nothing marked the display
        # cache dirty and the mask kept drawing the GPU texture captured when the
        # session opened. Strokes then surfaced minutes later, on whatever unrelated
        # invalidation came first, away from where the artist was working.
        paint_session_version,
        bool(getattr(preferences_module.get_preferences(), "cage_lit_shading", False)),
    )
