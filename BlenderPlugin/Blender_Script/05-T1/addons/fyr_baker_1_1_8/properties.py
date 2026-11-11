from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import math
import types
import uuid as _uuid

import bpy

from . import constants, dirty_rules, naming
from .registration import safe_register_class, safe_remove_attr, safe_unregister_class


def _overlay_dynamic_update(_self, context):
    from . import overlays

    scene = getattr(context, "scene", None)
    overlays.mark_interaction()
    overlays.tag_redraw_all_view3d(
        scene=scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    # Defer debug overlay refresh to a timer so it never runs inside an undo/redo
    # step where RNA data may be temporarily inconsistent (segfault on access).
    delay = constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS

    def _deferred_debug_refresh():
        from . import runtime

        runtime.request_debug_overlay_refresh(
            bpy.context,
            delay_seconds=delay,
            reason="overlay_dynamic_update",
        )

    try:
        timers = getattr(bpy.app, "timers", None)
        if timers is not None and hasattr(timers, "register"):
            timers.register(_deferred_debug_refresh, first_interval=max(0.01, delay))
    except Exception:
        pass


def _heatmap_preview_update(_self, context):
    from . import overlays

    scene = getattr(context, "scene", None)
    overlays.mark_interaction()
    overlays.tag_redraw_all_view3d(
        scene=scene,
        window=getattr(context, "window", None),
        sync_preview=True,
    )


#: Scene keys for what turning Cage Coverage on paused or switched on, so turning the
#: last coverage toggle off puts the viewport back: the map preview resumes and the cage
#: goes back off (it used to stay on, with the preview gone for good).
_COVERAGE_PAUSED_PREVIEW_KEY = "_fyr_coverage_paused_preview"
_COVERAGE_FORCED_CAGE_KEY = "_fyr_coverage_forced_cage"


def _end_preview_for_coverage(context, settings) -> None:
    try:
        from . import operators
        from . import preview_on_low

        if preview_on_low.any_preview_on_low_is_active(settings):
            scene = getattr(context, "scene", None)
            picker = str(getattr(settings, "preview_picker", "") or "")
            if scene is not None and picker and picker != "OFF" and _COVERAGE_PAUSED_PREVIEW_KEY not in scene:
                scene[_COVERAGE_PAUSED_PREVIEW_KEY] = picker
            operators._deactivate_preview_on_low(context)
    except Exception:
        return


def _restore_after_coverage(context, settings, overlay_state) -> None:
    """The last coverage toggle went off: undo what switching coverage on did."""
    scene = getattr(context, "scene", None)
    if scene is None or settings is None:
        return
    project = get_active_project(scene)
    if project is not None and any(
        bool(getattr(group, "show_cage_coverage", False)) for group in getattr(project, "groups", []) or []
    ):
        return
    forced_cage = bool(scene.get(_COVERAGE_FORCED_CAGE_KEY, False))
    paused_picker = str(scene.get(_COVERAGE_PAUSED_PREVIEW_KEY, "") or "")
    for key in (_COVERAGE_FORCED_CAGE_KEY, _COVERAGE_PAUSED_PREVIEW_KEY):
        if key in scene:
            del scene[key]
    if forced_cage and overlay_state is not None and bool(getattr(overlay_state, "show_cage_overlay", False)):
        overlay_state.show_cage_overlay = False
    if paused_picker and str(getattr(settings, "preview_picker", "") or "") == "OFF":
        try:
            # Re-activates the preview through the picker's own update, exactly as a click.
            settings.preview_picker = paused_picker
        except Exception:
            pass  # that map is no longer baked; nothing to resume


def _cage_coverage_shown_update(self, context):
    """Per-group cage-coverage toggle. Coverage is drawn for every group whose flag is on,
    independent of the active selection, so switching groups no longer moves the overlay.
    Enabling a group engages the global coverage gate (``show_error_heatmap``), which
    preview-on-low still uses to suppress/restore all coverage at once."""
    from . import overlays

    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    overlay_state = overlay_settings_state(settings) if settings is not None else None
    if overlay_state is not None and bool(getattr(self, "show_cage_coverage", False)):
        # Coverage and a map preview never show together: coverage drawn over a preview
        # material reads as neither. Turning coverage on ends the preview first, which
        # also restores the overlay gates the preview saved, so engage them after.
        _end_preview_for_coverage(context, settings)
        # Engage the global coverage gate and make sure the cage overlay (which hosts the
        # coverage draw) is on, so enabling coverage always actually shows something.
        if not bool(getattr(overlay_state, "show_error_heatmap", False)):
            overlay_state.show_error_heatmap = True
        if hasattr(overlay_state, "show_cage_overlay") and not bool(getattr(overlay_state, "show_cage_overlay", False)):
            overlay_state.show_cage_overlay = True
            if scene is not None:
                scene[_COVERAGE_FORCED_CAGE_KEY] = True
    elif overlay_state is not None:
        _restore_after_coverage(context, settings, overlay_state)
    overlays.mark_interaction()
    overlays.tag_redraw_all_view3d(
        scene=scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )


def _overlay_preview_visibility_update(_self, context):
    from . import overlays
    from . import runtime

    scene = getattr(context, "scene", None)
    overlays.mark_interaction()
    overlays.tag_redraw_all_view3d(
        scene=scene,
        window=getattr(context, "window", None),
        sync_preview=True,
    )
    runtime.request_debug_overlay_refresh(
        context,
        delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        reason="overlay_preview_visibility_update",
    )


def _request_live_normal_preview_refresh(context, reason: str) -> None:
    try:
        from . import operators

        operators.request_live_normal_preview_refresh(context, reason=reason)
    except Exception:
        return


def _preview_environment_update(self, context):
    try:
        from . import operators

        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        session_state = preview_session_state(settings) if settings is not None else None
        if session_state is None:
            return
        if (
            bool(getattr(session_state, "preview_on_low_active", False))
            or bool(getattr(session_state, "preview_pbr_on_low_active", False))
            or bool(getattr(session_state, "live_normal_preview_active", False))
        ):
            operators._apply_preview_on_low_viewport_state(context)
    except Exception:
        return


def _preview_material_setting_update(self, context):
    try:
        from . import operators

        scene = getattr(context, "scene", None)
        settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
        session_state = preview_session_state(settings) if settings is not None else None
        project = get_active_project(scene) if scene is not None else None
        if (
            project is not None
            and session_state is not None
            and bool(getattr(session_state, "preview_pbr_on_low_active", False))
        ):
            operators._sync_preview_material_for_project(scene, project)
    except Exception:
        return


def set_preview_map_type(settings, value, fallback: str = "") -> str:
    """Point the preview picker at a map type without ever raising.

    Two things make a direct assignment unsafe. Output records store per-channel
    effective types (``MATERIAL_ALBEDO``) that are not enum members, and the enum's
    items are filtered to map types that have actually been baked, so even a valid
    base type can be absent. Both used to surface as a TypeError traceback *after*
    the operator had already done its real work.
    """
    seen = []
    for candidate in (constants.base_map_type(value), constants.base_map_type(fallback), ""):
        if candidate in seen:
            continue
        seen.append(candidate)
        try:
            settings.preview_map_type = candidate
            return candidate
        except TypeError:
            continue
    return ""


#: Preview-picker items cache, keyed by the settings block's RNA pointer.
#: Value is ``(outputs_count, (map_type, ...))``. It lives here rather than in RNA
#: because the only consumer is an EnumProperty items callback, and ANY RNA write
#: from inside one re-enters enum resolution -- the cache write and the "reset the
#: selection" assignment together turned duplicate/remove/restore project into a
#: RecursionError. This callback is now read-only with respect to RNA; the stale
#: selection is corrected by set_preview_map_type from the operators that change it.
_PREVIEW_MAP_ITEMS_CACHE: dict[int, tuple[int, tuple[str, ...]]] = {}


def _settings_cache_key(settings) -> int:
    pointer = getattr(settings, "as_pointer", None)
    if callable(pointer):
        try:
            return int(pointer())
        except Exception:
            pass
    return id(settings)


def _preview_map_items_for_types(available_types) -> list[tuple[str, str, str]]:
    return [
        (map_type_id, label, description)
        for map_type_id, label, description in constants.MAP_TYPE_ITEMS
        if map_type_id in available_types
    ]


#: Keeps the picker's item strings alive: Blender does not copy strings returned by
#: an EnumProperty items callback, and freed ones render as garbage labels.
_PREVIEW_PICKER_ITEMS: list = []
_PREVIEW_PICKER_OFF = "OFF"


def _preview_picker_number(map_type: str) -> int:
    # Stable per type because MAP_TYPE_ITEMS is append-only; 0 is Off.
    for index, item in enumerate(constants.MAP_TYPE_ITEMS):
        if item[0] == map_type:
            return index + 1
    return 0


def _preview_picker_items(self, context):
    available = {item[0] for item in _available_preview_map_items(self, context) if item[0]}
    items = [(_PREVIEW_PICKER_OFF, "Off", "Stop the preview and restore the low-poly meshes' original materials", 0)]
    for index, (map_type, label, description) in enumerate(constants.MAP_TYPE_ITEMS):
        if map_type in available:
            items.append((map_type, label, description, index + 1))
    _PREVIEW_PICKER_ITEMS[:] = items
    return _PREVIEW_PICKER_ITEMS


def _preview_picker_get(self) -> int:
    """Derived from the live preview session, so the picker can never read stale."""
    session = preview_session_state(self)
    if session is None or not bool(getattr(session, "preview_on_low_active", False)):
        return 0
    return _preview_picker_number(constants.base_map_type(getattr(session, "preview_on_low_map_type", "")))


def _preview_picker_set(self, value) -> None:
    map_type = _PREVIEW_PICKER_OFF
    for index, item in enumerate(constants.MAP_TYPE_ITEMS):
        if index + 1 == int(value):
            map_type = item[0]
            break
    try:
        import bpy

        bpy.ops.master_baker.set_preview_map("EXEC_DEFAULT", map_type=map_type)
    except Exception:
        return


def _available_preview_map_items(self, context):
    """Return only map types that have baked outputs available for preview (cached).

    Must not write RNA: see _PREVIEW_MAP_ITEMS_CACHE.
    """
    scene = getattr(context, "scene", None)
    if scene is None:
        return []
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None:
        return []
    project = get_active_project(scene)
    if project is None:
        return []

    # Recalculate available map types. Records hold effective types; the items
    # below are base types. Without folding them together a baked
    # MATERIAL_ALBEDO never offers "Material".
    available_types = set()
    for output in getattr(project, "latest_outputs", []):
        map_type = constants.base_map_type(getattr(output, "map_type", ""))
        if map_type:
            available_types.add(map_type)

    # The cache is keyed by the active PROJECT and versioned by the set of baked
    # types, never by the output count: a rebake that swaps Normal+AO for
    # Curvature+Height keeps the count at 2, and switching to another project
    # with the same count would otherwise keep offering the previous project's
    # maps. Rebuilding the set above is a handful of string lookups per draw.
    cache_key = _settings_cache_key(project)
    version = tuple(sorted(available_types))
    cached = _PREVIEW_MAP_ITEMS_CACHE.get(cache_key)
    if cached is not None and cached[1] == version:
        if version:
            return _preview_map_items_for_types(set(version))
        return [("", "No Maps", "Bake maps to enable preview")]

    _PREVIEW_MAP_ITEMS_CACHE[cache_key] = (len(version), version)

    # If no baked outputs, return a placeholder item so the dropdown button shows text
    if not available_types:
        return [("", "No Maps", "Bake maps to enable preview")]

    # Filter MAP_TYPE_ITEMS to only include available types
    return _preview_map_items_for_types(available_types)




def _active_project_from_context(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return None
    try:
        return get_active_project(scene)
    except Exception:
        return None


def _enabled_project_map_types(project) -> list[str]:
    return dirty_rules.enabled_map_types_from_settings(getattr(project, "maps", []))


def resolve_aa_samples(project) -> int:
    """Effective jittered sample-pass count for a project.

    The sample count is the only anti-aliasing control: ``0`` means off, which
    is one un-jittered sample per pixel. That is why an explicitly stored ``0``
    is not treated as "unset" — only a missing IDProperty is, and only then does
    a pre-samples .blend migrate from the legacy ``anti_aliasing`` enum.
    """
    raw = None
    getter = getattr(project, "get", None)
    if callable(getter):
        try:
            raw = getter("aa_samples")
        except Exception:
            raw = None
        if raw is None:
            # Distinguish a pre-samples .blend (legacy enum stored, samples
            # absent) from a project that simply never moved off the default.
            try:
                legacy_stored = getter("anti_aliasing") is not None
            except Exception:
                legacy_stored = False
            if legacy_stored:
                raw = constants.anti_aliasing_to_samples(
                    getattr(project, "anti_aliasing", constants.DEFAULT_ANTI_ALIASING)
                )
    if raw is None:
        raw = getattr(project, "aa_samples", constants.DEFAULT_AA_SAMPLES)
    try:
        raw = int(raw)
    except (TypeError, ValueError):
        raw = constants.DEFAULT_AA_SAMPLES
    if raw <= 0:
        return constants.AA_SAMPLES_OFF_PASSES
    return max(constants.AA_SAMPLES_MIN, min(constants.AA_SAMPLES_MAX, raw))


def _same_rna_struct(left, right) -> bool:
    """Identity for RNA wrappers.

    Blender hands out a fresh bpy_struct wrapper for every PropertyGroup access, so
    ``owner is group`` is never true for two wrappers of the same struct. Compare the
    underlying RNA pointer when both sides expose one, and fall back to ``is`` for
    plain Python objects (tests, fakes).
    """
    if left is None or right is None:
        return False
    if left is right:
        return True
    left_ptr = getattr(left, "as_pointer", None)
    right_ptr = getattr(right, "as_pointer", None)
    if callable(left_ptr) and callable(right_ptr):
        try:
            return left_ptr() == right_ptr()
        except Exception:
            return False
    return False


def _resolve_group_names_for_owner(project, owner) -> list[str]:
    if project is None or owner is None:
        return []

    group_names: list[str] = []
    for group in getattr(project, "groups", []):
        group_name = str(getattr(group, "name", "") or "").strip()
        if not group_name:
            continue
        if any(
            _same_rna_struct(owner, candidate)
            for candidate in (
                group,
                getattr(group, "metadata", None),
                getattr(group, "collections", None),
                getattr(group, "role_assignments", None),
                getattr(group, "projection_settings", None),
                getattr(group, "paint_projection_settings", None),
                getattr(group, "custom_cage", None),
            )
        ):
            group_names.append(group_name)
            continue
        found_slot_owner = False
        for slot_collection in (getattr(group, "low_meshes", []), getattr(group, "high_meshes", [])):
            for slot in slot_collection:
                if _same_rna_struct(owner, slot) or _same_rna_struct(owner, getattr(slot, "object_ref", None)):
                    group_names.append(group_name)
                    found_slot_owner = True
                    break
            if found_slot_owner:
                break

    if group_names:
        return sorted(set(group_names))

    active_group = get_active_group(project)
    active_group_name = str(getattr(active_group, "name", "") or "").strip() if active_group is not None else ""
    return [active_group_name] if active_group_name else []


def _mark_project_dirty(context, *, project=None, group_names=None, map_types=None) -> None:
    from . import dirty_tracker

    if project is None:
        project = _active_project_from_context(context)
    if project is None or not dirty_tracker.is_session_active():
        return

    target_group_names = [
        str(group_name or "").strip()
        for group_name in (group_names if group_names is not None else [getattr(group, "name", "") for group in getattr(project, "groups", [])])
        if str(group_name or "").strip()
    ]
    target_map_types = dirty_rules.normalize_map_types(map_types if map_types is not None else _enabled_project_map_types(project))
    if not target_group_names or not target_map_types:
        return

    for group_name in sorted(set(target_group_names)):
        dirty_tracker.mark_dirty(group_name, set(target_map_types))


def _clear_project_map_dirty(context, map_type: str, *, project=None) -> None:
    from . import dirty_tracker

    if project is None:
        project = _active_project_from_context(context)
    normalized_map_type = dirty_rules.normalize_map_type(map_type)
    if project is None or not normalized_map_type or not dirty_tracker.is_session_active():
        return

    for group in getattr(project, "groups", []):
        group_name = str(getattr(group, "name", "") or "").strip()
        if group_name:
            dirty_tracker.clear_dirty(group_name, {normalized_map_type})


def _refresh_dirty_tracker_membership(context, *, project=None) -> None:
    from . import dirty_tracker

    if project is None:
        project = _active_project_from_context(context)
    if project is None or not dirty_tracker.is_session_active():
        return
    dirty_tracker.refresh_membership_index(project)


def _mark_group_projection_dirty(owner, context) -> None:
    project = _active_project_from_context(context)
    if project is None:
        return
    _mark_project_dirty(
        context,
        project=project,
        group_names=_resolve_group_names_for_owner(project, owner),
        map_types=dirty_rules.projection_dirty_map_types(getattr(project, "maps", [])),
    )
    _schedule_settings_prepare()


def _mark_group_all_maps_dirty(owner, context) -> None:
    project = _active_project_from_context(context)
    if project is None:
        return
    _mark_project_dirty(
        context,
        project=project,
        group_names=_resolve_group_names_for_owner(project, owner),
        map_types=_enabled_project_map_types(project),
    )
    _schedule_settings_prepare()


def _mark_group_id_dirty(owner, context) -> None:
    project = _active_project_from_context(context)
    if project is None:
        return
    _mark_project_dirty(
        context,
        project=project,
        group_names=_resolve_group_names_for_owner(project, owner),
        map_types={constants.MAP_ID},
    )
    _schedule_settings_prepare()


_LOW_SAMPLE_WARNING_SUPPRESSION_DEPTH = 0
_LOW_SAMPLE_WARNING_REQUESTS: dict[str, tuple[int, int]] = {}
_LAST_CONFIRMED_SAMPLE_COUNTS: dict[str, int] = {}


def _sample_warning_key(map_setting) -> str:
    return str(getattr(map_setting, "uuid", "") or "").strip()


@contextmanager
def suppress_low_sample_warning():
    global _LOW_SAMPLE_WARNING_SUPPRESSION_DEPTH
    _LOW_SAMPLE_WARNING_SUPPRESSION_DEPTH += 1
    try:
        yield
    finally:
        _LOW_SAMPLE_WARNING_SUPPRESSION_DEPTH = max(0, _LOW_SAMPLE_WARNING_SUPPRESSION_DEPTH - 1)


def set_map_samples_without_warning(map_setting, samples: int) -> None:
    key = _sample_warning_key(map_setting)
    with suppress_low_sample_warning():
        map_setting.samples = int(samples)
    if key:
        _LAST_CONFIRMED_SAMPLE_COUNTS[key] = int(samples)
        _LOW_SAMPLE_WARNING_REQUESTS.pop(key, None)


def confirm_low_sample_count(map_setting, samples: int) -> None:
    key = _sample_warning_key(map_setting)
    if key:
        _LAST_CONFIRMED_SAMPLE_COUNTS[key] = int(samples)
        _LOW_SAMPLE_WARNING_REQUESTS.pop(key, None)


def cancel_low_sample_count_warning(map_uuid: str) -> None:
    _LOW_SAMPLE_WARNING_REQUESTS.pop(str(map_uuid or "").strip(), None)


def pop_low_sample_warning_request() -> tuple[str, int, int] | None:
    if not _LOW_SAMPLE_WARNING_REQUESTS:
        return None
    map_uuid = next(iter(_LOW_SAMPLE_WARNING_REQUESTS))
    proposed_samples, previous_samples = _LOW_SAMPLE_WARNING_REQUESTS.pop(map_uuid)
    return map_uuid, proposed_samples, previous_samples


def _queue_low_sample_warning(map_setting) -> None:
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    ao_mode = str(getattr(map_setting, "ao_mode", constants.MAP_AO_MODE_RAYCAST) or "").strip().upper()
    if not constants.map_uses_samples(map_type, ao_mode):
        return

    try:
        sample_count = int(getattr(map_setting, "samples", constants.MAP_RECOMMENDED_SAMPLES))
    except (TypeError, ValueError):
        return

    key = _sample_warning_key(map_setting)
    if not key:
        return
    if _LOW_SAMPLE_WARNING_SUPPRESSION_DEPTH > 0:
        _LAST_CONFIRMED_SAMPLE_COUNTS[key] = sample_count
        _LOW_SAMPLE_WARNING_REQUESTS.pop(key, None)
        return
    if sample_count >= constants.MAP_LOW_SAMPLE_WARNING_THRESHOLD:
        _LAST_CONFIRMED_SAMPLE_COUNTS[key] = sample_count
        _LOW_SAMPLE_WARNING_REQUESTS.pop(key, None)
        return

    previous_samples = _LAST_CONFIRMED_SAMPLE_COUNTS.get(key, constants.default_samples_for_map(map_type))
    if previous_samples < constants.MAP_LOW_SAMPLE_WARNING_THRESHOLD:
        return
    _LOW_SAMPLE_WARNING_REQUESTS[key] = (sample_count, previous_samples)


def _samples_update(self, context):
    _map_setting_update(self, context)
    _queue_low_sample_warning(self)


def _trigger_activity_rewarm(context, reason):
    """Activity-driven GPU keep-warm: on a bake-setting change, ask the resident
    backend worker to re-pin residency + spin GPU clocks so the next bake starts
    warm, and reset the idle timer that eventually releases the pin.

    Fully best-effort and debounced inside runtime.schedule_warmkeep_arm; wrapped
    here so a keep-warm hiccup can never raise into a Blender property update."""
    try:
        from . import runtime as _runtime
        from . import high_mesh_cache  # noqa: F401  (kept resident/imported alongside prewarm)
    except Exception:
        return
    try:
        _runtime.schedule_warmkeep_arm(reason=reason)
    except Exception:
        pass


def _schedule_settings_prepare() -> None:
    """Fire the speculative PREPARE for the exact new job after a map-setting
    change, debounced from the LAST change (slider drags fire one update per
    step). The PREPARE precomputes the heavy work — including the full-sample
    world-AO shading dispatch — during user think-time, so the eventual bake
    click only pays the ~0.5s RUN instead of prepare+bake serially (measured:
    settings-change PREPARE 1.3s of which ~1.0s is the world-AO dispatch;
    warm RUN alone 0.45-0.53s at ~2050 spp).

    Cold high-mesh capture is forbidden on this path: resolving a multi-million
    evaluated mesh on the main thread freezes Blender for seconds. Geometry
    warm-up stays on file-open / membership / explicit bake.
    """
    try:
        from . import runtime as _runtime

        _runtime.schedule_speculative_prepare(
            delay=0.5,
            restart=True,
            allow_cold_high_warm=False,
        )
    except Exception:
        pass


def _map_setting_update(self, context):
    project = _active_project_from_context(context)
    if project is not None:
        from . import texture_reprojection
    map_type = dirty_rules.normalize_map_type(getattr(self, "map_type", ""))
    if project is None or not map_type:
        _trigger_activity_rewarm(context, reason="map_setting_changed")
        return
    if bool(getattr(self, "enabled", False)):
        _mark_project_dirty(context, project=project, map_types={map_type})
        _trigger_activity_rewarm(context, reason="map_setting_changed")
        _schedule_settings_prepare()
        return
    _clear_project_map_dirty(context, map_type, project=project)
    _trigger_activity_rewarm(context, reason="map_setting_changed")
    _schedule_settings_prepare()


def project_high_objects(project) -> list:
    """Every distinct high object across the project's groups, in group order."""
    from . import project_structure

    seen: set[int] = set()
    objects: list = []
    for group in getattr(project, "groups", None) or ():
        try:
            highs = project_structure.group_role_targets(group, constants.OBJECT_ROLE_HIGH)
        except Exception:  # noqa: BLE001 - a broken group must not hide the others
            continue
        for obj in highs or ():
            if getattr(obj, "type", "") != "MESH":
                continue
            key = obj.as_pointer() if hasattr(obj, "as_pointer") else id(obj)
            if key in seen:
                continue
            seen.add(key)
            objects.append(obj)
    return objects


def _attribute_name_search(self, context, edit_text):
    """Bakeable attribute names on the project's high meshes, evaluated (Geometry Nodes
    outputs included). Reads names and types only, never element data."""
    from . import color_stream

    project = _active_project_from_context(context)
    if project is None:
        return []
    try:
        depsgraph = context.evaluated_depsgraph_get()
    except Exception:  # noqa: BLE001
        depsgraph = None
    names: set[str] = set()
    for obj in project_high_objects(project):
        try:
            mesh = obj.evaluated_get(depsgraph).data if depsgraph is not None else obj.data
        except Exception:  # noqa: BLE001
            mesh = getattr(obj, "data", None)
        if mesh is not None:
            names.update(color_stream.bakeable_attribute_names(mesh))
    needle = str(edit_text or "").lower()
    return sorted(name for name in names if needle in name.lower())


#: Every label add_map_setting can stamp an auto suffix with. Membership is what
#: separates a stale "Normal_2" stamp from a hand-typed "Batch_2".
_AUTO_SUFFIX_LABELS = frozenset(constants.MAP_FILE_LABELS.values())


def _clear_stale_auto_output_suffix(map_setting) -> None:
    """Drop an auto-stamped "<MapFileLabel>_<n>" suffix that names the WRONG type.

    add_map_setting stamps the second row of a type with "<Label>_<n>". Retyping
    that row leaves the stamp behind: it renames the new type's output file, and it
    keeps the number reserved for a type the row no longer has, so the next add of
    the original type stamps the same suffix twice. Only an exact auto-stamp for a
    different type is cleared -- a hand-typed suffix never matches the pattern.
    """
    suffix = str(getattr(map_setting, "output_suffix", "") or "").strip()
    if not suffix:
        return
    base, _, index = suffix.rpartition("_")
    if not base or not index.isdigit() or base not in _AUTO_SUFFIX_LABELS:
        return
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    if base == constants.MAP_FILE_LABELS.get(map_type):
        return
    map_setting.output_suffix = ""


def _normal_encoding_update(self, context):
    # A second Normal row carries an auto-stamped "Normal_<n>" suffix. As a Derivative
    # row it already writes its own file, so the stamp would only rename it.
    if naming.normal_row_is_derivative(self):
        suffix = str(getattr(self, "output_suffix", "") or "").strip()
        base, _, index = suffix.rpartition("_")
        if index.isdigit() and base == constants.MAP_FILE_LABELS.get(constants.MAP_NORMAL):
            self.output_suffix = ""
    _map_setting_update(self, context)


def _map_type_update(self, context):
    _clear_stale_auto_output_suffix(self)
    # Retyping a row (AO -> Curvature) is a bake-affecting change like every other
    # row edit: without this the new type was never marked dirty and Live Bake
    # skipped the row the artist just changed.
    _map_setting_update(self, context)


def _map_enabled_update(self, context):
    """Toggle a map on/off in the stack.

    Must NOT schedule speculative PREPARE. That path re-exports highs on the
    main thread (multi-second Not Responding on multi-million meshes). Enable
    only changes which maps bake; geometry prewarm is unchanged. Mark dirty +
    GPU warmkeep, and refresh live normal preview if needed.
    """
    project = _active_project_from_context(context)
    if project is not None:
        from . import texture_reprojection
    map_type = dirty_rules.normalize_map_type(getattr(self, "map_type", ""))
    if project is not None and map_type:
        if bool(getattr(self, "enabled", False)):
            _mark_project_dirty(context, project=project, map_types={map_type})
        else:
            _clear_project_map_dirty(context, map_type, project=project)
    _trigger_activity_rewarm(context, reason="map_enabled_changed")
    # Do not call _normal_preview_config_update here: it re-enters
    # _map_setting_update and would schedule the blocking PREPARE we just
    # avoided. Only poke live normal preview when Normal itself toggled.
    if map_type == constants.MAP_NORMAL:
        _request_live_normal_preview_refresh(context, "map_enabled_changed")
    # The Bakeability readout's AO/Bevel/Raycast verdict depends on whether the
    # job is material-only, which is exactly what this toggle changes. Nothing
    # else invalidates its cache — a map toggle is not a depsgraph material update.
    try:
        from . import bakeability_ui

        bakeability_ui.request_update()
    except Exception:
        pass


def _ao_mode_update(self, context):
    if str(getattr(self, "ao_mode", constants.MAP_AO_MODE_RAYCAST)).strip().upper() == constants.MAP_AO_MODE_DIFFUSIVE_ESCAPE:
        # Every one of these is a raycast-only control. Clear them all: the old
        # early return after the first hit left the rest set, so a switch to
        # Diffusive Escape could keep e.g. the ground plane enabled while the mode
        # that reads it was gone.
        for flag in (
            "ao_ignore_groups",
            "ao_occlude_other_groups",
            "ao_relative_to_bounding_box",
            "ao_use_ground_plane",
        ):
            if bool(getattr(self, flag, False)):
                setattr(self, flag, False)
        # Use Bevel Normal is left alone. Diffusive Escape never shades from it
        # (resolve_ao_bevel_normal), and clearing the enum would forget Auto.
    _map_setting_update(self, context)


def _thickness_ignore_groups_update(self, context):
    _map_setting_update(self, context)


# Guard set keyed by map-item pointer so writing preset transport values from
# _lighting_quality_update cannot re-enter through the transport fields'
# _map_setting_update callbacks (same pattern as _RESOLUTION_SYNC_GUARD).
_LIGHTING_QUALITY_SYNC_GUARD: set[int] = set()


def _lighting_quality_update(self, context):
    """Apply a lighting quality preset to ONLY this map row's transport fields.

    When the new value is a named preset (not CUSTOM), copy its
    (direct_samples, indirect_paths, max_bounces, noise_threshold) tuple onto
    the same map item. Never touches other map rows or any global setting."""
    key = _resolution_owner_key(self)
    if key not in _LIGHTING_QUALITY_SYNC_GUARD:
        preset = str(getattr(self, "lighting_quality", constants.LIGHTING_QUALITY_BALANCED) or "").strip().upper()
        values = constants.LIGHTING_QUALITY_PRESET_VALUES.get(preset)
        if values is not None:
            direct_samples, indirect_paths, max_bounces, noise_threshold = values
            _LIGHTING_QUALITY_SYNC_GUARD.add(key)
            try:
                if int(getattr(self, "lighting_direct_samples", 0)) != int(direct_samples):
                    self.lighting_direct_samples = int(direct_samples)
                if int(getattr(self, "lighting_indirect_paths", 0)) != int(indirect_paths):
                    self.lighting_indirect_paths = int(indirect_paths)
                if int(getattr(self, "lighting_max_bounces", 0)) != int(max_bounces):
                    self.lighting_max_bounces = int(max_bounces)
                if float(getattr(self, "lighting_noise_threshold", 0.0)) != float(noise_threshold):
                    self.lighting_noise_threshold = float(noise_threshold)
            finally:
                _LIGHTING_QUALITY_SYNC_GUARD.discard(key)
    _map_setting_update(self, context)


def _lighting_transport_update(self, context):
    """Editing a lighting number promotes Quality to Custom, keeping the typed value.

    The four transport fields used to be drawn disabled whenever a named preset was
    selected. Blender renders a disabled number widget muted grey but still lets the
    click land in some 5.x builds, so the value appeared to change and then snapped
    back on the next preset write -- the "greyed out but it still changes" a tester
    reported. Editing one now means Custom, which is the standard DCC behaviour and
    keeps the preset honest: a preset either owns all four values or is not selected.

    Guarded by the same set `_lighting_quality_update` uses, so applying a preset
    (which writes all four) cannot bounce the enum straight back to Custom.
    """
    key = _resolution_owner_key(self)
    if key not in _LIGHTING_QUALITY_SYNC_GUARD:
        current = str(getattr(self, "lighting_quality", "") or "").strip().upper()
        if current and current != constants.LIGHTING_QUALITY_CUSTOM:
            _LIGHTING_QUALITY_SYNC_GUARD.add(key)
            try:
                self.lighting_quality = constants.LIGHTING_QUALITY_CUSTOM
            finally:
                _LIGHTING_QUALITY_SYNC_GUARD.discard(key)
    _map_setting_update(self, context)


# Project-level settings (AA, resolution, margin, formats, ...) fold into the
# backend's prepared-group cache key, so changing one silently invalidates the
# standing prewarm: without a fresh speculative PREPARE the next bake pays a
# full cold prepare (~20-50s on a heavy scene) even though the panel said the
# scene cache was ready. These update callbacks are the ONLY reliable trigger —
# custom-property changes produce no depsgraph updates at all (verified
# empirically), so a depsgraph-side signature check never fires.
def _project_all_maps_dirty_update(self, context):
    _mark_project_dirty(context, project=self)
    _schedule_settings_prepare()


def _aa_samples_update(self, context):
    # Keep the retained legacy enum coarsely in sync so any remaining reader of
    # anti_aliasing (reprojection scale, older backends) tracks the user's
    # choice. Exact sample counts flow through aa_samples everywhere that needs
    # them (job payload, presets, project copy, dirty signature).
    try:
        nearest = constants.samples_to_anti_aliasing(getattr(self, "aa_samples", constants.DEFAULT_AA_SAMPLES))
        if getattr(self, "anti_aliasing", None) != nearest:
            self.anti_aliasing = nearest
    except Exception:
        pass
    _mark_project_dirty(context, project=self)
    _schedule_settings_prepare()


def _project_margin_update(self, context):
    _project_live_normal_preview_update(self, context)
    _mark_project_dirty(context, project=self)
    _schedule_settings_prepare()


def effective_bake_margin(project, width: int, height: int) -> int:
    """Pixel radius that reaches every texel when bake dilation is Infinite.

    The bake protocol has one integer margin shared by native and Cycles paths.
    The image diagonal is enough for the GPU's Euclidean JFA radius and the
    eight-neighbour chart fills, including rectangular UDIM tiles.
    """
    if str(getattr(project, "margin_mode", constants.DILATION_DISTANCE)) != constants.DILATION_INFINITE:
        value = getattr(project, "margin", constants.DEFAULT_MARGIN)
        return max(0, int(constants.DEFAULT_MARGIN if value is None else value))
    return math.ceil(math.hypot(max(1, int(width)), max(1, int(height))))


def _project_tangent_basis_update(self, context):
    _project_live_normal_preview_update(self, context)
    _mark_project_dirty(
        context,
        project=self,
        map_types=dirty_rules.tangent_basis_dirty_map_types(getattr(self, "maps", [])),
    )
    _schedule_settings_prepare()


def _project_ignore_backface_update(self, context):
    _overlay_dynamic_update(self, context)
    _mark_project_dirty(context, project=self)
    _schedule_settings_prepare()


def _texture_set_name_update(self, context):
    _group_collection_metadata_update(self, context)
    _mark_group_all_maps_dirty(self, context)


def _rename_export_rows_for_texture_set(project, prev_name: str, new_name: str) -> None:
    """Follow a set rename into the Export dialog's override and exclusion rows.

    Both are keyed by the set's link name; only the delete path pruned them, so
    an excluded set renamed Trim -> Trim_A silently started exporting again and
    its size/padding override stopped applying.
    """
    export_settings = getattr(project, "export_settings", None)
    if export_settings is None:
        return
    prev_key = str(prev_name or "").strip().casefold()
    if not prev_key:
        return
    for collection_name in ("set_overrides", "excluded_texture_sets"):
        for row in getattr(export_settings, collection_name, None) or []:
            if str(getattr(row, "name", "") or "").strip().casefold() == prev_key:
                try:
                    row.name = str(new_name or "")
                except Exception:
                    pass


def _texture_set_identity_rename(self, context):
    """Keep group->set links intact when a texture set is renamed in place.

    Groups reference their set by name string (`group.texture_set_name`), so a raw
    rename would orphan them. We track the set's previous name in a hidden IDProperty
    (`_identity_name`) and rewrite every member group's link old -> new. The settings
    panel seeds that tracker for older projects before the editable name field is drawn.
    """
    new_name = (getattr(self, "name", "") or "").strip()
    prev = str(self.get("_identity_name", "") or "")
    if prev == new_name:
        return
    if prev:
        settings = getattr(getattr(context, "scene", None), "fyr_baker_settings", None)
        for project in getattr(settings, "projects", []):
            sets = getattr(project, "texture_sets", [])
            if any(ts.as_pointer() == self.as_pointer() for ts in sets):
                prev_key = prev.strip().casefold()
                _rename_export_rows_for_texture_set(project, prev, new_name)
                for group in getattr(project, "groups", []):
                    if (getattr(group, "texture_set_name", "") or "").strip().casefold() == prev_key:
                        group.texture_set_name = new_name
                break
    self["_identity_name"] = new_name


def seed_texture_set_identity(texture_set) -> None:
    """Seed the previous-name tracker used by in-place texture-set rename."""
    if texture_set is None:
        return
    try:
        if not str(texture_set.get("_identity_name", "") or ""):
            texture_set["_identity_name"] = str(getattr(texture_set, "name", "") or "").strip()
    except Exception:
        pass


def _group_id_metadata_update(self, context):
    _group_collection_metadata_update(self, context)
    _mark_group_id_dirty(self, context)


# Bulk operators (auto-build from names) assign dozens of role slots in a loop.
# Each object_ref assignment fires _group_membership_update, whose overlay /
# preview / high-mesh-prewarm / backend-prepare / dirty-tracker cascade touches
# the (potentially multi-million-tri) high meshes. Left un-batched that turns a
# single build into O(N^2) work + repeated backend re-entry -- a multi-second
# freeze that reads as a crash. Callers wrap the loop in
# suspend_group_membership_updates() and run bulk_group_membership_refresh() once
# at the end.
_SUSPEND_MEMBERSHIP_UPDATES = 0


def suspend_group_membership_updates():
    """Context manager: silence per-slot _group_membership_update during bulk edits."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        global _SUSPEND_MEMBERSHIP_UPDATES
        _SUSPEND_MEMBERSHIP_UPDATES += 1
        try:
            yield
        finally:
            _SUSPEND_MEMBERSHIP_UPDATES -= 1

    return _ctx()


def _group_membership_refresh(context):
    """The reactive cascade that follows a group-membership change (scene-wide)."""
    _overlay_static_update(None, context)
    try:
        from . import overlays

        overlays.sync_preview_visibility(getattr(context, "scene", None))
    except Exception:
        pass
    _request_live_normal_preview_refresh(context, "group_membership_update")
    try:
        from . import high_mesh_cache

        high_mesh_cache.request_context_prewarm(context, reason="group_membership_update")
    except Exception:
        pass
    try:
        from . import runtime as _runtime

        _runtime.schedule_backend_prewarm(reason="group_membership_update")
        _runtime.schedule_speculative_prepare()
    except Exception:
        pass
    _refresh_dirty_tracker_membership(context)


def bulk_group_membership_refresh(context, groups=None):
    """One-shot equivalent of _group_membership_update after a suppressed bulk edit.

    Runs the scene-wide reactive cascade once, then marks every touched group's
    maps dirty (the per-slot callback would have done this incrementally).
    """
    _group_membership_refresh(context)
    for group in groups or []:
        _mark_group_all_maps_dirty(group, context)


def _group_membership_update(self, context):
    if _SUSPEND_MEMBERSHIP_UPDATES:
        return
    _group_membership_refresh(context)
    _mark_group_all_maps_dirty(self, context)


def _overlay_static_update(_self, context):
    from . import overlays
    from . import runtime

    scene = getattr(context, "scene", None)
    overlays.tag_redraw_all_view3d(
        scene=scene,
        clear_static=True,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    runtime.request_debug_overlay_refresh(
        context,
        delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        reason="overlay_static_update",
    )


def _overlay_visibility_update(_self, context):
    from . import overlays
    from . import runtime

    scene = getattr(context, "scene", None)
    overlays.mark_interaction()
    overlays.tag_redraw_all_view3d(scene=scene, window=getattr(context, "window", None))
    runtime.request_debug_overlay_refresh(
        context,
        delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        reason="overlay_visibility_update",
    )


def _overlay_static_visibility_update(_self, context):
    from . import overlays
    from . import runtime

    scene = getattr(context, "scene", None)
    overlays.tag_redraw_all_view3d(
        scene=scene,
        clear_static=True,
        window=getattr(context, "window", None),
    )
    runtime.request_debug_overlay_refresh(
        context,
        delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        reason="overlay_static_visibility_update",
    )


def _cage_offset_update(_self, context):
    from . import overlays
    from . import runtime

    scene = getattr(context, "scene", None)
    overlays.mark_interaction()
    overlays.tag_redraw_all_view3d(
        scene=scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    runtime.request_debug_overlay_refresh(
        context,
        delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        reason="cage_offset_update",
    )
    _request_live_normal_preview_refresh(context, "cage_offset_update")
    _mark_group_projection_dirty(_self, context)


def _projection_static_update(self, context):
    _overlay_static_update(self, context)
    _request_live_normal_preview_refresh(context, "projection_static_update")
    _mark_group_projection_dirty(self, context)


def _projection_static_visibility_update(self, context):
    _overlay_static_visibility_update(self, context)
    _request_live_normal_preview_refresh(context, "projection_static_visibility_update")
    _mark_group_projection_dirty(self, context)


_cage_scope_propagating = False


@contextmanager
def suppress_cage_scope_propagation():
    """Write cage settings on several groups without mirroring each write to siblings."""
    global _cage_scope_propagating
    previous = _cage_scope_propagating
    _cage_scope_propagating = True
    try:
        yield
    finally:
        _cage_scope_propagating = previous


def _propagate_cage_scope(source_group, context, attr: str) -> None:
    """Mirror a cage setting from the edited group to its in-scope siblings.

    The scope (active group / texture set / whole project) is chosen by the user
    in the cage panel header (MasterBakerUiState.cage_settings_scope). A module
    guard stops the siblings' own update callbacks from re-propagating, while
    still letting each sibling run its normal dirty/redraw work.
    """
    global _cage_scope_propagating
    if _cage_scope_propagating:
        return
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None:
        return
    ui_state = scene_ui_state(settings)
    scope = str(getattr(ui_state, "cage_settings_scope", constants.CAGE_SCOPE_BAKE_GROUP) or "")
    project = _active_project_from_context(context)
    if project is None:
        return
    try:
        value = getattr(source_group, attr)
    except Exception:
        return
    if scope == constants.CAGE_SCOPE_BAKE_GROUP:
        targets = dropdown_bake_group_sibling_targets(project, source_group)
    else:
        targets = cage_scope_target_groups(
            project,
            source_group,
            scope,
            selected_objects=getattr(context, "selected_objects", None) or (),
        )
    if not targets:
        return

    _cage_scope_propagating = True
    try:
        for group in targets:
            try:
                if getattr(group, attr) != value:
                    setattr(group, attr, value)
            except Exception:
                pass
    finally:
        _cage_scope_propagating = False


def _object_identity(obj):
    try:
        return obj.as_pointer()
    except Exception:
        return id(obj)


def groups_owning_selected_low_meshes(project, selected_objects) -> list:
    """Bake groups of *project* that own at least one selected low-poly mesh."""
    selected = {_object_identity(obj) for obj in (selected_objects or ()) if obj is not None}
    if not selected:
        return []
    owners = []
    for group in getattr(project, "groups", []):
        role_state = group_role_assignments_state(group)
        for slot in getattr(role_state, "low_meshes", []) or []:
            obj = getattr(slot, "object_ref", None)
            if obj is not None and _object_identity(obj) in selected:
                owners.append(group)
                break
    return owners


def bake_group_target_names(project, settings=None) -> list[str]:
    """Names of the bake groups the header dropdown is editing.

    An empty stored list means the active bake group alone. Shift-click in the
    dropdown stores more than one name, and setting changes apply to each of them.
    """
    groups = list(getattr(project, "groups", []) or [])
    known = {
        str(getattr(group, "name", "") or "").strip()
        for group in groups
        if str(getattr(group, "name", "") or "").strip()
    }
    ui_state = scene_ui_state(settings) if settings is not None else None
    raw = str(getattr(ui_state, "bake_group_targets", "") or "") if ui_state is not None else ""
    names = []
    for part in raw.split("\n"):
        name = part.strip()
        if name and name in known and name not in names:
            names.append(name)
    if names:
        return names
    active = peek_active_group(project) if project is not None else None
    active_name = str(getattr(active, "name", "") or "").strip() if active is not None else ""
    return [active_name] if active_name else []


def set_bake_group_targets(settings, names) -> None:
    ui_state = scene_ui_state(settings) if settings is not None else None
    if ui_state is None or not hasattr(ui_state, "bake_group_targets"):
        return
    cleaned = []
    for name in names or []:
        text = str(name or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    ui_state.bake_group_targets = "\n".join(cleaned)


def resolve_bake_group_target_click(current_names, active_name, clicked_name, *, extend: bool) -> list[str]:
    """Names left selected after a click in the bake-group menu.

    A plain click keeps only the clicked group. Shift-click adds or removes it.
    The last remaining group stays selected.
    """
    clicked = str(clicked_name or "").strip()
    if not clicked:
        return [str(name).strip() for name in (current_names or []) if str(name).strip()]
    if not extend:
        return [clicked]
    names = [str(name).strip() for name in (current_names or []) if str(name).strip()]
    active = str(active_name or "").strip()
    if not names and active:
        names = [active]
    if clicked in names:
        names = [name for name in names if name != clicked]
        return names or [clicked]
    names.append(clicked)
    return names


def dropdown_bake_group_sibling_targets(project, source_group) -> list:
    """Other dropdown-selected groups a Bake Group scoped edit should mirror to."""
    try:
        import bpy

        scene = getattr(getattr(bpy, "context", None), "scene", None)
    except Exception:
        return []
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    if settings is None or project is None or source_group is None:
        return []
    wanted = set(bake_group_target_names(project, settings))
    if len(wanted) < 2:
        return []
    source_ptr = _object_identity(source_group)
    targets = []
    for group in getattr(project, "groups", []) or []:
        name = str(getattr(group, "name", "") or "").strip()
        if name not in wanted or _object_identity(group) == source_ptr:
            continue
        targets.append(group)
    return targets


def cage_scope_target_groups(project, source_group, scope: str, *, selected_objects=()) -> list:
    """Sibling groups a cage-setting edit on *source_group* is mirrored to.

    BAKE_GROUP: none. TEXTURE_SET: the groups sharing its texture set. GLOBAL:
    every other group. SELECTED: every other group that owns a selected low mesh
    (the active group is edited directly whether or not it is selected; nothing
    relevant selected means nothing is mirrored).
    """
    scope = str(scope or "")
    if scope == constants.CAGE_SCOPE_BAKE_GROUP:
        return []
    source_ptr = _object_identity(source_group)
    if scope == constants.CAGE_SCOPE_SELECTED:
        candidates = groups_owning_selected_low_meshes(project, selected_objects)
    else:
        candidates = list(getattr(project, "groups", []))
    source_set = (getattr(source_group, "texture_set_name", "") or "").strip()
    targets = []
    for group in candidates:
        if _object_identity(group) == source_ptr:
            continue
        if scope == constants.CAGE_SCOPE_TEXTURE_SET:
            if (getattr(group, "texture_set_name", "") or "").strip() != source_set:
                continue
        targets.append(group)
    return targets


def _cage_mode_scope_update(self, context):
    _projection_static_visibility_update(self, context)
    _propagate_cage_scope(self, context, "cage_mode")


def _average_normals_scope_update(self, context):
    _projection_static_update(self, context)
    _propagate_cage_scope(self, context, "average_normals")


def _match_by_isolation_scope_update(self, context):
    _projection_static_update(self, context)
    _propagate_cage_scope(self, context, "match_by_isolation")


def _projection_rear_distance_scope_update(self, context):
    _projection_static_update(self, context)
    _propagate_cage_scope(self, context, "projection_rear_distance")


def _cage_offset_scope_update(self, context):
    _cage_offset_update(self, context)
    _propagate_cage_scope(self, context, "cage_offset")


def _cage_coverage_scope_update(self, context):
    # Coverage follows the cage panel's Apply-To scope like every other cage
    # setting: with Texture Set / Global selected, toggling coverage on one
    # group mirrors the flag to its in-scope siblings (each sibling's own
    # update then engages the gate and queues its coverage build). The
    # propagation guard keeps the mirrored writes from re-propagating.
    _cage_coverage_shown_update(self, context)
    _propagate_cage_scope(self, context, "show_cage_coverage")


def _uv_layer_update(self, context):
    project = _active_project_from_context(context)
    if project is not None:
        from . import texture_reprojection
        texture_reprojection.invalidate(project, "Bake UV layer changed; switch Live Reproject on again to re-read the layout")
    _overlay_static_update(self, context)
    _request_live_normal_preview_refresh(context, "uv_layer_update")
    _mark_group_projection_dirty(self, context)


def _mesh_object_pointer_poll(_self, obj):
    return obj is not None and getattr(obj, "type", None) == "MESH"


# ---------------------------------------------------------------------------
# Cage offset (Distance Based): ONE slider that shows and sets the FINAL cage distance
# (group offset + per-mesh offset) of the low meshes the "Apply To" scope covers:
#   Selected     -> the selected low meshes (their per-mesh offsets are set)
#   Bake Group   -> every low mesh of the group owning the viewed mesh
#   Texture Set  -> every low mesh of the groups sharing its texture set
#   Global       -> every low mesh of the project
# For the group scopes the group offset takes the value and the covered per-mesh
# offsets are cleared, so what is dragged is what every covered mesh gets. The two
# stored layers never show in the panel (two raw bars made the artist add them up).
#
# The slider reads the mesh the artist is looking at (the viewport's active object when
# it is a low of this project, else the active group's active low) and edits that one's
# scope. Its range is sized to the value and the mesh: a Blender slider spreads its SOFT
# range over the button (value = soft_min + f * soft_range), and 0..10 m was ~4 cm per
# pixel -- unusable for a 2-3 mm cage on a 20 cm prop.
CAGE_OFFSET_SLIDER_RANGES = (0.01, 0.1, 1.0, 10.0)
_CAGE_OFFSET_RANGE_SUFFIX = {0.01: "r001", 0.1: "r01", 1.0: "r1", 10.0: "r10"}


def resolve_cage_offset_target(project, active_group, active_object=None):
    """(group, low slot) the offset slider reads: the viewport's active low mesh when it
    belongs to *project*, else the active group and its active low slot."""
    if project is not None and active_object is not None and getattr(active_object, "type", None) == "MESH":
        for group in getattr(project, "groups", []) or []:
            role_state = group_role_assignments_state(group)
            for slot in getattr(role_state, "low_meshes", []) or []:
                if getattr(slot, "object_ref", None) == active_object:
                    return group, slot
    if active_group is None:
        return None, None
    return active_group, peek_active_low_slot(active_group)


def focus_cage_offset_target(project, group, slot) -> None:
    """Make *group* the active bake group and *slot* its active low mesh, so the panel
    header and every other cage control agree with the mesh being edited. The flat
    low_mesh_index is the authoritative copy (mirrored into role_assignments)."""
    if project is None or group is None:
        return
    try:
        for index, candidate in enumerate(getattr(project, "groups", []) or []):
            if candidate == group:
                if int(getattr(project, "active_group_index", index)) != index:
                    project.active_group_index = index
                break
        if slot is None:
            return
        role_state = group_role_assignments_state(group)
        for index, candidate in enumerate(getattr(role_state, "low_meshes", []) or []):
            if candidate == slot:
                if hasattr(group, "low_mesh_index") and int(group.low_mesh_index) != index:
                    group.low_mesh_index = index
                if int(getattr(role_state, "low_mesh_index", index)) != index:
                    role_state.low_mesh_index = index
                break
    except (ReferenceError, AttributeError, TypeError):
        return


def _distance_group(group) -> bool:
    return str(getattr(group, "cage_mode", "") or "") == constants.CAGE_MODE_DISTANCE


def _group_low_slots(group) -> list:
    role_state = group_role_assignments_state(group)
    return [slot for slot in (getattr(role_state, "low_meshes", []) or []) if getattr(slot, "object_ref", None) is not None]


def cage_offset_scope_groups(project, anchor_group, scope: str) -> list:
    """Distance-mode groups a group-level scope covers, anchor first."""
    if anchor_group is None:
        return []
    groups = [anchor_group]
    if scope in (constants.CAGE_SCOPE_TEXTURE_SET, constants.CAGE_SCOPE_GLOBAL):
        for group in cage_scope_target_groups(project, anchor_group, scope):
            if _distance_group(group) and not any(existing == group for existing in groups):
                groups.append(group)
    elif scope == constants.CAGE_SCOPE_BAKE_GROUP:
        for group in dropdown_bake_group_sibling_targets(project, anchor_group):
            if _distance_group(group) and not any(existing == group for existing in groups):
                groups.append(group)
    return groups


def cage_offset_scope_slots(project, anchor_group, anchor_slot, scope: str, selected_objects=()) -> list:
    """(group, low slot) pairs the offset slider sets, anchor first."""
    pairs = []

    def add(group, slot):
        if group is None or slot is None:
            return
        if any(g == group and s == slot for g, s in pairs):
            return
        pairs.append((group, slot))

    add(anchor_group, anchor_slot)
    if scope == constants.CAGE_SCOPE_SELECTED:
        selected = [obj for obj in (selected_objects or ()) if obj is not None]
        for group in getattr(project, "groups", []) or []:
            if not _distance_group(group):
                continue
            for slot in _group_low_slots(group):
                if any(slot.object_ref == obj for obj in selected):
                    add(group, slot)
        return pairs
    for group in cage_offset_scope_groups(project, anchor_group, scope):
        for slot in _group_low_slots(group):
            add(group, slot)
    return pairs


def cage_final_offset(group, slot) -> float:
    return max(
        0.0,
        float(getattr(group, "cage_offset", 0.0) or 0.0)
        + (float(getattr(slot, "cage_offset_delta", 0.0) or 0.0) if slot is not None else 0.0),
    )


def cage_offset_scope_mixed(pairs) -> bool:
    return len({round(cage_final_offset(group, slot), 6) for group, slot in pairs}) > 1


def apply_scoped_cage_offset(project, anchor_group, pairs, scope: str, value: float, *, per_pair=None) -> None:
    """Set the final offset of every (group, slot) in *pairs*.

    Selected: per-mesh offsets (delta = value - group offset). Group scopes: the group
    offset takes the value and the covered per-mesh offsets are cleared. *per_pair*
    optionally maps a pair index to its own value (scoped Estimate).
    """
    value = max(0.0, float(value))
    with suppress_cage_scope_propagation():
        if scope == constants.CAGE_SCOPE_SELECTED:
            for index, (group, slot) in enumerate(pairs):
                target = max(0.0, float((per_pair or {}).get(index, value)))
                delta = target - float(getattr(group, "cage_offset", 0.0) or 0.0)
                if float(getattr(slot, "cage_offset_delta", 0.0) or 0.0) != delta:
                    slot.cage_offset_delta = delta
            return
        done = []
        for index, (group, slot) in enumerate(pairs):
            if not any(existing == group for existing in done):
                done.append(group)
                target = max(0.0, float((per_pair or {}).get(index, value)))
                if float(getattr(group, "cage_offset", 0.0) or 0.0) != target:
                    group.cage_offset = target
            if float(getattr(slot, "cage_offset_delta", 0.0) or 0.0) != 0.0:
                slot.cage_offset_delta = 0.0


def cage_offset_scope_from_context(context=None):
    """(project, anchor group, anchor slot, scope, pairs) for the offset slider."""
    context = context if context is not None else getattr(bpy, "context", None)
    scene = getattr(context, "scene", None) if context is not None else None
    project = get_active_project(scene) if scene is not None else None
    if project is None:
        return None, None, None, constants.CAGE_SCOPE_BAKE_GROUP, []
    group, slot = resolve_cage_offset_target(project, get_active_group(project), getattr(context, "active_object", None))
    if group is None or not _distance_group(group):
        return project, group, slot, constants.CAGE_SCOPE_BAKE_GROUP, []
    settings = getattr(scene, "fyr_baker_settings", None)
    ui_state = scene_ui_state(settings) if settings is not None else None
    scope = str(getattr(ui_state, "cage_settings_scope", constants.CAGE_SCOPE_BAKE_GROUP) or constants.CAGE_SCOPE_BAKE_GROUP)
    pairs = cage_offset_scope_slots(project, group, slot, scope, getattr(context, "selected_objects", None) or ())
    return project, group, slot, scope, pairs


def cage_low_size(slot) -> float:
    """Largest world-space dimension of the slot's low mesh (0 when unknown)."""
    obj = getattr(slot, "object_ref", None) if slot is not None else None
    dims = getattr(obj, "dimensions", None) if obj is not None else None
    try:
        return max(abs(float(dims[0])), abs(float(dims[1])), abs(float(dims[2])))
    except Exception:
        return 0.0


def cage_offset_slider_range(value: float, low_size: float) -> float:
    """Smallest decade range holding the value (with headroom) and a quarter of the low size."""
    need = max(abs(float(value)) * 1.25, 0.25 * max(float(low_size), 0.0))
    for candidate in CAGE_OFFSET_SLIDER_RANGES:
        if need <= candidate:
            return candidate
    return CAGE_OFFSET_SLIDER_RANGES[-1]


def cage_offset_proxy_name(value: float, low_size: float) -> str:
    return "cage_offset_final_" + _CAGE_OFFSET_RANGE_SUFFIX[cage_offset_slider_range(value, low_size)]


def _cage_offset_final_get(_self) -> float:
    _project, group, slot, _scope, _pairs = cage_offset_scope_from_context()
    return cage_final_offset(group, slot) if group is not None else 0.0


def _cage_offset_final_set(_self, value: float) -> None:
    project, group, slot, scope, pairs = cage_offset_scope_from_context()
    if group is None or not pairs:
        return
    focus_cage_offset_target(project, group, slot)
    apply_scoped_cage_offset(project, group, pairs, scope, value)


def _cage_offset_proxy(span: float):
    return bpy.props.FloatProperty(
        name="Offset",
        default=0.0,
        precision=5,
        step=1,
        min=0.0,
        max=100.0,
        soft_min=0.0,
        soft_max=span,
        subtype="DISTANCE",
        description=(
            "Final Distance Based cage offset. Applies to what Apply To covers: the selected "
            "low meshes, the bake group, its texture set, or every bake group"
        ),
        get=_cage_offset_final_get,
        set=_cage_offset_final_set,
        options={"HIDDEN", "SKIP_SAVE"},
    )


def _selected_low_cage_offset_get(_self) -> float:
    try:
        from . import cage_session

        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None) if context is not None else None
        return float(cage_session.selected_low_offset_value(scene, context=context))
    except Exception:
        return 0.0


def _tag_selected_cage_offset_redraw(context, *, dirty_groups: list[object], reason: str) -> None:
    from . import overlays
    from . import runtime

    scene = getattr(context, "scene", None)
    overlays.mark_interaction()
    overlays.tag_redraw_all_view3d(
        scene=scene,
        window=getattr(context, "window", None),
        sync_preview=False,
    )
    runtime.request_debug_overlay_refresh(
        context,
        delay_seconds=constants.VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS,
        reason=reason,
    )
    _request_live_normal_preview_refresh(context, reason)
    for dirty_group in dirty_groups:
        _mark_group_projection_dirty(dirty_group, context)


def _selected_group_cage_offset_get(_self) -> float:
    try:
        from . import cage_session

        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None) if context is not None else None
        return float(cage_session.selected_group_offset_value(scene, context=context))
    except Exception:
        return 0.0


