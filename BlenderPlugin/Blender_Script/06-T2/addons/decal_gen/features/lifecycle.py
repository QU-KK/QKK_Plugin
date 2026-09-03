# SPDX-License-Identifier: GPL-2.0-or-later
"""Live scene synchronization, source-bevel handlers, class registry, keymaps, register, and unregister.

Loaded into the add-on package shared namespace by __init__.py.
"""



def scene_live_sync_cache_key(source_obj, decal_obj=None):
    if source_obj is None:
        return ""
    if decal_obj is not None:
        return f"{source_obj.name_full}\0{decal_obj.name_full}"
    return source_obj.name_full


SCENE_LIVE_EDIT_PROPERTIES = (
    "face_width",
    "randomize_face_width",
    "minimum_face_width",
    "maximum_face_width",
    "surface_offset",
    "uv_scale",
    "seed",
    "decal_amount",
    "maximum_decal_length",
    "use_edge_split",
    "split_angle",
    "taper_sliced_ends",
    "slice_taper_length",
    "auto_trim_corner_ends",
    "corner_end_trim_multiplier",
    "crevice_removal",
    "crevice_detection_mode",
    "crevice_ao_distance",
    "crevice_ao_samples",
    "remove_short_edges",
    "minimum_edge_length",
    "randomize_horizontal_offset",
    "horizontal_randomize_amount",
    "auto_face_width",
    "auto_width_samples",
    "auto_width_clearance",
    "clamp_edge_overlaps",
    "overlap_clearance",
    "normal_mode",
    "normal_keep_sharp",
    "normal_weight",
    "normal_threshold",
    "use_face_loop_slide",
    "add_weld_modifier",
    "weld_distance",
    "add_center_displace_modifier",
    "center_displace_strength",
    "add_shrinkwrap_modifier",
    "add_subdivision_modifier",
    "add_decimate_modifier",
    "add_bevel_modifier",
    "bevel_edge_center",
    "center_bevel_width",
    "center_bevel_segments",
    "center_bevel_profile",
    "bevel_harden_normals",
    "bevel_angle",
    "match_source_material",
)


def _stable_scene_setting_value(value):
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, (int, bool, str)):
        return value
    if value is None:
        return None
    return getattr(value, "name_full", getattr(value, "name", str(value)))


def scene_live_edit_signature(settings):
    return tuple(
        _stable_scene_setting_value(getattr(settings, name, None))
        for name in SCENE_LIVE_EDIT_PROPERTIES
    ) + (
        _stable_scene_setting_value(getattr(settings, "decal_material", None)),
        bool(getattr(settings, "use_material", True)),
    )


EDGEDECAL_LAST_SCENE_SYNC_TARGET = ""


def copy_scene_live_settings_to_decal(scene_settings, decal_obj):
    global EDGEDECAL_SETTINGS_SYNCING
    data = decal_obj.edge_decal_object_settings
    previous_initialized = data.initialized
    previous_live_update = data.live_update
    EDGEDECAL_SETTINGS_SYNCING = True
    try:
        data.initialized = False
        data.live_update = False
        source_obj = getattr(data, "source_object", None)
        selection_mode = (
            data.selection_mode
            or str(decal_obj.get("edge_decal_selection_mode", "SELECTED_EDGES"))
        )

        for property_name in SCENE_LIVE_EDIT_PROPERTIES:
            if hasattr(scene_settings, property_name) and hasattr(data, property_name):
                setattr(data, property_name, getattr(scene_settings, property_name))

        if hasattr(data, "decal_template_material"):
            data.decal_template_material = (
                root_decal_template_material(scene_settings.decal_material)
                if getattr(scene_settings, "use_material", True)
                else None
            )
    finally:
        data.initialized = previous_initialized or True
        data.live_update = previous_live_update or True
        EDGEDECAL_SETTINGS_SYNCING = False