def _selected_group_cage_offset_set(_self, value: float) -> None:
    try:
        from . import cage_session

        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None) if context is not None else None
        dirty_groups: list[object] = []
        new_value = max(0.0, float(value))
        for target_group in cage_session.selected_low_target_groups(scene, context=context):
            if float(getattr(target_group, "cage_offset", 0.0) or 0.0) == new_value:
                continue
            target_group.cage_offset = new_value
            dirty_groups.append(target_group)
        if context is not None and dirty_groups:
            _tag_selected_cage_offset_redraw(
                context,
                dirty_groups=dirty_groups,
                reason="selected_group_cage_offset_set",
            )
    except Exception:
        return


def _selected_low_cage_offset_set(_self, value: float) -> None:
    try:
        from . import cage_session

        context = getattr(bpy, "context", None)
        scene = getattr(context, "scene", None) if context is not None else None
        dirty_groups: list[object] = []
        requested_offset = max(0.0, float(value))
        for target in cage_session.resolve_selected_low_slot_targets(scene, context=context):
            new_delta = requested_offset - float(getattr(target.group, "cage_offset", 0.0) or 0.0)
            current_value = float(getattr(target.slot, "cage_offset_delta", 0.0) or 0.0)
            if current_value == new_delta:
                continue
            target.slot.cage_offset_delta = new_delta
            if not any(existing == target.group for existing in dirty_groups):
                dirty_groups.append(target.group)
        if context is not None and dirty_groups:
            _tag_selected_cage_offset_redraw(
                context,
                dirty_groups=dirty_groups,
                reason="selected_low_cage_offset_set",
            )
    except Exception:
        return


def _custom_cage_update(self, context):
    if getattr(self, "custom_cage", None) is not None:
        self.cage_mode = constants.CAGE_MODE_CUSTOM
    _refresh_dirty_tracker_membership(context)
    _projection_static_visibility_update(self, context)


def _normal_preview_config_update(self, context):
    _map_setting_update(self, context)
    if str(getattr(self, "map_type", "") or "").strip().upper() != constants.MAP_NORMAL:
        return
    _request_live_normal_preview_refresh(context, "normal_preview_config_update")


def _normal_format_update(self, context):
    # normal_format is the source of truth for Normal rows; flip_green is a hidden
    # legacy mirror that map_flip_green() already derives from it. Keep the stored
    # pair consistent so serialized state (job, presets, support bundle) cannot
    # disagree with the enum the user actually set.
    normal_format = str(getattr(self, "normal_format", "") or "").strip().upper()
    desired_flip = normal_format == constants.NORMAL_FORMAT_DIRECTX
    if bool(getattr(self, "flip_green", False)) != desired_flip:
        try:
            self.flip_green = desired_flip
        except (AttributeError, TypeError, ValueError):
            pass
    # The Output panel surfaces this as ONE project-wide "Normal Format" choice, yet the
    # value lives per row and duplicate Normal rows are supported. Mirror the pick
    # to every other Normal row of the project so no row keeps the old convention.
    if str(getattr(self, "map_type", "") or "").strip().upper() == constants.MAP_NORMAL:
        project = _active_project_from_context(context)
        for sibling in getattr(project, "maps", []) if project is not None else []:
            if _same_rna_struct(sibling, self) or getattr(sibling, "is_add_phantom", False):
                continue
            if str(getattr(sibling, "map_type", "") or "").strip().upper() != constants.MAP_NORMAL:
                continue
            if str(getattr(sibling, "normal_format", "") or "").strip().upper() != normal_format:
                try:
                    sibling.normal_format = normal_format
                except (AttributeError, TypeError, ValueError):
                    pass
    _normal_preview_config_update(self, context)


def _rename_seed_texture_set(project, prev_name: str, new_name: str) -> None:
    """Keep the auto-seeded, project-named texture set following a project rename.

    create_default_project seeds a texture set named after the project so the first
    Add Group / COMBINED auto-build joins a real set. That seed's name is otherwise
    frozen at creation, so renaming the project before building would strand it as an
    empty duplicate once COMBINED auto-build links the groups to the NEW project name
    (`_apply_auto_texture_set_mode`). We locate the set still carrying the OLD project
    name and rename it, which fires `_texture_set_identity_rename` to rewrite any group
    links old -> new. A set the user deliberately renamed no longer matches prev_name,
    so it is left alone, and we skip if a set already carries the new name.
    """
    prev = (prev_name or "").strip()
    new = (new_name or "").strip()
    if not prev or not new or prev == new:
        return
    seed = find_texture_set(project, prev)
    if seed is None or find_texture_set(project, new) is not None:
        return
    try:
        seed.name = new
    except (ReferenceError, AttributeError):
        pass


def _project_name_update(self, _context):
    new_name = (getattr(self, "name", "") or "").strip() or "BakeProject"
    prev_name = str(self.get("_identity_name", "") or "")
    if prev_name != new_name:
        _rename_seed_texture_set(self, prev_name, new_name)
        self["_identity_name"] = new_name
    collection = getattr(self, "root_collection", None)
    if collection is None:
        _mark_project_dirty(_context, project=self)
        return
    try:
        collection.name = (getattr(self, "name", "") or "").strip() or "BakeProject"
    except ReferenceError:
        _mark_project_dirty(_context, project=self)
        return
    _mark_project_dirty(_context, project=self)


def _group_name_update(self, _context):
    base_name = (getattr(self, "name", "") or "").strip() or "BakeGroup"
    collections_state = group_collections_state(self)
    group_collection = getattr(collections_state, "group_collection", None)
    if group_collection is not None:
        try:
            group_collection.name = base_name
        except ReferenceError:
            pass
    low_collection = getattr(collections_state, "low_collection", None)
    if low_collection is not None:
        try:
            low_collection.name = f"{base_name}_Low"
        except ReferenceError:
            pass
    high_collection = getattr(collections_state, "high_collection", None)
    if high_collection is not None:
        try:
            high_collection.name = f"{base_name}_High"
        except ReferenceError:
            pass
    cage_collection = getattr(collections_state, "cage_collection", None)
    if cage_collection is not None:
        try:
            cage_collection.name = f"{base_name}_Cage"
        except ReferenceError:
            pass
    _group_collection_metadata_update(self, _context)
    _refresh_dirty_tracker_membership(_context)
    _mark_group_all_maps_dirty(self, _context)


def _ui_name_get(self):
    return str(getattr(self, "name", "") or "")


def _project_ui_name_set(self, value):
    # PropertyGroup.name is a built-in and ignores a subclass description, so the
    # N-panel field is this proxy. Writing name still runs the rename side effects.
    self.name = value
    _project_name_update(self, bpy.context)


def _group_ui_name_set(self, value):
    previous = str(getattr(self, "name", "") or "")
    self.name = value
    _group_name_update(self, bpy.context)
    _follow_group_rename(self, previous, str(getattr(self, "name", "") or ""))


def _follow_group_rename(group, previous: str, name: str) -> None:
    """Carry an artist's rename into the places that remember a group by name.

    The header dropdown's multi-selection and the role tags on the group's own
    meshes store the name string; without this a renamed group dropped out of the
    selection and Auto-Build regrouped its meshes under the old name.
    """
    if not previous or previous == name:
        return
    try:
        settings = getattr(getattr(bpy.context, "scene", None), "fyr_baker_settings", None)
    except Exception:
        settings = None
    ui_state = scene_ui_state(settings) if settings is not None else None
    raw = str(getattr(ui_state, "bake_group_targets", "") or "") if ui_state is not None else ""
    if raw:
        parts = raw.split("\n")
        if previous in (part.strip() for part in parts):
            set_bake_group_targets(settings, [name if part.strip() == previous else part for part in parts])
    from . import tagging

    role_state = group_role_assignments_state(group)
    objects = [
        getattr(slot, "object_ref", None)
        for attr in ("low_meshes", "high_meshes")
        for slot in getattr(role_state, attr, None) or []
    ]
    objects.append(getattr(group, "custom_cage", None))
    for obj in objects:
        if obj is None:
            continue
        try:
            tagging.rename_group_tag(obj, previous, name)
        except (AttributeError, ReferenceError, TypeError):
            pass


def _texture_set_ui_name_set(self, value):
    self.name = value
    _texture_set_identity_rename(self, bpy.context)


def _group_collection_metadata_update(self, _context):
    _sync_group_metadata_state(self)
    collection = getattr(group_collections_state(self), "group_collection", None)
    if collection is None:
        return
    try:
        from . import tagging
        metadata_state = group_metadata_state(self)

        tagging.set_metadata_names(
            collection,
            group_name=(getattr(metadata_state, "texture_set_name", "") or "").strip() or (getattr(metadata_state, "name", "") or "").strip() or None,
            collection_name=(getattr(metadata_state, "id_collection_name", "") or "").strip() or (getattr(metadata_state, "name", "") or "").strip() or None,
        )
    except ReferenceError:
        return


_GROUP_METADATA_ATTRS = (
    "name",
    "texture_set_name",
    "id_collection_name",
    "id_color_set_name",
)


_GROUP_COLLECTION_POINTER_ATTRS = (
    "group_collection",
    "low_collection",
    "high_collection",
    "cage_collection",
)

_GROUP_ROLE_ASSIGNMENT_ATTRS = (
    "low_meshes",
    "low_mesh_index",
    "high_meshes",
    "high_mesh_index",
    "use_low_as_high",
)

_GROUP_PROJECTION_ATTRS = (
    "uv_layer_name",
    "cage_mode",
    "custom_cage",
    "cage_offset",
    "projection_rear_distance",
    "average_normals",
    "ignore_backface",
    "match_by_isolation",
)

_GROUP_PAINT_PROJECTION_ATTRS = (
    "paint_offset_image",
    "paint_offset_scale",
    "paint_skew_image",
    "paint_skew",
)

_MAP_NORMAL_SETTING_ATTRS = (
    "normal_space",
    "normal_format",
    "flip_green",
)

_MAP_AO_SETTING_ATTRS = (
    "ao_mode",
    "ao_distance",
    "ao_min_distance",
    "ao_two_sided",
    "ao_ignore_groups",
    "ao_occlude_other_groups",
    "ao_bevel_normal",
    "ao_cavity_weight",
    "ao_relative_to_bounding_box",
    "ao_spread_angle",
    "ao_distribution",
    "ao_ignore_backface",
    "ao_self_occlusion",
    "ao_attenuation",
    "ao_output_min",
    "ao_output_max",
    "ao_use_ground_plane",
    "ao_diffusion_quality",
    "ao_diffusion_clearance_scale",
    "ao_diffusion_clearance_exponent",
)

_MAP_ENV_LIGHT_SETTING_ATTRS = (
    "env_light_intensity",
    "env_light_occlusion_strength",
    "env_light_contrast",
    "env_light_up_axis",
    "env_light_sky_color",
    "env_light_ground_color",
)

# Self Intersection scope of the curvature probe rays (MBBJOB33). The item ORDER is
# Painter's dropdown order; the explicit VALUES are not sequential on purpose: before
# MBBJOB33 this property name held the fold-detection BOOL, and every saved row stores
# it as the integer 0 (or 1). An enum reads that stored integer back by value, so GROUP
# (the pre-MBBJOB33 behaviour) must own value 0 or every legacy row would silently open
# as "Never" and bake flat. See _migrate_legacy_curvature_probe_fields for the 1 case.
_CURVATURE_SELF_INTERSECTION_ITEMS = (
    ("NEVER", "Never", "Probe rays ignore the high-poly mesh matched to this low-poly mesh; only other meshes contribute", "", 3),
    ("SAME_MESH", "Only Same Mesh Name", "Probe rays only hit the high-poly mesh matched to this low-poly mesh by name, like AO's Same Mesh Only", "", 1),
    ("GROUP", "Same Group", "Probe rays hit every high-poly mesh in this bake group (default)", "", 0),
    ("ALL_GROUPS", "Always", "Probe rays hit the high-poly meshes of every bake group in the scene, like AO's Occlude Other Groups. Reaches other groups only when an AO map bakes in the same run; otherwise it behaves like Same Group", "", 2),
)

_MAP_CURVATURE_SETTING_ATTRS = (
    "curvature_scale",
    "curvature_tonemapping_min",
    "curvature_tonemapping_max",
    "curvature_distance",
    "curvature_relative_to_bounding_box",
    "curvature_secondary_rays",
    "curvature_detect_folds",
    "curvature_self_intersection",
    "curvature_auto_tonemapping",
    "curvature_value_min",
    "curvature_value_max",
    "curvature_method",
    "curvature_soften",
    "curvature_output_mode",
)

_MAP_THICKNESS_SETTING_ATTRS = (
    "thickness_distance",
    "thickness_dither",
    "thickness_scale",
    "thickness_min_distance",
    "thickness_gamma",
    "thickness_ignore_groups",
    "thickness_normalization",
    "thickness_log_response",
)

_MAP_DENSITY_SETTING_ATTRS = (
    "thickness_distance",
    "thickness_scale",
    "thickness_gamma",
    "thickness_ignore_groups",
    "density_auto_levels",
    "density_auto_levels_per_group",
)

_MAP_ID_SETTING_ATTRS = ("id_source",)

_MAP_POSITION_SETTING_ATTRS = (
    "position_normalization",
    "position_mode",
    "position_axis",
    "relative_to_bounding_box",
)

_MAP_HEIGHT_SETTING_ATTRS = (
    "height_inner_distance",
    "height_outer_distance",
    "height_dither",
)


def _supports_group_state_sync(group) -> bool:
    return (
        callable(getattr(group, "as_pointer", None))
        or hasattr(group, "bl_rna")
        or hasattr(group, "id_data")
    )


def _sync_group_metadata_state(group) -> None:
    nested_state = getattr(group, "metadata", None)
    if nested_state is None:
        return
    if not _supports_group_state_sync(group):
        return
    if not all(hasattr(group, attr_name) for attr_name in _GROUP_METADATA_ATTRS):
        return
    for attr_name in _GROUP_METADATA_ATTRS:
        try:
            value = getattr(group, attr_name, "")
            if getattr(nested_state, attr_name, "") != value:
                setattr(nested_state, attr_name, value)
        except (ReferenceError, AttributeError):
            return


def _sync_group_collections_state(group) -> None:
    nested_state = getattr(group, "collections", None)
    if nested_state is None:
        return
    if not _supports_group_state_sync(group):
        return
    if not all(hasattr(group, attr_name) for attr_name in _GROUP_COLLECTION_POINTER_ATTRS):
        return
    for attr_name in _GROUP_COLLECTION_POINTER_ATTRS:
        try:
            flat_value = getattr(group, attr_name, None)
            nested_value = getattr(nested_state, attr_name, None)
            if flat_value == nested_value:
                continue
            if nested_value is not None:
                # Nested is authoritative — ensure_child_collection writes here.
                # Keep flat alias in sync with nested so UI bindings see the value.
                setattr(group, attr_name, nested_value)
            else:
                # Only flat has a value: legacy migration (old save without nested state).
                setattr(nested_state, attr_name, flat_value)
        except (ReferenceError, AttributeError):
            return


def _sync_group_role_assignments_state(group) -> None:
    nested_state = getattr(group, "role_assignments", None)
    if nested_state is None:
        return
    if not _supports_group_state_sync(group):
        return
    if not all(hasattr(group, attr_name) for attr_name in _GROUP_ROLE_ASSIGNMENT_ATTRS[:4]):
        return
    _sync_group_role_assignments_from_flat(group, force=False)


def _adopt_stored_legacy_cage_mode(group, nested_state) -> None:
    # The flat cage_mode default used to be DISTANCE, so a group saved on it stored nothing
    # flat while the sync below stored DISTANCE nested. Read under the AUTOMATIC default,
    # that group would flip its saved cage; pin the flat value to the stored nested one.
    # Both enums share CAGE_MODE_ITEMS, so the raw stored index copies over as-is, and
    # the raw write skips the update callback (no cage-scope propagation on file load).
    try:
        if group.is_property_set("cage_mode") or not nested_state.is_property_set("cage_mode"):
            return
        group["cage_mode"] = nested_state["cage_mode"]
    except (AttributeError, KeyError, ReferenceError, TypeError):
        return


def _sync_group_projection_state(group) -> None:
    nested_state = getattr(group, "projection_settings", None)
    if nested_state is None:
        return
    if not _supports_group_state_sync(group):
        return
    if not all(hasattr(group, attr_name) for attr_name in _GROUP_PROJECTION_ATTRS):
        return
    _adopt_stored_legacy_cage_mode(group, nested_state)
    for attr_name in _GROUP_PROJECTION_ATTRS:
        try:
            value = getattr(group, attr_name, None)
            if getattr(nested_state, attr_name, None) != value:
                setattr(nested_state, attr_name, value)
        except (ReferenceError, AttributeError):
            return