def edge_decal_scene_live_sync_timer():
    global EDGEDECAL_SCENE_LIVE_SYNC_RUNNING
    global EDGEDECAL_LAST_SCENE_SYNC_TARGET

    try:
        context = bpy.context
        scene = getattr(context, "scene", None)
        source_obj = resolve_live_update_source(context)

        if scene is None or source_obj is None:
            EDGEDECAL_LAST_SCENE_SYNC_TARGET = ""
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

        scene_settings = getattr(scene, "edge_decal_settings", None)
        if scene_settings is None:
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

        # While interactive mode is running, keep sidebar edits on the active
        # layer but defer live regeneration until the tool exits.
        if EDGEDECAL_INTERACTIVE_RUNNING:
            if EDGEDECAL_SCENE_SETTINGS_COPYING:
                return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

            decal_obj = active_decal_layer_for_source(source_obj, context=context)
            if decal_obj is not None:
                target_key = scene_live_sync_cache_key(source_obj, decal_obj)
                if EDGEDECAL_LAST_SCENE_SYNC_TARGET != target_key:
                    sync_fn = globals().get("sync_scene_settings_from_decal_layer")
                    if sync_fn is not None:
                        sync_fn(context, source_obj, decal_obj)
                    EDGEDECAL_LAST_SCENE_SYNC_TARGET = target_key
                    return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL
                signature = scene_live_edit_signature(scene_settings)
                cache_key = target_key
                previous_signature = EDGEDECAL_SCENE_LIVE_SYNC_CACHE.get(cache_key)
                if previous_signature != signature:
                    apply_fn = globals().get("apply_scene_settings_to_active_layer")
                    if apply_fn is not None:
                        apply_fn(context, scene_settings)
                    else:
                        copy_scene_live_settings_to_decal(
                            scene_settings,
                            decal_obj,
                        )
                        EDGEDECAL_SCENE_LIVE_SYNC_CACHE[cache_key] = signature
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

        if regenerating_active() or EDGEDECAL_SETTINGS_SYNCING:
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

        if EDGEDECAL_SCENE_SETTINGS_COPYING:
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

        decal_obj = active_decal_layer_for_source(source_obj, context=context)
        if (
            decal_obj is None
            or decal_obj.get("edge_decal_locked", False)
            or decal_obj.data is None
            or len(decal_obj.data.polygons) == 0
            or not getattr(
                decal_obj.edge_decal_object_settings,
                "initialized",
                False,
            )
            or not getattr(
                decal_obj.edge_decal_object_settings,
                "live_update",
                False,
            )
            or not decal_has_regeneratable_source_data(decal_obj)
        ):
            if decal_obj is None:
                EDGEDECAL_LAST_SCENE_SYNC_TARGET = ""
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

        target_key = scene_live_sync_cache_key(source_obj, decal_obj)
        if EDGEDECAL_LAST_SCENE_SYNC_TARGET != target_key:
            sync_fn = globals().get("sync_scene_settings_from_decal_layer")
            if sync_fn is not None:
                sync_fn(context, source_obj, decal_obj)
            EDGEDECAL_LAST_SCENE_SYNC_TARGET = target_key
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

        signature = scene_live_edit_signature(scene_settings)
        cache_key = target_key
        previous_signature = EDGEDECAL_SCENE_LIVE_SYNC_CACHE.get(cache_key)
        if previous_signature is None:
            EDGEDECAL_SCENE_LIVE_SYNC_CACHE[cache_key] = signature
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL
        if previous_signature == signature:
            return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

        EDGEDECAL_SCENE_LIVE_SYNC_CACHE[cache_key] = signature
        copy_scene_live_settings_to_decal(scene_settings, decal_obj)
        queue_decal_live_update(
            decal_obj,
            fast_geometry_only=bool(
                getattr(scene_settings, "fast_geometry_only", False)
            ),
        )
    except (ReferenceError, RuntimeError, AttributeError):
        pass

    return EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL

def _source_bevel_signature(source_obj):
    values = source_bevel_settings(source_obj)
    if values is None:
        return None
    return (
        round(values["width"], 8),
        values["segments"],
        round(values["profile"], 6),
        round(values["angle_limit"], 8),
        values["limit_method"],
        values["affect"],
        values["offset_type"],
        values["harden_normals"],
        values["loop_slide"],
        values["use_clamp_overlap"],
        values["miter_outer"],
        values["miter_inner"],
    )


def decal_uses_face_generation(decal_obj):
    """Return whether a decal layer was generated from selected faces."""
    data = getattr(decal_obj, "edge_decal_object_settings", None)
    return bool(
        decal_obj is not None
        and (
            decal_obj.get("edge_decal_mode") == "FACE_SURFACES"
            or str(
                getattr(data, "selection_mode", "")
                if data is not None
                else ""
            ) == "SELECTED_FACES"
        )
    )


def disable_face_generated_decal_bevel(decal_obj):
    """Keep face-generated layers free of the controlled Bevel modifier."""
    global EDGEDECAL_SETTINGS_SYNCING
    data = getattr(decal_obj, "edge_decal_object_settings", None)
    if data is not None:
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            data.add_bevel_modifier = False
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing
    modifier = generated_decal_bevel_modifier(decal_obj)
    if modifier is not None:
        decal_obj.modifiers.remove(modifier)


def sync_generated_decal_bevels(source_obj, scene_settings=None):
    values = source_bevel_settings(source_obj)

    if values is None:
        for decal_obj in iter_generated_decals(source_obj=source_obj):
            if decal_uses_face_generation(decal_obj):
                disable_face_generated_decal_bevel(decal_obj)
                continue
            if (
                scene_settings is not None
                and scene_settings.add_bevel_modifier
            ):
                ensure_decal_bevel_modifier(
                    decal_obj,
                    source_obj,
                    scene_settings,
                )
                order_decal_finish_modifiers(decal_obj)
                continue

            modifier = generated_decal_bevel_modifier(decal_obj)
            if modifier is not None:
                decal_obj.modifiers.remove(modifier)
        return

    if scene_settings is not None:
        global EDGEDECAL_SETTINGS_SYNCING
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            scene_settings.add_bevel_modifier = True
            scene_settings.center_bevel_width = values["width"]
            scene_settings.center_bevel_segments = values["segments"]
            scene_settings.center_bevel_profile = values["profile"]
            scene_settings.bevel_angle = values["angle_limit"]
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing

    for decal_obj in iter_generated_decals(source_obj=source_obj):
        if decal_uses_face_generation(decal_obj):
            disable_face_generated_decal_bevel(decal_obj)
            continue
        layer_settings = getattr(
            decal_obj,
            "edge_decal_object_settings",
            None,
        )
        if layer_settings is not None:
            previous_syncing = EDGEDECAL_SETTINGS_SYNCING
            EDGEDECAL_SETTINGS_SYNCING = True
            try:
                layer_settings.add_bevel_modifier = True
                layer_settings.center_bevel_width = values["width"]
                layer_settings.center_bevel_segments = values["segments"]
                layer_settings.center_bevel_profile = values["profile"]
                layer_settings.bevel_angle = values["angle_limit"]
            finally:
                EDGEDECAL_SETTINGS_SYNCING = previous_syncing
        if (
            scene_settings is None
            or scene_settings.add_bevel_modifier
        ):
            if layer_settings is not None:
                ensure_decal_bevel_modifier(
                    decal_obj,
                    source_obj,
                    layer_settings,
                )
            elif scene_settings is not None:
                ensure_decal_bevel_modifier(
                    decal_obj,
                    source_obj,
                    scene_settings,
                )
            else:
                ensure_decal_match_source_bevel(decal_obj, source_obj)
            order_decal_finish_modifiers(decal_obj)
            continue

        modifier = generated_decal_bevel_modifier(decal_obj)
        if modifier is not None:
            decal_obj.modifiers.remove(modifier)


@persistent
def edge_decal_sync_source_bevel_handler(_scene, depsgraph):
    global EDGEDECAL_BEVEL_SYNC_RUNNING
    if EDGEDECAL_BEVEL_SYNC_RUNNING:
        return
    EDGEDECAL_BEVEL_SYNC_RUNNING = True
    try:
        scene_settings = getattr(bpy.context.scene, "edge_decal_settings", None)
        for update in depsgraph.updates:
            source_obj = getattr(update, "id", None)
            # Modifier updates can report the evaluated object. The decal
            # registry is keyed by the original source object's pointer, so
            # using the evaluated pointer makes the lookup return no layers
            # even though the source-Bevel signature itself is current.
            source_obj = getattr(source_obj, "original", source_obj)
            if not isinstance(source_obj, bpy.types.Object):
                continue
            if source_obj.type != "MESH" or source_obj.get("edge_decal_generated"):
                continue
            signature = _source_bevel_signature(source_obj)
            cache_key = source_obj.name_full
            if EDGEDECAL_BEVEL_SYNC_CACHE.get(cache_key) == signature:
                continue
            EDGEDECAL_BEVEL_SYNC_CACHE[cache_key] = signature
            sync_generated_decal_bevels(source_obj, scene_settings)
    finally:
        EDGEDECAL_BEVEL_SYNC_RUNNING = False


@persistent
def edge_decal_invalidate_prepared_source_cache_handler(_scene, depsgraph):
    """Discard prepared topology whenever an original source mesh changes."""
    if regenerating_active():
        return

    invalidated_meshes = set()
    for update in depsgraph.updates:
        if not getattr(update, "is_updated_geometry", False):
            continue

        updated_id = getattr(update, "id", None)
        updated_id = getattr(updated_id, "original", updated_id)
        mesh = None
        if isinstance(updated_id, bpy.types.Mesh):
            mesh = updated_id
        elif (
            isinstance(updated_id, bpy.types.Object)
            and updated_id.type == "MESH"
            and not updated_id.get("edge_decal_generated")
        ):
            mesh = updated_id.data

        if mesh is None:
            continue
        mesh_pointer = int(mesh.as_pointer())
        if mesh_pointer in invalidated_meshes:
            continue
        invalidated_meshes.add(mesh_pointer)
        invalidate_prepared_source_cache_if_changed(mesh)


@persistent
def edge_decal_clear_prepared_source_cache_handler(*_args):
    """BMesh snapshots cannot survive loading a different file state."""
    clear_prepared_source_cache(reset_stats=True)


EDGEDECAL_BEVEL_SYNC_RUNNING = False
EDGEDECAL_DECAL_REGISTRY_PREVIOUS = {}
EDGEDECAL_DECALS_BY_SOURCE = {}
EDGEDECAL_SOURCE_POINTER_BY_DECAL_POINTER = {}
EDGEDECAL_OBJECT_COUNT_SIGNATURES = {}
EDGEDECAL_DECAL_REGISTRY_READY = False
EDGEDECAL_LAYER_REPAIR_HANDLER_RUNNING = False


def _decal_registry_candidate(obj):
    """Cheap validation for objects already obtained from Blender data."""
    if obj is None:
        return False
    try:
        return bool(
            obj.type == "MESH"
            and obj.get("edge_decal_generated")
            and not obj.get("edge_decal_interactive_backup", False)
            and getattr(obj, "users_collection", ())
        )
    except ReferenceError:
        return False


def _decal_registry_source(decal_obj, object_by_name=None):
    parent = getattr(decal_obj, "parent", None)
    if (
        parent is not None
        and getattr(parent, "type", None) == "MESH"
        and not parent.get("edge_decal_generated")
    ):
        return parent

    data = getattr(decal_obj, "edge_decal_object_settings", None)
    source_obj = getattr(data, "source_object", None) if data is not None else None
    if (
        source_obj is not None
        and getattr(source_obj, "type", None) == "MESH"
        and not source_obj.get("edge_decal_generated")
    ):
        return source_obj

    stored_name = str(decal_obj.get("edge_decal_source", ""))
    if object_by_name is not None:
        return object_by_name.get(stored_name)
    return find_object_by_name_or_full(stored_name)