def _sync_group_paint_projection_state(group) -> None:
    nested_state = getattr(group, "paint_projection_settings", None)
    if nested_state is None:
        return
    if not _supports_group_state_sync(group):
        return
    if not all(hasattr(group, attr_name) for attr_name in _GROUP_PAINT_PROJECTION_ATTRS):
        return
    for attr_name in _GROUP_PAINT_PROJECTION_ATTRS:
        try:
            value = getattr(group, attr_name, None)
            if getattr(nested_state, attr_name, None) != value:
                setattr(nested_state, attr_name, value)
        except (ReferenceError, AttributeError):
            return


def _sync_map_setting_family(map_item, subgroup_attr: str, attrs: tuple) -> None:
    nested = getattr(map_item, subgroup_attr, None)
    if nested is None:
        return
    for attr in attrs:
        if not hasattr(nested, attr):
            # thickness_dither lives on the row only; returning on the first
            # missing attribute used to skip every attribute after it.
            continue
        try:
            value = getattr(map_item, attr, None)
            if value is None:
                continue
            existing = getattr(nested, attr, None)
            if existing != value:
                setattr(nested, attr, value)
        except (AttributeError, ReferenceError):
            continue


def _sync_map_normal_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "normal_settings", _MAP_NORMAL_SETTING_ATTRS)


def _sync_map_ao_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "ao_settings", _MAP_AO_SETTING_ATTRS)


def _sync_map_env_light_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "env_light_settings", _MAP_ENV_LIGHT_SETTING_ATTRS)


def _sync_map_curvature_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "curvature_settings", _MAP_CURVATURE_SETTING_ATTRS)


def _sync_map_thickness_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "thickness_settings", _MAP_THICKNESS_SETTING_ATTRS)


def _sync_map_density_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "thickness_settings", _MAP_DENSITY_SETTING_ATTRS)


def _sync_map_id_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "id_settings", _MAP_ID_SETTING_ATTRS)


def _sync_map_position_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "position_settings", _MAP_POSITION_SETTING_ATTRS)


def _sync_map_height_settings(map_item) -> None:
    _sync_map_setting_family(map_item, "height_settings", _MAP_HEIGHT_SETTING_ATTRS)


def _copy_slot_collection_items(source_collection, target_collection) -> None:
    if source_collection is target_collection or target_collection is None:
        return
    # This is a flat->nested mirror, not a membership change: the flat side already
    # fired its own update. Each nested item.object_ref write would otherwise fire
    # _group_membership_update, whose preview-visibility sync reads
    # group_role_assignments_state on the same group while the copy is half done,
    # re-triggering this sync and recursing forever (hard hang: restore/preset load).
    with suspend_group_membership_updates():
        # The per-mesh Object Offset is edited on the NESTED slot (the UI reads
        # role_assignments), while the flat slot keeps its default 0. Every file load
        # force-mirrors flat -> nested, which wiped the user's offsets on reopen. Keep a
        # nested delta whenever the flat slot for the same object carries none.
        kept_deltas = []
        # Casts AO is edited on the nested slot too; an "off" there survives the mirror.
        kept_non_casters = []
        for existing in target_collection or []:
            existing_delta = float(getattr(existing, "cage_offset_delta", 0.0) or 0.0)
            if existing_delta != 0.0:
                kept_deltas.append((getattr(existing, "object_ref", None), existing_delta))
            if not bool(getattr(existing, "casts_ao", True)) and getattr(existing, "object_ref", None) is not None:
                kept_non_casters.append(getattr(existing, "object_ref", None))
        if hasattr(target_collection, "clear"):
            target_collection.clear()
        else:
            while target_collection:
                target_collection.pop()
        seen_refs = []
        for source in source_collection or []:
            source_ref = getattr(source, "object_ref", None)
            # Skip duplicate object references so a drifted source (e.g. slots that
            # accumulated the same mesh twice from an older duplicate-project bug)
            # does not propagate the duplication into the synced copy.
            if source_ref is not None and any(existing == source_ref for existing in seen_refs):
                continue
            seen_refs.append(source_ref)
            item = target_collection.add() if hasattr(target_collection, "add") else types.SimpleNamespace()
            if not hasattr(target_collection, "add"):
                target_collection.append(item)
            item.object_ref = source_ref
            source_delta = float(getattr(source, "cage_offset_delta", 0.0) or 0.0)
            if source_delta == 0.0 and source_ref is not None:
                for kept_ref, kept_delta in kept_deltas:
                    if kept_ref == source_ref:
                        source_delta = kept_delta
                        break
            item.cage_offset_delta = source_delta
            casts_ao = bool(getattr(source, "casts_ao", True)) and not any(
                kept_ref == source_ref for kept_ref in kept_non_casters
            )
            # Assign only a change: the update callback re-arms prepare and dirties AO rows.
            if bool(getattr(item, "casts_ao", True)) != casts_ao:
                item.casts_ao = casts_ao


def _slot_collection_object_refs(collection) -> list:
    refs = []
    for slot in collection or []:
        refs.append(getattr(slot, "object_ref", None))
    return refs


def _slot_collections_match(source_collection, target_collection) -> bool:
    source_refs = _slot_collection_object_refs(source_collection)
    target_refs = _slot_collection_object_refs(target_collection)
    if len(source_refs) != len(target_refs):
        return False
    return all(a == b for a, b in zip(source_refs, target_refs))


def _dedupe_slot_collection_in_place(collection) -> bool:
    """Drop slots whose object_ref repeats an earlier slot, keeping the first.

    Heals slot lists that an older duplicate-project bug left with the same mesh
    listed more than once. Returns True when anything was removed.
    """
    if collection is None:
        return False
    try:
        length = len(collection)
    except TypeError:
        return False
    seen_refs = []
    duplicate_indices = []
    for index in range(length):
        ref = getattr(collection[index], "object_ref", None)
        if ref is not None and any(existing == ref for existing in seen_refs):
            duplicate_indices.append(index)
        else:
            seen_refs.append(ref)
    if not duplicate_indices:
        return False
    remove = getattr(collection, "remove", None)
    if not callable(remove):
        return False
    for index in reversed(duplicate_indices):
        remove(index)
    return True


def _collection_is_empty(collection) -> bool:
    if collection is None:
        return True
    try:
        return len(collection) <= 0
    except TypeError:
        for _item in collection:
            return False
    return True


def _should_sync_slot_collection_from_flat(source_collection, target_collection, *, force: bool) -> bool:
    if source_collection is target_collection or target_collection is None:
        return False
    if force:
        return True
    # The flat list is only authoritative once populated; never clobber an existing
    # nested copy from an empty flat list.
    if _collection_is_empty(source_collection):
        return False
    # Re-sync when the nested copy is missing entirely, or when it has drifted from
    # the flat (authoritative) list — e.g. accumulated duplicate slots.
    return _collection_is_empty(target_collection) or not _slot_collections_match(source_collection, target_collection)


_ROLE_ASSIGNMENT_SYNC_GUARD: set[int] = set()


def _sync_group_role_assignments_from_flat(group, *, force: bool = False) -> None:
    nested_state = getattr(group, "role_assignments", None)
    if nested_state is None:
        return
    if not _supports_group_state_sync(group):
        return
    if not all(hasattr(group, attr_name) for attr_name in _GROUP_ROLE_ASSIGNMENT_ATTRS[:4]):
        return
    # Update callbacks fired by the mirror below can read
    # group_role_assignments_state on this same group; a re-entrant sync would see
    # the half-copied nested list as drift and restart the copy forever.
    guard_key = _resolution_owner_key(group)
    if guard_key in _ROLE_ASSIGNMENT_SYNC_GUARD:
        return
    _ROLE_ASSIGNMENT_SYNC_GUARD.add(guard_key)
    try:
        # Heal duplicate slots an older duplicate-project bug may have left in the
        # authoritative flat lists before mirroring them into the nested state.
        _dedupe_slot_collection_in_place(getattr(group, "low_meshes", None))
        _dedupe_slot_collection_in_place(getattr(group, "high_meshes", None))
        low_source = getattr(group, "low_meshes", [])
        low_target = getattr(nested_state, "low_meshes", None)
        if _should_sync_slot_collection_from_flat(low_source, low_target, force=force):
            _copy_slot_collection_items(low_source, low_target)

        high_source = getattr(group, "high_meshes", [])
        high_target = getattr(nested_state, "high_meshes", None)
        if _should_sync_slot_collection_from_flat(high_source, high_target, force=force):
            _copy_slot_collection_items(high_source, high_target)

        for attr_name in ("low_mesh_index", "high_mesh_index", "use_low_as_high"):
            try:
                default_value = False if attr_name == "use_low_as_high" else 0
                raw_value = getattr(group, attr_name, default_value)
                value = bool(raw_value) if attr_name == "use_low_as_high" else int(raw_value)
                if getattr(nested_state, attr_name, default_value) != value:
                    setattr(nested_state, attr_name, value)
            except (ReferenceError, AttributeError):
                return
    finally:
        _ROLE_ASSIGNMENT_SYNC_GUARD.discard(guard_key)


_RESOLUTION_SYNC_GUARD: set[int] = set()


def _resolution_owner_key(owner) -> int:
    as_pointer = getattr(owner, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(owner)


def _resolution_preset_update(self, _context):
    key = _resolution_owner_key(self)
    if key in _RESOLUTION_SYNC_GUARD:
        return
    target_size = constants.OUTPUT_SIZE_DIMENSIONS.get(getattr(self, "resolution_preset", constants.OUTPUT_SIZE_CUSTOM))
    if target_size is None:
        return
    changed = False
    _RESOLUTION_SYNC_GUARD.add(key)
    try:
        if int(getattr(self, "resolution_x", 0)) != int(target_size):
            self.resolution_x = int(target_size)
            changed = True
        if int(getattr(self, "resolution_y", 0)) != int(target_size):
            self.resolution_y = int(target_size)
            changed = True
    finally:
        _RESOLUTION_SYNC_GUARD.discard(key)
    if not changed:
        return
    # The guard silences _resolution_x/_y_update's side effects for the writes
    # above, so a preset pick has to carry them itself: without these the next
    # bake could serve the cached outputs at the old size and pay a cold prepare.
    _request_live_normal_preview_refresh(_context, "resolution_preset_update")
    _mark_project_dirty(_context, project=self)
    _schedule_settings_prepare()


def _update_resolution_preset_from_dimensions(self) -> None:
    preset = constants.output_size_preset_from_dimensions(
        int(getattr(self, "resolution_x", constants.DEFAULT_RESOLUTION)),
        int(getattr(self, "resolution_y", constants.DEFAULT_RESOLUTION)),
    )
    if getattr(self, "resolution_preset", constants.OUTPUT_SIZE_CUSTOM) == preset:
        return
    self.resolution_preset = preset


def _resolution_x_update(self, _context):
    key = _resolution_owner_key(self)
    if key in _RESOLUTION_SYNC_GUARD:
        return
    _RESOLUTION_SYNC_GUARD.add(key)
    try:
        if bool(getattr(self, "lock_resolution", True)):
            target_width = int(getattr(self, "resolution_x", constants.DEFAULT_RESOLUTION))
            if int(getattr(self, "resolution_y", 0)) != target_width:
                self.resolution_y = target_width
        _update_resolution_preset_from_dimensions(self)
    finally:
        _RESOLUTION_SYNC_GUARD.discard(key)
    _request_live_normal_preview_refresh(_context, "resolution_x_update")
    _mark_project_dirty(_context, project=self)
    _schedule_settings_prepare()


def _resolution_y_update(self, _context):
    key = _resolution_owner_key(self)
    if key in _RESOLUTION_SYNC_GUARD:
        return
    _RESOLUTION_SYNC_GUARD.add(key)
    try:
        if bool(getattr(self, "lock_resolution", True)):
            target_width = int(getattr(self, "resolution_x", constants.DEFAULT_RESOLUTION))
            if int(getattr(self, "resolution_y", 0)) != target_width:
                self.resolution_y = target_width
        _update_resolution_preset_from_dimensions(self)
    finally:
        _RESOLUTION_SYNC_GUARD.discard(key)
    _request_live_normal_preview_refresh(_context, "resolution_y_update")
    _mark_project_dirty(_context, project=self)
    _schedule_settings_prepare()


def _resolution_lock_update(self, _context):
    key = _resolution_owner_key(self)
    if key in _RESOLUTION_SYNC_GUARD:
        return
    _RESOLUTION_SYNC_GUARD.add(key)
    try:
        if bool(getattr(self, "lock_resolution", True)):
            target_width = int(getattr(self, "resolution_x", constants.DEFAULT_RESOLUTION))
            if int(getattr(self, "resolution_y", 0)) != target_width:
                self.resolution_y = target_width
        _update_resolution_preset_from_dimensions(self)
    finally:
        _RESOLUTION_SYNC_GUARD.discard(key)
    _request_live_normal_preview_refresh(_context, "resolution_lock_update")
    _mark_project_dirty(_context, project=self)
    # Locking can change resolution_y, which invalidates the prepared job like
    # the X/Y/preset callbacks do; they all re-prewarm, this one did not.
    _schedule_settings_prepare()


def _project_live_normal_preview_update(_self, context):
    _request_live_normal_preview_refresh(context, "project_live_normal_preview_update")


def _slot_pointer(slot) -> int:
    try:
        return int(slot.as_pointer())
    except Exception:
        return id(slot)


def _slot_casts_ao_update(self, context):
    project = _active_project_from_context(context)
    if project is not None:
        # The UI edits the nested role_assignments slot while file loads mirror the flat
        # slot over it, so keep both copies of this mesh's slot in step.
        own = _slot_pointer(self)
        obj = getattr(self, "object_ref", None)
        value = bool(getattr(self, "casts_ao", True))
        for group in getattr(project, "groups", []):
            role_state = getattr(group, "role_assignments", None)
            collections = (getattr(group, "high_meshes", None), getattr(role_state, "high_meshes", None))
            if not any(_slot_pointer(slot) == own for collection in collections for slot in (collection or [])):
                continue
            for collection in collections:
                for slot in collection or []:
                    if (
                        _slot_pointer(slot) != own
                        and obj is not None
                        and getattr(slot, "object_ref", None) == obj
                        and bool(getattr(slot, "casts_ao", True)) != value
                    ):
                        slot.casts_ao = value
        # Every group: with Occlude Other Groups a mesh shadows other groups' AO as well.
        _mark_project_dirty(context, project=project, map_types=set(constants.AO_OCCLUDER_MAP_TYPES))
    _trigger_activity_rewarm(context, reason="casts_ao_changed")
    _schedule_settings_prepare()


class MasterBakerObjectSlot(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(name="Object", type=bpy.types.Object, update=_group_membership_update)
    casts_ao: bpy.props.BoolProperty(
        name="Casts AO",
        default=True,
        description=(
            "Let this high-poly mesh shadow other meshes in Ambient Occlusion, Bent Normal, Cavity "
            "and Environment Light. Turn it off for floating details such as bolts, buttons and "
            "panels so they leave no dark outline on the surface beneath. The mesh still projects "
            "into every map and still shadows itself"
        ),
        update=_slot_casts_ao_update,
    )
    cage_offset_delta: bpy.props.FloatProperty(
        name="Per-Mesh Offset",
        default=0.0,
        precision=5,
        step=1,
        soft_min=-1.0,
        soft_max=1.0,
        subtype="DISTANCE",
        description="Add an extra Distance Based cage offset to this low-poly mesh on top of the bake group's base offset",
        update=_cage_offset_update,
    )


class MasterBakerMapNormalSettings(bpy.types.PropertyGroup):
    normal_space: bpy.props.EnumProperty(
        name="Normal Space",
        items=constants.MAP_NORMAL_SPACE_ITEMS,
        default=constants.MAP_NORMAL_SPACE_TANGENT,
    )
    normal_format: bpy.props.EnumProperty(
        name="Normal Format",
        items=constants.NORMAL_FORMAT_ITEMS,
        default=constants.NORMAL_FORMAT_OPENGL,
    )
    flip_green: bpy.props.BoolProperty(
        name="Flip Green",
        default=False,
        description="Invert the green channel for normal output",
        options={"HIDDEN"},
    )


class MasterBakerMapAOSettings(bpy.types.PropertyGroup):
    ao_mode: bpy.props.EnumProperty(
        name="Method",
        items=constants.MAP_AO_MODE_ITEMS,
        default=constants.MAP_AO_MODE_RAYCAST,
    )
    ao_distance: bpy.props.FloatProperty(
        name="AO Distance",
        # 0 = unlimited: occlusion accumulates from the whole scene like other
        # bakers' defaults, so wide crevices shade instead of reading white.
        default=0.0,
        min=0.0,
        soft_max=10.0,
        description="Set the maximum ray distance for AO and bent normals. 0 = unlimited, which darkens wider, deeper creases. With Relative to Bounds enabled, a non-zero value is a fraction of model size",
    )
    ao_min_distance: bpy.props.FloatProperty(
        name="Min Distance",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        description="Ignore AO and bent-normal occluders closer than this distance. 0 = no minimum, so nearby hits count. With Relative to Bounds enabled, a non-zero value is a fraction of model size",
    )
    ao_two_sided: bpy.props.BoolProperty(
        name="Two-Sided",
        default=False,
        description="Include high-poly backfaces when calculating AO and bent normals",
    )
    ao_ignore_groups: bpy.props.BoolProperty(
        name="Same Mesh Only",
        default=False,
        description="Only let AO and bent-normal rays hit the high-poly mesh matched to the current low-poly mesh",
    )
    ao_occlude_other_groups: bpy.props.BoolProperty(
        name="Occlude Other Groups",
        default=False,
        description="Let this map's rays hit the high-poly meshes of other bake groups (AO and Bent Normal: the whole scene; Thickness and Density: the same texture set). Same Mesh Only still applies on top",
    )
    ao_bevel_normal: bpy.props.EnumProperty(
        name="Use Bevel Normal",
        items=(
            (
                constants.AO_BEVEL_NORMAL_AUTO,
                "Auto",
                "A Bevel shader shades convex edges from the bevel normal; other materials stay geometric",
            ),
            (constants.AO_BEVEL_NORMAL_OFF, "Off", "AO from the geometry only"),
            (
                constants.AO_BEVEL_NORMAL_CONVEX,
                "Convex Edges",
                "Bevelled convex edges shade from the bevel normal; concave fillets keep the geometric normal so crevices stay dark (ZenBBQ's AO)",
            ),
            (
                constants.AO_BEVEL_NORMAL_ALL,
                "All Edges",
                "Every bevelled edge shades from the bevel normal, like Cycles' AO node fed a Bevel normal; concave fillets get lighter",
            ),
        ),
        default=constants.AO_BEVEL_NORMAL_AUTO,
        description=(
            "Shade this map from the Normal map's material detail. Auto does this for a Bevel shader. "
            "Needs a tangent Normal row with Material Detail set to Auto"
        ),
    )
    curvature_bevel_mask: bpy.props.BoolProperty(
        name="Bevel Mask",
        default=True,
        description=(
            "Draw every bevelled edge of a Bevel shader at full strength (convex white, concave black), "
            "like ZenBBQ's bevel mask. Off keeps true curvature, which reads faint for small bevels"
        ),
    )
    ao_cavity_weight: bpy.props.FloatProperty(
        name="Cavity Weight",
        default=0.0,
        min=-1.0,
        max=1.0,
        description="Control the balance between broad surface occlusion and tight cavity detail",
    )
    ao_relative_to_bounding_box: bpy.props.BoolProperty(
        name="Relative to Bounds",
        default=True,
        description="Scale Max Distance and Min Distance by the model's size, so the same settings work across differently sized assets. Hidden while both are 0, where it has nothing to scale",
    )
    ao_spread_angle: bpy.props.FloatProperty(
        name="Spread Angle",
        default=180.0,
        min=1.0,
        max=180.0,
        description="Set the width of the AO sampling cone. 180° uses the full hemisphere; lower values concentrate rays toward the surface normal for tighter, more directional shadows",
    )
    ao_distribution: bpy.props.EnumProperty(
        name="Distribution",
        items=(
            ("COSINE", "Cosine", "Cosine-weighted hemisphere sampling"),
            ("UNIFORM", "Uniform", "Uniform hemisphere sampling"),
        ),
        # Uniform by default: cosine weighting near-zeroes grazing occluders, so
        # opposing crevice walls read white; uniform matches other bakers' AO look.
        default="UNIFORM",
    )
    ao_ignore_backface: bpy.props.BoolProperty(
        name="Ignore Backface",
        # On by default (Marmoset/Painter behavior): coincident interior shells on
        # multi-layer assets otherwise read as full occlusion.
        default=True,
        description="Ignore hits on back-facing high-poly surfaces when calculating AO and bent normals",
    )
    ao_self_occlusion: bpy.props.FloatProperty(
        name="Self Occlusion",
        default=1.0,
        min=0.0,
        max=1.0,
        description=(
            "Control how strongly each high-poly mesh occludes itself. 1 uses full self-occlusion; "
            "lower values reduce self-shadowing without reducing occlusion from other meshes"
        ),
    )
    ao_attenuation: bpy.props.FloatProperty(
        name="Attenuation",
        default=0.0,
        min=0.0,
        soft_max=4.0,
        description="Control how quickly AO fades with distance. 0 gives every hit equal weight; higher values emphasize nearby contact shadows. Requires a finite AO Distance",
    )
    ao_output_min: bpy.props.FloatProperty(
        name="Darkest Value",
        default=constants.DEFAULT_AO_OUTPUT_MIN,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Set the darkest value the AO map can output",
    )
    ao_output_max: bpy.props.FloatProperty(
        name="Lightest Value",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Set the lightest value the AO map can output",
    )
    ao_use_ground_plane: bpy.props.BoolProperty(
        name="Floor Occlusion",
        default=False,
        description="Darken downward-facing surfaces as if the model rests on an infinite floor (directional ground occlusion), useful for static/grounded assets",
    )
    ao_diffusion_quality: bpy.props.EnumProperty(
        name="Quality",
        items=constants.MAP_AO_DIFFUSION_QUALITY_ITEMS,
        default=constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM,
    )
    ao_diffusion_clearance_scale: bpy.props.FloatProperty(
        name="Clearance Scale",
        default=0.2,
        min=0.01,
        max=1.0,
        subtype="FACTOR",
        description="Set the gap size that Diffusive AO treats as fully open, relative to AO Distance",
    )
    ao_diffusion_clearance_exponent: bpy.props.FloatProperty(
        name="Clearance Exponent",
        default=2.0,
        min=0.25,
        soft_max=8.0,
        description="Control how sharply narrow gaps darken in Diffusive mode",
    )


class MasterBakerMapEnvLightSettings(bpy.types.PropertyGroup):
    env_light_intensity: bpy.props.FloatProperty(
        name="Intensity",
        default=1.0,
        min=0.0,
        soft_max=8.0,
        description="Control the brightness of the environment-light map",
    )
    env_light_occlusion_strength: bpy.props.FloatProperty(
        name="Occlusion",
        default=0.6,
        min=0.0,
        max=1.0,
        description="Control how strongly AO darkens the environment-light map",
    )
    env_light_contrast: bpy.props.FloatProperty(
        name="Contrast",
        default=1.0,
        min=0.01,
        soft_max=4.0,
        description="Control the contrast between sky and ground lighting",
    )
    env_light_up_axis: bpy.props.EnumProperty(
        name="Up Axis",
        items=(
            ("Z", "Z+", "Use +Z as environment up"),
            ("Y", "Y+", "Use +Y as environment up"),
            ("X", "X+", "Use +X as environment up"),
            ("NEG_Z", "Z-", "Use -Z as environment up"),
            ("NEG_Y", "Y-", "Use -Y as environment up"),
            ("NEG_X", "X-", "Use -X as environment up"),
        ),
        default="Z",
    )
    env_light_sky_color: bpy.props.FloatVectorProperty(
        name="Sky",
        size=3,
        subtype="COLOR",
        min=0.0,
        max=1.0,
        default=(0.55, 0.70, 1.00),
        description="Set the color of light coming from the sky",
    )
    env_light_ground_color: bpy.props.FloatVectorProperty(
        name="Ground",
        size=3,
        subtype="COLOR",
        min=0.0,
        max=1.0,
        default=(0.18, 0.16, 0.14),
        description="Set the color of light coming from the ground",
    )


class MasterBakerMapCurvatureSettings(bpy.types.PropertyGroup):
    curvature_scale: bpy.props.FloatProperty(
        name="Curvature Scale",
        default=1.0,
        min=0.01,
        soft_max=8.0,
        description="Control the strength of curvature, cavity, concave, and convex maps",
    )
    # Neutral 0/1 default — mirrors MasterBakerMapSetting (see the note there).
    curvature_tonemapping_min: bpy.props.FloatProperty(
        name="Black Point",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Choose which curvature value becomes black in the output",
    )
    curvature_tonemapping_max: bpy.props.FloatProperty(
        name="White Point",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Choose which curvature value becomes white in the output",
    )
    curvature_distance: bpy.props.FloatProperty(
        name="Curvature Distance",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        description="Set how far curvature sampling reaches. 0 chooses a distance automatically from the low-poly mesh's size (Mesh Rays: 0.2% of it, Painter-style; other methods: 2%)",
    )
    curvature_relative_to_bounding_box: bpy.props.BoolProperty(
        name="Relative to Bounds",
        default=False,
        description="Scale Radius by the low-poly mesh's size, so the same setting works across differently sized assets. Hidden while Radius is 0 (automatic), where it has nothing to scale",
    )
    curvature_secondary_rays: bpy.props.IntProperty(
        name="Secondary Rays",
        default=64,
        min=4,
        soft_max=512,
        max=4096,
        description="Number of probe rays cast around each hit for Mesh Rays, Principal and Direction curvature. Painter's default is 256; higher is smoother and slower",
    )
    curvature_detect_folds: bpy.props.BoolProperty(
        name="Detect Folds",
        default=False,
        description="Detect high-poly geometry that folds back and nearly touches itself so tight self-contact creases read as sharp curvature",
    )
    curvature_self_intersection: bpy.props.EnumProperty(
        name="Self Intersection",
        items=_CURVATURE_SELF_INTERSECTION_ITEMS,
        default="GROUP",
        description="Choose which high-poly meshes the curvature probe rays are allowed to hit",
    )
    curvature_auto_tonemapping: bpy.props.BoolProperty(
        name="Auto Tonemapping (per UV tile)",
        default=False,
        description="Stretch each UV tile's signed curvature so its strongest values reach full black and white. Value Bounds are ignored while this is on",
    )
    curvature_value_min: bpy.props.FloatProperty(
        name="Value Bounds Min",
        default=-1.0,
        min=-1.0,
        max=1.0,
        description="Signed curvature value that becomes black in the output. -1/1 leaves the map untouched",
    )
    curvature_value_max: bpy.props.FloatProperty(
        name="Value Bounds Max",
        default=1.0,
        min=-1.0,
        max=1.0,
        description="Signed curvature value that becomes white in the output. -1/1 leaves the map untouched",
    )
    curvature_method: bpy.props.EnumProperty(
        name="Method",
        items=(
            ("THICKNESS", "Geometric", "Estimate curvature from hit-position/normal neighborhoods"),
            ("NORMAL_DERIVATIVE", "Normal Derivative", "Capture fine curvature detail from changes in the baked normal map"),
            ("MESH_RAYS", "Mesh Rays", "Cast secondary rays around each high-poly hit and measure how the surface bends, like Painter's Generate from Mesh. Responds to Secondary Rays, Radius and Self Intersection"),
        ),
        default="NORMAL_DERIVATIVE",
        description="Choose how curvature is calculated",
    )
    curvature_soften: bpy.props.FloatProperty(
        name="Detail Smoothing",
        default=0.5,
        min=0.0,
        soft_max=1.0,
        description=(
            "Width of the normal-derivative sampling kernel, in texels. Smooths fine curvature "
            "detail as it is derived, which is not the same as the output blur in General. "
            "Geometric ignores this"
        ),
    )
    curvature_output_mode: bpy.props.EnumProperty(
        name="Output",
        items=(
            ("SIGNED", "Signed", "Convex areas brighten, concave areas darken. Use for edge wear, dirt, or weathering masks"),
            ("PRINCIPAL", "Principal", "Separates sharp and gentle curvature into R and G channels. Use when you need independent control over tight edges vs broad curves"),
            ("DIRECTION", "Direction", "Points along the strongest curvature direction. Native on Fyr GPU; approximate on Cycles"),
        ),
        default="SIGNED",
        description="Choose how curvature is encoded in the output",
    )


class MasterBakerMapThicknessSettings(bpy.types.PropertyGroup):
    thickness_distance: bpy.props.FloatProperty(
        name="Distance",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        description="Set how far thickness or density sampling reaches. 0 chooses a distance automatically from the low-poly mesh's size",
    )
    thickness_scale: bpy.props.FloatProperty(
        name="Scale",
        default=1.0,
        min=0.01,
        soft_max=8.0,
        description="Scale the normalized thickness or density values",
    )
    thickness_min_distance: bpy.props.FloatProperty(
        name="Thickness Min Distance",
        default=1.0,
        soft_min=-1.0,
        soft_max=10.0,
        description="Set the minimum inward distance. -1 chooses a range automatically from the mesh bounds",
    )
    thickness_gamma: bpy.props.FloatProperty(
        name="Gamma",
        default=1.0,
        min=0.01,
        soft_max=4.0,
        description="Apply a gamma curve to the map result",
    )
    thickness_ignore_groups: bpy.props.BoolProperty(
        name="Same Mesh Only",
        default=False,
        description="Only let thickness or density rays hit the high-poly mesh matched to the current low-poly mesh",
    )
    thickness_normalization: bpy.props.BoolProperty(
        name="Automatic Normalization",
        default=False,
        description=(
            "Scale the output values to fit within a 0-1 range: the thickest point becomes "
            "pure black and the thinnest pure white. Useful when the thickness range leaves "
            "every value bunched near white, which happens on models whose walls are far "
            "finer than their overall size"
        ),
    )
    thickness_log_response: bpy.props.BoolProperty(
        name="Logarithmic Response",
        default=False,
        description=(
            "Encode thickness on a logarithmic scale instead of a linear one. Keeps thin "
            "parts distinguishable from each other on models whose wall thickness varies a "
            "lot, and compresses the thickest areas instead of clipping them to black"
        ),
    )
    density_auto_levels: bpy.props.BoolProperty(
        name="Auto Levels",
        default=False,
        description="Stretch Density values across more of the black-to-white range while ignoring extreme outliers",
    )
    density_auto_levels_per_group: bpy.props.BoolProperty(
        name="Per Bake Group",
        default=True,
        description="Calculate Auto Levels separately for each bake group instead of sharing one range across the project",
    )


class MasterBakerMapIDSettings(bpy.types.PropertyGroup):
    id_source: bpy.props.EnumProperty(
        name="ID Source",
        items=constants.MAP_ID_SOURCE_ITEMS,
        default=constants.MAP_ID_SOURCE_OBJECT,
    )


class MasterBakerMapPositionSettings(bpy.types.PropertyGroup):
    position_normalization: bpy.props.EnumProperty(
        name="Position Normalization",
        items=constants.MAP_POSITION_NORMALIZATION_ITEMS,
        default=constants.MAP_POSITION_NORMALIZATION_BOUNDING_BOX,
    )
    position_mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("ABSOLUTE", "Absolute", "Encode raw object-space coordinates"),
            ("RELATIVE", "Relative", "Encode coordinates relative to local origin"),
        ),
        default="ABSOLUTE",
    )
    position_axis: bpy.props.EnumProperty(
        name="Axis",
        items=(
            ("XYZ", "XYZ", "Encode all three axes"),
            ("X", "X", "Encode X axis only"),
            ("Y", "Y", "Encode Y axis only"),
            ("Z", "Z", "Encode Z axis only"),
        ),
        default="XYZ",
    )
    relative_to_bounding_box: bpy.props.BoolProperty(
        name="Relative to Bounding Box",
        default=True,
        description="Normalize Position output within the active low-poly mesh's bounds instead of using the object origin",
        options={"HIDDEN"},
    )


class MasterBakerMapHeightSettings(bpy.types.PropertyGroup):
    height_inner_distance: bpy.props.FloatProperty(
        name="Inner Distance",
        default=0.0,
        soft_min=-10.0,
        soft_max=10.0,
        description="Set the inward distance encoded by the Height map. 0 chooses the range automatically",
    )
    height_outer_distance: bpy.props.FloatProperty(
        name="Outer Distance",
        default=0.0,
        soft_min=-10.0,
        soft_max=10.0,
        description="Set the outward distance encoded by the Height map. 0 chooses the range automatically",
    )
    height_dither: bpy.props.BoolProperty(
        name="Dither",
        default=False,
        description="Apply deterministic ordered dithering when writing 8-bit Height output to reduce banding",
    )
    thickness_dither: bpy.props.BoolProperty(
        name="Dither",
        default=False,
        description="Apply randomized dithering when writing 8-bit Thickness output to reduce banding",
    )


def _material_detail_mode_items(self, _context):
    if getattr(self, "map_type", "") == constants.MAP_AO:
        return constants.MATERIAL_DETAIL_MODE_ITEMS
    return constants.MATERIAL_NORMAL_DETAIL_MODE_ITEMS