def clear_decal_registry():
    global EDGEDECAL_DECAL_REGISTRY_READY
    EDGEDECAL_DECAL_REGISTRY_PREVIOUS.clear()
    EDGEDECAL_DECALS_BY_SOURCE.clear()
    EDGEDECAL_SOURCE_POINTER_BY_DECAL_POINTER.clear()
    EDGEDECAL_OBJECT_COUNT_SIGNATURES.clear()
    EDGEDECAL_DECAL_REGISTRY_READY = False


def register_decal_in_registry(decal_obj, source_obj=None):
    """Register one known decal without searching the rest of the scene."""
    if not _decal_registry_candidate(decal_obj):
        return False
    if source_obj is None:
        source_obj = _decal_registry_source(decal_obj)
    if (
        source_obj is None
        or getattr(source_obj, "type", None) != "MESH"
        or source_obj.get("edge_decal_generated")
    ):
        return False

    try:
        decal_pointer = int(decal_obj.as_pointer())
        source_pointer = int(source_obj.as_pointer())
        decal_name = decal_obj.name_full
        source_name = source_obj.name_full
    except ReferenceError:
        return False

    old_source_pointer = EDGEDECAL_SOURCE_POINTER_BY_DECAL_POINTER.get(
        decal_pointer
    )
    if old_source_pointer is not None:
        old_bucket = EDGEDECAL_DECALS_BY_SOURCE.get(old_source_pointer)
        if old_bucket is not None:
            for old_name, old_obj in tuple(old_bucket["decals"].items()):
                if old_obj == decal_obj or old_name == decal_name:
                    old_bucket["decals"].pop(old_name, None)
                    EDGEDECAL_DECAL_REGISTRY_PREVIOUS.pop(old_name, None)
            if not old_bucket["decals"]:
                EDGEDECAL_DECALS_BY_SOURCE.pop(old_source_pointer, None)

    bucket = EDGEDECAL_DECALS_BY_SOURCE.setdefault(
        source_pointer,
        {"source": source_obj, "decals": {}},
    )
    bucket["source"] = source_obj
    bucket["decals"][decal_name] = decal_obj
    EDGEDECAL_SOURCE_POINTER_BY_DECAL_POINTER[decal_pointer] = source_pointer
    EDGEDECAL_DECAL_REGISTRY_PREVIOUS[decal_name] = source_name
    return True


def registered_decal_layers_for_source(source_obj):
    """Return cached layers, or None while the one-time registry is unavailable."""
    if not EDGEDECAL_DECAL_REGISTRY_READY:
        return None
    if source_obj is None:
        layers = []
        for bucket in EDGEDECAL_DECALS_BY_SOURCE.values():
            layers.extend(
                decal_obj
                for decal_obj in bucket["decals"].values()
                if _decal_registry_candidate(decal_obj)
            )
        return layers

    try:
        bucket = EDGEDECAL_DECALS_BY_SOURCE.get(int(source_obj.as_pointer()))
    except ReferenceError:
        return []
    if bucket is None:
        return []
    return [
        decal_obj
        for decal_obj in bucket["decals"].values()
        if decal_layer_is_valid(
            decal_obj,
            source_obj,
            assume_in_object_data=True,
        )
    ]


def registered_decal_sources():
    if not EDGEDECAL_DECAL_REGISTRY_READY:
        return []
    sources = []
    for bucket in EDGEDECAL_DECALS_BY_SOURCE.values():
        source_obj = bucket["source"]
        try:
            if (
                source_obj.type == "MESH"
                and not source_obj.get("edge_decal_generated")
                and bucket["decals"]
            ):
                sources.append(source_obj)
        except ReferenceError:
            continue
    return sources


def _scan_decal_registry_entries():
    if not hasattr(bpy.data, "objects"):
        return []
    objects = list(bpy.data.objects)
    object_by_name = {}
    for obj in objects:
        object_by_name[obj.name] = obj
        object_by_name[obj.name_full] = obj

    entries = []
    for decal_obj in objects:
        if not _decal_registry_candidate(decal_obj):
            continue
        source_obj = _decal_registry_source(decal_obj, object_by_name)
        if source_obj is not None:
            entries.append((decal_obj, source_obj))
    return entries


def _collect_decal_registry():
    """Map each generated decal object to its source mesh name."""
    return {
        decal_obj.name_full: source_obj.name_full
        for decal_obj, source_obj in _scan_decal_registry_entries()
    }


def rebuild_decal_registry():
    """Perform the rare full scan used after register, load, undo, or redo."""
    global EDGEDECAL_DECAL_REGISTRY_READY
    clear_decal_registry()
    for decal_obj, source_obj in _scan_decal_registry_entries():
        register_decal_in_registry(decal_obj, source_obj)
    data_object_count = len(bpy.data.objects)
    for scene in bpy.data.scenes:
        EDGEDECAL_OBJECT_COUNT_SIGNATURES[int(scene.as_pointer())] = (
            data_object_count,
            len(scene.objects),
        )
    EDGEDECAL_DECAL_REGISTRY_READY = True
    return dict(EDGEDECAL_DECAL_REGISTRY_PREVIOUS)


def _scene_object_count_changed(scene):
    """Detect link/unlink/delete events without walking known decals each update."""
    if scene is None:
        return False
    scene_pointer = int(scene.as_pointer())
    signature = (len(bpy.data.objects), len(scene.objects))
    previous = EDGEDECAL_OBJECT_COUNT_SIGNATURES.get(scene_pointer)
    EDGEDECAL_OBJECT_COUNT_SIGNATURES[scene_pointer] = signature
    return previous is not None and previous != signature


def _prune_decal_registry():
    """Remove deleted/unlinked known decals without inspecting ordinary objects."""
    removed = []
    for source_pointer, bucket in tuple(EDGEDECAL_DECALS_BY_SOURCE.items()):
        source_obj = bucket["source"]
        source_name = ""
        try:
            source_name = source_obj.name_full
        except ReferenceError:
            pass

        for decal_name, decal_obj in tuple(bucket["decals"].items()):
            if _decal_registry_candidate(decal_obj):
                continue
            removed.append((decal_name, source_obj, source_name))
            bucket["decals"].pop(decal_name, None)
            EDGEDECAL_DECAL_REGISTRY_PREVIOUS.pop(decal_name, None)
            try:
                EDGEDECAL_SOURCE_POINTER_BY_DECAL_POINTER.pop(
                    int(decal_obj.as_pointer()),
                    None,
                )
            except ReferenceError:
                pass

        if not bucket["decals"]:
            EDGEDECAL_DECALS_BY_SOURCE.pop(source_pointer, None)
    return removed


def _schedule_repair_for_source(source_obj):
    """Repair one source mesh on the next timer tick after a viewport delete."""
    schedule_decal_layer_repair(source_obj)


@persistent
def edge_decal_repair_layers_handler(_scene, depsgraph):
    global EDGEDECAL_DECAL_REGISTRY_PREVIOUS
    global EDGEDECAL_LAYER_REPAIR_HANDLER_RUNNING

    if (
        EDGEDECAL_LAYER_REPAIR_HANDLER_RUNNING
        or not hasattr(bpy.data, "objects")
    ):
        return
    EDGEDECAL_LAYER_REPAIR_HANDLER_RUNNING = True
    try:
        previous = dict(EDGEDECAL_DECAL_REGISTRY_PREVIOUS or {})
        affected_sources = {}
        if not EDGEDECAL_DECAL_REGISTRY_READY:
            rebuild_decal_registry()
            current_names = set(EDGEDECAL_DECAL_REGISTRY_PREVIOUS)
            for decal_name in set(previous) - current_names:
                source_obj = source_mesh_for_removed_decal(
                    decal_name,
                    previous.get(decal_name, ""),
                )
                if source_obj is not None:
                    try:
                        affected_sources[int(source_obj.as_pointer())] = source_obj
                    except ReferenceError:
                        pass

        if _scene_object_count_changed(_scene):
            for _decal_name, source_obj, source_name in _prune_decal_registry():
                if source_obj is None and source_name:
                    source_obj = find_object_by_name_or_full(source_name)
                if source_obj is not None:
                    try:
                        affected_sources[int(source_obj.as_pointer())] = source_obj
                    except ReferenceError:
                        pass

        for update in getattr(depsgraph, "updates", ()):
            updated_obj = getattr(update, "id", None)
            updated_obj = getattr(updated_obj, "original", updated_obj)
            if not isinstance(updated_obj, bpy.types.Object):
                continue
            try:
                updated_pointer = int(updated_obj.as_pointer())
            except ReferenceError:
                continue
            if (
                updated_pointer in EDGEDECAL_SOURCE_POINTER_BY_DECAL_POINTER
                and not _decal_registry_candidate(updated_obj)
            ):
                for _name, source_obj, _source_name in _prune_decal_registry():
                    if source_obj is not None:
                        try:
                            affected_sources[int(source_obj.as_pointer())] = source_obj
                        except ReferenceError:
                            pass
                continue
            if updated_obj.get("edge_decal_generated"):
                repaired = repair_duplicated_decal_source_ownership(updated_obj)
                source_obj = _decal_registry_source(updated_obj)
                if source_obj is not None:
                    register_decal_in_registry(updated_obj, source_obj)
                    affected_sources[int(source_obj.as_pointer())] = source_obj
                if repaired is not None:
                    old_source, new_source = repaired
                    for source_obj in (old_source, new_source):
                        if source_obj is not None:
                            try:
                                affected_sources[int(source_obj.as_pointer())] = source_obj
                            except ReferenceError:
                                pass
                continue

            if (
                updated_obj.type == "MESH"
                and not updated_obj.get("edge_decal_generated")
                and registered_decal_layers_for_source(updated_obj)
            ):
                affected_sources[int(updated_obj.as_pointer())] = updated_obj

        for source_obj in affected_sources.values():
            if source_mesh_needs_layer_repair(source_obj):
                repair_decal_layers_for_source(source_obj, activate=False)
    finally:
        EDGEDECAL_LAYER_REPAIR_HANDLER_RUNNING = False