class MasterBakerMapSetting(bpy.types.PropertyGroup):
    import uuid as _uuid_mod

    uuid: bpy.props.StringProperty(
        name="UUID",
        default="",
        description="Unique persistent identifier for this map stack item. Do not modify.",
        options={"HIDDEN"},
    )
    map_type: bpy.props.EnumProperty(
        name="Map",
        items=constants.MAP_TYPE_ITEMS,
        default=constants.MAP_NORMAL,
        update=_map_type_update,
    )

    def ensure_uuid(self):
        """Assign a new UUID if missing."""
        if not getattr(self, "uuid", None):
            self.uuid = str(self._uuid_mod.uuid4())

    enabled: bpy.props.BoolProperty(
        name="Enabled",
        description="Include this map in the bake",
        default=True,
        update=_map_enabled_update,
    )
    samples: bpy.props.IntProperty(
        name="Rays",
        default=constants.MAP_RECOMMENDED_SAMPLES,
        min=1,
        max=constants.MAP_MAX_SAMPLES,
        soft_max=constants.MAP_MAX_SAMPLES,
        description="Number of rays traced for maps such as AO, Thickness, and Cavity. More rays reduce noise but take longer",
        update=_samples_update,
    )
    is_add_phantom: bpy.props.BoolProperty(name="Is Add Phantom", default=False)
    output_suffix: bpy.props.StringProperty(
        name="Output Suffix",
        default="",
        description="Enter a custom name for this map and its output file, or leave blank to use the default",
        update=_map_setting_update,
    )
    roughness_normal_variance: bpy.props.BoolProperty(
        name="Add Lost Normal Detail",
        default=False,
        description=(
            "Add the surface detail the normal map is too low-resolution to store. "
            "Bumps smaller than one texel get averaged flat, but the surface is still "
            "bumpy, so without this the bake comes out shinier than the high poly"
        ),
        update=_map_setting_update,
    )
    roughness_normal_variance_strength: bpy.props.FloatProperty(
        name="Amount",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description=(
            "How much of the lost detail to add. 1.0 adds all of it as measured, which "
            "can read stronger than the high poly on some materials; 0 leaves roughness "
            "exactly as baked"
        ),
        update=_map_setting_update,
    )
    normal_space: bpy.props.EnumProperty(
        name="Normal Space",
        description="Coordinate space the normal map is baked in",
        items=constants.MAP_NORMAL_SPACE_ITEMS,
        default=constants.MAP_NORMAL_SPACE_TANGENT,
        update=_normal_preview_config_update,
    )
    normal_format: bpy.props.EnumProperty(
        name="Normal Format",
        description="Green-channel direction of tangent normal maps. OpenGL keeps +Y; DirectX flips it",
        items=constants.NORMAL_FORMAT_ITEMS,
        default=constants.NORMAL_FORMAT_OPENGL,
        update=_normal_format_update,
    )
    material_detail_mode: bpy.props.EnumProperty(
        name="Material Detail",
        items=_material_detail_mode_items,
        # Blender requires an integer default when EnumProperty items are
        # supplied by a callback. Value 1 is MATERIAL_DETAIL_AUTO.
        default=1,
        description=(
            "Off bakes geometry only. Auto combines geometry with compatible high-poly "
            "material normal, bump, height, or AO detail. Material Only (Normal maps) "
            "transfers that material detail without geometric high-to-low normals. "
            "Manual (AO) uses a chosen AO image"
        ),
        update=_map_setting_update,
    )
    material_detail_image: bpy.props.PointerProperty(
        name="Source",
        type=bpy.types.Image,
        description="Choose the AO image to include when Material Detail is set to Manual",
        update=_map_setting_update,
    )
    normal_relief: bpy.props.FloatProperty(
        name="Relief",
        default=0.5,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description=(
            "Higher keeps more mid-frequency bump and cracks; lower washes micro-grain "
            "for a cleaner map. Only applies to material EMIT normal bakes"
        ),
        update=_map_setting_update,
    )
    flip_green: bpy.props.BoolProperty(
        name="Flip Green",
        default=False,
        description="Invert the green channel for normal output",
        options={"HIDDEN"},
        update=_normal_preview_config_update,
    )
    ao_distance: bpy.props.FloatProperty(
        name="AO Distance",
        # 0 = unlimited: occlusion accumulates from the whole scene like other
        # bakers' defaults, so wide crevices shade instead of reading white.
        default=0.0,
        min=0.0,
        soft_max=10.0,
        description="Set the maximum ray distance for AO and bent normals. 0 = unlimited, which darkens wider, deeper creases. With Relative to Bounds enabled, a non-zero value is a fraction of model size",
        update=_map_setting_update,
    )
    ao_min_distance: bpy.props.FloatProperty(
        name="Min Distance",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        description="Ignore AO and bent-normal occluders closer than this distance. 0 = no minimum, so nearby hits count. With Relative to Bounds enabled, a non-zero value is a fraction of model size",
        update=_map_setting_update,
    )
    ao_two_sided: bpy.props.BoolProperty(
        name="Two-Sided",
        default=False,
        description="Include high-poly backfaces when calculating AO and bent normals",
        update=_map_setting_update,
    )
    ao_ignore_groups: bpy.props.BoolProperty(
        name="Same Mesh Only",
        default=False,
        description="Only let AO and bent-normal rays hit the high-poly mesh matched to the current low-poly mesh",
        update=_map_setting_update,
    )
    ao_occlude_other_groups: bpy.props.BoolProperty(
        name="Occlude Other Groups",
        default=False,
        description="Let this map's rays hit the high-poly meshes of other bake groups (AO and Bent Normal: the whole scene; Thickness and Density: the same texture set). Same Mesh Only still applies on top",
        update=_map_setting_update,
    )
    ao_bevel_normal: bpy.props.EnumProperty(
        name="Use Bevel Normal",
        items=(
            (
                constants.AO_BEVEL_NORMAL_AUTO,
                "Auto",
                "A Bevel shader shades convex edges from the bevel normal; other materials stay geometric",
            ),
            (constants.AO_BEVEL_NORMAL_OFF, "Off", "AO from the geometry only"),
            (
                constants.AO_BEVEL_NORMAL_CONVEX,
                "Convex Edges",
                "Bevelled convex edges shade from the bevel normal; concave fillets keep the geometric normal so crevices stay dark (ZenBBQ's AO)",
            ),
            (
                constants.AO_BEVEL_NORMAL_ALL,
                "All Edges",
                "Every bevelled edge shades from the bevel normal, like Cycles' AO node fed a Bevel normal; concave fillets get lighter",
            ),
        ),
        default=constants.AO_BEVEL_NORMAL_AUTO,
        description=(
            "Shade this map from the Normal map's material detail. Auto does this for a Bevel shader. "
            "Needs a tangent Normal row with Material Detail set to Auto"
        ),
        update=_map_setting_update,
    )
    curvature_bevel_mask: bpy.props.BoolProperty(
        name="Bevel Mask",
        default=True,
        description=(
            "Draw every bevelled edge of a Bevel shader at full strength (convex white, concave black), "
            "like ZenBBQ's bevel mask. Off keeps true curvature, which reads faint for small bevels"
        ),
        update=_map_setting_update,
    )
    ao_cavity_weight: bpy.props.FloatProperty(
        name="Cavity Weight",
        default=-1.0,
        min=-1.0,
        max=1.0,
        description="Control the balance between broad surface occlusion and tight cavity detail",
        update=_map_setting_update,
    )
    ao_relative_to_bounding_box: bpy.props.BoolProperty(
        name="Relative to Bounds",
        default=True,
        description="Scale Max Distance and Min Distance by the model's size, so the same settings work across differently sized assets. Hidden while both are 0, where it has nothing to scale",
        update=_map_setting_update,
    )
    ao_spread_angle: bpy.props.FloatProperty(
        name="Spread Angle",
        default=180.0,
        min=1.0,
        max=180.0,
        description="Set the width of the AO sampling cone. 180° uses the full hemisphere; lower values concentrate rays toward the surface normal for tighter, more directional shadows",
        update=_map_setting_update,
    )
    ao_distribution: bpy.props.EnumProperty(
        name="Distribution",
        items=(
            ("COSINE", "Cosine", "Cosine-weighted hemisphere sampling"),
            ("UNIFORM", "Uniform", "Uniform hemisphere sampling"),
        ),
        description="How AO sample rays are spread across the hemisphere",
        # Uniform by default: cosine weighting near-zeroes grazing occluders, so
        # opposing crevice walls read white; uniform matches other bakers' AO look.
        default="UNIFORM",
        update=_map_setting_update,
    )
    ao_ignore_backface: bpy.props.BoolProperty(
        name="Ignore Backface",
        # THIS is the value the bake uses: the UI draws it and export.py sends it.
        # The MasterBakerMapAOSettings mirror of the same name is written FROM here by
        # _sync_map_setting_family and is never read back, so its default could not take
        # effect -- which is how this shipped at False for years while the mirror carried
        # the intended True and the reason for it. Keep the two in agreement.
        #
        # On by default, matching the project-level `ignore_backface` that already
        # governs the projection ray: a hemisphere ray that hits the BACK of a triangle
        # has entered geometry from behind, which on layered assets (cloth sheets,
        # eyelashes, stacked armour) reads as full occlusion where nothing is actually
        # occluding. On a closed watertight mesh an outward ray meets a front face first,
        # so this is close to a no-op there -- it only bites where it is meant to.
        #
        # It also has to be one answer for the whole AO-visibility family: Bent Normal is
        # the mean UNOCCLUDED direction of the same visibility test AO integrates, so AO
        # and Bent Normal disagreeing about which directions are blocked is incoherent.
        default=True,
        description="Ignore hits on back-facing high-poly surfaces when calculating AO and bent normals",
        update=_map_setting_update,
    )
    ao_self_occlusion: bpy.props.FloatProperty(
        name="Self Occlusion",
        default=1.0,
        min=0.0,
        max=1.0,
        description=(
            "Control how strongly each high-poly mesh occludes itself. 1 uses full self-occlusion; "
            "lower values reduce self-shadowing without reducing occlusion from other meshes"
        ),
        update=_map_setting_update,
    )
    ao_attenuation: bpy.props.FloatProperty(
        name="Attenuation",
        default=0.0,
        min=0.0,
        soft_max=4.0,
        description="Control how quickly AO fades with distance. 0 gives every hit equal weight; higher values emphasize nearby contact shadows. Requires a finite AO Distance",
        update=_map_setting_update,
    )
    ao_output_min: bpy.props.FloatProperty(
        name="Darkest Value",
        default=constants.DEFAULT_AO_OUTPUT_MIN,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Set the darkest value the AO map can output",
        update=_map_setting_update,
    )
    ao_output_max: bpy.props.FloatProperty(
        name="Lightest Value",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Set the lightest value the AO map can output",
        update=_map_setting_update,
    )
    ao_use_ground_plane: bpy.props.BoolProperty(
        name="Floor Occlusion",
        default=False,
        description="Darken downward-facing surfaces as if the model rests on an infinite floor (directional ground occlusion), useful for static/grounded assets",
        update=_map_setting_update,
    )
    ao_mode: bpy.props.EnumProperty(
        name="Method",
        description="How ambient occlusion is calculated",
        items=constants.MAP_AO_MODE_ITEMS,
        default=constants.MAP_AO_MODE_RAYCAST,
        update=_ao_mode_update,
    )
    ao_diffusion_quality: bpy.props.EnumProperty(
        name="Quality",
        items=constants.MAP_AO_DIFFUSION_QUALITY_ITEMS,
        default=constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM,
        description="Resolution preset for the diffusive AO field",
        update=_map_setting_update,
    )
    ao_diffusion_clearance_scale: bpy.props.FloatProperty(
        name="Clearance Scale",
        default=0.2,
        min=0.01,
        max=1.0,
        subtype="FACTOR",
        description="Set the gap size that Diffusive AO treats as fully open, relative to AO Distance",
        update=_map_setting_update,
    )
    ao_diffusion_clearance_exponent: bpy.props.FloatProperty(
        name="Clearance Exponent",
        default=2.0,
        min=0.25,
        soft_max=8.0,
        description="Control how sharply narrow gaps darken in Diffusive mode",
        update=_map_setting_update,
    )
    env_light_intensity: bpy.props.FloatProperty(
        name="Intensity",
        default=1.0,
        min=0.0,
        soft_max=8.0,
        description="Control the brightness of the environment-light map",
        update=_map_setting_update,
    )
    env_light_occlusion_strength: bpy.props.FloatProperty(
        name="Occlusion",
        default=0.6,
        min=0.0,
        max=1.0,
        description="Control how strongly AO darkens the environment-light map",
        update=_map_setting_update,
    )
    env_light_contrast: bpy.props.FloatProperty(
        name="Contrast",
        default=1.0,
        min=0.01,
        soft_max=4.0,
        description="Control the contrast between sky and ground lighting",
        update=_map_setting_update,
    )
    env_light_up_axis: bpy.props.EnumProperty(
        name="Up Axis",
        items=(
            ("Z", "Z+", "Use +Z as environment up"),
            ("Y", "Y+", "Use +Y as environment up"),
            ("X", "X+", "Use +X as environment up"),
            ("NEG_Z", "Z-", "Use -Z as environment up"),
            ("NEG_Y", "Y-", "Use -Y as environment up"),
            ("NEG_X", "X-", "Use -X as environment up"),
        ),
        description="Which object axis the environment-light map treats as up",
        default="Z",
        update=_map_setting_update,
    )
    env_light_sky_color: bpy.props.FloatVectorProperty(
        name="Sky",
        size=3,
        subtype="COLOR",
        min=0.0,
        max=1.0,
        default=(0.55, 0.70, 1.00),
        description="Set the color of light coming from the sky",
        update=_map_setting_update,
    )
    env_light_ground_color: bpy.props.FloatVectorProperty(
        name="Ground",
        size=3,
        subtype="COLOR",
        min=0.0,
        max=1.0,
        default=(0.18, 0.16, 0.14),
        description="Set the color of light coming from the ground",
        update=_map_setting_update,
    )
    curvature_scale: bpy.props.FloatProperty(
        name="Curvature Scale",
        default=1.0,
        min=0.01,
        soft_max=8.0,
        description="Control the strength of curvature, cavity, concave, and convex maps",
        update=_map_setting_update,
    )
    # Black/White Point default to the NEUTRAL 0/1 range. The Marmoset-matched
    # curvature response is calibrated against an unstretched output; the legacy
    # 0.4/0.6 window was a 5x levels stretch that railed that curve. Keep new maps and
    # "Restore Defaults" neutral (apply_default_map_setting_values) and let the artist
    # dial a stretch deliberately.
    curvature_tonemapping_min: bpy.props.FloatProperty(
        name="Black Point",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Choose which curvature value becomes black in the output",
        update=_map_setting_update,
    )
    curvature_tonemapping_max: bpy.props.FloatProperty(
        name="White Point",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Choose which curvature value becomes white in the output",
        update=_map_setting_update,
    )
    curvature_distance: bpy.props.FloatProperty(
        name="Curvature Distance",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        description="Set how far curvature sampling reaches. 0 chooses a distance automatically from the low-poly mesh's size (Mesh Rays: 0.2% of it, Painter-style; other methods: 2%)",
        update=_map_setting_update,
    )
    curvature_relative_to_bounding_box: bpy.props.BoolProperty(
        name="Relative to Bounds",
        default=False,
        description="Scale Radius by the low-poly mesh's size, so the same setting works across differently sized assets. Hidden while Radius is 0 (automatic), where it has nothing to scale",
        update=_map_setting_update,
    )
    curvature_secondary_rays: bpy.props.IntProperty(
        name="Secondary Rays",
        default=64,
        min=4,
        soft_max=512,
        max=4096,
        description="Number of probe rays cast around each hit for Mesh Rays, Principal and Direction curvature. Painter's default is 256; higher is smoother and slower",
        update=_map_setting_update,
    )
    curvature_detect_folds: bpy.props.BoolProperty(
        name="Detect Folds",
        default=False,
        description="Detect high-poly geometry that folds back and nearly touches itself so tight self-contact creases read as sharp curvature",
        update=_map_setting_update,
    )
    curvature_self_intersection: bpy.props.EnumProperty(
        name="Self Intersection",
        items=_CURVATURE_SELF_INTERSECTION_ITEMS,
        default="GROUP",
        description="Choose which high-poly meshes the curvature probe rays are allowed to hit",
        update=_map_setting_update,
    )
    curvature_auto_tonemapping: bpy.props.BoolProperty(
        name="Auto Tonemapping (per UV tile)",
        default=False,
        description="Stretch each UV tile's signed curvature so its strongest values reach full black and white. Value Bounds are ignored while this is on",
        update=_map_setting_update,
    )
    curvature_value_min: bpy.props.FloatProperty(
        name="Value Bounds Min",
        default=-1.0,
        min=-1.0,
        max=1.0,
        description="Signed curvature value that becomes black in the output. -1/1 leaves the map untouched",
        update=_map_setting_update,
    )
    curvature_value_max: bpy.props.FloatProperty(
        name="Value Bounds Max",
        default=1.0,
        min=-1.0,
        max=1.0,
        description="Signed curvature value that becomes white in the output. -1/1 leaves the map untouched",
        update=_map_setting_update,
    )
    curvature_method: bpy.props.EnumProperty(
        name="Method",
        items=(
            ("THICKNESS", "Geometric", "Estimate curvature from hit-position/normal neighborhoods"),
            ("NORMAL_DERIVATIVE", "Normal Derivative", "Capture fine curvature detail from changes in the baked normal map"),
            ("MESH_RAYS", "Mesh Rays", "Cast secondary rays around each high-poly hit and measure how the surface bends, like Painter's Generate from Mesh. Responds to Secondary Rays, Radius and Self Intersection"),
        ),
        default="NORMAL_DERIVATIVE",
        description="Choose how curvature is calculated",
        update=_map_setting_update,
    )
    curvature_soften: bpy.props.FloatProperty(
        name="Detail Smoothing",
        default=0.5,
        min=0.0,
        soft_max=1.0,
        description=(
            "Width of the normal-derivative sampling kernel, in texels. Smooths fine curvature "
            "detail as it is derived, which is not the same as the output blur in General. "
            "Geometric ignores this"
        ),
        update=_map_setting_update,
    )
    curvature_output_mode: bpy.props.EnumProperty(
        name="Output",
        items=(
            ("SIGNED", "Signed", "Convex areas brighten, concave areas darken. Use for edge wear, dirt, or weathering masks"),
            ("PRINCIPAL", "Principal", "Separates sharp and gentle curvature into R and G channels. Use when you need independent control over tight edges vs broad curves"),
            ("DIRECTION", "Direction", "Points along the strongest curvature direction. Native on Fyr GPU; approximate on Cycles"),
        ),
        default="SIGNED",
        description="Choose how curvature is encoded in the output",
        update=_map_setting_update,
    )
    thickness_distance: bpy.props.FloatProperty(
        name="Distance",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        description="Set how far thickness or density sampling reaches. 0 chooses a distance automatically from the low-poly mesh's size",
        update=_map_setting_update,
    )
    thickness_scale: bpy.props.FloatProperty(
        name="Scale",
        default=1.0,
        min=0.01,
        soft_max=8.0,
        description="Scale the normalized thickness or density values",
        update=_map_setting_update,
    )
    thickness_min_distance: bpy.props.FloatProperty(
        name="Thickness Min Distance",
        default=-1.0,
        soft_min=-1.0,
        soft_max=10.0,
        description="Set the minimum inward distance. -1 chooses a range automatically from the mesh bounds",
        update=_map_setting_update,
    )
    thickness_gamma: bpy.props.FloatProperty(
        name="Gamma",
        default=1.0,
        min=0.01,
        soft_max=4.0,
        description="Apply a gamma curve to the map result",
        update=_map_setting_update,
    )
    thickness_ignore_groups: bpy.props.BoolProperty(
        name="Same Mesh Only",
        default=False,
        description="Only let thickness or density rays hit the high-poly mesh matched to the current low-poly mesh",
        update=_thickness_ignore_groups_update,
    )
    thickness_normalization: bpy.props.BoolProperty(
        name="Automatic Normalization",
        default=False,
        description=(
            "Scale the output values to fit within a 0-1 range: the thickest point becomes "
            "pure black and the thinnest pure white. Useful when the thickness range leaves "
            "every value bunched near white, which happens on models whose walls are far "
            "finer than their overall size"
        ),
        update=_map_setting_update,
    )
    thickness_log_response: bpy.props.BoolProperty(
        name="Logarithmic Response",
        default=False,
        description=(
            "Encode thickness on a logarithmic scale instead of a linear one. Keeps thin "
            "parts distinguishable from each other on models whose wall thickness varies a "
            "lot, and compresses the thickest areas instead of clipping them to black"
        ),
        update=_map_setting_update,
    )
    density_auto_levels: bpy.props.BoolProperty(
        name="Auto Levels",
        default=False,
        description="Stretch Density values across more of the black-to-white range while ignoring extreme outliers",
        update=_map_setting_update,
    )
    density_auto_levels_per_group: bpy.props.BoolProperty(
        name="Per Bake Group",
        default=True,
        description="Calculate Auto Levels separately for each bake group instead of sharing one range across the project",
        update=_map_setting_update,
    )
    id_source: bpy.props.EnumProperty(
        name="ID Source",
        description="What each color in the ID map represents",
        items=constants.MAP_ID_SOURCE_ITEMS,
        default=constants.MAP_ID_SOURCE_OBJECT,
        update=_map_setting_update,
    )
    attribute_name: bpy.props.StringProperty(
        name="Attribute",
        description="Mesh attribute on the high poly to bake. Geometry Nodes outputs count; a high without it bakes black",
        default="",
        search=_attribute_name_search,
        search_options={"SORT"},
        update=_map_setting_update,
    )
    attribute_range_min: bpy.props.FloatProperty(
        name="Min",
        description="Attribute value that bakes black",
        default=0.0,
        precision=4,
        update=_map_setting_update,
    )
    attribute_range_max: bpy.props.FloatProperty(
        name="Max",
        description="Attribute value that bakes white",
        default=1.0,
        precision=4,
        update=_map_setting_update,
    )
    normal_encoding: bpy.props.EnumProperty(
        name="Output",
        description="What a tangent-space Normal row writes",
        items=constants.NORMAL_ENCODING_ITEMS,
        default=constants.NORMAL_ENCODING_NORMAL,
        update=_normal_encoding_update,
    )
    derivative_max_slope: bpy.props.FloatProperty(
        name="Max Slope",
        description="Slope written as full red/green (0 or 1). Steeper slopes clip. 1 is a 45 degree surface, 2 about 63 degrees",
        default=constants.DEFAULT_DERIVATIVE_MAX_SLOPE,
        min=0.05,
        soft_max=10.0,
        precision=2,
        update=_map_setting_update,
    )
    wireframe_line_width: bpy.props.FloatProperty(
        name="Line Width",
        description="Width of the drawn UV edges, in pixels of the baked texture",
        default=constants.DEFAULT_WIREFRAME_LINE_WIDTH,
        min=0.25,
        max=32.0,
        precision=2,
        subtype="PIXEL",
        update=_map_setting_update,
    )
    wireframe_triangles: bpy.props.BoolProperty(
        name="Triangles",
        description="Draw every triangle edge, including the diagonals that split quads and n-gons. Off draws the polygon edges only",
        default=False,
        update=_map_setting_update,
    )
    position_normalization: bpy.props.EnumProperty(
        name="Position Normalization",
        description="How position values are fit into the 0–1 color range",
        items=constants.MAP_POSITION_NORMALIZATION_ITEMS,
        default=constants.MAP_POSITION_NORMALIZATION_BOUNDING_BOX,
        update=_map_setting_update,
    )
    position_mode: bpy.props.EnumProperty(
        name="Mode",
        description="Whether position values are raw object-space coordinates or offsets from the local origin",
        items=(
            ("ABSOLUTE", "Absolute", "Encode raw object-space coordinates"),
            ("RELATIVE", "Relative", "Encode coordinates relative to local origin"),
        ),
        default="ABSOLUTE",
        update=_map_setting_update,
    )
    position_axis: bpy.props.EnumProperty(
        name="Axis",
        description="Which object axes the position map encodes",
        items=(
            ("XYZ", "XYZ", "Encode all three axes"),
            ("X", "X", "Encode X axis only"),
            ("Y", "Y", "Encode Y axis only"),
            ("Z", "Z", "Encode Z axis only"),
        ),
        default="XYZ",
        update=_map_setting_update,
    )
    relative_to_bounding_box: bpy.props.BoolProperty(
        name="Relative to Bounding Box",
        default=True,
        description="Normalize Position output within the active low-poly mesh's bounds instead of using the object origin",
        options={"HIDDEN"},
        update=_map_setting_update,
    )
    height_inner_distance: bpy.props.FloatProperty(
        name="Inner Distance",
        default=0.0,
        soft_min=-10.0,
        soft_max=10.0,
        description="Set the inward distance encoded by the Height map. 0 chooses the range automatically",
        update=_map_setting_update,
    )
    height_outer_distance: bpy.props.FloatProperty(
        name="Outer Distance",
        default=0.0,
        soft_min=-10.0,
        soft_max=10.0,
        description="Set the outward distance encoded by the Height map. 0 chooses the range automatically",
        update=_map_setting_update,
    )
    height_dither: bpy.props.BoolProperty(
        name="Dither",
        default=False,
        description="Apply deterministic ordered dithering when writing 8-bit Height output to reduce banding",
        update=_map_setting_update,
    )
    thickness_dither: bpy.props.BoolProperty(
        name="Dither",
        default=False,
        description="Apply randomized dithering when writing 8-bit Thickness output to reduce banding",
        update=_map_setting_update,
    )
    denoising_enabled: bpy.props.BoolProperty(
        name="Denoise",
        default=False,
        description="Reduce ray-tracing noise after baking so lower sample counts can produce smoother results",
        update=_map_setting_update,
    )
    # Soften: inherited from the project unless this row overrides it (Marmoset model).
    # resolve_map_soften() is the ONLY place the two are combined -- read it, never the
    # raw fields, when building a bake job or a dirty-state fingerprint.
    soften_override: bpy.props.BoolProperty(
        name="Override Soften",
        default=False,
        description="Use this map's own Soften value instead of the project's Soften setting",
        update=_map_setting_update,
    )
    soften: bpy.props.FloatProperty(
        name="Soften",
        default=constants.DEFAULT_SOFTEN,
        min=0.0,
        max=constants.SOFTEN_MAX,
        soft_max=constants.SOFTEN_MAX,
        description=(
            "Blur this map after baking. The value is the blur radius in texels; 0, the default, "
            "leaves the raw bake untouched"
        ),
        update=_map_setting_update,
    )
    material_channel: bpy.props.EnumProperty(
        name="Channel",
        items=constants.MATERIAL_CHANNEL_ITEMS,
        default=constants.MATERIAL_CHANNEL_ALBEDO,
        description="PBR channel to bake from the material's Principled BSDF",
        update=_map_setting_update,
    )
    # Advanced per-output execution route. AUTO picks Fyr when Material IR can run
    # the graph, otherwise Cycles. Fyr requires a native path (fails preflight if
    # unavailable); Cycles forces the compatibility path. Enum ids stay BACKEND /
    # BLENDER for .blend compatibility. Recorded per output in diagnostics; routing
    # is never silently changed after preflight.
    execution_route: bpy.props.EnumProperty(
        name="Route",
        items=constants.EXECUTION_ROUTE_ITEMS,
        default=constants.EXECUTION_ROUTE_AUTO,
        description="Which engine bakes this output. Auto uses Fyr when possible, otherwise Cycles",
        update=_map_setting_update,
    )
    # Procedural material capture provenance (docs/PROCEDURAL_MATERIAL_CAPTURE_PLAN.md).
    material_origin: bpy.props.EnumProperty(
        name="Origin",
        items=constants.MATERIAL_ORIGIN_ITEMS,
        default=constants.MATERIAL_ORIGIN_MANUAL,
        description="How this material map row was created",
        options={"HIDDEN"},
    )
    material_binding_key: bpy.props.StringProperty(
        name="Binding Key",
        default="",
        description="Stable logical binding for capture/custom synchronization",
        options={"HIDDEN"},
    )
    material_resolve_state: bpy.props.EnumProperty(
        name="Resolve",
        items=constants.MATERIAL_RESOLVE_ITEMS,
        default=constants.MATERIAL_RESOLVE_RESOLVED,
        description="Source coverage / validity for this material binding",
        options={"HIDDEN"},
    )
    material_data_type: bpy.props.EnumProperty(
        name="Data Type",
        items=constants.MATERIAL_DATA_TYPE_ITEMS,
        default=constants.MATERIAL_DATA_COLOR,
        options={"HIDDEN"},
    )
    material_vector_encoding: bpy.props.EnumProperty(
        name="Vector Encoding",
        items=constants.MATERIAL_VECTOR_ENCODE_ITEMS,
        default=constants.MATERIAL_VECTOR_ENCODE_UNIT,
        options={"HIDDEN"},
    )
    material_custom_name: bpy.props.StringProperty(
        name="Custom Name",
        default="",
        options={"HIDDEN"},
    )
    material_source_node_ids: bpy.props.StringProperty(
        name="Source Nodes",
        default="",
        options={"HIDDEN"},
    )
    material_status_message: bpy.props.StringProperty(
        name="Status",
        default="",
        options={"HIDDEN"},
    )
    material_previous_enabled: bpy.props.BoolProperty(
        name="Previous Enabled",
        default=True,
        options={"HIDDEN"},
    )
    lighting_output: bpy.props.EnumProperty(
        name="Output",
        items=constants.LIGHTING_OUTPUT_ITEMS,
        default=constants.LIGHTING_OUTPUT_LIGHTING,
        description="Choose the scene-lighting result to bake. Lighting stores pure HDR irradiance without albedo or emission; Lit Color includes diffuse albedo and emission",
        update=_map_setting_update,
    )
    lighting_engine: bpy.props.EnumProperty(
        name="Engine",
        items=constants.LIGHTING_ENGINE_ITEMS,
        default=constants.LIGHTING_ENGINE_AUTO,
        description="Choose how Fyr Baker reads materials and lights. Auto follows the scene's render engine; this does not change which hardware performs the bake",
        update=_map_setting_update,
    )
    lighting_quality: bpy.props.EnumProperty(
        name="Quality",
        items=constants.LIGHTING_QUALITY_ITEMS,
        default=constants.LIGHTING_QUALITY_BALANCED,
        description="Set the quality for this lighting map. Choose Custom to edit samples, bounces, and the noise threshold below; other maps are not affected",
        update=_lighting_quality_update,
    )
    lighting_direct_enabled: bpy.props.BoolProperty(
        name="Direct",
        default=True,
        description="Include direct light from lamps and their shadows",
        update=_map_setting_update,
    )
    lighting_indirect_enabled: bpy.props.BoolProperty(
        name="Indirect",
        default=True,
        description="Include indirect light bounced between surfaces",
        update=_map_setting_update,
    )
    lighting_world_enabled: bpy.props.BoolProperty(
        name="World",
        default=True,
        description="Include lighting from the world or environment",
        update=_map_setting_update,
    )
    lighting_emission_enabled: bpy.props.BoolProperty(
        name="Emission",
        default=True,
        description="Include light emitted by material surfaces",
        update=_map_setting_update,
    )
    lighting_direct_samples: bpy.props.IntProperty(
        name="Direct Rays",
        default=64,
        min=1,
        max=4096,
        description="Set the rays per output pixel for soft shadows and world lighting. Point-like lights always use one ray",
        update=_lighting_transport_update,
    )
    lighting_indirect_paths: bpy.props.IntProperty(
        name="Indirect Paths",
        default=64,
        min=1,
        max=65536,
        description="Set the indirect-light paths traced per output pixel",
        update=_lighting_transport_update,
    )
    lighting_max_bounces: bpy.props.IntProperty(
        name="Max Bounces",
        default=4,
        min=0,
        max=32,
        description="Set the maximum number of times indirect light can bounce",
        update=_lighting_transport_update,
    )
    lighting_occlude_other_groups: bpy.props.BoolProperty(
        name="Include Other Groups",
        default=True,
        description="Let every bake group's meshes cast shadows and bounce light onto this map, so a whole scene lights as one. Off keeps each group lit on its own",
        update=_map_setting_update,
    )
    lighting_exposure: bpy.props.FloatProperty(
        name="Exposure",
        default=1.0,
        min=0.0,
        soft_max=8.0,
        precision=3,
        description="Multiply the baked light by this value",
        update=_map_setting_update,
    )
    lighting_noise_threshold: bpy.props.FloatProperty(
        name="Noise Threshold",
        default=0.02,
        min=0.0,
        max=1.0,
        precision=3,
        description="Stop adaptive sampling when remaining brightness noise falls below this value. 0 disables adaptive stopping",
        update=_lighting_transport_update,
    )
    normal_settings: bpy.props.PointerProperty(name="Normal Settings", type=MasterBakerMapNormalSettings)
    ao_settings: bpy.props.PointerProperty(name="AO Settings", type=MasterBakerMapAOSettings)
    env_light_settings: bpy.props.PointerProperty(name="Env Light Settings", type=MasterBakerMapEnvLightSettings)
    curvature_settings: bpy.props.PointerProperty(name="Curvature Settings", type=MasterBakerMapCurvatureSettings)
    thickness_settings: bpy.props.PointerProperty(name="Thickness Settings", type=MasterBakerMapThicknessSettings)
    id_settings: bpy.props.PointerProperty(name="ID Settings", type=MasterBakerMapIDSettings)
    position_settings: bpy.props.PointerProperty(name="Position Settings", type=MasterBakerMapPositionSettings)
    height_settings: bpy.props.PointerProperty(name="Height Settings", type=MasterBakerMapHeightSettings)


class MasterBakerOutputTileItem(bpy.types.PropertyGroup):
    """One concrete UDIM tile file behind a single logical output entry.

    These are deliberately *not* top-level outputs: a 40-tile character would otherwise turn
    one Normal map into forty rows in the output list.
    """

    udim_tile: bpy.props.IntProperty(name="UDIM Tile", default=0)
    file_path: bpy.props.StringProperty(name="File Path", subtype="FILE_PATH")
    width: bpy.props.IntProperty(name="Width", default=0)
    height: bpy.props.IntProperty(name="Height", default=0)
    stale: bpy.props.BoolProperty(
        name="Stale",
        default=False,
        description="File left over from an earlier bake for a tile that is no longer occupied. Fyr never deletes it on its own",
    )


class MasterBakerOutputImageItem(bpy.types.PropertyGroup):
    map_uuid: bpy.props.StringProperty(name="Map UUID")
    map_type: bpy.props.StringProperty(name="Map Type")
    # Effective backend type this file was baked as (e.g. MATERIAL_ROUGHNESS, LIGHTING).
    # map_type stores the raw stack type so the Outputs panel matches its row; export
    # templates address channels by effective type, and once the row's uuid is orphaned
    # (a preset load rebuilds the stack) this recorded value is the only translation left.
    effective_map_type: bpy.props.StringProperty(name="Effective Map Type")
    group_name: bpy.props.StringProperty(name="Bake Group")
    output_suffix: bpy.props.StringProperty(name="Output Suffix")
    display_name: bpy.props.StringProperty(name="Display Name")
    # Always a concrete file. For a tiled output this is the lowest live tile, so every
    # existing consumer (open, preview, thumbnail, reprojection) keeps working untouched.
    file_path: bpy.props.StringProperty(name="File Path", subtype="FILE_PATH")
    # Empty for an untiled output -- that emptiness is the tiled/untiled test everywhere.
    udim_logical_path: bpy.props.StringProperty(name="UDIM Path", subtype="FILE_PATH")
    udim_tiles: bpy.props.CollectionProperty(name="UDIM Tiles", type=MasterBakerOutputTileItem)


def output_is_tiled(output) -> bool:
    return bool(str(getattr(output, "udim_logical_path", "") or "").strip())


def output_live_tiles(output) -> list:
    """Tile rows Fyr just produced, ascending. Stale leftovers are excluded."""
    tiles = [tile for tile in getattr(output, "udim_tiles", []) or () if not bool(getattr(tile, "stale", False))]
    return sorted(tiles, key=lambda tile: int(getattr(tile, "udim_tile", 0) or 0))


def output_stale_tiles(output) -> list:
    tiles = [tile for tile in getattr(output, "udim_tiles", []) or () if bool(getattr(tile, "stale", False))]
    return sorted(tiles, key=lambda tile: int(getattr(tile, "udim_tile", 0) or 0))


def project_stale_tile_paths(project) -> list[str]:
    """Every stale concrete tile file across the project, de-duplicated, in stable order."""
    seen: set[str] = set()
    paths: list[str] = []
    for output in getattr(project, "latest_outputs", []) or ():
        for tile in output_stale_tiles(output):
            path = str(getattr(tile, "file_path", "") or "").strip()
            if path and path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


class MasterBakerBakeGroupMetadata(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="BakeGroup")
    # Empty by default: an unset link means "standalone group", and the output stem then
    # falls back to the BAKE GROUP name (naming.normalize_texture_set_name). Defaulting to
    # the literal "Default" made every out-of-box project write Default_*.tga and created a
    # phantom set with no backing texture_sets entry.
    texture_set_name: bpy.props.StringProperty(
        name="Texture Set",
        default="",
        description="Texture set this bake group belongs to. Bake groups sharing a texture set bake into one texture per map; leave it empty to bake the bake group as its own standalone texture named after the bake group",
    )
    id_collection_name: bpy.props.StringProperty(
        name="ID Collection",
        default="",
        description="Collection name that sets this bake group's ID color when Source is Collection. Leave empty to color each high mesh by its own collection",
    )
    id_color_set_name: bpy.props.StringProperty(
        name="Color Set",
        default="",
        description="Label that sets this bake group's ID color when Source is Color Set. Bake groups with the same label get the same color. Leave empty to color by Collection instead",
    )


class MasterBakerBakeGroupCollections(bpy.types.PropertyGroup):
    group_collection: bpy.props.PointerProperty(name="Group Collection", type=bpy.types.Collection, options={"HIDDEN"})
    low_collection: bpy.props.PointerProperty(name="Low Collection", type=bpy.types.Collection, options={"HIDDEN"})
    high_collection: bpy.props.PointerProperty(name="High Collection", type=bpy.types.Collection, options={"HIDDEN"})
    cage_collection: bpy.props.PointerProperty(name="Cage Collection", type=bpy.types.Collection, options={"HIDDEN"})


class MasterBakerBakeGroupRoleAssignments(bpy.types.PropertyGroup):
    low_meshes: bpy.props.CollectionProperty(name="Low Meshes", type=MasterBakerObjectSlot)
    low_mesh_index: bpy.props.IntProperty(name="Low Mesh Index", default=0, update=_overlay_static_update)
    high_meshes: bpy.props.CollectionProperty(name="High Meshes", type=MasterBakerObjectSlot)
    high_mesh_index: bpy.props.IntProperty(name="High Mesh Index", default=0, update=_overlay_static_update)
    use_low_as_high: bpy.props.BoolProperty(
        name="Use Low as High",
        default=False,
        description="Use this bake group's low-poly meshes as its projected high-poly sources without changing the saved High assignments",
        update=_group_membership_update,
    )


class MasterBakerBakeGroupProjectionSettings(bpy.types.PropertyGroup):
    uv_layer_name: bpy.props.StringProperty(
        name="UV Set",
        default="",
        description="Choose the low-poly UV layer used for baking, or leave blank to use each mesh's active UV layer",
        update=_uv_layer_update,
    )
    cage_mode: bpy.props.EnumProperty(
        name="Cage Mode",
        items=constants.CAGE_MODE_ITEMS,
        # Distance is the default, as in Painter and Marmoset. A new group's offset is
        # fitted at build time (operators._apply_estimated_cage_offsets_to_new_groups), so it needs no tuning.
        default=constants.CAGE_MODE_DISTANCE,
        update=_projection_static_visibility_update,
    )
    custom_cage: bpy.props.PointerProperty(
        name="Custom Cage",
        type=bpy.types.Object,
        poll=_mesh_object_pointer_poll,
        description="Pick a mesh object to use as the custom cage for this bake group",
        update=_custom_cage_update,
    )
    cage_offset: bpy.props.FloatProperty(
        name="Bake Group Offset",
        default=constants.DEFAULT_CAGE_OFFSET,
        precision=5,
        step=1,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        description="Set the base Distance Based cage offset shared by every low-poly mesh in this bake group",
        update=_cage_offset_update,
    )
    projection_rear_distance: bpy.props.FloatProperty(
        name="Rear Distance",
        default=0.0,
        precision=5,
        step=1,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        description="How far behind the low-poly surface a projection ray may still find the high-poly. Raise it when detail sunk into the low (a deep pocket or inset under a flat face) bakes blank however far the cage is pushed out. 0 = automatic: as deep as the cage reaches out, at least 5% of the low-poly mesh's size",
        update=_projection_static_update,
    )
    average_normals: bpy.props.BoolProperty(
        name="Average Normals",
        default=True,
        description="Average the low-poly normals across every hard edge (classic averaged cage). Off, rays follow the mesh's own normals: convex hard edges are still bridged so the projection reaches beveled corners, while concave hard edges stay split so neighbouring detail cannot leak across",
        update=_projection_static_update,
    )
    ignore_backface: bpy.props.BoolProperty(
        name="Ignore Backface",
        # On by default (Marmoset behavior): where the cage offset pokes through a
        # neighboring shell (tight crevices), the primary ray would otherwise
        # capture that shell's backface instead of the intended surface.
        default=True,
        description="Ignore backfacing high-poly hits during projection and secondary trace passes",
        options={"HIDDEN"},
        update=_projection_static_update,
    )
    match_by_isolation: bpy.props.BoolProperty(
        # The identifier stays match_by_isolation: it is serialized into presets, the job
        # format and the backend. Only the label changed, because "Isolation" never said
        # what it matched ON, and matching by name is what it actually does.
        name="Match By Mesh Name",
        default=False,
        description=(
            "Project each low-poly mesh only from the high-poly mesh whose name matches it "
            "(Wheel_low pairs with Wheel_high, Wheel_LP with Wheel_HP). Meshes with no unique "
            "match keep projecting from every high-poly in the bake group. This affects "
            "projection only: Ambient Occlusion and Thickness keep their own Same Mesh Only options"
        ),
        update=_projection_static_update,
    )


class MasterBakerBakeGroupPaintProjectionSettings(bpy.types.PropertyGroup):
    paint_offset_image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Paint Offset",
        description="Painted grayscale image controlling cage offset: white uses the full offset; black uses none",
        update=_projection_static_update,
    )
    paint_offset_scale: bpy.props.FloatProperty(
        name="Offset Scale",
        default=constants.DEFAULT_PAINT_OFFSET_SCALE,
        min=0.0,
        max=2.0,
        soft_max=2.0,
        description="Multiply the painted cage offset, or set a uniform value when no paint image is assigned",
        update=_cage_offset_update,
    )
    paint_skew_image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Paint Skew",
        description="Painted grayscale image controlling ray direction: black follows surface normals; white points toward the cage",
        update=_projection_static_update,
    )
    paint_skew: bpy.props.FloatProperty(
        name="Skew",
        default=constants.DEFAULT_PAINT_SKEW,
        min=0.0,
        max=1.0,
        description="Multiply the painted blend from the surface normals toward the cage direction",
        update=_cage_offset_update,
    )


class MasterBakerBakeGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Name",
        description="Name of this bake group",
        default="BakeGroup",
        update=_group_name_update,
    )
    # Drawn in place of name: Blender's built-in PropertyGroup.name tooltip cannot be replaced.
    ui_name: bpy.props.StringProperty(
        name="Name",
        description="Name of this bake group",
        get=_ui_name_get,
        set=_group_ui_name_set,
        options={"SKIP_SAVE"},
    )
    metadata: bpy.props.PointerProperty(name="Metadata", type=MasterBakerBakeGroupMetadata)
    collections: bpy.props.PointerProperty(name="Collections", type=MasterBakerBakeGroupCollections)
    role_assignments: bpy.props.PointerProperty(name="Role Assignments", type=MasterBakerBakeGroupRoleAssignments)
    projection_settings: bpy.props.PointerProperty(name="Projection Settings", type=MasterBakerBakeGroupProjectionSettings)
    paint_projection_settings: bpy.props.PointerProperty(name="Paint Projection Settings", type=MasterBakerBakeGroupPaintProjectionSettings)
    cage_menu_expanded: bpy.props.BoolProperty(name="Cage Menu Expanded", default=True, description="Expand this bake group in the cage menu to show its objects")
    # Display-only: hidden groups are filtered at draw assembly (build_overlay_cache),
    # not at static-cache build, so this toggle must never clear the static cache.
    cage_overlay_hidden: bpy.props.BoolProperty(name="Cage Overlay Hidden", default=False, description="Hide this bake group's cage from the viewport cage overlay", update=_overlay_dynamic_update)
    show_cage_coverage: bpy.props.BoolProperty(name="Show Cage Coverage", default=False, description="Visualize cage coverage for this bake group. Blue areas are covered; red areas are outside the cage and may produce missed rays. Texture Set and Global scopes update every group in scope", update=_cage_coverage_scope_update)
    low_material: bpy.props.PointerProperty(
        name="Only Material",
        type=bpy.types.Material,
        description=(
            "Bake only the faces of the low-poly meshes that use this material, so one mesh can "
            "feed one texture set per material. Leave empty to bake the whole meshes"
        ),
        update=_uv_layer_update,
    )
    # See MasterBakerBakeGroupMetadata.texture_set_name: empty == standalone, and the output
    # stem falls back to this bake group's own name.
    texture_set_name: bpy.props.StringProperty(
        name="Texture Set",
        default="",
        description="Texture set this bake group belongs to. Bake groups sharing a texture set bake into one texture per map; leave it empty to bake the bake group as its own standalone texture named after the bake group",
        update=_texture_set_name_update,
    )
    id_collection_name: bpy.props.StringProperty(
        name="ID Collection",
        default="",
        description="Collection name that sets this bake group's ID color when Source is Collection. Leave empty to color each high mesh by its own collection",
        update=_group_id_metadata_update,
    )
    id_color_set_name: bpy.props.StringProperty(
        name="Color Set",
        default="",
        description="Label that sets this bake group's ID color when Source is Color Set. Bake groups with the same label get the same color. Leave empty to color by Collection instead",
        update=_group_id_metadata_update,
    )
    uv_layer_name: bpy.props.StringProperty(
        name="UV Set",
        default="",
        description="Choose the low-poly UV layer used for baking, or leave blank to use each mesh's active UV layer",
        update=_uv_layer_update,
    )
    low_meshes: bpy.props.CollectionProperty(name="Low Meshes", type=MasterBakerObjectSlot)
    low_mesh_index: bpy.props.IntProperty(name="Low Mesh Index", default=0, update=_overlay_static_update)
    high_meshes: bpy.props.CollectionProperty(name="High Meshes", type=MasterBakerObjectSlot)
    high_mesh_index: bpy.props.IntProperty(name="High Mesh Index", default=0, update=_overlay_static_update)
    use_low_as_high: bpy.props.BoolProperty(
        name="Use Low as High",
        default=False,
        description="Use this bake group's low-poly meshes as its projected high-poly sources without changing the saved High assignments",
        update=_group_membership_update,
    )
    group_collection: bpy.props.PointerProperty(name="Group Collection", type=bpy.types.Collection, options={"HIDDEN"})
    low_collection: bpy.props.PointerProperty(name="Low Collection", type=bpy.types.Collection, options={"HIDDEN"})
    high_collection: bpy.props.PointerProperty(name="High Collection", type=bpy.types.Collection, options={"HIDDEN"})
    cage_collection: bpy.props.PointerProperty(name="Cage Collection", type=bpy.types.Collection, options={"HIDDEN"})
    cage_mode: bpy.props.EnumProperty(
        name="Cage Mode",
        description="How the cage is built for rays leaving the low-poly mesh",
        items=constants.CAGE_MODE_ITEMS,
        # Must match the nested projection default: this flat value is synced over it,
        # so the two always change together. Distance, as in Painter and Marmoset.
        default=constants.CAGE_MODE_DISTANCE,
        update=_cage_mode_scope_update,
    )
    custom_cage: bpy.props.PointerProperty(
        name="Custom Cage",
        type=bpy.types.Object,
        poll=_mesh_object_pointer_poll,
        description="Pick a mesh object to use as the custom cage for this bake group",
        update=_custom_cage_update,
    )
    cage_offset: bpy.props.FloatProperty(
        name="Bake Group Offset",
        default=constants.DEFAULT_CAGE_OFFSET,
        precision=5,
        step=1,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        description="Set the base Distance Based cage offset shared by every low-poly mesh in this bake group",
        update=_cage_offset_scope_update,
    )
    projection_rear_distance: bpy.props.FloatProperty(
        name="Rear Distance",
        default=0.0,
        precision=5,
        step=1,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        description="How far behind the low-poly surface a projection ray may still find the high-poly. Raise it when detail sunk into the low (a deep pocket or inset under a flat face) bakes blank however far the cage is pushed out. 0 = automatic: as deep as the cage reaches out, at least 5% of the low-poly mesh's size",
        update=_projection_rear_distance_scope_update,
    )
    average_normals: bpy.props.BoolProperty(
        name="Average Normals",
        default=True,
        description="Average the low-poly normals across every hard edge (classic averaged cage). Off, rays follow the mesh's own normals: convex hard edges are still bridged so the projection reaches beveled corners, while concave hard edges stay split so neighbouring detail cannot leak across",
        update=_average_normals_scope_update,
    )
    ignore_backface: bpy.props.BoolProperty(
        name="Ignore Backface",
        # On by default (Marmoset behavior): where the cage offset pokes through a
        # neighboring shell (tight crevices), the primary ray would otherwise
        # capture that shell's backface instead of the intended surface.
        default=True,
        description="Ignore backfacing high-poly hits during projection and secondary trace passes",
        options={"HIDDEN"},
        update=_projection_static_update,
    )
    match_by_isolation: bpy.props.BoolProperty(
        # The identifier stays match_by_isolation: it is serialized into presets, the job
        # format and the backend. Only the label changed, because "Isolation" never said
        # what it matched ON, and matching by name is what it actually does.
        name="Match By Mesh Name",
        default=False,
        description=(
            "Project each low-poly mesh only from the high-poly mesh whose name matches it "
            "(Wheel_low pairs with Wheel_high, Wheel_LP with Wheel_HP). Meshes with no unique "
            "match keep projecting from every high-poly in the bake group. This affects "
            "projection only: Ambient Occlusion and Thickness keep their own Same Mesh Only options"
        ),
        update=_match_by_isolation_scope_update,
    )
    isolate_in_viewport: bpy.props.BoolProperty(
        name="Isolate Bake Group",
        description="Hide every object outside this bake group, or restore the previous viewport visibility",
        default=False,
    )
    paint_offset_image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Paint Offset",
        description="Painted grayscale image controlling cage offset: white uses the full offset; black uses none",
        update=_projection_static_update,
    )
    paint_offset_scale: bpy.props.FloatProperty(
        name="Offset Scale",
        default=constants.DEFAULT_PAINT_OFFSET_SCALE,
        min=0.0,
        max=2.0,
        soft_max=2.0,
        description="Multiply the painted cage offset, or set a uniform value when no paint image is assigned",
        update=_cage_offset_update,
    )
    paint_skew_image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Paint Skew",
        description="Painted grayscale image controlling ray direction: black follows surface normals; white points toward the cage",
        update=_projection_static_update,
    )
    paint_skew: bpy.props.FloatProperty(
        name="Skew",
        default=constants.DEFAULT_PAINT_SKEW,
        min=0.0,
        max=1.0,
        description="Multiply the painted blend from the surface normals toward the cage direction",
        update=_cage_offset_update,
    )


class MasterBakerUdimTile(bpy.types.PropertyGroup):
    """One artist-managed UDIM tile entry on a texture set.

    In Automatic mode these rows are overrides layered on top of detected occupancy: a row
    only has to exist for a tile the artist wants to include, exclude, or re-resolution. In
    Explicit mode the rows ARE the tile list.
    """

    number: bpy.props.IntProperty(
        name="Tile",
        description="UDIM tile number (1001 + column + 10 * row)",
        default=constants.UDIM_TILE_MIN,
        min=constants.UDIM_TILE_MIN,
        max=constants.UDIM_TILE_MAX,
        update=_project_all_maps_dirty_update,
    )
    override: bpy.props.EnumProperty(
        name="Override",
        description="Force this tile to be baked or skipped regardless of detected occupancy",
        items=constants.UDIM_TILE_OVERRIDE_ITEMS,
        default=constants.UDIM_TILE_OVERRIDE_NONE,
        update=_project_all_maps_dirty_update,
    )
    use_resolution_override: bpy.props.BoolProperty(
        name="Custom Resolution",
        description="Bake this tile at its own resolution instead of the project resolution",
        default=False,
        update=_project_all_maps_dirty_update,
    )
    resolution_x: bpy.props.IntProperty(
        name="Width",
        description="Output width for this tile",
        default=constants.DEFAULT_RESOLUTION,
        min=32,
        max=16384,
        update=_project_all_maps_dirty_update,
    )
    resolution_y: bpy.props.IntProperty(
        name="Height",
        description="Output height for this tile",
        default=constants.DEFAULT_RESOLUTION,
        min=32,
        max=16384,
        update=_project_all_maps_dirty_update,
    )


class MasterBakerTextureSet(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Name",
        description="Name of this texture set. Bake groups assigned to it share one output file per map",
        default="TextureSet",
        update=_texture_set_identity_rename,
    )
    # Drawn in place of name: Blender's built-in PropertyGroup.name tooltip cannot be replaced.
    ui_name: bpy.props.StringProperty(
        name="Set Name",
        description="Name of this texture set. Bake groups assigned to it share one output file per map",
        get=_ui_name_get,
        set=_texture_set_ui_name_set,
        options={"SKIP_SAVE"},
    )
    # UDIM configuration lives on the texture set, not the bake group, because every member
    # group composites into the same logical outputs -- so the tile set has to be a property
    # of the thing being composited.
    udim_mode: bpy.props.EnumProperty(
        name="UDIM Tiles",
        description="How Fyr Baker decides which UV tiles to bake for this texture set",
        items=constants.UDIM_MODE_ITEMS,
        default=constants.UDIM_MODE_AUTOMATIC,
        update=_project_all_maps_dirty_update,
    )
    udim_tiles: bpy.props.CollectionProperty(type=MasterBakerUdimTile)
    udim_tile_active_index: bpy.props.IntProperty(
        name="Highlighted Tile",
        description="Row highlighted in the tile list only",
        default=0,
        options={"HIDDEN"},
    )
    name_mode: bpy.props.EnumProperty(
        name="Name Source",
        description="Choose how Fyr Baker names this texture set's output files",
        items=constants.TEXTURE_SET_NAME_MODE_ITEMS,
        default=constants.TEXTURE_SET_NAME_CUSTOM,
    )
    # Inert active-row indices for the "Bake Groups in Set" / "Not in Set"
    # template_lists. Kept separate from project.active_group_index on purpose:
    # highlighting a row in either list must NOT change the project-wide active group.
    member_list_active_index: bpy.props.IntProperty(
        name="Highlighted Bake Group",
        description="Row highlighted in this list only. Does not change the active bake group",
        default=0,
        options={"HIDDEN"},
    )
    nonmember_list_active_index: bpy.props.IntProperty(
        name="Highlighted Bake Group",
        description="Row highlighted in this list only. Does not change the active bake group",
        default=0,
        options={"HIDDEN"},
    )


class MasterBakerExportSetExclusion(bpy.types.PropertyGroup):
    """One texture set the Export Textures dialog must SKIP.

    Exclusions rather than inclusions on purpose: a texture set created after the
    user last opened the dialog is then included automatically, which is what an
    artist expects from "export my asset". An include-list would silently drop
    every new set until it was ticked.
    """

    name: bpy.props.StringProperty(
        name="Texture Set",
        description="Link key of the texture set (or bake group name for a standalone group) left out of the export",
        default="",
    )


class MasterBakerExportSetOverride(bpy.types.PropertyGroup):
    """Per-texture-set Size / Padding / resize-filter overrides (SP parity).

    ``GLOBAL`` on any field means "use the matching Global settings row". Rows are
    keyed by texture-set link name (same keys as ``excluded_texture_sets``).
    """

    name: bpy.props.StringProperty(
        name="Texture Set",
        description="Link key of the texture set these overrides apply to",
        default="",
    )
    size: bpy.props.EnumProperty(
        name="Size",
        items=constants.EXPORT_SET_SIZE_ITEMS,
        default=constants.EXPORT_SET_USE_GLOBAL,
        description="Export resolution for this texture set",
    )
    resize_filter: bpy.props.EnumProperty(
        name="Resize Filter",
        items=constants.EXPORT_SET_RESIZE_FILTER_ITEMS,
        default=constants.EXPORT_SET_USE_GLOBAL,
        description="Filter used when this set is resized away from the bake resolution",
    )
    padding_mode: bpy.props.EnumProperty(
        name="Padding",
        items=constants.EXPORT_SET_PADDING_MODE_ITEMS,
        default=constants.EXPORT_SET_USE_GLOBAL,
        description="UV-island padding applied when packing this texture set",
    )
    padding_size: bpy.props.IntProperty(
        name="Padding Size",
        default=16,
        min=0,
        soft_max=256,
        description="Pixel distance for Dilation Distance padding on this set",
    )


# Blender does not keep a reference to the strings an EnumProperty items callback
# returns, so the list has to stay alive in a module global or the UI shows
# garbage. See the Python API's "EnumProperty item reference" caveat.
_EXPORT_TEMPLATE_ENUM_ITEMS: list[tuple[str, str, str]] = []
_EXPORT_TEMPLATE_ENUM_EMPTY = "__NONE__"


def _export_template_enum_items(_self, _context):
    items: list[tuple[str, str, str]] = []
    try:
        # Cached: an items callback runs on every redraw of the dropdown, and
        # list_templates() reads and validates every template file.
        from . import export_dialog

        infos = export_dialog.cached_template_infos()
    except Exception:
        infos = []
    for info in infos:
        label = f"{info.name} (built-in)" if info.builtin else info.name
        items.append(
            (
                info.name,
                label,
                "Output template shipped with Fyr Baker" if info.builtin else "Output template you saved",
            )
        )
    if not items:
        items = [(_EXPORT_TEMPLATE_ENUM_EMPTY, "No templates found", "No output template files could be read")]
    _EXPORT_TEMPLATE_ENUM_ITEMS[:] = items
    return _EXPORT_TEMPLATE_ENUM_ITEMS


def _export_template_enum_update(self, _context):
    """Mirror the dropdown into the persisted name string.

    ``template`` is the source of truth because a dynamic EnumProperty stores an
    index, which would point at a different template as soon as the user adds or
    removes one.
    """
    chosen = str(getattr(self, "template_enum", "") or "")
    self.template = "" if chosen == _EXPORT_TEMPLATE_ENUM_EMPTY else chosen


class MasterBakerExportSettings(bpy.types.PropertyGroup):
    """Per-project state of the Export Textures dialog (plan D5).

    Persisted in the .blend so clicking outside the popup — which Blender treats
    as a dismissal — never loses the user's setup.
    """

    output_dir: bpy.props.StringProperty(
        name="Output Directory",
        subtype="DIR_PATH",
        default="",
        # Blender 4.2+ rejects the blend-relative "//" prefix unless the property
        # opts in; the field is empty by default and falls back to the project's
        # exports subfolder, so both states have to be legal.
        options={"PATH_SUPPORTS_BLEND_RELATIVE"},
        description="Choose the folder exported textures are written to. Leave empty to use the exports subfolder in the project's output folder",
    )
    template: bpy.props.StringProperty(
        name="Output Template",
        default="",
        description="Name of the output template that decides file names, channel packing and formats. Empty uses the default template",
    )
    template_enum: bpy.props.EnumProperty(
        name="Output Template",
        description="Choose the output template that decides file names, channel packing and formats",
        items=_export_template_enum_items,
        update=_export_template_enum_update,
        options={"SKIP_SAVE"},
    )
    file_format_override: bpy.props.EnumProperty(
        name="File Type",
        items=constants.EXPORT_IMAGE_FORMAT_OVERRIDE_ITEMS,
        default=constants.EXPORT_OVERRIDE_NONE,
        description="Write every exported texture in this file type instead of the one each template output declares",
    )
    bit_depth_override: bpy.props.EnumProperty(
        name="Bit Depth",
        items=constants.EXPORT_BIT_DEPTH_OVERRIDE_ITEMS,
        default=constants.EXPORT_OVERRIDE_NONE,
        description="Write every exported texture at this bit depth instead of the one each template output declares",
    )
    export_mesh: bpy.props.BoolProperty(
        name="Export Mesh",
        default=False,
        description="Also write each exported texture set's low-poly meshes next to its textures",
    )
    mesh_format: bpy.props.EnumProperty(
        name="Mesh Format",
        items=constants.MESH_EXPORT_FORMAT_ITEMS,
        default=constants.MESH_EXPORT_FBX,
        description="Choose the file type used for the exported low-poly meshes",
    )
    bake_missing_maps: bpy.props.BoolProperty(
        name="Bake Missing Maps First",
        default=False,
        description=(
            "Before exporting, bake any enabled map the template needs that has not "
            "been baked yet, then export automatically. Maps that are not in the map "
            "stack cannot be baked and are still skipped"
        ),
    )
    size: bpy.props.EnumProperty(
        name="Size",
        items=constants.EXPORT_SIZE_ITEMS,
        default=constants.EXPORT_SIZE_FROM_SOURCE,
        description="Global export resolution. Per-set rows can override this",
    )
    resize_filter: bpy.props.EnumProperty(
        name="Resize Filter",
        items=constants.EXPORT_RESIZE_FILTER_ITEMS,
        default=constants.EXPORT_RESIZE_FILTER_TRIANGLE,
        description="Global filter used when exporting at a different resolution than the bake",
    )
    padding_mode: bpy.props.EnumProperty(
        name="Padding",
        items=constants.EXPORT_PADDING_MODE_ITEMS,
        default=constants.EXPORT_PADDING_NONE,
        description="Global UV-island padding applied by the packer. Per-set rows can override this",
    )
    padding_size: bpy.props.IntProperty(
        name="Padding Size",
        default=16,
        min=0,
        soft_max=256,
        description="Pixel distance for Global Dilation Distance padding",
    )
    dds_compression: bpy.props.EnumProperty(
        name="DDS Compression",
        items=constants.EXPORT_DDS_COMPRESSION_ITEMS,
        default=constants.EXPORT_DDS_BC7,
        description="Block compression used when exporting DDS files",
    )
    dds_generate_mips: bpy.props.BoolProperty(
        name="Generate Mipmaps",
        default=False,
        description=(
            "Store a full mipmap chain in exported DDS files, filtered in the colour space "
            "of each output. Files grow by about a third. Leave off when the engine "
            "builds its own mipmaps on import"
        ),
    )
    dialog_tab: bpy.props.EnumProperty(
        name="Tab",
        items=constants.EXPORT_DIALOG_TAB_ITEMS,
        default=constants.EXPORT_TAB_SETTINGS,
        # Deliberately NOT SKIP_SAVE: the dialog has to reopen on the tab the user
        # left it on, because clicking outside dismisses it without warning.
        description="Section of the export dialog to show",
        options={"HIDDEN"},
    )
    active_export_target: bpy.props.StringProperty(
        name="Active Export Target",
        default=constants.EXPORT_TARGET_GLOBAL,
        description="Empty selects Global settings; otherwise the selected texture-set key",
        options={"HIDDEN"},
    )
    excluded_texture_sets: bpy.props.CollectionProperty(
        name="Excluded Texture Sets",
        type=MasterBakerExportSetExclusion,
    )
    set_overrides: bpy.props.CollectionProperty(
        name="Texture Set Overrides",
        type=MasterBakerExportSetOverride,
    )


def _live_reproject_update(self, _context):
    from . import texture_reprojection
    texture_reprojection.on_toggle(self)


def _collection_mode_update(self, context):
    """Convert the project's Outliner organization to the newly chosen mode.

    Only collections move: bake membership is the role slots, so no map is marked
    dirty and no membership cascade runs. project_structure.apply_collection_mode is
    a no-op when the mode it last applied already matches (Blender fires this on
    every assignment, including a preset load writing the same value).
    """
    from . import project_structure

    summary = None
    try:
        summary = project_structure.apply_collection_mode(context, self)
    except Exception as exc:  # never let an Outliner tidy-up break a property write
        print(f"[FyrBaker] Collection mode change failed: {exc}")
    if summary is not None:
        # The one output that DOES follow collections: an ID map sourced by Collection
        # colors each source mesh by the collection it resolves to (Fyr's tagged
        # "<Group>_High" in FYR mode, the artist's own collection otherwise), unless the
        # group pins an ID Collection name. Every other map is untouched.
        if any(
            bool(getattr(item, "enabled", True))
            and not bool(getattr(item, "is_add_phantom", False))
            and str(getattr(item, "map_type", "") or "") == constants.MAP_ID
            and str(getattr(item, "id_source", "") or "") == constants.MAP_ID_SOURCE_COLLECTION
            for item in getattr(self, "maps", []) or []
        ):
            _mark_project_dirty(context, project=self, map_types=[constants.MAP_ID])
    window_manager = getattr(context, "window_manager", None)
    for window in getattr(window_manager, "windows", ()) or ():
        for area in getattr(getattr(window, "screen", None), "areas", ()) or ():
            if getattr(area, "type", "") in {"OUTLINER", "VIEW_3D"}:
                try:
                    area.tag_redraw()
                except Exception:
                    pass


class MasterBakerMaterialBindingSuppression(bpy.types.PropertyGroup):
    """User-deleted auto-detected material binding that should not be recreated until restored."""

    binding_key: bpy.props.StringProperty(name="Binding Key", default="")


class MasterBakerBakeProject(bpy.types.PropertyGroup):
    # Scene Blockers: meshes outside the bake groups that shade the whole-scene lighting
    # (walls, ceilings, props) without textures of their own.
    scene_blockers: bpy.props.PointerProperty(
        name="Scene Blockers",
        type=bpy.types.Collection,
        description=(
            "Meshes that cast shadows and bounce light into Scene Lighting maps that include other "
            "groups, without getting textures of their own (walls, ceilings, props)"
        ),
    )
    use_scene_blockers: bpy.props.BoolProperty(
        name="Use Scene Blockers",
        default=True,
        description="Let the Scene Blockers collection shade this project's Scene Lighting maps",
    )
    scene_blockers_cast_shadows: bpy.props.BoolProperty(
        name="Cast Shadows",
        default=True,
        description="Scene blockers block light: lamps, sky and glowing surfaces cast their shadows",
    )
    scene_blockers_bounce_light: bpy.props.BoolProperty(
        name="Bounce Light",
        default=True,
        description="Light bounces off scene blockers in their material colour. Off, they reflect no light but still block it",
    )
    # Stored-state schema stamp. 0 = saved before schema migrations existed; upgraded
    # by properties.migrate_project_schema (called from ensure_default_maps) so each
    # one-time migration step runs exactly once per project.
    schema_version: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    # Product/UI workflow. HIGH_TO_LOW is the existing projected-bake workflow and the
    # default for every project saved before this field existed (Blender applies the
    # EnumProperty default on load, so no schema migration is required). MATERIAL is the
    # same-object material-flatten workflow with no high-poly role. This is a distinct
    # axis from bake_mode (quality) and hierarchy_focus (UI). See
    # docs/MATERIAL_BAKING_WORKFLOW_PLAN.md. Never inferred from whether a high-mesh list
    # happens to be empty.
    workflow: bpy.props.EnumProperty(
        name="Workflow",
        items=constants.WORKFLOW_ITEMS,
        default=constants.WORKFLOW_HIGH_TO_LOW,
        description="Whether this project projects high-poly detail onto low-poly targets or flattens the selected objects' own materials",
        options={"HIDDEN"},
    )
    material_profile: bpy.props.EnumProperty(
        name="Material Profile",
        items=constants.MATERIAL_PROFILE_ITEMS,
        default=constants.MATERIAL_PROFILE_STANDARD,
        description="Which Principled channels automatic material capture treats as meaningful",
    )
    material_binding_suppressions: bpy.props.CollectionProperty(
        name="Suppressed Material Bindings",
        type=MasterBakerMaterialBindingSuppression,
    )
    name: bpy.props.StringProperty(
        name="Project Name",
        description="Name of this bake project",
        default="BakeProject",
        update=_project_name_update,
    )
    # Drawn in place of name: Blender's built-in PropertyGroup.name tooltip cannot be replaced.
    ui_name: bpy.props.StringProperty(
        name="Project Name",
        description="Name of this bake project",
        get=_ui_name_get,
        set=_project_ui_name_set,
        options={"SKIP_SAVE"},
    )
    live_reproject: bpy.props.BoolProperty(
        name="Live Reproject",
        description="Keep baked textures aligned while editing compatible UVs; settled edits replace outputs",
        default=False,
        update=_live_reproject_update,
    )
    reproject_generation: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    reproject_status: bpy.props.StringProperty(default="", options={"HIDDEN"})
    reproject_error: bpy.props.StringProperty(default="", options={"HIDDEN"})
    root_collection: bpy.props.PointerProperty(name="Project Collection", type=bpy.types.Collection, options={"HIDDEN"})
    # FYR is the default so every project saved before this field existed keeps its
    # scaffold with no migration (Blender applies the EnumProperty default on load).
    collection_mode: bpy.props.EnumProperty(
        name="Collections",
        items=constants.COLLECTION_MODE_ITEMS,
        default=constants.COLLECTION_MODE_FYR,
        description="Whether Fyr organizes this project's objects into its own collections or leaves them in yours",
        update=_collection_mode_update,
    )
    output_root: bpy.props.StringProperty(
        name="Output Root",
        subtype="DIR_PATH",
        default="//FyrBaker",
        # Blender 4.2+ rejects the blend-relative "//" prefix on path properties
        # unless they opt in with this flag. Without it the default "//FyrBaker"
        # renders the field red and spams "does not support blend relative //" warnings.
        options={"PATH_SUPPORTS_BLEND_RELATIVE"},
        description="Choose the folder for baked textures and temporary bake data",
        update=_project_all_maps_dirty_update,
    )
    resolution_preset: bpy.props.EnumProperty(
        name="Size",
        description="Square output size. Sets both width and height",
        items=constants.OUTPUT_SIZE_ITEMS,
        default=constants.OUTPUT_SIZE_2048,
        update=_resolution_preset_update,
    )
    lock_resolution: bpy.props.BoolProperty(
        name="Link Resolution",
        default=True,
        description="Keep Y the same as X for square output sizes",
        update=_resolution_lock_update,
    )
    resolution_x: bpy.props.IntProperty(
        name="Width",
        description="Output width in pixels",
        default=constants.DEFAULT_RESOLUTION,
        min=32,
        soft_max=16384,
        update=_resolution_x_update,
    )
    resolution_y: bpy.props.IntProperty(
        name="Height",
        description="Output height in pixels. Matches the width while resolution is linked",
        default=constants.DEFAULT_RESOLUTION,
        min=32,
        soft_max=16384,
        update=_resolution_y_update,
    )
    bit_depth: bpy.props.EnumProperty(name="Bit Depth", description="Bits per channel of the written maps. 16-bit, the default, keeps the gradients of Height, Position, Thickness and Bent Normal; 8-bit bands them but writes smaller files", items=constants.BIT_DEPTH_ITEMS, default=constants.DEFAULT_BIT_DEPTH, update=_project_all_maps_dirty_update)
    image_format: bpy.props.EnumProperty(
        name="Image Format",
        description="File format written for every baked map in this project",
        items=constants.IMAGE_FORMAT_ITEMS,
        default=constants.DEFAULT_IMAGE_FORMAT,
        update=_project_all_maps_dirty_update,
    )
    # Legacy control, kept DEFINED so pre-samples .blend files load cleanly and
    # for graceful degradation against older backends. Hidden from the UI; new
    # code reads aa_samples (see resolve_aa_samples) instead.
    anti_aliasing: bpy.props.EnumProperty(
        name="Samples",
        description="Set the anti-aliasing samples accumulated for each output pixel",
        items=constants.ANTI_ALIASING_ITEMS,
        default=constants.DEFAULT_ANTI_ALIASING,
        update=_project_all_maps_dirty_update,
    )
    aa_samples: bpy.props.IntProperty(
        name="Samples",
        description=(
            "Anti-aliasing samples per output pixel, applied to every baked map. "
            "More samples smooth edges and fine detail but increase bake time. "
            "Set to 0 to turn anti-aliasing off"
        ),
        default=constants.DEFAULT_AA_SAMPLES,
        min=constants.AA_SAMPLES_UI_MIN,
        max=constants.AA_SAMPLES_MAX,
        update=_aa_samples_update,
    )
    bevel_connected_only: bpy.props.BoolProperty(
        name="Bevel Connected Only",
        default=True,
        description=(
            "A Bevel shader on the high-poly rounds only the connected piece it is on. "
            "Off, it also rounds toward separate loose pieces of the same object that "
            "sit within the bevel radius, as Cycles does (keys resting on a base merge "
            "into it)"
        ),
    )
    soften: bpy.props.FloatProperty(
        name="Soften",
        default=constants.DEFAULT_SOFTEN,
        min=0.0,
        max=constants.SOFTEN_MAX,
        soft_max=constants.SOFTEN_MAX,
        description=(
            "Blur every baked map in this project after baking. The value is the blur radius in "
            "texels; 0, the default, leaves the raw bake untouched. Individual maps can opt out "
            "with Override Soften"
        ),
        update=_project_all_maps_dirty_update,
    )
    margin_mode: bpy.props.EnumProperty(
        name="Dilation",
        description="How far baked colors extend past UV islands. Distance uses the pixel count; Infinite fills every uncovered pixel",
        items=constants.DILATION_MODE_ITEMS,
        default=constants.DILATION_DISTANCE,
        update=_project_margin_update,
    )
    margin: bpy.props.IntProperty(
        name="Dilation",
        default=constants.DEFAULT_MARGIN,
        min=0,
        soft_max=128,
        description="Extend baked colors outward from UV islands by this many pixels to reduce visible seams",
        update=_project_margin_update,
    )
    tangent_basis: bpy.props.EnumProperty(
        name="Tangent Basis",
        items=constants.TANGENT_BASIS_ITEMS,
        default=constants.TANGENT_MIKKTSPACE,
        update=_project_tangent_basis_update,
    )
    ignore_backface: bpy.props.BoolProperty(
        name="Ignore Backface",
        # On by default (Marmoset behavior) — see the group-level flag.
        default=True,
        description="Ignore backfacing high-poly hits during projection for every bake group in this project",
        update=_project_ignore_backface_update,
    )
    respect_opacity: bpy.props.BoolProperty(
        name="Respect Opacity",
        default=True,
        description="Let projection and secondary bake rays pass through transparent texels in supported high-poly materials",
        update=_project_all_maps_dirty_update,
    )
    bake_mode: bpy.props.EnumProperty(name="Bake Mode", items=constants.BAKE_MODE_ITEMS, default=constants.BAKE_MODE_OFFLINE, update=_project_all_maps_dirty_update)
    denoise_quality: bpy.props.EnumProperty(
        name="Denoise Quality",
        items=[
            ("HIGH", "High", "High quality denoising. Most aggressive smoothing, slowest"),
            ("BALANCED", "Balanced", "Balanced quality and performance. Less aggressive than High, preserves more fine detail"),
            ("FAST", "Fast", "Fast denoising. Lightest touch, fastest, intended for previews"),
        ],
        default="HIGH",
        description="OIDN denoising model quality applied to every denoised map. Balanced and Fast use simpler models that preserve more high-frequency detail and are faster to run",
        update=_project_all_maps_dirty_update,
    )
    denoise_strength: bpy.props.FloatProperty(
        name="Denoise Strength",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Blend between the raw baked result (0) and the fully denoised result (1), applied to every denoised map. Lower values keep more detail and reduce over-smoothing or denoiser artifacts",
        update=_project_all_maps_dirty_update,
    )
    maps: bpy.props.CollectionProperty(name="Texture Maps", type=MasterBakerMapSetting)
    active_map_index: bpy.props.IntProperty(name="Map Index", default=0)
    texture_sets: bpy.props.CollectionProperty(name="Texture Sets", type=MasterBakerTextureSet)
    active_texture_set_index: bpy.props.IntProperty(name="Texture Set Index", default=0)
    hierarchy_focus: bpy.props.EnumProperty(
        name="Hierarchy Focus",
        description="Choose whether the settings panel shows the active bake group or texture set",
        items=constants.HIERARCHY_FOCUS_ITEMS,
        default=constants.HIERARCHY_FOCUS_GROUP,
        options={"HIDDEN"},
    )
    groups: bpy.props.CollectionProperty(name="Bake Groups", type=MasterBakerBakeGroup)
    active_group_index: bpy.props.IntProperty(name="Bake Group Index", default=0, update=_overlay_static_visibility_update)
    latest_outputs: bpy.props.CollectionProperty(name="Latest Outputs", type=MasterBakerOutputImageItem)
    active_output_index: bpy.props.IntProperty(name="Output Index", default=0)
    last_job_id: bpy.props.StringProperty(name="Last Job ID", default="")
    last_workspace_path: bpy.props.StringProperty(name="Last Workspace", subtype="DIR_PATH", default="")
    # Workspace of the last workspace a bake actually RAN in. `last_workspace_path`
    # is stamped by every prepare_bake_job call, including the speculative background
    # prepare that fires after edits and reloads, so it routinely points at a
    # workspace where no bake ever happened. The support bundle collected from such a
    # workspace carries no bake evidence at all: no backend_run.log, a progress file
    # still reading "Bake workspace exported", and a GPU log with only prepare-scope
    # timings. That is worse than useless when a tester is reporting a slow or hung
    # bake, so the bundle resolves through this bake-only pointer first.
    last_bake_workspace_path: bpy.props.StringProperty(name="Last Bake Workspace", subtype="DIR_PATH", default="")
    # Job id of the last bake that actually LAUNCHED. Same reasoning as
    # last_bake_workspace_path: `last_job_id` is stamped by every prepare, so a
    # speculative one landing mid-bake would orphan the run from the callbacks that
    # look its project up by id.
    last_bake_job_id: bpy.props.StringProperty(name="Last Bake Job Id", default="")
    last_bake_job_path: bpy.props.StringProperty(name="Last Bake Job Path", default="", options={"HIDDEN"})
    last_output_dir: bpy.props.StringProperty(name="Last Output Dir", default="")
    last_progress_percent: bpy.props.FloatProperty(name="Last Progress Percent", default=0.0, min=0.0, max=100.0)
    last_stage_progress_percent: bpy.props.FloatProperty(name="Last Stage Progress Percent", default=-1.0, min=-1.0, max=100.0)
    last_active_group: bpy.props.StringProperty(name="Last Active Bake Group", default="")
    last_active_map: bpy.props.StringProperty(name="Last Active Map", default="")
    last_warning_count: bpy.props.IntProperty(name="Last Warning Count", default=0, min=0)
    last_error_count: bpy.props.IntProperty(name="Last Error Count", default=0, min=0)
    last_warning_summary: bpy.props.StringProperty(name="Last Warning Summary", default="")
    last_error_summary: bpy.props.StringProperty(name="Last Error Summary", default="")
    last_status_message: bpy.props.StringProperty(name="Status", default=constants.STATUS_IDLE)
    last_baked_maps_state: bpy.props.StringProperty(name="Last Baked Maps State", default="", options={"HIDDEN"})
    active_bake_map_types: bpy.props.StringProperty(name="Active Bake Map Types", default="", options={"HIDDEN"})
    active_bake_map_uuids: bpy.props.StringProperty(name="Active Bake Map UUIDs", default="", options={"HIDDEN"})
    active_bake_group_names: bpy.props.StringProperty(name="Active Bake Group Names", default="", options={"HIDDEN"})
    last_incremental_bake_groups: bpy.props.StringProperty(name="Last Incremental Bake Groups", default="", options={"HIDDEN"})
    last_bake_duration_seconds: bpy.props.FloatProperty(name="Last Bake Duration Seconds", default=0.0, min=0.0, options={"HIDDEN"})
    last_bake_cache_state: bpy.props.StringProperty(name="Last Bake Cache State", default="", options={"HIDDEN"})
    # Export Textures dialog state. A separate product from the bake outputs above:
    # exporting never touches latest_outputs (plan section 4 step 6).
    export_settings: bpy.props.PointerProperty(name="Export Settings", type=MasterBakerExportSettings)


class MasterBakerImageEditorState(bpy.types.PropertyGroup):
    channel_mode: bpy.props.EnumProperty(
        name="Channels",
        items=constants.IMAGE_CHANNEL_MODE_ITEMS,
        default=constants.IMAGE_CHANNEL_COLOR,
    )
    mip_level: bpy.props.IntProperty(
        name="Mip Level",
        default=0,
        min=0,
        max=constants.IMAGE_EDITOR_MAX_MIP_LEVEL,
    )
    inspect_expanded: bpy.props.BoolProperty(name="Inspect Expanded", default=True)
    job_status_expanded: bpy.props.BoolProperty(name="Job Status Expanded", default=False)
    compare_enabled: bpy.props.BoolProperty(name="Compare Mode", default=False)
    compare_active_slot: bpy.props.EnumProperty(
        name="Compare Output",
        items=(
            ("A", "A", "Primary compare output"),
            ("B", "B", "Secondary compare output"),
        ),
        default="A",
    )
    compare_a_index: bpy.props.IntProperty(name="Compare A Index", default=-1)
    compare_b_index: bpy.props.IntProperty(name="Compare B Index", default=-1)