classes = (
    EDGEDECAL_AP_preferences,
    EDGEDECAL_PG_settings,
    EDGEDECAL_PG_object_settings,
    EDGEDECAL_PG_preset_ui,
    EDGEDECAL_OT_preset_save,
    EDGEDECAL_OT_preset_apply,
    EDGEDECAL_OT_preset_delete,
    EDGEDECAL_OT_regenerate,
    EDGEDECAL_OT_update_material,
    EDGEDECAL_OT_apply_uvs,
    EDGEDECAL_PG_uv_slice_pin,
    EDGEDECAL_PG_uv_pin,
    EDGEDECAL_OT_generate,
    EDGEDECAL_OT_generate_selected_faces,
    EDGEDECAL_OT_generate_contextual,
    EDGEDECAL_OT_generate_automatic,
    EDGEDECAL_OT_generate_intersections,
    EDGEDECAL_OT_generate_boolean,
    EDGEDECAL_OT_uv_pin_toggle_edit_mode,
    EDGEDECAL_OT_uv_slice_pin_set_shortcut,
    EDGEDECAL_OT_uv_pin_add_shortcut,
    EDGEDECAL_OT_uv_pin_remove_shortcut,
    EDGEDECAL_OT_uv_pin_move_shortcut,
    EDGEDECAL_OT_uv_pin_tool,
    EDGEDECAL_OT_uv_pin_add,
    EDGEDECAL_OT_uv_pin_delete,
    EDGEDECAL_OT_uv_pin_remove_index,
    EDGEDECAL_OT_uv_pin_clear,
    EDGEDECAL_OT_uv_pin_create_equal,
    EDGEDECAL_OT_layer_toggle_uv_pin,
    EDGEDECAL_OT_uv_slice_pin_add,
    EDGEDECAL_OT_uv_slice_pin_remove,
    EDGEDECAL_UL_uv_pins,
    EDGEDECAL_OT_apply_uv_pins,
    EDGEDECAL_OT_remove_decal_sections,
    EDGEDECAL_OT_interactive_generate,
    EDGEDECAL_OT_texture_mask_add,
    EDGEDECAL_OT_texture_mask_remove,
    EDGEDECAL_OT_texture_mask_reset,
    EDGEDECAL_OT_texture_mask_paint,
    EDGEDECAL_PG_unreal_export_settings,
    EDGEDECAL_OT_send_to_unreal,
    EDGEDECAL_OT_export_combined_mesh,
    EDGEDECAL_OT_export_unreal_bundle,
    EDGEDECAL_PG_layer_item,
    EDGEDECAL_UL_layers,
    EDGEDECAL_OT_layer_select,
    EDGEDECAL_OT_layer_add,
    EDGEDECAL_OT_layer_delete,
    EDGEDECAL_OT_layer_delete_active,
    EDGEDECAL_OT_layer_move,
    EDGEDECAL_OT_layer_apply_mask,
    EDGEDECAL_OT_layer_clear_mask,
    EDGEDECAL_OT_layer_toggle_lock,
    EDGEDECAL_OT_layer_toggle_visibility,
    EDGEDECAL_PT_panel,
    EDGEDECAL_PT_uv_pins,
)


def _sync_source_layer_ui_after_register():
    """Rebuild the registry and refresh only sources that own decals."""
    if not hasattr(bpy.data, "objects"):
        return None

    rebuild_decal_registry()
    for source_obj in registered_decal_sources():
        if layer_ui_props_available(source_obj):
            sync_source_layer_ui(source_obj)

    return None


@persistent
def edge_decal_rebuild_registry_handler(*_args):
    """Schedule one full registry rebuild after file-state replacement."""
    clear_decal_registry()
    if not bpy.app.timers.is_registered(_sync_source_layer_ui_after_register):
        bpy.app.timers.register(
            _sync_source_layer_ui_after_register,
            first_interval=0.0,
        )