_HIERARCHY_ROW_INDEX_SYNCING = False


def _hierarchy_row_index_update(self, context):
    """A click on a hierarchy list row selects that row's bake group.

    Group and mesh names are rename fields (double-click edits them), so a plain
    click lands on the list row itself. Mesh rows also select their object. A
    group row makes its group the only active
    one, like a plain click in the header dropdown. A child row (mesh, cage) of a
    group that is already open just makes that group active. The highlight then
    snaps back to the active group's row, since the highlight means "active group".
    The hierarchy timer also writes this index; for the active row that is a no-op.
    """
    global _HIERARCHY_ROW_INDEX_SYNCING
    if _HIERARCHY_ROW_INDEX_SYNCING:
        return
    rows = getattr(self, "hierarchy_rows", None)
    index = int(getattr(self, "hierarchy_row_index", -1))
    if rows is None or not (0 <= index < len(rows)):
        return
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    project = get_active_project(scene)
    if project is None:
        return
    groups = getattr(project, "groups", None) or []
    row = rows[index]
    group_index = int(getattr(row, "group_index", -1))
    if str(getattr(row, "kind", "") or "") == "mesh" and 0 <= group_index < len(groups):
        role_state = group_role_assignments_state(groups[group_index])
        attr = "low_meshes" if row.role == "low" else "high_meshes"
        slots = getattr(role_state, attr, ())
        if 0 <= row.slot_index < len(slots):
            obj = slots[row.slot_index].object_ref
            if obj is not None:
                bpy.ops.master_baker.select_cage_object(object_name=obj.name)
    if 0 <= group_index < len(groups):
        is_group_row = str(getattr(row, "kind", "") or "") == "group"
        focus_is_group = str(getattr(project, "hierarchy_focus", "") or "") == constants.HIERARCHY_FOCUS_GROUP
        if int(getattr(project, "active_group_index", -1)) != group_index or not focus_is_group:
            project.active_group_index = group_index
            project.hierarchy_focus = constants.HIERARCHY_FOCUS_GROUP
            if is_group_row:
                set_bake_group_targets(settings, [])
    active_index = int(getattr(project, "active_group_index", -1))
    focused = next(
        (
            position
            for position, slot in enumerate(rows)
            if str(getattr(slot, "kind", "") or "") == "group" and int(getattr(slot, "group_index", -1)) == active_index
        ),
        -1,
    )
    if focused >= 0 and focused != index:
        _HIERARCHY_ROW_INDEX_SYNCING = True
        try:
            self.hierarchy_row_index = focused
        finally:
            _HIERARCHY_ROW_INDEX_SYNCING = False


def set_hierarchy_row_index_quietly(ui_state, value: int) -> None:
    """Move the hierarchy highlight without treating it as a click on that row."""
    global _HIERARCHY_ROW_INDEX_SYNCING
    if int(getattr(ui_state, "hierarchy_row_index", -1)) == int(value):
        return
    _HIERARCHY_ROW_INDEX_SYNCING = True
    try:
        ui_state.hierarchy_row_index = int(value)
    finally:
        _HIERARCHY_ROW_INDEX_SYNCING = False


class MasterBakerHierarchyRow(bpy.types.PropertyGroup):
    """One visible line in the scrolling hierarchy list.

    Filled from a timer, never from panel draw. Draw only reads these fields.
    """

    kind: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    set_name: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    group_index: bpy.props.IntProperty(default=-1, options={"HIDDEN", "SKIP_SAVE"})
    member_indices: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    is_expanded: bpy.props.BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})
    is_last: bpy.props.BoolProperty(default=True, options={"HIDDEN", "SKIP_SAVE"})
    prefix: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    role: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    role_icon: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    slot_index: bpy.props.IntProperty(default=-1, options={"HIDDEN", "SKIP_SAVE"})
    glyph: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    operator_id: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    aspect: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})


class MasterBakerUiState(bpy.types.PropertyGroup):
    map_catalog_search: bpy.props.StringProperty(
        name="Search Maps",
        description="Filter the map catalog by map or category name",
        default="",
        options={"TEXTEDIT_UPDATE"},
    )
    sidebar_primary_section: bpy.props.EnumProperty(
        name="Sidebar Primary Section",
        items=constants.SIDEBAR_SECTION_ITEMS,
        default=constants.SIDEBAR_MESHES,
    )
    sidebar_selected_sections: bpy.props.StringProperty(
        name="Sidebar Selected Sections",
        default=constants.SIDEBAR_MESHES,
    )
    bake_panel_section: bpy.props.EnumProperty(
        name="Bake Panel Section",
        items=constants.BAKE_PANEL_SECTION_ITEMS,
        default=constants.BAKE_PANEL_SETTINGS,
    )
    hierarchy_collapsed_sets: bpy.props.StringProperty(
        name="Collapsed Texture Sets",
        description="Stores which texture sets are collapsed in the hierarchy",
        default="",
        options={"HIDDEN"},
    )
    # Length-only mirror of the visible hierarchy rows. SKIP_SAVE so the blend
    # file does not keep a stale copy; the panel rebuilds the length on draw.
    hierarchy_rows: bpy.props.CollectionProperty(type=MasterBakerHierarchyRow, options={"HIDDEN", "SKIP_SAVE"})
    hierarchy_row_index: bpy.props.IntProperty(
        name="Hierarchy Row",
        default=0,
        options={"HIDDEN", "SKIP_SAVE"},
        update=_hierarchy_row_index_update,
    )
    hierarchy_row_signature: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    auto_texture_set_mode: bpy.props.EnumProperty(
        name="Texture Sets",
        description="Choose how automatic grouping assigns bake groups to texture sets",
        items=constants.AUTO_TEXTURE_SET_MODE_ITEMS,
        default=constants.AUTO_TEXTURE_SET_PER_MATERIAL,
    )
    auto_group_granularity: bpy.props.EnumProperty(
        name="Bake Groups",
        description="Choose whether automatic grouping makes one bake group per name prefix or one per part",
        items=constants.AUTO_GROUP_GRANULARITY_ITEMS,
        default=constants.AUTO_GROUP_GRANULARITY_PART,
    )
    cage_settings_scope: bpy.props.EnumProperty(
        name="Apply Cage Settings To",
        description=(
            "Choose which bake groups receive cage-setting changes. Bake Group affects only the "
            "active group; Selected, Texture Set and Global also update the other groups in that "
            "scope. Resets to Bake Group each session"
        ),
        items=constants.CAGE_SETTINGS_SCOPE_ITEMS,
        default=constants.CAGE_SCOPE_BAKE_GROUP,
        options={"SKIP_SAVE"},
    )
    reveal_hierarchy_context: bpy.props.BoolProperty(
        name="Reveal Hierarchy Context",
        description="Show the focused texture set or bake group settings expanded after creating one from the header",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    bake_group_targets: bpy.props.StringProperty(
        name="Bake Group Targets",
        description="Bake groups included from the header menu. Shift-click adds or removes a group; setting changes apply to every included group",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    setup_project_expanded: bpy.props.BoolProperty(name="Setup Project Expanded", default=True)
    cage_debug_expanded: bpy.props.BoolProperty(name="Cage Debug Expanded", default=True)
    skew_debug_expanded: bpy.props.BoolProperty(name="Skew Debug Expanded", default=True)
    viewport_low_reference_expanded: bpy.props.BoolProperty(name="Low Mesh Expanded", default=False)
    viewport_high_reference_expanded: bpy.props.BoolProperty(name="High Mesh Expanded", default=True)
    viewport_cage_overlay_expanded: bpy.props.BoolProperty(name="Cage Overlay Expanded", default=True)
    viewport_debug_expanded: bpy.props.BoolProperty(name="Viewport Debug Expanded", default=False)
    selected_group_cage_offset: bpy.props.FloatProperty(
        name="Selected Base",
        default=0.0,
        precision=5,
        step=1,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        description="Set the base Distance Based cage offset for the bake groups containing the selected low-poly meshes",
        get=_selected_group_cage_offset_get,
        set=_selected_group_cage_offset_set,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    selected_low_cage_offset: bpy.props.FloatProperty(
        name="Selected Offset",
        default=0.0,
        precision=5,
        step=1,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        description="Set the final Distance Based cage offset for the selected low-poly meshes",
        get=_selected_low_cage_offset_get,
        set=_selected_low_cage_offset_set,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    # Cage offset slider: one proxy per range (see CAGE_OFFSET_SLIDER_RANGES).
    cage_offset_final_r001: _cage_offset_proxy(0.01)
    cage_offset_final_r01: _cage_offset_proxy(0.1)
    cage_offset_final_r1: _cage_offset_proxy(1.0)
    cage_offset_final_r10: _cage_offset_proxy(10.0)


class MasterBakerPreviewSessionState(bpy.types.PropertyGroup):
    preview_on_low_active: bpy.props.BoolProperty(name="Preview On Low Active", default=False, options={"HIDDEN"})
    preview_on_low_project_name: bpy.props.StringProperty(name="Preview On Low Project", default="", options={"HIDDEN"})
    preview_on_low_group_name: bpy.props.StringProperty(name="Preview On Low Group", default="", options={"HIDDEN"})
    preview_on_low_map_uuid: bpy.props.StringProperty(name="Preview On Low Map UUID", default="", options={"HIDDEN"})
    preview_on_low_map_type: bpy.props.StringProperty(name="Preview On Low Map", default="", options={"HIDDEN"})
    preview_on_low_map_index: bpy.props.IntProperty(name="Preview On Low Map Index", default=-1, options={"HIDDEN"})
    preview_on_low_output_suffix: bpy.props.StringProperty(name="Preview On Low Output Suffix", default="", options={"HIDDEN"})
    preview_on_low_scope: bpy.props.EnumProperty(
        name="Preview On Low Scope",
        items=constants.PREVIEW_ON_LOW_SCOPE_ITEMS,
        default=constants.PREVIEW_ON_LOW_SCOPE_ALL_GROUPS,
        options={"HIDDEN"},
    )
    preview_pbr_on_low_active: bpy.props.BoolProperty(name="Preview PBR On Low Active", default=False, options={"HIDDEN"})
    preview_pbr_on_low_project_name: bpy.props.StringProperty(name="Preview PBR On Low Project", default="", options={"HIDDEN"})
    preview_pbr_on_low_group_name: bpy.props.StringProperty(name="Preview PBR On Low Group", default="", options={"HIDDEN"})
    pbr_preview_normal_source: bpy.props.EnumProperty(
        name="Normal Source",
        items=constants.PBR_PREVIEW_NORMAL_SOURCE_ITEMS,
        default=constants.PBR_PREVIEW_NORMAL_TANGENT,
        options={"HIDDEN"},
    )
    pbr_preview_ao_strength: bpy.props.FloatProperty(
        name="AO Strength",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Blend the baked ambient occlusion into the material preview",
        options={"HIDDEN", "SKIP_SAVE"},
        update=_preview_material_setting_update,
    )
    preview_environment_rotation: bpy.props.FloatProperty(
        name="Rotation",
        default=0.0,
        min=-3.141592653589793,
        max=3.141592653589793,
        subtype="ANGLE",
        description="Rotate the Material Preview studio environment around the vertical axis",
        options={"HIDDEN", "SKIP_SAVE"},
        update=_preview_environment_update,
    )
    preview_environment_strength: bpy.props.FloatProperty(
        name="Strength",
        default=1.0,
        min=0.0,
        max=2.0,
        soft_max=1.5,
        description="Control the Material Preview studio environment intensity",
        options={"HIDDEN", "SKIP_SAVE"},
        update=_preview_environment_update,
    )
    preview_environment_show_background: bpy.props.BoolProperty(
        name="Show Background",
        default=False,
        description="Show the studio environment behind the previewed meshes",
        options={"HIDDEN", "SKIP_SAVE"},
        update=_preview_environment_update,
    )
    live_bake_active: bpy.props.BoolProperty(name="Live Bake Active", default=False, options={"HIDDEN", "SKIP_SAVE"})
    live_bake_project_name: bpy.props.StringProperty(name="Live Bake Project", default="", options={"HIDDEN", "SKIP_SAVE"})
    live_bake_project_index: bpy.props.IntProperty(name="Live Bake Project Index", default=-1, options={"HIDDEN", "SKIP_SAVE"})
    live_normal_preview_active: bpy.props.BoolProperty(name="Live Normal Preview Active", default=False, options={"HIDDEN"})
    live_normal_preview_scene_name: bpy.props.StringProperty(name="Live Normal Preview Scene", default="", options={"HIDDEN"})
    live_normal_preview_project_name: bpy.props.StringProperty(name="Live Normal Preview Project", default="", options={"HIDDEN"})
    live_normal_preview_group_name: bpy.props.StringProperty(name="Live Normal Preview Group", default="", options={"HIDDEN"})
    live_normal_preview_output_path: bpy.props.StringProperty(name="Live Normal Preview Output", default="", options={"HIDDEN"})
    preview_on_low_restore_show_cage_overlay: bpy.props.BoolProperty(
        name="Preview On Low Restore Cage Overlay",
        default=False,
        options={"HIDDEN"},
    )
    preview_on_low_restore_show_error_heatmap: bpy.props.BoolProperty(
        name="Preview On Low Restore Heatmap",
        default=False,
        options={"HIDDEN"},
    )
    preview_on_low_restore_show_ray_miss_debug: bpy.props.BoolProperty(
        name="Preview On Low Restore Ray Misses",
        default=False,
        options={"HIDDEN"},
    )
    preview_on_low_restore_viewport_state: bpy.props.StringProperty(
        name="Preview On Low Restore Viewport State",
        default="",
        options={"HIDDEN"},
    )
    preview_on_low_restore_high_visibility: bpy.props.StringProperty(
        name="Preview On Low Restore High Visibility",
        default="",
        options={"HIDDEN"},
    )
    material_ab_compare_active: bpy.props.BoolProperty(
        name="Material A/B Compare Active",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    material_ab_compare_side: bpy.props.StringProperty(
        name="Material A/B Compare Side",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    material_ab_compare_project_name: bpy.props.StringProperty(
        name="Material A/B Compare Project",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    material_ab_compare_restore_visibility: bpy.props.StringProperty(
        name="Material A/B Compare Restore Visibility",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    material_ab_compare_had_preview: bpy.props.BoolProperty(
        name="Material A/B Compare Had Preview",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )


class MasterBakerViewportOverlaySettings(bpy.types.PropertyGroup):
    show_cage_overlay: bpy.props.BoolProperty(
        name="Show Cage",
        default=True,
        description=(
            "Show the cage and its coverage in the viewport, hiding the high-poly meshes "
            "while it is on. Skew needles have their own toggle"
        ),
        update=_overlay_visibility_update,
    )
    cage_preview_scope: bpy.props.EnumProperty(
        name="Preview Scope",
        items=constants.CAGE_PREVIEW_SCOPE_ITEMS,
        default=constants.CAGE_PREVIEW_SCOPE_SELECTED_LOW_MESHES,
        description="Choose whether Cage Mode previews the active bake group or selected low-poly meshes",
        # Target resolution is hierarchy-driven (scope no longer changes which cages
        # are built), so this is display-only: no static rebuild on change.
        update=_overlay_dynamic_update,
    )
    auto_select_group_on_selection: bpy.props.BoolProperty(
        name="Auto-Select Bake Group on Selection",
        default=False,
        description="Automatically switch to the bake group containing the selected object",
    )
    show_cage_surface: bpy.props.BoolProperty(
        name="Show Cage Surface",
        default=True,
        description="Show the cage surface overlay",
        # Display-only toggle: consumed in build_overlay_cache and part of the
        # display key, so the (cheap) display cache rebuilds on its own. It never
        # affects the static cache contents, so avoid forcing a full static
        # rebuild here — that is what made this checkbox stutter the viewport.
        update=_overlay_dynamic_update,
    )
    cage_surface_color: bpy.props.FloatVectorProperty(
        name="Cage Surface Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.18, 0.88, 0.46),
        description="Viewport color for the cage surface overlay",
        # Color is a draw-time uniform / display-key entry, not baked into the
        # static batches — dynamic update keeps color-picker drags smooth.
        update=_overlay_dynamic_update,
    )
    show_cage_wireframe: bpy.props.BoolProperty(
        name="Show Cage Wireframe",
        default=True,
        description="Show the cage wireframe overlay",
        # See show_cage_surface: display-only, no static rebuild required.
        update=_overlay_dynamic_update,
    )
    cage_wireframe_color: bpy.props.FloatVectorProperty(
        name="Cage Wireframe Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.32, 1.0, 0.62),
        description="Viewport color for the cage wireframe overlay",
        update=_overlay_dynamic_update,
    )
    show_skew_debug: bpy.props.BoolProperty(
        name="Show Skew Needles",
        default=False,
        description=(
            "Draw the bake's projection rays as needles on the low-poly surface, "
            "independent of the cage overlay. Green needles leave the face straight; "
            "amber ones are tilted, by Smooth Cage at hard corners or by Paint Skew "
            "with a custom or automatic cage"
        ),
        update=_overlay_dynamic_update,
    )
    show_ray_miss_debug: bpy.props.BoolProperty(
        name="Show Ray Misses",
        default=False,
        description="Visualize projection rays that miss the matched high-poly mesh",
        # Miss lines come from the async debug-overlay result, not the static cache;
        # the dynamic update redraws and requests a debug refresh without a rebuild.
        update=_overlay_dynamic_update,
    )
    skew_debug_length: bpy.props.FloatProperty(
        name="Ray Length",
        default=constants.VIEWPORT_SKEW_LINE_LENGTH_SCALE,
        min=0.005,
        soft_max=0.25,
        precision=3,
        subtype="FACTOR",
        description="Control the length of the skew-direction lines shown on the low-poly surface",
        update=_overlay_dynamic_update,
    )
    skew_debug_constant_screen_size: bpy.props.BoolProperty(
        name="Constant Screen Size",
        default=False,
        description="Keep the skew needles the same length on screen regardless of zoom, like the Normals overlay",
        # A draw-time uniform, not a field input: no rebuild, only a redraw.
        update=_overlay_dynamic_update,
    )
    show_error_heatmap: bpy.props.BoolProperty(
        name="Heatmap",
        default=False,
        description="Visualize cage coverage on the low-poly surface. Covered areas use the Inside color; uncovered areas use the Outside color",
        update=_heatmap_preview_update,
    )
    heatmap_inside_color: bpy.props.FloatVectorProperty(
        name="Heatmap Inside Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.12, 0.46, 1.0),
        description="Set the color for low-poly regions covered by the cage",
        update=_heatmap_preview_update,
    )
    heatmap_outside_color: bpy.props.FloatVectorProperty(
        name="Heatmap Outside Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 0.08, 0.08),
        description="Set the color for low-poly regions outside the cage",
        update=_heatmap_preview_update,
    )
    cage_opacity: bpy.props.FloatProperty(
        name="Cage Opacity",
        default=1.0,
        min=0.05,
        max=1.0,
        precision=2,
        subtype="FACTOR",
        description="Control the opacity of the cage preview shell",
        update=_overlay_static_update,
    )
    cage_surface_opacity: bpy.props.FloatProperty(
        name="Cage Surface Opacity",
        default=0.42,
        min=0.0,
        max=1.0,
        precision=2,
        subtype="FACTOR",
        description="Control the opacity of the cage surface overlay",
        # Opacity is the cage colour's alpha — a draw-time uniform / display-key entry, not
        # baked into the static batches. Dynamic update keeps the slider drag smooth and
        # leaves the static cache (and the cage-coverage overlay) intact instead of
        # rebuilding it every frame.
        update=_overlay_dynamic_update,
    )
    cage_wireframe_opacity: bpy.props.FloatProperty(
        name="Cage Wireframe Opacity",
        default=0.38,
        min=0.0,
        max=1.0,
        precision=2,
        subtype="FACTOR",
        description="Control the opacity of the cage wireframe overlay",
        # Draw-time uniform / display-key entry — dynamic update (see cage_surface_opacity).
        update=_overlay_dynamic_update,
    )


def _paint_brush_redraw_update(_self, context):
    screen = getattr(context, "screen", None)
    for area in getattr(screen, "areas", None) or ():
        if getattr(area, "type", "") == "VIEW_3D":
            area.tag_redraw()


class MasterBakerPaintBrushSettings(bpy.types.PropertyGroup):
    """Brush of the Paint Offset / Paint Skew tools (paint_brush.py)."""

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("ADD", "Add", "Raise the value under the brush. Hold Ctrl to lower it", "ADD", 0),
            ("SUBTRACT", "Subtract", "Lower the value under the brush. Hold Ctrl to raise it", "REMOVE", 1),
            ("SMOOTH", "Smooth", "Even out the painted values. Hold Shift to smooth with any mode", "MOD_SMOOTH", 2),
            ("SET", "Set", "Move the value under the brush toward the target value. Hold Ctrl to erase", "IPO_CONSTANT", 3),
            ("ERASE", "Erase", "Move the value under the brush back to unpainted", "X", 4),
        ),
        default="ADD",
    )
    radius: bpy.props.IntProperty(
        name="Radius",
        description="Brush radius in screen pixels (F)",
        default=60,
        min=1,
        max=2000,
        soft_max=500,
        subtype="PIXEL",
        update=_paint_brush_redraw_update,
    )
    strength: bpy.props.FloatProperty(
        name="Strength",
        description="How strongly each dab changes the value (Shift+F)",
        default=0.5,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )
    use_pressure_radius: bpy.props.BoolProperty(
        name="Pressure Radius", description="Pen pressure scales the radius", default=False
    )
    use_pressure_strength: bpy.props.BoolProperty(
        name="Pressure Strength", description="Pen pressure scales the strength", default=True
    )
    falloff: bpy.props.EnumProperty(
        name="Falloff",
        items=(
            ("SMOOTH", "Smooth", "Soft edge", "SMOOTHCURVE", 0),
            ("SPHERE", "Sphere", "Round, full in the middle", "SPHERECURVE", 1),
            ("ROOT", "Root", "Strong centre, long tail", "ROOTCURVE", 2),
            ("SHARP", "Sharp", "Fast drop from the centre", "SHARPCURVE", 3),
            ("LINEAR", "Linear", "Straight drop to the rim", "LINCURVE", 4),
            ("CONSTANT", "Constant", "Same strength out to the rim", "NOCURVE", 5),
        ),
        default="SMOOTH",
    )
    hardness: bpy.props.FloatProperty(
        name="Hardness",
        description="Keep full strength out to this fraction of the radius",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )
    spacing: bpy.props.IntProperty(
        name="Spacing",
        description="Distance between dabs along a stroke, in percent of the radius",
        default=10,
        min=1,
        max=100,
        subtype="PERCENTAGE",
    )
    offset_target: bpy.props.FloatProperty(
        name="Offset",
        description="Target of Set for Paint Offset, as a change of the cage offset: 0% is unpainted, -100% puts the cage on the surface",
        default=0.0,
        min=-100.0,
        max=900.0,
        soft_max=300.0,
        subtype="PERCENTAGE",
    )
    skew_target: bpy.props.FloatProperty(
        name="Skew",
        description="Target of Set for Paint Skew: 0 leaves the bake ray as it is, 1 fires it straight off the low-poly face",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )
    use_front_faces_only: bpy.props.BoolProperty(
        name="Front Faces Only",
        description="Only paint surface that faces the view",
        default=True,
    )
    use_visible_only: bpy.props.BoolProperty(
        name="Visible Only",
        description="Only paint surface you can see, so parts in front or behind are left alone",
        default=True,
    )
    use_connected_only: bpy.props.BoolProperty(
        name="Connected Only",
        description="Only paint the piece of mesh under the brush",
        default=False,
    )
    offset_raise_color: bpy.props.FloatVectorProperty(
        name="Raised",
        subtype="COLOR",
        size=3,
        default=(0.16, 0.50, 1.00),
        min=0.0,
        max=1.0,
        description="Tint where Paint Offset pushes the cage further out. The default comes from the addon preferences",
        update=_paint_brush_redraw_update,
    )
    offset_lower_color: bpy.props.FloatVectorProperty(
        name="Lowered",
        subtype="COLOR",
        size=3,
        default=(1.00, 0.24, 0.20),
        min=0.0,
        max=1.0,
        description="Tint where Paint Offset pulls the cage in. The default comes from the addon preferences",
        update=_paint_brush_redraw_update,
    )
    # Set once the scene's offset tint colours were seeded from the addon preferences, so a
    # colour the artist picked here is never overwritten by the default again.
    offset_colors_seeded: bpy.props.BoolProperty(default=False, options={"HIDDEN"})
    show_values: bpy.props.BoolProperty(
        name="Show Values",
        description="Tint the surface where values are painted",
        default=True,
        update=_paint_brush_redraw_update,
    )


class MasterBakerUvSnapshot(bpy.types.PropertyGroup):
    schema_version: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    snapshot_uuid: bpy.props.StringProperty(default="", options={"HIDDEN"})
    source_object_uuid: bpy.props.StringProperty(default="", options={"HIDDEN"})
    source_object_name: bpy.props.StringProperty(default="")
    source_object_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    snapshot_name: bpy.props.StringProperty(name="Snapshot Name", default="UV Snapshot")
    captured_at: bpy.props.StringProperty(default="")
    blender_version: bpy.props.StringProperty(default="", options={"HIDDEN"})
    addon_version: bpy.props.StringProperty(default="", options={"HIDDEN"})
    topology_fingerprint: bpy.props.StringProperty(default="", options={"HIDDEN"})
    uv_layer_name: bpy.props.StringProperty(default="")
    face_count: bpy.props.IntProperty(default=0)
    loop_count: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    active_render: bpy.props.BoolProperty(default=False, options={"HIDDEN"})
    source_matrix: bpy.props.FloatVectorProperty(size=16, subtype="MATRIX", options={"HIDDEN"})
    payload_mesh: bpy.props.PointerProperty(type=bpy.types.Mesh, options={"HIDDEN"})


# --- Marmoset curvature calibration (temp tuning knobs) ---------------------
# Live-tunable calibration for the Marmoset-style curvature response so
# the defaults can be dialed in from Blender. Each tuple is
# (settings_property_name, env_var_name, default, min, max). The defaults are the
# current calibrated values baked into the backend; the sliders only diverge from
# them once the artist touches one, so untouched scenes bake exactly as before.
MM_CALIBRATION_KNOBS = (
    ("mm_power_gamma", "FYR_BAKER_MM_POWER_GAMMA", 1.792, 0.5, 3.0),
    ("mm_power_amplitude", "FYR_BAKER_MM_POWER_A", 9.2, 1.0, 30.0),
    ("mm_power_linear_floor", "FYR_BAKER_MM_POWER_LIN", 3.2, 0.0, 10.0),
    ("mm_power_faint", "FYR_BAKER_MM_POWER_FAINT", 1.75, 0.0, 6.0),
    ("mm_convex_boost", "FYR_BAKER_MM_CONVEX_BOOST", 1.7, 0.5, 4.0),
    ("mm_linear_bias", "FYR_BAKER_MM_LINEAR_BIAS", 1.0, 0.9, 1.2),
    ("mm_aa_jitter_scale", "FYR_BAKER_AA_JITTER_SCALE", 2.0, 1.0, 5.0),
)

# Guard so a bulk reset (which assigns every knob in turn) restarts the worker
# once at the end instead of once per assignment.
_MM_CALIBRATION_SUSPEND_UPDATE = False


def _apply_mm_calibration_mode_flags() -> None:
    """Enable the Marmoset curvature response stack (MM_CURVATURE_RESPONSE + MM_LINEAR mode
    flags) in os.environ so every spawned worker inherits it. These are mode selectors,
    not tuning values, and never change at runtime; the seven tuning values now flow
    per-bake through the job payload (see export.prepare_bake_job / protocol.py), so a
    slider change applies on the next bake with NO worker restart. Called once at
    register() and (idempotently) on any slider commit."""
    import os

    os.environ.setdefault("FYR_BAKER_MM_CURVATURE_RESPONSE", "1")
    os.environ.setdefault("FYR_BAKER_MM_LINEAR", "1")


def _mm_calibration_update(self, context):
    """On a calibration-slider commit just ensure the mode flags are present. The value
    itself is carried into the next bake by the job payload, so there is no env sync of
    the individual knobs and NO worker restart -- the resident worker reads the new value
    from the payload on its next RUN."""
    if _MM_CALIBRATION_SUSPEND_UPDATE:
        return
    _apply_mm_calibration_mode_flags()


def reset_mm_calibration(settings) -> None:
    """Restore every calibration knob to its calibrated default. No env sync of values
    and no worker restart -- the defaults ride into the next bake via the job payload."""
    global _MM_CALIBRATION_SUSPEND_UPDATE
    if settings is None:
        return
    _MM_CALIBRATION_SUSPEND_UPDATE = True
    try:
        for prop_name, _env, default, _lo, _hi in MM_CALIBRATION_KNOBS:
            setattr(settings, prop_name, default)
    finally:
        _MM_CALIBRATION_SUSPEND_UPDATE = False
    _apply_mm_calibration_mode_flags()


class MasterBakerSceneSettings(bpy.types.PropertyGroup):
    projects: bpy.props.CollectionProperty(name="Bake Projects", type=MasterBakerBakeProject)
    active_project_index: bpy.props.IntProperty(name="Project Index", default=0, update=_overlay_static_visibility_update)
    ui_state: bpy.props.PointerProperty(name="UI State", type=MasterBakerUiState)
    overlay_settings: bpy.props.PointerProperty(name="Overlay Settings", type=MasterBakerViewportOverlaySettings)
    paint_brush: bpy.props.PointerProperty(name="Paint Brush", type=MasterBakerPaintBrushSettings)
    preview_map_type: bpy.props.EnumProperty(name="Preview Map", items=_available_preview_map_items)
    # The header's picker. Stores nothing: get/set read and drive the live preview, so
    # choosing a map shows it and Off restores the original materials.
    preview_picker: bpy.props.EnumProperty(
        name="Preview Map",
        description="Show a baked map on the low-poly meshes, or Off to restore their materials",
        items=_preview_picker_items,
        get=_preview_picker_get,
        set=_preview_picker_set,
        options={"SKIP_SAVE"},
    )
    preview_session: bpy.props.PointerProperty(name="Preview Session", type=MasterBakerPreviewSessionState)
    image_editor: bpy.props.PointerProperty(name="Image Editor", type=MasterBakerImageEditorState)
    status_message: bpy.props.StringProperty(name="Session Status", default=constants.STATUS_IDLE)
    header_menu_fold: bpy.props.BoolProperty(
        name="Fyr Baker Header Controls",
        description="Show or hide the Fyr Baker controls in the 3D Viewport header",
        default=False,
        options={"SKIP_SAVE"},
    )
    # Vestigial: the preview-picker cache moved to _PREVIEW_MAP_ITEMS_CACHE because
    # writing these from the items callback re-entered enum resolution. Kept declared
    # so older files that stored them still load without a console warning.
    cached_preview_map_types: bpy.props.StringProperty(name="Cached Preview Map Types", default="", options={"HIDDEN", "SKIP_SAVE"})
    cached_outputs_count: bpy.props.IntProperty(name="Cached Outputs Count", default=-1, options={"HIDDEN", "SKIP_SAVE"})
    uv_snapshots: bpy.props.CollectionProperty(name="UV Snapshots", type=MasterBakerUvSnapshot)

    # --- Marmoset curvature calibration (temp tuning knobs) ---
    mm_power_gamma: bpy.props.FloatProperty(
        name="Response Gamma", description="Control the gamma curve applied to the curvature response",
        default=1.792, min=0.5, max=3.0, update=_mm_calibration_update,
    )
    mm_power_amplitude: bpy.props.FloatProperty(
        name="Response Amplitude", description="Control the strength of the cavity and curvature response",
        default=9.2, min=1.0, max=30.0, update=_mm_calibration_update,
    )
    mm_power_linear_floor: bpy.props.FloatProperty(
        name="Linear Floor", description="Set the minimum linear contribution to the response curve",
        default=3.2, min=0.0, max=10.0, update=_mm_calibration_update,
    )
    mm_power_faint: bpy.props.FloatProperty(
        name="Faint Detail", description="Control how strongly faint curvature details appear",
        default=1.75, min=0.0, max=6.0, update=_mm_calibration_update,
    )
    mm_convex_boost: bpy.props.FloatProperty(
        name="Convex Boost", description="Increase the response on convex surfaces",
        default=1.7, min=0.5, max=4.0, update=_mm_calibration_update,
    )
    mm_linear_bias: bpy.props.FloatProperty(
        name="White Bias", description="Shift the response toward brighter values",
        default=1.0, min=0.9, max=1.2, update=_mm_calibration_update,
    )
    mm_aa_jitter_scale: bpy.props.FloatProperty(
        name="AA Jitter Scale", description="Control how far anti-aliasing samples are offset within each pixel",
        default=2.0, min=1.0, max=5.0, update=_mm_calibration_update,
    )


CLASSES = (
    MasterBakerObjectSlot,
    MasterBakerMapNormalSettings,
    MasterBakerMapAOSettings,
    MasterBakerMapEnvLightSettings,
    MasterBakerMapCurvatureSettings,
    MasterBakerMapThicknessSettings,
    MasterBakerMapIDSettings,
    MasterBakerMapPositionSettings,
    MasterBakerMapHeightSettings,
    MasterBakerMapSetting,
    MasterBakerMaterialBindingSuppression,
    # Must register before MasterBakerOutputImageItem, which holds a CollectionProperty of it.
    MasterBakerOutputTileItem,
    MasterBakerOutputImageItem,
    MasterBakerBakeGroupMetadata,
    MasterBakerBakeGroupCollections,
    MasterBakerBakeGroupRoleAssignments,
    MasterBakerBakeGroupProjectionSettings,
    MasterBakerBakeGroupPaintProjectionSettings,
    MasterBakerBakeGroup,
    # Must register before MasterBakerTextureSet, which holds a CollectionProperty of it.
    MasterBakerUdimTile,
    MasterBakerTextureSet,
    # Must register before MasterBakerExportSettings, which holds a CollectionProperty of them.
    MasterBakerExportSetExclusion,
    MasterBakerExportSetOverride,
    # Must register before MasterBakerBakeProject, which points at it.
    MasterBakerExportSettings,
    MasterBakerBakeProject,
    MasterBakerImageEditorState,
    # Must register before MasterBakerUiState, which holds a CollectionProperty of it.
    MasterBakerHierarchyRow,
    MasterBakerUiState,
    MasterBakerPreviewSessionState,
    MasterBakerViewportOverlaySettings,
    MasterBakerPaintBrushSettings,
    MasterBakerUvSnapshot,
    MasterBakerSceneSettings,
)


def apply_default_map_setting_values(project, map_setting, *, enabled: bool | None = None) -> None:
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    default_normal_format = constants.default_normal_format_for_map(map_type)

    map_setting.map_type = map_type
    map_setting.enabled = (map_type in set(constants.DEFAULT_ENABLED_MAPS)) if enabled is None else bool(enabled)
    map_setting.samples = constants.default_samples_for_map(map_type)
    map_setting.output_suffix = ""
    map_setting.normal_space = constants.MAP_NORMAL_SPACE_TANGENT
    map_setting.normal_format = default_normal_format
    map_setting.flip_green = default_normal_format == constants.NORMAL_FORMAT_DIRECTX
    map_setting.material_detail_mode = constants.MATERIAL_DETAIL_AUTO
    map_setting.material_detail_image = None
    map_setting.ao_distance = 0.15
    map_setting.ao_min_distance = 0.0
    map_setting.ao_relative_to_bounding_box = True
    map_setting.ao_mode = constants.MAP_AO_MODE_RAYCAST
    map_setting.ao_two_sided = False
    map_setting.ao_ignore_groups = False
    # New AO and Bent Normal rows see the whole scene, like Marmoset Toolbag's default.
    # The RNA default stays False so a project saved before this keeps its look.
    map_setting.ao_occlude_other_groups = map_type in constants.WORLD_OCCLUSION_DEFAULT_MAP_TYPES
    map_setting.ao_bevel_normal = constants.AO_BEVEL_NORMAL_AUTO
    map_setting.curvature_bevel_mask = True
    map_setting.ao_cavity_weight = constants.default_ao_cavity_weight_for_map(map_type)
    map_setting.ao_output_min = constants.DEFAULT_AO_OUTPUT_MIN
    map_setting.ao_output_max = 1.0
    map_setting.ao_diffusion_quality = constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM
    map_setting.ao_diffusion_clearance_scale = 0.2
    map_setting.ao_diffusion_clearance_exponent = 2.0
    map_setting.curvature_scale = 1.0
    # Neutral output range: the Marmoset-matched curvature response was
    # calibrated against an unstretched output, so the legacy 0.4/0.6 window was a 5x
    # levels stretch that railed the curve. Artists can still dial a stretch.
    map_setting.curvature_tonemapping_min = 0.0
    map_setting.curvature_tonemapping_max = 1.0
    map_setting.curvature_distance = 0.0
    map_setting.curvature_relative_to_bounding_box = False
    map_setting.curvature_secondary_rays = 64
    map_setting.curvature_detect_folds = False
    map_setting.curvature_self_intersection = "GROUP"
    map_setting.curvature_auto_tonemapping = False
    map_setting.curvature_value_min = -1.0
    map_setting.curvature_value_max = 1.0
    map_setting.thickness_distance = 0.0
    map_setting.thickness_scale = 1.0
    map_setting.thickness_gamma = 1.0
    map_setting.thickness_min_distance = -1.0
    map_setting.thickness_ignore_groups = False
    map_setting.thickness_normalization = False
    map_setting.thickness_log_response = False
    map_setting.density_auto_levels = False
    map_setting.density_auto_levels_per_group = True
    map_setting.id_source = constants.MAP_ID_SOURCE_OBJECT
    map_setting.position_normalization = constants.MAP_POSITION_NORMALIZATION_BOUNDING_BOX
    map_setting.relative_to_bounding_box = True
    map_setting.height_inner_distance = 0.0
    map_setting.height_outer_distance = 0.0
    map_setting.height_dither = False
    map_setting.thickness_dither = False
    map_setting.denoising_enabled = constants.default_denoising_for_map(map_type)
    map_setting.soften_override = False
    map_setting.soften = constants.DEFAULT_SOFTEN
    map_setting.material_origin = constants.MATERIAL_ORIGIN_MANUAL
    map_setting.material_binding_key = ""
    map_setting.material_resolve_state = constants.MATERIAL_RESOLVE_RESOLVED
    map_setting.material_data_type = constants.MATERIAL_DATA_COLOR
    map_setting.material_vector_encoding = constants.MATERIAL_VECTOR_ENCODE_UNIT
    map_setting.material_custom_name = ""
    map_setting.material_source_node_ids = ""
    map_setting.material_status_message = ""
    map_setting.material_previous_enabled = True
    _reset_remaining_map_fields_to_rna_defaults(map_setting)


#: User-editable map fields Restore Defaults used to leave untouched (AO Spread stayed at
#: 30 degrees after a reset). Their declared RNA defaults are the source of truth, so
#: they are reset from bl_rna rather than a second hand-maintained list of values.
_MAP_FIELDS_RESET_FROM_RNA = (
    "ao_spread_angle",
    "ao_distribution",
    "ao_ignore_backface",
    "ao_self_occlusion",
    "ao_attenuation",
    "ao_use_ground_plane",
    "ao_ground_plane_offset",
    "curvature_method",
    "curvature_soften",
    "curvature_output_mode",
    "env_light_intensity",
    "env_light_occlusion_strength",
    "env_light_contrast",
    "env_light_up_axis",
    "env_light_sky_color",
    "env_light_ground_color",
    "lighting_quality",
    "lighting_engine",
    "lighting_direct_enabled",
    "lighting_direct_samples",
    "lighting_indirect_enabled",
    "lighting_indirect_paths",
    "lighting_world_enabled",
    "lighting_emission_enabled",
    "lighting_max_bounces",
    "lighting_noise_threshold",
    "lighting_occlude_other_groups",
    "lighting_exposure",
    "position_mode",
    "position_axis",
    "roughness_normal_variance",
    "roughness_normal_variance_strength",
    "normal_relief",
)


def _reset_remaining_map_fields_to_rna_defaults(map_setting) -> None:
    rna = getattr(map_setting, "bl_rna", None)
    rna_properties = getattr(rna, "properties", None)
    if rna_properties is None:
        return
    for name in _MAP_FIELDS_RESET_FROM_RNA:
        try:
            prop = rna_properties.get(name) if hasattr(rna_properties, "get") else rna_properties[name]
        except Exception:
            prop = None
        if prop is None or not hasattr(map_setting, name):
            continue
        try:
            if getattr(prop, "is_array", False) or int(getattr(prop, "array_length", 0) or 0) > 0:
                value = tuple(prop.default_array)
            else:
                value = prop.default
            if getattr(map_setting, name) != value:
                setattr(map_setting, name, value)
        except Exception:
            continue


def _migrate_legacy_cavity_output_range(project) -> int:
    """Neutralize Black/White Point on legacy CAVITY rows. Returns rows changed.

    The backend's output-range pass has NEVER applied to the Cavity kind (its gate was
    `is_ao || is_signed_curvature`), so any stored cavity curvature_tonemapping_min/max
    is inert legacy noise that no artist could have set deliberately -- every Cavity row
    simply inherited the old shared 0.4/0.6 default. Resetting it cannot destroy intent;
    leaving it would apply a surprise 5x levels stretch the moment the backend enables
    the pass for Cavity.

    Curvature / Concave / Convex are deliberately NOT touched: the pass was live for
    those kinds, so their stored values may well be intentional."""
    neutralized = 0
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False):
            continue
        if str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_CAVITY:
            continue
        try:
            black = float(getattr(item, "curvature_tonemapping_min", 0.0))
            white = float(getattr(item, "curvature_tonemapping_max", 1.0))
        except (TypeError, ValueError):
            black, white = 0.0, 1.0
        if black == 0.0 and white == 1.0:
            continue
        try:
            item.curvature_tonemapping_min = 0.0
            item.curvature_tonemapping_max = 1.0
        except (AttributeError, TypeError, ValueError):
            continue
        neutralized += 1
    return neutralized


def _migrate_legacy_normal_format_defaults(project) -> int:
    """Stamp the default normal format onto legacy Normal rows. Returns rows changed.

    `normal_format` is a static EnumProperty, so a project saved before the DirectX default
    existed is indistinguishable from one where the artist picked OpenGL: both store OPENGL.
    The old code resolved that ambiguity on every read (and on every ensure_default_maps
    call), which meant an explicit OpenGL choice was silently replaced by DirectX forever.
    Doing it once, gated on schema_version, keeps the historical result for old projects and
    lets the stored value be authoritative from then on."""
    upgraded = 0
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False):
            continue
        if not should_upgrade_legacy_normal_format(item):
            continue
        map_type = str(getattr(item, "map_type", "") or "").strip().upper()
        try:
            item.normal_format = constants.default_normal_format_for_map(map_type)
            item.flip_green = item.normal_format == constants.NORMAL_FORMAT_DIRECTX
        except (AttributeError, TypeError, ValueError):
            continue
        upgraded += 1
    return upgraded


def _migrate_legacy_tangent_basis(project) -> bool:
    """Reset a retired ``BLENDER`` tangent basis to MikkTSpace. Returns True when changed.

    Reading an enum whose stored value no longer exists yields "" (with an RNA
    warning), so anything that is not MikkTSpace is the legacy value.
    """
    try:
        current = str(getattr(project, "tangent_basis", "") or "")
    except Exception:
        current = ""
    if current == constants.TANGENT_MIKKTSPACE:
        return False
    try:
        project.tangent_basis = constants.TANGENT_MIKKTSPACE
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _migrate_legacy_curvature_probe_fields(project) -> int:
    """Carry the pre-MBBJOB33 curvature rows into the Painter-style probe fields.

    Before MBBJOB33 ``curvature_self_intersection`` was the fold-detection BOOL. It is
    now the probe-scope ENUM and the bool lives in ``curvature_detect_folds``. Every
    saved row stores the old bool as an integer under the enum's name; value 0 already
    reads as GROUP (see _CURVATURE_SELF_INTERSECTION_ITEMS), value 1 would read as
    SAME_MESH. A pre-MBBJOB33 row is recognised by the absence of the stored
    ``curvature_secondary_rays`` key, which every row written since carries. Returns
    rows changed."""
    migrated = 0
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False):
            continue
        targets = [item]
        nested = getattr(item, "curvature_settings", None)
        if nested is not None:
            targets.append(nested)
        changed = False
        for target in targets:
            try:
                keys = set(target.keys())
            except (AttributeError, TypeError):
                continue
            if "curvature_secondary_rays" in keys:
                continue
            raw = target.get("curvature_self_intersection", 0)
            detect_folds = bool(raw) if isinstance(raw, int) else False
            try:
                target.curvature_detect_folds = detect_folds
                target.curvature_self_intersection = "GROUP"
                target.curvature_secondary_rays = 64
                target.curvature_auto_tonemapping = False
                target.curvature_value_min = -1.0
                target.curvature_value_max = 1.0
            except (AttributeError, TypeError, ValueError):
                continue
            changed = True
        if changed:
            migrated += 1
    return migrated


def _migrate_phantom_default_texture_set_links(project) -> int:
    """Clear the legacy ``"Default"`` texture-set link off groups. Returns groups changed.

    That string was the old ``texture_set_name`` property default, so groups carried it
    without the artist ever joining a set -- and with no backing ``texture_sets`` entry it
    only served to name outputs ``Default_*.tga`` instead of after the bake group. A project
    where the artist really did create a set called "Default" has a backing entry, so that
    link is left alone.
    """
    legacy = constants.DEFAULT_TEXTURE_SET_NAME
    if find_texture_set(project, legacy) is not None:
        return 0
    cleared = 0
    for group in getattr(project, "groups", []) or ():
        if (getattr(group, "texture_set_name", "") or "").strip() != legacy:
            continue
        try:
            group.texture_set_name = ""
        except (AttributeError, TypeError, ValueError):
            continue
        cleared += 1
    return cleared


def _migrate_legacy_cage_mode_default(project) -> int:
    """Pin Automatic on groups that never stored a cage mode. Returns groups pinned.

    Blender saves only properties that were set. A group whose nested projection state
    stored a mode keeps it (_adopt_stored_legacy_cage_mode copies it flat); one that
    stored nothing at all rode the Automatic default. The default is now Distance
    (Painter and Marmoset), which without this step would silently re-cage those groups
    on a 2 cm Distance offset the next time the file opened."""
    pinned = 0
    for group in getattr(project, "groups", []):
        nested = getattr(group, "projection_settings", None)
        try:
            if group.is_property_set("cage_mode"):
                continue
            if nested is not None and nested.is_property_set("cage_mode"):
                _adopt_stored_legacy_cage_mode(group, nested)
                continue
            # Raw writes: no update callback, so no cage-scope propagation on load.
            group["cage_mode"] = _CAGE_MODE_AUTOMATIC_INDEX
            if nested is not None:
                nested["cage_mode"] = _CAGE_MODE_AUTOMATIC_INDEX
        except (AttributeError, KeyError, ReferenceError, TypeError):
            continue
        pinned += 1
    return pinned


_CAGE_MODE_AUTOMATIC_INDEX = next(
    index for index, item in enumerate(constants.CAGE_MODE_ITEMS) if item[0] == constants.CAGE_MODE_AUTOMATIC
)


def _migrate_legacy_texture_set_mode_default(project) -> bool:
    """Keep One Combined Set for scenes built before Set Per Material became the default.

    The mode lives on the scene's ui_state and Blender stores it only once set. A scene
    whose project already has bake groups and never chose a mode built them combined; a
    later Auto-Build must not silently regroup it by material. Fresh projects are stamped
    before they have groups, so they get the new default."""
    if not list(getattr(project, "groups", []) or []):
        return False
    scene = getattr(project, "id_data", None)
    ui_state = getattr(getattr(scene, "fyr_baker_settings", None), "ui_state", None)
    if ui_state is None:
        return False
    try:
        if ui_state.is_property_set("auto_texture_set_mode"):
            return False
        ui_state["auto_texture_set_mode"] = _TEXTURE_SET_MODE_COMBINED_INDEX
    except (AttributeError, KeyError, ReferenceError, TypeError):
        return False
    return True


_TEXTURE_SET_MODE_COMBINED_INDEX = next(
    index for index, item in enumerate(constants.AUTO_TEXTURE_SET_MODE_ITEMS)
    if item[0] == constants.AUTO_TEXTURE_SET_COMBINED
)


def migrate_project_schema(project) -> bool:
    """Run one-time stored-state upgrades on a project saved against an older schema.

    Gated on the project's schema_version stamp so each step runs exactly once, no
    matter how often ensure_default_maps is called. Add new steps as
    `if stored_version < N:` blocks and bump PROJECT_SCHEMA_VERSION."""
    if project is None:
        return False
    try:
        stored_version = int(getattr(project, "schema_version", 0) or 0)
    except (TypeError, ValueError):
        stored_version = 0
    if stored_version >= constants.PROJECT_SCHEMA_VERSION:
        return False

    if stored_version < 1:
        neutralized = _migrate_legacy_cavity_output_range(project)
        if neutralized:
            print(
                f"[MasterBaker] project '{getattr(project, 'name', '')}': reset Black/White Point to "
                f"0.0/1.0 on {neutralized} legacy Cavity map row(s) - the output-range pass never "
                f"applied to Cavity, so the stored values were inert legacy defaults."
            )

    if stored_version < 3:
        upgraded = _migrate_legacy_normal_format_defaults(project)
        if upgraded:
            print(
                f"[MasterBaker] project '{getattr(project, 'name', '')}': upgraded {upgraded} legacy "
                f"Normal map row(s) to the default normal format. From now on the "
                f"stored Normal Format is used verbatim, so an explicit OpenGL choice sticks."
            )

    if stored_version < 4:
        cleared = _migrate_phantom_default_texture_set_links(project)
        if cleared:
            print(
                f"[MasterBaker] project '{getattr(project, 'name', '')}': cleared the legacy "
                f"\"{constants.DEFAULT_TEXTURE_SET_NAME}\" texture-set link on {cleared} bake "
                f"group(s). Their outputs are now named after the bake group."
            )

    if stored_version < 5:
        if _migrate_legacy_tangent_basis(project):
            print(
                f"[MasterBaker] project '{getattr(project, 'name', '')}': tangent basis reset to "
                f"MikkTSpace. The retired \"Blender\" option baked a flat per-face basis that "
                f"never matched Blender's own (MikkTSpace) tangents; the Normal map is marked "
                f"for a rebake."
            )

    if stored_version < 6:
        migrated = _migrate_legacy_curvature_probe_fields(project)
        if migrated:
            print(
                f"[MasterBaker] project '{getattr(project, 'name', '')}': moved the legacy curvature "
                f"Self Intersection checkbox to Detect Folds on {migrated} map row(s) and reset the "
                f"probe scope to Same Group (the pre-MBBJOB33 behaviour)."
            )

    if stored_version < 7:
        pinned = _migrate_legacy_cage_mode_default(project)
        if pinned:
            print(
                f"[MasterBaker] project '{getattr(project, 'name', '')}': kept Automatic cages on "
                f"{pinned} bake group(s) saved before Distance became the default."
            )

    if stored_version < 8:
        if _migrate_legacy_texture_set_mode_default(project):
            print(
                f"[MasterBaker] project '{getattr(project, 'name', '')}': kept One Combined Set "
                f"for Auto-Build in a scene built before Set Per Material became the default."
            )

    try:
        project.schema_version = constants.PROJECT_SCHEMA_VERSION
    except (AttributeError, TypeError, ValueError):
        pass
    return True


def _migrate_legacy_scene_lighting_rows(project: MasterBakerBakeProject) -> None:
    """Retype legacy LIGHTING / LIT_COLOR rows to the consolidated SCENE_LIGHTING type,
    preserving all row settings and the row uuid (so output tracking and cache keys
    survive). The previous type becomes the row's lighting_output selector."""
    for item in project.maps:
        if getattr(item, "is_add_phantom", False):
            continue
        raw = str(getattr(item, "map_type", "") or "").strip().upper()
        if raw not in constants.LEGACY_SCENE_LIGHTING_MAP_TYPES:
            continue
        item.lighting_output = raw  # LIGHTING_OUTPUT_* identifiers equal the legacy types
        item.map_type = constants.MAP_SCENE_LIGHTING


def ensure_default_maps(project: MasterBakerBakeProject) -> None:
    remove_phantom_map_items(project)
    migrate_project_schema(project)
    _migrate_legacy_scene_lighting_rows(project)
    # MATERIAL-workflow (Bake Selected Materials) stacks are authored, not catalogued: the
    # dialog / Rescan Materials put exactly the requested channels in, and only
    # constants.MATERIAL_WORKFLOW_MAP_TYPES are meaningful for a self-bake project. Seeding
    # the geometry catalogue here is what silently re-added an enabled NORMAL row (plus AO /
    # Curvature / ID) on every bake -- prepare_bake_job calls this -- so a 2-channel project
    # baked 3+ maps. Migrations above still run for these projects.
    if str(getattr(project, "workflow", "") or "").strip().upper() == constants.WORKFLOW_MATERIAL:
        return
    existing = {getattr(item, "map_type", "") for item in project.maps if not getattr(item, "is_add_phantom", False)}
    for map_type, _label, _description in constants.MAP_TYPE_ITEMS:
        if map_type in constants.LEGACY_SCENE_LIGHTING_MAP_TYPES:
            continue
        if map_type in existing:
            # Existing rows are left alone: the normal-format upgrade is a one-time
            # schema migration above, never a per-call re-derivation (QA bug #4).
            continue
        item = _add_map_item(project.maps)
        item.map_type = map_type
        ensure_map_setting_uuid(item)
        apply_default_map_setting_values(project, item)


def find_map_setting(project: MasterBakerBakeProject, map_type: str):
    normalized_map_type = str(map_type or "").strip().upper()
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False):
            continue
        if str(getattr(item, "map_type", "")).strip().upper() == normalized_map_type:
            return item
    return None


def ensure_map_setting_uuid(map_setting) -> str:
    normalized_uuid = str(getattr(map_setting, "uuid", "") or "").strip()
    if normalized_uuid:
        return normalized_uuid

    ensure_uuid_fn = getattr(map_setting, "ensure_uuid", None)
    if callable(ensure_uuid_fn):
        ensure_uuid_fn()
        normalized_uuid = str(getattr(map_setting, "uuid", "") or "").strip()
        if normalized_uuid:
            return normalized_uuid

    generated_uuid = str(_uuid.uuid4())
    try:
        setattr(map_setting, "uuid", generated_uuid)
    except Exception:
        return ""
    return str(getattr(map_setting, "uuid", "") or "").strip() or generated_uuid


def find_map_setting_by_uuid(project: MasterBakerBakeProject, map_uuid: str):
    normalized_uuid = str(map_uuid or "").strip()
    if not normalized_uuid:
        return None
    from . import runtime_output_images as _scope

    if _scope._NORMALIZED_PATH_CACHE is not None:
        # Inside a progress/refresh pass the stack is fixed, and this lookup runs once per
        # tracked output: index the rows once (first row wins, as the scan below does).
        index = _scope.cached_normalized_path(
            "map_uuid_index",
            str(id(project)),
            lambda: (_build_map_uuid_index(project), project),
        )[0]
        return index.get(normalized_uuid)
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False):
            continue
        if ensure_map_setting_uuid(item) == normalized_uuid:
            return item
    return None


def _build_map_uuid_index(project) -> dict:
    index: dict = {}
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False):
            continue
        index.setdefault(ensure_map_setting_uuid(item), item)
    return index


def resolve_map_setting(
    project: MasterBakerBakeProject,
    *,
    map_uuid: str = "",
    map_type: str = "",
    output_suffix: str = "",
    map_stack_index: int = -1,
):
    normalized_uuid = str(map_uuid or "").strip()
    if normalized_uuid:
        return find_map_setting_by_uuid(project, normalized_uuid)

    normalized_map_type = str(map_type or "").strip().upper()
    normalized_suffix = str(output_suffix or "").strip()
    if normalized_suffix:
        for item in getattr(project, "maps", []):
            if getattr(item, "is_add_phantom", False):
                continue
            item_map_type = str(getattr(item, "map_type", "") or "").strip().upper()
            if normalized_map_type and item_map_type != normalized_map_type:
                continue
            if (effective_map_output_suffix(project, item) or "") == normalized_suffix:
                return item

    if map_stack_index >= 0:
        maps = getattr(project, "maps", [])
        try:
            item = maps[map_stack_index]
        except Exception:
            item = None
        if item is not None and not getattr(item, "is_add_phantom", False):
            item_map_type = str(getattr(item, "map_type", "") or "").strip().upper()
            if not normalized_map_type or item_map_type == normalized_map_type:
                return item

    if normalized_map_type:
        return find_map_setting(project, normalized_map_type)
    return None


def ensure_map_setting(project: MasterBakerBakeProject, map_type: str):
    existing = find_map_setting(project, map_type)
    if existing is not None:
        return existing

    return add_map_setting(project, map_type)


def remove_phantom_map_items(project: MasterBakerBakeProject) -> None:
    maps = getattr(project, "maps", None)
    if maps is None:
        return
    removed = False
    for i in range(len(maps) - 1, -1, -1):
        if getattr(maps[i], "is_add_phantom", False):
            if hasattr(maps, "remove"):
                maps.remove(i)
            else:
                del maps[i]
            removed = True
    if removed and hasattr(project, "active_map_index"):
        project.active_map_index = resolve_active_index(getattr(project, "active_map_index", 0), len(maps)) or 0


def add_map_setting(project: MasterBakerBakeProject, map_type: str):
    normalized_type = str(map_type or "").strip().upper()
    remove_phantom_map_items(project)
    # Count same-type maps BEFORE adding the new one.
    existing_count = sum(
        1 for ms in project.maps
        if not getattr(ms, "is_add_phantom", False)
        and str(getattr(ms, "map_type", "") or "").strip().upper() == normalized_type
    )
    item = _add_map_item(project.maps)
    item.map_type = normalized_type
    ensure_map_setting_uuid(item)
    apply_default_map_setting_values(project, item, enabled=False)
    # MATERIAL rows are named by their channel / custom output through
    # effective_map_output_suffix (Albedo, Roughness, ...). A literal stamp here
    # would be computed before the operator assigns material_channel, freezing the
    # channel-blind "Material_2" onto a row that should read "Albedo". ATTRIBUTE rows
    # are named by their attribute the same way (naming._attribute_row_output_suffix).
    if existing_count >= 1 and normalized_type not in {constants.MAP_MATERIAL, constants.MAP_ATTRIBUTE}:
        # Pre-assign a suffix in the form "<MapFileLabel>_<n>" (e.g. "AO_2", "Thickness_3")
        # so the new map is immediately distinguishable regardless of its mode setting.
        # Underscore (not a space) keeps the resulting texture filename shell/engine-safe.
        type_label = constants.MAP_FILE_LABELS.get(normalized_type, normalized_type.title())
        prefix = f"{type_label}_"
        # Scan EVERY row, not just same-type ones: a row that was stamped "Normal_2"
        # and later retyped still owns that suffix, and filtering by type made it
        # invisible here — the next Normal add stamped "Normal_2" a second time and
        # two rows ended up writing the same file name.
        used_numbers = {
            int(str(getattr(ms, "output_suffix", "") or "").strip()[len(prefix):])
            for ms in project.maps
            if not getattr(ms, "is_add_phantom", False)
            and str(getattr(ms, "output_suffix", "") or "").strip().startswith(prefix)
            and str(getattr(ms, "output_suffix", "") or "").strip()[len(prefix):].isdigit()
        }
        n = 2
        while n in used_numbers:
            n += 1
        item.output_suffix = f"{type_label}_{n}"
    return item



def reset_map_setting(project: MasterBakerBakeProject, map_setting) -> None:
    enabled = getattr(map_setting, "enabled", None)
    apply_default_map_setting_values(project, map_setting, enabled=enabled if enabled is not None else None)


def reset_map_setting_value(project: MasterBakerBakeProject, map_setting, property_name: str) -> bool:
    normalized_property_name = str(property_name or "").strip()
    if not normalized_property_name:
        return False
    defaults = types.SimpleNamespace(map_type=str(getattr(map_setting, "map_type", "") or "").strip().upper())
    apply_default_map_setting_values(project, defaults)
    if not hasattr(defaults, normalized_property_name):
        return False
    setattr(map_setting, normalized_property_name, getattr(defaults, normalized_property_name))
    return True


def remove_active_map(project: MasterBakerBakeProject) -> bool:
    remove_phantom_map_items(project)
    index = resolve_active_index(getattr(project, "active_map_index", 0), len(getattr(project, "maps", [])))
    if index is None:
        return False
    item = project.maps[index]
    binding_key = str(getattr(item, "material_binding_key", "") or "").strip()
    origin = str(getattr(item, "material_origin", "") or "")
    if hasattr(project.maps, "add") and hasattr(project.maps, "remove"):
        try:
            project.maps.remove(index)
        except (TypeError, ValueError):
            del project.maps[index]
    else:
        del project.maps[index]
    project.active_map_index = resolve_active_index(index, len(project.maps)) or 0
    if binding_key:
        try:
            from . import material_capture_sync
            material_capture_sync.on_map_removed(project, binding_key, origin)
        except Exception:
            pass
    return True


def peek_active_map(project: MasterBakerBakeProject):
    index = resolve_active_index(getattr(project, "active_map_index", 0), len(getattr(project, "maps", [])))
    if index is None:
        return None
    item = project.maps[index]
    if getattr(item, "is_add_phantom", False):
        return None
    return item


def peek_previewed_map(project: MasterBakerBakeProject, settings):
    """Get the map currently being previewed on low meshes, or None if no preview is active."""
    if project is None or settings is None:
        return None
    session_state = preview_session_state(settings)
    if session_state is None:
        return None
    if not bool(getattr(session_state, "preview_on_low_active", False)):
        return None
    if str(getattr(session_state, "preview_on_low_project_name", "") or "") != str(getattr(project, "name", "") or ""):
        return None
    
    # Try to find by UUID first (most precise)
    map_uuid = str(getattr(session_state, "preview_on_low_map_uuid", "") or "").strip()
    if map_uuid:
        for item in getattr(project, "maps", []):
            if getattr(item, "is_add_phantom", False):
                continue
            if ensure_map_setting_uuid(item) == map_uuid:
                return item
    
    # Fallback to map type
    map_type = str(getattr(session_state, "preview_on_low_map_type", "") or "").strip().upper()
    if map_type:
        for item in getattr(project, "maps", []):
            if getattr(item, "is_add_phantom", False):
                continue
            if str(getattr(item, "map_type", "") or "").strip().upper() == map_type:
                return item
    
    return None


map_output_suffix = naming.map_output_suffix


_MAP_DUPLICATE_SIGNATURE_IGNORED = {
    "rna_type",
    "uuid",
    "enabled",
    "is_add_phantom",
    "output_suffix",
    # Legacy nested settings mirror the exported flat properties and have
    # distinct RNA identities per row, so including them would hide matches.
    "normal_settings",
    "ao_settings",
    "env_light_settings",
    "curvature_settings",
    "thickness_settings",
    "id_settings",
    "position_settings",
    "height_settings",
}


_MAP_COPY_IGNORED = _MAP_DUPLICATE_SIGNATURE_IGNORED - {"enabled"}


def copy_map_setting_values(source, target) -> None:
    """Copy bake-relevant fields from one map row to another."""
    rna = getattr(source, "bl_rna", None)
    if rna is not None:
        for prop in rna.properties:
            identifier = str(getattr(prop, "identifier", "") or "")
            if not identifier or identifier in _MAP_COPY_IGNORED:
                continue
            if bool(getattr(prop, "is_readonly", False)):
                continue
            if not hasattr(target, identifier):
                continue
            try:
                setattr(target, identifier, getattr(source, identifier))
            except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                continue
        return

    for identifier, value in vars(source).items():
        if identifier.startswith("_") or identifier in _MAP_COPY_IGNORED:
            continue
        if hasattr(target, identifier):
            setattr(target, identifier, value)


def _assign_duplicate_output_suffix(project, source, target) -> None:
    """Give ``target`` an explicit suffix that won't collide on disk."""
    from . import export as export_module

    effective_type = export_module.effective_map_type_for_setting(source)
    # The COPY is the row that must take a new label -- the source keeps whatever file
    # name it already writes (see naming.effective_map_output_suffix). Prefer the copy's
    # own mode label ("Raycast", "Signed", "Tangent", ...) so the new file is
    # self-describing, and only fall back to the plain type label when there is none.
    base = str(getattr(source, "output_suffix", "") or "").strip()
    if not base:
        base = str(naming._auto_map_output_suffix_base(target) or "").strip()
    if not base:
        map_type = str(getattr(source, "map_type", "") or "").strip().upper()
        base = constants.MAP_FILE_LABELS.get(map_type, naming.map_label(map_type))

    used_suffixes = set()
    target_ptr = getattr(target, "as_pointer", lambda: None)()
    target_uuid = str(getattr(target, "uuid", "") or "").strip()
    for candidate in getattr(project, "maps", []):
        if getattr(candidate, "is_add_phantom", False):
            continue
        is_target = candidate is target
        if not is_target and target_ptr is not None:
            cand_ptr = getattr(candidate, "as_pointer", lambda: None)()
            is_target = cand_ptr is not None and cand_ptr == target_ptr
        if not is_target and target_uuid:
            is_target = str(getattr(candidate, "uuid", "") or "").strip() == target_uuid
        if is_target:
            continue
        if export_module.effective_map_type_for_setting(candidate) != effective_type:
            continue
        # A row whose effective suffix is None writes the PLAIN file label, so that label
        # is taken even though the suffix is empty. Recording "" here instead let the copy
        # claim the base label and push the original off its own file name.
        resolved = str(effective_map_output_suffix(project, candidate) or "").strip()
        if not resolved:
            resolved = naming._base_output_file_label(
                str(getattr(candidate, "map_type", "") or ""), candidate
            )
        used_suffixes.add(resolved)

    candidate = base
    counter = 2
    while candidate in used_suffixes:
        candidate = f"{base}_{counter}"
        counter += 1
    target.output_suffix = candidate


def duplicate_map_setting(project: MasterBakerBakeProject, map_setting):
    """Insert a copy of ``map_setting`` directly below it in the map stack."""
    if project is None or map_setting is None:
        return None
    remove_phantom_map_items(project)

    source_index = None
    source_uuid = ensure_map_setting_uuid(map_setting)
    for index, candidate in enumerate(getattr(project, "maps", [])):
        if getattr(candidate, "is_add_phantom", False):
            continue
        if candidate is map_setting:
            source_index = index
            break
        if ensure_map_setting_uuid(candidate) == source_uuid:
            source_index = index
            break
    if source_index is None:
        return None

    maps = project.maps
    copy = _add_map_item(maps)
    insert_at = source_index + 1
    new_index = len(maps) - 1

    # Blender 5.x ignores CollectionProperty.move on a freshly added row until it
    # carries at least one user-facing field. Seed output_suffix (reassigned below)
    # and uuid so we can re-resolve the RNA item after the move.
    copy.output_suffix = str(getattr(map_setting, "output_suffix", "") or "") or " "
    copy.uuid = ""
    copy_uuid = ensure_map_setting_uuid(copy)

    if new_index != insert_at and hasattr(maps, "move"):
        try:
            maps.move(new_index, insert_at)
        except (TypeError, ValueError):
            pass

    copy = None
    for index, candidate in enumerate(maps):
        if ensure_map_setting_uuid(candidate) == copy_uuid:
            copy = candidate
            insert_at = index
            break
    if copy is None:
        return None

    copy_map_setting_values(map_setting, copy)
    copy.uuid = copy_uuid
    _assign_duplicate_output_suffix(project, map_setting, copy)

    project.active_map_index = insert_at
    return copy


def _map_duplicate_signature_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "name_full"):
        return (
            str(getattr(value, "name_full", "") or ""),
            str(getattr(value, "filepath", "") or ""),
        )
    try:
        return tuple(_map_duplicate_signature_value(item) for item in value)
    except TypeError:
        return str(value)


def map_bake_settings_signature(map_setting) -> tuple:
    """Return a conservative fingerprint of settings that affect baked pixels.

    Output identity and enabled state are intentionally excluded: two rows that
    write different filenames can still request the exact same expensive bake.
    """
    property_names: list[str] = []
    rna = getattr(map_setting, "bl_rna", None)
    if rna is not None:
        property_names = [
            str(getattr(prop, "identifier", "") or "")
            for prop in getattr(rna, "properties", [])
        ]
    if not property_names:
        property_names = list(vars(map_setting))

    signature = []
    for property_name in sorted(set(property_names)):
        if not property_name or property_name in _MAP_DUPLICATE_SIGNATURE_IGNORED:
            continue
        if not hasattr(map_setting, property_name):
            continue
        try:
            value = getattr(map_setting, property_name)
        except (AttributeError, ReferenceError, RuntimeError):
            continue
        signature.append((property_name, _map_duplicate_signature_value(value)))
    return tuple(signature)


def exact_duplicate_map_settings(project, map_setting) -> list:
    """Return other rows whose pixel-affecting settings are identical."""
    if project is None or map_setting is None:
        return []
    target_uuid = str(getattr(map_setting, "uuid", "") or "").strip()
    target_pointer = getattr(map_setting, "as_pointer", lambda: None)()
    # map_type is part of the signature, so only same-type rows can match. Comparing it
    # first skips the full RNA fingerprint of every other row: the map stack calls this
    # once per drawn row, which made each sidebar redraw O(rows^2) fingerprints (fyrtest51,
    # 21 rows: 99,015 fingerprints, 26.7 s of main-thread time across one bake's redraws).
    target_map_type = getattr(map_setting, "map_type", None)
    target_signature = None
    duplicates = []
    for candidate in getattr(project, "maps", []):
        if bool(getattr(candidate, "is_add_phantom", False)):
            continue
        if getattr(candidate, "map_type", None) != target_map_type:
            continue
        is_self = candidate is map_setting
        if not is_self and target_pointer is not None:
            candidate_pointer = getattr(candidate, "as_pointer", lambda: None)()
            is_self = candidate_pointer is not None and candidate_pointer == target_pointer
        if not is_self and target_uuid:
            is_self = str(getattr(candidate, "uuid", "") or "").strip() == target_uuid
        if is_self:
            continue
        if target_signature is None:
            target_signature = map_bake_settings_signature(map_setting)
        if map_bake_settings_signature(candidate) == target_signature:
            duplicates.append(candidate)
    return duplicates


# The suffix-resolution rules moved to naming.py so the bpy-free preflight validator
# resolves output file names through exactly the same code the exporter uses. These
# names stay here because most of the addon reaches them through ``properties``.
_iter_same_type_maps = naming._iter_same_type_maps
_auto_map_output_suffix_base = naming._auto_map_output_suffix_base
_next_available_suffix = naming._next_available_suffix
map_mode_label = naming.map_mode_label
effective_map_output_suffix = naming.effective_map_output_suffix
effective_map_type_for_setting = naming.effective_map_type_for_setting


def map_output_label(map_setting) -> str:
    suffix = map_output_suffix(map_setting)
    if suffix:
        return suffix
    return constants.MAP_LABELS.get(getattr(map_setting, "map_type", ""), "")


def map_flip_green(map_setting) -> bool:
    normal_format = str(getattr(map_setting, "normal_format", "") or "").strip().upper()
    if normal_format == constants.NORMAL_FORMAT_DIRECTX:
        return True
    if normal_format == constants.NORMAL_FORMAT_OPENGL:
        return False
    return bool(getattr(map_setting, "flip_green", False))


def should_upgrade_legacy_normal_format(map_setting) -> bool:
    """Whether this row still holds the pre-DirectX OPENGL enum default.

    ONE-TIME migration predicate only (see _migrate_legacy_normal_format_defaults).
    Never call it from a read path: the stored normal_format is authoritative."""
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    normal_space = str(getattr(map_setting, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT) or "").strip().upper()
    normal_format = str(getattr(map_setting, "normal_format", "") or "").strip().upper()
    if map_type != constants.MAP_NORMAL:
        return False
    if normal_space != constants.MAP_NORMAL_SPACE_TANGENT:
        return False
    if normal_format != constants.NORMAL_FORMAT_OPENGL:
        return False
    return not bool(getattr(map_setting, "flip_green", False))


def effective_normal_format(map_setting) -> str:
    """The row's stored normal format, verbatim whenever it is set.

    The map-type default only fills in for a row that carries no value at all (a plain
    dict/stub, never a registered PropertyGroup). Anything smarter here would override
    an explicit user choice — see _migrate_legacy_normal_format_defaults."""
    normal_format = str(getattr(map_setting, "normal_format", "") or "").strip().upper()
    if normal_format:
        return normal_format
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    return constants.default_normal_format_for_map(map_type)


def map_position_normalization(map_setting) -> str:
    normalization = str(getattr(map_setting, "position_normalization", "") or "").strip().upper()
    if normalization in {
        constants.MAP_POSITION_NORMALIZATION_BOUNDING_BOX,
        constants.MAP_POSITION_NORMALIZATION_BOUNDING_SPHERE,
        constants.MAP_POSITION_NORMALIZATION_OBJECT_ORIGIN,
    }:
        return normalization
    if bool(getattr(map_setting, "relative_to_bounding_box", True)):
        return constants.MAP_POSITION_NORMALIZATION_BOUNDING_BOX
    return constants.MAP_POSITION_NORMALIZATION_OBJECT_ORIGIN


def resolve_map_soften(project, map_setting) -> float:
    """Effective Soften for one map row.

    The project owns one Soften value that every map inherits; a row opts out with
    Override Soften and supplies its own (the Marmoset model). This is the ONLY place
    the two are combined -- export, the rebuild fingerprint, and the UI all read it, so
    a row can never bake at a value the panel does not show.
    """
    if bool(getattr(map_setting, "soften_override", False)):
        value = getattr(map_setting, "soften", constants.DEFAULT_SOFTEN)
    elif project is not None:
        value = getattr(project, "soften", constants.DEFAULT_SOFTEN)
    else:
        value = getattr(map_setting, "soften", constants.DEFAULT_SOFTEN)
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = constants.DEFAULT_SOFTEN
    return min(max(value, 0.0), constants.SOFTEN_MAX)