def register():
    invalidate_edge_decal_bundled_asset_cache()
    invalidate_edge_decal_preset_cache()

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.edge_decal_settings = PointerProperty(
        type=EDGEDECAL_PG_settings
    )
    bpy.types.Scene.edge_decal_preset_ui = PointerProperty(
        type=EDGEDECAL_PG_preset_ui
    )
    bpy.types.Scene.edge_decal_unreal_export = PointerProperty(
        type=EDGEDECAL_PG_unreal_export_settings
    )
    bpy.types.Object.edge_decal_object_settings = PointerProperty(
        type=EDGEDECAL_PG_object_settings
    )
    bpy.types.Object.edge_decal_layers_ui = CollectionProperty(
        type=EDGEDECAL_PG_layer_item,
    )
    bpy.types.Object.edge_decal_layer_index = IntProperty(
        name="Active Decal Layer",
        description="Selected row in the Decal Layers list",
        default=0,
        min=0,
        update=update_edge_decal_layer_index,
    )

    if not bpy.app.timers.is_registered(_sync_source_layer_ui_after_register):
        bpy.app.timers.register(
            _sync_source_layer_ui_after_register,
            first_interval=0.0,
        )

    bpy.types.Scene.edge_decal_uv_pins = CollectionProperty(
        type=EDGEDECAL_PG_uv_pin
    )
    bpy.types.Scene.edge_decal_uv_pin_index = IntProperty(
        name="Selected UV Pin",
        default=-1,
        min=-1,
    )
    bpy.types.Scene.edge_decal_uv_pin_material = PointerProperty(
        name="UV Pin Material",
        type=bpy.types.Material,
        description="Edit the persistent UV pin set for this material",
        update=update_uv_pin_material_selection,
    )
    bpy.types.Scene.edge_decal_show_uv_pins = BoolProperty(
        name="Show UV Pins",
        default=True,
        description="Display all decal pins in the UV Editor",
        update=update_uv_pin_overlay_setting,
    )
    bpy.types.Scene.edge_decal_pin_edit_active = BoolProperty(
        name="Editing UV Pins",
        default=False,
        options={"HIDDEN"},
    )
    bpy.types.Scene.edge_decal_selected_pin_color = FloatVectorProperty(
        name="Selected Pin Color",
        subtype="COLOR",
        size=3,
        default=(1.0, 0.35, 0.05),
        min=0.0,
        max=1.0,
        update=update_uv_pin_overlay_setting,
    )
    bpy.types.Scene.edge_decal_unselected_pin_color = FloatVectorProperty(
        name="Unselected Pin Color",
        subtype="COLOR",
        size=3,
        default=(0.15, 0.7, 1.0),
        min=0.0,
        max=1.0,
        update=update_uv_pin_overlay_setting,
    )
    bpy.types.Scene.edge_decal_selected_pin_size = FloatProperty(
        name="Selected Pin Size",
        default=10.0,
        min=3.0,
        max=40.0,
        soft_min=5.0,
        soft_max=20.0,
        update=update_uv_pin_overlay_setting,
    )
    bpy.types.Scene.edge_decal_unselected_pin_size = FloatProperty(
        name="Unselected Pin Size",
        default=7.0,
        min=3.0,
        max=40.0,
        soft_min=4.0,
        soft_max=18.0,
        update=update_uv_pin_overlay_setting,
    )

    global EDGEDECAL_UV_PIN_DRAW_HANDLE
    if EDGEDECAL_UV_PIN_DRAW_HANDLE is None:
        EDGEDECAL_UV_PIN_DRAW_HANDLE = (
            bpy.types.SpaceImageEditor.draw_handler_add(
                draw_uv_pin_overlay,
                (),
                "WINDOW",
                "POST_PIXEL",
            )
        )

    global EDGEDECAL_ADDON_KEYMAPS
    window_manager = bpy.context.window_manager
    keyconfig = window_manager.keyconfigs.addon if window_manager else None

    if keyconfig is not None:
        keymap = keyconfig.keymaps.new(
            name="Image",
            space_type="IMAGE_EDITOR",
        )

        add_item = keymap.keymap_items.new(
            EDGEDECAL_OT_uv_pin_add_shortcut.bl_idname,
            type="LEFTMOUSE",
            value="PRESS",
            shift=True,
        )
        EDGEDECAL_ADDON_KEYMAPS.append((keymap, add_item))

        remove_item = keymap.keymap_items.new(
            EDGEDECAL_OT_uv_pin_remove_shortcut.bl_idname,
            type="RIGHTMOUSE",
            value="PRESS",
            shift=True,
        )
        EDGEDECAL_ADDON_KEYMAPS.append((keymap, remove_item))

        move_item = keymap.keymap_items.new(
            EDGEDECAL_OT_uv_pin_move_shortcut.bl_idname,
            type="LEFTMOUSE",
            value="PRESS",
        )
        EDGEDECAL_ADDON_KEYMAPS.append((keymap, move_item))

        exit_edit_item = keymap.keymap_items.new(
            EDGEDECAL_OT_uv_pin_toggle_edit_mode.bl_idname,
            type="ESC",
            value="PRESS",
        )
        exit_edit_item.properties.exit_only = True
        EDGEDECAL_ADDON_KEYMAPS.append((keymap, exit_edit_item))


    if edge_decal_sync_source_bevel_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(edge_decal_sync_source_bevel_handler)
    if edge_decal_repair_layers_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(edge_decal_repair_layers_handler)
    if (
        edge_decal_invalidate_prepared_source_cache_handler
        not in bpy.app.handlers.depsgraph_update_post
    ):
        bpy.app.handlers.depsgraph_update_post.append(
            edge_decal_invalidate_prepared_source_cache_handler
        )
    if (
        edge_decal_clear_prepared_source_cache_handler
        not in bpy.app.handlers.load_post
    ):
        bpy.app.handlers.load_post.append(
            edge_decal_clear_prepared_source_cache_handler
        )
    if edge_decal_rebuild_registry_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(edge_decal_rebuild_registry_handler)
    if edge_decal_rebuild_registry_handler not in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.append(edge_decal_rebuild_registry_handler)
    if edge_decal_rebuild_registry_handler not in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.append(edge_decal_rebuild_registry_handler)
    if edge_decal_initialize_presets_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(edge_decal_initialize_presets_handler)

    # This timer initializes only JSON-backed settings.  Material libraries and
    # their image datablocks remain untouched until generated geometry uses one.
    schedule_edge_decal_preset_initialization()

    global EDGEDECAL_SCENE_LIVE_SYNC_RUNNING
    if not bpy.app.timers.is_registered(edge_decal_scene_live_sync_timer):
        bpy.app.timers.register(
            edge_decal_scene_live_sync_timer,
            first_interval=EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL,
            persistent=True,
        )
    EDGEDECAL_SCENE_LIVE_SYNC_RUNNING = True