def summarize_map_settings(map_setting) -> dict[str, object]:
    raw_map_type = str(getattr(map_setting, "map_type", ""))
    if raw_map_type.strip().upper() == constants.MAP_CURVATURE:
        output_mode = str(getattr(map_setting, "curvature_output_mode", "SIGNED") or "SIGNED").strip().upper()
        if output_mode == "PRINCIPAL":
            raw_map_type = constants.MAP_PRINCIPAL_CURVATURE
        elif output_mode == "DIRECTION":
            raw_map_type = constants.MAP_CURVATURE_DIRECTION
    return {
        "map_type": raw_map_type,
        "enabled": bool(getattr(map_setting, "enabled", True)),
        "samples": int(getattr(map_setting, "samples", 1)),
        "output_suffix": map_output_suffix(map_setting) or "",
        "normal_space": str(getattr(map_setting, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT)),
        "normal_format": str(getattr(map_setting, "normal_format", constants.NORMAL_FORMAT_OPENGL)),
        "normal_relief": float(getattr(map_setting, "normal_relief", 0.5)),
        "flip_green": map_flip_green(map_setting),
        "ao_mode": str(getattr(map_setting, "ao_mode", constants.MAP_AO_MODE_RAYCAST)),
        "ao_distance": float(getattr(map_setting, "ao_distance", 0.0)),
        "ao_min_distance": float(getattr(map_setting, "ao_min_distance", 0.0)),
        "ao_two_sided": bool(getattr(map_setting, "ao_two_sided", False)),
        "ao_ignore_groups": bool(getattr(map_setting, "ao_ignore_groups", False)),
        "ao_occlude_other_groups": bool(getattr(map_setting, "ao_occlude_other_groups", False)),
        "ao_bevel_normal": str(getattr(map_setting, "ao_bevel_normal", constants.AO_BEVEL_NORMAL_AUTO)),
        "curvature_bevel_mask": bool(getattr(map_setting, "curvature_bevel_mask", True)),
        "ao_cavity_weight": float(getattr(map_setting, "ao_cavity_weight", constants.default_ao_cavity_weight_for_map(getattr(map_setting, "map_type", "")))),
        "ao_output_min": float(getattr(map_setting, "ao_output_min", constants.DEFAULT_AO_OUTPUT_MIN)),
        "ao_output_max": float(getattr(map_setting, "ao_output_max", 1.0)),
        "ao_diffusion_quality": str(getattr(map_setting, "ao_diffusion_quality", constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM)),
        "ao_diffusion_clearance_scale": float(getattr(map_setting, "ao_diffusion_clearance_scale", 0.2)),
        "ao_diffusion_clearance_exponent": float(getattr(map_setting, "ao_diffusion_clearance_exponent", 2.0)),
        "curvature_scale": float(getattr(map_setting, "curvature_scale", 1.0)),
        "curvature_tonemapping_min": float(getattr(map_setting, "curvature_tonemapping_min", 0.0)),
        "curvature_tonemapping_max": float(getattr(map_setting, "curvature_tonemapping_max", 1.0)),
        "curvature_distance": float(getattr(map_setting, "curvature_distance", 0.0)),
        "curvature_relative_to_bounding_box": bool(getattr(map_setting, "curvature_relative_to_bounding_box", False)),
        "curvature_secondary_rays": int(getattr(map_setting, "curvature_secondary_rays", 64)),
        "curvature_detect_folds": bool(getattr(map_setting, "curvature_detect_folds", False)),
        "curvature_self_intersection": str(getattr(map_setting, "curvature_self_intersection", "GROUP")),
        "curvature_auto_tonemapping": bool(getattr(map_setting, "curvature_auto_tonemapping", False)),
        "curvature_value_min": float(getattr(map_setting, "curvature_value_min", -1.0)),
        "curvature_value_max": float(getattr(map_setting, "curvature_value_max", 1.0)),
        "curvature_method": str(getattr(map_setting, "curvature_method", "NORMAL_DERIVATIVE")),
        "soften_override": bool(getattr(map_setting, "soften_override", False)),
        "soften": float(getattr(map_setting, "soften", constants.DEFAULT_SOFTEN)),
        "thickness_distance": float(getattr(map_setting, "thickness_distance", 0.0)),
        "thickness_min_distance": float(getattr(map_setting, "thickness_min_distance", -1.0)),
        "thickness_scale": float(getattr(map_setting, "thickness_scale", 1.0)),
        "thickness_gamma": float(getattr(map_setting, "thickness_gamma", 1.0)),
        "thickness_ignore_groups": bool(getattr(map_setting, "thickness_ignore_groups", False)),
        "thickness_normalization": bool(getattr(map_setting, "thickness_normalization", False)),
        "thickness_log_response": bool(getattr(map_setting, "thickness_log_response", False)),
        "density_auto_levels": bool(getattr(map_setting, "density_auto_levels", False)),
        "density_auto_levels_per_group": bool(getattr(map_setting, "density_auto_levels_per_group", True)),
        "id_source": str(getattr(map_setting, "id_source", constants.MAP_ID_SOURCE_OBJECT)),
        "position_normalization": map_position_normalization(map_setting),
        "relative_to_bounding_box": bool(getattr(map_setting, "relative_to_bounding_box", True)),
        "height_inner_distance": float(getattr(map_setting, "height_inner_distance", 0.0)),
        "height_outer_distance": float(getattr(map_setting, "height_outer_distance", 0.0)),
        "height_dither": bool(getattr(map_setting, "height_dither", False)),
    }


def supported_map_type_items(project: MasterBakerBakeProject):
    return list(constants.MAP_TYPE_ITEMS)


def _add_map_item(collection):
    if hasattr(collection, "add"):
        return collection.add()
    item = types.SimpleNamespace()
    collection.append(item)
    return item


def resolve_active_index(active_index: int, item_count: int) -> int | None:
    if item_count <= 0:
        return None
    return min(max(active_index, 0), item_count - 1)


def peek_active_project(scene) -> MasterBakerBakeProject | None:
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None:
        return None
    index = resolve_active_index(settings.active_project_index, len(settings.projects))
    if index is None:
        return None
    return settings.projects[index]


def peek_active_group(project: MasterBakerBakeProject) -> MasterBakerBakeGroup | None:
    index = resolve_active_index(project.active_group_index, len(project.groups))
    if index is None:
        return None
    return project.groups[index]


def get_active_project(scene) -> MasterBakerBakeProject | None:
    settings = getattr(scene, "fyr_baker_settings", None)
    if settings is None or not settings.projects:
        return None
    index = resolve_active_index(settings.active_project_index, len(settings.projects))
    if index is None:
        return None
    return settings.projects[index]


def get_active_group(project: MasterBakerBakeProject) -> MasterBakerBakeGroup | None:
    if not project.groups:
        return None
    index = resolve_active_index(project.active_group_index, len(project.groups))
    if index is None:
        return None
    return project.groups[index]


def get_active_texture_set(project: MasterBakerBakeProject):
    texture_sets = getattr(project, "texture_sets", None)
    if not texture_sets:
        return None
    index = resolve_active_index(getattr(project, "active_texture_set_index", 0), len(texture_sets))
    if index is None:
        return None
    return texture_sets[index]


def find_texture_set(project: MasterBakerBakeProject, name: str):
    target = (name or "").strip()
    if not target:
        return None
    for texture_set in getattr(project, "texture_sets", []):
        if str(getattr(texture_set, "name", "") or "").strip() == target:
            return texture_set
    return None


def ensure_texture_set(project: MasterBakerBakeProject, name: str):
    """Find or create the texture-set entry for `name` (the group link key)."""
    key = (name or "").strip()
    if not key:
        return None
    existing = find_texture_set(project, key)
    if existing is not None:
        return existing
    texture_set = project.texture_sets.add()
    texture_set.name = key  # fires _texture_set_identity_rename -> seeds _identity_name
    return texture_set


def reconcile_texture_sets(project: MasterBakerBakeProject) -> int:
    """Ensure every set name referenced by a group has a texture-set entry.

    Auto-heals projects whose groups were named by the auto-build/suffix ops (which set
    group.texture_set_name without creating the collection entry). Returns the count added.
    """
    added = 0
    for group in getattr(project, "groups", []):
        key = (getattr(group, "texture_set_name", "") or "").strip()
        if key and find_texture_set(project, key) is None:
            ensure_texture_set(project, key)
            added += 1
    return added


def _blend_file_stem() -> str:
    path = getattr(getattr(bpy, "data", None), "filepath", "") or ""
    return Path(path).stem.strip() if path else ""


def _texture_set_material_name(project: MasterBakerBakeProject, set_key: str) -> str:
    """First real material found on a low mesh of any group in this texture set.

    Transient "preview on low" materials are skipped — otherwise an active map
    preview would leak the internal preview-material name into output filenames
    (and falsely satisfy the "assign a material" validation).
    """
    for group in getattr(project, "groups", []):
        if (getattr(group, "texture_set_name", "") or "").strip() != (set_key or "").strip():
            continue
        role_state = group_role_assignments_state(group)
        for slot in getattr(role_state, "low_meshes", []):
            obj = getattr(slot, "object_ref", None)
            for mat_slot in getattr(obj, "material_slots", []) or []:
                mat = getattr(mat_slot, "material", None)
                name = getattr(mat, "name", "") if mat is not None else ""
                if name and not name.startswith(constants.PREVIEW_MATERIAL_NAME_PREFIX):
                    return str(name)
    return ""


def texture_set_effective_name(project: MasterBakerBakeProject, texture_set) -> str:
    """Resolve the output file token for a texture set from its name_mode.

    The set's ``name`` remains the stable link key that groups reference; only the
    OUTPUT token changes with the mode, so switching mode never breaks group links.
    Any mode falls back to the stored name when its source is unavailable (unsaved
    .blend, no material) so outputs always have a sensible name.
    """
    stored = str(getattr(texture_set, "name", "") or "").strip()
    mode = str(getattr(texture_set, "name_mode", constants.TEXTURE_SET_NAME_CUSTOM) or "")
    if mode == constants.TEXTURE_SET_NAME_BLEND_FILE:
        return _blend_file_stem() or stored
    if mode == constants.TEXTURE_SET_NAME_MATERIAL:
        return _texture_set_material_name(project, stored) or stored
    return stored


def resolve_texture_set_output_name(project: MasterBakerBakeProject, set_key: str) -> str | None:
    """Effective output token for a group's texture-set link key (or None)."""
    key = (set_key or "").strip()
    if not key:
        return None
    texture_set = find_texture_set(project, key)
    if texture_set is None:
        return key
    return texture_set_effective_name(project, texture_set) or key


def summarize_group_roles(group: MasterBakerBakeGroup):
    metadata_state = group_metadata_state(group)
    role_state = group_role_assignments_state(group)
    projection_state = group_projection_settings_state(group)
    cage_object = getattr(projection_state, "custom_cage", None)
    return {
        "low_count": len(getattr(role_state, "low_meshes", [])),
        "high_count": len(effective_high_mesh_slots(group)),
        "configured_high_count": len(getattr(role_state, "high_meshes", [])),
        "use_low_as_high": bool(getattr(role_state, "use_low_as_high", False)),
        "has_custom_cage": cage_object is not None,
        "custom_cage_name": getattr(cage_object, "name", "") if cage_object is not None else "",
        "cage_mode": getattr(projection_state, "cage_mode", ""),
        "cage_offset": float(getattr(projection_state, "cage_offset", 0.0)),
        "id_collection_name": (getattr(metadata_state, "id_collection_name", "") or "").strip(),
        "id_color_set_name": (getattr(metadata_state, "id_color_set_name", "") or "").strip(),
    }


def peek_active_low_slot(group):
    role_state = group_role_assignments_state(group)
    slots = getattr(role_state, "low_meshes", [])
    index = resolve_active_index(getattr(role_state, "low_mesh_index", 0), len(slots))
    if index is None:
        return None
    return slots[index]


def reset_latest_outputs(project: MasterBakerBakeProject) -> None:
    project.latest_outputs.clear()
    project.active_output_index = 0


def reset_runtime_state(project: MasterBakerBakeProject) -> None:
    project.last_progress_percent = 0.0
    project.last_stage_progress_percent = -1.0
    project.last_active_group = ""
    project.last_active_map = ""
    project.last_warning_count = 0
    project.last_error_count = 0
    project.last_warning_summary = ""
    project.last_error_summary = ""


def peek_latest_output(project: MasterBakerBakeProject, index: int):
    if index < 0 or index >= len(project.latest_outputs):
        return None
    return project.latest_outputs[index]


def summarize_latest_output(project: MasterBakerBakeProject, index: int) -> str:
    output = peek_latest_output(project, index)
    if output is None:
        return "None"
    label = output.display_name or Path(output.file_path).name or output.file_path or "Untitled"
    # Report the position within the de-duplicated set so the count matches the
    # visible outputs list and the next/previous navigation.
    primaries = unique_latest_output_indices(project)
    total = len(primaries) or len(project.latest_outputs)
    position = index
    if index in primaries:
        position = primaries.index(index)
    else:
        key = str(getattr(output, "file_path", "") or "").strip().casefold()
        if key:
            for i, idx in enumerate(primaries):
                other = str(getattr(project.latest_outputs[idx], "file_path", "") or "").strip().casefold()
                if other == key:
                    position = i
                    break
    return f"{position + 1}/{total}: {label}"


def resolve_latest_output_index(project: MasterBakerBakeProject, index: int | None = None) -> int | None:
    if not project.latest_outputs:
        return None
    if index is None:
        index = project.active_output_index
    return resolve_active_index(index, len(project.latest_outputs))


def unique_latest_output_indices(project: MasterBakerBakeProject) -> list[int]:
    """First index per distinct output file, matching MASTER_BAKER_UL_outputs.

    A combined texture set records one entry per (group x map) that all write the
    same atlas file, so the raw list holds each file N_groups times. Navigation
    should step over the same de-duplicated set the outputs list displays.
    """
    seen: set[str] = set()
    indices: list[int] = []
    for index, out in enumerate(getattr(project, "latest_outputs", [])):
        key = str(getattr(out, "file_path", "") or "").strip().casefold()
        if key:
            if key in seen:
                continue
            seen.add(key)
        indices.append(index)
    return indices


def cycle_latest_output_index(project: MasterBakerBakeProject, step: int) -> int | None:
    current_index = resolve_latest_output_index(project)
    if current_index is None:
        return None
    primaries = unique_latest_output_indices(project)
    if not primaries:
        return None
    outputs = project.latest_outputs
    current_key = ""
    if 0 <= current_index < len(outputs):
        current_key = str(getattr(outputs[current_index], "file_path", "") or "").strip().casefold()
    # Locate the current output within the de-duplicated set. If it is a hidden
    # duplicate row, fall back to the primary index sharing its file path.
    if current_index in primaries:
        position = primaries.index(current_index)
    else:
        position = 0
        if current_key:
            for i, idx in enumerate(primaries):
                key = str(getattr(outputs[idx], "file_path", "") or "").strip().casefold()
                if key == current_key:
                    position = i
                    break
    return primaries[(position + step) % len(primaries)]


def find_latest_output_index(
    project: MasterBakerBakeProject,
    *,
    map_uuid: str = "",
    map_type: str = "",
    group_name: str = "",
    output_suffix: str = "",
    strict: bool = False,
) -> int | None:
    normalized_map_uuid = str(map_uuid or "").strip()
    normalized_map_type = str(map_type or "").strip().upper()
    normalized_group_name = str(group_name or "").strip().casefold()
    normalized_suffix = str(output_suffix or "").strip()
    if normalized_map_uuid:
        fallback_index = None
        type_group_match = None
        for index, item in enumerate(project.latest_outputs):
            item_map_uuid = str(getattr(item, "map_uuid", "") or "").strip()
            if item_map_uuid != normalized_map_uuid:
                continue
            if fallback_index is None:
                fallback_index = index
            item_group_name = str(getattr(item, "group_name", "") or "").strip().casefold()
            if normalized_group_name and item_group_name != normalized_group_name:
                continue
            if not normalized_suffix:
                return index
            item_suffix = str(getattr(item, "output_suffix", "") or "").strip()
            if item_suffix == normalized_suffix:
                return index
            if type_group_match is None:
                type_group_match = index
        if strict and (normalized_group_name or normalized_suffix):
            return None
        return type_group_match if type_group_match is not None else fallback_index
    fallback_index = None
    type_group_match = None  # best type+group match ignoring suffix (backward-compat fallback)
    for index, item in enumerate(project.latest_outputs):
        # A tracked output answers to BOTH the raw stack type it is stored under
        # (``MATERIAL``, ``SCENE_LIGHTING``) and its effective/backend type
        # (``MATERIAL_ALBEDO``, ``LIGHTING``): the Outputs panel looks it up by the
        # row's raw type while the PBR preview looks the same file up by channel.
        item_map_types = {
            str(getattr(item, "map_type", "") or "").strip().upper(),
            str(getattr(item, "effective_map_type", "") or "").strip().upper(),
        }
        item_map_types.discard("")
        if normalized_map_type and normalized_map_type not in item_map_types:
            continue
        item_group_name = str(getattr(item, "group_name", "") or "").strip().casefold()
        group_ok = not normalized_group_name or item_group_name == normalized_group_name
        if not group_ok:
            if fallback_index is None:
                fallback_index = index
            continue
        if not normalized_suffix:
            return index
        item_suffix = str(getattr(item, "output_suffix", "") or "").strip()
        if item_suffix == normalized_suffix:
            return index
        if type_group_match is None:
            type_group_match = index
    # Suffix requested but no exact match – fall back to type+group match for backward-compat
    # In strict mode, skip the fallback so duplicate map types don't share a thumbnail.
    if strict and normalized_suffix:
        return None
    return type_group_match if type_group_match is not None else fallback_index


def find_latest_output_index_by_map(
    project: MasterBakerBakeProject,
    map_type: str,
    group_name: str = "",
    output_suffix: str = "",
    *,
    map_uuid: str = "",
    strict: bool = False,
) -> int | None:
    return find_latest_output_index(
        project,
        map_uuid=map_uuid,
        map_type=map_type,
        group_name=group_name,
        output_suffix=output_suffix,
        strict=strict,
    )


def resolve_output_selection_index(
    project: MasterBakerBakeProject,
    *,
    output_index: int = -1,
    map_uuid: str = "",
    map_type: str = "",
    group_name: str = "",
    output_suffix: str = "",
    strict: bool = False,
) -> int | None:
    def _legacy_unambiguous_index(
        normalized_map_type: str,
        normalized_group_name: str,
    ) -> int | None:
        same_type_maps = [
            item
            for item in getattr(project, "maps", [])
            if not getattr(item, "is_add_phantom", False)
            and str(getattr(item, "map_type", "") or "").strip().upper() == normalized_map_type
        ]
        if len(same_type_maps) != 1:
            return None
        matches = []
        for index, item in enumerate(getattr(project, "latest_outputs", [])):
            item_map_type = str(getattr(item, "map_type", "") or "").strip().upper()
            if item_map_type != normalized_map_type:
                continue
            item_group_name = str(getattr(item, "group_name", "") or "").strip().casefold()
            if normalized_group_name and item_group_name != normalized_group_name:
                continue
            matches.append(index)
            if len(matches) > 1:
                return None
        return matches[0] if matches else None

    if output_index >= 0:
        return resolve_latest_output_index(project, output_index)
    normalized_map_uuid = str(map_uuid or "").strip()
    if normalized_map_uuid:
        map_setting = find_map_setting_by_uuid(project, normalized_map_uuid)
        if map_setting is None:
            return None
        normalized_group_name = str(group_name or "").strip().casefold()
        normalized_map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
        effective_suffix = effective_map_output_suffix(project, map_setting) or ""
        resolved_index = find_latest_output_index(
            project,
            map_uuid=normalized_map_uuid,
            group_name=group_name,
            output_suffix=effective_suffix,
            strict=strict,
        )
        if resolved_index is not None:
            return resolved_index
        if effective_suffix:
            return find_latest_output_index_by_map(
                project,
                normalized_map_type,
                group_name,
                effective_suffix,
                strict=strict,
            )
        return _legacy_unambiguous_index(normalized_map_type, normalized_group_name)
    if output_suffix or map_type:
        map_setting = resolve_map_setting(project, map_type=map_type, output_suffix=output_suffix)
        if map_setting is not None and output_suffix:
            return find_latest_output_index_by_map(
                project,
                str(getattr(map_setting, "map_type", "") or ""),
                group_name,
                effective_map_output_suffix(project, map_setting) or "",
                strict=strict,
            )
    if map_type:
        return find_latest_output_index_by_map(project, map_type, group_name, output_suffix, strict=strict)
    return resolve_latest_output_index(project)


class _LegacyMappedStateAdapter:
    __slots__ = ("_owner",)

    _ATTRS: dict[str, str] = {}

    def __init__(self, owner):
        object.__setattr__(self, "_owner", owner)

    def __getattr__(self, name):
        mapped_name = self._ATTRS.get(name)
        if mapped_name is None:
            raise AttributeError(name)
        return getattr(self._owner, mapped_name)

    def __setattr__(self, name, value):
        mapped_name = self._ATTRS.get(name)
        if mapped_name is None:
            raise AttributeError(name)
        setattr(self._owner, mapped_name, value)


class _LegacyImageEditorStateAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "channel_mode": "image_editor_channel_mode",
        "mip_level": "image_editor_mip_level",
        "inspect_expanded": "image_editor_inspect_expanded",
        "job_status_expanded": "image_editor_job_status_expanded",
        "compare_enabled": "image_editor_compare_enabled",
        "compare_active_slot": "image_editor_compare_active_slot",
        "compare_a_index": "image_editor_compare_a_index",
        "compare_b_index": "image_editor_compare_b_index",
    }

class _LegacyUiStateAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "map_catalog_search": "map_catalog_search",
        "sidebar_primary_section": "sidebar_primary_section",
        "sidebar_selected_sections": "sidebar_selected_sections",
        "bake_panel_section": "bake_panel_section",
        "setup_project_expanded": "setup_project_expanded",
        "cage_debug_expanded": "cage_debug_expanded",
        "skew_debug_expanded": "skew_debug_expanded",
        "viewport_low_reference_expanded": "viewport_low_reference_expanded",
        "viewport_high_reference_expanded": "viewport_high_reference_expanded",
        "viewport_cage_overlay_expanded": "viewport_cage_overlay_expanded",
        "viewport_debug_expanded": "viewport_debug_expanded",
        "selected_group_cage_offset": "selected_group_cage_offset",
        "selected_low_cage_offset": "selected_low_cage_offset",
    }


class _LegacyPreviewSessionStateAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "preview_on_low_active": "preview_on_low_active",
        "preview_on_low_project_name": "preview_on_low_project_name",
        "preview_on_low_group_name": "preview_on_low_group_name",
        "preview_on_low_map_uuid": "preview_on_low_map_uuid",
        "preview_on_low_map_type": "preview_on_low_map_type",
        "preview_on_low_map_index": "preview_on_low_map_index",
        "preview_on_low_output_suffix": "preview_on_low_output_suffix",
        "preview_on_low_scope": "preview_on_low_scope",
        "preview_pbr_on_low_active": "preview_pbr_on_low_active",
        "preview_pbr_on_low_project_name": "preview_pbr_on_low_project_name",
        "preview_pbr_on_low_group_name": "preview_pbr_on_low_group_name",
        "pbr_preview_normal_source": "pbr_preview_normal_source",
        "pbr_preview_ao_strength": "pbr_preview_ao_strength",
        "preview_environment_rotation": "preview_environment_rotation",
        "preview_environment_strength": "preview_environment_strength",
        "preview_environment_show_background": "preview_environment_show_background",
        "live_bake_active": "live_bake_active",
        "live_bake_project_name": "live_bake_project_name",
        "live_bake_project_index": "live_bake_project_index",
        "live_normal_preview_active": "live_normal_preview_active",
        "live_normal_preview_scene_name": "live_normal_preview_scene_name",
        "live_normal_preview_project_name": "live_normal_preview_project_name",
        "live_normal_preview_group_name": "live_normal_preview_group_name",
        "live_normal_preview_output_path": "live_normal_preview_output_path",
        "preview_on_low_restore_show_cage_overlay": "preview_on_low_restore_show_cage_overlay",
        "preview_on_low_restore_show_error_heatmap": "preview_on_low_restore_show_error_heatmap",
        "preview_on_low_restore_show_ray_miss_debug": "preview_on_low_restore_show_ray_miss_debug",
        "preview_on_low_restore_viewport_state": "preview_on_low_restore_viewport_state",
        "preview_on_low_restore_high_visibility": "preview_on_low_restore_high_visibility",
        "material_ab_compare_active": "material_ab_compare_active",
        "material_ab_compare_side": "material_ab_compare_side",
        "material_ab_compare_project_name": "material_ab_compare_project_name",
        "material_ab_compare_restore_visibility": "material_ab_compare_restore_visibility",
        "material_ab_compare_had_preview": "material_ab_compare_had_preview",
    }


class _LegacyViewportOverlaySettingsAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "show_cage_overlay": "show_cage_overlay",
        "cage_preview_scope": "cage_preview_scope",
        "show_cage_surface": "show_cage_surface",
        "cage_surface_color": "cage_surface_color",
        "show_cage_wireframe": "show_cage_wireframe",
        "cage_wireframe_color": "cage_wireframe_color",
        "show_skew_debug": "show_skew_debug",
        "show_ray_miss_debug": "show_ray_miss_debug",
        "skew_debug_length": "skew_debug_length",
        "skew_debug_constant_screen_size": "skew_debug_constant_screen_size",
        "show_error_heatmap": "show_error_heatmap",
        "heatmap_inside_color": "heatmap_inside_color",
        "heatmap_outside_color": "heatmap_outside_color",
        "cage_opacity": "cage_opacity",
        "cage_surface_opacity": "cage_surface_opacity",
        "cage_wireframe_opacity": "cage_wireframe_opacity",
    }


class _LegacyBakeGroupMetadataAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "name": "name",
        "texture_set_name": "texture_set_name",
        "id_collection_name": "id_collection_name",
        "id_color_set_name": "id_color_set_name",
    }


class _LegacyBakeGroupCollectionsAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "group_collection": "group_collection",
        "low_collection": "low_collection",
        "high_collection": "high_collection",
        "cage_collection": "cage_collection",
    }


class _LegacyBakeGroupRoleAssignmentsAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "low_meshes": "low_meshes",
        "low_mesh_index": "low_mesh_index",
        "high_meshes": "high_meshes",
        "high_mesh_index": "high_mesh_index",
        "use_low_as_high": "use_low_as_high",
    }


class _LegacyBakeGroupProjectionSettingsAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "uv_layer_name": "uv_layer_name",
        "cage_mode": "cage_mode",
        "custom_cage": "custom_cage",
        "cage_offset": "cage_offset",
        "projection_rear_distance": "projection_rear_distance",
        "average_normals": "average_normals",
        "ignore_backface": "ignore_backface",
        "match_by_isolation": "match_by_isolation",
    }


class _LegacyBakeGroupPaintProjectionSettingsAdapter(_LegacyMappedStateAdapter):
    __slots__ = ()

    _ATTRS = {
        "paint_offset_image": "paint_offset_image",
        "paint_offset_scale": "paint_offset_scale",
        "paint_skew_image": "paint_skew_image",
        "paint_skew": "paint_skew",
    }


def scene_ui_state(scene_settings: MasterBakerSceneSettings):
    nested_state = getattr(scene_settings, "ui_state", None)
    if nested_state is not None:
        return nested_state
    return _LegacyUiStateAdapter(scene_settings)


def preview_session_state(scene_settings: MasterBakerSceneSettings):
    nested_state = getattr(scene_settings, "preview_session", None)
    if nested_state is not None:
        return nested_state
    return _LegacyPreviewSessionStateAdapter(scene_settings)


def overlay_settings_state(scene_settings: MasterBakerSceneSettings):
    nested_state = getattr(scene_settings, "overlay_settings", None)
    if nested_state is not None:
        return nested_state
    return _LegacyViewportOverlaySettingsAdapter(scene_settings)


def image_editor_state(scene_settings: MasterBakerSceneSettings):
    nested_state = getattr(scene_settings, "image_editor", None)
    if nested_state is not None:
        return nested_state
    return _LegacyImageEditorStateAdapter(scene_settings)


def group_metadata_state(group: MasterBakerBakeGroup):
    nested_state = getattr(group, "metadata", None)
    if nested_state is not None:
        _sync_group_metadata_state(group)
        return nested_state
    return _LegacyBakeGroupMetadataAdapter(group)


def group_collections_state(group: MasterBakerBakeGroup):
    nested_state = getattr(group, "collections", None)
    if nested_state is not None:
        _sync_group_collections_state(group)
        return nested_state
    return _LegacyBakeGroupCollectionsAdapter(group)


#: Groups already synced in the current read-only pass (see role_sync_once_per_pass),
#: or None outside one.
_ROLE_SYNC_PASS: set[int] | None = None
#: Bumped each time an outermost pass starts, so per-pass memos elsewhere
#: (cage_session.resolve_preview_targets) can tell one pass from the next.
_ROLE_SYNC_PASS_SERIAL = 0


class role_sync_once_per_pass:
    """Sync each group's role slots at most once while this block runs.

    The viewport overlay reads a group's role state ~5 times per group per frame to
    build its cache keys, and every read re-ran the flat-to-nested mirror check (dedupe
    scan plus slot compare): ~150 checks a frame at 30 groups, most of the overlay's
    per-frame cost. Nothing edits the slots during a draw, so the first sync of each
    group stands for the rest of the pass. Re-entrant: an inner block joins the outer.
    """

    def __enter__(self):
        global _ROLE_SYNC_PASS, _ROLE_SYNC_PASS_SERIAL
        self._outer = _ROLE_SYNC_PASS is not None
        if not self._outer:
            _ROLE_SYNC_PASS = set()
            _ROLE_SYNC_PASS_SERIAL += 1
        return self

    def __exit__(self, *_exc):
        global _ROLE_SYNC_PASS
        if not self._outer:
            _ROLE_SYNC_PASS = None
        return False


def group_role_assignments_state(group: MasterBakerBakeGroup):
    nested_state = getattr(group, "role_assignments", None)
    if nested_state is not None:
        synced = _ROLE_SYNC_PASS
        if synced is None:
            _sync_group_role_assignments_state(group)
        else:
            key = _resolution_owner_key(group)
            if key not in synced:
                synced.add(key)
                _sync_group_role_assignments_state(group)
        return nested_state
    return _LegacyBakeGroupRoleAssignmentsAdapter(group)


def group_uses_low_as_high(group) -> bool:
    """Return the explicit per-group low-to-low source intent."""
    role_state = group_role_assignments_state(group)
    return bool(getattr(role_state, "use_low_as_high", getattr(group, "use_low_as_high", False)))


def effective_high_mesh_slots(group):
    """Resolve projected source slots without mutating configured role membership."""
    role_state = group_role_assignments_state(group)
    attr_name = "low_meshes" if bool(getattr(role_state, "use_low_as_high", False)) else "high_meshes"
    return getattr(role_state, attr_name, [])


def group_ao_non_caster_objects(group) -> list[str]:
    """Object names of *group*'s high meshes with Casts AO off (job: ao_non_caster_objects).

    The slot toggle, or Substance's "_ignorebf" token in the object name. Use Low as High
    projects from the lows, which carry no such toggle, so it yields none.
    """
    if group_uses_low_as_high(group):
        return []
    names: set[str] = set()
    role_state = group_role_assignments_state(group)
    for collection in (getattr(role_state, "high_meshes", None), getattr(group, "high_meshes", None)):
        for slot in collection or []:
            obj = getattr(slot, "object_ref", None)
            if obj is not None and not slot_casts_ao(slot):
                names.add(str(obj.name))
    return sorted(names)


def slot_casts_ao(slot) -> bool:
    """Effective Casts AO of a High slot: its toggle (an _ignorebf name does not change it)."""
    return bool(getattr(slot, "casts_ao", True))


def effective_high_mesh_objects(group) -> list:
    objects = []
    for slot in effective_high_mesh_slots(group):
        obj = getattr(slot, "object_ref", None)
        if obj is None or getattr(obj, "type", "MESH") != "MESH":
            continue
        if any(existing is obj for existing in objects):
            continue
        objects.append(obj)
    return objects


def group_projection_settings_state(group: MasterBakerBakeGroup):
    nested_state = getattr(group, "projection_settings", None)
    if nested_state is not None:
        _sync_group_projection_state(group)
        return nested_state
    return _LegacyBakeGroupProjectionSettingsAdapter(group)


def group_paint_projection_settings_state(group: MasterBakerBakeGroup):
    nested_state = getattr(group, "paint_projection_settings", None)
    if nested_state is not None:
        _sync_group_paint_projection_state(group)
        return nested_state
    return _LegacyBakeGroupPaintProjectionSettingsAdapter(group)


def map_normal_settings_state(map_item):
    nested = getattr(map_item, "normal_settings", None)
    if nested is not None:
        _sync_map_normal_settings(map_item)
        return nested
    return map_item


def map_ao_settings_state(map_item):
    nested = getattr(map_item, "ao_settings", None)
    if nested is not None:
        _sync_map_ao_settings(map_item)
        return nested
    return map_item


def map_env_light_settings_state(map_item):
    nested = getattr(map_item, "env_light_settings", None)
    if nested is not None:
        _sync_map_env_light_settings(map_item)
        return nested
    return map_item


def map_curvature_settings_state(map_item):
    nested = getattr(map_item, "curvature_settings", None)
    if nested is not None:
        _sync_map_curvature_settings(map_item)
        return nested
    return map_item


def map_thickness_settings_state(map_item):
    nested = getattr(map_item, "thickness_settings", None)
    if nested is not None:
        normalized_map_type = str(getattr(map_item, "map_type", "") or "").strip().upper()
        if normalized_map_type == constants.MAP_DENSITY:
            _sync_map_density_settings(map_item)
        else:
            _sync_map_thickness_settings(map_item)
        return nested
    return map_item


def map_id_settings_state(map_item):
    nested = getattr(map_item, "id_settings", None)
    if nested is not None:
        _sync_map_id_settings(map_item)
        return nested
    return map_item


def map_position_settings_state(map_item):
    nested = getattr(map_item, "position_settings", None)
    if nested is not None:
        _sync_map_position_settings(map_item)
        return nested
    return map_item


def map_height_settings_state(map_item):
    nested = getattr(map_item, "height_settings", None)
    if nested is not None:
        _sync_map_height_settings(map_item)
        return nested
    return map_item


def resolve_settings_surface(scene_settings: MasterBakerSceneSettings, prop_name: str):
    if scene_settings is None:
        return None
    normalized_prop_name = str(prop_name or "").strip()
    if not normalized_prop_name:
        return None
    if hasattr(scene_settings, normalized_prop_name):
        return scene_settings

    ui_state = scene_ui_state(scene_settings)
    if hasattr(ui_state, normalized_prop_name):
        return ui_state

    preview_state = preview_session_state(scene_settings)
    if hasattr(preview_state, normalized_prop_name):
        return preview_state

    overlay_state = overlay_settings_state(scene_settings)
    if hasattr(overlay_state, normalized_prop_name):
        return overlay_state

    editor_state = image_editor_state(scene_settings)
    if hasattr(editor_state, normalized_prop_name):
        return editor_state

    return None


def compare_slot_index(scene_settings: MasterBakerSceneSettings, slot: str) -> int:
    editor_state = image_editor_state(scene_settings)
    if slot == "B":
        return editor_state.compare_b_index
    return editor_state.compare_a_index


def summarize_compare_slot(project: MasterBakerBakeProject, scene_settings: MasterBakerSceneSettings, slot: str) -> str:
    index = compare_slot_index(scene_settings, slot)
    if index < 0:
        return f"{slot}: Empty"
    output = peek_latest_output(project, index)
    if output is None:
        return f"{slot}: Missing #{index + 1}"
    label = output.display_name or Path(output.file_path).name or output.file_path or "Untitled"
    return f"{slot}: {index + 1}/{len(project.latest_outputs)}: {label}"


def summarize_compare_state(project: MasterBakerBakeProject, scene_settings: MasterBakerSceneSettings) -> str:
    editor_state = image_editor_state(scene_settings)
    status = "Enabled" if editor_state.compare_enabled else "Disabled"
    active = editor_state.compare_active_slot
    return f"Compare {status} | Active Compare: {active} | {summarize_compare_slot(project, scene_settings, 'A')} | {summarize_compare_slot(project, scene_settings, 'B')}"


def set_compare_slot_index(scene_settings: MasterBakerSceneSettings, slot: str, index: int) -> None:
    editor_state = image_editor_state(scene_settings)
    if slot == "B":
        editor_state.compare_b_index = index
        return
    editor_state.compare_a_index = index


def swap_compare_slots(scene_settings: MasterBakerSceneSettings) -> None:
    editor_state = image_editor_state(scene_settings)
    editor_state.compare_a_index, editor_state.compare_b_index = (
        editor_state.compare_b_index,
        editor_state.compare_a_index,
    )


def _migrate_scene_projects() -> None:
    data = getattr(bpy, "data", None)
    scenes = getattr(data, "scenes", None) if data is not None else None
    if scenes is None:
        return
    for scene in scenes:
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None:
            continue
        for project in getattr(settings, "projects", []):
            ensure_default_maps(project)
            for group in getattr(project, "groups", []):
                _sync_group_metadata_state(group)
                _sync_group_collections_state(group)
                _sync_group_role_assignments_from_flat(group, force=True)
                _sync_group_projection_state(group)
                _sync_group_paint_projection_state(group)


def _adopt_legacy_cage_modes_on_load(_filepath=None) -> None:
    # Most cage code reads the flat group.cage_mode directly, before any nested sync runs,
    # so an opened file has to pin its legacy cage modes up front.
    for scene in getattr(bpy.data, "scenes", ()):
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None:
            continue
        for project in getattr(settings, "projects", ()):
            # Before anything reads the flat cage modes, and before a new group can be
            # added under an old stamp (and be mistaken for a legacy one next load).
            migrate_project_schema(project)
            for group in getattr(project, "groups", ()):
                nested_state = getattr(group, "projection_settings", None)
                if nested_state is not None:
                    _adopt_stored_legacy_cage_mode(group, nested_state)


#: The load_post callback actually appended (wrapped in @persistent at register time).
_LOAD_POST_HANDLER = None


def register():
    global _LOAD_POST_HANDLER
    for cls in CLASSES:
        safe_register_class(cls)

    bpy.types.Scene.fyr_baker_settings = bpy.props.PointerProperty(type=MasterBakerSceneSettings)
    _migrate_scene_projects()
    handlers = bpy.app.handlers
    _LOAD_POST_HANDLER = handlers.persistent(_adopt_legacy_cage_modes_on_load)
    if _LOAD_POST_HANDLER not in handlers.load_post:
        handlers.load_post.append(_LOAD_POST_HANDLER)
    # Enable the Marmoset curvature response stack once at addon load so every
    # backend worker inherits the mode flags at spawn. The per-knob tuning VALUES flow
    # per-bake through the job payload (no env, no worker restart on a slider change).
    _apply_mm_calibration_mode_flags()


def unregister():
    global _LOAD_POST_HANDLER
    if _LOAD_POST_HANDLER is not None and _LOAD_POST_HANDLER in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_LOAD_POST_HANDLER)
    _LOAD_POST_HANDLER = None
    safe_remove_attr(bpy.types.Scene, "fyr_baker_settings")
    _PREVIEW_MAP_ITEMS_CACHE.clear()

    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