def unregister():
    global EDGEDECAL_SCENE_LIVE_SYNC_RUNNING
    global EDGEDECAL_SCENE_SETTINGS_COPYING
    global EDGEDECAL_SETTINGS_SYNCING
    global EDGEDECAL_REGENERATING_DEPTH
    global EDGEDECAL_LIVE_UPDATE_RUNNING
    EDGEDECAL_SCENE_LIVE_SYNC_RUNNING = False
    EDGEDECAL_SCENE_SETTINGS_COPYING = False
    EDGEDECAL_SETTINGS_SYNCING = False
    EDGEDECAL_REGENERATING_DEPTH = 0
    EDGEDECAL_LIVE_UPDATE_RUNNING = False
    if bpy.app.timers.is_registered(process_decal_live_update_queue):
        bpy.app.timers.unregister(process_decal_live_update_queue)
    EDGEDECAL_LIVE_UPDATE_QUEUE.clear()
    if bpy.app.timers.is_registered(edge_decal_scene_live_sync_timer):
        bpy.app.timers.unregister(edge_decal_scene_live_sync_timer)
    if bpy.app.timers.is_registered(edge_decal_initialize_presets_timer):
        bpy.app.timers.unregister(edge_decal_initialize_presets_timer)
    EDGEDECAL_SCENE_LIVE_SYNC_CACHE.clear()

    if edge_decal_sync_source_bevel_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(edge_decal_sync_source_bevel_handler)
    if edge_decal_repair_layers_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(edge_decal_repair_layers_handler)
    if (
        edge_decal_invalidate_prepared_source_cache_handler
        in bpy.app.handlers.depsgraph_update_post
    ):
        bpy.app.handlers.depsgraph_update_post.remove(
            edge_decal_invalidate_prepared_source_cache_handler
        )
    if (
        edge_decal_clear_prepared_source_cache_handler
        in bpy.app.handlers.load_post
    ):
        bpy.app.handlers.load_post.remove(
            edge_decal_clear_prepared_source_cache_handler
        )
    if edge_decal_rebuild_registry_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(edge_decal_rebuild_registry_handler)
    if edge_decal_rebuild_registry_handler in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(edge_decal_rebuild_registry_handler)
    if edge_decal_rebuild_registry_handler in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(edge_decal_rebuild_registry_handler)
    if edge_decal_initialize_presets_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(
            edge_decal_initialize_presets_handler
        )
    clear_prepared_source_cache(reset_stats=True)
    clear_decal_registry()
    EDGEDECAL_BEVEL_SYNC_CACHE.clear()
    global EDGEDECAL_ADDON_KEYMAPS
    for keymap, keymap_item in EDGEDECAL_ADDON_KEYMAPS:
        keymap.keymap_items.remove(keymap_item)
    EDGEDECAL_ADDON_KEYMAPS.clear()

    global EDGEDECAL_UV_PIN_DRAW_HANDLE
    if EDGEDECAL_UV_PIN_DRAW_HANDLE is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(
            EDGEDECAL_UV_PIN_DRAW_HANDLE,
            "WINDOW",
        )
        EDGEDECAL_UV_PIN_DRAW_HANDLE = None

    for property_name in (
        "edge_decal_unselected_pin_size",
        "edge_decal_selected_pin_size",
        "edge_decal_unselected_pin_color",
        "edge_decal_selected_pin_color",
        "edge_decal_pin_edit_active",
        "edge_decal_show_uv_pins",
    ):
        if hasattr(bpy.types.Scene, property_name):
            delattr(bpy.types.Scene, property_name)

    if hasattr(bpy.types.Scene, "edge_decal_uv_pin_index"):
        del bpy.types.Scene.edge_decal_uv_pin_index

    if hasattr(bpy.types.Scene, "edge_decal_uv_pin_material"):
        del bpy.types.Scene.edge_decal_uv_pin_material

    if hasattr(bpy.types.Scene, "edge_decal_uv_pins"):
        del bpy.types.Scene.edge_decal_uv_pins

    if hasattr(bpy.types.Scene, "edge_decal_settings"):
        del bpy.types.Scene.edge_decal_settings

    if hasattr(bpy.types.Scene, "edge_decal_preset_ui"):
        del bpy.types.Scene.edge_decal_preset_ui

    if hasattr(bpy.types.Scene, "edge_decal_unreal_export"):
        del bpy.types.Scene.edge_decal_unreal_export

    if hasattr(bpy.types.Object, "edge_decal_object_settings"):
        del bpy.types.Object.edge_decal_object_settings

    if hasattr(bpy.types.Object, "edge_decal_layer_index"):
        del bpy.types.Object.edge_decal_layer_index

    if hasattr(bpy.types.Object, "edge_decal_layers_ui"):
        del bpy.types.Object.edge_decal_layers_ui

    EDGEDECAL_LIVE_UPDATE_QUEUE.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
